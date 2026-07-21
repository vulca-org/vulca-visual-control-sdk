"""Gemini image generation provider.

Supports imageSize (512/1K/2K/4K) and aspectRatio via Google GenAI API.
"""
from __future__ import annotations

import asyncio
import base64
import io
import math
import os

from vulca.providers.base import ImageEditCapabilities, ImageProvider, ImageResult
from vulca.providers.retry import with_retry

# Gemini API uses named size tiers, not arbitrary pixel dimensions.
# Map pixel dimensions to the closest imageSize tier.
_SIZE_TIERS = [
    (512, "512"),
    (1024, "1K"),
    (2048, "2K"),
    (4096, "4K"),
]

# Supported aspect ratios (Gemini API).
_ASPECT_RATIOS = {
    "1:1", "1:4", "1:8", "2:3", "3:2", "3:4", "4:1",
    "4:3", "4:5", "5:4", "8:1", "9:16", "16:9", "21:9",
}


def _pixels_to_image_size(long_edge: int) -> str:
    """Map pixel dimension (long edge) to Gemini imageSize tier."""
    for threshold, tier in _SIZE_TIERS:
        if long_edge <= threshold:
            return tier
    return "4K"


def _dims_to_aspect_ratio(width: int, height: int) -> str:
    """Find the closest supported aspect ratio for given dimensions."""
    if width == height or width <= 0 or height <= 0:
        return "1:1"
    target = width / height
    best_ratio = "1:1"
    best_diff = float("inf")
    for ar in _ASPECT_RATIOS:
        a, b = ar.split(":")
        ratio = int(a) / int(b)
        diff = abs(ratio - target)
        if diff < best_diff:
            best_diff = diff
            best_ratio = ar
    return best_ratio


def _detect_mime_type(data: bytes) -> str:
    """Detect image mime type from magic bytes."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _build_visible_mask_reference(mask_bytes: bytes) -> bytes:
    """Render an alpha edit mask as visible black/white guidance for Gemini."""
    from PIL import Image

    with Image.open(io.BytesIO(mask_bytes)) as mask_img:
        alpha = mask_img.convert("RGBA").split()[-1]
        visible = alpha.point(lambda value: 255 if value < 128 else 0)
    rgb = Image.new("RGB", visible.size, (0, 0, 0))
    rgb.paste((255, 255, 255), mask=visible)
    buf = io.BytesIO()
    rgb.save(buf, format="PNG")
    return buf.getvalue()


def _iter_image_parts(response: object):
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            yield part


class GeminiImageProvider:
    """Image generation via Google Gemini API.

    Supports imageSize control (512/1K/2K/4K) and aspectRatio.
    Width/height params are mapped to the closest Gemini tier + ratio.
    """

    capabilities: frozenset[str] = frozenset({"raw_rgba", "multilingual_prompt"})

    def __init__(
        self,
        api_key: str = "",
        model: str = "gemini-3.1-flash-image-preview",
        timeout: int = 90,
    ):
        self.api_key = (
            api_key
            or os.environ.get("GOOGLE_API_KEY", "")
            or os.environ.get("GEMINI_API_KEY", "")
        )
        self.model = model
        self.timeout = timeout

    def edit_capabilities(self) -> ImageEditCapabilities:
        return ImageEditCapabilities(
            supports_edits=True,
            requires_mask_for_edits=True,
            supports_unmasked_edits=False,
            supports_masked_edits=True,
        )

    async def generate(
        self,
        prompt: str,
        *,
        tradition: str = "",
        subject: str = "",
        reference_image_b64: str = "",
        negative_prompt: str = "",
        seed: int | None = None,
        steps: int | None = None,
        cfg_scale: float | None = None,
        width: int = 1024,
        height: int = 1024,
        **kwargs,
    ) -> ImageResult:
        if not self.api_key:
            raise ValueError(
                "Gemini API key required. Set GOOGLE_API_KEY env var "
                "or pass api_key to GeminiImageProvider()."
            )

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)

        # Map width/height to Gemini imageSize + aspectRatio
        long_edge = max(width, height)
        image_size = kwargs.pop("image_size", None) or _pixels_to_image_size(long_edge)
        aspect_ratio = kwargs.pop("aspect_ratio", None) or _dims_to_aspect_ratio(width, height)

        # Skip prompt wrapping when caller provides a complete prompt
        # (e.g., LayerGenerateNode's "Digital design asset..." prompt)
        raw = kwargs.pop("raw_prompt", False)
        if raw:
            full_prompt = prompt
        else:
            full_prompt = self._build_prompt(prompt, tradition, subject, aspect_ratio, kwargs)
        if negative_prompt:
            full_prompt = f"{full_prompt}\n(avoid: {negative_prompt})"

        # Gemini has no diffusion sampler → steps / cfg_scale do not apply.
        _ = (steps, cfg_scale)

        contents: list = []
        if reference_image_b64:
            ref_bytes = base64.b64decode(reference_image_b64)
            ref_mime = _detect_mime_type(ref_bytes)
            contents.append(types.Part.from_bytes(data=ref_bytes, mime_type=ref_mime))
        contents.append(full_prompt)

        config_kwargs: dict = dict(
            response_modalities=["Text", "Image"],
            image_config=types.ImageConfig(
                image_size=image_size,
                aspect_ratio=aspect_ratio,
            ),
        )
        tools = kwargs.pop("tools", None)
        if tools:
            config_kwargs["tools"] = tools

        # Wire deterministic seed when caller supplied one. Older google-genai
        # builds may not expose the `seed` field on GenerateContentConfig
        # (TypeError on unknown kwarg); narrow the except to that case only so
        # pydantic ValidationError from malformed seed input still surfaces.
        if seed is not None:
            try:
                config = types.GenerateContentConfig(seed=seed, **config_kwargs)
            except TypeError:
                config = types.GenerateContentConfig(**config_kwargs)
        else:
            config = types.GenerateContentConfig(**config_kwargs)

        def _is_retryable(exc: Exception) -> bool:
            if isinstance(exc, asyncio.TimeoutError):
                return True
            # Retry on rate-limit (429), server error (500), or unavailable (503)
            status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            if status in (429, 500, 503):
                return True
            return False

        async def _call() -> object:
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(
                        client.models.generate_content,
                        model=self.model,
                        contents=contents,
                        config=config,
                    ),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"Gemini image generation timed out after {self.timeout}s")

        response = await with_retry(
            _call,
            max_retries=3,
            base_delay_ms=500,
            max_delay_ms=16_000,
            retryable_check=_is_retryable,
        )

        for part in _iter_image_parts(response):
            inline_data = getattr(part, "inline_data", None)
            mime_type = getattr(inline_data, "mime_type", "")
            if inline_data and mime_type.startswith("image/"):
                img_b64 = base64.b64encode(inline_data.data).decode()
                return ImageResult(
                    image_b64=img_b64,
                    mime=mime_type,
                    metadata={
                        "model": self.model,
                        "image_size": image_size,
                        "aspect_ratio": aspect_ratio,
                    },
                )

        # No image data — classify the failure before surfacing the error so
        # users get an actionable remediation hint instead of a generic
        # "no image data" message (codex 2026-04-23 audit).
        prompt_feedback = getattr(response, "prompt_feedback", None)
        block_reason = getattr(prompt_feedback, "block_reason", None) if prompt_feedback else None
        if block_reason:
            raise RuntimeError(
                f"Gemini blocked the request: {block_reason}. "
                f"Check content policy or tune prompt."
            )

        # Detect quota / billing blocks. Free-tier keys return a
        # `limit: 0` error for image gen endpoints (see billing memory note);
        # plus 429-style quota exhaustion on paid tiers.
        raw_text = ""
        try:
            raw_text = str(response)
        except Exception:
            raw_text = ""
        lowered = raw_text.lower()
        if (
            "quota" in lowered
            or "limit: 0" in lowered
            or "resource_exhausted" in lowered
            or "billing" in lowered
        ):
            raise RuntimeError(
                "Gemini quota exhausted or free tier blocked for image gen. "
                "Upgrade via aistudio.google.com/app/apikey or switch provider."
            )

        raise RuntimeError(
            "Gemini returned no image data "
            "(enable VULCA_DEBUG=1 for raw response inspection)"
        )

    async def inpaint_with_mask(
        self,
        *,
        image_path: str,
        mask_path: str,
        prompt: str,
        tradition: str = "default",
        size: str = "",
        quality: str | None = None,
        input_fidelity: str | None = None,
        output_format: str | None = None,
    ) -> ImageResult:
        if not self.api_key:
            raise ValueError(
                "Gemini API key required. Set GOOGLE_API_KEY env var "
                "or pass api_key to GeminiImageProvider()."
            )

        from google import genai
        from google.genai import types
        from PIL import Image

        _ = (quality, input_fidelity, output_format)
        with open(image_path, "rb") as image_fh:
            image_bytes = image_fh.read()
        with open(mask_path, "rb") as mask_fh:
            mask_bytes = mask_fh.read()
        visible_mask_bytes = _build_visible_mask_reference(mask_bytes)

        if size and "x" in size:
            try:
                width_text, height_text = size.lower().split("x", 1)
                width, height = int(width_text), int(height_text)
            except ValueError:
                with Image.open(image_path) as source_probe:
                    width, height = source_probe.size
        else:
            with Image.open(image_path) as source_probe:
                width, height = source_probe.size

        image_size = _pixels_to_image_size(max(width, height))
        aspect_ratio = _dims_to_aspect_ratio(width, height)
        full_prompt = (
            f"{prompt}\n\n"
            "Use the first image as the source crop. Use the second image as a "
            "visible binary edit mask rendered from the original RGBA mask: "
            "white mask pixels (original transparent mask pixels) mark the edit "
            "region, and black mask pixels (original opaque mask pixels) mark "
            "source context that should stay visually preserved. Repaint only "
            "the white edit region. Do not create a new scene outside the masked "
            "replacement area. The mask image is not part of the output: do not "
            "draw the mask, do not copy its white or black shapes, and do not "
            "leave mask-colored background behind."
        )
        if tradition and tradition != "default":
            full_prompt += (
                f"\nMaintain the {tradition.replace('_', ' ')} cultural tradition "
                "and technique."
            )

        client = genai.Client(api_key=self.api_key)
        contents = [
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=_detect_mime_type(image_bytes),
            ),
            types.Part.from_bytes(
                data=visible_mask_bytes,
                mime_type="image/png",
            ),
            full_prompt,
        ]
        config = types.GenerateContentConfig(
            response_modalities=["Text", "Image"],
            image_config=types.ImageConfig(
                image_size=image_size,
                aspect_ratio=aspect_ratio,
            ),
        )

        def _is_retryable(exc: Exception) -> bool:
            if isinstance(exc, asyncio.TimeoutError):
                return True
            status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            return status in (429, 500, 503)

        async def _call() -> object:
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(
                        client.models.generate_content,
                        model=self.model,
                        contents=contents,
                        config=config,
                    ),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"Gemini image edit timed out after {self.timeout}s")

        response = await with_retry(
            _call,
            max_retries=3,
            base_delay_ms=500,
            max_delay_ms=16_000,
            retryable_check=_is_retryable,
        )

        for part in _iter_image_parts(response):
            inline_data = getattr(part, "inline_data", None)
            mime_type = getattr(inline_data, "mime_type", "")
            if inline_data and mime_type.startswith("image/"):
                img_b64 = base64.b64encode(inline_data.data).decode()
                return ImageResult(
                    image_b64=img_b64,
                    mime=mime_type,
                    metadata={
                        "model": self.model,
                        "mode": "gemini_mask_adapter",
                        "image_size": image_size,
                        "aspect_ratio": aspect_ratio,
                    },
                )

        prompt_feedback = getattr(response, "prompt_feedback", None)
        block_reason = getattr(prompt_feedback, "block_reason", None) if prompt_feedback else None
        if block_reason:
            raise RuntimeError(
                f"Gemini blocked the edit request: {block_reason}. "
                f"Check content policy or tune prompt."
            )

        raw_text = ""
        try:
            raw_text = str(response)
        except Exception:
            raw_text = ""
        lowered = raw_text.lower()
        if (
            "quota" in lowered
            or "limit: 0" in lowered
            or "resource_exhausted" in lowered
            or "billing" in lowered
        ):
            raise RuntimeError(
                "Gemini quota exhausted or free tier blocked for image edits. "
                "Upgrade via aistudio.google.com/app/apikey or switch provider."
            )

        raise RuntimeError(
            "Gemini returned no image data for masked edit "
            "(enable VULCA_DEBUG=1 for raw response inspection)"
        )

    def _build_prompt(
        self, prompt: str, tradition: str, subject: str,
        aspect_ratio: str, kwargs: dict,
    ) -> str:
        parts = [f"Generate a high-quality artwork: {prompt}"]
        if tradition and tradition != "default":
            parts.append(f"Style: {tradition.replace('_', ' ')} tradition")
        if subject:
            parts.append(f"Subject: {subject}")
        cultural_guidance = kwargs.get("cultural_guidance", "")
        if cultural_guidance:
            parts.append(f"\n{cultural_guidance}")
        improvement_focus = kwargs.get("improvement_focus", "")
        if improvement_focus:
            parts.append(f"\n{improvement_focus}")
        return "\n".join(parts)
