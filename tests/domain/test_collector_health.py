"""
Tests for collector health domain models

Tests CollectorPerformanceMetrics, CollectorHealthSummary, and from_json factory.
"""

from datetime import datetime

import pytest

from execution.domain.collector_health import (
    CollectorHealthSummary,
    CollectorPerformanceMetrics,
    from_json,
)


class TestCollectorPerformanceMetrics:
    """Tests for CollectorPerformanceMetrics domain model"""

    def test_metrics_creation(self, sample_collector_metrics):
        """Test creating CollectorPerformanceMetrics instance"""
        metrics = sample_collector_metrics
        assert metrics.collector_name == "quality"
        assert metrics.execution_time_ms == 45230.5
        assert metrics.success is True
        assert metrics.project_count == 12
        assert metrics.api_call_count == 150
        assert metrics.rate_limit_hits == 0
        assert metrics.retry_count == 2
        assert metrics.error_message is None
        assert metrics.error_type is None

    def test_status_good(self, sample_collector_metrics):
        """Test status property for fast successful collector (<60s)"""
        assert sample_collector_metrics.status == "Good"

    def test_status_caution(self, sample_timestamp):
        """Test status property for slow collector (60-120s)"""
        metrics = CollectorPerformanceMetrics(
            timestamp=sample_timestamp,
            collector_name="deployment",
            execution_time_ms=75000,  # 75 seconds
            success=True,
            project_count=10,
            api_call_count=100,
            rate_limit_hits=0,
            retry_count=0,
        )
        assert metrics.status == "Caution"

    def test_status_action_needed_slow(self, sample_timestamp):
        """Test status property for very slow collector (>120s)"""
        metrics = CollectorPerformanceMetrics(
            timestamp=sample_timestamp,
            collector_name="risk",
            execution_time_ms=135000,  # 135 seconds
            success=True,
            project_count=10,
            api_call_count=200,
            rate_limit_hits=0,
            retry_count=0,
        )
        assert metrics.status == "Action Needed"

    def test_status_failed(self, sample_failed_collector_metrics):
        """Test status property for failed collector"""
        assert sample_failed_collector_metrics.status == "Failed"

    def test_status_class_good(self, sample_collector_metrics):
        """Test status_class property for good status"""
        assert sample_collector_metrics.status_class == "good"

    def test_status_class_caution(self, sample_timestamp):
        """Test status_class property for caution status"""
        metrics = CollectorPerformanceMetrics(
            timestamp=sample_timestamp,
            collector_name="deployment",
            execution_time_ms=75000,
            success=True,
            project_count=10,
            api_call_count=100,
            rate_limit_hits=0,
            retry_count=0,
        )
        assert metrics.status_class == "caution"

    def test_status_class_action(self, sample_failed_collector_metrics):
        """Test status_class property for action needed/failed status"""
        assert sample_failed_collector_metrics.status_class == "action"

    def test_execution_time_seconds(self, sample_collector_metrics):
        """Test execution_time_seconds property conversion"""
        assert sample_collector_metrics.execution_time_seconds == pytest.approx(45.2305)

    def test_execution_time_seconds_precision(self, sample_timestamp):
        """Test execution_time_seconds with various precision values"""
        metrics = CollectorPerformanceMetrics(
            timestamp=sample_timestamp,
            collector_name="quality",
            execution_time_ms=1234.56789,
            success=True,
            project_count=5,
            api_call_count=50,
            rate_limit_hits=0,
            retry_count=0,
        )
        assert metrics.execution_time_seconds == pytest.approx(1.23456789)

    def test_failed_collector_has_error_details(self, sample_failed_collector_metrics):
        """Test that failed collectors capture error information"""
        assert sample_failed_collector_metrics.success is False
        assert sample_failed_collector_metrics.error_message == "Connection timeout"
        assert sample_failed_collector_metrics.error_type == "TimeoutError"

    def test_timestamp_inheritance(self, sample_collector_metrics):
        """Test that timestamp is inherited from MetricSnapshot"""
        assert isinstance(sample_collector_metrics.timestamp, datetime)


class TestCollectorHealthSummary:
    """Tests for CollectorHealthSummary aggregation model"""

    def test_summary_creation(self, sample_collector_health_summary):
        """Test creating CollectorHealthSummary instance"""
        summary = sample_collector_health_summary
        assert summary.total_runs == 7
        assert summary.successful_runs == 6
        assert summary.failed_runs == 1
        assert summary.avg_execution_time_ms == pytest.approx(52340.5)
        assert summary.total_api_calls == 850
        assert summary.total_rate_limit_hits == 0
        assert summary.slowest_collector == "risk"
        assert summary.slowest_collector_time_ms == pytest.approx(89234.2)

    def test_success_rate_pct(self, sample_collector_health_summary):
        """Test success_rate_pct property calculation"""
        # 6 successful out of 7 total = 85.71%
        assert sample_collector_health_summary.success_rate_pct == pytest.approx(85.71428571)

    def test_success_rate_pct_perfect(self):
        """Test success_rate_pct with 100% success"""
        summary = CollectorHealthSummary(
            total_runs=7,
            successful_runs=7,
            failed_runs=0,
            avg_execution_time_ms=50000,
            total_api_calls=500,
            total_rate_limit_hits=0,
            slowest_collector="risk",
            slowest_collector_time_ms=80000,
        )
        assert summary.success_rate_pct == pytest.approx(100.0)

    def test_success_rate_pct_zero_runs(self):
        """Test success_rate_pct with zero runs (edge case)"""
        summary = CollectorHealthSummary(
            total_runs=0,
            successful_runs=0,
            failed_runs=0,
            avg_execution_time_ms=0,
            total_api_calls=0,
            total_rate_limit_hits=0,
            slowest_collector=None,
            slowest_collector_time_ms=None,
        )
        assert summary.success_rate_pct == 0.0

    def test_failure_rate_pct(self, sample_collector_health_summary):
        """Test failure_rate_pct property calculation"""
        # 1 failed out of 7 total = 14.29%
        assert sample_collector_health_summary.failure_rate_pct == pytest.approx(14.28571429)

    def test_overall_status_good(self):
        """Test overall_status when all metrics are healthy"""
        summary = CollectorHealthSummary(
            total_runs=7,
            successful_runs=7,
            failed_runs=0,
            avg_execution_time_ms=45000,  # <60s
            total_api_calls=500,
            total_rate_limit_hits=0,  # No rate limits
            slowest_collector="quality",
            slowest_collector_time_ms=50000,
        )
        assert summary.overall_status == "Good"

    def test_overall_status_caution_failures(self):
        """Test overall_status with minor failures (>0% but ≤10%)"""
        summary = CollectorHealthSummary(
            total_runs=20,
            successful_runs=19,
            failed_runs=1,  # 5% failure rate
            avg_execution_time_ms=45000,
            total_api_calls=500,
            total_rate_limit_hits=0,
            slowest_collector="quality",
            slowest_collector_time_ms=50000,
        )
        assert summary.overall_status == "Caution"

    def test_overall_status_caution_slow(self):
        """Test overall_status with slow execution (60-120s avg)"""
        summary = CollectorHealthSummary(
            total_runs=7,
            successful_runs=7,
            failed_runs=0,
            avg_execution_time_ms=75000,  # 75s average
            total_api_calls=500,
            total_rate_limit_hits=0,
            slowest_collector="risk",
            slowest_collector_time_ms=90000,
        )
        assert summary.overall_status == "Caution"

    def test_overall_status_action_high_failure_rate(self):
        """Test overall_status with high failure rate (>10%)"""
        summary = CollectorHealthSummary(
            total_runs=10,
            successful_runs=8,
            failed_runs=2,  # 20% failure rate
            avg_execution_time_ms=45000,
            total_api_calls=500,
            total_rate_limit_hits=0,
            slowest_collector="quality",
            slowest_collector_time_ms=50000,
        )
        assert summary.overall_status == "Action Needed"

    def test_overall_status_action_very_slow(self):
        """Test overall_status with very slow execution (>120s avg)"""
        summary = CollectorHealthSummary(
            total_runs=7,
            successful_runs=7,
            failed_runs=0,
            avg_execution_time_ms=135000,  # 135s average
            total_api_calls=500,
            total_rate_limit_hits=0,
            slowest_collector="risk",
            slowest_collector_time_ms=150000,
        )
        assert summary.overall_status == "Action Needed"

    def test_overall_status_action_rate_limits(self):
        """Test overall_status with rate limit hits"""
        summary = CollectorHealthSummary(
            total_runs=7,
            successful_runs=7,
            failed_runs=0,
            avg_execution_time_ms=45000,
            total_api_calls=500,
            total_rate_limit_hits=5,  # Any rate limits = action needed
            slowest_collector="quality",
            slowest_collector_time_ms=50000,
        )
        assert summary.overall_status == "Action Needed"


class TestFromJsonFactory:
    """Tests for from_json factory method"""

    def test_from_json_successful_collector(self):
        """Test deserializing successful collector metrics from JSON"""
        data = {
            "timestamp": "2026-02-11T14:30:00.123456",
            "collector_name": "quality",
            "execution_time_ms": 45230.5,
            "success": True,
            "project_count": 12,
            "api_call_count": 150,
            "rate_limit_hits": 0,
            "retry_count": 2,
            "error_message": None,
            "error_type": None,
        }

        metrics = from_json(data)

        assert metrics.collector_name == "quality"
        assert metrics.execution_time_ms == pytest.approx(45230.5)
        assert metrics.success is True
        assert metrics.project_count == 12
        assert metrics.api_call_count == 150
        assert metrics.rate_limit_hits == 0
        assert metrics.retry_count == 2
        assert metrics.error_message is None
        assert metrics.error_type is None
        assert isinstance(metrics.timestamp, datetime)

    def test_from_json_failed_collector(self):
        """Test deserializing failed collector metrics from JSON"""
        data = {
            "timestamp": "2026-02-11T14:30:00",
            "collector_name": "deployment",
            "execution_time_ms": 12345.67,
            "success": False,
            "project_count": 8,
            "api_call_count": 75,
            "rate_limit_hits": 1,
            "retry_count": 3,
            "error_message": "Connection timeout",
            "error_type": "TimeoutError",
        }

        metrics = from_json(data)

        assert metrics.collector_name == "deployment"
        assert metrics.success is False
        assert metrics.error_message == "Connection timeout"
        assert metrics.error_type == "TimeoutError"

    def test_from_json_with_rate_limits(self):
        """Test deserializing metrics with rate limit hits"""
        data = {
            "timestamp": "2026-02-11T14:30:00",
            "collector_name": "risk",
            "execution_time_ms": 89234.2,
            "success": True,
            "project_count": 15,
            "api_call_count": 500,
            "rate_limit_hits": 3,
            "retry_count": 5,
            "error_message": None,
            "error_type": None,
        }

        metrics = from_json(data)

        assert metrics.rate_limit_hits == 3
        assert metrics.retry_count == 5

    def test_from_json_timestamp_parsing(self):
        """Test that timestamp is correctly parsed as datetime"""
        data = {
            "timestamp": "2026-02-11T14:30:00",
            "collector_name": "quality",
            "execution_time_ms": 1000.0,
            "success": True,
            "project_count": 5,
            "api_call_count": 50,
            "rate_limit_hits": 0,
            "retry_count": 0,
        }

        metrics = from_json(data)

        assert isinstance(metrics.timestamp, datetime)
        assert metrics.timestamp.year == 2026
        assert metrics.timestamp.month == 2
        assert metrics.timestamp.day == 11
        assert metrics.timestamp.hour == 14
        assert metrics.timestamp.minute == 30
