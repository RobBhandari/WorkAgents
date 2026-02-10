"""
Tests for ADO Quality Metrics Collector

Comprehensive test coverage for ado_quality_metrics.py including:
- WIQL query building and area path filtering
- Bug fetching with batch utilities
- Bug age distribution calculations
- MTTR (Mean Time To Repair) calculations
- Test execution time metrics
- Project metrics collection orchestration
- Data persistence and validation

Run with:
    pytest tests/collectors/test_ado_quality_metrics.py -v
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, mock_open, patch

import pytest
from azure.devops.exceptions import AzureDevOpsServiceError

from execution.collectors.ado_quality_metrics import (
    _build_area_filter_clause,
    _fetch_bug_details,
    _parse_repair_times,
    calculate_bug_age_distribution,
    calculate_mttr,
    calculate_test_execution_time,
    collect_quality_metrics_for_project,
    query_bugs_for_quality,
    save_quality_metrics,
)
from execution.utils.ado_batch_utils import BatchFetchError

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_wit_client():
    """Mock Work Item Tracking client"""
    client = Mock()
    client.query_by_wiql = Mock()
    client.get_work_items = Mock()
    return client


@pytest.fixture
def mock_test_client():
    """Mock Test client"""
    client = Mock()
    client.get_test_runs = Mock()
    return client


@pytest.fixture
def mock_connection(mock_wit_client, mock_test_client):
    """Mock ADO connection with clients"""
    connection = Mock()
    connection.clients.get_work_item_tracking_client = Mock(return_value=mock_wit_client)
    connection.clients.get_test_client = Mock(return_value=mock_test_client)
    return connection


@pytest.fixture
def sample_bug_active():
    """Sample active bug work item"""
    return {
        "System.Id": 1001,
        "System.Title": "Login button not responsive",
        "System.State": "Active",
        "System.CreatedDate": "2026-01-15T10:00:00Z",
        "System.WorkItemType": "Bug",
        "Microsoft.VSTS.Common.Priority": 2,
        "Microsoft.VSTS.Common.Severity": "2 - High",
        "System.Tags": "ui;frontend",
        "System.CreatedBy": {"displayName": "Alice Johnson"},
    }


@pytest.fixture
def sample_bug_closed():
    """Sample closed bug work item"""
    return {
        "System.Id": 1002,
        "System.Title": "Database connection timeout",
        "System.State": "Closed",
        "System.CreatedDate": "2026-01-10T08:00:00Z",
        "System.WorkItemType": "Bug",
        "Microsoft.VSTS.Common.Priority": 1,
        "Microsoft.VSTS.Common.Severity": "1 - Critical",
        "System.Tags": "backend;database",
        "Microsoft.VSTS.Common.ClosedDate": "2026-01-15T16:00:00Z",
        "Microsoft.VSTS.Common.ResolvedDate": "2026-01-15T14:00:00Z",
        "System.CreatedBy": {"displayName": "Bob Smith"},
    }


@pytest.fixture
def sample_bug_resolved():
    """Sample resolved bug work item"""
    return {
        "System.Id": 1003,
        "System.Title": "Memory leak in background service",
        "System.State": "Resolved",
        "System.CreatedDate": "2026-01-20T09:00:00Z",
        "System.WorkItemType": "Bug",
        "Microsoft.VSTS.Common.Priority": 2,
        "Microsoft.VSTS.Common.Severity": "3 - Medium",
        "System.Tags": "performance;memory",
        "Microsoft.VSTS.Common.ResolvedDate": "2026-01-25T17:00:00Z",
        "System.CreatedBy": {"displayName": "Charlie Davis"},
    }


@pytest.fixture
def sample_open_bugs(sample_bug_active, sample_bug_resolved):
    """List of open bugs for testing"""
    return [sample_bug_active, sample_bug_resolved]


@pytest.fixture
def sample_all_bugs(sample_bug_active, sample_bug_closed, sample_bug_resolved):
    """List of all bugs for testing"""
    return [sample_bug_active, sample_bug_closed, sample_bug_resolved]


@pytest.fixture
def sample_project():
    """Sample project metadata"""
    return {
        "project_name": "Engineering Platform",
        "project_key": "eng-platform",
        "ado_project_name": "EngineeringPlatform",
    }


@pytest.fixture
def sample_project_with_area_filter():
    """Sample project with area path filter"""
    return {
        "project_name": "Engineering Platform",
        "project_key": "eng-platform",
        "ado_project_name": "EngineeringPlatform",
        "area_path_filter": "EXCLUDE:EngineeringPlatform\\Archive",
    }


@pytest.fixture
def sample_test_run():
    """Sample test run data"""
    run = Mock()
    run.started_date = datetime(2026, 2, 10, 10, 0, 0, tzinfo=UTC)
    run.completed_date = datetime(2026, 2, 10, 10, 30, 0, tzinfo=UTC)
    return run


@pytest.fixture
def sample_quality_metrics():
    """Sample quality metrics for saving"""
    return {
        "week_date": "2026-02-10",
        "week_number": 6,
        "projects": [
            {
                "project_key": "eng-platform",
                "project_name": "Engineering Platform",
                "bug_age_distribution": {
                    "median_age_days": 15.5,
                    "p85_age_days": 30.2,
                    "p95_age_days": 45.8,
                    "sample_size": 25,
                    "ages_distribution": {"0-7_days": 5, "8-30_days": 12, "31-90_days": 6, "90+_days": 2},
                },
                "mttr": {
                    "mttr_days": 5.5,
                    "median_mttr_days": 4.2,
                    "p85_mttr_days": 8.5,
                    "p95_mttr_days": 12.1,
                    "sample_size": 50,
                    "mttr_distribution": {"0-1_days": 10, "1-7_days": 30, "7-30_days": 8, "30+_days": 2},
                },
                "test_execution_time": {
                    "sample_size": 20,
                    "median_minutes": 25.5,
                    "p85_minutes": 35.0,
                    "p95_minutes": 42.5,
                },
                "total_bugs_analyzed": 75,
                "open_bugs_count": 25,
                "excluded_security_bugs": {"total": 5, "open": 2},
                "collected_at": "2026-02-10T12:00:00",
            }
        ],
        "config": {"lookback_days": 90},
    }


@pytest.fixture
def temp_history_file(tmp_path):
    """Temporary history file path"""
    return tmp_path / "quality_history.json"


# =============================================================================
# Tests for _build_area_filter_clause
# =============================================================================


class TestBuildAreaFilterClause:
    """Tests for area path filter clause building"""

    def test_no_filter_returns_empty_string(self):
        """Test that None filter returns empty string"""
        result = _build_area_filter_clause(None)
        assert result == ""

    def test_exclude_filter_builds_not_under_clause(self):
        """Test EXCLUDE filter builds NOT UNDER clause"""
        result = _build_area_filter_clause("EXCLUDE:MyProject\\Archive")
        assert "NOT UNDER" in result
        assert "MyProject\\Archive" in result

    def test_include_filter_builds_under_clause(self):
        """Test INCLUDE filter builds UNDER clause"""
        result = _build_area_filter_clause("INCLUDE:MyProject\\Team1")
        assert "UNDER" in result
        assert "NOT UNDER" not in result
        assert "MyProject\\Team1" in result

    def test_empty_string_filter_returns_empty(self):
        """Test empty string filter returns empty string"""
        result = _build_area_filter_clause("")
        assert result == ""

    @patch("execution.collectors.ado_quality_metrics.WIQLValidator.validate_area_path")
    def test_calls_wiql_validator_for_exclude(self, mock_validator):
        """Test that EXCLUDE filter validates area path"""
        mock_validator.return_value = "ValidatedPath"
        _build_area_filter_clause("EXCLUDE:UntrustedPath")
        mock_validator.assert_called_once_with("UntrustedPath")

    @patch("execution.collectors.ado_quality_metrics.WIQLValidator.validate_area_path")
    def test_calls_wiql_validator_for_include(self, mock_validator):
        """Test that INCLUDE filter validates area path"""
        mock_validator.return_value = "ValidatedPath"
        _build_area_filter_clause("INCLUDE:UntrustedPath")
        mock_validator.assert_called_once_with("UntrustedPath")

    def test_malformed_filter_without_prefix_returns_empty(self):
        """Test malformed filter without prefix returns empty string"""
        result = _build_area_filter_clause("SomeProject\\Area")
        assert result == ""


# =============================================================================
# Tests for _fetch_bug_details
# =============================================================================


class TestFetchBugDetails:
    """Tests for batch bug fetching"""

    def test_empty_bug_ids_returns_empty_list(self, mock_wit_client):
        """Test fetching with empty ID list returns empty list"""
        result = _fetch_bug_details(mock_wit_client, [], ["System.Id", "System.Title"])
        assert result == []
        mock_wit_client.get_work_items.assert_not_called()

    @patch("execution.collectors.ado_quality_metrics.batch_fetch_work_items")
    @patch("execution.collectors.ado_quality_metrics.logger")
    def test_fetches_bugs_with_specified_fields(self, mock_logger, mock_batch_fetch, mock_wit_client):
        """Test that bugs are fetched with specified fields"""
        mock_batch_fetch.return_value = ([{"System.Id": 1, "System.Title": "Bug 1"}], [])

        fields = ["System.Id", "System.Title", "System.State"]
        result = _fetch_bug_details(mock_wit_client, [1, 2, 3], fields)

        mock_batch_fetch.assert_called_once_with(mock_wit_client, item_ids=[1, 2, 3], fields=fields, logger=mock_logger)
        assert len(result) == 1

    @patch("execution.collectors.ado_quality_metrics.batch_fetch_work_items")
    def test_logs_warning_on_failed_ids(self, mock_batch_fetch, mock_wit_client, caplog):
        """Test that warnings are logged for failed IDs"""
        mock_batch_fetch.return_value = ([{"System.Id": 1}], [2, 3])

        with caplog.at_level(logging.WARNING):
            result = _fetch_bug_details(mock_wit_client, [1, 2, 3], ["System.Id"])

        assert "Failed to fetch 2 out of 3 bugs" in caplog.text
        assert len(result) == 1

    @patch("execution.collectors.ado_quality_metrics.batch_fetch_work_items")
    def test_raises_batch_fetch_error_on_complete_failure(self, mock_batch_fetch, mock_wit_client):
        """Test that BatchFetchError is raised when all batches fail"""
        mock_batch_fetch.side_effect = BatchFetchError("All batches failed")

        with pytest.raises(BatchFetchError):
            _fetch_bug_details(mock_wit_client, [1, 2, 3], ["System.Id"])

    @patch("execution.collectors.ado_quality_metrics.batch_fetch_work_items")
    def test_returns_empty_list_on_batch_error_with_logging(self, mock_batch_fetch, mock_wit_client, caplog):
        """Test that empty list is returned and error logged when catching BatchFetchError"""
        mock_batch_fetch.side_effect = BatchFetchError("Network error")

        # The function raises, not catches, so we should catch it in the test
        with pytest.raises(BatchFetchError):
            _fetch_bug_details(mock_wit_client, [1, 2], ["System.Id"])


# =============================================================================
# Tests for query_bugs_for_quality
# =============================================================================


class TestQueryBugsForQuality:
    """Tests for WIQL bug querying"""

    @patch("execution.collectors.ado_quality_metrics._fetch_bug_details")
    @patch("execution.collectors.ado_quality_metrics.WIQLValidator")
    def test_queries_all_bugs_and_open_bugs(self, mock_validator, mock_fetch, mock_wit_client):
        """Test that both all bugs and open bugs are queried"""
        # Setup validator
        mock_validator.validate_project_name.return_value = "TestProject"
        mock_validator.validate_date_iso8601.return_value = "2025-11-12"

        # Setup WIQL responses
        mock_all_bugs_result = Mock()
        mock_all_bugs_result.work_items = [Mock(id=1), Mock(id=2)]

        mock_open_bugs_result = Mock()
        mock_open_bugs_result.work_items = [Mock(id=1)]

        mock_wit_client.query_by_wiql.side_effect = [mock_all_bugs_result, mock_open_bugs_result]

        # Setup fetch responses
        mock_fetch.side_effect = [[{"System.Id": 1}, {"System.Id": 2}], [{"System.Id": 1}]]

        result = query_bugs_for_quality(mock_wit_client, "TestProject", lookback_days=90)

        assert len(result["all_bugs"]) == 2
        assert len(result["open_bugs"]) == 1
        assert mock_wit_client.query_by_wiql.call_count == 2

    @patch("execution.collectors.ado_quality_metrics._fetch_bug_details")
    @patch("execution.collectors.ado_quality_metrics.WIQLValidator")
    def test_applies_area_path_filter(self, mock_validator, mock_fetch, mock_wit_client):
        """Test that area path filter is applied to queries"""
        mock_validator.validate_project_name.return_value = "TestProject"
        mock_validator.validate_date_iso8601.return_value = "2025-11-12"
        mock_validator.validate_area_path.return_value = "TestProject\\Archive"

        mock_result = Mock()
        mock_result.work_items = []
        mock_wit_client.query_by_wiql.return_value = mock_result

        query_bugs_for_quality(
            mock_wit_client, "TestProject", lookback_days=90, area_path_filter="EXCLUDE:TestProject\\Archive"
        )

        # Verify validator was called
        mock_validator.validate_area_path.assert_called_once_with("TestProject\\Archive")

    @patch("execution.collectors.ado_quality_metrics._fetch_bug_details")
    @patch("execution.collectors.ado_quality_metrics.WIQLValidator")
    def test_handles_no_bugs_found(self, mock_validator, mock_fetch, mock_wit_client):
        """Test handling when no bugs are found"""
        mock_validator.validate_project_name.return_value = "EmptyProject"
        mock_validator.validate_date_iso8601.return_value = "2025-11-12"

        mock_result = Mock()
        mock_result.work_items = None
        mock_wit_client.query_by_wiql.return_value = mock_result

        result = query_bugs_for_quality(mock_wit_client, "EmptyProject")

        assert result["all_bugs"] == []
        assert result["open_bugs"] == []

    @patch("execution.collectors.ado_quality_metrics._fetch_bug_details")
    @patch("execution.collectors.ado_quality_metrics.WIQLValidator")
    def test_handles_batch_fetch_error_gracefully(self, mock_validator, mock_fetch, mock_wit_client, caplog):
        """Test that BatchFetchError is handled gracefully"""
        mock_validator.validate_project_name.return_value = "TestProject"
        mock_validator.validate_date_iso8601.return_value = "2025-11-12"

        mock_result = Mock()
        mock_result.work_items = [Mock(id=1), Mock(id=2)]
        mock_wit_client.query_by_wiql.return_value = mock_result

        mock_fetch.side_effect = BatchFetchError("Network timeout")

        with caplog.at_level(logging.WARNING):
            result = query_bugs_for_quality(mock_wit_client, "TestProject")

        assert result["all_bugs"] == []
        assert result["open_bugs"] == []
        assert "Error fetching" in caplog.text

    @patch("execution.collectors.ado_quality_metrics._fetch_bug_details")
    @patch("execution.collectors.ado_quality_metrics.WIQLValidator")
    def test_uses_custom_lookback_days(self, mock_validator, mock_fetch, mock_wit_client):
        """Test that custom lookback days are used in query"""
        mock_validator.validate_project_name.return_value = "TestProject"
        mock_validator.validate_date_iso8601.side_effect = lambda x: x

        mock_result = Mock()
        mock_result.work_items = []
        mock_wit_client.query_by_wiql.return_value = mock_result

        # Calculate expected date
        expected_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        query_bugs_for_quality(mock_wit_client, "TestProject", lookback_days=30)

        # Verify the date validator was called with the correct date
        assert mock_validator.validate_date_iso8601.called


# =============================================================================
# Tests for calculate_bug_age_distribution
# =============================================================================


class TestCalculateBugAgeDistribution:
    """Tests for bug age distribution calculations"""

    def test_empty_bugs_returns_zero_distribution(self):
        """Test empty bug list returns zero distribution"""
        result = calculate_bug_age_distribution([])

        assert result["median_age_days"] is None
        assert result["p85_age_days"] is None
        assert result["p95_age_days"] is None
        assert result["sample_size"] == 0
        assert result["ages_distribution"]["0-7_days"] == 0

    def test_calculates_age_distribution_correctly(self):
        """Test age distribution calculation with valid bugs"""
        now = datetime.now(UTC)

        bugs = [
            {"System.Id": 1, "System.CreatedDate": (now - timedelta(days=5)).isoformat()},
            {"System.Id": 2, "System.CreatedDate": (now - timedelta(days=15)).isoformat()},
            {"System.Id": 3, "System.CreatedDate": (now - timedelta(days=45)).isoformat()},
            {"System.Id": 4, "System.CreatedDate": (now - timedelta(days=100)).isoformat()},
        ]

        result = calculate_bug_age_distribution(bugs)

        assert result["sample_size"] == 4
        assert result["median_age_days"] is not None
        assert result["ages_distribution"]["0-7_days"] == 1
        assert result["ages_distribution"]["8-30_days"] == 1
        assert result["ages_distribution"]["31-90_days"] == 1
        assert result["ages_distribution"]["90+_days"] == 1

    def test_handles_missing_created_date(self):
        """Test handling of bugs with missing created dates"""
        bugs: list[dict] = [
            {"System.Id": 1, "System.CreatedDate": None},
            {"System.Id": 2},  # Missing field entirely
        ]

        result = calculate_bug_age_distribution(bugs)

        assert result["sample_size"] == 0
        assert result["median_age_days"] is None

    def test_handles_invalid_date_format(self, caplog):
        """Test handling of invalid date formats"""
        bugs = [
            {"System.Id": 1, "System.CreatedDate": "invalid-date"},
            {"System.Id": 2, "System.CreatedDate": "2026-02-10T10:00:00Z"},
        ]

        with caplog.at_level(logging.WARNING):
            result = calculate_bug_age_distribution(bugs)

        # Should skip invalid date but process valid one
        assert result["sample_size"] == 1

    def test_all_bugs_in_same_bucket(self):
        """Test distribution when all bugs are in the same age bucket"""
        now = datetime.now(UTC)

        bugs: list[dict] = [
            {"System.Id": i, "System.CreatedDate": (now - timedelta(days=3)).isoformat()} for i in range(10)
        ]

        result = calculate_bug_age_distribution(bugs)

        assert result["sample_size"] == 10
        assert result["ages_distribution"]["0-7_days"] == 10
        assert result["ages_distribution"]["8-30_days"] == 0

    def test_calculates_percentiles_correctly(self):
        """Test that percentile calculations are correct"""
        now = datetime.now(UTC)

        # Create bugs with known ages: 1, 2, 3, ..., 100 days
        bugs: list[dict] = [
            {"System.Id": i, "System.CreatedDate": (now - timedelta(days=i)).isoformat()} for i in range(1, 101)
        ]

        result = calculate_bug_age_distribution(bugs)

        assert result["sample_size"] == 100
        # Median should be around 50
        assert 45 <= result["median_age_days"] <= 55
        # P85 should be around 85
        assert 80 <= result["p85_age_days"] <= 90
        # P95 should be around 95
        assert 90 <= result["p95_age_days"] <= 100


# =============================================================================
# Tests for _parse_repair_times
# =============================================================================


class TestParseRepairTimes:
    """Tests for repair time parsing"""

    def test_empty_bugs_returns_empty_list(self):
        """Test empty bug list returns empty repair times"""
        result = _parse_repair_times([])
        assert result == []

    def test_calculates_repair_time_for_closed_bugs(self):
        """Test repair time calculation for closed bugs"""
        bugs = [
            {
                "System.CreatedDate": "2026-01-01T10:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-05T10:00:00Z",
            },
            {
                "System.CreatedDate": "2026-01-10T08:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-15T08:00:00Z",
            },
        ]

        result = _parse_repair_times(bugs)

        assert len(result) == 2
        assert result[0] == 4.0  # 4 days
        assert result[1] == 5.0  # 5 days

    def test_skips_bugs_without_closed_date(self):
        """Test that open bugs without closed date are skipped"""
        bugs: list[dict] = [
            {
                "System.CreatedDate": "2026-01-01T10:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-05T10:00:00Z",
            },
            {
                "System.CreatedDate": "2026-01-10T08:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": None,
            },
            {
                "System.CreatedDate": "2026-01-15T12:00:00Z",
                # Missing ClosedDate entirely
            },
        ]

        result = _parse_repair_times(bugs)

        assert len(result) == 1
        assert result[0] == 4.0

    def test_handles_fractional_days(self):
        """Test that fractional days are calculated correctly"""
        bugs = [
            {
                "System.CreatedDate": "2026-01-01T10:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-01T22:00:00Z",
            }
        ]

        result = _parse_repair_times(bugs)

        assert len(result) == 1
        assert result[0] == 0.5  # 12 hours = 0.5 days

    def test_handles_invalid_dates(self):
        """Test handling of invalid date formats"""
        bugs = [
            {
                "System.CreatedDate": "invalid-date",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-05T10:00:00Z",
            },
            {
                "System.CreatedDate": "2026-01-01T10:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": "invalid-date",
            },
        ]

        result = _parse_repair_times(bugs)

        # Both should be skipped due to invalid dates
        assert len(result) == 0


# =============================================================================
# Tests for calculate_mttr
# =============================================================================


class TestCalculateMTTR:
    """Tests for MTTR calculations"""

    def test_empty_bugs_returns_none_values(self):
        """Test empty bug list returns None for all MTTR metrics"""
        result = calculate_mttr([])

        assert result["mttr_days"] is None
        assert result["median_mttr_days"] is None
        assert result["p85_mttr_days"] is None
        assert result["p95_mttr_days"] is None
        assert result["sample_size"] == 0

    def test_calculates_mttr_correctly(self):
        """Test MTTR calculation with valid bugs"""
        bugs = [
            {
                "System.CreatedDate": "2026-01-01T10:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-05T10:00:00Z",
            },
            {
                "System.CreatedDate": "2026-01-02T10:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-08T10:00:00Z",
            },
            {
                "System.CreatedDate": "2026-01-03T10:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-06T10:00:00Z",
            },
        ]

        result = calculate_mttr(bugs)

        assert result["sample_size"] == 3
        # Mean: (4 + 6 + 3) / 3 = 4.33
        assert 4.0 <= result["mttr_days"] <= 4.5
        # Median: 4
        assert result["median_mttr_days"] == 4.0

    def test_calculates_distribution_buckets(self):
        """Test MTTR distribution bucket calculations"""
        bugs = [
            {
                "System.CreatedDate": "2026-01-01T10:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-01T20:00:00Z",  # < 1 day
            },
            {
                "System.CreatedDate": "2026-01-01T10:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-04T10:00:00Z",  # 1-7 days
            },
            {
                "System.CreatedDate": "2026-01-01T10:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-15T10:00:00Z",  # 7-30 days
            },
            {
                "System.CreatedDate": "2026-01-01T10:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": "2026-02-15T10:00:00Z",  # 30+ days
            },
        ]

        result = calculate_mttr(bugs)

        assert result["mttr_distribution"]["0-1_days"] == 1
        assert result["mttr_distribution"]["1-7_days"] == 1
        assert result["mttr_distribution"]["7-30_days"] == 1
        assert result["mttr_distribution"]["30+_days"] == 1

    def test_handles_only_open_bugs(self):
        """Test handling when all bugs are open (no closed dates)"""
        bugs: list[dict] = [
            {"System.CreatedDate": "2026-01-01T10:00:00Z"},
            {"System.CreatedDate": "2026-01-02T10:00:00Z", "Microsoft.VSTS.Common.ClosedDate": None},
        ]

        result = calculate_mttr(bugs)

        assert result["mttr_days"] is None
        assert result["sample_size"] == 0

    def test_mixed_open_and_closed_bugs(self):
        """Test MTTR calculation with mixed open and closed bugs"""
        bugs: list[dict] = [
            {
                "System.CreatedDate": "2026-01-01T10:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-05T10:00:00Z",
            },
            {
                "System.CreatedDate": "2026-01-02T10:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": None,
            },
            {
                "System.CreatedDate": "2026-01-03T10:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-06T10:00:00Z",
            },
        ]

        result = calculate_mttr(bugs)

        # Only closed bugs should be counted
        assert result["sample_size"] == 2

    def test_calculates_percentiles(self):
        """Test percentile calculations for MTTR"""
        # Create 100 bugs with repair times from 1 to 100 days
        bugs: list[dict] = [
            {
                "System.CreatedDate": "2026-01-01T10:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": (
                    f"2026-01-{min(i + 1, 31):02d}T10:00:00Z"
                    if i < 30
                    else (
                        f"2026-02-{min(i - 29, 28):02d}T10:00:00Z"
                        if i < 58
                        else f"2026-03-{min(i - 57, 31):02d}T10:00:00Z"
                    )
                ),
            }
            for i in range(1, 101)
        ]

        result = calculate_mttr(bugs)

        assert result["sample_size"] == 100
        assert result["p85_mttr_days"] is not None
        assert result["p95_mttr_days"] is not None


# =============================================================================
# Tests for calculate_test_execution_time
# =============================================================================


class TestCalculateTestExecutionTime:
    """Tests for test execution time calculations"""

    def test_empty_test_runs_returns_none(self, mock_test_client):
        """Test empty test runs returns None values"""
        mock_test_client.get_test_runs.return_value = []

        result = calculate_test_execution_time(mock_test_client, "TestProject")

        assert result["sample_size"] == 0
        assert result["median_minutes"] is None
        assert result["p85_minutes"] is None
        assert result["p95_minutes"] is None

    def test_calculates_execution_time_correctly(self, mock_test_client):
        """Test execution time calculation with valid test runs"""
        run1 = Mock()
        run1.started_date = datetime(2026, 2, 10, 10, 0, 0, tzinfo=UTC)
        run1.completed_date = datetime(2026, 2, 10, 10, 30, 0, tzinfo=UTC)  # 30 minutes

        run2 = Mock()
        run2.started_date = datetime(2026, 2, 10, 11, 0, 0, tzinfo=UTC)
        run2.completed_date = datetime(2026, 2, 10, 11, 45, 0, tzinfo=UTC)  # 45 minutes

        run3 = Mock()
        run3.started_date = datetime(2026, 2, 10, 12, 0, 0, tzinfo=UTC)
        run3.completed_date = datetime(2026, 2, 10, 12, 15, 0, tzinfo=UTC)  # 15 minutes

        mock_test_client.get_test_runs.return_value = [run1, run2, run3]

        result = calculate_test_execution_time(mock_test_client, "TestProject")

        assert result["sample_size"] == 3
        assert result["median_minutes"] == 30.0

    def test_skips_runs_without_timestamps(self, mock_test_client):
        """Test that runs without timestamps are skipped"""
        run1 = Mock()
        run1.started_date = datetime(2026, 2, 10, 10, 0, 0, tzinfo=UTC)
        run1.completed_date = datetime(2026, 2, 10, 10, 30, 0, tzinfo=UTC)

        run2 = Mock()
        run2.started_date = None
        run2.completed_date = datetime(2026, 2, 10, 11, 30, 0, tzinfo=UTC)

        run3 = Mock()
        run3.started_date = datetime(2026, 2, 10, 12, 0, 0, tzinfo=UTC)
        run3.completed_date = None

        mock_test_client.get_test_runs.return_value = [run1, run2, run3]

        result = calculate_test_execution_time(mock_test_client, "TestProject")

        assert result["sample_size"] == 1

    def test_skips_negative_duration(self, mock_test_client):
        """Test that negative durations are skipped"""
        run1 = Mock()
        run1.started_date = datetime(2026, 2, 10, 10, 30, 0, tzinfo=UTC)
        run1.completed_date = datetime(2026, 2, 10, 10, 0, 0, tzinfo=UTC)  # Negative

        run2 = Mock()
        run2.started_date = datetime(2026, 2, 10, 11, 0, 0, tzinfo=UTC)
        run2.completed_date = datetime(2026, 2, 10, 11, 30, 0, tzinfo=UTC)  # Valid

        mock_test_client.get_test_runs.return_value = [run1, run2]

        result = calculate_test_execution_time(mock_test_client, "TestProject")

        assert result["sample_size"] == 1

    def test_handles_api_error(self, mock_test_client):
        """Test handling of Azure DevOps API errors"""
        # Mock a generic API error that matches the except clause
        mock_test_client.get_test_runs.side_effect = ValueError("API connection failed")

        result = calculate_test_execution_time(mock_test_client, "TestProject")

        assert result["sample_size"] == 0
        assert result["median_minutes"] is None

    def test_handles_attribute_error(self, mock_test_client):
        """Test handling of attribute errors"""
        mock_test_client.get_test_runs.side_effect = AttributeError("Missing attribute")

        result = calculate_test_execution_time(mock_test_client, "TestProject")

        assert result["sample_size"] == 0

    def test_requests_top_50_runs(self, mock_test_client):
        """Test that function requests top 50 test runs"""
        mock_test_client.get_test_runs.return_value = []

        calculate_test_execution_time(mock_test_client, "TestProject")

        mock_test_client.get_test_runs.assert_called_once_with(project="TestProject", top=50)


# =============================================================================
# Tests for collect_quality_metrics_for_project
# =============================================================================


class TestCollectQualityMetricsForProject:
    """Tests for project-level metrics collection orchestration"""

    @patch("execution.collectors.ado_quality_metrics.filter_security_bugs")
    @patch("execution.collectors.ado_quality_metrics.calculate_test_execution_time")
    @patch("execution.collectors.ado_quality_metrics.calculate_mttr")
    @patch("execution.collectors.ado_quality_metrics.calculate_bug_age_distribution")
    @patch("execution.collectors.ado_quality_metrics.query_bugs_for_quality")
    def test_collects_all_metrics_for_project(
        self, mock_query, mock_age_dist, mock_mttr, mock_test_exec, mock_filter, mock_connection, sample_project
    ):
        """Test that all metrics are collected for a project"""
        # Setup mocks
        mock_query.return_value = {"all_bugs": [{"System.Id": 1}], "open_bugs": [{"System.Id": 1}]}
        mock_filter.return_value = ([{"System.Id": 1}], 0)
        mock_age_dist.return_value = {
            "median_age_days": 10.0,
            "p85_age_days": 15.0,
            "p95_age_days": 20.0,
            "sample_size": 1,
            "ages_distribution": {"0-7_days": 0, "8-30_days": 1, "31-90_days": 0, "90+_days": 0},
        }
        mock_mttr.return_value = {
            "mttr_days": 5.0,
            "median_mttr_days": 4.5,
            "p85_mttr_days": 7.0,
            "p95_mttr_days": 9.0,
            "sample_size": 1,
            "mttr_distribution": {"0-1_days": 0, "1-7_days": 1, "7-30_days": 0, "30+_days": 0},
        }
        mock_test_exec.return_value = {
            "median_minutes": 20.0,
            "p85_minutes": 25.0,
            "p95_minutes": 30.0,
            "sample_size": 1,
        }

        config = {"lookback_days": 90}
        result = collect_quality_metrics_for_project(mock_connection, sample_project, config)

        assert result["project_key"] == "eng-platform"
        assert result["project_name"] == "Engineering Platform"
        assert "bug_age_distribution" in result
        assert "mttr" in result
        assert "test_execution_time" in result
        assert result["total_bugs_analyzed"] == 1
        assert result["open_bugs_count"] == 1

    @patch("execution.collectors.ado_quality_metrics.filter_security_bugs")
    @patch("execution.collectors.ado_quality_metrics.calculate_test_execution_time")
    @patch("execution.collectors.ado_quality_metrics.calculate_mttr")
    @patch("execution.collectors.ado_quality_metrics.calculate_bug_age_distribution")
    @patch("execution.collectors.ado_quality_metrics.query_bugs_for_quality")
    def test_uses_ado_project_name_if_different(
        self, mock_query, mock_age_dist, mock_mttr, mock_test_exec, mock_filter, mock_connection, sample_project
    ):
        """Test that ADO project name is used if different from display name"""
        mock_query.return_value = {"all_bugs": [], "open_bugs": []}
        mock_filter.return_value = ([], 0)
        mock_age_dist.return_value = {
            "median_age_days": None,
            "p85_age_days": None,
            "p95_age_days": None,
            "sample_size": 0,
            "ages_distribution": {"0-7_days": 0, "8-30_days": 0, "31-90_days": 0, "90+_days": 0},
        }
        mock_mttr.return_value = {
            "mttr_days": None,
            "median_mttr_days": None,
            "p85_mttr_days": None,
            "p95_mttr_days": None,
            "sample_size": 0,
            "mttr_distribution": {"0-1_days": 0, "1-7_days": 0, "7-30_days": 0, "30+_days": 0},
        }
        mock_test_exec.return_value = {
            "median_minutes": None,
            "p85_minutes": None,
            "p95_minutes": None,
            "sample_size": 0,
        }

        config = {"lookback_days": 90}
        collect_quality_metrics_for_project(mock_connection, sample_project, config)

        # Verify ADO project name was used
        mock_query.assert_called_once()
        call_args = mock_query.call_args
        assert call_args[0][1] == "EngineeringPlatform"

    @patch("execution.collectors.ado_quality_metrics.filter_security_bugs")
    @patch("execution.collectors.ado_quality_metrics.calculate_test_execution_time")
    @patch("execution.collectors.ado_quality_metrics.calculate_mttr")
    @patch("execution.collectors.ado_quality_metrics.calculate_bug_age_distribution")
    @patch("execution.collectors.ado_quality_metrics.query_bugs_for_quality")
    def test_applies_area_path_filter(
        self,
        mock_query,
        mock_age_dist,
        mock_mttr,
        mock_test_exec,
        mock_filter,
        mock_connection,
        sample_project_with_area_filter,
    ):
        """Test that area path filter is passed to query"""
        mock_query.return_value = {"all_bugs": [], "open_bugs": []}
        mock_filter.return_value = ([], 0)
        mock_age_dist.return_value = {
            "median_age_days": None,
            "p85_age_days": None,
            "p95_age_days": None,
            "sample_size": 0,
            "ages_distribution": {"0-7_days": 0, "8-30_days": 0, "31-90_days": 0, "90+_days": 0},
        }
        mock_mttr.return_value = {
            "mttr_days": None,
            "median_mttr_days": None,
            "p85_mttr_days": None,
            "p95_mttr_days": None,
            "sample_size": 0,
            "mttr_distribution": {"0-1_days": 0, "1-7_days": 0, "7-30_days": 0, "30+_days": 0},
        }
        mock_test_exec.return_value = {
            "median_minutes": None,
            "p85_minutes": None,
            "p95_minutes": None,
            "sample_size": 0,
        }

        config = {"lookback_days": 90}
        collect_quality_metrics_for_project(mock_connection, sample_project_with_area_filter, config)

        call_args = mock_query.call_args
        assert call_args[1]["area_path_filter"] == "EXCLUDE:EngineeringPlatform\\Archive"

    @patch("execution.collectors.ado_quality_metrics.filter_security_bugs")
    @patch("execution.collectors.ado_quality_metrics.calculate_test_execution_time")
    @patch("execution.collectors.ado_quality_metrics.calculate_mttr")
    @patch("execution.collectors.ado_quality_metrics.calculate_bug_age_distribution")
    @patch("execution.collectors.ado_quality_metrics.query_bugs_for_quality")
    def test_filters_security_bugs(
        self, mock_query, mock_age_dist, mock_mttr, mock_test_exec, mock_filter, mock_connection, sample_project
    ):
        """Test that security bugs are filtered out"""
        mock_query.return_value = {
            "all_bugs": [{"System.Id": 1}, {"System.Id": 2, "System.Tags": "armorcode"}],
            "open_bugs": [{"System.Id": 2, "System.Tags": "armorcode"}],
        }
        mock_filter.side_effect = [([{"System.Id": 1}], 1), ([], 1)]
        mock_age_dist.return_value = {
            "median_age_days": None,
            "p85_age_days": None,
            "p95_age_days": None,
            "sample_size": 0,
            "ages_distribution": {"0-7_days": 0, "8-30_days": 0, "31-90_days": 0, "90+_days": 0},
        }
        mock_mttr.return_value = {
            "mttr_days": None,
            "median_mttr_days": None,
            "p85_mttr_days": None,
            "p95_mttr_days": None,
            "sample_size": 0,
            "mttr_distribution": {"0-1_days": 0, "1-7_days": 0, "7-30_days": 0, "30+_days": 0},
        }
        mock_test_exec.return_value = {
            "median_minutes": None,
            "p85_minutes": None,
            "p95_minutes": None,
            "sample_size": 0,
        }

        config = {"lookback_days": 90}
        result = collect_quality_metrics_for_project(mock_connection, sample_project, config)

        assert result["excluded_security_bugs"]["total"] == 1
        assert result["excluded_security_bugs"]["open"] == 1
        assert mock_filter.call_count == 2

    @patch("execution.collectors.ado_quality_metrics.filter_security_bugs")
    @patch("execution.collectors.ado_quality_metrics.calculate_test_execution_time")
    @patch("execution.collectors.ado_quality_metrics.calculate_mttr")
    @patch("execution.collectors.ado_quality_metrics.calculate_bug_age_distribution")
    @patch("execution.collectors.ado_quality_metrics.query_bugs_for_quality")
    def test_includes_collection_timestamp(
        self, mock_query, mock_age_dist, mock_mttr, mock_test_exec, mock_filter, mock_connection, sample_project
    ):
        """Test that collection timestamp is included"""
        mock_query.return_value = {"all_bugs": [], "open_bugs": []}
        mock_filter.return_value = ([], 0)
        mock_age_dist.return_value = {
            "median_age_days": None,
            "p85_age_days": None,
            "p95_age_days": None,
            "sample_size": 0,
            "ages_distribution": {"0-7_days": 0, "8-30_days": 0, "31-90_days": 0, "90+_days": 0},
        }
        mock_mttr.return_value = {
            "mttr_days": None,
            "median_mttr_days": None,
            "p85_mttr_days": None,
            "p95_mttr_days": None,
            "sample_size": 0,
            "mttr_distribution": {"0-1_days": 0, "1-7_days": 0, "7-30_days": 0, "30+_days": 0},
        }
        mock_test_exec.return_value = {
            "median_minutes": None,
            "p85_minutes": None,
            "p95_minutes": None,
            "sample_size": 0,
        }

        config = {"lookback_days": 90}
        result = collect_quality_metrics_for_project(mock_connection, sample_project, config)

        assert "collected_at" in result
        # Verify it's a valid ISO timestamp
        datetime.fromisoformat(result["collected_at"])


# =============================================================================
# Tests for save_quality_metrics
# =============================================================================


class TestSaveQualityMetrics:
    """Tests for saving quality metrics to history file"""

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    def test_saves_metrics_to_new_file(self, mock_load, mock_save, sample_quality_metrics, temp_history_file):
        """Test saving metrics to a new file"""
        mock_load.return_value = {"weeks": []}

        result = save_quality_metrics(sample_quality_metrics, str(temp_history_file))

        assert result is True
        mock_save.assert_called_once()

        # Verify the saved data structure
        saved_data = mock_save.call_args[0][0]
        assert "weeks" in saved_data
        assert len(saved_data["weeks"]) == 1

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    def test_appends_to_existing_history(self, mock_load, mock_save, sample_quality_metrics, temp_history_file):
        """Test appending to existing history file"""
        existing_history = {
            "weeks": [
                {"week_date": "2026-02-03", "projects": []},
                {"week_date": "2026-02-10", "projects": []},
            ]
        }
        mock_load.return_value = existing_history

        save_quality_metrics(sample_quality_metrics, str(temp_history_file))

        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["weeks"]) == 3

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    def test_keeps_only_last_52_weeks(self, mock_load, mock_save, sample_quality_metrics, temp_history_file):
        """Test that only last 52 weeks are kept"""
        # Create 52 weeks of existing data
        existing_history = {
            "weeks": [{"week_date": f"2025-{i:02d}-01", "projects": []} for i in range(1, 13)] * 5
        }  # 60 weeks

        mock_load.return_value = existing_history

        save_quality_metrics(sample_quality_metrics, str(temp_history_file))

        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["weeks"]) == 52

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    def test_rejects_empty_projects(self, mock_load, mock_save, temp_history_file):
        """Test that metrics with no projects are rejected"""
        empty_metrics = {"week_date": "2026-02-10", "projects": []}

        result = save_quality_metrics(empty_metrics, str(temp_history_file))

        assert result is False
        mock_save.assert_not_called()

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    def test_rejects_all_zero_bugs(self, mock_load, mock_save, temp_history_file):
        """Test that metrics with all zero bugs are rejected"""
        zero_metrics = {
            "week_date": "2026-02-10",
            "projects": [
                {"project_key": "test", "total_bugs_analyzed": 0, "open_bugs_count": 0},
                {"project_key": "test2", "total_bugs_analyzed": 0, "open_bugs_count": 0},
            ],
        }

        result = save_quality_metrics(zero_metrics, str(temp_history_file))

        assert result is False
        mock_save.assert_not_called()

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    def test_accepts_some_zero_some_nonzero(self, mock_load, mock_save, temp_history_file):
        """Test that metrics with some zero and some non-zero are accepted"""
        mock_load.return_value = {"weeks": []}

        mixed_metrics = {
            "week_date": "2026-02-10",
            "projects": [
                {"project_key": "test1", "total_bugs_analyzed": 0, "open_bugs_count": 0},
                {"project_key": "test2", "total_bugs_analyzed": 10, "open_bugs_count": 5},
            ],
        }

        result = save_quality_metrics(mixed_metrics, str(temp_history_file))

        assert result is True
        mock_save.assert_called_once()

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    def test_handles_corrupted_history_file(
        self, mock_load, mock_save, sample_quality_metrics, temp_history_file, caplog
    ):
        """Test handling of corrupted history file"""
        # Return invalid structure
        mock_load.return_value = {"invalid": "structure"}

        with caplog.at_level(logging.WARNING):
            result = save_quality_metrics(sample_quality_metrics, str(temp_history_file))

        assert result is True
        assert "invalid structure" in caplog.text

        # Should recreate structure
        saved_data = mock_save.call_args[0][0]
        assert "weeks" in saved_data
        assert len(saved_data["weeks"]) == 1

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    def test_handles_save_error(self, mock_load, mock_save, sample_quality_metrics, temp_history_file, caplog):
        """Test handling of save errors"""
        mock_load.return_value = {"weeks": []}
        mock_save.side_effect = OSError("Disk full")

        with caplog.at_level(logging.ERROR):
            result = save_quality_metrics(sample_quality_metrics, str(temp_history_file))

        assert result is False
        assert "Failed to save" in caplog.text

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    def test_creates_directory_if_missing(self, mock_load, mock_save, sample_quality_metrics, temp_history_file):
        """Test that parent directory is created if missing"""
        mock_load.return_value = {"weeks": []}

        # Use a path with non-existent parent
        nested_path = temp_history_file.parent / "nested" / "dir" / "quality.json"

        result = save_quality_metrics(sample_quality_metrics, str(nested_path))

        assert result is True
        assert nested_path.parent.exists()
