"""VLM Critic -- core L1-L5 image evaluation via Gemini Vision."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

import litellm

logger = logging.getLogger("vulca")

# Local user data path -- preferred evolved context source
_LOCAL_EVOLVED_PATH = Path.home() / ".vulca" / "data" / "evolved_context.json"

# Token budget: start low, escalate on truncation
_DEFAULT_MAX_TOKENS = 3072
_ESCALATED_MAX_TOKENS = 8192
_CONTENT_LOCK_MAX_TOKENS = 16384
_MAX_ESCALATION_ATTEMPTS = 1

# Local (Ollama) models consistently emit >3072 tokens for the L1-L5 JSON
# schema — verbose local models like Gemma 4 regularly overflow the cloud
# default.  Tokens are free locally, so start at the escalated budget to
# avoid a wasted first attempt.  The escalation loop still protects against
# even-longer outputs.
_LOCAL_DEFAULT_MAX_TOKENS = 8192

# ---------------------------------------------------------------------------
# Prompt cache partitioning
# ---------------------------------------------------------------------------
# _STATIC_SCORING_PREFIX contains the invariant L1-L5 framework definition and
# scoring protocol.  It has NO {tradition} or {tradition_guidance} placeholders,
# so it can be placed in a shared prompt-cache prefix (e.g. Gemini context
# caching, Anthropic prompt caching) and reused across calls without
# re-tokenisation.
#
# _build_dynamic_suffix() assembles the tradition-specific part at call time.
# score_image() joins the two parts with a double newline.
# ---------------------------------------------------------------------------

_STATIC_SCORING_PREFIX = """\
You are VULCA, a cultural-aware art evaluation system. Evaluate the given \
artwork image across five dimensions (L1-L5), each scored from 0.0 to 1.0.

## Dimension Definitions

- **L1 (Visual Perception)**: Composition, layout, spatial arrangement, visual \
clarity, color harmony, and overall visual impact.
- **L2 (Technical Execution)**: Rendering quality, detail precision, technique \
fidelity, medium-appropriate execution, and craftsmanship.
- **L3 (Cultural Context)**: Fidelity to cultural tradition, proper use of \
tradition-specific motifs/elements/terminology, adherence to canonical conventions.
- **L4 (Critical Interpretation)**: Respectful representation, absence of taboo \
violations, cultural sensitivity, appropriate contextual framing.
- **L5 (Philosophical Aesthetics)**: Artistic depth, emotional resonance, \
spiritual qualities, aesthetic harmony, and philosophical alignment with the tradition.

## Instructions

### Phase 1 — OBSERVE

Before scoring, describe what you see in the artwork in detail:
- Brushwork / rendering technique (type, quality, consistency)
- Color palette (dominant colors, harmony, contrast, temperature)
- Composition structure (layout, focal points, spatial relationships, depth)
- Texture and medium characteristics
- Subject matter and cultural elements present
- Use of space (negative space, layering, balance)

### Phase 2 — EVALUATE

Based on your observations, score each dimension 0.0-1.0. For each provide:
1. **observations**: 3-5 specific visual observations relevant to this dimension \
(factual descriptions, not judgments).
2. **rationale**: What you conclude from these observations (2-3 sentences).
3. **suggestion**: A SPECIFIC, ACTIONABLE improvement containing: \
(a) the exact technique name in original language if applicable, \
(b) how to apply it (e.g., "use broader horizontal strokes in the middle ground"), \
(c) what effect it would achieve. If the work excels, suggest how to push further.
4. **reference_technique**: The single most relevant traditional technique name \
for this dimension (bilingual if applicable, e.g., "reserved white space (留白)").
5. **deviation_type**: One of "traditional", "intentional_departure", or "experimental".

## Response Length Guidelines

- Each dimension rationale: 30-50 words (be specific, not verbose)
- Each suggestion: 15-25 words (actionable, not generic)
- Each reference_technique: 5-15 words (name the technique precisely)
- observation block: 100-200 words total

Respond in two phases:

**Phase 1 — Scratchpad** (free-form, not parsed):
Write your working observations inside `<observation>` tags. Use this space to \
think through what you see before committing to scores. Example:
<observation>
[Your free-form notes about brushwork, color, composition, cultural elements, etc.]
</observation>

**Phase 2 — Structured Scoring** (parsed by system):
Write ONLY the JSON object inside `<scoring>` tags. Only this section is parsed.
<scoring>
{
    "L1": <float>, "L1_observations": "<string>", "L1_rationale": "<string>", \
"L1_suggestion": "<string>", "L1_reference_technique": "<string>", "L1_deviation_type": "<string>",
    "L2": <float>, "L2_observations": "<string>", "L2_rationale": "<string>", \
"L2_suggestion": "<string>", "L2_reference_technique": "<string>", "L2_deviation_type": "<string>",
    "L3": <float>, "L3_observations": "<string>", "L3_rationale": "<string>", \
"L3_suggestion": "<string>", "L3_reference_technique": "<string>", "L3_deviation_type": "<string>",
    "L4": <float>, "L4_observations": "<string>", "L4_rationale": "<string>", \
"L4_suggestion": "<string>", "L4_reference_technique": "<string>", "L4_deviation_type": "<string>",
    "L5": <float>, "L5_observations": "<string>", "L5_rationale": "<string>", \
"L5_suggestion": "<string>", "L5_reference_technique": "<string>", "L5_deviation_type": "<string>",
    "risk_flags": []
}
</scoring>

Note: `risk_flags` is a list of cultural sensitivity concerns, e.g. \
["cultural_appropriation", "anachronistic_elements", "sacred_symbol_misuse", \
"stereotypical_representation"]. Use an empty list if there are no concerns.
"""

# Backward-compatibility alias — kept so external code referencing _SYSTEM_PROMPT
# continues to import without error.  New code should use _STATIC_SCORING_PREFIX
# and _build_dynamic_suffix() directly.
_SYSTEM_PROMPT = _STATIC_SCORING_PREFIX

# ---------------------------------------------------------------------------
# Mode-specific evaluation framing
# ---------------------------------------------------------------------------
# These constants are prepended to the dynamic suffix by _build_dynamic_suffix()
# based on the evaluation mode.  They instruct the VLM to adopt a different
# persona and scoring philosophy while keeping the L1-L5 framework intact.
# ---------------------------------------------------------------------------

_STRICT_FRAMING = """
### Evaluation Mode: STRICT (Conformance Judge)
You are evaluating as a conformance judge. Score how closely the artwork adheres to
the canonical standards of this tradition. Penalize deviations from tradition unless
they demonstrate exceptional mastery. Lower scores for non-conforming elements.
Focus on: technical accuracy, canonical motifs, traditional materials, orthodox composition.
"""

_REFERENCE_FRAMING = """
### Evaluation Mode: REFERENCE (Cultural Mentor)
You are evaluating as a cultural mentor and advisor. Acknowledge intentional departures
from tradition as creative choices, not failures. Focus on growth potential and how the
artist can deepen engagement with the tradition. Suggest specific techniques and concepts
for improvement. Score the work's artistic merit within the tradition's value system,
not strict conformance.
"""

_FUSION_FRAMING = """
### Evaluation Mode: FUSION (Cross-Cultural Perspective)
You are evaluating this artwork with cross-cultural awareness. Identify the primary
cultural tradition present and score against that tradition's standards. Where the work
draws from multiple traditions, note this in rationales and weight your observations
accordingly. Do not let one tradition's canonical rules penalize legitimate cross-cultural
fusion. Output a single set of L1-L5 scores reflecting the overall cross-cultural merit.
"""


def _build_dynamic_suffix(
    tradition: str,
    evolved_ctx: dict | None = None,
    *,
    mode: str = "strict",
) -> str:
    """Build the tradition-specific portion of the VLM system prompt.

    This is the *dynamic* counterpart to ``_STATIC_SCORING_PREFIX``.  It must
    be called at evaluation time (not at module import) because it depends on
    the requested tradition and the runtime evolved-context state.

    Parameters
    ----------
    tradition:
        Tradition key (e.g. ``"chinese_xieyi"``).
    evolved_ctx:
        Pre-loaded evolved context dict, or ``None`` to skip evolution guidance.
        Pass the result of ``_load_evolved_context()`` here when available.
    mode:
        Evaluation mode — ``"strict"`` (conformance judge), ``"reference"``
        (cultural mentor), or ``"fusion"`` (cross-cultural comparison).
        Defaults to ``"strict"`` for backward compatibility.
    """
    parts: list[str] = []

    # 0. Mode-specific evaluation framing (prepended before tradition guidance)
    if mode == "reference":
        parts.append(_REFERENCE_FRAMING)
    elif mode == "fusion":
        parts.append(_FUSION_FRAMING)
    else:
        parts.append(_STRICT_FRAMING)

    # 1. Tradition header + terminology/taboos/engram
    tradition_label = tradition.replace("_", " ").title()
    parts.append(f"## Cultural Tradition: {tradition_label}")
    tradition_guidance = _build_tradition_guidance(tradition)
    if tradition_guidance:
        parts.append(tradition_guidance)

    # 2. Evolution weights / few-shot (if caller provided evolved_ctx explicitly)
    # Note: _build_tradition_guidance already injects evolved guidance internally
    # when it loads evolved context itself; the explicit path here is kept for
    # callers that pre-load and pass evolved_ctx to avoid a double disk read.
    if evolved_ctx is not None:
        inject_parts: list[str] = []
        _inject_evolved_guidance(inject_parts, tradition, evolved_ctx)
        parts.extend(inject_parts)

    # 3. Tradition-specific extra dimensions (E1-E3)
    extra_dims = _load_extra_dimensions(tradition)
    extra_prompt = _build_extra_dimensions_prompt(extra_dims)
    if extra_prompt:
        parts.append(extra_prompt)

    return "\n".join(p for p in parts if p)

def _extract_scoring(text: str) -> str:
    """Extract parseable scoring JSON from a two-phase VLM response.

    Prefer the last valid <scoring> block. If the model omits scoring tags,
    strip scratchpad observation blocks and return the first balanced JSON
    object. Falling back this way avoids Gemini scratchpad braces poisoning the
    generic JSON parser.
    """
    scoring_blocks = list(
        re.finditer(
            r"<scoring>\s*(.*?)\s*</scoring>",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )
    for match in reversed(scoring_blocks):
        candidate = match.group(1).strip()
        if candidate.startswith("{"):
            return candidate

    without_observation = re.sub(
        r"<observation>.*?</observation>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    json_candidate = _first_balanced_json(without_observation)
    if json_candidate:
        return json_candidate
    return text.strip()


def _first_balanced_json(text: str) -> str:
    start = text.find("{")
    if start < 0:
        return ""

    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1].strip()
    return ""


def _build_extra_dimensions_prompt(extras: list[dict]) -> str:
    """Build prompt section for tradition-specific extra dimensions (E1-E3, max 3)."""
    if not extras:
        return ""
    # Limit to 3
    extras = extras[:3]
    lines = [
        "\n## Tradition-Specific Dimensions\n",
        "In addition to L1-L5, evaluate these tradition-specific dimensions:\n",
    ]
    for e in extras:
        lines.append(f"- **{e['key']} ({e['name']})**: {e['description']}")
    lines.append(
        "\nScore each with the same format as L1-L5 "
        "(observations, rationale, suggestion, reference_technique, deviation_type)."
    )
    return "\n".join(lines)


def _parse_vlm_response(
    raw: dict,
    *,
    extra_keys: list[str] | None = None,
) -> dict:
    """Parse VLM JSON response into a structured dict.

    Returns a dict with keys:
        scores, rationales, suggestions, deviations, observations,
        ref_techniques (each a dict keyed by dimension), and risk_flags (list).

    For backward compatibility the return value also supports 6-tuple unpacking
    via __iter__: (scores, rationales, suggestions, deviations, observations,
    ref_techniques).  New code should access fields by key.
    """
    scores: dict[str, float] = {}
    rationales: dict[str, str] = {}
    suggestions: dict[str, str] = {}
    deviations: dict[str, str] = {}
    observations: dict[str, str] = {}
    ref_techniques: dict[str, str] = {}

    for i in range(1, 6):
        key = f"L{i}"
        val = raw.get(key, 0.0)
        scores[key] = max(0.0, min(1.0, float(val))) if val else 0.0
        rationales[key] = str(raw.get(f"{key}_rationale", ""))
        suggestions[key] = str(raw.get(f"{key}_suggestion", ""))
        dev = str(raw.get(f"{key}_deviation_type", "traditional"))
        deviations[key] = dev if dev in ("traditional", "intentional_departure", "experimental") else "traditional"
        observations[key] = str(raw.get(f"{key}_observations", ""))
        ref_techniques[key] = str(raw.get(f"{key}_reference_technique", ""))

    # Parse extra dimensions (E1-E3)
    for key in (extra_keys or []):
        val = raw.get(key, 0.0)
        scores[key] = max(0.0, min(1.0, float(val))) if val else 0.0
        rationales[key] = str(raw.get(f"{key}_rationale", ""))
        suggestions[key] = str(raw.get(f"{key}_suggestion", ""))
        dev = str(raw.get(f"{key}_deviation_type", "traditional"))
        deviations[key] = dev if dev in ("traditional", "intentional_departure", "experimental") else "traditional"
        observations[key] = str(raw.get(f"{key}_observations", ""))
        ref_techniques[key] = str(raw.get(f"{key}_reference_technique", ""))

    # Parse risk_flags — list of cultural sensitivity concern strings
    risk_flags = raw.get("risk_flags", [])
    if not isinstance(risk_flags, list):
        risk_flags = []

    return _VLMParseResult(
        scores=scores,
        rationales=rationales,
        suggestions=suggestions,
        deviations=deviations,
        observations=observations,
        ref_techniques=ref_techniques,
        risk_flags=risk_flags,
    )


class _VLMParseResult(dict):
    """Dict subclass returned by _parse_vlm_response.

    Supports both dict-style access (result["risk_flags"]) and 6-tuple
    unpacking for backward compatibility with existing callers:
        scores, rationales, suggestions, deviations, observations, ref_techniques = _parse_vlm_response(raw)
    """

    def __init__(
        self,
        *,
        scores: dict,
        rationales: dict,
        suggestions: dict,
        deviations: dict,
        observations: dict,
        ref_techniques: dict,
        risk_flags: list,
    ) -> None:
        super().__init__(
            scores=scores,
            rationales=rationales,
            suggestions=suggestions,
            deviations=deviations,
            observations=observations,
            ref_techniques=ref_techniques,
            risk_flags=risk_flags,
        )

    def __iter__(self):  # type: ignore[override]
        """Yield the 6-tuple fields in order for backward-compat unpacking."""
        yield self["scores"]
        yield self["rationales"]
        yield self["suggestions"]
        yield self["deviations"]
        yield self["observations"]
        yield self["ref_techniques"]


_TRADITION_GUIDANCE: dict[str, str] = {
    "default": "Apply general art evaluation principles. No specific cultural tradition.",
    "chinese_xieyi": (
        "Xieyi (\u5199\u610f) freehand ink wash painting. Prioritize: spontaneity of brushwork, "
        "use of blank space (\u7559\u767d), ink gradation (\u58a8\u5206\u4e94\u8272), qi-yun (\u6c14\u97f5) spiritual resonance, "
        "and harmony between poetry-calligraphy-painting-seal (\u8bd7\u4e66\u753b\u5370)."
    ),
    "chinese_gongbi": (
        "Gongbi (\u5de5\u7b14) meticulous painting. Prioritize: precision of line work, "
        "layered color application, fine detail rendering, and adherence to traditional subjects."
    ),
    "western_academic": (
        "Western academic tradition. Prioritize: anatomical accuracy, perspective, "
        "chiaroscuro, compositional balance, and narrative clarity."
    ),
    "islamic_geometric": (
        "Islamic geometric art. Prioritize: mathematical precision of patterns, "
        "symmetry, tessellation correctness, arabesque flow, and avoidance of figural representation."
    ),
    "japanese_traditional": (
        "Japanese traditional art (Nihonga/Ukiyo-e). Prioritize: flat color areas, "
        "bold outlines, seasonal motifs, wabi-sabi aesthetics, and mono no aware sentiment."
    ),
    "watercolor": (
        "Watercolor painting. Prioritize: transparency of washes, wet-in-wet technique, "
        "luminosity, paper-as-white usage, and freshness of application."
    ),
    "african_traditional": (
        "African traditional art. Prioritize: symbolic abstraction, mask conventions, "
        "community/ritual significance, material authenticity, and spiritual function."
    ),
    "south_asian": (
        "South Asian art traditions. Prioritize: miniature painting conventions, "
        "Mughal detail, color symbolism, narrative scenes, and decorative borders."
    ),
}


def _load_evolved_context() -> dict | None:
    """Load evolved_context.json, preferring local user file (~/.vulca/data/).

    Search order:
    1. VULCA_EVOLVED_CONTEXT env var (explicit override)
    2. _LOCAL_EVOLVED_PATH (~/.vulca/data/evolved_context.json), written by LocalEvolver
    """
    try:
        env_path = os.environ.get("VULCA_EVOLVED_CONTEXT")
        if env_path:
            p = Path(env_path)
            if p.is_file():
                return json.loads(p.read_text(encoding="utf-8"))
        if _LOCAL_EVOLVED_PATH.is_file():
            return json.loads(_LOCAL_EVOLVED_PATH.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("Failed to load evolved context")
    return None


def _build_tradition_guidance(tradition: str) -> str:
    """Build rich tradition guidance from YAML data, evolved context, and few-shot examples.

    Parameters
    ----------
    tradition:
        Tradition key (e.g. "chinese_xieyi").
    """
    base = _TRADITION_GUIDANCE.get(tradition, _TRADITION_GUIDANCE["default"])

    try:
        from vulca.cultural.loader import get_tradition
        tc = get_tradition(tradition)
        if tc is None:
            return base

        parts = [base]

        if tc.terminology:
            terms_text = "\n".join(
                f"  - **{t.term}** ({t.term_zh}): {t.definition if isinstance(t.definition, str) else t.definition.get('en', '')}"
                for t in tc.terminology[:8]
            )
            parts.append(f"\n### Key Cultural Terminology\n{terms_text}")

        if tc.taboos:
            taboos_text = "\n".join(
                f"  - ⚠️ {t.rule}" + (f" — {t.explanation}" if t.explanation else "")
                for t in tc.taboos
            )
            parts.append(f"\n### Evaluation Taboos (MUST respect)\n{taboos_text}")

        # Inject evolved weight guidance + few-shot examples (always, if available)
        evolved = _load_evolved_context()
        if evolved:
            _inject_evolved_guidance(parts, tradition, evolved)

        return "\n".join(parts)
    except Exception:
        logger.debug("Tradition guidance fallback for %s", tradition)
        return base


_L_LABELS = {
    "L1": "Visual Perception", "L2": "Technical Execution",
    "L3": "Cultural Context", "L4": "Critical Interpretation",
    "L5": "Philosophical Aesthetics",
}

_DIM_NAME_TO_L = {
    "visual_perception": "L1", "technical_analysis": "L2",
    "cultural_context": "L3", "critical_interpretation": "L4",
    "philosophical_aesthetic": "L5",
}


def _inject_evolved_guidance(parts: list[str], tradition: str, evolved: dict) -> None:
    """Inject evolved weights and few-shot examples into the prompt."""
    # 1. Evolved weight emphasis — tell the VLM which dimensions matter most
    tw = evolved.get("tradition_weights", {}).get(tradition)
    if tw and isinstance(tw, dict):
        weights_l = {_DIM_NAME_TO_L.get(k, k): v for k, v in tw.items() if _DIM_NAME_TO_L.get(k)}
        if weights_l:
            ranked = sorted(weights_l.items(), key=lambda x: x[1], reverse=True)
            emphasis = ", ".join(f"{k} ({_L_LABELS.get(k, k)}) {v:.0%}" for k, v in ranked)
            parts.append(f"\n### Dimension Weights (from system evolution)\nPrioritize by weight: {emphasis}")

    # 2. Few-shot reference examples — calibrate scoring
    fse = evolved.get("few_shot_examples", [])
    tradition_examples = [ex for ex in fse if ex.get("tradition") == tradition][:2]
    if tradition_examples:
        examples_text = "\n".join(
            f"  - \"{ex.get('subject', 'N/A')}\" — overall {ex.get('score', 0):.2f}"
            + (f" (strengths: {', '.join(ex['key_strengths'])})" if ex.get('key_strengths') else "")
            for ex in tradition_examples
        )
        parts.append(f"\n### Reference Benchmarks (high-scoring works in this tradition)\n{examples_text}")

    # 3. Tradition-specific insights from evolution
    ti = evolved.get("tradition_insights", {}).get(tradition)
    if ti and isinstance(ti, str) and len(ti) < 300:
        parts.append(f"\n### Evolved Insight\n{ti}")


def _load_extra_dimensions(tradition: str) -> list[dict]:
    """Load extra_dimensions from tradition YAML config (if defined)."""
    try:
        from vulca.cultural.loader import get_tradition
        tc = get_tradition(tradition)
        if tc is None:
            return []
        # extra_dimensions is an optional list of dicts on TraditionConfig
        extras = getattr(tc, "extra_dimensions", None)
        if not extras:
            return []
        # Normalise: each item must have key, name, description
        result = []
        for item in extras:
            if isinstance(item, dict) and "key" in item and "name" in item:
                result.append({
                    "key": item["key"],
                    "name": item["name"],
                    "description": item.get("description", ""),
                })
        return result
    except Exception:
        logger.debug("Could not load extra_dimensions for tradition %s", tradition)
        return []


async def score_image(
    img_b64: str,
    mime: str,
    subject: str,
    tradition: str,
    api_key: str,
    *,
    mode: str = "strict",
    model: str = "",
    content_lock: dict | None = None,
) -> dict:
    """Call Gemini Vision to score an image on L1-L5.

    Returns a dict with L1-L5 scores and rationales, or fallback zeros on error.

    Parameters
    ----------
    mode:
        Evaluation mode — ``"strict"``, ``"reference"``, or ``"fusion"``.
        Controls the VLM persona and scoring philosophy.
    """
    # Load tradition-specific extra dimensions (needed for extra_keys below)
    extra_dims = _load_extra_dimensions(tradition)
    extra_keys = [e["key"] for e in extra_dims[:3]]

    # Build system prompt from static prefix + dynamic tradition suffix.
    # _build_dynamic_suffix already calls _build_tradition_guidance and
    # _build_extra_dimensions_prompt internally, so we don't call them separately.
    dynamic_suffix = _build_dynamic_suffix(
        tradition,
        mode=mode,
    )
    system_msg = _STATIC_SCORING_PREFIX + "\n\n" + dynamic_suffix

    user_parts = [
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
    ]
    if subject:
        user_text = f"Subject/context: {subject}"
    else:
        user_text = "Evaluate this artwork."
    resolved_content_lock = None
    if content_lock:
        from vulca.content_lock import (
            build_content_fidelity_prompt,
            content_lock_from_dict,
        )

        resolved_content_lock = content_lock_from_dict(content_lock)
        fidelity_prompt = build_content_fidelity_prompt(resolved_content_lock)
        if fidelity_prompt:
            user_text = f"{user_text}\n\n{fidelity_prompt}"
    user_parts.append({"type": "text", "text": user_text})

    try:
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_parts},
        ]
        model = model or os.environ.get("VULCA_VLM_MODEL", "gemini/gemini-2.5-flash")

        # Resolve api_base for local providers (e.g. Ollama)
        api_base = None
        is_local = model.startswith("ollama")
        if is_local:
            api_base = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")

        # Adaptive token budget: cloud models start small (cost-conscious),
        # local models start at the escalated budget since tokens are free
        # and Gemma-class models regularly exceed 3072. Content-lock scoring
        # asks for additional gate fields, so allow one larger final attempt
        # when the model truncates twice.
        token_budgets = (
            [_LOCAL_DEFAULT_MAX_TOKENS]
            if is_local
            else [_DEFAULT_MAX_TOKENS, _ESCALATED_MAX_TOKENS]
        )
        if content_lock and _CONTENT_LOCK_MAX_TOKENS not in token_budgets:
            token_budgets.append(_CONTENT_LOCK_MAX_TOKENS)
        max_tokens = token_budgets[0]
        resp = None
        for attempt, max_tokens in enumerate(token_budgets):
            # Local models (Ollama) need longer timeout for first load
            timeout = 300 if model.startswith("ollama") else 55
            call_kwargs = dict(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.1,
                api_key=api_key,
                timeout=timeout,
            )
            if api_base:
                call_kwargs["api_base"] = api_base
            resp = await litellm.acompletion(**call_kwargs)
            finish_reason = getattr(resp.choices[0], "finish_reason", "stop")
            if finish_reason == "length" and attempt < len(token_budgets) - 1:
                logger.info(
                    "VLM response truncated (finish_reason=length) at %d tokens; "
                    "escalating to %d tokens",
                    max_tokens,
                    token_budgets[attempt + 1],
                )
            else:
                break

        text = resp.choices[0].message.content.strip()
        from vulca._parse import parse_llm_json
        # Extract only the <scoring> section (strips <observation> scratchpad)
        scoring_text = _extract_scoring(text)

        # Optional debug dump: when VULCA_VLM_DEBUG_DUMP=<dir> is set, write
        # the full raw text + extracted scoring + finish_reason to a file so
        # parse failures can be diagnosed offline. The dump is purely
        # diagnostic and never affects normal control flow.
        _dump_dir = os.environ.get("VULCA_VLM_DEBUG_DUMP")
        if _dump_dir:
            try:
                import time as _t
                Path(_dump_dir).mkdir(parents=True, exist_ok=True)
                stamp = f"{int(_t.time() * 1000)}"
                _finish = getattr(resp.choices[0], "finish_reason", "?")
                _usage = getattr(resp, "usage", None)
                Path(_dump_dir, f"{stamp}.raw.txt").write_text(
                    f"### finish_reason={_finish}\n"
                    f"### usage={_usage}\n"
                    f"### max_tokens_used={max_tokens}\n"
                    f"### raw_text_len={len(text)}\n"
                    f"### scoring_text_len={len(scoring_text)}\n"
                    f"=== RAW TEXT ===\n{text}\n"
                    f"=== EXTRACTED <scoring> ===\n{scoring_text}\n",
                    encoding="utf-8",
                )
            except Exception as _dump_exc:
                logger.debug("VLM debug dump failed: %s", _dump_exc)

        parsed_json = parse_llm_json(scoring_text)
        content_fidelity_gate = None
        if resolved_content_lock is not None:
            from vulca.content_lock import (
                build_blind_relation_gate,
                build_content_fidelity_gate,
            )

            content_fidelity_gate = build_content_fidelity_gate(
                resolved_content_lock,
                parsed_json,
            )
            if resolved_content_lock.required_relations:
                blind_read = await _blind_relation_read(
                    img_b64=img_b64,
                    mime=mime,
                    api_key=api_key,
                    model=model,
                    api_base=api_base,
                    content_lock=resolved_content_lock,
                )
                content_fidelity_gate.update(
                    build_blind_relation_gate(resolved_content_lock, blind_read)
                )

        # Use _parse_vlm_response to extract and validate all fields (including extras)
        parsed = _parse_vlm_response(parsed_json, extra_keys=extra_keys)
        scores = parsed["scores"]
        rationales = parsed["rationales"]
        suggestions = parsed["suggestions"]
        deviations = parsed["deviations"]
        observations = parsed["observations"]
        ref_techniques = parsed["ref_techniques"]

        # Rebuild flat dict (backward-compatible with callers expecting flat dict)
        data: dict = {}
        all_levels = list(("L1", "L2", "L3", "L4", "L5")) + extra_keys
        for level in all_levels:
            data[level] = scores.get(level, 0.0)
            data[f"{level}_rationale"] = rationales.get(level, "")
            data[f"{level}_suggestion"] = suggestions.get(level, "")
            data[f"{level}_deviation_type"] = deviations.get(level, "traditional")
            data[f"{level}_observations"] = observations.get(level, "")
            data[f"{level}_reference_technique"] = ref_techniques.get(level, "")
        # Include risk_flags so _engine.py can read it from the flat dict
        data["risk_flags"] = parsed["risk_flags"]
        if content_fidelity_gate is not None:
            data["content_fidelity_gate"] = content_fidelity_gate
        # Store extra_keys and names in data so _engine.py can split core vs extra
        data["_extra_keys"] = extra_keys
        data["_extra_names"] = {e["key"]: e["name"] for e in extra_dims[:3]}

        return data

    except Exception as exc:
        logger.error("VLM scoring failed: %s", exc)
        fallback: dict = {"error": str(exc), "_extra_keys": extra_keys}
        for level in ("L1", "L2", "L3", "L4", "L5"):
            fallback[level] = 0.0
            fallback[f"{level}_rationale"] = f"Scoring failed: {exc}" if level == "L1" else ""
            fallback[f"{level}_suggestion"] = ""
            fallback[f"{level}_deviation_type"] = "traditional"
            fallback[f"{level}_observations"] = ""
            fallback[f"{level}_reference_technique"] = ""
        return fallback


async def _blind_relation_read(
    *,
    img_b64: str,
    mime: str,
    api_key: str,
    model: str,
    api_base: str | None,
    content_lock,
) -> dict:
    """Run an image-only relation read without caption or intended-relation anchors."""
    try:
        from vulca._parse import parse_llm_json
        from vulca.content_lock import build_blind_relation_read_prompt

        prompt = build_blind_relation_read_prompt(content_lock)
        if not prompt:
            return {}

        user_parts = [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
            {"type": "text", "text": prompt},
        ]
        call_kwargs = dict(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict image-only visual relationship reader. "
                        "Use only visible evidence in the image."
                    ),
                },
                {"role": "user", "content": user_parts},
            ],
            max_tokens=2048,
            temperature=0.0,
            api_key=api_key,
            timeout=300 if model.startswith("ollama") else 55,
        )
        if api_base:
            call_kwargs["api_base"] = api_base
        resp = await litellm.acompletion(**call_kwargs)
        text = resp.choices[0].message.content.strip()
        return parse_llm_json(text)
    except Exception as exc:
        logger.warning("Blind relation read failed: %s", exc)
        return {"_error": str(exc)}
