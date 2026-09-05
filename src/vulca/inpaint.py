"""Inpaint API -- partial region redraw with Gemini blend.

v0.17.14 adds a native mask_path branch: callers supply a precision RGBA mask
(SAM output, layer alpha, HSV filter result) instead of a coarse rectangular
region. The mask path goes through a provider's mask-aware edit endpoint
(currently OpenAI /v1/images/edits) and bypasses the legacy
detect_region → crop → feathered-paste pipeline entirely.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from vulca.types import InpaintResult

logger = logging.getLogger("vulca.inpaint")


def _scratch_output_path(scratch_root: Path, requested: str) -> Path:
    """Resolve an optional output below the caller-owned scratch root."""
    root = scratch_root.resolve(strict=True)
    if not requested:
        return root / "blended.png"
    candidate = Path(requested).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        raise ValueError("scratch output path is invalid") from None
    if not resolved.is_relative_to(root):
        raise ValueError("scratch output path must stay inside scratch_dir")
    if candidate.is_symlink():
        raise ValueError("scratch output path must not be a symlink")
    return candidate


async def ainpaint(
    image: str,
    *,
    region: str = "",
    instruction: str,
    mask_path: str = "",
    tradition: str = "default",
    provider: str = "",
    count: int = 4,
    select: int | None = None,
    output: str = "",
    output_path: str = "",
    api_key: str = "",
    mock: bool = False,
    scratch_dir: str = "",
) -> InpaintResult:
    """Inpaint a region of an artwork (async).

    Two branches:

    1. **Native mask** (preferred, v0.17.14+): pass ``mask_path`` to a PNG with
       an alpha channel where alpha=0 marks pixels to edit and alpha=255 marks
       pixels to preserve. Uses the provider's mask-aware edit endpoint
       directly. Currently supported on ``openai`` (gpt-image-2).

    2. **Legacy region**: ``region`` as NL ("fix the sky") or coordinates
       ("0,0,100,35"). VLM detects bbox → crops → img2img full-canvas regen
       → feathered rectangular paste. Imprecise — prefer mask_path when
       available.

    Precedence: ``mask_path`` wins over ``region`` if both are set (a warning
    is logged).

    Args:
        image: Path to the image file.
        region: Legacy NL/coords region (used only when mask_path is empty).
        instruction: What to paint in the masked / cropped region.
        mask_path: PNG with alpha channel (0=edit, 255=preserve).
        tradition: Cultural tradition for style consistency.
        provider: Image generation provider. Default ``openai`` because that
            is the only mask-aware backend right now; legacy callers passing
            ``gemini`` for the region path still work.
        count: Number of repaint variants for the legacy region path.
        select: Auto-select variant index (0-based). None = return all.
        output: (legacy alias of output_path) Output path for blended image.
        output_path: Explicit output path. If empty, defaults next to source.
        api_key: API key override.
        mock: Use mock mode (no real API calls).
        scratch_dir: Optional caller-owned scratch root. Coordinate crops,
            repaint variants, and the blended output are written beneath it;
            the root is never deleted by this function.
    """
    from vulca.studio.phases.inpaint import (
        InpaintPhase,
        crop_region,
        is_coordinate_string,
        parse_region_coordinates,
    )

    t0 = time.monotonic()

    if mask_path and region:
        logger.warning(
            "ainpaint: both mask_path and region given — using mask_path "
            "(precedence rule). Drop region= to silence."
        )

    # Default provider depends on path: openai for mask (only one with native
    # /v1/images/edits mask-aware editing), gemini for legacy region (the
    # historical default — codex P2.5 review flagged a silent default flip
    # that would have rerouted legacy callers' billing).
    if mask_path:
        resolved_provider = provider or "openai"
        return await _ainpaint_with_mask(
            image=image,
            mask_path=mask_path,
            instruction=instruction,
            tradition=tradition,
            provider=resolved_provider,
            output_path=output_path or output,
            api_key=api_key,
            mock=mock,
            scratch_dir=scratch_dir,
            t0=t0,
        )

    resolved_provider = provider or "gemini"

    if not region:
        raise ValueError(
            "ainpaint: either mask_path or region is required. "
            "Pass mask_path=<png> for native mask edits, or region=<NL|x,y,w,h> "
            "for legacy crop-and-paste."
        )

    phase = InpaintPhase()

    # 1. Parse or detect region
    if is_coordinate_string(region):
        bbox = parse_region_coordinates(region)
    else:
        if mock:
            bbox = {"x": 0, "y": 0, "w": 50, "h": 50}
        else:
            bbox = await phase.detect_region(image, region, api_key=api_key)

    # 2. Crop
    import tempfile

    if scratch_dir:
        scratch_root = Path(scratch_dir).expanduser()
        scratch_root.mkdir(parents=True, exist_ok=True)
    else:
        scratch_root = Path(tempfile.mkdtemp(prefix="vulca-inpaint-"))
    crop_dir = str(scratch_root)
    crop_path = crop_region(image, bbox, output_dir=crop_dir)

    # 3. Repaint variants
    if mock:
        from PIL import Image as PILImage

        variants = []
        for i in range(count):
            p = Path(crop_dir) / f"repaint_v{i + 1}.png"
            PILImage.new("RGB", (128, 128), f"#{i * 30 + 50:02x}{i * 20 + 80:02x}FF").save(str(p))
            variants.append(str(p))
    else:
        variants = await phase.repaint(
            image,
            crop_path,
            instruction=instruction,
            tradition=tradition,
            provider=resolved_provider,
            count=count,
            output_dir=crop_dir,
            api_key=api_key,
        )

    # 4. Select + Blend
    sel_idx = select if select is not None else 0
    sel_idx = min(sel_idx, len(variants) - 1) if variants else 0

    blended = ""
    if variants:
        if mock:
            from PIL import Image as PILImage

            blended_path = scratch_root / "blended.png"
            PILImage.new("RGB", (256, 256), "blue").save(str(blended_path))
            blended = str(blended_path)
        else:
            blend_output = output_path or output
            if scratch_dir:
                blend_output = str(_scratch_output_path(scratch_root, blend_output))
            blended = await phase.blend(
                image,
                variants[sel_idx],
                bbox=bbox,
                output_path=blend_output,
                api_key=api_key,
            )

    elapsed = int((time.monotonic() - t0) * 1000)
    cost = 0.0 if mock else 0.05
    cost_is_estimate = not mock

    return InpaintResult(
        bbox=bbox,
        variants=variants,
        selected=sel_idx,
        blended=blended,
        original=image,
        instruction=instruction,
        tradition=tradition,
        latency_ms=elapsed,
        cost_usd=cost,
        cost_is_estimate=cost_is_estimate,
    )


def _bbox_from_mask_alpha(mask_rgba) -> dict:
    """Compute percentage bbox of the mask's alpha=0 (editable) region.

    Returns ``{x, y, w, h}`` as integer percentages of the mask canvas.
    Falls back to the full canvas when the mask is fully opaque (legacy
    contract — agent gets a non-lying signal that everything was in scope).

    Codex 2026-04-25 P1 finding: pre-revision returned hardcoded
    {0,0,100,100} regardless of mask shape, which lied to downstream
    attribution/scoring code.
    """
    from PIL import Image

    alpha = mask_rgba.split()[-1]
    bbox = alpha.point(lambda v: 255 if v < 128 else 0).getbbox()
    if bbox is None:
        return {"x": 0, "y": 0, "w": 100, "h": 100}
    x1, y1, x2, y2 = bbox
    w_total, h_total = mask_rgba.size
    return {
        "x": int(x1 / w_total * 100),
        "y": int(y1 / h_total * 100),
        "w": max(1, int((x2 - x1) / w_total * 100)),
        "h": max(1, int((y2 - y1) / h_total * 100)),
    }


async def _ainpaint_with_mask(
    *,
    image: str,
    mask_path: str,
    instruction: str,
    tradition: str,
    provider: str,
    output_path: str,
    api_key: str,
    mock: bool,
    scratch_dir: str,
    t0: float,
) -> InpaintResult:
    """Native mask-based inpaint via provider edit endpoint."""
    from PIL import Image as PILImage

    src_p = Path(image)
    mask_p = Path(mask_path)
    if not src_p.exists():
        raise FileNotFoundError(f"image not found: {image}")
    if not mask_p.exists():
        raise FileNotFoundError(f"mask_path not found: {mask_path}")

    with PILImage.open(str(src_p)) as src_img:
        src_img.load()
        src_size = src_img.size
    with PILImage.open(str(mask_p)) as mask_img:
        mask_img.load()
        mask_size = mask_img.size
        # Compute the actually-edited bbox from mask alpha=0 region. Codex
        # 2026-04-25 P1: hardcoded {0,0,100,100} fabricated a full-canvas
        # box and would poison downstream attribution / scoring.
        edit_bbox = _bbox_from_mask_alpha(mask_img.convert("RGBA"))

    if mask_size != src_size:
        raise ValueError(
            f"mask size {mask_size} != image size {src_size}; "
            "resize mask to match before calling inpaint_artwork(mask_path=...)"
        )

    # Resolve output path early so mock and real branches share it.
    if scratch_dir:
        scratch_root = Path(scratch_dir).expanduser()
        scratch_root.mkdir(parents=True, exist_ok=True)
        output_path = str(_scratch_output_path(scratch_root, output_path))
    else:
        scratch_root = None
    out_path = output_path or (
        str(scratch_root / "blended.png")
        if scratch_root is not None
        else str(src_p.with_name(f"inpainted_{src_p.stem}.png"))
    )

    if mock:
        # Mock path: copy source as the "edited" output. Tests assert the
        # mask path was honored without needing a real provider.
        with PILImage.open(str(src_p)) as im:
            im.convert("RGB").save(out_path, "PNG")
        elapsed = int((time.monotonic() - t0) * 1000)
        return InpaintResult(
            bbox=edit_bbox,
            variants=[out_path],
            selected=0,
            blended=out_path,
            original=image,
            instruction=instruction,
            tradition=tradition,
            latency_ms=elapsed,
            cost_usd=0.0,
            cost_is_estimate=False,
        )

    if provider != "openai":
        if scratch_dir:
            from vulca.capability.runtime import CapabilityProviderUnsupportedError

            raise CapabilityProviderUnsupportedError()
        raise NotImplementedError(
            f"inpaint_artwork(mask_path=...) is only supported on provider='openai' "
            f"(gpt-image-2). Got provider={provider!r}. Either switch provider, "
            "or fall back to the legacy region= path which does work for non-OpenAI "
            "providers (less precise — feathered rectangle paste)."
        )

    from vulca.providers.openai_provider import OpenAIImageProvider

    prov = OpenAIImageProvider(
        api_key=api_key,
        model="gpt-image-2",
    )
    result = await prov.inpaint_with_mask(
        image_path=str(src_p),
        mask_path=str(mask_p),
        prompt=instruction,
        tradition=tradition,
    )

    import base64

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(base64.b64decode(result.image_b64))

    elapsed = int((time.monotonic() - t0) * 1000)
    reported_cost = (result.metadata or {}).get("cost_usd")
    cost = float(reported_cost) if reported_cost else 0.05
    cost_is_estimate = not reported_cost
    return InpaintResult(
        bbox=edit_bbox,
        variants=[out_path],
        selected=0,
        blended=out_path,
        original=image,
        instruction=instruction,
        tradition=tradition,
        latency_ms=elapsed,
        cost_usd=cost,
        cost_is_estimate=cost_is_estimate,
    )


def inpaint(
    image: str,
    *,
    region: str = "",
    instruction: str,
    mask_path: str = "",
    tradition: str = "default",
    provider: str = "",
    count: int = 4,
    select: int | None = None,
    output: str = "",
    output_path: str = "",
    api_key: str = "",
    mock: bool = False,
    scratch_dir: str = "",
) -> InpaintResult:
    """Inpaint a region of an artwork (sync wrapper). See ``ainpaint``.

    ``provider=""`` (default) means: route to ``openai`` when ``mask_path``
    is set (only mask-aware backend), otherwise route to ``gemini``
    (legacy region default). Pass an explicit ``provider=`` to override.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            ainpaint(
                image,
                region=region,
                instruction=instruction,
                mask_path=mask_path,
                tradition=tradition,
                provider=provider,
                count=count,
                select=select,
                output=output,
                output_path=output_path,
                api_key=api_key,
                mock=mock,
                scratch_dir=scratch_dir,
            )
        )
    finally:
        loop.close()
