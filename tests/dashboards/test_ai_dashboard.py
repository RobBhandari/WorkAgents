"""
Tests for AI Contributions Dashboard

Tests the refactored AI dashboard generator.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from execution.dashboards.ai import (
    _build_context,
    _calculate_summary,
    _get_author_stats_from_prs,
    _get_project_stats_from_prs,
    _load_devin_analysis,
    _query_pr_data,
    generate_ai_dashboard,
)


class TestDataLoaders:
    """Tests for data loading functions"""

    def test_load_devin_analysis_success(self, tmp_path, monkeypatch):
        """Test successful loading of Devin analysis"""
        # Create mock analysis file
        analysis_data = {
            "summary": {
                "total_prs": 100,
                "devin_prs": 30,
                "human_prs": 70,
                "devin_percentage": 30.0,
            },
            "devin_prs": [],
        }

        # Create temp directory structure
        temp_observatory = tmp_path / ".tmp" / "observatory"
        temp_observatory.mkdir(parents=True)
        analysis_file = temp_observatory / "devin_analysis.json"
        analysis_file.write_text(json.dumps(analysis_data))

        # Change to temp directory so relative paths work
        import os

        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            result = _load_devin_analysis()
            assert result["summary"]["total_prs"] == 100
            assert result["summary"]["devin_prs"] == 30
        finally:
            os.chdir(original_cwd)

    def test_load_devin_analysis_not_found(self, monkeypatch):
        """Test error handling when analysis file doesn't exist"""
        monkeypatch.setattr("os.path.exists", lambda x: False)

        with pytest.raises(FileNotFoundError) as exc_info:
            _load_devin_analysis()

        assert "Devin analysis file not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_pr_data_success(self, tmp_path, monkeypatch):
        """Test successful querying of PR data from API"""
        # Create mock project discovery file
        discovery_data = {
            "projects": [
                {
                    "project_name": "TestProject",
                    "ado_project_name": "TestProject",
                }
            ]
        }

        # Create temp directory structure
        temp_observatory = tmp_path / ".tmp" / "observatory"
        temp_observatory.mkdir(parents=True)
        discovery_file = temp_observatory / "ado_structure.json"
        discovery_file.write_text(json.dumps(discovery_data))

        # Change to temp directory so relative paths work
        import os

        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            # Mock the REST client and query functions
            from unittest.mock import AsyncMock, MagicMock

            mock_client = MagicMock()
            mock_client.get_repositories = AsyncMock(return_value={"value": [{"id": "repo1", "name": "TestRepo"}]})

            monkeypatch.setattr("execution.dashboards.ai.get_ado_rest_client", lambda: mock_client)
            monkeypatch.setattr(
                "execution.dashboards.ai.GitTransformer.transform_repositories_response",
                lambda x: [{"id": "repo1", "name": "TestRepo"}],
            )
            monkeypatch.setattr(
                "execution.dashboards.ai.query_pull_requests",
                AsyncMock(return_value=[{"pr_id": 1, "created_by": "Alice"}]),
            )

            result = await _query_pr_data()
            assert isinstance(result, list)
            assert len(result) > 0
            assert result[0]["project_name"] == "TestProject"
        finally:
            os.chdir(original_cwd)

    def test_query_pr_data_no_discovery(self, monkeypatch):
        """Test error handling when project discovery file doesn't exist"""
        monkeypatch.setattr("pathlib.Path.exists", lambda x: False)

        import asyncio

        with pytest.raises(FileNotFoundError):
            asyncio.run(_query_pr_data())


class TestStatsCalculation:
    """Tests for statistics calculation functions"""

    def test_get_author_stats_from_prs(self):
        """Test author statistics calculation from PR data"""
        pr_data = [
            {"created_by": "Alice"},
            {"created_by": "Bob"},
            {"created_by": "Alice"},
            {"created_by": "Devin AI"},
        ]

        result = _get_author_stats_from_prs(pr_data)
        assert result["Alice"] == 2
        assert result["Bob"] == 1
        assert result["Devin AI"] == 1

    def test_get_author_stats_from_prs_no_data(self):
        """Test author stats with no data"""
        assert _get_author_stats_from_prs([]) == {}

    def test_get_project_stats_from_prs(self):
        """Test project statistics calculation from PR data"""
        pr_data = [
            {"project_name": "ProjectA", "created_by": "Alice"},
            {"project_name": "ProjectA", "created_by": "Devin AI"},
            {"project_name": "ProjectA", "created_by": "Bob"},
            {"project_name": "ProjectB", "created_by": "devin integration"},
            {"project_name": "ProjectB", "created_by": "Charlie"},
        ]

        result = _get_project_stats_from_prs(pr_data)
        assert result["ProjectA"]["total"] == 3
        assert result["ProjectA"]["devin"] == 1
        assert result["ProjectB"]["total"] == 2
        assert result["ProjectB"]["devin"] == 1

    def test_get_project_stats_from_prs_no_data(self):
        """Test project stats with no data"""
        assert _get_project_stats_from_prs([]) == {}

    def test_calculate_summary(self):
        """Test summary statistics calculation"""
        analysis = {
            "summary": {
                "total_prs": 150,
                "devin_prs": 45,
                "human_prs": 105,
                "devin_percentage": 30.0,
            }
        }
        author_stats = {"Alice": 50, "Bob": 30, "Devin AI": 45}
        project_stats = {
            "ProjectA": {"total": 80, "devin": 20},
            "ProjectB": {"total": 70, "devin": 25},
        }

        result = _calculate_summary(analysis, author_stats, project_stats)

        assert result["total_prs"] == 150
        assert result["devin_prs"] == 45
        assert result["human_prs"] == 105
        assert result["devin_percentage"] == 30.0
        assert result["author_count"] == 3
        assert result["project_count"] == 2


class TestContextBuilder:
    """Tests for template context building"""

    def test_build_context_structure(self):
        """Test that context has all required fields"""
        analysis = {
            "summary": {
                "total_prs": 100,
                "devin_prs": 30,
                "human_prs": 70,
                "devin_percentage": 30.0,
            },
            "devin_prs": [
                {
                    "pr_id": 123,
                    "project": "TestProject",
                    "title": "Test PR",
                    "created_by": "Devin AI",
                    "commit_count": 5,
                    "created_date": "2026-01-15T10:00:00",
                }
            ],
        }

        author_stats = {"Alice": 50, "Devin AI": 30}
        project_stats = {"ProjectA": {"total": 100, "devin": 30}}
        summary_stats = {
            "total_prs": 100,
            "devin_prs": 30,
            "human_prs": 70,
            "devin_percentage": 30.0,
            "author_count": 2,
            "project_count": 1,
        }

        context = _build_context(analysis, author_stats, project_stats, summary_stats)

        # Check required fields
        assert "framework_css" in context
        assert "framework_js" in context
        assert "summary_stats" in context
        assert "author_labels" in context
        assert "author_counts" in context
        assert "project_items" in context
        assert "recent_prs" in context

    def test_build_context_chart_data(self):
        """Test chart data formatting"""
        analysis: dict[str, object] = {"summary": {}, "devin_prs": []}
        author_stats = {"Alice": 50, "Bob": 30, "Charlie": 20}
        project_stats: dict[str, dict[str, int]] = {}
        summary_stats = {
            "total_prs": 100,
            "devin_prs": 0,
            "human_prs": 100,
            "devin_percentage": 0,
            "author_count": 3,
            "project_count": 0,
        }

        context = _build_context(analysis, author_stats, project_stats, summary_stats)

        # Check author chart data (should be sorted by count, descending)
        assert len(context["author_labels"]) == 3
        assert context["author_labels"][0] == "Alice"  # Highest count
        assert context["author_counts"][0] == 50

    def test_build_context_recent_prs(self):
        """Test recent PRs formatting"""
        analysis = {
            "summary": {},
            "devin_prs": [
                {
                    "pr_id": 123,
                    "project": "TestProject",
                    "title": "Test PR",
                    "created_by": "Devin AI",
                    "commit_count": 5,
                    "created_date": "2026-01-15T10:00:00",
                }
            ],
        }

        context = _build_context(
            analysis,
            {},
            {},
            {
                "total_prs": 1,
                "devin_prs": 1,
                "human_prs": 0,
                "devin_percentage": 100,
                "author_count": 1,
                "project_count": 1,
            },
        )

        assert len(context["recent_prs"]) == 1
        pr = context["recent_prs"][0]
        assert pr["pr_id"] == 123
        assert pr["project"] == "TestProject"
        assert pr["created_date"] == "2026-01-15"  # Date extracted


class TestDashboardGeneration:
    """Tests for main dashboard generation"""

    @patch("execution.dashboards.ai._load_devin_analysis")
    @patch("execution.dashboards.ai._query_pr_data")
    @patch("execution.dashboards.ai.render_dashboard")
    def test_generate_ai_dashboard_success(self, mock_render, mock_query_pr, mock_analysis, tmp_path):
        """Test successful dashboard generation"""
        # Setup mocks
        mock_analysis.return_value = {
            "summary": {
                "total_prs": 100,
                "devin_prs": 30,
                "human_prs": 70,
                "devin_percentage": 30.0,
            },
            "devin_prs": [],
        }

        # Mock async function
        from unittest.mock import AsyncMock

        mock_query_pr.return_value = [
            {"project_name": "TestProject", "created_by": "Alice"},
        ]

        # Patch asyncio.run to execute the coroutine
        with patch("asyncio.run") as mock_async_run:
            mock_async_run.return_value = [
                {"project_name": "TestProject", "created_by": "Alice"},
            ]

            mock_render.return_value = "<html>Dashboard HTML</html>"

            output_path = tmp_path / "ai_dashboard.html"
            html = generate_ai_dashboard(output_path)

            # Verify
            assert html == "<html>Dashboard HTML</html>"
            assert output_path.exists()
            assert mock_render.called
            assert mock_analysis.called
            assert mock_async_run.called

    @patch("execution.dashboards.ai._load_devin_analysis")
    def test_generate_ai_dashboard_missing_data(self, mock_analysis):
        """Test dashboard generation with missing data file"""
        mock_analysis.side_effect = FileNotFoundError("Devin analysis file not found")

        with pytest.raises(FileNotFoundError):
            generate_ai_dashboard()

    @patch("execution.dashboards.ai._load_devin_analysis")
    @patch("execution.dashboards.ai.render_dashboard")
    def test_generate_ai_dashboard_no_output_path(self, mock_render, mock_analysis):
        """Test dashboard generation without writing to file"""
        mock_analysis.return_value = {
            "summary": {
                "total_prs": 100,
                "devin_prs": 30,
                "human_prs": 70,
                "devin_percentage": 30.0,
            },
            "devin_prs": [],
        }

        # Mock asyncio.run to return PR data
        with patch("asyncio.run") as mock_async_run:
            mock_async_run.return_value = []
            mock_render.return_value = "<html>Dashboard</html>"

            html = generate_ai_dashboard(output_path=None)

            assert html == "<html>Dashboard</html>"
            assert mock_render.called
