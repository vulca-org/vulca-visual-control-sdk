"""Deterministic Pillow contracts for the first static visual Cells."""

from __future__ import annotations

import base64
from io import BytesIO
import json
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


def _mode_bytes(mode: str, size: tuple[int, int] = (80, 40)) -> bytes:
    colors: dict[str, object] = {
        "RGB": (21, 42, 63),
        "RGBA": (21, 42, 63, 200),
        "L": 96,
        "P": 3,
        "CMYK": (10, 20, 30, 40),
        "I": 96,
        "F": 0.5,
        "1": 1,
    }
    buffer = BytesIO()
    image = Image.new(mode, size, colors[mode])
    image.save(buffer, format="PNG" if mode in {"RGB", "RGBA", "L", "P"} else "TIFF")
    return buffer.getvalue()


def _bmp_bytes(size: tuple[int, int] = (100, 60)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (21, 42, 63)).save(buffer, format="BMP")
    return buffer.getvalue()


def test_compose_is_deterministic_and_stays_inside_declared_safe_overlay_zone(
    tmp_path: Path,
) -> None:
    background = tmp_path / "background.png"
    background_bytes = _png_bytes()
    background.write_bytes(background_bytes)
    inputs = {
        "background": str(background),
        "headline": "Campaign title",
        "body": "A restrained supporting line",
        "cta": "Learn more",
        "palette": {"text": "#ffffff", "accent": "#ffcc00"},
        "layout_template": "bottom_left",
        "safe_area": {"top": 0.10, "right": 0.10, "bottom": 0.10, "left": 0.10},
    }
    options = {"authorized_paths": [str(background)]}

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


@pytest.mark.parametrize(
    ("capability", "capability_id", "inputs_key"),
    [
        (ComposeStaticCapability, "vulca.image.compose_static", "background"),
        (AdaptStaticCapability, "vulca.image.adapt_static", "master"),
        (ValidateStaticCapability, "vulca.image.validate_static", "artifact"),
    ],
)
def test_static_filesystem_inputs_require_explicit_path_authority(
    tmp_path: Path,
    capability: type[ComposeStaticCapability] | type[AdaptStaticCapability] | type[ValidateStaticCapability],
    capability_id: str,
    inputs_key: str,
) -> None:
    path = tmp_path / f"{inputs_key}.png"
    path.write_bytes(_png_bytes())
    inputs: dict = {inputs_key: str(path)}
    if capability is ComposeStaticCapability:
        inputs["headline"] = "Title"
    elif capability is AdaptStaticCapability:
        inputs.update(width=40, height=40, media_type="image/png", mode="CONTAIN")

    import asyncio

    result = asyncio.run(capability().invoke(_invocation(capability_id, inputs)))

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.NOT_STARTED
    assert result.error_code == "UNAUTHORIZED_PATH"


def test_static_missing_path_is_not_treated_as_base64(tmp_path: Path) -> None:
    import asyncio

    missing = tmp_path / "missing.png"
    result = asyncio.run(
        ComposeStaticCapability().invoke(
            _invocation(
                "vulca.image.compose_static",
                {"background": str(missing), "headline": "Title"},
            )
        )
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.error_code == "MISSING_INPUT"


def test_static_symlink_escape_is_rejected_before_read(tmp_path: Path) -> None:
    approved = tmp_path / "approved"
    approved.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(_png_bytes())
    link = approved / "linked.png"
    link.symlink_to(outside)

    import asyncio

    result = asyncio.run(
        AdaptStaticCapability().invoke(
            _invocation(
                "vulca.image.adapt_static",
                {
                    "master": str(link),
                    "width": 40,
                    "height": 40,
                    "media_type": "image/png",
                    "mode": "CONTAIN",
                },
                options={"authorized_roots": [str(approved)]},
            )
        )
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.error_code == "UNAUTHORIZED_PATH"


@pytest.mark.parametrize("mode", ("RGB", "RGBA", "L", "P"))
def test_compose_normalizes_supported_pillow_modes(mode: str) -> None:
    import asyncio

    result = asyncio.run(
        ComposeStaticCapability().invoke(
            _invocation(
                "vulca.image.compose_static",
                {"background": _raw_b64(_mode_bytes(mode)), "headline": "Title"},
            )
        )
    )

    assert result.status is CapabilityStatus.SUCCEEDED
    with Image.open(BytesIO(result.artifacts[0].content)) as output:
        assert output.size == (80, 40)
        assert output.format == "PNG"


@pytest.mark.parametrize("mode", ("RGB", "RGBA", "L", "P"))
def test_adapt_normalizes_supported_pillow_modes(mode: str) -> None:
    import asyncio

    result = asyncio.run(
        AdaptStaticCapability().invoke(
            _invocation(
                "vulca.image.adapt_static",
                {
                    "master": _raw_b64(_mode_bytes(mode)),
                    "width": 40,
                    "height": 30,
                    "media_type": "image/png",
                    "mode": "CONTAIN",
                },
            )
        )
    )

    assert result.status is CapabilityStatus.SUCCEEDED
    with Image.open(BytesIO(result.artifacts[0].content)) as output:
        assert output.size == (40, 30)


@pytest.mark.parametrize("mode", ("CMYK", "I", "F", "1"))
def test_static_rejects_unsupported_pillow_modes_structurally(mode: str) -> None:
    import asyncio

    result = asyncio.run(
        AdaptStaticCapability().invoke(
            _invocation(
                "vulca.image.adapt_static",
                {
                    "master": _raw_b64(_mode_bytes(mode)),
                    "width": 40,
                    "height": 30,
                    "media_type": "image/png",
                    "mode": "CONTAIN",
                },
            )
        )
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.error_code == "UNSUPPORTED_MODE"


def test_validate_fails_unknown_actual_mime_even_without_expected_mime() -> None:
    import asyncio

    result = asyncio.run(
        ValidateStaticCapability().invoke(
            _invocation(
                "vulca.image.validate_static",
                {"artifact": _raw_b64(_bmp_bytes())},
            )
        )
    )

    assert result.status is CapabilityStatus.SUCCEEDED
    assert result.output["validation_status"] == "FAIL"
    assert result.output["checks"]["media_type"]["status"] == "FAIL"


@pytest.mark.parametrize("mode", ("RGB", "RGBA", "L", "P"))
def test_validate_accepts_supported_modes_without_mutating_source(
    mode: str,
    tmp_path: Path,
) -> None:
    import asyncio

    source = tmp_path / f"supported-{mode}.png"
    source_bytes = _mode_bytes(mode)
    source.write_bytes(source_bytes)
    result = asyncio.run(
        ValidateStaticCapability().invoke(
            _invocation(
                "vulca.image.validate_static",
                {"artifact": str(source), "color_mode": mode},
                options={"authorized_paths": [str(source)]},
            )
        )
    )

    assert result.status is CapabilityStatus.SUCCEEDED
    assert result.output["checks"]["color_mode"]["status"] == "PASS"
    assert result.output["checks"]["color_mode"]["actual"] == mode
    assert source.read_bytes() == source_bytes


@pytest.mark.parametrize("mode", ("CMYK", "I", "F", "1"))
@pytest.mark.parametrize("with_expected_mode", (False, True))
def test_validate_rejects_unsupported_modes_with_or_without_expected_mode(
    mode: str,
    with_expected_mode: bool,
) -> None:
    import asyncio

    inputs: dict = {"artifact": _raw_b64(_mode_bytes(mode))}
    if with_expected_mode:
        inputs["color_mode"] = mode
    result = asyncio.run(
        ValidateStaticCapability().invoke(
            _invocation("vulca.image.validate_static", inputs)
        )
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.NOT_STARTED
    assert result.error_code == "UNSUPPORTED_MODE"
    assert result.artifacts == ()


def test_validate_safe_area_echoes_only_allowlisted_finite_numeric_fields() -> None:
    import asyncio

    secret = "static-safe-area-secret"
    invocation = _invocation(
        "vulca.image.validate_static",
        {
            "artifact": _raw_b64(_png_bytes()),
            "safe_area": {"top": 0.1},
        },
    )
    safe_area = invocation.inputs["safe_area"]
    assert isinstance(safe_area, dict)
    safe_area["right"] = float("nan")
    safe_area["internal"] = {"api_key": secret}

    result = asyncio.run(ValidateStaticCapability().invoke(invocation))

    assert result.status is CapabilityStatus.SUCCEEDED
    assert result.output["validation_status"] == "FAIL"
    check = result.output["checks"]["safe_area"]
    assert check["status"] == "FAIL"
    assert check["expected"] == {"top": 0.1}
    assert secret not in repr(result)
    json.dumps(result.output, allow_nan=False)


@pytest.mark.parametrize("overflowing_value", (10**1000, -(10**1000)))
def test_validate_safe_area_overflow_is_structured_and_never_echoed(
    overflowing_value: int,
) -> None:
    import asyncio

    result = asyncio.run(
        ValidateStaticCapability().invoke(
            _invocation(
                "vulca.image.validate_static",
                {
                    "artifact": _raw_b64(_png_bytes()),
                    "safe_area": {
                        "top": overflowing_value,
                        "left": 0.1,
                        "internal": {"note": "unknown nested value"},
                    },
                },
            )
        )
    )

    assert result.status is CapabilityStatus.SUCCEEDED
    assert result.output["validation_status"] == "FAIL"
    check = result.output["checks"]["safe_area"]
    assert check == {
        "status": "FAIL",
        "expected": {"left": 0.1},
        "actual": "invalid",
    }
    assert str(abs(overflowing_value)) not in repr(result)
    assert "unknown nested value" not in repr(result)
    json.dumps(result.output, allow_nan=False)
