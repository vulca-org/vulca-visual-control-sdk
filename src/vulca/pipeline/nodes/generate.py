"""GenerateNode -- image generation via pluggable providers."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import re
import time
from typing import Any

from vulca.pipeline.node import NodeContext, PipelineNode

logger = logging.getLogger("vulca")

# L-label → full dimension name (for refinement strategies)
_L_TO_DIM = {
    "L1": "visual_perception",
    "L2": "technical_analysis",
    "L3": "cultural_context",
    "L4": "critical_interpretation",
    "L5": "philosophical_aesthetic",
}

# Per-dimension refinement strategies (ported from old DraftAgent)
_REFINEMENT_STRATEGIES: dict[str, str] = {
    "visual_perception": (
        "Focus on visual composition: improve spatial arrangement, color harmony, "
        "contrast, line quality, and overall visual balance. Enhance the image's "
        "immediate visual impact."
    ),
    "technical_analysis": (
        "Improve technical execution: refine brushwork/rendering technique, "
        "material handling, detail precision, and craftsmanship quality. "
        "Ensure technical mastery is evident."
    ),
    "cultural_context": (
        "Strengthen cultural authenticity: incorporate tradition-specific symbols, "
        "motifs, and compositional conventions. Ensure the work reflects deep "
        "understanding of its cultural tradition's visual language."
    ),
    "critical_interpretation": (
        "Deepen interpretive layers: add narrative depth, symbolic richness, "
        "and art-historical references. The work should invite critical reading "
        "beyond surface aesthetics."
    ),
    "philosophical_aesthetic": (
        "Elevate philosophical dimension: embed philosophical concepts through "
        "visual metaphor, explore beauty/sublimity, and create contemplative depth. "
        "The work should transcend technique to reach aesthetic meaning."
    ),
}


def _looks_like_sample_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9]*[_-]\d{2,}", value.strip(), re.IGNORECASE))


class GenerateNode(PipelineNode):
    """Generate an image from a text prompt via the Provider Registry.

    Supports any registered provider (mock, gemini/nb2, openai, comfyui, or
    custom ``ImageProvider`` instances passed via ``ctx.image_provider``).

    On round >= 2, incorporates previous round's critique feedback into the
    generation prompt for targeted improvement.
    """

    name = "generate"

    _GENERATE_TIMEOUT_S = 150  # Hard timeout for image generation

    async def run(self, ctx: NodeContext) -> dict[str, Any]:
        provider = ctx.provider or "mock"

        # Intentional literal: "mock" here means "no registered image provider
        # AND no injected instance" — the short-circuit to canned mock output.
        # Registered mock_v2 / user-defined providers are routed through the
        # ImageProviderRegistry via _provider_generate and never hit this branch,
        # so a capability lookup here would be functionally redundant.
        if provider == "mock" and ctx.image_provider is None:
            return self._mock_generate(ctx)

        # Route through Provider Registry (or custom image_provider)
        return await self._provider_generate(ctx, provider)

    # ------------------------------------------------------------------
    # Provider-based generation (uses Registry or custom instance)
    # ------------------------------------------------------------------

    async def _provider_generate(
        self, ctx: NodeContext, provider_name: str
    ) -> dict[str, Any]:
        """Generate image using the Provider Registry or a custom instance."""
        from vulca.providers import get_image_provider

        prompt = ctx.get("prompt") or ctx.subject or ctx.intent
        node_params = ctx.get("node_params") or {}
        gen_params = node_params.get("generate") or {}

        content_lock_data = gen_params.get("content_lock")
        if content_lock_data:
            from vulca.content_lock import (
                build_content_lock_prompt,
                content_lock_from_dict,
            )

            content_lock = content_lock_from_dict(content_lock_data)
            lock_prompt = build_content_lock_prompt(content_lock)
            if lock_prompt:
                original_prompt = ctx.intent or prompt
                prompt = (
                    f"{lock_prompt}\n\n"
                    f"USER INTENT TO PRESERVE VERBATIM:\n{original_prompt}"
                )

        # Build extra kwargs with cultural guidance + improvement instructions
        extra_kwargs: dict[str, Any] = {}

        cultural_guidance = self._build_generation_guidance(ctx.tradition)
        if cultural_guidance:
            extra_kwargs["cultural_guidance"] = cultural_guidance

        if ctx.round_num >= 2:
            improvement = self._build_improvement_prompt(ctx)
            if improvement:
                extra_kwargs["improvement_focus"] = improvement

        # Resolve reference image (top-level or node_params)
        ref_b64 = ctx.get("reference_image_b64") or ""
        if not ref_b64:
            ref_b64 = gen_params.get("reference_image_b64", "")

        # Inject color palette into prompt if provided
        color_palette = gen_params.get("color_palette", "")
        if color_palette:
            prompt = f"{prompt}\n\nColor palette: use these exact colors: {color_palette}"

        _progress = ctx.emit_progress or (lambda _msg: None)

        logger.info(
            "GenerateNode round %d via '%s' (%d chars prompt%s)",
            ctx.round_num,
            provider_name,
            len(prompt),
            ", +ref_image" if ref_b64 else "",
        )
        _progress(f"Generating via {provider_name} provider...")

        t0 = time.monotonic()
        try:
            # Use custom image_provider if available, else Registry lookup
            if ctx.image_provider is not None:
                provider_instance = ctx.image_provider
            else:
                # TODO(v0.21): plumb model/quality from pipeline ctx —
                # currently silently defaults to OpenAIImageProvider's
                # gpt-image-1. See v0.20 PR audit on layers_redraw fix.
                provider_instance = get_image_provider(
                    provider_name, api_key=ctx.api_key
                )

            subject_for_provider = ctx.subject or ""
            if content_lock_data and _looks_like_sample_id(subject_for_provider):
                subject_for_provider = ""

            result = await asyncio.wait_for(
                provider_instance.generate(
                    prompt,
                    tradition=ctx.tradition,
                    subject=subject_for_provider,
                    reference_image_b64=ref_b64,
                    **extra_kwargs,
                ),
                timeout=self._GENERATE_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "%s generation timed out after %ds — falling back to mock",
                provider_name,
                self._GENERATE_TIMEOUT_S,
            )
            return self._mock_generate(ctx)
        except Exception as exc:
            err = str(exc).lower()
            recoverable = any(
                k in err
                for k in ("429", "quota", "rate", "503", "unavailable", "timeout", "no image data")
            )
            if recoverable:
                logger.warning(
                    "%s API error — falling back to mock: %s", provider_name, exc
                )
                return self._mock_generate(ctx)
            raise

        latency_ms = int((time.monotonic() - t0) * 1000)
        _progress(
            f"Image generated in {latency_ms / 1000:.1f}s — preparing for evaluation"
        )

        candidate_id = (
            (result.metadata or {}).get("candidate_id")
            or hashlib.sha256(
                f"{ctx.subject}:{ctx.round_num}:{provider_name}".encode()
            ).hexdigest()[:12]
        )
        image_url = (result.metadata or {}).get(
            "image_url"
        ) or f"{provider_name}://{candidate_id}"

        logger.info(
            "%s generated image (%dms, %d chars b64)",
            provider_name,
            latency_ms,
            len(result.image_b64),
        )

        cultural_terms, cultural_taboos = self._extract_cultural_info(ctx.tradition)

        return {
            "image_b64": result.image_b64,
            "image_mime": result.mime,
            "candidate_id": candidate_id,
            "image_url": image_url,
            "cultural_guidance": {
                "terminology": cultural_terms,
                "taboos": cultural_taboos,
                "tradition": ctx.tradition,
            },
        }

    # ------------------------------------------------------------------
    # Mock provider (fast path, no external calls)
    # ------------------------------------------------------------------

    # Tradition → background color for mock SVG placeholders
    _TRADITION_COLORS: dict[str, str] = {
        "chinese_xieyi": "#3a3a3a",
        "chinese_gongbi": "#c43f2f",
        "japanese_traditional": "#264653",
        "japanese_wabi_sabi": "#264653",
        "islamic_geometric": "#2a9d8f",
        "watercolor": "#89c2d9",
        "western_academic": "#8a5a44",
        "western_classical": "#8a5a44",
        "african_traditional": "#bc6c25",
        "african_ubuntu": "#bc6c25",
        "south_asian": "#e9c46a",
        "persian_miniature": "#2a9d8f",
        "korean_minhwa": "#5F8A50",
    }

    @staticmethod
    def _mock_generate(ctx: NodeContext) -> dict[str, Any]:
        """Return a deterministic SVG placeholder with tradition/subject info."""
        candidate_id = hashlib.sha256(
            f"{ctx.subject}:{ctx.round_num}".encode()
        ).hexdigest()[:12]
        tradition = ctx.tradition or "default"
        bg = GenerateNode._TRADITION_COLORS.get(tradition, "#5F8A50")
        tradition_display = tradition.replace("_", " ").title()
        subject_value = ctx.subject or "Untitled"
        if _looks_like_sample_id(subject_value):
            subject_value = "Untitled"
        subject_display = subject_value[:50]
        # Escape XML special characters
        for old, new in [("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ('"', "&quot;")]:
            subject_display = subject_display.replace(old, new)
            tradition_display = tradition_display.replace(old, new)

        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512">'
            f'<rect width="512" height="512" fill="{bg}" rx="24"/>'
            f'<text x="256" y="200" text-anchor="middle" font-size="28" '
            f'fill="white" font-family="sans-serif">{tradition_display}</text>'
            f'<text x="256" y="256" text-anchor="middle" font-size="20" '
            f'fill="rgba(255,255,255,0.7)" font-family="sans-serif">Round {ctx.round_num}</text>'
            f'<text x="256" y="310" text-anchor="middle" font-size="16" '
            f'fill="rgba(255,255,255,0.5)" font-family="sans-serif">{subject_display}</text>'
            f'<text x="256" y="420" text-anchor="middle" font-size="14" '
            f'fill="rgba(255,255,255,0.3)" font-family="sans-serif">VULCA Preview</text>'
            f'</svg>'
        )
        img_b64 = base64.b64encode(svg.encode()).decode()

        cultural_terms, cultural_taboos = GenerateNode._extract_cultural_info(tradition)

        return {
            "image_b64": img_b64,
            "image_mime": "image/svg+xml",
            "candidate_id": candidate_id,
            "image_url": f"mock://{candidate_id}.svg",
            "cultural_guidance": {
                "terminology": cultural_terms,
                "taboos": cultural_taboos,
                "tradition": tradition,
            },
        }

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_cultural_info(tradition: str) -> tuple[list[str], list[str]]:
        """Extract cultural terms and taboos for frontend visibility."""
        cultural_terms: list[str] = []
        cultural_taboos: list[str] = []
        try:
            from vulca.cultural.loader import get_tradition
            tc = get_tradition(tradition)
            if tc:
                cultural_terms = [t.term for t in (tc.terminology or [])[:6]]
                cultural_taboos = [t.rule for t in (tc.taboos or [])]
        except Exception:
            logger.debug("Failed to extract cultural info for %s", tradition)
        return cultural_terms, cultural_taboos

    # ------------------------------------------------------------------
    # Cultural guidance for generation
    # ------------------------------------------------------------------

    @staticmethod
    def _build_generation_guidance(tradition: str) -> str:
        """Build cultural guidance for the generation prompt.

        Separate from _vlm.py's evaluation guidance — this tells the model
        HOW to create, not how to judge.
        """
        parts: list[str] = []

        try:
            from vulca.cultural.loader import get_tradition
            tc = get_tradition(tradition)
            if tc is not None:
                if tc.terminology:
                    terms = "\n".join(
                        f"  - Apply {t.term} ({t.term_zh}): "
                        f"{t.definition if isinstance(t.definition, str) else t.definition.get('en', '')}"
                        for t in tc.terminology[:6]
                    )
                    parts.append(f"Cultural techniques to incorporate:\n{terms}")

                if tc.taboos:
                    taboos = "\n".join(
                        f"  - AVOID: {t.rule}"
                        + (f" ({t.explanation})" if t.explanation else "")
                        for t in tc.taboos
                    )
                    parts.append(f"Cultural constraints (must respect):\n{taboos}")

        except Exception:
            logger.debug("Cultural guidance not available for %s", tradition)

        # Inject evolution context (simple hint or rich trend, based on data volume)
        try:
            import os
            from vulca.digestion.local_evolver import LocalEvolver
            data_dir = os.environ.get("VULCA_EVOLVED_DATA_DIR", "")
            evolver = LocalEvolver(data_dir=data_dir) if data_dir else LocalEvolver()
            evolved = evolver.load_evolved(tradition)
            if evolved and evolved.get("weak_dimensions"):
                session_count = evolved.get("session_count", 0)
                dim_labels = {
                    "L1": "Visual Perception", "L2": "Technical Execution",
                    "L3": "Cultural Context", "L4": "Critical Interpretation",
                    "L5": "Philosophical Aesthetics",
                }

                if session_count >= 5 and evolved.get("strict_weak"):
                    # Rich trend context (iteration 4)
                    core_dims = evolved.get("strict_weak", evolved["weak_dimensions"])
                    innovation = evolved.get("innovation_signals", []) + evolved.get("reference_trends", [])
                    innovation = list(dict.fromkeys(innovation))  # dedupe preserving order
                    # Stable = not in core or innovation
                    all_dims = ["L1", "L2", "L3", "L4", "L5"]
                    stable = [d for d in all_dims if d not in core_dims and d not in innovation]

                    lines = [f"Evolution context for {tradition} (based on {session_count} sessions):"]
                    if core_dims:
                        core_text = ", ".join(f"{d} ({dim_labels.get(d, d)})" for d in core_dims)
                        lines.append(f"- Strengthen: {core_text} — historically weaker in traditional use")
                    if innovation:
                        innov_text = ", ".join(f"{d} ({dim_labels.get(d, d)})" for d in innovation)
                        lines.append(f"- Creative space: {innov_text} — often explored by experimental users")
                    if stable:
                        stable_text = ", ".join(f"{d} ({dim_labels.get(d, d)})" for d in stable)
                        lines.append(f"- Maintain: {stable_text} — consistent across modes")
                    parts.append("\n".join(lines))
                else:
                    # Simple hint (iteration 1 fallback for < 5 sessions)
                    weak_text = ", ".join(
                        f"{d} ({dim_labels.get(d, d)})" for d in evolved["weak_dimensions"]
                    )
                    parts.append(
                        f"Evolution hint: historically weaker dimensions for {tradition}: "
                        f"{weak_text}. Give extra attention to these areas in your generation."
                    )
        except Exception:
            pass  # Evolution is advisory, never blocks generation

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Critique-driven improvement prompt (round >= 2)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_improvement_prompt(ctx: NodeContext) -> str:
        """Build improvement instructions from previous round's critique."""
        prev_scores: dict[str, float] = ctx.get("scores", {})
        prev_rationales: dict[str, str] = ctx.get("rationales", {})
        weakest: list[str] = ctx.get("weakest_dimensions", [])

        # Also check node_params for improvement_focus (from HITL rerun)
        node_params = ctx.get("node_params") or {}
        gen_params = node_params.get("generate") or {}
        improvement_focus = gen_params.get("improvement_focus", [])
        if improvement_focus and not weakest:
            weakest = improvement_focus

        if not prev_scores:
            # Even without prev_scores, if we have improvement_focus, generate guidance
            if improvement_focus:
                dim_names = [_L_TO_DIM.get(d, d) for d in improvement_focus]
                strategies = [_REFINEMENT_STRATEGIES.get(dn, "") for dn in dim_names]
                parts = [f"IMPROVEMENT FOCUS (Round {ctx.round_num}):"]
                for dim, strategy in zip(improvement_focus, strategies):
                    parts.append(f"\n  Focus on {_L_TO_DIM.get(dim, dim)}:")
                    if strategy:
                        parts.append(f"    Strategy: {strategy}")
                return "\n".join(parts)
            return ""

        if not weakest:
            sorted_dims = sorted(prev_scores.items(), key=lambda x: x[1])
            weakest = [d for d, _ in sorted_dims[:2]]

        parts = [
            f"IMPROVEMENT REQUIRED (Round {ctx.round_num}):",
            f"Previous round scored {ctx.get('weighted_total', 0.0):.2f} overall.",
            "\nWeakest dimensions to improve:",
        ]

        for dim in weakest:
            score = prev_scores.get(dim, 0.0)
            rationale = prev_rationales.get(f"{dim}_rationale", "")
            dim_name = _L_TO_DIM.get(dim, dim)
            strategy = _REFINEMENT_STRATEGIES.get(dim_name, "")

            parts.append(f"\n  {dim} ({score:.2f}/1.0):")
            if rationale:
                parts.append(f"    Critique: {rationale}")
            if strategy:
                parts.append(f"    Strategy: {strategy}")

        parts.append(
            "\nCreate a SIGNIFICANTLY improved version addressing these specific weaknesses. "
            "Maintain the strengths from the previous version."
        )

        return "\n".join(parts)
