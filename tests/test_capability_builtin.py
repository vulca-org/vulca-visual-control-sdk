"""Contract tests for the six first-JobClass provider-backed Cells."""

from __future__ import annotations

import base64
import inspect
import logging
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from vulca.capability import (
    CapabilityInvocation,
    CapabilityMaturity,
    CapabilityStatus,
    CapabilityResult,
    SideEffectState,
)
from vulca.providers.base import ImageResult
from vulca.types import EvalResult

from vulca.capability import builtin as builtin_module
from vulca.capability import runtime as runtime_module
from vulca.capability.builtin import (
    EditImageCapability,
    EvaluateImageCapability,
    GenerateImageCapability,
    builtin_registry,
)
from vulca.capability.runtime import (
    CapabilityProviderConstructionError,
    CapabilityProviderTimeoutError,
    CapabilityProviderTransportError,
    CapabilityProviderUnsupportedError,
    EnvironmentCapabilityRuntime,
)


class FakeCapabilityRuntime:
    """Runtime double that never resolves a real paid or network provider."""

    def __init__(
        self,
        *,
        provider: object | None = None,
        api_key: str = "",
        provider_error: Exception | None = None,
        api_key_error: Exception | None = None,
    ) -> None:
        self.provider = provider
        self.api_key_value = api_key
        self.provider_calls: list[tuple[str, str, dict]] = []
        self.api_key_calls: list[str] = []
        self.provider_error = provider_error
        self.api_key_error = api_key_error

    def image_provider(self, *, provider_name: str, binding_ref: str, constructor_options: dict) -> object:
        self.provider_calls.append((provider_name, binding_ref, dict(constructor_options)))
        if self.provider_error is not None:
            raise self.provider_error
        if self.provider is None:
            raise AssertionError("test runtime was not given a provider")
        return self.provider

    def api_key(self, *, binding_ref: str) -> str:
        self.api_key_calls.append(binding_ref)
        if self.api_key_error is not None:
            raise self.api_key_error
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


def _jpeg_bytes(size: tuple[int, int] = (32, 24)) -> bytes:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", size, (31, 62, 93)).save(buffer, format="JPEG")
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
    assert set(registry._capabilities) == {(capability_id, "1.0.0") for capability_id in expected}
    expected_manifests = {
        "vulca.image.generate": (
            "image-generation",
            ("provider_binding", "secret_binding"),
            (),
            ("PROVIDER_TIMEOUT", "PROVIDER_TRANSPORT_FAILED"),
            False,
        ),
        "vulca.image.edit": (
            "image-edit",
            ("source_binding", "provider_binding", "secret_binding"),
            (),
            ("PROVIDER_TIMEOUT", "PROVIDER_TRANSPORT_FAILED"),
            False,
        ),
        "vulca.image.compose_static": ("static-composition", ("authorised_inputs",), (), (), True),
        "vulca.image.adapt_static": ("static-adaptation", ("authorised_inputs",), (), (), True),
        "vulca.image.validate_static": ("static-validation", ("authorised_inputs",), (), (), True),
        "vulca.image.evaluate": (
            "image-evaluation",
            ("evaluator_binding", "secret_binding"),
            ("independent_vlm",),
            ("PROVIDER_TIMEOUT", "PROVIDER_TRANSPORT_FAILED"),
            False,
        ),
    }
    assert set(expected_manifests) == expected
    for capability_id, (kind, authorities, evaluators, retryable, deterministic) in expected_manifests.items():
        capability = registry.resolve(capability_id, "1.0.0")
        manifest = capability.manifest
        assert manifest.capability_id == capability_id
        assert manifest.version == "1.0.0"
        assert manifest.kind == kind
        assert manifest.owner == "vulca"
        assert manifest.maturity is CapabilityMaturity.NATIVE
        assert manifest.input_schema == {}
        assert manifest.output_schema == {}
        assert manifest.authority_requirements == authorities
        assert manifest.evaluator_bindings == evaluators
        assert manifest.retryable_codes == retryable
        assert manifest.deterministic is deterministic


@pytest.mark.asyncio
async def test_generate_adapter_returns_hashed_artifact_and_calls_provider_once() -> None:
    generated_bytes = _png_bytes()
    provider = SimpleNamespace(
        generate=AsyncMock(
            return_value=ImageResult(
                image_b64=base64.b64encode(generated_bytes).decode("ascii"),
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
    assert result.artifacts[0].content == generated_bytes
    assert result.artifacts[0].sha256 == "1e6a203ef9b5909254d20328a60d90d4085623a8f4f176068cdfe4a8c7bef3db"
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
                    image_b64=base64.b64encode(_png_bytes()).decode("ascii"),
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
                image_b64=base64.b64encode(_png_bytes()).decode("ascii"),
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
async def test_generate_declared_provider_construction_failure_is_not_started() -> None:
    runtime = FakeCapabilityRuntime(
        provider_error=CapabilityProviderConstructionError("bad test-secret")
    )

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
async def test_generate_rejects_corrupt_declared_png_without_artifact() -> None:
    provider = SimpleNamespace(
        generate=AsyncMock(
            return_value=ImageResult(
                image_b64=base64.b64encode(b"not-a-real-image").decode("ascii"),
                mime="image/png",
            )
        )
    )

    result = await GenerateImageCapability(
        runtime=FakeCapabilityRuntime(provider=provider)
    ).invoke(_generate_invocation())

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.UNKNOWN
    assert result.error_code == "CORRUPT_ARTIFACT"
    assert result.artifacts == ()
    provider.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_rejects_actual_image_mime_mismatch_without_artifact() -> None:
    provider = SimpleNamespace(
        generate=AsyncMock(
            return_value=ImageResult(
                image_b64=base64.b64encode(_jpeg_bytes()).decode("ascii"),
                mime="image/png",
            )
        )
    )

    result = await GenerateImageCapability(
        runtime=FakeCapabilityRuntime(provider=provider)
    ).invoke(_generate_invocation())

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.UNKNOWN
    assert result.error_code == "INVALID_MEDIA_TYPE"
    assert result.artifacts == ()
    provider.generate.assert_awaited_once()


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
            options={
                "provider": "mock",
                "binding_ref": "binding:mock",
                "authorized_paths": [str(source)],
            },
        )
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.UNKNOWN
    assert result.error_code == "EMPTY_ARTIFACT"


@pytest.mark.asyncio
async def test_programming_errors_propagate_sanitized_by_type() -> None:
    provider = SimpleNamespace(generate=AsyncMock(side_effect=RuntimeError("programming bug")))

    with pytest.raises(RuntimeError, match="capability programming error") as caught:
        await GenerateImageCapability(
            runtime=FakeCapabilityRuntime(provider=provider)
        ).invoke(_generate_invocation())
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


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
        selected.write_bytes(_png_bytes((32, 24), color=(11, 22, 33)))
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
        options={
            "provider": "mock",
            "binding_ref": "binding:mock",
            "authorized_paths": [str(source)],
        },
    )

    result = await EditImageCapability(runtime=runtime).invoke(invocation)

    assert result.status is CapabilityStatus.SUCCEEDED
    assert result.cost_minor == 5
    assert result.artifacts[0].content == _png_bytes((32, 24), color=(11, 22, 33))
    assert result.output["source_sha256"]
    assert result.output["output_sha256"]
    assert captured["image"] == str(source)
    assert captured["region"] == "10,20,30,15"
    assert captured["mask_path"] == ""
    assert captured["count"] == 1
    assert captured["select"] == 0
    assert captured["api_key"] == "test-secret-never-record"
    assert Path(captured["scratch_dir"]).is_absolute()
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
        output.write_bytes(_png_bytes((32, 24), color=(11, 22, 33)))
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
            options={
                "provider": "mock",
                "binding_ref": "binding:mock",
                "authorized_paths": [str(source), str(mask)],
            },
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
            options={
                "provider": "mock",
                "binding_ref": "binding:mock",
                "authorized_paths": [str(source)],
            },
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
            options={
                "provider": "mock",
                "binding_ref": "binding:mock",
                "authorized_paths": [str(source), str(mask)],
            },
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
            options={
                "binding_ref": "binding:vlm",
                "mock": True,
                **({"authorized_paths": [str(image_path)]} if not use_base64 else {}),
            },
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
async def test_evaluate_rejects_corrupt_base64_before_evaluator_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluator = AsyncMock()
    monkeypatch.setattr(builtin_module, "aevaluate", evaluator)

    result = await EvaluateImageCapability(runtime=FakeCapabilityRuntime()).invoke(
        _invocation(
            "vulca.image.evaluate",
            {
                "image": base64.b64encode(b"not-a-real-image").decode("ascii"),
                "intent": "assess",
            },
            options={"binding_ref": "binding:vlm"},
        )
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.NOT_STARTED
    assert result.error_code == "CORRUPT_ARTIFACT"
    assert result.artifacts == ()
    evaluator.assert_not_awaited()


@pytest.mark.asyncio
async def test_evaluate_provider_timeout_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_aevaluate(image, **kwargs):
        raise TimeoutError("evaluation test-secret")

    monkeypatch.setattr(builtin_module, "aevaluate", fake_aevaluate)
    invocation = _invocation(
        "vulca.image.evaluate",
        {"image": base64.b64encode(_png_bytes()).decode("ascii"), "intent": "assess"},
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

    with pytest.raises(RuntimeError, match="capability programming error") as caught:
        await EvaluateImageCapability(runtime=FakeCapabilityRuntime()).invoke(
            _invocation(
                "vulca.image.evaluate",
                {"image": base64.b64encode(_png_bytes()).decode("ascii"), "intent": "assess"},
                options={"binding_ref": "binding:vlm"},
            )
        )
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def _edit_invocation_for_source(source: Path, *, invocation_id: str = "inv_edit_c1") -> CapabilityInvocation:
    return _invocation(
        "vulca.image.edit",
        {
            "source": str(source),
            "region": "0,0,50,50",
            "instruction": "replace the bounded region",
            "reference_type": "coordinate",
        },
        options={
            "provider": "mock",
            "binding_ref": "binding:mock",
            "authorized_paths": [str(source)],
        },
        invocation_id=invocation_id,
    )


@pytest.mark.asyncio
async def test_edit_c1_consumes_blended_full_canvas_and_deletes_only_owned_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(_png_bytes((32, 24), color=(10, 20, 30)))
    caller_root = tmp_path / "vulca-inpaint-caller-owned"
    caller_root.mkdir()
    caller_sentinel = caller_root / "must-survive.txt"
    caller_sentinel.write_text("caller-owned")
    captured: dict[str, object] = {}

    async def fake_ainpaint(image: str, **kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        root = Path(str(kwargs["scratch_dir"]))
        repaint = root / "repaint.png"
        blended = root / "blended.png"
        repaint.write_bytes(_png_bytes((8, 8), color=(255, 0, 0)))
        blended_bytes = _png_bytes((32, 24), color=(0, 0, 255))
        blended.write_bytes(blended_bytes)
        return SimpleNamespace(
            variants=[str(repaint)],
            selected=0,
            blended=str(blended),
            cost_usd=0.01,
        )

    monkeypatch.setattr(builtin_module, "ainpaint", fake_ainpaint)
    result = await EditImageCapability(runtime=FakeCapabilityRuntime()).invoke(
        _edit_invocation_for_source(source)
    )

    assert result.status is CapabilityStatus.SUCCEEDED
    assert result.artifacts[0].content == _png_bytes((32, 24), color=(0, 0, 255))
    assert result.artifacts[0].content != _png_bytes((8, 8), color=(255, 0, 0))
    assert caller_root.exists()
    assert caller_sentinel.read_text() == "caller-owned"
    owned_root = Path(str(captured["scratch_dir"]))
    assert owned_root.exists() is False
    assert Path(str(captured["output_path"])).parent == owned_root
    assert Path(str(captured["output"])).parent == owned_root


@pytest.mark.asyncio
@pytest.mark.parametrize("blended_kind", ["outside", "relative", "symlink"])
async def test_edit_c1_rejects_output_escape_without_deleting_caller_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blended_kind: str
) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(_png_bytes())
    outside = tmp_path / "outside.png"
    outside_bytes = _png_bytes()
    outside.write_bytes(outside_bytes)
    caller_root = tmp_path / "vulca-inpaint-caller-owned"
    caller_root.mkdir()
    caller_file = caller_root / "keep.png"
    caller_file.write_bytes(outside_bytes)

    async def fake_ainpaint(image: str, **kwargs: object) -> SimpleNamespace:
        root = Path(str(kwargs["scratch_dir"]))
        variant = root / "variant.png"
        variant.write_bytes(_png_bytes())
        if blended_kind == "outside":
            blended = str(caller_file)
        elif blended_kind == "relative":
            blended = "relative.png"
        else:
            blended_path = root / "blended.png"
            blended_path.symlink_to(caller_file)
            blended = str(blended_path)
        return SimpleNamespace(variants=[str(variant)], selected=0, blended=blended, cost_usd=0)

    monkeypatch.setattr(builtin_module, "ainpaint", fake_ainpaint)
    result = await EditImageCapability(runtime=FakeCapabilityRuntime()).invoke(
        _edit_invocation_for_source(source, invocation_id=f"inv_{blended_kind}")
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.UNKNOWN
    assert result.error_code == "OUTPUT_OUTSIDE_SCRATCH"
    assert caller_root.exists()
    assert caller_file.read_bytes() == outside_bytes


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("variants_count", "selected"),
    [(2, 0), (1, 1)],
)
async def test_edit_c1_rejects_multiple_variants_and_nonzero_selection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    variants_count: int,
    selected: int,
) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(_png_bytes())

    async def fake_ainpaint(image: str, **kwargs: object) -> SimpleNamespace:
        root = Path(str(kwargs["scratch_dir"]))
        variants = []
        for index in range(variants_count):
            path = root / f"variant-{index}.png"
            path.write_bytes(_png_bytes())
            variants.append(str(path))
        blended = root / "blended.png"
        blended.write_bytes(_png_bytes())
        return SimpleNamespace(
            variants=variants,
            selected=selected,
            blended=str(blended),
            cost_usd=0,
        )

    monkeypatch.setattr(builtin_module, "ainpaint", fake_ainpaint)
    result = await EditImageCapability(runtime=FakeCapabilityRuntime()).invoke(
        _edit_invocation_for_source(source, invocation_id=f"inv_variants_{variants_count}_{selected}")
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.error_code == "INVALID_VARIANTS"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("output_kind", "expected_code"),
    [("corrupt", "CORRUPT_ARTIFACT"), ("wrong_size", "DIMENSION_MISMATCH")],
)
async def test_edit_c1_rejects_corrupt_or_wrong_size_blended_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    output_kind: str,
    expected_code: str,
) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(_png_bytes((32, 24)))

    async def fake_ainpaint(image: str, **kwargs: object) -> SimpleNamespace:
        root = Path(str(kwargs["scratch_dir"]))
        variant = root / "variant.png"
        blended = root / "blended.png"
        variant.write_bytes(_png_bytes((32, 24)))
        if output_kind == "corrupt":
            blended.write_bytes(b"not-an-image")
        else:
            blended.write_bytes(_png_bytes((8, 8)))
        return SimpleNamespace(variants=[str(variant)], selected=0, blended=str(blended), cost_usd=0)

    monkeypatch.setattr(builtin_module, "ainpaint", fake_ainpaint)
    result = await EditImageCapability(runtime=FakeCapabilityRuntime()).invoke(
        _edit_invocation_for_source(source, invocation_id=f"inv_{output_kind}")
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.error_code == expected_code
    assert result.artifacts == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("exception_type", [RuntimeError, ValueError, TypeError])
async def test_unexpected_provider_errors_preserve_type_but_sanitize_all_adapters(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    exception_type: type[Exception],
) -> None:
    secret = f"raw-secret-{exception_type.__name__}"
    caplog.set_level(logging.DEBUG)
    provider = SimpleNamespace(generate=AsyncMock(side_effect=exception_type(secret)))

    with pytest.raises(exception_type, match="capability programming error") as generate_error:
        await GenerateImageCapability(runtime=FakeCapabilityRuntime(provider=provider)).invoke(
            _generate_invocation()
        )
    assert generate_error.value.__cause__ is None
    assert generate_error.value.__context__ is None
    assert secret not in repr(generate_error.value)

    source = tmp_path / "source.png"
    source.write_bytes(_png_bytes())

    async def bad_ainpaint(image: str, **kwargs: object) -> object:
        raise exception_type(secret)

    monkeypatch.setattr(builtin_module, "ainpaint", bad_ainpaint)
    with pytest.raises(exception_type, match="capability programming error") as edit_error:
        await EditImageCapability(runtime=FakeCapabilityRuntime()).invoke(
            _edit_invocation_for_source(source, invocation_id=f"inv_edit_{exception_type.__name__}")
        )
    assert edit_error.value.__cause__ is None
    assert edit_error.value.__context__ is None
    assert secret not in repr(edit_error.value)

    async def bad_aevaluate(image: str, **kwargs: object) -> object:
        raise exception_type(secret)

    monkeypatch.setattr(builtin_module, "aevaluate", bad_aevaluate)
    with pytest.raises(exception_type, match="capability programming error") as evaluate_error:
        await EvaluateImageCapability(runtime=FakeCapabilityRuntime()).invoke(
            _invocation(
                "vulca.image.evaluate",
                {"image": base64.b64encode(_png_bytes()).decode("ascii"), "intent": "assess"},
                options={"binding_ref": "binding:vlm"},
                invocation_id=f"inv_eval_{exception_type.__name__}",
            )
        )
    assert evaluate_error.value.__cause__ is None
    assert evaluate_error.value.__context__ is None
    assert secret not in repr(evaluate_error.value)
    assert secret not in caplog.text


def test_runtime_construction_boundary_drops_raw_exception_context(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "provider-construction-context-secret"

    def fail_provider_lookup(*args: object, **kwargs: object) -> object:
        raise ValueError(secret)

    monkeypatch.setattr(runtime_module, "get_image_provider", fail_provider_lookup)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(CapabilityProviderConstructionError) as caught:
        EnvironmentCapabilityRuntime().image_provider(
            provider_name="broken",
            binding_ref="binding:broken",
            constructor_options={},
        )

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert secret not in str(caught.value)
    assert secret not in caplog.text


@pytest.mark.parametrize("exception_type", (RuntimeError, TypeError, OSError))
def test_runtime_provider_lookup_programming_errors_preserve_type_without_secret_graph(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    exception_type: type[Exception],
) -> None:
    secret = f"provider-lookup-{exception_type.__name__}-secret"

    def fail_provider_lookup(*args: object, **kwargs: object) -> object:
        raise exception_type(secret)

    monkeypatch.setattr(runtime_module, "get_image_provider", fail_provider_lookup)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(exception_type, match="^capability programming error$") as caught:
        EnvironmentCapabilityRuntime().image_provider(
            provider_name="broken",
            binding_ref="binding:broken",
            constructor_options={},
        )

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert secret not in str(caught.value)
    assert secret not in repr(caught.value)
    assert secret not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("boundary_type", "error_code"),
    [
        (CapabilityProviderTimeoutError, "PROVIDER_TIMEOUT"),
        (CapabilityProviderTransportError, "PROVIDER_TRANSPORT_FAILED"),
        (CapabilityProviderUnsupportedError, "PROVIDER_UNSUPPORTED"),
    ],
)
async def test_declared_provider_boundaries_map_to_unknown_without_raw_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    boundary_type: type[Exception],
    error_code: str,
) -> None:
    secret = "boundary-secret"
    caplog.set_level(logging.DEBUG)
    provider = SimpleNamespace(generate=AsyncMock(side_effect=boundary_type(secret)))
    generate = await GenerateImageCapability(runtime=FakeCapabilityRuntime(provider=provider)).invoke(
        _generate_invocation()
    )
    assert generate.status is CapabilityStatus.FAILED
    assert generate.side_effect_state is SideEffectState.UNKNOWN
    assert generate.error_code == error_code
    assert secret not in repr(generate)
    provider.generate.assert_awaited_once()

    source = tmp_path / "source.png"
    source.write_bytes(_png_bytes())

    async def edit_boundary(image: str, **kwargs: object) -> object:
        raise boundary_type(secret)

    monkeypatch.setattr(builtin_module, "ainpaint", edit_boundary)
    edit = await EditImageCapability(runtime=FakeCapabilityRuntime()).invoke(
        _edit_invocation_for_source(source, invocation_id=f"inv_edit_{error_code}")
    )
    assert edit.status is CapabilityStatus.FAILED
    expected_call_state = (
        SideEffectState.NOT_STARTED
        if boundary_type is CapabilityProviderUnsupportedError
        else SideEffectState.UNKNOWN
    )
    assert edit.side_effect_state is expected_call_state
    assert edit.error_code == error_code
    assert secret not in repr(edit)

    async def evaluate_boundary(image: str, **kwargs: object) -> object:
        raise boundary_type(secret)

    monkeypatch.setattr(builtin_module, "aevaluate", evaluate_boundary)
    evaluate = await EvaluateImageCapability(runtime=FakeCapabilityRuntime()).invoke(
        _invocation(
            "vulca.image.evaluate",
            {"image": base64.b64encode(_png_bytes()).decode("ascii"), "intent": "assess"},
            options={"binding_ref": "binding:vlm"},
            invocation_id=f"inv_eval_{error_code}",
        )
    )
    assert evaluate.status is CapabilityStatus.FAILED
    assert evaluate.side_effect_state is expected_call_state
    assert evaluate.error_code == error_code
    assert secret not in repr(evaluate)
    assert secret not in caplog.text


@pytest.mark.asyncio
async def test_declared_construction_and_unsupported_failures_are_not_started() -> None:
    secret = "construction-secret"
    for boundary_type, code in (
        (CapabilityProviderConstructionError, "PROVIDER_CONSTRUCTION_FAILED"),
        (CapabilityProviderUnsupportedError, "PROVIDER_UNSUPPORTED"),
    ):
        runtime = FakeCapabilityRuntime(provider_error=boundary_type(secret))
        result = await GenerateImageCapability(runtime=runtime).invoke(_generate_invocation())
        assert result.status is CapabilityStatus.FAILED
        assert result.side_effect_state is SideEffectState.NOT_STARTED
        assert result.error_code == code
        assert secret not in repr(result)


@pytest.mark.asyncio
async def test_declared_construction_failure_during_operation_is_not_started(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "operation-construction-secret"
    provider = SimpleNamespace(
        generate=AsyncMock(side_effect=CapabilityProviderConstructionError(secret))
    )
    generated = await GenerateImageCapability(
        runtime=FakeCapabilityRuntime(provider=provider)
    ).invoke(_generate_invocation())
    assert generated.status is CapabilityStatus.FAILED
    assert generated.side_effect_state is SideEffectState.NOT_STARTED
    assert generated.error_code == "PROVIDER_CONSTRUCTION_FAILED"
    assert secret not in repr(generated)

    async def evaluate_construction(image: str, **kwargs: object) -> object:
        raise CapabilityProviderConstructionError(secret)

    monkeypatch.setattr(builtin_module, "aevaluate", evaluate_construction)
    evaluated = await EvaluateImageCapability(runtime=FakeCapabilityRuntime()).invoke(
        _invocation(
            "vulca.image.evaluate",
            {"image": base64.b64encode(_png_bytes()).decode("ascii"), "intent": "assess"},
            options={"binding_ref": "binding:vlm"},
        )
    )
    assert evaluated.status is CapabilityStatus.FAILED
    assert evaluated.side_effect_state is SideEffectState.NOT_STARTED
    assert evaluated.error_code == "PROVIDER_CONSTRUCTION_FAILED"
    assert secret not in repr(evaluated)


@pytest.mark.asyncio
async def test_declared_secret_resolution_failures_are_not_started_for_edit_and_evaluate(
    tmp_path: Path,
) -> None:
    secret = "binding-construction-secret"
    source = tmp_path / "c1-secret-boundary-source.png"
    source.write_bytes(_png_bytes())
    try:
        edit = await EditImageCapability(
            runtime=FakeCapabilityRuntime(api_key_error=CapabilityProviderConstructionError(secret))
        ).invoke(_edit_invocation_for_source(source, invocation_id="inv_edit_construction"))
        assert edit.status is CapabilityStatus.FAILED
        assert edit.side_effect_state is SideEffectState.NOT_STARTED
        assert edit.error_code == "PROVIDER_CONSTRUCTION_FAILED"
        assert secret not in repr(edit)

        evaluate = await EvaluateImageCapability(
            runtime=FakeCapabilityRuntime(api_key_error=CapabilityProviderConstructionError(secret))
        ).invoke(
            _invocation(
                "vulca.image.evaluate",
                {"image": base64.b64encode(_png_bytes()).decode("ascii"), "intent": "assess"},
                options={"binding_ref": "binding:vlm"},
                invocation_id="inv_evaluate_construction",
            )
        )
        assert evaluate.status is CapabilityStatus.FAILED
        assert evaluate.side_effect_state is SideEffectState.NOT_STARTED
        assert evaluate.error_code == "PROVIDER_CONSTRUCTION_FAILED"
        assert secret not in repr(evaluate)
    finally:
        source.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_generation_receipt_redacts_secret_echoes_from_provider_metadata() -> None:
    secret = "metadata-secret"
    provider = SimpleNamespace(
        generate=AsyncMock(
            return_value=ImageResult(
                image_b64=base64.b64encode(_png_bytes()).decode("ascii"),
                mime="image/png",
                metadata={
                    "provider": f"provider-{secret}",
                    "model": f"model-{secret}",
                    "request_id": f"request-{secret}",
                    "cost_usd": 0.01,
                },
            )
        )
    )
    result = await GenerateImageCapability(
        runtime=FakeCapabilityRuntime(provider=provider, api_key=secret)
    ).invoke(_generate_invocation())

    assert result.status is CapabilityStatus.SUCCEEDED
    assert secret not in repr(result)
    assert secret not in repr(result.output)
    assert secret not in repr(result.provider_receipt)
    assert "[REDACTED]" in repr(result.provider_receipt)


@pytest.mark.asyncio
async def test_evaluation_output_redacts_secret_echoes_in_summary_rationale_and_recommendation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "evaluator-secret"

    async def fake_aevaluate(image: str, **kwargs: object) -> EvalResult:
        return EvalResult(
            score=0.8,
            tradition="default",
            dimensions={"L1": 0.8},
            rationales={"L1": f"rationale {secret}"},
            summary=f"summary {secret}",
            risk_level="low",
            risk_flags=[f"risk-{secret}"],
            recommendations=[f"recommendation {secret}"],
            latency_ms=1,
            cost_usd=0.01,
            raw={"provider": secret},
        )

    monkeypatch.setattr(builtin_module, "aevaluate", fake_aevaluate)
    result = await EvaluateImageCapability(
        runtime=FakeCapabilityRuntime(api_key=secret)
    ).invoke(
        _invocation(
            "vulca.image.evaluate",
            {"image": base64.b64encode(_png_bytes()).decode("ascii"), "intent": "assess"},
            options={"binding_ref": "binding:vlm", "model": f"model-{secret}", "provider": f"provider-{secret}"},
        )
    )

    assert result.status is CapabilityStatus.SUCCEEDED
    assert secret not in repr(result)
    assert secret not in repr(result.output)
    assert secret not in repr(result.provider_receipt)
    assert "[REDACTED]" in repr(result.output)


@pytest.mark.asyncio
async def test_evaluation_rejects_nested_credential_keys_without_secret_echo(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "nested-evaluator-secret"

    async def fake_aevaluate(image: str, **kwargs: object) -> EvalResult:
        return EvalResult(
            score=0.8,
            tradition="default",
            dimensions={"L1": 0.8},
            rationales={"L1": {"api_key": secret}},  # type: ignore[dict-item]
            summary="summary",
            risk_level="low",
            risk_flags=[],
            recommendations=[],
            latency_ms=1,
            cost_usd=0.01,
            raw={},
        )

    monkeypatch.setattr(builtin_module, "aevaluate", fake_aevaluate)
    caplog.set_level(logging.DEBUG)
    result = await EvaluateImageCapability(
        runtime=FakeCapabilityRuntime(api_key=secret)
    ).invoke(
        _invocation(
            "vulca.image.evaluate",
            {"image": base64.b64encode(_png_bytes()).decode("ascii"), "intent": "assess"},
            options={"binding_ref": "binding:vlm"},
        )
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.UNKNOWN
    assert result.error_code == "INVALID_EVALUATION_RESULT"
    assert secret not in repr(result)
    assert secret not in caplog.text


@pytest.mark.asyncio
async def test_evaluation_preserves_normal_creative_text_that_mentions_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_aevaluate(image: str, **kwargs: object) -> EvalResult:
        return EvalResult(
            score=0.8,
            tradition="default",
            dimensions={"L1": 0.8},
            rationales={"L1": "A secret garden is the visual metaphor."},
            summary="The secret garden remains legible.",
            risk_level="low",
            risk_flags=[],
            recommendations=["Keep the secret garden motif."],
            latency_ms=1,
            cost_usd=0.01,
            raw={},
        )

    monkeypatch.setattr(builtin_module, "aevaluate", fake_aevaluate)
    result = await EvaluateImageCapability(
        runtime=FakeCapabilityRuntime(api_key="actual-binding-token")
    ).invoke(
        _invocation(
            "vulca.image.evaluate",
            {"image": base64.b64encode(_png_bytes()).decode("ascii"), "intent": "assess"},
            options={"binding_ref": "binding:vlm"},
        )
    )

    assert result.status is CapabilityStatus.SUCCEEDED
    assert result.output["summary"] == "The secret garden remains legible."
    assert result.output["rationales"]["L1"] == "A secret garden is the visual metaphor."


@pytest.mark.asyncio
async def test_generate_rejects_unsupported_output_format_before_provider_call() -> None:
    provider = SimpleNamespace(
        generate=AsyncMock(
            return_value=ImageResult(
                image_b64=base64.b64encode(b"bytes").decode("ascii"),
                mime="image/png",
            )
        )
    )
    invocation = _generate_invocation()
    inputs = dict(invocation.inputs)
    inputs["output_format"] = "bmp"
    invalid = _invocation("vulca.image.generate", inputs, options=dict(invocation.options))
    runtime = FakeCapabilityRuntime(provider=provider)

    result = await GenerateImageCapability(runtime=runtime).invoke(invalid)

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.NOT_STARTED
    assert result.error_code == "INVALID_FORMAT"
    assert runtime.provider_calls == []
    provider.generate.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "collision",
    (
        "prompt",
        "tradition",
        "subject",
        "reference_image_b64",
        "negative_prompt",
        "seed",
        "steps",
        "cfg_scale",
        "width",
        "height",
        "input_fidelity",
        "quality",
        "output_format",
    ),
)
async def test_generate_rejects_request_option_collisions_before_provider_call(collision: str) -> None:
    provider = SimpleNamespace(generate=AsyncMock())
    invocation = _generate_invocation()
    options = dict(invocation.options)
    options["request_options"] = {collision: "collision-value"}
    runtime = FakeCapabilityRuntime(provider=provider)

    result = await GenerateImageCapability(runtime=runtime).invoke(
        _invocation("vulca.image.generate", dict(invocation.inputs), options=options)
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.NOT_STARTED
    assert result.error_code == "REQUEST_OPTION_COLLISION"
    assert runtime.provider_calls == []
    provider.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_reference_file_requires_explicit_path_authority(tmp_path: Path) -> None:
    reference = tmp_path / "reference.png"
    reference.write_bytes(_png_bytes())
    provider = SimpleNamespace(generate=AsyncMock())
    invocation = _generate_invocation()
    inputs = dict(invocation.inputs)
    inputs["reference_image_b64"] = str(reference)
    runtime = FakeCapabilityRuntime(provider=provider)

    result = await GenerateImageCapability(runtime=runtime).invoke(
        _invocation("vulca.image.generate", inputs, options=dict(invocation.options))
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.error_code == "UNAUTHORIZED_PATH"
    assert runtime.provider_calls == []
    provider.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_reference_symlink_escape_is_rejected(tmp_path: Path) -> None:
    approved = tmp_path / "approved"
    approved.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(_png_bytes())
    reference = approved / "reference.png"
    reference.symlink_to(outside)
    provider = SimpleNamespace(generate=AsyncMock())
    invocation = _generate_invocation()
    inputs = dict(invocation.inputs)
    inputs["reference_image_b64"] = str(reference)
    options = dict(invocation.options)
    options["authorized_roots"] = [str(approved)]
    runtime = FakeCapabilityRuntime(provider=provider)

    result = await GenerateImageCapability(runtime=runtime).invoke(
        _invocation("vulca.image.generate", inputs, options=options)
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.error_code == "UNAUTHORIZED_PATH"
    assert runtime.provider_calls == []
    provider.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_edit_source_file_requires_explicit_path_authority(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(_png_bytes())
    ainpaint = AsyncMock()
    monkeypatch.setattr(builtin_module, "ainpaint", ainpaint)

    result = await EditImageCapability(runtime=FakeCapabilityRuntime()).invoke(
        _invocation(
            "vulca.image.edit",
            {
                "source": str(source),
                "region": "0,0,50,50",
                "instruction": "replace the bounded region",
                "reference_type": "coordinate",
            },
            options={"provider": "mock", "binding_ref": "binding:mock"},
        )
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.NOT_STARTED
    assert result.error_code == "UNAUTHORIZED_PATH"
    ainpaint.assert_not_awaited()


@pytest.mark.asyncio
async def test_evaluate_image_file_requires_explicit_path_authority(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(_png_bytes())
    aevaluate = AsyncMock()
    monkeypatch.setattr(builtin_module, "aevaluate", aevaluate)

    result = await EvaluateImageCapability(runtime=FakeCapabilityRuntime()).invoke(
        _invocation(
            "vulca.image.evaluate",
            {"image": str(image), "intent": "assess"},
            options={"binding_ref": "binding:vlm"},
        )
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.NOT_STARTED
    assert result.error_code == "UNAUTHORIZED_PATH"
    aevaluate.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf, object()])
async def test_evaluate_rejects_non_json_values_as_invalid_result(
    monkeypatch: pytest.MonkeyPatch, bad_value: object
) -> None:
    async def fake_aevaluate(image: str, **kwargs: object) -> EvalResult:
        return EvalResult(
            score=bad_value,  # type: ignore[arg-type]
            tradition="default",
            dimensions={"L1": 0.8},
            rationales={"L1": "clear"},
            summary="summary",
            risk_level="low",
            risk_flags=[],
            recommendations=[],
            latency_ms=1,
            cost_usd=0.01,
            raw={},
        )

    monkeypatch.setattr(builtin_module, "aevaluate", fake_aevaluate)
    result = await EvaluateImageCapability(runtime=FakeCapabilityRuntime()).invoke(
        _invocation(
            "vulca.image.evaluate",
            {"image": base64.b64encode(_png_bytes()).decode("ascii"), "intent": "assess"},
            options={"binding_ref": "binding:vlm"},
        )
    )

    assert result.status is CapabilityStatus.FAILED
    assert result.side_effect_state is SideEffectState.UNKNOWN
    assert result.error_code == "INVALID_EVALUATION_RESULT"
