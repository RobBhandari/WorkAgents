"""
Tests for ADO Risk Metrics Collector

Tests cover:
- File path extraction from Git changes
- Commit data building and structuring
- Commit change fetching with error handling
- Recent commits querying
- Pull request querying
- Code churn analysis
- Knowledge distribution calculations
- Module coupling analysis
- Risk metrics collection for projects
- History file saving with validation
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest
from azure.devops.exceptions import AzureDevOpsServiceError

from execution.collectors.ado_risk_metrics import (
    _build_commit_data,
    _extract_file_paths_from_changes,
    _fetch_commit_changes,
    analyze_code_churn,
    calculate_knowledge_distribution,
    calculate_module_coupling,
    collect_risk_metrics_for_project,
    query_pull_requests,
    query_recent_commits,
    save_risk_metrics,
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def create_azure_error(message: str) -> AzureDevOpsServiceError:
    """
    Create a proper AzureDevOpsServiceError instance.

    AzureDevOpsServiceError requires a wrapped exception object with specific attributes.
    """
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


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_git_changes_dict():
    """Mock Git changes object with dictionary-style change items"""
    changes = Mock()
    changes.changes = [
        {"item": {"path": "/src/file1.py"}},
        {"item": {"path": "/src/file2.py"}},
        {"item": {"path": "/tests/test_file.py"}},
    ]
    return changes


@pytest.fixture
def mock_git_changes_object():
    """Mock Git changes object with object-style change items"""
    change1 = Mock()
    change1.item = Mock()
    change1.item.path = "/src/module.py"

    change2 = Mock()
    change2.item = Mock()
    change2.item.path = "/docs/readme.md"

    changes = Mock()
    changes.changes = [change1, change2]
    return changes


@pytest.fixture
def mock_git_changes_empty():
    """Mock Git changes object with no changes"""
    changes = Mock()
    changes.changes = []
    return changes


@pytest.fixture
def mock_git_changes_none():
    """Mock Git changes object that is None"""
    return None


@pytest.fixture
def mock_commit():
    """Mock Git commit object"""
    commit = Mock()
    commit.commit_id = "abc123def456"
    commit.author = Mock()
    commit.author.name = "John Doe"
    commit.author.date = datetime(2026, 2, 1, 10, 30, 0)
    commit.comment = "Fix bug in authentication"
    return commit


@pytest.fixture
def mock_commit_no_author():
    """Mock Git commit with no author"""
    commit = Mock()
    commit.commit_id = "xyz789"
    commit.author = None
    commit.comment = "Anonymous commit"
    return commit


@pytest.fixture
def sample_commits_data():
    """Sample commit data for churn analysis"""
    return [
        {
            "commit_id": "commit1",
            "author": "Alice",
            "date": datetime(2026, 2, 1).isoformat(),
            "message": "Add feature A",
            "changes": 5,
            "files": ["/src/feature_a.py", "/src/utils.py", "/tests/test_a.py"],
        },
        {
            "commit_id": "commit2",
            "author": "Bob",
            "date": datetime(2026, 2, 2).isoformat(),
            "message": "Fix bug in utils",
            "changes": 2,
            "files": ["/src/utils.py", "/tests/test_utils.py"],
        },
        {
            "commit_id": "commit3",
            "author": "Alice",
            "date": datetime(2026, 2, 3).isoformat(),
            "message": "Update feature A",
            "changes": 3,
            "files": ["/src/feature_a.py", "/src/utils.py"],
        },
        {
            "commit_id": "commit4",
            "author": "Charlie",
            "date": datetime(2026, 2, 4).isoformat(),
            "message": "Add feature B",
            "changes": 4,
            "files": ["/src/feature_b.py", "/tests/test_b.py"],
        },
    ]


@pytest.fixture
def sample_pr_data():
    """Sample PR data for size analysis"""
    return [
        {
            "pr_id": 101,
            "title": "Small PR - Quick fix",
            "created_date": "2026-02-01T10:00:00",
            "closed_date": "2026-02-01T11:00:00",
            "commit_count": 2,
            "status": "completed",
            "created_by": "Alice",
            "created_by_email": "alice@example.com",
            "source_branch": "refs/heads/bugfix/auth",
            "description": "Fixed authentication issue",
        },
        {
            "pr_id": 102,
            "title": "Large PR - New feature",
            "created_date": "2026-02-05T09:00:00",
            "closed_date": "2026-02-08T16:00:00",
            "commit_count": 15,
            "status": "completed",
            "created_by": "Bob",
            "created_by_email": "bob@example.com",
            "source_branch": "refs/heads/feature/dashboard",
            "description": "Added new dashboard",
        },
    ]


@pytest.fixture
def temp_history_file(tmp_path):
    """Create a temporary history file path"""
    return tmp_path / "risk_history.json"


# ============================================================================
# TESTS: _extract_file_paths_from_changes
# ============================================================================


class TestExtractFilePathsFromChanges:
    """Test file path extraction from Git changes"""

    def test_extract_from_dict_changes(self, mock_git_changes_dict):
        """Test extracting paths from dictionary-style changes"""
        paths = _extract_file_paths_from_changes(mock_git_changes_dict)

        assert len(paths) == 3
        assert "/src/file1.py" in paths
        assert "/src/file2.py" in paths
        assert "/tests/test_file.py" in paths

    def test_extract_from_object_changes(self, mock_git_changes_object):
        """Test extracting paths from object-style changes"""
        paths = _extract_file_paths_from_changes(mock_git_changes_object)

        assert len(paths) == 2
        assert "/src/module.py" in paths
        assert "/docs/readme.md" in paths

    def test_extract_from_empty_changes(self, mock_git_changes_empty):
        """Test handling empty changes list"""
        paths = _extract_file_paths_from_changes(mock_git_changes_empty)

        assert paths == []

    def test_extract_from_none_changes(self, mock_git_changes_none):
        """Test handling None changes"""
        paths = _extract_file_paths_from_changes(mock_git_changes_none)

        assert paths == []

    def test_extract_handles_missing_item(self):
        """Test handling changes with missing item field"""
        changes = Mock()
        changes.changes = [
            {"item": {"path": "/src/valid.py"}},
            {"item": None},  # Missing item
            {},  # No item key
        ]

        paths = _extract_file_paths_from_changes(changes)

        assert len(paths) == 1
        assert "/src/valid.py" in paths

    def test_extract_handles_missing_path(self):
        """Test handling changes with missing path field"""
        changes = Mock()
        changes.changes = [
            {"item": {"path": "/src/valid.py"}},
            {"item": {}},  # Missing path
        ]

        paths = _extract_file_paths_from_changes(changes)

        assert len(paths) == 1
        assert "/src/valid.py" in paths

    def test_extract_no_changes_attribute(self):
        """Test handling changes object without changes attribute"""
        changes = Mock(spec=[])  # Mock with no attributes

        paths = _extract_file_paths_from_changes(changes)

        assert paths == []


# ============================================================================
# TESTS: _build_commit_data
# ============================================================================


class TestBuildCommitData:
    """Test commit data dictionary building"""

    def test_build_with_full_data(self, mock_commit):
        """Test building commit data with all parameters"""
        files = ["/src/file1.py", "/src/file2.py"]
        result = _build_commit_data(mock_commit, changes=5, files=files)

        assert result["commit_id"] == "abc123def456"
        assert result["author"] == "John Doe"
        assert result["date"] == datetime(2026, 2, 1, 10, 30, 0)
        assert result["message"] == "Fix bug in authentication"
        assert result["changes"] == 5
        assert result["files"] == files

    def test_build_with_defaults(self, mock_commit):
        """Test building commit data with default parameters"""
        result = _build_commit_data(mock_commit)

        assert result["commit_id"] == "abc123def456"
        assert result["author"] == "John Doe"
        assert result["changes"] == 0
        assert result["files"] == []

    def test_build_with_no_author(self, mock_commit_no_author):
        """Test building commit data when author is None"""
        result = _build_commit_data(mock_commit_no_author)

        assert result["commit_id"] == "xyz789"
        assert result["author"] == "Unknown"
        assert result["date"] is None
        assert result["message"] == "Anonymous commit"

    def test_build_preserves_empty_files_list(self, mock_commit):
        """Test that empty files list is preserved"""
        result = _build_commit_data(mock_commit, changes=3, files=[])

        assert result["changes"] == 3
        assert result["files"] == []


# ============================================================================
# TESTS: _fetch_commit_changes
# ============================================================================


class TestFetchCommitChanges:
    """Test fetching file changes for a commit"""

    def test_fetch_successful(self, mock_git_changes_dict):
        """Test successfully fetching commit changes"""
        git_client = Mock()
        git_client.get_changes.return_value = mock_git_changes_dict

        change_count, file_paths = _fetch_commit_changes(git_client, "commit123", "repo456", "TestProject")

        assert change_count == 3
        assert len(file_paths) == 3
        git_client.get_changes.assert_called_once_with(
            commit_id="commit123", repository_id="repo456", project="TestProject"
        )

    def test_fetch_with_empty_changes(self, mock_git_changes_empty):
        """Test fetching when commit has no changes"""
        git_client = Mock()
        git_client.get_changes.return_value = mock_git_changes_empty

        change_count, file_paths = _fetch_commit_changes(git_client, "commit123", "repo456", "TestProject")

        assert change_count == 0
        assert file_paths == []

    def test_fetch_azure_devops_error(self):
        """Test handling AzureDevOpsServiceError"""
        git_client = Mock()
        git_client.get_changes.side_effect = create_azure_error("API Error")

        change_count, file_paths = _fetch_commit_changes(git_client, "commit123", "repo456", "TestProject")

        assert change_count == 0
        assert file_paths == []

    def test_fetch_connection_error(self):
        """Test handling ConnectionError"""
        git_client = Mock()
        git_client.get_changes.side_effect = ConnectionError("Network error")

        change_count, file_paths = _fetch_commit_changes(git_client, "commit123", "repo456", "TestProject")

        assert change_count == 0
        assert file_paths == []

    def test_fetch_timeout_error(self):
        """Test handling TimeoutError"""
        git_client = Mock()
        git_client.get_changes.side_effect = TimeoutError("Request timed out")

        change_count, file_paths = _fetch_commit_changes(git_client, "commit123", "repo456", "TestProject")

        assert change_count == 0
        assert file_paths == []

    def test_fetch_short_commit_id(self):
        """Test handling short commit ID (less than 8 chars)"""
        git_client = Mock()
        git_client.get_changes.side_effect = create_azure_error("Error")

        # Should not crash with short commit ID
        change_count, file_paths = _fetch_commit_changes(git_client, "abc", "repo456", "TestProject")

        assert change_count == 0
        assert file_paths == []


# ============================================================================
# TESTS: query_recent_commits
# ============================================================================


class TestQueryRecentCommits:
    """Test querying recent commits"""

    def test_query_commits_success(self, mock_commit, mock_git_changes_dict):
        """Test successfully querying commits"""
        git_client = Mock()

        # Create multiple commits
        commits = [mock_commit for _ in range(5)]
        git_client.get_commits.return_value = commits
        git_client.get_changes.return_value = mock_git_changes_dict

        result = query_recent_commits(git_client, "TestProject", "repo123", days=30)

        assert len(result) == 5
        assert all("commit_id" in commit for commit in result)
        assert all("author" in commit for commit in result)
        assert all("files" in commit for commit in result)

    def test_query_commits_respects_detail_limit(self, mock_commit, mock_git_changes_dict):
        """Test that only first N commits get detailed file changes"""
        git_client = Mock()

        # Create 25 commits (more than COMMIT_DETAIL_LIMIT of 20)
        commits = [mock_commit for _ in range(25)]
        git_client.get_commits.return_value = commits
        git_client.get_changes.return_value = mock_git_changes_dict

        with patch("execution.collectors.ado_risk_metrics.sampling_config") as mock_config:
            mock_config.COMMIT_DETAIL_LIMIT = 20
            result = query_recent_commits(git_client, "TestProject", "repo123", days=30)

        # Should have 25 commits total
        assert len(result) == 25

        # First 20 should have file details
        assert git_client.get_changes.call_count == 20

        # Last 5 should have basic info only (changes=0, files=[])
        assert all(commit["changes"] == 0 for commit in result[20:])
        assert all(commit["files"] == [] for commit in result[20:])

    def test_query_commits_date_criteria(self, mock_commit):
        """Test that date criteria is properly set"""
        git_client = Mock()
        git_client.get_commits.return_value = [mock_commit]
        git_client.get_changes.return_value = Mock(changes=[])

        query_recent_commits(git_client, "TestProject", "repo123", days=90)

        # Verify search criteria was passed
        call_args = git_client.get_commits.call_args
        assert call_args[1]["search_criteria"] is not None
        assert call_args[1]["top"] == 100

    def test_query_commits_azure_error(self):
        """Test handling AzureDevOpsServiceError in get_commits"""
        git_client = Mock()
        git_client.get_commits.side_effect = create_azure_error("API Error")

        result = query_recent_commits(git_client, "TestProject", "repo123", days=30)

        assert result == []

    def test_query_commits_connection_error(self):
        """Test handling ConnectionError"""
        git_client = Mock()
        git_client.get_commits.side_effect = ConnectionError("Network error")

        result = query_recent_commits(git_client, "TestProject", "repo123", days=30)

        assert result == []

    def test_query_commits_timeout_error(self):
        """Test handling TimeoutError"""
        git_client = Mock()
        git_client.get_commits.side_effect = TimeoutError("Request timed out")

        result = query_recent_commits(git_client, "TestProject", "repo123", days=30)

        assert result == []


# ============================================================================
# TESTS: query_pull_requests
# ============================================================================


class TestQueryPullRequests:
    """Test querying pull requests"""

    def test_query_prs_success(self):
        """Test successfully querying PRs"""
        git_client = Mock()

        # Mock PR objects
        pr1 = Mock()
        pr1.pull_request_id = 101
        pr1.title = "Fix bug"
        pr1.creation_date = datetime.now()
        pr1.closed_date = datetime.now()
        pr1.status = "completed"
        pr1.created_by = Mock(display_name="Alice", unique_name="alice@example.com")
        pr1.source_ref_name = "refs/heads/bugfix"
        pr1.description = "Fixed the bug"

        git_client.get_pull_requests.return_value = [pr1]
        git_client.get_pull_request_commits.return_value = [Mock(), Mock()]  # 2 commits

        result = query_pull_requests(git_client, "TestProject", "repo123", days=30)

        assert len(result) == 1
        assert result[0]["pr_id"] == 101
        assert result[0]["title"] == "Fix bug"
        assert result[0]["commit_count"] == 2
        assert result[0]["created_by"] == "Alice"

    def test_query_prs_filters_by_date(self):
        """Test that PRs are filtered by creation date"""
        git_client = Mock()

        # Create PRs with different dates
        recent_pr = Mock()
        recent_pr.pull_request_id = 101
        recent_pr.title = "Recent"
        recent_pr.creation_date = datetime.now()
        recent_pr.closed_date = datetime.now()
        recent_pr.status = "completed"
        recent_pr.created_by = Mock(display_name="Alice", unique_name="alice@example.com")

        old_pr = Mock()
        old_pr.pull_request_id = 102
        old_pr.title = "Old"
        old_pr.creation_date = datetime.now() - timedelta(days=100)
        old_pr.closed_date = datetime.now() - timedelta(days=99)
        old_pr.status = "completed"
        old_pr.created_by = Mock(display_name="Bob", unique_name="bob@example.com")

        git_client.get_pull_requests.return_value = [recent_pr, old_pr]
        git_client.get_pull_request_commits.return_value = []

        result = query_pull_requests(git_client, "TestProject", "repo123", days=30)

        # Only recent PR should be included
        assert len(result) == 1
        assert result[0]["pr_id"] == 101

    def test_query_prs_handles_missing_commits(self):
        """Test handling when PR commits cannot be fetched"""
        git_client = Mock()

        pr = Mock()
        pr.pull_request_id = 101
        pr.title = "Test PR"
        pr.creation_date = datetime.now()
        pr.closed_date = datetime.now()
        pr.status = "completed"
        pr.created_by = Mock(display_name="Alice", unique_name="alice@example.com")

        git_client.get_pull_requests.return_value = [pr]
        git_client.get_pull_request_commits.side_effect = create_azure_error("Error")

        result = query_pull_requests(git_client, "TestProject", "repo123", days=30)

        assert len(result) == 1
        assert result[0]["commit_count"] == 0

    def test_query_prs_handles_no_created_by(self):
        """Test handling PR with no created_by field"""
        git_client = Mock()

        pr = Mock()
        pr.pull_request_id = 101
        pr.title = "Test PR"
        pr.creation_date = datetime.now()
        pr.closed_date = datetime.now()
        pr.status = "completed"
        pr.created_by = None

        git_client.get_pull_requests.return_value = [pr]
        git_client.get_pull_request_commits.return_value = []

        result = query_pull_requests(git_client, "TestProject", "repo123", days=30)

        assert len(result) == 1
        assert result[0]["created_by"] == "Unknown"
        assert result[0]["created_by_email"] is None

    def test_query_prs_azure_error(self):
        """Test handling AzureDevOpsServiceError"""
        git_client = Mock()
        git_client.get_pull_requests.side_effect = create_azure_error("API Error")

        result = query_pull_requests(git_client, "TestProject", "repo123", days=30)

        assert result == []

    def test_query_prs_connection_error(self):
        """Test handling ConnectionError"""
        git_client = Mock()
        git_client.get_pull_requests.side_effect = ConnectionError("Network error")

        result = query_pull_requests(git_client, "TestProject", "repo123", days=30)

        assert result == []

    def test_query_prs_parsing_error(self):
        """Test handling AttributeError when parsing PR commits"""
        git_client = Mock()

        pr = Mock()
        pr.pull_request_id = 101
        pr.title = "Test PR"
        pr.creation_date = datetime.now()
        pr.closed_date = datetime.now()
        pr.status = "completed"
        pr.created_by = Mock(display_name="Alice", unique_name="alice@example.com")

        git_client.get_pull_requests.return_value = [pr]
        git_client.get_pull_request_commits.side_effect = AttributeError("Parse error")

        result = query_pull_requests(git_client, "TestProject", "repo123", days=30)

        # Should still return PR with commit_count=0
        assert len(result) == 1
        assert result[0]["commit_count"] == 0


# ============================================================================
# TESTS: analyze_code_churn
# ============================================================================


class TestAnalyzeCodeChurn:
    """Test code churn analysis"""

    def test_analyze_churn_basic(self, sample_commits_data):
        """Test basic churn analysis"""
        result = analyze_code_churn(sample_commits_data)

        assert result["total_commits"] == 4
        assert result["total_file_changes"] == 14  # 5 + 2 + 3 + 4
        assert result["unique_files_touched"] == 6
        assert result["avg_changes_per_commit"] == 3.5  # 14 / 4

    def test_analyze_churn_identifies_hot_paths(self, sample_commits_data):
        """Test that hot paths are identified correctly"""
        result = analyze_code_churn(sample_commits_data)

        hot_paths = result["hot_paths"]
        assert len(hot_paths) > 0

        # /src/utils.py should be the hottest path (appears in 3 commits)
        hottest = hot_paths[0]
        assert hottest["path"] == "/src/utils.py"
        assert hottest["change_count"] == 3

    def test_analyze_churn_empty_commits(self):
        """Test churn analysis with no commits"""
        result = analyze_code_churn([])

        assert result["total_commits"] == 0
        assert result["total_file_changes"] == 0
        assert result["unique_files_touched"] == 0
        assert result["avg_changes_per_commit"] == 0
        assert result["hot_paths"] == []

    def test_analyze_churn_commits_with_no_files(self):
        """Test commits with no file changes"""
        commits = [
            {
                "commit_id": "commit1",
                "author": "Alice",
                "date": datetime(2026, 2, 1).isoformat(),
                "message": "Empty commit",
                "changes": 0,
                "files": [],
            }
        ]

        result = analyze_code_churn(commits)

        assert result["total_commits"] == 1
        assert result["total_file_changes"] == 0
        assert result["unique_files_touched"] == 0
        assert result["hot_paths"] == []

    def test_analyze_churn_respects_hot_paths_limit(self):
        """Test that hot paths limit is respected"""
        # Create commits with many unique files
        commits = []
        for i in range(30):
            commits.append(
                {
                    "commit_id": f"commit{i}",
                    "author": "Alice",
                    "date": datetime(2026, 2, 1).isoformat(),
                    "message": f"Commit {i}",
                    "changes": 1,
                    "files": [f"/src/file{i}.py"],
                }
            )

        with patch("execution.collectors.ado_risk_metrics.sampling_config") as mock_config:
            mock_config.HOT_PATHS_LIMIT = 20
            result = analyze_code_churn(commits)

        # Should limit to 20 hot paths
        assert len(result["hot_paths"]) == 20


# ============================================================================
# TESTS: calculate_knowledge_distribution
# ============================================================================


class TestCalculateKnowledgeDistribution:
    """Test knowledge distribution calculation"""

    def test_knowledge_distribution_basic(self, sample_commits_data):
        """Test basic knowledge distribution"""
        result = calculate_knowledge_distribution(sample_commits_data)

        assert result["total_files_analyzed"] == 6
        assert result["single_owner_count"] > 0
        assert result["two_owner_count"] >= 0
        assert result["multi_owner_count"] >= 0

    def test_knowledge_distribution_single_owner(self):
        """Test files with single owner"""
        commits = [
            {
                "commit_id": "c1",
                "author": "Alice",
                "date": datetime(2026, 2, 1).isoformat(),
                "message": "Add feature",
                "changes": 2,
                "files": ["/src/feature.py", "/tests/test_feature.py"],
            }
        ]

        result = calculate_knowledge_distribution(commits)

        assert result["total_files_analyzed"] == 2
        assert result["single_owner_count"] == 2
        assert result["single_owner_pct"] == 100.0

    def test_knowledge_distribution_two_owners(self):
        """Test files with exactly two owners"""
        commits = [
            {
                "commit_id": "c1",
                "author": "Alice",
                "date": datetime(2026, 2, 1).isoformat(),
                "message": "Add feature",
                "changes": 1,
                "files": ["/src/shared.py"],
            },
            {
                "commit_id": "c2",
                "author": "Bob",
                "date": datetime(2026, 2, 2).isoformat(),
                "message": "Update feature",
                "changes": 1,
                "files": ["/src/shared.py"],
            },
        ]

        result = calculate_knowledge_distribution(commits)

        assert result["total_files_analyzed"] == 1
        assert result["two_owner_count"] == 1
        assert result["single_owner_pct"] == 0.0

    def test_knowledge_distribution_multi_owners(self):
        """Test files with multiple owners"""
        commits = [
            {
                "commit_id": "c1",
                "author": "Alice",
                "date": datetime(2026, 2, 1).isoformat(),
                "message": "Update",
                "changes": 1,
                "files": ["/src/core.py"],
            },
            {
                "commit_id": "c2",
                "author": "Bob",
                "date": datetime(2026, 2, 2).isoformat(),
                "message": "Update",
                "changes": 1,
                "files": ["/src/core.py"],
            },
            {
                "commit_id": "c3",
                "author": "Charlie",
                "date": datetime(2026, 2, 3).isoformat(),
                "message": "Update",
                "changes": 1,
                "files": ["/src/core.py"],
            },
        ]

        result = calculate_knowledge_distribution(commits)

        assert result["total_files_analyzed"] == 1
        assert result["multi_owner_count"] == 1

    def test_knowledge_distribution_empty_commits(self):
        """Test with no commits"""
        result = calculate_knowledge_distribution([])

        assert result["total_files_analyzed"] == 0
        assert result["single_owner_count"] == 0
        assert result["single_owner_pct"] == 0

    def test_knowledge_distribution_limits_output(self):
        """Test that single_owner_files is limited to top 20"""
        commits = []
        for i in range(30):
            commits.append(
                {
                    "commit_id": f"c{i}",
                    "author": "Alice",
                    "date": datetime(2026, 2, 1).isoformat(),
                    "message": f"Commit {i}",
                    "changes": 1,
                    "files": [f"/src/file{i}.py"],
                }
            )

        result = calculate_knowledge_distribution(commits)

        assert result["single_owner_count"] == 30
        assert len(result["single_owner_files"]) == 20  # Limited to top 20

    def test_knowledge_distribution_unknown_author(self):
        """Test handling commits with Unknown author"""
        commits = [
            {
                "commit_id": "c1",
                "author": "Unknown",
                "date": datetime(2026, 2, 1).isoformat(),
                "message": "Update",
                "changes": 1,
                "files": ["/src/file.py"],
            }
        ]

        result = calculate_knowledge_distribution(commits)

        assert result["single_owner_count"] == 1
        assert result["single_owner_files"][0]["owner"] == "Unknown"


# ============================================================================
# TESTS: calculate_module_coupling
# ============================================================================


class TestCalculateModuleCoupling:
    """Test module coupling calculation"""

    def test_module_coupling_basic(self):
        """Test basic module coupling detection"""
        commits = [
            {
                "commit_id": "c1",
                "author": "Alice",
                "date": datetime(2026, 2, 1).isoformat(),
                "message": "Update A and B",
                "changes": 2,
                "files": ["/src/module_a.py", "/src/module_b.py"],
            },
            {
                "commit_id": "c2",
                "author": "Bob",
                "date": datetime(2026, 2, 2).isoformat(),
                "message": "Update A and B again",
                "changes": 2,
                "files": ["/src/module_a.py", "/src/module_b.py"],
            },
            {
                "commit_id": "c3",
                "author": "Charlie",
                "date": datetime(2026, 2, 3).isoformat(),
                "message": "Update A and B third time",
                "changes": 2,
                "files": ["/src/module_a.py", "/src/module_b.py"],
            },
        ]

        result = calculate_module_coupling(commits)

        assert result["total_coupled_pairs"] == 1
        assert len(result["top_coupled_pairs"]) == 1

        pair = result["top_coupled_pairs"][0]
        assert pair["co_change_count"] == 3
        assert {pair["file1"], pair["file2"]} == {
            "/src/module_a.py",
            "/src/module_b.py",
        }

    def test_module_coupling_multiple_pairs(self):
        """Test detecting multiple coupled pairs"""
        commits = [
            # A and B coupled (3 times)
            {
                "commit_id": "c1",
                "files": ["/src/a.py", "/src/b.py"],
                "author": "Alice",
                "date": datetime(2026, 2, 1).isoformat(),
                "message": "Update",
                "changes": 2,
            },
            {
                "commit_id": "c2",
                "files": ["/src/a.py", "/src/b.py"],
                "author": "Alice",
                "date": datetime(2026, 2, 2).isoformat(),
                "message": "Update",
                "changes": 2,
            },
            {
                "commit_id": "c3",
                "files": ["/src/a.py", "/src/b.py"],
                "author": "Alice",
                "date": datetime(2026, 2, 3).isoformat(),
                "message": "Update",
                "changes": 2,
            },
            # C and D coupled (4 times)
            {
                "commit_id": "c4",
                "files": ["/src/c.py", "/src/d.py"],
                "author": "Bob",
                "date": datetime(2026, 2, 4).isoformat(),
                "message": "Update",
                "changes": 2,
            },
            {
                "commit_id": "c5",
                "files": ["/src/c.py", "/src/d.py"],
                "author": "Bob",
                "date": datetime(2026, 2, 5).isoformat(),
                "message": "Update",
                "changes": 2,
            },
            {
                "commit_id": "c6",
                "files": ["/src/c.py", "/src/d.py"],
                "author": "Bob",
                "date": datetime(2026, 2, 6).isoformat(),
                "message": "Update",
                "changes": 2,
            },
            {
                "commit_id": "c7",
                "files": ["/src/c.py", "/src/d.py"],
                "author": "Bob",
                "date": datetime(2026, 2, 7).isoformat(),
                "message": "Update",
                "changes": 2,
            },
        ]

        result = calculate_module_coupling(commits)

        assert result["total_coupled_pairs"] == 2

        # Should be sorted by co-change count (descending)
        assert result["top_coupled_pairs"][0]["co_change_count"] == 4
        assert result["top_coupled_pairs"][1]["co_change_count"] == 3

    def test_module_coupling_filters_weak_coupling(self):
        """Test that pairs with less than 3 co-changes are filtered"""
        commits = [
            {
                "commit_id": "c1",
                "files": ["/src/a.py", "/src/b.py"],
                "author": "Alice",
                "date": datetime(2026, 2, 1).isoformat(),
                "message": "Update",
                "changes": 2,
            },
            {
                "commit_id": "c2",
                "files": ["/src/a.py", "/src/b.py"],
                "author": "Alice",
                "date": datetime(2026, 2, 2).isoformat(),
                "message": "Update",
                "changes": 2,
            },
            # Only 2 co-changes - should be filtered
        ]

        result = calculate_module_coupling(commits)

        assert result["total_coupled_pairs"] == 0
        assert result["top_coupled_pairs"] == []

    def test_module_coupling_single_file_commits(self):
        """Test that single-file commits don't create coupling"""
        commits = [
            {
                "commit_id": "c1",
                "files": ["/src/a.py"],
                "author": "Alice",
                "date": datetime(2026, 2, 1).isoformat(),
                "message": "Update",
                "changes": 1,
            }
        ]

        result = calculate_module_coupling(commits)

        assert result["total_coupled_pairs"] == 0

    def test_module_coupling_empty_commits(self):
        """Test with no commits"""
        result = calculate_module_coupling([])

        assert result["total_coupled_pairs"] == 0
        assert result["top_coupled_pairs"] == []

    def test_module_coupling_limits_output(self):
        """Test that output is limited to top 20 pairs"""
        commits = []
        # Create 30 unique coupled pairs
        for i in range(30):
            for _ in range(3):  # Each pair appears 3 times
                commits.append(
                    {
                        "commit_id": f"c{i}_{_}",
                        "files": [f"/src/file{i}_a.py", f"/src/file{i}_b.py"],
                        "author": "Alice",
                        "date": datetime(2026, 2, 1).isoformat(),
                        "message": "Update",
                        "changes": 2,
                    }
                )

        result = calculate_module_coupling(commits)

        assert result["total_coupled_pairs"] == 30
        assert len(result["top_coupled_pairs"]) == 20  # Limited to top 20

    def test_module_coupling_three_file_commit(self):
        """Test commits with 3 files create multiple pairs"""
        commits = [
            {
                "commit_id": "c1",
                "files": ["/src/a.py", "/src/b.py", "/src/c.py"],
                "author": "Alice",
                "date": datetime(2026, 2, 1).isoformat(),
                "message": "Update",
                "changes": 3,
            },
            {
                "commit_id": "c2",
                "files": ["/src/a.py", "/src/b.py", "/src/c.py"],
                "author": "Alice",
                "date": datetime(2026, 2, 2).isoformat(),
                "message": "Update",
                "changes": 3,
            },
            {
                "commit_id": "c3",
                "files": ["/src/a.py", "/src/b.py", "/src/c.py"],
                "author": "Alice",
                "date": datetime(2026, 2, 3).isoformat(),
                "message": "Update",
                "changes": 3,
            },
        ]

        result = calculate_module_coupling(commits)

        # 3 files should create 3 pairs: (a,b), (a,c), (b,c)
        assert result["total_coupled_pairs"] == 3


# ============================================================================
# TESTS: collect_risk_metrics_for_project
# ============================================================================


class TestCollectRiskMetricsForProject:
    """Test risk metrics collection for a project"""

    def test_collect_metrics_success(self, sample_commits_data):
        """Test successfully collecting metrics for a project"""
        # Mock connection and clients
        connection = Mock()
        git_client = Mock()
        wit_client = Mock()
        connection.clients.get_git_client.return_value = git_client
        connection.clients.get_work_item_tracking_client.return_value = wit_client

        # Mock repositories
        repo1 = Mock()
        repo1.id = "repo1"
        repo1.name = "MainRepo"

        git_client.get_repositories.return_value = [repo1]

        # Mock commits
        with patch(
            "execution.collectors.ado_risk_metrics.query_recent_commits",
            return_value=sample_commits_data,
        ):
            project = {
                "project_name": "Test Project",
                "project_key": "test-project",
                "ado_project_name": "TestProject",
            }
            config = {"lookback_days": 90}

            result = collect_risk_metrics_for_project(connection, project, config)

        assert result["project_key"] == "test-project"
        assert result["project_name"] == "Test Project"
        assert result["repository_count"] == 1
        assert "code_churn" in result
        assert "knowledge_distribution" in result
        assert "module_coupling" in result
        assert "collected_at" in result

    def test_collect_metrics_no_repos(self):
        """Test collecting metrics when no repositories exist"""
        connection = Mock()
        git_client = Mock()
        wit_client = Mock()
        connection.clients.get_git_client.return_value = git_client
        connection.clients.get_work_item_tracking_client.return_value = wit_client

        git_client.get_repositories.return_value = []

        project = {
            "project_name": "Empty Project",
            "project_key": "empty-project",
            "ado_project_name": "EmptyProject",
        }
        config = {"lookback_days": 90}

        result = collect_risk_metrics_for_project(connection, project, config)

        assert result["repository_count"] == 0
        assert result["code_churn"]["total_commits"] == 0

    def test_collect_metrics_repo_error(self):
        """Test handling repository API errors"""
        connection = Mock()
        git_client = Mock()
        wit_client = Mock()
        connection.clients.get_git_client.return_value = git_client
        connection.clients.get_work_item_tracking_client.return_value = wit_client

        git_client.get_repositories.side_effect = create_azure_error("API Error")

        project = {
            "project_name": "Error Project",
            "project_key": "error-project",
            "ado_project_name": "ErrorProject",
        }
        config = {"lookback_days": 90}

        result = collect_risk_metrics_for_project(connection, project, config)

        assert result["repository_count"] == 0

    def test_collect_metrics_multiple_repos(self, sample_commits_data):
        """Test collecting metrics across multiple repositories"""
        connection = Mock()
        git_client = Mock()
        wit_client = Mock()
        connection.clients.get_git_client.return_value = git_client
        connection.clients.get_work_item_tracking_client.return_value = wit_client

        repo1 = Mock()
        repo1.id = "repo1"
        repo1.name = "Repo1"

        repo2 = Mock()
        repo2.id = "repo2"
        repo2.name = "Repo2"

        git_client.get_repositories.return_value = [repo1, repo2]

        with patch(
            "execution.collectors.ado_risk_metrics.query_recent_commits",
            return_value=sample_commits_data,
        ):
            project = {
                "project_name": "Multi Repo Project",
                "project_key": "multi-repo",
                "ado_project_name": "MultiRepo",
            }
            config = {"lookback_days": 90}

            result = collect_risk_metrics_for_project(connection, project, config)

        assert result["repository_count"] == 2
        # Should aggregate commits from both repos
        assert result["code_churn"]["total_commits"] == 8  # 4 commits * 2 repos


# ============================================================================
# TESTS: save_risk_metrics
# ============================================================================


class TestSaveRiskMetrics:
    """Test saving risk metrics to history file"""

    def test_save_new_history_file(self, temp_history_file):
        """Test creating new history file"""
        metrics = {
            "week_date": "2026-02-07",
            "week_number": 6,
            "projects": [
                {
                    "project_key": "test-project",
                    "project_name": "Test Project",
                    "code_churn": {
                        "total_commits": 10,
                        "total_file_changes": 50,
                        "unique_files_touched": 20,
                        "hot_paths": [],
                        "avg_changes_per_commit": 5.0,
                    },
                    "repository_count": 2,
                }
            ],
            "config": {"lookback_days": 90},
        }

        result = save_risk_metrics(metrics, str(temp_history_file))

        assert result is True
        assert temp_history_file.exists()

        # Verify contents
        with open(temp_history_file) as f:
            history = json.load(f)

        assert "weeks" in history
        assert len(history["weeks"]) == 1
        assert history["weeks"][0] == metrics

    def test_save_append_to_existing(self, temp_history_file):
        """Test appending to existing history"""
        # Create existing history
        existing = {
            "weeks": [
                {
                    "week_date": "2026-01-31",
                    "projects": [{"project_key": "old", "code_churn": {"total_commits": 5}}],
                }
            ]
        }
        temp_history_file.write_text(json.dumps(existing))

        # Add new week
        new_metrics = {
            "week_date": "2026-02-07",
            "projects": [{"project_key": "new", "code_churn": {"total_commits": 10}}],
        }

        result = save_risk_metrics(new_metrics, str(temp_history_file))

        assert result is True

        # Verify both weeks present
        with open(temp_history_file) as f:
            history = json.load(f)

        assert len(history["weeks"]) == 2
        assert history["weeks"][0]["week_date"] == "2026-01-31"
        assert history["weeks"][1]["week_date"] == "2026-02-07"

    def test_save_limits_to_52_weeks(self, temp_history_file):
        """Test that history is limited to last 52 weeks"""
        # Create history with 60 weeks
        existing = {"weeks": [{"week_date": f"2025-{i:02d}-01"} for i in range(1, 61)]}
        temp_history_file.write_text(json.dumps(existing))

        # Add one more week with valid data
        new_metrics = {
            "week_date": "2026-02-07",
            "projects": [{"project_key": "test", "code_churn": {"total_commits": 10}, "repository_count": 1}],
        }

        save_risk_metrics(new_metrics, str(temp_history_file))

        # Should keep only last 52 (60 existing + 1 new = 61, then trim to 52)
        with open(temp_history_file) as f:
            history = json.load(f)

        assert len(history["weeks"]) == 52
        assert history["weeks"][-1]["week_date"] == "2026-02-07"

    def test_save_rejects_empty_projects(self, temp_history_file):
        """Test that metrics with no projects are rejected"""
        metrics = {
            "week_date": "2026-02-07",
            "projects": [],  # Empty
        }

        result = save_risk_metrics(metrics, str(temp_history_file))

        assert result is False
        assert not temp_history_file.exists()

    def test_save_rejects_all_zero_data(self, temp_history_file):
        """Test that metrics with all zeros are rejected"""
        metrics = {
            "week_date": "2026-02-07",
            "projects": [
                {
                    "project_key": "test",
                    "code_churn": {
                        "total_commits": 0,
                        "unique_files_touched": 0,
                    },
                    "repository_count": 0,
                }
            ],
        }

        result = save_risk_metrics(metrics, str(temp_history_file))

        assert result is False
        assert not temp_history_file.exists()

    def test_save_accepts_partial_zero_data(self, temp_history_file):
        """Test that metrics with some valid data are accepted"""
        metrics = {
            "week_date": "2026-02-07",
            "projects": [
                {
                    "project_key": "test1",
                    "code_churn": {"total_commits": 10},
                    "repository_count": 1,
                },
                {
                    "project_key": "test2",
                    "code_churn": {"total_commits": 0},
                    "repository_count": 0,
                },
            ],
        }

        result = save_risk_metrics(metrics, str(temp_history_file))

        assert result is True

    def test_save_handles_corrupted_file(self, temp_history_file):
        """Test handling corrupted existing history file"""
        # Write invalid JSON
        temp_history_file.write_text("not valid json")

        metrics = {
            "week_date": "2026-02-07",
            "projects": [{"project_key": "test", "code_churn": {"total_commits": 10}}],
        }

        # Should recover and create new history
        result = save_risk_metrics(metrics, str(temp_history_file))

        assert result is True

        with open(temp_history_file) as f:
            history = json.load(f)

        assert len(history["weeks"]) == 1

    def test_save_handles_invalid_structure(self, temp_history_file):
        """Test handling existing file with invalid structure"""
        # Write valid JSON but wrong structure
        temp_history_file.write_text(json.dumps({"invalid": "structure"}))

        metrics = {
            "week_date": "2026-02-07",
            "projects": [{"project_key": "test", "code_churn": {"total_commits": 10}}],
        }

        result = save_risk_metrics(metrics, str(temp_history_file))

        assert result is True

        with open(temp_history_file) as f:
            history = json.load(f)

        # Should recreate with correct structure
        assert "weeks" in history
        assert len(history["weeks"]) == 1
