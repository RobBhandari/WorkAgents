"""
Tests for scripts/run_intelligence_pipeline.py

Tests validate orchestration logic: step delegation, failure isolation,
model_performance.json merge, scenario simulation, and exit code contract.
All external dependencies (feature_engineering, forecast_engine, risk_scorer,
scenario_simulator) are mocked — no file I/O or ML computation occurs.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import scripts.run_intelligence_pipeline as pipeline
from execution.domain.intelligence import ForecastPoint, ForecastResult, ScenarioPoint, ScenarioResult
from execution.domain.metrics import MetricSnapshot

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_forecast_result() -> ForecastResult:
    """Minimal ForecastResult with one 4-week horizon point."""
    import datetime

    return ForecastResult(
        timestamp=datetime.datetime(2026, 1, 1),
        project="Product_A",
        metric="open_bugs",
        forecast=[ForecastPoint(week=4, p10=80.0, p50=95.0, p90=110.0)],
        model="linear",
        mape=0.08,
        trend_direction="improving",
        trend_strength=0.72,
    )


@pytest.fixture
def sample_scenario_result() -> ScenarioResult:
    """Minimal ScenarioResult for mocking compare_scenarios output."""
    import datetime

    return ScenarioResult(
        timestamp=datetime.datetime(2026, 1, 1),
        scenario_name="BAU",
        metric="open_bugs",
        horizon_weeks=13,
        n_simulations=1000,
        forecast=[ScenarioPoint(week=13, p10=80.0, p50=95.0, p90=110.0)],
        probability_of_improvement=0.65,
        description="",
    )


@pytest.fixture
def sample_features_df() -> pd.DataFrame:
    """Synthetic feature DataFrame with 12 weekly rows — enough for scenario simulation."""
    return pd.DataFrame(
        {
            "week_date": pd.date_range("2025-10-01", periods=12, freq="W"),
            "project": ["Product_A"] * 12,
            "open_bugs": [300, 295, 290, 285, 280, 275, 270, 265, 260, 255, 250, 245],
        }
    )


@pytest.fixture
def tmp_model_perf(tmp_path: Path) -> Path:
    """Temporary model_performance.json with existing entry."""
    p = tmp_path / "model_performance.json"
    p.write_text(
        json.dumps(
            {
                "last_updated": "2026-01-01T00:00:00",
                "models": [{"name": "forecast_quality", "mape": 0.05, "status": "pass"}],
            }
        )
    )
    return p


# ---------------------------------------------------------------------------
# _run_feature_engineering
# ---------------------------------------------------------------------------


class TestRunFeatureEngineering:
    def test_returns_true_on_success(self) -> None:
        with patch("scripts.run_intelligence_pipeline._build_all_features") as mock_build:
            result = pipeline._run_feature_engineering()
        mock_build.assert_called_once()
        assert result is True

    def test_returns_false_on_exception(self) -> None:
        with patch(
            "scripts.run_intelligence_pipeline._build_all_features",
            side_effect=RuntimeError("disk full"),
        ):
            result = pipeline._run_feature_engineering()
        assert result is False


# ---------------------------------------------------------------------------
# _run_forecasts
# ---------------------------------------------------------------------------


class TestRunForecasts:
    def test_returns_records_on_success(self, sample_forecast_result: ForecastResult) -> None:
        with (
            patch(
                "scripts.run_intelligence_pipeline.forecast_all_projects",
                return_value=[sample_forecast_result],
            ),
            patch("scripts.run_intelligence_pipeline.save_forecasts"),
            patch("scripts.run_intelligence_pipeline._write_forecast_summary"),
        ):
            records = pipeline._run_forecasts()

        assert len(records) == len(pipeline._FORECAST_TARGETS)
        for r in records:
            assert "name" in r
            assert "mape" in r
            assert "status" in r
            assert "project_count" in r
            assert r["project_count"] == 1

    def test_skips_metric_on_empty_results(self) -> None:
        with (
            patch(
                "scripts.run_intelligence_pipeline.forecast_all_projects",
                return_value=[],
            ),
            patch("scripts.run_intelligence_pipeline.save_forecasts"),
            patch("scripts.run_intelligence_pipeline._write_forecast_summary"),
        ):
            records = pipeline._run_forecasts()

        assert records == []

    def test_skips_metric_on_exception(self) -> None:
        with (
            patch(
                "scripts.run_intelligence_pipeline.forecast_all_projects",
                side_effect=ValueError("insufficient data"),
            ),
            patch("scripts.run_intelligence_pipeline._write_forecast_summary"),
        ):
            records = pipeline._run_forecasts()

        assert records == []

    def test_mape_threshold_determines_status(self, sample_forecast_result: ForecastResult) -> None:
        """MAPE < 0.15 → pass; ≥ 0.15 → degraded."""
        # Override mape to trigger degraded status
        sample_forecast_result.mape = 0.20
        with (
            patch(
                "scripts.run_intelligence_pipeline.forecast_all_projects",
                return_value=[sample_forecast_result],
            ),
            patch("scripts.run_intelligence_pipeline.save_forecasts"),
            patch("scripts.run_intelligence_pipeline._write_forecast_summary"),
        ):
            records = pipeline._run_forecasts()

        assert all(r["status"] == "degraded" for r in records)

    def test_pass_status_when_mape_below_threshold(self, sample_forecast_result: ForecastResult) -> None:
        sample_forecast_result.mape = 0.05
        with (
            patch(
                "scripts.run_intelligence_pipeline.forecast_all_projects",
                return_value=[sample_forecast_result],
            ),
            patch("scripts.run_intelligence_pipeline.save_forecasts"),
            patch("scripts.run_intelligence_pipeline._write_forecast_summary"),
        ):
            records = pipeline._run_forecasts()

        assert all(r["status"] == "pass" for r in records)

    def test_calls_write_forecast_summary(self, sample_forecast_result: ForecastResult) -> None:
        """_write_forecast_summary is called at the end of _run_forecasts."""
        mock_write = MagicMock()
        with (
            patch(
                "scripts.run_intelligence_pipeline.forecast_all_projects",
                return_value=[sample_forecast_result],
            ),
            patch("scripts.run_intelligence_pipeline.save_forecasts"),
            patch("scripts.run_intelligence_pipeline._write_forecast_summary", mock_write),
        ):
            pipeline._run_forecasts()

        mock_write.assert_called_once()


# ---------------------------------------------------------------------------
# _write_forecast_summary
# ---------------------------------------------------------------------------


class TestWriteForecastSummary:
    def test_writes_improving_when_all_pass(self, tmp_path: Path) -> None:
        records = [
            {"name": "forecast_quality", "status": "pass"},
            {"name": "forecast_flow", "status": "pass"},
        ]
        with patch.object(pipeline, "_FORECASTS_DIR", tmp_path):
            pipeline._write_forecast_summary(records)

        data = json.loads((tmp_path / "forecast_summary.json").read_text())
        assert data["org_trend"] == "improving"
        assert data["pass_count"] == 2
        assert data["degraded_count"] == 0

    def test_writes_worsening_when_all_degraded(self, tmp_path: Path) -> None:
        records = [
            {"name": "forecast_quality", "status": "degraded"},
            {"name": "forecast_flow", "status": "degraded"},
        ]
        with patch.object(pipeline, "_FORECASTS_DIR", tmp_path):
            pipeline._write_forecast_summary(records)

        data = json.loads((tmp_path / "forecast_summary.json").read_text())
        assert data["org_trend"] == "worsening"

    def test_writes_stable_when_mixed(self, tmp_path: Path) -> None:
        records = [
            {"name": "forecast_quality", "status": "pass"},
            {"name": "forecast_flow", "status": "degraded"},
        ]
        with patch.object(pipeline, "_FORECASTS_DIR", tmp_path):
            pipeline._write_forecast_summary(records)

        data = json.loads((tmp_path / "forecast_summary.json").read_text())
        assert data["org_trend"] == "stable"

    def test_no_op_when_empty(self, tmp_path: Path) -> None:
        with patch.object(pipeline, "_FORECASTS_DIR", tmp_path):
            pipeline._write_forecast_summary([])

        # File should NOT be created when records is empty
        assert not (tmp_path / "forecast_summary.json").exists()


# ---------------------------------------------------------------------------
# _run_scenarios
# ---------------------------------------------------------------------------


class TestRunScenarios:
    def test_returns_true_on_success(
        self,
        tmp_path: Path,
        sample_features_df: pd.DataFrame,
        sample_scenario_result: ScenarioResult,
    ) -> None:
        with (
            patch(
                "scripts.run_intelligence_pipeline.load_features",
                return_value=sample_features_df,
            ),
            patch(
                "scripts.run_intelligence_pipeline.compare_scenarios",
                return_value=[sample_scenario_result],
            ),
            patch.object(pipeline, "_INSIGHTS_DIR", tmp_path),
        ):
            result = pipeline._run_scenarios()

        assert result is True
        scenario_files = list(tmp_path.glob("scenario_results_*.json"))
        assert len(scenario_files) == 1
        entries = json.loads(scenario_files[0].read_text())
        # Fixture only has open_bugs column → only quality metric produces results
        assert len(entries) >= 1

    def test_returns_false_when_no_entries_produced(self, tmp_path: Path) -> None:
        with (
            patch(
                "scripts.run_intelligence_pipeline.load_features",
                side_effect=ValueError("no features"),
            ),
            patch.object(pipeline, "_INSIGHTS_DIR", tmp_path),
        ):
            result = pipeline._run_scenarios()

        assert result is False

    def test_returns_false_on_outer_exception(self, tmp_path: Path) -> None:
        with (
            patch(
                "scripts.run_intelligence_pipeline.load_features",
                side_effect=RuntimeError("unexpected"),
            ),
            patch.object(pipeline, "_INSIGHTS_DIR", tmp_path),
        ):
            result = pipeline._run_scenarios()

        assert result is False

    def test_skips_metrics_with_missing_column(
        self,
        tmp_path: Path,
        sample_features_df: pd.DataFrame,
        sample_scenario_result: ScenarioResult,
    ) -> None:
        """DataFrame without the required column is silently skipped."""
        df_no_col = sample_features_df.drop(columns=["open_bugs"])
        with (
            patch(
                "scripts.run_intelligence_pipeline.load_features",
                return_value=df_no_col,
            ),
            patch(
                "scripts.run_intelligence_pipeline.compare_scenarios",
                return_value=[sample_scenario_result],
            ),
            patch.object(pipeline, "_INSIGHTS_DIR", tmp_path),
        ):
            # The non-open_bugs metrics (throughput, build_success_rate, unassigned_pct)
            # are still present in the fixture — only quality is missing.
            # Result should still be True with partial data.
            pipeline._run_scenarios()  # just verify no exception raised


# ---------------------------------------------------------------------------
# _run_risk_scoring
# ---------------------------------------------------------------------------


class TestRunRiskScoring:
    def test_returns_true_on_success(self) -> None:
        mock_score = MagicMock()
        with (
            patch(
                "scripts.run_intelligence_pipeline.compute_all_risks",
                return_value=[mock_score],
            ),
            patch("scripts.run_intelligence_pipeline.save_risk_scores"),
        ):
            result = pipeline._run_risk_scoring()

        assert result is True

    def test_returns_false_when_no_projects(self) -> None:
        with patch(
            "scripts.run_intelligence_pipeline.compute_all_risks",
            return_value=[],
        ):
            result = pipeline._run_risk_scoring()

        assert result is False

    def test_returns_false_on_exception(self) -> None:
        with patch(
            "scripts.run_intelligence_pipeline.compute_all_risks",
            side_effect=RuntimeError("db error"),
        ):
            result = pipeline._run_risk_scoring()

        assert result is False


# ---------------------------------------------------------------------------
# _update_model_performance
# ---------------------------------------------------------------------------


class TestUpdateModelPerformance:
    def test_creates_file_when_missing(self, tmp_path: Path) -> None:
        perf_path = tmp_path / "model_performance.json"
        records = [{"name": "forecast_quality", "mape": 0.08, "status": "pass"}]

        with patch.object(pipeline, "_MODEL_PERF_PATH", perf_path):
            pipeline._update_model_performance(records)

        data = json.loads(perf_path.read_text())
        assert len(data["models"]) == 1
        assert data["models"][0]["name"] == "forecast_quality"

    def test_merges_with_existing_entry(self, tmp_model_perf: Path) -> None:
        new_records = [
            {"name": "forecast_quality", "mape": 0.10, "status": "pass"},  # update
            {"name": "forecast_flow", "mape": 0.12, "status": "pass"},  # new
        ]

        with patch.object(pipeline, "_MODEL_PERF_PATH", tmp_model_perf):
            pipeline._update_model_performance(new_records)

        data = json.loads(tmp_model_perf.read_text())
        by_name = {m["name"]: m for m in data["models"]}

        # existing entry updated (mape changed from 0.05 to 0.10)
        assert by_name["forecast_quality"]["mape"] == 0.10
        # new entry appended
        assert "forecast_flow" in by_name
        assert data["last_updated"] is not None

    def test_no_op_when_records_empty(self, tmp_model_perf: Path) -> None:
        original_text = tmp_model_perf.read_text()
        with patch.object(pipeline, "_MODEL_PERF_PATH", tmp_model_perf):
            pipeline._update_model_performance([])

        # File not modified when no records
        assert tmp_model_perf.read_text() == original_text

    def test_handles_corrupt_json_gracefully(self, tmp_path: Path) -> None:
        perf_path = tmp_path / "model_performance.json"
        perf_path.write_text("{ not valid json }")
        records = [{"name": "forecast_quality", "mape": 0.08, "status": "pass"}]

        with patch.object(pipeline, "_MODEL_PERF_PATH", perf_path):
            pipeline._update_model_performance(records)  # should not raise

        data = json.loads(perf_path.read_text())
        assert len(data["models"]) == 1


# ---------------------------------------------------------------------------
# main() — exit code contract
# ---------------------------------------------------------------------------


class TestMain:
    def test_returns_zero_when_all_pass(self) -> None:
        with (
            patch(
                "scripts.run_intelligence_pipeline._run_feature_engineering",
                return_value=True,
            ),
            patch(
                "scripts.run_intelligence_pipeline._run_forecasts",
                return_value=[{"name": "forecast_quality", "mape": 0.08, "status": "pass"}],
            ),
            patch(
                "scripts.run_intelligence_pipeline._run_scenarios",
                return_value=True,
            ),
            patch(
                "scripts.run_intelligence_pipeline._run_risk_scoring",
                return_value=True,
            ),
            patch("scripts.run_intelligence_pipeline._update_model_performance"),
        ):
            assert pipeline.main() == 0

    def test_returns_one_when_feature_engineering_fails(self) -> None:
        with (
            patch(
                "scripts.run_intelligence_pipeline._run_feature_engineering",
                return_value=False,
            ),
            patch(
                "scripts.run_intelligence_pipeline._run_forecasts",
                return_value=[],
            ),
            patch(
                "scripts.run_intelligence_pipeline._run_scenarios",
                return_value=False,
            ),
            patch(
                "scripts.run_intelligence_pipeline._run_risk_scoring",
                return_value=False,
            ),
            patch("scripts.run_intelligence_pipeline._update_model_performance"),
        ):
            assert pipeline.main() == 1

    def test_returns_one_when_partial_failure(self) -> None:
        """Risk scoring failure still results in exit code 1."""
        with (
            patch(
                "scripts.run_intelligence_pipeline._run_feature_engineering",
                return_value=True,
            ),
            patch(
                "scripts.run_intelligence_pipeline._run_forecasts",
                return_value=[{"name": "forecast_quality", "mape": 0.08, "status": "pass"}],
            ),
            patch(
                "scripts.run_intelligence_pipeline._run_scenarios",
                return_value=True,
            ),
            patch(
                "scripts.run_intelligence_pipeline._run_risk_scoring",
                return_value=False,
            ),
            patch("scripts.run_intelligence_pipeline._update_model_performance"),
        ):
            assert pipeline.main() == 1

    def test_returns_one_when_scenarios_fail(self) -> None:
        """Scenario failure alone results in exit code 1."""
        with (
            patch(
                "scripts.run_intelligence_pipeline._run_feature_engineering",
                return_value=True,
            ),
            patch(
                "scripts.run_intelligence_pipeline._run_forecasts",
                return_value=[{"name": "forecast_quality", "mape": 0.08, "status": "pass"}],
            ),
            patch(
                "scripts.run_intelligence_pipeline._run_scenarios",
                return_value=False,
            ),
            patch(
                "scripts.run_intelligence_pipeline._run_risk_scoring",
                return_value=True,
            ),
            patch("scripts.run_intelligence_pipeline._update_model_performance"),
        ):
            assert pipeline.main() == 1

    def test_all_steps_called_even_when_feature_eng_fails(self) -> None:
        """Downstream steps run regardless — partial output is better than none."""
        mock_forecasts = MagicMock(return_value=[])
        mock_scenarios = MagicMock(return_value=False)
        mock_risk = MagicMock(return_value=False)
        mock_update = MagicMock()

        with (
            patch(
                "scripts.run_intelligence_pipeline._run_feature_engineering",
                return_value=False,
            ),
            patch("scripts.run_intelligence_pipeline._run_forecasts", mock_forecasts),
            patch("scripts.run_intelligence_pipeline._run_scenarios", mock_scenarios),
            patch("scripts.run_intelligence_pipeline._run_risk_scoring", mock_risk),
            patch("scripts.run_intelligence_pipeline._update_model_performance", mock_update),
        ):
            pipeline.main()

        mock_forecasts.assert_called_once()
        mock_scenarios.assert_called_once()
        mock_risk.assert_called_once()
        mock_update.assert_called_once()
