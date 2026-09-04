"""Mock evaluations must announce themselves.

A mock run produces a full-looking score sheet. If nothing on that sheet says the
scores are synthetic, a report built from it is indistinguishable from a report
built from real model calls, and a misconfigured key or a stray --mock flag turns
into a plausible-looking fabrication. These tests fix the disclosure contract:
the flag travels with the result, and every renderer shows it.
"""

from __future__ import annotations

import asyncio
import io
from contextlib import redirect_stdout

import pytest

from vulca.types import EvalResult


MARKER = "MOCK"


def _mock_eval() -> EvalResult:
    """A mock evaluation through the public API, as a user would obtain one."""
    from vulca.evaluate import evaluate

    return evaluate("nonexistent.png", tradition="chinese_xieyi", mock=True)


def _bare_result(**over) -> EvalResult:
    """A minimally-populated real result, for the negative case."""
    base = dict(
        score=0.82,
        tradition="chinese_xieyi",
        dimensions={f"L{i}": 0.8 for i in range(1, 6)},
        rationales={f"L{i}": "" for i in range(1, 6)},
        summary="Overall excellent.",
        risk_level="low",
        risk_flags=[],
        recommendations=[],
    )
    base.update(over)
    return EvalResult(**base)


class TestResultCarriesMockFlag:
    def test_evalresult_has_mock_field_defaulting_false(self):
        assert "mock" in EvalResult.__dataclass_fields__
        assert _bare_result().mock is False

    def test_mock_engine_marks_its_result(self):
        assert _mock_eval().mock is True

    def test_mock_run_reports_no_cost(self):
        # A run that made no API call must not report a price for it.
        assert _mock_eval().cost_usd == 0.0


class TestRenderersDiscloseMock:
    def _render(self, fn, result) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(result)
        return buf.getvalue()

    def test_strict_output_marks_mock(self):
        from vulca.cli import _print_strict_result

        out = self._render(_print_strict_result, _mock_eval())
        assert MARKER in out

    def test_reference_output_marks_mock(self):
        from vulca.cli import _print_reference_result

        result = _mock_eval()
        result.eval_mode = "reference"
        out = self._render(_print_reference_result, result)
        assert MARKER in out

    def test_real_output_is_not_marked(self):
        # Guard against a marker that is always on, which would be just as useless.
        from vulca.cli import _print_strict_result

        real = _bare_result(cost_usd=0.0011)
        assert MARKER not in self._render(_print_strict_result, real)


class TestFusionDisclosesMock:
    """Fusion compares several traditions at once; one mock result taints the table."""

    def test_fusion_output_marks_mock(self):
        import io
        from contextlib import redirect_stdout
        from vulca.cli import _print_fusion_result

        results = [("chinese_xieyi", _mock_eval()), ("western_academic", _mock_eval())]
        buf = io.StringIO()
        with redirect_stdout(buf):
            _print_fusion_result(results)
        out = buf.getvalue()
        assert MARKER in out
        assert "cost: $" not in out.lower()

    def test_fusion_real_output_is_not_marked(self):
        import io
        from contextlib import redirect_stdout
        from vulca.cli import _print_fusion_result

        results = [("chinese_xieyi", _bare_result()), ("western_academic", _bare_result())]
        buf = io.StringIO()
        with redirect_stdout(buf):
            _print_fusion_result(results)
        out = buf.getvalue()
        assert MARKER not in out
        assert "cost: $" in out.lower()


# -- Create path -----------------------------------------------------------
#
# `create` selects a provider by name rather than a boolean, and "mock" is one
# of the choices. A synthetic image with a printed price is the same failure as
# a synthetic score sheet with one.


def _bare_create(**over):
    from vulca.types import CreateResult

    base = dict(session_id="s1", mode="create", tradition="chinese_xieyi")
    base.update(over)
    return CreateResult(**base)


class TestCreateCarriesProvenance:
    def test_createresult_has_mock_and_provider_fields(self):
        from vulca.types import CreateResult

        assert "mock" in CreateResult.__dataclass_fields__
        assert "provider" in CreateResult.__dataclass_fields__
        r = _bare_create()
        assert r.mock is False
        assert r.provider == ""


class TestCreateRendererDisclosesMock:
    def _render(self, result) -> str:
        import io
        from contextlib import redirect_stdout
        from vulca.cli import _print_create_result

        buf = io.StringIO()
        with redirect_stdout(buf):
            _print_create_result(result)
        return buf.getvalue()

    def test_mock_provider_is_disclosed(self):
        out = self._render(_bare_create(mock=True, provider="mock", cost_usd=0.0))
        assert MARKER in out
        assert "cost: $" not in out.lower()

    def test_real_provider_is_not_marked(self):
        out = self._render(_bare_create(provider="nb2", cost_usd=0.0042))
        assert MARKER not in out
        assert "cost: $" in out.lower()


# -- Failed scoring --------------------------------------------------------
#
# `_vlm.score_image` catches every exception and returns a complete result with
# all five dimensions at 0.0. Nothing on that result says the run failed, so a
# crash is delivered as a confident verdict of zero -- worse than a mock score,
# because it happens without anyone asking for it.


def _failed_vlm_payload(msg: str = "boom") -> dict:
    """The shape `_vlm.score_image` returns from its except branch."""
    out: dict = {"error": msg, "_extra_keys": []}
    for level in ("L1", "L2", "L3", "L4", "L5"):
        out[level] = 0.0
        out[f"{level}_rationale"] = f"Scoring failed: {msg}" if level == "L1" else ""
        out[f"{level}_suggestion"] = ""
        out[f"{level}_deviation_type"] = "traditional"
        out[f"{level}_observations"] = ""
        out[f"{level}_reference_technique"] = ""
    return out


class TestFailedRunIsMarked:
    def test_evalresult_has_failed_and_error_fields(self):
        assert "failed" in EvalResult.__dataclass_fields__
        assert "error" in EvalResult.__dataclass_fields__
        r = _bare_result()
        assert r.failed is False
        assert r.error == ""

    def test_engine_marks_a_failed_scoring_run(self, monkeypatch):
        import vulca._engine as eng

        async def _boom(**kwargs):
            return _failed_vlm_payload("'NoneType' object has no attribute 'strip'")

        monkeypatch.setattr(eng, "score_image", _boom)
        monkeypatch.setattr(eng, "load_image_base64", lambda *a, **k: _immediate(("", "image/png")))

        engine = eng.Engine(api_key="k")
        result = asyncio.run(engine.run("x.png", tradition="chinese_xieyi"))
        assert result.failed is True
        assert "NoneType" in result.error
        assert result.score == 0.0


def _immediate(value):
    async def _coro():
        return value
    return _coro()


class TestRenderersDiscloseFailure:
    def _render(self, result) -> str:
        import io
        from contextlib import redirect_stdout
        from vulca.cli import _print_strict_result

        buf = io.StringIO()
        with redirect_stdout(buf):
            _print_strict_result(result)
        return buf.getvalue()

    def test_failed_output_is_marked(self):
        out = self._render(_bare_result(score=0.0, failed=True, error="boom"))
        assert "FAILED" in out
        assert "boom" in out

    def test_successful_output_is_not_marked(self):
        assert "FAILED" not in self._render(_bare_result())


class TestExitCode:
    def test_failed_evaluation_exits_nonzero(self):
        from vulca.cli import _exit_code_for

        assert _exit_code_for(_bare_result(failed=True, error="boom")) != 0
        assert _exit_code_for(_bare_result()) == 0


# -- Cost provenance -------------------------------------------------------
#
# `_estimate_cost` returns 0.001 + 0.0001 + 0.0002 * len(skills): a constant.
# It printed the same $0.0011 for a mock run and for a real one against the
# live API. Labelling a constant as "Cost" is the same failure as labelling a
# mock score as a measurement.


class TestCostProvenance:
    def test_result_records_whether_cost_was_measured(self):
        assert "cost_is_estimate" in EvalResult.__dataclass_fields__
        # Anything not explicitly measured is an estimate.
        assert _bare_result().cost_is_estimate is True

    def test_estimated_cost_is_labelled_as_such(self):
        import io
        from contextlib import redirect_stdout
        from vulca.cli import _print_strict_result

        buf = io.StringIO()
        with redirect_stdout(buf):
            _print_strict_result(_bare_result(cost_usd=0.0011, cost_is_estimate=True))
        out = buf.getvalue()
        assert "Est. cost" in out
        assert "Cost: $" not in out

    def test_measured_cost_is_not_called_an_estimate(self):
        import io
        from contextlib import redirect_stdout
        from vulca.cli import _print_strict_result

        buf = io.StringIO()
        with redirect_stdout(buf):
            _print_strict_result(_bare_result(cost_usd=0.0042, cost_is_estimate=False))
        out = buf.getvalue()
        assert "Cost: $" in out
        assert "Est. cost" not in out

    def test_engine_prefers_a_measured_cost_over_the_estimate(self, monkeypatch):
        import vulca._engine as eng

        payload = {f"L{i}": 0.8 for i in range(1, 6)}
        payload["_extra_keys"] = []
        payload["_cost_usd"] = 0.0037

        async def _scored(**kwargs):
            return payload

        monkeypatch.setattr(eng, "score_image", _scored)
        monkeypatch.setattr(eng, "load_image_base64", lambda *a, **k: _immediate(("", "image/png")))

        result = asyncio.run(eng.Engine(api_key="k").run("x.png", tradition="chinese_xieyi"))
        assert result.cost_usd == 0.0037
        assert result.cost_is_estimate is False
