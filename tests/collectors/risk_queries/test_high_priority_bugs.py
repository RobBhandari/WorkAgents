#!/usr/bin/env python3
"""
Tests for HighPriorityBugsQuery

Comprehensive test coverage for high-priority bug query class.
Tests WIQL query generation, result parsing, filtering, and edge cases.
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from azure.devops.exceptions import AzureDevOpsServiceError

from execution.collectors.risk_queries.high_priority_bugs import HighPriorityBugsQuery
from execution.utils.ado_batch_utils import BatchFetchError


@pytest.fixture
def mock_wit_client():
    """Create a mock Work Item Tracking client."""
    return MagicMock()


@pytest.fixture
def sample_high_priority_bugs():
    """Sample high-priority bug data for testing."""
    return [
        {
            "System.Id": 1001,
            "System.Title": "Critical production crash",
            "System.State": "Active",
            "System.CreatedDate": "2024-01-15T10:00:00Z",
            "Microsoft.VSTS.Common.Priority": 1,
            "Microsoft.VSTS.Common.Severity": "1 - Critical",
            "System.Tags": "",
            "System.CreatedBy": {"displayName": "John Doe"},
        },
        {
            "System.Id": 1002,
            "System.Title": "Data corruption in payment flow",
            "System.State": "Active",
            "System.CreatedDate": "2024-01-16T11:30:00Z",
            "Microsoft.VSTS.Common.Priority": 2,
            "Microsoft.VSTS.Common.Severity": "2 - High",
            "System.Tags": "",
            "System.CreatedBy": {"displayName": "Jane Smith"},
        },
        {
            "System.Id": 1003,
            "System.Title": "Security vulnerability in auth",
            "System.State": "New",
            "System.CreatedDate": "2024-01-17T14:00:00Z",
            "Microsoft.VSTS.Common.Priority": 1,
            "Microsoft.VSTS.Common.Severity": "1 - Critical",
            "System.Tags": "armorcode;security",
            "System.CreatedBy": {"displayName": "ArmorCode Bot"},
        },
    ]


class TestHighPriorityBugsQueryInit:
    """Test HighPriorityBugsQuery initialization."""

    def test_init_with_client(self, mock_wit_client):
        """Test initialization with WIT client."""
        query = HighPriorityBugsQuery(mock_wit_client)
        assert query.wit_client is mock_wit_client

    def test_init_stores_client_reference(self, mock_wit_client):
        """Test that client reference is stored correctly."""
        query = HighPriorityBugsQuery(mock_wit_client)
        assert hasattr(query, "wit_client")
        assert query.wit_client == mock_wit_client


class TestHighPriorityBugsQueryWIQL:
    """Test WIQL query building."""

    def test_build_wiql_basic(self, mock_wit_client):
        """Test basic WIQL query generation."""
        query = HighPriorityBugsQuery(mock_wit_client)
        wiql = query.build_wiql("MyProject")

        assert "MyProject" in wiql
        assert "System.WorkItemType] = 'Bug'" in wiql
        assert "Microsoft.VSTS.Common.Priority] IN (1, 2)" in wiql
        assert "System.State] NOT IN ('Closed', 'Removed')" in wiql

    def test_build_wiql_with_area_filter(self, mock_wit_client):
        """Test WIQL query with area path filter."""
        query = HighPriorityBugsQuery(mock_wit_client)
        wiql = query.build_wiql("MyProject", area_filter_clause="AND [System.AreaPath] NOT UNDER 'Test'")

        assert "MyProject" in wiql
        assert "AND [System.AreaPath] NOT UNDER 'Test'" in wiql

    def test_build_wiql_orders_by_priority_and_date(self, mock_wit_client):
        """Test that WIQL orders by priority first, then created date."""
        query = HighPriorityBugsQuery(mock_wit_client)
        wiql = query.build_wiql("MyProject")

        assert "ORDER BY [Microsoft.VSTS.Common.Priority] ASC, [System.CreatedDate] ASC" in wiql

    def test_build_wiql_selects_required_fields(self, mock_wit_client):
        """Test that WIQL selects all required fields."""
        query = HighPriorityBugsQuery(mock_wit_client)
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
        ]
        for field in required_fields:
            assert field in wiql


class TestHighPriorityBugsQueryAreaFilter:
    """Test area path filter building."""

    def test_build_area_filter_exclude(self, mock_wit_client):
        """Test building EXCLUDE area filter clause."""
        query = HighPriorityBugsQuery(mock_wit_client)
        clause = query._build_area_filter_clause("EXCLUDE:TestPath")

        assert "NOT UNDER" in clause
        assert "TestPath" in clause

    def test_build_area_filter_include(self, mock_wit_client):
        """Test building INCLUDE area filter clause."""
        query = HighPriorityBugsQuery(mock_wit_client)
        clause = query._build_area_filter_clause("INCLUDE:ProdPath")

        assert "UNDER" in clause
        assert "NOT UNDER" not in clause
        assert "ProdPath" in clause

    def test_build_area_filter_none(self, mock_wit_client):
        """Test building area filter with None returns empty string."""
        query = HighPriorityBugsQuery(mock_wit_client)
        clause = query._build_area_filter_clause(None)

        assert clause == ""

    def test_build_area_filter_empty_string(self, mock_wit_client):
        """Test building area filter with empty string returns empty string."""
        query = HighPriorityBugsQuery(mock_wit_client)
        clause = query._build_area_filter_clause("")

        assert clause == ""


class TestHighPriorityBugsQueryExecute:
    """Test query execution."""

    def test_execute_success(self, mock_wit_client, sample_high_priority_bugs):
        """Test successful query execution."""
        # Mock query result
        mock_work_items = [Mock(id=1001), Mock(id=1002), Mock(id=1003)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        # Mock batch fetch to return bugs (filter out security bug later)
        with patch("execution.collectors.risk_queries.high_priority_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (sample_high_priority_bugs, [])

            with patch("execution.collectors.risk_queries.high_priority_bugs.filter_security_bugs") as mock_filter:
                # Filter out bug 1003 (security bug)
                filtered_bugs = sample_high_priority_bugs[:2]
                mock_filter.return_value = (filtered_bugs, 1)

                query = HighPriorityBugsQuery(mock_wit_client)
                result = query.execute("MyProject")

                assert result["project"] == "MyProject"
                assert result["count"] == 2
                assert result["priority_1_count"] == 1
                assert result["priority_2_count"] == 1
                assert result["excluded_security_bugs"] == 1
                assert len(result["high_priority_bugs"]) == 2

    def test_execute_no_bugs_found(self, mock_wit_client):
        """Test query execution when no bugs found."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = HighPriorityBugsQuery(mock_wit_client)
        result = query.execute("MyProject")

        assert result["project"] == "MyProject"
        assert result["count"] == 0
        assert result["priority_1_count"] == 0
        assert result["priority_2_count"] == 0
        assert result["excluded_security_bugs"] == 0
        assert result["high_priority_bugs"] == []

    def test_execute_with_area_filter(self, mock_wit_client, sample_high_priority_bugs):
        """Test query execution with area path filter."""
        mock_work_items = [Mock(id=1001), Mock(id=1002)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.high_priority_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (sample_high_priority_bugs[:2], [])

            with patch("execution.collectors.risk_queries.high_priority_bugs.filter_security_bugs") as mock_filter:
                mock_filter.return_value = (sample_high_priority_bugs[:2], 0)

                query = HighPriorityBugsQuery(mock_wit_client)
                result = query.execute("MyProject", area_path_filter="EXCLUDE:TestArea")

                assert result["count"] == 2

    def test_execute_counts_priority_1_correctly(self, mock_wit_client):
        """Test that Priority 1 bugs are counted correctly."""
        mock_work_items = [Mock(id=1001)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        p1_bugs = [
            {
                "System.Id": 1001,
                "Microsoft.VSTS.Common.Priority": 1,
                "System.CreatedBy": {"displayName": "John Doe"},
                "System.Tags": "",
            }
        ]

        with patch("execution.collectors.risk_queries.high_priority_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (p1_bugs, [])

            with patch("execution.collectors.risk_queries.high_priority_bugs.filter_security_bugs") as mock_filter:
                mock_filter.return_value = (p1_bugs, 0)

                query = HighPriorityBugsQuery(mock_wit_client)
                result = query.execute("MyProject")

                assert result["priority_1_count"] == 1
                assert result["priority_2_count"] == 0

    def test_execute_counts_priority_2_correctly(self, mock_wit_client):
        """Test that Priority 2 bugs are counted correctly."""
        mock_work_items = [Mock(id=1002)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        p2_bugs = [
            {
                "System.Id": 1002,
                "Microsoft.VSTS.Common.Priority": 2,
                "System.CreatedBy": {"displayName": "Jane Smith"},
                "System.Tags": "",
            }
        ]

        with patch("execution.collectors.risk_queries.high_priority_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (p2_bugs, [])

            with patch("execution.collectors.risk_queries.high_priority_bugs.filter_security_bugs") as mock_filter:
                mock_filter.return_value = (p2_bugs, 0)

                query = HighPriorityBugsQuery(mock_wit_client)
                result = query.execute("MyProject")

                assert result["priority_1_count"] == 0
                assert result["priority_2_count"] == 1

    def test_execute_filters_security_bugs(self, mock_wit_client, sample_high_priority_bugs):
        """Test that security bugs are filtered out."""
        mock_work_items = [Mock(id=1001), Mock(id=1002), Mock(id=1003)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.high_priority_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (sample_high_priority_bugs, [])

            with patch("execution.collectors.risk_queries.high_priority_bugs.filter_security_bugs") as mock_filter:
                # Simulate filtering out 1 security bug
                filtered_bugs = sample_high_priority_bugs[:2]
                mock_filter.return_value = (filtered_bugs, 1)

                query = HighPriorityBugsQuery(mock_wit_client)
                result = query.execute("MyProject")

                assert result["excluded_security_bugs"] == 1
                assert result["count"] == 2


class TestHighPriorityBugsQueryErrors:
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

        query = HighPriorityBugsQuery(mock_wit_client)

        with pytest.raises(AzureDevOpsServiceError):
            query.execute("MyProject")

    def test_execute_batch_fetch_error(self, mock_wit_client):
        """Test handling of BatchFetchError."""
        mock_work_items = [Mock(id=1001)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.high_priority_bugs.batch_fetch_work_items") as mock_batch:
            mock_batch.side_effect = BatchFetchError("Batch fetch failed")

            query = HighPriorityBugsQuery(mock_wit_client)

            with pytest.raises(BatchFetchError):
                query.execute("MyProject")

    def test_execute_handles_failed_ids(self, mock_wit_client, sample_high_priority_bugs):
        """Test that failed IDs are logged but don't stop execution."""
        mock_work_items = [Mock(id=1001), Mock(id=1002), Mock(id=1003)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.high_priority_bugs.batch_fetch_work_items") as mock_batch:
            # Simulate some failed IDs
            mock_batch.return_value = (sample_high_priority_bugs[:2], [1003])

            with patch("execution.collectors.risk_queries.high_priority_bugs.filter_security_bugs") as mock_filter:
                mock_filter.return_value = (sample_high_priority_bugs[:2], 0)

                query = HighPriorityBugsQuery(mock_wit_client)
                result = query.execute("MyProject")

                # Should still return results for successfully fetched bugs
                assert result["count"] == 2


class TestHighPriorityBugsQueryResultStructure:
    """Test result structure and fields."""

    def test_execute_returns_required_fields(self, mock_wit_client):
        """Test that execute returns all required fields."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = HighPriorityBugsQuery(mock_wit_client)
        result = query.execute("MyProject")

        required_fields = [
            "project",
            "high_priority_bugs",
            "count",
            "priority_1_count",
            "priority_2_count",
            "excluded_security_bugs",
            "queried_at",
        ]

        for field in required_fields:
            assert field in result

    def test_execute_queried_at_is_iso_format(self, mock_wit_client):
        """Test that queried_at timestamp is in ISO format."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = HighPriorityBugsQuery(mock_wit_client)
        result = query.execute("MyProject")

        # Should be parseable as ISO datetime
        datetime.fromisoformat(result["queried_at"])

    def test_execute_high_priority_bugs_is_list(self, mock_wit_client):
        """Test that high_priority_bugs is always a list."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = HighPriorityBugsQuery(mock_wit_client)
        result = query.execute("MyProject")

        assert isinstance(result["high_priority_bugs"], list)

    def test_execute_counts_are_integers(self, mock_wit_client):
        """Test that all count fields are integers."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = HighPriorityBugsQuery(mock_wit_client)
        result = query.execute("MyProject")

        assert isinstance(result["count"], int)
        assert isinstance(result["priority_1_count"], int)
        assert isinstance(result["priority_2_count"], int)
        assert isinstance(result["excluded_security_bugs"], int)
