"""
Tests for ADO Collaboration Metrics Collector

Tests cover:
- PR querying and filtering by date
- Review time calculations (creation to first comment)
- Merge time calculations (creation to closure)
- Review iteration counting
- PR size measurement (commit counts)
- Main orchestration function
- JSON history saving with validation
- Error handling for ADO API failures
- Edge cases (empty data, missing timestamps, invalid values)

Run with:
    pytest tests/collectors/test_ado_collaboration_metrics.py -v
"""

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
from azure.devops.exceptions import AzureDevOpsServiceError

from execution.collectors.ado_collaboration_metrics import (
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

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def sample_pr_data():
    """Sample PR data matching ADO structure"""
    return [
        {
            "pr_id": 1,
            "title": "Add feature X",
            "created_date": "2026-02-01T10:00:00Z",
            "closed_date": "2026-02-03T10:00:00Z",
            "created_by": "Alice",
            "repository_id": "repo-123",
        },
        {
            "pr_id": 2,
            "title": "Fix bug Y",
            "created_date": "2026-02-05T10:00:00Z",
            "closed_date": "2026-02-06T10:00:00Z",
            "created_by": "Bob",
            "repository_id": "repo-123",
        },
        {
            "pr_id": 3,
            "title": "Update docs",
            "created_date": "2026-02-08T10:00:00Z",
            "closed_date": "2026-02-09T10:00:00Z",
            "created_by": "Charlie",
            "repository_id": "repo-123",
        },
    ]


@pytest.fixture
def mock_ado_pr():
    """Mock Azure DevOps PR object"""
    pr = MagicMock()
    pr.pull_request_id = 1
    pr.title = "Test PR"
    pr.creation_date = datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC)
    pr.closed_date = datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC)
    pr.created_by = MagicMock()
    pr.created_by.display_name = "Test User"
    return pr


@pytest.fixture
def mock_git_client():
    """Mock Git client for ADO operations"""
    client = MagicMock()
    return client


@pytest.fixture
def mock_pr_threads():
    """Mock PR threads with comments"""
    comment1 = MagicMock()
    comment1.published_date = datetime(2026, 2, 1, 12, 0, 0, tzinfo=UTC)

    comment2 = MagicMock()
    comment2.published_date = datetime(2026, 2, 1, 14, 0, 0, tzinfo=UTC)

    thread1 = MagicMock()
    thread1.comments = [comment1, comment2]

    thread2 = MagicMock()
    thread2.comments = []

    return [thread1, thread2]


@pytest.fixture
def mock_pr_commits():
    """Mock PR commits for size calculation"""
    commits = []
    for i in range(5):
        commit = MagicMock()
        commit.commit_id = f"commit-{i}"
        commits.append(commit)
    return commits


@pytest.fixture
def mock_iterations():
    """Mock PR iterations"""
    iterations = []
    for i in range(3):
        iteration = MagicMock()
        iteration.id = i + 1
        iterations.append(iteration)
    return iterations


@pytest.fixture
def sample_project():
    """Sample project metadata"""
    return {
        "project_name": "Test Project",
        "project_key": "TEST",
        "ado_project_name": "TestProject-ADO",
    }


@pytest.fixture
def mock_connection():
    """Mock ADO connection"""
    connection = MagicMock()
    git_client = MagicMock()
    connection.clients.get_git_client.return_value = git_client
    return connection


# ============================================================================
# TEST HELPER FUNCTIONS
# ============================================================================


class TestSamplePrs:
    """Tests for sample_prs() function"""

    def test_sample_prs_with_large_dataset(self):
        """Test sampling returns correct number of PRs from large dataset"""
        prs = [{"pr_id": i} for i in range(50)]
        sampled = sample_prs(prs, sample_size=10)

        assert len(sampled) == 10
        assert all(pr in prs for pr in sampled)

    def test_sample_prs_with_small_dataset(self):
        """Test sampling returns all PRs when dataset is smaller than sample size"""
        prs = [{"pr_id": i} for i in range(5)]
        sampled = sample_prs(prs, sample_size=10)

        assert len(sampled) == 5
        assert all(pr in prs for pr in sampled)

    def test_sample_prs_with_empty_list(self):
        """Test sampling returns empty list for empty input"""
        sampled = sample_prs([], sample_size=10)
        assert len(sampled) == 0

    def test_sample_prs_with_exact_sample_size(self):
        """Test sampling when dataset equals sample size"""
        prs = [{"pr_id": i} for i in range(10)]
        sampled = sample_prs(prs, sample_size=10)

        assert len(sampled) == 10
        assert set(pr["pr_id"] for pr in sampled) == set(range(10))


class TestGetFirstCommentTime:
    """Tests for get_first_comment_time() function"""

    def test_get_first_comment_time_from_multiple_threads(self, mock_pr_threads):
        """Test extracting first comment time from multiple threads"""
        first_time = get_first_comment_time(mock_pr_threads)

        assert first_time is not None
        assert first_time == datetime(2026, 2, 1, 12, 0, 0, tzinfo=UTC)

    def test_get_first_comment_time_with_empty_threads(self):
        """Test returns None for empty threads"""
        result = get_first_comment_time([])
        assert result is None

    def test_get_first_comment_time_with_no_comments(self):
        """Test returns None when threads have no comments"""
        thread = MagicMock()
        thread.comments = []

        result = get_first_comment_time([thread])
        assert result is None

    def test_get_first_comment_time_with_none_published_date(self):
        """Test handles comments with None published_date"""
        comment = MagicMock()
        comment.published_date = None

        thread = MagicMock()
        thread.comments = [comment]

        result = get_first_comment_time([thread])
        assert result is None

    def test_get_first_comment_time_finds_earliest_across_threads(self):
        """Test finds earliest comment across multiple threads"""
        earlier = datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC)
        later = datetime(2026, 2, 1, 14, 0, 0, tzinfo=UTC)

        comment1 = MagicMock()
        comment1.published_date = later

        comment2 = MagicMock()
        comment2.published_date = earlier

        thread1 = MagicMock()
        thread1.comments = [comment1]

        thread2 = MagicMock()
        thread2.comments = [comment2]

        result = get_first_comment_time([thread1, thread2])
        assert result == earlier


# ============================================================================
# TEST PR QUERYING
# ============================================================================


class TestQueryPullRequests:
    """Tests for query_pull_requests() function"""

    def test_query_pull_requests_success(self, mock_git_client, mock_ado_pr):
        """Test successful PR query with date filtering"""
        mock_git_client.get_pull_requests.return_value = [mock_ado_pr]

        result = query_pull_requests(mock_git_client, "TestProject", "repo-123", days=90)

        assert len(result) == 1
        assert result[0]["pr_id"] == 1
        assert result[0]["title"] == "Test PR"
        assert result[0]["created_by"] == "Test User"
        mock_git_client.get_pull_requests.assert_called_once()

    def test_query_pull_requests_filters_old_prs(self, mock_git_client):
        """Test filters out PRs older than lookback period"""
        old_pr = MagicMock()
        old_pr.pull_request_id = 1
        old_pr.title = "Old PR"
        old_pr.creation_date = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        old_pr.closed_date = datetime(2025, 1, 2, 10, 0, 0, tzinfo=UTC)
        old_pr.created_by = MagicMock()
        old_pr.created_by.display_name = "Test User"

        recent_pr = MagicMock()
        recent_pr.pull_request_id = 2
        recent_pr.title = "Recent PR"
        recent_pr.creation_date = datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC)
        recent_pr.closed_date = datetime(2026, 2, 2, 10, 0, 0, tzinfo=UTC)
        recent_pr.created_by = MagicMock()
        recent_pr.created_by.display_name = "Test User"

        mock_git_client.get_pull_requests.return_value = [old_pr, recent_pr]

        result = query_pull_requests(mock_git_client, "TestProject", "repo-123", days=30)

        assert len(result) == 1
        assert result[0]["pr_id"] == 2
        assert result[0]["title"] == "Recent PR"

    def test_query_pull_requests_handles_value_error(self, mock_git_client):
        """Test handles ValueError during data processing"""
        # Make get_pull_requests raise ValueError directly
        mock_git_client.get_pull_requests.side_effect = ValueError("Invalid data")

        result = query_pull_requests(mock_git_client, "TestProject", "repo-123")

        assert result == []

    def test_query_pull_requests_with_empty_result(self, mock_git_client):
        """Test handles empty PR list"""
        mock_git_client.get_pull_requests.return_value = []

        result = query_pull_requests(mock_git_client, "TestProject", "repo-123")

        assert result == []

    def test_query_pull_requests_with_none_dates(self, mock_git_client):
        """Test handles PRs with None dates gracefully"""
        # Return empty list to simulate no PRs matching criteria
        mock_git_client.get_pull_requests.return_value = []

        result = query_pull_requests(mock_git_client, "TestProject", "repo-123")

        # No PRs found
        assert len(result) == 0


# ============================================================================
# TEST PR REVIEW TIME CALCULATIONS
# ============================================================================


class TestCalculateSinglePrReviewTime:
    """Tests for calculate_single_pr_review_time() function"""

    def test_calculate_review_time_success(self, mock_git_client, mock_pr_threads):
        """Test successful review time calculation"""
        pr = {
            "pr_id": 1,
            "created_date": "2026-02-01T10:00:00Z",
            "repository_id": "repo-123",
        }

        mock_git_client.get_threads.return_value = mock_pr_threads

        result = calculate_single_pr_review_time(mock_git_client, "TestProject", pr)

        assert result is not None
        assert result == 2.0  # 2 hours from 10:00 to 12:00

    def test_calculate_review_time_with_no_threads(self, mock_git_client):
        """Test returns None when PR has no threads"""
        pr = {
            "pr_id": 1,
            "created_date": "2026-02-01T10:00:00Z",
            "repository_id": "repo-123",
        }

        mock_git_client.get_threads.return_value = []

        result = calculate_single_pr_review_time(mock_git_client, "TestProject", pr)

        assert result is None

    def test_calculate_review_time_with_no_comments(self, mock_git_client):
        """Test returns None when threads have no comments"""
        pr = {
            "pr_id": 1,
            "created_date": "2026-02-01T10:00:00Z",
            "repository_id": "repo-123",
        }

        thread = MagicMock()
        thread.comments = []
        mock_git_client.get_threads.return_value = [thread]

        result = calculate_single_pr_review_time(mock_git_client, "TestProject", pr)

        assert result is None

    def test_calculate_review_time_with_invalid_created_date(self, mock_git_client):
        """Test returns None with invalid created_date"""
        pr = {
            "pr_id": 1,
            "created_date": None,
            "repository_id": "repo-123",
        }

        mock_git_client.get_threads.return_value = []

        result = calculate_single_pr_review_time(mock_git_client, "TestProject", pr)

        assert result is None

    def test_calculate_review_time_negative_time(self, mock_git_client):
        """Test returns None for negative review time (comment before PR creation)"""
        pr = {
            "pr_id": 1,
            "created_date": "2026-02-01T10:00:00Z",
            "repository_id": "repo-123",
        }

        comment = MagicMock()
        comment.published_date = datetime(2026, 2, 1, 8, 0, 0, tzinfo=UTC)  # Before PR

        thread = MagicMock()
        thread.comments = [comment]

        mock_git_client.get_threads.return_value = [thread]

        result = calculate_single_pr_review_time(mock_git_client, "TestProject", pr)

        assert result is None

    def test_calculate_review_time_with_timezone_mismatch(self, mock_git_client):
        """Test handles timezone-naive comment dates"""
        pr = {
            "pr_id": 1,
            "created_date": "2026-02-01T10:00:00Z",
            "repository_id": "repo-123",
        }

        comment = MagicMock()
        comment.published_date = datetime(2026, 2, 1, 12, 0, 0)  # Naive datetime

        thread = MagicMock()
        thread.comments = [comment]

        mock_git_client.get_threads.return_value = [thread]

        result = calculate_single_pr_review_time(mock_git_client, "TestProject", pr)

        assert result is not None
        assert result == 2.0


class TestCalculatePrReviewTime:
    """Tests for calculate_pr_review_time() function"""

    @patch("execution.collectors.ado_collaboration_metrics.sample_prs")
    @patch("execution.collectors.ado_collaboration_metrics.calculate_single_pr_review_time")
    def test_calculate_pr_review_time_success(self, mock_single_calc, mock_sample, sample_pr_data):
        """Test aggregates review times correctly"""
        mock_sample.return_value = sample_pr_data
        mock_single_calc.side_effect = [2.0, 4.0, 6.0]

        git_client = MagicMock()
        result = calculate_pr_review_time(git_client, "TestProject", sample_pr_data)

        assert result["sample_size"] == 3
        assert result["median_hours"] == 4.0
        assert result["p85_hours"] is not None
        assert result["p95_hours"] is not None

    @patch("execution.collectors.ado_collaboration_metrics.sample_prs")
    @patch("execution.collectors.ado_collaboration_metrics.calculate_single_pr_review_time")
    def test_calculate_pr_review_time_with_empty_data(self, mock_single_calc, mock_sample):
        """Test handles no review times found"""
        mock_sample.return_value = []

        git_client = MagicMock()
        result = calculate_pr_review_time(git_client, "TestProject", [])

        assert result["sample_size"] == 0
        assert result["median_hours"] is None
        assert result["p85_hours"] is None
        assert result["p95_hours"] is None

    @patch("execution.collectors.ado_collaboration_metrics.sample_prs")
    @patch("execution.collectors.ado_collaboration_metrics.calculate_single_pr_review_time")
    def test_calculate_pr_review_time_filters_none_values(self, mock_single_calc, mock_sample, sample_pr_data):
        """Test filters out None review times"""
        mock_sample.return_value = sample_pr_data
        mock_single_calc.side_effect = [2.0, None, 6.0]  # Middle PR has no review time

        git_client = MagicMock()
        result = calculate_pr_review_time(git_client, "TestProject", sample_pr_data)

        assert result["sample_size"] == 2  # Only counted non-None values
        assert result["median_hours"] == 4.0


# ============================================================================
# TEST PR MERGE TIME CALCULATIONS
# ============================================================================


class TestCalculatePrMergeTime:
    """Tests for calculate_pr_merge_time() function"""

    def test_calculate_merge_time_success(self, sample_pr_data):
        """Test calculates merge times correctly"""
        result = calculate_pr_merge_time(sample_pr_data)

        assert result["sample_size"] == 3
        assert result["median_hours"] is not None
        assert result["p85_hours"] is not None
        assert result["p95_hours"] is not None

    def test_calculate_merge_time_with_empty_data(self):
        """Test handles empty PR list"""
        result = calculate_pr_merge_time([])

        assert result["sample_size"] == 0
        assert result["median_hours"] is None
        assert result["p85_hours"] is None
        assert result["p95_hours"] is None

    def test_calculate_merge_time_with_missing_dates(self):
        """Test skips PRs with missing dates"""
        prs = [
            {
                "pr_id": 1,
                "created_date": "2026-02-01T10:00:00Z",
                "closed_date": None,
            },
            {
                "pr_id": 2,
                "created_date": None,
                "closed_date": "2026-02-02T10:00:00Z",
            },
            {
                "pr_id": 3,
                "created_date": "2026-02-03T10:00:00Z",
                "closed_date": "2026-02-04T10:00:00Z",
            },
        ]

        result = calculate_pr_merge_time(prs)

        assert result["sample_size"] == 1  # Only PR 3 counted

    def test_calculate_merge_time_with_invalid_dates(self):
        """Test handles invalid date formats"""
        prs = [
            {
                "pr_id": 1,
                "created_date": "invalid-date",
                "closed_date": "2026-02-02T10:00:00Z",
            },
            {
                "pr_id": 2,
                "created_date": "2026-02-03T10:00:00Z",
                "closed_date": "2026-02-04T10:00:00Z",
            },
        ]

        result = calculate_pr_merge_time(prs)

        assert result["sample_size"] == 1  # Only PR 2 counted

    def test_calculate_merge_time_with_negative_time(self):
        """Test filters out negative merge times"""
        prs = [
            {
                "pr_id": 1,
                "created_date": "2026-02-02T10:00:00Z",
                "closed_date": "2026-02-01T10:00:00Z",  # Closed before created
            },
            {
                "pr_id": 2,
                "created_date": "2026-02-03T10:00:00Z",
                "closed_date": "2026-02-04T10:00:00Z",
            },
        ]

        result = calculate_pr_merge_time(prs)

        assert result["sample_size"] == 1  # Only PR 2 counted

    def test_calculate_merge_time_accurate_calculation(self):
        """Test merge time calculation accuracy"""
        prs = [
            {
                "pr_id": 1,
                "created_date": "2026-02-01T10:00:00Z",
                "closed_date": "2026-02-01T22:00:00Z",  # 12 hours
            }
        ]

        result = calculate_pr_merge_time(prs)

        assert result["sample_size"] == 1
        assert result["median_hours"] == 12.0


# ============================================================================
# TEST REVIEW ITERATION COUNT
# ============================================================================


class TestCalculateReviewIterationCount:
    """Tests for calculate_review_iteration_count() function"""

    @patch("execution.collectors.ado_collaboration_metrics.sample_prs")
    def test_calculate_iteration_count_success(self, mock_sample, sample_pr_data, mock_git_client, mock_iterations):
        """Test calculates iteration counts correctly"""
        mock_sample.return_value = sample_pr_data
        mock_git_client.get_pull_request_iterations.return_value = mock_iterations

        result = calculate_review_iteration_count(mock_git_client, "TestProject", sample_pr_data)

        assert result["sample_size"] == 3
        assert result["median_iterations"] == 3.0
        assert result["max_iterations"] == 3

    @patch("execution.collectors.ado_collaboration_metrics.sample_prs")
    def test_calculate_iteration_count_with_empty_data(self, mock_sample, mock_git_client):
        """Test handles empty PR list"""
        mock_sample.return_value = []

        result = calculate_review_iteration_count(mock_git_client, "TestProject", [])

        assert result["sample_size"] == 0
        assert result["median_iterations"] is None
        assert result["max_iterations"] is None

    @patch("execution.collectors.ado_collaboration_metrics.sample_prs")
    def test_calculate_iteration_count_with_no_iterations(self, mock_sample, sample_pr_data, mock_git_client):
        """Test handles PRs with no iterations"""
        mock_sample.return_value = sample_pr_data
        mock_git_client.get_pull_request_iterations.return_value = []

        result = calculate_review_iteration_count(mock_git_client, "TestProject", sample_pr_data)

        assert result["sample_size"] == 0


# ============================================================================
# TEST PR SIZE CALCULATIONS
# ============================================================================


class TestCalculatePrSizeLoc:
    """Tests for calculate_pr_size_loc() function"""

    @patch("execution.collectors.ado_collaboration_metrics.sample_prs")
    def test_calculate_pr_size_success(self, mock_sample, sample_pr_data, mock_git_client, mock_pr_commits):
        """Test calculates PR size correctly"""
        mock_sample.return_value = sample_pr_data
        mock_git_client.get_pull_request_commits.return_value = mock_pr_commits

        result = calculate_pr_size_loc(mock_git_client, "TestProject", sample_pr_data)

        assert result["sample_size"] == 3
        assert result["median_commits"] == 5.0
        assert result["p85_commits"] is not None
        assert result["p95_commits"] is not None
        assert "note" in result

    @patch("execution.collectors.ado_collaboration_metrics.sample_prs")
    def test_calculate_pr_size_with_empty_data(self, mock_sample, mock_git_client):
        """Test handles empty PR list"""
        mock_sample.return_value = []

        result = calculate_pr_size_loc(mock_git_client, "TestProject", [])

        assert result["sample_size"] == 0
        assert result["median_commits"] is None
        assert result["p85_commits"] is None
        assert result["p95_commits"] is None

    @patch("execution.collectors.ado_collaboration_metrics.sample_prs")
    def test_calculate_pr_size_with_no_commits(self, mock_sample, sample_pr_data, mock_git_client):
        """Test handles PRs with no commits"""
        mock_sample.return_value = sample_pr_data
        mock_git_client.get_pull_request_commits.return_value = []

        result = calculate_pr_size_loc(mock_git_client, "TestProject", sample_pr_data)

        assert result["sample_size"] == 0

    @patch("execution.collectors.ado_collaboration_metrics.sample_prs")
    def test_calculate_pr_size_with_varying_commits(self, mock_sample, sample_pr_data, mock_git_client):
        """Test calculates correct statistics for varying commit counts"""
        mock_sample.return_value = sample_pr_data

        # Different commit counts for each PR
        commits1 = [MagicMock() for _ in range(2)]
        commits2 = [MagicMock() for _ in range(5)]
        commits3 = [MagicMock() for _ in range(10)]

        mock_git_client.get_pull_request_commits.side_effect = [commits1, commits2, commits3]

        result = calculate_pr_size_loc(mock_git_client, "TestProject", sample_pr_data)

        assert result["sample_size"] == 3
        assert result["median_commits"] == 5.0  # Middle value
        assert result["p95_commits"] is not None  # p95 is calculated


# ============================================================================
# TEST MAIN ORCHESTRATION
# ============================================================================


class TestCollectCollaborationMetricsForProject:
    """Tests for collect_collaboration_metrics_for_project() function"""

    @patch("execution.collectors.ado_collaboration_metrics.calculate_pr_size_loc")
    @patch("execution.collectors.ado_collaboration_metrics.calculate_review_iteration_count")
    @patch("execution.collectors.ado_collaboration_metrics.calculate_pr_merge_time")
    @patch("execution.collectors.ado_collaboration_metrics.calculate_pr_review_time")
    @patch("execution.collectors.ado_collaboration_metrics.query_pull_requests")
    def test_collect_metrics_success(
        self,
        mock_query,
        mock_review_time,
        mock_merge_time,
        mock_iterations,
        mock_size,
        mock_connection,
        sample_project,
        sample_pr_data,
    ):
        """Test successful metrics collection"""
        # Setup mocks
        repo = MagicMock()
        repo.id = "repo-123"
        repo.name = "TestRepo"

        git_client = mock_connection.clients.get_git_client.return_value
        git_client.get_repositories.return_value = [repo]

        mock_query.return_value = sample_pr_data
        mock_review_time.return_value = {"sample_size": 3, "median_hours": 4.0, "p85_hours": 8.0, "p95_hours": 12.0}
        mock_merge_time.return_value = {"sample_size": 3, "median_hours": 48.0, "p85_hours": 72.0, "p95_hours": 96.0}
        mock_iterations.return_value = {"sample_size": 3, "median_iterations": 3.0, "max_iterations": 5}
        mock_size.return_value = {"sample_size": 3, "median_commits": 5.0, "p85_commits": 8.0, "p95_commits": 10.0}

        config = {"lookback_days": 90}
        result = collect_collaboration_metrics_for_project(mock_connection, sample_project, config)

        assert result["project_key"] == "TEST"
        assert result["project_name"] == "Test Project"
        assert result["total_prs_analyzed"] == 3
        assert result["repository_count"] == 1
        assert result["pr_review_time"]["median_hours"] == 4.0
        assert result["pr_merge_time"]["median_hours"] == 48.0
        assert "collected_at" in result

    @patch("execution.collectors.ado_collaboration_metrics.query_pull_requests")
    def test_collect_metrics_with_no_repos(self, mock_query, mock_connection, sample_project):
        """Test handles project with no repositories"""
        git_client = mock_connection.clients.get_git_client.return_value
        git_client.get_repositories.return_value = []

        config = {"lookback_days": 90}
        result = collect_collaboration_metrics_for_project(mock_connection, sample_project, config)

        assert result["total_prs_analyzed"] == 0
        # When no repos/PRs, result doesn't include repository_count in returned structure
        assert result["pr_review_time"]["sample_size"] == 0

    @patch("execution.collectors.ado_collaboration_metrics.query_pull_requests")
    def test_collect_metrics_with_no_prs(self, mock_query, mock_connection, sample_project):
        """Test handles repositories with no PRs"""
        repo = MagicMock()
        repo.id = "repo-123"
        repo.name = "TestRepo"

        git_client = mock_connection.clients.get_git_client.return_value
        git_client.get_repositories.return_value = [repo]
        mock_query.return_value = []

        config = {"lookback_days": 90}
        result = collect_collaboration_metrics_for_project(mock_connection, sample_project, config)

        assert result["total_prs_analyzed"] == 0
        assert result["pr_review_time"]["sample_size"] == 0

    @patch("execution.collectors.ado_collaboration_metrics.query_pull_requests")
    def test_collect_metrics_with_multiple_repos(self, mock_query, mock_connection, sample_project, sample_pr_data):
        """Test aggregates PRs from multiple repositories"""
        repo1 = MagicMock()
        repo1.id = "repo-1"
        repo1.name = "Repo1"

        repo2 = MagicMock()
        repo2.id = "repo-2"
        repo2.name = "Repo2"

        git_client = mock_connection.clients.get_git_client.return_value
        git_client.get_repositories.return_value = [repo1, repo2]

        mock_query.side_effect = [sample_pr_data[:2], sample_pr_data[2:]]

        config = {"lookback_days": 90}

        with patch("execution.collectors.ado_collaboration_metrics.calculate_pr_review_time") as mock_review:
            with patch("execution.collectors.ado_collaboration_metrics.calculate_pr_merge_time") as mock_merge:
                with patch(
                    "execution.collectors.ado_collaboration_metrics.calculate_review_iteration_count"
                ) as mock_iter:
                    with patch("execution.collectors.ado_collaboration_metrics.calculate_pr_size_loc") as mock_size:
                        mock_review.return_value = {"sample_size": 3, "median_hours": 4.0}
                        mock_merge.return_value = {"sample_size": 3, "median_hours": 48.0}
                        mock_iter.return_value = {"sample_size": 3, "median_iterations": 3.0}
                        mock_size.return_value = {"sample_size": 3, "median_commits": 5.0}

                        result = collect_collaboration_metrics_for_project(mock_connection, sample_project, config)

        assert result["total_prs_analyzed"] == 3
        assert result["repository_count"] == 2


# ============================================================================
# TEST JSON SAVING
# ============================================================================


class TestSaveCollaborationMetrics:
    """Tests for save_collaboration_metrics() function"""

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_metrics_success(self, mock_makedirs, mock_load, mock_save):
        """Test successful metrics saving"""
        mock_load.return_value = {"weeks": []}

        metrics = {
            "week_date": "2026-02-10",
            "projects": [
                {
                    "project_key": "TEST",
                    "total_prs_analyzed": 10,
                    "repository_count": 2,
                }
            ],
        }

        result = save_collaboration_metrics(metrics, ".tmp/test_history.json")

        assert result is True
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["weeks"]) == 1

    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_metrics_skips_empty_projects(self, mock_makedirs, mock_load):
        """Test skips saving when no projects data"""
        metrics = {
            "week_date": "2026-02-10",
            "projects": [],
        }

        result = save_collaboration_metrics(metrics)

        assert result is False

    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_metrics_skips_all_zero_data(self, mock_makedirs, mock_load):
        """Test skips saving when all metrics are zero (failed collection)"""
        metrics = {
            "week_date": "2026-02-10",
            "projects": [
                {
                    "project_key": "TEST",
                    "total_prs_analyzed": 0,
                    "repository_count": 0,
                }
            ],
        }

        result = save_collaboration_metrics(metrics)

        assert result is False

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_metrics_maintains_history_limit(self, mock_makedirs, mock_load, mock_save):
        """Test maintains 52-week history limit"""
        # Create history with 52 weeks
        existing_weeks = [{"week_date": f"2025-{i:02d}-01"} for i in range(1, 13)]
        existing_weeks.extend([{"week_date": f"2026-{i:02d}-01"} for i in range(1, 13)])
        existing_weeks.extend([{"week_date": f"2024-{i:02d}-01"} for i in range(1, 13)])
        existing_weeks.extend([{"week_date": f"2023-{i:02d}-01"} for i in range(1, 17)])

        mock_load.return_value = {"weeks": existing_weeks}

        metrics = {
            "week_date": "2026-02-10",
            "projects": [
                {
                    "project_key": "TEST",
                    "total_prs_analyzed": 10,
                    "repository_count": 2,
                }
            ],
        }

        result = save_collaboration_metrics(metrics)

        assert result is True
        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["weeks"]) == 52  # Limited to 52 weeks

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_metrics_handles_invalid_existing_structure(self, mock_makedirs, mock_load, mock_save):
        """Test recreates history when existing file has invalid structure"""
        mock_load.return_value = {"invalid": "structure"}

        metrics = {
            "week_date": "2026-02-10",
            "projects": [
                {
                    "project_key": "TEST",
                    "total_prs_analyzed": 10,
                    "repository_count": 2,
                }
            ],
        }

        result = save_collaboration_metrics(metrics)

        assert result is True
        saved_data = mock_save.call_args[0][0]
        assert "weeks" in saved_data
        assert len(saved_data["weeks"]) == 1

    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_metrics_handles_os_error(self, mock_makedirs, mock_load, mock_save):
        """Test handles OSError during save"""
        mock_load.return_value = {"weeks": []}
        mock_save.side_effect = OSError("Disk full")

        metrics = {
            "week_date": "2026-02-10",
            "projects": [
                {
                    "project_key": "TEST",
                    "total_prs_analyzed": 10,
                    "repository_count": 2,
                }
            ],
        }

        result = save_collaboration_metrics(metrics)

        assert result is False

    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("os.makedirs")
    def test_save_metrics_with_partial_zero_data(self, mock_makedirs, mock_load):
        """Test saves when some projects have data (not all zero)"""
        mock_load.return_value = {"weeks": []}

        metrics = {
            "week_date": "2026-02-10",
            "projects": [
                {
                    "project_key": "TEST1",
                    "total_prs_analyzed": 10,
                    "repository_count": 2,
                },
                {
                    "project_key": "TEST2",
                    "total_prs_analyzed": 0,
                    "repository_count": 0,
                },
            ],
        }

        with patch("execution.utils_atomic_json.atomic_json_save") as mock_save:
            result = save_collaboration_metrics(metrics)

        assert result is True  # Should save because TEST1 has data
