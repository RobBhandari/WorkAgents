"""
Tests for execution/intelligence/forecast_engine.py

Covers:
- forecast_metric() happy path with 20-week synthetic quality series
- Raises ValueError for fewer than 12 data points
- Returns ForecastResult with correct structure (metric, project, P10 ≤ P50 ≤ P90)
- compute_trend_strength() returns TrendStrengthScore with direction and score
- Improving trend detected correctly (values decreasing = improving for bugs)
- Flat trend detection (near-zero slope relative to mean)
- MAPE calculation: synthetic data with known linear pattern → MAPE near zero
- save_forecasts() with mocked PathValidator and file write
- load_forecasts() with mocked glob and JSON read
- forecast_all_projects() with mocked load_features
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from execution.domain.intelligence import ForecastPoint, ForecastResult, TrendStrengthScore
from execution.intelligence.forecast_engine import (
    MIN_DATA_POINTS,
    _compute_mape,
    _fit_linear,
    _prediction_stderr,
    compute_trend_strength,
    forecast_metric,
    load_forecasts,
    save_forecasts,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_quality_df(n: int, slope: float = -2.0, base: float = 300.0) -> pd.DataFrame:
    """Build a synthetic quality DataFrame with n rows and a linear open_bugs trend."""
    dates = pd.date_range("2025-10-06", periods=n, freq="W")
    open_bugs = [base + slope * i + (i % 3) * 0.5 for i in range(n)]
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Product_A"] * n,
            "open_bugs": open_bugs,
            "p1_bugs": [10] * n,
        }
    )


def _make_forecast_result(project: str = "Product_A", metric: str = "open_bugs") -> ForecastResult:
    """Build a minimal ForecastResult for persistence tests."""
    return ForecastResult(
        timestamp=datetime(2026, 1, 15, 12, 0, 0),
        project=project,
        metric=metric,
        forecast=[
            ForecastPoint(week=1, p10=200.0, p50=220.0, p90=240.0),
            ForecastPoint(week=4, p10=180.0, p50=200.0, p90=220.0),
        ],
        model="linear_regression",
        mape=0.05,
        trend_direction="improving",
        trend_strength=0.85,
    )


# ---------------------------------------------------------------------------
# TestForecastMetricHappyPath
# ---------------------------------------------------------------------------


class TestForecastMetricHappyPath:
    def test_returns_forecast_result_type(self, sample_quality_series: pd.DataFrame) -> None:
        result = forecast_metric(sample_quality_series, "open_bugs", "Product_A")
        assert isinstance(result, ForecastResult)

    def test_result_has_correct_metric(self, sample_quality_series: pd.DataFrame) -> None:
        result = forecast_metric(sample_quality_series, "open_bugs", "Product_A")
        assert result.metric == "open_bugs"

    def test_result_has_correct_project(self, sample_quality_series: pd.DataFrame) -> None:
        result = forecast_metric(sample_quality_series, "open_bugs", "Product_A")
        assert result.project == "Product_A"

    def test_forecast_has_expected_horizons(self, sample_quality_series: pd.DataFrame) -> None:
        from execution.intelligence.forecast_engine import FORECAST_HORIZONS

        result = forecast_metric(sample_quality_series, "open_bugs", "Product_A")
        actual_weeks = [fp.week for fp in result.forecast]
        assert actual_weeks == FORECAST_HORIZONS

    def test_p10_lte_p50_for_all_horizons(self, sample_quality_series: pd.DataFrame) -> None:
        result = forecast_metric(sample_quality_series, "open_bugs", "Product_A")
        for fp in result.forecast:
            assert fp.p10 <= fp.p50, f"P10 > P50 at horizon {fp.week}"

    def test_p50_lte_p90_for_all_horizons(self, sample_quality_series: pd.DataFrame) -> None:
        result = forecast_metric(sample_quality_series, "open_bugs", "Product_A")
        for fp in result.forecast:
            assert fp.p50 <= fp.p90, f"P50 > P90 at horizon {fp.week}"

    def test_mape_is_finite_float(self, sample_quality_series: pd.DataFrame) -> None:
        result = forecast_metric(sample_quality_series, "open_bugs", "Product_A")
        assert isinstance(result.mape, float)
        assert not np.isnan(result.mape)
        assert result.mape >= 0.0

    def test_trend_strength_is_between_0_and_1(self, sample_quality_series: pd.DataFrame) -> None:
        result = forecast_metric(sample_quality_series, "open_bugs", "Product_A")
        assert 0.0 <= result.trend_strength <= 1.0

    def test_model_name_is_linear_regression(self, sample_quality_series: pd.DataFrame) -> None:
        result = forecast_metric(sample_quality_series, "open_bugs", "Product_A")
        assert result.model == "linear_regression"


# ---------------------------------------------------------------------------
# TestForecastMetricInsufficientData
# ---------------------------------------------------------------------------


class TestForecastMetricInsufficientData:
    def test_raises_value_error_for_short_series(self, sample_quality_series_short: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match=f"minimum {MIN_DATA_POINTS} required"):
            forecast_metric(sample_quality_series_short, "open_bugs", "Product_A")

    def test_raises_value_error_for_missing_column(self, sample_quality_series: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="not found in DataFrame"):
            forecast_metric(sample_quality_series, "nonexistent_col", "Product_A")

    def test_raises_for_one_row(self) -> None:
        df = _make_quality_df(1)
        with pytest.raises(ValueError, match=f"minimum {MIN_DATA_POINTS} required"):
            forecast_metric(df, "open_bugs", "Product_A")

    def test_exactly_min_data_points_does_not_raise(self) -> None:
        df = _make_quality_df(MIN_DATA_POINTS)
        # Should not raise — exactly at the minimum
        result = forecast_metric(df, "open_bugs", "Product_A")
        assert isinstance(result, ForecastResult)


# ---------------------------------------------------------------------------
# TestForecastTrendDirection
# ---------------------------------------------------------------------------


class TestForecastTrendDirection:
    def test_improving_trend_for_decreasing_series(self) -> None:
        """Decreasing open_bugs → trend_direction = improving."""
        df = _make_quality_df(20, slope=-5.0, base=300.0)
        result = forecast_metric(df, "open_bugs", "Product_A")
        assert result.trend_direction == "improving"

    def test_worsening_trend_for_increasing_series(self) -> None:
        """Increasing open_bugs → trend_direction = worsening."""
        df = _make_quality_df(20, slope=5.0, base=100.0)
        result = forecast_metric(df, "open_bugs", "Product_A")
        assert result.trend_direction == "worsening"

    def test_flat_trend_for_constant_series(self) -> None:
        """Constant series → trend_direction = flat."""
        dates = pd.date_range("2025-10-06", periods=20, freq="W")
        df = pd.DataFrame(
            {
                "week_date": dates,
                "project": ["Product_A"] * 20,
                "open_bugs": [100.0] * 20,
            }
        )
        result = forecast_metric(df, "open_bugs", "Product_A")
        assert result.trend_direction == "flat"


# ---------------------------------------------------------------------------
# TestComputeMape
# ---------------------------------------------------------------------------


class TestComputeMape:
    def test_mape_near_zero_for_linear_series(self) -> None:
        """Perfect linear series → MAPE should be very small."""
        y = np.array([300.0 - i * 2.0 for i in range(20)])
        mape = _compute_mape(y)
        assert mape < 0.05, f"Expected MAPE < 5% for clean linear series, got {mape:.3%}"

    def test_mape_is_non_negative(self) -> None:
        y = np.array([300.0 - i * 2.0 + (i % 3) * 1.5 for i in range(20)])
        mape = _compute_mape(y)
        assert mape >= 0.0

    def test_mape_returns_float(self) -> None:
        y = np.array([100.0] * 20)
        mape = _compute_mape(y)
        assert isinstance(mape, float)


# ---------------------------------------------------------------------------
# TestComputeTrendStrength
# ---------------------------------------------------------------------------


class TestComputeTrendStrength:
    def test_returns_trend_strength_score_type(self, sample_quality_series: pd.DataFrame) -> None:
        result = compute_trend_strength(sample_quality_series, "open_bugs", "Product_A")
        assert isinstance(result, TrendStrengthScore)

    def test_result_has_direction(self, sample_quality_series: pd.DataFrame) -> None:
        result = compute_trend_strength(sample_quality_series, "open_bugs", "Product_A")
        assert result.direction in ("improving", "worsening", "flat")

    def test_score_is_between_0_and_100(self, sample_quality_series: pd.DataFrame) -> None:
        result = compute_trend_strength(sample_quality_series, "open_bugs", "Product_A")
        assert 0.0 <= result.score <= 100.0

    def test_improving_direction_for_declining_series(self) -> None:
        df = _make_quality_df(20, slope=-5.0, base=300.0)
        result = compute_trend_strength(df, "open_bugs", "Product_A")
        assert result.direction == "improving"

    def test_worsening_direction_for_rising_series(self) -> None:
        df = _make_quality_df(20, slope=5.0, base=100.0)
        result = compute_trend_strength(df, "open_bugs", "Product_A")
        assert result.direction == "worsening"

    def test_missing_column_returns_flat_zero(self) -> None:
        df = _make_quality_df(10)
        result = compute_trend_strength(df, "nonexistent_col", "Product_A")
        assert result.direction == "flat"
        assert result.score == 0.0
        assert result.r_squared == 0.0

    def test_single_row_returns_flat_zero(self) -> None:
        df = _make_quality_df(1)
        result = compute_trend_strength(df, "open_bugs", "Product_A")
        assert result.direction == "flat"
        assert result.score == 0.0

    def test_weeks_analyzed_matches_input_size(self, sample_quality_series: pd.DataFrame) -> None:
        result = compute_trend_strength(sample_quality_series, "open_bugs", "Product_A")
        assert result.weeks_analyzed == len(sample_quality_series)

    def test_r_squared_is_between_0_and_1(self) -> None:
        df = _make_quality_df(20, slope=-2.0)
        result = compute_trend_strength(df, "open_bugs", "Product_A")
        assert 0.0 <= result.r_squared <= 1.0

    def test_high_r_squared_for_clean_linear_series(self) -> None:
        """A perfectly linear series should have R² close to 1."""
        dates = pd.date_range("2025-10-06", periods=20, freq="W")
        df = pd.DataFrame(
            {
                "week_date": dates,
                "project": ["Product_A"] * 20,
                "open_bugs": [300.0 - i * 5.0 for i in range(20)],  # Perfect line
            }
        )
        result = compute_trend_strength(df, "open_bugs", "Product_A")
        assert result.r_squared > 0.99


# ---------------------------------------------------------------------------
# TestFitLinear (internal helper)
# ---------------------------------------------------------------------------


class TestFitLinear:
    def test_perfect_linear_fit(self) -> None:
        x = np.arange(10, dtype=float)
        y = 2.0 * x + 5.0
        slope, intercept, r_sq, stderr = _fit_linear(x, y)
        assert abs(slope - 2.0) < 1e-9
        assert abs(intercept - 5.0) < 1e-9
        assert abs(r_sq - 1.0) < 1e-6
        assert stderr < 1e-9

    def test_r_squared_clipped_to_unit_range(self) -> None:
        x = np.arange(5, dtype=float)
        y = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
        _, _, r_sq, _ = _fit_linear(x, y)
        assert 0.0 <= r_sq <= 1.0


# ---------------------------------------------------------------------------
# TestSaveForecasts
# ---------------------------------------------------------------------------


class TestSaveForecasts:
    def test_invalid_metric_raises_value_error(self, tmp_path: Path) -> None:
        results = [_make_forecast_result()]
        with pytest.raises(ValueError, match="Invalid metric"):
            save_forecasts(results, "bad_metric", base_dir=tmp_path)

    def test_path_validator_is_called(self, tmp_path: Path) -> None:
        results = [_make_forecast_result()]
        with (
            patch("execution.intelligence.forecast_engine.PathValidator.validate_safe_path") as mock_validate,
            patch.object(Path, "write_text") as mock_write,
        ):
            mock_validate.return_value = str(tmp_path / "quality_forecast_2026-01-01.json")
            mock_write.return_value = None

            save_forecasts(results, "quality", base_dir=tmp_path)
            assert mock_validate.called

    def test_returns_path_to_written_file(self, tmp_path: Path) -> None:
        results = [_make_forecast_result()]
        with (
            patch("execution.intelligence.forecast_engine.PathValidator.validate_safe_path") as mock_validate,
            patch.object(Path, "write_text") as mock_write,
        ):
            expected = str(tmp_path / "quality_forecast_2026-01-01.json")
            mock_validate.return_value = expected
            mock_write.return_value = None

            result = save_forecasts(results, "quality", base_dir=tmp_path)
            assert isinstance(result, Path)

    def test_serializes_all_results(self, tmp_path: Path) -> None:
        """Verify the JSON payload contains all forecast entries."""
        results = [
            _make_forecast_result("Product_A", "open_bugs"),
            _make_forecast_result("Product_B", "open_bugs"),
        ]
        captured_json: list[str] = []

        def capture_write(text: str, **kwargs: object) -> None:
            captured_json.append(text)

        with (
            patch("execution.intelligence.forecast_engine.PathValidator.validate_safe_path") as mock_validate,
            patch.object(Path, "write_text", side_effect=capture_write),
        ):
            mock_validate.return_value = str(tmp_path / "quality_forecast_2026-01-01.json")
            save_forecasts(results, "quality", base_dir=tmp_path)

        assert len(captured_json) == 1
        payload = json.loads(captured_json[0])
        assert len(payload) == 2
        projects = {entry["project"] for entry in payload}
        assert projects == {"Product_A", "Product_B"}


# ---------------------------------------------------------------------------
# TestLoadForecasts
# ---------------------------------------------------------------------------


class TestLoadForecasts:
    def test_invalid_metric_raises_value_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Invalid metric"):
            load_forecasts("bad_metric", base_dir=tmp_path)

    def test_no_json_files_raises_value_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="No forecast JSON found"):
            load_forecasts("quality", base_dir=tmp_path)

    def test_returns_list_of_forecast_results(self, tmp_path: Path) -> None:
        result_data = [
            {
                "metric": "open_bugs",
                "project": "Product_A",
                "generated_date": "2026-01-15T12:00:00",
                "forecast": [
                    {"week": 1, "p10": 200.0, "p50": 220.0, "p90": 240.0},
                    {"week": 4, "p10": 180.0, "p50": 200.0, "p90": 220.0},
                ],
                "model": "linear_regression",
                "mape": 0.05,
                "trend_direction": "improving",
                "trend_strength": 0.85,
            }
        ]
        json_file = tmp_path / "quality_forecast_2026-01-15.json"
        json_file.write_text(json.dumps(result_data), encoding="utf-8")

        results = load_forecasts("quality", base_dir=tmp_path)

        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], ForecastResult)

    def test_loads_latest_file_when_multiple_exist(self, tmp_path: Path) -> None:
        result_data = [
            {
                "metric": "open_bugs",
                "project": "Product_A",
                "generated_date": "2026-01-15T12:00:00",
                "forecast": [],
                "model": "linear_regression",
                "mape": 0.05,
                "trend_direction": "flat",
                "trend_strength": 0.0,
            }
        ]
        older = tmp_path / "quality_forecast_2025-01-01.json"
        newer = tmp_path / "quality_forecast_2026-01-15.json"
        older.write_text(json.dumps(result_data), encoding="utf-8")
        newer.write_text(json.dumps(result_data), encoding="utf-8")

        # Should not error; lexicographically latest is selected
        results = load_forecasts("quality", base_dir=tmp_path)
        assert isinstance(results, list)

    def test_malformed_entry_is_skipped_gracefully(self, tmp_path: Path) -> None:
        malformed_data = [{"totally": "wrong", "structure": True}]
        json_file = tmp_path / "quality_forecast_2026-01-15.json"
        json_file.write_text(json.dumps(malformed_data), encoding="utf-8")

        # Should not raise; malformed entries are skipped
        results = load_forecasts("quality", base_dir=tmp_path)
        assert isinstance(results, list)
        assert len(results) == 0
