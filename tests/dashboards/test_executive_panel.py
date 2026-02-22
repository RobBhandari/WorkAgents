"""
Tests for execution/dashboards/executive_panel.py

Covers:
- generate_executive_panel() with no data (mocked empty loaders) — returns HTML with no-data state
- generate_executive_panel() with synthetic RiskScore objects — HTML contains product names
- _calculate_summary() with empty list → has_data: False in result
- _calculate_summary() with 3 RiskScore objects → correct org_risk_score, critical_count, high_count
- framework_css and framework_js present in rendered HTML
- KPI cards present in rendered output
- Summary cards have correct values
- _build_context() includes required framework keys
- _load_risk_scores() gracefully handles missing directory
- _load_forecasts_summary() gracefully handles missing file
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from execution.dashboards.executive_panel import (
    _build_context,
    _build_portfolio_trend_chart,
    _calculate_summary,
    _load_forecasts_summary,
    _load_risk_scores,
    _risk_status_class,
    generate_executive_panel,
    main,
)
from execution.domain.intelligence import RiskScore, RiskScoreComponent

# ---------------------------------------------------------------------------
# Fixtures — synthetic RiskScore objects (no real project names)
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_risk_scores_low() -> list[RiskScore]:
    """3 projects all scoring below 40 → level = 'low'."""
    return [
        RiskScore(project="Product_A", total=20.0, components=[]),
        RiskScore(project="Product_B", total=30.0, components=[]),
        RiskScore(project="Product_C", total=35.0, components=[]),
    ]


@pytest.fixture
def sample_risk_scores_mixed() -> list[RiskScore]:
    """Mixed risk levels: 1 critical (>80), 1 high (>60), 1 medium (>40)."""
    return [
        RiskScore(project="Product_A", total=85.0, components=[]),  # critical
        RiskScore(project="Product_B", total=65.0, components=[]),  # high
        RiskScore(project="Product_C", total=45.0, components=[]),  # medium
    ]


@pytest.fixture
def sample_risk_score_single() -> list[RiskScore]:
    """Single project with known risk score."""
    return [RiskScore(project="Product_A", total=50.0, components=[])]


# ---------------------------------------------------------------------------
# TestCalculateSummary
# ---------------------------------------------------------------------------


class TestCalculateSummary:
    def test_empty_list_has_data_false(self) -> None:
        result = _calculate_summary([], {})
        assert result["has_data"] is False

    def test_empty_list_returns_zero_org_risk(self) -> None:
        result = _calculate_summary([], {})
        assert result["org_risk_score"] == 0.0

    def test_empty_list_returns_zero_counts(self) -> None:
        result = _calculate_summary([], {})
        assert result["critical_count"] == 0
        assert result["high_count"] == 0
        assert result["total_count"] == 0

    def test_empty_list_top_risks_is_empty(self) -> None:
        result = _calculate_summary([], {})
        assert result["top_risks"] == []

    def test_empty_list_trend_is_stable(self) -> None:
        result = _calculate_summary([], {})
        assert result["org_trend"] == "stable"

    def test_has_data_true_when_scores_present(self, sample_risk_scores_low: list[RiskScore]) -> None:
        result = _calculate_summary(sample_risk_scores_low, {})
        assert result["has_data"] is True

    def test_org_risk_score_is_correct_average(self, sample_risk_scores_low: list[RiskScore]) -> None:
        result = _calculate_summary(sample_risk_scores_low, {})
        expected = round((20.0 + 30.0 + 35.0) / 3, 1)
        assert result["org_risk_score"] == expected

    def test_critical_count_correct(self, sample_risk_scores_mixed: list[RiskScore]) -> None:
        result = _calculate_summary(sample_risk_scores_mixed, {})
        assert result["critical_count"] == 1  # Product_A at 85.0

    def test_high_count_correct(self, sample_risk_scores_mixed: list[RiskScore]) -> None:
        result = _calculate_summary(sample_risk_scores_mixed, {})
        assert result["high_count"] == 1  # Product_B at 65.0

    def test_total_count_correct(self, sample_risk_scores_mixed: list[RiskScore]) -> None:
        result = _calculate_summary(sample_risk_scores_mixed, {})
        assert result["total_count"] == 3

    def test_top_risks_limited_to_3(self, sample_risk_scores_low: list[RiskScore]) -> None:
        # Add extra scores to exceed 3
        many_scores = [RiskScore(project=f"Product_{i}", total=float(i * 10), components=[]) for i in range(7)]
        result = _calculate_summary(many_scores, {})
        assert len(result["top_risks"]) <= 3

    def test_top_risks_sorted_descending(self, sample_risk_scores_mixed: list[RiskScore]) -> None:
        result = _calculate_summary(sample_risk_scores_mixed, {})
        top = result["top_risks"]
        scores = [rs.total for rs in top]
        assert scores == sorted(scores, reverse=True)

    def test_org_trend_from_forecast_summary(self, sample_risk_scores_low: list[RiskScore]) -> None:
        forecast_summary = {"org_trend": "improving"}
        result = _calculate_summary(sample_risk_scores_low, forecast_summary)
        assert result["org_trend"] == "improving"

    def test_org_trend_defaults_stable_for_unknown_value(self, sample_risk_scores_low: list[RiskScore]) -> None:
        forecast_summary = {"org_trend": "something_invalid"}
        result = _calculate_summary(sample_risk_scores_low, forecast_summary)
        assert result["org_trend"] == "stable"

    def test_org_trend_stable_when_no_forecast_summary(self, sample_risk_scores_low: list[RiskScore]) -> None:
        result = _calculate_summary(sample_risk_scores_low, {})
        assert result["org_trend"] == "stable"


# ---------------------------------------------------------------------------
# TestRiskStatusClass
# ---------------------------------------------------------------------------


class TestRiskStatusClass:
    def test_score_above_70_returns_action(self) -> None:
        assert _risk_status_class(75.0) == "status-action"

    def test_score_above_40_returns_caution(self) -> None:
        assert _risk_status_class(55.0) == "status-caution"

    def test_score_at_or_below_40_returns_good(self) -> None:
        assert _risk_status_class(40.0) == "status-good"
        assert _risk_status_class(20.0) == "status-good"

    def test_boundary_exactly_70_returns_caution(self) -> None:
        # score=70 is not > 70, so returns caution
        assert _risk_status_class(70.0) == "status-caution"

    def test_boundary_exactly_40_returns_good(self) -> None:
        # score=40 is not > 40, so returns good
        assert _risk_status_class(40.0) == "status-good"


# ---------------------------------------------------------------------------
# TestLoadRiskScores
# ---------------------------------------------------------------------------


class TestLoadRiskScores:
    def test_missing_directory_returns_empty(self, tmp_path: Path) -> None:
        missing_dir = tmp_path / "no_such_dir"
        result = _load_risk_scores(base_dir=missing_dir)
        assert result == []

    def test_loads_risk_scores_from_json_file(self, tmp_path: Path) -> None:
        data = [
            {"project": "Product_A", "total": 55.0},
            {"project": "Product_B", "total": 30.0},
        ]
        json_file = tmp_path / "risk_scores_2026-01-15.json"
        json_file.write_text(json.dumps(data), encoding="utf-8")

        result = _load_risk_scores(base_dir=tmp_path)

        assert len(result) == 2
        projects = {rs.project for rs in result}
        assert "Product_A" in projects
        assert "Product_B" in projects

    def test_loads_from_nested_scores_key(self, tmp_path: Path) -> None:
        data = {
            "scores": [
                {"project": "Product_A", "total": 55.0},
            ]
        }
        json_file = tmp_path / "risk_scores_2026-01-15.json"
        json_file.write_text(json.dumps(data), encoding="utf-8")

        result = _load_risk_scores(base_dir=tmp_path)
        assert len(result) == 1
        assert result[0].project == "Product_A"

    def test_malformed_json_is_skipped_gracefully(self, tmp_path: Path) -> None:
        json_file = tmp_path / "risk_scores_bad.json"
        json_file.write_text("NOT JSON AT ALL", encoding="utf-8")

        # Should not raise
        result = _load_risk_scores(base_dir=tmp_path)
        assert isinstance(result, list)

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        result = _load_risk_scores(base_dir=tmp_path)
        assert result == []


# ---------------------------------------------------------------------------
# TestLoadForecastsSummary
# ---------------------------------------------------------------------------


class TestLoadForecastsSummary:
    def test_missing_directory_returns_empty_dict(self, tmp_path: Path) -> None:
        missing = tmp_path / "no_dir"
        result = _load_forecasts_summary(base_dir=missing)
        assert result == {}

    def test_missing_file_returns_empty_dict(self, tmp_path: Path) -> None:
        result = _load_forecasts_summary(base_dir=tmp_path)
        assert result == {}

    def test_loads_summary_from_json(self, tmp_path: Path) -> None:
        data = {"org_trend": "improving", "total_projects": 5}
        summary_file = tmp_path / "forecast_summary.json"
        summary_file.write_text(json.dumps(data), encoding="utf-8")

        result = _load_forecasts_summary(base_dir=tmp_path)
        assert result["org_trend"] == "improving"
        assert result["total_projects"] == 5

    def test_malformed_json_returns_empty_dict(self, tmp_path: Path) -> None:
        summary_file = tmp_path / "forecast_summary.json"
        summary_file.write_text("INVALID JSON", encoding="utf-8")

        result = _load_forecasts_summary(base_dir=tmp_path)
        assert result == {}


# ---------------------------------------------------------------------------
# TestBuildContext
# ---------------------------------------------------------------------------


class TestBuildContext:
    def _make_summary(self, has_data: bool = True) -> dict:
        if not has_data:
            return {
                "org_risk_score": 0.0,
                "critical_count": 0,
                "high_count": 0,
                "total_count": 0,
                "top_risks": [],
                "org_trend": "stable",
                "has_data": False,
            }
        return {
            "org_risk_score": 55.0,
            "critical_count": 1,
            "high_count": 2,
            "total_count": 5,
            "top_risks": [RiskScore(project="Product_A", total=85.0, components=[])],
            "org_trend": "improving",
            "has_data": True,
        }

    def test_framework_css_present(self) -> None:
        summary = self._make_summary()
        context = _build_context(summary, "")
        assert "framework_css" in context
        assert context["framework_css"] != ""

    def test_framework_js_present(self) -> None:
        summary = self._make_summary()
        context = _build_context(summary, "")
        assert "framework_js" in context
        assert context["framework_js"] != ""

    def test_kpi_cards_present(self) -> None:
        summary = self._make_summary()
        context = _build_context(summary, "")
        assert "kpi_cards" in context
        assert len(context["kpi_cards"]) == 4

    def test_kpi_cards_have_label_and_value(self) -> None:
        summary = self._make_summary()
        context = _build_context(summary, "")
        for card in context["kpi_cards"]:
            assert "label" in card
            assert "value" in card
            assert "status_class" in card

    def test_has_data_propagated(self) -> None:
        summary = self._make_summary(has_data=False)
        context = _build_context(summary, "")
        assert context["has_data"] is False

    def test_org_risk_score_in_context(self) -> None:
        summary = self._make_summary()
        context = _build_context(summary, "")
        assert context["org_risk_score"] == 55.0

    def test_trend_class_improving(self) -> None:
        summary = self._make_summary()
        context = _build_context(summary, "")
        assert context["trend_class"] == "trend-improving"

    def test_trend_class_worsening(self) -> None:
        summary = self._make_summary()
        summary["org_trend"] = "worsening"
        context = _build_context(summary, "")
        assert context["trend_class"] == "trend-worsening"

    def test_trend_arrow_improving(self) -> None:
        summary = self._make_summary()
        context = _build_context(summary, "")
        assert context["trend_arrow"] == "↓"

    def test_risk_gauge_html_empty_when_no_data(self) -> None:
        summary = self._make_summary(has_data=False)
        context = _build_context(summary, "")
        assert context["risk_gauge_html"] == ""

    def test_risk_gauge_html_non_empty_when_data(self) -> None:
        summary = self._make_summary(has_data=True)
        context = _build_context(summary, "")
        assert context["risk_gauge_html"] != ""


# ---------------------------------------------------------------------------
# TestGenerateExecutivePanel (integration — mocked I/O)
# ---------------------------------------------------------------------------


class TestGenerateExecutivePanel:
    def test_returns_html_string(self) -> None:
        with (
            patch("execution.dashboards.executive_panel._load_risk_scores", return_value=[]),
            patch("execution.dashboards.executive_panel._load_forecasts_summary", return_value={}),
            patch("execution.dashboards.executive_panel._build_portfolio_trend_chart", return_value=""),
        ):
            html = generate_executive_panel()

        assert isinstance(html, str)
        assert len(html) > 100

    def test_no_data_html_contains_doctype(self) -> None:
        with (
            patch("execution.dashboards.executive_panel._load_risk_scores", return_value=[]),
            patch("execution.dashboards.executive_panel._load_forecasts_summary", return_value={}),
            patch("execution.dashboards.executive_panel._build_portfolio_trend_chart", return_value=""),
        ):
            html = generate_executive_panel()

        assert "<!DOCTYPE html>" in html or "<html" in html

    def test_html_contains_framework_css_when_data_present(self, sample_risk_scores_mixed: list[RiskScore]) -> None:
        with (
            patch(
                "execution.dashboards.executive_panel._load_risk_scores",
                return_value=sample_risk_scores_mixed,
            ),
            patch("execution.dashboards.executive_panel._load_forecasts_summary", return_value={}),
            patch("execution.dashboards.executive_panel._build_portfolio_trend_chart", return_value=""),
        ):
            html = generate_executive_panel()

        # The framework CSS should be embedded in the rendered HTML
        assert "<style" in html

    def test_html_contains_product_names_when_data_present(self, sample_risk_scores_mixed: list[RiskScore]) -> None:
        with (
            patch(
                "execution.dashboards.executive_panel._load_risk_scores",
                return_value=sample_risk_scores_mixed,
            ),
            patch("execution.dashboards.executive_panel._load_forecasts_summary", return_value={}),
            patch("execution.dashboards.executive_panel._build_portfolio_trend_chart", return_value=""),
        ):
            html = generate_executive_panel()

        # At least one product should appear in the HTML
        assert "Product_A" in html or "Product_B" in html or "Product_C" in html

    def test_kpi_labels_appear_in_html(self, sample_risk_scores_mixed: list[RiskScore]) -> None:
        with (
            patch(
                "execution.dashboards.executive_panel._load_risk_scores",
                return_value=sample_risk_scores_mixed,
            ),
            patch("execution.dashboards.executive_panel._load_forecasts_summary", return_value={}),
            patch("execution.dashboards.executive_panel._build_portfolio_trend_chart", return_value=""),
        ):
            html = generate_executive_panel()

        assert "Org Risk Score" in html
        assert "Critical Projects" in html

    def test_writes_file_when_output_dir_provided(self, tmp_path: Path) -> None:
        with (
            patch("execution.dashboards.executive_panel._load_risk_scores", return_value=[]),
            patch("execution.dashboards.executive_panel._load_forecasts_summary", return_value={}),
            patch("execution.dashboards.executive_panel._build_portfolio_trend_chart", return_value=""),
        ):
            generate_executive_panel(output_dir=tmp_path)

        written = tmp_path / "executive_panel.html"
        assert written.exists()
        assert written.stat().st_size > 100

    def test_no_file_written_when_no_output_dir(self, tmp_path: Path) -> None:
        with (
            patch("execution.dashboards.executive_panel._load_risk_scores", return_value=[]),
            patch("execution.dashboards.executive_panel._load_forecasts_summary", return_value={}),
            patch("execution.dashboards.executive_panel._build_portfolio_trend_chart", return_value=""),
        ):
            generate_executive_panel(output_dir=None)

        # Ensure no file was written in tmp_path (not the default location)
        assert not (tmp_path / "executive_panel.html").exists()

    def test_generation_date_present_in_html(self) -> None:
        with (
            patch("execution.dashboards.executive_panel._load_risk_scores", return_value=[]),
            patch("execution.dashboards.executive_panel._load_forecasts_summary", return_value={}),
            patch("execution.dashboards.executive_panel._build_portfolio_trend_chart", return_value=""),
        ):
            html = generate_executive_panel()

        assert "Generated:" in html or "2026" in html


# ---------------------------------------------------------------------------
# TestBuildPortfolioTrendChart
# ---------------------------------------------------------------------------


class TestBuildPortfolioTrendChart:
    def test_missing_file_returns_empty_string(self, tmp_path: Path) -> None:
        result = _build_portfolio_trend_chart(feature_dir=tmp_path)
        assert result == ""

    def test_valid_entries_returns_html_string(self, tmp_path: Path) -> None:
        data = {
            "entries": [
                {"date": "2026-01-01", "avg_risk": 45.0},
                {"date": "2026-01-08", "avg_risk": 50.0},
                {"date": "2026-01-15", "avg_risk": 42.0},
            ]
        }
        history_file = tmp_path / "portfolio_risk_history.json"
        history_file.write_text(json.dumps(data), encoding="utf-8")

        result = _build_portfolio_trend_chart(feature_dir=tmp_path)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_entries_list_returns_empty_string(self, tmp_path: Path) -> None:
        data: dict[str, list] = {"entries": []}
        history_file = tmp_path / "portfolio_risk_history.json"
        history_file.write_text(json.dumps(data), encoding="utf-8")

        result = _build_portfolio_trend_chart(feature_dir=tmp_path)
        assert result == ""

    def test_malformed_json_returns_empty_string(self, tmp_path: Path) -> None:
        history_file = tmp_path / "portfolio_risk_history.json"
        history_file.write_text("NOT VALID JSON", encoding="utf-8")

        result = _build_portfolio_trend_chart(feature_dir=tmp_path)
        assert result == ""

    def test_entries_without_date_filtered_out(self, tmp_path: Path) -> None:
        """Entries with no 'date' key produce empty label, which is filtered."""
        data = {
            "entries": [
                {"avg_risk": 45.0},  # no date key → label "" → filtered out
            ]
        }
        history_file = tmp_path / "portfolio_risk_history.json"
        history_file.write_text(json.dumps(data), encoding="utf-8")

        result = _build_portfolio_trend_chart(feature_dir=tmp_path)
        assert result == ""

    def test_integer_risk_values_coerced_to_float(self, tmp_path: Path) -> None:
        """avg_risk as int or string number should be coerced without error."""
        data = {
            "entries": [
                {"date": "2026-01-01", "avg_risk": 45},  # int
                {"date": "2026-01-08", "avg_risk": "50.5"},  # string number
            ]
        }
        history_file = tmp_path / "portfolio_risk_history.json"
        history_file.write_text(json.dumps(data), encoding="utf-8")

        # Should not raise — float() coercion handles both
        result = _build_portfolio_trend_chart(feature_dir=tmp_path)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# TestMain
# ---------------------------------------------------------------------------


class TestMain:
    def test_main_calls_generate_executive_panel(self, tmp_path: Path) -> None:
        fake_html = "<html><body>test</body></html>"
        with (
            patch(
                "execution.dashboards.executive_panel.generate_executive_panel",
                return_value=fake_html,
            ) as mock_gen,
            patch(
                "execution.dashboards.executive_panel.OUTPUT_PATH",
                tmp_path / "executive_panel.html",
            ),
        ):
            main()

        mock_gen.assert_called_once()

    def test_main_logs_when_output_file_exists(self, tmp_path: Path) -> None:
        output_path = tmp_path / "executive_panel.html"
        output_path.write_text("<html></html>", encoding="utf-8")

        with (
            patch(
                "execution.dashboards.executive_panel.generate_executive_panel",
                return_value="<html></html>",
            ),
            patch(
                "execution.dashboards.executive_panel.OUTPUT_PATH",
                output_path,
            ),
        ):
            # Should complete without raising
            main()

    def test_main_logs_when_output_file_not_on_disk(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "not_written.html"

        with (
            patch(
                "execution.dashboards.executive_panel.generate_executive_panel",
                return_value="<html>content</html>",
            ),
            patch(
                "execution.dashboards.executive_panel.OUTPUT_PATH",
                nonexistent,
            ),
        ):
            # OUTPUT_PATH does not exist — takes the else branch
            main()

    def test_main_raises_oserror_on_failure(self) -> None:
        with patch(
            "execution.dashboards.executive_panel.generate_executive_panel",
            side_effect=OSError("disk full"),
        ):
            with pytest.raises(OSError, match="disk full"):
                main()
