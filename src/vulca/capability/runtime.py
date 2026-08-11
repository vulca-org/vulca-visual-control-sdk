"""Runtime dependency boundary for canonical VULCA capability Cells.

The capability contracts deliberately contain no provider credentials.  A
runtime resolves provider bindings and secrets at the last possible moment,
inside the adapter call stack.  Platforms can therefore inject a stricter
runtime without changing any Cell contract.
"""

from __future__ import annotations

import os
import re
from typing import Mapping, Protocol

from vulca.providers import ImageProvider, get_image_provider

from .types import JsonValue


class CapabilityRuntime(Protocol):
    """Resolve trusted provider bindings for a capability invocation."""

    def image_provider(
        self,
        *,
        provider_name: str,
        binding_ref: str,
        constructor_options: Mapping[str, JsonValue],
    ) -> ImageProvider: ...

    def api_key(self, *, binding_ref: str) -> str: ...


def _binding_env_name(binding_ref: str) -> str:
    """Map a local binding reference to an opt-in environment variable name."""
    if binding_ref.startswith("env:"):
        return binding_ref[4:]
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", binding_ref).strip("_").upper()
    return f"VULCA_BINDING_{normalized}" if normalized else ""


class EnvironmentCapabilityRuntime:
    """Default local runtime using the SDK's existing provider registry.

    A binding may explicitly name an environment variable with ``env:NAME``.
    Otherwise the runtime first checks ``VULCA_BINDING_<REF>`` and then leaves
    provider-specific environment lookup to the existing provider classes.
    This keeps local backwards compatibility while ensuring that a secret is
    never copied into a :class:`CapabilityInvocation`.
    """

    def image_provider(
        self,
        *,
        provider_name: str,
        binding_ref: str,
        constructor_options: Mapping[str, JsonValue],
    ) -> ImageProvider:
        options = dict(constructor_options)
        key = self.api_key(binding_ref=binding_ref)
        if key and "api_key" not in options:
            # ``api_key`` is added only to the provider constructor call.  It
            # is not part of the invocation, receipt, or result envelope.
            options["api_key"] = key
        return get_image_provider(provider_name, **options)

    def api_key(self, *, binding_ref: str) -> str:
        env_name = _binding_env_name(binding_ref)
        if env_name:
            value = os.environ.get(env_name)
            if value:
                return value
        return ""


__all__ = ["CapabilityRuntime", "EnvironmentCapabilityRuntime"]
