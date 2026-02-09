"""
Tests for Flow Dashboard Generator

Tests cover:
- Data loading (FlowDataLoader)
- Portfolio summary calculation
- Status determination
- Summary card generation
- Work type card generation
- Project row formatting
- Project table building
- Context building
- Dashboard generation
- Error handling
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from execution.dashboards.flow import FlowDataLoader, _build_context, generate_flow_dashboard
from execution.dashboards.flow_helpers import (
    build_project_tables,
    build_summary_cards,
    build_work_type_cards,
    calculate_portfolio_summary,
    calculate_status,
    format_project_row,
)


@pytest.fixture
def sample_flow_data():
    """Sample flow data for testing"""
    return {
        "week_number": 6,
        "week_date": "2026-02-06",
        "projects": [
            {
                "project_name": "OneOffice",
                "work_type_metrics": {
                    "Bug": {
                        "open_count": 125,
                        "closed_count_90d": 45,
                        "lead_time": {"p50": 7.5, "p85": 15.2, "p95": 25.8, "sample_size": 45},
                        "throughput": {"per_week": 0.5, "closed_count": 45},
                        "cycle_time_variance": {"std_dev_days": 8.2, "coefficient_of_variation": 110.0},
                        "dual_metrics": {
                            "operational": {"p50": 7.2, "p85": 14.8, "closed_count": 42},
                            "cleanup": {"p50": 485.0, "p85": 620.3, "closed_count": 3},
                            "indicators": {"is_cleanup_effort": False, "cleanup_percentage": 6.7},
                        },
                    },
                    "User Story": {
                        "open_count": 50,
                        "closed_count_90d": 20,
                        "lead_time": {"p50": 12.0, "p85": 30.0, "p95": 45.0, "sample_size": 20},
                        "throughput": {"per_week": 0.3, "closed_count": 20},
                        "cycle_time_variance": {"std_dev_days": 10.0, "coefficient_of_variation": 83.3},
                        "dual_metrics": {"operational": {}, "cleanup": {}, "indicators": {}},
                    },
                    "Task": {
                        "open_count": 30,
                        "closed_count_90d": 15,
                        "lead_time": {"p50": 5.0, "p85": 12.0, "p95": 18.0, "sample_size": 15},
                        "throughput": {"per_week": 0.2, "closed_count": 15},
                        "cycle_time_variance": {"std_dev_days": 5.0, "coefficient_of_variation": 100.0},
                        "dual_metrics": {"operational": {}, "cleanup": {}, "indicators": {}},
                    },
                },
            },
            {
                "project_name": "API Gateway",
                "work_type_metrics": {
                    "Bug": {
                        "open_count": 75,
                        "closed_count_90d": 30,
                        "lead_time": {"p50": 10.0, "p85": 25.0, "p95": 40.0, "sample_size": 30},
                        "throughput": {"per_week": 0.4, "closed_count": 30},
                        "cycle_time_variance": {"std_dev_days": 12.0, "coefficient_of_variation": 120.0},
                        "dual_metrics": {"operational": {}, "cleanup": {}, "indicators": {}},
                    }
                },
            },
        ],
    }


@pytest.fixture
def temp_flow_file(tmp_path):
    """Create a temporary flow history file"""
    return tmp_path / "flow_history.json"


class TestFlowDataLoader:
    """Test FlowDataLoader class"""

    def test_init_default_path(self):
        """Test initialization with default path"""
        loader = FlowDataLoader()

        assert loader.history_file == Path(".tmp/observatory/flow_history.json")

    def test_init_custom_path(self):
        """Test initialization with custom path"""
        custom_path = Path("custom/path/flow.json")
        loader = FlowDataLoader(custom_path)

        assert loader.history_file == custom_path

    def test_load_latest_week_success(self, sample_flow_data):
        """Test successful loading of latest week"""
        history_data = {"weeks": [sample_flow_data]}

        with patch("builtins.open", mock_open(read_data=json.dumps(history_data))):
            loader = FlowDataLoader()
            data = loader.load_latest_week()

            assert data["week_number"] == 6
            assert data["week_date"] == "2026-02-06"
            assert len(data["projects"]) == 2

    def test_load_latest_week_file_not_found(self):
        """Test FileNotFoundError when history file doesn't exist"""
        loader = FlowDataLoader(Path("nonexistent.json"))

        with pytest.raises(FileNotFoundError):
            loader.load_latest_week()

    def test_load_latest_week_no_weeks(self):
        """Test ValueError when weeks array is empty"""
        history_data = {"weeks": []}

        with patch("builtins.open", mock_open(read_data=json.dumps(history_data))):
            loader = FlowDataLoader()

            with pytest.raises(ValueError) as exc_info:
                loader.load_latest_week()

            assert "No weeks data" in str(exc_info.value)

    def test_load_latest_week_returns_most_recent(self):
        """Test that loading returns the most recent week"""
        history_data = {
            "weeks": [
                {"week_number": 5, "week_date": "2026-01-30", "projects": []},
                {"week_number": 6, "week_date": "2026-02-06", "projects": []},
            ]
        }

        with patch("builtins.open", mock_open(read_data=json.dumps(history_data))):
            loader = FlowDataLoader()
            data = loader.load_latest_week()

            assert data["week_number"] == 6
            assert data["week_date"] == "2026-02-06"


class TestCalculatePortfolioSummary:
    """Test portfolio summary calculation"""

    def test_calculate_summary_basic(self, sample_flow_data):
        """Test basic summary calculation"""
        summary = calculate_portfolio_summary(sample_flow_data)

        assert summary["project_count"] == 2
        assert summary["total_wip"] == 280  # 125+50+30+75
        assert summary["total_closed"] == 110  # 45+20+15+30

    def test_calculate_summary_lead_times(self, sample_flow_data):
        """Test lead time aggregation"""
        summary = calculate_portfolio_summary(sample_flow_data)

        # Should have lead times from Bug, User Story, Task for project 1, and Bug for project 2
        assert len(summary["by_type"]["Bug"]["lead_times"]) == 2  # 15.2, 25.0
        assert len(summary["by_type"]["User Story"]["lead_times"]) == 1  # 30.0
        assert len(summary["by_type"]["Task"]["lead_times"]) == 1  # 12.0

    def test_calculate_summary_average_lead_time(self, sample_flow_data):
        """Test average lead time calculation"""
        summary = calculate_portfolio_summary(sample_flow_data)

        # Average of 15.2, 30.0, 12.0, 25.0 = 20.55
        expected_avg = (15.2 + 30.0 + 12.0 + 25.0) / 4
        assert abs(summary["avg_lead_time"] - expected_avg) < 0.01

    def test_calculate_summary_by_type(self, sample_flow_data):
        """Test work type breakdown"""
        summary = calculate_portfolio_summary(sample_flow_data)

        # Check Bug totals
        assert summary["by_type"]["Bug"]["open"] == 200  # 125 + 75
        assert summary["by_type"]["Bug"]["closed"] == 75  # 45 + 30

        # Check User Story totals
        assert summary["by_type"]["User Story"]["open"] == 50
        assert summary["by_type"]["User Story"]["closed"] == 20

        # Check Task totals
        assert summary["by_type"]["Task"]["open"] == 30
        assert summary["by_type"]["Task"]["closed"] == 15

    def test_calculate_summary_no_lead_times(self):
        """Test summary with no valid lead times"""
        week_data = {"projects": [{"work_type_metrics": {"Bug": {"open_count": 10, "closed_count_90d": 5}}}]}

        summary = calculate_portfolio_summary(week_data)

        assert summary["avg_lead_time"] == 0

    def test_calculate_summary_empty_projects(self):
        """Test summary with empty projects list"""
        week_data = {"projects": []}

        summary = calculate_portfolio_summary(week_data)

        assert summary["project_count"] == 0
        assert summary["total_wip"] == 0
        assert summary["total_closed"] == 0
        assert summary["avg_lead_time"] == 0


class TestCalculateStatus:
    """Test status calculation"""

    def test_status_good_all_metrics(self):
        """Test Good status when all metrics meet targets"""
        status_html, tooltip, priority = calculate_status(p85=50.0, p50=25.0)

        assert "Good" in status_html
        assert "#10b981" in status_html  # Green
        assert priority == 2

    def test_status_caution_one_metric_poor(self):
        """Test Caution status when one metric is poor"""
        status_html, tooltip, priority = calculate_status(p85=160.0, p50=25.0)

        assert "Caution" in status_html
        assert "#f59e0b" in status_html  # Amber
        assert priority == 1

    def test_status_caution_both_caution(self):
        """Test Caution status when both metrics in caution range"""
        status_html, tooltip, priority = calculate_status(p85=80.0, p50=50.0)

        assert "Caution" in status_html
        assert "#f59e0b" in status_html  # Amber
        assert priority == 1

    def test_status_action_needed_both_poor(self):
        """Test Action Needed when both metrics are poor"""
        status_html, tooltip, priority = calculate_status(p85=200.0, p50=100.0)

        assert "Action Needed" in status_html
        assert "#ef4444" in status_html  # Red
        assert priority == 0

    def test_tooltip_content(self):
        """Test tooltip contains metric details"""
        status_html, tooltip, priority = calculate_status(p85=80.0, p50=50.0)

        assert "P85 Lead Time" in tooltip
        assert "80.0 days" in tooltip
        assert "Median Lead Time" in tooltip
        assert "50.0 days" in tooltip
        assert "caution" in tooltip.lower()

    def test_status_with_zero_values(self):
        """Test status with zero values"""
        status_html, tooltip, priority = calculate_status(p85=0, p50=0)

        # With no data, should default to Good
        assert priority == 2
        assert "no data" in tooltip.lower()


class TestBuildSummaryCards:
    """Test summary cards generation"""

    def testbuild_summary_cards_count(self):
        """Test that 4 summary cards are generated"""
        summary_stats = {"avg_lead_time": 20.5, "total_wip": 280, "total_closed": 110, "project_count": 2}

        cards = build_summary_cards(summary_stats)

        assert len(cards) == 4

    def testbuild_summary_cards_content(self):
        """Test summary card content"""
        summary_stats = {"avg_lead_time": 20.5, "total_wip": 280, "total_closed": 110, "project_count": 2}

        cards = build_summary_cards(summary_stats)

        # Check for key content
        assert "Average Lead Time" in cards[0]
        assert "20" in cards[0] or "21" in cards[0]  # Rounded (can be either depending on implementation)
        assert "Total WIP" in cards[1]
        assert "280" in cards[1]
        assert "Closed" in cards[2]
        assert "110" in cards[2]
        assert "Projects" in cards[3]
        assert "2" in cards[3]

    def testbuild_summary_cards_formatting(self):
        """Test that cards have proper formatting"""
        summary_stats = {"avg_lead_time": 123.4, "total_wip": 1234, "total_closed": 567, "project_count": 10}

        cards = build_summary_cards(summary_stats)

        # Check for comma formatting
        assert "1,234" in cards[1]  # WIP card
        assert "567" in cards[2]  # Closed card


class TestBuildWorkTypeCards:
    """Test work type cards generation"""

    def testbuild_work_type_cards_count(self):
        """Test that 3 work type cards are generated"""
        summary_stats = {
            "by_type": {
                "Bug": {"open": 200, "closed": 75},
                "User Story": {"open": 50, "closed": 20},
                "Task": {"open": 30, "closed": 15},
            }
        }

        cards = build_work_type_cards(summary_stats)

        assert len(cards) == 3

    def testbuild_work_type_cards_content(self):
        """Test work type card content"""
        summary_stats = {
            "by_type": {
                "Bug": {"open": 200, "closed": 75},
                "User Story": {"open": 50, "closed": 20},
                "Task": {"open": 30, "closed": 15},
            }
        }

        cards = build_work_type_cards(summary_stats)

        # Check Bug card
        assert "Bugs" in cards[0]
        assert "200" in cards[0]
        assert "75" in cards[0]

        # Check User Story card
        assert "User Stories" in cards[1]
        assert "50" in cards[1]
        assert "20" in cards[1]

        # Check Task card
        assert "Tasks" in cards[2]
        assert "30" in cards[2]
        assert "15" in cards[2]

    def testbuild_work_type_cards_colors(self):
        """Test work type cards have color styling"""
        summary_stats = {
            "by_type": {
                "Bug": {"open": 200, "closed": 75},
                "User Story": {"open": 50, "closed": 20},
                "Task": {"open": 30, "closed": 15},
            }
        }

        cards = build_work_type_cards(summary_stats)

        # Check for color codes
        assert "#ef4444" in cards[0]  # Bug - Red
        assert "#3b82f6" in cards[1]  # User Story - Blue
        assert "#10b981" in cards[2]  # Task - Green


class TestFormatProjectRow:
    """Test project row formatting"""

    def testformat_project_row_basic(self, sample_flow_data):
        """Test basic project row formatting"""
        project = sample_flow_data["projects"][0]
        row = format_project_row(project, "Bug")

        assert row is not None
        assert row["name"] == "OneOffice"
        assert row["p85"] == "15.2"
        assert row["p50"] == "7.5"
        assert row["throughput"] == "0.5"
        assert row["cv"] == "110"
        assert row["open"] == "125"
        assert row["closed"] == "45"

    def testformat_project_row_with_cleanup(self, sample_flow_data):
        """Test project row with cleanup work"""
        project = sample_flow_data["projects"][0]
        row = format_project_row(project, "Bug")

        assert not row["has_cleanup"]  # Sample has is_cleanup_effort=False
        assert row["cleanup_pct"] == "6.7"

    def testformat_project_row_no_data(self, sample_flow_data):
        """Test project row with no data for work type"""
        project = sample_flow_data["projects"][1]  # API Gateway doesn't have Task data
        row = format_project_row(project, "Task")

        assert row is None

    def testformat_project_row_status(self, sample_flow_data):
        """Test project row includes status"""
        project = sample_flow_data["projects"][0]
        row = format_project_row(project, "Bug")

        assert "status_html" in row
        assert "status_tooltip" in row
        assert "status_priority" in row
        assert isinstance(row["status_priority"], int)


class TestBuildProjectTables:
    """Test project table building"""

    def testbuild_project_tables_count(self, sample_flow_data):
        """Test that 3 work type tables are built"""
        summary_stats = calculate_portfolio_summary(sample_flow_data)
        tables = build_project_tables(sample_flow_data, summary_stats)

        assert len(tables) == 3

    def testbuild_project_tables_structure(self, sample_flow_data):
        """Test project table structure"""
        summary_stats = calculate_portfolio_summary(sample_flow_data)
        tables = build_project_tables(sample_flow_data, summary_stats)

        for table in tables:
            assert "name" in table
            assert "color" in table
            assert "avg_lead_time" in table
            assert "total_open" in table
            assert "total_closed" in table
            assert "projects" in table

    def testbuild_project_tables_sorting(self):
        """Test projects are sorted by status priority"""
        week_data = {
            "projects": [
                {
                    "project_name": "Good Project",
                    "work_type_metrics": {
                        "Bug": {
                            "open_count": 10,
                            "closed_count_90d": 5,
                            "lead_time": {"p50": 10.0, "p85": 30.0},
                            "throughput": {"per_week": 0.5},
                            "cycle_time_variance": {"std_dev_days": 5.0, "coefficient_of_variation": 50.0},
                            "dual_metrics": {"operational": {}, "cleanup": {}, "indicators": {}},
                        }
                    },
                },
                {
                    "project_name": "Bad Project",
                    "work_type_metrics": {
                        "Bug": {
                            "open_count": 10,
                            "closed_count_90d": 5,
                            "lead_time": {"p50": 100.0, "p85": 200.0},
                            "throughput": {"per_week": 0.1},
                            "cycle_time_variance": {"std_dev_days": 20.0, "coefficient_of_variation": 200.0},
                            "dual_metrics": {"operational": {}, "cleanup": {}, "indicators": {}},
                        }
                    },
                },
            ]
        }

        summary_stats = calculate_portfolio_summary(week_data)
        tables = build_project_tables(week_data, summary_stats)

        # Bug table should have Bad Project first (lower priority = worse status)
        bug_table = tables[0]
        assert bug_table["projects"][0]["name"] == "Bad Project"
        assert bug_table["projects"][1]["name"] == "Good Project"


class TestBuildContext:
    """Test context building for template"""

    def test_build_context_keys(self, sample_flow_data):
        """Test that context has all required keys"""
        summary_stats = calculate_portfolio_summary(sample_flow_data)
        context = _build_context(sample_flow_data, summary_stats)

        required_keys = [
            "framework_css",
            "framework_js",
            "generation_date",
            "week_number",
            "week_date",
            "portfolio_status",
            "portfolio_status_color",
            "summary_cards",
            "work_type_cards",
            "work_types",
            "project_count",
        ]

        for key in required_keys:
            assert key in context

    def test_build_context_values(self, sample_flow_data):
        """Test context values are correct"""
        summary_stats = calculate_portfolio_summary(sample_flow_data)
        context = _build_context(sample_flow_data, summary_stats)

        assert context["week_number"] == 6
        assert context["week_date"] == "2026-02-06"
        assert context["project_count"] == 2
        assert len(context["summary_cards"]) == 4
        assert len(context["work_type_cards"]) == 3
        assert len(context["work_types"]) == 3

    def test_build_context_portfolio_status_healthy(self):
        """Test portfolio status - HEALTHY"""
        week_data = {"week_number": 6, "week_date": "2026-02-06", "projects": []}
        summary_stats = {
            "avg_lead_time": 50.0,  # < 60
            "total_wip": 0,
            "total_closed": 0,
            "project_count": 0,
            "by_type": {
                "Bug": {"open": 0, "closed": 0, "lead_times": []},
                "User Story": {"open": 0, "closed": 0, "lead_times": []},
                "Task": {"open": 0, "closed": 0, "lead_times": []},
            },
        }

        context = _build_context(week_data, summary_stats)

        assert context["portfolio_status"] == "HEALTHY"
        assert context["portfolio_status_color"] == "#10b981"

    def test_build_context_portfolio_status_caution(self):
        """Test portfolio status - CAUTION"""
        week_data = {"week_number": 6, "week_date": "2026-02-06", "projects": []}
        summary_stats = {
            "avg_lead_time": 100.0,  # 60-150
            "total_wip": 0,
            "total_closed": 0,
            "project_count": 0,
            "by_type": {
                "Bug": {"open": 0, "closed": 0, "lead_times": []},
                "User Story": {"open": 0, "closed": 0, "lead_times": []},
                "Task": {"open": 0, "closed": 0, "lead_times": []},
            },
        }

        context = _build_context(week_data, summary_stats)

        assert context["portfolio_status"] == "CAUTION"
        assert context["portfolio_status_color"] == "#f59e0b"

    def test_build_context_portfolio_status_action_needed(self):
        """Test portfolio status - ACTION NEEDED"""
        week_data = {"week_number": 6, "week_date": "2026-02-06", "projects": []}
        summary_stats = {
            "avg_lead_time": 200.0,  # > 150
            "total_wip": 0,
            "total_closed": 0,
            "project_count": 0,
            "by_type": {
                "Bug": {"open": 0, "closed": 0, "lead_times": []},
                "User Story": {"open": 0, "closed": 0, "lead_times": []},
                "Task": {"open": 0, "closed": 0, "lead_times": []},
            },
        }

        context = _build_context(week_data, summary_stats)

        assert context["portfolio_status"] == "ACTION NEEDED"
        assert context["portfolio_status_color"] == "#f87171"


class TestGenerateFlowDashboard:
    """Test main dashboard generation function"""

    @patch("execution.dashboards.flow.FlowDataLoader")
    @patch("execution.dashboards.flow.render_dashboard")
    def test_generate_dashboard_success(self, mock_render, mock_loader_class, sample_flow_data):
        """Test successful dashboard generation"""
        mock_loader = MagicMock()
        mock_loader.load_latest_week.return_value = sample_flow_data
        mock_loader_class.return_value = mock_loader
        mock_render.return_value = "<html>Dashboard</html>"

        html = generate_flow_dashboard()

        assert html == "<html>Dashboard</html>"
        mock_loader.load_latest_week.assert_called_once()
        mock_render.assert_called_once()

    @patch("execution.dashboards.flow.FlowDataLoader")
    @patch("execution.dashboards.flow.render_dashboard")
    def test_generate_dashboard_with_output_path(self, mock_render, mock_loader_class, sample_flow_data, tmp_path):
        """Test dashboard generation with file output"""
        mock_loader = MagicMock()
        mock_loader.load_latest_week.return_value = sample_flow_data
        mock_loader_class.return_value = mock_loader
        mock_render.return_value = "<html>Dashboard</html>"

        output_path = tmp_path / "flow.html"
        html = generate_flow_dashboard(output_path)

        assert output_path.exists()
        assert output_path.read_text(encoding="utf-8") == "<html>Dashboard</html>"

    @patch("execution.dashboards.flow.FlowDataLoader")
    def test_generate_dashboard_file_not_found(self, mock_loader_class):
        """Test dashboard generation with missing data file"""
        mock_loader = MagicMock()
        mock_loader.load_latest_week.side_effect = FileNotFoundError("Flow history not found")
        mock_loader_class.return_value = mock_loader

        with pytest.raises(FileNotFoundError):
            generate_flow_dashboard()


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_project_with_missing_metrics(self):
        """Test handling project with incomplete metrics"""
        project = {"project_name": "Incomplete", "work_type_metrics": {"Bug": {"open_count": 10}}}

        row = format_project_row(project, "Bug")

        # Should return None only if both open and closed are 0
        # With open_count=10, it should return a row (even if closed is 0)
        assert row is not None
        assert row["name"] == "Incomplete"
        assert row["open"] == "10"

    def test_project_with_zero_values(self):
        """Test handling project with zero values"""
        project = {
            "project_name": "Empty",
            "work_type_metrics": {"Bug": {"open_count": 0, "closed_count_90d": 0}},
        }

        row = format_project_row(project, "Bug")

        assert row is None

    def test_summary_with_no_projects(self):
        """Test summary calculation with no projects"""
        week_data = {"projects": []}

        summary = calculate_portfolio_summary(week_data)

        assert summary["avg_lead_time"] == 0
        assert summary["total_wip"] == 0
        assert summary["total_closed"] == 0
        assert summary["project_count"] == 0
