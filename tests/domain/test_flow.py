"""
Tests for flow domain models
"""

import pytest
from datetime import datetime
from execution.domain.flow import FlowMetrics


class TestFlowMetrics:
    """Test FlowMetrics domain model"""

    def test_flow_metrics_creation(self):
        """Test creating FlowMetrics instance"""
        metrics = FlowMetrics(
            timestamp=datetime(2026, 2, 7, 10, 0, 0),
            project="TestApp",
            lead_time_p50=7.5,
            lead_time_p85=15.2,
            lead_time_p95=25.8,
            cycle_time_p50=4.2,
            cycle_time_p85=8.5,
            cycle_time_p95=14.3,
            wip_count=25,
            aging_items=5,
            throughput=12,
        )

        assert metrics.project == "TestApp"
        assert metrics.lead_time_p50 == 7.5
        assert metrics.wip_count == 25
        assert metrics.throughput == 12

    def test_has_lead_time_data_true(self):
        """Test has_lead_time_data when data exists"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", lead_time_p50=10.0)
        assert metrics.has_lead_time_data is True

    def test_has_lead_time_data_false(self):
        """Test has_lead_time_data when data is None"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", lead_time_p50=None)
        assert metrics.has_lead_time_data is False

    def test_has_cycle_time_data_true(self):
        """Test has_cycle_time_data when data exists"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", cycle_time_p50=5.0)
        assert metrics.has_cycle_time_data is True

    def test_has_cycle_time_data_false(self):
        """Test has_cycle_time_data when data is None"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", cycle_time_p50=None)
        assert metrics.has_cycle_time_data is False

    def test_lead_time_variability_normal(self):
        """Test lead_time_variability calculation"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", lead_time_p50=10.0, lead_time_p95=25.0)
        assert metrics.lead_time_variability() == 2.5

    def test_lead_time_variability_no_data(self):
        """Test lead_time_variability when no data"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", lead_time_p50=None)
        assert metrics.lead_time_variability() is None

    def test_lead_time_variability_zero_p50(self):
        """Test lead_time_variability when P50 is zero"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", lead_time_p50=0.0, lead_time_p95=10.0)
        assert metrics.lead_time_variability() is None

    def test_lead_time_variability_missing_p95(self):
        """Test lead_time_variability when P95 is None"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", lead_time_p50=10.0, lead_time_p95=None)
        assert metrics.lead_time_variability() is None

    def test_cycle_time_variability_normal(self):
        """Test cycle_time_variability calculation"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", cycle_time_p50=5.0, cycle_time_p95=15.0)
        assert metrics.cycle_time_variability() == 3.0

    def test_cycle_time_variability_no_data(self):
        """Test cycle_time_variability when no data"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", cycle_time_p50=None)
        assert metrics.cycle_time_variability() is None

    def test_cycle_time_variability_zero_p50(self):
        """Test cycle_time_variability when P50 is zero"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", cycle_time_p50=0.0, cycle_time_p95=10.0)
        assert metrics.cycle_time_variability() is None

    def test_has_high_variability_true(self):
        """Test has_high_variability when above threshold"""
        metrics = FlowMetrics(
            timestamp=datetime.now(), project="Test", lead_time_p50=10.0, lead_time_p95=40.0  # 4x variability
        )
        assert metrics.has_high_variability(threshold=3.0) is True

    def test_has_high_variability_false(self):
        """Test has_high_variability when below threshold"""
        metrics = FlowMetrics(
            timestamp=datetime.now(), project="Test", lead_time_p50=10.0, lead_time_p95=20.0  # 2x variability
        )
        assert metrics.has_high_variability(threshold=3.0) is False

    def test_has_high_variability_no_data(self):
        """Test has_high_variability when no data"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", lead_time_p50=None)
        assert metrics.has_high_variability() is False

    def test_aging_percentage_normal(self):
        """Test aging_percentage calculation"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", wip_count=100, aging_items=25)
        assert metrics.aging_percentage() == 25.0

    def test_aging_percentage_zero_wip(self):
        """Test aging_percentage when no WIP"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", wip_count=0, aging_items=0)
        assert metrics.aging_percentage() is None

    def test_has_aging_issues_true(self):
        """Test has_aging_issues when above threshold"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", wip_count=100, aging_items=30)  # 30%
        assert metrics.has_aging_issues(threshold_percent=20.0) is True

    def test_has_aging_issues_false(self):
        """Test has_aging_issues when below threshold"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", wip_count=100, aging_items=10)  # 10%
        assert metrics.has_aging_issues(threshold_percent=20.0) is False

    def test_has_aging_issues_no_wip(self):
        """Test has_aging_issues when no WIP"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="Test", wip_count=0, aging_items=0)
        assert metrics.has_aging_issues() is False

    def test_has_flow_issues_multiple_problems(self):
        """Test has_flow_issues with multiple issues"""
        metrics = FlowMetrics(
            timestamp=datetime.now(),
            project="Test",
            lead_time_p50=20.0,  # >14 days
            lead_time_p95=80.0,  # 4x variability
            wip_count=100,
            aging_items=30,  # 30% aging
        )
        assert metrics.has_flow_issues() is True

    def test_has_flow_issues_variability_only(self):
        """Test has_flow_issues with high variability only"""
        metrics = FlowMetrics(
            timestamp=datetime.now(),
            project="Test",
            lead_time_p50=10.0,
            lead_time_p95=40.0,  # 4x variability
            wip_count=100,
            aging_items=5,  # 5% aging - OK
        )
        assert metrics.has_flow_issues() is True

    def test_has_flow_issues_aging_only(self):
        """Test has_flow_issues with aging issues only"""
        metrics = FlowMetrics(
            timestamp=datetime.now(),
            project="Test",
            lead_time_p50=10.0,
            lead_time_p95=20.0,  # 2x variability - OK
            wip_count=100,
            aging_items=30,  # 30% aging
        )
        assert metrics.has_flow_issues() is True

    def test_has_flow_issues_slow_delivery(self):
        """Test has_flow_issues with slow delivery"""
        metrics = FlowMetrics(
            timestamp=datetime.now(),
            project="Test",
            lead_time_p50=20.0,  # >14 days
            lead_time_p95=40.0,  # 2x variability - OK
            wip_count=100,
            aging_items=5,  # 5% aging - OK
        )
        assert metrics.has_flow_issues() is True

    def test_has_flow_issues_false(self):
        """Test has_flow_issues when no issues"""
        metrics = FlowMetrics(
            timestamp=datetime.now(),
            project="Test",
            lead_time_p50=7.0,  # <14 days
            lead_time_p95=14.0,  # 2x variability - OK
            wip_count=100,
            aging_items=10,  # 10% aging - OK
        )
        assert metrics.has_flow_issues() is False

    def test_str_representation(self):
        """Test string representation"""
        metrics = FlowMetrics(timestamp=datetime.now(), project="MyApp", lead_time_p50=7.5, wip_count=25, aging_items=5)
        result = str(metrics)
        assert "MyApp" in result
        assert "7.5" in result
        assert "wip=25" in result
        assert "aging=5" in result
