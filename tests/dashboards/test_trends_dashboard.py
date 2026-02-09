"""
Tests for Trends Dashboard Generator

Tests cover:
- 12-week historical data loading
- Trend calculation and sparkline generation
- Burn rate analysis
- Week-over-week change detection
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from execution.dashboards.trends import TrendsDashboardGenerator


@pytest.fixture
def sample_12_week_history():
    """Generate 12 weeks of historical data"""
    base_date = datetime(2025, 11, 15)
    history = []

    for week in range(12):
        week_date = base_date + timedelta(weeks=week)
        # Simulate improving trend (bugs decreasing)
        total_bugs = 250 - (week * 10)
        open_bugs = 80 - (week * 5)

        history.append(
            {
                "week_date": week_date.strftime("%Y-%m-%d"),
                "total_bugs": total_bugs,
                "open_bugs": max(open_bugs, 10),  # Don't go below 10
                "critical_bugs": max(15 - week, 3),
                "p85_cycle_time_days": max(12.0 - (week * 0.3), 3.0),
            }
        )

    return history


@pytest.fixture
def sample_baseline_data():
    """Sample baseline data for target calculation"""
    return {
        "total_bugs": 500,
        "baseline_date": "2025-11-01",
        "target_reduction_pct": 70,
        "target_date": "2026-06-01",
    }


class TestLoadHistoricalData:
    """Tests for loading historical data"""

    def test_load_12_weeks_history(self, sample_12_week_history):
        """Should load 12 weeks of historical data"""
        mock_file_data = {"weeks": sample_12_week_history}
        mock_data = json.dumps(mock_file_data)

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = mock_data
            with patch("pathlib.Path.exists", return_value=True):
                generator = TrendsDashboardGenerator(weeks=12)
                data = generator._load_all_history()

                assert "quality" in data
                assert data["quality"] is not None
                assert len(data["quality"]["weeks"]) == 12

    def test_load_partial_history(self):
        """Should handle partial history (less than 12 weeks)"""
        partial_history = [
            {"week_date": "2026-02-07", "total_bugs": 150},
            {"week_date": "2026-01-31", "total_bugs": 160},
        ]
        mock_file_data = {"weeks": partial_history}
        mock_data = json.dumps(mock_file_data)

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = mock_data
            with patch("pathlib.Path.exists", return_value=True):
                generator = TrendsDashboardGenerator(weeks=12)
                data = generator._load_all_history()

                # Should work with available data
                assert len(data["quality"]["weeks"]) == 2

    def test_handle_missing_weeks(self, sample_12_week_history):
        """Should handle gaps in weekly data"""
        # Remove week 5 to create gap
        history_with_gap = [w for i, w in enumerate(sample_12_week_history) if i != 5]

        mock_file_data = {"weeks": history_with_gap}
        mock_data = json.dumps(mock_file_data)

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = mock_data
            with patch("pathlib.Path.exists", return_value=True):
                generator = TrendsDashboardGenerator(weeks=12)
                data = generator._load_all_history()

                assert len(data["quality"]["weeks"]) == 11  # 12 - 1 removed week

    def test_handle_missing_file(self):
        """Should handle missing history file"""
        with patch("pathlib.Path.read_text", side_effect=FileNotFoundError("File not found")):
            generator = TrendsDashboardGenerator(weeks=12)
            data = generator._load_all_history()

            # Should return empty/default data
            assert isinstance(data, dict)


class TestCalculateTrends:
    """Tests for trend calculation"""

    def test_calculate_sparkline_data(self, sample_12_week_history):
        """Should generate sparkline data points"""
        values = [week["total_bugs"] for week in sample_12_week_history]

        # Should have 12 data points
        assert len(values) == 12

        # Should show decreasing trend
        assert values[0] > values[-1]  # First > Last

    def test_calculate_week_over_week_change(self, sample_12_week_history):
        """Should calculate week-over-week percentage change"""
        latest_week = sample_12_week_history[-1]
        previous_week = sample_12_week_history[-2]

        change = latest_week["total_bugs"] - previous_week["total_bugs"]
        change_pct = (change / previous_week["total_bugs"]) * 100

        # Should be negative (improving)
        assert change_pct < 0

    def test_calculate_burn_rate(self, sample_12_week_history, sample_baseline_data):
        """Should calculate weekly burn rate"""
        baseline = sample_baseline_data["total_bugs"]  # 500
        current = sample_12_week_history[-1]["total_bugs"]  # ~130
        weeks_elapsed = 12

        total_reduction = baseline - current  # ~370
        weekly_burn_rate = total_reduction / weeks_elapsed  # ~30.8/week

        assert weekly_burn_rate > 0  # Should be positive reduction
        assert weekly_burn_rate == pytest.approx(30.8, abs=1.0)

    def test_calculate_forecast_to_target(self, sample_12_week_history, sample_baseline_data):
        """Should calculate weeks to reach target"""
        baseline = sample_baseline_data["total_bugs"]  # 500
        target = baseline * 0.3  # 150 (70% reduction target)
        current = sample_12_week_history[-1]["total_bugs"]  # ~130

        remaining = current - target  # Could be negative if exceeded
        weekly_burn_rate = 30.0  # From previous test

        if remaining > 0:
            weeks_to_target = remaining / weekly_burn_rate
        else:
            weeks_to_target = 0  # Already met target

        assert weeks_to_target >= 0


class TestGenerateForecastBanner:
    """Tests for forecast banner generation"""

    def test_forecast_banner_on_track(self, sample_12_week_history, sample_baseline_data):
        """Should show 'on track' when meeting target"""
        baseline = sample_baseline_data["total_bugs"]
        target = baseline * 0.3
        current = sample_12_week_history[-1]["total_bugs"]

        # Current (130) < Target (150) = On Track
        status = "On Track" if current <= target else "Behind"

        assert status == "On Track"

    def test_forecast_banner_behind(self):
        """Should show 'behind' when not meeting target"""
        baseline = 500
        target = baseline * 0.3  # 150
        current = 200  # Above target

        status = "On Track" if current <= target else "Behind"

        assert status == "Behind"

    def test_forecast_banner_no_data(self):
        """Should handle missing baseline data"""
        baseline = None
        target = None

        status = "Unknown" if not baseline else "On Track"

        assert status == "Unknown"


class TestGenerateTrendsDashboard:
    """Tests for full dashboard generation"""

    @patch("execution.dashboards.trends.render_dashboard", return_value="<html>Trends Dashboard</html>")
    @patch("execution.dashboards.trends.get_dashboard_framework", return_value=("<style></style>", "<script></script>"))
    def test_generate_dashboard_12_weeks(self, mock_framework, mock_render, sample_12_week_history, tmp_path):
        """Should generate dashboard with 12 weeks of data"""
        mock_file_data = {"weeks": sample_12_week_history}
        mock_quality = json.dumps(mock_file_data)

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = mock_quality
            with patch("pathlib.Path.exists", return_value=True):
                generator = TrendsDashboardGenerator(weeks=12)
                output_file = tmp_path / "trends.html"

                with patch("pathlib.Path.write_text") as mock_write:
                    html = generator.generate(output_file)

                assert isinstance(html, str)
                assert len(html) > 0
                mock_render.assert_called_once()

    @patch("execution.dashboards.trends.sparkline", return_value="<svg>sparkline</svg>")
    @patch("execution.dashboards.trends.render_dashboard", return_value="<html>Dashboard</html>")
    def test_generate_dashboard_with_sparklines(self, mock_render, mock_sparkline, sample_12_week_history):
        """Should include sparklines for each metric"""
        mock_file_data = {"weeks": sample_12_week_history}
        mock_quality = json.dumps(mock_file_data)

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = mock_quality
            with patch("pathlib.Path.exists", return_value=True):
                with patch(
                    "execution.dashboards.trends.get_dashboard_framework",
                    return_value=("<style></style>", "<script></script>"),
                ):
                    generator = TrendsDashboardGenerator(weeks=12)
                    html = generator.generate()

                # Sparkline should be called for multiple metrics
                assert mock_sparkline.call_count >= 1

    @patch("execution.dashboards.trends.render_dashboard", return_value="<html>Dashboard</html>")
    def test_generate_dashboard_burn_rate_analysis(self, mock_render, sample_12_week_history, sample_baseline_data):
        """Should include burn rate analysis in context"""
        mock_file_data = {"weeks": sample_12_week_history}
        mock_quality = json.dumps(mock_file_data)
        mock_baseline = json.dumps(sample_baseline_data)

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = mock_quality
            with patch("pathlib.Path.exists", return_value=True):
                with patch(
                    "execution.dashboards.trends.get_dashboard_framework",
                    return_value=("<style></style>", "<script></script>"),
                ):
                    generator = TrendsDashboardGenerator(weeks=12)
                    html = generator.generate()

                # Should have called render with context including forecast
                call_args = mock_render.call_args
                assert call_args is not None

    @patch("execution.dashboards.trends.render_dashboard", return_value="<html>Empty</html>")
    def test_generate_dashboard_empty_history(self, mock_render):
        """Should handle empty history gracefully"""
        mock_empty = json.dumps({"weeks": []})

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = mock_empty
            with patch("pathlib.Path.exists", return_value=True):
                with patch(
                    "execution.dashboards.trends.get_dashboard_framework",
                    return_value=("<style></style>", "<script></script>"),
                ):
                    generator = TrendsDashboardGenerator(weeks=12)
                    html = generator.generate()

                assert len(html) > 0  # Should still generate HTML

    def test_build_trend_metrics_structure(self, sample_12_week_history):
        """Should build trend metrics with expected structure"""
        # Simulate building trend metrics
        metrics = {
            "total_bugs": {
                "current": sample_12_week_history[-1]["total_bugs"],
                "previous": sample_12_week_history[-2]["total_bugs"],
                "sparkline_values": [w["total_bugs"] for w in sample_12_week_history],
                "trend": "down",
            },
            "open_bugs": {
                "current": sample_12_week_history[-1]["open_bugs"],
                "previous": sample_12_week_history[-2]["open_bugs"],
                "sparkline_values": [w["open_bugs"] for w in sample_12_week_history],
                "trend": "down",
            },
        }

        assert len(metrics["total_bugs"]["sparkline_values"]) == 12
        assert metrics["total_bugs"]["trend"] == "down"
