"""Protocol definitions for pluggable providers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class ImageResult:
    """Result from an image generation provider."""
    image_b64: str
    mime: str = "image/png"
    metadata: dict | None = None


@dataclass(frozen=True)
class ImageEditCapabilities:
    """Provider/model edit support used by layer redraw routing."""

    supports_edits: bool = False
    requires_mask_for_edits: bool = True
    supports_unmasked_edits: bool = False
    supports_masked_edits: bool = False
    supports_input_fidelity: bool = False
    supports_quality: bool = False
    supports_output_format: bool = False


@dataclass
class L1L5Scores:
    """L1-L5 dimension scores from a VLM provider."""
    L1: float
    L2: float
    L3: float
    L4: float
    L5: float
    rationales: dict[str, str] | None = None


@runtime_checkable
class ImageProvider(Protocol):
    """Protocol for image generation backends."""

    # Image-runtime capability flags. Scoped to image generation details
    # (e.g. "raw_rgba", future "streaming", "batch", "reference_image").
    # For coarse provider-kind questions (vlm_scoring, llm_text, cost_tracked)
    # use vulca.providers.capabilities.provider_capabilities() instead.
    capabilities: frozenset[str] = frozenset()

    async def generate(
        self,
        prompt: str,
        *,
        tradition: str = "",
        subject: str = "",
        reference_image_b64: str = "",
        negative_prompt: str = "",
        seed: int | None = None,
        steps: int | None = None,
        cfg_scale: float | None = None,
        width: int = 1024,
        height: int = 1024,
        input_fidelity: str | None = None,
        quality: str | None = None,
        output_format: str | None = None,
        **kwargs,
    ) -> ImageResult: ...


@runtime_checkable
class VLMProvider(Protocol):
    """Protocol for VLM scoring backends."""
    async def score(
        self,
        image_b64: str,
        *,
        tradition: str = "",
        subject: str = "",
        guidance: str = "",
        **kwargs,
    ) -> L1L5Scores: ...


class ProviderRequestRejected(RuntimeError):
    """The provider received the request and refused it with an HTTP status.

    Subclasses ``RuntimeError`` so existing callers keep working; carries the
    status so capability adapters can classify the failure without parsing
    the human-readable message.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
