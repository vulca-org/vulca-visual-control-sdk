"""Canonical, exact-version capability contracts for the VULCA SDK."""

from .registry import (
    CapabilityError,
    CapabilityInvocationMismatch,
    CapabilityNotFound,
    CapabilityRegistry,
    DuplicateCapability,
)
from .types import (
    Capability,
    CapabilityArtifact,
    CapabilityInvocation,
    CapabilityManifest,
    CapabilityMaturity,
    CapabilityResult,
    CapabilityStatus,
    JsonScalar,
    JsonValue,
    SideEffectState,
    sha256_bytes,
)
from .runtime import (
    CapabilityProviderConstructionError,
    CapabilityProviderTimeoutError,
    CapabilityProviderTransportError,
    CapabilityProviderUnsupportedError,
    CapabilityRuntime,
    EnvironmentCapabilityRuntime,
)
from .builtin import (
    EditImageCapability,
    EvaluateImageCapability,
    GenerateImageCapability,
    builtin_registry,
)
from .static import AdaptStaticCapability, ComposeStaticCapability, ValidateStaticCapability

__all__ = [
    "JsonScalar",
    "JsonValue",
    "CapabilityMaturity",
    "CapabilityStatus",
    "SideEffectState",
    "CapabilityManifest",
    "CapabilityInvocation",
    "CapabilityArtifact",
    "CapabilityResult",
    "Capability",
    "sha256_bytes",
    "CapabilityError",
    "CapabilityNotFound",
    "DuplicateCapability",
    "CapabilityInvocationMismatch",
    "CapabilityRegistry",
    "CapabilityRuntime",
    "EnvironmentCapabilityRuntime",
    "CapabilityProviderConstructionError",
    "CapabilityProviderTimeoutError",
    "CapabilityProviderTransportError",
    "CapabilityProviderUnsupportedError",
    "GenerateImageCapability",
    "EditImageCapability",
    "ComposeStaticCapability",
    "AdaptStaticCapability",
    "ValidateStaticCapability",
    "EvaluateImageCapability",
    "builtin_registry",
]
