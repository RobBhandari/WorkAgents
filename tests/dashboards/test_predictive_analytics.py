"""
Tests for execution/dashboards/predictive_analytics.py

Covers:
- _load_scenario_results() with missing dir → returns []
- _calculate_summary() with empty list → has_data False
- _calculate_summary() with 3 ScenarioResult objects → correct scenario_count, best_scenario_name
- _build_context() → contains framework_css, framework_js
- generate_predictive_analytics() with mocked loaders → returns HTML string
- generate_predictive_analytics() with output_dir → writes file
- _build_scenario_comparison_chart() with empty list → returns ""
- _build_scenario_comparison_chart() with scenarios → returns non-empty string
- main() integration behaviour (mocked generate)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from execution.dashboards.predictive_analytics import (
    _build_context,
    _build_scenario_comparison_chart,
    _calculate_summary,
    _load_scenario_results,
    generate_predictive_analytics,
    main,
)
from execution.domain.intelligence import ScenarioPoint, ScenarioResult

_TS = datetime(2025, 10, 6)

# ---------------------------------------------------------------------------
# Fixtures — synthetic ScenarioResult objects (no real project names)
# ---------------------------------------------------------------------------


@pytest.fixture
def single_scenario() -> ScenarioResult:
    """One BAU scenario with a single forecast point."""
    return ScenarioResult(
        timestamp=_TS,
        scenario_name="BAU",
        metric="quality",
        horizon_weeks=13,
        n_simulations=1000,
        forecast=[ScenarioPoint(week=13, p10=200.0, p50=250.0, p90=300.0)],
        probability_of_improvement=0.35,
        description="Business as usual baseline scenario.",
    )


@pytest.fixture
def sample_scenarios() -> list[ScenarioResult]:
    """Three scenarios covering a range of improvement probabilities."""
    return [
        ScenarioResult(
            timestamp=_TS,
            scenario_name="BAU",
            metric="quality",
            horizon_weeks=13,
            n_simulations=1000,
            forecast=[ScenarioPoint(week=13, p10=200.0, p50=250.0, p90=300.0)],
            probability_of_improvement=0.35,
            description="Business as usual.",
        ),
        ScenarioResult(
            timestamp=_TS,
            scenario_name="Accelerated",
            metric="quality",
            horizon_weeks=13,
            n_simulations=1000,
            forecast=[ScenarioPoint(week=13, p10=150.0, p50=180.0, p90=220.0)],
            probability_of_improvement=0.75,
            description="Increased investment scenario.",
        ),
        ScenarioResult(
            timestamp=_TS,
            scenario_name="Sprint",
            metric="quality",
            horizon_weeks=13,
            n_simulations=1000,
            forecast=[ScenarioPoint(week=13, p10=100.0, p50=130.0, p90=170.0)],
            probability_of_improvement=0.60,
            description="Sprint surge scenario.",
        ),
    ]


@pytest.fixture
def empty_summary() -> dict:
    return {
        "has_data": False,
        "scenario_count": 0,
        "best_scenario_name": "—",
        "best_probability": 0.0,
        "scenarios": [],
    }


@pytest.fixture
def full_summary(sample_scenarios: list[ScenarioResult]) -> dict:
    return _calculate_summary(sample_scenarios)


# ---------------------------------------------------------------------------
# TestLoadScenarioResults
# ---------------------------------------------------------------------------


class TestLoadScenarioResults:
    def test_missing_directory_returns_empty_list(self, tmp_path: Path) -> None:
        missing = tmp_path / "no_such_dir"
        result = _load_scenario_results(base_dir=missing)
        assert result == []

    def test_empty_directory_returns_empty_list(self, tmp_path: Path) -> None:
        result = _load_scenario_results(base_dir=tmp_path)
        assert result == []

    def test_loads_scenarios_from_list_json(self, tmp_path: Path) -> None:
        data = [
            {
                "scenario_name": "BAU",
                "metric": "quality",
                "horizon_weeks": 13,
                "n_simulations": 500,
                "forecast": [{"week": 13, "p10": 200.0, "p50": 250.0, "p90": 300.0}],
                "probability_of_improvement": 0.4,
                "description": "",
            }
        ]
        f = tmp_path / "scenario_results_2026-01-01.json"
        f.write_text(json.dumps(data), encoding="utf-8")

        result = _load_scenario_results(base_dir=tmp_path)
        assert len(result) == 1
        assert result[0].scenario_name == "BAU"

    def test_loads_scenarios_from_nested_scenarios_key(self, tmp_path: Path) -> None:
        data = {
            "scenarios": [
                {
                    "scenario_name": "Sprint",
                    "metric": "bugs",
                    "horizon_weeks": 4,
                    "n_simulations": 200,
                    "forecast": [{"week": 4, "p10": 10.0, "p50": 15.0, "p90": 20.0}],
                    "probability_of_improvement": 0.55,
                    "description": "Sprint scenario",
                }
            ]
        }
        f = tmp_path / "scenario_results_alt.json"
        f.write_text(json.dumps(data), encoding="utf-8")

        result = _load_scenario_results(base_dir=tmp_path)
        assert len(result) == 1
        assert result[0].scenario_name == "Sprint"

    def test_malformed_json_is_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "scenario_results_bad.json"
        f.write_text("NOT VALID JSON", encoding="utf-8")

        result = _load_scenario_results(base_dir=tmp_path)
        assert isinstance(result, list)

    def test_only_glob_pattern_files_loaded(self, tmp_path: Path) -> None:
        """Files not matching scenario_results_*.json should be ignored."""
        other = tmp_path / "risk_scores_2026.json"
        other.write_text(json.dumps([{"project": "A", "total": 50.0}]), encoding="utf-8")

        result = _load_scenario_results(base_dir=tmp_path)
        assert result == []


# ---------------------------------------------------------------------------
# TestCalculateSummary
# ---------------------------------------------------------------------------


class TestCalculateSummary:
    def test_empty_list_has_data_false(self) -> None:
        result = _calculate_summary([])
        assert result["has_data"] is False

    def test_empty_list_scenario_count_zero(self) -> None:
        result = _calculate_summary([])
        assert result["scenario_count"] == 0

    def test_empty_list_best_scenario_name_placeholder(self) -> None:
        result = _calculate_summary([])
        assert result["best_scenario_name"] == "—"

    def test_empty_list_best_probability_zero(self) -> None:
        result = _calculate_summary([])
        assert result["best_probability"] == 0.0

    def test_empty_list_scenarios_is_empty_list(self) -> None:
        result = _calculate_summary([])
        assert result["scenarios"] == []

    def test_has_data_true_when_scenarios_present(self, sample_scenarios: list[ScenarioResult]) -> None:
        result = _calculate_summary(sample_scenarios)
        assert result["has_data"] is True

    def test_scenario_count_correct(self, sample_scenarios: list[ScenarioResult]) -> None:
        result = _calculate_summary(sample_scenarios)
        assert result["scenario_count"] == 3

    def test_best_scenario_name_is_highest_probability(self, sample_scenarios: list[ScenarioResult]) -> None:
        # Accelerated has 0.75 — highest
        result = _calculate_summary(sample_scenarios)
        assert result["best_scenario_name"] == "Accelerated"

    def test_best_probability_correct(self, sample_scenarios: list[ScenarioResult]) -> None:
        result = _calculate_summary(sample_scenarios)
        assert result["best_probability"] == 0.75

    def test_scenarios_list_preserved(self, sample_scenarios: list[ScenarioResult]) -> None:
        result = _calculate_summary(sample_scenarios)
        assert len(result["scenarios"]) == 3

    def test_single_scenario(self, single_scenario: ScenarioResult) -> None:
        result = _calculate_summary([single_scenario])
        assert result["has_data"] is True
        assert result["scenario_count"] == 1
        assert result["best_scenario_name"] == "BAU"
        assert result["best_probability"] == 0.35


# ---------------------------------------------------------------------------
# TestBuildScenarioComparisonChart
# ---------------------------------------------------------------------------


class TestBuildScenarioComparisonChart:
    def test_empty_list_returns_empty_string(self) -> None:
        result = _build_scenario_comparison_chart([])
        assert result == ""

    def test_scenario_without_forecast_skipped(self) -> None:
        s = ScenarioResult(
            timestamp=_TS,
            scenario_name="Empty",
            metric="quality",
            horizon_weeks=13,
            n_simulations=100,
            forecast=[],  # no forecast points
            probability_of_improvement=0.5,
        )
        result = _build_scenario_comparison_chart([s])
        # No data to chart → empty string
        assert result == ""

    def test_single_scenario_returns_html(self, single_scenario: ScenarioResult) -> None:
        result = _build_scenario_comparison_chart([single_scenario])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_multiple_scenarios_return_html(self, sample_scenarios: list[ScenarioResult]) -> None:
        result = _build_scenario_comparison_chart(sample_scenarios)
        assert isinstance(result, str)
        assert len(result) > 100

    def test_html_contains_plotly_div(self, sample_scenarios: list[ScenarioResult]) -> None:
        result = _build_scenario_comparison_chart(sample_scenarios)
        assert "<div" in result

    def test_html_contains_scenario_name(self, sample_scenarios: list[ScenarioResult]) -> None:
        result = _build_scenario_comparison_chart(sample_scenarios)
        assert "BAU" in result or "Accelerated" in result

    def test_integer_values_coerced_to_float(self) -> None:
        """Ensure int p-values do not raise TypeError."""
        s = ScenarioResult(
            timestamp=_TS,
            scenario_name="Test",
            metric="bugs",
            horizon_weeks=4,
            n_simulations=100,
            forecast=[ScenarioPoint(week=4, p10=10, p50=15, p90=20)],  # type: ignore[arg-type]
            probability_of_improvement=0.6,
        )
        # Should not raise
        result = _build_scenario_comparison_chart([s])
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# TestBuildContext
# ---------------------------------------------------------------------------


class TestBuildContext:
    def test_framework_css_present(self, empty_summary: dict) -> None:
        context = _build_context(empty_summary, "")
        assert "framework_css" in context
        assert context["framework_css"] != ""

    def test_framework_js_present(self, empty_summary: dict) -> None:
        context = _build_context(empty_summary, "")
        assert "framework_js" in context
        assert context["framework_js"] != ""

    def test_has_data_propagated_false(self, empty_summary: dict) -> None:
        context = _build_context(empty_summary, "")
        assert context["has_data"] is False

    def test_has_data_propagated_true(self, full_summary: dict) -> None:
        context = _build_context(full_summary, "")
        assert context["has_data"] is True

    def test_scenario_count_in_context(self, full_summary: dict) -> None:
        context = _build_context(full_summary, "")
        assert context["scenario_count"] == 3

    def test_best_scenario_name_in_context(self, full_summary: dict) -> None:
        context = _build_context(full_summary, "")
        assert context["best_scenario_name"] == "Accelerated"

    def test_chart_html_in_context(self, empty_summary: dict) -> None:
        context = _build_context(empty_summary, "<div>chart</div>")
        assert context["scenario_chart_html"] == "<div>chart</div>"

    def test_generated_at_present_in_context(self, empty_summary: dict) -> None:
        context = _build_context(empty_summary, "")
        assert "generated_at" in context
        assert "2026" in context["generated_at"] or len(context["generated_at"]) > 0

    def test_scenarios_list_in_context(self, full_summary: dict) -> None:
        context = _build_context(full_summary, "")
        assert "scenarios" in context
        assert len(context["scenarios"]) == 3


# ---------------------------------------------------------------------------
# TestGeneratePredictiveAnalytics (integration — mocked I/O)
# ---------------------------------------------------------------------------


class TestGeneratePredictiveAnalytics:
    def test_returns_html_string_with_no_data(self) -> None:
        with patch(
            "execution.dashboards.predictive_analytics._load_scenario_results",
            return_value=[],
        ):
            html = generate_predictive_analytics()

        assert isinstance(html, str)
        assert len(html) > 100

    def test_html_is_valid_document(self) -> None:
        with patch(
            "execution.dashboards.predictive_analytics._load_scenario_results",
            return_value=[],
        ):
            html = generate_predictive_analytics()

        assert "<!DOCTYPE html>" in html or "<html" in html

    def test_html_contains_framework_css(self, sample_scenarios: list[ScenarioResult]) -> None:
        with patch(
            "execution.dashboards.predictive_analytics._load_scenario_results",
            return_value=sample_scenarios,
        ):
            html = generate_predictive_analytics()

        assert "<style" in html

    def test_html_contains_scenario_names_when_data_present(self, sample_scenarios: list[ScenarioResult]) -> None:
        with patch(
            "execution.dashboards.predictive_analytics._load_scenario_results",
            return_value=sample_scenarios,
        ):
            html = generate_predictive_analytics()

        assert "BAU" in html or "Accelerated" in html or "Sprint" in html

    def test_html_contains_kpi_labels_when_data_present(self, sample_scenarios: list[ScenarioResult]) -> None:
        with patch(
            "execution.dashboards.predictive_analytics._load_scenario_results",
            return_value=sample_scenarios,
        ):
            html = generate_predictive_analytics()

        assert "Scenarios Loaded" in html or "Best Scenario" in html

    def test_writes_file_when_output_dir_provided(self, tmp_path: Path) -> None:
        with patch(
            "execution.dashboards.predictive_analytics._load_scenario_results",
            return_value=[],
        ):
            generate_predictive_analytics(output_dir=tmp_path)

        written = tmp_path / "predictive_analytics.html"
        assert written.exists()
        assert written.stat().st_size > 100

    def test_no_file_written_when_no_output_dir(self, tmp_path: Path) -> None:
        with patch(
            "execution.dashboards.predictive_analytics._load_scenario_results",
            return_value=[],
        ):
            generate_predictive_analytics(output_dir=None)

        # Nothing should appear in tmp_path
        assert not (tmp_path / "predictive_analytics.html").exists()

    def test_no_data_message_in_html_when_empty(self) -> None:
        with patch(
            "execution.dashboards.predictive_analytics._load_scenario_results",
            return_value=[],
        ):
            html = generate_predictive_analytics()

        assert "Not Yet Available" in html or "not" in html.lower()


# ---------------------------------------------------------------------------
# TestMain
# ---------------------------------------------------------------------------


class TestMain:
    def test_main_calls_generate(self, tmp_path: Path) -> None:
        fake_html = "<html><body>test</body></html>"
        with (
            patch(
                "execution.dashboards.predictive_analytics.generate_predictive_analytics",
                return_value=fake_html,
            ) as mock_gen,
            patch(
                "execution.dashboards.predictive_analytics.OUTPUT_PATH",
                tmp_path / "predictive_analytics.html",
            ),
        ):
            main()

        mock_gen.assert_called_once()

    def test_main_logs_when_output_file_exists(self, tmp_path: Path) -> None:
        output_path = tmp_path / "predictive_analytics.html"
        output_path.write_text("<html></html>", encoding="utf-8")

        with (
            patch(
                "execution.dashboards.predictive_analytics.generate_predictive_analytics",
                return_value="<html></html>",
            ),
            patch(
                "execution.dashboards.predictive_analytics.OUTPUT_PATH",
                output_path,
            ),
        ):
            main()  # Should not raise

    def test_main_logs_when_output_file_not_on_disk(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "not_written.html"

        with (
            patch(
                "execution.dashboards.predictive_analytics.generate_predictive_analytics",
                return_value="<html>content</html>",
            ),
            patch(
                "execution.dashboards.predictive_analytics.OUTPUT_PATH",
                nonexistent,
            ),
        ):
            main()  # Takes the else branch — should not raise

    def test_main_raises_oserror_on_failure(self) -> None:
        with patch(
            "execution.dashboards.predictive_analytics.generate_predictive_analytics",
            side_effect=OSError("disk full"),
        ):
            with pytest.raises(OSError, match="disk full"):
                main()
