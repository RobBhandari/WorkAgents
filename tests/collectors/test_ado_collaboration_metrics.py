#!/usr/bin/env python3
"""
Tests for ADO Collaboration Metrics Collector

Verifies:
- PR sampling logic
- PR query with REST client mocking
- Pure calculation functions (review time, merge time, iterations, PR size)
- History save logic with validation
- Collector class orchestration
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from execution.collectors.ado_collaboration_metrics import (
    CollaborationCollector,
    calculate_pr_merge_time,
    calculate_pr_review_time,
    calculate_pr_size_loc,
    calculate_review_iteration_count,
    calculate_single_pr_review_time,
    collect_collaboration_metrics_for_project,
    get_first_comment_time,
    query_pull_requests,
    sample_prs,
    save_collaboration_metrics,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_prs_list() -> list[dict]:
    """Sample list of PR dicts for testing."""
    now = datetime.now(UTC)
    return [
        {
            "pr_id": i,
            "title": f"PR {i}",
            "created_date": (now - timedelta(days=i)).isoformat(),
            "closed_date": (now - timedelta(days=i) + timedelta(hours=i + 1)).isoformat(),
            "created_by": f"dev{i}",
            "repository_id": "repo-1",
        }
        for i in range(1, 21)
    ]


@pytest.fixture
def sample_threads() -> list[dict]:
    """Sample PR threads with comments."""
    now = datetime.now(UTC)
    earlier = now - timedelta(hours=2)
    later = now + timedelta(hours=1)
    return [
        {"comments": [{"published_date": now.isoformat()}, {"published_date": later.isoformat()}]},
        {"comments": [{"published_date": earlier.isoformat()}]},
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
def sample_rest_client() -> AsyncMock:
    """Mock REST client with standard responses."""
    client = AsyncMock()
    client.get_pull_requests = AsyncMock(return_value={"value": []})
    client.get_repositories = AsyncMock(return_value={"value": []})
    client.get_pull_request_threads = AsyncMock(return_value={"value": []})
    client.get_pull_request_iterations = AsyncMock(return_value={"value": []})
    client.get_pull_request_commits = AsyncMock(return_value={"value": []})
    return client


# ---------------------------------------------------------------------------
# Test: sample_prs
# ---------------------------------------------------------------------------


class TestSamplePrs:
    """Test PR sampling logic."""

    def test_sample_normal_size(self):
        """Sample from list larger than sample_size returns sample_size items."""
        prs = [{"pr_id": i} for i in range(50)]
        result = sample_prs(prs, sample_size=10)
        assert len(result) == 10
        assert all(pr in prs for pr in result)

    def test_sample_smaller_than_size(self):
        """Sample from list smaller than sample_size returns all items."""
        prs = [{"pr_id": i} for i in range(3)]
        result = sample_prs(prs, sample_size=10)
        assert len(result) == 3

    def test_sample_exact_size(self):
        """Sample from list equal to sample_size returns all items."""
        prs = [{"pr_id": i} for i in range(10)]
        result = sample_prs(prs, sample_size=10)
        assert len(result) == 10

    def test_sample_empty_list(self):
        """Sample from empty list returns empty list."""
        result = sample_prs([], sample_size=10)
        assert result == []

    def test_sample_single_item(self):
        """Sample from single-item list returns that item."""
        prs = [{"pr_id": 1}]
        result = sample_prs(prs, sample_size=10)
        assert result == prs


# ---------------------------------------------------------------------------
# Test: get_first_comment_time
# ---------------------------------------------------------------------------


class TestGetFirstCommentTime:
    """Test first comment time extraction."""

    def test_returns_earliest_comment(self, sample_threads):
        """Should return the earliest comment timestamp across all threads."""
        result = get_first_comment_time(sample_threads)
        assert result is not None
        # The earliest is 2 hours ago
        now = datetime.now(UTC)
        assert abs((result - (now - timedelta(hours=2))).total_seconds()) < 2

    def test_empty_threads(self):
        """Empty thread list returns None."""
        assert get_first_comment_time([]) is None

    def test_threads_with_no_comments(self):
        """Threads with empty comment lists return None."""
        threads: list = [{"comments": []}, {"comments": []}]
        assert get_first_comment_time(threads) is None

    def test_invalid_date_skipped(self):
        """Invalid date strings are skipped gracefully."""
        threads = [{"comments": [{"published_date": "not-a-date"}]}]
        assert get_first_comment_time(threads) is None

    def test_missing_published_date(self):
        """Comments without published_date are skipped."""
        threads = [{"comments": [{"author": "someone"}]}]
        assert get_first_comment_time(threads) is None


# ---------------------------------------------------------------------------
# Test: query_pull_requests
# ---------------------------------------------------------------------------


class TestQueryPullRequests:
    """Test PR querying with mocked REST client."""

    @pytest.mark.asyncio
    async def test_returns_prs(self, sample_rest_client):
        """Should return transformed PR data."""
        now = datetime.now(UTC)
        transformed = [
            {
                "pull_request_id": 1,
                "title": "Test PR",
                "creation_date": now.isoformat(),
                "closed_date": (now + timedelta(hours=2)).isoformat(),
                "created_by": "dev1",
            }
        ]

        with patch(
            "execution.collectors.ado_collaboration_metrics.GitTransformer.transform_pull_requests_response",
            return_value=transformed,
        ):
            result = await query_pull_requests(sample_rest_client, "Proj", "repo-1", days=90)

        assert len(result) == 1
        assert result[0]["pr_id"] == 1
        assert result[0]["repository_id"] == "repo-1"

    @pytest.mark.asyncio
    async def test_filters_old_prs(self, sample_rest_client):
        """PRs older than lookback period are filtered out."""
        old_date = (datetime.now(UTC) - timedelta(days=200)).isoformat()
        transformed = [
            {
                "pull_request_id": 1,
                "title": "Old PR",
                "creation_date": old_date,
                "closed_date": old_date,
                "created_by": "dev1",
            }
        ]

        with patch(
            "execution.collectors.ado_collaboration_metrics.GitTransformer.transform_pull_requests_response",
            return_value=transformed,
        ):
            result = await query_pull_requests(sample_rest_client, "Proj", "repo-1", days=90)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_api_error_returns_empty(self, sample_rest_client):
        """API errors return empty list."""
        sample_rest_client.get_pull_requests.side_effect = Exception("API down")
        result = await query_pull_requests(sample_rest_client, "Proj", "repo-1")
        assert result == []


# ---------------------------------------------------------------------------
# Test: calculate_pr_merge_time
# ---------------------------------------------------------------------------


class TestCalculatePrMergeTime:
    """Test PR merge time calculation (pure function)."""

    def test_valid_prs(self, sample_prs_list):
        """Should calculate merge time stats from valid PRs."""
        result = calculate_pr_merge_time(sample_prs_list)
        assert result["sample_size"] > 0
        assert result["median_hours"] is not None
        assert result["median_hours"] > 0

    def test_empty_prs(self):
        """Empty list yields zero sample_size and None stats."""
        result = calculate_pr_merge_time([])
        assert result["sample_size"] == 0
        assert result["median_hours"] is None

    def test_missing_dates_skipped(self):
        """PRs with missing dates are skipped."""
        prs = [{"pr_id": 1, "created_date": None, "closed_date": None}]
        result = calculate_pr_merge_time(prs)
        assert result["sample_size"] == 0

    def test_negative_merge_time_skipped(self):
        """PRs where closed < created are skipped (negative time)."""
        now = datetime.now(UTC)
        prs = [
            {
                "pr_id": 1,
                "created_date": now.isoformat(),
                "closed_date": (now - timedelta(hours=5)).isoformat(),
            }
        ]
        result = calculate_pr_merge_time(prs)
        assert result["sample_size"] == 0


# ---------------------------------------------------------------------------
# Test: calculate_pr_review_time (async, needs mocks)
# ---------------------------------------------------------------------------


class TestCalculatePrReviewTime:
    """Test PR review time aggregation."""

    @pytest.mark.asyncio
    async def test_no_valid_times_returns_empty(self, sample_rest_client):
        """When no review times can be calculated, returns empty stats."""
        prs = [{"pr_id": 1, "repository_id": "r1", "created_date": "bad"}]

        with patch("execution.collectors.ado_collaboration_metrics.sample_prs", return_value=prs):
            with patch(
                "execution.collectors.ado_collaboration_metrics.calculate_single_pr_review_time",
                return_value=None,
            ):
                result = await calculate_pr_review_time(sample_rest_client, "Proj", prs)

        assert result["sample_size"] == 0
        assert result["median_hours"] is None

    @pytest.mark.asyncio
    async def test_valid_review_times(self, sample_rest_client, sample_prs_list):
        """With valid review times, returns proper stats."""
        with patch(
            "execution.collectors.ado_collaboration_metrics.sample_prs",
            return_value=sample_prs_list[:3],
        ):
            with patch(
                "execution.collectors.ado_collaboration_metrics.calculate_single_pr_review_time",
                side_effect=[2.0, 4.0, 6.0],
            ):
                result = await calculate_pr_review_time(sample_rest_client, "Proj", sample_prs_list)

        assert result["sample_size"] == 3
        assert result["median_hours"] == 4.0


# ---------------------------------------------------------------------------
# Test: calculate_single_pr_review_time
# ---------------------------------------------------------------------------


class TestCalculateSinglePrReviewTime:
    """Test single PR review time calculation."""

    @pytest.mark.asyncio
    async def test_returns_hours(self, sample_rest_client):
        """Should return review hours when threads have comments."""
        now = datetime.now(UTC)
        pr = {
            "pr_id": 1,
            "repository_id": "r1",
            "created_date": (now - timedelta(hours=3)).isoformat(),
        }

        threads_response: dict = {"value": []}
        sample_rest_client.get_pull_request_threads.return_value = threads_response

        transformed_threads = [{"comments": [{"published_date": now.isoformat()}]}]

        with patch(
            "execution.collectors.ado_collaboration_metrics.GitTransformer.transform_threads_response",
            return_value=transformed_threads,
        ):
            result = await calculate_single_pr_review_time(sample_rest_client, "Proj", pr)

        assert result is not None
        assert abs(result - 3.0) < 0.1

    @pytest.mark.asyncio
    async def test_no_threads_returns_none(self, sample_rest_client):
        """No threads means no review time."""
        pr = {"pr_id": 1, "repository_id": "r1", "created_date": datetime.now(UTC).isoformat()}

        with patch(
            "execution.collectors.ado_collaboration_metrics.GitTransformer.transform_threads_response",
            return_value=[],
        ):
            result = await calculate_single_pr_review_time(sample_rest_client, "Proj", pr)

        assert result is None

    @pytest.mark.asyncio
    async def test_api_error_returns_none(self, sample_rest_client):
        """API error returns None gracefully."""
        sample_rest_client.get_pull_request_threads.side_effect = Exception("fail")
        pr = {"pr_id": 1, "repository_id": "r1", "created_date": datetime.now(UTC).isoformat()}
        result = await calculate_single_pr_review_time(sample_rest_client, "Proj", pr)
        assert result is None


# ---------------------------------------------------------------------------
# Test: calculate_review_iteration_count
# ---------------------------------------------------------------------------


class TestCalculateReviewIterationCount:
    """Test review iteration count calculation."""

    @pytest.mark.asyncio
    async def test_valid_iterations(self, sample_rest_client, sample_prs_list):
        """Should return iteration stats from API responses."""
        sample_rest_client.get_pull_request_iterations.return_value = {"value": [{"id": 1}, {"id": 2}, {"id": 3}]}

        with patch(
            "execution.collectors.ado_collaboration_metrics.sample_prs",
            return_value=sample_prs_list[:2],
        ):
            result = await calculate_review_iteration_count(sample_rest_client, "Proj", sample_prs_list)

        assert result["sample_size"] == 2
        assert result["median_iterations"] == 3.0
        assert result["max_iterations"] == 3

    @pytest.mark.asyncio
    async def test_empty_iterations(self, sample_rest_client, sample_prs_list):
        """Empty iteration responses yield zero sample_size."""
        sample_rest_client.get_pull_request_iterations.return_value = {"value": []}

        with patch(
            "execution.collectors.ado_collaboration_metrics.sample_prs",
            return_value=sample_prs_list[:2],
        ):
            result = await calculate_review_iteration_count(sample_rest_client, "Proj", sample_prs_list)

        assert result["sample_size"] == 0
        assert result["median_iterations"] is None


# ---------------------------------------------------------------------------
# Test: calculate_pr_size_loc
# ---------------------------------------------------------------------------


class TestCalculatePrSizeLoc:
    """Test PR size (commit count) calculation."""

    @pytest.mark.asyncio
    async def test_valid_commits(self, sample_rest_client, sample_prs_list):
        """Should return commit count stats."""
        sample_rest_client.get_pull_request_commits.return_value = {"value": [{"commitId": "a"}, {"commitId": "b"}]}

        with patch(
            "execution.collectors.ado_collaboration_metrics.sample_prs",
            return_value=sample_prs_list[:2],
        ):
            result = await calculate_pr_size_loc(sample_rest_client, "Proj", sample_prs_list)

        assert result["sample_size"] == 2
        assert result["median_commits"] == 2.0

    @pytest.mark.asyncio
    async def test_no_commits(self, sample_rest_client, sample_prs_list):
        """No commits yields zero sample_size."""
        sample_rest_client.get_pull_request_commits.return_value = {"value": []}

        with patch(
            "execution.collectors.ado_collaboration_metrics.sample_prs",
            return_value=sample_prs_list[:1],
        ):
            result = await calculate_pr_size_loc(sample_rest_client, "Proj", sample_prs_list)

        assert result["sample_size"] == 0
        assert result["median_commits"] is None


# ---------------------------------------------------------------------------
# Test: save_collaboration_metrics
# ---------------------------------------------------------------------------


class TestSaveCollaborationMetrics:
    """Test saving collaboration metrics to history file."""

    def test_save_valid_data(self, tmp_path):
        """Should save valid metrics and return True."""
        output_file = str(tmp_path / "collab_history.json")
        metrics = {
            "week_date": "2026-03-15",
            "projects": [{"project_key": "P1", "total_prs_analyzed": 10, "repository_count": 2}],
        }

        with patch(
            "execution.utils_atomic_json.load_json_with_recovery",
            return_value={"weeks": []},
        ):
            with patch("execution.utils_atomic_json.atomic_json_save") as mock_save:
                result = save_collaboration_metrics(metrics, output_file)

        assert result is True
        mock_save.assert_called_once()

    def test_skip_empty_projects(self):
        """Should skip saving when no projects present."""
        metrics: dict = {"projects": []}
        result = save_collaboration_metrics(metrics, "/tmp/test.json")
        assert result is False

    def test_skip_zero_data(self):
        """Should skip saving when all projects have zero data."""
        metrics = {
            "projects": [{"total_prs_analyzed": 0, "repository_count": 0}],
        }
        result = save_collaboration_metrics(metrics, "/tmp/test.json")
        assert result is False

    def test_save_trims_to_52_weeks(self, tmp_path):
        """History should be trimmed to 52 weeks max."""
        output_file = str(tmp_path / "collab_history.json")
        existing = {"weeks": [{"week": i} for i in range(55)]}
        metrics = {
            "projects": [{"project_key": "P1", "total_prs_analyzed": 5, "repository_count": 1}],
        }

        with patch(
            "execution.utils_atomic_json.load_json_with_recovery",
            return_value=existing,
        ):
            with patch("execution.utils_atomic_json.atomic_json_save") as mock_save:
                save_collaboration_metrics(metrics, output_file)

        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["weeks"]) == 52

    def test_save_os_error_returns_false(self, tmp_path):
        """OSError during save returns False."""
        output_file = str(tmp_path / "collab_history.json")
        metrics = {
            "projects": [{"project_key": "P1", "total_prs_analyzed": 5, "repository_count": 1}],
        }

        with patch(
            "execution.utils_atomic_json.load_json_with_recovery",
            return_value={"weeks": []},
        ):
            with patch(
                "execution.utils_atomic_json.atomic_json_save",
                side_effect=OSError("disk full"),
            ):
                result = save_collaboration_metrics(metrics, output_file)

        assert result is False


# ---------------------------------------------------------------------------
# Test: CollaborationCollector orchestration
# ---------------------------------------------------------------------------


class TestCollaborationCollector:
    """Test collector class orchestration."""

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_collaboration_metrics.save_collaboration_metrics", return_value=True)
    @patch("execution.collectors.ado_collaboration_metrics.collect_collaboration_metrics_for_project")
    @patch("execution.collectors.ado_collaboration_metrics.track_collector_performance")
    async def test_run_success(self, mock_tracker, mock_collect, mock_save):
        """Successful run collects and saves metrics."""
        # Setup tracker context manager
        tracker_inst = Mock()
        mock_tracker.return_value.__enter__ = Mock(return_value=tracker_inst)
        mock_tracker.return_value.__exit__ = Mock(return_value=None)

        mock_collect.return_value = {
            "project_key": "P1",
            "project_name": "Proj",
            "total_prs_analyzed": 10,
            "pr_review_time": {"median_hours": 2.0},
            "pr_merge_time": {"median_hours": 5.0},
            "review_iteration_count": {"median_iterations": 2.0},
            "pr_size": {"median_commits": 3.0},
        }

        discovery = {"projects": [{"project_name": "Proj", "project_key": "P1"}]}

        with patch.object(CollaborationCollector, "__init__", return_value=None):
            collector = CollaborationCollector.__new__(CollaborationCollector)
            collector._base = Mock()
            collector._base.load_discovery_data.return_value = discovery
            collector._base.get_rest_client.return_value = AsyncMock()
            collector.config = {"lookback_days": 90}

            result = await collector.run()

        assert result is True
        mock_save.assert_called_once()
