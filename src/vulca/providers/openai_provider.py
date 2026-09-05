"""OpenAI DALL-E image generation provider."""
from __future__ import annotations

import base64
import io
import logging
import os
import re

from vulca.providers.base import ImageEditCapabilities, ImageProvider, ImageResult, ProviderRequestRejected
from vulca.providers.retry import with_retry


logger = logging.getLogger("vulca.openai")

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"

MODEL_CAPABILITIES: dict[str, dict[str, bool]] = {
    "dall-e-2": {
        "input_fidelity": False,
        "quality": False,
        "output_format": False,
    },
    "dall-e-3": {
        "input_fidelity": False,
        "quality": True,
        "output_format": False,
    },
    "gpt-image-1": {
        "input_fidelity": False,
        "quality": True,
        "output_format": True,
    },
    "gpt-image-1.5": {
        "input_fidelity": True,
        "quality": True,
        "output_format": True,
    },
    "gpt-image-2": {
        "input_fidelity": False,
        "quality": True,
        "output_format": True,
    },
    "gpt-image-2-2026-04-21": {
        "input_fidelity": False,
        "quality": True,
        "output_format": True,
    },
}

MODEL_TOKEN_PRICING_PER_MILLION: dict[str, dict[str, float]] = {
    "gpt-image-1": {"input": 10.0, "output": 40.0},
    "gpt-image-1.5": {"input": 8.0, "output": 32.0},
    "gpt-image-2": {"input": 8.0, "output": 30.0},
    "gpt-image-2-2026-04-21": {"input": 8.0, "output": 30.0},
}

def _openai_edit_capabilities(model: str) -> ImageEditCapabilities:
    if not model.startswith("gpt-image"):
        return ImageEditCapabilities()
    if model in ("gpt-image-2", "gpt-image-2-2026-04-21"):
        return ImageEditCapabilities(
            supports_edits=True,
            requires_mask_for_edits=True,
            supports_unmasked_edits=False,
            supports_masked_edits=True,
            supports_input_fidelity=False,
            supports_quality=True,
            supports_output_format=True,
        )
    return ImageEditCapabilities(
        supports_edits=True,
        requires_mask_for_edits=False,
        supports_unmasked_edits=True,
        supports_masked_edits=True,
        supports_input_fidelity=(model == "gpt-image-1.5"),
        supports_quality=True,
        supports_output_format=True,
    )


MODEL_STATIC_IMAGE_PRICING: dict[str, dict[str, dict[str, float]]] = {
    "dall-e-2": {
        "standard": {
            "1024x1024": 0.020,
            "1024x1536": 0.018,
            "1536x1024": 0.020,
        },
    },
    "dall-e-3": {
        "standard": {
            "1024x1024": 0.040,
            "1024x1792": 0.080,
            "1792x1024": 0.080,
        },
        "hd": {
            "1024x1024": 0.080,
            "1024x1792": 0.120,
            "1792x1024": 0.120,
        },
    },
}


def _drop_unsupported_params(model: str, values: dict[str, str | None]) -> dict[str, str]:
    capabilities = MODEL_CAPABILITIES.get(
        model,
        {"input_fidelity": True, "quality": True, "output_format": True},
    )
    kept: dict[str, str] = {}
    for param, value in values.items():
        if value is None:
            continue
        if capabilities.get(param, True):
            kept[param] = value
            continue
        logger.info("[param-dropped] model=%s param=%s — not supported", model, param)
    return kept


def _normalize_quality_for_model(model: str, quality: str) -> str:
    """Map gpt-image vocabulary to model-specific accepted values.

    DALL-E-3 only accepts "standard" / "hd"; gpt-image-* uses "high" / "auto" /
    "medium" / "low". Cross-model callers passing the gpt-image vocabulary to
    DALL-E-3 would 400 upstream — translate to the closest equivalent here.
    """
    if model != "dall-e-3":
        return quality
    normalized = quality.lower()
    if normalized in {"hd", "standard"}:
        return normalized
    if normalized in {"high", "auto"}:
        return "hd"
    if normalized in {"medium", "low"}:
        return "standard"
    return quality


def _mime_for_output_format(output_format: str | None) -> str:
    normalized = (output_format or "png").lower()
    if normalized in {"jpeg", "jpg"}:
        return "image/jpeg"
    if normalized == "webp":
        return "image/webp"
    return "image/png"


def _normalize_openai_base_url(base_url: str) -> str:
    url = (base_url or "https://api.openai.com").strip().rstrip("/")
    if not url:
        url = "https://api.openai.com"
    if url.endswith("/v1"):
        return url
    return f"{url}/v1"


def _openai_image_endpoint(base_url: str, endpoint: str) -> str:
    return f"{_normalize_openai_base_url(base_url)}/images/{endpoint}"


def _extract_cost_usd(
    *,
    model: str,
    data: dict,
    size: str,
    quality: str | None,
) -> float | None:
    usage = data.get("usage") or {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")

    if isinstance(input_tokens, (int, float)) or isinstance(output_tokens, (int, float)):
        pricing = MODEL_TOKEN_PRICING_PER_MILLION.get(model)
        if pricing is not None:
            total = (
                (float(input_tokens or 0) * pricing["input"])
                + (float(output_tokens or 0) * pricing["output"])
            ) / 1_000_000
            return round(total, 6)

    static_pricing = MODEL_STATIC_IMAGE_PRICING.get(model)
    if static_pricing is None:
        logger.info(
            "[cost-unknown] model=%s usage=%s — no pricing entry, returning None",
            model, usage,
        )
        return None

    quality_key = "standard"
    if model == "dall-e-3" and (quality or "").lower() in {"high", "hd"}:
        quality_key = "hd"
    by_size = static_pricing.get(quality_key, {})
    return by_size.get(size) or by_size.get("1024x1024")


def _extract_chat_image_reference(data: dict) -> str:
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("chat completions image response had no choices")
    message = choices[0].get("message") or {}
    content = message.get("content") or ""
    if isinstance(content, list):
        content = "\n".join(
            str(part.get("text", "") or part.get("image_url", {}).get("url", ""))
            for part in content
            if isinstance(part, dict)
        )
    if not isinstance(content, str):
        raise RuntimeError("chat completions image response content was not text")

    data_url = re.search(r"data:image/[^;]+;base64,([A-Za-z0-9+/=_-]+)", content)
    if data_url:
        return data_url.group(1)
    markdown_url = re.search(r"!\[[^\]]*\]\((https?://[^)]+)\)", content)
    if markdown_url:
        return markdown_url.group(1)
    plain_url = re.search(r"https?://\S+", content)
    if plain_url:
        return plain_url.group(0).rstrip(").,;")
    raise RuntimeError("chat completions image response did not contain an image")


class OpenAIImageProvider:
    """Image generation via OpenAI DALL-E 3 API."""

    capabilities: frozenset[str] = frozenset({"raw_rgba"})

    def __init__(
        self,
        api_key: str = "",
        model: str = "gpt-image-1",
        base_url: str = "",
        timeout: float = 120.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.base_url = _normalize_openai_base_url(
            base_url
            or os.environ.get("VULCA_OPENAI_BASE_URL", "")
            or os.environ.get("OPENAI_BASE_URL", "")
        )
        self.timeout = float(timeout)
        self.max_retries = int(max_retries)

    def edit_capabilities(self) -> ImageEditCapabilities:
        return _openai_edit_capabilities(self.model)

    def _image_endpoint_mode(self) -> str:
        return os.environ.get("VULCA_OPENAI_IMAGE_ENDPOINT", "").strip().lower()

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
        background: str = "auto",
        input_fidelity: str | None = None,
        quality: str | None = None,
        output_format: str | None = None,
        **kwargs,
    ) -> ImageResult:
        # OpenAI image endpoints (DALL-E 3 / gpt-image-1 / gpt-image-2) do not
        # expose seed, sampler steps, or CFG — accept for signature symmetry
        # and ignore.
        _ = (seed, steps, cfg_scale)

        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY env var "
                "or pass api_key to OpenAIImageProvider()."
            )

        import httpx

        full_prompt = prompt
        if not kwargs.get("raw_prompt", False):
            if tradition and tradition != "default":
                full_prompt = f"{prompt} (cultural tradition: {tradition.replace('_', ' ')})"
        if negative_prompt:
            full_prompt = f"{full_prompt} (avoid: {negative_prompt})"

        # Accepted sizes: DALL-E 3 uses 1024x1024, 1024x1792, 1792x1024.
        # gpt-image-1 / gpt-image-2 additionally accept 1024x1536 (portrait)
        # and 1536x1024 (landscape). Union both sets for simplicity; any
        # unsupported combo still falls back to 1024x1024.
        allowed_sizes = {
            (1024, 1024),
            (1024, 1792),
            (1792, 1024),
            (1024, 1536),
            (1536, 1024),
        }
        size = f"{width}x{height}" if (width, height) in allowed_sizes else "1024x1024"

        def _is_retryable(exc: Exception) -> bool:
            # httpx.HTTPStatusError carries a response with status_code
            response = getattr(exc, "response", None)
            if response is not None:
                status = getattr(response, "status_code", None)
                if status in (429, 500, 503):
                    return True
                return False
            # Our enriched 429 RuntimeError (normalized for readability) keeps
            # the rate-limit marker so retry logic still kicks in. Terminal
            # RuntimeErrors (403/402/400) do not carry this marker.
            if isinstance(exc, ProviderRequestRejected) and exc.status_code == 429:
                return True
            if isinstance(exc, RuntimeError) and "rate limit hit" in str(exc).lower():
                return True
            # Network-level errors (timeout, connect) are retryable
            if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
                return True
            return False

        # Only gpt-image-* supports reference-based editing without a mask.
        # dall-e-2 /edits requires a mask + square PNG + returns URLs by default,
        # none of which this provider currently handles.
        use_edits = bool(reference_image_b64)
        if use_edits and not self.model.startswith("gpt-image"):
            raise ValueError(
                f"OpenAI img2img (reference_image_b64) requires a gpt-image-* "
                f"model; current model={self.model!r} is not supported on /edits."
            )

        # Capture for closure
        model = self.model
        filtered_params = _drop_unsupported_params(
            model,
            {
                "input_fidelity": input_fidelity,
                "quality": quality,
                "output_format": output_format,
            },
        )
        if "quality" in filtered_params:
            filtered_params["quality"] = _normalize_quality_for_model(
                model, filtered_params["quality"]
            )
        effective_output_format = (
            filtered_params.get("output_format", "png")
            if model.startswith("gpt-image")
            else "png"
        )

        async def _call() -> ImageResult:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                if use_edits:
                    ref_bytes = base64.b64decode(reference_image_b64)
                    files = {
                        "image": ("ref.png", io.BytesIO(ref_bytes), "image/png"),
                    }
                    form = {
                        "model": model,
                        "prompt": full_prompt,
                        "n": "1",
                        "size": size,
                    }
                    form.update(filtered_params)
                    resp = await client.post(
                        _openai_image_endpoint(self.base_url, "edits"),
                        headers=headers, files=files, data=form,
                    )
                else:
                    payload: dict = {
                        "model": model,
                        "prompt": full_prompt,
                        "n": 1,
                        "size": size,
                    }
                    if model.startswith("gpt-image"):
                        payload["background"] = background
                        # Caller-supplied output_format wins; default stays png
                        # for backward-compat with gpt-image-1 callers.
                        payload["output_format"] = effective_output_format
                        if "quality" in filtered_params:
                            payload["quality"] = filtered_params["quality"]
                    else:
                        payload["response_format"] = "b64_json"
                        if "quality" in filtered_params:
                            payload["quality"] = filtered_params["quality"]
                    resp = await client.post(
                        _openai_image_endpoint(self.base_url, "generations"),
                        headers=headers, json=payload,
                    )
                # Classify common user-facing failure modes with actionable
                # remediation hints BEFORE raise_for_status / retry logic
                # sees them (codex 2026-04-23 audit). Only 429 is retryable
                # downstream; 402/400/403 are terminal from the user's POV.
                body_text = ""
                try:
                    body_text = (resp.text or "")[:500]
                except Exception:
                    body_text = ""
                body_lower = body_text.lower()

                # 403 Org-verification (gpt-image-2 launch gates API access)
                if resp.status_code == 403:
                    if "organization must be verified" in body_lower:
                        raise ProviderRequestRejected(
                            f"OpenAI model {model!r} requires Org verification at "
                            "https://platform.openai.com/settings/organization/general. "
                            "Wait 15 min after verifying.",
                            status_code=403,
                        )
                # 402 billing / insufficient credits
                elif resp.status_code == 402:
                    raise ProviderRequestRejected(
                        "OpenAI billing blocked: insufficient credits or "
                        "payment failure. Visit "
                        "https://platform.openai.com/settings/organization/billing "
                        "to fix.",
                        status_code=402,
                    )
                # 400 content-policy / safety violation
                elif resp.status_code == 400 and (
                    "content_policy_violation" in body_lower
                    or "safety" in body_lower
                ):
                    raise ProviderRequestRejected(
                        "OpenAI content policy blocked the request. "
                        "Revise the prompt or negative_prompt to reduce "
                        "policy-triggering terms.",
                        status_code=400,
                    )
                # 429 rate limit — enrich the message. `_is_retryable`
                # recognizes this RuntimeError marker ("rate limit hit") so
                # with_retry still backs off and retries.
                elif resp.status_code == 429:
                    raise ProviderRequestRejected(
                        "OpenAI rate limit hit. "
                        "Retry in ~60s or reduce concurrency.",
                        status_code=429,
                    )
                resp.raise_for_status()
                data = resp.json()

            img_b64 = data["data"][0].get("b64_json") or data["data"][0].get("b64", "")
            metadata = {
                "model": self.model,
                "endpoint": "edits" if use_edits else "generations",
                "output_format": effective_output_format,
                "revised_prompt": data["data"][0].get("revised_prompt", ""),
            }
            cost_usd = _extract_cost_usd(
                model=model,
                data=data,
                size=size,
                quality=filtered_params.get("quality", quality),
            )
            if cost_usd is not None:
                metadata["cost_usd"] = cost_usd
            if data.get("usage"):
                metadata["usage"] = data["usage"]
            return ImageResult(
                image_b64=img_b64,
                mime=_mime_for_output_format(effective_output_format),
                metadata=metadata,
            )

        return await with_retry(
            _call,
            max_retries=self.max_retries,
            base_delay_ms=500,
            max_delay_ms=16_000,
            retryable_check=_is_retryable,
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
        """Mask-aware inpaint via /v1/images/edits.

        Mask convention (alpha=0 = edit, alpha=255 = preserve) maps directly
        onto OpenAI's transparency semantic — the mask is uploaded as PNG
        unchanged. Only supported on gpt-image-* models.

        Optional model knobs (v0.20.1 — fix the silent-drop bug uncovered
        in v0.20 PR audit):
        - ``quality``: ``"low" | "medium" | "high" | "auto"`` (gpt-image-*).
        - ``input_fidelity``: ``"high" | "low"`` — only honored by models
          whose capability table sets ``input_fidelity=True`` (currently
          gpt-image-1.5; gpt-image-2 strips it).
        - ``output_format``: ``"png" | "webp" | "jpeg"`` (gpt-image-*).
        Each parameter is passed through ``_drop_unsupported_params`` so
        callers don't have to know per-model capability matrices.
        """
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY env var "
                "or pass api_key to OpenAIImageProvider()."
            )
        if not self.model.startswith("gpt-image"):
            raise ValueError(
                f"inpaint_with_mask requires a gpt-image-* model "
                f"(current model={self.model!r})."
            )

        import httpx

        full_prompt = prompt
        if tradition and tradition != "default":
            full_prompt = (
                f"{prompt} (cultural tradition: {tradition.replace('_', ' ')})"
            )

        # Probe mask size; pick a supported edit size near it.
        from PIL import Image as PILImage
        with open(image_path, "rb") as fh_img, open(mask_path, "rb") as fh_mask:
            image_bytes = fh_img.read()
            mask_bytes = fh_mask.read()

        if not size:
            with PILImage.open(image_path) as src_img:
                w, h = src_img.size
            allowed_sizes = {
                (1024, 1024),
                (1024, 1536),
                (1536, 1024),
            }
            size = f"{w}x{h}" if (w, h) in allowed_sizes else "1024x1024"

        if self._image_endpoint_mode() in {"chat_completions", "chat-completions"}:
            image_b64 = base64.b64encode(image_bytes).decode()
            mask_b64 = base64.b64encode(mask_bytes).decode()
            chat_prompt = (
                f"{full_prompt}\n\n"
                "Use the first image as the source crop. Use the second image "
                "as the edit mask; the transparent region marks the pixels to "
                "repaint, and opaque pixels should be preserved as context. "
                "Return only the edited image."
            )

            async def _call_chat() -> ImageResult:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    headers = {"Authorization": f"Bearer {self.api_key}"}
                    payload = {
                        "model": self.model,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": chat_prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/png;base64,{image_b64}"
                                        },
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/png;base64,{mask_b64}"
                                        },
                                    },
                                ],
                            }
                        ],
                    }
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    if resp.status_code == 429:
                        raise ProviderRequestRejected("OpenAI rate limit hit. rate limit hit", status_code=429)
                    resp.raise_for_status()
                    data = resp.json()
                    image_ref = _extract_chat_image_reference(data)
                    if image_ref.startswith("http://") or image_ref.startswith("https://"):
                        img_resp = await client.get(image_ref)
                        img_resp.raise_for_status()
                        image_ref = base64.b64encode(img_resp.content).decode()
                    metadata = {
                        "model": self.model,
                        "endpoint": "chat/completions",
                        "mode": "chat_completions_image",
                    }
                    if data.get("usage"):
                        metadata["usage"] = data["usage"]
                    return ImageResult(
                        image_b64=image_ref,
                        mime="image/png",
                        metadata=metadata,
                    )

            def _is_chat_retryable(exc: Exception) -> bool:
                response = getattr(exc, "response", None)
                if response is not None:
                    status = getattr(response, "status_code", None)
                    return status in (429, 500, 503)
                if isinstance(exc, RuntimeError) and "rate limit hit" in str(exc).lower():
                    return True
                if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
                    return True
                return False

            return await with_retry(
                _call_chat,
                max_retries=self.max_retries,
                base_delay_ms=500,
                max_delay_ms=16_000,
                retryable_check=_is_chat_retryable,
            )

        # v0.20.1 — drop knobs the current model doesn't support, then fold
        # them into the form so /v1/images/edits sees them at the wire layer.
        # Fixes the silent-drop hole that let v0.20 ship-gate run on
        # gpt-image-1 default while CHANGELOG claimed gpt-image-2 high.
        edit_filtered_params = _drop_unsupported_params(
            self.model,
            {
                "input_fidelity": input_fidelity,
                "quality": quality,
                "output_format": output_format,
            },
        )
        effective_output_format = edit_filtered_params.get("output_format", "png")

        async def _call() -> ImageResult:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                files = {
                    "image": ("image.png", image_bytes, "image/png"),
                    "mask": ("mask.png", mask_bytes, "image/png"),
                }
                form = {
                    "model": self.model,
                    "prompt": full_prompt,
                    "n": "1",
                    "size": size,
                }
                form.update(edit_filtered_params)
                resp = await client.post(
                    _openai_image_endpoint(self.base_url, "edits"),
                    headers=headers, files=files, data=form,
                )

                body_text = ""
                try:
                    body_text = (resp.text or "")[:500]
                except Exception:
                    body_text = ""
                body_lower = body_text.lower()

                if resp.status_code == 403 and "organization must be verified" in body_lower:
                    raise ProviderRequestRejected(
                        f"OpenAI model {self.model!r} requires Org verification at "
                        "https://platform.openai.com/settings/organization/general.",
                        status_code=403,
                    )
                if resp.status_code == 402:
                    raise ProviderRequestRejected(
                        "OpenAI billing blocked: insufficient credits or "
                        "payment failure.",
                        status_code=402,
                    )
                if resp.status_code == 400 and (
                    "content_policy_violation" in body_lower
                    or "safety" in body_lower
                ):
                    raise ProviderRequestRejected(
                        "OpenAI content policy blocked the inpaint request.",
                        status_code=400,
                    )
                if resp.status_code == 429:
                    raise ProviderRequestRejected("OpenAI rate limit hit. rate limit hit", status_code=429)
                resp.raise_for_status()
                data = resp.json()

            img_b64 = data["data"][0].get("b64_json") or data["data"][0].get("b64", "")
            metadata = {
                "model": self.model,
                "endpoint": "edits",
                "mode": "inpaint_with_mask",
                "output_format": effective_output_format,
            }
            cost_usd = _extract_cost_usd(
                model=self.model, data=data, size=size, quality=None,
            )
            if cost_usd is not None:
                metadata["cost_usd"] = cost_usd
            if data.get("usage"):
                metadata["usage"] = data["usage"]
            return ImageResult(
                image_b64=img_b64,
                mime=_mime_for_output_format(effective_output_format),
                metadata=metadata,
            )

        def _is_retryable(exc: Exception) -> bool:
            response = getattr(exc, "response", None)
            if response is not None:
                status = getattr(response, "status_code", None)
                return status in (429, 500, 503)
            if isinstance(exc, ProviderRequestRejected) and exc.status_code == 429:
                return True
            if isinstance(exc, RuntimeError) and "rate limit hit" in str(exc).lower():
                return True
            if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
                return True
            return False

        return await with_retry(
            _call,
            max_retries=self.max_retries,
            base_delay_ms=500,
            max_delay_ms=16_000,
            retryable_check=_is_retryable,
        )
