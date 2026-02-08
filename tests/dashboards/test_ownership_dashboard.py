"""
Tests for Ownership Dashboard

Tests the refactored ownership dashboard generator.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from execution.dashboards.ownership import (
    _build_context,
    _build_project_rows,
    _calculate_ownership_status,
    _calculate_summary,
    _generate_ownership_drilldown_html,
    _get_work_type_rag_status,
    _load_ownership_data,
    generate_ownership_dashboard,
)


class TestDataLoaders:
    """Tests for data loading functions"""

    def test_load_ownership_data_success(self, tmp_path, monkeypatch):
        """Test successful loading of ownership data"""
        # Create mock ownership history file
        ownership_data = {
            "weeks": [
                {
                    "week_number": 5,
                    "week_date": "2026-02-07",
                    "projects": [
                        {
                            "project_name": "TestProject",
                            "total_items_analyzed": 100,
                            "unassigned": {"unassigned_count": 20, "unassigned_pct": 20.0},
                            "assignment_distribution": {"assignee_count": 5, "top_assignees": [], "load_imbalance_ratio": 2.0},
                        }
                    ],
                }
            ]
        }

        # Create temp directory structure
        temp_observatory = tmp_path / ".tmp" / "observatory"
        temp_observatory.mkdir(parents=True)
        history_file = temp_observatory / "ownership_history.json"
        history_file.write_text(json.dumps(ownership_data))

        # Change to temp directory so relative paths work
        import os
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            result = _load_ownership_data()
            assert result["week_number"] == 5
            assert len(result["projects"]) == 1
        finally:
            os.chdir(original_cwd)

    def test_load_ownership_data_not_found(self, monkeypatch):
        """Test error handling when ownership file doesn't exist"""
        monkeypatch.setattr("os.path.exists", lambda x: False)

        with pytest.raises(FileNotFoundError) as exc_info:
            _load_ownership_data()

        assert "Ownership history file not found" in str(exc_info.value)


class TestStatusCalculation:
    """Tests for status calculation functions"""

    def test_calculate_ownership_status_low_unassigned(self):
        """Test status for low unassigned percentage"""
        result = _calculate_ownership_status(15.0)

        assert result["priority"] == 2  # Low priority (good)
        assert "Low Unassigned" in result["status_html"]
        assert "#10b981" in result["status_html"]  # Green color

    def test_calculate_ownership_status_medium_unassigned(self):
        """Test status for medium unassigned percentage"""
        result = _calculate_ownership_status(35.0)

        assert result["priority"] == 1  # Medium priority
        assert "Medium Unassigned" in result["status_html"]
        assert "#f59e0b" in result["status_html"]  # Amber color

    def test_calculate_ownership_status_high_unassigned(self):
        """Test status for high unassigned percentage"""
        result = _calculate_ownership_status(65.0)

        assert result["priority"] == 0  # High priority (needs action)
        assert "High Unassigned" in result["status_html"]
        assert "#ef4444" in result["status_html"]  # Red color

    def test_get_work_type_rag_status_good(self):
        """Test RAG status for good work type assignment"""
        result = _get_work_type_rag_status(15.0)

        assert result["rag_class"] == "rag-green"
        assert result["rag_color"] == "#10b981"
        assert result["status_text"] == "Good"

    def test_get_work_type_rag_status_caution(self):
        """Test RAG status for cautionary work type assignment"""
        result = _get_work_type_rag_status(35.0)

        assert result["rag_class"] == "rag-amber"
        assert result["rag_color"] == "#f59e0b"
        assert result["status_text"] == "Caution"

    def test_get_work_type_rag_status_action_needed(self):
        """Test RAG status for work type needing action"""
        result = _get_work_type_rag_status(60.0)

        assert result["rag_class"] == "rag-red"
        assert result["rag_color"] == "#ef4444"
        assert result["status_text"] == "Action Needed"


class TestSummaryCalculation:
    """Tests for summary calculation"""

    def test_calculate_summary_healthy(self):
        """Test summary calculation for healthy ownership"""
        ownership_data = {
            "projects": [
                {
                    "total_items_analyzed": 100,
                    "unassigned": {"unassigned_count": 5, "unassigned_pct": 5.0},
                },
                {
                    "total_items_analyzed": 200,
                    "unassigned": {"unassigned_count": 10, "unassigned_pct": 5.0},
                },
            ]
        }

        result = _calculate_summary(ownership_data)

        assert result["total_unassigned"] == 15
        assert result["total_all_items"] == 300
        assert result["avg_unassigned_pct"] == 5.0
        assert result["status_text"] == "HEALTHY"
        assert result["status_color"] == "#10b981"
        assert result["project_count"] == 2

    def test_calculate_summary_caution(self):
        """Test summary calculation for cautionary ownership"""
        ownership_data = {
            "projects": [
                {
                    "total_items_analyzed": 100,
                    "unassigned": {"unassigned_count": 20, "unassigned_pct": 20.0},
                }
            ]
        }

        result = _calculate_summary(ownership_data)

        assert result["avg_unassigned_pct"] == 20.0
        assert result["status_text"] == "CAUTION"
        assert result["status_color"] == "#f59e0b"

    def test_calculate_summary_action_needed(self):
        """Test summary calculation for ownership needing action"""
        ownership_data = {
            "projects": [
                {
                    "total_items_analyzed": 100,
                    "unassigned": {"unassigned_count": 40, "unassigned_pct": 40.0},
                }
            ]
        }

        result = _calculate_summary(ownership_data)

        assert result["avg_unassigned_pct"] == 40.0
        assert result["status_text"] == "ACTION NEEDED"
        assert result["status_color"] == "#f87171"


class TestProjectRows:
    """Tests for project row building"""

    def test_build_project_rows_sorting(self):
        """Test that project rows are sorted correctly"""
        projects = [
            {
                "project_name": "ProjectA",
                "total_items_analyzed": 100,
                "unassigned": {"unassigned_count": 10, "unassigned_pct": 10.0},
                "assignment_distribution": {"assignee_count": 5, "top_assignees": [], "load_imbalance_ratio": 2.0},
            },
            {
                "project_name": "ProjectB",
                "total_items_analyzed": 100,
                "unassigned": {"unassigned_count": 60, "unassigned_pct": 60.0},
                "assignment_distribution": {"assignee_count": 3, "top_assignees": [], "load_imbalance_ratio": 3.0},
            },
            {
                "project_name": "ProjectC",
                "total_items_analyzed": 100,
                "unassigned": {"unassigned_count": 30, "unassigned_pct": 30.0},
                "assignment_distribution": {"assignee_count": 4, "top_assignees": [], "load_imbalance_ratio": 2.5},
            },
        ]

        result = _build_project_rows(projects)

        # Should be sorted by priority (Red->Amber->Green), then by unassigned % descending
        assert result[0]["project_name"] == "ProjectB"  # 60% - High priority (red)
        assert result[1]["project_name"] == "ProjectC"  # 30% - Medium priority (amber)
        assert result[2]["project_name"] == "ProjectA"  # 10% - Low priority (green)

    def test_build_project_rows_with_active_days(self):
        """Test project rows with developer active days"""
        projects = [
            {
                "project_name": "ProjectA",
                "total_items_analyzed": 100,
                "unassigned": {"unassigned_count": 10, "unassigned_pct": 10.0},
                "assignment_distribution": {"assignee_count": 5, "top_assignees": [], "load_imbalance_ratio": 2.0},
                "developer_active_days": {"avg_active_days": 15.5, "sample_size": 10},
            }
        ]

        result = _build_project_rows(projects)

        assert result[0]["avg_active_days"] == 15.5
        assert result[0]["sample_size"] == 10


class TestDrilldownHtml:
    """Tests for drill-down HTML generation"""

    def test_generate_ownership_drilldown_html_basic(self):
        """Test basic drill-down HTML generation"""
        project = {
            "assignment_distribution": {
                "top_assignees": [("Alice", 30), ("Bob", 20), ("Unassigned", 10)],
                "load_imbalance_ratio": 2.5,
            },
            "work_type_segmentation": {
                "Bug": {"total": 50, "unassigned": 10, "unassigned_pct": 20.0}
            },
            "area_unassigned_stats": {
                "areas": [
                    {"area_path": "Area1", "total_items": 100, "unassigned_items": 20, "unassigned_pct": 20.0}
                ]
            },
        }

        html = _generate_ownership_drilldown_html(project)

        assert "Alice" in html
        assert "Bob" in html
        # Note: "Unassigned" appears in section headers like "Area Unassigned Statistics"
        # but should not appear as an assignee in the assignment distribution
        assert html.count("Alice") >= 1
        assert html.count("Bob") >= 1
        assert "2.5:1" in html  # Load imbalance
        assert "Bug" in html
        assert "Area1" in html


class TestDashboardGeneration:
    """Tests for main dashboard generation"""

    @patch("execution.dashboards.ownership._load_ownership_data")
    @patch("execution.dashboards.ownership.render_dashboard")
    def test_generate_ownership_dashboard_success(self, mock_render, mock_load, tmp_path):
        """Test successful dashboard generation"""
        # Setup mocks
        mock_load.return_value = {
            "week_number": 5,
            "week_date": "2026-02-07",
            "projects": [
                {
                    "project_name": "TestProject",
                    "total_items_analyzed": 100,
                    "unassigned": {"unassigned_count": 10, "unassigned_pct": 10.0},
                    "assignment_distribution": {"assignee_count": 5, "top_assignees": [], "load_imbalance_ratio": 2.0},
                }
            ],
        }

        mock_render.return_value = "<html>Dashboard HTML</html>"

        output_path = tmp_path / "ownership_dashboard.html"
        html = generate_ownership_dashboard(output_path)

        # Verify
        assert html == "<html>Dashboard HTML</html>"
        assert output_path.exists()
        assert mock_render.called
        assert mock_load.called

    @patch("execution.dashboards.ownership._load_ownership_data")
    def test_generate_ownership_dashboard_missing_data(self, mock_load):
        """Test dashboard generation with missing data file"""
        mock_load.side_effect = FileNotFoundError("Ownership history file not found")

        with pytest.raises(FileNotFoundError):
            generate_ownership_dashboard()

    @patch("execution.dashboards.ownership._load_ownership_data")
    @patch("execution.dashboards.ownership.render_dashboard")
    def test_generate_ownership_dashboard_no_output_path(self, mock_render, mock_load):
        """Test dashboard generation without writing to file"""
        mock_load.return_value = {
            "week_number": 5,
            "week_date": "2026-02-07",
            "projects": [
                {
                    "project_name": "TestProject",
                    "total_items_analyzed": 100,
                    "unassigned": {"unassigned_count": 10, "unassigned_pct": 10.0},
                    "assignment_distribution": {"assignee_count": 5, "top_assignees": [], "load_imbalance_ratio": 2.0},
                }
            ],
        }

        mock_render.return_value = "<html>Dashboard</html>"

        html = generate_ownership_dashboard(output_path=None)

        assert html == "<html>Dashboard</html>"
        assert mock_render.called


class TestContextBuilder:
    """Tests for template context building"""

    def test_build_context_structure(self):
        """Test that context has all required fields"""
        ownership_data = {
            "week_number": 5,
            "week_date": "2026-02-07",
            "projects": [
                {
                    "project_name": "TestProject",
                    "total_items_analyzed": 100,
                    "unassigned": {"unassigned_count": 10, "unassigned_pct": 10.0},
                    "assignment_distribution": {"assignee_count": 5, "top_assignees": [], "load_imbalance_ratio": 2.0},
                }
            ],
        }

        summary_stats = {
            "total_unassigned": 10,
            "total_all_items": 100,
            "avg_unassigned_pct": 10.0,
            "status_color": "#10b981",
            "status_text": "HEALTHY",
            "project_count": 1,
        }

        context = _build_context(ownership_data, summary_stats)

        # Check required fields
        assert "framework_css" in context
        assert "framework_js" in context
        assert "week_number" in context
        assert "week_date" in context
        assert "summary_stats" in context
        assert "project_rows" in context
