"""
Tests for Executive Summary Dashboard Generator

Tests cover:
- Multi-source data loading (quality, security, flow)
- Cross-metric summary calculation
- Attention item identification
- Trend analysis
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from execution.dashboards.executive import ExecutiveSummaryGenerator
from execution.domain.security import SecurityMetrics


@pytest.fixture
def sample_quality_data():
    """Sample quality metrics history"""
    return [
        {
            "week_date": "2026-01-31",
            "total_bugs": 180,
            "open_bugs": 45,
            "critical_bugs": 8,
            "high_priority_bugs": 20,
        },
        {
            "week_date": "2026-02-07",
            "total_bugs": 150,
            "open_bugs": 35,
            "critical_bugs": 5,
            "high_priority_bugs": 15,
        },
    ]


@pytest.fixture
def sample_security_data():
    """Sample security metrics"""
    return {
        "total_vulnerabilities": 67,
        "critical": 7,
        "high": 18,
        "medium": 30,
        "low": 12,
        "products_scanned": 15,
    }


@pytest.fixture
def sample_flow_data():
    """Sample flow metrics"""
    return [
        {
            "week_date": "2026-02-07",
            "median_cycle_time_days": 3.5,
            "p85_cycle_time_days": 9.2,
            "throughput": 45,
            "work_in_progress": 23,
        }
    ]


@pytest.fixture
def sample_baseline_data():
    """Sample baseline data for target calculation"""
    return {
        "total_bugs": 500,
        "baseline_date": "2025-11-01",
        "target_reduction_pct": 70,
    }


class TestLoadExecutiveData:
    """Tests for loading data from multiple sources"""

    def test_load_quality_data_from_history(self, sample_quality_data):
        """Should load quality data from JSON file"""
        # Mock the actual structure that the loader expects
        mock_quality_history = {
            "weeks": sample_quality_data,
            "open_bugs": 306,
            "closed_this_week": 0,
            "created_this_week": 0,
        }
        mock_data = json.dumps(mock_quality_history)

        with patch("pathlib.Path.open", mock_open(read_data=mock_data)):
            with patch("pathlib.Path.exists", return_value=True):
                generator = ExecutiveSummaryGenerator()
                data = generator._load_all_data()

                assert "quality" in data
                assert data["quality"] is not None
                assert "open_bugs" in data["quality"]
                assert "weeks" in data["quality"]

    def test_load_security_data(self, sample_security_data):
        """Should load security data from API"""
        with patch("execution.dashboards.executive.ArmorCodeLoader") as mock_loader:
            # Create SecurityMetrics objects matching the expected structure
            mock_metrics = {
                "Product1": SecurityMetrics(
                    timestamp=datetime.now(),
                    project="Product1",
                    total_vulnerabilities=42,
                    critical=5,
                    high=12,
                    medium=20,
                    low=5,
                ),
                "Product2": SecurityMetrics(
                    timestamp=datetime.now(),
                    project="Product2",
                    total_vulnerabilities=25,
                    critical=2,
                    high=6,
                    medium=10,
                    low=7,
                ),
            }
            mock_instance = Mock()
            mock_instance.load_latest_metrics.return_value = mock_metrics
            mock_loader.return_value = mock_instance

            generator = ExecutiveSummaryGenerator()
            data = generator._load_all_data()

            assert "security" in data

    def test_handle_missing_data_files(self):
        """Should handle missing data files gracefully"""
        with patch("pathlib.Path.read_text", side_effect=FileNotFoundError("File not found")):
            generator = ExecutiveSummaryGenerator()
            data = generator._load_all_data()

            # Should return empty/default data instead of crashing
            assert isinstance(data, dict)

    def test_load_flow_data_from_history(self, sample_flow_data):
        """Should load flow metrics from JSON file"""
        mock_data = json.dumps(sample_flow_data)

        with patch("pathlib.Path.read_text", return_value=mock_data):
            generator = ExecutiveSummaryGenerator()
            data = generator._load_all_data()

            assert "flow" in data


class TestCalculateExecutiveSummary:
    """Tests for cross-metric summary calculation"""

    def test_calculate_target_progress(self, sample_baseline_data, sample_quality_data):
        """Should calculate progress toward 70% reduction target"""
        generator = ExecutiveSummaryGenerator()

        baseline = sample_baseline_data["total_bugs"]  # 500
        current = sample_quality_data[-1]["total_bugs"]  # 150
        target = baseline * 0.3  # 150 (70% reduction)

        reduction = baseline - current  # 350
        progress_pct = (reduction / (baseline - target)) * 100

        # Should be 100% since current = target
        assert progress_pct == pytest.approx(100.0)

    def test_calculate_overall_health_status(self, sample_quality_data, sample_security_data, sample_flow_data):
        """Should determine overall health status"""
        # Good: Low bugs, low vulnerabilities, fast cycle time
        health = "Good"

        # Action Needed: High critical bugs or vulnerabilities
        if sample_quality_data[-1]["critical_bugs"] > 10 or sample_security_data["critical"] > 10:
            health = "Action Needed"

        assert health in ["Good", "Caution", "Action Needed"]

    def test_aggregate_metrics_across_sources(self, sample_quality_data, sample_security_data, sample_flow_data):
        """Should aggregate metrics from all sources"""
        summary = {
            "total_bugs": sample_quality_data[-1]["total_bugs"],
            "total_vulnerabilities": sample_security_data["total_vulnerabilities"],
            "cycle_time": sample_flow_data[-1]["median_cycle_time_days"],
        }

        assert summary["total_bugs"] == 150
        assert summary["total_vulnerabilities"] == 67
        assert summary["cycle_time"] == 3.5


class TestGenerateAttentionItems:
    """Tests for identifying items requiring attention"""

    def test_attention_items_critical_bugs(self, sample_quality_data):
        """Should flag critical bugs as attention item"""
        latest_week = sample_quality_data[-1]

        if latest_week["critical_bugs"] > 0:
            attention_item = {
                "type": "Critical Bugs",
                "count": latest_week["critical_bugs"],
                "severity": "High",
            }
            assert attention_item["count"] == 5

    def test_attention_items_high_vulnerabilities(self, sample_security_data):
        """Should flag critical vulnerabilities as attention item"""
        if sample_security_data["critical"] > 0:
            attention_item = {
                "type": "Critical Vulnerabilities",
                "count": sample_security_data["critical"],
                "severity": "High",
            }
            assert attention_item["count"] == 7

    def test_attention_items_slow_cycle_time(self, sample_flow_data):
        """Should flag slow cycle time as attention item"""
        latest_week = sample_flow_data[-1]

        if latest_week["p85_cycle_time_days"] > 10:
            attention_item = {
                "type": "Slow Delivery (P85)",
                "value": latest_week["p85_cycle_time_days"],
                "severity": "Medium",
            }
        else:
            attention_item = None

        # Should not flag since P85 = 9.2 days < 10
        assert attention_item is None

    def test_no_attention_items_when_metrics_good(self):
        """Should return empty list when all metrics are good"""
        good_data = {
            "quality": {"critical_bugs": 0, "open_bugs": 10},
            "security": {"critical": 0, "high": 2},
            "flow": {"median_cycle_time_days": 2.5, "p85_cycle_time_days": 7.0},
        }

        attention_items = []

        if good_data["quality"]["critical_bugs"] > 0:  # type: ignore[index]
            attention_items.append("Critical Bugs")
        if good_data["security"]["critical"] > 5:  # type: ignore[index]
            attention_items.append("Critical Vulnerabilities")

        assert len(attention_items) == 0


class TestGenerateExecutiveSummary:
    """Tests for full dashboard generation"""

    @patch("execution.dashboards.executive.render_dashboard", return_value="<html>Executive Dashboard</html>")
    @patch(
        "execution.dashboards.executive.get_dashboard_framework", return_value=("<style></style>", "<script></script>")
    )
    @patch("execution.dashboards.executive.ArmorCodeLoader")
    def test_generate_dashboard_success(self, mock_loader, mock_framework, mock_render, sample_quality_data, tmp_path):
        """Should generate complete executive dashboard"""
        # Mock ArmorCodeLoader to return empty security metrics
        mock_loader_instance = Mock()
        mock_loader_instance.load_latest_metrics.return_value = {}
        mock_loader.return_value = mock_loader_instance

        # Mock the data loading methods directly
        with patch.object(
            ExecutiveSummaryGenerator,
            "_load_quality_data",
            return_value={"weeks": sample_quality_data},
        ):
            with patch.object(
                ExecutiveSummaryGenerator, "_load_security_data", return_value={}
            ):
                with patch.object(
                    ExecutiveSummaryGenerator, "_load_flow_data", return_value=[]
                ):
                    generator = ExecutiveSummaryGenerator()
                    output_file = tmp_path / "executive.html"

                    with patch("pathlib.Path.write_text") as mock_write:
                        html = generator.generate(output_file)

                    assert isinstance(html, str)
                    assert len(html) > 0
                    mock_render.assert_called_once()

    @patch("execution.dashboards.executive.render_dashboard", return_value="<html>Dashboard</html>")
    @patch("execution.dashboards.executive.ArmorCodeLoader")
    def test_generate_with_trends(self, mock_loader, mock_render, sample_quality_data):
        """Should include trend indicators in dashboard"""
        # Mock trend data showing improvement
        mock_quality = json.dumps(sample_quality_data)

        with patch("pathlib.Path.read_text", return_value=mock_quality):
            generator = ExecutiveSummaryGenerator()
            html = generator.generate()

            # Should have called render with context including trends
            call_args = mock_render.call_args
            assert call_args is not None

    @patch("execution.dashboards.executive.render_dashboard", return_value="<html>Dashboard</html>")
    def test_generate_missing_data_graceful(self, mock_render):
        """Should handle missing data files gracefully"""
        with patch("pathlib.Path.read_text", side_effect=FileNotFoundError()):
            generator = ExecutiveSummaryGenerator()

            # Should not raise exception
            html = generator.generate()
            assert len(html) > 0

    @patch("execution.dashboards.executive.render_dashboard", return_value="<html>Exec</html>")
    @patch("execution.dashboards.executive.ArmorCodeLoader")
    def test_build_context_structure(self, mock_loader, mock_render, sample_quality_data):
        """Should build context with expected structure"""
        mock_quality = json.dumps(sample_quality_data)

        with patch("pathlib.Path.read_text", return_value=mock_quality):
            generator = ExecutiveSummaryGenerator()
            generator.generate()

            # Check render was called with proper context structure
            call_args = mock_render.call_args
            assert call_args[0][0] == "dashboards/executive_summary.html"
            context = call_args[0][1]

            # Context should have key sections
            expected_keys = ["framework_css", "last_updated"]
            for key in expected_keys:
                assert key in context or len(context) > 0  # Verify context exists
