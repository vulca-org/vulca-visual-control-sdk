"""Contract tests for the canonical, exact-version capability SDK surface."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vulca.capability import (
    Capability,
    CapabilityArtifact,
    CapabilityInvocation,
    CapabilityInvocationMismatch,
    CapabilityManifest,
    CapabilityMaturity,
    CapabilityNotFound,
    CapabilityRegistry,
    CapabilityResult,
    CapabilityStatus,
    DuplicateCapability,
    SideEffectState,
    sha256_bytes,
)


def _manifest(
    *,
    capability_id: str = "test.echo",
    version: str = "1.0.0",
    retryable_codes: tuple[str, ...] = (),
) -> CapabilityManifest:
    return CapabilityManifest(
        capability_id=capability_id,
        version=version,
        kind="test",
        owner="tests",
        maturity=CapabilityMaturity.NATIVE,
        input_schema={},
        output_schema={},
        authority_requirements=(),
        evaluator_bindings=(),
        retryable_codes=retryable_codes,
        deterministic=True,
    )


def _invocation(*, capability_id: str = "test.echo", version: str = "1.0.0") -> CapabilityInvocation:
    return CapabilityInvocation(
        invocation_id="inv_test",
        capability_id=capability_id,
        capability_version=version,
        inputs={},
    )


def _result(
    *,
    status: CapabilityStatus = CapabilityStatus.SUCCEEDED,
    side_effect_state: SideEffectState = SideEffectState.COMPLETED,
    error_code: str | None = None,
) -> CapabilityResult:
    return CapabilityResult(
        invocation_id="inv_test",
        status=status,
        side_effect_state=side_effect_state,
        output={},
        artifacts=(),
        provider_receipt={},
        latency_ms=0,
        cost_minor=0,
        currency="USD",
        error_code=error_code,
    )


class FakeCapability:
    """Small real capability implementation used to exercise registry behavior."""

    def __init__(
        self,
        *,
        version: str,
        capability_id: str = "test.echo",
        result: CapabilityResult | None = None,
        retryable_codes: tuple[str, ...] = (),
    ) -> None:
        self.manifest = _manifest(
            capability_id=capability_id,
            version=version,
            retryable_codes=retryable_codes,
        )
        self.result = result
        self.invocations: list[CapabilityInvocation] = []

    async def invoke(self, invocation: CapabilityInvocation) -> CapabilityResult:
        self.invocations.append(invocation)
        return self.result or _result()


def test_fake_capability_conforms_to_protocol() -> None:
    capability: Capability = FakeCapability(version="1.0.0")
    assert capability.manifest.version == "1.0.0"


def test_artifact_rejects_wrong_hash() -> None:
    with pytest.raises(ValueError, match="sha256"):
        CapabilityArtifact("hero", "image/png", b"png", "0" * 64)


def test_artifact_accepts_matching_hash() -> None:
    artifact = CapabilityArtifact("hero", "image/png", b"png", sha256_bytes(b"png"))
    assert artifact.sha256 == "8f8cbb7dcf46e0bc7d53265749a6c17d116093a6ba95e442764060c76fd4a86c"


def test_contract_dataclasses_are_frozen() -> None:
    values_and_fields = (
        (_manifest(), "owner"),
        (_invocation(), "invocation_id"),
        (CapabilityArtifact("hero", "image/png", b"png", sha256_bytes(b"png")), "logical_name"),
        (_result(), "currency"),
    )

    for value, field in values_and_fields:
        with pytest.raises(FrozenInstanceError):
            setattr(value, field, "changed")


def test_registry_requires_exact_version() -> None:
    registry = CapabilityRegistry()
    registry.register(FakeCapability(version="1.0.0"))
    with pytest.raises(CapabilityNotFound, match="1.0.1"):
        registry.resolve("test.echo", "1.0.1")


def test_registry_requires_exact_capability_id() -> None:
    registry = CapabilityRegistry()
    registry.register(FakeCapability(version="1.0.0"))
    with pytest.raises(CapabilityNotFound, match="other.echo"):
        registry.resolve("other.echo", "1.0.0")


def test_registry_rejects_duplicate_id_and_version() -> None:
    registry = CapabilityRegistry()
    registry.register(FakeCapability(version="1.0.0"))
    with pytest.raises(DuplicateCapability):
        registry.register(FakeCapability(version="1.0.0"))


@pytest.mark.asyncio
async def test_registry_invokes_the_resolved_exact_capability() -> None:
    registry = CapabilityRegistry()
    capability = FakeCapability(version="1.0.0")
    registry.register(capability)
    invocation = _invocation()

    result = await registry.invoke(invocation)

    assert result.status is CapabilityStatus.SUCCEEDED
    assert capability.invocations == [invocation]


@pytest.mark.asyncio
async def test_registry_rejects_manifest_mismatch_before_invocation() -> None:
    registry = CapabilityRegistry()
    capability = FakeCapability(version="1.0.0")
    registry.register(capability)
    capability.manifest = _manifest(capability_id="other.echo", version="9.0.0")

    with pytest.raises(CapabilityInvocationMismatch, match="manifest"):
        await registry.invoke(_invocation())

    assert capability.invocations == []


@pytest.mark.parametrize("field", ("invocation_id", "capability_id", "capability_version"))
def test_invocation_rejects_empty_identity_fields(field: str) -> None:
    values = {
        "invocation_id": "inv_test",
        "capability_id": "test.echo",
        "capability_version": "1.0.0",
        "inputs": {},
    }
    values[field] = ""

    with pytest.raises(ValueError, match=field):
        CapabilityInvocation(**values)


@pytest.mark.parametrize(
    "key",
    (
        "api_key",
        "access_token",
        "auth_token",
        "secret",
        "authorization",
        "credential",
        "provider_api_key",
        "database_secret",
        "oauth_credential",
    ),
)
def test_invocation_rejects_nested_credentials(key: str) -> None:
    with pytest.raises(ValueError, match="credential-bearing"):
        CapabilityInvocation(
            invocation_id="inv_test",
            capability_id="test.echo",
            capability_version="1.0.0",
            inputs={},
            options={"provider": [{"nested": {key: "must-not-enter"}}]},
        )


def test_invocation_allows_binding_refs_and_non_secret_controls() -> None:
    invocation = CapabilityInvocation(
        invocation_id="inv_test",
        capability_id="test.echo",
        capability_version="1.0.0",
        inputs={"binding_ref": "settings:OPENAI_API_KEY"},
        options={"binding_ref": "mock:none", "max_tokens": 128},
    )

    assert invocation.options["binding_ref"] == "mock:none"
    assert invocation.options["max_tokens"] == 128


@pytest.mark.parametrize(
    ("status", "side_effect_state", "error_code", "message"),
    (
        (CapabilityStatus.FAILED, SideEffectState.NOT_STARTED, None, "error_code"),
        (CapabilityStatus.SUCCEEDED, SideEffectState.COMPLETED, "E_FAIL", "error_code"),
        (CapabilityStatus.SUCCEEDED, SideEffectState.UNKNOWN, None, "COMPLETED"),
        (CapabilityStatus.FAILED, SideEffectState.COMPLETED, "E_FAIL", "side_effect_state"),
    ),
)
def test_result_enforces_status_error_and_side_effect_invariants(
    status: CapabilityStatus,
    side_effect_state: SideEffectState,
    error_code: str | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _result(status=status, side_effect_state=side_effect_state, error_code=error_code)


def test_result_allows_unknown_side_effect_state_only_for_failure() -> None:
    result = _result(
        status=CapabilityStatus.FAILED,
        side_effect_state=SideEffectState.UNKNOWN,
        error_code="PROVIDER_TIMEOUT",
    )

    assert result.side_effect_state is SideEffectState.UNKNOWN


@pytest.mark.asyncio
async def test_unknown_side_effect_is_not_automatically_retried() -> None:
    registry = CapabilityRegistry()
    capability = FakeCapability(
        version="1.0.0",
        result=_result(
            status=CapabilityStatus.FAILED,
            side_effect_state=SideEffectState.UNKNOWN,
            error_code="TEMPORARY_PROVIDER_ERROR",
        ),
        retryable_codes=("TEMPORARY_PROVIDER_ERROR",),
    )
    registry.register(capability)

    result = await registry.invoke(_invocation())

    assert result.side_effect_state is SideEffectState.UNKNOWN
    assert len(capability.invocations) == 1


def test_root_exports_capability_surface_without_dropping_existing_exports() -> None:
    import vulca

    legacy_exports = (
        "__version__",
        "evaluate",
        "aevaluate",
        "create",
        "acreate",
        "inpaint",
        "ainpaint",
        "compose_prompt_from_design",
        "session",
        "asession",
        "traditions",
        "get_weights",
        "EvalResult",
        "CreateResult",
        "InpaintResult",
        "SkillResult",
        "ImageProvider",
        "VLMProvider",
        "ImageResult",
        "L1L5Scores",
    )
    capability_exports = (
        "CapabilityManifest",
        "CapabilityInvocation",
        "CapabilityResult",
        "SideEffectState",
        "CapabilityRegistry",
    )

    assert all(name in vulca.__all__ and hasattr(vulca, name) for name in legacy_exports)
    assert all(name in vulca.__all__ and hasattr(vulca, name) for name in capability_exports)
