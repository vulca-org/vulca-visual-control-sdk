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
        assert "Cost: $" not in out

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
        assert "Cost: $" in out
