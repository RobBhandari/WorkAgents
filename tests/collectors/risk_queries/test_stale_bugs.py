#!/usr/bin/env python3
"""
Tests for StaleBugsQuery

Comprehensive test coverage for stale bug query class.
Tests WIQL query generation, age calculation, result parsing, filtering, and edge cases.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from azure.devops.exceptions import AzureDevOpsServiceError

from execution.collectors.risk_queries.stale_bugs import StaleBugsQuery
from execution.utils.ado_batch_utils import BatchFetchError


@pytest.fixture
def mock_wit_client():
    """Create a mock Work Item Tracking client."""
    return MagicMock()


@pytest.fixture
def sample_stale_bugs():
    """Sample stale bug data for testing."""
    return [
        {
            "System.Id": 2001,
            "System.Title": "Old UI bug from last quarter",
            "System.State": "Active",
            "System.CreatedDate": "2023-10-15T10:00:00Z",
            "Microsoft.VSTS.Common.Priority": 3,
            "Microsoft.VSTS.Common.Severity": "3 - Medium",
            "System.Tags": "",
            "System.CreatedBy": {"displayName": "John Doe"},
            "Microsoft.VSTS.Common.StateChangeDate": "2023-10-15T10:00:00Z",
        },
        {
            "System.Id": 2002,
            "System.Title": "Stale data sync issue",
            "System.State": "Active",
            "System.CreatedDate": "2023-11-01T14:30:00Z",
            "Microsoft.VSTS.Common.Priority": 2,
            "Microsoft.VSTS.Common.Severity": "2 - High",
            "System.Tags": "",
            "System.CreatedBy": {"displayName": "Jane Smith"},
            "Microsoft.VSTS.Common.StateChangeDate": "2023-11-01T14:30:00Z",
        },
        {
            "System.Id": 2003,
            "System.Title": "Security bug found months ago",
            "System.State": "New",
            "System.CreatedDate": "2023-09-20T09:00:00Z",
            "Microsoft.VSTS.Common.Priority": 1,
            "Microsoft.VSTS.Common.Severity": "1 - Critical",
            "System.Tags": "armorcode;security",
            "System.CreatedBy": {"displayName": "ArmorCode Bot"},
            "Microsoft.VSTS.Common.StateChangeDate": "2023-09-20T09:00:00Z",
        },
    ]


class TestStaleBugsQueryInit:
    """Test StaleBugsQuery initialization."""

    def test_init_with_client_default_threshold(self, mock_wit_client):
        """Test initialization with default threshold."""
        query = StaleBugsQuery(mock_wit_client)
        assert query.wit_client is mock_wit_client
        assert query.stale_threshold_days == 30

    def test_init_with_custom_threshold(self, mock_wit_client):
        """Test initialization with custom threshold."""
        query = StaleBugsQuery(mock_wit_client, stale_threshold_days=60)
        assert query.stale_threshold_days == 60

    def test_init_stores_client_reference(self, mock_wit_client):
        """Test that client reference is stored correctly."""
        query = StaleBugsQuery(mock_wit_client)
        assert hasattr(query, "wit_client")
        assert query.wit_client == mock_wit_client


class TestStaleBugsQueryWIQL:
    """Test WIQL query building."""

    def test_build_wiql_basic(self, mock_wit_client):
        """Test basic WIQL query generation."""
        query = StaleBugsQuery(mock_wit_client, stale_threshold_days=30)
        stale_date = "2024-01-01"
        wiql = query.build_wiql("MyProject", stale_date)

        assert "MyProject" in wiql
        assert "System.WorkItemType] = 'Bug'" in wiql
        assert "System.CreatedDate] < '2024-01-01'" in wiql
        assert "System.State] NOT IN ('Closed', 'Removed')" in wiql

    def test_build_wiql_with_area_filter(self, mock_wit_client):
        """Test WIQL query with area path filter."""
        query = StaleBugsQuery(mock_wit_client)
        stale_date = "2024-01-01"
        wiql = query.build_wiql("MyProject", stale_date, area_filter_clause="AND [System.AreaPath] NOT UNDER 'Test'")

        assert "MyProject" in wiql
        assert "AND [System.AreaPath] NOT UNDER 'Test'" in wiql

    def test_build_wiql_orders_by_created_date(self, mock_wit_client):
        """Test that WIQL orders by created date ascending (oldest first)."""
        query = StaleBugsQuery(mock_wit_client)
        stale_date = "2024-01-01"
        wiql = query.build_wiql("MyProject", stale_date)

        assert "ORDER BY [System.CreatedDate] ASC" in wiql

    def test_build_wiql_selects_required_fields(self, mock_wit_client):
        """Test that WIQL selects all required fields."""
        query = StaleBugsQuery(mock_wit_client)
        stale_date = "2024-01-01"
        wiql = query.build_wiql("MyProject", stale_date)

        required_fields = [
            "System.Id",
            "System.Title",
            "System.State",
            "System.CreatedDate",
            "Microsoft.VSTS.Common.Priority",
            "Microsoft.VSTS.Common.Severity",
            "System.Tags",
            "System.CreatedBy",
            "Microsoft.VSTS.Common.StateChangeDate",
        ]
        for field in required_fields:
            assert field in wiql


class TestStaleBugsQueryAreaFilter:
    """Test area path filter building."""

    def test_build_area_filter_exclude(self, mock_wit_client):
        """Test building EXCLUDE area filter clause."""
        query = StaleBugsQuery(mock_wit_client)
        clause = query._build_area_filter_clause("EXCLUDE:TestPath")

        assert "NOT UNDER" in clause
        assert "TestPath" in clause

    def test_build_area_filter_include(self, mock_wit_client):
        """Test building INCLUDE area filter clause."""
        query = StaleBugsQuery(mock_wit_client)
        clause = query._build_area_filter_clause("INCLUDE:ProdPath")

        assert "UNDER" in clause
        assert "NOT UNDER" not in clause
        assert "ProdPath" in clause

    def test_build_area_filter_none(self, mock_wit_client):
        """Test building area filter with None returns empty string."""
        query = StaleBugsQuery(mock_wit_client)
        clause = query._build_area_filter_clause(None)

        assert clause == ""

    def test_build_area_filter_empty_string(self, mock_wit_client):
        """Test building area filter with empty string returns empty string."""
        query = StaleBugsQuery(mock_wit_client)
        clause = query._build_area_filter_clause("")

        assert clause == ""


class TestStaleBugsQueryAgeCalculation:
    """Test bug age calculation."""

    def test_calculate_bug_age_days_iso_string(self, mock_wit_client):
        """Test age calculation with ISO date string."""
        query = StaleBugsQuery(mock_wit_client)

        # Bug created 100 days ago
        created_date = (datetime.now() - timedelta(days=100)).isoformat()
        bug = {"System.CreatedDate": created_date, "System.Id": 1001}

        age = query._calculate_bug_age_days(bug)

        # Should be approximately 100 days (allow small variance for test execution time)
        assert 99 <= age <= 101

    def test_calculate_bug_age_days_with_timezone(self, mock_wit_client):
        """Test age calculation with timezone-aware ISO string."""
        query = StaleBugsQuery(mock_wit_client)

        # Bug created 50 days ago with Z timezone
        created_date = (datetime.now() - timedelta(days=50)).isoformat() + "Z"
        bug = {"System.CreatedDate": created_date, "System.Id": 1002}

        age = query._calculate_bug_age_days(bug)

        assert 49 <= age <= 51

    def test_calculate_bug_age_days_no_created_date(self, mock_wit_client):
        """Test age calculation when created date is missing."""
        query = StaleBugsQuery(mock_wit_client)
        bug = {"System.Id": 1003}

        age = query._calculate_bug_age_days(bug)

        assert age == 0

    def test_calculate_bug_age_days_invalid_date_format(self, mock_wit_client):
        """Test age calculation with invalid date format."""
        query = StaleBugsQuery(mock_wit_client)
        bug = {"System.CreatedDate": "invalid-date", "System.Id": 1004}

        age = query._calculate_bug_age_days(bug)

        # Should return 0 for invalid dates
        assert age == 0

    def test_calculate_bug_age_days_datetime_object(self, mock_wit_client):
        """Test age calculation when created date is already a datetime object."""
        query = StaleBugsQuery(mock_wit_client)

        # Bug created 75 days ago
        from datetime import timezone

        created_date = datetime.now(UTC) - timedelta(days=75)
        bug = {"System.CreatedDate": created_date, "System.Id": 1005}

        age = query._calculate_bug_age_days(bug)

        assert 74 <= age <= 76


class TestStaleBugsQueryExecute:
    """Test query execution."""

    def test_execute_success(self, mock_wit_client, sample_stale_bugs):
        """Test successful query execution."""
        # Mock query result
        mock_work_items = [Mock(id=2001), Mock(id=2002), Mock(id=2003)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        # Mock batch fetch to return bugs (filter out security bug later)
        with patch("execution.collectors.risk_queries.stale_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (sample_stale_bugs, [])

            with patch("execution.collectors.risk_queries.stale_bugs.filter_security_bugs") as mock_filter:
                # Filter out bug 2003 (security bug)
                filtered_bugs = sample_stale_bugs[:2]
                mock_filter.return_value = (filtered_bugs, 1)

                query = StaleBugsQuery(mock_wit_client, stale_threshold_days=30)
                result = query.execute("MyProject")

                assert result["project"] == "MyProject"
                assert result["count"] == 2
                assert result["stale_threshold_days"] == 30
                assert result["excluded_security_bugs"] == 1
                assert len(result["stale_bugs"]) == 2

    def test_execute_no_bugs_found(self, mock_wit_client):
        """Test query execution when no bugs found."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = StaleBugsQuery(mock_wit_client, stale_threshold_days=45)
        result = query.execute("MyProject")

        assert result["project"] == "MyProject"
        assert result["count"] == 0
        assert result["stale_threshold_days"] == 45
        assert result["avg_age_days"] == 0.0
        assert result["oldest_bug_days"] == 0
        assert result["excluded_security_bugs"] == 0
        assert result["stale_bugs"] == []

    def test_execute_with_area_filter(self, mock_wit_client, sample_stale_bugs):
        """Test query execution with area path filter."""
        mock_work_items = [Mock(id=2001), Mock(id=2002)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.stale_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (sample_stale_bugs[:2], [])

            with patch("execution.collectors.risk_queries.stale_bugs.filter_security_bugs") as mock_filter:
                mock_filter.return_value = (sample_stale_bugs[:2], 0)

                query = StaleBugsQuery(mock_wit_client)
                result = query.execute("MyProject", area_path_filter="EXCLUDE:TestArea")

                assert result["count"] == 2

    def test_execute_adds_age_days_to_bugs(self, mock_wit_client):
        """Test that age_days field is added to each bug."""
        mock_work_items = [Mock(id=2001)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        created_date = (datetime.now() - timedelta(days=60)).isoformat()
        bugs = [
            {
                "System.Id": 2001,
                "System.CreatedDate": created_date,
                "System.CreatedBy": {"displayName": "John Doe"},
                "System.Tags": "",
            }
        ]

        with patch("execution.collectors.risk_queries.stale_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (bugs, [])

            with patch("execution.collectors.risk_queries.stale_bugs.filter_security_bugs") as mock_filter:
                mock_filter.return_value = (bugs, 0)

                query = StaleBugsQuery(mock_wit_client, stale_threshold_days=30)
                result = query.execute("MyProject")

                assert "age_days" in result["stale_bugs"][0]
                assert 59 <= result["stale_bugs"][0]["age_days"] <= 61

    def test_execute_calculates_avg_age(self, mock_wit_client):
        """Test that average age is calculated correctly."""
        mock_work_items = [Mock(id=2001), Mock(id=2002)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        # Bug 1: 60 days old, Bug 2: 40 days old (avg = 50)
        bugs = [
            {
                "System.Id": 2001,
                "System.CreatedDate": (datetime.now() - timedelta(days=60)).isoformat(),
                "System.CreatedBy": {"displayName": "John Doe"},
                "System.Tags": "",
            },
            {
                "System.Id": 2002,
                "System.CreatedDate": (datetime.now() - timedelta(days=40)).isoformat(),
                "System.CreatedBy": {"displayName": "Jane Smith"},
                "System.Tags": "",
            },
        ]

        with patch("execution.collectors.risk_queries.stale_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (bugs, [])

            with patch("execution.collectors.risk_queries.stale_bugs.filter_security_bugs") as mock_filter:
                mock_filter.return_value = (bugs, 0)

                query = StaleBugsQuery(mock_wit_client)
                result = query.execute("MyProject")

                # Average should be around 50 days
                assert 48 <= result["avg_age_days"] <= 52

    def test_execute_finds_oldest_bug(self, mock_wit_client):
        """Test that oldest bug is identified correctly."""
        mock_work_items = [Mock(id=2001), Mock(id=2002)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        # Bug 1: 90 days old, Bug 2: 45 days old
        bugs = [
            {
                "System.Id": 2001,
                "System.CreatedDate": (datetime.now() - timedelta(days=90)).isoformat(),
                "System.CreatedBy": {"displayName": "John Doe"},
                "System.Tags": "",
            },
            {
                "System.Id": 2002,
                "System.CreatedDate": (datetime.now() - timedelta(days=45)).isoformat(),
                "System.CreatedBy": {"displayName": "Jane Smith"},
                "System.Tags": "",
            },
        ]

        with patch("execution.collectors.risk_queries.stale_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (bugs, [])

            with patch("execution.collectors.risk_queries.stale_bugs.filter_security_bugs") as mock_filter:
                mock_filter.return_value = (bugs, 0)

                query = StaleBugsQuery(mock_wit_client)
                result = query.execute("MyProject")

                # Oldest should be around 90 days
                assert 88 <= result["oldest_bug_days"] <= 92

    def test_execute_filters_security_bugs(self, mock_wit_client, sample_stale_bugs):
        """Test that security bugs are filtered out."""
        mock_work_items = [Mock(id=2001), Mock(id=2002), Mock(id=2003)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.stale_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (sample_stale_bugs, [])

            with patch("execution.collectors.risk_queries.stale_bugs.filter_security_bugs") as mock_filter:
                # Simulate filtering out 1 security bug
                filtered_bugs = sample_stale_bugs[:2]
                mock_filter.return_value = (filtered_bugs, 1)

                query = StaleBugsQuery(mock_wit_client)
                result = query.execute("MyProject")

                assert result["excluded_security_bugs"] == 1
                assert result["count"] == 2


class TestStaleBugsQueryErrors:
    """Test error handling."""

    def test_execute_ado_service_error(self, mock_wit_client):
        """Test handling of AzureDevOpsServiceError."""
        # Create proper AzureDevOpsServiceError with wrapped exception
        wrapped_exception = Mock()
        wrapped_exception.message = "ADO API error"
        wrapped_exception.inner_exception = None
        wrapped_exception.exception_id = None
        wrapped_exception.type_name = "TestError"
        wrapped_exception.type_key = "TestError"
        wrapped_exception.error_code = 0
        wrapped_exception.event_id = 0

        mock_wit_client.query_by_wiql.side_effect = AzureDevOpsServiceError(wrapped_exception)

        query = StaleBugsQuery(mock_wit_client)

        with pytest.raises(AzureDevOpsServiceError):
            query.execute("MyProject")

    def test_execute_batch_fetch_error(self, mock_wit_client):
        """Test handling of BatchFetchError."""
        mock_work_items = [Mock(id=2001)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.stale_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.side_effect = BatchFetchError("Batch fetch failed")

            query = StaleBugsQuery(mock_wit_client)

            with pytest.raises(BatchFetchError):
                query.execute("MyProject")

    def test_execute_handles_failed_ids(self, mock_wit_client, sample_stale_bugs):
        """Test that failed IDs are logged but don't stop execution."""
        mock_work_items = [Mock(id=2001), Mock(id=2002), Mock(id=2003)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.stale_bugs.batch_fetch_work_items") as mock_batch:
            # Simulate some failed IDs
            mock_batch.return_value = (sample_stale_bugs[:2], [2003])

            with patch("execution.collectors.risk_queries.stale_bugs.filter_security_bugs") as mock_filter:
                mock_filter.return_value = (sample_stale_bugs[:2], 0)

                query = StaleBugsQuery(mock_wit_client)
                result = query.execute("MyProject")

                # Should still return results for successfully fetched bugs
                assert result["count"] == 2


class TestStaleBugsQueryResultStructure:
    """Test result structure and fields."""

    def test_execute_returns_required_fields(self, mock_wit_client):
        """Test that execute returns all required fields."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = StaleBugsQuery(mock_wit_client, stale_threshold_days=30)
        result = query.execute("MyProject")

        required_fields = [
            "project",
            "stale_bugs",
            "count",
            "stale_threshold_days",
            "avg_age_days",
            "oldest_bug_days",
            "excluded_security_bugs",
            "queried_at",
        ]

        for field in required_fields:
            assert field in result

    def test_execute_queried_at_is_iso_format(self, mock_wit_client):
        """Test that queried_at timestamp is in ISO format."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = StaleBugsQuery(mock_wit_client)
        result = query.execute("MyProject")

        # Should be parseable as ISO datetime
        datetime.fromisoformat(result["queried_at"])

    def test_execute_stale_bugs_is_list(self, mock_wit_client):
        """Test that stale_bugs is always a list."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = StaleBugsQuery(mock_wit_client)
        result = query.execute("MyProject")

        assert isinstance(result["stale_bugs"], list)

    def test_execute_counts_are_integers(self, mock_wit_client):
        """Test that all count fields are integers."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = StaleBugsQuery(mock_wit_client, stale_threshold_days=45)
        result = query.execute("MyProject")

        assert isinstance(result["count"], int)
        assert isinstance(result["stale_threshold_days"], int)
        assert isinstance(result["oldest_bug_days"], int)
        assert isinstance(result["excluded_security_bugs"], int)

    def test_execute_avg_age_is_float(self, mock_wit_client):
        """Test that avg_age_days is a float."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = StaleBugsQuery(mock_wit_client)
        result = query.execute("MyProject")

        assert isinstance(result["avg_age_days"], float)

    def test_execute_avg_age_rounded_to_one_decimal(self, mock_wit_client):
        """Test that avg_age_days is rounded to 1 decimal place."""
        mock_work_items = [Mock(id=2001), Mock(id=2002), Mock(id=2003)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        # Create bugs with ages that will result in fractional average
        bugs = [
            {
                "System.Id": 2001,
                "System.CreatedDate": (datetime.now() - timedelta(days=33)).isoformat(),
                "System.CreatedBy": {"displayName": "John Doe"},
                "System.Tags": "",
            },
            {
                "System.Id": 2002,
                "System.CreatedDate": (datetime.now() - timedelta(days=34)).isoformat(),
                "System.CreatedBy": {"displayName": "Jane Smith"},
                "System.Tags": "",
            },
            {
                "System.Id": 2003,
                "System.CreatedDate": (datetime.now() - timedelta(days=35)).isoformat(),
                "System.CreatedBy": {"displayName": "Bob Johnson"},
                "System.Tags": "",
            },
        ]

        with patch("execution.collectors.risk_queries.stale_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (bugs, [])

            with patch("execution.collectors.risk_queries.stale_bugs.filter_security_bugs") as mock_filter:
                mock_filter.return_value = (bugs, 0)

                query = StaleBugsQuery(mock_wit_client)
                result = query.execute("MyProject")

                # Check that result has only 1 decimal place
                assert result["avg_age_days"] == round(result["avg_age_days"], 1)
