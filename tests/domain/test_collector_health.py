"""
Tests for execution/domain/collector_health.py

Covers CollectorPerformanceMetrics and CollectorHealthSummary domain models.
"""

from datetime import datetime

import pytest

from execution.domain.collector_health import (
    CollectorHealthSummary,
    CollectorPerformanceMetrics,
    from_json,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_TIMESTAMP = "2026-02-11T14:30:00.123456"


@pytest.fixture
def sample_json() -> dict:
    """Minimal valid JSON dict for from_json()."""
    return {
        "timestamp": SAMPLE_TIMESTAMP,
        "collector_name": "quality",
        "execution_time_ms": 45230.5,
        "success": True,
        "project_count": 12,
        "api_call_count": 150,
        "rate_limit_hits": 0,
        "retry_count": 2,
    }


@pytest.fixture
def good_metrics() -> CollectorPerformanceMetrics:
    """Successful run under 60s → status Good."""
    return CollectorPerformanceMetrics(
        timestamp=datetime.now(),
        collector_name="quality",
        execution_time_ms=30000,
        success=True,
        project_count=5,
        api_call_count=50,
        rate_limit_hits=0,
        retry_count=0,
    )


# ---------------------------------------------------------------------------
# from_json
# ---------------------------------------------------------------------------


class TestFromJson:
    def test_basic_deserialization(self, sample_json: dict) -> None:
        metrics = from_json(sample_json)
        assert metrics.collector_name == "quality"
        assert metrics.execution_time_ms == 45230.5
        assert metrics.success is True
        assert metrics.project_count == 12
        assert metrics.api_call_count == 150
        assert metrics.rate_limit_hits == 0
        assert metrics.retry_count == 2

    def test_timestamp_parsed_correctly(self, sample_json: dict) -> None:
        metrics = from_json(sample_json)
        assert isinstance(metrics.timestamp, datetime)
        assert metrics.timestamp.year == 2026

    def test_optional_error_fields_default_to_none(self, sample_json: dict) -> None:
        metrics = from_json(sample_json)
        assert metrics.error_message is None
        assert metrics.error_type is None

    def test_optional_error_fields_populated_when_present(self, sample_json: dict) -> None:
        sample_json["error_message"] = "Connection refused"
        sample_json["error_type"] = "ConnectionError"
        metrics = from_json(sample_json)
        assert metrics.error_message == "Connection refused"
        assert metrics.error_type == "ConnectionError"


# ---------------------------------------------------------------------------
# CollectorPerformanceMetrics.status
# ---------------------------------------------------------------------------


class TestCollectorPerformanceMetricsStatus:
    def test_failed_run_returns_failed(self) -> None:
        metrics = CollectorPerformanceMetrics(
            timestamp=datetime.now(),
            collector_name="quality",
            execution_time_ms=1000,
            success=False,
            project_count=0,
            api_call_count=0,
            rate_limit_hits=0,
            retry_count=0,
            error_message="Timeout",
        )
        assert metrics.status == "Failed"

    def test_fast_successful_run_returns_good(self, good_metrics: CollectorPerformanceMetrics) -> None:
        assert good_metrics.status == "Good"

    def test_60_to_120_seconds_returns_caution(self) -> None:
        metrics = CollectorPerformanceMetrics(
            timestamp=datetime.now(),
            collector_name="deployment",
            execution_time_ms=90000,
            success=True,
            project_count=5,
            api_call_count=80,
            rate_limit_hits=0,
            retry_count=1,
        )
        assert metrics.status == "Caution"

    def test_over_120_seconds_returns_action_needed(self) -> None:
        metrics = CollectorPerformanceMetrics(
            timestamp=datetime.now(),
            collector_name="risk",
            execution_time_ms=150000,
            success=True,
            project_count=5,
            api_call_count=200,
            rate_limit_hits=3,
            retry_count=5,
        )
        assert metrics.status == "Action Needed"

    def test_failed_overrides_execution_time(self) -> None:
        """Failed status takes priority even when execution is fast."""
        metrics = CollectorPerformanceMetrics(
            timestamp=datetime.now(),
            collector_name="security",
            execution_time_ms=100,
            success=False,
            project_count=0,
            api_call_count=1,
            rate_limit_hits=0,
            retry_count=0,
        )
        assert metrics.status == "Failed"


# ---------------------------------------------------------------------------
# CollectorPerformanceMetrics.status_class
# ---------------------------------------------------------------------------


class TestCollectorPerformanceMetricsStatusClass:
    def test_good_maps_to_good(self, good_metrics: CollectorPerformanceMetrics) -> None:
        assert good_metrics.status_class == "good"

    def test_caution_maps_to_caution(self) -> None:
        metrics = CollectorPerformanceMetrics(
            timestamp=datetime.now(),
            collector_name="flow",
            execution_time_ms=75000,
            success=True,
            project_count=3,
            api_call_count=30,
            rate_limit_hits=0,
            retry_count=0,
        )
        assert metrics.status_class == "caution"

    def test_action_needed_maps_to_action(self) -> None:
        metrics = CollectorPerformanceMetrics(
            timestamp=datetime.now(),
            collector_name="flow",
            execution_time_ms=200000,
            success=True,
            project_count=3,
            api_call_count=30,
            rate_limit_hits=0,
            retry_count=0,
        )
        assert metrics.status_class == "action"

    def test_failed_maps_to_action(self) -> None:
        metrics = CollectorPerformanceMetrics(
            timestamp=datetime.now(),
            collector_name="flow",
            execution_time_ms=1000,
            success=False,
            project_count=0,
            api_call_count=0,
            rate_limit_hits=0,
            retry_count=0,
        )
        assert metrics.status_class == "action"


# ---------------------------------------------------------------------------
# CollectorPerformanceMetrics.execution_time_seconds
# ---------------------------------------------------------------------------


class TestExecutionTimeSeconds:
    def test_converts_ms_to_seconds(self, good_metrics: CollectorPerformanceMetrics) -> None:
        assert good_metrics.execution_time_seconds == 30.0

    def test_fractional_milliseconds(self, sample_json: dict) -> None:
        metrics = from_json(sample_json)
        assert abs(metrics.execution_time_seconds - 45.2305) < 0.0001


# ---------------------------------------------------------------------------
# CollectorHealthSummary
# ---------------------------------------------------------------------------


class TestCollectorHealthSummary:
    def _make_summary(
        self,
        total: int = 7,
        successful: int = 7,
        failed: int = 0,
        avg_ms: float = 40000,
        rate_limits: int = 0,
    ) -> CollectorHealthSummary:
        return CollectorHealthSummary(
            total_runs=total,
            successful_runs=successful,
            failed_runs=failed,
            avg_execution_time_ms=avg_ms,
            total_api_calls=500,
            total_rate_limit_hits=rate_limits,
            slowest_collector="risk",
            slowest_collector_time_ms=avg_ms,
        )

    def test_success_rate_all_pass(self) -> None:
        s = self._make_summary(total=7, successful=7)
        assert s.success_rate_pct == pytest.approx(100.0)

    def test_success_rate_partial(self) -> None:
        s = self._make_summary(total=7, successful=6, failed=1)
        assert s.success_rate_pct == pytest.approx(6 / 7 * 100)

    def test_success_rate_zero_runs(self) -> None:
        s = self._make_summary(total=0, successful=0, failed=0)
        assert s.success_rate_pct == 0.0

    def test_failure_rate_complements_success(self) -> None:
        s = self._make_summary(total=4, successful=3, failed=1)
        assert s.failure_rate_pct == pytest.approx(100 - s.success_rate_pct)

    def test_overall_status_good_all_pass_fast(self) -> None:
        s = self._make_summary(total=7, successful=7, avg_ms=40000, rate_limits=0)
        assert s.overall_status == "Good"

    def test_overall_status_caution_one_failure(self) -> None:
        s = self._make_summary(total=10, successful=9, failed=1, avg_ms=40000)
        assert s.overall_status == "Caution"

    def test_overall_status_caution_slow_avg(self) -> None:
        s = self._make_summary(total=7, successful=7, avg_ms=70000, rate_limits=0)
        assert s.overall_status == "Caution"

    def test_overall_status_action_needed_high_failure_rate(self) -> None:
        # >10% failure rate: 2/7 ≈ 28%
        s = self._make_summary(total=7, successful=5, failed=2, avg_ms=40000)
        assert s.overall_status == "Action Needed"

    def test_overall_status_action_needed_rate_limits(self) -> None:
        s = self._make_summary(total=7, successful=7, avg_ms=40000, rate_limits=1)
        assert s.overall_status == "Action Needed"

    def test_overall_status_action_needed_very_slow(self) -> None:
        s = self._make_summary(total=7, successful=7, avg_ms=150000, rate_limits=0)
        assert s.overall_status == "Action Needed"
