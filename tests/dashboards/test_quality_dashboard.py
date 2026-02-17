"""
Tests for Quality Dashboard Generator

Tests cover:
- Dashboard generation
- Summary calculation
- Context building
- Project row generation
- RAG status determination
- Distribution section generation
- Error handling
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

import pytest

from execution.dashboards.quality import (
    _build_context,
    _build_project_rows,
    _calculate_composite_status,
    _calculate_summary,
    _generate_drilldown_html,
    _get_metric_rag_status,
    _query_quality_data,
    generate_quality_dashboard,
)
from execution.dashboards.quality_legacy import (
    build_summary_cards,
    generate_distribution_section,
    get_distribution_bucket_rag_status,
)


@pytest.fixture
def sample_quality_data():
    """Sample quality data for testing"""
    return {
        "week_number": 5,
        "week_date": "2026-02-07",
        "projects": [
            {
                "project_name": "API Gateway",
                "total_bugs_analyzed": 100,
                "open_bugs_count": 25,
                "bug_age_distribution": {
                    "median_age_days": 15.5,
                    "p85_age_days": 45.2,
                    "p95_age_days": 120.8,
                    "ages_distribution": {
                        "0-7_days": 10,
                        "8-30_days": 8,
                        "31-90_days": 5,
                        "90+_days": 2,
                    },
                },
                "mttr": {
                    "mttr_days": 5.2,
                    "p85_mttr_days": 12.5,
                    "p95_mttr_days": 18.9,
                    "mttr_distribution": {
                        "0-1_days": 15,
                        "1-7_days": 20,
                        "7-30_days": 8,
                        "30+_days": 2,
                    },
                },
                "excluded_security_bugs": {"total": 3, "open": 1},
            },
            {
                "project_name": "Web App",
                "total_bugs_analyzed": 80,
                "open_bugs_count": 15,
                "bug_age_distribution": {
                    "median_age_days": 8.0,
                    "p85_age_days": 35.0,
                    "p95_age_days": 75.0,
                    "ages_distribution": {
                        "0-7_days": 7,
                        "8-30_days": 5,
                        "31-90_days": 2,
                        "90+_days": 1,
                    },
                },
                "mttr": {
                    "mttr_days": 4.5,
                    "p85_mttr_days": 10.0,
                    "p95_mttr_days": 15.0,
                    "mttr_distribution": {
                        "0-1_days": 12,
                        "1-7_days": 18,
                        "7-30_days": 5,
                        "30+_days": 1,
                    },
                },
                "excluded_security_bugs": {"total": 2, "open": 0},
            },
        ],
    }


@pytest.fixture
def sample_discovery_data():
    """Sample discovery data for testing"""
    return {
        "projects": [
            {"project_name": "API Gateway", "project_key": "api-gateway"},
            {"project_name": "Web App", "project_key": "web-app"},
        ]
    }


@pytest.fixture
def temp_quality_file(tmp_path):
    """Create a temporary quality history file"""
    return tmp_path / "quality_history.json"


class TestQueryQualityData:
    """Test querying quality data from ADO API"""

    @pytest.mark.asyncio
    async def test_query_quality_data_success(self, sample_discovery_data, sample_quality_data):
        """Test successful querying of quality data from ADO API"""
        mock_project_metrics = sample_quality_data["projects"]

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(sample_discovery_data))):
                with patch("execution.dashboards.quality.get_ado_rest_client"):
                    with patch(
                        "execution.dashboards.quality.collect_quality_metrics_for_project",
                        side_effect=[
                            AsyncMock(return_value=mock_project_metrics[0])(),
                            AsyncMock(return_value=mock_project_metrics[1])(),
                        ],
                    ):
                        data = await _query_quality_data()

                        assert data["week_number"] > 0
                        assert data["week_date"]
                        assert len(data["projects"]) == 2
                        assert data["projects"][0]["project_name"] == "API Gateway"

    @pytest.mark.asyncio
    async def test_query_quality_data_file_not_found(self):
        """Test FileNotFoundError when discovery file doesn't exist"""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError) as exc_info:
                await _query_quality_data()

            assert "Discovery data not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_quality_data_no_projects(self):
        """Test ValueError when no projects in discovery"""
        discovery_data = {"projects": []}

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(discovery_data))):
                with pytest.raises(ValueError) as exc_info:
                    await _query_quality_data()

                assert "No projects found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_quality_data_handles_exceptions(self, sample_discovery_data):
        """Test that API exceptions are handled gracefully"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(sample_discovery_data))):
                with patch("execution.dashboards.quality.get_ado_rest_client"):
                    with patch(
                        "execution.dashboards.quality.collect_quality_metrics_for_project",
                        side_effect=[Exception("API Error"), Exception("API Error")],
                    ):
                        with pytest.raises(Exception) as exc_info:
                            await _query_quality_data()

                        assert "Failed to collect metrics" in str(exc_info.value)


class TestCalculateSummary:
    """Test summary statistics calculation"""

    def test_calculate_summary_basic(self, sample_quality_data):
        """Test basic summary calculation"""
        summary = _calculate_summary(sample_quality_data["projects"])

        assert summary["total_bugs"] == 180  # 100 + 80
        assert summary["total_open"] == 40  # 25 + 15
        assert summary["total_excluded"] == 5  # 3 + 2
        assert summary["project_count"] == 2

    def test_calculate_summary_mttr_average(self, sample_quality_data):
        """Test MTTR average calculation"""
        summary = _calculate_summary(sample_quality_data["projects"])

        # Average MTTR should be (5.2 + 4.5) / 2 = 4.85
        assert abs(summary["avg_mttr"] - 4.85) < 0.01

    def test_calculate_summary_status_healthy(self, sample_quality_data):
        """Test status determination for healthy MTTR"""
        summary = _calculate_summary(sample_quality_data["projects"])

        # avg_mttr = 4.85 < 7, so status should be HEALTHY
        assert summary["status_text"] == "HEALTHY"
        assert summary["status_color"] == "#10b981"

    def test_calculate_summary_status_caution(self):
        """Test status determination for caution-level MTTR"""
        projects = [
            {"total_bugs_analyzed": 50, "open_bugs_count": 10, "mttr": {"mttr_days": 10.0}},
            {"total_bugs_analyzed": 50, "open_bugs_count": 10, "mttr": {"mttr_days": 12.0}},
        ]

        summary = _calculate_summary(projects)

        # avg_mttr = 11.0 (between 7-14), so status should be CAUTION
        assert summary["status_text"] == "CAUTION"
        assert summary["status_color"] == "#f59e0b"

    def test_calculate_summary_status_action_needed(self):
        """Test status determination for action-needed MTTR"""
        projects = [
            {"total_bugs_analyzed": 50, "open_bugs_count": 10, "mttr": {"mttr_days": 20.0}},
            {"total_bugs_analyzed": 50, "open_bugs_count": 10, "mttr": {"mttr_days": 25.0}},
        ]

        summary = _calculate_summary(projects)

        # avg_mttr = 22.5 > 14, so status should be ACTION NEEDED
        assert summary["status_text"] == "ACTION NEEDED"
        assert summary["status_color"] == "#f87171"

    def test_calculate_summary_no_mttr_data(self):
        """Test summary with missing MTTR data"""
        projects = [
            {"total_bugs_analyzed": 50, "open_bugs_count": 10, "mttr": {}},
            {"total_bugs_analyzed": 50, "open_bugs_count": 10},
        ]

        summary = _calculate_summary(projects)

        # No valid MTTR data, avg should be 0
        assert summary["avg_mttr"] == 0


class TestBuildSummaryCards:
    """Test summary cards generation"""

    def testbuild_summary_cards_count(self):
        """Test that 4 summary cards are generated"""
        summary_stats = {
            "avg_mttr": 5.5,
            "total_bugs": 180,
            "total_open": 40,
            "total_excluded": 5,
        }

        cards = build_summary_cards(summary_stats)

        assert len(cards) == 4

    def testbuild_summary_cards_mttr_content(self):
        """Test MTTR card content"""
        summary_stats = {
            "avg_mttr": 5.5,
            "total_bugs": 180,
            "total_open": 40,
            "total_excluded": 5,
        }

        cards = build_summary_cards(summary_stats)

        # First card should be MTTR
        assert "MTTR" in cards[0]
        assert "5.5" in cards[0]
        assert "days" in cards[0]

    def testbuild_summary_cards_formatting(self):
        """Test that cards have proper HTML structure"""
        summary_stats = {
            "avg_mttr": 5.5,
            "total_bugs": 1234,
            "total_open": 567,
            "total_excluded": 89,
        }

        cards = build_summary_cards(summary_stats)

        # Check for comma formatting
        assert "1,234" in cards[1]  # Total bugs card
        assert "567" in cards[2]  # Open bugs card


class TestCalculateCompositeStatus:
    """Test composite status calculation"""

    def test_status_good_all_metrics(self):
        """Test Good status when all metrics meet targets"""
        status_html, tooltip, priority = _calculate_composite_status(mttr=5.0, median_age=20.0)

        assert "Good" in status_html
        assert "#10b981" in status_html  # Green color
        assert priority == 2

    def test_status_caution_one_metric(self):
        """Test Caution status when one metric needs attention"""
        status_html, tooltip, priority = _calculate_composite_status(mttr=10.0, median_age=20.0)

        assert "Caution" in status_html
        assert "#f59e0b" in status_html  # Amber color
        assert priority == 1

    def test_status_action_needed_both_poor(self):
        """Test Action Needed when both metrics are poor"""
        status_html, tooltip, priority = _calculate_composite_status(mttr=20.0, median_age=80.0)

        assert "Action Needed" in status_html
        assert "#ef4444" in status_html  # Red color
        assert priority == 0

    def test_tooltip_content(self):
        """Test tooltip contains metric details"""
        status_html, tooltip, priority = _calculate_composite_status(mttr=10.0, median_age=45.0)

        assert "MTTR" in tooltip
        assert "10.0 days" in tooltip
        assert "Median bug age" in tooltip
        assert "45 days" in tooltip

    def test_none_values_handled(self):
        """Test that None values are handled gracefully"""
        status_html, tooltip, priority = _calculate_composite_status(mttr=None, median_age=None)

        # With no metrics, should default to Good
        assert priority == 2


class TestGetMetricRagStatus:
    """Test RAG status determination for metrics"""

    def test_bug_age_p85_green(self):
        """Test Bug Age P85 green threshold"""
        rag_class, color, status = _get_metric_rag_status("Bug Age P85", 45.0)

        assert rag_class == "rag-green"
        assert color == "#10b981"
        assert status == "Good"

    def test_bug_age_p85_amber(self):
        """Test Bug Age P85 amber threshold"""
        rag_class, color, status = _get_metric_rag_status("Bug Age P85", 120.0)

        assert rag_class == "rag-amber"
        assert color == "#f59e0b"
        assert status == "Caution"

    def test_bug_age_p85_red(self):
        """Test Bug Age P85 red threshold"""
        rag_class, color, status = _get_metric_rag_status("Bug Age P85", 200.0)

        assert rag_class == "rag-red"
        assert color == "#ef4444"
        assert status == "Action Needed"

    def test_mttr_p95_thresholds(self):
        """Test MTTR P95 RAG thresholds"""
        # Green
        rag_class, _, status = _get_metric_rag_status("MTTR P95", 15.0)
        assert rag_class == "rag-green"

        # Amber
        rag_class, _, status = _get_metric_rag_status("MTTR P95", 30.0)
        assert rag_class == "rag-amber"

        # Red
        rag_class, _, status = _get_metric_rag_status("MTTR P95", 50.0)
        assert rag_class == "rag-red"

    def test_none_value_returns_unknown(self):
        """Test that None returns unknown status"""
        rag_class, color, status = _get_metric_rag_status("Bug Age P85", None)

        assert rag_class == "rag-unknown"
        assert color == "#6b7280"
        assert status == "No Data"


class TestGetDistributionBucketRagStatus:
    """Test RAG status for distribution buckets"""

    def test_bug_age_distribution_colors(self):
        """Test bug age distribution bucket colors"""
        # Green buckets
        rag_class, color = get_distribution_bucket_rag_status("bug_age", "0-7_days")
        assert rag_class == "rag-green"

        rag_class, color = get_distribution_bucket_rag_status("bug_age", "8-30_days")
        assert rag_class == "rag-green"

        # Amber bucket
        rag_class, color = get_distribution_bucket_rag_status("bug_age", "31-90_days")
        assert rag_class == "rag-amber"

        # Red bucket
        rag_class, color = get_distribution_bucket_rag_status("bug_age", "90+_days")
        assert rag_class == "rag-red"

    def test_mttr_distribution_colors(self):
        """Test MTTR distribution bucket colors"""
        # Green buckets
        rag_class, color = get_distribution_bucket_rag_status("mttr", "0-1_days")
        assert rag_class == "rag-green"

        rag_class, color = get_distribution_bucket_rag_status("mttr", "1-7_days")
        assert rag_class == "rag-green"

        # Amber bucket
        rag_class, color = get_distribution_bucket_rag_status("mttr", "7-30_days")
        assert rag_class == "rag-amber"

        # Red bucket
        rag_class, color = get_distribution_bucket_rag_status("mttr", "30+_days")
        assert rag_class == "rag-red"


class TestGenerateDistributionSection:
    """Test distribution section generation"""

    def test_bug_age_distribution_section(self):
        """Test bug age distribution section HTML"""
        distribution = {"0-7_days": 10, "8-30_days": 8, "31-90_days": 5, "90+_days": 2}

        html = generate_distribution_section("Bug Age Distribution", distribution, "bug_age", "bugs")

        assert "Bug Age Distribution" in html
        assert "0-7 Days" in html
        assert "10 bugs" in html
        assert "90+ Days" in html
        assert "2 bugs" in html

    def test_mttr_distribution_section(self):
        """Test MTTR distribution section HTML"""
        distribution = {"0-1_days": 15, "1-7_days": 20, "7-30_days": 8, "30+_days": 2}

        html = generate_distribution_section("MTTR Distribution", distribution, "mttr", "bugs")

        assert "MTTR Distribution" in html
        assert "0-1 Days" in html
        assert "15 bugs" in html
        assert "30+ Days" in html
        assert "2 bugs" in html


class TestGenerateDrilldownHtml:
    """Test drill-down HTML generation"""

    def test_generate_drilldown_with_full_data(self, sample_quality_data):
        """Test drill-down generation with complete data"""
        project = sample_quality_data["projects"][0]
        html = _generate_drilldown_html(project)

        assert "detail-content" in html
        assert "Detailed Metrics" in html
        assert "Bug Age Distribution" in html
        assert "MTTR Distribution" in html

    def test_generate_drilldown_with_no_data(self):
        """Test drill-down with missing data"""
        project = {
            "project_name": "Empty Project",
            "bug_age_distribution": {},
            "mttr": {},
        }

        html = _generate_drilldown_html(project)

        assert "No detailed metrics available" in html


class TestBuildProjectRows:
    """Test project row generation"""

    def test_build_project_rows_count(self, sample_quality_data):
        """Test correct number of project rows"""
        rows = _build_project_rows(sample_quality_data["projects"])

        assert len(rows) == 2

    def test_build_project_rows_content(self, sample_quality_data):
        """Test project row content"""
        rows = _build_project_rows(sample_quality_data["projects"])

        # Check first project
        assert rows[0]["name"] == "API Gateway"
        assert rows[0]["open_bugs"] == 25
        assert "days" in rows[0]["mttr_str"]
        assert "days" in rows[0]["median_age_str"]

    def test_build_project_rows_sorting(self):
        """Test project rows are sorted by status priority"""
        projects = [
            {
                "project_name": "Good Project",
                "open_bugs_count": 5,
                "bug_age_distribution": {"median_age_days": 10.0},
                "mttr": {"mttr_days": 5.0},
            },
            {
                "project_name": "Bad Project",
                "open_bugs_count": 20,
                "bug_age_distribution": {"median_age_days": 80.0},
                "mttr": {"mttr_days": 20.0},
            },
        ]

        rows = _build_project_rows(projects)

        # Bad project should be first (higher priority = lower number)
        assert rows[0]["name"] == "Bad Project"
        assert rows[1]["name"] == "Good Project"


class TestBuildContext:
    """Test context building for template"""

    def test_build_context_keys(self, sample_quality_data):
        """Test that context has all required keys"""
        summary = _calculate_summary(sample_quality_data["projects"])
        context = _build_context(sample_quality_data, summary)

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

    def test_build_context_values(self, sample_quality_data):
        """Test context values are correct"""
        summary = _calculate_summary(sample_quality_data["projects"])
        context = _build_context(sample_quality_data, summary)

        assert context["week_number"] == 5
        assert context["week_date"] == "2026-02-07"
        assert context["project_count"] == 2
        assert len(context["summary_cards"]) == 4
        assert len(context["projects"]) == 2


class TestGenerateQualityDashboard:
    """Test main dashboard generation function"""

    @pytest.mark.asyncio
    @patch("execution.dashboards.quality._query_quality_data")
    @patch("execution.dashboards.quality.render_dashboard")
    async def test_generate_dashboard_success(self, mock_render, mock_query, sample_quality_data):
        """Test successful dashboard generation"""
        mock_query.return_value = sample_quality_data
        mock_render.return_value = "<html>Dashboard</html>"

        html = await generate_quality_dashboard()

        assert html == "<html>Dashboard</html>"
        mock_query.assert_called_once()
        mock_render.assert_called_once()

    @pytest.mark.asyncio
    @patch("execution.dashboards.quality._query_quality_data")
    @patch("execution.dashboards.quality.render_dashboard")
    async def test_generate_dashboard_with_output_path(self, mock_render, mock_query, sample_quality_data, tmp_path):
        """Test dashboard generation with file output"""
        mock_query.return_value = sample_quality_data
        mock_render.return_value = "<html>Dashboard</html>"

        output_path = tmp_path / "quality.html"
        html = await generate_quality_dashboard(output_path)

        assert output_path.exists()
        assert output_path.read_text(encoding="utf-8") == "<html>Dashboard</html>"

    @pytest.mark.asyncio
    @patch("execution.dashboards.quality._query_quality_data")
    async def test_generate_dashboard_file_not_found(self, mock_query):
        """Test dashboard generation with missing discovery file"""
        mock_query.side_effect = FileNotFoundError("Discovery data not found")

        with pytest.raises(FileNotFoundError):
            await generate_quality_dashboard()


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_projects_with_none_mttr(self):
        """Test handling projects with None MTTR values"""
        projects = [
            {
                "project_name": "No MTTR",
                "total_bugs_analyzed": 50,
                "open_bugs_count": 10,
                "bug_age_distribution": {"median_age_days": 15.0},
                "mttr": {"mttr_days": None},
            }
        ]

        rows = _build_project_rows(projects)

        assert rows[0]["mttr_str"] == "N/A"

    def test_projects_with_none_median_age(self):
        """Test handling projects with None median age"""
        projects = [
            {
                "project_name": "No Age",
                "total_bugs_analyzed": 50,
                "open_bugs_count": 10,
                "bug_age_distribution": {"median_age_days": None},
                "mttr": {"mttr_days": 5.0},
            }
        ]

        rows = _build_project_rows(projects)

        assert rows[0]["median_age_str"] == "N/A"

    def test_empty_projects_list(self):
        """Test handling empty projects list"""
        summary = _calculate_summary([])

        assert summary["total_bugs"] == 0
        assert summary["total_open"] == 0
        assert summary["avg_mttr"] == 0
        assert summary["project_count"] == 0

    def test_project_missing_excluded_bugs(self):
        """Test handling project without excluded_security_bugs field"""
        projects = [
            {
                "project_name": "Legacy",
                "total_bugs_analyzed": 50,
                "open_bugs_count": 10,
                "bug_age_distribution": {"median_age_days": 15.0},
                "mttr": {"mttr_days": 5.0},
                # No excluded_security_bugs field
            }
        ]

        summary = _calculate_summary(projects)

        # Should handle missing field gracefully
        assert summary["total_excluded"] == 0
