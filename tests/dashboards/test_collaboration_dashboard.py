"""
Tests for Collaboration Dashboard Generator

Tests cover:
- Dashboard generation
- Summary calculation
- Context building
- Project row generation
- Composite status determination
- Data loading from ADO API
- Error handling
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from execution.dashboards.collaboration import (
    _build_context,
    _build_project_rows,
    _build_summary_cards,
    _calculate_composite_status,
    _calculate_summary,
    _load_collaboration_data,
    generate_collaboration_dashboard,
)


@pytest.fixture
def sample_collaboration_data():
    """Sample collaboration data for testing"""
    return {
        "week_date": "2026-02-07",
        "projects": [
            {
                "project_name": "API Gateway",
                "total_prs_analyzed": 50,
                "pr_merge_time": {
                    "median_hours": 18.5,
                    "p85_hours": 42.3,
                    "sample_size": 50,
                },
                "review_iteration_count": {
                    "median_iterations": 3.2,
                    "max_iterations": 8,
                },
                "pr_size": {
                    "median_commits": 4.5,
                    "p85_commits": 8.2,
                },
            },
            {
                "project_name": "Web App",
                "total_prs_analyzed": 30,
                "pr_merge_time": {
                    "median_hours": 48.0,
                    "p85_hours": 96.5,
                    "sample_size": 30,
                },
                "review_iteration_count": {
                    "median_iterations": 5.5,
                    "max_iterations": 12,
                },
                "pr_size": {
                    "median_commits": 8.0,
                    "p85_commits": 15.0,
                },
            },
        ],
    }


@pytest.fixture
def mock_discovery_data():
    """Sample discovery data for testing"""
    return {
        "projects": [
            {
                "project_name": "API Gateway",
                "project_key": "api",
                "ado_project_name": "API Gateway",
            },
            {
                "project_name": "Web App",
                "project_key": "web",
                "ado_project_name": "Web App",
            },
        ]
    }


class TestLoadCollaborationData:
    """Test loading collaboration data from ADO API"""

    @pytest.mark.asyncio
    async def test_load_collaboration_data_success(self, sample_collaboration_data, mock_discovery_data):
        """Test successful loading of collaboration data from ADO API"""
        discovery_json = json.dumps(mock_discovery_data)

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=discovery_json)):
                with patch("execution.dashboards.collaboration.get_ado_rest_client") as mock_client:
                    with patch(
                        "execution.dashboards.collaboration.collect_collaboration_metrics_for_project"
                    ) as mock_collect:
                        # Mock the collector to return project metrics
                        mock_collect.side_effect = sample_collaboration_data["projects"]

                        data = await _load_collaboration_data()

                        assert "week_date" in data
                        assert len(data["projects"]) == 2
                        assert data["projects"][0]["project_name"] == "API Gateway"

    @pytest.mark.asyncio
    async def test_load_collaboration_data_file_not_found(self):
        """Test FileNotFoundError when discovery file doesn't exist"""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError) as exc_info:
                await _load_collaboration_data()

            assert "Discovery file not found" in str(exc_info.value)
            assert "discover_projects.py" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_load_collaboration_data_no_projects(self):
        """Test handling when no projects are in discovery data"""
        discovery_data = {"projects": []}
        discovery_json = json.dumps(discovery_data)

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=discovery_json)):
                data = await _load_collaboration_data()

                assert len(data["projects"]) == 0
                assert "week_date" in data

    @pytest.mark.asyncio
    async def test_load_collaboration_data_handles_api_errors(self, mock_discovery_data):
        """Test handling of API errors during collection"""
        discovery_json = json.dumps(mock_discovery_data)

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=discovery_json)):
                with patch("execution.dashboards.collaboration.get_ado_rest_client"):
                    with patch(
                        "execution.dashboards.collaboration.collect_collaboration_metrics_for_project"
                    ) as mock_collect:
                        # Simulate one project failing
                        mock_collect.side_effect = [
                            {"project_name": "API Gateway", "total_prs_analyzed": 50},
                            Exception("API Error"),
                        ]

                        data = await _load_collaboration_data()

                        # Should have 1 successful project
                        assert len(data["projects"]) == 1
                        assert data["projects"][0]["project_name"] == "API Gateway"


class TestCalculateSummary:
    """Test summary statistics calculation"""

    def test_calculate_summary_basic(self, sample_collaboration_data):
        """Test basic summary calculation"""
        summary = _calculate_summary(sample_collaboration_data["projects"])

        assert summary["total_prs"] == 80  # 50 + 30
        assert summary["projects_with_prs"] == 2
        assert summary["avg_prs_per_project"] == 40  # 80 // 2

    def test_calculate_summary_no_projects(self):
        """Test summary with empty projects list"""
        summary = _calculate_summary([])

        assert summary["total_prs"] == 0
        assert summary["projects_with_prs"] == 0
        assert summary["avg_prs_per_project"] == 0

    def test_calculate_summary_some_empty_projects(self):
        """Test summary with some projects having no PRs"""
        projects = [
            {"project_name": "Active", "total_prs_analyzed": 50},
            {"project_name": "Inactive", "total_prs_analyzed": 0},
            {"project_name": "Also Active", "total_prs_analyzed": 30},
        ]

        summary = _calculate_summary(projects)

        assert summary["total_prs"] == 80
        assert summary["projects_with_prs"] == 2  # Only count active
        assert summary["avg_prs_per_project"] == 40  # 80 // 2


class TestBuildSummaryCards:
    """Test summary cards generation"""

    def test_build_summary_cards_count(self):
        """Test that 3 summary cards are generated"""
        summary_stats = {
            "total_prs": 80,
            "projects_with_prs": 5,
            "avg_prs_per_project": 16,
        }

        cards = _build_summary_cards(summary_stats)

        assert len(cards) == 3

    def test_build_summary_cards_content(self):
        """Test summary card content"""
        summary_stats = {
            "total_prs": 1234,
            "projects_with_prs": 5,
            "avg_prs_per_project": 246,
        }

        cards = _build_summary_cards(summary_stats)

        # Check for expected values
        assert "1,234" in cards[0]  # Total PRs (formatted with comma)
        assert "5" in cards[1]  # Projects with PRs
        assert "246" in cards[2]  # Avg PRs


class TestCalculateCompositeStatus:
    """Test composite status calculation"""

    def test_status_good_all_metrics(self):
        """Test Good status when all metrics meet targets"""
        status_text, status_class, tooltip, priority = _calculate_composite_status(
            merge_time=18.0, iterations=2.0, pr_size=4.0
        )

        assert "Good" in status_text
        assert status_class == "good"
        assert priority == 2
        assert "good" in tooltip.lower()

    def test_status_caution_one_metric(self):
        """Test Caution status when one metric needs attention"""
        status_text, status_class, tooltip, priority = _calculate_composite_status(
            merge_time=48.0,  # Caution: 24-72h
            iterations=2.0,  # Good
            pr_size=4.0,  # Good
        )

        assert "Caution" in status_text
        assert status_class == "caution"
        assert priority == 1

    def test_status_action_needed_multiple_poor(self):
        """Test Action Needed when multiple metrics are poor"""
        status_text, status_class, tooltip, priority = _calculate_composite_status(
            merge_time=80.0,  # Poor: >72h
            iterations=6.0,  # Poor: >5
            pr_size=4.0,  # Good
        )

        assert "Action Needed" in status_text
        assert status_class == "action"
        assert priority == 0

    def test_status_caution_one_poor(self):
        """Test Caution when only one metric is poor"""
        status_text, status_class, tooltip, priority = _calculate_composite_status(
            merge_time=80.0,  # Poor: >72h
            iterations=2.0,  # Good
            pr_size=4.0,  # Good
        )

        assert "Caution" in status_text
        assert status_class == "caution"
        assert priority == 1

    def test_tooltip_content(self):
        """Test tooltip contains metric details"""
        status_text, status_class, tooltip, priority = _calculate_composite_status(
            merge_time=48.0, iterations=3.5, pr_size=7.0
        )

        assert "48.0h" in tooltip
        assert "3.5 iterations" in tooltip
        assert "7.0 commits" in tooltip
        assert "caution" in tooltip.lower()

    def test_none_values_handled(self):
        """Test that None values are handled gracefully"""
        status_text, status_class, tooltip, priority = _calculate_composite_status(
            merge_time=None, iterations=None, pr_size=None
        )

        assert "No Data" in status_text
        assert status_class == "no-data"
        assert priority == 3

    def test_merge_time_thresholds(self):
        """Test merge time threshold boundaries"""
        # Good: < 24h
        _, _, _, priority = _calculate_composite_status(merge_time=20.0, iterations=2.0, pr_size=4.0)
        assert priority == 2  # Good

        # Caution: 24-72h
        _, _, _, priority = _calculate_composite_status(merge_time=48.0, iterations=2.0, pr_size=4.0)
        assert priority == 1  # Caution

        # Poor: > 72h
        _, _, _, priority = _calculate_composite_status(merge_time=80.0, iterations=2.0, pr_size=4.0)
        assert priority == 1  # Caution (only one poor)

    def test_iterations_thresholds(self):
        """Test iterations threshold boundaries"""
        # Good: <= 2
        _, _, _, priority = _calculate_composite_status(merge_time=20.0, iterations=2.0, pr_size=4.0)
        assert priority == 2  # Good

        # Caution: 3-5
        _, _, _, priority = _calculate_composite_status(merge_time=20.0, iterations=3.5, pr_size=4.0)
        assert priority == 1  # Caution

        # Poor: > 5
        _, _, _, priority = _calculate_composite_status(merge_time=20.0, iterations=6.0, pr_size=4.0)
        assert priority == 1  # Caution (only one poor)

    def test_pr_size_thresholds(self):
        """Test PR size threshold boundaries"""
        # Good: <= 5
        _, _, _, priority = _calculate_composite_status(merge_time=20.0, iterations=2.0, pr_size=4.0)
        assert priority == 2  # Good

        # Caution: 6-10
        _, _, _, priority = _calculate_composite_status(merge_time=20.0, iterations=2.0, pr_size=7.0)
        assert priority == 1  # Caution

        # Poor: > 10
        _, _, _, priority = _calculate_composite_status(merge_time=20.0, iterations=2.0, pr_size=12.0)
        assert priority == 1  # Caution (only one poor)


class TestBuildProjectRows:
    """Test project row generation"""

    def test_build_project_rows_count(self, sample_collaboration_data):
        """Test correct number of project rows"""
        rows = _build_project_rows(sample_collaboration_data["projects"])

        assert len(rows) == 2

    def test_build_project_rows_content(self, sample_collaboration_data):
        """Test project row content"""
        rows = _build_project_rows(sample_collaboration_data["projects"])

        # Find API Gateway project
        api_gateway = next(r for r in rows if r["name"] == "API Gateway")

        assert api_gateway["total_prs"] == 50
        assert "18.5h" in api_gateway["merge_display"]
        assert "3.2" in api_gateway["iterations_display"]
        assert "4.5" in api_gateway["size_display"]

    def test_build_project_rows_sorting(self):
        """Test project rows are sorted by status priority"""
        projects = [
            {
                "project_name": "Good Project",
                "total_prs_analyzed": 50,
                "pr_merge_time": {"median_hours": 18.0, "p85_hours": 35.0, "sample_size": 50},
                "review_iteration_count": {"median_iterations": 2.0, "max_iterations": 5},
                "pr_size": {"median_commits": 4.0, "p85_commits": 7.0},
            },
            {
                "project_name": "Bad Project",
                "total_prs_analyzed": 30,
                "pr_merge_time": {"median_hours": 80.0, "p85_hours": 120.0, "sample_size": 30},
                "review_iteration_count": {"median_iterations": 6.0, "max_iterations": 12},
                "pr_size": {"median_commits": 12.0, "p85_commits": 20.0},
            },
        ]

        rows = _build_project_rows(projects)

        # Bad project should be first (lower priority number = higher urgency)
        assert rows[0]["name"] == "Bad Project"
        assert rows[1]["name"] == "Good Project"

    def test_build_project_rows_missing_data(self):
        """Test handling of missing data"""
        projects = [
            {
                "project_name": "Incomplete Project",
                "total_prs_analyzed": 10,
                "pr_merge_time": {},
                "review_iteration_count": {},
                "pr_size": {},
            }
        ]

        rows = _build_project_rows(projects)

        assert rows[0]["merge_display"] == "N/A"
        assert rows[0]["iterations_display"] == "N/A"
        assert rows[0]["size_display"] == "N/A"
        assert "No Data" in rows[0]["status_text"]

    def test_build_project_rows_tooltips(self, sample_collaboration_data):
        """Test tooltips contain detailed information"""
        rows = _build_project_rows(sample_collaboration_data["projects"])

        api_gateway = next(r for r in rows if r["name"] == "API Gateway")

        assert "P85" in api_gateway["merge_detail"]
        assert "42.3h" in api_gateway["merge_detail"]
        assert "Max: 8" in api_gateway["iterations_detail"]
        assert "8.2 commits" in api_gateway["size_detail"]


class TestBuildContext:
    """Test context building for template"""

    def test_build_context_keys(self, sample_collaboration_data):
        """Test that context has all required keys"""
        summary = _calculate_summary(sample_collaboration_data["projects"])
        context = _build_context(sample_collaboration_data, summary)

        required_keys = [
            "framework_css",
            "framework_js",
            "generation_date",
            "collection_date",
            "summary_cards",
            "projects",
        ]

        for key in required_keys:
            assert key in context

    def test_build_context_values(self, sample_collaboration_data):
        """Test context values are correct"""
        summary = _calculate_summary(sample_collaboration_data["projects"])
        context = _build_context(sample_collaboration_data, summary)

        assert context["collection_date"] == "2026-02-07"
        assert len(context["summary_cards"]) == 3
        assert len(context["projects"]) == 2


class TestGenerateCollaborationDashboard:
    """Test main dashboard generation function"""

    @pytest.mark.asyncio
    @patch("execution.dashboards.collaboration._load_collaboration_data")
    @patch("execution.dashboards.collaboration.render_dashboard")
    async def test_generate_dashboard_success(self, mock_render, mock_load, sample_collaboration_data):
        """Test successful dashboard generation"""
        mock_load.return_value = sample_collaboration_data
        mock_render.return_value = "<html>Dashboard</html>"

        html = await generate_collaboration_dashboard()

        assert html == "<html>Dashboard</html>"
        mock_load.assert_called_once()
        mock_render.assert_called_once()

    @pytest.mark.asyncio
    @patch("execution.dashboards.collaboration._load_collaboration_data")
    @patch("execution.dashboards.collaboration.render_dashboard")
    async def test_generate_dashboard_with_output_path(
        self, mock_render, mock_load, sample_collaboration_data, tmp_path
    ):
        """Test dashboard generation with file output"""
        mock_load.return_value = sample_collaboration_data
        mock_render.return_value = "<html>Dashboard</html>"

        output_path = tmp_path / "collaboration.html"
        html = await generate_collaboration_dashboard(output_path)

        assert output_path.exists()
        assert output_path.read_text(encoding="utf-8") == "<html>Dashboard</html>"

    @pytest.mark.asyncio
    @patch("execution.dashboards.collaboration._load_collaboration_data")
    async def test_generate_dashboard_file_not_found(self, mock_load):
        """Test dashboard generation with missing discovery file"""
        mock_load.side_effect = FileNotFoundError("Discovery file not found")

        with pytest.raises(FileNotFoundError):
            await generate_collaboration_dashboard()


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_zero_prs_project(self):
        """Test handling of projects with zero PRs"""
        projects = [
            {
                "project_name": "Empty",
                "total_prs_analyzed": 0,
                "pr_merge_time": {},
                "review_iteration_count": {},
                "pr_size": {},
            }
        ]

        rows = _build_project_rows(projects)

        assert rows[0]["total_prs"] == 0
        assert rows[0]["merge_display"] == "N/A"

    def test_very_large_pr_counts(self):
        """Test formatting of large PR counts"""
        summary_stats = {
            "total_prs": 10000,
            "projects_with_prs": 50,
            "avg_prs_per_project": 200,
        }

        cards = _build_summary_cards(summary_stats)

        # Check for comma formatting
        assert "10,000" in cards[0]

    def test_mixed_metric_availability(self):
        """Test handling projects with some metrics missing"""
        projects = [
            {
                "project_name": "Partial Data",
                "total_prs_analyzed": 25,
                "pr_merge_time": {"median_hours": 30.0, "p85_hours": 60.0, "sample_size": 25},
                "review_iteration_count": {},  # Missing
                "pr_size": {"median_commits": 6.0, "p85_commits": 10.0},
            }
        ]

        rows = _build_project_rows(projects)

        assert "30.0h" in rows[0]["merge_display"]
        assert rows[0]["iterations_display"] == "N/A"
        assert "6.0" in rows[0]["size_display"]
