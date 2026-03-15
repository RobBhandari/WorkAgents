#!/usr/bin/env python3
"""
Tests for ADO Flow Metrics Collector

Verifies:
- collect_flow_metrics_for_project: metric calculation orchestration
- _strip_detail_lists_for_history: PII stripping before persistence
- save_flow_metrics: history file management with validation
- FlowCollector.run: end-to-end collection flow
- FlowCollector._log_summary: summary output formatting
"""

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from execution.collectors.ado_flow_metrics import (
    FlowCollector,
    _strip_detail_lists_for_history,
    collect_flow_metrics_for_project,
    save_flow_metrics,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_project() -> dict:
    """Sample project metadata from discovery."""
    return {
        "project_name": "TestProject",
        "project_key": "TP",
        "ado_project_name": "TestProject-ADO",
        "area_path_filter": "TestProject\\Team1",
    }


@pytest.fixture
def sample_project_minimal() -> dict:
    """Project without optional fields."""
    return {
        "project_name": "MinimalProject",
        "project_key": "MP",
    }


@pytest.fixture
def sample_work_items() -> dict:
    """Sample query_work_items_for_flow return value."""
    return {
        "Bug": {
            "open_items": [{"id": 1, "title": "Bug1"}],
            "closed_items": [{"id": 2, "title": "Bug2"}],
            "open_count": 1,
            "closed_count": 1,
            "excluded_security_bugs": {"open": 2, "closed": 3},
        },
        "User Story": {
            "open_items": [{"id": 3, "title": "Story1"}],
            "closed_items": [],
            "open_count": 1,
            "closed_count": 0,
            "excluded_security_bugs": {"open": 0, "closed": 0},
        },
        "Task": {
            "open_items": [],
            "closed_items": [{"id": 4, "title": "Task1"}],
            "open_count": 0,
            "closed_count": 1,
            "excluded_security_bugs": {"open": 0, "closed": 0},
        },
    }


@pytest.fixture
def sample_lead_time() -> dict:
    return {"p50": 5, "p85": 12, "p95": 20, "raw_values": [3, 5, 12, 20]}


@pytest.fixture
def sample_dual_metrics() -> dict:
    return {
        "operational": {"p85": 10},
        "cleanup": {"closed_count": 2, "avg_age_years": 1.5},
        "indicators": {"is_cleanup_effort": False, "cleanup_percentage": 10.0},
    }


@pytest.fixture
def sample_aging() -> dict:
    return {
        "count": 3,
        "threshold_days": 30,
        "items": [{"id": 1, "title": "Old item", "age_days": 45}],
    }


@pytest.fixture
def sample_throughput() -> dict:
    return {"per_week": 2.5, "total": 10}


@pytest.fixture
def sample_variance() -> dict:
    return {"std_dev_days": 4.2, "coefficient_of_variation": 35}


@pytest.fixture
def sample_config() -> dict:
    return {"lookback_days": 90, "aging_threshold_days": 30}


@pytest.fixture
def sample_project_metrics() -> list:
    """Sample project metrics list for _log_summary."""
    return [
        {
            "project_key": "TP",
            "project_name": "TestProject",
            "total_open": 10,
            "total_closed_90d": 25,
            "work_type_metrics": {
                "Bug": {
                    "open_count": 5,
                    "closed_count_90d": 10,
                    "aging_items": {"count": 2},
                    "excluded_security_bugs": {"open": 1, "closed": 2},
                },
                "User Story": {
                    "open_count": 3,
                    "closed_count_90d": 10,
                    "aging_items": {"count": 1},
                },
                "Task": {
                    "open_count": 2,
                    "closed_count_90d": 5,
                    "aging_items": {"count": 0},
                },
            },
        },
    ]


# ---------------------------------------------------------------------------
# Tests: collect_flow_metrics_for_project
# ---------------------------------------------------------------------------


class TestCollectFlowMetricsForProject:
    """Test the main collection orchestration function."""

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_flow_metrics.calculate_cycle_time_variance")
    @patch("execution.collectors.ado_flow_metrics.calculate_throughput")
    @patch("execution.collectors.ado_flow_metrics.calculate_aging_items")
    @patch("execution.collectors.ado_flow_metrics.calculate_dual_metrics")
    @patch("execution.collectors.ado_flow_metrics.calculate_lead_time")
    @patch("execution.collectors.ado_flow_metrics.query_work_items_for_flow", new_callable=AsyncMock)
    async def test_returns_correct_structure(
        self,
        mock_query,
        mock_lead_time,
        mock_dual,
        mock_aging,
        mock_throughput,
        mock_variance,
        sample_project,
        sample_work_items,
        sample_lead_time,
        sample_dual_metrics,
        sample_aging,
        sample_throughput,
        sample_variance,
        sample_config,
    ):
        mock_query.return_value = sample_work_items
        mock_lead_time.return_value = sample_lead_time
        mock_dual.return_value = sample_dual_metrics
        mock_aging.return_value = sample_aging
        mock_throughput.return_value = sample_throughput
        mock_variance.return_value = sample_variance

        rest_client = Mock()
        result = await collect_flow_metrics_for_project(rest_client, sample_project, sample_config)

        assert result["project_key"] == "TP"
        assert result["project_name"] == "TestProject"
        assert result["total_open"] == 2  # Bug:1 + Story:1 + Task:0
        assert result["total_closed_90d"] == 2  # Bug:1 + Story:0 + Task:1
        assert "work_type_metrics" in result
        assert "collected_at" in result
        for wt in ["Bug", "User Story", "Task"]:
            assert wt in result["work_type_metrics"]

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_flow_metrics.calculate_cycle_time_variance")
    @patch("execution.collectors.ado_flow_metrics.calculate_throughput")
    @patch("execution.collectors.ado_flow_metrics.calculate_aging_items")
    @patch("execution.collectors.ado_flow_metrics.calculate_dual_metrics")
    @patch("execution.collectors.ado_flow_metrics.calculate_lead_time")
    @patch("execution.collectors.ado_flow_metrics.query_work_items_for_flow", new_callable=AsyncMock)
    async def test_uses_ado_project_name(
        self,
        mock_query,
        mock_lead_time,
        mock_dual,
        mock_aging,
        mock_throughput,
        mock_variance,
        sample_project,
        sample_config,
    ):
        """Verify query uses ado_project_name, not project_name."""
        mock_query.return_value = {}
        mock_lead_time.return_value = {"p50": 0, "p85": 0, "p95": 0}
        mock_dual.return_value = {"operational": {}, "cleanup": {}, "indicators": {"is_cleanup_effort": False}}
        mock_aging.return_value = {"count": 0, "threshold_days": 30, "items": []}
        mock_throughput.return_value = {"per_week": 0}
        mock_variance.return_value = {"std_dev_days": 0, "coefficient_of_variation": 0}

        await collect_flow_metrics_for_project(Mock(), sample_project, sample_config)

        mock_query.assert_called_once()
        call_args = mock_query.call_args
        assert call_args[0][1] == "TestProject-ADO"
        assert call_args[1]["area_path_filter"] == "TestProject\\Team1"

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_flow_metrics.calculate_cycle_time_variance")
    @patch("execution.collectors.ado_flow_metrics.calculate_throughput")
    @patch("execution.collectors.ado_flow_metrics.calculate_aging_items")
    @patch("execution.collectors.ado_flow_metrics.calculate_dual_metrics")
    @patch("execution.collectors.ado_flow_metrics.calculate_lead_time")
    @patch("execution.collectors.ado_flow_metrics.query_work_items_for_flow", new_callable=AsyncMock)
    async def test_minimal_project_defaults(
        self,
        mock_query,
        mock_lead_time,
        mock_dual,
        mock_aging,
        mock_throughput,
        mock_variance,
        sample_project_minimal,
        sample_config,
    ):
        """Project without ado_project_name falls back to project_name."""
        mock_query.return_value = {}
        mock_lead_time.return_value = {"p50": 0, "p85": 0, "p95": 0}
        mock_dual.return_value = {"operational": {}, "cleanup": {}, "indicators": {"is_cleanup_effort": False}}
        mock_aging.return_value = {"count": 0, "threshold_days": 30, "items": []}
        mock_throughput.return_value = {"per_week": 0}
        mock_variance.return_value = {"std_dev_days": 0, "coefficient_of_variation": 0}

        await collect_flow_metrics_for_project(Mock(), sample_project_minimal, sample_config)

        call_args = mock_query.call_args
        assert call_args[0][1] == "MinimalProject"
        assert call_args[1]["area_path_filter"] is None

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_flow_metrics.calculate_cycle_time_variance")
    @patch("execution.collectors.ado_flow_metrics.calculate_throughput")
    @patch("execution.collectors.ado_flow_metrics.calculate_aging_items")
    @patch("execution.collectors.ado_flow_metrics.calculate_dual_metrics")
    @patch("execution.collectors.ado_flow_metrics.calculate_lead_time")
    @patch("execution.collectors.ado_flow_metrics.query_work_items_for_flow", new_callable=AsyncMock)
    async def test_cleanup_detected_path(
        self,
        mock_query,
        mock_lead_time,
        mock_dual,
        mock_aging,
        mock_throughput,
        mock_variance,
        sample_project,
        sample_config,
    ):
        """When cleanup is detected, dual_metrics indicators show it."""
        mock_query.return_value = {
            "Bug": {"open_items": [], "closed_items": [{"id": 1}], "open_count": 0, "closed_count": 1},
        }
        mock_lead_time.return_value = {"p50": 5, "p85": 10, "p95": 20}
        mock_dual.return_value = {
            "operational": {"p85": 8},
            "cleanup": {"closed_count": 5, "avg_age_years": 2.0},
            "indicators": {"is_cleanup_effort": True, "cleanup_percentage": 45.0},
        }
        mock_aging.return_value = {"count": 0, "threshold_days": 30, "items": []}
        mock_throughput.return_value = {"per_week": 1}
        mock_variance.return_value = {"std_dev_days": 3, "coefficient_of_variation": 25}

        result = await collect_flow_metrics_for_project(Mock(), sample_project, sample_config)

        bug_metrics = result["work_type_metrics"]["Bug"]
        assert bug_metrics["dual_metrics"]["indicators"]["is_cleanup_effort"] is True


# ---------------------------------------------------------------------------
# Tests: _strip_detail_lists_for_history
# ---------------------------------------------------------------------------


class TestStripDetailListsForHistory:
    """Test PII/detail stripping before history persistence."""

    def test_strips_aging_items(self):
        project = {
            "work_type_metrics": {
                "Bug": {
                    "aging_items": {"count": 2, "items": [{"id": 1, "title": "Secret"}]},
                    "lead_time": {"p85": 10},
                },
            },
        }
        result = _strip_detail_lists_for_history(project)

        assert "items" not in result["work_type_metrics"]["Bug"]["aging_items"]
        assert result["work_type_metrics"]["Bug"]["aging_items"]["count"] == 2

    def test_strips_lead_time_raw_values(self):
        project = {
            "work_type_metrics": {
                "Task": {
                    "aging_items": {"count": 0},
                    "lead_time": {"p85": 10, "raw_values": [1, 2, 3]},
                },
            },
        }
        result = _strip_detail_lists_for_history(project)

        assert "raw_values" not in result["work_type_metrics"]["Task"]["lead_time"]
        assert result["work_type_metrics"]["Task"]["lead_time"]["p85"] == 10

    def test_does_not_mutate_original(self):
        project = {
            "work_type_metrics": {
                "Bug": {
                    "aging_items": {"count": 1, "items": [{"id": 1}]},
                    "lead_time": {"p85": 5, "raw_values": [5]},
                },
            },
        }
        _strip_detail_lists_for_history(project)

        # Original must be unchanged
        assert "items" in project["work_type_metrics"]["Bug"]["aging_items"]
        assert "raw_values" in project["work_type_metrics"]["Bug"]["lead_time"]

    def test_handles_empty_work_type_metrics(self):
        project: dict = {"work_type_metrics": {}}
        result = _strip_detail_lists_for_history(project)
        assert result["work_type_metrics"] == {}

    def test_handles_missing_work_type_metrics(self):
        project: dict = {"project_name": "NoMetrics"}
        result = _strip_detail_lists_for_history(project)
        assert result["project_name"] == "NoMetrics"

    def test_strips_across_multiple_work_types(self):
        project = {
            "work_type_metrics": {
                "Bug": {
                    "aging_items": {"count": 1, "items": [{"id": 1}]},
                    "lead_time": {"p85": 5, "raw_values": [5]},
                },
                "User Story": {
                    "aging_items": {"count": 2, "items": [{"id": 2}, {"id": 3}]},
                    "lead_time": {"p85": 8, "raw_values": [3, 8]},
                },
            },
        }
        result = _strip_detail_lists_for_history(project)

        for wt in ["Bug", "User Story"]:
            assert "items" not in result["work_type_metrics"][wt]["aging_items"]
            assert "raw_values" not in result["work_type_metrics"][wt]["lead_time"]


# ---------------------------------------------------------------------------
# Tests: save_flow_metrics
# ---------------------------------------------------------------------------


class TestSaveFlowMetrics:
    """Test history file saving with validation."""

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery", return_value={"weeks": []})
    @patch("os.makedirs")
    def test_save_success(self, mock_makedirs, mock_load, mock_save):
        metrics = {
            "projects": [
                {"total_open": 5, "total_closed_90d": 10, "work_type_metrics": {}},
            ],
        }
        result = save_flow_metrics(metrics, "/tmp/test_flow.json")

        assert result is True
        mock_save.assert_called_once()

    def test_save_empty_projects_skips(self):
        metrics: dict = {"projects": []}
        result = save_flow_metrics(metrics)
        assert result is False

    def test_save_all_zeros_skips(self):
        metrics = {
            "projects": [
                {"total_open": 0, "total_closed_90d": 0},
            ],
        }
        result = save_flow_metrics(metrics)
        assert result is False

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_invalid_history_structure_recreates(self, mock_makedirs, mock_load, mock_save):
        """If existing history is malformed, recreate it."""
        mock_load.return_value = ["not", "a", "dict"]
        metrics = {
            "projects": [
                {"total_open": 1, "total_closed_90d": 2, "work_type_metrics": {}},
            ],
        }
        result = save_flow_metrics(metrics, "/tmp/test.json")

        assert result is True
        saved_data = mock_save.call_args[0][0]
        assert "weeks" in saved_data

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_appends_to_existing_history(self, mock_makedirs, mock_load, mock_save):
        mock_load.return_value = {"weeks": [{"week_date": "2026-01-01"}]}
        metrics = {
            "projects": [
                {"total_open": 3, "total_closed_90d": 7, "work_type_metrics": {}},
            ],
        }
        save_flow_metrics(metrics, "/tmp/test.json")

        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["weeks"]) == 2

    @patch("execution.utils_atomic_json.atomic_json_save", side_effect=OSError("disk full"))
    @patch("execution.utils_atomic_json.load_json_with_recovery", return_value={"weeks": []})
    @patch("os.makedirs")
    def test_save_write_failure_returns_false(self, mock_makedirs, mock_load, mock_save):
        metrics = {
            "projects": [
                {"total_open": 1, "total_closed_90d": 1, "work_type_metrics": {}},
            ],
        }
        result = save_flow_metrics(metrics, "/tmp/test.json")
        assert result is False

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_strips_detail_lists(self, mock_makedirs, mock_load, mock_save):
        """Verify detail lists are stripped before persisting."""
        mock_load.return_value = {"weeks": []}
        metrics = {
            "projects": [
                {
                    "total_open": 1,
                    "total_closed_90d": 1,
                    "work_type_metrics": {
                        "Bug": {
                            "aging_items": {"count": 1, "items": [{"title": "secret"}]},
                            "lead_time": {"p85": 5, "raw_values": [5]},
                        },
                    },
                },
            ],
        }
        save_flow_metrics(metrics, "/tmp/test.json")

        saved_data = mock_save.call_args[0][0]
        bug = saved_data["weeks"][0]["projects"][0]["work_type_metrics"]["Bug"]
        assert "items" not in bug["aging_items"]
        assert "raw_values" not in bug["lead_time"]

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_history_missing_weeks_key(self, mock_makedirs, mock_load, mock_save):
        """Dict without 'weeks' key is treated as invalid."""
        mock_load.return_value = {"data": "something"}
        metrics = {
            "projects": [{"total_open": 1, "total_closed_90d": 1, "work_type_metrics": {}}],
        }
        result = save_flow_metrics(metrics, "/tmp/test.json")
        assert result is True
        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["weeks"]) == 1


# ---------------------------------------------------------------------------
# Tests: FlowCollector.run
# ---------------------------------------------------------------------------


class TestFlowCollectorRun:
    """Test FlowCollector end-to-end run."""

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_flow_metrics.save_flow_metrics", return_value=True)
    @patch("execution.collectors.ado_flow_metrics.collect_flow_metrics_for_project", new_callable=AsyncMock)
    @patch("execution.collectors.ado_flow_metrics.track_collector_performance")
    async def test_run_success(self, mock_tracker, mock_collect, mock_save):
        mock_tracker_ctx = Mock()
        mock_tracker_ctx.__enter__ = Mock(return_value=mock_tracker_ctx)
        mock_tracker_ctx.__exit__ = Mock(return_value=None)
        mock_tracker.return_value = mock_tracker_ctx

        mock_collect.return_value = {
            "project_key": "TP",
            "project_name": "Test",
            "total_open": 5,
            "total_closed_90d": 10,
            "work_type_metrics": {},
        }

        collector = FlowCollector()
        with patch.object(
            collector._base,
            "load_discovery_data",
            return_value={
                "projects": [{"project_name": "Test", "project_key": "TP"}],
            },
        ):
            with patch.object(collector._base, "get_rest_client", return_value=Mock()):
                result = await collector.run()

        assert result is True
        mock_collect.assert_called_once()
        mock_save.assert_called_once()

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_flow_metrics.track_collector_performance")
    async def test_run_no_projects(self, mock_tracker):
        mock_tracker_ctx = Mock()
        mock_tracker_ctx.__enter__ = Mock(return_value=mock_tracker_ctx)
        mock_tracker_ctx.__exit__ = Mock(return_value=None)
        mock_tracker.return_value = mock_tracker_ctx

        collector = FlowCollector()
        with patch.object(collector._base, "load_discovery_data", return_value={"projects": []}):
            result = await collector.run()

        assert result is False

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_flow_metrics.save_flow_metrics", return_value=True)
    @patch("execution.collectors.ado_flow_metrics.collect_flow_metrics_for_project", new_callable=AsyncMock)
    @patch("execution.collectors.ado_flow_metrics.track_collector_performance")
    async def test_run_handles_collection_exception(self, mock_tracker, mock_collect, mock_save):
        mock_tracker_ctx = Mock()
        mock_tracker_ctx.__enter__ = Mock(return_value=mock_tracker_ctx)
        mock_tracker_ctx.__exit__ = Mock(return_value=None)
        mock_tracker.return_value = mock_tracker_ctx

        mock_collect.side_effect = ValueError("API error")

        collector = FlowCollector()
        with patch.object(
            collector._base,
            "load_discovery_data",
            return_value={
                "projects": [{"project_name": "Test", "project_key": "TP"}],
            },
        ):
            with patch.object(collector._base, "get_rest_client", return_value=Mock()):
                result = await collector.run()

        # Exception is caught by gather(return_exceptions=True), empty project_metrics
        mock_save.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: FlowCollector._log_summary
# ---------------------------------------------------------------------------


class TestFlowCollectorLogSummary:
    """Test summary logging output."""

    def test_log_summary_with_data(self, sample_project_metrics, capsys):
        collector = FlowCollector()
        collector._log_summary(sample_project_metrics)

        output = capsys.readouterr().out
        assert "Projects processed: 1" in output
        assert "Bug:" in output
        assert "User Story:" in output
        assert "Task:" in output
        assert "Total WIP (all types): 10" in output
        assert "Total Closed (90d, all types): 25" in output

    def test_log_summary_empty_list(self, capsys):
        collector = FlowCollector()
        collector._log_summary([])

        output = capsys.readouterr().out
        assert "Projects processed: 0" in output

    def test_log_summary_shows_excluded_security_bugs(self, sample_project_metrics, capsys):
        collector = FlowCollector()
        collector._log_summary(sample_project_metrics)

        output = capsys.readouterr().out
        assert "Security bugs excluded" in output

    def test_log_summary_no_security_exclusions(self, capsys):
        """When no security bugs excluded, that line should not appear."""
        metrics = [
            {
                "project_key": "TP",
                "project_name": "Test",
                "total_open": 5,
                "total_closed_90d": 10,
                "work_type_metrics": {
                    "Bug": {
                        "open_count": 5,
                        "closed_count_90d": 10,
                        "aging_items": {"count": 0},
                        "excluded_security_bugs": {"open": 0, "closed": 0},
                    },
                    "User Story": {"open_count": 0, "closed_count_90d": 0, "aging_items": {"count": 0}},
                    "Task": {"open_count": 0, "closed_count_90d": 0, "aging_items": {"count": 0}},
                },
            },
        ]
        collector = FlowCollector()
        collector._log_summary(metrics)

        output = capsys.readouterr().out
        assert "Security bugs excluded" not in output
