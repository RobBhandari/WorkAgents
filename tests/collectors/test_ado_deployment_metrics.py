#!/usr/bin/env python3
"""
Tests for ADO Deployment Metrics Collector

Verifies deployment metrics collection and calculation:
- Build querying and transformation
- Deployment frequency calculation
- Build success rate calculation
- Build duration statistics
- Lead time for changes calculation
- Pipeline detail stripping for history
- Save/validation logic
- DeploymentCollector.run orchestration
"""

import json
from datetime import UTC, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from execution.collectors.ado_deployment_metrics import (
    DeploymentCollector,
    _calculate_single_build_lead_time,
    _strip_pipeline_names_for_history,
    _validate_deployment_data,
    calculate_build_duration,
    calculate_build_success_rate,
    calculate_deployment_frequency,
    calculate_lead_time_for_changes,
    collect_deployment_metrics_for_project,
    query_builds,
    save_deployment_metrics,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_builds() -> list[dict]:
    """Sample build data as returned by query_builds."""
    return [
        {
            "build_id": 101,
            "build_number": "20260301.1",
            "definition_id": 1,
            "definition_name": "CI-Pipeline",
            "status": "completed",
            "result": "succeeded",
            "start_time": "2026-03-01T10:00:00Z",
            "finish_time": "2026-03-01T10:05:00Z",
            "duration_minutes": 5.0,
            "source_branch": "refs/heads/main",
            "source_version": "abc123",
            "requested_for": "user@example.com",
        },
        {
            "build_id": 102,
            "build_number": "20260301.2",
            "definition_id": 1,
            "definition_name": "CI-Pipeline",
            "status": "completed",
            "result": "failed",
            "start_time": "2026-03-01T11:00:00Z",
            "finish_time": "2026-03-01T11:03:00Z",
            "duration_minutes": 3.0,
            "source_branch": "refs/heads/feature",
            "source_version": "def456",
            "requested_for": "user2@example.com",
        },
        {
            "build_id": 103,
            "build_number": "20260302.1",
            "definition_id": 2,
            "definition_name": "Deploy-Pipeline",
            "status": "completed",
            "result": "succeeded",
            "start_time": "2026-03-02T09:00:00Z",
            "finish_time": "2026-03-02T09:10:00Z",
            "duration_minutes": 10.0,
            "source_branch": "refs/heads/main",
            "source_version": "ghi789",
            "requested_for": "user@example.com",
        },
        {
            "build_id": 104,
            "build_number": "20260302.2",
            "definition_id": 1,
            "definition_name": "CI-Pipeline",
            "status": "completed",
            "result": "canceled",
            "start_time": "2026-03-02T12:00:00Z",
            "finish_time": "2026-03-02T12:01:00Z",
            "duration_minutes": 1.0,
            "source_branch": "refs/heads/main",
            "source_version": "jkl012",
            "requested_for": "user@example.com",
        },
    ]


@pytest.fixture
def sample_project() -> dict:
    """Sample project metadata."""
    return {
        "project_name": "TestProject",
        "project_key": "TP",
        "ado_project_name": "TestProject",
    }


@pytest.fixture
def sample_week_metrics(sample_builds) -> dict:
    """Sample week metrics for save testing."""
    return {
        "week_date": "2026-03-15",
        "week_number": 11,
        "projects": [
            {
                "project_key": "TP",
                "project_name": "TestProject",
                "deployment_frequency": {
                    "total_successful_builds": 2,
                    "by_pipeline": {"CI-Pipeline": 1, "Deploy-Pipeline": 1},
                },
                "build_success_rate": {
                    "total_builds": 4,
                    "by_pipeline": {"CI-Pipeline": {"succeeded": 1, "failed": 1}},
                },
                "build_duration": {
                    "sample_size": 4,
                    "by_pipeline": {"CI-Pipeline": {"count": 3, "median_minutes": 3.0}},
                },
                "lead_time_for_changes": {"sample_size": 2},
            }
        ],
        "config": {"lookback_days": 90},
    }


# ---------------------------------------------------------------------------
# Tests: query_builds
# ---------------------------------------------------------------------------


class TestQueryBuilds:
    """Test build querying and transformation."""

    @pytest.mark.asyncio
    async def test_query_builds_transforms_response(self):
        """Test that query_builds transforms REST response into build dicts."""
        mock_client = AsyncMock()
        mock_client.get_builds.return_value = {"value": []}

        with patch(
            "execution.collectors.ado_deployment_metrics.BuildTransformer.transform_builds_response",
            return_value=[
                {
                    "id": 1,
                    "build_number": "20260301.1",
                    "definition": {"id": 10, "name": "CI"},
                    "status": "completed",
                    "result": "succeeded",
                    "start_time": "2026-03-01T10:00:00Z",
                    "finish_time": "2026-03-01T10:05:00Z",
                    "source_branch": "refs/heads/main",
                    "source_version": "abc123",
                    "requested_for": "user",
                }
            ],
        ):
            result = await query_builds(mock_client, "MyProject", days=30)

        assert len(result) == 1
        assert result[0]["build_id"] == 1
        assert result[0]["definition_name"] == "CI"
        assert result[0]["duration_minutes"] == 5.0

    @pytest.mark.asyncio
    async def test_query_builds_no_duration_when_missing_times(self):
        """Test duration is None when start/finish times are missing."""
        mock_client = AsyncMock()
        mock_client.get_builds.return_value = {"value": []}

        with patch(
            "execution.collectors.ado_deployment_metrics.BuildTransformer.transform_builds_response",
            return_value=[
                {
                    "id": 2,
                    "build_number": "1",
                    "definition": {"id": 1, "name": "P"},
                    "status": "completed",
                    "result": "succeeded",
                    "start_time": None,
                    "finish_time": None,
                    "source_branch": "main",
                    "source_version": "abc",
                    "requested_for": "u",
                }
            ],
        ):
            result = await query_builds(mock_client, "Proj")

        assert result[0]["duration_minutes"] is None

    @pytest.mark.asyncio
    async def test_query_builds_returns_empty_on_exception(self):
        """Test that exceptions return empty list."""
        mock_client = AsyncMock()
        mock_client.get_builds.side_effect = RuntimeError("API error")

        result = await query_builds(mock_client, "Proj")

        assert result == []


# ---------------------------------------------------------------------------
# Tests: calculate_deployment_frequency
# ---------------------------------------------------------------------------


class TestCalculateDeploymentFrequency:
    """Test deployment frequency calculation."""

    def test_counts_successful_builds(self, sample_builds):
        """Test frequency counts only succeeded builds."""
        result = calculate_deployment_frequency(sample_builds, lookback_days=90)

        assert result["total_successful_builds"] == 2
        assert result["lookback_days"] == 90
        assert result["pipeline_count"] == 2
        assert result["by_pipeline"]["CI-Pipeline"] == 1
        assert result["by_pipeline"]["Deploy-Pipeline"] == 1

    def test_deployments_per_week(self, sample_builds):
        """Test weekly deployment rate calculation."""
        result = calculate_deployment_frequency(sample_builds, lookback_days=14)

        expected_rate = round(2 / 2, 2)  # 2 successful / 2 weeks
        assert result["deployments_per_week"] == expected_rate

    def test_empty_builds(self):
        """Test with no builds."""
        result = calculate_deployment_frequency([], lookback_days=90)

        assert result["total_successful_builds"] == 0
        assert result["deployments_per_week"] == 0
        assert result["pipeline_count"] == 0


# ---------------------------------------------------------------------------
# Tests: calculate_build_success_rate
# ---------------------------------------------------------------------------


class TestCalculateBuildSuccessRate:
    """Test build success rate calculation."""

    def test_success_rate_calculation(self, sample_builds):
        """Test overall success rate percentage."""
        result = calculate_build_success_rate(sample_builds)

        assert result["total_builds"] == 4
        assert result["succeeded"] == 2
        assert result["failed"] == 1
        assert result["canceled"] == 1
        assert result["success_rate_pct"] == 50.0

    def test_by_pipeline_breakdown(self, sample_builds):
        """Test per-pipeline result breakdown."""
        result = calculate_build_success_rate(sample_builds)

        assert "CI-Pipeline" in result["by_pipeline"]
        assert result["by_pipeline"]["CI-Pipeline"]["succeeded"] == 1
        assert result["by_pipeline"]["CI-Pipeline"]["failed"] == 1

    def test_empty_builds(self):
        """Test with no builds returns zero rate."""
        result = calculate_build_success_rate([])

        assert result["total_builds"] == 0
        assert result["success_rate_pct"] == 0


# ---------------------------------------------------------------------------
# Tests: calculate_build_duration
# ---------------------------------------------------------------------------


class TestCalculateBuildDuration:
    """Test build duration statistics."""

    def test_duration_statistics(self, sample_builds):
        """Test median, min, max calculation."""
        result = calculate_build_duration(sample_builds)

        assert result["sample_size"] == 4
        # durations: 5.0, 3.0, 10.0, 1.0 → median = 4.0
        assert result["median_minutes"] == 4.0
        assert result["min_minutes"] == 1.0
        assert result["max_minutes"] == 10.0

    def test_no_duration_data(self):
        """Test with builds missing duration."""
        builds = [{"duration_minutes": None, "definition_name": "P"}]
        result = calculate_build_duration(builds)

        assert result["sample_size"] == 0
        assert result["median_minutes"] is None

    def test_by_pipeline_stats(self, sample_builds):
        """Test per-pipeline duration stats."""
        result = calculate_build_duration(sample_builds)

        assert "CI-Pipeline" in result["by_pipeline"]
        assert result["by_pipeline"]["CI-Pipeline"]["count"] == 3


# ---------------------------------------------------------------------------
# Tests: _calculate_single_build_lead_time
# ---------------------------------------------------------------------------


class TestCalculateSingleBuildLeadTime:
    """Test single build lead time calculation."""

    def test_positive_lead_time(self):
        """Test lead time when build finishes after commit."""
        commit_time = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)
        build = {"finish_time": "2026-03-01T12:00:00Z", "build_id": 1}

        with patch(
            "execution.collectors.ado_deployment_metrics.parse_ado_timestamp",
            return_value=datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC),
        ):
            result = _calculate_single_build_lead_time(commit_time, build)

        assert result == 2.0

    def test_negative_lead_time_returns_none(self):
        """Test that negative lead time returns None."""
        commit_time = datetime(2026, 3, 1, 14, 0, 0, tzinfo=UTC)
        build = {"finish_time": "2026-03-01T12:00:00Z", "build_id": 1}

        with patch(
            "execution.collectors.ado_deployment_metrics.parse_ado_timestamp",
            return_value=datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC),
        ):
            result = _calculate_single_build_lead_time(commit_time, build)

        assert result is None

    def test_none_finish_time_returns_none(self):
        """Test that missing finish time returns None."""
        commit_time = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)
        build = {"finish_time": None, "build_id": 1}

        with patch(
            "execution.collectors.ado_deployment_metrics.parse_ado_timestamp",
            return_value=None,
        ):
            result = _calculate_single_build_lead_time(commit_time, build)

        assert result is None


# ---------------------------------------------------------------------------
# Tests: calculate_lead_time_for_changes
# ---------------------------------------------------------------------------


class TestCalculateLeadTimeForChanges:
    """Test lead time for changes calculation."""

    @pytest.mark.asyncio
    async def test_lead_time_with_valid_data(self):
        """Test lead time calculation with valid commit timestamps."""
        mock_client = AsyncMock()
        builds = [
            {
                "build_id": 1,
                "result": "succeeded",
                "finish_time": "2026-03-01T12:00:00Z",
                "source_version": "abc",
            }
        ]
        commit_dt = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)

        with (
            patch(
                "execution.collectors.ado_deployment_metrics._get_commit_timestamp_from_build",
                return_value=commit_dt,
            ),
            patch(
                "execution.collectors.ado_deployment_metrics._calculate_single_build_lead_time",
                return_value=2.0,
            ),
        ):
            result = await calculate_lead_time_for_changes(mock_client, "Proj", builds)

        assert result["sample_size"] == 1
        assert result["median_hours"] == 2.0

    @pytest.mark.asyncio
    async def test_lead_time_no_commit_timestamps(self):
        """Test lead time returns empty when no commit timestamps found."""
        mock_client = AsyncMock()
        builds = [
            {
                "build_id": 1,
                "result": "succeeded",
                "finish_time": "2026-03-01T12:00:00Z",
                "source_version": "abc",
            }
        ]

        with patch(
            "execution.collectors.ado_deployment_metrics._get_commit_timestamp_from_build",
            return_value=None,
        ):
            result = await calculate_lead_time_for_changes(mock_client, "Proj", builds)

        assert result["sample_size"] == 0
        assert result["median_hours"] is None


# ---------------------------------------------------------------------------
# Tests: _strip_pipeline_names_for_history
# ---------------------------------------------------------------------------


class TestStripPipelineNamesForHistory:
    """Test pipeline detail stripping for history persistence."""

    def test_strips_by_pipeline_fields(self):
        """Test that by_pipeline dicts are removed."""
        project = {
            "project_key": "TP",
            "deployment_frequency": {"total_successful_builds": 5, "by_pipeline": {"CI": 5}},
            "build_success_rate": {"total_builds": 10, "by_pipeline": {"CI": {"succeeded": 8}}},
            "build_duration": {"sample_size": 10, "by_pipeline": {"CI": {"count": 10}}},
        }

        result = _strip_pipeline_names_for_history(project)

        assert "by_pipeline" not in result["deployment_frequency"]
        assert "by_pipeline" not in result["build_success_rate"]
        assert "by_pipeline" not in result["build_duration"]

    def test_does_not_modify_original(self):
        """Test that original dict is not mutated."""
        project = {
            "deployment_frequency": {"by_pipeline": {"CI": 5}},
            "build_success_rate": {},
            "build_duration": {},
        }

        _strip_pipeline_names_for_history(project)

        assert "by_pipeline" in project["deployment_frequency"]

    def test_handles_missing_sections(self):
        """Test stripping when sections are missing."""
        project = {"project_key": "TP"}

        result = _strip_pipeline_names_for_history(project)

        assert result["project_key"] == "TP"


# ---------------------------------------------------------------------------
# Tests: _validate_deployment_data
# ---------------------------------------------------------------------------


class TestValidateDeploymentData:
    """Test deployment data validation."""

    def test_valid_data(self, sample_week_metrics):
        """Test validation passes with valid data."""
        assert _validate_deployment_data(sample_week_metrics) is True

    def test_empty_projects(self):
        """Test validation fails with no projects."""
        assert _validate_deployment_data({"projects": []}) is False

    def test_all_zero_data(self):
        """Test validation fails when all projects have zero data."""
        metrics = {
            "projects": [
                {
                    "deployment_frequency": {"total_successful_builds": 0},
                    "build_success_rate": {"total_builds": 0},
                }
            ]
        }
        assert _validate_deployment_data(metrics) is False


# ---------------------------------------------------------------------------
# Tests: save_deployment_metrics
# ---------------------------------------------------------------------------


class TestSaveDeploymentMetrics:
    """Test saving deployment metrics to history."""

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_success(self, mock_makedirs, mock_load, mock_save, sample_week_metrics, tmp_path):
        """Test successful save appends to history."""
        mock_load.return_value = {"weeks": []}
        output_file = str(tmp_path / "deployment_history.json")

        result = save_deployment_metrics(sample_week_metrics, output_file)

        assert result is True
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["weeks"]) == 1
        # Verify pipeline details stripped
        proj = saved_data["weeks"][0]["projects"][0]
        assert "by_pipeline" not in proj["deployment_frequency"]

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_limits_to_52_weeks(self, mock_makedirs, mock_load, mock_save, sample_week_metrics, tmp_path):
        """Test history is capped at 52 weeks."""
        mock_load.return_value = {"weeks": [{"week": i} for i in range(52)]}
        output_file = str(tmp_path / "deployment_history.json")

        save_deployment_metrics(sample_week_metrics, output_file)

        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["weeks"]) == 52

    def test_save_skips_invalid_data(self):
        """Test save returns False for invalid data."""
        result = save_deployment_metrics({"projects": []})
        assert result is False

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_handles_os_error(self, mock_makedirs, mock_load, mock_save, sample_week_metrics, tmp_path):
        """Test save returns False on OSError."""
        mock_load.return_value = {"weeks": []}
        mock_save.side_effect = OSError("Disk full")
        output_file = str(tmp_path / "deployment_history.json")

        result = save_deployment_metrics(sample_week_metrics, output_file)

        assert result is False


# ---------------------------------------------------------------------------
# Tests: collect_deployment_metrics_for_project
# ---------------------------------------------------------------------------


class TestCollectDeploymentMetricsForProject:
    """Test per-project metric collection."""

    @pytest.mark.asyncio
    async def test_returns_empty_metrics_when_no_builds(self, sample_project):
        """Test that empty builds produce zero-value metrics."""
        mock_client = AsyncMock()

        with patch(
            "execution.collectors.ado_deployment_metrics.query_builds",
            return_value=[],
        ):
            result = await collect_deployment_metrics_for_project(mock_client, sample_project, {"lookback_days": 90})

        assert result["deployment_frequency"]["total_successful_builds"] == 0
        assert result["build_success_rate"]["total_builds"] == 0

    @pytest.mark.asyncio
    async def test_collects_all_metrics(self, sample_project, sample_builds):
        """Test full metric collection when builds exist."""
        mock_client = AsyncMock()

        with (
            patch(
                "execution.collectors.ado_deployment_metrics.query_builds",
                return_value=sample_builds,
            ),
            patch(
                "execution.collectors.ado_deployment_metrics.calculate_lead_time_for_changes",
                return_value={"sample_size": 1, "median_hours": 2.0, "p85_hours": 3.0, "p95_hours": 4.0},
            ),
        ):
            result = await collect_deployment_metrics_for_project(mock_client, sample_project, {"lookback_days": 90})

        assert result["project_key"] == "TP"
        assert result["deployment_frequency"]["total_successful_builds"] == 2
        assert result["build_success_rate"]["total_builds"] == 4
        assert result["build_duration"]["sample_size"] == 4
        assert result["lead_time_for_changes"]["median_hours"] == 2.0


# ---------------------------------------------------------------------------
# Tests: DeploymentCollector.run
# ---------------------------------------------------------------------------


class TestDeploymentCollectorRun:
    """Test DeploymentCollector orchestration."""

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_deployment_metrics.save_deployment_metrics", return_value=True)
    @patch("execution.collectors.ado_deployment_metrics.collect_deployment_metrics_for_project")
    @patch("execution.collectors.ado_deployment_metrics.track_collector_performance")
    def test_run_success(self, mock_tracker, mock_collect, mock_save):
        """Test successful collector run."""
        # Setup tracker context manager
        mock_ctx = MagicMock()
        mock_tracker.return_value.__enter__ = Mock(return_value=mock_ctx)
        mock_tracker.return_value.__exit__ = Mock(return_value=None)

        mock_collect.return_value = {
            "project_key": "TP",
            "project_name": "TestProject",
            "deployment_frequency": {"total_successful_builds": 5},
            "build_success_rate": {"total_builds": 10},
        }

        collector = DeploymentCollector()

        with (
            patch.object(
                collector._base,
                "load_discovery_data",
                return_value={"projects": [{"project_name": "TestProject", "project_key": "TP"}]},
            ),
            patch.object(collector._base, "get_rest_client", return_value=AsyncMock()),
            patch("logging.basicConfig"),
        ):
            import asyncio

            result = asyncio.get_event_loop().run_until_complete(collector.run())

        assert result is True

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_deployment_metrics.track_collector_performance")
    def test_run_no_projects(self, mock_tracker):
        """Test run returns False with no projects."""
        mock_ctx = MagicMock()
        mock_tracker.return_value.__enter__ = Mock(return_value=mock_ctx)
        mock_tracker.return_value.__exit__ = Mock(return_value=None)

        collector = DeploymentCollector()

        with (
            patch.object(collector._base, "load_discovery_data", return_value={"projects": []}),
            patch("logging.basicConfig"),
        ):
            import asyncio

            result = asyncio.get_event_loop().run_until_complete(collector.run())

        assert result is False
