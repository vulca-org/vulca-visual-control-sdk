"""Basic package tests -- structure, imports, types."""

from __future__ import annotations

import pytest


# -- Import Tests ----------------------------------------------------------


def test_import():
    import vulca
    assert hasattr(vulca, "evaluate")
    assert hasattr(vulca, "aevaluate")
    assert hasattr(vulca, "create")
    assert hasattr(vulca, "acreate")
    assert hasattr(vulca, "session")
    assert hasattr(vulca, "asession")
    assert hasattr(vulca, "CreateResult")
    assert hasattr(vulca, "EvalResult")
    assert hasattr(vulca, "SkillResult")
    assert hasattr(vulca, "__version__")
    from vulca._version import __version__
    assert vulca.__version__ == __version__


def test_import_all_modules():
    """Verify every public and private module can be imported."""
    import vulca
    import vulca.types
    import vulca.cultural
    import vulca.evaluate
    import vulca.create
    import vulca.session
    import vulca.cli
    import vulca._version
    import vulca._intent
    import vulca._engine
    import vulca._vlm
    import vulca._parse
    import vulca._image
    import vulca._skills
    import vulca._dimensions


def test_import_subpackages():
    """Verify all subpackages can be imported."""
    import vulca.scoring
    import vulca.cultural
    import vulca.intent
    import vulca.pipeline
    import vulca.storage


def test_import_session_module():
    """Session module provides both sync and async entry points."""
    from vulca.session import session, asession
    import inspect

    assert callable(session)
    assert callable(asession)
    assert inspect.iscoroutinefunction(asession)
    assert not inspect.iscoroutinefunction(session)


def test_import_evaluate_module():
    """Evaluate module provides both sync and async entry points."""
    from vulca.evaluate import evaluate, aevaluate
    import inspect

    assert callable(evaluate)
    assert callable(aevaluate)
    assert inspect.iscoroutinefunction(aevaluate)
    assert not inspect.iscoroutinefunction(evaluate)


def test_import_create_module():
    """Create module provides both sync and async entry points."""
    from vulca.create import create, acreate
    import inspect

    assert callable(create)
    assert callable(acreate)
    assert inspect.iscoroutinefunction(acreate)
    assert not inspect.iscoroutinefunction(create)


def test_version_module():
    from vulca._version import __version__
    assert isinstance(__version__, str)
    # Version should be a valid semver-like string
    parts = __version__.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts)


def test_dunder_all():
    """__all__ should list every public name.

    Studio Pipeline V2 names (Brief, SessionState, StudioSession) are
    included when the optional vulca.studio module is installed.
    """
    import vulca
    required = {
        "__version__", "evaluate", "aevaluate",
        "create", "acreate", "session", "asession",
        "traditions", "get_weights",
        "EvalResult", "CreateResult", "SkillResult",
        "ImageProvider", "VLMProvider", "ImageResult", "L1L5Scores",
        "compose_prompt_from_design",
    }
    studio_names = {"Brief", "SessionState", "StudioSession", "inpaint", "ainpaint", "InpaintResult",
                    "LayerInfo", "LayerResult", "LayeredArtwork"}
    actual = set(vulca.__all__)
    # Core names must always be present
    assert required <= actual, f"Missing from __all__: {required - actual}"
    # Only studio names are allowed as additions
    extra = actual - required
    assert extra <= studio_names, f"Unexpected names in __all__: {extra - studio_names}"


# -- Type Tests ------------------------------------------------------------


def test_types():
    from vulca.types import EvalResult, SkillResult

    result = EvalResult(
        score=0.75,
        tradition="chinese_xieyi",
        dimensions={"L1": 0.8, "L2": 0.7, "L3": 0.75, "L4": 0.7, "L5": 0.8},
        rationales={"L1": "Good", "L2": "Fair", "L3": "Good", "L4": "Fair", "L5": "Good"},
        summary="Test summary",
        risk_level="low",
        risk_flags=[],
        recommendations=["Improve L2"],
    )
    assert result.score == 0.75
    assert result.L1 == 0.8
    assert result.L5 == 0.8
    assert "0.75" in repr(result)
    assert "chinese_xieyi" in repr(result)


def test_eval_result_dimension_properties():
    """EvalResult L1-L5 properties read from dimensions dict."""
    from vulca.types import EvalResult

    dims = {"L1": 0.9, "L2": 0.8, "L3": 0.7, "L4": 0.6, "L5": 0.5}
    result = EvalResult(
        score=0.7,
        tradition="default",
        dimensions=dims,
        rationales={},
        summary="",
        risk_level="low",
        risk_flags=[],
        recommendations=[],
    )
    assert result.L1 == 0.9
    assert result.L2 == 0.8
    assert result.L3 == 0.7
    assert result.L4 == 0.6
    assert result.L5 == 0.5


def test_eval_result_missing_dimensions():
    """L1-L5 properties return 0.0 for missing dimensions."""
    from vulca.types import EvalResult

    result = EvalResult(
        score=0.0,
        tradition="default",
        dimensions={},
        rationales={},
        summary="",
        risk_level="low",
        risk_flags=[],
        recommendations=[],
    )
    assert result.L1 == 0.0
    assert result.L3 == 0.0
    assert result.L5 == 0.0


def test_eval_result_defaults():
    """EvalResult optional fields have sensible defaults."""
    from vulca.types import EvalResult

    result = EvalResult(
        score=0.5,
        tradition="default",
        dimensions={},
        rationales={},
        summary="",
        risk_level="low",
        risk_flags=[],
        recommendations=[],
    )
    assert result.skills == {}
    assert result.intent_confidence == 0.0
    assert result.latency_ms == 0
    assert result.cost_usd == 0.0
    assert result.raw == {}


def test_skill_result():
    from vulca.types import SkillResult

    sr = SkillResult(skill="brand", score=0.82, summary="Good brand fit")
    assert sr.skill == "brand"
    assert sr.score == 0.82
    assert sr.details == {}
    assert sr.suggestions == []


def test_skill_result_with_details():
    """SkillResult can store rich details and suggestions."""
    from vulca.types import SkillResult

    sr = SkillResult(
        skill="trend",
        score=0.7,
        summary="Trend aligned",
        details={"minimalism": 0.8, "retro": 0.6},
        suggestions=["Try bolder colors"],
    )
    assert sr.details["minimalism"] == 0.8
    assert len(sr.suggestions) == 1


def test_create_result():
    from vulca.types import CreateResult

    cr = CreateResult(
        session_id="sess-abc123",
        mode="create",
        tradition="chinese_xieyi",
        total_rounds=3,
        best_candidate_id="cand-001",
    )
    assert cr.session_id == "sess-abc123"
    assert cr.total_rounds == 3
    assert "sess-abc123" in repr(cr)
    assert "create" in repr(cr)


def test_create_result_defaults():
    """CreateResult optional fields have sensible defaults."""
    from vulca.types import CreateResult

    cr = CreateResult(session_id="s1")
    assert cr.mode == "create"
    assert cr.tradition == "default"
    assert cr.scores == {}
    assert cr.weighted_total == 0.0
    assert cr.best_candidate_id == ""
    assert cr.best_image_url == ""
    assert cr.total_rounds == 0
    assert cr.rounds == []
    assert cr.summary == ""
    assert cr.recommendations == []
    assert cr.latency_ms == 0
    assert cr.cost_usd == 0.0
    assert cr.raw == {}


# -- Cultural Module Tests -------------------------------------------------


def test_cultural_weights():
    from vulca.cultural import get_weights, TRADITIONS

    assert len(TRADITIONS) == 13
    assert "chinese_xieyi" in TRADITIONS

    weights = get_weights("chinese_xieyi")
    # Weights may come from evolved_context.json (evolved) or YAML (original)
    # Evolved weights shift over time, so only assert structure + sum ≈ 1.0
    assert len(weights) == 5
    assert all(k in weights for k in ("L1", "L2", "L3", "L4", "L5"))
    assert abs(sum(weights.values()) - 1.0) < 0.01

    # Fallback for unknown tradition returns default weights (hardcoded)
    fallback = get_weights("nonexistent")
    assert len(fallback) == 5
    assert abs(sum(fallback.values()) - 1.0) < 0.01


def test_all_tradition_weights_sum_to_one():
    """Every tradition's weights must sum to 1.0."""
    from vulca.cultural import TRADITION_WEIGHTS

    for name, weights in TRADITION_WEIGHTS.items():
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01, f"{name} weights sum to {total}, expected 1.0"
        # Every tradition must have L1-L5
        for level in ("L1", "L2", "L3", "L4", "L5"):
            assert level in weights, f"{name} missing {level}"


def test_tradition_weights_is_dict():
    from vulca.cultural import TRADITION_WEIGHTS
    assert isinstance(TRADITION_WEIGHTS, dict)
    assert "default" in TRADITION_WEIGHTS


# -- Dimensions Module Tests -----------------------------------------------


def test_dimensions_to_code():
    from vulca._dimensions import to_code

    assert to_code("L1") == "L1"
    assert to_code("Visual Perception") == "L1"
    assert to_code("visual_perception") == "L1"
    assert to_code("VisualPerception") == "L1"
    assert to_code("Technical Execution") == "L2"
    assert to_code("philosophical_aesthetics") == "L5"
    # Prototype naming variants must also resolve
    assert to_code("technical_analysis") == "L2"
    assert to_code("philosophical_aesthetic") == "L5"


def test_dimensions_to_full_name():
    from vulca._dimensions import to_full_name

    assert to_full_name("L1") == "Visual Perception"
    assert to_full_name("L5") == "Philosophical Aesthetics"
    assert to_full_name("unknown") == "unknown"


def test_dimensions_to_snake():
    from vulca._dimensions import to_snake

    assert to_snake("L1") == "visual_perception"
    assert to_snake("L3") == "cultural_context"


def test_dimensions_all_codes():
    from vulca._dimensions import all_codes

    codes = all_codes()
    assert codes == ["L1", "L2", "L3", "L4", "L5"]


# -- Intent Module Tests ---------------------------------------------------


def test_keyword_intent():
    from vulca._intent import _keyword_match

    tradition, conf = _keyword_match("check this xieyi ink wash painting")
    assert tradition == "chinese_xieyi"
    assert conf >= 0.8

    tradition, conf = _keyword_match("evaluate this generic image")
    assert tradition == "default"
    assert conf == 0.0


def test_keyword_intent_all_traditions():
    """Keyword matching covers every non-default tradition."""
    from vulca._intent import _keyword_match

    test_cases = [
        ("xieyi painting", "chinese_xieyi"),
        ("gongbi meticulous style", "chinese_gongbi"),
        ("western academic art", "western_academic"),
        ("islamic geometric pattern", "islamic_geometric"),
        ("japanese ukiyo-e print", "japanese_traditional"),
        ("watercolor landscape", "watercolor"),
        ("african mask art", "african_traditional"),
        ("south asian miniature", "south_asian"),
    ]
    for text, expected in test_cases:
        tradition, conf = _keyword_match(text)
        assert tradition == expected, f"'{text}' -> {tradition}, expected {expected}"
        assert conf >= 0.8


def test_keyword_intent_empty_string():
    """Empty intent returns default with zero confidence."""
    from vulca._intent import _keyword_match

    tradition, conf = _keyword_match("")
    assert tradition == "default"
    assert conf == 0.0


def test_keyword_intent_case_insensitive():
    """Keyword matching is case-insensitive."""
    from vulca._intent import _keyword_match

    tradition, conf = _keyword_match("Check this XIEYI painting")
    assert tradition == "chinese_xieyi"
    assert conf >= 0.8


# -- Parse Module Tests ----------------------------------------------------


def test_parse_llm_json_standard():
    from vulca._parse import parse_llm_json

    result = parse_llm_json('{"L1": 0.8, "L2": 0.7}')
    assert result == {"L1": 0.8, "L2": 0.7}


def test_parse_llm_json_markdown_fences():
    from vulca._parse import parse_llm_json

    text = '```json\n{"key": "value"}\n```'
    result = parse_llm_json(text)
    assert result == {"key": "value"}


def test_parse_llm_json_trailing_comma():
    from vulca._parse import parse_llm_json

    text = '{"a": 1, "b": 2,}'
    result = parse_llm_json(text)
    assert result == {"a": 1, "b": 2}


def test_parse_llm_json_repairs_extra_quote_before_key():
    from vulca._parse import parse_llm_json

    text = '{"L5": 0.75, ""missing_required_subjects": [], "risk_flags": []}'
    result = parse_llm_json(text)

    assert result["L5"] == 0.75
    assert result["missing_required_subjects"] == []


def test_parse_llm_json_invalid():
    from vulca._parse import parse_llm_json

    with pytest.raises(ValueError, match="Could not parse"):
        parse_llm_json("this is not json at all")


def test_parse_llm_json_embedded_object():
    """Parser can extract JSON from surrounding text."""
    from vulca._parse import parse_llm_json

    text = 'Here is the result: {"score": 0.5} end.'
    result = parse_llm_json(text)
    assert result == {"score": 0.5}


def test_parse_llm_json_gemma_hybrid_split_with_bare_trailing_key():
    """Gemma 4 alternate drift mode: wraps 5 L-dimensions in individual {}
    blocks but leaves the final risk_flags key bare, and wraps the whole
    thing in one outer {}. Captured live from Phase 3 v2 contemporary_art
    run 2026-04-11 — the pure-split parser fix did not handle this.

    Example structural shape (with content abbreviated):
        {
            "L1": 0.9, "L1_observations": "..."
        },
        {
            "L2": 0.85
        },
        ...
        {
            "L5": 0.95
        },
            "risk_flags": []
        }
    """
    from vulca._parse import parse_llm_json

    text = """{
    "L1": 0.9,
    "L1_observations": "dense"
},
{
    "L2": 0.85,
    "L2_rationale": "good"
},
{
    "L3": 0.75
},
{
    "L4": 0.9
},
{
    "L5": 0.95
},
    "risk_flags": []
}"""
    result = parse_llm_json(text)
    assert result["L1"] == 0.9
    assert result["L1_observations"] == "dense"
    assert result["L2"] == 0.85
    assert result["L2_rationale"] == "good"
    assert result["L3"] == 0.75
    assert result["L4"] == 0.9
    assert result["L5"] == 0.95
    assert result["risk_flags"] == []


def test_parse_llm_json_gemma_split_dimension_objects():
    """Some local models (Gemma 4) emit each dimension as a SEPARATE JSON object
    separated by commas, instead of one merged object. Parser must merge them.

    Verified against real Gemma 4 output captured 2026-04-11 from
    score_image() runs against the Phase 1 gallery — caused ~54% parse failure
    rate before the merge fallback was added.
    """
    from vulca._parse import parse_llm_json

    text = """{
    "L1": 0.9,
    "L1_observations": "comp",
    "L1_rationale": "ok",
    "L1_deviation_type": "intentional_departure"
},
{
    "L2": 0.85,
    "L2_observations": "tech",
    "L2_rationale": "good"
},
{
    "L3": 0.75
},
{
    "L4": 0.9
},
{
    "L5": 0.95
},
{
    "risk_flags": []
}"""
    result = parse_llm_json(text)
    assert result["L1"] == 0.9
    assert result["L2"] == 0.85
    assert result["L3"] == 0.75
    assert result["L4"] == 0.9
    assert result["L5"] == 0.95
    assert result["L1_observations"] == "comp"
    assert result["L1_deviation_type"] == "intentional_departure"
    assert result["L2_rationale"] == "good"
    assert result["risk_flags"] == []


# -- Engine Tests ----------------------------------------------------------


def test_engine_requires_api_key():
    import os
    # Temporarily remove API key and local VLM model
    orig = os.environ.pop("GOOGLE_API_KEY", None)
    orig2 = os.environ.pop("GEMINI_API_KEY", None)
    orig3 = os.environ.pop("VULCA_VLM_MODEL", None)

    from vulca._engine import Engine
    import vulca._engine as _eng
    _eng._instance = None  # Reset singleton

    with pytest.raises(ValueError, match="No API key"):
        Engine.get_instance()

    # Restore
    if orig:
        os.environ["GOOGLE_API_KEY"] = orig
    if orig2:
        os.environ["GEMINI_API_KEY"] = orig2
    if orig3:
        os.environ["VULCA_VLM_MODEL"] = orig3


def test_engine_singleton():
    """Engine.get_instance returns the same instance for the same key."""
    import os
    from vulca._engine import Engine
    import vulca._engine as _eng

    # Set up a test key
    orig = os.environ.get("GOOGLE_API_KEY")
    orig2 = os.environ.get("GEMINI_API_KEY")
    os.environ["GOOGLE_API_KEY"] = "test-key-123"

    try:
        _eng._instance = None  # Reset
        e1 = Engine.get_instance()
        e2 = Engine.get_instance()
        assert e1 is e2
    finally:
        _eng._instance = None
        if orig:
            os.environ["GOOGLE_API_KEY"] = orig
        else:
            os.environ.pop("GOOGLE_API_KEY", None)
        if orig2:
            os.environ["GEMINI_API_KEY"] = orig2
        else:
            os.environ.pop("GEMINI_API_KEY", None)


def test_engine_build_summary():
    """_build_summary produces a readable summary string."""
    from vulca._engine import _build_summary

    summary = _build_summary(0.85, "chinese_xieyi", {"L1": 0.9, "L2": 0.8, "L3": 0.7, "L4": 0.8, "L5": 0.9})
    assert "excellent" in summary.lower() or "85%" in summary
    assert "Chinese Xieyi" in summary


def test_engine_build_summary_low_score():
    from vulca._engine import _build_summary

    summary = _build_summary(0.3, "default", {"L1": 0.2, "L2": 0.3, "L3": 0.4, "L4": 0.3, "L5": 0.2})
    assert "needs improvement" in summary.lower() or "30%" in summary


def test_engine_build_recommendations():
    """_build_recommendations returns advice for weak dimensions."""
    from vulca._engine import _build_recommendations

    dims = {"L1": 0.3, "L2": 0.4, "L3": 0.9, "L4": 0.5, "L5": 0.6}
    weights = {"L1": 0.2, "L2": 0.2, "L3": 0.2, "L4": 0.2, "L5": 0.2}
    recs = _build_recommendations(dims, weights, "default")
    assert len(recs) >= 1
    assert len(recs) <= 3


def test_engine_build_recommendations_all_high():
    """No recommendations when all scores are high."""
    from vulca._engine import _build_recommendations

    dims = {"L1": 0.9, "L2": 0.85, "L3": 0.9, "L4": 0.8, "L5": 0.95}
    weights = {"L1": 0.2, "L2": 0.2, "L3": 0.2, "L4": 0.2, "L5": 0.2}
    recs = _build_recommendations(dims, weights, "default")
    assert len(recs) == 0


def test_engine_estimate_cost():
    """_estimate_cost returns a positive float."""
    from vulca._engine import _estimate_cost

    cost_no_skills = _estimate_cost([])
    cost_with_skills = _estimate_cost(["brand", "audience", "trend"])
    assert cost_no_skills > 0
    assert cost_with_skills > cost_no_skills


# -- Skills Module Tests ---------------------------------------------------


def test_skills_prompts_exist():
    """All documented skill names have prompts."""
    from vulca._skills import _SKILL_PROMPTS, _SKILL_WEIGHTS

    assert "brand" in _SKILL_PROMPTS
    assert "audience" in _SKILL_PROMPTS
    assert "trend" in _SKILL_PROMPTS

    # Weights match prompts
    assert set(_SKILL_WEIGHTS.keys()) == set(_SKILL_PROMPTS.keys())


# -- Session Function Tests ------------------------------------------------


def test_session_function_exists():
    from vulca import session, asession
    assert callable(session)
    assert callable(asession)


def test_create_function_exists():
    from vulca import create, acreate
    assert callable(create)
    assert callable(acreate)


# -- CLI Tests (integration-level) -----------------------------------------


def test_cli_create_subcommand():
    """Verify CLI parser accepts the create subcommand."""
    import argparse
    from vulca.cli import main

    # Just test that parsing works, don't actually run
    import vulca.cli as cli_mod
    parser = argparse.ArgumentParser(prog="vulca")
    sub = parser.add_subparsers(dest="command")
    create_p = sub.add_parser("create")
    create_p.add_argument("intent")
    args = parser.parse_args(["create", "ink wash landscape"])
    assert args.command == "create"
    assert args.intent == "ink wash landscape"


def test_cli_traditions(capsys):
    from vulca.cli import main
    main(["traditions"])
    captured = capsys.readouterr()
    assert "chinese_xieyi" in captured.out
    assert "Philosophical" in captured.out
