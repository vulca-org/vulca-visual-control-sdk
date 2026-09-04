"""Core evaluation engine -- simplified pipeline for the pip package.

Combines IntentAgent + SkillSelector + VLMCritic + SkillExecutors
into a single streamlined class.
"""

from __future__ import annotations

import asyncio
import logging
import os

from vulca._image import load_image_base64
from vulca._intent import resolve_intent
from vulca._vlm import score_image
from vulca._skills import run_skill
from vulca.cultural import get_weights, TRADITIONS
from vulca.types import EvalResult

logger = logging.getLogger("vulca")

_instance: Engine | None = None
_DEFAULT_VLM_MODEL = "gemini/gemini-2.5-flash"


def _resolve_vlm_model(vlm_model: str = "") -> str:
    return vlm_model or os.environ.get("VULCA_VLM_MODEL", _DEFAULT_VLM_MODEL)


def _resolve_api_key(
    api_key: str = "",
    *,
    mock: bool = False,
    vlm_model: str = "",
    allow_missing: bool = False,
) -> str:
    if mock:
        return api_key or ""

    key = api_key or os.environ.get("GOOGLE_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
    resolved_model = _resolve_vlm_model(vlm_model)
    if key:
        return key
    if resolved_model.startswith("ollama"):
        return "local"
    if allow_missing:
        return ""
    raise ValueError(
        "No API key found. Set GOOGLE_API_KEY environment variable, "
        "pass api_key='...' to vulca.evaluate(), or use mock=True."
    )


def _build_rubric_payload(tradition: str, image_path: str) -> dict:
    from vulca.cultural.loader import get_tradition_guide
    from vulca.layers.plan_prompt import get_tradition_layer_order

    guide = get_tradition_guide(tradition)
    if guide is None:
        raise ValueError(f"Unknown tradition: {tradition!r}")

    rubric = dict(guide)
    rubric["tradition_layers"] = get_tradition_layer_order(tradition)
    score_schema = {f"L{i}": None for i in range(1, 6)}
    score_schema.update({f"L{i}_rationale": "" for i in range(1, 6)})
    return {
        "rubric": rubric,
        "image_path": image_path,
        "score_schema": score_schema,
        "tradition": tradition,
        "eval_mode": "rubric_only",
        "score": None,
        "summary": "",
    }


class Engine:
    """Stateless evaluation engine. Use ``Engine.get_instance()``."""

    def __init__(
        self,
        api_key: str = "",
        mock: bool = False,
        vlm_model: str = "",
        _allow_missing_api_key: bool = False,
    ) -> None:
        self.mock = mock
        self.vlm_model = _resolve_vlm_model(vlm_model)
        self.api_key = _resolve_api_key(
            api_key,
            mock=mock,
            vlm_model=self.vlm_model,
            allow_missing=_allow_missing_api_key,
        )

    @classmethod
    def get_instance(
        cls,
        api_key: str = "",
        mock: bool = False,
        vlm_model: str = "",
        _allow_missing_api_key: bool = False,
    ) -> Engine:
        global _instance
        resolved_model = _resolve_vlm_model(vlm_model)
        key = _resolve_api_key(
            api_key,
            mock=mock,
            vlm_model=resolved_model,
            allow_missing=_allow_missing_api_key,
        )
        if (
            _instance is None
            or (api_key and _instance.api_key != key)
            or mock != (_instance.mock if _instance else False)
            or resolved_model != (_instance.vlm_model if _instance else "")
        ):
            _instance = cls(
                api_key=key,
                mock=mock,
                vlm_model=resolved_model,
                _allow_missing_api_key=_allow_missing_api_key,
            )
        return _instance

    async def run(
        self,
        image: str,
        intent: str = "",
        tradition: str = "",
        subject: str = "",
        skills: list[str] | None = None,
        mode: str = "strict",
        vlm_model: str = "",
    ) -> EvalResult | dict:
        resolved_vlm_model = _resolve_vlm_model(vlm_model or self.vlm_model)

        # Step 1: Load image (skip for mock)
        if mode == "rubric_only":
            resolved_tradition = tradition or "default"
            if resolved_tradition not in TRADITIONS:
                raise ValueError(
                    "rubric_only mode requires an explicit built-in tradition. "
                    "Use list_traditions() to choose one."
                )
            return _build_rubric_payload(resolved_tradition, image)

        if not self.mock:
            img_b64, mime = await load_image_base64(image)
        else:
            img_b64, mime = "", "image/png"

        # Step 2: Resolve intent -> tradition
        intent_confidence = 0.0
        if tradition and tradition in TRADITIONS:
            resolved_tradition = tradition
            intent_confidence = 1.0
        elif intent and not self.mock:
            resolved_tradition, intent_confidence = await resolve_intent(
                intent, api_key=self.api_key
            )
        else:
            resolved_tradition = tradition or "default"

        # Step 3: Get cultural weights
        weights = get_weights(resolved_tradition)

        # Step 4: VLM scoring (L1-L5)
        if self.mock:
            vlm_result = _mock_scores(resolved_tradition)
        else:
            vlm_result = await score_image(
                img_b64=img_b64,
                mime=mime,
                subject=subject or intent,
                tradition=resolved_tradition,
                api_key=_resolve_api_key(self.api_key, vlm_model=resolved_vlm_model),
                mode=mode,
                model=resolved_vlm_model,
            )

        # Step 5: Compute weighted total + extract suggestions/deviations/observations
        dimensions = {}
        rationales = {}
        suggestions = {}
        deviation_types = {}
        observations = {}
        reference_techniques = {}
        for level in ("L1", "L2", "L3", "L4", "L5"):
            dimensions[level] = vlm_result.get(level, 0.0)
            rationales[level] = vlm_result.get(f"{level}_rationale", "")
            suggestions[level] = vlm_result.get(f"{level}_suggestion", "")
            deviation_types[level] = vlm_result.get(f"{level}_deviation_type", "traditional")
            observations[level] = vlm_result.get(f"{level}_observations", "")
            reference_techniques[level] = vlm_result.get(f"{level}_reference_technique", "")

        # Extract extra dimension results (E1-E3, tradition-specific)
        extra_keys: list[str] = vlm_result.get("_extra_keys", [])
        extra_scores: dict[str, float] = {}
        extra_rationales: dict[str, str] = {}
        extra_suggestions: dict[str, str] = {}
        extra_observations: dict[str, str] = {}
        for ekey in extra_keys:
            extra_scores[ekey] = vlm_result.get(ekey, 0.0)
            extra_rationales[ekey] = vlm_result.get(f"{ekey}_rationale", "")
            extra_suggestions[ekey] = vlm_result.get(f"{ekey}_suggestion", "")
            extra_observations[ekey] = vlm_result.get(f"{ekey}_observations", "")

        weighted_total = sum(
            dimensions.get(f"L{i}", 0) * weights.get(f"L{i}", 0.2)
            for i in range(1, 6)
        )

        # Step 6: Run extra skills (parallel)
        skill_results = {}
        if skills:
            tasks = [
                run_skill(name, img_b64, mime, self.api_key)
                for name in skills
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for name, res in zip(skills, results):
                if isinstance(res, Exception):
                    logger.warning("Skill %s failed: %s", name, res)
                else:
                    skill_results[name] = res

        # Step 7: Build result
        risk_flags = vlm_result.get("risk_flags", [])
        risk_level = "high" if risk_flags else ("medium" if weighted_total < 0.5 else "low")

        recommendations = _build_recommendations(dimensions, weights, resolved_tradition, suggestions)

        summary = _build_summary(weighted_total, resolved_tradition, dimensions, mode)

        # A mock run calls no API, so it has no cost to report. Otherwise prefer
        # what the provider actually charged; _estimate_cost is a constant and
        # must not be presented as a measurement.
        measured = vlm_result.get("_cost_usd")
        if self.mock:
            cost, cost_is_estimate = 0.0, False
        elif measured is not None:
            cost, cost_is_estimate = float(measured), False
        else:
            cost, cost_is_estimate = _estimate_cost(skills or []), True

        # score_image swallows every exception and returns zeros; carry that
        # fact onto the result so callers are not handed a fabricated verdict.
        scoring_error = str(vlm_result.get("error") or "")

        return EvalResult(
            score=round(weighted_total, 4),
            tradition=resolved_tradition,
            dimensions=dimensions,
            rationales=rationales,
            summary=summary,
            risk_level=risk_level,
            risk_flags=risk_flags,
            recommendations=recommendations,
            suggestions=suggestions,
            deviation_types=deviation_types,
            observations=observations,
            reference_techniques=reference_techniques,
            extra_scores=extra_scores,
            extra_rationales=extra_rationales,
            extra_suggestions=extra_suggestions,
            extra_observations=extra_observations,
            eval_mode=mode,
            skills=skill_results,
            intent_confidence=intent_confidence,
            cost_usd=cost,
            cost_is_estimate=cost_is_estimate,
            mock=self.mock,
            failed=bool(scoring_error),
            error=scoring_error,
            raw=vlm_result,
        )


def _build_summary(score: float, tradition: str, dims: dict, mode: str = "strict") -> str:
    """Generate a human-readable summary."""
    tradition_label = tradition.replace("_", " ").title()

    strongest = max(dims, key=lambda k: dims.get(k, 0)) if dims else "L1"
    weakest = min(dims, key=lambda k: dims.get(k, 0)) if dims else "L5"

    level_names = {"L1": "Visual Perception", "L2": "Technical Execution", "L3": "Cultural Context", "L4": "Critical Interpretation", "L5": "Philosophical Aesthetics"}

    if mode == "reference":
        alignment = "high" if score >= 0.8 else "moderate" if score >= 0.5 else "low"
        return (
            f"{alignment.title()} alignment ({score:.0%}) with {tradition_label} tradition. "
            f"Closest: {level_names.get(strongest, strongest)} ({dims.get(strongest, 0):.0%}). "
            f"Most divergent: {level_names.get(weakest, weakest)} ({dims.get(weakest, 0):.0%})."
        )

    quality = "excellent" if score >= 0.8 else "good" if score >= 0.6 else "fair" if score >= 0.4 else "needs improvement"
    return (
        f"Overall {quality} ({score:.0%}) under {tradition_label} tradition. "
        f"Strongest: {level_names.get(strongest, strongest)} ({dims.get(strongest, 0):.0%}). "
        f"Room for growth: {level_names.get(weakest, weakest)} ({dims.get(weakest, 0):.0%})."
    )


def _build_recommendations(
    dims: dict, weights: dict, tradition: str, suggestions: dict | None = None,
) -> list[str]:
    """Generate actionable recommendations based on weak dimensions.

    Prefers VLM-generated suggestions when available (more specific),
    falls back to generic advice.
    """
    recs = []
    generic_advice = {
        "L1": "Improve composition, layout, and spatial arrangement for stronger visual impact.",
        "L2": "Focus on technical execution -- rendering quality, detail precision, and medium fidelity.",
        "L3": "Deepen cultural context -- incorporate tradition-specific motifs, terminology, and conventions.",
        "L4": "Ensure respectful representation -- avoid cultural insensitivity and taboo violations.",
        "L5": "Explore philosophical depth -- emotional resonance, spiritual qualities, and aesthetic harmony.",
    }
    for level in sorted(dims, key=lambda k: dims.get(k, 0)):
        if dims.get(level, 0) < 0.7:
            # Prefer VLM suggestion (specific) over generic advice
            vlm_suggestion = (suggestions or {}).get(level, "")
            if vlm_suggestion:
                recs.append(vlm_suggestion)
            else:
                recs.append(generic_advice.get(level, f"Improve {level}."))
        if len(recs) >= 3:
            break
    return recs


def _estimate_cost(skills: list[str]) -> float:
    """Estimate API cost in USD."""
    base = 0.001  # VLM critic
    intent = 0.0001  # intent resolution
    per_skill = 0.0002  # each extra skill
    return round(base + intent + len(skills) * per_skill, 6)


def _mock_scores(tradition: str = "default") -> dict:
    """Return deterministic mock L1-L5 scores for testing without API key."""
    import hashlib

    seed = int(hashlib.md5(tradition.encode()).hexdigest()[:8], 16) % 1000
    base = 0.65 + (seed % 20) / 100  # 0.65 - 0.84
    tradition_label = tradition.replace("_", " ").title()
    return {
        "L1": round(min(base + 0.05, 1.0), 4),
        "L2": round(min(base + 0.00, 1.0), 4),
        "L3": round(min(base + 0.10, 1.0), 4),
        "L4": round(min(base + 0.03, 1.0), 4),
        "L5": round(min(base + 0.08, 1.0), 4),
        "L1_rationale": "Mock: Visual composition assessment.",
        "L2_rationale": "Mock: Technical execution assessment.",
        "L3_rationale": "Mock: Cultural context assessment.",
        "L4_rationale": "Mock: Critical interpretation assessment.",
        "L5_rationale": "Mock: Philosophical aesthetics assessment.",
        "L1_suggestion": f"Enhance spatial balance with {tradition_label}-appropriate composition.",
        "L2_suggestion": f"Refine technique precision for {tradition_label} standards.",
        "L3_suggestion": f"Incorporate more {tradition_label} cultural motifs and terminology.",
        "L4_suggestion": "Ensure cultural references are respectful and contextually appropriate.",
        "L5_suggestion": "Deepen philosophical resonance through symbolic layering.",
        "L1_deviation_type": "traditional",
        "L2_deviation_type": "traditional",
        "L3_deviation_type": "traditional",
        "L4_deviation_type": "traditional",
        "L5_deviation_type": "traditional",
        "risk_flags": [],
    }
