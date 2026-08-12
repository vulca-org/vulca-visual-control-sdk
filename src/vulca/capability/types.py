"""Immutable contracts for canonical VULCA capabilities."""

from __future__ import annotations

import hashlib
import hmac
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, TypeAlias

try:
    # StrEnum was added to the standard library in Python 3.11.
    from enum import StrEnum
except ImportError:  # pragma: no cover - exercised by Python 3.10 runtime
    class StrEnum(str, Enum):  # type: ignore[no-redef]  # intentional 3.10 fallback
        """Python 3.10-compatible subset of the Python 3.11 StrEnum API."""

        def __str__(self) -> str:
            return str(self.value)

        def __format__(self, format_spec: str) -> str:
            return str.__format__(str(self.value), format_spec)


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class CapabilityMaturity(StrEnum):
    NATIVE = "NATIVE"
    ORCHESTRATED = "ORCHESTRATED"
    INTEGRATED = "INTEGRATED"
    UNSUPPORTED = "UNSUPPORTED"


class CapabilityStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class SideEffectState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    COMPLETED = "COMPLETED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CapabilityManifest:
    capability_id: str
    version: str
    kind: str
    owner: str
    maturity: CapabilityMaturity
    input_schema: dict[str, JsonValue]
    output_schema: dict[str, JsonValue]
    authority_requirements: tuple[str, ...]
    evaluator_bindings: tuple[str, ...]
    retryable_codes: tuple[str, ...]
    deterministic: bool
    deprecated: bool = False


_CREDENTIAL_KEYS = frozenset(
    {
        "api_key",
        "access_token",
        "auth_token",
        "secret",
        "authorization",
        "credential",
    }
)
_CREDENTIAL_SUFFIXES = ("_api_key", "_secret", "_credential")


def _is_credential_key(key: str) -> bool:
    normalized_key = key.lower()
    return normalized_key in _CREDENTIAL_KEYS or normalized_key.endswith(_CREDENTIAL_SUFFIXES)


def _validate_finite_json(value: object, field_name: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if math.isfinite(value):
            return
        raise ValueError(f"{field_name} must contain only finite JSON values")
    if isinstance(value, list):
        for nested in value:
            _validate_finite_json(nested, field_name)
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{field_name} must use string mapping keys for finite JSON")
            _validate_finite_json(nested, field_name)
        return
    raise ValueError(f"{field_name} must contain only finite JSON values")


def _validate_json_object(value: object, field_name: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dict")
    _validate_finite_json(value, field_name)


def _credential_key_path(value: object, path: str) -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                continue
            if _is_credential_key(key):
                return f"{path}.{key}"
            nested_path = _credential_key_path(nested, f"{path}.{key}")
            if nested_path is not None:
                return nested_path
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            nested_path = _credential_key_path(nested, f"{path}[{index}]")
            if nested_path is not None:
                return nested_path
    return None


def _validate_non_empty_identity(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty")


@dataclass(frozen=True)
class CapabilityInvocation:
    invocation_id: str
    capability_id: str
    capability_version: str
    inputs: dict[str, JsonValue]
    options: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_empty_identity("invocation_id", self.invocation_id)
        _validate_non_empty_identity("capability_id", self.capability_id)
        _validate_non_empty_identity("capability_version", self.capability_version)

        for field_name, value in (("inputs", self.inputs), ("options", self.options)):
            _validate_json_object(value, field_name)
            credential_path = _credential_key_path(value, field_name)
            if credential_path is not None:
                raise ValueError(f"{field_name} contains credential-bearing key at {credential_path}")


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 digest for byte content."""
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class CapabilityArtifact:
    logical_name: str
    media_type: str
    content: bytes
    sha256: str

    def __post_init__(self) -> None:
        expected_sha256 = sha256_bytes(self.content)
        if not isinstance(self.sha256, str) or not hmac.compare_digest(self.sha256, expected_sha256):
            raise ValueError("sha256 does not match content")


@dataclass(frozen=True)
class CapabilityResult:
    invocation_id: str
    status: CapabilityStatus
    side_effect_state: SideEffectState
    output: dict[str, JsonValue]
    artifacts: tuple[CapabilityArtifact, ...]
    provider_receipt: dict[str, JsonValue]
    latency_ms: int
    cost_minor: int
    currency: str
    error_code: str | None = None

    def __post_init__(self) -> None:
        for field_name, value in (("output", self.output), ("provider_receipt", self.provider_receipt)):
            _validate_json_object(value, field_name)
            credential_path = _credential_key_path(value, field_name)
            if credential_path is not None:
                raise ValueError(f"{field_name} contains credential-bearing key at {credential_path}")

        if self.status not in (CapabilityStatus.SUCCEEDED, CapabilityStatus.FAILED):
            raise ValueError("status must be SUCCEEDED or FAILED")

        if self.status == CapabilityStatus.SUCCEEDED:
            if self.error_code is not None:
                raise ValueError("SUCCEEDED results must not include error_code")
            if self.side_effect_state != SideEffectState.COMPLETED:
                raise ValueError("SUCCEEDED results require side_effect_state COMPLETED")
        elif self.status == CapabilityStatus.FAILED:
            if not isinstance(self.error_code, str) or not self.error_code.strip():
                raise ValueError("FAILED results require a non-empty error_code")
            if self.side_effect_state not in (SideEffectState.NOT_STARTED, SideEffectState.UNKNOWN):
                raise ValueError("FAILED results require side_effect_state NOT_STARTED or UNKNOWN")


class Capability(Protocol):
    manifest: CapabilityManifest

    async def invoke(self, invocation: CapabilityInvocation) -> CapabilityResult: ...
