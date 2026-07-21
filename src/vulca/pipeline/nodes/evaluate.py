"""EvaluateNode -- L1-L5 image scoring via VLM or mock."""

from __future__ import annotations

import logging
from typing import Any

from vulca.pipeline.node import NodeContext, PipelineNode
from vulca.providers.capabilities import VLM_SCORING, provider_capabilities

logger = logging.getLogger("vulca")


class EvaluateNode(PipelineNode):
    """Score a generated image on L1-L5 dimensions.

    Wraps :func:`vulca._vlm.score_image` and computes a weighted total
    using the tradition's L1-L5 weights.
    """

    name = "evaluate"

    async def run(self, ctx: NodeContext) -> dict[str, Any]:
        # ------------------------------------------------------------------
        # Algo coverage: scan ctx.data for keys ending in '_evidence' and
        # determine which L1-L5 dimensions are covered by upstream tool nodes.
        # ------------------------------------------------------------------
        algo_covered_dims, algo_scores = self._detect_algo_coverage(ctx)

        img_b64 = ctx.get("image_b64", "")
        img_mime = ctx.get("image_mime", "image/png")

        weights = self._get_weights(ctx)

        if not img_b64:
            logger.warning("EvaluateNode: no image_b64 in context, using mock scores")
            result = self._mock_scores(ctx)
            merged = self._merge_algo_scores(result, algo_scores, algo_covered_dims, weights)
            return self._apply_content_fidelity_gate(ctx, merged)

        if VLM_SCORING not in provider_capabilities(ctx.provider) or not ctx.api_key:
            result = self._mock_scores(ctx)
            merged = self._merge_algo_scores(result, algo_scores, algo_covered_dims, weights)
            return self._apply_content_fidelity_gate(ctx, merged)

        result = await self._vlm_scores(ctx, img_b64, img_mime)
        merged = self._merge_algo_scores(result, algo_scores, algo_covered_dims, weights)
        return self._apply_content_fidelity_gate(ctx, merged)

    @staticmethod
    def _detect_algo_coverage(
        ctx: NodeContext,
    ) -> tuple[list[str], dict[str, float]]:
        """Scan ctx.data for _evidence keys and build algo_scores for covered dims.

        Returns
        -------
        (algo_covered_dims, algo_scores)
            algo_covered_dims: list of L-dimension strings covered by algo tools
            algo_scores:       {dim: score} where score = 0.5 + confidence * 0.4
        """
        from vulca.tools.registry import ToolRegistry

        try:
            registry = ToolRegistry()
            registry.discover()
            replacements = registry.list_replacements()
        except Exception:
            return [], {}

        # Build a map: tool_name → list[dim] it covers under "evaluate"
        # e.g. {"whitespace_analyze": ["L1"], "color_gamut_check": ["L3"]}
        tool_dims: dict[str, list[str]] = {}
        for tool_name, replaces in replacements.items():
            dims = replaces.get("evaluate", [])
            if dims:
                tool_dims[tool_name] = dims

        algo_covered_dims: list[str] = []
        algo_scores: dict[str, float] = {}

        for tool_name, dims in tool_dims.items():
            evidence_key = f"{tool_name}_evidence"
            evidence = ctx.get(evidence_key)
            if evidence is None:
                continue
            confidence = float(evidence.get("confidence", 0.0))
            score = 0.5 + confidence * 0.4
            for dim in dims:
                if dim not in algo_covered_dims:
                    algo_covered_dims.append(dim)
                algo_scores[dim] = round(score, 4)

        return algo_covered_dims, algo_scores

    @staticmethod
    def _merge_algo_scores(
        result: dict[str, Any],
        algo_scores: dict[str, float],
        algo_covered_dims: list[str],
        weights: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Merge algo-derived scores into *result* and recompute weighted_total.

        Parameters
        ----------
        result:
            Dict returned by _mock_scores() or _vlm_scores().
        algo_scores:
            {dim: score} derived from upstream tool evidence.
        algo_covered_dims:
            Ordered list of dimensions covered by algo tools.

        Returns
        -------
        dict
            Updated result with overwritten scores, recomputed weighted_total,
            and ``algo_covered_dims`` key.
        """
        if not algo_covered_dims:
            result["algo_covered_dims"] = []
            return result

        scores: dict[str, float] = dict(result.get("scores", {}))
        for dim, score in algo_scores.items():
            scores[dim] = score

        # Recompute weighted_total with the merged scores
        # We don't have ctx here, so read weights from what's in the result
        # We need to recompute — use the same formula as _mock_scores
        # The weights are not stored in result, so we re-read from tradition.
        # Use uniform weights as safe fallback; caller context is lost here.
        # To keep this static, we sum with equal 0.2 weight if no weights stored.
        # But we can use the stored weighted_total as baseline and adjust.
        # Better: recompute from scratch using uniform 0.2 (5 dimensions).
        # This is acceptable since weights are applied in _mock_scores too.
        # Use tradition-specific weights if provided, uniform 0.2 as fallback
        w = weights or {}
        weighted_total = sum(scores.get(f"L{i}", 0.0) * w.get(f"L{i}", 0.2) for i in range(1, 6))

        result = dict(result)
        result["scores"] = scores
        result["weighted_total"] = round(weighted_total, 4)
        result["algo_covered_dims"] = algo_covered_dims
        return result

    @staticmethod
    def _get_weights(ctx: NodeContext) -> dict[str, float]:
        """Resolve L1-L5 weights: custom (from Canvas slider) > tradition default."""
        node_params = ctx.get("node_params") or {}
        custom = (node_params.get("evaluate") or {}).get("custom_weights")
        if custom and isinstance(custom, dict):
            return custom
        from vulca.cultural import get_weights
        return get_weights(ctx.tradition)

    @staticmethod
    def _apply_content_fidelity_gate(
        ctx: NodeContext,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        node_params = ctx.get("node_params") or {}
        eval_params = node_params.get("evaluate") or {}
        gate = result.get("content_fidelity_gate") or eval_params.get(
            "content_fidelity_gate"
        )
        if not gate:
            return result

        from vulca.content_lock import apply_content_fidelity_gate

        return apply_content_fidelity_gate(result, gate)

    @staticmethod
    def _apply_locked_dimensions(
        new_scores: dict[str, float],
        locked: list[str],
        previous: dict[str, float],
    ) -> dict[str, float]:
        """Overwrite locked dimensions with previous-round scores.

        Returns a copy of *new_scores* with locked dimensions replaced by
        values from *previous* (when available).
        """
        result = dict(new_scores)
        for dim in locked:
            if dim in previous:
                result[dim] = previous[dim]
        return result

    @staticmethod
    def _mock_scores(ctx: NodeContext) -> dict[str, Any]:
        """Return deterministic mock scores for testing."""
        base = 0.65 + (ctx.round_num * 0.05)
        scores = {
            "L1": min(1.0, base + 0.05),
            "L2": min(1.0, base),
            "L3": min(1.0, base + 0.10),
            "L4": min(1.0, base + 0.03),
            "L5": min(1.0, base + 0.08),
        }
        rationales = {f"{k}_rationale": f"Mock score for {k}" for k in scores}

        node_params = ctx.get("node_params") or {}
        locked: list[str] = (node_params.get("evaluate") or {}).get("locked_dimensions", [])
        previous: dict[str, float] = ctx.get("scores") or {}
        if locked and previous:
            scores = EvaluateNode._apply_locked_dimensions(scores, locked, previous)

        weights = EvaluateNode._get_weights(ctx)
        weighted_total = sum(scores[k] * weights.get(k, 0.2) for k in scores)

        return {
            "scores": scores,
            "rationales": rationales,
            "weighted_total": round(weighted_total, 4),
        }

    @staticmethod
    async def _vlm_scores(
        ctx: NodeContext,
        img_b64: str,
        img_mime: str,
    ) -> dict[str, Any]:
        """Call VLM for real L1-L5 evaluation."""
        from vulca._vlm import score_image

        eval_mode = ctx.get("eval_mode", "strict")
        node_params = ctx.get("node_params") or {}
        eval_params = node_params.get("evaluate") or {}

        data = await score_image(
            img_b64=img_b64,
            mime=img_mime,
            subject=ctx.subject or ctx.intent,
            tradition=ctx.tradition,
            api_key=ctx.api_key,
            mode=eval_mode,
            content_lock=eval_params.get("content_lock"),
        )

        # If VLM failed (quota/network error), fall back to mock scores
        if data.get("error"):
            logger.warning("VLM scoring failed, falling back to mock: %s", data["error"])
            fallback = EvaluateNode._mock_scores(ctx)
            fallback["evaluation_source"] = "mock_fallback"
            fallback["evaluation_error"] = str(data["error"])
            return fallback

        scores = {f"L{i}": data.get(f"L{i}", 0.0) for i in range(1, 6)}
        rationales = {
            f"L{i}_rationale": data.get(f"L{i}_rationale", "") for i in range(1, 6)
        }

        locked_vlm: list[str] = (node_params.get("evaluate") or {}).get("locked_dimensions", [])
        previous_vlm: dict[str, float] = ctx.get("scores") or {}
        if locked_vlm and previous_vlm:
            scores = EvaluateNode._apply_locked_dimensions(scores, locked_vlm, previous_vlm)

        weights = EvaluateNode._get_weights(ctx)
        weighted_total = sum(scores[k] * weights.get(k, 0.2) for k in scores)

        return {
            "scores": scores,
            "rationales": rationales,
            "risk_flags": data.get("risk_flags", []),
            "weighted_total": round(weighted_total, 4),
            "content_fidelity_gate": data.get("content_fidelity_gate"),
            "evaluation_source": "vlm",
            "evaluation_error": "",
        }
