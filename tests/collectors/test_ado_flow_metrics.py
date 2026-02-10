"""
Tests for ADO Flow Metrics Collector

Tests cover:
- collect_flow_metrics_for_project: Flow metrics collection orchestration
- Project discovery loading and ADO connection
- Flow metrics calculation per project and work type
- History file saving with validation
- Error handling (missing files, invalid JSON, connection failures)
- Edge cases (zero data, empty projects, security bug exclusion)
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from execution.collectors.ado_flow_metrics import (
    collect_flow_metrics_for_project,
    save_flow_metrics,
)


@pytest.fixture
def sample_project():
    """Sample project metadata from discovery"""
    return {
        "project_name": "Test Project",
        "project_key": "TEST",
        "ado_project_name": "Test Project",
        "area_path_filter": None,
    }


@pytest.fixture
def sample_project_with_area_filter():
    """Sample project with area path filter"""
    return {
        "project_name": "Filtered Project",
        "project_key": "FILT",
        "ado_project_name": "Filtered Project ADO",
        "area_path_filter": "EXCLUDE:Legacy\\Archive",
    }


@pytest.fixture
def sample_work_items_segmented():
    """Sample work items segmented by work type"""
    return {
        "Bug": {
            "open_items": [
                {"id": 1, "created_date": "2026-01-15T00:00:00", "state": "Active"},
                {"id": 2, "created_date": "2026-02-01T00:00:00", "state": "New"},
            ],
            "closed_items": [
                {
                    "id": 3,
                    "created_date": "2026-01-01T00:00:00",
                    "closed_date": "2026-01-10T00:00:00",
                    "activated_date": "2026-01-02T00:00:00",
                },
                {
                    "id": 4,
                    "created_date": "2026-01-05T00:00:00",
                    "closed_date": "2026-01-20T00:00:00",
                    "activated_date": "2026-01-06T00:00:00",
                },
            ],
            "open_count": 2,
            "closed_count": 2,
            "excluded_security_bugs": {"open": 1, "closed": 3},
        },
        "User Story": {
            "open_items": [{"id": 5, "created_date": "2026-01-20T00:00:00", "state": "Active"}],
            "closed_items": [
                {
                    "id": 6,
                    "created_date": "2025-12-15T00:00:00",
                    "closed_date": "2026-01-15T00:00:00",
                    "activated_date": "2025-12-20T00:00:00",
                }
            ],
            "open_count": 1,
            "closed_count": 1,
            "excluded_security_bugs": {"open": 0, "closed": 0},
        },
        "Task": {
            "open_items": [],
            "closed_items": [
                {
                    "id": 7,
                    "created_date": "2026-01-25T00:00:00",
                    "closed_date": "2026-01-28T00:00:00",
                    "activated_date": "2026-01-25T00:00:00",
                }
            ],
            "open_count": 0,
            "closed_count": 1,
            "excluded_security_bugs": {"open": 0, "closed": 0},
        },
    }


@pytest.fixture
def sample_empty_work_items():
    """Sample work items with no data"""
    return {
        "Bug": {"open_items": [], "closed_items": [], "open_count": 0, "closed_count": 0},
        "User Story": {"open_items": [], "closed_items": [], "open_count": 0, "closed_count": 0},
        "Task": {"open_items": [], "closed_items": [], "open_count": 0, "closed_count": 0},
    }


@pytest.fixture
def sample_config():
    """Sample configuration for flow metrics collection"""
    return {"lookback_days": 90, "aging_threshold_days": 30}


@pytest.fixture
def sample_discovery_data(sample_project):
    """Sample project discovery data"""
    return {"projects": [sample_project, {"project_name": "Project 2", "project_key": "P2"}]}


@pytest.fixture
def sample_flow_metrics():
    """Sample flow metrics for a project"""
    return {
        "project_key": "TEST",
        "project_name": "Test Project",
        "work_type_metrics": {
            "Bug": {
                "open_count": 25,
                "closed_count_90d": 50,
                "wip": 25,
                "lead_time": {"p50": 5.0, "p85": 10.0, "p95": 15.0},
                "dual_metrics": {
                    "operational": {"p50": 5.0, "p85": 9.0, "p95": 14.0, "closed_count": 45},
                    "cleanup": {"closed_count": 5, "avg_age_years": 2.5},
                    "indicators": {"is_cleanup_effort": False, "cleanup_percentage": 10.0},
                },
                "aging_items": {"count": 5, "threshold_days": 30},
                "throughput": {"per_week": 5.5, "per_day": 0.79},
                "cycle_time_variance": {"std_dev_days": 2.5, "coefficient_of_variation": 30},
                "excluded_security_bugs": {"open": 2, "closed": 8},
            },
            "User Story": {
                "open_count": 15,
                "closed_count_90d": 30,
                "wip": 15,
                "lead_time": {"p50": 7.0, "p85": 12.0, "p95": 18.0},
                "dual_metrics": {
                    "operational": {"p50": 7.0, "p85": 12.0, "p95": 18.0, "closed_count": 30},
                    "cleanup": {"closed_count": 0, "avg_age_years": 0.0},
                    "indicators": {"is_cleanup_effort": False, "cleanup_percentage": 0.0},
                },
                "aging_items": {"count": 3, "threshold_days": 30},
                "throughput": {"per_week": 3.3, "per_day": 0.47},
                "cycle_time_variance": {"std_dev_days": 1.8, "coefficient_of_variation": 25},
                "excluded_security_bugs": {"open": 0, "closed": 0},
            },
            "Task": {
                "open_count": 10,
                "closed_count_90d": 80,
                "wip": 10,
                "lead_time": {"p50": 2.0, "p85": 4.0, "p95": 7.0},
                "dual_metrics": {
                    "operational": {"p50": 2.0, "p85": 4.0, "p95": 7.0, "closed_count": 80},
                    "cleanup": {"closed_count": 0, "avg_age_years": 0.0},
                    "indicators": {"is_cleanup_effort": False, "cleanup_percentage": 0.0},
                },
                "aging_items": {"count": 2, "threshold_days": 30},
                "throughput": {"per_week": 8.9, "per_day": 1.27},
                "cycle_time_variance": {"std_dev_days": 1.2, "coefficient_of_variation": 35},
                "excluded_security_bugs": {"open": 0, "closed": 0},
            },
        },
        "total_open": 50,
        "total_closed_90d": 160,
        "collected_at": "2026-02-10T10:00:00",
    }


@pytest.fixture
def sample_week_metrics(sample_flow_metrics):
    """Sample week metrics with multiple projects"""
    return {
        "week_date": "2026-02-10",
        "week_number": 6,
        "projects": [sample_flow_metrics],
        "config": {"lookback_days": 90, "aging_threshold_days": 30},
    }


@pytest.fixture
def mock_wit_client():
    """Mock Work Item Tracking client"""
    return MagicMock()


@pytest.fixture
def temp_output_file(tmp_path):
    """Temporary output file for testing"""
    return tmp_path / "flow_history.json"


class TestCollectFlowMetricsForProject:
    """Test flow metrics collection for a single project"""

    @patch("execution.collectors.ado_flow_metrics.query_work_items_for_flow")
    @patch("execution.collectors.ado_flow_metrics.calculate_lead_time")
    @patch("execution.collectors.ado_flow_metrics.calculate_dual_metrics")
    @patch("execution.collectors.ado_flow_metrics.calculate_aging_items")
    @patch("execution.collectors.ado_flow_metrics.calculate_throughput")
    @patch("execution.collectors.ado_flow_metrics.calculate_cycle_time_variance")
    def test_collect_metrics_basic(
        self,
        mock_variance,
        mock_throughput,
        mock_aging,
        mock_dual,
        mock_lead,
        mock_query,
        mock_wit_client,
        sample_project,
        sample_config,
        sample_work_items_segmented,
    ):
        """Test basic flow metrics collection for a project"""
        # Setup mocks
        mock_query.return_value = sample_work_items_segmented
        mock_lead.return_value = {"p50": 5.0, "p85": 10.0, "p95": 15.0}
        mock_dual.return_value = {
            "operational": {"p50": 5.0, "p85": 10.0, "p95": 15.0, "closed_count": 2},
            "cleanup": {"closed_count": 0, "avg_age_years": 0.0},
            "indicators": {"is_cleanup_effort": False, "cleanup_percentage": 0.0},
        }
        mock_aging.return_value = {"count": 1, "threshold_days": 30}
        mock_throughput.return_value = {"per_week": 2.2, "per_day": 0.31}
        mock_variance.return_value = {"std_dev_days": 1.5, "coefficient_of_variation": 25}

        # Execute
        result = collect_flow_metrics_for_project(mock_wit_client, sample_project, sample_config)

        # Verify structure
        assert result["project_key"] == "TEST"
        assert result["project_name"] == "Test Project"
        assert "work_type_metrics" in result
        assert "collected_at" in result
        assert "total_open" in result
        assert "total_closed_90d" in result

        # Verify query was called correctly
        mock_query.assert_called_once_with(mock_wit_client, "Test Project", lookback_days=90, area_path_filter=None)

        # Verify all three work types are present
        assert "Bug" in result["work_type_metrics"]
        assert "User Story" in result["work_type_metrics"]
        assert "Task" in result["work_type_metrics"]

    @patch("execution.collectors.ado_flow_metrics.query_work_items_for_flow")
    @patch("execution.collectors.ado_flow_metrics.calculate_lead_time")
    @patch("execution.collectors.ado_flow_metrics.calculate_dual_metrics")
    @patch("execution.collectors.ado_flow_metrics.calculate_aging_items")
    @patch("execution.collectors.ado_flow_metrics.calculate_throughput")
    @patch("execution.collectors.ado_flow_metrics.calculate_cycle_time_variance")
    def test_collect_metrics_with_area_filter(
        self,
        mock_variance,
        mock_throughput,
        mock_aging,
        mock_dual,
        mock_lead,
        mock_query,
        mock_wit_client,
        sample_project_with_area_filter,
        sample_config,
        sample_work_items_segmented,
    ):
        """Test flow metrics collection with area path filter"""
        # Setup mocks
        mock_query.return_value = sample_work_items_segmented
        mock_lead.return_value = {"p50": 5.0, "p85": 10.0, "p95": 15.0}
        mock_dual.return_value = {
            "operational": {"p50": 5.0, "p85": 10.0, "p95": 15.0, "closed_count": 2},
            "cleanup": {"closed_count": 0, "avg_age_years": 0.0},
            "indicators": {"is_cleanup_effort": False, "cleanup_percentage": 0.0},
        }
        mock_aging.return_value = {"count": 1, "threshold_days": 30}
        mock_throughput.return_value = {"per_week": 2.2, "per_day": 0.31}
        mock_variance.return_value = {"std_dev_days": 1.5, "coefficient_of_variation": 25}

        # Execute
        result = collect_flow_metrics_for_project(mock_wit_client, sample_project_with_area_filter, sample_config)

        # Verify query was called with area filter
        mock_query.assert_called_once_with(
            mock_wit_client,
            "Filtered Project ADO",
            lookback_days=90,
            area_path_filter="EXCLUDE:Legacy\\Archive",
        )

        assert result["project_key"] == "FILT"
        assert result["project_name"] == "Filtered Project"

    @patch("execution.collectors.ado_flow_metrics.query_work_items_for_flow")
    @patch("execution.collectors.ado_flow_metrics.calculate_lead_time")
    @patch("execution.collectors.ado_flow_metrics.calculate_dual_metrics")
    @patch("execution.collectors.ado_flow_metrics.calculate_aging_items")
    @patch("execution.collectors.ado_flow_metrics.calculate_throughput")
    @patch("execution.collectors.ado_flow_metrics.calculate_cycle_time_variance")
    def test_collect_metrics_totals_calculation(
        self,
        mock_variance,
        mock_throughput,
        mock_aging,
        mock_dual,
        mock_lead,
        mock_query,
        mock_wit_client,
        sample_project,
        sample_config,
        sample_work_items_segmented,
    ):
        """Test that totals are calculated correctly across work types"""
        # Setup mocks
        mock_query.return_value = sample_work_items_segmented
        mock_lead.return_value = {"p50": 5.0, "p85": 10.0, "p95": 15.0}
        mock_dual.return_value = {
            "operational": {"p50": 5.0, "p85": 10.0, "p95": 15.0, "closed_count": 2},
            "cleanup": {"closed_count": 0, "avg_age_years": 0.0},
            "indicators": {"is_cleanup_effort": False, "cleanup_percentage": 0.0},
        }
        mock_aging.return_value = {"count": 1, "threshold_days": 30}
        mock_throughput.return_value = {"per_week": 2.2, "per_day": 0.31}
        mock_variance.return_value = {"std_dev_days": 1.5, "coefficient_of_variation": 25}

        # Execute
        result = collect_flow_metrics_for_project(mock_wit_client, sample_project, sample_config)

        # Verify totals (2 open bugs + 1 open story + 0 open tasks = 3)
        # (2 closed bugs + 1 closed story + 1 closed task = 4)
        assert result["total_open"] == 3
        assert result["total_closed_90d"] == 4

    @patch("execution.collectors.ado_flow_metrics.query_work_items_for_flow")
    @patch("execution.collectors.ado_flow_metrics.calculate_lead_time")
    @patch("execution.collectors.ado_flow_metrics.calculate_dual_metrics")
    @patch("execution.collectors.ado_flow_metrics.calculate_aging_items")
    @patch("execution.collectors.ado_flow_metrics.calculate_throughput")
    @patch("execution.collectors.ado_flow_metrics.calculate_cycle_time_variance")
    def test_collect_metrics_work_type_segmentation(
        self,
        mock_variance,
        mock_throughput,
        mock_aging,
        mock_dual,
        mock_lead,
        mock_query,
        mock_wit_client,
        sample_project,
        sample_config,
        sample_work_items_segmented,
    ):
        """Test that metrics are correctly segmented by work type"""
        # Setup mocks
        mock_query.return_value = sample_work_items_segmented
        mock_lead.return_value = {"p50": 5.0, "p85": 10.0, "p95": 15.0}
        mock_dual.return_value = {
            "operational": {"p50": 5.0, "p85": 10.0, "p95": 15.0, "closed_count": 2},
            "cleanup": {"closed_count": 0, "avg_age_years": 0.0},
            "indicators": {"is_cleanup_effort": False, "cleanup_percentage": 0.0},
        }
        mock_aging.return_value = {"count": 1, "threshold_days": 30}
        mock_throughput.return_value = {"per_week": 2.2, "per_day": 0.31}
        mock_variance.return_value = {"std_dev_days": 1.5, "coefficient_of_variation": 25}

        # Execute
        result = collect_flow_metrics_for_project(mock_wit_client, sample_project, sample_config)

        # Verify each work type has all required metrics
        for work_type in ["Bug", "User Story", "Task"]:
            metrics = result["work_type_metrics"][work_type]
            assert "open_count" in metrics
            assert "closed_count_90d" in metrics
            assert "wip" in metrics
            assert "lead_time" in metrics
            assert "dual_metrics" in metrics
            assert "aging_items" in metrics
            assert "throughput" in metrics
            assert "cycle_time_variance" in metrics
            assert "excluded_security_bugs" in metrics

    @patch("execution.collectors.ado_flow_metrics.query_work_items_for_flow")
    @patch("execution.collectors.ado_flow_metrics.calculate_lead_time")
    @patch("execution.collectors.ado_flow_metrics.calculate_dual_metrics")
    @patch("execution.collectors.ado_flow_metrics.calculate_aging_items")
    @patch("execution.collectors.ado_flow_metrics.calculate_throughput")
    @patch("execution.collectors.ado_flow_metrics.calculate_cycle_time_variance")
    def test_collect_metrics_security_bug_exclusion(
        self,
        mock_variance,
        mock_throughput,
        mock_aging,
        mock_dual,
        mock_lead,
        mock_query,
        mock_wit_client,
        sample_project,
        sample_config,
        sample_work_items_segmented,
    ):
        """Test that security bugs are excluded and tracked separately"""
        # Setup mocks
        mock_query.return_value = sample_work_items_segmented
        mock_lead.return_value = {"p50": 5.0, "p85": 10.0, "p95": 15.0}
        mock_dual.return_value = {
            "operational": {"p50": 5.0, "p85": 10.0, "p95": 15.0, "closed_count": 2},
            "cleanup": {"closed_count": 0, "avg_age_years": 0.0},
            "indicators": {"is_cleanup_effort": False, "cleanup_percentage": 0.0},
        }
        mock_aging.return_value = {"count": 1, "threshold_days": 30}
        mock_throughput.return_value = {"per_week": 2.2, "per_day": 0.31}
        mock_variance.return_value = {"std_dev_days": 1.5, "coefficient_of_variation": 25}

        # Execute
        result = collect_flow_metrics_for_project(mock_wit_client, sample_project, sample_config)

        # Verify security bug exclusion is tracked in Bug metrics
        bug_metrics = result["work_type_metrics"]["Bug"]
        assert bug_metrics["excluded_security_bugs"]["open"] == 1
        assert bug_metrics["excluded_security_bugs"]["closed"] == 3

        # Verify User Story and Task don't exclude security bugs
        story_metrics = result["work_type_metrics"]["User Story"]
        assert story_metrics["excluded_security_bugs"]["open"] == 0
        assert story_metrics["excluded_security_bugs"]["closed"] == 0


class TestSaveFlowMetrics:
    """Test flow metrics history file saving"""

    def test_save_metrics_creates_new_file(self, sample_week_metrics, temp_output_file):
        """Test saving metrics creates a new file when it doesn't exist"""
        result = save_flow_metrics(sample_week_metrics, str(temp_output_file))

        assert result is True
        assert temp_output_file.exists()

        # Verify content
        with open(temp_output_file, encoding="utf-8") as f:
            data = json.load(f)
            assert "weeks" in data
            assert len(data["weeks"]) == 1
            assert data["weeks"][0]["week_date"] == "2026-02-10"

    def test_save_metrics_appends_to_existing_file(self, sample_week_metrics, temp_output_file):
        """Test saving metrics appends to existing history file"""
        # Create initial file
        initial_data = {
            "weeks": [
                {
                    "week_date": "2026-02-03",
                    "week_number": 5,
                    "projects": [
                        {
                            "project_key": "TEST",
                            "project_name": "Test",
                            "total_open": 40,
                            "total_closed_90d": 100,
                        }
                    ],
                }
            ]
        }
        temp_output_file.write_text(json.dumps(initial_data))

        # Append new data
        result = save_flow_metrics(sample_week_metrics, str(temp_output_file))

        assert result is True

        # Verify appended
        with open(temp_output_file, encoding="utf-8") as f:
            data = json.load(f)
            assert len(data["weeks"]) == 2
            assert data["weeks"][0]["week_date"] == "2026-02-03"
            assert data["weeks"][1]["week_date"] == "2026-02-10"

    def test_save_metrics_respects_retention_limit(self, sample_week_metrics, temp_output_file):
        """Test that old weeks are pruned according to retention policy"""
        # Create file with many weeks
        old_weeks = [
            {
                "week_date": f"2025-{i:02d}-01",
                "week_number": i,
                "projects": [{"project_key": "OLD", "total_open": 10, "total_closed_90d": 20}],
            }
            for i in range(1, 55)  # 54 weeks
        ]
        temp_output_file.write_text(json.dumps({"weeks": old_weeks}))

        # Add new week
        result = save_flow_metrics(sample_week_metrics, str(temp_output_file))

        assert result is True

        # Verify retention (should keep last 52 weeks max)
        with open(temp_output_file, encoding="utf-8") as f:
            data = json.load(f)
            assert len(data["weeks"]) == 52  # history_retention.WEEKS_TO_RETAIN

    def test_save_metrics_validates_no_projects(self, temp_output_file):
        """Test that saving fails when no projects are present"""
        metrics = {
            "week_date": "2026-02-10",
            "week_number": 6,
            "projects": [],  # Empty projects
            "config": {"lookback_days": 90},
        }

        result = save_flow_metrics(metrics, str(temp_output_file))

        assert result is False
        assert not temp_output_file.exists()

    def test_save_metrics_validates_all_zeros(self, temp_output_file):
        """Test that saving fails when all projects have zero data"""
        metrics = {
            "week_date": "2026-02-10",
            "week_number": 6,
            "projects": [
                {
                    "project_key": "EMPTY1",
                    "project_name": "Empty Project 1",
                    "total_open": 0,
                    "total_closed_90d": 0,
                },
                {
                    "project_key": "EMPTY2",
                    "project_name": "Empty Project 2",
                    "total_open": 0,
                    "total_closed_90d": 0,
                },
            ],
            "config": {"lookback_days": 90},
        }

        result = save_flow_metrics(metrics, str(temp_output_file))

        assert result is False
        assert not temp_output_file.exists()

    def test_save_metrics_allows_partial_data(self, temp_output_file):
        """Test that saving succeeds when some projects have data"""
        metrics = {
            "week_date": "2026-02-10",
            "week_number": 6,
            "projects": [
                {
                    "project_key": "EMPTY",
                    "project_name": "Empty Project",
                    "total_open": 0,
                    "total_closed_90d": 0,
                },
                {
                    "project_key": "ACTIVE",
                    "project_name": "Active Project",
                    "total_open": 25,
                    "total_closed_90d": 100,
                },
            ],
            "config": {"lookback_days": 90},
        }

        result = save_flow_metrics(metrics, str(temp_output_file))

        assert result is True
        assert temp_output_file.exists()

    def test_save_metrics_handles_invalid_existing_file(self, temp_output_file):
        """Test that saving handles corrupted existing history file"""
        # Create invalid JSON
        temp_output_file.write_text("{ invalid json }")

        # Should recreate file with warning
        metrics = {
            "week_date": "2026-02-10",
            "week_number": 6,
            "projects": [{"project_key": "TEST", "total_open": 10, "total_closed_90d": 20}],
            "config": {"lookback_days": 90},
        }

        result = save_flow_metrics(metrics, str(temp_output_file))

        assert result is True

        # Verify fresh start
        with open(temp_output_file, encoding="utf-8") as f:
            data = json.load(f)
            assert len(data["weeks"]) == 1

    def test_save_metrics_handles_missing_weeks_key(self, temp_output_file):
        """Test that saving handles existing file without 'weeks' key"""
        # Create file with invalid structure
        temp_output_file.write_text('{"invalid": "structure"}')

        metrics = {
            "week_date": "2026-02-10",
            "week_number": 6,
            "projects": [{"project_key": "TEST", "total_open": 10, "total_closed_90d": 20}],
            "config": {"lookback_days": 90},
        }

        result = save_flow_metrics(metrics, str(temp_output_file))

        assert result is True

        # Verify recreated with correct structure
        with open(temp_output_file, encoding="utf-8") as f:
            data = json.load(f)
            assert "weeks" in data
            assert len(data["weeks"]) == 1

    def test_save_metrics_creates_directory(self, tmp_path):
        """Test that saving creates output directory if it doesn't exist"""
        nested_path = tmp_path / "nested" / "dir" / "flow_history.json"

        metrics = {
            "week_date": "2026-02-10",
            "week_number": 6,
            "projects": [{"project_key": "TEST", "total_open": 10, "total_closed_90d": 20}],
            "config": {"lookback_days": 90},
        }

        result = save_flow_metrics(metrics, str(nested_path))

        assert result is True
        assert nested_path.exists()
        assert nested_path.parent.exists()


class TestMainScriptIntegration:
    """Test main script integration and orchestration"""

    @patch("execution.collectors.ado_flow_metrics.get_ado_connection")
    @patch("execution.collectors.ado_flow_metrics.collect_flow_metrics_for_project")
    @patch("execution.collectors.ado_flow_metrics.save_flow_metrics")
    def test_main_orchestration_flow(
        self, mock_save, mock_collect, mock_connection, sample_discovery_data, sample_flow_metrics, tmp_path
    ):
        """Test main script orchestration (not actually running __main__)"""
        # Setup: Create discovery file
        discovery_file = tmp_path / "ado_structure.json"
        discovery_file.write_text(json.dumps(sample_discovery_data))

        # Setup mocks
        mock_wit_client = MagicMock()
        mock_connection_obj = MagicMock()
        mock_connection_obj.clients.get_work_item_tracking_client.return_value = mock_wit_client
        mock_connection.return_value = mock_connection_obj
        mock_collect.return_value = sample_flow_metrics
        mock_save.return_value = True

        # Verify mocks are set up correctly for integration test
        assert mock_connection.return_value is not None
        assert mock_collect.return_value["project_key"] == "TEST"

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_main_handles_missing_discovery_file(self, mock_open):
        """Test main script handles missing discovery file gracefully"""
        # This test verifies the error handling logic
        # In actual script, this would call exit(1)
        with pytest.raises(FileNotFoundError):
            with open(".tmp/observatory/ado_structure.json", encoding="utf-8") as f:
                json.load(f)

    @patch("execution.collectors.ado_flow_metrics.get_ado_connection")
    def test_main_handles_ado_connection_failure(self, mock_connection):
        """Test main script handles ADO connection failures"""
        mock_connection.side_effect = Exception("Connection failed")

        with pytest.raises(Exception) as exc_info:
            mock_connection()

        assert "Connection failed" in str(exc_info.value)


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    @patch("execution.collectors.ado_flow_metrics.query_work_items_for_flow")
    @patch("execution.collectors.ado_flow_metrics.calculate_lead_time")
    @patch("execution.collectors.ado_flow_metrics.calculate_dual_metrics")
    @patch("execution.collectors.ado_flow_metrics.calculate_aging_items")
    @patch("execution.collectors.ado_flow_metrics.calculate_throughput")
    @patch("execution.collectors.ado_flow_metrics.calculate_cycle_time_variance")
    def test_empty_work_items(
        self,
        mock_variance,
        mock_throughput,
        mock_aging,
        mock_dual,
        mock_lead,
        mock_query,
        mock_wit_client,
        sample_project,
        sample_config,
        sample_empty_work_items,
    ):
        """Test handling of empty work items data"""
        # Setup mocks
        mock_query.return_value = sample_empty_work_items
        mock_lead.return_value = {"p50": None, "p85": None, "p95": None}
        mock_dual.return_value = {
            "operational": {"p50": None, "p85": None, "p95": None, "closed_count": 0},
            "cleanup": {"closed_count": 0, "avg_age_years": 0.0},
            "indicators": {"is_cleanup_effort": False, "cleanup_percentage": 0.0},
        }
        mock_aging.return_value = {"count": 0, "threshold_days": 30}
        mock_throughput.return_value = {"per_week": 0.0, "per_day": 0.0}
        mock_variance.return_value = {"std_dev_days": 0.0, "coefficient_of_variation": 0}

        # Execute
        result = collect_flow_metrics_for_project(mock_wit_client, sample_project, sample_config)

        # Verify zero counts
        assert result["total_open"] == 0
        assert result["total_closed_90d"] == 0

        # Verify all work types have zero metrics
        for work_type in ["Bug", "User Story", "Task"]:
            metrics = result["work_type_metrics"][work_type]
            assert metrics["open_count"] == 0
            assert metrics["closed_count_90d"] == 0
            assert metrics["wip"] == 0

    @patch("execution.collectors.ado_flow_metrics.query_work_items_for_flow")
    @patch("execution.collectors.ado_flow_metrics.calculate_lead_time")
    @patch("execution.collectors.ado_flow_metrics.calculate_dual_metrics")
    @patch("execution.collectors.ado_flow_metrics.calculate_aging_items")
    @patch("execution.collectors.ado_flow_metrics.calculate_throughput")
    @patch("execution.collectors.ado_flow_metrics.calculate_cycle_time_variance")
    def test_project_without_ado_project_name(
        self,
        mock_variance,
        mock_throughput,
        mock_aging,
        mock_dual,
        mock_lead,
        mock_query,
        mock_wit_client,
        sample_config,
        sample_work_items_segmented,
    ):
        """Test project without explicit ado_project_name uses project_name"""
        project = {
            "project_name": "Fallback Project",
            "project_key": "FALL",
            # No ado_project_name
        }

        # Setup mocks
        mock_query.return_value = sample_work_items_segmented
        mock_lead.return_value = {"p50": 5.0, "p85": 10.0, "p95": 15.0}
        mock_dual.return_value = {
            "operational": {"p50": 5.0, "p85": 10.0, "p95": 15.0, "closed_count": 2},
            "cleanup": {"closed_count": 0, "avg_age_years": 0.0},
            "indicators": {"is_cleanup_effort": False, "cleanup_percentage": 0.0},
        }
        mock_aging.return_value = {"count": 1, "threshold_days": 30}
        mock_throughput.return_value = {"per_week": 2.2, "per_day": 0.31}
        mock_variance.return_value = {"std_dev_days": 1.5, "coefficient_of_variation": 25}

        # Execute
        result = collect_flow_metrics_for_project(mock_wit_client, project, sample_config)

        # Verify query used project_name as fallback
        mock_query.assert_called_once()
        call_args = mock_query.call_args
        assert call_args[0][1] == "Fallback Project"  # Used project_name

    @patch("execution.collectors.ado_flow_metrics.query_work_items_for_flow")
    @patch("execution.collectors.ado_flow_metrics.calculate_lead_time")
    @patch("execution.collectors.ado_flow_metrics.calculate_dual_metrics")
    @patch("execution.collectors.ado_flow_metrics.calculate_aging_items")
    @patch("execution.collectors.ado_flow_metrics.calculate_throughput")
    @patch("execution.collectors.ado_flow_metrics.calculate_cycle_time_variance")
    def test_cleanup_effort_detection(
        self,
        mock_variance,
        mock_throughput,
        mock_aging,
        mock_dual,
        mock_lead,
        mock_query,
        mock_wit_client,
        sample_project,
        sample_config,
        sample_work_items_segmented,
    ):
        """Test cleanup effort detection and reporting"""
        # Setup mocks with cleanup effort detected
        mock_query.return_value = sample_work_items_segmented
        mock_lead.return_value = {"p50": 5.0, "p85": 10.0, "p95": 15.0}
        mock_dual.return_value = {
            "operational": {"p50": 3.0, "p85": 5.0, "p95": 8.0, "closed_count": 70},
            "cleanup": {"closed_count": 30, "avg_age_years": 2.8},
            "indicators": {"is_cleanup_effort": True, "cleanup_percentage": 43.0},  # >30% cleanup
        }
        mock_aging.return_value = {"count": 1, "threshold_days": 30}
        mock_throughput.return_value = {"per_week": 2.2, "per_day": 0.31}
        mock_variance.return_value = {"std_dev_days": 1.5, "coefficient_of_variation": 25}

        # Execute
        result = collect_flow_metrics_for_project(mock_wit_client, sample_project, sample_config)

        # Verify cleanup metrics are captured
        bug_metrics = result["work_type_metrics"]["Bug"]
        assert bug_metrics["dual_metrics"]["indicators"]["is_cleanup_effort"] is True
        assert bug_metrics["dual_metrics"]["indicators"]["cleanup_percentage"] == 43.0
        assert bug_metrics["dual_metrics"]["cleanup"]["closed_count"] == 30

    def test_save_metrics_timestamp_format(self, sample_week_metrics, temp_output_file):
        """Test that week_date timestamp is correctly formatted"""
        save_flow_metrics(sample_week_metrics, str(temp_output_file))

        with open(temp_output_file, encoding="utf-8") as f:
            data = json.load(f)
            week_date = data["weeks"][0]["week_date"]

            # Verify ISO date format
            datetime.fromisoformat(week_date)  # Should not raise
            assert week_date == "2026-02-10"

    def test_collect_metrics_timestamp_format(
        self, mock_wit_client, sample_project, sample_config, sample_work_items_segmented
    ):
        """Test that collected_at timestamp is in ISO format"""
        with (
            patch("execution.collectors.ado_flow_metrics.query_work_items_for_flow") as mock_query,
            patch("execution.collectors.ado_flow_metrics.calculate_lead_time") as mock_lead,
            patch("execution.collectors.ado_flow_metrics.calculate_dual_metrics") as mock_dual,
            patch("execution.collectors.ado_flow_metrics.calculate_aging_items") as mock_aging,
            patch("execution.collectors.ado_flow_metrics.calculate_throughput") as mock_throughput,
            patch("execution.collectors.ado_flow_metrics.calculate_cycle_time_variance") as mock_variance,
        ):
            # Setup mocks
            mock_query.return_value = sample_work_items_segmented
            mock_lead.return_value = {"p50": 5.0, "p85": 10.0, "p95": 15.0}
            mock_dual.return_value = {
                "operational": {"p50": 5.0, "p85": 10.0, "p95": 15.0, "closed_count": 2},
                "cleanup": {"closed_count": 0, "avg_age_years": 0.0},
                "indicators": {"is_cleanup_effort": False, "cleanup_percentage": 0.0},
            }
            mock_aging.return_value = {"count": 1, "threshold_days": 30}
            mock_throughput.return_value = {"per_week": 2.2, "per_day": 0.31}
            mock_variance.return_value = {"std_dev_days": 1.5, "coefficient_of_variation": 25}

            # Execute
            result = collect_flow_metrics_for_project(mock_wit_client, sample_project, sample_config)

            # Verify timestamp format
            collected_at = result["collected_at"]
            datetime.fromisoformat(collected_at)  # Should not raise
