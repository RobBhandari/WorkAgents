#!/usr/bin/env python3
"""
Tests for ADO Quality Metrics Collector

Verifies quality metrics collection:
- Area path filter clause building
- Bug detail fetching with batch utility
- Bug age distribution calculation
- MTTR calculation
- Test execution time calculation
- Metrics save with validation
- QualityCollector.run orchestration
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from execution.collectors.ado_quality_metrics import (
    QualityCollector,
    _build_ages_distribution,
    _build_area_filter_clause,
    _collect_bug_ages,
    _fetch_bug_details,
    _parse_repair_times,
    _unpack_bug_gather_results,
    calculate_bug_age_distribution,
    calculate_mttr,
    calculate_test_execution_time,
    save_quality_metrics,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_open_bugs() -> list[dict]:
    """Sample open bugs with varying ages."""
    now = datetime.now(UTC)
    return [
        {"System.Id": 1, "System.CreatedDate": (now - timedelta(days=3)).isoformat()},
        {"System.Id": 2, "System.CreatedDate": (now - timedelta(days=15)).isoformat()},
        {"System.Id": 3, "System.CreatedDate": (now - timedelta(days=60)).isoformat()},
        {"System.Id": 4, "System.CreatedDate": (now - timedelta(days=120)).isoformat()},
    ]


@pytest.fixture
def sample_all_bugs() -> list[dict]:
    """Sample bugs with created and closed dates for MTTR."""
    now = datetime.now(UTC)
    return [
        {
            "System.Id": 10,
            "System.CreatedDate": (now - timedelta(days=10)).isoformat(),
            "Microsoft.VSTS.Common.ClosedDate": (now - timedelta(days=5)).isoformat(),
        },
        {
            "System.Id": 11,
            "System.CreatedDate": (now - timedelta(days=20)).isoformat(),
            "Microsoft.VSTS.Common.ClosedDate": (now - timedelta(days=18)).isoformat(),
        },
        {
            "System.Id": 12,
            "System.CreatedDate": (now - timedelta(days=30)).isoformat(),
            # Not closed yet — no ClosedDate
        },
    ]


@pytest.fixture
def sample_discovery_data() -> dict:
    """Sample discovery data for collector run."""
    return {
        "projects": [
            {
                "project_name": "ProjectAlpha",
                "project_key": "PA",
                "ado_project_name": "ProjectAlpha",
            },
        ]
    }


@pytest.fixture
def sample_project_metrics() -> list[dict]:
    """Sample project metrics for save_quality_metrics."""
    return [
        {
            "project_key": "PA",
            "project_name": "ProjectAlpha",
            "total_bugs_analyzed": 10,
            "open_bugs_count": 3,
            "excluded_security_bugs": {"total": 1, "open": 0},
            "mttr": {"mttr_days": 5.0},
            "bug_age_distribution": {"median_age_days": 12.0},
            "test_execution_time": {"median_minutes": 4.2},
        }
    ]


# ---------------------------------------------------------------------------
# Tests: _build_area_filter_clause
# ---------------------------------------------------------------------------


class TestBuildAreaFilterClause:
    """Test WIQL area path filter clause building."""

    def test_none_returns_empty(self):
        assert _build_area_filter_clause(None) == ""

    def test_empty_string_returns_empty(self):
        assert _build_area_filter_clause("") == ""

    @patch("execution.collectors.ado_quality_metrics.WIQLValidator")
    def test_exclude_prefix(self, mock_validator):
        mock_validator.validate_area_path.return_value = "Project\\Security"
        result = _build_area_filter_clause("EXCLUDE:Project\\Security")
        assert "NOT UNDER" in result
        assert "'Project\\Security'" in result
        mock_validator.validate_area_path.assert_called_once_with("Project\\Security")

    @patch("execution.collectors.ado_quality_metrics.WIQLValidator")
    def test_include_prefix(self, mock_validator):
        mock_validator.validate_area_path.return_value = "Project\\Dev"
        result = _build_area_filter_clause("INCLUDE:Project\\Dev")
        assert "UNDER" in result
        assert "NOT UNDER" not in result
        assert "'Project\\Dev'" in result

    def test_invalid_prefix_returns_empty(self):
        result = _build_area_filter_clause("SOMETHING:Path")
        assert result == ""


# ---------------------------------------------------------------------------
# Tests: _fetch_bug_details
# ---------------------------------------------------------------------------


class TestFetchBugDetails:
    """Test bug detail fetching via REST batch utility."""

    @pytest.mark.asyncio
    async def test_empty_ids_returns_empty(self):
        mock_client = Mock()
        result = await _fetch_bug_details(mock_client, [], ["System.Id"])
        assert result == []

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_quality_metrics.batch_fetch_work_items_rest", new_callable=AsyncMock)
    @patch("execution.collectors.ado_quality_metrics.WorkItemTransformer")
    async def test_successful_fetch(self, mock_transformer, mock_batch):
        mock_batch.return_value = ([{"id": 1, "fields": {}}], [])
        mock_transformer.transform_work_items_response.return_value = [{"System.Id": 1}]

        mock_client = Mock()
        result = await _fetch_bug_details(mock_client, [1], ["System.Id"])

        assert len(result) == 1
        mock_batch.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_quality_metrics.batch_fetch_work_items_rest", new_callable=AsyncMock)
    async def test_fetch_raises_on_total_failure(self, mock_batch):
        mock_batch.side_effect = Exception("All batches failed")
        mock_client = Mock()

        with pytest.raises(Exception, match="All batches failed"):
            await _fetch_bug_details(mock_client, [1, 2], ["System.Id"])

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_quality_metrics.batch_fetch_work_items_rest", new_callable=AsyncMock)
    @patch("execution.collectors.ado_quality_metrics.WorkItemTransformer")
    async def test_partial_failure_logs_warning(self, mock_transformer, mock_batch):
        mock_batch.return_value = ([{"id": 1, "fields": {}}], [2])
        mock_transformer.transform_work_items_response.return_value = [{"System.Id": 1}]

        mock_client = Mock()
        result = await _fetch_bug_details(mock_client, [1, 2], ["System.Id"])

        assert len(result) == 1


# ---------------------------------------------------------------------------
# Tests: _build_ages_distribution
# ---------------------------------------------------------------------------


class TestBuildAgesDistribution:
    """Test age bucket distribution calculation."""

    def test_all_buckets(self):
        ages = [3.0, 10.0, 50.0, 100.0]
        dist = _build_ages_distribution(ages)
        assert dist == {"0-7_days": 1, "8-30_days": 1, "31-90_days": 1, "90+_days": 1}

    def test_empty_ages(self):
        dist = _build_ages_distribution([])
        assert dist == {"0-7_days": 0, "8-30_days": 0, "31-90_days": 0, "90+_days": 0}

    def test_boundary_values(self):
        ages = [7.0, 7.1, 30.0, 30.1, 90.0, 90.1]
        dist = _build_ages_distribution(ages)
        assert dist["0-7_days"] == 1  # 7.0
        assert dist["8-30_days"] == 2  # 7.1, 30.0
        assert dist["31-90_days"] == 2  # 30.1, 90.0
        assert dist["90+_days"] == 1  # 90.1


# ---------------------------------------------------------------------------
# Tests: calculate_bug_age_distribution
# ---------------------------------------------------------------------------


class TestCalculateBugAgeDistribution:
    """Test bug age distribution calculation."""

    def test_with_valid_bugs(self, sample_open_bugs):
        result = calculate_bug_age_distribution(sample_open_bugs)
        assert result["sample_size"] == 4
        assert result["median_age_days"] is not None
        assert result["p85_age_days"] is not None
        assert result["p95_age_days"] is not None
        assert sum(result["ages_distribution"].values()) == 4

    def test_empty_bugs(self):
        result = calculate_bug_age_distribution([])
        assert result["sample_size"] == 0
        assert result["median_age_days"] is None

    def test_unparseable_dates(self):
        bugs = [{"System.Id": 99, "System.CreatedDate": "not-a-date"}]
        result = calculate_bug_age_distribution(bugs)
        assert result["sample_size"] == 0


# ---------------------------------------------------------------------------
# Tests: _parse_repair_times and calculate_mttr
# ---------------------------------------------------------------------------


class TestCalculateMttr:
    """Test MTTR (Mean Time To Repair) calculation."""

    def test_with_closed_bugs(self, sample_all_bugs):
        result = calculate_mttr(sample_all_bugs)
        # 2 out of 3 bugs have closed dates
        assert result["sample_size"] == 2
        assert result["mttr_days"] is not None
        assert result["mttr_days"] > 0

    def test_no_closed_bugs(self):
        bugs = [{"System.Id": 1, "System.CreatedDate": "2025-01-01T00:00:00Z"}]
        result = calculate_mttr(bugs)
        assert result["sample_size"] == 0
        assert result["mttr_days"] is None
        assert result["mttr_distribution"] == {"0-1_days": 0, "1-7_days": 0, "7-30_days": 0, "30+_days": 0}

    def test_empty_bugs(self):
        result = calculate_mttr([])
        assert result["sample_size"] == 0

    def test_mttr_distribution_buckets(self):
        now = datetime.now(UTC)
        bugs = [
            {
                "System.CreatedDate": (now - timedelta(hours=12)).isoformat(),
                "Microsoft.VSTS.Common.ClosedDate": now.isoformat(),
            },
            {
                "System.CreatedDate": (now - timedelta(days=3)).isoformat(),
                "Microsoft.VSTS.Common.ClosedDate": now.isoformat(),
            },
            {
                "System.CreatedDate": (now - timedelta(days=15)).isoformat(),
                "Microsoft.VSTS.Common.ClosedDate": now.isoformat(),
            },
            {
                "System.CreatedDate": (now - timedelta(days=45)).isoformat(),
                "Microsoft.VSTS.Common.ClosedDate": now.isoformat(),
            },
        ]
        result = calculate_mttr(bugs)
        assert result["sample_size"] == 4
        assert result["mttr_distribution"]["0-1_days"] == 1
        assert result["mttr_distribution"]["1-7_days"] == 1
        assert result["mttr_distribution"]["7-30_days"] == 1
        assert result["mttr_distribution"]["30+_days"] == 1


# ---------------------------------------------------------------------------
# Tests: calculate_test_execution_time
# ---------------------------------------------------------------------------


class TestCalculateTestExecutionTime:
    """Test test execution time calculation."""

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_quality_metrics.TestTransformer")
    async def test_with_valid_runs(self, mock_transformer):
        mock_client = AsyncMock()
        mock_client.get_test_runs = AsyncMock(return_value={"value": []})

        mock_transformer.transform_test_runs_response.return_value = [
            {"started_date": "2025-06-01T10:00:00Z", "completed_date": "2025-06-01T10:05:00Z"},
            {"started_date": "2025-06-01T11:00:00Z", "completed_date": "2025-06-01T11:10:00Z"},
        ]

        result = await calculate_test_execution_time(mock_client, "TestProject")
        assert result["sample_size"] == 2
        assert result["median_minutes"] is not None

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_quality_metrics.TestTransformer")
    async def test_no_test_runs(self, mock_transformer):
        mock_client = AsyncMock()
        mock_client.get_test_runs = AsyncMock(return_value={"value": []})
        mock_transformer.transform_test_runs_response.return_value = []

        result = await calculate_test_execution_time(mock_client, "TestProject")
        assert result["sample_size"] == 0
        assert result["median_minutes"] is None

    @pytest.mark.asyncio
    async def test_api_error_returns_default(self):
        mock_client = AsyncMock()
        mock_client.get_test_runs = AsyncMock(side_effect=Exception("API error"))

        result = await calculate_test_execution_time(mock_client, "TestProject")
        assert result["sample_size"] == 0
        assert result["median_minutes"] is None


# ---------------------------------------------------------------------------
# Tests: _unpack_bug_gather_results
# ---------------------------------------------------------------------------


class TestUnpackBugGatherResults:
    """Test unpacking of asyncio.gather results."""

    def test_both_tasks_success(self):
        results = [["bug1"], ["bug2"]]
        all_bugs, open_bugs = _unpack_bug_gather_results(results, True, True)
        assert all_bugs == ["bug1"]
        assert open_bugs == ["bug2"]

    def test_all_bugs_only(self):
        results = [["bug1"]]
        all_bugs, open_bugs = _unpack_bug_gather_results(results, True, False)
        assert all_bugs == ["bug1"]
        assert open_bugs == []

    def test_open_bugs_only(self):
        results = [["bug2"]]
        all_bugs, open_bugs = _unpack_bug_gather_results(results, False, True)
        assert all_bugs == []
        assert open_bugs == ["bug2"]

    def test_exception_in_all_bugs(self):
        results = [ValueError("fail"), ["bug2"]]
        all_bugs, open_bugs = _unpack_bug_gather_results(results, True, True)
        assert all_bugs == []
        assert open_bugs == ["bug2"]


# ---------------------------------------------------------------------------
# Tests: save_quality_metrics
# ---------------------------------------------------------------------------


class TestSaveQualityMetrics:
    """Test metrics persistence with validation."""

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_success(self, mock_makedirs, mock_load, mock_save, sample_project_metrics):
        mock_load.return_value = {"weeks": []}
        metrics = {"projects": sample_project_metrics}

        result = save_quality_metrics(metrics, ".tmp/observatory/quality_history.json")

        assert result is True
        mock_save.assert_called_once()

    def test_save_empty_projects(self):
        metrics: dict = {"projects": []}
        result = save_quality_metrics(metrics)
        assert result is False

    def test_save_all_zero_bugs(self):
        metrics = {
            "projects": [
                {"total_bugs_analyzed": 0, "open_bugs_count": 0},
            ]
        }
        result = save_quality_metrics(metrics)
        assert result is False

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_trims_to_52_weeks(self, mock_makedirs, mock_load, mock_save, sample_project_metrics):
        existing_weeks = [{"week_date": f"2025-01-{i:02d}"} for i in range(1, 53)]
        mock_load.return_value = {"weeks": existing_weeks}
        metrics = {"projects": sample_project_metrics}

        save_quality_metrics(metrics, ".tmp/observatory/quality_history.json")

        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["weeks"]) == 52

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_invalid_history_structure(self, mock_makedirs, mock_load, mock_save, sample_project_metrics):
        mock_load.return_value = "not a dict"
        metrics = {"projects": sample_project_metrics}

        result = save_quality_metrics(metrics, ".tmp/observatory/quality_history.json")

        assert result is True
        saved_data = mock_save.call_args[0][0]
        assert "weeks" in saved_data

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_os_error(self, mock_makedirs, mock_load, mock_save, sample_project_metrics):
        mock_load.return_value = {"weeks": []}
        mock_save.side_effect = OSError("Disk full")
        metrics = {"projects": sample_project_metrics}

        result = save_quality_metrics(metrics, ".tmp/observatory/quality_history.json")

        assert result is False


# ---------------------------------------------------------------------------
# Tests: QualityCollector.run
# ---------------------------------------------------------------------------


class TestQualityCollectorRun:
    """Test main collector orchestration."""

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_quality_metrics.save_quality_metrics", return_value=True)
    @patch("execution.collectors.ado_quality_metrics.collect_quality_metrics_for_project", new_callable=AsyncMock)
    @patch("execution.core.collector_metrics.track_collector_performance")
    async def test_run_success(self, mock_tracker, mock_collect, mock_save, sample_discovery_data):
        mock_tracker_ctx = MagicMock()
        mock_tracker_ctx.__enter__ = Mock(return_value=mock_tracker_ctx)
        mock_tracker_ctx.__exit__ = Mock(return_value=None)
        mock_tracker.return_value = mock_tracker_ctx

        mock_collect.return_value = {
            "project_key": "PA",
            "project_name": "ProjectAlpha",
            "total_bugs_analyzed": 10,
            "open_bugs_count": 3,
            "excluded_security_bugs": {"total": 0, "open": 0},
            "mttr": {"mttr_days": 5.0},
            "bug_age_distribution": {},
            "test_execution_time": {},
        }

        collector = QualityCollector()
        with patch.object(collector._base, "load_discovery_data", return_value=sample_discovery_data):
            with patch.object(collector._base, "get_rest_client", return_value=Mock()):
                result = await collector.run()

        assert result is True
        mock_save.assert_called_once()

    @pytest.mark.asyncio
    @patch("execution.core.collector_metrics.track_collector_performance")
    async def test_run_no_projects(self, mock_tracker):
        mock_tracker_ctx = MagicMock()
        mock_tracker_ctx.__enter__ = Mock(return_value=mock_tracker_ctx)
        mock_tracker_ctx.__exit__ = Mock(return_value=None)
        mock_tracker.return_value = mock_tracker_ctx

        collector = QualityCollector()
        with patch.object(collector._base, "load_discovery_data", return_value={"projects": []}):
            result = await collector.run()

        assert result is False
