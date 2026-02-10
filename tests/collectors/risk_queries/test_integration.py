#!/usr/bin/env python3
"""
Integration Tests for Risk Queries

Tests the orchestration of all risk query classes working together.
Validates that the Command pattern allows flexible composition of queries.
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock

import pytest

from execution.collectors.risk_queries import (
    BlockedBugsQuery,
    HighPriorityBugsQuery,
    MissingTestsQuery,
    StaleBugsQuery,
)


@pytest.fixture
def mock_wit_client():
    """Mock Work Item Tracking client."""
    client = Mock()
    client.query_by_wiql = Mock()
    client.get_work_items = Mock()
    return client


@pytest.fixture
def sample_query_result():
    """Sample WIQL query result with work item references."""
    mock_result = Mock()
    mock_result.work_items = [
        Mock(id=101),
        Mock(id=102),
        Mock(id=103),
    ]
    return mock_result


@pytest.fixture
def sample_work_items():
    """Sample work item details from ADO."""
    return [
        {
            "System.Id": 101,
            "System.Title": "Critical bug",
            "System.State": "Active",
            "System.CreatedDate": "2026-01-01T00:00:00Z",
            "Microsoft.VSTS.Common.Priority": 1,
            "Microsoft.VSTS.Common.Severity": "1 - Critical",
            "System.Tags": "",
            "System.CreatedBy": "user1@example.com",
        },
        {
            "System.Id": 102,
            "System.Title": "High priority issue",
            "System.State": "Active",
            "System.CreatedDate": "2026-01-15T00:00:00Z",
            "Microsoft.VSTS.Common.Priority": 2,
            "Microsoft.VSTS.Common.Severity": "2 - High",
            "System.Tags": "",
            "System.CreatedBy": "user2@example.com",
        },
        {
            "System.Id": 103,
            "System.Title": "Blocked task",
            "System.State": "Active",
            "System.CreatedDate": "2026-02-01T00:00:00Z",
            "Microsoft.VSTS.Common.Priority": 2,
            "System.Tags": "",
            "System.CreatedBy": "user3@example.com",
        },
    ]


class TestRiskQueryIntegration:
    """Integration tests for orchestrating multiple risk queries."""

    def test_all_queries_can_be_instantiated(self, mock_wit_client):
        """Test that all query classes can be instantiated with the same client."""
        # All queries should work with the same WIT client
        high_priority = HighPriorityBugsQuery(mock_wit_client)
        stale = StaleBugsQuery(mock_wit_client, stale_threshold_days=30)
        blocked = BlockedBugsQuery(mock_wit_client)
        missing_tests = MissingTestsQuery(mock_wit_client)

        # All should have execute() method
        assert hasattr(high_priority, "execute")
        assert hasattr(stale, "execute")
        assert hasattr(blocked, "execute")
        assert hasattr(missing_tests, "execute")

        # All should have build_wiql() method
        assert hasattr(high_priority, "build_wiql")
        assert hasattr(stale, "build_wiql")
        assert hasattr(blocked, "build_wiql")
        assert hasattr(missing_tests, "build_wiql")

    def test_query_list_pattern(self, mock_wit_client):
        """Test Command pattern: list of queries can be instantiated and stored."""
        # Create list of queries (Command pattern)
        queries = [
            HighPriorityBugsQuery(mock_wit_client),
            StaleBugsQuery(mock_wit_client, stale_threshold_days=30),
            BlockedBugsQuery(mock_wit_client),
            MissingTestsQuery(mock_wit_client),
        ]

        # All queries should be instantiated
        assert len(queries) == 4
        assert all(hasattr(q, "execute") for q in queries)
        assert all(hasattr(q, "build_wiql") for q in queries)

        # Verify correct classes
        assert isinstance(queries[0], HighPriorityBugsQuery)
        assert isinstance(queries[1], StaleBugsQuery)
        assert isinstance(queries[2], BlockedBugsQuery)
        assert isinstance(queries[3], MissingTestsQuery)

    def test_selective_query_execution(self, mock_wit_client):
        """Test that queries can be selectively instantiated based on needs."""
        # Scenario: Only want high-priority and blocked bugs
        queries = [
            HighPriorityBugsQuery(mock_wit_client),
            BlockedBugsQuery(mock_wit_client),
        ]

        # Should have exactly 2 queries
        assert len(queries) == 2
        assert isinstance(queries[0], HighPriorityBugsQuery)
        assert isinstance(queries[1], BlockedBugsQuery)

    def test_queries_with_different_configurations(self, mock_wit_client):
        """Test that each query can be configured differently."""
        # Different configurations for different query types
        high_priority = HighPriorityBugsQuery(mock_wit_client)
        stale_30 = StaleBugsQuery(mock_wit_client, stale_threshold_days=30)
        stale_60 = StaleBugsQuery(mock_wit_client, stale_threshold_days=60)

        # Verify different configurations
        assert isinstance(high_priority, HighPriorityBugsQuery)
        assert isinstance(stale_30, StaleBugsQuery)
        assert stale_30.stale_threshold_days == 30
        assert isinstance(stale_60, StaleBugsQuery)
        assert stale_60.stale_threshold_days == 60

    def test_multiple_query_types(self, mock_wit_client):
        """Test creating multiple query types together."""
        # Create multiple query types
        queries = [
            HighPriorityBugsQuery(mock_wit_client),
            StaleBugsQuery(mock_wit_client, stale_threshold_days=30),
            BlockedBugsQuery(mock_wit_client),
        ]

        # Verify all created successfully
        assert len(queries) == 3
        assert all(hasattr(q, "execute") for q in queries)
        assert all(hasattr(q, "build_wiql") for q in queries)

    def test_query_wiql_generation(self, mock_wit_client):
        """Test that all queries can generate WIQL."""
        from datetime import datetime

        high_priority = HighPriorityBugsQuery(mock_wit_client)
        stale = StaleBugsQuery(mock_wit_client, stale_threshold_days=30)
        blocked = BlockedBugsQuery(mock_wit_client)

        # Test WIQL generation for each query type
        wiql1 = high_priority.build_wiql("TestProject")
        assert isinstance(wiql1, str)
        assert "SELECT" in wiql1
        assert "TestProject" in wiql1

        # StaleBugsQuery needs a date parameter
        wiql2 = stale.build_wiql("TestProject", stale_date="2026-01-01")
        assert isinstance(wiql2, str)
        assert "SELECT" in wiql2
        assert "TestProject" in wiql2

        wiql3 = blocked.build_wiql("TestProject")
        assert isinstance(wiql3, str)
        assert "SELECT" in wiql3
        assert "TestProject" in wiql3

    def test_queries_share_common_interface(self, mock_wit_client):
        """Test that all queries implement the same interface."""
        queries = [
            HighPriorityBugsQuery(mock_wit_client),
            StaleBugsQuery(mock_wit_client, stale_threshold_days=30),
            BlockedBugsQuery(mock_wit_client),
            MissingTestsQuery(mock_wit_client),
        ]

        # All queries should have the same methods
        for query in queries:
            assert hasattr(query, "execute"), f"{query.__class__.__name__} should have execute method"
            assert hasattr(query, "build_wiql"), f"{query.__class__.__name__} should have build_wiql method"
            assert hasattr(query, "wit_client"), f"{query.__class__.__name__} should have wit_client attribute"
            assert callable(query.execute), f"{query.__class__.__name__}.execute should be callable"
            assert callable(query.build_wiql), f"{query.__class__.__name__}.build_wiql should be callable"

    def test_query_wiql_for_multiple_projects(self, mock_wit_client):
        """Test that same query instance can generate WIQL for multiple projects."""
        # Create query once
        query = HighPriorityBugsQuery(mock_wit_client)

        # Generate WIQL for multiple projects
        projects = ["Project1", "Project2", "Project3"]
        wiql_list = [query.build_wiql(proj) for proj in projects]

        # Should have WIQL for all projects
        assert len(wiql_list) == 3
        for i, wiql in enumerate(wiql_list):
            assert projects[i] in wiql
            assert "SELECT" in wiql


class TestRiskCollectorPattern:
    """Test patterns for building a risk collector using the query classes."""

    def test_collector_with_query_list(self, mock_wit_client):
        """Test collector pattern that manages a list of queries."""
        # Simple collector class
        class RiskCollector:
            def __init__(self, wit_client):
                self.queries = [
                    HighPriorityBugsQuery(wit_client),
                    StaleBugsQuery(wit_client, stale_threshold_days=30),
                    BlockedBugsQuery(wit_client),
                    MissingTestsQuery(wit_client),
                ]

        # Create collector
        collector = RiskCollector(mock_wit_client)

        # Verify collector has all queries
        assert len(collector.queries) == 4
        assert all(hasattr(q, "execute") for q in collector.queries)
        assert isinstance(collector.queries[0], HighPriorityBugsQuery)
        assert isinstance(collector.queries[1], StaleBugsQuery)
        assert isinstance(collector.queries[2], BlockedBugsQuery)
        assert isinstance(collector.queries[3], MissingTestsQuery)

    def test_collector_with_configurable_queries(self, mock_wit_client):
        """Test collector that accepts query configuration."""
        # Collector with configurable query list
        class ConfigurableRiskCollector:
            def __init__(self, wit_client, query_classes: list):
                self.queries = [query_cls(wit_client) for query_cls in query_classes]

        # Create collector with subset of queries
        collector = ConfigurableRiskCollector(
            mock_wit_client,
            query_classes=[HighPriorityBugsQuery, BlockedBugsQuery],
        )

        # Should have exactly 2 queries
        assert len(collector.queries) == 2
        assert isinstance(collector.queries[0], HighPriorityBugsQuery)
        assert isinstance(collector.queries[1], BlockedBugsQuery)
