"""
Tests for Deployment Dashboard Generator

Tests cover:
- Data querying from ADO API
- Domain model conversion (from_json)
- Summary calculation
- Summary card generation
- Project row formatting
- Context building
- Dashboard generation
- Error handling
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

try:
    from tests.test_config import TEST_PRODUCTS
except ImportError:
    # Fallback to example config if test_config.py doesn't exist (e.g., in CI)
    from tests.test_config_example import TEST_PRODUCTS

from execution.dashboards.deployment import (
    _build_context,
    _build_project_rows,
    _build_summary_cards,
    _calculate_summary,
    _query_deployment_data,
    generate_deployment_dashboard,
)
from execution.domain.deployment import DeploymentMetrics, from_json


@pytest.fixture
def sample_deployment_data():
    """Sample deployment data for testing"""
    return {
        "weeks": [
            {
                "week_date": "2026-02-06",
                "week_number": 6,
                "projects": [
                    {
                        "project_name": TEST_PRODUCTS["product1"],
                        "deployment_frequency": {
                            "total_successful_builds": 100,
                            "deployments_per_week": 7.7,
                            "lookback_days": 90,
                            "pipeline_count": 5,
                        },
                        "build_success_rate": {
                            "total_builds": 110,
                            "succeeded": 100,
                            "failed": 10,
                            "success_rate_pct": 90.9,
                        },
                        "build_duration": {
                            "median_minutes": 8.5,
                            "p85_minutes": 12.3,
                        },
                        "lead_time_for_changes": {
                            "median_hours": 2.5,
                            "p85_hours": 6.0,
                        },
                    },
                    {
                        "project_name": "API Gateway",
                        "deployment_frequency": {
                            "total_successful_builds": 50,
                            "deployments_per_week": 3.8,
                            "lookback_days": 90,
                            "pipeline_count": 2,
                        },
                        "build_success_rate": {
                            "total_builds": 70,
                            "succeeded": 50,
                            "failed": 20,
                            "success_rate_pct": 71.4,
                        },
                        "build_duration": {
                            "median_minutes": 15.0,
                            "p85_minutes": 25.0,
                        },
                        "lead_time_for_changes": {
                            "median_hours": 5.0,
                            "p85_hours": 12.0,
                        },
                    },
                    {
                        "project_name": "Inactive Project",
                        "deployment_frequency": {
                            "total_successful_builds": 0,
                            "deployments_per_week": 0.0,
                            "lookback_days": 90,
                            "pipeline_count": 0,
                        },
                        "build_success_rate": {
                            "total_builds": 0,
                            "succeeded": 0,
                            "failed": 0,
                            "success_rate_pct": 0.0,
                        },
                        "build_duration": {
                            "median_minutes": 0.0,
                            "p85_minutes": 0.0,
                        },
                        "lead_time_for_changes": {
                            "median_hours": 0.0,
                            "p85_hours": 0.0,
                        },
                    },
                ],
            }
        ]
    }


@pytest.fixture
def sample_metrics_list(sample_deployment_data):
    """Convert sample data to metrics list"""
    latest_week = sample_deployment_data["weeks"][-1]
    return [from_json(project) for project in latest_week["projects"]]


@pytest.fixture
def sample_raw_projects(sample_deployment_data):
    """Get raw project data for testing"""
    latest_week = sample_deployment_data["weeks"][-1]
    return latest_week["projects"]


@pytest.fixture
def sample_discovery_data():
    """Sample ADO discovery data"""
    return {
        "projects": [
            {"project_name": TEST_PRODUCTS["product1"], "ado_project_name": TEST_PRODUCTS["product1"]},
            {"project_name": "API Gateway", "ado_project_name": "API Gateway"},
            {"project_name": "Inactive Project", "ado_project_name": "Inactive Project"},
        ]
    }


class TestQueryDeploymentData:
    """Test _query_deployment_data function"""

    @pytest.mark.asyncio
    async def test_query_deployment_data_success(self, sample_deployment_data, sample_discovery_data):
        """Test successful querying of deployment data from ADO"""
        # Mock discovery file
        discovery_json = json.dumps(sample_discovery_data)

        # Mock raw project results
        raw_projects = sample_deployment_data["weeks"][0]["projects"]

        with patch("builtins.open", mock_open(read_data=discovery_json)):
            with patch("pathlib.Path.exists", return_value=True):
                with patch(
                    "execution.dashboards.deployment.get_ado_rest_client", return_value=MagicMock()
                ) as mock_client:
                    with patch(
                        "execution.dashboards.deployment._collect_project_metrics",
                        side_effect=[raw_projects[0], raw_projects[1], raw_projects[2]],
                    ):
                        metrics_list, projects, collection_date = await _query_deployment_data()

                        assert len(metrics_list) == 3
                        assert len(projects) == 3
                        assert isinstance(metrics_list[0], DeploymentMetrics)
                        assert isinstance(projects[0], dict)
                        # Collection date should be today's date
                        assert len(collection_date) == 10  # YYYY-MM-DD format

    @pytest.mark.asyncio
    async def test_query_deployment_data_file_not_found(self):
        """Test FileNotFoundError when discovery file doesn't exist"""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError) as exc_info:
                await _query_deployment_data()

            assert "Discovery data file not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_deployment_data_no_projects(self):
        """Test ValueError when projects array is empty"""
        empty_data = {"projects": []}

        with patch("builtins.open", mock_open(read_data=json.dumps(empty_data))):
            with patch("pathlib.Path.exists", return_value=True):
                with pytest.raises(ValueError) as exc_info:
                    await _query_deployment_data()

                assert "No projects found" in str(exc_info.value)


class TestDomainModelConversion:
    """Test from_json domain model conversion"""

    def test_from_json_complete_data(self, sample_deployment_data):
        """Test conversion with complete data"""
        project_data = sample_deployment_data["weeks"][0]["projects"][0]
        metrics = from_json(project_data)

        assert metrics.project_name == TEST_PRODUCTS["product1"]
        assert metrics.deployment_frequency.total_successful_builds == 100
        assert metrics.deployment_frequency.deployments_per_week == 7.7
        assert metrics.build_success_rate.success_rate_pct == 90.9
        assert metrics.build_duration.median_minutes == 8.5
        assert metrics.lead_time_for_changes.median_hours == 2.5

    def test_from_json_missing_optional_fields(self):
        """Test conversion with missing optional fields"""
        project_data = {
            "project_name": "Test Project",
            "deployment_frequency": {
                "total_successful_builds": 10,
                "deployments_per_week": 1.0,
            },
            "build_success_rate": {
                "total_builds": 10,
                "succeeded": 10,
                "failed": 0,
                "success_rate_pct": 100.0,
            },
            "build_duration": {},  # Empty
            "lead_time_for_changes": {},  # Empty
        }

        metrics = from_json(project_data)

        assert metrics.project_name == "Test Project"
        assert metrics.build_duration.median_minutes == 0.0
        assert metrics.lead_time_for_changes.median_hours == 0.0


class TestCalculateSummary:
    """Test _calculate_summary function"""

    def test_calculate_summary_with_data(self, sample_metrics_list):
        """Test summary calculation with data"""
        summary = _calculate_summary(sample_metrics_list)

        assert summary["total_builds"] == 180  # 110 + 70 + 0
        assert summary["total_successful"] == 150  # 100 + 50 + 0
        assert summary["overall_success_rate"] == pytest.approx(83.33, abs=0.01)
        assert summary["project_count"] == 3

    def test_calculate_summary_empty_list(self):
        """Test summary calculation with empty list"""
        summary = _calculate_summary([])

        assert summary["total_builds"] == 0
        assert summary["total_successful"] == 0
        assert summary["overall_success_rate"] == 0.0
        assert summary["project_count"] == 0

    def test_calculate_summary_zero_builds(self):
        """Test summary calculation with projects having zero builds"""
        project_data = {
            "project_name": "Zero Builds",
            "deployment_frequency": {
                "total_successful_builds": 0,
                "deployments_per_week": 0.0,
            },
            "build_success_rate": {
                "total_builds": 0,
                "succeeded": 0,
                "failed": 0,
                "success_rate_pct": 0.0,
            },
            "build_duration": {"median_minutes": 0.0, "p85_minutes": 0.0},
            "lead_time_for_changes": {"median_hours": 0.0, "p85_hours": 0.0},
        }

        metrics = from_json(project_data)
        summary = _calculate_summary([metrics])

        assert summary["overall_success_rate"] == 0.0


class TestBuildSummaryCards:
    """Test _build_summary_cards function"""

    def test_build_summary_cards(self):
        """Test summary card generation"""
        summary_stats = {
            "total_builds": 180,
            "total_successful": 150,
            "overall_success_rate": 83.33,
            "project_count": 3,
        }

        cards = _build_summary_cards(summary_stats)

        assert len(cards) == 3
        assert "180" in cards[0]  # Total builds
        assert "150" in cards[0]  # Successful
        assert "83.3%" in cards[1]  # Success rate
        assert "3" in cards[2]  # Project count


class TestBuildProjectRows:
    """Test _build_project_rows function"""

    def test_build_project_rows_sorted(self, sample_metrics_list, sample_raw_projects):
        """Test project rows are sorted by deployment frequency"""
        rows = _build_project_rows(sample_metrics_list, sample_raw_projects)

        # Should be sorted by deployments per week (descending)
        assert rows[0]["name"] == TEST_PRODUCTS["product1"]  # 7.7/week
        assert rows[1]["name"] == "API Gateway"  # 3.8/week
        assert rows[2]["name"] == "Inactive Project"  # 0.0/week

    def test_build_project_rows_display_values(self, sample_metrics_list, sample_raw_projects):
        """Test project row display values"""
        rows = _build_project_rows(sample_metrics_list, sample_raw_projects)

        # Check first project (OneOffice)
        first_row = rows[0]
        assert first_row["deploys_display"] == "7.7/week"
        assert first_row["success_display"] == "90.9%"
        assert first_row["duration_display"] == "8.5m"
        assert first_row["lead_time_display"] == "2.5h"

    def test_build_project_rows_tooltips(self, sample_metrics_list, sample_raw_projects):
        """Test project row tooltips"""
        rows = _build_project_rows(sample_metrics_list, sample_raw_projects)

        # Check tooltips
        first_row = rows[0]
        assert "100 successful builds" in first_row["deploys_tooltip"]
        assert "100/110 builds" in first_row["success_tooltip"]
        assert "P85: 12.3m" in first_row["duration_tooltip"]
        assert "P85: 6.0h" in first_row["lead_time_tooltip"]

    def test_build_project_rows_status_good(self, sample_metrics_list, sample_raw_projects):
        """Test status for healthy project (Good)"""
        rows = _build_project_rows(sample_metrics_list, sample_raw_projects)

        # OneOffice: 90.9% success rate, 7.7 deploys/week
        first_row = rows[0]
        assert first_row["status_display"] == "✓ Good"
        assert first_row["status_class"] == "good"

    def test_build_project_rows_status_caution(self, sample_metrics_list, sample_raw_projects):
        """Test status for caution project"""
        rows = _build_project_rows(sample_metrics_list, sample_raw_projects)

        # API Gateway: 71.4% success rate, 3.8 deploys/week
        second_row = rows[1]
        assert second_row["status_display"] == "⚠ Caution"
        assert second_row["status_class"] == "caution"

    def test_build_project_rows_status_inactive(self, sample_metrics_list, sample_raw_projects):
        """Test status for inactive project"""
        rows = _build_project_rows(sample_metrics_list, sample_raw_projects)

        # Inactive Project: 0 deploys
        third_row = rows[2]
        assert third_row["status_display"] == "○ Inactive"
        assert third_row["status_class"] == "inactive"


class TestBuildContext:
    """Test _build_context function"""

    def test_build_context_structure(self, sample_metrics_list, sample_raw_projects):
        """Test context dictionary structure"""
        summary_stats = _calculate_summary(sample_metrics_list)
        context = _build_context(sample_metrics_list, sample_raw_projects, summary_stats, "2026-02-06")

        # Check required keys
        assert "framework_css" in context
        assert "framework_js" in context
        assert "generation_date" in context
        assert "summary_cards" in context
        assert "projects" in context
        assert "show_glossary" in context

    def test_build_context_generation_date(self, sample_metrics_list, sample_raw_projects):
        """Test generation date formatting"""
        summary_stats = _calculate_summary(sample_metrics_list)
        context = _build_context(sample_metrics_list, sample_raw_projects, summary_stats, "2026-02-06")

        assert "2026-02-06" in context["generation_date"]
        assert "Generated" in context["generation_date"]

    def test_build_context_summary_cards(self, sample_metrics_list, sample_raw_projects):
        """Test summary cards in context"""
        summary_stats = _calculate_summary(sample_metrics_list)
        context = _build_context(sample_metrics_list, sample_raw_projects, summary_stats, "2026-02-06")

        assert len(context["summary_cards"]) == 3
        assert isinstance(context["summary_cards"][0], str)

    def test_build_context_projects(self, sample_metrics_list, sample_raw_projects):
        """Test projects list in context"""
        summary_stats = _calculate_summary(sample_metrics_list)
        context = _build_context(sample_metrics_list, sample_raw_projects, summary_stats, "2026-02-06")

        assert len(context["projects"]) == 3
        assert isinstance(context["projects"][0], dict)


class TestGenerateDeploymentDashboard:
    """Test generate_deployment_dashboard function"""

    @pytest.mark.asyncio
    @patch("execution.dashboards.deployment.render_dashboard")
    @patch("execution.dashboards.deployment._query_deployment_data")
    async def test_generate_deployment_dashboard_success(
        self, mock_query, mock_render, sample_metrics_list, sample_raw_projects
    ):
        """Test successful dashboard generation"""
        # Setup mocks
        mock_query.return_value = (sample_metrics_list, sample_raw_projects, "2026-02-06")
        mock_render.return_value = "<html>Test Dashboard</html>"

        # Generate dashboard
        html = await generate_deployment_dashboard()

        # Verify calls
        mock_query.assert_called_once()
        mock_render.assert_called_once()

        # Verify output
        assert html == "<html>Test Dashboard</html>"

    @pytest.mark.asyncio
    @patch("execution.dashboards.deployment.render_dashboard")
    @patch("execution.dashboards.deployment._query_deployment_data")
    async def test_generate_deployment_dashboard_with_output_path(
        self, mock_query, mock_render, sample_metrics_list, sample_raw_projects, tmp_path
    ):
        """Test dashboard generation with output file"""
        # Setup mocks
        mock_query.return_value = (sample_metrics_list, sample_raw_projects, "2026-02-06")
        mock_render.return_value = "<html>Test Dashboard</html>"

        # Generate dashboard with output path
        output_path = tmp_path / "deployment_dashboard.html"
        html = await generate_deployment_dashboard(output_path)

        # Verify file was written
        assert output_path.exists()
        assert output_path.read_text(encoding="utf-8") == "<html>Test Dashboard</html>"

    @pytest.mark.asyncio
    @patch("execution.dashboards.deployment._query_deployment_data")
    async def test_generate_deployment_dashboard_file_not_found(self, mock_query):
        """Test dashboard generation with missing data file"""
        # Setup mock to raise FileNotFoundError
        mock_query.side_effect = FileNotFoundError("Discovery data file not found")

        # Verify exception is raised
        with pytest.raises(FileNotFoundError):
            await generate_deployment_dashboard()

    @pytest.mark.asyncio
    @patch("execution.dashboards.deployment.render_dashboard")
    @patch("execution.dashboards.deployment._query_deployment_data")
    async def test_generate_deployment_dashboard_output_format(
        self, mock_query, mock_render, sample_metrics_list, sample_raw_projects
    ):
        """Test dashboard output contains expected content"""
        # Setup mocks
        mock_query.return_value = (sample_metrics_list, sample_raw_projects, "2026-02-06")
        mock_render.return_value = """
        <html>
            <h1>Deployment Dashboard</h1>
            <div>DORA Metrics</div>
            <table>
                <tr><td>OneOffice</td></tr>
                <tr><td>API Gateway</td></tr>
            </table>
        </html>
        """

        # Generate dashboard
        html = await generate_deployment_dashboard()

        # Verify content
        assert "Deployment Dashboard" in html
        assert "OneOffice" in html
        assert "API Gateway" in html


class TestDomainModelProperties:
    """Test domain model computed properties"""

    def test_deployment_frequency_is_active(self):
        """Test is_active property"""
        project_data = {
            "project_name": "Active",
            "deployment_frequency": {"total_successful_builds": 10, "deployments_per_week": 1.0},
            "build_success_rate": {"total_builds": 10, "succeeded": 10, "failed": 0, "success_rate_pct": 100.0},
            "build_duration": {"median_minutes": 5.0, "p85_minutes": 10.0},
            "lead_time_for_changes": {"median_hours": 1.0, "p85_hours": 2.0},
        }

        metrics = from_json(project_data)
        assert metrics.deployment_frequency.is_active is True
        assert metrics.is_inactive is False

    def test_deployment_frequency_is_frequent(self):
        """Test is_frequent property"""
        project_data = {
            "project_name": "Frequent",
            "deployment_frequency": {"total_successful_builds": 100, "deployments_per_week": 7.7},
            "build_success_rate": {"total_builds": 110, "succeeded": 100, "failed": 10, "success_rate_pct": 90.9},
            "build_duration": {"median_minutes": 8.5, "p85_minutes": 12.3},
            "lead_time_for_changes": {"median_hours": 2.5, "p85_hours": 6.0},
        }

        metrics = from_json(project_data)
        assert metrics.deployment_frequency.is_frequent is True

    def test_build_success_rate_is_stable(self):
        """Test is_stable property"""
        project_data = {
            "project_name": "Stable",
            "deployment_frequency": {"total_successful_builds": 90, "deployments_per_week": 7.0},
            "build_success_rate": {"total_builds": 100, "succeeded": 90, "failed": 10, "success_rate_pct": 90.0},
            "build_duration": {"median_minutes": 5.0, "p85_minutes": 10.0},
            "lead_time_for_changes": {"median_hours": 1.0, "p85_hours": 2.0},
        }

        metrics = from_json(project_data)
        assert metrics.build_success_rate.is_stable is True

    def test_deployment_metrics_is_healthy(self):
        """Test is_healthy property"""
        project_data = {
            "project_name": "Healthy",
            "deployment_frequency": {"total_successful_builds": 100, "deployments_per_week": 7.7},
            "build_success_rate": {"total_builds": 110, "succeeded": 100, "failed": 10, "success_rate_pct": 90.9},
            "build_duration": {"median_minutes": 8.5, "p85_minutes": 12.3},
            "lead_time_for_changes": {"median_hours": 2.5, "p85_hours": 6.0},
        }

        metrics = from_json(project_data)
        assert metrics.is_healthy is True
        assert metrics.status == "Good"
        assert metrics.status_class == "good"
