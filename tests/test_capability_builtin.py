"""Contract tests for the six first-JobClass provider-backed Cells."""

from __future__ import annotations

import base64
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from vulca.capability import (
    CapabilityInvocation,
    CapabilityStatus,
    CapabilityResult,
    SideEffectState,
)
from vulca.providers.base import ImageResult
from vulca.types import EvalResult

from vulca.capability import builtin as builtin_module
from vulca.capability.builtin import (
    EditImageCapability,
    EvaluateImageCapability,
    GenerateImageCapability,
    builtin_registry,
)


class FakeCapabilityRuntime:
    """Runtime double that never resolves a real paid or network provider."""

    def __init__(
        self,
        *,
        provider: object | None = None,
        api_key: str = "",
        provider_error: Exception | None = None,
    ) -> None:
        self.provider = provider
        self.api_key_value = api_key
        self.provider_calls: list[tuple[str, str, dict]] = []
        self.api_key_calls: list[str] = []
        self.provider_error = provider_error

    def image_provider(self, *, provider_name: str, binding_ref: str, constructor_options: dict) -> object:
        self.provider_calls.append((provider_name, binding_ref, dict(constructor_options)))
        if self.provider_error is not None:
            raise self.provider_error
        if self.provider is None:
            raise AssertionError("test runtime was not given a provider")
        return self.provider

    def api_key(self, *, binding_ref: str) -> str:
        self.api_key_calls.append(binding_ref)
        return self.api_key_value


def _invocation(
    capability_id: str,
    inputs: dict,
    *,
    options: dict | None = None,
    invocation_id: str = "inv_test",
) -> CapabilityInvocation:
    return CapabilityInvocation(
        invocation_id=invocation_id,
        capability_id=capability_id,
        capability_version="1.0.0",
        inputs=inputs,
        options=options or {},
    )


def _generate_invocation(*, cost_options: dict | None = None) -> CapabilityInvocation:
    return _invocation(
        "vulca.image.generate",
        {
            "prompt": "a quiet campaign hero image",
            "tradition": "chinese_xieyi",
            "subject": "mountain and river",
            "width": 64,
            "height": 48,
            "seed": 7,
            "negative_prompt": "text artifacts",
            "input_fidelity": "high",
            "quality": "standard",
            "output_format": "png",
        },
        options={
            "provider": "mock",
            "binding_ref": "binding:mock",
            "constructor_options": {"model": "mock-v1", **(cost_options or {})},
        },
    )


def _png_bytes(
    size: tuple[int, int] = (32, 24),
    *,
    mode: str = "RGB",
    color: tuple[int, ...] = (31, 62, 93),
) -> bytes:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new(mode, size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_builtin_registry_exposes_exact_first_jobclass_cells() -> None:
    registry = builtin_registry(runtime=FakeCapabilityRuntime())

    expected = {
        "vulca.image.generate",
        "vulca.image.edit",
        "vulca.image.compose_static",
        "vulca.image.adapt_static",
        "vulca.image.validate_static",
        "vulca.image.evaluate",
    }
    for capability_id in expected:
        capability = registry.resolve(capability_id, "1.0.0")
        assert capability.manifest.capability_id == capability_id
        assert capability.manifest.version == "1.0.0"


@pytest.mark.asyncio
async def test_generate_adapter_returns_hashed_artifact_and_calls_provider_once() -> None:
    provider = SimpleNamespace(
        generate=AsyncMock(
            return_value=ImageResult(
                image_b64=base64.b64encode(b"png-bytes").decode("ascii"),
                mime="image/png",
                metadata={
                    "provider": "mock",
                    "model": "mock-v1",
                    "request_id": "req_test",
                    "cost_usd": 0.04,
                    "api_key": "test-secret-never-record",
                },
            )
        )
    )
    runtime = FakeCapabilityRuntime(provider=provider, api_key="test-secret-never-record")

    result = await GenerateImageCapability(runtime=runtime).invoke(_generate_invocation())

    assert result.status is CapabilityStatus.SUCCEEDED
    assert result.side_effect_state is SideEffectState.COMPLETED
    assert result.artifacts[0].content == b"png-bytes"
    assert result.artifacts[0].sha256 == (
        "ea80334363eed145dfeee51ebae7dc3f1cd7d0c7879f8bfd2070c061d3c33f56"
    )
    assert result.cost_minor == 4
    assert result.provider_receipt["provider"] == "mock"
    assert result.provider_receipt["model"] == "mock-v1"
    assert result.provider_receipt["request_id"] == "req_test"
    assert "api_key" not in result.provider_receipt
    assert "test-secret-never-record" not in repr(result)
    provider.generate.assert_awaited_once()
    call = provider.generate.await_args
    assert call.args == ("a quiet campaign hero image",)
    assert call.kwargs["tradition"] == "chinese_xieyi"
    assert call.kwargs["subject"] == "mountain and river"
    assert call.kwargs["width"] == 64
    assert call.kwargs["height"] == 48
    assert call.kwargs["seed"] == 7
    assert call.kwargs["negative_prompt"] == "text artifacts"
    assert call.kwargs["input_fidelity"] == "high"
    assert call.kwargs["quality"] == "standard"
    assert call.kwargs["output_format"] == "png"
    assert runtime.provider_calls == [("mock", "binding:mock", {"model": "mock-v1"})]


@pytest.mark.asyncio
async def test_generate_cost_rounds_half_up_and_absent_cost_is_unknown() -> None:
    for metadata, expected_minor, expected_known in (
        ({"cost_usd": 0.045}, 5, True),
        ({}, 0, False),
    ):
        provider = SimpleNamespace(
            generate=AsyncMock(
                return_value=ImageResult(
                    image_b64=base64.b64encode(b"bytes").decode("ascii"),
                    mime="image/png",
                    metadata=metadata,
                )
            )
        )
        result = await GenerateImageCapability(
            runtime=FakeCapabilityRuntime(provider=provider)
        ).invoke(_generate_invocation())

        assert result.cost_minor == expected_minor
        assert result.provider_receipt["costKnown"] is expected_known


@pytest.mark.asyncio
async def test_generate_never_calls_legacy_create_or_evaluate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = SimpleNamespace(
        generate=AsyncMock(
            return_value=ImageResult(
                image_b64=base64.b64encode(b"bytes").decode("ascii"),
                mime="image/png",
            )
        )
    )

    evaluate = AsyncMock()
    monkeypatch.setattr(builtin_module, "aevaluate", evaluate)

    result = await GenerateImageCapability(
        runtime=FakeCapabilityRuntime(provider=provider)
    ).invoke(_generate_invocation())

    assert result.status is CapabilityStatus.SUCCEEDED
    assert not hasattr(builtin_module, "acreate")
    assert "acreate" not in inspect.getsource(builtin_module)
    evaluate.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_provider_construction_failure_is_not_started() -> None:
    runtime = FakeCapabilityRuntime(provider_error=ValueError("bad test-secret"))

    result = await GenerateImageCapability(runtime=runtime).invoke(_generate_invocation())

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.NOT_STARTED
    assert result.error_code == "PROVIDER_CONSTRUCTION_FAILED"
    assert "bad test-secret" not in repr(result)


@pytest.mark.asyncio
async def test_generate_timeout_is_unknown_without_reconciliation_receipt() -> None:
    provider = SimpleNamespace(generate=AsyncMock(side_effect=TimeoutError("network test-secret")))

    result = await GenerateImageCapability(
        runtime=FakeCapabilityRuntime(provider=provider)
    ).invoke(_generate_invocation())

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.UNKNOWN
    assert result.error_code == "PROVIDER_TIMEOUT"
    assert "test-secret" not in repr(result)
    provider.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_transport_failure_is_unknown_and_is_not_retried() -> None:
    provider = SimpleNamespace(
        generate=AsyncMock(side_effect=ConnectionError("connection test-secret"))
    )

    result = await GenerateImageCapability(
        runtime=FakeCapabilityRuntime(provider=provider)
    ).invoke(_generate_invocation())

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.UNKNOWN
    assert result.error_code == "PROVIDER_TRANSPORT_FAILED"
    provider.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_generation_is_not_reported_as_success() -> None:
    provider = SimpleNamespace(
        generate=AsyncMock(return_value=ImageResult(image_b64="", mime="image/png"))
    )

    result = await GenerateImageCapability(
        runtime=FakeCapabilityRuntime(provider=provider)
    ).invoke(_generate_invocation())

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.UNKNOWN
    assert result.error_code == "EMPTY_ARTIFACT"


@pytest.mark.asyncio
async def test_empty_edit_is_not_reported_as_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(_png_bytes())
    monkeypatch.setattr(
        builtin_module,
        "ainpaint",
        AsyncMock(return_value=SimpleNamespace(variants=[], selected=0, blended="", cost_usd=0.0)),
    )

    result = await EditImageCapability(runtime=FakeCapabilityRuntime()).invoke(
        _invocation(
            "vulca.image.edit",
            {
                "source": str(source),
                "region": "10,20,30,15",
                "instruction": "repair the bounded region",
                "reference_type": "coordinate",
            },
            options={"provider": "mock", "binding_ref": "binding:mock"},
        )
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.UNKNOWN
    assert result.error_code == "EMPTY_ARTIFACT"


@pytest.mark.asyncio
async def test_programming_errors_propagate_instead_of_being_provider_failures() -> None:
    provider = SimpleNamespace(generate=AsyncMock(side_effect=RuntimeError("programming bug")))

    with pytest.raises(RuntimeError, match="programming bug"):
        await GenerateImageCapability(
            runtime=FakeCapabilityRuntime(provider=provider)
        ).invoke(_generate_invocation())


@pytest.mark.asyncio
async def test_edit_forwards_one_bounded_coordinate_variant_and_cleans_only_wrapper_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source.png"
    source_bytes = _png_bytes()
    source.write_bytes(source_bytes)
    captured: dict = {}

    async def fake_ainpaint(image, **kwargs):
        kwargs["image"] = image
        captured.update(kwargs)
        selected = Path(kwargs["output_path"])
        selected.write_bytes(b"edited-bytes")
        return SimpleNamespace(
            variants=[str(selected)],
            selected=0,
            blended=str(selected),
            cost_usd=0.045,
        )

    monkeypatch.setattr(builtin_module, "ainpaint", fake_ainpaint)
    runtime = FakeCapabilityRuntime(api_key="test-secret-never-record")
    invocation = _invocation(
        "vulca.image.edit",
        {
            "source": str(source),
            "region": "10,20,30,15",
            "instruction": "repair the bounded region",
            "tradition": "chinese_xieyi",
            "reference_type": "coordinate",
        },
        options={"provider": "mock", "binding_ref": "binding:mock"},
    )

    result = await EditImageCapability(runtime=runtime).invoke(invocation)

    assert result.status is CapabilityStatus.SUCCEEDED
    assert result.cost_minor == 5
    assert result.artifacts[0].content == b"edited-bytes"
    assert result.output["source_sha256"]
    assert result.output["output_sha256"]
    assert captured["image"] == str(source)
    assert captured["region"] == "10,20,30,15"
    assert captured["mask_path"] == ""
    assert captured["count"] == 1
    assert captured["select"] == 0
    assert captured["api_key"] == "test-secret-never-record"
    assert not Path(captured["output_path"]).exists()
    assert source.read_bytes() == source_bytes
    assert "test-secret-never-record" not in repr(result)


@pytest.mark.asyncio
async def test_edit_accepts_only_same_size_mask_and_never_uses_natural_language_region(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source.png"
    mask = tmp_path / "mask.png"
    source_bytes = _png_bytes((32, 24))
    source.write_bytes(source_bytes)
    mask.write_bytes(_png_bytes((32, 24), mode="RGBA", color=(0, 0, 0, 0)))
    calls: list[dict] = []

    async def fake_ainpaint(image, **kwargs):
        kwargs["image"] = image
        calls.append(kwargs)
        output = Path(kwargs["output_path"])
        output.write_bytes(b"edited")
        return SimpleNamespace(variants=[str(output)], selected=0, blended=str(output), cost_usd=0)

    monkeypatch.setattr(builtin_module, "ainpaint", fake_ainpaint)
    runtime = FakeCapabilityRuntime()

    result = await EditImageCapability(runtime=runtime).invoke(
        _invocation(
            "vulca.image.edit",
            {
                "source": str(source),
                "mask": str(mask),
                "instruction": "replace the approved region",
                "tradition": "default",
                "reference_type": "mask",
            },
            options={"provider": "mock", "binding_ref": "binding:mock"},
        )
    )

    assert result.status is CapabilityStatus.SUCCEEDED
    assert calls[0]["mask_path"] == str(mask)
    assert calls[0]["region"] == ""
    assert calls[0]["count"] == 1
    assert calls[0]["select"] == 0

    invalid = await EditImageCapability(runtime=runtime).invoke(
        _invocation(
            "vulca.image.edit",
            {
                "source": str(source),
                "region": "the sky",
                "instruction": "edit it",
                "reference_type": "coordinate",
            },
            options={"provider": "mock", "binding_ref": "binding:mock"},
            invocation_id="inv_invalid",
        )
    )
    assert invalid.status is CapabilityStatus.FAILED
    assert invalid.side_effect_state is SideEffectState.NOT_STARTED
    assert invalid.error_code == "INVALID_REGION"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_edit_rejects_a_different_size_mask_before_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source.png"
    mask = tmp_path / "mask.png"
    source.write_bytes(_png_bytes((32, 24)))
    mask.write_bytes(_png_bytes((16, 12), mode="RGBA", color=(0, 0, 0, 0)))
    ainpaint = AsyncMock()
    monkeypatch.setattr(builtin_module, "ainpaint", ainpaint)

    result = await EditImageCapability(runtime=FakeCapabilityRuntime()).invoke(
        _invocation(
            "vulca.image.edit",
            {
                "source": str(source),
                "mask": str(mask),
                "instruction": "replace the approved region",
                "reference_type": "mask",
            },
            options={"provider": "mock", "binding_ref": "binding:mock"},
        )
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.NOT_STARTED
    assert result.error_code == "MASK_SIZE_MISMATCH"
    ainpaint.assert_not_awaited()


def _eval_result(*, secret: str = "") -> EvalResult:
    return EvalResult(
        score=0.8,
        tradition="chinese_xieyi",
        dimensions={"L1": 0.8, "L2": 0.7, "L3": 0.9, "L4": 0.6, "L5": 0.75},
        rationales={"L1": "clear", "L2": "sound"},
        summary="good",
        risk_level="low",
        risk_flags=[],
        recommendations=["keep the restraint"],
        latency_ms=12,
        cost_usd=0.045,
        raw={"api_key": secret},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("use_base64", (False, True))
async def test_evaluate_maps_path_or_base64_to_json_safe_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, use_base64: bool
) -> None:
    image_path = tmp_path / "image.png"
    image_path.write_bytes(_png_bytes())
    image_input = (
        base64.b64encode(image_path.read_bytes()).decode("ascii")
        if use_base64
        else str(image_path)
    )
    captured: dict = {}

    async def fake_aevaluate(image, **kwargs):
        captured["image"] = image
        captured["kwargs"] = kwargs
        return _eval_result(secret="test-secret-never-record")

    monkeypatch.setattr(builtin_module, "aevaluate", fake_aevaluate)
    runtime = FakeCapabilityRuntime(api_key="test-secret-never-record")
    result = await EvaluateImageCapability(runtime=runtime).invoke(
        _invocation(
            "vulca.image.evaluate",
            {"image": image_input, "intent": "assess the hero", "tradition": "chinese_xieyi"},
            options={"binding_ref": "binding:vlm", "mock": True},
            invocation_id=f"inv_eval_{use_base64}",
        )
    )

    assert result.status is CapabilityStatus.SUCCEEDED
    assert result.artifacts == ()
    assert result.output["score"] == 0.8
    assert result.output["dimensions"]["L1"] == 0.8
    assert result.output["rationales"]["L1"] == "clear"
    assert result.output["risk"] == "low"
    assert result.output["recommendations"] == ["keep the restraint"]
    assert result.output["latency_ms"] == 12
    assert result.cost_minor == 5
    assert "raw" not in result.output
    assert "test-secret-never-record" not in repr(result)
    if use_base64:
        assert captured["image"].startswith("data:image/png;base64,")
    else:
        assert captured["image"] == str(image_path)
    assert captured["kwargs"]["api_key"] == "test-secret-never-record"


@pytest.mark.asyncio
async def test_evaluate_provider_timeout_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_aevaluate(image, **kwargs):
        raise TimeoutError("evaluation test-secret")

    monkeypatch.setattr(builtin_module, "aevaluate", fake_aevaluate)
    invocation = _invocation(
        "vulca.image.evaluate",
        {"image": base64.b64encode(b"image").decode("ascii"), "intent": "assess"},
        options={"binding_ref": "binding:vlm"},
    )

    result = await EvaluateImageCapability(
        runtime=FakeCapabilityRuntime(api_key="test-secret-never-record")
    ).invoke(invocation)

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.UNKNOWN
    assert result.error_code == "PROVIDER_TIMEOUT"
    assert "test-secret" not in repr(result)


@pytest.mark.asyncio
async def test_evaluate_programming_errors_propagate(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_aevaluate(image, **kwargs):
        raise RuntimeError("programming bug")

    monkeypatch.setattr(builtin_module, "aevaluate", fake_aevaluate)

    with pytest.raises(RuntimeError, match="programming bug"):
        await EvaluateImageCapability(runtime=FakeCapabilityRuntime()).invoke(
            _invocation(
                "vulca.image.evaluate",
                {"image": base64.b64encode(b"image").decode("ascii"), "intent": "assess"},
                options={"binding_ref": "binding:vlm"},
            )
        )
