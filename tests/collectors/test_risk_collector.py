#!/usr/bin/env python3
"""
Tests for ADORiskCollector

Tests the orchestration class that coordinates all risk query classes.
"""

from unittest.mock import Mock, patch

import pytest

from execution.collectors.risk_collector import ADORiskCollector


@pytest.fixture
def mock_wit_client():
    """Mock Work Item Tracking client."""
    client = Mock()
    return client


@pytest.fixture
def sample_query_result():
    """Sample query result from risk queries."""
    return {
        "project": "TestProject",
        "high_priority_bugs": [],
        "count": 0,
        "priority_1_count": 0,
        "priority_2_count": 0,
        "excluded_security_bugs": 0,
        "queried_at": "2026-02-10T10:00:00",
    }


class TestADORiskCollectorInitialization:
    """Test ADORiskCollector initialization and configuration."""

    def test_default_initialization(self, mock_wit_client):
        """Test collector initializes with default settings."""
        collector = ADORiskCollector(mock_wit_client)

        # Should have all 4 queries by default
        assert len(collector.queries) == 4

        # Check query names
        query_names = collector.get_query_names()
        assert "HighPriorityBugsQuery" in query_names
        assert "StaleBugsQuery" in query_names
        assert "BlockedBugsQuery" in query_names
        assert "MissingTestsQuery" in query_names

    def test_custom_stale_threshold(self, mock_wit_client):
        """Test collector accepts custom stale threshold."""
        collector = ADORiskCollector(mock_wit_client, stale_threshold_days=60)

        assert collector.stale_threshold_days == 60

    def test_selective_query_enablement(self, mock_wit_client):
        """Test that queries can be selectively enabled/disabled."""
        # Only enable high-priority and blocked queries
        collector = ADORiskCollector(
            mock_wit_client,
            enable_high_priority=True,
            enable_stale=False,
            enable_blocked=True,
            enable_missing_tests=False,
        )

        # Should have exactly 2 queries
        assert len(collector.queries) == 2

        query_names = collector.get_query_names()
        assert "HighPriorityBugsQuery" in query_names
        assert "BlockedBugsQuery" in query_names
        assert "StaleBugsQuery" not in query_names
        assert "MissingTestsQuery" not in query_names

    def test_all_queries_disabled(self, mock_wit_client):
        """Test collector with all queries disabled."""
        collector = ADORiskCollector(
            mock_wit_client,
            enable_high_priority=False,
            enable_stale=False,
            enable_blocked=False,
            enable_missing_tests=False,
        )

        # Should have no queries
        assert len(collector.queries) == 0


class TestADORiskCollectorExecution:
    """Test ADORiskCollector query execution."""

    @patch("execution.collectors.risk_collector.HighPriorityBugsQuery")
    @patch("execution.collectors.risk_collector.StaleBugsQuery")
    @patch("execution.collectors.risk_collector.BlockedBugsQuery")
    @patch("execution.collectors.risk_collector.MissingTestsQuery")
    def test_collect_metrics_success(
        self, mock_missing_tests, mock_blocked, mock_stale, mock_high_priority, mock_wit_client
    ):
        """Test successful metrics collection."""
        # Setup mock query instances with proper class names
        query_configs = [
            (mock_high_priority, "HighPriorityBugsQuery"),
            (mock_stale, "StaleBugsQuery"),
            (mock_blocked, "BlockedBugsQuery"),
            (mock_missing_tests, "MissingTestsQuery"),
        ]

        for mock_query_class, class_name in query_configs:
            mock_instance = Mock()
            mock_instance.__class__.__name__ = class_name
            mock_instance.execute.return_value = {
                "project": "TestProject",
                "count": 5,
                "queried_at": "2026-02-10T10:00:00",
            }
            mock_query_class.return_value = mock_instance

        collector = ADORiskCollector(mock_wit_client)
        result = collector.collect_metrics(project_name="TestProject")

        # Verify structure
        assert result["project"] == "TestProject"
        assert "highprioritybugs" in result
        assert "stalebugs" in result
        assert "blockedbugs" in result
        assert "missingtests" in result
        assert "summary" in result

        # Verify summary
        summary = result["summary"]
        assert summary["queries_executed"] == 4
        assert summary["queries_failed"] == 0
        assert summary["total_risk_items"] == 20  # 5 items per query * 4 queries

    @patch("execution.collectors.risk_collector.HighPriorityBugsQuery")
    @patch("execution.collectors.risk_collector.StaleBugsQuery")
    def test_collect_metrics_with_area_filter(self, mock_stale, mock_high_priority, mock_wit_client):
        """Test metrics collection with area path filter."""
        # Setup mocks with proper class names
        mock_high_priority_instance = Mock()
        mock_high_priority_instance.__class__.__name__ = "HighPriorityBugsQuery"
        mock_high_priority_instance.execute.return_value = {
            "project": "TestProject",
            "count": 3,
            "queried_at": "2026-02-10T10:00:00",
        }
        mock_high_priority.return_value = mock_high_priority_instance

        mock_stale_instance = Mock()
        mock_stale_instance.__class__.__name__ = "StaleBugsQuery"
        mock_stale_instance.execute.return_value = {
            "project": "TestProject",
            "count": 3,
            "queried_at": "2026-02-10T10:00:00",
        }
        mock_stale.return_value = mock_stale_instance

        collector = ADORiskCollector(
            mock_wit_client,
            enable_high_priority=True,
            enable_stale=True,
            enable_blocked=False,
            enable_missing_tests=False,
        )

        result = collector.collect_metrics(project_name="TestProject", area_path_filter="EXCLUDE:TestProject\\Archive")

        # Verify area filter was passed to queries
        mock_high_priority_instance.execute.assert_called_once_with(
            project_name="TestProject", area_path_filter="EXCLUDE:TestProject\\Archive"
        )

        assert result["project"] == "TestProject"

    @patch("execution.collectors.risk_collector.HighPriorityBugsQuery")
    @patch("execution.collectors.risk_collector.StaleBugsQuery")
    def test_collect_metrics_with_query_failure(self, mock_stale, mock_high_priority, mock_wit_client):
        """Test metrics collection when one query fails."""
        # First query succeeds
        mock_high_priority_instance = Mock()
        mock_high_priority_instance.__class__.__name__ = "HighPriorityBugsQuery"
        mock_high_priority_instance.execute.return_value = {
            "project": "TestProject",
            "count": 5,
            "queried_at": "2026-02-10T10:00:00",
        }
        mock_high_priority.return_value = mock_high_priority_instance

        # Second query fails
        mock_stale_instance = Mock()
        mock_stale_instance.__class__.__name__ = "StaleBugsQuery"
        mock_stale_instance.execute.side_effect = Exception("API Error")
        mock_stale.return_value = mock_stale_instance

        collector = ADORiskCollector(
            mock_wit_client,
            enable_high_priority=True,
            enable_stale=True,
            enable_blocked=False,
            enable_missing_tests=False,
        )

        result = collector.collect_metrics(project_name="TestProject")

        # Verify partial success
        assert result["project"] == "TestProject"
        assert "highprioritybugs" in result
        assert result["highprioritybugs"]["count"] == 5

        # Verify error recorded
        assert "stalebugs" in result
        assert "error" in result["stalebugs"]
        assert result["stalebugs"]["error"] == "API Error"

        # Verify summary reflects failure
        summary = result["summary"]
        assert summary["queries_executed"] == 2
        assert summary["queries_failed"] == 1
        assert summary["total_risk_items"] == 5  # Only successful query counted

        # Verify errors list
        assert "errors" in result
        assert len(result["errors"]) == 1
        assert result["errors"][0]["query"] == "stalebugs"


class TestADORiskCollectorMultiProject:
    """Test ADORiskCollector multi-project collection."""

    @patch("execution.collectors.risk_collector.HighPriorityBugsQuery")
    @patch("execution.collectors.risk_collector.StaleBugsQuery")
    @patch("execution.collectors.risk_collector.BlockedBugsQuery")
    @patch("execution.collectors.risk_collector.MissingTestsQuery")
    def test_collect_for_multiple_projects(
        self, mock_missing_tests, mock_blocked, mock_stale, mock_high_priority, mock_wit_client
    ):
        """Test collecting metrics for multiple projects."""
        # Setup mock query instances with proper class names
        query_configs = [
            (mock_high_priority, "HighPriorityBugsQuery"),
            (mock_stale, "StaleBugsQuery"),
            (mock_blocked, "BlockedBugsQuery"),
            (mock_missing_tests, "MissingTestsQuery"),
        ]

        for mock_query_class, class_name in query_configs:
            mock_instance = Mock()
            mock_instance.__class__.__name__ = class_name
            # Return different counts based on call
            mock_instance.execute.return_value = {
                "project": "TestProject",
                "count": 2,
                "queried_at": "2026-02-10T10:00:00",
            }
            mock_query_class.return_value = mock_instance

        collector = ADORiskCollector(mock_wit_client)

        projects = [
            {"project_name": "Project1"},
            {"project_name": "Project2"},
            {"project_name": "Project3"},
        ]

        results = collector.collect_for_multiple_projects(projects)

        # Should have results for all projects
        assert len(results) == 3
        assert results[0]["project"] == "Project1"
        assert results[1]["project"] == "Project2"
        assert results[2]["project"] == "Project3"

    @patch("execution.collectors.risk_collector.HighPriorityBugsQuery")
    def test_collect_for_multiple_projects_with_filters(self, mock_high_priority, mock_wit_client):
        """Test multi-project collection with per-project filters."""
        # Setup mock with proper class name
        mock_instance = Mock()
        mock_instance.__class__.__name__ = "HighPriorityBugsQuery"
        mock_instance.execute.return_value = {
            "project": "TestProject",
            "count": 1,
            "queried_at": "2026-02-10T10:00:00",
        }
        mock_high_priority.return_value = mock_instance

        collector = ADORiskCollector(
            mock_wit_client,
            enable_high_priority=True,
            enable_stale=False,
            enable_blocked=False,
            enable_missing_tests=False,
        )

        projects = [
            {"project_name": "Project1", "area_path_filter": "EXCLUDE:Project1\\Archive"},
            {"project_name": "Project2", "area_path_filter": "INCLUDE:Project2\\Active"},
            {"project_name": "Project3"},  # No filter
        ]

        results = collector.collect_for_multiple_projects(projects)

        # Verify all projects processed
        assert len(results) == 3

    @patch("execution.collectors.risk_collector.HighPriorityBugsQuery")
    def test_collect_for_multiple_projects_with_failure(self, mock_high_priority, mock_wit_client):
        """Test multi-project collection when one project fails."""
        # Setup mock to fail on second project
        mock_instance = Mock()
        mock_instance.__class__.__name__ = "HighPriorityBugsQuery"

        def execute_side_effect(project_name, area_path_filter=None):
            if project_name == "Project2":
                raise Exception("API Error for Project2")
            return {"project": project_name, "count": 1, "queried_at": "2026-02-10T10:00:00"}

        mock_instance.execute.side_effect = execute_side_effect
        mock_high_priority.return_value = mock_instance

        collector = ADORiskCollector(
            mock_wit_client,
            enable_high_priority=True,
            enable_stale=False,
            enable_blocked=False,
            enable_missing_tests=False,
        )

        projects = [
            {"project_name": "Project1"},
            {"project_name": "Project2"},
            {"project_name": "Project3"},
        ]

        results = collector.collect_for_multiple_projects(projects)

        # Should still have all 3 results (including error)
        assert len(results) == 3

        # First and third should succeed
        assert results[0]["project"] == "Project1"
        assert "error" not in results[0]

        # Second should have error in query results
        assert results[1]["project"] == "Project2"
        assert "errors" in results[1]
        assert len(results[1]["errors"]) == 1
        assert "API Error for Project2" in results[1]["errors"][0]["error"]

        # Third should succeed
        assert results[2]["project"] == "Project3"
        assert "error" not in results[2]

    def test_collect_for_projects_with_missing_names(self, mock_wit_client):
        """Test multi-project collection skips projects without names."""
        collector = ADORiskCollector(mock_wit_client)

        projects = [
            {"project_name": "Project1"},
            {"invalid_key": "NoProjectName"},  # Missing project_name
            {"project_name": "Project3"},
        ]

        with patch.object(collector, "collect_metrics") as mock_collect:
            mock_collect.return_value = {
                "project": "TestProject",
                "summary": {"total_risk_items": 0, "queries_executed": 4, "queries_failed": 0},
            }

            results = collector.collect_for_multiple_projects(projects)

            # Should only process projects with valid names
            assert mock_collect.call_count == 2


class TestADORiskCollectorHelpers:
    """Test ADORiskCollector helper methods."""

    def test_get_query_names(self, mock_wit_client):
        """Test get_query_names returns correct query class names."""
        collector = ADORiskCollector(mock_wit_client)

        query_names = collector.get_query_names()

        assert len(query_names) == 4
        assert "HighPriorityBugsQuery" in query_names
        assert "StaleBugsQuery" in query_names
        assert "BlockedBugsQuery" in query_names
        assert "MissingTestsQuery" in query_names

    def test_get_query_names_with_selective_queries(self, mock_wit_client):
        """Test get_query_names with selective query enablement."""
        collector = ADORiskCollector(
            mock_wit_client,
            enable_high_priority=True,
            enable_stale=False,
            enable_blocked=True,
            enable_missing_tests=False,
        )

        query_names = collector.get_query_names()

        assert len(query_names) == 2
        assert "HighPriorityBugsQuery" in query_names
        assert "BlockedBugsQuery" in query_names
