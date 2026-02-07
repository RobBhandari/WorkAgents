"""
Tests for base metrics domain models
"""

import pytest
from datetime import datetime, timedelta
from execution.domain.metrics import MetricSnapshot, TrendData


class TestMetricSnapshot:
    """Test MetricSnapshot base class"""

    def test_metric_snapshot_creation(self):
        """Test creating MetricSnapshot"""
        timestamp = datetime(2026, 2, 7, 10, 0, 0)
        snapshot = MetricSnapshot(timestamp=timestamp, project="TestApp")

        assert snapshot.timestamp == timestamp
        assert snapshot.project == "TestApp"

    def test_metric_snapshot_no_project(self):
        """Test MetricSnapshot without project"""
        timestamp = datetime.now()
        snapshot = MetricSnapshot(timestamp=timestamp)

        assert snapshot.timestamp == timestamp
        assert snapshot.project is None

    def test_metric_snapshot_invalid_timestamp(self):
        """Test MetricSnapshot raises error for invalid timestamp"""
        with pytest.raises(TypeError, match="timestamp must be datetime"):
            MetricSnapshot(timestamp="2026-02-07")


class TestTrendData:
    """Test TrendData time series model"""

    def test_trend_data_creation(self):
        """Test creating TrendData"""
        values = [50.0, 45.0, 42.0, 38.0]
        timestamps = [
            datetime(2026, 1, 1),
            datetime(2026, 1, 8),
            datetime(2026, 1, 15),
            datetime(2026, 1, 22)
        ]
        trend = TrendData(values=values, timestamps=timestamps, label="Open Bugs")

        assert trend.values == values
        assert trend.timestamps == timestamps
        assert trend.label == "Open Bugs"

    def test_trend_data_mismatched_lengths(self):
        """Test TrendData raises error for mismatched lengths"""
        values = [50.0, 45.0, 42.0]
        timestamps = [datetime(2026, 1, 1), datetime(2026, 1, 8)]  # Only 2

        with pytest.raises(ValueError, match="must have same length"):
            TrendData(values=values, timestamps=timestamps)

    def test_latest(self):
        """Test latest() returns most recent value"""
        values = [50.0, 45.0, 42.0, 38.0]
        timestamps = [datetime(2026, 1, i) for i in range(1, 5)]
        trend = TrendData(values=values, timestamps=timestamps)

        assert trend.latest() == 38.0

    def test_latest_empty(self):
        """Test latest() returns None for empty data"""
        trend = TrendData(values=[], timestamps=[])
        assert trend.latest() is None

    def test_earliest(self):
        """Test earliest() returns first value"""
        values = [50.0, 45.0, 42.0, 38.0]
        timestamps = [datetime(2026, 1, i) for i in range(1, 5)]
        trend = TrendData(values=values, timestamps=timestamps)

        assert trend.earliest() == 50.0

    def test_earliest_empty(self):
        """Test earliest() returns None for empty data"""
        trend = TrendData(values=[], timestamps=[])
        assert trend.earliest() is None

    def test_week_over_week_change(self):
        """Test week-over-week change calculation"""
        values = [50.0, 45.0, 42.0]
        timestamps = [datetime(2026, 1, i) for i in range(1, 4)]
        trend = TrendData(values=values, timestamps=timestamps)

        # Latest (42) - Previous (45) = -3
        assert trend.week_over_week_change() == -3.0

    def test_week_over_week_change_insufficient_data(self):
        """Test week-over-week change returns None with <2 values"""
        trend = TrendData(values=[50.0], timestamps=[datetime.now()])
        assert trend.week_over_week_change() is None

    def test_week_over_week_percent_change(self):
        """Test week-over-week percent change"""
        values = [100.0, 90.0]
        timestamps = [datetime(2026, 1, 1), datetime(2026, 1, 8)]
        trend = TrendData(values=values, timestamps=timestamps)

        # (90 - 100) / 100 * 100 = -10%
        assert trend.week_over_week_percent_change() == -10.0

    def test_week_over_week_percent_change_insufficient_data(self):
        """Test percent change returns None with <2 values"""
        trend = TrendData(values=[50.0], timestamps=[datetime.now()])
        assert trend.week_over_week_percent_change() is None

    def test_week_over_week_percent_change_zero_previous(self):
        """Test percent change returns None when previous is zero"""
        values = [0.0, 10.0]
        timestamps = [datetime(2026, 1, 1), datetime(2026, 1, 8)]
        trend = TrendData(values=values, timestamps=timestamps)

        assert trend.week_over_week_percent_change() is None

    def test_total_change(self):
        """Test total change from first to last"""
        values = [50.0, 45.0, 42.0, 38.0]
        timestamps = [datetime(2026, 1, i) for i in range(1, 5)]
        trend = TrendData(values=values, timestamps=timestamps)

        # 38 - 50 = -12
        assert trend.total_change() == -12.0

    def test_total_change_insufficient_data(self):
        """Test total change returns None with <2 values"""
        trend = TrendData(values=[50.0], timestamps=[datetime.now()])
        assert trend.total_change() is None

    def test_is_improving_lower_is_better_true(self):
        """Test is_improving when lower is better and values decreasing"""
        values = [50.0, 45.0]
        timestamps = [datetime(2026, 1, 1), datetime(2026, 1, 8)]
        trend = TrendData(values=values, timestamps=timestamps)

        assert trend.is_improving(lower_is_better=True) is True

    def test_is_improving_lower_is_better_false(self):
        """Test is_improving when lower is better but values increasing"""
        values = [45.0, 50.0]
        timestamps = [datetime(2026, 1, 1), datetime(2026, 1, 8)]
        trend = TrendData(values=values, timestamps=timestamps)

        assert trend.is_improving(lower_is_better=True) is False

    def test_is_improving_higher_is_better_true(self):
        """Test is_improving when higher is better and values increasing"""
        values = [45.0, 50.0]
        timestamps = [datetime(2026, 1, 1), datetime(2026, 1, 8)]
        trend = TrendData(values=values, timestamps=timestamps)

        assert trend.is_improving(lower_is_better=False) is True

    def test_is_improving_higher_is_better_false(self):
        """Test is_improving when higher is better but values decreasing"""
        values = [50.0, 45.0]
        timestamps = [datetime(2026, 1, 1), datetime(2026, 1, 8)]
        trend = TrendData(values=values, timestamps=timestamps)

        assert trend.is_improving(lower_is_better=False) is False

    def test_is_improving_insufficient_data(self):
        """Test is_improving returns None with insufficient data"""
        trend = TrendData(values=[50.0], timestamps=[datetime.now()])
        assert trend.is_improving() is None

    def test_average(self):
        """Test average calculation"""
        values = [10.0, 20.0, 30.0, 40.0]
        timestamps = [datetime(2026, 1, i) for i in range(1, 5)]
        trend = TrendData(values=values, timestamps=timestamps)

        assert trend.average() == 25.0

    def test_average_empty(self):
        """Test average returns None for empty data"""
        trend = TrendData(values=[], timestamps=[])
        assert trend.average() is None

    def test_get_range(self):
        """Test get_range returns last N values"""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        timestamps = [datetime(2026, 1, i) for i in range(1, 6)]
        trend = TrendData(values=values, timestamps=timestamps, label="Test")

        last_3 = trend.get_range(n=3)

        assert last_3.values == [30.0, 40.0, 50.0]
        assert len(last_3.timestamps) == 3
        assert last_3.label == "Test"

    def test_get_range_larger_than_data(self):
        """Test get_range returns all data if n >= length"""
        values = [10.0, 20.0]
        timestamps = [datetime(2026, 1, 1), datetime(2026, 1, 8)]
        trend = TrendData(values=values, timestamps=timestamps)

        result = trend.get_range(n=5)

        # Should return same object since n >= len
        assert result is trend
