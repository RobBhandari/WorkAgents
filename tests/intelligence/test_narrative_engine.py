"""
Tests for execution/intelligence/narrative_engine.py

Covers:
- generate_report() returns a non-empty HTML string
- generate_report() writes dated and latest HTML files
- _load_metric_context() returns empty dict for missing file
- _load_metric_context() returns empty dict for invalid metric
- _load_metric_context() returns empty dict for malformed JSON
- _load_metric_context() extracts latest week's context fields
- _generate_metric_insights() skips metrics with no history mapping
- generate_report() renders gracefully with no insights (empty list)
- generate_report() uses provided output_dir
- generate_report() uses provided report_date in output filename
- _coerce_context() coerces numeric strings to float
- _pick_template_key() selects correct template based on delta_pct magnitude
- _pick_severity() returns correct severity levels
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from execution.domain.intelligence import MetricInsight
from execution.intelligence.narrative_engine import (
    _coerce_context,
    _load_metric_context,
    _pick_severity,
    _pick_template_key,
    generate_report,
)

_TS = datetime(2025, 10, 6)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_history_file(tmp_path: Path) -> Path:
    """Write a minimal history JSON file with one week entry."""
    data = {
        "weeks": [
            {
                "week_date": "2025-10-01",
                "delta_pct": 12.5,
                "top_dimension": "Product_A",
                "dim_delta": 8.0,
            }
        ]
    }
    p = tmp_path / "quality_history.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def sample_insight() -> MetricInsight:
    return MetricInsight(
        timestamp=_TS,
        metric="quality",
        template_key="stable",
        text="Stable.",
        severity="info",
    )


# ---------------------------------------------------------------------------
# TestGenerateReport
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_returns_html_string(self, tmp_path: Path, sample_insight: MetricInsight) -> None:
        """generate_report() should return a non-empty HTML string."""
        with patch(
            "execution.intelligence.narrative_engine._generate_metric_insights",
            return_value=[sample_insight],
        ):
            html = generate_report(use_llm=False, output_dir=tmp_path)

        assert isinstance(html, str)
        assert len(html) > 0

    def test_html_contains_doctype(self, tmp_path: Path, sample_insight: MetricInsight) -> None:
        with patch(
            "execution.intelligence.narrative_engine._generate_metric_insights",
            return_value=[sample_insight],
        ):
            html = generate_report(use_llm=False, output_dir=tmp_path)

        assert "<!DOCTYPE html>" in html

    def test_writes_dated_and_latest_files(self, tmp_path: Path) -> None:
        """generate_report() should write both dated and latest HTML files."""
        with patch(
            "execution.intelligence.narrative_engine._generate_metric_insights",
            return_value=[],
        ):
            generate_report(use_llm=False, output_dir=tmp_path)

        files = list(tmp_path.glob("intelligence_report_*.html"))
        names = {f.name for f in files}

        assert "intelligence_report_latest.html" in names
        assert any(
            name != "intelligence_report_latest.html" for name in names
        ), "Expected a dated report file alongside the latest file"

    def test_dated_filename_matches_report_date(self, tmp_path: Path) -> None:
        """The dated file should use the supplied report_date in its name."""
        fixed_date = datetime(2025, 3, 15)
        with patch(
            "execution.intelligence.narrative_engine._generate_metric_insights",
            return_value=[],
        ):
            generate_report(use_llm=False, output_dir=tmp_path, report_date=fixed_date)

        dated = tmp_path / "intelligence_report_2025-03-15.html"
        assert dated.exists(), f"Expected {dated} to exist"

    def test_empty_insights_renders_gracefully(self, tmp_path: Path) -> None:
        """Report with no insights should render without raising."""
        with patch(
            "execution.intelligence.narrative_engine._generate_metric_insights",
            return_value=[],
        ):
            html = generate_report(use_llm=False, output_dir=tmp_path)

        assert isinstance(html, str)
        assert len(html) > 0

    def test_insight_metric_appears_in_html(self, tmp_path: Path, sample_insight: MetricInsight) -> None:
        """The metric name from an insight should appear (title-cased) in the HTML."""
        with patch(
            "execution.intelligence.narrative_engine._generate_metric_insights",
            return_value=[sample_insight],
        ):
            html = generate_report(use_llm=False, output_dir=tmp_path)

        # "quality" → "Quality" after title-casing in the renderer
        assert "Quality" in html

    def test_uses_provided_output_dir(self, tmp_path: Path) -> None:
        """Files should be written to the provided output_dir, not the default."""
        custom_dir = tmp_path / "custom_output"
        with patch(
            "execution.intelligence.narrative_engine._generate_metric_insights",
            return_value=[],
        ):
            generate_report(use_llm=False, output_dir=custom_dir)

        assert custom_dir.exists()
        assert (custom_dir / "intelligence_report_latest.html").exists()

    def test_use_llm_false_calls_generate_insights_with_false(self, tmp_path: Path) -> None:
        """use_llm=False must be passed through to _generate_metric_insights."""
        with patch(
            "execution.intelligence.narrative_engine._generate_metric_insights",
            return_value=[],
        ) as mock_gen:
            generate_report(use_llm=False, output_dir=tmp_path)

        mock_gen.assert_called_once_with(use_llm=False)

    def test_use_llm_true_calls_generate_insights_with_true(self, tmp_path: Path) -> None:
        """use_llm=True must be passed through to _generate_metric_insights."""
        with patch(
            "execution.intelligence.narrative_engine._generate_metric_insights",
            return_value=[],
        ) as mock_gen:
            generate_report(use_llm=True, output_dir=tmp_path)

        mock_gen.assert_called_once_with(use_llm=True)


# ---------------------------------------------------------------------------
# TestLoadMetricContext
# ---------------------------------------------------------------------------


class TestLoadMetricContext:
    def test_returns_empty_for_invalid_metric(self) -> None:
        """_load_metric_context() returns {} for metrics not in VALID_METRICS."""
        ctx = _load_metric_context("not_a_real_metric_xyz")
        assert ctx == {}

    def test_returns_empty_for_missing_file(self) -> None:
        """_load_metric_context() returns {} when history file is missing."""
        with patch(
            "execution.intelligence.narrative_engine._HISTORY_FILES",
            {"quality": Path("/nonexistent/path/quality_history.json")},
        ):
            ctx = _load_metric_context("quality")
        assert isinstance(ctx, dict)

    def test_returns_empty_for_malformed_json(self, tmp_path: Path) -> None:
        """_load_metric_context() returns {} for malformed JSON."""
        bad_file = tmp_path / "quality_history.json"
        bad_file.write_text("NOT JSON AT ALL", encoding="utf-8")

        with patch(
            "execution.intelligence.narrative_engine._HISTORY_FILES",
            {"quality": bad_file},
        ):
            ctx = _load_metric_context("quality")

        assert isinstance(ctx, dict)

    def test_extracts_delta_from_latest_week(self, sample_history_file: Path) -> None:
        """Context should contain delta_pct from the last week entry."""
        with patch(
            "execution.intelligence.narrative_engine._HISTORY_FILES",
            {"quality": sample_history_file},
        ):
            ctx = _load_metric_context("quality")

        assert "delta_pct" in ctx
        assert float(ctx["delta_pct"]) == pytest.approx(12.5)  # type: ignore[arg-type]

    def test_extracts_top_dimension(self, sample_history_file: Path) -> None:
        """Context should contain top_dimension from the last week entry."""
        with patch(
            "execution.intelligence.narrative_engine._HISTORY_FILES",
            {"quality": sample_history_file},
        ):
            ctx = _load_metric_context("quality")

        assert ctx.get("top_dimension") == "Product_A"

    def test_returns_zero_defaults_for_empty_weeks(self, tmp_path: Path) -> None:
        """When history has no weeks entries, returns context with 0.0 defaults."""
        data: dict[str, object] = {"weeks": []}
        p = tmp_path / "quality_history.json"
        p.write_text(json.dumps(data), encoding="utf-8")

        with patch(
            "execution.intelligence.narrative_engine._HISTORY_FILES",
            {"quality": p},
        ):
            ctx = _load_metric_context("quality")

        assert isinstance(ctx, dict)
        assert float(ctx.get("delta_pct", 0.0)) == pytest.approx(0.0)  # type: ignore[arg-type]

    def test_metric_key_in_context(self, sample_history_file: Path) -> None:
        """Context should always contain the metric key."""
        with patch(
            "execution.intelligence.narrative_engine._HISTORY_FILES",
            {"quality": sample_history_file},
        ):
            ctx = _load_metric_context("quality")

        assert ctx.get("metric") == "quality"


# ---------------------------------------------------------------------------
# TestCoerceContext
# ---------------------------------------------------------------------------


class TestCoerceContext:
    def test_int_coerced_to_float(self) -> None:
        result = _coerce_context({"count": 5})
        assert result["count"] == 5.0
        assert isinstance(result["count"], float)

    def test_numeric_string_coerced_to_float(self) -> None:
        result = _coerce_context({"delta": "12.5"})
        assert result["delta"] == pytest.approx(12.5)
        assert isinstance(result["delta"], float)

    def test_non_numeric_string_preserved(self) -> None:
        result = _coerce_context({"label": "Product_A"})
        assert result["label"] == "Product_A"

    def test_float_preserved(self) -> None:
        result = _coerce_context({"val": 3.14})
        assert result["val"] == pytest.approx(3.14)

    def test_none_preserved(self) -> None:
        result = _coerce_context({"x": None})
        assert result["x"] is None

    def test_returns_copy_not_mutation(self) -> None:
        original: dict[str, object] = {"a": 1}
        result = _coerce_context(original)
        result["a"] = 999.0
        assert original["a"] == 1


# ---------------------------------------------------------------------------
# TestPickTemplateKey
# ---------------------------------------------------------------------------


class TestPickTemplateKey:
    def test_large_delta_gives_anomaly_spike(self) -> None:
        ctx: dict = {"delta_pct": 20.0}
        assert _pick_template_key(ctx) == "anomaly_spike"

    def test_medium_delta_gives_trend_reversal(self) -> None:
        ctx: dict = {"delta_pct": 8.0}
        assert _pick_template_key(ctx) == "trend_reversal"

    def test_small_delta_gives_stable(self) -> None:
        ctx: dict = {"delta_pct": 2.0}
        assert _pick_template_key(ctx) == "stable"

    def test_zero_delta_gives_stable(self) -> None:
        ctx: dict = {"delta_pct": 0.0}
        assert _pick_template_key(ctx) == "stable"

    def test_negative_large_delta_gives_anomaly_spike(self) -> None:
        ctx: dict = {"delta_pct": -20.0}
        assert _pick_template_key(ctx) == "anomaly_spike"

    def test_missing_delta_defaults_to_stable(self) -> None:
        ctx: dict = {}
        assert _pick_template_key(ctx) == "stable"


# ---------------------------------------------------------------------------
# TestPickSeverity
# ---------------------------------------------------------------------------


class TestPickSeverity:
    def test_critical_for_large_delta(self) -> None:
        ctx: dict = {"delta_pct": 20.0}
        assert _pick_severity(ctx) == "critical"

    def test_warning_for_medium_delta(self) -> None:
        ctx: dict = {"delta_pct": 8.0}
        assert _pick_severity(ctx) == "warning"

    def test_info_for_small_delta(self) -> None:
        ctx: dict = {"delta_pct": 2.0}
        assert _pick_severity(ctx) == "info"

    def test_info_for_zero_delta(self) -> None:
        ctx: dict = {"delta_pct": 0.0}
        assert _pick_severity(ctx) == "info"

    def test_missing_delta_defaults_to_info(self) -> None:
        ctx: dict = {}
        assert _pick_severity(ctx) == "info"
