"""
Tests for Risk Dashboard Generator

Tests cover:
- Dashboard generation
- Data loading
- Summary calculation
- Context building
- Project row generation
- Activity level determination
- Drilldown HTML generation
- Error handling
"""

import json
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from execution.dashboards.risk import (
    _build_context,
    _build_project_rows,
    _build_summary_cards,
    _calculate_activity_level,
    _calculate_summary,
    _generate_drilldown_html,
    _query_risk_data,
    generate_risk_dashboard,
)


@pytest.fixture
def sample_risk_data():
    """Sample risk data for testing"""
    return {
        "week_number": 6,
        "week_date": "2026-02-06",
        "projects": [
            {
                "project_key": "API_Gateway",
                "project_name": "API Gateway",
                "repository_count": 3,
                "code_churn": {
                    "total_commits": 150,
                    "total_file_changes": 1200,
                    "unique_files_touched": 300,
                    "avg_changes_per_commit": 8.0,
                    "hot_paths": [
                        {"path": "/src/api/routes.py", "change_count": 45},
                        {"path": "/src/api/handlers.py", "change_count": 38},
                    ],
                },
                "pr_size_distribution": {
                    "total_prs": 25,
                    "small_prs": 15,
                    "small_pct": 60.0,
                    "large_prs": 5,
                    "large_pct": 20.0,
                },
                "knowledge_distribution": {
                    "single_owner_pct": 35.5,
                    "total_files_analyzed": 280,
                },
                "module_coupling": {
                    "total_coupled_pairs": 12,
                },
            },
            {
                "project_key": "Web_App",
                "project_name": "Web Application",
                "repository_count": 1,
                "code_churn": {
                    "total_commits": 80,
                    "total_file_changes": 600,
                    "unique_files_touched": 150,
                    "avg_changes_per_commit": 7.5,
                    "hot_paths": [
                        {"path": "/src/components/Dashboard.tsx", "change_count": 22},
                    ],
                },
                "pr_size_distribution": {
                    "total_prs": 15,
                    "small_prs": 10,
                    "small_pct": 66.7,
                    "large_prs": 2,
                    "large_pct": 13.3,
                },
                "knowledge_distribution": {
                    "single_owner_pct": 45.0,
                    "total_files_analyzed": 140,
                },
                "module_coupling": {
                    "total_coupled_pairs": 8,
                },
            },
            {
                "project_key": "Legacy_System",
                "project_name": "Legacy System",
                "repository_count": 1,
                "code_churn": {
                    "total_commits": 5,
                    "total_file_changes": 20,
                    "unique_files_touched": 10,
                    "avg_changes_per_commit": 4.0,
                    "hot_paths": [],
                },
                "pr_size_distribution": {},
                "knowledge_distribution": {},
                "module_coupling": {},
            },
        ],
    }


@pytest.fixture
def temp_risk_file(tmp_path):
    """Create a temporary risk history file"""
    return tmp_path / "risk_history.json"


class TestQueryRiskData:
    """Test querying risk data from ADO API"""

    @pytest.mark.asyncio
    async def test_query_risk_data_success(self, sample_risk_data):
        """Test successful querying of risk data from API"""
        discovery_data = {
            "projects": [
                {
                    "project_key": "API_Gateway",
                    "project_name": "API Gateway",
                    "ado_project_name": "API Gateway",
                }
            ]
        }

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(discovery_data))):
                with patch("execution.dashboards.risk.collect_risk_metrics_for_project") as mock_collect:
                    with patch("execution.collectors.ado_rest_client.get_ado_rest_client"):
                        # Mock the collector to return sample project data
                        mock_collect.return_value = sample_risk_data["projects"][0]

                        data = await _query_risk_data()

                        assert "week_number" in data
                        assert "week_date" in data
                        assert len(data["projects"]) == 1
                        assert data["projects"][0]["project_name"] == "API Gateway"

    @pytest.mark.asyncio
    async def test_query_risk_data_file_not_found(self):
        """Test FileNotFoundError when discovery file doesn't exist"""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError) as exc_info:
                await _query_risk_data()

            assert "Project discovery not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_risk_data_no_projects(self):
        """Test ValueError when no projects in discovery data"""
        discovery_data: dict[str, list] = {"projects": []}

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(discovery_data))):
                with pytest.raises(ValueError) as exc_info:
                    await _query_risk_data()

                assert "No projects found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_risk_data_handles_exceptions(self):
        """Test that API exceptions are handled gracefully"""
        discovery_data = {
            "projects": [
                {"project_key": "Project1", "project_name": "Project 1"},
                {"project_key": "Project2", "project_name": "Project 2"},
            ]
        }

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(discovery_data))):
                with patch("execution.dashboards.risk.collect_risk_metrics_for_project") as mock_collect:
                    with patch("execution.collectors.ado_rest_client.get_ado_rest_client"):
                        # First project succeeds, second fails
                        mock_collect.side_effect = [
                            {"project_name": "Project 1", "code_churn": {}},
                            Exception("API error"),
                        ]

                        data = await _query_risk_data()

                        # Should only have 1 successful project
                        assert len(data["projects"]) == 1
                        assert data["projects"][0]["project_name"] == "Project 1"


class TestCalculateSummary:
    """Test summary statistics calculation"""

    def test_calculate_summary_basic(self, sample_risk_data):
        """Test basic summary calculation"""
        summary = _calculate_summary(sample_risk_data["projects"])

        # 150 + 80 + 5 = 235 total commits
        assert summary["total_commits"] == 235
        # 300 + 150 + 10 = 460 total files
        assert summary["total_files"] == 460
        # All 3 projects have commits
        assert summary["active_projects"] == 3
        assert summary["project_count"] == 3

    def test_calculate_summary_status_low_activity(self):
        """Test status determination for low activity"""
        projects = [
            {"code_churn": {"total_commits": 50, "unique_files_touched": 20}},
            {"code_churn": {"total_commits": 30, "unique_files_touched": 15}},
        ]

        summary = _calculate_summary(projects)

        # total_commits = 80 < 300, so status should be LOW ACTIVITY
        assert summary["status_text"] == "LOW ACTIVITY"
        assert summary["status_color"] == "#6b7280"

    def test_calculate_summary_status_moderate_activity(self):
        """Test status determination for moderate activity"""
        projects = [
            {"code_churn": {"total_commits": 200, "unique_files_touched": 100}},
            {"code_churn": {"total_commits": 150, "unique_files_touched": 80}},
        ]

        summary = _calculate_summary(projects)

        # total_commits = 350 (between 300-1000), so status should be MODERATE ACTIVITY
        assert summary["status_text"] == "MODERATE ACTIVITY"
        assert summary["status_color"] == "#f59e0b"

    def test_calculate_summary_status_high_activity(self):
        """Test status determination for high activity"""
        projects = [
            {"code_churn": {"total_commits": 800, "unique_files_touched": 400}},
            {"code_churn": {"total_commits": 300, "unique_files_touched": 200}},
        ]

        summary = _calculate_summary(projects)

        # total_commits = 1100 > 1000, so status should be HIGH ACTIVITY
        assert summary["status_text"] == "HIGH ACTIVITY"
        assert summary["status_color"] == "#10b981"

    def test_calculate_summary_no_code_churn_data(self):
        """Test summary with missing code_churn data"""
        projects: list[dict[str, object]] = [
            {"project_name": "Empty Project 1"},
            {"project_name": "Empty Project 2", "code_churn": {}},
        ]

        summary = _calculate_summary(projects)

        assert summary["total_commits"] == 0
        assert summary["total_files"] == 0
        assert summary["active_projects"] == 0


class TestBuildSummaryCards:
    """Test summary cards generation"""

    def test_build_summary_cards_count(self):
        """Test that 4 summary cards are generated"""
        summary_stats = {
            "total_commits": 235,
            "total_files": 460,
            "active_projects": 3,
            "project_count": 5,
        }

        cards = _build_summary_cards(summary_stats)

        assert len(cards) == 4

    def test_build_summary_cards_content(self):
        """Test summary card content"""
        summary_stats = {
            "total_commits": 1234,
            "total_files": 5678,
            "active_projects": 8,
            "project_count": 10,
        }

        cards = _build_summary_cards(summary_stats)

        # Check for formatted numbers
        assert "1,234" in cards[0]  # Total Commits
        assert "5,678" in cards[1]  # Files Changed
        assert "8" in cards[2]  # Active Projects
        assert "GIT" in cards[3]  # Data Source


class TestCalculateActivityLevel:
    """Test activity level calculation"""

    def test_activity_level_high(self):
        """Test high activity level (100+ commits)"""
        activity_html, tooltip, priority = _calculate_activity_level(150)

        assert "High Activity" in activity_html
        assert "#10b981" in activity_html  # Green color
        assert "150 commits" in tooltip
        assert priority == 0

    def test_activity_level_medium(self):
        """Test medium activity level (20-99 commits)"""
        activity_html, tooltip, priority = _calculate_activity_level(50)

        assert "Medium Activity" in activity_html
        assert "#f59e0b" in activity_html  # Amber color
        assert "50 commits" in tooltip
        assert priority == 1

    def test_activity_level_low(self):
        """Test low activity level (<20 commits)"""
        activity_html, tooltip, priority = _calculate_activity_level(5)

        assert "Low Activity" in activity_html
        assert "#6b7280" in activity_html  # Gray color
        assert "5 commits" in tooltip
        assert priority == 2

    def test_activity_level_boundary_high(self):
        """Test boundary at 100 commits (should be high)"""
        activity_html, tooltip, priority = _calculate_activity_level(100)

        assert "High Activity" in activity_html
        assert priority == 0

    def test_activity_level_boundary_medium(self):
        """Test boundary at 20 commits (should be medium)"""
        activity_html, tooltip, priority = _calculate_activity_level(20)

        assert "Medium Activity" in activity_html
        assert priority == 1


class TestGenerateDrilldownHtml:
    """Test drill-down HTML generation"""

    def test_generate_drilldown_with_full_data(self, sample_risk_data):
        """Test drill-down generation with complete data"""
        project = sample_risk_data["projects"][0]
        html = _generate_drilldown_html(project)

        assert "detail-content" in html or "detail-section" in html
        assert "150" in html  # Total commits
        assert "1,200" in html  # File changes
        assert "8.0" in html  # Avg changes per commit

    def test_generate_drilldown_with_pr_data(self, sample_risk_data):
        """Test drill-down with PR size distribution"""
        project = sample_risk_data["projects"][0]
        html = _generate_drilldown_html(project)

        assert "25" in html  # Total PRs
        assert "15" in html  # Small PRs
        assert "5" in html  # Large PRs

    def test_generate_drilldown_with_hot_paths(self, sample_risk_data):
        """Test drill-down with hot paths"""
        project = sample_risk_data["projects"][0]
        html = _generate_drilldown_html(project)

        assert "/src/api/routes.py" in html
        assert "45" in html  # Change count

    def test_generate_drilldown_with_no_activity(self):
        """Test drill-down with no activity"""
        project = {
            "project_name": "Inactive Project",
            "code_churn": {"total_commits": 0},
            "pr_size_distribution": {},
        }

        html = _generate_drilldown_html(project)

        assert "No code activity" in html or "no-data" in html.lower()

    def test_generate_drilldown_with_missing_data(self):
        """Test drill-down with missing optional fields"""
        project = {
            "project_name": "Minimal Project",
            "code_churn": {"total_commits": 10},
        }

        html = _generate_drilldown_html(project)

        # Should not crash, should handle missing data gracefully
        assert isinstance(html, str)
        assert len(html) > 0


class TestBuildProjectRows:
    """Test project row generation"""

    def test_build_project_rows_count(self, sample_risk_data):
        """Test correct number of project rows"""
        rows = _build_project_rows(sample_risk_data["projects"])

        assert len(rows) == 3

    def test_build_project_rows_content(self, sample_risk_data):
        """Test project row content"""
        rows = _build_project_rows(sample_risk_data["projects"])

        # Find API Gateway row
        api_gateway = next(r for r in rows if r["name"] == "API Gateway")

        assert api_gateway["commits"] == 150
        assert api_gateway["files"] == 300
        assert api_gateway["knowledge_display"] == "35.5%"
        assert api_gateway["coupling_display"] == "12"
        assert "High Activity" in api_gateway["activity_level"]

    def test_build_project_rows_sorting(self, sample_risk_data):
        """Test project rows are sorted by activity priority"""
        rows = _build_project_rows(sample_risk_data["projects"])

        # First row should be high activity (API Gateway - 150 commits)
        assert rows[0]["name"] == "API Gateway"
        assert rows[0]["activity_priority"] == 0

        # Second row should be medium activity (Web Application - 80 commits)
        assert rows[1]["name"] == "Web Application"
        assert rows[1]["activity_priority"] == 1

        # Last row should be low activity (Legacy System - 5 commits)
        assert rows[2]["name"] == "Legacy System"
        assert rows[2]["activity_priority"] == 2

    def test_build_project_rows_missing_knowledge_data(self):
        """Test handling projects with missing knowledge distribution"""
        projects = [
            {
                "project_name": "No Knowledge Data",
                "code_churn": {"total_commits": 50, "unique_files_touched": 25},
                # No knowledge_distribution field
            }
        ]

        rows = _build_project_rows(projects)

        assert rows[0]["knowledge_display"] == "N/A"
        assert "No file data" in rows[0]["knowledge_title"]

    def test_build_project_rows_missing_coupling_data(self):
        """Test handling projects with missing module coupling"""
        projects = [
            {
                "project_name": "No Coupling Data",
                "code_churn": {"total_commits": 50, "unique_files_touched": 25},
                # No module_coupling field
            }
        ]

        rows = _build_project_rows(projects)

        assert rows[0]["coupling_display"] == "N/A"
        assert "No coupling data" in rows[0]["coupling_title"]

    def test_build_project_rows_zero_values(self):
        """Test handling projects with zero values"""
        projects = [
            {
                "project_name": "Zero Values",
                "code_churn": {"total_commits": 0, "unique_files_touched": 0},
                "knowledge_distribution": {"single_owner_pct": 0, "total_files_analyzed": 0},
                "module_coupling": {"total_coupled_pairs": 0},
            }
        ]

        rows = _build_project_rows(projects)

        assert rows[0]["commits"] == 0
        assert rows[0]["files"] == 0
        assert rows[0]["knowledge_display"] == "N/A"
        assert rows[0]["coupling_display"] == "N/A"


class TestBuildContext:
    """Test context building for template"""

    def test_build_context_keys(self, sample_risk_data):
        """Test that context has all required keys"""
        summary = _calculate_summary(sample_risk_data["projects"])
        context = _build_context(sample_risk_data, summary)

        required_keys = [
            "framework_css",
            "framework_js",
            "generation_date",
            "week_number",
            "week_date",
            "status_color",
            "status_text",
            "project_count",
            "summary_cards",
            "projects",
        ]

        for key in required_keys:
            assert key in context

    def test_build_context_values(self, sample_risk_data):
        """Test context values are correct"""
        summary = _calculate_summary(sample_risk_data["projects"])
        context = _build_context(sample_risk_data, summary)

        assert context["week_number"] == 6
        assert context["week_date"] == "2026-02-06"
        assert context["project_count"] == 3
        assert len(context["summary_cards"]) == 4
        assert len(context["projects"]) == 3


class TestGenerateRiskDashboard:
    """Test main dashboard generation function"""

    @patch("execution.dashboards.risk.asyncio.run")
    @patch("execution.dashboards.risk.render_dashboard")
    def test_generate_dashboard_success(self, mock_render, mock_asyncio_run, sample_risk_data):
        """Test successful dashboard generation"""
        mock_asyncio_run.return_value = sample_risk_data
        mock_render.return_value = "<html>Dashboard</html>"

        html = generate_risk_dashboard()

        assert html == "<html>Dashboard</html>"
        mock_asyncio_run.assert_called_once()
        mock_render.assert_called_once()

    @patch("execution.dashboards.risk.asyncio.run")
    @patch("execution.dashboards.risk.render_dashboard")
    def test_generate_dashboard_with_output_path(self, mock_render, mock_asyncio_run, sample_risk_data, tmp_path):
        """Test dashboard generation with file output"""
        mock_asyncio_run.return_value = sample_risk_data
        mock_render.return_value = "<html>Dashboard</html>"

        output_path = tmp_path / "risk.html"
        html = generate_risk_dashboard(output_path)

        assert output_path.exists()
        assert output_path.read_text(encoding="utf-8") == "<html>Dashboard</html>"

    @patch("execution.dashboards.risk.asyncio.run")
    def test_generate_dashboard_file_not_found(self, mock_asyncio_run):
        """Test dashboard generation with missing discovery file"""
        mock_asyncio_run.side_effect = FileNotFoundError("Project discovery not found")

        with pytest.raises(FileNotFoundError):
            generate_risk_dashboard()


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_projects_list(self):
        """Test handling empty projects list"""
        summary = _calculate_summary([])

        assert summary["total_commits"] == 0
        assert summary["total_files"] == 0
        assert summary["active_projects"] == 0
        assert summary["project_count"] == 0

    def test_project_with_none_values(self):
        """Test handling projects with None values"""
        projects = [
            {
                "project_name": "Null Project",
                "code_churn": {
                    "total_commits": None,
                    "unique_files_touched": None,
                },
                "knowledge_distribution": {
                    "single_owner_pct": None,
                },
            }
        ]

        rows = _build_project_rows(projects)

        assert rows[0]["commits"] == 0
        assert rows[0]["files"] == 0

    def test_project_missing_all_optional_fields(self):
        """Test handling project with only required fields"""
        projects = [
            {
                "project_name": "Minimal Project",
            }
        ]

        rows = _build_project_rows(projects)

        assert rows[0]["name"] == "Minimal Project"
        assert rows[0]["commits"] == 0
        assert rows[0]["knowledge_display"] == "N/A"
        assert rows[0]["coupling_display"] == "N/A"

    def test_very_large_numbers(self):
        """Test handling very large metric values"""
        projects = [
            {
                "project_name": "Huge Project",
                "code_churn": {
                    "total_commits": 999999,
                    "unique_files_touched": 888888,
                },
            }
        ]

        rows = _build_project_rows(projects)

        assert rows[0]["commits"] == 999999
        assert rows[0]["files"] == 888888
        # Should be high activity
        assert rows[0]["activity_priority"] == 0
