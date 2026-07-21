"""Evaluate and Create module tests -- import, signature, and mocked functionality."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vulca.types import CreateResult, EvalResult, SkillResult


# -- Evaluate Module -------------------------------------------------------


class TestEvaluateImport:
    """Verify evaluate module structure."""

    def test_evaluate_is_callable(self):
        from vulca.evaluate import evaluate
        assert callable(evaluate)

    def test_aevaluate_is_async(self):
        from vulca.evaluate import aevaluate
        assert inspect.iscoroutinefunction(aevaluate)

    def test_evaluate_signature(self):
        from vulca.evaluate import evaluate
        sig = inspect.signature(evaluate)
        params = list(sig.parameters.keys())
        assert "image" in params
        assert "intent" in params
        assert "tradition" in params
        assert "subject" in params
        assert "skills" in params
        assert "api_key" in params
        assert "vlm_model" in params

    def test_aevaluate_signature(self):
        from vulca.evaluate import aevaluate
        sig = inspect.signature(aevaluate)
        params = list(sig.parameters.keys())
        assert "image" in params
        assert "include_evidence" not in params
        assert "vlm_model" in params


class TestEvaluateWithMock:
    """Test evaluate flow with mocked Engine."""

    def test_aevaluate_calls_engine(self):
        """aevaluate delegates to Engine.run and returns EvalResult."""
        mock_result = EvalResult(
            score=0.75,
            tradition="chinese_xieyi",
            dimensions={"L1": 0.8, "L2": 0.7, "L3": 0.75, "L4": 0.7, "L5": 0.8},
            rationales={"L1": "Good", "L2": "Ok", "L3": "Good", "L4": "Ok", "L5": "Good"},
            summary="Test",
            risk_level="low",
            risk_flags=[],
            recommendations=[],
        )

        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(return_value=mock_result)

        with patch("vulca._engine.Engine.get_instance", return_value=mock_engine):
            from vulca.evaluate import aevaluate
            result = asyncio.run(aevaluate("test.jpg", api_key="fake-key"))

        assert isinstance(result, EvalResult)
        assert result.score == 0.75
        assert result.tradition == "chinese_xieyi"
        mock_engine.run.assert_called_once()

    def test_evaluate_sync_calls_engine(self):
        """evaluate (sync) also delegates to Engine."""
        mock_result = EvalResult(
            score=0.60,
            tradition="default",
            dimensions={"L1": 0.6, "L2": 0.6, "L3": 0.6, "L4": 0.6, "L5": 0.6},
            rationales={},
            summary="Test",
            risk_level="low",
            risk_flags=[],
            recommendations=[],
        )

        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(return_value=mock_result)

        with patch("vulca._engine.Engine.get_instance", return_value=mock_engine):
            from vulca.evaluate import evaluate
            result = evaluate("test.jpg", api_key="fake-key")

        assert isinstance(result, EvalResult)
        assert result.score == 0.60

    def test_aevaluate_records_latency(self):
        """aevaluate sets latency_ms on the result."""
        mock_result = EvalResult(
            score=0.5,
            tradition="default",
            dimensions={},
            rationales={},
            summary="",
            risk_level="low",
            risk_flags=[],
            recommendations=[],
            latency_ms=0,
        )

        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(return_value=mock_result)

        with patch("vulca._engine.Engine.get_instance", return_value=mock_engine):
            from vulca.evaluate import aevaluate
            result = asyncio.run(aevaluate("test.jpg", api_key="fake-key"))

        # latency_ms should be set (>= 0, usually very small in tests)
        assert result.latency_ms >= 0

    def test_engine_run_rubric_only_skips_vlm(self):
        import os
        import vulca._engine as eng_mod
        from vulca._engine import Engine

        env = {k: v for k, v in os.environ.items()
               if k not in {"GOOGLE_API_KEY", "GEMINI_API_KEY", "VULCA_VLM_MODEL"}}
        eng_mod._instance = None

        with patch.dict(os.environ, env, clear=True):
            with patch("vulca._engine.score_image", new=AsyncMock()) as mock_score, \
                 patch("vulca._engine.load_image_base64", new=AsyncMock()) as mock_load:
                engine = Engine(_allow_missing_api_key=True)
                result = asyncio.run(
                    engine.run(
                        "/tmp/test.png",
                        tradition="chinese_gongbi",
                        mode="rubric_only",
                    )
                )

        assert result["eval_mode"] == "rubric_only"
        assert result["tradition"] == "chinese_gongbi"
        assert result["image_path"] == "/tmp/test.png"
        assert result["score"] is None
        assert result["summary"] == ""
        assert result["score_schema"]["L1"] is None
        assert result["score_schema"]["L5_rationale"] == ""
        assert "rubric" in result
        assert "tradition_layers" in result["rubric"]
        mock_score.assert_not_called()
        mock_load.assert_not_called()

    def test_aevaluate_runtime_vlm_model_ollama_without_env(self):
        import os
        import vulca._engine as eng_mod

        mock_vlm = {
            "L1": 0.8,
            "L2": 0.7,
            "L3": 0.75,
            "L4": 0.7,
            "L5": 0.8,
            "L1_rationale": "",
            "L2_rationale": "",
            "L3_rationale": "",
            "L4_rationale": "",
            "L5_rationale": "",
        }
        env = {k: v for k, v in os.environ.items()
               if k not in {"GOOGLE_API_KEY", "GEMINI_API_KEY", "VULCA_VLM_MODEL"}}
        eng_mod._instance = None

        with patch.dict(os.environ, env, clear=True):
            with patch("vulca._engine.load_image_base64", new=AsyncMock(return_value=("AAAA", "image/png"))), \
                 patch("vulca._engine.score_image", new=AsyncMock(return_value=mock_vlm)) as mock_score:
                from vulca.evaluate import aevaluate

                result = asyncio.run(
                    aevaluate(
                        "test.png",
                        tradition="default",
                        vlm_model="ollama/gemma3:4b",
                    )
                )

        assert isinstance(result, EvalResult)
        assert result.eval_mode == "strict"
        assert result.tradition == "default"
        score_kwargs = mock_score.await_args.kwargs
        assert score_kwargs["model"] == "ollama/gemma3:4b"
        assert score_kwargs["api_key"] == "local"


# -- Create Module ---------------------------------------------------------


class TestCreateImport:
    """Verify create module structure."""

    def test_create_is_callable(self):
        from vulca.create import create
        assert callable(create)

    def test_acreate_is_async(self):
        from vulca.create import acreate
        assert inspect.iscoroutinefunction(acreate)

    def test_create_signature(self):
        from vulca.create import create
        sig = inspect.signature(create)
        params = list(sig.parameters.keys())
        assert "intent" in params
        assert "tradition" in params
        assert "subject" in params
        assert "provider" in params
        assert "api_key" in params
        assert "base_url" in params

    def test_acreate_signature(self):
        from vulca.create import acreate
        sig = inspect.signature(acreate)
        params = list(sig.parameters.keys())
        assert "intent" in params
        assert "provider" in params


class TestCreateWithMock:
    """Test create flow with mocked httpx."""

    def test_acreate_builds_create_result(self):
        """acreate posts to API and returns CreateResult."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "session_id": "sess-test",
            "mode": "create",
            "tradition": "chinese_xieyi",
            "total_rounds": 2,
            "best_candidate_id": "cand-01",
            "best_image_url": "https://example.com/img.png",
            "scores": {"L1": 0.8},
            "weighted_total": 0.75,
            "summary": "Created artwork",
            "recommendations": ["Add more detail"],
            "latency_ms": 500,
            "cost_usd": 0.01,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        import httpx
        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            from vulca.create import acreate
            result = asyncio.run(acreate(
                "ink wash landscape", api_key="fake-key", mode="remote"
            ))

        assert isinstance(result, CreateResult)
        assert result.session_id == "sess-test"
        assert result.tradition == "chinese_xieyi"
        assert result.total_rounds == 2
        assert result.best_candidate_id == "cand-01"

    def test_acreate_uses_env_url(self):
        """acreate reads VULCA_API_URL from environment."""
        import os
        from urllib.parse import urlsplit

        import httpx

        mock_response = MagicMock()
        mock_response.json.return_value = {"session_id": "s1"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        orig = os.environ.get("VULCA_API_URL")
        os.environ["VULCA_API_URL"] = "https://custom.api.com"

        try:
            with patch.object(httpx, "AsyncClient", return_value=mock_client):
                from vulca.create import acreate
                asyncio.run(acreate("test intent", mode="remote"))

            # Verify the URL was used
            call_args = mock_client.post.call_args
            assert urlsplit(call_args[0][0]).hostname == "custom.api.com"
        finally:
            if orig:
                os.environ["VULCA_API_URL"] = orig
            else:
                os.environ.pop("VULCA_API_URL", None)


# -- Session Module --------------------------------------------------------


class TestSessionImport:
    """Verify session module structure."""

    def test_session_is_callable(self):
        from vulca.session import session
        assert callable(session)

    def test_asession_is_async(self):
        from vulca.session import asession
        assert inspect.iscoroutinefunction(asession)

    def test_session_signature(self):
        from vulca.session import session
        sig = inspect.signature(session)
        params = list(sig.parameters.keys())
        assert "intent" in params
        assert "image" in params
        assert "tradition" in params
        assert "api_key" in params

    def test_asession_routes_with_image(self):
        """asession with image calls aevaluate."""
        mock_result = EvalResult(
            score=0.8,
            tradition="default",
            dimensions={},
            rationales={},
            summary="",
            risk_level="low",
            risk_flags=[],
            recommendations=[],
        )

        with patch("vulca.evaluate.aevaluate", new_callable=AsyncMock, return_value=mock_result) as mock_eval:
            from vulca.session import asession
            result = asyncio.run(asession("test intent", image="test.jpg", api_key="fake"))

        assert isinstance(result, EvalResult)
        mock_eval.assert_called_once()

    def test_asession_routes_without_image(self):
        """asession without image calls acreate."""
        mock_result = CreateResult(session_id="s1")

        with patch("vulca.create.acreate", new_callable=AsyncMock, return_value=mock_result) as mock_create:
            from vulca.session import asession
            result = asyncio.run(asession("create ink wash"))

        assert isinstance(result, CreateResult)
        mock_create.assert_called_once()


# -- EvalResult Serialization ----------------------------------------------


class TestResultSerialization:
    """Verify results can be serialized with dataclasses.asdict."""

    def test_eval_result_to_dict(self):
        result = EvalResult(
            score=0.7,
            tradition="default",
            dimensions={"L1": 0.7},
            rationales={"L1": "Good"},
            summary="Test",
            risk_level="low",
            risk_flags=[],
            recommendations=["Improve"],
        )
        d = asdict(result)
        assert d["score"] == 0.7
        assert d["tradition"] == "default"
        assert d["dimensions"]["L1"] == 0.7

    def test_create_result_to_dict(self):
        result = CreateResult(session_id="s1", mode="create", tradition="default")
        d = asdict(result)
        assert d["session_id"] == "s1"
        assert d["mode"] == "create"

    def test_skill_result_to_dict(self):
        sr = SkillResult(skill="brand", score=0.8, summary="Good")
        d = asdict(sr)
        assert d["skill"] == "brand"
        assert d["score"] == 0.8

    def test_eval_result_with_skills_to_dict(self):
        """EvalResult containing SkillResults can be fully serialized."""
        result = EvalResult(
            score=0.7,
            tradition="default",
            dimensions={},
            rationales={},
            summary="",
            risk_level="low",
            risk_flags=[],
            recommendations=[],
            skills={"brand": SkillResult(skill="brand", score=0.8, summary="Good")},
        )
        d = asdict(result)
        assert d["skills"]["brand"]["score"] == 0.8


def test_evaluate_node_applies_vlm_content_fidelity_gate():
    from vulca.content_lock import extract_content_lock
    from vulca.pipeline.node import NodeContext
    from vulca.pipeline.nodes import EvaluateNode

    lock = extract_content_lock(
        "Ink and wash painting of bamboo beside vertical Chinese calligraphy."
    )
    ctx = NodeContext(
        subject="track1_0002",
        intent=lock.original_intent,
        tradition="chinese_xieyi",
        provider="gemini",
        api_key="fake-key",
    )
    ctx.set("image_b64", "iVBORw0KGgo=")
    ctx.set("node_params", {"evaluate": {"content_lock": lock.to_dict()}})

    scored = {
        "L1": 0.95,
        "L2": 0.92,
        "L3": 1.0,
        "L4": 1.0,
        "L5": 0.94,
        "L1_rationale": "Strong image.",
        "L2_rationale": "Strong technique.",
        "L3_rationale": "Strong style.",
        "L4_rationale": "Respectful.",
        "L5_rationale": "Poetic.",
        "content_fidelity_gate": {
            "required_subjects": ["bamboo"],
            "missing_required_subjects": ["bamboo"],
            "required_text_elements": ["vertical Chinese calligraphy"],
            "missing_required_text_elements": [],
        },
    }

    with patch("vulca._vlm.score_image", new=AsyncMock(return_value=scored)) as mock_score:
        result = asyncio.run(EvaluateNode().run(ctx))

    assert mock_score.await_args.kwargs["content_lock"] == lock.to_dict()
    assert result["weighted_total"] == 0.25
    assert result["scores"]["L3"] == 0.25
    assert "content_fidelity_failed" in result["risk_flags"]


def test_evaluate_node_applies_vlm_relation_semantics_gate():
    from vulca.content_lock import extract_content_lock
    from vulca.pipeline.node import NodeContext
    from vulca.pipeline.nodes import EvaluateNode

    lock = extract_content_lock(
        "Wartime illustration of mounted soldiers beside fleeing civilians, "
        "burning village ruins, and aircraft overhead."
    )
    ctx = NodeContext(
        subject="track1_0747",
        intent=lock.original_intent,
        tradition="default",
        provider="gemini",
        api_key="fake-key",
    )
    ctx.set("image_b64", "iVBORw0KGgo=")
    ctx.set("node_params", {"evaluate": {"content_lock": lock.to_dict()}})

    scored = {
        "L1": 0.95,
        "L2": 0.92,
        "L3": 1.0,
        "L4": 1.0,
        "L5": 0.94,
        "L1_rationale": "Strong image.",
        "L2_rationale": "Strong technique.",
        "L3_rationale": "Strong style.",
        "L4_rationale": "Respectful.",
        "L5_rationale": "Poetic.",
        "content_fidelity_gate": {
            "required_relations": lock.required_relations,
            "apparent_relations": ["mounted soldiers appear to chase civilians"],
            "relation_semantics_failed": True,
            "forbidden_readings_present": ["soldiers chasing civilians"],
        },
    }

    with patch("vulca._vlm.score_image", new=AsyncMock(return_value=scored)):
        result = asyncio.run(EvaluateNode().run(ctx))

    assert result["weighted_total"] == 0.25
    assert result["scores"]["L4"] == 0.25
    assert "content_fidelity_failed" in result["risk_flags"]
    assert "Relation semantics failed" in result["rationales"]["content_fidelity"]


def test_evaluate_node_marks_vlm_parse_fallback_explicitly():
    from vulca.pipeline.node import NodeContext
    from vulca.pipeline.nodes import EvaluateNode

    ctx = NodeContext(
        subject="track1_0064",
        intent="A Gongbi vertical hanging scroll with lotus blossoms.",
        tradition="chinese_gongbi",
        provider="gemini",
        api_key="fake-key",
    )
    ctx.set("image_b64", "iVBORw0KGgo=")

    scored = {
        "error": "Could not parse JSON from LLM output",
        "L1": 0.0,
        "L2": 0.0,
        "L3": 0.0,
        "L4": 0.0,
        "L5": 0.0,
    }

    with patch("vulca._vlm.score_image", new=AsyncMock(return_value=scored)):
        result = asyncio.run(EvaluateNode().run(ctx))

    assert result["evaluation_source"] == "mock_fallback"
    assert result["evaluation_error"] == "Could not parse JSON from LLM output"


def test_extract_scoring_falls_back_to_first_json_after_scratchpad():
    from vulca._parse import parse_llm_json
    from vulca._vlm import _extract_scoring

    raw = """**Phase 1 - Scratchpad**
<observation>
The model ignored the requested subject. This note includes braces {not json}.
</observation>
{"L1": 0.2, "L2": 0.2, "L3": 0.1, "L4": 0.1, "L5": 0.2}
"""

    scoring = _extract_scoring(raw)
    parsed = parse_llm_json(scoring)

    assert parsed["L3"] == 0.1
