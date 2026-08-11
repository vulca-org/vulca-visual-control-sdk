"""Deterministic Pillow contracts for the first static visual Cells."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from vulca.capability import CapabilityInvocation, CapabilityStatus, SideEffectState
from vulca.capability.static import (
    AdaptStaticCapability,
    ComposeStaticCapability,
    ValidateStaticCapability,
)


def _png_bytes(
    size: tuple[int, int] = (200, 120),
    *,
    mode: str = "RGB",
    color: tuple[int, ...] = (21, 42, 63),
) -> bytes:
    buffer = BytesIO()
    Image.new(mode, size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _raw_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _invocation(capability_id: str, inputs: dict, *, options: dict | None = None) -> CapabilityInvocation:
    return CapabilityInvocation(
        invocation_id="inv_static",
        capability_id=capability_id,
        capability_version="1.0.0",
        inputs=inputs,
        options=options or {},
    )


def _font_fixture(tmp_path: Path) -> Path:
    source = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
    if not source.exists():
        pytest.skip("the test environment has no authorised system font fixture")
    destination = tmp_path / "approved-font.ttf"
    destination.write_bytes(source.read_bytes())
    return destination


def test_compose_is_deterministic_and_stays_inside_declared_safe_overlay_zone(
    tmp_path: Path,
) -> None:
    background = tmp_path / "background.png"
    background_bytes = _png_bytes()
    background.write_bytes(background_bytes)
    font = _font_fixture(tmp_path)
    inputs = {
        "background": str(background),
        "headline": "Campaign title",
        "body": "A restrained supporting line",
        "cta": "Learn more",
        "font_path": str(font),
        "palette": {"text": "#ffffff", "accent": "#ffcc00"},
        "layout_template": "bottom_left",
        "safe_area": {"top": 0.10, "right": 0.10, "bottom": 0.10, "left": 0.10},
    }
    options = {"authorized_paths": [str(background), str(font)]}

    import asyncio

    result_one = asyncio.run(
        ComposeStaticCapability().invoke(
            _invocation("vulca.image.compose_static", inputs, options=options)
        )
    )
    result_two = asyncio.run(
        ComposeStaticCapability().invoke(
            _invocation("vulca.image.compose_static", inputs, options=options)
        )
    )

    assert result_one.status is CapabilityStatus.SUCCEEDED
    assert result_one.side_effect_state is SideEffectState.COMPLETED
    assert result_one.artifacts[0].media_type == "image/png"
    assert result_one.artifacts[0].content == result_two.artifacts[0].content
    zone = result_one.output["overlay_zone"]
    with Image.open(BytesIO(result_one.artifacts[0].content)) as output:
        assert output.size == (200, 120)
        assert output.getpixel((0, 0)) == (21, 42, 63)
        with Image.open(background) as original:
            for y in range(output.height):
                for x in range(output.width):
                    inside = (
                        zone["x"] <= x < zone["x"] + zone["width"]
                        and zone["y"] <= y < zone["y"] + zone["height"]
                    )
                    if not inside:
                        assert output.getpixel((x, y)) == original.getpixel((x, y))

    assert zone["x"] >= 20
    assert zone["y"] >= 12
    assert zone["x"] + zone["width"] <= 180
    assert zone["y"] + zone["height"] <= 108
    for bound in result_one.output["text_bounds"]:
        assert zone["x"] <= bound["x"]
        assert zone["y"] <= bound["y"]
        assert bound["x"] + bound["width"] <= zone["x"] + zone["width"]
        assert bound["y"] + bound["height"] <= zone["y"] + zone["height"]
    assert background.read_bytes() == background_bytes


def test_compose_rejects_unresolved_or_unauthorised_font_and_logo_paths(tmp_path: Path) -> None:
    background = _raw_b64(_png_bytes())
    font = tmp_path / "not-authorised.ttf"
    font.write_bytes(b"not-a-font")
    logo = tmp_path / "logo.png"
    logo.write_bytes(_png_bytes((12, 12), color=(255, 0, 0)))
    invocation = _invocation(
        "vulca.image.compose_static",
        {
            "background": background,
            "headline": "Title",
            "font_path": str(font),
            "logo": str(logo),
            "safe_area": {"top": 0.1, "right": 0.1, "bottom": 0.1, "left": 0.1},
        },
        options={"authorized_paths": []},
    )

    import asyncio

    result = asyncio.run(ComposeStaticCapability().invoke(invocation))

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.NOT_STARTED
    assert result.error_code == "UNAUTHORIZED_PATH"


def test_compose_rejects_path_traversal_outside_authorised_root(tmp_path: Path) -> None:
    approved = tmp_path / "approved"
    approved.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(_png_bytes((12, 12), color=(255, 0, 0)))
    background = _raw_b64(_png_bytes())
    traversal = approved / ".." / "outside.png"

    import asyncio

    result = asyncio.run(
        ComposeStaticCapability().invoke(
            _invocation(
                "vulca.image.compose_static",
                {
                    "background": background,
                    "headline": "Title",
                    "logo": str(traversal),
                },
                options={"authorized_roots": [str(approved)]},
            )
        )
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.error_code == "UNAUTHORIZED_PATH"


@pytest.mark.parametrize("mode", ("COVER", "CONTAIN", "SMART_CENTER"))
def test_adapt_produces_exact_dimensions_and_requested_media_type(mode: str) -> None:
    import asyncio

    result = asyncio.run(
        AdaptStaticCapability().invoke(
            _invocation(
                "vulca.image.adapt_static",
                {
                    "master": _raw_b64(_png_bytes((80, 40))),
                    "width": 120,
                    "height": 90,
                    "media_type": "image/png",
                    "mode": mode,
                },
            )
        )
    )

    assert result.status is CapabilityStatus.SUCCEEDED
    assert result.output["width"] == 120
    assert result.output["height"] == 90
    assert result.output["media_type"] == "image/png"
    with Image.open(BytesIO(result.artifacts[0].content)) as output:
        assert output.size == (120, 90)
        assert output.format == "PNG"


def test_adapt_is_deterministic_and_does_not_mutate_source(tmp_path: Path) -> None:
    source = tmp_path / "master.png"
    source_bytes = _png_bytes((80, 40))
    source.write_bytes(source_bytes)
    import asyncio

    invocation = _invocation(
        "vulca.image.adapt_static",
        {
            "master": str(source),
            "width": 40,
            "height": 40,
            "media_type": "image/jpeg",
            "mode": "SMART_CENTER",
        },
        options={"authorized_paths": [str(source)]},
    )
    result_one = asyncio.run(AdaptStaticCapability().invoke(invocation))
    result_two = asyncio.run(AdaptStaticCapability().invoke(invocation))

    assert result_one.status is CapabilityStatus.SUCCEEDED
    assert result_one.artifacts[0].content == result_two.artifacts[0].content
    assert result_one.artifacts[0].media_type == "image/jpeg"
    with Image.open(BytesIO(result_one.artifacts[0].content)) as output:
        assert output.size == (40, 40)
        assert output.format == "JPEG"
    assert source.read_bytes() == source_bytes


def test_adapt_rejects_unknown_mode_and_never_silently_changes_format() -> None:
    import asyncio

    result = asyncio.run(
        AdaptStaticCapability().invoke(
            _invocation(
                "vulca.image.adapt_static",
                {
                    "master": _raw_b64(_png_bytes()),
                    "width": 40,
                    "height": 40,
                    "media_type": "image/tiff",
                    "mode": "FILL",
                },
            )
        )
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.NOT_STARTED
    assert result.error_code == "INVALID_FORMAT"


def test_adapt_rejects_invalid_dimensions_before_writing() -> None:
    import asyncio

    result = asyncio.run(
        AdaptStaticCapability().invoke(
            _invocation(
                "vulca.image.adapt_static",
                {
                    "master": _raw_b64(_png_bytes()),
                    "width": 0,
                    "height": 40,
                    "media_type": "image/png",
                    "mode": "CONTAIN",
                },
            )
        )
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.NOT_STARTED
    assert result.error_code == "INVALID_DIMENSIONS"


def test_validate_returns_structured_pass_checks_without_release_decision() -> None:
    import asyncio

    data = _png_bytes((100, 60), mode="RGB")
    result = asyncio.run(
        ValidateStaticCapability().invoke(
            _invocation(
                "vulca.image.validate_static",
                {
                    "artifact": _raw_b64(data),
                    "media_type": "image/png",
                    "width": 100,
                    "height": 60,
                    "color_mode": "RGB",
                    "alpha_policy": "FORBID",
                    "safe_area": {"top": 0.1, "right": 0.1, "bottom": 0.1, "left": 0.1},
                    "max_bytes": len(data) + 10,
                    "filename": "hero.png",
                    "required_naming_pattern": r"^hero\.png$",
                },
            )
        )
    )

    assert result.status is CapabilityStatus.SUCCEEDED
    assert result.output["validation_status"] == "PASS"
    assert all(check["status"] == "PASS" for check in result.output["checks"].values())
    assert "release" not in result.output
    assert result.artifacts == ()


def test_validate_reports_fail_checks_for_technical_mismatches() -> None:
    import asyncio

    data = _png_bytes((100, 60), mode="RGBA", color=(21, 42, 63, 180))
    result = asyncio.run(
        ValidateStaticCapability().invoke(
            _invocation(
                "vulca.image.validate_static",
                {
                    "artifact": _raw_b64(data),
                    "media_type": "image/png",
                    "width": 99,
                    "height": 60,
                    "color_mode": "RGB",
                    "alpha_policy": "FORBID",
                    "safe_area": {"top": 0.6, "right": 0.1, "bottom": 0.1, "left": 0.1},
                    "max_bytes": 1,
                    "filename": "wrong.jpg",
                    "required_naming_pattern": r"^hero\.png$",
                },
            )
        )
    )

    assert result.status is CapabilityStatus.SUCCEEDED
    assert result.output["validation_status"] == "FAIL"
    assert any(check["status"] == "FAIL" for check in result.output["checks"].values())
    assert "release_decision" not in result.output


def test_validate_rejects_corrupt_input_as_not_started() -> None:
    import asyncio

    result = asyncio.run(
        ValidateStaticCapability().invoke(
            _invocation(
                "vulca.image.validate_static",
                {"artifact": _raw_b64(b"not-an-image")},
            )
        )
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.NOT_STARTED
    assert result.error_code == "CORRUPT_ARTIFACT"
