"""
Tests for execution/dashboards/model_performance_dashboard.py

Covers:
- _load_data() returns empty list and "Unknown" on missing file
- _load_data() parses valid JSON correctly
- _load_data() handles malformed JSON gracefully
- _calculate_summary() with all-healthy models → portfolio_status "Good"
- _calculate_summary() with mixed models → portfolio_status "Caution"
- _calculate_summary() with all-degraded models → portfolio_status "Action Needed"
- _calculate_summary() with empty list → has_data False, "No Data"
- _calculate_summary() computes avg_mape and avg_classification_accuracy correctly
- _build_context() includes required framework_css and framework_js keys
- _build_context() includes summary_cards and model_rows
- _build_context() filters out unknown model names
- _build_context() passes valid models through to model_rows
- generate_model_performance_dashboard() returns HTML string containing <html
- generate_model_performance_dashboard() writes file when output_dir provided
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from execution.dashboards.model_performance_dashboard import (
    _build_context,
    _calculate_summary,
    _load_data,
    generate_model_performance_dashboard,
)

# ---------------------------------------------------------------------------
# Sample model records matching the expected JSON schema
# ---------------------------------------------------------------------------

_SAMPLE_MODELS: list[dict] = [
    {
        "model_name": "forecast_quality",
        "metric": "quality",
        "algorithm": "linregress",
        "mape": 0.08,
        "classification_accuracy": None,
        "drift_score": 0.01,
        "last_trained": "2026-02-20T00:00:00Z",
        "status": "healthy",
    },
    {
        "model_name": "health_classifier",
        "metric": "composite",
        "algorithm": "random_forest",
        "mape": None,
        "classification_accuracy": 0.87,
        "drift_score": 0.05,
        "last_trained": "2026-02-20T00:00:00Z",
        "status": "degraded",
    },
]

_ALL_HEALTHY_MODELS: list[dict] = [
    {
        "model_name": "forecast_quality",
        "metric": "quality",
        "algorithm": "linregress",
        "mape": 0.08,
        "classification_accuracy": None,
        "drift_score": 0.01,
        "last_trained": "2026-02-20T00:00:00Z",
        "status": "healthy",
    },
    {
        "model_name": "forecast_security",
        "metric": "security",
        "algorithm": "linregress",
        "mape": 0.10,
        "classification_accuracy": None,
        "drift_score": 0.02,
        "last_trained": "2026-02-20T00:00:00Z",
        "status": "healthy",
    },
]

_ALL_DEGRADED_MODELS: list[dict] = [
    {
        "model_name": "forecast_quality",
        "metric": "quality",
        "algorithm": "linregress",
        "mape": 0.30,
        "classification_accuracy": None,
        "drift_score": 0.20,
        "last_trained": "2026-01-01T00:00:00Z",
        "status": "degraded",
    },
    {
        "model_name": "forecast_deployment",
        "metric": "deployment",
        "algorithm": "linregress",
        "mape": 0.40,
        "classification_accuracy": None,
        "drift_score": 0.25,
        "last_trained": "2026-01-01T00:00:00Z",
        "status": "degraded",
    },
]


# ---------------------------------------------------------------------------
# TestLoadData
# ---------------------------------------------------------------------------


class TestLoadData:
    def test_missing_file_returns_empty_models(self) -> None:
        models, last_updated = _load_data(Path("/nonexistent/model_performance.json"))
        assert models == []

    def test_missing_file_returns_unknown_last_updated(self) -> None:
        _, last_updated = _load_data(Path("/nonexistent/model_performance.json"))
        assert last_updated == "Unknown"

    def test_parses_valid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "model_performance.json"
        p.write_text(
            json.dumps({"last_updated": "2026-02-22T06:00:00Z", "models": _SAMPLE_MODELS}),
            encoding="utf-8",
        )
        models, last_updated = _load_data(p)
        assert len(models) == 2
        assert last_updated == "2026-02-22T06:00:00Z"

    def test_parses_model_names(self, tmp_path: Path) -> None:
        p = tmp_path / "model_performance.json"
        p.write_text(
            json.dumps({"last_updated": "2026-02-22", "models": _SAMPLE_MODELS}),
            encoding="utf-8",
        )
        models, _ = _load_data(p)
        names = {m["model_name"] for m in models}
        assert "forecast_quality" in names
        assert "health_classifier" in names

    def test_handles_malformed_json(self, tmp_path: Path) -> None:
        p = tmp_path / "model_performance.json"
        p.write_text("NOT VALID JSON", encoding="utf-8")
        models, last_updated = _load_data(p)
        assert models == []
        assert last_updated == "Unknown"

    def test_empty_models_list(self, tmp_path: Path) -> None:
        p = tmp_path / "model_performance.json"
        p.write_text(json.dumps({"last_updated": None, "models": []}), encoding="utf-8")
        models, last_updated = _load_data(p)
        assert models == []
        assert last_updated == "Unknown"

    def test_null_last_updated_returns_unknown(self, tmp_path: Path) -> None:
        p = tmp_path / "model_performance.json"
        p.write_text(json.dumps({"last_updated": None, "models": _SAMPLE_MODELS}), encoding="utf-8")
        _, last_updated = _load_data(p)
        assert last_updated == "Unknown"


# ---------------------------------------------------------------------------
# TestCalculateSummary
# ---------------------------------------------------------------------------


class TestCalculateSummary:
    def test_empty_list_has_data_false(self) -> None:
        summary = _calculate_summary([])
        assert summary["has_data"] is False

    def test_empty_list_portfolio_status_no_data(self) -> None:
        summary = _calculate_summary([])
        assert summary["portfolio_status"] == "No Data"

    def test_empty_list_totals_zero(self) -> None:
        summary = _calculate_summary([])
        assert summary["total_models"] == 0
        assert summary["healthy_count"] == 0
        assert summary["degraded_count"] == 0

    def test_empty_list_avg_values_none(self) -> None:
        summary = _calculate_summary([])
        assert summary["avg_mape"] is None
        assert summary["avg_classification_accuracy"] is None

    def test_all_healthy_returns_good(self) -> None:
        summary = _calculate_summary(_ALL_HEALTHY_MODELS)
        assert summary["portfolio_status"] == "Good"
        assert summary["healthy_count"] == 2
        assert summary["degraded_count"] == 0

    def test_mixed_returns_caution(self) -> None:
        summary = _calculate_summary(_SAMPLE_MODELS)
        assert summary["portfolio_status"] == "Caution"

    def test_all_degraded_returns_action_needed(self) -> None:
        summary = _calculate_summary(_ALL_DEGRADED_MODELS)
        assert summary["portfolio_status"] == "Action Needed"

    def test_avg_mape_calculated_correctly(self) -> None:
        # Both models have mape
        models = [
            {**_SAMPLE_MODELS[0], "mape": 0.10},
            {**_SAMPLE_MODELS[0], "mape": 0.20, "model_name": "forecast_security"},
        ]
        summary = _calculate_summary(models)
        assert summary["avg_mape"] == pytest.approx(0.15)

    def test_avg_mape_none_when_no_mape_values(self) -> None:
        models = [
            {
                "model_name": "health_classifier",
                "status": "healthy",
                "mape": None,
                "classification_accuracy": 0.9,
            }
        ]
        summary = _calculate_summary(models)
        assert summary["avg_mape"] is None

    def test_avg_classification_accuracy_calculated(self) -> None:
        models = [
            {
                "model_name": "health_classifier",
                "status": "healthy",
                "mape": None,
                "classification_accuracy": 0.80,
            },
            {
                "model_name": "clustering",
                "status": "healthy",
                "mape": None,
                "classification_accuracy": 0.90,
            },
        ]
        summary = _calculate_summary(models)
        assert summary["avg_classification_accuracy"] == pytest.approx(0.85)

    def test_has_data_true_when_models_present(self) -> None:
        summary = _calculate_summary(_SAMPLE_MODELS)
        assert summary["has_data"] is True

    def test_total_models_count(self) -> None:
        summary = _calculate_summary(_SAMPLE_MODELS)
        assert summary["total_models"] == 2


# ---------------------------------------------------------------------------
# TestBuildContext
# ---------------------------------------------------------------------------


class TestBuildContext:
    def test_includes_framework_css(self) -> None:
        summary = _calculate_summary(_SAMPLE_MODELS)
        context = _build_context(summary, _SAMPLE_MODELS, "2026-02-22")
        assert "framework_css" in context
        assert context["framework_css"] != ""

    def test_includes_framework_js(self) -> None:
        summary = _calculate_summary(_SAMPLE_MODELS)
        context = _build_context(summary, _SAMPLE_MODELS, "2026-02-22")
        assert "framework_js" in context
        assert context["framework_js"] != ""

    def test_includes_summary_cards(self) -> None:
        summary = _calculate_summary(_SAMPLE_MODELS)
        context = _build_context(summary, _SAMPLE_MODELS, "2026-02-22")
        assert "summary_cards" in context
        assert len(context["summary_cards"]) == 5

    def test_summary_cards_have_required_keys(self) -> None:
        summary = _calculate_summary(_SAMPLE_MODELS)
        context = _build_context(summary, _SAMPLE_MODELS, "2026-02-22")
        for card in context["summary_cards"]:
            assert "title" in card
            assert "value" in card
            assert "status_class" in card

    def test_includes_model_rows(self) -> None:
        summary = _calculate_summary(_SAMPLE_MODELS)
        context = _build_context(summary, _SAMPLE_MODELS, "2026-02-22")
        assert "model_rows" in context

    def test_filters_unknown_model_names(self) -> None:
        """Unknown model names must be excluded from model_rows."""
        models = [
            {"model_name": "unknown_model_xyz", "status": "healthy"},
        ]
        summary = _calculate_summary(models)
        context = _build_context(summary, models, "2026-02-22")
        assert len(context["model_rows"]) == 0

    def test_valid_models_appear_in_rows(self) -> None:
        summary = _calculate_summary(_SAMPLE_MODELS)
        context = _build_context(summary, _SAMPLE_MODELS, "2026-02-22")
        row_names = {row["model_name"] for row in context["model_rows"]}
        assert "forecast_quality" in row_names
        assert "health_classifier" in row_names

    def test_model_row_has_required_keys(self) -> None:
        summary = _calculate_summary(_SAMPLE_MODELS)
        context = _build_context(summary, _SAMPLE_MODELS, "2026-02-22")
        for row in context["model_rows"]:
            assert "model_name" in row
            assert "status" in row
            assert "status_class" in row
            assert "mape_display" in row
            assert "accuracy_display" in row
            assert "drift_score" in row
            assert "last_trained" in row

    def test_healthy_model_gets_status_good_class(self) -> None:
        models = [_SAMPLE_MODELS[0]]  # forecast_quality — healthy
        summary = _calculate_summary(models)
        context = _build_context(summary, models, "2026-02-22")
        assert context["model_rows"][0]["status_class"] == "status-good"

    def test_degraded_model_gets_status_action_class(self) -> None:
        models = [_SAMPLE_MODELS[1]]  # health_classifier — degraded
        summary = _calculate_summary(models)
        context = _build_context(summary, models, "2026-02-22")
        assert context["model_rows"][0]["status_class"] == "status-action"

    def test_none_mape_displays_dash(self) -> None:
        models = [_SAMPLE_MODELS[1]]  # health_classifier — mape is None
        summary = _calculate_summary(models)
        context = _build_context(summary, models, "2026-02-22")
        assert context["model_rows"][0]["mape_display"] == "—"

    def test_none_accuracy_displays_dash(self) -> None:
        models = [_SAMPLE_MODELS[0]]  # forecast_quality — classification_accuracy is None
        summary = _calculate_summary(models)
        context = _build_context(summary, models, "2026-02-22")
        assert context["model_rows"][0]["accuracy_display"] == "—"

    def test_has_data_propagated(self) -> None:
        summary = _calculate_summary([])
        context = _build_context(summary, [], "2026-02-22")
        assert context["has_data"] is False

    def test_portfolio_status_propagated(self) -> None:
        summary = _calculate_summary(_SAMPLE_MODELS)
        context = _build_context(summary, _SAMPLE_MODELS, "2026-02-22")
        assert context["portfolio_status"] == "Caution"

    def test_breadcrumbs_present(self) -> None:
        summary = _calculate_summary([])
        context = _build_context(summary, [], "2026-02-22")
        assert "breadcrumbs" in context
        assert len(context["breadcrumbs"]) == 2


# ---------------------------------------------------------------------------
# TestGenerateModelPerformanceDashboard (integration — mocked I/O)
# ---------------------------------------------------------------------------


class TestGenerateModelPerformanceDashboard:
    def test_returns_html_string(self, tmp_path: Path) -> None:
        p = tmp_path / "model_performance.json"
        p.write_text(
            json.dumps({"last_updated": "2026-02-22", "models": _SAMPLE_MODELS}),
            encoding="utf-8",
        )
        with patch("execution.dashboards.model_performance_dashboard._MODEL_PERFORMANCE_PATH", p):
            html = generate_model_performance_dashboard()

        assert isinstance(html, str)
        assert len(html) > 100

    def test_html_contains_html_tag(self, tmp_path: Path) -> None:
        p = tmp_path / "model_performance.json"
        p.write_text(
            json.dumps({"last_updated": "2026-02-22", "models": _SAMPLE_MODELS}),
            encoding="utf-8",
        )
        with patch("execution.dashboards.model_performance_dashboard._MODEL_PERFORMANCE_PATH", p):
            html = generate_model_performance_dashboard()

        assert "<html" in html.lower()

    def test_no_data_state_renders(self, tmp_path: Path) -> None:
        """Empty models list should render the no-data state without raising."""
        p = tmp_path / "model_performance.json"
        p.write_text(json.dumps({"last_updated": None, "models": []}), encoding="utf-8")
        with patch("execution.dashboards.model_performance_dashboard._MODEL_PERFORMANCE_PATH", p):
            html = generate_model_performance_dashboard()

        assert isinstance(html, str)
        assert len(html) > 100

    def test_writes_file_when_output_dir_provided(self, tmp_path: Path) -> None:
        src = tmp_path / "model_performance.json"
        src.write_text(
            json.dumps({"last_updated": "2026-02-22", "models": _SAMPLE_MODELS}),
            encoding="utf-8",
        )
        out_dir = tmp_path / "dashboards"
        with patch("execution.dashboards.model_performance_dashboard._MODEL_PERFORMANCE_PATH", src):
            generate_model_performance_dashboard(output_dir=out_dir)

        written = out_dir / "model_performance_dashboard.html"
        assert written.exists()
        assert written.stat().st_size > 100

    def test_no_file_written_without_output_dir(self, tmp_path: Path) -> None:
        p = tmp_path / "model_performance.json"
        p.write_text(json.dumps({"last_updated": "2026-02-22", "models": []}), encoding="utf-8")
        with patch("execution.dashboards.model_performance_dashboard._MODEL_PERFORMANCE_PATH", p):
            generate_model_performance_dashboard(output_dir=None)

        # No file should land in tmp_path root
        assert not (tmp_path / "model_performance_dashboard.html").exists()

    def test_model_names_appear_in_html(self, tmp_path: Path) -> None:
        p = tmp_path / "model_performance.json"
        p.write_text(
            json.dumps({"last_updated": "2026-02-22", "models": _SAMPLE_MODELS}),
            encoding="utf-8",
        )
        with patch("execution.dashboards.model_performance_dashboard._MODEL_PERFORMANCE_PATH", p):
            html = generate_model_performance_dashboard()

        assert "forecast_quality" in html
        assert "health_classifier" in html

    def test_missing_data_file_renders_gracefully(self, tmp_path: Path) -> None:
        """When model_performance.json is missing, dashboard renders the no-data state."""
        with patch(
            "execution.dashboards.model_performance_dashboard._MODEL_PERFORMANCE_PATH",
            tmp_path / "nonexistent.json",
        ):
            html = generate_model_performance_dashboard()

        assert isinstance(html, str)
        assert len(html) > 100
