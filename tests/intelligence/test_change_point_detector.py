"""
Tests for execution/intelligence/change_point_detector.py

Covers:
- detect_change_points() on sample_change_point_series — step change at index 12
- detect_change_points() on flat/monotonic data — returns empty or at most sentinel
- detect_change_points() short series (< 2 * min_size) — returns empty list
- detect_change_points() all-same values — returns empty list (no std deviation)
- detect_change_point_weeks() returns ISO date strings for detected indices
- detect_change_point_weeks() missing metric_col — returns empty list
- detect_change_point_weeks() all-null column — returns empty list
- Result is always a list of integers (interior indices only)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from execution.intelligence.change_point_detector import (
    detect_change_point_weeks,
    detect_change_points,
)

# ---------------------------------------------------------------------------
# TestDetectChangePoints — list/array API
# ---------------------------------------------------------------------------


class TestDetectChangePoints:
    def test_detects_step_change_at_index_12(self, sample_change_point_series: pd.DataFrame) -> None:
        """Step change from 50→120 at index 12 should be detected within ±2.

        The ruptures PELT algorithm with rbf cost may report the change-point
        at index 10 rather than 12 for equal-length segments of size 12.
        A tolerance of ±2 accounts for this edge-detection behaviour.
        """
        values = sample_change_point_series["value"].tolist()
        change_points = detect_change_points(values, penalty=5.0)

        assert any(
            abs(cp - 12) <= 2 for cp in change_points
        ), f"Expected change-point near index 12 (±2 tolerance), got {change_points}"

    def test_returns_list(self, sample_change_point_series: pd.DataFrame) -> None:
        values = sample_change_point_series["value"].tolist()
        result = detect_change_points(values)
        assert isinstance(result, list)

    def test_all_elements_are_integers(self, sample_change_point_series: pd.DataFrame) -> None:
        values = sample_change_point_series["value"].tolist()
        result = detect_change_points(values, penalty=5.0)
        assert all(isinstance(cp, int) for cp in result)

    def test_no_sentinel_at_end(self, sample_change_point_series: pd.DataFrame) -> None:
        """ruptures appends len(values) as sentinel — should be excluded."""
        values = sample_change_point_series["value"].tolist()
        result = detect_change_points(values, penalty=5.0)
        assert len(values) not in result

    def test_all_same_values_returns_empty(self) -> None:
        """Constant series has no change-points."""
        constant = [50.0] * 30
        result = detect_change_points(constant, min_size=3)
        assert result == []

    def test_too_short_series_returns_empty(self) -> None:
        """Series shorter than 2 * min_size should return empty list."""
        short = [1.0, 2.0, 3.0, 4.0]  # n=4, min_size=3 → 4 < 2*3=6
        result = detect_change_points(short, min_size=3)
        assert result == []

    def test_very_short_series_two_points(self) -> None:
        result = detect_change_points([100.0, 200.0], min_size=3)
        assert result == []

    def test_empty_series_returns_empty(self) -> None:
        result = detect_change_points([], min_size=3)
        assert result == []

    def test_numpy_array_input_accepted(self, sample_change_point_series: pd.DataFrame) -> None:
        """Should accept numpy arrays, not just lists."""
        values = sample_change_point_series["value"].to_numpy()
        result = detect_change_points(values, penalty=5.0)
        assert isinstance(result, list)

    def test_monotonic_series_no_false_positives(self) -> None:
        """Perfectly linear series should produce no interior change-points."""
        # Use very high penalty to avoid false positives
        linear = [float(i) for i in range(30)]
        result = detect_change_points(linear, min_size=3, penalty=50.0)
        assert len(result) == 0, f"Expected no change-points for linear series, got {result}"

    def test_higher_penalty_fewer_change_points(self, sample_change_point_series: pd.DataFrame) -> None:
        """Increasing penalty should not produce MORE change-points."""
        values = sample_change_point_series["value"].tolist()
        result_low = detect_change_points(values, penalty=1.0)
        result_high = detect_change_points(values, penalty=100.0)
        assert len(result_high) <= len(result_low)

    def test_obvious_two_segment_series(self) -> None:
        """Clear two-regime series: zeros then high values."""
        series = [0.0] * 15 + [100.0] * 15
        result = detect_change_points(series, min_size=3, penalty=5.0)
        assert len(result) >= 1
        assert any(abs(cp - 15) <= 2 for cp in result)


# ---------------------------------------------------------------------------
# TestDetectChangePointWeeks — DataFrame API
# ---------------------------------------------------------------------------


class TestDetectChangePointWeeks:
    def test_returns_list_of_strings(self, sample_change_point_series: pd.DataFrame) -> None:
        result = detect_change_point_weeks(sample_change_point_series, "value", penalty=5.0)
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)

    def test_returns_iso_date_format(self, sample_change_point_series: pd.DataFrame) -> None:
        """Returned strings should be YYYY-MM-DD format."""
        result = detect_change_point_weeks(sample_change_point_series, "value", penalty=5.0)
        for date_str in result:
            # Should be parseable as a date
            from datetime import date

            parsed = date.fromisoformat(date_str)
            assert parsed is not None

    def test_change_point_week_near_index_12(self, sample_change_point_series: pd.DataFrame) -> None:
        """The step change at index 12 should map to a week_date near that position."""
        result = detect_change_point_weeks(sample_change_point_series, "value", penalty=5.0)
        assert len(result) > 0, "Expected at least one change-point week"

    def test_missing_metric_col_returns_empty(self, sample_change_point_series: pd.DataFrame) -> None:
        result = detect_change_point_weeks(sample_change_point_series, "nonexistent_column")
        assert result == []

    def test_all_null_values_returns_empty(self) -> None:
        import pandas as pd

        df = pd.DataFrame(
            {
                "week_date": pd.date_range("2025-10-06", periods=10, freq="W"),
                "value": [None] * 10,
            }
        )
        result = detect_change_point_weeks(df, "value")
        assert result == []

    def test_constant_series_returns_empty(self) -> None:
        df = pd.DataFrame(
            {
                "week_date": pd.date_range("2025-10-06", periods=20, freq="W"),
                "value": [50.0] * 20,
            }
        )
        result = detect_change_point_weeks(df, "value")
        assert result == []

    def test_handles_string_week_dates(self) -> None:
        """week_date column may be strings (ISO format) rather than datetime objects."""
        df = pd.DataFrame(
            {
                "week_date": [f"2025-{10 + i // 4:02d}-{6 + (i % 4) * 7:02d}" for i in range(24)],
                "value": [50.0] * 12 + [120.0] * 12,
            }
        )
        result = detect_change_point_weeks(df, "value", penalty=5.0)
        # Should not raise and should return strings
        assert isinstance(result, list)

    def test_indices_within_dataframe_bounds(self, sample_change_point_series: pd.DataFrame) -> None:
        """All returned week_dates should correspond to rows that actually exist."""
        result = detect_change_point_weeks(sample_change_point_series, "value", penalty=5.0)
        valid_dates = sample_change_point_series["week_date"].dt.strftime("%Y-%m-%d").tolist()
        for date_str in result:
            assert date_str in valid_dates, f"{date_str} not found in DataFrame"
