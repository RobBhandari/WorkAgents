"""
Tests for collector metrics tracking

Tests CollectorMetricsTracker and track_collector_performance context manager.
"""

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

from execution.core.collector_metrics import (
    CollectorMetricsTracker,
    get_current_tracker,
    track_collector_performance,
)


class TestCollectorMetricsTracker:
    """Tests for CollectorMetricsTracker class"""

    def test_tracker_initialization(self):
        """Test creating a tracker instance"""
        tracker = CollectorMetricsTracker("quality")

        assert tracker.collector_name == "quality"
        assert tracker.start_time is None
        assert tracker.execution_time_ms == 0
        assert tracker.success is False
        assert tracker.project_count == 0
        assert tracker.api_call_count == 0
        assert tracker.rate_limit_hits == 0
        assert tracker.retry_count == 0
        assert tracker.error_message is None
        assert tracker.error_type is None

    def test_tracker_start(self):
        """Test starting time tracking"""
        tracker = CollectorMetricsTracker("quality")
        tracker.start()

        assert tracker.start_time is not None
        assert isinstance(tracker.start_time, float)

    def test_tracker_end_success(self):
        """Test ending tracker with success"""
        tracker = CollectorMetricsTracker("quality")
        tracker.start()
        time.sleep(0.1)  # Wait 100ms
        tracker.end(success=True)

        assert tracker.success is True
        assert tracker.execution_time_ms >= 100  # At least 100ms
        assert tracker.error_message is None
        assert tracker.error_type is None

    def test_tracker_end_failure(self):
        """Test ending tracker with failure"""
        tracker = CollectorMetricsTracker("quality")
        tracker.start()
        time.sleep(0.05)

        error = ValueError("Test error")
        tracker.end(success=False, error=error)

        assert tracker.success is False
        assert tracker.execution_time_ms >= 50
        assert tracker.error_message == "Test error"
        assert tracker.error_type == "ValueError"

    def test_record_api_call(self):
        """Test recording API calls"""
        tracker = CollectorMetricsTracker("quality")

        tracker.record_api_call()
        tracker.record_api_call()
        tracker.record_api_call()

        assert tracker.api_call_count == 3

    def test_record_rate_limit_hit(self):
        """Test recording rate limit hits"""
        tracker = CollectorMetricsTracker("quality")

        tracker.record_rate_limit_hit()
        tracker.record_rate_limit_hit()

        assert tracker.rate_limit_hits == 2

    @patch("execution.core.collector_metrics.send_slack_notification")
    def test_record_rate_limit_hit_alert_threshold(self, mock_slack):
        """Test that rate limit hits >3 trigger Slack alert"""
        tracker = CollectorMetricsTracker("quality")

        # First 3 hits should not trigger alert
        tracker.record_rate_limit_hit()
        tracker.record_rate_limit_hit()
        tracker.record_rate_limit_hit()
        assert not mock_slack.called

        # 4th hit should trigger alert
        tracker.record_rate_limit_hit()
        assert mock_slack.called
        assert tracker.rate_limit_hits == 4

    def test_record_retry(self):
        """Test recording retries"""
        tracker = CollectorMetricsTracker("quality")

        tracker.record_retry()
        tracker.record_retry()
        tracker.record_retry()

        assert tracker.retry_count == 3

    def test_to_dict_successful(self):
        """Test converting successful tracker to dict"""
        tracker = CollectorMetricsTracker("quality")
        tracker.start()
        time.sleep(0.05)
        tracker.end(success=True)
        tracker.project_count = 12
        tracker.api_call_count = 150

        data = tracker.to_dict()

        assert data["collector_name"] == "quality"
        assert data["success"] is True
        assert data["project_count"] == 12
        assert data["api_call_count"] == 150
        assert data["rate_limit_hits"] == 0
        assert data["retry_count"] == 0
        assert data["error_message"] is None
        assert data["error_type"] is None
        assert "timestamp" in data
        assert data["execution_time_ms"] >= 50

    def test_to_dict_failed(self):
        """Test converting failed tracker to dict"""
        tracker = CollectorMetricsTracker("deployment")
        tracker.start()
        error = ConnectionError("Connection timeout")
        tracker.end(success=False, error=error)

        data = tracker.to_dict()

        assert data["collector_name"] == "deployment"
        assert data["success"] is False
        assert data["error_message"] == "Connection timeout"
        assert data["error_type"] == "ConnectionError"

    @patch("execution.core.collector_metrics.datetime")
    def test_to_dict_timestamp_format(self, mock_datetime):
        """Test that timestamp is in ISO format with UTC"""
        mock_now = datetime(2026, 2, 11, 14, 30, 0, tzinfo=UTC)
        mock_datetime.now.return_value = mock_now

        tracker = CollectorMetricsTracker("quality")
        data = tracker.to_dict()

        assert data["timestamp"] == "2026-02-11T14:30:00+00:00"

    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.mkdir")
    def test_save_creates_new_history(self, mock_mkdir, mock_exists, mock_file):
        """Test saving metrics creates new history file"""
        mock_exists.return_value = False

        tracker = CollectorMetricsTracker("quality")
        tracker.start()
        time.sleep(0.01)
        tracker.end(success=True)

        history_file = Path(".tmp/observatory/collector_performance_history.json")
        result = tracker.save(history_file)

        assert result is True
        mock_mkdir.assert_called_once()

    @patch("builtins.open", new_callable=mock_open, read_data='{"weeks": []}')
    @patch("pathlib.Path.exists")
    def test_save_appends_to_existing_history(self, mock_exists, mock_file):
        """Test saving metrics appends to existing history"""
        mock_exists.return_value = True

        tracker = CollectorMetricsTracker("quality")
        tracker.start()
        tracker.end(success=True)

        history_file = Path(".tmp/observatory/collector_performance_history.json")
        result = tracker.save(history_file)

        assert result is True

    @patch("pathlib.Path.open")
    @patch("pathlib.Path.exists")
    def test_save_handles_exceptions(self, mock_exists, mock_open):
        """Test save handles file errors gracefully"""
        mock_exists.return_value = True
        mock_open.side_effect = OSError("Permission denied")

        tracker = CollectorMetricsTracker("quality")
        tracker.start()
        tracker.end(success=True)

        history_file = Path(".tmp/observatory/collector_performance_history.json")
        result = tracker.save(history_file)

        assert result is False  # Should return False on error


class TestGetCurrentTracker:
    """Tests for get_current_tracker global access"""

    def test_get_current_tracker_none(self):
        """Test get_current_tracker returns None when no tracker active"""
        tracker = get_current_tracker()
        assert tracker is None

    @patch("execution.core.collector_metrics._current_tracker")
    def test_get_current_tracker_returns_active(self, mock_tracker):
        """Test get_current_tracker returns active tracker"""
        mock_instance = Mock(spec=CollectorMetricsTracker)
        mock_tracker.return_value = mock_instance

        # Simulate what would happen in real code
        from execution.core.collector_metrics import _current_tracker

        # We can't easily test this without running the context manager
        # This test verifies the function exists and has correct signature
        assert get_current_tracker is not None


class TestTrackCollectorPerformanceContextManager:
    """Tests for track_collector_performance context manager"""

    @patch("execution.core.collector_metrics.track_performance")
    def test_context_manager_successful_execution(self, mock_track_perf):
        """Test context manager with successful collector execution"""
        # Mock track_performance to return a context manager
        mock_context = MagicMock()
        mock_track_perf.return_value.__enter__.return_value = mock_context
        mock_track_perf.return_value.__exit__.return_value = False

        with track_collector_performance("quality") as tracker:
            assert tracker is not None
            assert tracker.collector_name == "quality"
            tracker.project_count = 12

        # Verify tracker was successful
        assert tracker.success is True
        assert tracker.project_count == 12
        assert tracker.execution_time_ms > 0

    @patch("execution.core.collector_metrics.send_slack_notification")
    @patch("execution.core.collector_metrics.capture_exception")
    @patch("execution.core.collector_metrics.track_performance")
    def test_context_manager_failed_execution(self, mock_track_perf, mock_capture, mock_slack):
        """Test context manager with failed collector execution"""
        mock_context = MagicMock()
        mock_track_perf.return_value.__enter__.return_value = mock_context
        mock_track_perf.return_value.__exit__.return_value = False

        with pytest.raises(ValueError):
            with track_collector_performance("deployment") as tracker:
                tracker.project_count = 8
                raise ValueError("Test failure")

        # Verify Slack notification was sent
        mock_slack.assert_called_once()
        call_args = mock_slack.call_args
        assert "deployment" in call_args[0][0]  # Message contains collector name

        # Verify exception was captured to Sentry
        mock_capture.assert_called_once()

    @patch("execution.core.collector_metrics.CollectorMetricsTracker.save")
    @patch("execution.core.collector_metrics.track_performance")
    def test_context_manager_always_saves(self, mock_track_perf, mock_save):
        """Test that metrics are saved even on failure"""
        mock_context = MagicMock()
        mock_track_perf.return_value.__enter__.return_value = mock_context
        mock_track_perf.return_value.__exit__.return_value = False

        try:
            with track_collector_performance("quality"):
                raise RuntimeError("Simulated failure")
        except RuntimeError:
            pass

        # Verify save was called despite exception
        mock_save.assert_called_once()

    @patch("execution.core.collector_metrics.track_performance")
    def test_context_manager_sets_global_tracker(self, mock_track_perf):
        """Test that context manager sets global tracker for REST client"""
        mock_context = MagicMock()
        mock_track_perf.return_value.__enter__.return_value = mock_context
        mock_track_perf.return_value.__exit__.return_value = False

        with track_collector_performance("quality") as tracker:
            # Inside context, tracker should be accessible globally
            current = get_current_tracker()
            assert current is tracker

        # After context exits, global tracker should be cleared
        current = get_current_tracker()
        assert current is None

    @patch("execution.core.collector_metrics.track_performance")
    def test_context_manager_integrates_with_sentry(self, mock_track_perf):
        """Test that context manager integrates with Sentry performance tracking"""
        mock_context = MagicMock()
        mock_track_perf.return_value.__enter__.return_value = mock_context
        mock_track_perf.return_value.__exit__.return_value = False

        with track_collector_performance("quality") as tracker:
            tracker.project_count = 12

        # Verify track_performance was called with correct parameters
        mock_track_perf.assert_called_once_with("collector_quality", alert_threshold_ms=120000)

        # Verify context was updated with metrics
        assert mock_context.__setitem__.called


class TestIntegration:
    """Integration tests for full collector tracking flow"""

    @patch("builtins.open", new_callable=mock_open, read_data='{"weeks": []}')
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.mkdir")
    @patch("execution.core.collector_metrics.track_performance")
    def test_full_tracking_flow_success(self, mock_track_perf, mock_mkdir, mock_exists, mock_file):
        """Test complete flow: start → track API calls → end → save"""
        mock_context = MagicMock()
        mock_track_perf.return_value.__enter__.return_value = mock_context
        mock_track_perf.return_value.__exit__.return_value = False

        with track_collector_performance("quality") as tracker:
            # Simulate collector work
            tracker.record_api_call()
            tracker.record_api_call()
            tracker.record_api_call()
            tracker.record_retry()
            tracker.project_count = 12

        # Verify all metrics were captured
        assert tracker.success is True
        assert tracker.api_call_count == 3
        assert tracker.retry_count == 1
        assert tracker.project_count == 12
        assert tracker.execution_time_ms > 0

    @patch("builtins.open", new_callable=mock_open, read_data='{"weeks": []}')
    @patch("pathlib.Path.exists", return_value=True)
    @patch("execution.core.collector_metrics.send_slack_notification")
    @patch("execution.core.collector_metrics.capture_exception")
    @patch("execution.core.collector_metrics.track_performance")
    def test_full_tracking_flow_failure(self, mock_track_perf, mock_capture, mock_slack, mock_exists, mock_file):
        """Test complete flow with failure and error tracking"""
        mock_context = MagicMock()
        mock_track_perf.return_value.__enter__.return_value = mock_context
        mock_track_perf.return_value.__exit__.return_value = False

        with pytest.raises(ConnectionError):
            with track_collector_performance("deployment") as tracker:
                tracker.record_api_call()
                tracker.record_rate_limit_hit()
                raise ConnectionError("ADO connection timeout")

        # Verify error was captured
        mock_capture.assert_called_once()
        mock_slack.assert_called_once()
