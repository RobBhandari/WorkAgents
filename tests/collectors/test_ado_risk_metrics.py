#!/usr/bin/env python3
"""
Tests for ADO Delivery Risk Metrics Collector

Verifies risk metrics collection and analysis:
- File path extraction from REST API changes
- Commit data building
- Code churn analysis
- Knowledge distribution calculation
- Module coupling detection
- History stripping for persistence
- Data validation
- Save logic with atomic writes
- Collector orchestration
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from execution.collectors.ado_risk_metrics import (
    RiskCollector,
    _build_commit_data,
    _extract_file_paths_from_changes,
    _fetch_commit_changes,
    _strip_detail_lists_for_history,
    _validate_risk_data,
    analyze_code_churn,
    calculate_knowledge_distribution,
    calculate_module_coupling,
    collect_risk_metrics_for_project,
    query_recent_commits,
    save_risk_metrics,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_changes_response() -> dict:
    """Sample Git changes REST API response"""
    return {
        "changes": [
            {"item": {"path": "/src/main.py"}},
            {"item": {"path": "/src/utils.py"}},
            {"item": {"path": "/tests/test_main.py"}},
        ]
    }


@pytest.fixture
def sample_commit() -> dict:
    """Sample transformed commit dict"""
    return {
        "commit_id": "abc12345def67890",
        "author_name": "Alice",
        "author_date": "2026-03-10T10:00:00Z",
        "comment": "fix: resolve edge case",
    }


@pytest.fixture
def sample_commits() -> list[dict]:
    """Sample list of commit data dicts for analysis functions"""
    return [
        {
            "commit_id": "aaa",
            "author": "Alice",
            "date": "2026-03-10",
            "message": "feat: add module",
            "changes": 3,
            "files": ["/src/a.py", "/src/b.py", "/src/c.py"],
        },
        {
            "commit_id": "bbb",
            "author": "Bob",
            "date": "2026-03-11",
            "message": "fix: bug",
            "changes": 2,
            "files": ["/src/a.py", "/src/b.py"],
        },
        {
            "commit_id": "ccc",
            "author": "Alice",
            "date": "2026-03-12",
            "message": "refactor: clean up",
            "changes": 1,
            "files": ["/src/a.py"],
        },
        {
            "commit_id": "ddd",
            "author": "Alice",
            "date": "2026-03-13",
            "message": "feat: new feature",
            "changes": 2,
            "files": ["/src/a.py", "/src/b.py"],
        },
    ]


@pytest.fixture
def sample_project() -> dict:
    """Sample project metadata from discovery"""
    return {
        "project_name": "TestProject",
        "project_key": "TP",
        "ado_project_name": "TestProject",
    }


@pytest.fixture
def sample_risk_metrics() -> dict:
    """Sample week metrics for save_risk_metrics"""
    return {
        "week_date": "2026-03-15",
        "week_number": 11,
        "projects": [
            {
                "project_key": "TP",
                "project_name": "TestProject",
                "code_churn": {
                    "total_commits": 10,
                    "total_file_changes": 25,
                    "unique_files_touched": 8,
                    "hot_paths": [{"path": "/src/a.py", "change_count": 5}],
                    "avg_changes_per_commit": 2.5,
                },
                "knowledge_distribution": {
                    "total_files_analyzed": 8,
                    "single_owner_count": 3,
                    "two_owner_count": 2,
                    "multi_owner_count": 3,
                    "single_owner_pct": 37.5,
                    "single_owner_files": [{"path": "/src/x.py", "owner": "Alice"}],
                },
                "module_coupling": {
                    "total_coupled_pairs": 1,
                    "top_coupled_pairs": [{"file1": "/src/a.py", "file2": "/src/b.py", "co_change_count": 4}],
                    "note": "Pairs that changed together 3+ times",
                },
                "repository_count": 2,
                "collected_at": "2026-03-15T10:00:00",
            }
        ],
        "config": {"lookback_days": 90},
    }


# ---------------------------------------------------------------------------
# _extract_file_paths_from_changes
# ---------------------------------------------------------------------------


class TestExtractFilePathsFromChanges:
    def test_valid_changes(self, sample_changes_response):
        result = _extract_file_paths_from_changes(sample_changes_response)
        assert result == ["/src/main.py", "/src/utils.py", "/tests/test_main.py"]

    def test_empty_changes(self):
        assert _extract_file_paths_from_changes({"changes": []}) == []

    def test_none_input(self):
        assert _extract_file_paths_from_changes(None) == []  # type: ignore[arg-type]

    def test_missing_changes_key(self):
        assert _extract_file_paths_from_changes({"other": "data"}) == []

    def test_malformed_items(self):
        """Items missing 'item' or 'path' are skipped"""
        changes = {
            "changes": [
                {"item": None},
                {"other": "data"},
                {"item": {"no_path": True}},
                {"item": {"path": "/valid.py"}},
            ]
        }
        assert _extract_file_paths_from_changes(changes) == ["/valid.py"]


# ---------------------------------------------------------------------------
# _build_commit_data
# ---------------------------------------------------------------------------


class TestBuildCommitData:
    def test_full_commit(self, sample_commit):
        result = _build_commit_data(sample_commit, changes=3, files=["/a.py", "/b.py"])
        assert result["commit_id"] == "abc12345def67890"
        assert result["author"] == "Alice"
        assert result["date"] == "2026-03-10T10:00:00Z"
        assert result["message"] == "fix: resolve edge case"
        assert result["changes"] == 3
        assert result["files"] == ["/a.py", "/b.py"]

    def test_defaults(self):
        result = _build_commit_data({})
        assert result["commit_id"] is None
        assert result["author"] == "Unknown"
        assert result["changes"] == 0
        assert result["files"] == []

    def test_files_none_defaults_to_empty(self, sample_commit):
        result = _build_commit_data(sample_commit, files=None)
        assert result["files"] == []


# ---------------------------------------------------------------------------
# analyze_code_churn
# ---------------------------------------------------------------------------


class TestAnalyzeCodeChurn:
    def test_basic_churn(self, sample_commits):
        result = analyze_code_churn(sample_commits)
        assert result["total_commits"] == 4
        assert result["total_file_changes"] == 8  # 3+2+1+2
        assert result["unique_files_touched"] == 3  # a, b, c
        assert result["avg_changes_per_commit"] == 2.0
        # hot_paths should have a.py as top (4 changes)
        assert result["hot_paths"][0]["path"] == "/src/a.py"
        assert result["hot_paths"][0]["change_count"] == 4

    def test_empty_commits(self):
        result = analyze_code_churn([])
        assert result["total_commits"] == 0
        assert result["total_file_changes"] == 0
        assert result["avg_changes_per_commit"] == 0


# ---------------------------------------------------------------------------
# calculate_knowledge_distribution
# ---------------------------------------------------------------------------


class TestCalculateKnowledgeDistribution:
    def test_distribution(self, sample_commits):
        result = calculate_knowledge_distribution(sample_commits)
        # /src/c.py only touched by Alice -> single owner
        assert result["single_owner_count"] >= 1
        # /src/a.py touched by Alice and Bob -> two owners
        assert result["two_owner_count"] >= 1
        assert result["total_files_analyzed"] == 3

    def test_empty_commits(self):
        result = calculate_knowledge_distribution([])
        assert result["total_files_analyzed"] == 0
        assert result["single_owner_pct"] == 0

    def test_single_author_all_files(self):
        commits = [
            {"author": "Solo", "files": ["/x.py", "/y.py"]},
            {"author": "Solo", "files": ["/y.py", "/z.py"]},
        ]
        result = calculate_knowledge_distribution(commits)
        assert result["single_owner_count"] == 3
        assert result["single_owner_pct"] == 100.0


# ---------------------------------------------------------------------------
# calculate_module_coupling
# ---------------------------------------------------------------------------


class TestCalculateModuleCoupling:
    def test_coupling_detected(self, sample_commits):
        result = calculate_module_coupling(sample_commits)
        # a.py and b.py change together in 3 commits (aaa, bbb, ddd) -> co_change_count=3
        assert result["total_coupled_pairs"] >= 1
        top = result["top_coupled_pairs"][0]
        assert top["file1"] == "/src/a.py"
        assert top["file2"] == "/src/b.py"
        assert top["co_change_count"] == 3

    def test_no_coupling_below_threshold(self):
        """Pairs changed together fewer than 3 times are excluded"""
        commits = [
            {"files": ["/a.py", "/b.py"]},
            {"files": ["/a.py", "/b.py"]},
            {"files": ["/c.py"]},
        ]
        result = calculate_module_coupling(commits)
        assert result["total_coupled_pairs"] == 0

    def test_empty_commits(self):
        result = calculate_module_coupling([])
        assert result["total_coupled_pairs"] == 0

    def test_single_file_commits(self):
        """Commits with one file produce no pairs"""
        commits = [{"files": ["/a.py"]}, {"files": ["/b.py"]}]
        result = calculate_module_coupling(commits)
        assert result["total_coupled_pairs"] == 0


# ---------------------------------------------------------------------------
# _strip_detail_lists_for_history
# ---------------------------------------------------------------------------


class TestStripDetailListsForHistory:
    def test_strips_fields(self, sample_risk_metrics):
        project = sample_risk_metrics["projects"][0]
        stripped = _strip_detail_lists_for_history(project)
        assert "hot_paths" not in stripped["code_churn"]
        assert "single_owner_files" not in stripped["knowledge_distribution"]
        assert "top_coupled_pairs" not in stripped["module_coupling"]

    def test_preserves_aggregates(self, sample_risk_metrics):
        project = sample_risk_metrics["projects"][0]
        stripped = _strip_detail_lists_for_history(project)
        assert stripped["code_churn"]["total_commits"] == 10
        assert stripped["knowledge_distribution"]["single_owner_count"] == 3
        assert stripped["module_coupling"]["total_coupled_pairs"] == 1

    def test_does_not_mutate_original(self, sample_risk_metrics):
        project = sample_risk_metrics["projects"][0]
        _strip_detail_lists_for_history(project)
        assert "hot_paths" in project["code_churn"]


# ---------------------------------------------------------------------------
# _validate_risk_data
# ---------------------------------------------------------------------------


class TestValidateRiskData:
    def test_valid_data(self, sample_risk_metrics):
        result = _validate_risk_data(sample_risk_metrics)
        assert result is not None
        assert len(result) == 1

    def test_empty_projects(self):
        assert _validate_risk_data({"projects": []}) is None

    def test_missing_projects_key(self):
        assert _validate_risk_data({}) is None

    def test_all_zero_data(self):
        metrics = {
            "projects": [
                {
                    "code_churn": {"total_commits": 0, "unique_files_touched": 0},
                    "repository_count": 0,
                }
            ]
        }
        assert _validate_risk_data(metrics) is None


# ---------------------------------------------------------------------------
# save_risk_metrics
# ---------------------------------------------------------------------------


class TestSaveRiskMetrics:
    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("os.makedirs")
    def test_save_success(self, mock_makedirs, mock_save, mock_load, sample_risk_metrics, tmp_path):
        mock_load.return_value = {"weeks": []}
        output = str(tmp_path / "risk_history.json")

        result = save_risk_metrics(sample_risk_metrics, output_file=output)

        assert result is True
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["weeks"]) == 1
        # Verify stripping happened
        assert "hot_paths" not in saved_data["weeks"][0]["projects"][0]["code_churn"]

    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("os.makedirs")
    def test_save_appends_to_history(self, mock_makedirs, mock_save, mock_load, sample_risk_metrics, tmp_path):
        mock_load.return_value = {"weeks": [{"week_date": "2026-03-08"}]}
        output = str(tmp_path / "risk_history.json")

        save_risk_metrics(sample_risk_metrics, output_file=output)

        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["weeks"]) == 2

    def test_save_returns_false_on_empty_projects(self):
        result = save_risk_metrics({"projects": []})
        assert result is False

    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("os.makedirs")
    def test_save_trims_to_52_weeks(self, mock_makedirs, mock_save, mock_load, sample_risk_metrics, tmp_path):
        mock_load.return_value = {"weeks": [{"week_date": f"w{i}"} for i in range(52)]}
        output = str(tmp_path / "risk_history.json")

        save_risk_metrics(sample_risk_metrics, output_file=output)

        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["weeks"]) == 52  # trimmed from 53

    @patch("execution.utils_atomic_json.load_json_with_recovery")
    @patch("execution.utils_atomic_json.atomic_json_save")
    @patch("os.makedirs")
    def test_save_handles_corrupted_history(self, mock_makedirs, mock_save, mock_load, sample_risk_metrics, tmp_path):
        """Invalid existing history is recreated"""
        mock_load.return_value = "not a dict"
        output = str(tmp_path / "risk_history.json")

        result = save_risk_metrics(sample_risk_metrics, output_file=output)

        assert result is True
        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["weeks"]) == 1


# ---------------------------------------------------------------------------
# _fetch_commit_changes (async)
# ---------------------------------------------------------------------------


class TestFetchCommitChanges:
    @pytest.mark.asyncio
    async def test_success(self, sample_changes_response):
        client = AsyncMock()
        client.get_changes.return_value = sample_changes_response

        count, paths = await _fetch_commit_changes(client, "abc123", "repo1", "proj")

        assert count == 3
        assert paths == ["/src/main.py", "/src/utils.py", "/tests/test_main.py"]

    @pytest.mark.asyncio
    async def test_api_error_returns_defaults(self):
        client = AsyncMock()
        client.get_changes.side_effect = Exception("timeout")

        count, paths = await _fetch_commit_changes(client, "abc123", "repo1", "proj")

        assert count == 0
        assert paths == []


# ---------------------------------------------------------------------------
# query_recent_commits (async)
# ---------------------------------------------------------------------------


class TestQueryRecentCommits:
    @pytest.mark.asyncio
    @patch("execution.collectors.ado_risk_metrics.GitTransformer")
    async def test_returns_commits(self, mock_transformer):
        client = AsyncMock()
        client.get_commits.return_value = {"value": []}
        mock_transformer.transform_commits_response.return_value = [
            {"commit_id": "aaa", "author_name": "A", "author_date": "d", "comment": "m"},
        ]
        client.get_changes.return_value = {"changes": [{"item": {"path": "/f.py"}}]}

        result = await query_recent_commits(client, "proj", "repo1", days=7)

        assert len(result) == 1
        assert result[0]["commit_id"] == "aaa"
        assert result[0]["files"] == ["/f.py"]

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_risk_metrics.GitTransformer")
    async def test_api_error_returns_empty(self, mock_transformer):
        client = AsyncMock()
        client.get_commits.side_effect = Exception("network error")

        result = await query_recent_commits(client, "proj", "repo1")

        assert result == []


# ---------------------------------------------------------------------------
# collect_risk_metrics_for_project (async)
# ---------------------------------------------------------------------------


class TestCollectRiskMetricsForProject:
    @pytest.mark.asyncio
    @patch("execution.collectors.ado_risk_metrics.GitTransformer")
    async def test_collects_and_aggregates(self, mock_transformer, sample_project):
        client = AsyncMock()
        client.get_repositories.return_value = {"value": []}
        mock_transformer.transform_repositories_response.return_value = [
            {"id": "repo1", "name": "Repo1"},
        ]
        # Return empty commits list for simplicity
        client.get_commits.return_value = {"value": []}
        mock_transformer.transform_commits_response.return_value = []

        result = await collect_risk_metrics_for_project(client, sample_project, {"lookback_days": 30})

        assert result["project_key"] == "TP"
        assert result["project_name"] == "TestProject"
        assert result["repository_count"] == 1
        assert "code_churn" in result
        assert "knowledge_distribution" in result
        assert "module_coupling" in result

    @pytest.mark.asyncio
    @patch("execution.collectors.ado_risk_metrics.GitTransformer")
    async def test_handles_repo_fetch_error(self, mock_transformer, sample_project):
        client = AsyncMock()
        client.get_repositories.side_effect = Exception("forbidden")

        result = await collect_risk_metrics_for_project(client, sample_project, {})

        assert result["repository_count"] == 0
        assert result["code_churn"]["total_commits"] == 0


# ---------------------------------------------------------------------------
# RiskCollector orchestration
# ---------------------------------------------------------------------------


class TestRiskCollector:
    @patch("execution.collectors.ado_risk_metrics.save_risk_metrics", return_value=True)
    @patch("execution.collectors.ado_risk_metrics.collect_risk_metrics_for_project")
    @patch("execution.collectors.ado_risk_metrics.track_collector_performance")
    @pytest.mark.asyncio
    async def test_run_success(self, mock_tracker, mock_collect, mock_save):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = Mock(return_value=mock_ctx)
        mock_ctx.__exit__ = Mock(return_value=None)
        mock_tracker.return_value = mock_ctx

        mock_collect.return_value = {
            "project_key": "TP",
            "project_name": "TestProject",
            "code_churn": {"total_commits": 5, "unique_files_touched": 3},
            "knowledge_distribution": {"single_owner_count": 1},
            "module_coupling": {"total_coupled_pairs": 0},
            "repository_count": 1,
        }

        collector = RiskCollector()
        with patch.object(
            collector._base,
            "load_discovery_data",
            return_value={"projects": [{"project_name": "TestProject", "project_key": "TP"}]},
        ):
            with patch.object(collector._base, "get_rest_client", return_value=AsyncMock()):
                result = await collector.run()

        assert result is True
        mock_save.assert_called_once()

    @patch("execution.collectors.ado_risk_metrics.track_collector_performance")
    @pytest.mark.asyncio
    async def test_run_no_projects(self, mock_tracker):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = Mock(return_value=mock_ctx)
        mock_ctx.__exit__ = Mock(return_value=None)
        mock_tracker.return_value = mock_ctx

        collector = RiskCollector()
        with patch.object(collector._base, "load_discovery_data", return_value={"projects": []}):
            result = await collector.run()

        assert result is False
