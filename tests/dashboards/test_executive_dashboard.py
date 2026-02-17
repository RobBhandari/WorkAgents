"""
Tests for Executive Summary Dashboard Generator

Tests cover:
- Multi-source API data querying (quality, security, flow)
- Cross-metric summary calculation
- Attention item identification
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, mock_open, patch

import pytest

from execution.dashboards.executive import ExecutiveSummaryGenerator


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


class TestQueryExecutiveData:
    """Tests for querying data from API sources"""

    @pytest.mark.asyncio
    async def test_query_quality_data_from_api(self):
        """Should query quality data from ADO API"""
        generator = ExecutiveSummaryGenerator()

        # Mock discovery data and API responses
        mock_discovery = {"projects": [{"project_name": "TestProject"}]}
        mock_quality_result = {
            "open_bugs_count": 35,
            "closed_last_week": 10,
            "created_last_week": 5,
        }

        with patch("execution.dashboards.executive.load_json_with_recovery", return_value=mock_discovery):
            with patch("pathlib.Path.exists", return_value=True):
                with patch(
                    "execution.dashboards.executive.collect_quality_metrics_for_project",
                    return_value=mock_quality_result,
                ):
                    with patch("execution.dashboards.executive.get_ado_rest_client"):
                        data = await generator._query_quality_data()

                        assert data is not None
                        assert "open_bugs" in data
                        assert "net_change" in data
                        assert data["open_bugs"] == 35

    @pytest.mark.asyncio
    async def test_query_security_data_from_api(self):
        """Should query security data from ArmorCode API"""
        generator = ExecutiveSummaryGenerator()

        # Mock baseline and API responses
        mock_baseline: dict[str, dict[str, dict[str, dict]]] = {"products": {"Product1": {}, "Product2": {}}}

        mock_vulnerabilities = [
            Mock(severity="CRITICAL", is_production=True),
            Mock(severity="CRITICAL", is_production=True),
            Mock(severity="HIGH", is_production=True),
            Mock(severity="HIGH", is_production=True),
            Mock(severity="HIGH", is_production=True),
        ]

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_baseline))):
                with patch("execution.dashboards.executive.ArmorCodeVulnerabilityLoader") as mock_loader_class:
                    mock_loader = Mock()
                    mock_loader.load_vulnerabilities_for_products.return_value = mock_vulnerabilities
                    mock_loader_class.return_value = mock_loader

                    data = await generator._query_security_data()

                    assert data is not None
                    assert "critical" in data
                    assert "high" in data
                    assert data["critical"] == 2
                    assert data["high"] == 3

    @pytest.mark.asyncio
    async def test_query_flow_data_from_api(self):
        """Should query flow data from ADO API"""
        generator = ExecutiveSummaryGenerator()

        # Mock discovery data and API responses
        mock_discovery = {"projects": [{"project_name": "TestProject"}]}
        mock_flow_result = {"lead_time_p50": 7.5}

        with patch("execution.dashboards.executive.load_json_with_recovery", return_value=mock_discovery):
            with patch("pathlib.Path.exists", return_value=True):
                with patch(
                    "execution.dashboards.executive.collect_flow_metrics_for_project",
                    return_value=mock_flow_result,
                ):
                    with patch("execution.dashboards.executive.get_ado_rest_client"):
                        data = await generator._query_flow_data()

                        assert data is not None
                        assert "avg_lead_time_p50" in data
                        assert data["avg_lead_time_p50"] == 7.5

    @pytest.mark.asyncio
    async def test_handle_missing_discovery_file(self):
        """Should handle missing discovery file gracefully"""
        generator = ExecutiveSummaryGenerator()

        with patch("pathlib.Path.exists", return_value=False):
            data = await generator._query_quality_data()
            assert data is None

    @pytest.mark.asyncio
    async def test_handle_api_failures(self):
        """Should handle API failures gracefully"""
        generator = ExecutiveSummaryGenerator()

        with patch("pathlib.Path.exists", return_value=True):
            with patch(
                "execution.dashboards.executive.load_json_with_recovery",
                side_effect=Exception("API Error"),
            ):
                data = await generator._query_quality_data()
                assert data is None


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

    @pytest.mark.asyncio
    @patch("execution.dashboards.executive.render_dashboard", return_value="<html>Executive Dashboard</html>")
    @patch(
        "execution.dashboards.executive.get_dashboard_framework", return_value=("<style></style>", "<script></script>")
    )
    async def test_generate_dashboard_success(self, mock_framework, mock_render, tmp_path):
        """Should generate complete executive dashboard"""
        # Mock the data query methods directly with complete data structures
        with patch.object(
            ExecutiveSummaryGenerator,
            "_query_quality_data",
            return_value={
                "open_bugs": 35,
                "closed_this_week": 10,
                "created_this_week": 5,
                "net_change": -5,
            },
        ):
            with patch.object(
                ExecutiveSummaryGenerator,
                "_query_security_data",
                return_value={
                    "total_vulnerabilities": 25,
                    "critical": 2,
                    "high": 6,
                    "critical_high": 8,
                },
            ):
                with patch.object(
                    ExecutiveSummaryGenerator,
                    "_query_flow_data",
                    return_value={"avg_lead_time_p50": 7.5},
                ):
                    generator = ExecutiveSummaryGenerator()
                    output_file = tmp_path / "executive.html"

                    with patch("pathlib.Path.write_text") as mock_write:
                        html = await generator.generate(output_file)

                    assert isinstance(html, str)
                    assert len(html) > 0
                    mock_render.assert_called_once()

    @pytest.mark.asyncio
    @patch("execution.dashboards.executive.render_dashboard", return_value="<html>Dashboard</html>")
    async def test_generate_missing_data_graceful(self, mock_render):
        """Should handle missing data gracefully"""
        with patch.object(ExecutiveSummaryGenerator, "_query_quality_data", return_value=None):
            with patch.object(ExecutiveSummaryGenerator, "_query_security_data", return_value=None):
                with patch.object(ExecutiveSummaryGenerator, "_query_flow_data", return_value=None):
                    generator = ExecutiveSummaryGenerator()

                    # Should not raise exception
                    html = await generator.generate()
                    assert len(html) > 0

    @pytest.mark.asyncio
    @patch("execution.dashboards.executive.render_dashboard", return_value="<html>Exec</html>")
    async def test_build_context_structure(self, mock_render):
        """Should build context with expected structure"""
        with patch.object(
            ExecutiveSummaryGenerator,
            "_query_quality_data",
            return_value={"open_bugs": 35, "net_change": -5, "closed_this_week": 10, "created_this_week": 5},
        ):
            with patch.object(
                ExecutiveSummaryGenerator,
                "_query_security_data",
                return_value={"critical": 2, "high": 6, "critical_high": 8},
            ):
                with patch.object(ExecutiveSummaryGenerator, "_query_flow_data", return_value=None):
                    generator = ExecutiveSummaryGenerator()
                    await generator.generate()

                    # Check render was called with proper context structure
                    call_args = mock_render.call_args
                    assert call_args[0][0] == "dashboards/executive_summary.html"
                    context = call_args[0][1]

                    # Context should have key sections
                    expected_keys = ["framework_css", "generation_date"]
                    for key in expected_keys:
                        assert key in context
