"""VULCA -- AI-native creation organism.

Create, critique, and evolve cultural art through multi-agent AI pipelines.

v0.6.0 adds Gemini LLM intent parsing (implicit element extraction),
Digestion V2 (4-layer learning system), and Studio polish (preloader,
style weights, concept preview). 10/10 E2E agent test pass rate.

Usage::

    import vulca

    # Evaluate an artwork
    result = vulca.evaluate("painting.jpg")
    print(result.score)          # 0.82
    print(result.tradition)      # "chinese_xieyi"
    print(result.dimensions)     # {"L1": 0.75, "L2": 0.82, ...}

    # With intent
    result = vulca.evaluate("painting.jpg", intent="check ink wash style")

    # With explicit tradition
    result = vulca.evaluate("painting.jpg", tradition="chinese_xieyi")

    # Async
    result = await vulca.aevaluate("painting.jpg", intent="...")

    # Studio Pipeline V2
    from vulca.studio import Brief, SessionState, StudioSession
    brief = Brief.from_intent("水墨山水，强调留白")
    session = StudioSession(brief=brief)
"""

import os

# Importing provider-facing modules can touch LiteLLM. Keep default imports
# offline unless the caller has explicitly chosen another cost-map behavior.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")

from vulca._version import __version__
from vulca.capability import (
    CapabilityInvocation,
    CapabilityManifest,
    CapabilityRegistry,
    CapabilityResult,
    SideEffectState,
)
from vulca.create import acreate, create
from vulca.evaluate import aevaluate, evaluate
from vulca.inpaint import ainpaint, inpaint
from vulca.prompting import compose_prompt_from_design
from vulca.providers.base import ImageProvider, ImageResult, L1L5Scores, VLMProvider
from vulca.session import asession, session
from vulca.types import CreateResult, EvalResult, InpaintResult, SkillResult

# Studio Pipeline V2 (v0.5.0) — conditional import, module ships separately
try:
    from vulca.studio import Brief, SessionState, StudioSession
    _STUDIO_AVAILABLE = True
except ImportError:
    _STUDIO_AVAILABLE = False

# Layers module (v0.7.0) — conditional import
try:
    from vulca.layers import LayerInfo, LayerResult, LayeredArtwork
    _LAYERS_AVAILABLE = True
except ImportError:
    _LAYERS_AVAILABLE = False


def traditions() -> list[str]:
    """List all available cultural traditions."""
    try:
        from vulca.cultural.loader import get_known_traditions
        result = get_known_traditions()
        if result:
            return result
    except Exception:
        pass
    from vulca.cultural import TRADITIONS
    return list(TRADITIONS)


def get_weights(tradition: str) -> dict[str, float]:
    """Get L1-L5 weights for a tradition (evolved if available)."""
    from vulca.cultural import get_weights as _get_weights
    return _get_weights(tradition)


__all__ = [
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
    "CapabilityManifest",
    "CapabilityInvocation",
    "CapabilityResult",
    "SideEffectState",
    "CapabilityRegistry",
]

# Studio Pipeline V2 (v0.5.0) — extend __all__ when module is available
if _STUDIO_AVAILABLE:
    __all__ += ["Brief", "SessionState", "StudioSession"]

# Layers module (v0.7.0) — extend __all__ when module is available
if _LAYERS_AVAILABLE:
    __all__ += ["LayerInfo", "LayerResult", "LayeredArtwork"]
