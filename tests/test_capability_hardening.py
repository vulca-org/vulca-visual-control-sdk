"""Regression pins for the 0.24.2 capability hardening.

Every test here failed against v0.24.1 (tag 0f66cc7b) before the matching fix
landed; see docs/superpowers/specs/2026-09-05-vulca-0.24.2-capability-hardening-design.md.
"""
from __future__ import annotations

import base64
import struct
import zlib
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from PIL import Image

from vulca.capability import CapabilityInvocation, CapabilityStatus, SideEffectState
from vulca.capability import builtin as builtin_module
from vulca.capability.builtin import (
    EditImageCapability,
    EvaluateImageCapability,
    GenerateImageCapability,
)
from vulca.capability.runtime import CapabilityProviderTimeoutError
from vulca.capability.static import AdaptStaticCapability
from vulca.providers.price_schedule import (
    estimate_openai_image_cost,
    get_openai_image_price_schedule,
)
from vulca.types import EvalResult


class FakeCapabilityRuntime:
    def __init__(self, *, provider: object | None = None, api_key: str = "k", api_key_error: Exception | None = None) -> None:
        self.provider = provider
        self.api_key_value = api_key
        self.api_key_error = api_key_error

    def image_provider(self, *, provider_name: str, binding_ref: str, constructor_options: dict) -> object:
        assert self.provider is not None
        return self.provider

    def api_key(self, *, binding_ref: str) -> str:
        if self.api_key_error is not None:
            raise self.api_key_error
        return self.api_key_value


def _invocation(capability_id: str, inputs: dict, *, options: dict | None = None) -> CapabilityInvocation:
    return CapabilityInvocation(
        invocation_id="inv_hardening",
        capability_id=capability_id,
        capability_version="1.0.0",
        inputs=inputs,
        options=options or {},
    )


def _png_bytes(size: tuple[int, int] = (32, 24), color: tuple[int, int, int] = (31, 62, 93)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _bomb_png(width: int = 30000, height: int = 30000) -> bytes:
    """A syntactically valid PNG whose header claims a gigapixel canvas."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00")) + chunk(b"IEND", b"")


def _generate_invocation() -> CapabilityInvocation:
    return _invocation(
        "vulca.image.generate",
        {"prompt": "a quiet campaign hero image", "tradition": "chinese_xieyi", "width": 64, "height": 48, "output_format": "png"},
        options={"provider": "mock", "binding_ref": "binding:mock", "constructor_options": {"model": "mock-v1"}},
    )


def _eval_invocation() -> CapabilityInvocation:
    return _invocation(
        "vulca.image.evaluate",
        {"image": base64.b64encode(_png_bytes()).decode("ascii"), "intent": "assess"},
        options={"binding_ref": "binding:vlm", "mock": True},
    )


def _eval_result(**overrides: object) -> EvalResult:
    values: dict[str, object] = {
        "score": 0.8,
        "tradition": "chinese_xieyi",
        "dimensions": {"L1": 0.8},
        "rationales": {"L1": "clear"},
        "summary": "good",
        "risk_level": "low",
        "risk_flags": [],
        "recommendations": [],
        "latency_ms": 12,
        "cost_usd": 0.045,
        "raw": {},
    }
    values.update(overrides)
    return EvalResult(**values)  # type: ignore[arg-type]


# --- 1. provider failures are classified, not reported as programming errors ---


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (httpx.ReadTimeout("slow"), "PROVIDER_TIMEOUT"),
        (httpx.ConnectError("refused"), "PROVIDER_TRANSPORT_FAILED"),
    ],
)
async def test_generate_classifies_httpx_failures_with_declared_codes(exc: Exception, code: str) -> None:
    provider = SimpleNamespace(generate=AsyncMock(side_effect=exc))
    result = await GenerateImageCapability(runtime=FakeCapabilityRuntime(provider=provider)).invoke(_generate_invocation())
    assert result.status is CapabilityStatus.FAILED
    assert result.error_code == code
    assert result.side_effect_state is SideEffectState.UNKNOWN


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "state"), [(429, SideEffectState.NOT_STARTED), (503, SideEffectState.UNKNOWN)])
async def test_generate_reports_http_rejections_as_provider_rejected(status: int, state: SideEffectState) -> None:
    request = httpx.Request("POST", "https://api.example.invalid/v1/images/generations")
    exc = httpx.HTTPStatusError("rejected", request=request, response=httpx.Response(status, request=request))
    provider = SimpleNamespace(generate=AsyncMock(side_effect=exc))
    result = await GenerateImageCapability(runtime=FakeCapabilityRuntime(provider=provider)).invoke(_generate_invocation())
    assert result.status is CapabilityStatus.FAILED
    assert result.error_code == "PROVIDER_REJECTED"
    assert result.side_effect_state is state


@pytest.mark.asyncio
async def test_generate_reports_provider_request_rejections_with_their_status() -> None:
    from vulca.providers.base import ProviderRequestRejected

    provider = SimpleNamespace(generate=AsyncMock(side_effect=ProviderRequestRejected("OpenAI billing blocked", status_code=402)))
    result = await GenerateImageCapability(runtime=FakeCapabilityRuntime(provider=provider)).invoke(_generate_invocation())
    assert result.status is CapabilityStatus.FAILED
    assert result.error_code == "PROVIDER_REJECTED"
    assert result.side_effect_state is SideEffectState.NOT_STARTED


# --- 2. disclosure fields survive the capability boundary ---


@pytest.mark.asyncio
async def test_evaluate_failed_result_is_not_reported_as_a_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_aevaluate(image, **kwargs):
        return _eval_result(failed=True, error="scorer crashed", score=0.0)

    monkeypatch.setattr(builtin_module, "aevaluate", fake_aevaluate)
    result = await EvaluateImageCapability(runtime=FakeCapabilityRuntime()).invoke(_eval_invocation())
    assert result.status is CapabilityStatus.FAILED
    assert result.error_code == "EVALUATION_FAILED"
    assert result.side_effect_state is SideEffectState.UNKNOWN


@pytest.mark.asyncio
async def test_evaluate_carries_mock_and_estimate_disclosure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_aevaluate(image, **kwargs):
        return _eval_result(mock=True, cost_is_estimate=True, cost_usd=0.0011)

    monkeypatch.setattr(builtin_module, "aevaluate", fake_aevaluate)
    result = await EvaluateImageCapability(runtime=FakeCapabilityRuntime()).invoke(_eval_invocation())
    assert result.status is CapabilityStatus.SUCCEEDED
    assert result.output["mock"] is True
    assert result.output["cost_is_estimate"] is True
    assert result.provider_receipt["costKnown"] is False


@pytest.mark.asyncio
async def test_evaluate_measured_cost_is_known(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_aevaluate(image, **kwargs):
        return _eval_result(cost_is_estimate=False, cost_usd=0.0115)

    monkeypatch.setattr(builtin_module, "aevaluate", fake_aevaluate)
    result = await EvaluateImageCapability(runtime=FakeCapabilityRuntime()).invoke(_eval_invocation())
    assert result.output["cost_is_estimate"] is False
    assert result.provider_receipt["costKnown"] is True
    assert result.cost_minor == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(("is_estimate", "known"), [(True, False), (False, True)])
async def test_edit_reports_constant_cost_as_unknown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, is_estimate: bool, known: bool) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(_png_bytes())

    async def fake_ainpaint(image, **kwargs):
        selected = Path(kwargs["output_path"])
        selected.write_bytes(_png_bytes((32, 24), color=(11, 22, 33)))
        return SimpleNamespace(variants=[str(selected)], selected=0, blended=str(selected), cost_usd=0.05, cost_is_estimate=is_estimate)

    monkeypatch.setattr(builtin_module, "ainpaint", fake_ainpaint)
    result = await EditImageCapability(runtime=FakeCapabilityRuntime()).invoke(
        _invocation(
            "vulca.image.edit",
            {"source": str(source), "region": "10,20,30,15", "instruction": "repair", "tradition": "chinese_xieyi", "reference_type": "coordinate"},
            options={"provider": "mock", "binding_ref": "binding:mock", "authorized_paths": [str(source)]},
        )
    )
    assert result.status is CapabilityStatus.SUCCEEDED
    assert result.cost_minor == 5
    assert result.provider_receipt["costKnown"] is known


def test_inpaint_result_declares_whether_its_cost_is_an_estimate() -> None:
    from vulca.types import InpaintResult

    result = InpaintResult(bbox={}, variants=[], selected=0, blended="", original="", instruction="", tradition="")
    assert result.cost_is_estimate is True


# --- 3. image handling fails closed instead of exploding ---


def test_adapt_cover_never_materialises_an_oversized_intermediate(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    requested: list[tuple[int, int]] = []
    original_resize = Image.Image.resize

    def recording_resize(self: Image.Image, size, *args, **kwargs):
        requested.append(tuple(size))
        if size[0] * size[1] > 4 * 512 * 512:
            raise AssertionError(f"oversized intermediate requested: {size}")
        return original_resize(self, size, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "resize", recording_resize)
    result = asyncio.run(
        AdaptStaticCapability().invoke(
            _invocation(
                "vulca.image.adapt_static",
                {"master": base64.b64encode(_png_bytes((1, 4000))).decode("ascii"), "width": 512, "height": 512, "media_type": "image/png", "mode": "COVER"},
            )
        )
    )
    assert result.status is CapabilityStatus.SUCCEEDED, result.error_code
    assert result.output["width"] == 512 and result.output["height"] == 512
    assert requested and all(w * h <= 4 * 512 * 512 for w, h in requested)


def test_adapt_rejects_a_decompression_bomb_as_corrupt() -> None:
    import asyncio

    result = asyncio.run(
        AdaptStaticCapability().invoke(
            _invocation(
                "vulca.image.adapt_static",
                {"master": base64.b64encode(_bomb_png()).decode("ascii"), "width": 64, "height": 64, "media_type": "image/png", "mode": "COVER"},
            )
        )
    )
    assert result.status is CapabilityStatus.FAILED
    assert result.error_code == "CORRUPT_ARTIFACT"
    assert result.side_effect_state is SideEffectState.NOT_STARTED


def test_adapt_rejects_a_request_over_the_pixel_budget_before_decoding() -> None:
    import asyncio

    result = asyncio.run(
        AdaptStaticCapability().invoke(
            _invocation(
                "vulca.image.adapt_static",
                {"master": base64.b64encode(_png_bytes()).decode("ascii"), "width": 20000, "height": 20000, "media_type": "image/png", "mode": "COVER"},
            )
        )
    )
    assert result.status is CapabilityStatus.FAILED
    assert result.error_code == "INVALID_DIMENSIONS"


@pytest.mark.asyncio
async def test_generate_rejects_a_decompression_bomb_artifact_without_raising() -> None:
    provider = SimpleNamespace(generate=AsyncMock(return_value=SimpleNamespace(image_b64=base64.b64encode(_bomb_png()).decode("ascii"), mime="image/png", metadata={})))
    result = await GenerateImageCapability(runtime=FakeCapabilityRuntime(provider=provider)).invoke(_generate_invocation())
    assert result.status is CapabilityStatus.FAILED
    assert result.error_code == "CORRUPT_ARTIFACT"


# --- 4. the price schedule really is frozen ---


def test_price_schedule_is_isolated_from_caller_mutation() -> None:
    baseline = estimate_openai_image_cost(model="dall-e-3", size="1024x1024", quality="standard").estimated_max_cost_usd
    assert baseline > 0
    schedule = get_openai_image_price_schedule()
    schedule.raw["models"]["dall-e-3"]["rates"]["standard"]["1024x1024"] = 0.0
    again = estimate_openai_image_cost(
        model="dall-e-3", size="1024x1024", quality="standard", expected_schedule_hash=schedule.schedule_hash
    )
    assert again.estimated_max_cost_usd == baseline


# --- 5. pre-flight failures never claim a side effect ---


@pytest.mark.asyncio
async def test_preflight_provider_timeout_is_not_started() -> None:
    runtime = FakeCapabilityRuntime(api_key_error=CapabilityProviderTimeoutError("secret store timed out"))
    result = await GenerateImageCapability(runtime=runtime).invoke(_generate_invocation())
    assert result.status is CapabilityStatus.FAILED
    assert result.error_code == "PROVIDER_TIMEOUT"
    assert result.side_effect_state is SideEffectState.NOT_STARTED
