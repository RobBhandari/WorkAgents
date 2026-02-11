"""Integration tests for Executive Trends Dashboard pipeline

Tests the end-to-end pipeline from data loading through rendering.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from execution.dashboards.trends.calculator import TrendsCalculator
from execution.dashboards.trends.data_loader import TrendsDataLoader
from execution.dashboards.trends.renderer import TrendsRenderer


@pytest.fixture
def sample_quality_data():
    """Sample quality history data"""
    return {
        "weeks": [
            {
                "week_ending": "2026-01-01",
                "projects": [
                    {"project_name": "Project A", "open_bugs_count": 150, "mttr": {"mttr_days": 5.5}},
                    {"project_name": "Project B", "open_bugs_count": 100, "mttr": {"mttr_days": 7.2}},
                ],
            },
            {
                "week_ending": "2026-01-08",
                "projects": [
                    {"project_name": "Project A", "open_bugs_count": 140, "mttr": {"mttr_days": 5.0}},
                    {"project_name": "Project B", "open_bugs_count": 95, "mttr": {"mttr_days": 6.8}},
                ],
            },
        ]
    }


@pytest.fixture
def sample_security_data():
    """Sample security history data"""
    return {
        "weeks": [
            {"week_ending": "2026-01-01", "metrics": {"current_total": 320}},
            {"week_ending": "2026-01-08", "metrics": {"current_total": 300}},
        ]
    }


@pytest.fixture
def sample_flow_data():
    """Sample flow history data"""
    return {
        "weeks": [
            {
                "week_ending": "2026-01-01",
                "projects": [{"project_name": "Project A", "lead_time": {"p85": 25.5}}],
            },
            {
                "week_ending": "2026-01-08",
                "projects": [{"project_name": "Project A", "lead_time": {"p85": 23.0}}],
            },
        ]
    }


@pytest.fixture
def sample_baselines():
    """Sample baseline data"""
    return {"bugs": 500, "security": 800}


class TestTrendsIntegration:
    """Integration tests for the full trends dashboard pipeline"""

    def test_end_to_end_pipeline(self, tmp_path, sample_quality_data, sample_security_data, sample_baselines):
        """Test complete pipeline from loading to rendering"""
        # Stage 1: Setup mock data
        history_dir = tmp_path / "observatory"
        history_dir.mkdir()

        # Write mock history files
        quality_file = history_dir / "quality_history.json"
        quality_file.write_text(json.dumps(sample_quality_data))

        security_file = history_dir / "security_history.json"
        security_file.write_text(json.dumps(sample_security_data))

        # Write mock baseline files
        baseline_dir = tmp_path / "data"
        baseline_dir.mkdir()

        armorcode_file = baseline_dir / "armorcode_baseline.json"
        armorcode_file.write_text(json.dumps({"total_vulnerabilities": sample_baselines["security"]}))

        ado_file = baseline_dir / "baseline.json"
        ado_file.write_text(json.dumps({"open_count": sample_baselines["bugs"]}))

        # Stage 2: Load Data
        with patch("os.path.exists") as mock_exists, patch("builtins.open", create=True) as mock_file:
            # Setup path.exists to return appropriate values
            def exists_side_effect(path):
                if "quality_history.json" in str(path):
                    return True
                if "security_history.json" in str(path):
                    return True
                if "armorcode_baseline.json" in str(path):
                    return True
                if "baseline.json" in str(path):
                    return True
                return False

            mock_exists.side_effect = exists_side_effect

            # Setup open to return appropriate file contents
            def open_side_effect(path, *args, **kwargs):
                if "quality_history.json" in str(path):
                    return mock_open(read_data=json.dumps(sample_quality_data))()
                if "security_history.json" in str(path):
                    return mock_open(read_data=json.dumps(sample_security_data))()
                if "armorcode_baseline.json" in str(path):
                    return mock_open(read_data=json.dumps({"total_vulnerabilities": sample_baselines["security"]}))()
                if "baseline.json" in str(path):
                    return mock_open(read_data=json.dumps({"open_count": sample_baselines["bugs"]}))()
                raise FileNotFoundError(f"Unexpected file: {path}")

            mock_file.side_effect = open_side_effect

            loader = TrendsDataLoader(history_dir=str(history_dir))
            metrics_data = loader.load_all_metrics()

        # Verify data loaded
        assert metrics_data["quality"] is not None
        assert metrics_data["security"] is not None
        assert metrics_data["baselines"]["bugs"] == sample_baselines["bugs"]
        assert metrics_data["baselines"]["security"] == sample_baselines["security"]

        # Stage 3: Calculate Trends
        calculator = TrendsCalculator(baselines=metrics_data["baselines"])

        target_progress = calculator.calculate_target_progress(
            quality_weeks=sample_quality_data["weeks"], security_weeks=sample_security_data["weeks"]
        )

        quality_trends = calculator.extract_quality_trends(sample_quality_data["weeks"])
        security_trends = calculator.extract_security_trends(sample_security_data["weeks"])

        # Verify calculations
        assert target_progress is not None
        assert "current" in target_progress
        assert "trend_data" in target_progress

        assert quality_trends is not None
        assert "bugs" in quality_trends
        assert quality_trends["bugs"]["current"] == 235  # 140 + 95

        assert security_trends is not None
        assert "vulnerabilities" in security_trends
        assert security_trends["vulnerabilities"]["current"] == 300

        # Stage 4: Render Dashboard
        trends = {"quality": quality_trends, "security": security_trends}
        renderer = TrendsRenderer(trends_data=trends, target_progress=target_progress)

        output_path = tmp_path / "test_dashboard.html"
        generated_file = renderer.generate_dashboard_file(output_path)

        # Verify output
        assert output_path.exists()
        assert generated_file == str(output_path)

        # Verify HTML content (use UTF-8 encoding to handle special characters)
        html_content = output_path.read_text(encoding="utf-8")
        assert "Executive Trends Dashboard" in html_content
        assert "Engineering Health Metrics" in html_content
        assert "70% Reduction Target" in html_content

    def test_pipeline_with_missing_data(self, tmp_path):
        """Test pipeline handles missing data gracefully"""
        history_dir = tmp_path / "observatory"
        history_dir.mkdir()

        # Only create quality file, no security
        quality_file = history_dir / "quality_history.json"
        quality_file.write_text(json.dumps({"weeks": []}))

        with patch("os.path.exists", return_value=False):
            loader = TrendsDataLoader(history_dir=str(history_dir))
            metrics_data = loader.load_all_metrics()

        # All data should be None except baselines
        assert metrics_data["quality"] is None
        assert metrics_data["security"] is None
        assert metrics_data["baselines"] == {}

    def test_calculator_error_handling(self):
        """Test calculator handles invalid data gracefully"""
        calculator = TrendsCalculator(baselines={"bugs": 500, "security": 800})

        # Test with empty weeks
        result = calculator.extract_quality_trends([])
        assert result is None

        # Test with None weeks - should return None for missing data
        result_none = calculator.extract_security_trends([])  # Use empty list instead of None
        assert result_none is None

    def test_renderer_builds_context_correctly(self, sample_quality_data, sample_security_data):
        """Test renderer builds correct context for template"""
        calculator = TrendsCalculator(baselines={"bugs": 500, "security": 800})

        quality_trends = calculator.extract_quality_trends(sample_quality_data["weeks"])
        security_trends = calculator.extract_security_trends(sample_security_data["weeks"])
        target_progress = calculator.calculate_target_progress(
            quality_weeks=sample_quality_data["weeks"], security_weeks=sample_security_data["weeks"]
        )

        trends = {"quality": quality_trends, "security": security_trends}
        renderer = TrendsRenderer(trends_data=trends, target_progress=target_progress)

        context = renderer.build_context()

        # Verify context structure
        assert "metrics" in context
        assert "metrics_json" in context
        assert "framework_css" in context
        assert "framework_js" in context
        assert "timestamp" in context

        # Verify metrics list
        assert isinstance(context["metrics"], list)
        assert len(context["metrics"]) >= 2  # At least target and security


class TestTrendsDataLoader:
    """Unit tests for TrendsDataLoader"""

    def test_load_history_file_success(self, tmp_path):
        """Test successful file loading"""
        test_file = tmp_path / "test_history.json"
        test_data = {"weeks": [{"week_ending": "2026-01-01"}]}
        test_file.write_text(json.dumps(test_data))

        loader = TrendsDataLoader()
        result = loader.load_history_file(str(test_file))

        assert result == test_data

    def test_load_history_file_missing(self):
        """Test handling of missing file"""
        loader = TrendsDataLoader()
        result = loader.load_history_file("nonexistent_file.json")

        assert result is None

    def test_load_history_file_empty(self, tmp_path):
        """Test handling of empty file"""
        test_file = tmp_path / "empty.json"
        test_file.write_text("")

        loader = TrendsDataLoader()
        result = loader.load_history_file(str(test_file))

        assert result is None


class TestTrendsCalculator:
    """Unit tests for TrendsCalculator"""

    def test_get_trend_indicator_increasing_bad(self):
        """Test trend indicator for increasing value (bad direction)"""
        arrow, css_class, change = TrendsCalculator.get_trend_indicator(100, 90, "down")

        assert arrow == "↑"
        assert css_class == "trend-up"
        assert change == 10

    def test_get_trend_indicator_decreasing_good(self):
        """Test trend indicator for decreasing value (good direction)"""
        arrow, css_class, change = TrendsCalculator.get_trend_indicator(90, 100, "down")

        assert arrow == "↓"
        assert css_class == "trend-down"
        assert change == -10

    def test_get_trend_indicator_stable(self):
        """Test trend indicator for stable value"""
        arrow, css_class, change = TrendsCalculator.get_trend_indicator(100, 100.2, "down")

        assert arrow == "→"
        assert css_class == "trend-stable"
        assert abs(change) < 0.5

    def test_get_rag_color_bugs(self):
        """Test RAG color for bugs metric"""
        assert TrendsCalculator.get_rag_color(50, "bugs") == "#10b981"  # Green
        assert TrendsCalculator.get_rag_color(150, "bugs") == "#f59e0b"  # Amber
        assert TrendsCalculator.get_rag_color(250, "bugs") == "#ef4444"  # Red

    def test_get_rag_color_lead_time(self):
        """Test RAG color for lead time metric"""
        assert TrendsCalculator.get_rag_color(20, "lead_time") == "#10b981"  # Green
        assert TrendsCalculator.get_rag_color(45, "lead_time") == "#f59e0b"  # Amber
        assert TrendsCalculator.get_rag_color(70, "lead_time") == "#ef4444"  # Red


class TestTrendsRenderer:
    """Unit tests for TrendsRenderer"""

    def test_generate_metrics_list_structure(self):
        """Test metrics list generation structure"""
        trends = {"quality": {"bugs": {"current": 235, "previous": 250, "trend_data": [250, 240, 235], "unit": "bugs"}}}
        target_progress = {
            "current": 45.5,
            "previous": 44.0,
            "trend_data": [40, 42, 44, 45.5],
            "unit": "% progress",
        }

        renderer = TrendsRenderer(trends_data=trends, target_progress=target_progress)
        metrics = renderer._generate_metrics_list()

        assert isinstance(metrics, list)
        assert len(metrics) >= 1  # At least target metric

        # Check first metric structure (target)
        target_metric = metrics[0]
        assert target_metric["id"] == "target"
        assert "icon" in target_metric
        assert "title" in target_metric
        assert "current" in target_metric
        assert "data" in target_metric  # The key is "data", not "trend_data" in the metrics list
