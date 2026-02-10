#!/usr/bin/env python3
"""
Tests for MissingTestsQuery

Comprehensive test coverage for missing tests query class.
Tests WIQL query generation, test link checking, result parsing, and edge cases.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from azure.devops.exceptions import AzureDevOpsServiceError

from execution.collectors.risk_queries.missing_tests import MissingTestsQuery
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
def sample_closed_work_items():
    """Sample closed work item data for testing."""
    return [
        {
            "System.Id": 3001,
            "System.Title": "User Story without tests",
            "System.State": "Closed",
            "System.WorkItemType": "User Story",
            "System.CreatedDate": "2024-01-15T10:00:00Z",
            "Microsoft.VSTS.Common.ClosedDate": "2024-01-20T15:00:00Z",
            "Microsoft.VSTS.Common.Priority": 1,
            "System.CreatedBy": {"displayName": "John Doe"},
        },
        {
            "System.Id": 3002,
            "System.Title": "Feature without tests",
            "System.State": "Done",
            "System.WorkItemType": "Feature",
            "System.CreatedDate": "2024-01-16T11:30:00Z",
            "Microsoft.VSTS.Common.ClosedDate": "2024-01-22T16:00:00Z",
            "Microsoft.VSTS.Common.Priority": 2,
            "System.CreatedBy": {"displayName": "Jane Smith"},
        },
        {
            "System.Id": 3003,
            "System.Title": "User Story with tests",
            "System.State": "Closed",
            "System.WorkItemType": "User Story",
            "System.CreatedDate": "2024-01-17T14:00:00Z",
            "Microsoft.VSTS.Common.ClosedDate": "2024-01-23T17:00:00Z",
            "Microsoft.VSTS.Common.Priority": 1,
            "System.CreatedBy": {"displayName": "Bob Wilson"},
        },
    ]


class TestMissingTestsQueryInit:
    """Test MissingTestsQuery initialization."""

    def test_init_with_client(self, mock_wit_client):
        """Test initialization with WIT client."""
        query = MissingTestsQuery(mock_wit_client)
        assert query.wit_client is mock_wit_client

    def test_init_stores_client_reference(self, mock_wit_client):
        """Test that client reference is stored correctly."""
        query = MissingTestsQuery(mock_wit_client)
        assert hasattr(query, "wit_client")
        assert query.wit_client == mock_wit_client


class TestMissingTestsQueryWIQL:
    """Test WIQL query building."""

    def test_build_wiql_basic(self, mock_wit_client):
        """Test basic WIQL query generation."""
        query = MissingTestsQuery(mock_wit_client)
        lookback_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        wiql = query.build_wiql("MyProject", lookback_date)

        assert "MyProject" in wiql
        assert "System.WorkItemType] IN ('User Story', 'Feature')" in wiql
        assert "System.State] IN ('Closed', 'Done', 'Resolved')" in wiql
        assert "Microsoft.VSTS.Common.ClosedDate]" in wiql

    def test_build_wiql_with_lookback_date(self, mock_wit_client):
        """Test WIQL query with specific lookback date."""
        query = MissingTestsQuery(mock_wit_client)
        lookback_date = "2024-01-01"
        wiql = query.build_wiql("MyProject", lookback_date)

        assert lookback_date in wiql

    def test_build_wiql_with_area_filter(self, mock_wit_client):
        """Test WIQL query with area path filter."""
        query = MissingTestsQuery(mock_wit_client)
        lookback_date = "2024-01-01"
        wiql = query.build_wiql("MyProject", lookback_date, area_filter_clause="AND [System.AreaPath] NOT UNDER 'Test'")

        assert "MyProject" in wiql
        assert "AND [System.AreaPath] NOT UNDER 'Test'" in wiql

    def test_build_wiql_orders_by_closed_date_desc(self, mock_wit_client):
        """Test that WIQL orders by closed date descending."""
        query = MissingTestsQuery(mock_wit_client)
        lookback_date = "2024-01-01"
        wiql = query.build_wiql("MyProject", lookback_date)

        assert "ORDER BY [Microsoft.VSTS.Common.ClosedDate] DESC" in wiql

    def test_build_wiql_selects_required_fields(self, mock_wit_client):
        """Test that WIQL selects all required fields."""
        query = MissingTestsQuery(mock_wit_client)
        lookback_date = "2024-01-01"
        wiql = query.build_wiql("MyProject", lookback_date)

        required_fields = [
            "System.Id",
            "System.Title",
            "System.State",
            "System.WorkItemType",
            "System.CreatedDate",
            "Microsoft.VSTS.Common.ClosedDate",
            "Microsoft.VSTS.Common.Priority",
            "System.CreatedBy",
        ]
        for field in required_fields:
            assert field in wiql


class TestMissingTestsQueryAreaFilter:
    """Test area path filter building."""

    def test_build_area_filter_exclude(self, mock_wit_client):
        """Test building EXCLUDE area filter clause."""
        query = MissingTestsQuery(mock_wit_client)
        clause = query._build_area_filter_clause("EXCLUDE:TestPath")

        assert "NOT UNDER" in clause
        assert "TestPath" in clause

    def test_build_area_filter_include(self, mock_wit_client):
        """Test building INCLUDE area filter clause."""
        query = MissingTestsQuery(mock_wit_client)
        clause = query._build_area_filter_clause("INCLUDE:ProdPath")

        assert "UNDER" in clause
        assert "NOT UNDER" not in clause
        assert "ProdPath" in clause

    def test_build_area_filter_none(self, mock_wit_client):
        """Test building area filter with None returns empty string."""
        query = MissingTestsQuery(mock_wit_client)
        clause = query._build_area_filter_clause(None)

        assert clause == ""

    def test_build_area_filter_empty_string(self, mock_wit_client):
        """Test building area filter with empty string returns empty string."""
        query = MissingTestsQuery(mock_wit_client)
        clause = query._build_area_filter_clause("")

        assert clause == ""


class TestMissingTestsQueryTestLinks:
    """Test test link checking logic."""

    def test_has_test_links_with_test_relation(self, mock_wit_client):
        """Test that work item with TestedBy relation returns True."""
        query = MissingTestsQuery(mock_wit_client)

        # Mock work item with TestedBy relation
        mock_work_item = Mock()
        mock_relation = Mock()
        mock_relation.rel = "Microsoft.VSTS.Common.TestedBy-Forward"
        mock_work_item.relations = [mock_relation]
        mock_wit_client.get_work_item.return_value = mock_work_item

        result = query._has_test_links(3001)
        assert result is True

    def test_has_test_links_without_test_relation(self, mock_wit_client):
        """Test that work item without TestedBy relation returns False."""
        query = MissingTestsQuery(mock_wit_client)

        # Mock work item with other relations but no TestedBy
        mock_work_item = Mock()
        mock_relation = Mock()
        mock_relation.rel = "System.LinkTypes.Related"
        mock_work_item.relations = [mock_relation]
        mock_wit_client.get_work_item.return_value = mock_work_item

        result = query._has_test_links(3001)
        assert result is False

    def test_has_test_links_no_relations(self, mock_wit_client):
        """Test that work item with no relations returns False."""
        query = MissingTestsQuery(mock_wit_client)

        # Mock work item with no relations
        mock_work_item = Mock()
        mock_work_item.relations = None
        mock_wit_client.get_work_item.return_value = mock_work_item

        result = query._has_test_links(3001)
        assert result is False

    def test_has_test_links_empty_relations(self, mock_wit_client):
        """Test that work item with empty relations list returns False."""
        query = MissingTestsQuery(mock_wit_client)

        # Mock work item with empty relations list
        mock_work_item = Mock()
        mock_work_item.relations = []
        mock_wit_client.get_work_item.return_value = mock_work_item

        result = query._has_test_links(3001)
        assert result is False

    def test_has_test_links_handles_ado_error(self, mock_wit_client):
        """Test that ADO errors are handled gracefully (assumes has tests)."""
        query = MissingTestsQuery(mock_wit_client)

        mock_wit_client.get_work_item.side_effect = create_mock_ado_error()

        # Should return True (conservative assumption) when error occurs
        result = query._has_test_links(3001)
        assert result is True

    def test_has_test_links_handles_unexpected_error(self, mock_wit_client):
        """Test that unexpected errors are handled gracefully."""
        query = MissingTestsQuery(mock_wit_client)

        mock_wit_client.get_work_item.side_effect = Exception("Unexpected error")

        # Should return True (conservative assumption) when error occurs
        result = query._has_test_links(3001)
        assert result is True


class TestMissingTestsQueryExecute:
    """Test query execution."""

    def test_execute_success(self, mock_wit_client, sample_closed_work_items):
        """Test successful query execution."""
        # Mock query result
        mock_work_items = [Mock(id=3001), Mock(id=3002), Mock(id=3003)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        # Mock batch fetch to return work items
        with patch("execution.collectors.risk_queries.missing_tests.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (sample_closed_work_items, [])

            # Create query instance and patch _has_test_links
            query = MissingTestsQuery(mock_wit_client)

            # Mock test link checking: 3001 and 3002 have no tests, 3003 has tests
            with patch.object(query, "_has_test_links") as mock_has_tests:
                mock_has_tests.side_effect = [False, False, True]

                result = query.execute("MyProject", lookback_days=90)

                assert result["project"] == "MyProject"
                assert result["count"] == 2
                assert result["user_story_count"] == 1
                assert result["feature_count"] == 1
                assert result["total_closed_items"] == 3
                assert result["test_coverage_pct"] == 33.3

    def test_execute_no_work_items_found(self, mock_wit_client):
        """Test query execution when no work items found."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = MissingTestsQuery(mock_wit_client)
        result = query.execute("MyProject")

        assert result["project"] == "MyProject"
        assert result["count"] == 0
        assert result["user_story_count"] == 0
        assert result["feature_count"] == 0
        assert result["total_closed_items"] == 0
        assert result["test_coverage_pct"] == 100.0

    def test_execute_all_items_have_tests(self, mock_wit_client, sample_closed_work_items):
        """Test query execution when all work items have tests."""
        mock_work_items = [Mock(id=3001), Mock(id=3002), Mock(id=3003)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.missing_tests.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (sample_closed_work_items, [])

            query = MissingTestsQuery(mock_wit_client)

            # All items have tests
            with patch.object(query, "_has_test_links") as mock_has_tests:
                mock_has_tests.return_value = True

                result = query.execute("MyProject")

                assert result["count"] == 0
                assert result["test_coverage_pct"] == 100.0

    def test_execute_with_area_filter(self, mock_wit_client, sample_closed_work_items):
        """Test query execution with area path filter."""
        mock_work_items = [Mock(id=3001), Mock(id=3002)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.missing_tests.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (sample_closed_work_items[:2], [])

            query = MissingTestsQuery(mock_wit_client)

            with patch.object(query, "_has_test_links") as mock_has_tests:
                mock_has_tests.return_value = False

                result = query.execute("MyProject", area_path_filter="EXCLUDE:TestArea")

                assert result["count"] == 2

    def test_execute_custom_lookback_days(self, mock_wit_client, sample_closed_work_items):
        """Test query execution with custom lookback period."""
        mock_work_items = [Mock(id=3001)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.missing_tests.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = ([sample_closed_work_items[0]], [])

            query = MissingTestsQuery(mock_wit_client)

            with patch.object(query, "_has_test_links") as mock_has_tests:
                mock_has_tests.return_value = False

                result = query.execute("MyProject", lookback_days=30)

                assert result["total_closed_items"] == 1

    def test_execute_counts_work_item_types(self, mock_wit_client):
        """Test that work item types are counted correctly."""
        mock_work_items = [Mock(id=3001), Mock(id=3002), Mock(id=3003), Mock(id=3004)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        mixed_work_items = [
            {"System.Id": 3001, "System.WorkItemType": "User Story"},
            {"System.Id": 3002, "System.WorkItemType": "User Story"},
            {"System.Id": 3003, "System.WorkItemType": "Feature"},
            {"System.Id": 3004, "System.WorkItemType": "Feature"},
        ]

        with patch("execution.collectors.risk_queries.missing_tests.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (mixed_work_items, [])

            query = MissingTestsQuery(mock_wit_client)

            with patch.object(query, "_has_test_links") as mock_has_tests:
                mock_has_tests.return_value = False

                result = query.execute("MyProject")

                assert result["user_story_count"] == 2
                assert result["feature_count"] == 2

    def test_execute_calculates_coverage_percentage(self, mock_wit_client, sample_closed_work_items):
        """Test that test coverage percentage is calculated correctly."""
        mock_work_items = [Mock(id=3001), Mock(id=3002), Mock(id=3003)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.missing_tests.batch_fetch_work_items") as mock_batch:
            mock_batch.return_value = (sample_closed_work_items, [])

            query = MissingTestsQuery(mock_wit_client)

            # 1 out of 3 has tests = 33.3% coverage
            with patch.object(query, "_has_test_links") as mock_has_tests:
                mock_has_tests.side_effect = [False, False, True]

                result = query.execute("MyProject")

                assert result["test_coverage_pct"] == 33.3


class TestMissingTestsQueryErrors:
    """Test error handling."""

    def test_execute_ado_service_error(self, mock_wit_client):
        """Test handling of AzureDevOpsServiceError."""
        mock_wit_client.query_by_wiql.side_effect = create_mock_ado_error()

        query = MissingTestsQuery(mock_wit_client)

        with pytest.raises(AzureDevOpsServiceError):
            query.execute("MyProject")

    def test_execute_batch_fetch_error(self, mock_wit_client):
        """Test handling of BatchFetchError."""
        mock_work_items = [Mock(id=3001)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.missing_tests.batch_fetch_work_items") as mock_batch:
            mock_batch.side_effect = BatchFetchError("Batch fetch failed")

            query = MissingTestsQuery(mock_wit_client)

            with pytest.raises(BatchFetchError):
                query.execute("MyProject")

    def test_execute_handles_failed_ids(self, mock_wit_client, sample_closed_work_items):
        """Test that failed IDs are logged but don't stop execution."""
        mock_work_items = [Mock(id=3001), Mock(id=3002), Mock(id=3003)]
        mock_wit_client.query_by_wiql.return_value.work_items = mock_work_items

        with patch("execution.collectors.risk_queries.missing_tests.batch_fetch_work_items") as mock_batch:
            # Simulate some failed IDs
            mock_batch.return_value = (sample_closed_work_items[:2], [3003])

            query = MissingTestsQuery(mock_wit_client)

            with patch.object(query, "_has_test_links") as mock_has_tests:
                mock_has_tests.return_value = False

                result = query.execute("MyProject")

                # Should still return results for successfully fetched items
                assert result["count"] == 2


class TestMissingTestsQueryResultStructure:
    """Test result structure and fields."""

    def test_execute_returns_required_fields(self, mock_wit_client):
        """Test that execute returns all required fields."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = MissingTestsQuery(mock_wit_client)
        result = query.execute("MyProject")

        required_fields = [
            "project",
            "work_items_without_tests",
            "count",
            "user_story_count",
            "feature_count",
            "total_closed_items",
            "test_coverage_pct",
            "queried_at",
        ]

        for field in required_fields:
            assert field in result

    def test_execute_queried_at_is_iso_format(self, mock_wit_client):
        """Test that queried_at timestamp is in ISO format."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = MissingTestsQuery(mock_wit_client)
        result = query.execute("MyProject")

        # Should be parseable as ISO datetime
        datetime.fromisoformat(result["queried_at"])

    def test_execute_work_items_without_tests_is_list(self, mock_wit_client):
        """Test that work_items_without_tests is always a list."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = MissingTestsQuery(mock_wit_client)
        result = query.execute("MyProject")

        assert isinstance(result["work_items_without_tests"], list)

    def test_execute_counts_are_integers(self, mock_wit_client):
        """Test that all count fields are integers."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = MissingTestsQuery(mock_wit_client)
        result = query.execute("MyProject")

        assert isinstance(result["count"], int)
        assert isinstance(result["user_story_count"], int)
        assert isinstance(result["feature_count"], int)
        assert isinstance(result["total_closed_items"], int)

    def test_execute_coverage_pct_is_float(self, mock_wit_client):
        """Test that test_coverage_pct is a float."""
        mock_wit_client.query_by_wiql.return_value.work_items = []

        query = MissingTestsQuery(mock_wit_client)
        result = query.execute("MyProject")

        assert isinstance(result["test_coverage_pct"], float)
