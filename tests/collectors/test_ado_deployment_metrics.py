"""
Tests for ADO Deployment Metrics Collector

Tests cover:
- query_builds() - Build pipeline queries with mocked Azure DevOps responses
- calculate_deployment_frequency() - DORA deployment frequency metrics
- calculate_build_success_rate() - Build success rate calculations
- calculate_build_duration() - Build duration statistics
- calculate_lead_time_for_changes() - Lead time from commit to deployment
- save_deployment_metrics() - History file persistence
- Error handling for network issues, invalid data, API failures
"""

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from execution.collectors.ado_deployment_metrics import (
    _calculate_single_build_lead_time,
    _get_commit_timestamp_from_build,
    calculate_build_duration,
    calculate_build_success_rate,
    calculate_deployment_frequency,
    calculate_lead_time_for_changes,
    collect_deployment_metrics_for_project,
    query_builds,
    save_deployment_metrics,
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def create_azure_error(message: str):
    """
    Create a proper AzureDevOpsServiceError instance.

    AzureDevOpsServiceError requires a wrapped exception object with specific attributes.
    """
    from azure.devops.exceptions import AzureDevOpsServiceError

    wrapped_exception = Mock()
    wrapped_exception.message = message
    wrapped_exception.inner_exception = None
    wrapped_exception.exception_id = None
    wrapped_exception.type_name = "TestError"
    wrapped_exception.type_key = "TestError"
    wrapped_exception.error_code = 0
    wrapped_exception.event_id = 0
    return AzureDevOpsServiceError(wrapped_exception)


# ============================================================================
# FIXTURES - Mock Build Data
# ============================================================================


@pytest.fixture
def mock_build_successful():
    """Create a mock successful build object"""
    build = Mock()
    build.id = 12345
    build.build_number = "20240210.1"
    build.definition = Mock()
    build.definition.id = 101
    build.definition.name = "CI Pipeline"
    build.status = "completed"
    build.result = "succeeded"
    build.start_time = datetime(2026, 2, 10, 9, 0, 0, tzinfo=UTC)
    build.finish_time = datetime(2026, 2, 10, 9, 15, 0, tzinfo=UTC)
    build.source_branch = "refs/heads/main"
    build.source_version = "abc123def456"
    build.requested_for = Mock()
    build.requested_for.display_name = "John Doe"
    return build


@pytest.fixture
def mock_build_failed():
    """Create a mock failed build object"""
    build = Mock()
    build.id = 12346
    build.build_number = "20240210.2"
    build.definition = Mock()
    build.definition.id = 101
    build.definition.name = "CI Pipeline"
    build.status = "completed"
    build.result = "failed"
    build.start_time = datetime(2026, 2, 10, 10, 0, 0, tzinfo=UTC)
    build.finish_time = datetime(2026, 2, 10, 10, 30, 0, tzinfo=UTC)
    build.source_branch = "refs/heads/feature/bug-fix"
    build.source_version = "def789ghi012"
    build.requested_for = Mock()
    build.requested_for.display_name = "Jane Smith"
    return build


@pytest.fixture
def mock_build_in_progress():
    """Create a mock in-progress build (no finish_time)"""
    build = Mock()
    build.id = 12347
    build.build_number = "20240210.3"
    build.definition = Mock()
    build.definition.id = 102
    build.definition.name = "Release Pipeline"
    build.status = "inProgress"
    build.result = None
    build.start_time = datetime(2026, 2, 10, 11, 0, 0, tzinfo=UTC)
    build.finish_time = None
    build.source_branch = "refs/heads/main"
    build.source_version = "ghi345jkl678"
    build.requested_for = Mock()
    build.requested_for.display_name = "CI Bot"
    return build


@pytest.fixture
def mock_build_canceled():
    """Create a mock canceled build"""
    build = Mock()
    build.id = 12348
    build.build_number = "20240210.4"
    build.definition = Mock()
    build.definition.id = 101
    build.definition.name = "CI Pipeline"
    build.status = "completed"
    build.result = "canceled"
    build.start_time = datetime(2026, 2, 10, 12, 0, 0, tzinfo=UTC)
    build.finish_time = datetime(2026, 2, 10, 12, 5, 0, tzinfo=UTC)
    build.source_branch = "refs/heads/experimental"
    build.source_version = "jkl901mno234"
    build.requested_for = Mock()
    build.requested_for.display_name = "Admin User"
    return build


@pytest.fixture
def mock_build_partial_success():
    """Create a mock partially succeeded build"""
    build = Mock()
    build.id = 12349
    build.build_number = "20240210.5"
    build.definition = Mock()
    build.definition.id = 103
    build.definition.name = "Deploy Pipeline"
    build.status = "completed"
    build.result = "partiallySucceeded"
    build.start_time = datetime(2026, 2, 10, 13, 0, 0, tzinfo=UTC)
    build.finish_time = datetime(2026, 2, 10, 13, 45, 0, tzinfo=UTC)
    build.source_branch = "refs/heads/main"
    build.source_version = "mno567pqr890"
    build.requested_for = Mock()
    build.requested_for.display_name = "Deploy Bot"
    return build


@pytest.fixture
def sample_build_data_list():
    """Sample build data as list of dicts (output of query_builds)"""
    return [
        {
            "build_id": 1,
            "build_number": "20240201.1",
            "definition_id": 101,
            "definition_name": "CI Pipeline",
            "status": "completed",
            "result": "succeeded",
            "start_time": "2026-02-01T09:00:00+00:00",
            "finish_time": "2026-02-01T09:15:00+00:00",
            "duration_minutes": 15.0,
            "source_branch": "refs/heads/main",
            "source_version": "abc123",
            "requested_for": "Alice",
        },
        {
            "build_id": 2,
            "build_number": "20240202.1",
            "definition_id": 101,
            "definition_name": "CI Pipeline",
            "status": "completed",
            "result": "failed",
            "start_time": "2026-02-02T10:00:00+00:00",
            "finish_time": "2026-02-02T10:30:00+00:00",
            "duration_minutes": 30.0,
            "source_branch": "refs/heads/feature/test",
            "source_version": "def456",
            "requested_for": "Bob",
        },
        {
            "build_id": 3,
            "build_number": "20240203.1",
            "definition_id": 102,
            "definition_name": "Release Pipeline",
            "status": "completed",
            "result": "succeeded",
            "start_time": "2026-02-03T11:00:00+00:00",
            "finish_time": "2026-02-03T11:25:00+00:00",
            "duration_minutes": 25.0,
            "source_branch": "refs/heads/main",
            "source_version": "ghi789",
            "requested_for": "Charlie",
        },
        {
            "build_id": 4,
            "build_number": "20240204.1",
            "definition_id": 101,
            "definition_name": "CI Pipeline",
            "status": "completed",
            "result": "canceled",
            "start_time": "2026-02-04T12:00:00+00:00",
            "finish_time": "2026-02-04T12:05:00+00:00",
            "duration_minutes": 5.0,
            "source_branch": "refs/heads/test",
            "source_version": "jkl012",
            "requested_for": "Dave",
        },
        {
            "build_id": 5,
            "build_number": "20240205.1",
            "definition_id": 103,
            "definition_name": "Deploy Pipeline",
            "status": "completed",
            "result": "partiallySucceeded",
            "start_time": "2026-02-05T13:00:00+00:00",
            "finish_time": "2026-02-05T13:45:00+00:00",
            "duration_minutes": 45.0,
            "source_branch": "refs/heads/main",
            "source_version": "mno345",
            "requested_for": "Eve",
        },
    ]


@pytest.fixture
def temp_deployment_history_file(tmp_path):
    """Create a temporary deployment history file path"""
    return tmp_path / "deployment_history.json"


# ============================================================================
# TEST CLASS: query_builds()
# ============================================================================


class TestQueryBuilds:
    """Test query_builds() function with mocked Azure DevOps Build API"""

    def test_query_builds_success(self, mock_build_successful, mock_build_failed):
        """Test successful build query returns properly formatted data"""
        mock_client = Mock()
        mock_client.get_builds.return_value = [mock_build_successful, mock_build_failed]

        result = query_builds(mock_client, "TestProject", days=90)

        assert len(result) == 2
        assert result[0]["build_id"] == 12345
        assert result[0]["build_number"] == "20240210.1"
        assert result[0]["definition_name"] == "CI Pipeline"
        assert result[0]["result"] == "succeeded"
        assert result[0]["duration_minutes"] == 15.0
        assert result[1]["result"] == "failed"
        assert result[1]["duration_minutes"] == 30.0

    def test_query_builds_calculates_duration(self, mock_build_successful):
        """Test that duration is calculated correctly from start/finish times"""
        mock_client = Mock()
        mock_client.get_builds.return_value = [mock_build_successful]

        result = query_builds(mock_client, "TestProject", days=90)

        # 15 minutes duration (09:00 to 09:15)
        assert result[0]["duration_minutes"] == 15.0

    def test_query_builds_no_finish_time(self, mock_build_in_progress):
        """Test build with no finish_time (in-progress) has None duration"""
        mock_client = Mock()
        mock_client.get_builds.return_value = [mock_build_in_progress]

        result = query_builds(mock_client, "TestProject", days=90)

        assert result[0]["duration_minutes"] is None
        assert result[0]["finish_time"] is None

    def test_query_builds_with_custom_days(self, mock_build_successful):
        """Test query_builds respects custom lookback period"""
        mock_client = Mock()
        mock_client.get_builds.return_value = [mock_build_successful]

        query_builds(mock_client, "TestProject", days=30)

        # Verify min_time is approximately 30 days ago
        call_args = mock_client.get_builds.call_args
        min_time = call_args.kwargs["min_time"]
        expected_date = datetime.now() - timedelta(days=30)
        assert abs((min_time - expected_date).total_seconds()) < 60  # Within 1 minute

    def test_query_builds_empty_result(self):
        """Test query_builds with no builds returns empty list"""
        mock_client = Mock()
        mock_client.get_builds.return_value = []

        result = query_builds(mock_client, "TestProject", days=90)

        assert result == []

    def test_query_builds_handles_missing_definition(self):
        """Test query_builds handles builds with no definition"""
        mock_build = Mock()
        mock_build.id = 999
        mock_build.build_number = "test.1"
        mock_build.definition = None
        mock_build.status = "completed"
        mock_build.result = "succeeded"
        mock_build.start_time = datetime(2026, 2, 10, 9, 0, 0, tzinfo=UTC)
        mock_build.finish_time = datetime(2026, 2, 10, 9, 15, 0, tzinfo=UTC)
        mock_build.source_branch = "refs/heads/main"
        mock_build.source_version = "abc123"
        mock_build.requested_for = Mock()
        mock_build.requested_for.display_name = "Test User"

        mock_client = Mock()
        mock_client.get_builds.return_value = [mock_build]

        result = query_builds(mock_client, "TestProject", days=90)

        assert result[0]["definition_id"] is None
        assert result[0]["definition_name"] == "Unknown"

    def test_query_builds_handles_missing_requested_for(self, mock_build_successful):
        """Test query_builds handles builds with no requested_for"""
        mock_build_successful.requested_for = None

        mock_client = Mock()
        mock_client.get_builds.return_value = [mock_build_successful]

        result = query_builds(mock_client, "TestProject", days=90)

        assert result[0]["requested_for"] == "Unknown"

    def test_query_builds_azure_service_error(self):
        """Test query_builds handles AzureDevOpsServiceError gracefully"""
        mock_client = Mock()
        mock_client.get_builds.side_effect = create_azure_error("API Error")

        result = query_builds(mock_client, "TestProject", days=90)

        assert result == []

    def test_query_builds_connection_error(self):
        """Test query_builds handles ConnectionError gracefully"""
        mock_client = Mock()
        mock_client.get_builds.side_effect = ConnectionError("Network error")

        result = query_builds(mock_client, "TestProject", days=90)

        assert result == []

    def test_query_builds_timeout_error(self):
        """Test query_builds handles TimeoutError gracefully"""
        mock_client = Mock()
        mock_client.get_builds.side_effect = TimeoutError("Request timeout")

        result = query_builds(mock_client, "TestProject", days=90)

        assert result == []

    def test_query_builds_attribute_error(self):
        """Test query_builds handles AttributeError in build data"""
        mock_build = Mock()
        mock_build.id = 999
        # Missing critical attributes - will cause AttributeError

        mock_client = Mock()
        mock_client.get_builds.return_value = [mock_build]

        # Should handle error and return empty list
        result = query_builds(mock_client, "TestProject", days=90)
        assert result == []


# ============================================================================
# TEST CLASS: calculate_deployment_frequency()
# ============================================================================


class TestCalculateDeploymentFrequency:
    """Test deployment frequency calculations (DORA metric)"""

    def test_deployment_frequency_with_successful_builds(self, sample_build_data_list):
        """Test deployment frequency counts successful builds correctly"""
        result = calculate_deployment_frequency(sample_build_data_list, lookback_days=90)

        # 2 successful builds (build_id 1 and 3)
        assert result["total_successful_builds"] == 2
        assert result["lookback_days"] == 90
        # 90 days / 7 = ~12.86 weeks, 2 builds / 12.86 = 0.16 per week
        assert result["deployments_per_week"] == pytest.approx(0.16, rel=0.01)

    def test_deployment_frequency_by_pipeline(self, sample_build_data_list):
        """Test deployment frequency grouped by pipeline"""
        result = calculate_deployment_frequency(sample_build_data_list, lookback_days=90)

        # CI Pipeline: 1 success, Release Pipeline: 1 success
        assert result["by_pipeline"]["CI Pipeline"] == 1
        assert result["by_pipeline"]["Release Pipeline"] == 1
        assert result["pipeline_count"] == 2

    def test_deployment_frequency_empty_builds(self):
        """Test deployment frequency with no builds"""
        result = calculate_deployment_frequency([], lookback_days=90)

        assert result["total_successful_builds"] == 0
        assert result["deployments_per_week"] == 0.0
        assert result["by_pipeline"] == {}
        assert result["pipeline_count"] == 0

    def test_deployment_frequency_only_failed_builds(self):
        """Test deployment frequency with only failed builds"""
        builds = [
            {
                "build_id": 1,
                "definition_name": "CI",
                "result": "failed",
                "start_time": "2026-02-01T09:00:00+00:00",
                "finish_time": "2026-02-01T09:15:00+00:00",
                "duration_minutes": 15.0,
            },
            {
                "build_id": 2,
                "definition_name": "CI",
                "result": "canceled",
                "start_time": "2026-02-02T09:00:00+00:00",
                "finish_time": "2026-02-02T09:15:00+00:00",
                "duration_minutes": 15.0,
            },
        ]

        result = calculate_deployment_frequency(builds, lookback_days=30)

        assert result["total_successful_builds"] == 0
        assert result["deployments_per_week"] == 0.0

    def test_deployment_frequency_custom_lookback(self):
        """Test deployment frequency with custom lookback period"""
        builds = [{"build_id": i, "definition_name": "Pipeline", "result": "succeeded"} for i in range(10)]

        result = calculate_deployment_frequency(builds, lookback_days=14)

        # 14 days = 2 weeks, 10 builds / 2 weeks = 5 per week
        assert result["lookback_days"] == 14
        assert result["deployments_per_week"] == 5.0

    def test_deployment_frequency_multiple_pipelines(self):
        """Test deployment frequency across multiple pipelines"""
        builds = [
            {"build_id": 1, "definition_name": "Backend", "result": "succeeded"},
            {"build_id": 2, "definition_name": "Backend", "result": "succeeded"},
            {"build_id": 3, "definition_name": "Frontend", "result": "succeeded"},
            {"build_id": 4, "definition_name": "Frontend", "result": "succeeded"},
            {"build_id": 5, "definition_name": "Frontend", "result": "succeeded"},
            {"build_id": 6, "definition_name": "API", "result": "succeeded"},
        ]

        result = calculate_deployment_frequency(builds, lookback_days=90)

        assert result["total_successful_builds"] == 6
        assert result["by_pipeline"]["Backend"] == 2
        assert result["by_pipeline"]["Frontend"] == 3
        assert result["by_pipeline"]["API"] == 1
        assert result["pipeline_count"] == 3


# ============================================================================
# TEST CLASS: calculate_build_success_rate()
# ============================================================================


class TestCalculateBuildSuccessRate:
    """Test build success rate calculations"""

    def test_build_success_rate_all_metrics(self, sample_build_data_list):
        """Test build success rate with mixed build results"""
        result = calculate_build_success_rate(sample_build_data_list)

        assert result["total_builds"] == 5
        assert result["succeeded"] == 2
        assert result["failed"] == 1
        assert result["canceled"] == 1
        assert result["partially_succeeded"] == 1
        # 2 succeeded / 5 total = 40%
        assert result["success_rate_pct"] == 40.0

    def test_build_success_rate_by_result(self, sample_build_data_list):
        """Test build success rate grouped by result"""
        result = calculate_build_success_rate(sample_build_data_list)

        assert result["by_result"]["succeeded"] == 2
        assert result["by_result"]["failed"] == 1
        assert result["by_result"]["canceled"] == 1
        assert result["by_result"]["partiallySucceeded"] == 1

    def test_build_success_rate_by_pipeline(self, sample_build_data_list):
        """Test build success rate grouped by pipeline"""
        result = calculate_build_success_rate(sample_build_data_list)

        # CI Pipeline: 1 success, 1 fail, 1 cancel
        assert result["by_pipeline"]["CI Pipeline"]["succeeded"] == 1
        assert result["by_pipeline"]["CI Pipeline"]["failed"] == 1
        assert result["by_pipeline"]["CI Pipeline"]["canceled"] == 1

        # Release Pipeline: 1 success
        assert result["by_pipeline"]["Release Pipeline"]["succeeded"] == 1

        # Deploy Pipeline: 1 partial
        assert result["by_pipeline"]["Deploy Pipeline"]["partiallySucceeded"] == 1

    def test_build_success_rate_all_successful(self):
        """Test build success rate with 100% success"""
        builds = [
            {"build_id": 1, "definition_name": "CI", "result": "succeeded"},
            {"build_id": 2, "definition_name": "CI", "result": "succeeded"},
            {"build_id": 3, "definition_name": "CI", "result": "succeeded"},
        ]

        result = calculate_build_success_rate(builds)

        assert result["total_builds"] == 3
        assert result["succeeded"] == 3
        assert result["failed"] == 0
        assert result["success_rate_pct"] == 100.0

    def test_build_success_rate_all_failed(self):
        """Test build success rate with 0% success"""
        builds = [
            {"build_id": 1, "definition_name": "CI", "result": "failed"},
            {"build_id": 2, "definition_name": "CI", "result": "failed"},
        ]

        result = calculate_build_success_rate(builds)

        assert result["total_builds"] == 2
        assert result["succeeded"] == 0
        assert result["failed"] == 2
        assert result["success_rate_pct"] == 0.0

    def test_build_success_rate_empty_builds(self):
        """Test build success rate with no builds"""
        result = calculate_build_success_rate([])

        assert result["total_builds"] == 0
        assert result["succeeded"] == 0
        assert result["failed"] == 0
        assert result["success_rate_pct"] == 0.0


# ============================================================================
# TEST CLASS: calculate_build_duration()
# ============================================================================


class TestCalculateBuildDuration:
    """Test build duration statistics"""

    def test_build_duration_statistics(self, sample_build_data_list):
        """Test build duration calculates correct statistics"""
        result = calculate_build_duration(sample_build_data_list)

        assert result["sample_size"] == 5
        # Durations: [15, 30, 25, 5, 45]
        assert result["median_minutes"] == 25.0
        assert result["min_minutes"] == 5.0
        assert result["max_minutes"] == 45.0

    def test_build_duration_by_pipeline(self, sample_build_data_list):
        """Test build duration grouped by pipeline"""
        result = calculate_build_duration(sample_build_data_list)

        # CI Pipeline: [15, 30, 5] -> median = 15
        assert result["by_pipeline"]["CI Pipeline"]["count"] == 3
        assert result["by_pipeline"]["CI Pipeline"]["median_minutes"] == 15.0

        # Release Pipeline: [25]
        assert result["by_pipeline"]["Release Pipeline"]["count"] == 1
        assert result["by_pipeline"]["Release Pipeline"]["median_minutes"] == 25.0

        # Deploy Pipeline: [45]
        assert result["by_pipeline"]["Deploy Pipeline"]["count"] == 1
        assert result["by_pipeline"]["Deploy Pipeline"]["median_minutes"] == 45.0

    def test_build_duration_no_duration_data(self):
        """Test build duration with no duration data"""
        builds = [
            {"build_id": 1, "definition_name": "CI", "duration_minutes": None},
            {"build_id": 2, "definition_name": "CI", "duration_minutes": None},
        ]

        result = calculate_build_duration(builds)

        assert result["sample_size"] == 0
        assert result["median_minutes"] is None
        assert result["p85_minutes"] is None
        assert result["p95_minutes"] is None

    def test_build_duration_empty_builds(self):
        """Test build duration with no builds"""
        result = calculate_build_duration([])

        assert result["sample_size"] == 0
        assert result["median_minutes"] is None

    def test_build_duration_single_build(self):
        """Test build duration with single build"""
        builds = [{"build_id": 1, "definition_name": "CI", "duration_minutes": 20.5}]

        result = calculate_build_duration(builds)

        assert result["sample_size"] == 1
        assert result["median_minutes"] == 20.5
        assert result["min_minutes"] == 20.5
        assert result["max_minutes"] == 20.5

    def test_build_duration_percentiles(self):
        """Test build duration percentile calculations"""
        # Create builds with known durations: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        builds = [{"build_id": i, "definition_name": "CI", "duration_minutes": float(i * 10)} for i in range(1, 11)]

        result = calculate_build_duration(builds)

        assert result["sample_size"] == 10
        assert result["median_minutes"] == 55.0  # Median of [10..100]
        assert result["p85_minutes"] == pytest.approx(86.5, rel=0.01)
        assert result["p95_minutes"] == pytest.approx(95.5, rel=0.01)


# ============================================================================
# TEST CLASS: _get_commit_timestamp_from_build()
# ============================================================================


class TestGetCommitTimestampFromBuild:
    """Test commit timestamp extraction from builds"""

    def test_get_commit_timestamp_success(self):
        """Test successful commit timestamp extraction"""
        mock_change = Mock()
        mock_change.timestamp = datetime(2026, 2, 10, 8, 0, 0, tzinfo=UTC)

        mock_build_client = Mock()
        mock_build_client.get_build_changes.return_value = [mock_change]

        build_dict = {
            "build_id": 123,
            "finish_time": "2026-02-10T09:00:00+00:00",
            "source_version": "abc123",
        }

        result = _get_commit_timestamp_from_build(mock_build_client, "TestProject", build_dict)

        assert result == datetime(2026, 2, 10, 8, 0, 0, tzinfo=UTC)
        mock_build_client.get_build_changes.assert_called_once_with(project="TestProject", build_id=123)

    def test_get_commit_timestamp_no_finish_time(self):
        """Test returns None when build has no finish_time"""
        mock_build_client = Mock()

        build_dict = {
            "build_id": 123,
            "finish_time": None,
            "source_version": "abc123",
        }

        result = _get_commit_timestamp_from_build(mock_build_client, "TestProject", build_dict)

        assert result is None

    def test_get_commit_timestamp_no_source_version(self):
        """Test returns None when build has no source_version"""
        mock_build_client = Mock()

        build_dict = {
            "build_id": 123,
            "finish_time": "2026-02-10T09:00:00+00:00",
            "source_version": None,
        }

        result = _get_commit_timestamp_from_build(mock_build_client, "TestProject", build_dict)

        assert result is None

    def test_get_commit_timestamp_no_changes(self):
        """Test returns None when build has no changes"""
        mock_build_client = Mock()
        mock_build_client.get_build_changes.return_value = []

        build_dict = {
            "build_id": 123,
            "finish_time": "2026-02-10T09:00:00+00:00",
            "source_version": "abc123",
        }

        result = _get_commit_timestamp_from_build(mock_build_client, "TestProject", build_dict)

        assert result is None

    def test_get_commit_timestamp_change_no_timestamp(self):
        """Test returns None when change has no timestamp"""
        mock_change = Mock()
        mock_change.timestamp = None

        mock_build_client = Mock()
        mock_build_client.get_build_changes.return_value = [mock_change]

        build_dict = {
            "build_id": 123,
            "finish_time": "2026-02-10T09:00:00+00:00",
            "source_version": "abc123",
        }

        result = _get_commit_timestamp_from_build(mock_build_client, "TestProject", build_dict)

        assert result is None

    def test_get_commit_timestamp_azure_service_error(self):
        """Test handles AzureDevOpsServiceError gracefully"""
        mock_build_client = Mock()
        mock_build_client.get_build_changes.side_effect = create_azure_error("API Error")

        build_dict = {
            "build_id": 123,
            "finish_time": "2026-02-10T09:00:00+00:00",
            "source_version": "abc123",
        }

        result = _get_commit_timestamp_from_build(mock_build_client, "TestProject", build_dict)

        assert result is None

    def test_get_commit_timestamp_attribute_error(self):
        """Test handles AttributeError gracefully"""
        mock_change = Mock()
        del mock_change.timestamp  # Remove timestamp attribute

        mock_build_client = Mock()
        mock_build_client.get_build_changes.return_value = [mock_change]

        build_dict = {
            "build_id": 123,
            "finish_time": "2026-02-10T09:00:00+00:00",
            "source_version": "abc123",
        }

        result = _get_commit_timestamp_from_build(mock_build_client, "TestProject", build_dict)

        assert result is None


# ============================================================================
# TEST CLASS: _calculate_single_build_lead_time()
# ============================================================================


class TestCalculateSingleBuildLeadTime:
    """Test lead time calculation for single builds"""

    def test_calculate_lead_time_positive(self):
        """Test lead time calculation with valid timestamps"""
        commit_time = datetime(2026, 2, 10, 8, 0, 0, tzinfo=UTC)
        build_dict = {"build_id": 123, "finish_time": "2026-02-10T10:00:00+00:00"}

        result = _calculate_single_build_lead_time(commit_time, build_dict)

        # 2 hours = 2.0 hours
        assert result == 2.0

    def test_calculate_lead_time_fractional_hours(self):
        """Test lead time calculation with fractional hours"""
        commit_time = datetime(2026, 2, 10, 8, 0, 0, tzinfo=UTC)
        build_dict = {"build_id": 123, "finish_time": "2026-02-10T08:30:00+00:00"}

        result = _calculate_single_build_lead_time(commit_time, build_dict)

        # 30 minutes = 0.5 hours
        assert result == 0.5

    def test_calculate_lead_time_negative(self):
        """Test returns None for negative lead time (build before commit)"""
        commit_time = datetime(2026, 2, 10, 10, 0, 0, tzinfo=UTC)
        build_dict = {"build_id": 123, "finish_time": "2026-02-10T08:00:00+00:00"}

        result = _calculate_single_build_lead_time(commit_time, build_dict)

        assert result is None

    def test_calculate_lead_time_no_finish_time(self):
        """Test returns None when build has no finish_time"""
        commit_time = datetime(2026, 2, 10, 8, 0, 0, tzinfo=UTC)
        build_dict = {"build_id": 123, "finish_time": None}

        result = _calculate_single_build_lead_time(commit_time, build_dict)

        assert result is None

    def test_calculate_lead_time_timezone_aware(self):
        """Test lead time calculation handles timezone-aware datetimes"""
        commit_time = datetime(2026, 2, 10, 8, 0, 0, tzinfo=UTC)
        build_dict = {"build_id": 123, "finish_time": "2026-02-10T10:00:00+00:00"}

        result = _calculate_single_build_lead_time(commit_time, build_dict)

        assert result == 2.0

    def test_calculate_lead_time_timezone_naive_commit(self):
        """Test lead time calculation with naive commit timestamp"""
        commit_time = datetime(2026, 2, 10, 8, 0, 0)  # Naive datetime
        build_dict = {"build_id": 123, "finish_time": "2026-02-10T10:00:00+00:00"}

        result = _calculate_single_build_lead_time(commit_time, build_dict)

        assert result == 2.0

    def test_calculate_lead_time_invalid_finish_time(self):
        """Test returns None for invalid finish_time format"""
        commit_time = datetime(2026, 2, 10, 8, 0, 0, tzinfo=UTC)
        build_dict = {"build_id": 123, "finish_time": "invalid-date"}

        result = _calculate_single_build_lead_time(commit_time, build_dict)

        assert result is None


# ============================================================================
# TEST CLASS: calculate_lead_time_for_changes()
# ============================================================================


class TestCalculateLeadTimeForChanges:
    """Test lead time for changes calculations"""

    def test_calculate_lead_time_with_valid_data(self):
        """Test lead time calculation with valid commit and build data"""
        mock_change = Mock()
        mock_change.timestamp = datetime(2026, 2, 10, 8, 0, 0, tzinfo=UTC)

        mock_build_client = Mock()
        mock_build_client.get_build_changes.return_value = [mock_change]

        mock_git_client = Mock()

        builds = [
            {
                "build_id": 1,
                "result": "succeeded",
                "finish_time": "2026-02-10T10:00:00+00:00",
                "source_version": "abc123",
            },
            {
                "build_id": 2,
                "result": "succeeded",
                "finish_time": "2026-02-10T12:00:00+00:00",
                "source_version": "def456",
            },
        ]

        result = calculate_lead_time_for_changes(mock_build_client, mock_git_client, "TestProject", builds)

        assert result["sample_size"] == 2
        # Both builds have same commit time (8:00), finished at 10:00 and 12:00
        # Lead times: 2 hours, 4 hours -> median = 3.0
        assert result["median_hours"] == 3.0

    def test_calculate_lead_time_no_successful_builds(self):
        """Test lead time with no successful builds"""
        mock_build_client = Mock()
        mock_git_client = Mock()

        builds = [
            {"build_id": 1, "result": "failed", "finish_time": "2026-02-10T10:00:00+00:00"},
        ]

        result = calculate_lead_time_for_changes(mock_build_client, mock_git_client, "TestProject", builds)

        assert result["sample_size"] == 0
        assert result["median_hours"] is None

    def test_calculate_lead_time_no_commit_timestamps(self):
        """Test lead time when no commit timestamps can be extracted"""
        mock_build_client = Mock()
        mock_build_client.get_build_changes.return_value = []

        mock_git_client = Mock()

        builds = [
            {
                "build_id": 1,
                "result": "succeeded",
                "finish_time": "2026-02-10T10:00:00+00:00",
                "source_version": "abc123",
            },
        ]

        result = calculate_lead_time_for_changes(mock_build_client, mock_git_client, "TestProject", builds)

        assert result["sample_size"] == 0
        assert result["median_hours"] is None

    def test_calculate_lead_time_limits_to_50_builds(self):
        """Test lead time only processes first 50 successful builds"""
        mock_change = Mock()
        mock_change.timestamp = datetime(2026, 2, 10, 8, 0, 0, tzinfo=UTC)

        mock_build_client = Mock()
        mock_build_client.get_build_changes.return_value = [mock_change]

        mock_git_client = Mock()

        # Create 100 successful builds
        builds = [
            {
                "build_id": i,
                "result": "succeeded",
                "finish_time": "2026-02-10T10:00:00+00:00",
                "source_version": f"commit{i}",
            }
            for i in range(100)
        ]

        result = calculate_lead_time_for_changes(mock_build_client, mock_git_client, "TestProject", builds)

        # Should only process 50 builds
        assert result["sample_size"] == 50

    def test_calculate_lead_time_filters_negative_lead_times(self):
        """Test lead time filters out negative lead times"""
        mock_change_future = Mock()
        mock_change_future.timestamp = datetime(2026, 2, 10, 12, 0, 0, tzinfo=UTC)  # After finish

        mock_change_past = Mock()
        mock_change_past.timestamp = datetime(2026, 2, 10, 8, 0, 0, tzinfo=UTC)  # Before finish

        mock_build_client = Mock()

        def get_changes_side_effect(project, build_id):
            if build_id == 1:
                return [mock_change_future]
            else:
                return [mock_change_past]

        mock_build_client.get_build_changes.side_effect = get_changes_side_effect

        mock_git_client = Mock()

        builds = [
            {
                "build_id": 1,
                "result": "succeeded",
                "finish_time": "2026-02-10T10:00:00+00:00",
                "source_version": "abc123",
            },
            {
                "build_id": 2,
                "result": "succeeded",
                "finish_time": "2026-02-10T10:00:00+00:00",
                "source_version": "def456",
            },
        ]

        result = calculate_lead_time_for_changes(mock_build_client, mock_git_client, "TestProject", builds)

        # Only build 2 should be counted (positive lead time)
        assert result["sample_size"] == 1


# ============================================================================
# TEST CLASS: collect_deployment_metrics_for_project()
# ============================================================================


class TestCollectDeploymentMetricsForProject:
    """Test end-to-end project metrics collection"""

    @patch("execution.collectors.ado_deployment_metrics.calculate_lead_time_for_changes")
    @patch("execution.collectors.ado_deployment_metrics.query_builds")
    def test_collect_metrics_success(self, mock_query_builds, mock_calc_lead_time, sample_build_data_list):
        """Test successful metrics collection for a project"""
        mock_query_builds.return_value = sample_build_data_list
        mock_calc_lead_time.return_value = {"sample_size": 2, "median_hours": 3.5, "p85_hours": 5.0, "p95_hours": 6.0}

        mock_connection = Mock()
        mock_build_client = Mock()
        mock_git_client = Mock()
        mock_connection.clients.get_build_client.return_value = mock_build_client
        mock_connection.clients.get_git_client.return_value = mock_git_client

        project = {
            "project_key": "test-proj",
            "project_name": "Test Project",
            "ado_project_name": "ADO Test Project",
        }

        config = {"lookback_days": 90}

        result = collect_deployment_metrics_for_project(mock_connection, project, config)

        assert result["project_key"] == "test-proj"
        assert result["project_name"] == "Test Project"
        assert "deployment_frequency" in result
        assert "build_success_rate" in result
        assert "build_duration" in result
        assert "lead_time_for_changes" in result
        assert "collected_at" in result

    @patch("execution.collectors.ado_deployment_metrics.query_builds")
    def test_collect_metrics_no_builds(self, mock_query_builds):
        """Test metrics collection when no builds found"""
        mock_query_builds.return_value = []

        mock_connection = Mock()
        mock_build_client = Mock()
        mock_git_client = Mock()
        mock_connection.clients.get_build_client.return_value = mock_build_client
        mock_connection.clients.get_git_client.return_value = mock_git_client

        project = {
            "project_key": "empty-proj",
            "project_name": "Empty Project",
        }

        config = {"lookback_days": 90}

        result = collect_deployment_metrics_for_project(mock_connection, project, config)

        assert result["deployment_frequency"]["total_successful_builds"] == 0
        assert result["build_success_rate"]["total_builds"] == 0
        assert result["build_duration"]["sample_size"] == 0
        assert result["lead_time_for_changes"]["sample_size"] == 0

    @patch("execution.collectors.ado_deployment_metrics.query_builds")
    def test_collect_metrics_uses_ado_project_name(self, mock_query_builds):
        """Test that collection uses ado_project_name when available"""
        mock_query_builds.return_value = []

        mock_connection = Mock()
        mock_build_client = Mock()
        mock_git_client = Mock()
        mock_connection.clients.get_build_client.return_value = mock_build_client
        mock_connection.clients.get_git_client.return_value = mock_git_client

        project = {
            "project_key": "test",
            "project_name": "Test",
            "ado_project_name": "Different ADO Name",
        }

        config = {"lookback_days": 90}

        collect_deployment_metrics_for_project(mock_connection, project, config)

        # Should call query_builds with ado_project_name
        mock_query_builds.assert_called_with(mock_build_client, "Different ADO Name", days=90)


# ============================================================================
# TEST CLASS: save_deployment_metrics()
# ============================================================================


class TestSaveDeploymentMetrics:
    """Test deployment metrics persistence"""

    def test_save_metrics_creates_new_file(self, temp_deployment_history_file):
        """Test saving metrics creates new history file"""
        metrics = {
            "week_date": "2026-02-10",
            "week_number": 6,
            "projects": [
                {
                    "project_key": "test",
                    "project_name": "Test Project",
                    "deployment_frequency": {"total_successful_builds": 10},
                    "build_success_rate": {"total_builds": 15},
                }
            ],
            "config": {"lookback_days": 90},
        }

        result = save_deployment_metrics(metrics, str(temp_deployment_history_file))

        assert result is True
        assert temp_deployment_history_file.exists()

        # Verify saved data
        saved_data = json.loads(temp_deployment_history_file.read_text())
        assert "weeks" in saved_data
        assert len(saved_data["weeks"]) == 1
        assert saved_data["weeks"][0]["week_date"] == "2026-02-10"

    def test_save_metrics_appends_to_existing_file(self, temp_deployment_history_file):
        """Test saving metrics appends to existing history"""
        # Create existing history
        existing_history = {
            "weeks": [
                {
                    "week_date": "2026-02-03",
                    "projects": [{"project_key": "old", "deployment_frequency": {"total_successful_builds": 5}}],
                }
            ]
        }
        temp_deployment_history_file.write_text(json.dumps(existing_history))

        # Save new metrics
        new_metrics = {
            "week_date": "2026-02-10",
            "projects": [{"project_key": "new", "deployment_frequency": {"total_successful_builds": 10}}],
        }

        result = save_deployment_metrics(new_metrics, str(temp_deployment_history_file))

        assert result is True

        # Verify both entries exist
        saved_data = json.loads(temp_deployment_history_file.read_text())
        assert len(saved_data["weeks"]) == 2
        assert saved_data["weeks"][0]["week_date"] == "2026-02-03"
        assert saved_data["weeks"][1]["week_date"] == "2026-02-10"

    def test_save_metrics_limits_to_52_weeks(self, temp_deployment_history_file):
        """Test saving metrics keeps only last 52 weeks"""
        # Create history with 60 existing weeks
        existing_history = {
            "weeks": [
                {
                    "week_date": f"2025-{i:02d}-01",
                    "projects": [{"project_key": "old", "deployment_frequency": {"total_successful_builds": 1}}],
                }
                for i in range(1, 13)
            ]
            * 5  # 60 weeks
        }
        temp_deployment_history_file.write_text(json.dumps(existing_history))

        # Save new metrics (with valid data to pass validation)
        new_metrics = {
            "week_date": "2026-02-10",
            "projects": [{"project_key": "new", "deployment_frequency": {"total_successful_builds": 5}}],
        }

        save_deployment_metrics(new_metrics, str(temp_deployment_history_file))

        # Verify only 52 weeks kept (60 existing + 1 new = 61, then trimmed to 52)
        saved_data = json.loads(temp_deployment_history_file.read_text())
        assert len(saved_data["weeks"]) == 52

    def test_save_metrics_skips_empty_projects(self, temp_deployment_history_file):
        """Test saving metrics skips data with no projects"""
        metrics = {"week_date": "2026-02-10", "projects": []}

        result = save_deployment_metrics(metrics, str(temp_deployment_history_file))

        assert result is False
        assert not temp_deployment_history_file.exists()

    def test_save_metrics_skips_all_zero_data(self, temp_deployment_history_file):
        """Test saving metrics skips data with all zeros (failed collection)"""
        metrics = {
            "week_date": "2026-02-10",
            "projects": [
                {
                    "project_key": "test",
                    "deployment_frequency": {"total_successful_builds": 0},
                    "build_success_rate": {"total_builds": 0},
                }
            ],
        }

        result = save_deployment_metrics(metrics, str(temp_deployment_history_file))

        assert result is False
        assert not temp_deployment_history_file.exists()

    def test_save_metrics_allows_partial_data(self, temp_deployment_history_file):
        """Test saving metrics allows partial data (some zeros OK)"""
        metrics = {
            "week_date": "2026-02-10",
            "projects": [
                {
                    "project_key": "test",
                    "deployment_frequency": {"total_successful_builds": 5},
                    "build_success_rate": {"total_builds": 0},  # OK if some data exists
                }
            ],
        }

        result = save_deployment_metrics(metrics, str(temp_deployment_history_file))

        assert result is True

    def test_save_metrics_handles_invalid_existing_structure(self, temp_deployment_history_file):
        """Test saving metrics recreates history if structure invalid"""
        # Create invalid history
        temp_deployment_history_file.write_text('{"invalid": "structure"}')

        metrics = {
            "week_date": "2026-02-10",
            "projects": [{"project_key": "test", "deployment_frequency": {"total_successful_builds": 5}}],
        }

        result = save_deployment_metrics(metrics, str(temp_deployment_history_file))

        assert result is True

        # Verify recreated structure
        saved_data = json.loads(temp_deployment_history_file.read_text())
        assert "weeks" in saved_data
        assert len(saved_data["weeks"]) == 1
