#!/usr/bin/env python3
"""
Tests for ADO Ownership Metrics Collector

Covers:
- Area filter clause building
- WIQL query execution
- Pure analysis functions (unassigned, distribution, area stats, segmentation)
- PII stripping for history
- Save logic with validation
- Collector orchestration
"""

import json
from collections import defaultdict
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from execution.collectors.ado_ownership_metrics import (
    OwnershipCollector,
    _accumulate_repo_commits,
    _build_area_filter_clause,
    _build_developer_stats,
    _calculate_load_imbalance,
    _count_unassigned_by_type,
    _execute_wiql_query,
    _extract_assignee_name,
    _is_unassigned,
    _strip_pii_for_history,
    calculate_area_unassigned_stats,
    calculate_assignment_distribution,
    calculate_developer_active_days,
    calculate_unassigned_items,
    calculate_work_type_segmentation,
    save_ownership_metrics,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_open_items() -> list[dict]:
    """Sample open work items for analysis tests."""
    return [
        {
            "System.Id": 1,
            "System.Title": "Fix login bug",
            "System.WorkItemType": "Bug",
            "System.State": "Active",
            "System.AssignedTo": {"displayName": "Alice"},
            "System.AreaPath": "Project\\TeamA",
            "System.CreatedDate": "2026-01-01T00:00:00Z",
        },
        {
            "System.Id": 2,
            "System.Title": "Add search feature",
            "System.WorkItemType": "User Story",
            "System.State": "New",
            "System.AssignedTo": None,
            "System.AreaPath": "Project\\TeamA",
            "System.CreatedDate": "2026-01-02T00:00:00Z",
        },
        {
            "System.Id": 3,
            "System.Title": "Update docs",
            "System.WorkItemType": "Task",
            "System.State": "Active",
            "System.AssignedTo": {"displayName": "Bob"},
            "System.AreaPath": "Project\\TeamB",
            "System.CreatedDate": "2026-01-03T00:00:00Z",
        },
        {
            "System.Id": 4,
            "System.Title": "Orphan task",
            "System.WorkItemType": "Task",
            "System.State": "New",
            "System.AssignedTo": {},
            "System.AreaPath": "Project\\TeamB",
            "System.CreatedDate": "2026-01-04T00:00:00Z",
        },
        {
            "System.Id": 5,
            "System.Title": "Another bug",
            "System.WorkItemType": "Bug",
            "System.State": "Active",
            "System.AssignedTo": {"displayName": "Alice"},
            "System.AreaPath": "Project\\TeamA",
            "System.CreatedDate": "2026-01-05T00:00:00Z",
        },
    ]


@pytest.fixture
def sample_project_metrics() -> dict:
    """Sample project metrics with PII fields for strip test."""
    return {
        "project_key": "P1",
        "project_name": "Project1",
        "unassigned": {
            "unassigned_count": 2,
            "total_items": 5,
            "unassigned_pct": 40.0,
            "items": [{"id": 2, "title": "Secret item"}],
            "by_type": {"bugs": 0, "features": 1, "tasks": 1},
        },
        "assignment_distribution": {
            "assignee_count": 2,
            "top_assignees": [("Alice", 3), ("Bob", 1)],
            "load_imbalance_ratio": 3.0,
        },
        "developer_active_days": {
            "sample_size": 2,
            "total_commits": 10,
            "lookback_days": 90,
            "developers": [{"developer": "Alice", "active_days": 20}],
            "avg_active_days": 15.0,
        },
        "area_unassigned_stats": {
            "area_count": 2,
            "areas": [{"area_path": "Project\\TeamA", "total_items": 3}],
        },
        "total_items_analyzed": 5,
    }


# ---------------------------------------------------------------------------
# _build_area_filter_clause
# ---------------------------------------------------------------------------


class TestBuildAreaFilterClause:
    """Test area filter clause building."""

    def test_none_filter_returns_empty(self):
        clause, msg = _build_area_filter_clause(None)
        assert clause == ""
        assert msg is None

    def test_empty_string_returns_empty(self):
        clause, msg = _build_area_filter_clause("")
        assert clause == ""
        assert msg is None

    @patch("execution.collectors.ado_ownership_metrics.WIQLValidator")
    def test_exclude_filter(self, mock_validator):
        mock_validator.validate_area_path.return_value = "Project\\Sandbox"
        clause, msg = _build_area_filter_clause("EXCLUDE:Project\\Sandbox")
        assert "NOT UNDER" in clause
        assert "Project\\Sandbox" in clause
        assert msg is not None and "Excluding" in msg

    @patch("execution.collectors.ado_ownership_metrics.WIQLValidator")
    def test_include_filter(self, mock_validator):
        mock_validator.validate_area_path.return_value = "Project\\Core"
        clause, msg = _build_area_filter_clause("INCLUDE:Project\\Core")
        assert "UNDER" in clause
        assert "NOT UNDER" not in clause
        assert msg is not None and "Including" in msg

    def test_invalid_format_returns_empty(self):
        clause, msg = _build_area_filter_clause("SOMETHING:Path")
        assert clause == ""
        assert msg is None


# ---------------------------------------------------------------------------
# _execute_wiql_query
# ---------------------------------------------------------------------------


class TestExecuteWiqlQuery:
    """Test WIQL query execution with mocked REST client."""

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_ownership_metrics.WIQLValidator")
    @patch("execution.collectors.ado_ownership_metrics.WorkItemTransformer")
    async def test_returns_item_ids(self, mock_transformer, mock_validator):
        mock_validator.validate_project_name.return_value = "TestProject"

        mock_item1 = Mock()
        mock_item1.id = 101
        mock_item2 = Mock()
        mock_item2.id = 102
        mock_wiql_result = Mock()
        mock_wiql_result.work_items = [mock_item1, mock_item2]
        mock_transformer.transform_wiql_response.return_value = mock_wiql_result

        rest_client = AsyncMock()
        rest_client.query_by_wiql.return_value = {"workItems": []}

        result = await _execute_wiql_query(rest_client, "TestProject", "")
        assert result == [101, 102]
        rest_client.query_by_wiql.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_ownership_metrics.WIQLValidator")
    @patch("execution.collectors.ado_ownership_metrics.WorkItemTransformer")
    async def test_returns_empty_when_no_items(self, mock_transformer, mock_validator):
        mock_validator.validate_project_name.return_value = "TestProject"
        mock_wiql_result = Mock()
        mock_wiql_result.work_items = []
        mock_transformer.transform_wiql_response.return_value = mock_wiql_result

        rest_client = AsyncMock()
        result = await _execute_wiql_query(rest_client, "TestProject", "")
        assert result == []


# ---------------------------------------------------------------------------
# _is_unassigned
# ---------------------------------------------------------------------------


class TestIsUnassigned:
    def test_none_is_unassigned(self):
        assert _is_unassigned(None) is True

    def test_empty_dict_is_unassigned(self):
        assert _is_unassigned({}) is True

    def test_dict_without_display_name_is_unassigned(self):
        assert _is_unassigned({"id": "123"}) is True

    def test_dict_with_display_name_is_assigned(self):
        assert _is_unassigned({"displayName": "Alice"}) is False

    def test_string_value_is_assigned(self):
        assert _is_unassigned("alice@example.com") is False


# ---------------------------------------------------------------------------
# calculate_unassigned_items
# ---------------------------------------------------------------------------


class TestCalculateUnassignedItems:
    def test_counts_unassigned(self, sample_open_items):
        result = calculate_unassigned_items(sample_open_items)
        assert result["unassigned_count"] == 2  # items 2 (None) and 4 (empty dict)
        assert result["total_items"] == 5
        assert result["unassigned_pct"] == 40.0

    def test_empty_list(self):
        result = calculate_unassigned_items([])
        assert result["unassigned_count"] == 0
        assert result["unassigned_pct"] == 0

    def test_by_type_breakdown(self, sample_open_items):
        result = calculate_unassigned_items(sample_open_items)
        by_type = result["by_type"]
        assert by_type["features"] == 1  # User Story counts as feature
        assert by_type["tasks"] == 1
        assert by_type["bugs"] == 0

    def test_items_capped_at_20(self):
        items = [
            {
                "System.Id": i,
                "System.Title": f"Item {i}",
                "System.WorkItemType": "Bug",
                "System.State": "New",
                "System.AssignedTo": None,
                "System.AreaPath": "P",
                "System.CreatedDate": "2026-01-01",
            }
            for i in range(30)
        ]
        result = calculate_unassigned_items(items)
        assert len(result["items"]) == 20
        assert result["unassigned_count"] == 30


# ---------------------------------------------------------------------------
# calculate_assignment_distribution
# ---------------------------------------------------------------------------


class TestCalculateAssignmentDistribution:
    def test_distribution(self, sample_open_items):
        result = calculate_assignment_distribution(sample_open_items)
        assert result["assignee_count"] == 2  # Alice, Bob (excludes Unassigned)
        assert len(result["top_assignees"]) <= 10

    def test_empty_items(self):
        result = calculate_assignment_distribution([])
        assert result["assignee_count"] == 0
        assert result["top_assignees"] == []
        assert result["load_imbalance_ratio"] is None


# ---------------------------------------------------------------------------
# _calculate_load_imbalance
# ---------------------------------------------------------------------------


class TestCalculateLoadImbalance:
    def test_single_assignee_returns_none(self):
        assert _calculate_load_imbalance([("Alice", 5)]) is None

    def test_two_named_assignees(self):
        result = _calculate_load_imbalance([("Alice", 10), ("Bob", 5)])
        assert result == 2.0

    def test_unassigned_excluded_from_min(self):
        # Max is Alice=10, min named is Bob=2 (Unassigned excluded)
        result = _calculate_load_imbalance([("Alice", 10), ("Unassigned", 1), ("Bob", 2)])
        assert result == 5.0

    def test_only_one_named_returns_none(self):
        result = _calculate_load_imbalance([("Alice", 10), ("Unassigned", 5)])
        assert result is None


# ---------------------------------------------------------------------------
# calculate_area_unassigned_stats
# ---------------------------------------------------------------------------


class TestCalculateAreaUnassignedStats:
    def test_area_stats(self, sample_open_items):
        result = calculate_area_unassigned_stats(sample_open_items)
        assert result["area_count"] == 2
        areas = {a["area_path"]: a for a in result["areas"]}
        assert areas["Project\\TeamA"]["total_items"] == 3
        assert areas["Project\\TeamA"]["unassigned_items"] == 1
        assert areas["Project\\TeamB"]["unassigned_items"] == 1

    def test_empty_items(self):
        result = calculate_area_unassigned_stats([])
        assert result["area_count"] == 0
        assert result["areas"] == []


# ---------------------------------------------------------------------------
# calculate_work_type_segmentation
# ---------------------------------------------------------------------------


class TestCalculateWorkTypeSegmentation:
    def test_segmentation(self, sample_open_items):
        result = calculate_work_type_segmentation(sample_open_items)
        assert result["Bug"]["total"] == 2
        assert result["Bug"]["unassigned"] == 0
        assert result["User Story"]["total"] == 1
        assert result["User Story"]["unassigned"] == 1
        assert result["Task"]["total"] == 2
        assert result["Task"]["unassigned"] == 1
        assert result["Other"]["total"] == 0


# ---------------------------------------------------------------------------
# _strip_pii_for_history
# ---------------------------------------------------------------------------


class TestStripPiiForHistory:
    def test_removes_pii_fields(self, sample_project_metrics):
        result = _strip_pii_for_history(sample_project_metrics)
        assert "items" not in result["unassigned"]
        assert "top_assignees" not in result["assignment_distribution"]
        assert "developers" not in result["developer_active_days"]
        assert "areas" not in result["area_unassigned_stats"]

    def test_preserves_aggregate_fields(self, sample_project_metrics):
        result = _strip_pii_for_history(sample_project_metrics)
        assert result["unassigned"]["unassigned_count"] == 2
        assert result["assignment_distribution"]["assignee_count"] == 2
        assert result["developer_active_days"]["sample_size"] == 2

    def test_does_not_mutate_original(self, sample_project_metrics):
        _strip_pii_for_history(sample_project_metrics)
        assert "items" in sample_project_metrics["unassigned"]
        assert "top_assignees" in sample_project_metrics["assignment_distribution"]


# ---------------------------------------------------------------------------
# _accumulate_repo_commits
# ---------------------------------------------------------------------------


class TestAccumulateRepoCommits:
    def test_accumulates_commits(self):
        developer_dates: defaultdict = defaultdict(set)
        commits = [
            {"author_name": "Alice", "author_date": "2026-01-01T10:00:00Z"},
            {"author_name": "Alice", "author_date": "2026-01-02T10:00:00Z"},
            {"author_name": "Bob", "author_date": "2026-01-01T12:00:00Z"},
        ]
        added = _accumulate_repo_commits(commits, developer_dates)
        assert added == 3
        assert len(developer_dates["Alice"]) == 2
        assert len(developer_dates["Bob"]) == 1

    def test_skips_invalid_dates(self):
        developer_dates: defaultdict = defaultdict(set)
        commits = [
            {"author_name": "Alice", "author_date": "not-a-date"},
            {"author_name": "Bob", "author_date": "2026-01-01T10:00:00Z"},
        ]
        added = _accumulate_repo_commits(commits, developer_dates)
        assert added == 1

    def test_skips_missing_fields(self):
        developer_dates: defaultdict = defaultdict(set)
        commits = [{"author_name": None, "author_date": "2026-01-01T10:00:00Z"}, {}]
        added = _accumulate_repo_commits(commits, developer_dates)
        assert added == 0


# ---------------------------------------------------------------------------
# save_ownership_metrics
# ---------------------------------------------------------------------------


class TestSaveOwnershipMetrics:
    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    def test_save_valid_data(self, mock_load, mock_save):
        mock_load.return_value = {"weeks": []}
        metrics = {"projects": [{"total_items_analyzed": 10, "assignment_distribution": {"assignee_count": 3}}]}
        result = save_ownership_metrics(metrics, "test.json")
        assert result is True
        mock_save.assert_called_once()

    def test_save_empty_projects_skipped(self):
        result = save_ownership_metrics({"projects": []}, "test.json")
        assert result is False

    def test_save_no_projects_key_skipped(self):
        result = save_ownership_metrics({}, "test.json")
        assert result is False

    def test_save_all_zeros_skipped(self):
        metrics = {"projects": [{"total_items_analyzed": 0, "assignment_distribution": {"assignee_count": 0}}]}
        result = save_ownership_metrics(metrics, "test.json")
        assert result is False

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    def test_save_caps_at_52_weeks(self, mock_load, mock_save):
        mock_load.return_value = {"weeks": [{"week": i} for i in range(55)]}
        metrics = {"projects": [{"total_items_analyzed": 5, "assignment_distribution": {"assignee_count": 2}}]}
        save_ownership_metrics(metrics, "test.json")
        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["weeks"]) == 52

    @patch("execution.utils_atomic_json.atomic_json_save", side_effect=OSError("disk full"))
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    def test_save_os_error_returns_false(self, mock_load, mock_save):
        mock_load.return_value = {"weeks": []}
        metrics = {"projects": [{"total_items_analyzed": 5, "assignment_distribution": {"assignee_count": 2}}]}
        result = save_ownership_metrics(metrics, "test.json")
        assert result is False


# ---------------------------------------------------------------------------
# OwnershipCollector orchestration
# ---------------------------------------------------------------------------


class TestOwnershipCollector:
    @patch("execution.collectors.ado_ownership_metrics.save_ownership_metrics", return_value=True)
    @patch("execution.collectors.ado_ownership_metrics.collect_ownership_metrics_for_project")
    @patch("execution.collectors.ado_ownership_metrics.track_collector_performance")
    def test_run_success(self, mock_tracker, mock_collect, mock_save):
        # Setup tracker context manager
        tracker_inst = Mock()
        tracker_inst.__enter__ = Mock(return_value=tracker_inst)
        tracker_inst.__exit__ = Mock(return_value=None)
        mock_tracker.return_value = tracker_inst

        mock_collect.return_value = {
            "project_key": "P1",
            "project_name": "Project1",
            "unassigned": {"unassigned_count": 1},
            "total_items_analyzed": 5,
        }

        with patch.object(OwnershipCollector, "__init__", lambda self: None):
            collector = OwnershipCollector()
            collector._base = Mock()
            collector._base.config = {"lookback_days": 90}
            collector._base.load_discovery_data.return_value = {
                "projects": [{"project_name": "Project1", "project_key": "P1"}]
            }
            collector._base.get_rest_client.return_value = Mock()
            collector.config = {"lookback_days": 90}
            collector.logger = Mock()

            import asyncio

            result = asyncio.get_event_loop().run_until_complete(collector.run())

        assert result is True
        mock_save.assert_called_once()

    @patch("execution.collectors.ado_ownership_metrics.track_collector_performance")
    def test_run_no_projects(self, mock_tracker):
        tracker_inst = Mock()
        tracker_inst.__enter__ = Mock(return_value=tracker_inst)
        tracker_inst.__exit__ = Mock(return_value=None)
        mock_tracker.return_value = tracker_inst

        with patch.object(OwnershipCollector, "__init__", lambda self: None):
            collector = OwnershipCollector()
            collector._base = Mock()
            collector._base.config = {"lookback_days": 90}
            collector._base.load_discovery_data.return_value = {"projects": []}
            collector.config = {"lookback_days": 90}
            collector.logger = Mock()

            import asyncio

            result = asyncio.get_event_loop().run_until_complete(collector.run())

        assert result is False


# ---------------------------------------------------------------------------
# _extract_assignee_name
# ---------------------------------------------------------------------------


class TestExtractAssigneeName:
    def test_dict_with_display_name(self):
        assert _extract_assignee_name({"displayName": "Alice"}) == "Alice"

    def test_dict_without_display_name(self):
        assert _extract_assignee_name({"id": "123"}) == "Unassigned"

    def test_none_returns_unassigned(self):
        assert _extract_assignee_name(None) == "Unassigned"

    def test_string_returns_string(self):
        assert _extract_assignee_name("alice@example.com") == "alice@example.com"
