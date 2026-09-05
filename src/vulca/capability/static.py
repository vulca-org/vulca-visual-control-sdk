"""Deterministic, dependency-light static visual capability Cells."""

from __future__ import annotations

import base64
import binascii
import math
import re
import time
from io import BytesIO
from pathlib import Path
from typing import Mapping, TypeAlias, cast

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from .types import (
    CapabilityArtifact,
    CapabilityInvocation,
    CapabilityMaturity,
    CapabilityManifest,
    CapabilityResult,
    CapabilityStatus,
    JsonValue,
    SideEffectState,
    sha256_bytes,
)


_VERSION = "1.0.0"
_USD = "USD"
_MIME_TO_FORMAT = {
    "image/png": "PNG",
    "image/jpeg": "JPEG",
    "image/webp": "WEBP",
    "image/gif": "GIF",
}
_SUPPORTED_IMAGE_MODES = frozenset({"RGB", "RGBA", "L", "P"})
_PATH_SUFFIXES = frozenset({".bmp", ".gif", ".jpeg", ".jpg", ".otf", ".png", ".ttf", ".webp"})
_Font: TypeAlias = ImageFont.FreeTypeFont | ImageFont.ImageFont


class _StaticFailure(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _manifest(capability_id: str, *, kind: str) -> CapabilityManifest:
    return CapabilityManifest(
        capability_id=capability_id,
        version=_VERSION,
        kind=kind,
        owner="vulca",
        maturity=CapabilityMaturity.NATIVE,
        input_schema={},
        output_schema={},
        authority_requirements=("authorised_inputs",),
        evaluator_bindings=(),
        retryable_codes=(),
        deterministic=True,
    )


def _elapsed_ms(start: float) -> int:
    return max(0, int((time.perf_counter() - start) * 1000))


def _failed(invocation: CapabilityInvocation, code: str, start: float) -> CapabilityResult:
    return CapabilityResult(
        invocation_id=invocation.invocation_id,
        status=CapabilityStatus.FAILED,
        side_effect_state=SideEffectState.NOT_STARTED,
        output={},
        artifacts=(),
        provider_receipt={},
        latency_ms=_elapsed_ms(start),
        cost_minor=0,
        currency=_USD,
        error_code=code,
    )


def _success(
    invocation: CapabilityInvocation,
    *,
    output: dict[str, JsonValue],
    artifacts: tuple[CapabilityArtifact, ...],
    start: float,
) -> CapabilityResult:
    latency_ms = _elapsed_ms(start)
    return CapabilityResult(
        invocation_id=invocation.invocation_id,
        status=CapabilityStatus.SUCCEEDED,
        side_effect_state=SideEffectState.COMPLETED,
        output=output,
        artifacts=artifacts,
        provider_receipt={"costKnown": False, "latency_ms": latency_ms},
        latency_ms=latency_ms,
        cost_minor=0,
        currency=_USD,
    )


def _decode_base64(value: str) -> bytes:
    payload = value.strip()
    if payload.startswith("data:"):
        marker = ",base64,"
        index = payload.lower().find(marker)
        if index < 0:
            raise _StaticFailure("INVALID_BASE64")
        payload = payload[index + len(marker) :]
    if not payload:
        raise _StaticFailure("INVALID_BASE64")
    try:
        data = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise _StaticFailure("INVALID_BASE64") from None
    if not data:
        raise _StaticFailure("EMPTY_ARTIFACT")
    return data


def _looks_like_path(value: str) -> bool:
    text = value.strip()
    path = Path(text).expanduser()
    return (
        path.is_absolute()
        or text.startswith(("./", "../", "~/"))
        or path.suffix.lower() in _PATH_SUFFIXES
    )


def _authorised_path(path: Path, options: Mapping[str, JsonValue], *, required: bool = True) -> Path:
    paths_value = options.get("authorized_paths", [])
    roots_value = options.get("authorized_roots", [])
    if not isinstance(paths_value, list) or not isinstance(roots_value, list):
        raise _StaticFailure("INVALID_AUTHORIZATION")
    if any(not isinstance(value, str) for value in [*paths_value, *roots_value]):
        raise _StaticFailure("INVALID_AUTHORIZATION")
    try:
        resolved = path.expanduser().resolve(strict=True)
        paths = [Path(cast(str, value)).expanduser().resolve(strict=True) for value in paths_value]
        roots = [Path(cast(str, value)).expanduser().resolve(strict=True) for value in roots_value]
    except (FileNotFoundError, OSError, RuntimeError, ValueError):
        raise _StaticFailure("MISSING_INPUT") from None
    if not paths and not roots:
        if required:
            raise _StaticFailure("UNAUTHORIZED_PATH")
        return resolved
    if resolved in paths or any(resolved.is_relative_to(root) for root in roots):
        return resolved
    raise _StaticFailure("UNAUTHORIZED_PATH")


def _read_input(value: object, options: Mapping[str, JsonValue], *, required_path_auth: bool = True) -> bytes:
    if not isinstance(value, str) or not value.strip():
        raise _StaticFailure("INVALID_INPUT")
    try:
        candidate = Path(value).expanduser()
        is_file = candidate.is_file()
    except (OSError, RuntimeError, ValueError):
        is_file = False
        candidate = Path(".")
    if is_file:
        resolved = _authorised_path(candidate, options, required=required_path_auth)
        try:
            data = resolved.read_bytes()
        except OSError:
            raise _StaticFailure("MISSING_INPUT") from None
        if not data:
            raise _StaticFailure("EMPTY_ARTIFACT")
        return data
    if _looks_like_path(value):
        _authorised_path(candidate, options, required=True)
        raise _StaticFailure("MISSING_INPUT")
    return _decode_base64(value)


def _open_image(data: bytes) -> Image.Image:
    try:
        with Image.open(BytesIO(data)) as opened:
            opened.load()
            return opened.copy()
    except (UnidentifiedImageError, OSError, TypeError, ValueError, SyntaxError):
        raise _StaticFailure("CORRUPT_ARTIFACT") from None


def _mime_from_bytes(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return ""


def _normalise_image(image: Image.Image) -> Image.Image:
    if image.mode not in _SUPPORTED_IMAGE_MODES:
        raise _StaticFailure("UNSUPPORTED_MODE")
    if image.mode in {"RGB", "RGBA"}:
        return image.copy()
    if image.mode == "P":
        return image.convert("RGBA" if _alpha_present(image) else "RGB")
    return image.convert("RGB")


def _encode_image(image: Image.Image, media_type: str) -> bytes:
    normalized = media_type.lower()
    image_format = _MIME_TO_FORMAT.get(normalized)
    if image_format is None:
        raise _StaticFailure("INVALID_FORMAT")
    prepared = _normalise_image(image)
    if image_format == "JPEG" and prepared.mode == "RGBA":
        canvas = Image.new("RGB", prepared.size, (255, 255, 255))
        canvas.paste(prepared, mask=prepared.getchannel("A"))
        prepared = canvas
    elif image_format in {"JPEG", "GIF"} and prepared.mode not in {"RGB", "L", "P"}:
        prepared = prepared.convert("RGB")
    output = BytesIO()
    save_options: dict[str, object] = {}
    if image_format == "JPEG":
        save_options.update(quality=95, subsampling=0, optimize=False, progressive=False)
    elif image_format == "WEBP":
        save_options.update(lossless=True, method=6)
    try:
        prepared.save(output, format=image_format, **save_options)
    except (OSError, TypeError, ValueError):
        raise _StaticFailure("UNSUPPORTED_MODE") from None
    return output.getvalue()


def _dimensions(values: Mapping[str, JsonValue]) -> tuple[int, int]:
    width = values.get("width")
    height = values.get("height")
    if isinstance(width, bool) or not isinstance(width, int) or isinstance(height, bool) or not isinstance(height, int):
        raise _StaticFailure("INVALID_DIMENSIONS")
    if width <= 0 or height <= 0:
        raise _StaticFailure("INVALID_DIMENSIONS")
    return width, height


def _safe_area(values: Mapping[str, JsonValue], width: int, height: int) -> dict[str, int]:
    raw = values.get("safe_area", {})
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise _StaticFailure("INVALID_SAFE_AREA")
    margins: dict[str, float] = {}
    for side in ("top", "right", "bottom", "left"):
        value = raw.get(side, 0.0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise _StaticFailure("INVALID_SAFE_AREA")
        numeric = float(value)
        if not math.isfinite(numeric) or numeric < 0 or numeric >= 0.5:
            raise _StaticFailure("INVALID_SAFE_AREA")
        margins[side] = numeric
    x = math.ceil(margins["left"] * width)
    y = math.ceil(margins["top"] * height)
    right = math.floor((1.0 - margins["right"]) * width)
    bottom = math.floor((1.0 - margins["bottom"]) * height)
    if right <= x or bottom <= y:
        raise _StaticFailure("INVALID_SAFE_AREA")
    return {"x": x, "y": y, "width": right - x, "height": bottom - y}


def _colour(value: object, default: tuple[int, int, int]) -> tuple[int, ...]:
    if value is None:
        return default
    if isinstance(value, str):
        text = value.strip().lstrip("#")
        if len(text) == 3:
            text = "".join(character * 2 for character in text)
        if len(text) not in (6, 8) or not re.fullmatch(r"[0-9a-fA-F]+", text):
            raise _StaticFailure("INVALID_PALETTE")
        try:
            channels = tuple(int(text[index : index + 2], 16) for index in range(0, len(text), 2))
        except ValueError:
            raise _StaticFailure("INVALID_PALETTE") from None
        return cast(tuple[int, ...], channels)
    if isinstance(value, list) and len(value) in (3, 4) and all(isinstance(item, int) for item in value):
        if any(item < 0 or item > 255 for item in value):
            raise _StaticFailure("INVALID_PALETTE")
        channels = tuple(cast(int, item) for item in value)
        return cast(tuple[int, ...], channels)
    raise _StaticFailure("INVALID_PALETTE")


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: _Font) -> int:
    box = draw.textbbox((0, 0), text, font=font, anchor="lt")
    return int(max(0, box[2] - box[0]))


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: _Font, max_width: int) -> list[str]:
    if not text:
        return []
    lines: list[str] = []
    for paragraph in text.splitlines() or [text]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if _text_width(draw, candidate, font) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = ""
            for character in word:
                candidate_character = f"{current}{character}"
                if current and _text_width(draw, candidate_character, font) > max_width:
                    lines.append(current)
                    current = character
                else:
                    current = candidate_character
        if current:
            lines.append(current)
    return lines


def _load_font(value: object, options: Mapping[str, JsonValue], size: int) -> _Font:
    if value is None or value == "":
        return ImageFont.load_default()
    if not isinstance(value, str):
        raise _StaticFailure("INVALID_FONT")
    try:
        path = _authorised_path(Path(value), options, required=True)
        return ImageFont.truetype(str(path), size=size)
    except _StaticFailure:
        raise
    except (OSError, ValueError):
        raise _StaticFailure("INVALID_FONT") from None


def _fit_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_value: object,
    options: Mapping[str, JsonValue],
    *,
    initial_size: int,
    max_width: int,
) -> tuple[list[str], _Font]:
    for size in range(max(8, initial_size), 7, -1):
        font = _load_font(font_value, options, size)
        lines = _wrap_text(draw, text, font, max_width)
        if lines and max((_text_width(draw, line, font) for line in lines), default=0) <= max_width:
            return lines, font
    raise _StaticFailure("TEXT_OVERFLOW")


def _resize_cover(image: Image.Image, width: int, height: int) -> Image.Image:
    scale = max(width / image.width, height / image.height)
    resized = image.resize((max(width, round(image.width * scale)), max(height, round(image.height * scale))), Image.Resampling.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _resize_contain(image: Image.Image, width: int, height: int, media_type: str) -> Image.Image:
    scale = min(width / image.width, height / image.height)
    resized = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
    has_alpha = "A" in resized.getbands()
    if media_type == "image/png" and has_alpha:
        canvas: Image.Image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    else:
        canvas = Image.new("RGB", (width, height), (0, 0, 0))
        if resized.mode not in {"RGB", "RGBA", "L"}:
            resized = resized.convert("RGBA" if has_alpha else "RGB")
    left = (width - resized.width) // 2
    top = (height - resized.height) // 2
    if "A" in resized.getbands():
        canvas.paste(resized, (left, top), resized.getchannel("A"))
    else:
        canvas.paste(resized, (left, top))
    return canvas


class ComposeStaticCapability:
    manifest = _manifest("vulca.image.compose_static", kind="static-composition")

    async def invoke(self, invocation: CapabilityInvocation) -> CapabilityResult:
        start = time.perf_counter()
        try:
            values = invocation.inputs
            options = invocation.options
            background_data = _read_input(values.get("background"), options)
            background = _normalise_image(_open_image(background_data))
            zone = _safe_area(values, background.width, background.height)
            headline = values.get("headline")
            if not isinstance(headline, str) or not headline.strip():
                raise _StaticFailure("INVALID_COPY")
            body = values.get("body", "")
            cta = values.get("cta", "")
            if not isinstance(body, str) or not isinstance(cta, str):
                raise _StaticFailure("INVALID_COPY")
            template = values.get("layout_template", "bottom_left")
            if not isinstance(template, str) or template not in {"bottom_left", "top_left", "center", "bottom_right"}:
                raise _StaticFailure("INVALID_LAYOUT")
            palette = values.get("palette", {})
            if palette is None:
                palette = {}
            if not isinstance(palette, dict):
                raise _StaticFailure("INVALID_PALETTE")
            text_colour = _colour(palette.get("text"), (255, 255, 255))
            accent_colour = _colour(palette.get("accent"), (255, 204, 0))
            font_value = values.get("font_path", "")
            logo_value = values.get("logo")
            logo: Image.Image | None = None
            if logo_value is not None and logo_value != "":
                logo = _normalise_image(_open_image(_read_input(logo_value, options, required_path_auth=True)))
            draw = ImageDraw.Draw(background)
            max_width = zone["width"]
            blocks: list[tuple[str, list[str], _Font, tuple[int, ...]]] = []
            for label, content, fraction in (
                ("headline", headline, 0.12),
                ("body", body, 0.075),
                ("cta", cta, 0.065),
            ):
                if not content:
                    continue
                lines, font = _fit_lines(
                    draw,
                    content,
                    font_value,
                    options,
                    initial_size=max(8, int(background.height * fraction)),
                    max_width=max_width,
                )
                blocks.append((label, lines, font, text_colour))
            line_heights: list[int] = []
            for _, lines, font, _ in blocks:
                box = draw.textbbox((0, 0), "Ag", font=font, anchor="lt")
                line_heights.append(int(max(1, box[3] - box[1])))
            total_height = sum(height * len(lines) for height, (_, lines, _, _) in zip(line_heights, blocks))
            total_height += max(0, len(blocks) - 1) * 8
            if total_height > zone["height"]:
                raise _StaticFailure("TEXT_OVERFLOW")
            if template in {"bottom_left", "bottom_right"}:
                cursor_y = zone["y"] + zone["height"] - total_height
            elif template == "center":
                cursor_y = zone["y"] + (zone["height"] - total_height) // 2
            else:
                cursor_y = zone["y"]
            text_bounds: list[dict[str, JsonValue]] = []
            for block_index, (label, lines, font, colour) in enumerate(blocks):
                line_height = line_heights[block_index]
                for line in lines:
                    line_width = _text_width(draw, line, font)
                    if template == "bottom_right":
                        cursor_x = zone["x"] + zone["width"] - line_width
                    else:
                        cursor_x = zone["x"]
                    draw.text((cursor_x, cursor_y), line, font=font, fill=colour, anchor="lt")
                    text_bounds.append(
                        {
                            "label": label,
                            "x": cursor_x,
                            "y": cursor_y,
                            "width": line_width,
                            "height": line_height,
                        }
                    )
                    cursor_y += line_height
                cursor_y += 8
            if logo is not None:
                max_logo_width = max(1, zone["width"] // 3)
                max_logo_height = max(1, zone["height"] // 4)
                scale = min(max_logo_width / logo.width, max_logo_height / logo.height, 1.0)
                logo = logo.resize((max(1, round(logo.width * scale)), max(1, round(logo.height * scale))), Image.Resampling.LANCZOS)
                logo_x = zone["x"] + zone["width"] - logo.width if template == "bottom_right" else zone["x"]
                logo_y = zone["y"]
                if "A" in logo.getbands():
                    background.paste(logo, (logo_x, logo_y), logo.getchannel("A"))
                else:
                    background.paste(logo, (logo_x, logo_y))
            if cta:
                # A small accent marker makes the CTA explicit while remaining
                # wholly inside the same safe overlay zone.
                cta_bounds = [bound for bound in text_bounds if bound["label"] == "cta"]
                for bound in cta_bounds:
                    x = cast(int, bound["x"])
                    y = cast(int, bound["y"])
                    width = cast(int, bound["width"])
                    height = cast(int, bound["height"])
                    draw.rectangle(
                        (
                            max(zone["x"], x - 4),
                            max(zone["y"], y - 2),
                            min(zone["x"] + zone["width"] - 1, x + width + 4),
                            min(zone["y"] + zone["height"] - 1, y + height + 2),
                        ),
                        outline=accent_colour,
                        width=1,
                    )
            output_bytes = _encode_image(background, "image/png")
            artifact = CapabilityArtifact(
                logical_name="composed-static",
                media_type="image/png",
                content=output_bytes,
                sha256=sha256_bytes(output_bytes),
            )
            return _success(
                invocation,
                output={
                    "media_type": "image/png",
                    "width": background.width,
                    "height": background.height,
                    "overlay_zone": cast(JsonValue, zone),
                    "text_bounds": cast(JsonValue, text_bounds),
                },
                artifacts=(artifact,),
                start=start,
            )
        except _StaticFailure as failure:
            return _failed(invocation, failure.code, start)


class AdaptStaticCapability:
    manifest = _manifest("vulca.image.adapt_static", kind="static-adaptation")

    async def invoke(self, invocation: CapabilityInvocation) -> CapabilityResult:
        start = time.perf_counter()
        try:
            values = invocation.inputs
            options = invocation.options
            width, height = _dimensions(values)
            media_type = values.get("media_type")
            if not isinstance(media_type, str) or media_type.lower() not in _MIME_TO_FORMAT:
                raise _StaticFailure("INVALID_FORMAT")
            media_type = media_type.lower()
            mode = values.get("mode")
            if not isinstance(mode, str) or mode.upper() not in {"COVER", "CONTAIN", "SMART_CENTER"}:
                raise _StaticFailure("INVALID_FORMAT")
            source = _normalise_image(_open_image(_read_input(values.get("master"), options)))
            if mode.upper() == "CONTAIN":
                output = _resize_contain(source, width, height, media_type)
            else:
                output = _resize_cover(source, width, height)
            output_bytes = _encode_image(output, media_type)
            artifact = CapabilityArtifact(
                logical_name="adapted-static",
                media_type=media_type,
                content=output_bytes,
                sha256=sha256_bytes(output_bytes),
            )
            return _success(
                invocation,
                output={"width": width, "height": height, "media_type": media_type, "mode": mode.upper()},
                artifacts=(artifact,),
                start=start,
            )
        except _StaticFailure as failure:
            return _failed(invocation, failure.code, start)


def _check(status: bool, expected: JsonValue, actual: JsonValue) -> dict[str, JsonValue]:
    return {"status": "PASS" if status else "FAIL", "expected": expected, "actual": actual}


def _safe_area_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        normalized = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    if not math.isfinite(normalized) or not 0 <= normalized < 0.5:
        return None
    return normalized


def _alpha_present(image: Image.Image) -> bool:
    return "A" in image.getbands() or "transparency" in image.info


class ValidateStaticCapability:
    manifest = _manifest("vulca.image.validate_static", kind="static-validation")

    async def invoke(self, invocation: CapabilityInvocation) -> CapabilityResult:
        start = time.perf_counter()
        try:
            values = invocation.inputs
            options = invocation.options
            data = _read_input(values.get("artifact"), options)
            image = _open_image(data)
            if image.mode not in _SUPPORTED_IMAGE_MODES:
                raise _StaticFailure("UNSUPPORTED_MODE")
        except _StaticFailure as failure:
            return _failed(invocation, failure.code, start)

        actual_mime = _mime_from_bytes(data)
        expected_mime_value = values.get("media_type", values.get("expected_media_type"))
        expected_mime = expected_mime_value.lower() if isinstance(expected_mime_value, str) else None
        width, height = image.size
        expected_width_value = values.get("width")
        expected_height_value = values.get("height")
        expected_width = (
            expected_width_value
            if isinstance(expected_width_value, int) and not isinstance(expected_width_value, bool)
            else None
        )
        expected_height = (
            expected_height_value
            if isinstance(expected_height_value, int) and not isinstance(expected_height_value, bool)
            else None
        )
        expected_mode_value = values.get("color_mode", values.get("colour_mode"))
        expected_mode = expected_mode_value if isinstance(expected_mode_value, str) else None
        alpha_policy_value = values.get("alpha_policy")
        alpha_policy = alpha_policy_value.upper() if isinstance(alpha_policy_value, str) else None
        checks: dict[str, JsonValue] = {
            "media_type": _check(
                actual_mime in _MIME_TO_FORMAT
                and (expected_mime is None or expected_mime == actual_mime),
                expected_mime,
                actual_mime,
            ),
            "width": _check(
                expected_width_value is None or (expected_width is not None and expected_width == width),
                expected_width,
                width,
            ),
            "height": _check(
                expected_height_value is None or (expected_height is not None and expected_height == height),
                expected_height,
                height,
            ),
            "color_mode": _check(expected_mode is None or expected_mode == image.mode, expected_mode, image.mode),
        }
        if alpha_policy is None:
            checks["alpha_policy"] = _check(True, None, "UNSPECIFIED")
        elif alpha_policy in {"FORBID", "OPAQUE"}:
            checks["alpha_policy"] = _check(not _alpha_present(image), alpha_policy, "present" if _alpha_present(image) else "absent")
        elif alpha_policy == "REQUIRE":
            checks["alpha_policy"] = _check(_alpha_present(image), alpha_policy, "present" if _alpha_present(image) else "absent")
        elif alpha_policy == "ALLOW":
            checks["alpha_policy"] = _check(True, alpha_policy, "present" if _alpha_present(image) else "absent")
        else:
            checks["alpha_policy"] = _check(False, alpha_policy, "unsupported policy")

        safe_area_value = values.get("safe_area")
        safe_area_ok = True
        parsed_safe_area: dict[str, JsonValue] = {}
        safe_area_expected: JsonValue = None
        if safe_area_value is not None:
            safe_area_expected = parsed_safe_area
            if not isinstance(safe_area_value, dict):
                safe_area_ok = False
            else:
                for side in ("top", "right", "bottom", "left"):
                    if side not in safe_area_value:
                        continue
                    value = safe_area_value[side]
                    normalized = _safe_area_number(value)
                    if normalized is None:
                        safe_area_ok = False
                    else:
                        parsed_safe_area[side] = normalized
        checks["safe_area"] = _check(
            safe_area_ok,
            safe_area_expected,
            "valid" if safe_area_ok else "invalid",
        )

        max_bytes_value = values.get("max_bytes")
        max_bytes = (
            max_bytes_value
            if isinstance(max_bytes_value, int) and not isinstance(max_bytes_value, bool)
            else None
        )
        max_bytes_ok = max_bytes_value is None or (max_bytes is not None and len(data) <= max_bytes)
        checks["max_bytes"] = _check(max_bytes_ok, max_bytes, len(data))

        filename = values.get("filename", "")
        pattern = values.get("required_naming_pattern")
        naming_ok = True
        if pattern is not None:
            if not isinstance(filename, str) or not isinstance(pattern, str):
                naming_ok = False
            else:
                try:
                    naming_ok = re.fullmatch(pattern, filename) is not None
                except re.error:
                    naming_ok = False
        checks["naming_pattern"] = _check(naming_ok, pattern if isinstance(pattern, str) else None, filename if isinstance(filename, str) else None)

        all_pass = all(isinstance(value, dict) and value.get("status") == "PASS" for value in checks.values())
        return _success(
            invocation,
            output={"validation_status": "PASS" if all_pass else "FAIL", "checks": checks},
            artifacts=(),
            start=start,
        )


__all__ = ["ComposeStaticCapability", "AdaptStaticCapability", "ValidateStaticCapability"]
