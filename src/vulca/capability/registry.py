"""Exact-version capability registration and invocation."""

from __future__ import annotations

from .types import Capability, CapabilityInvocation, CapabilityResult


class CapabilityError(Exception):
    """Base class for canonical capability registry errors."""


class CapabilityNotFound(CapabilityError, LookupError):
    """Raised when an exact capability ID and version are not registered."""


class DuplicateCapability(CapabilityError):
    """Raised when an exact capability ID and version is already registered."""


class CapabilityInvocationMismatch(CapabilityError, ValueError):
    """Raised when a resolved capability manifest does not match an invocation."""


class CapabilityRegistry:
    """Registry that resolves capabilities by exact ``(id, version)`` pairs."""

    def __init__(self) -> None:
        self._capabilities: dict[tuple[str, str], Capability] = {}

    def register(self, capability: Capability) -> None:
        key = (capability.manifest.capability_id, capability.manifest.version)
        if key in self._capabilities:
            capability_id, version = key
            raise DuplicateCapability(
                f"capability {capability_id!r} version {version!r} is already registered"
            )
        self._capabilities[key] = capability

    def resolve(self, capability_id: str, version: str) -> Capability:
        key = (capability_id, version)
        try:
            return self._capabilities[key]
        except KeyError as exc:
            raise CapabilityNotFound(
                f"capability {capability_id!r} version {version!r} is not registered"
            ) from exc

    async def invoke(self, invocation: CapabilityInvocation) -> CapabilityResult:
        capability = self.resolve(invocation.capability_id, invocation.capability_version)
        manifest = capability.manifest
        if (
            manifest.capability_id != invocation.capability_id
            or manifest.version != invocation.capability_version
        ):
            raise CapabilityInvocationMismatch(
                "resolved capability manifest does not match invocation: "
                f"manifest=({manifest.capability_id!r}, {manifest.version!r}), "
                f"invocation=({invocation.capability_id!r}, {invocation.capability_version!r})"
            )
        return await capability.invoke(invocation)
