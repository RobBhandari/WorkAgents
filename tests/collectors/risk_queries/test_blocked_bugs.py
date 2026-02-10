#!/usr/bin/env python3
"""
Tests for BlockedBugsQuery

Comprehensive test coverage for blocked bug query class.
Tests WIQL query generation, result parsing, filtering, and edge cases.
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from azure.devops.exceptions import AzureDevOpsServiceError

from execution.collectors.risk_queries.blocked_bugs import BlockedBugsQuery
from execution.utils.ado_batch_utils import BatchFetchError


def create_mock_ado_error(message: str = "ADO API error") -> AzureDevOpsServiceError:
    """Create a properly formatted AzureDevOpsServiceError for testing."""
    wrapped_exception = Mock()
    wrapped_exception.message = message
    wrapped_exception.inner_exception = None
    wrapped_exception.exception_id = None
    wrapped_exception.type_name = "TestError"
    wrapped_exception.type_key = None
    wrapped_exception.error_code = 0
    wrapped_exception.event_id = 0
    wrapped_exception.custom_properties = {}
    return AzureDevOpsServiceError(wrapped_exception)


@pytest.fixture
def mock_wit_client():
    """Create a mock Work Item Tracking client."""
    return MagicMock()


@pytest.fixture
def sample_blocked_bugs():
    """Sample blocked bug data for testing."""
    return [
        {
            "System.Id": 2001,
            "System.Title": "Bug blocked by infrastructure issue",
            "System.State": "Active",
            "System.CreatedDate": "2024-01-15T10:00:00Z",
            "Microsoft.VSTS.Common.Priority": 1,
            "Microsoft.VSTS.Common.Severity": "1 - Critical",
            "System.Tags": "",
            "System.CreatedBy": {"displayName": "John Doe"},
            "Microsoft.VSTS.CMMI.Blocked": "Yes",
        },
        {
            "System.Id": 2002,
            "System.Title": "Bug blocked by third-party dependency",
            "System.State": "Active",
            "System.CreatedDate": "2024-01-16T11:30:00Z",
            "Microsoft.VSTS.Common.Priority": 2,
            "Microsoft.VSTS.Common.Severity": "2 - High",
            "System.Tags": "",
            "System.CreatedBy": {"displayName": "Jane Smith"},
            "Microsoft.VSTS.CMMI.Blocked": "Yes",
        },
        {
            "System.Id": 2003,
            "System.Title": "Security bug blocked by vendor",
            "System.State": "New",
            "System.CreatedDate": "2024-01-17T14:00:00Z",
            "Microsoft.VSTS.Common.Priority": 1,
            "Microsoft.VSTS.Common.Severity": "1 - Critical",
            "System.Tags": "armorcode;security",
            "System.CreatedBy": {"displayName": "ArmorCode Bot"},
            "Microsoft.VSTS.CMMI.Blocked": "Yes",
        },
        {
            "System.Id": 2004,
            "System.Title": "Low priority blocked bug",
            "System.State": "Active",
            "System.CreatedDate": "2024-01-18T15:00:00Z",
            "Microsoft.VSTS.Common.Priority": 3,
            "Microsoft.VSTS.Common.Severity": "3 - Medium",
            "System.Tags": "",
            "System.CreatedBy": {"displayName": "Bob Wilson"},
            "Microsoft.VSTS.CMMI.Blocked": "Yes",
        },
    ]


class TestBlockedBugsQueryInit:
    """Test BlockedBugsQuery initialization."""

    def test_init_with_client(self, mock_wit_client):
        """Test initialization with WIT client."""
        query = BlockedBugsQuery(mock_wit_client)
        assert query.wit_client is mock_wit_client

    def test_init_stores_client_reference(self, mock_wit_client):
        """Test that client reference is stored correctly."""
        query = BlockedBugsQuery(mock_wit_client)
        assert hasattr(query, "wit_client")
        assert query.wit_client == mock_wit_client


class TestBlockedBugsQueryWIQL:
    """Test WIQL query building."""

    def test_build_wiql_basic(self, mock_wit_client):
        """Test basic WIQL query generation."""
        query = BlockedBugsQuery(mock_wit_client)
        wiql = query.build_wiql("MyProject")

        assert "MyProject" in wiql
        assert "System.WorkItemType] = 'Bug'" in wiql
        assert "Microsoft.VSTS.CMMI.Blocked] = 'Yes'" in wiql
        assert "System.State] NOT IN ('Closed', 'Removed')" in wiql

    def test_build_wiql_with_area_filter(self, mock_wit_client):
        """Test WIQL query with area path filter."""
        query = BlockedBugsQuery(mock_wit_client)
        wiql = query.build_wiql("MyProject", area_filter_clause="AND [System.AreaPath] NOT UNDER 'Test'")

        assert "MyProject" in wiql
        assert "AND [System.AreaPath] NOT UNDER 'Test'" in wiql

    def test_build_wiql_orders_by_priority_and_date(self, mock_wit_client):
        """Test that WIQL orders by priority first, then created date."""
        query = BlockedBugsQuery(mock_wit_client)
        wiql = query.build_wiql("MyProject")

        assert "ORDER BY [Microsoft.VSTS.Common.Priority] ASC, [System.CreatedDate] ASC" in wiql

    def test_build_wiql_selects_required_fields(self, mock_wit_client):
        """Test that WIQL selects all required fields."""
        query = BlockedBugsQuery(mock_wit_client)
        wiql = query.build_wiql("MyProject")

        required_fields = [
            "System.Id",
            "System.Title",
            "System.State",
            "System.CreatedDate",
            "Microsoft.VSTS.Common.Priority",
            "Microsoft.VSTS.Common.Severity",
            "System.Tags",
            "System.CreatedBy",
            "Microsoft.VSTS.CMMI.Blocked",
        ]
        for field in required_fields:
            assert field in wiql


class TestBlockedBugsQueryAreaFilter:
    """Test area path filter building."""

    def test_build_area_filter_exclude(self, mock_wit_client):
        """Test building EXCLUDE area filter clause."""
        query = BlockedBugsQuery(mock_wit_client)
        clause = query._build_area_filter_clause("EXCLUDE:TestPath")

        assert "NOT UNDER" in clause
        assert "TestPath" in clause

    def test_build_area_filter_include(self, mock_wit_client):
        """Test building INCLUDE area filter clause."""
        query = BlockedBugsQuery(mock_wit_client)
        clause = query._build_area_filter_clause("INCLUDE:ProdPath")

        assert "UNDER" in clause
        assert "NOT UNDER" not in clause
        assert "ProdPath" in clause

    def test_build_area_filter_none(self, mock_wit_client):
        """Test building area filter with None returns empty string."""
        query = BlockedBugsQuery(mock_wit_client)
        clause = query._build_area_filter_clause(None)

        assert clause == ""

    def test_build_area_filter_empty_string(self, mock_wit_client):
        """Test building area filter with empty string returns empty string."""
        query = BlockedBugsQuery(mock_wit_client)
        clause = query._build_area_filter_clause("")

        assert clause == ""


class TestBlockedBugsQueryExecute:
    """Test query execution."""

    def test_execute_success(self, mock_wit_client, sample_blocked_bugs):
        """Test successful query execution."""
        # Mock query result
        mock_work_items = [Mock(id=2001), Mock(id=2002), Mock(id=2003), Mock(id=2004)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        # Mock batch fetch to return bugs (filter out security bug later)
        with patch("execution.collectors.risk_queries.blocked_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (sample_blocked_bugs, [])

            with patch("execution.collectors.risk_queries.blocked_bugs.filter_security_bugs") as mock_filter:
                # Filter out bug 2003 (security bug)
                filtered_bugs = [sample_blocked_bugs[0], sample_blocked_bugs[1], sample_blocked_bugs[3]]
                mock_filter.return_value = (filtered_bugs, 1)

                query = BlockedBugsQuery(mock_wit_client)
                result = query.execute("MyProject")

                assert result["project"] == "MyProject"
                assert result["count"] == 3
                assert result["priority_1_count"] == 1
                assert result["priority_2_count"] == 1
                assert result["priority_3_count"] == 1
                assert result["priority_4_count"] == 0
                assert result["excluded_security_bugs"] == 1
                assert len(result["blocked_bugs"]) == 3

    def test_execute_no_bugs_found(self, mock_wit_client):
        """Test query execution when no bugs found."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = BlockedBugsQuery(mock_wit_client)
        result = query.execute("MyProject")

        assert result["project"] == "MyProject"
        assert result["count"] == 0
        assert result["priority_1_count"] == 0
        assert result["priority_2_count"] == 0
        assert result["priority_3_count"] == 0
        assert result["priority_4_count"] == 0
        assert result["excluded_security_bugs"] == 0
        assert result["blocked_bugs"] == []

    def test_execute_with_area_filter(self, mock_wit_client, sample_blocked_bugs):
        """Test query execution with area path filter."""
        mock_work_items = [Mock(id=2001), Mock(id=2002)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.blocked_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (sample_blocked_bugs[:2], [])

            with patch("execution.collectors.risk_queries.blocked_bugs.filter_security_bugs") as mock_filter:
                mock_filter.return_value = (sample_blocked_bugs[:2], 0)

                query = BlockedBugsQuery(mock_wit_client)
                result = query.execute("MyProject", area_path_filter="EXCLUDE:TestArea")

                assert result["count"] == 2

    def test_execute_counts_all_priorities(self, mock_wit_client):
        """Test that all priority levels are counted correctly."""
        mock_work_items = [Mock(id=2001), Mock(id=2002), Mock(id=2003), Mock(id=2004)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        all_priority_bugs = [
            {"System.Id": 2001, "Microsoft.VSTS.Common.Priority": 1, "System.Tags": "", "System.CreatedBy": {}},
            {"System.Id": 2002, "Microsoft.VSTS.Common.Priority": 2, "System.Tags": "", "System.CreatedBy": {}},
            {"System.Id": 2003, "Microsoft.VSTS.Common.Priority": 3, "System.Tags": "", "System.CreatedBy": {}},
            {"System.Id": 2004, "Microsoft.VSTS.Common.Priority": 4, "System.Tags": "", "System.CreatedBy": {}},
        ]

        with patch("execution.collectors.risk_queries.blocked_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (all_priority_bugs, [])

            with patch("execution.collectors.risk_queries.blocked_bugs.filter_security_bugs") as mock_filter:
                mock_filter.return_value = (all_priority_bugs, 0)

                query = BlockedBugsQuery(mock_wit_client)
                result = query.execute("MyProject")

                assert result["priority_1_count"] == 1
                assert result["priority_2_count"] == 1
                assert result["priority_3_count"] == 1
                assert result["priority_4_count"] == 1

    def test_execute_filters_security_bugs(self, mock_wit_client, sample_blocked_bugs):
        """Test that security bugs are filtered out."""
        mock_work_items = [Mock(id=2001), Mock(id=2002), Mock(id=2003)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.blocked_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (sample_blocked_bugs[:3], [])

            with patch("execution.collectors.risk_queries.blocked_bugs.filter_security_bugs") as mock_filter:
                # Simulate filtering out 1 security bug
                filtered_bugs = sample_blocked_bugs[:2]
                mock_filter.return_value = (filtered_bugs, 1)

                query = BlockedBugsQuery(mock_wit_client)
                result = query.execute("MyProject")

                assert result["excluded_security_bugs"] == 1
                assert result["count"] == 2


class TestBlockedBugsQueryErrors:
    """Test error handling."""

    def test_execute_ado_service_error(self, mock_wit_client):
        """Test handling of AzureDevOpsServiceError."""
        mock_wit_client.query_by_wiql.side_effect = create_mock_ado_error()

        query = BlockedBugsQuery(mock_wit_client)

        with pytest.raises(AzureDevOpsServiceError):
            query.execute("MyProject")

    def test_execute_batch_fetch_error(self, mock_wit_client):
        """Test handling of BatchFetchError."""
        mock_work_items = [Mock(id=2001)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.blocked_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.side_effect = BatchFetchError("Batch fetch failed")

            query = BlockedBugsQuery(mock_wit_client)

            with pytest.raises(BatchFetchError):
                query.execute("MyProject")

    def test_execute_handles_failed_ids(self, mock_wit_client, sample_blocked_bugs):
        """Test that failed IDs are logged but don't stop execution."""
        mock_work_items = [Mock(id=2001), Mock(id=2002), Mock(id=2003)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.blocked_bugs.batch_fetch_work_items") as mock_batch:
            # Simulate some failed IDs
            mock_batch.return_value = (sample_blocked_bugs[:2], [2003])

            with patch("execution.collectors.risk_queries.blocked_bugs.filter_security_bugs") as mock_filter:
                mock_filter.return_value = (sample_blocked_bugs[:2], 0)

                query = BlockedBugsQuery(mock_wit_client)
                result = query.execute("MyProject")

                # Should still return results for successfully fetched bugs
                assert result["count"] == 2


class TestBlockedBugsQueryResultStructure:
    """Test result structure and fields."""

    def test_execute_returns_required_fields(self, mock_wit_client):
        """Test that execute returns all required fields."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = BlockedBugsQuery(mock_wit_client)
        result = query.execute("MyProject")

        required_fields = [
            "project",
            "blocked_bugs",
            "count",
            "priority_1_count",
            "priority_2_count",
            "priority_3_count",
            "priority_4_count",
            "excluded_security_bugs",
            "queried_at",
        ]

        for field in required_fields:
            assert field in result

    def test_execute_queried_at_is_iso_format(self, mock_wit_client):
        """Test that queried_at timestamp is in ISO format."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = BlockedBugsQuery(mock_wit_client)
        result = query.execute("MyProject")

        # Should be parseable as ISO datetime
        datetime.fromisoformat(result["queried_at"])

    def test_execute_blocked_bugs_is_list(self, mock_wit_client):
        """Test that blocked_bugs is always a list."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = BlockedBugsQuery(mock_wit_client)
        result = query.execute("MyProject")

        assert isinstance(result["blocked_bugs"], list)

    def test_execute_counts_are_integers(self, mock_wit_client):
        """Test that all count fields are integers."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = BlockedBugsQuery(mock_wit_client)
        result = query.execute("MyProject")

        assert isinstance(result["count"], int)
        assert isinstance(result["priority_1_count"], int)
        assert isinstance(result["priority_2_count"], int)
        assert isinstance(result["priority_3_count"], int)
        assert isinstance(result["priority_4_count"], int)
        assert isinstance(result["excluded_security_bugs"], int)
