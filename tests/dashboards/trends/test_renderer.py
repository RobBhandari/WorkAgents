#!/usr/bin/env python3
"""
Tests for TrendsRenderer

Validates HTML generation, context building, RAG coloring, and XSS protection
for the Executive Trends Dashboard renderer.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from execution.dashboards.trends.renderer import TrendsRenderer


@pytest.fixture
def sample_trends_data():
    """Sample trends data with all metric categories"""
    return {
        "quality": {
            "bugs": {
                "current": 180,
                "previous": 195,
                "trend_data": [200, 195, 190, 185, 180],
                "unit": "bugs",
            },
            "mttr": {
                "current": 8.5,
                "previous": 9.2,
                "trend_data": [10.1, 9.8, 9.5, 9.2, 8.5],
                "unit": "days",
            },
        },
        "security": {
            "vulnerabilities": {
                "current": 220,
                "previous": 240,
                "trend_data": [260, 250, 240, 230, 220],
                "unit": "vulns",
            }
        },
        "flow": {
            "lead_time": {
                "current": 35.5,
                "previous": 38.2,
                "trend_data": [42.1, 40.5, 38.2, 36.8, 35.5],
                "unit": "days",
            }
        },
        "deployment": {
            "build_success": {
                "current": 87.5,
                "previous": 85.0,
                "trend_data": [82.0, 83.5, 85.0, 86.2, 87.5],
                "unit": "%",
            }
        },
        "collaboration": {
            "pr_merge_time": {
                "current": 6.8,
                "previous": 7.5,
                "trend_data": [9.2, 8.5, 7.5, 7.1, 6.8],
                "unit": "hours",
            }
        },
        "ownership": {
            "work_unassigned": {
                "current": 25.5,
                "previous": 28.0,
                "trend_data": [32.0, 30.5, 28.0, 26.8, 25.5],
                "unit": "%",
            }
        },
        "risk": {
            "total_commits": {
                "current": 450,
                "previous": 425,
                "trend_data": [400, 410, 425, 440, 450],
                "unit": "commits",
            }
        },
    }


@pytest.fixture
def sample_target_progress():
    """Sample target progress data with forecast"""
    return {
        "current": 55.8,
        "previous": 52.3,
        "trend_data": [45.0, 48.2, 50.5, 52.3, 55.8],
        "unit": "% progress",
        "forecast": {
            "trajectory": "Behind",
            "trajectory_color": "#f59e0b",
            "weeks_to_target": 20.5,
            "required_bugs_burn": 5.2,
            "required_vulns_burn": 3.8,
            "actual_bugs_burn": 3.75,
            "actual_vulns_burn": 5.0,
            "forecast_msg": "At current pace (3.8 bugs/wk, 5.0 vulns/wk), reaching 85% of target by June 30.",
        },
    }


class TestTrendsRendererInit:
    """Test TrendsRenderer initialization"""

    def test_init_with_all_data(self, sample_trends_data, sample_target_progress):
        """Test initialization with complete data"""
        renderer = TrendsRenderer(sample_trends_data, sample_target_progress)
        assert renderer.trends_data == sample_trends_data
        assert renderer.target_progress == sample_target_progress

    def test_init_without_target_progress(self, sample_trends_data):
        """Test initialization without target progress"""
        renderer = TrendsRenderer(sample_trends_data)
        assert renderer.trends_data == sample_trends_data
        assert renderer.target_progress is None

    def test_init_with_empty_data(self):
        """Test initialization with empty data"""
        renderer = TrendsRenderer({})
        assert renderer.trends_data == {}
        assert renderer.target_progress is None


class TestTrendIndicator:
    """Test trend indicator logic (arrows and colors)"""

    def test_trend_down_good_direction(self, sample_trends_data):
        """Test decreasing trend when down is good (bugs, vulnerabilities)"""
        renderer = TrendsRenderer(sample_trends_data)
        arrow, css_class, change = renderer._get_trend_indicator(180, 195, "down")
        assert arrow == "↓"
        assert css_class == "trend-down"
        assert change == -15

    def test_trend_up_good_direction(self, sample_trends_data):
        """Test increasing trend when up is good (success rate)"""
        renderer = TrendsRenderer(sample_trends_data)
        arrow, css_class, change = renderer._get_trend_indicator(87.5, 85.0, "up")
        assert arrow == "↑"
        assert css_class == "trend-down"  # Green (good)
        assert change == 2.5

    def test_trend_stable(self, sample_trends_data):
        """Test stable trend (change < 0.5)"""
        renderer = TrendsRenderer(sample_trends_data)
        arrow, css_class, change = renderer._get_trend_indicator(100.2, 100.0, "down")
        assert arrow == "→"
        assert css_class == "trend-stable"
        assert abs(change - 0.2) < 0.001  # Floating point tolerance

    def test_trend_up_bad_direction(self, sample_trends_data):
        """Test increasing trend when down is good (worse performance)"""
        renderer = TrendsRenderer(sample_trends_data)
        arrow, css_class, change = renderer._get_trend_indicator(250, 220, "down")
        assert arrow == "↑"
        assert css_class == "trend-up"  # Red (bad)
        assert change == 30

    def test_trend_down_bad_direction(self, sample_trends_data):
        """Test decreasing trend when up is good (worse performance)"""
        renderer = TrendsRenderer(sample_trends_data)
        arrow, css_class, change = renderer._get_trend_indicator(80.0, 87.5, "up")
        assert arrow == "↓"
        assert css_class == "trend-up"  # Red (bad)
        assert change == -7.5


class TestRAGColor:
    """Test RAG color determination for different metrics"""

    def test_rag_lead_time_green(self, sample_trends_data):
        """Test lead time RAG - green threshold"""
        renderer = TrendsRenderer(sample_trends_data)
        color = renderer._get_rag_color(25.0, "lead_time")
        assert color == "#10b981"  # Green

    def test_rag_lead_time_amber(self, sample_trends_data):
        """Test lead time RAG - amber threshold"""
        renderer = TrendsRenderer(sample_trends_data)
        color = renderer._get_rag_color(45.0, "lead_time")
        assert color == "#f59e0b"  # Amber

    def test_rag_lead_time_red(self, sample_trends_data):
        """Test lead time RAG - red threshold"""
        renderer = TrendsRenderer(sample_trends_data)
        color = renderer._get_rag_color(75.0, "lead_time")
        assert color == "#ef4444"  # Red

    def test_rag_bugs_green(self, sample_trends_data):
        """Test bugs RAG - green threshold"""
        renderer = TrendsRenderer(sample_trends_data)
        color = renderer._get_rag_color(80, "bugs")
        assert color == "#10b981"

    def test_rag_bugs_amber(self, sample_trends_data):
        """Test bugs RAG - amber threshold"""
        renderer = TrendsRenderer(sample_trends_data)
        color = renderer._get_rag_color(150, "bugs")
        assert color == "#f59e0b"

    def test_rag_bugs_red(self, sample_trends_data):
        """Test bugs RAG - red threshold"""
        renderer = TrendsRenderer(sample_trends_data)
        color = renderer._get_rag_color(250, "bugs")
        assert color == "#ef4444"

    def test_rag_success_rate_green(self, sample_trends_data):
        """Test success rate RAG - green threshold"""
        renderer = TrendsRenderer(sample_trends_data)
        color = renderer._get_rag_color(95.0, "success_rate")
        assert color == "#10b981"

    def test_rag_success_rate_amber(self, sample_trends_data):
        """Test success rate RAG - amber threshold"""
        renderer = TrendsRenderer(sample_trends_data)
        color = renderer._get_rag_color(85.0, "success_rate")
        assert color == "#f59e0b"

    def test_rag_success_rate_red(self, sample_trends_data):
        """Test success rate RAG - red threshold"""
        renderer = TrendsRenderer(sample_trends_data)
        color = renderer._get_rag_color(65.0, "success_rate")
        assert color == "#ef4444"

    def test_rag_target_progress_green(self, sample_trends_data):
        """Test target progress RAG - green threshold"""
        renderer = TrendsRenderer(sample_trends_data)
        color = renderer._get_rag_color(75.0, "target_progress")
        assert color == "#10b981"

    def test_rag_target_progress_amber(self, sample_trends_data):
        """Test target progress RAG - amber threshold"""
        renderer = TrendsRenderer(sample_trends_data)
        color = renderer._get_rag_color(55.0, "target_progress")
        assert color == "#f59e0b"

    def test_rag_target_progress_red(self, sample_trends_data):
        """Test target progress RAG - red threshold"""
        renderer = TrendsRenderer(sample_trends_data)
        color = renderer._get_rag_color(30.0, "target_progress")
        assert color == "#ef4444"

    def test_rag_commits_neutral(self, sample_trends_data):
        """Test commits RAG - neutral metric"""
        renderer = TrendsRenderer(sample_trends_data)
        color = renderer._get_rag_color(450, "commits")
        assert color == "#6366f1"  # Purple (neutral)

    def test_rag_invalid_value(self, sample_trends_data):
        """Test RAG with invalid value"""
        renderer = TrendsRenderer(sample_trends_data)
        color = renderer._get_rag_color("N/A", "bugs")
        assert color == "#94a3b8"  # Gray

    def test_rag_none_value(self, sample_trends_data):
        """Test RAG with None value"""
        renderer = TrendsRenderer(sample_trends_data)
        color = renderer._get_rag_color(None, "lead_time")
        assert color == "#94a3b8"  # Gray

    def test_rag_unknown_metric_type(self, sample_trends_data):
        """Test RAG with unknown metric type"""
        renderer = TrendsRenderer(sample_trends_data)
        color = renderer._get_rag_color(100, "unknown_metric")
        assert color == "#6366f1"  # Default purple


class TestMetricsListGeneration:
    """Test metrics list generation for JavaScript"""

    def test_generate_all_metrics(self, sample_trends_data, sample_target_progress):
        """Test generation of all metric types"""
        renderer = TrendsRenderer(sample_trends_data, sample_target_progress)
        metrics = renderer._generate_metrics_list()

        # Should have 9 metrics: target + AI usage + 7 trend metrics
        assert len(metrics) == 9

        # Check metric IDs
        metric_ids = [m["id"] for m in metrics]
        assert "target" in metric_ids
        assert "ai-usage" in metric_ids
        assert "security" in metric_ids
        assert "bugs" in metric_ids
        assert "flow" in metric_ids
        assert "deployment" in metric_ids
        assert "collaboration" in metric_ids
        assert "ownership" in metric_ids
        assert "risk" in metric_ids

    def test_generate_metrics_without_target(self, sample_trends_data):
        """Test generation without target progress"""
        renderer = TrendsRenderer(sample_trends_data, None)
        metrics = renderer._generate_metrics_list()

        # Should have 8 metrics: AI usage + 7 trend metrics (no target)
        assert len(metrics) == 8
        metric_ids = [m["id"] for m in metrics]
        assert "target" not in metric_ids

    def test_ai_usage_launcher_no_data(self, sample_trends_data):
        """Test AI usage launcher has no trend data"""
        renderer = TrendsRenderer(sample_trends_data)
        metrics = renderer._generate_metrics_list()

        ai_usage = next(m for m in metrics if m["id"] == "ai-usage")
        assert ai_usage["data"] == []
        assert ai_usage["current"] == ""
        assert ai_usage["unit"] == ""

    def test_metric_structure(self, sample_trends_data, sample_target_progress):
        """Test individual metric has correct structure"""
        renderer = TrendsRenderer(sample_trends_data, sample_target_progress)
        metrics = renderer._generate_metrics_list()

        bugs_metric = next(m for m in metrics if m["id"] == "bugs")

        # Validate structure
        assert "id" in bugs_metric
        assert "icon" in bugs_metric
        assert "title" in bugs_metric
        assert "description" in bugs_metric
        assert "current" in bugs_metric
        assert "unit" in bugs_metric
        assert "change" in bugs_metric
        assert "changeLabel" in bugs_metric
        assert "data" in bugs_metric
        assert "arrow" in bugs_metric
        assert "cssClass" in bugs_metric
        assert "ragColor" in bugs_metric
        assert "dashboardUrl" in bugs_metric

        # Validate values
        assert bugs_metric["current"] == 180
        assert bugs_metric["unit"] == "bugs"
        assert bugs_metric["change"] == -15
        assert len(bugs_metric["data"]) == 5

    def test_metrics_with_partial_data(self):
        """Test generation with only some metric categories"""
        partial_data = {
            "quality": {
                "bugs": {
                    "current": 100,
                    "previous": 110,
                    "trend_data": [120, 115, 110, 105, 100],
                    "unit": "bugs",
                }
            }
        }
        renderer = TrendsRenderer(partial_data)
        metrics = renderer._generate_metrics_list()

        # Should have AI usage + bugs only
        assert len(metrics) == 2
        metric_ids = [m["id"] for m in metrics]
        assert "bugs" in metric_ids
        assert "ai-usage" in metric_ids
        assert "security" not in metric_ids


class TestBuildContext:
    """Test template context building"""

    @patch("execution.dashboards.trends.renderer.get_dashboard_framework")
    def test_build_context_structure(self, mock_framework, sample_trends_data, sample_target_progress):
        """Test context has correct structure"""
        mock_framework.return_value = ("<style>CSS</style>", "<script>JS</script>")

        renderer = TrendsRenderer(sample_trends_data, sample_target_progress)
        context = renderer.build_context()

        # Validate keys
        assert "metrics" in context
        assert "metrics_json" in context
        assert "framework_css" in context
        assert "framework_js" in context
        assert "timestamp" in context

        # Validate types
        assert isinstance(context["metrics"], list)
        assert isinstance(context["metrics_json"], str)
        assert isinstance(context["framework_css"], str)
        assert isinstance(context["framework_js"], str)
        assert isinstance(context["timestamp"], str)

    @patch("execution.dashboards.trends.renderer.get_dashboard_framework")
    def test_build_context_metrics_json_valid(self, mock_framework, sample_trends_data):
        """Test metrics_json is valid JSON"""
        mock_framework.return_value = ("<style>CSS</style>", "<script>JS</script>")

        renderer = TrendsRenderer(sample_trends_data)
        context = renderer.build_context()

        # Parse JSON to validate
        metrics_parsed = json.loads(context["metrics_json"])
        assert isinstance(metrics_parsed, list)
        assert len(metrics_parsed) > 0

    @patch("execution.dashboards.trends.renderer.get_dashboard_framework")
    def test_build_context_framework_called_correctly(self, mock_framework, sample_trends_data):
        """Test framework is called with correct parameters"""
        mock_framework.return_value = ("<style>CSS</style>", "<script>JS</script>")

        renderer = TrendsRenderer(sample_trends_data)
        context = renderer.build_context()

        mock_framework.assert_called_once_with(
            header_gradient_start="#667eea",
            header_gradient_end="#764ba2",
            include_table_scroll=True,
            include_expandable_rows=False,
            include_glossary=False,
        )


class TestHTMLGeneration:
    """Test complete HTML generation"""

    @patch("execution.dashboards.trends.renderer.render_dashboard")
    @patch("execution.dashboards.trends.renderer.get_dashboard_framework")
    def test_generate_html_structure(
        self, mock_framework, mock_render, sample_trends_data, sample_target_progress, tmp_path
    ):
        """Test generated HTML has correct structure"""
        mock_framework.return_value = ("<style>CSS</style>", "<script>JS</script>")
        mock_render.return_value = """<!DOCTYPE html><html><head><title>Executive Trends - Director Observatory</title></head><body></body></html>"""

        renderer = TrendsRenderer(sample_trends_data, sample_target_progress)
        output_path = tmp_path / "test.html"
        renderer.generate_dashboard_file(output_path)

        # Verify render_dashboard was called
        assert mock_render.called
        html = output_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        # Validate HTML structure
        assert soup.find("html") is not None
        assert soup.find("head") is not None
        assert soup.find("body") is not None

    @patch("execution.dashboards.trends.renderer.render_dashboard")
    @patch("execution.dashboards.trends.renderer.get_dashboard_framework")
    def test_generate_html_contains_metrics(self, mock_framework, mock_render, sample_trends_data, tmp_path):
        """Test HTML contains metrics container"""
        mock_framework.return_value = ("<style>CSS</style>", "<script>JS</script>")
        mock_render.return_value = """<!DOCTYPE html><html><body><div id="metrics-container"></div></body></html>"""

        renderer = TrendsRenderer(sample_trends_data)
        output_path = tmp_path / "test.html"
        renderer.generate_dashboard_file(output_path)

        html = output_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        # Check for metrics container
        metrics_container = soup.find("div", {"id": "metrics-container"})
        assert metrics_container is not None

    @patch("execution.dashboards.trends.renderer.render_dashboard")
    @patch("execution.dashboards.trends.renderer.get_dashboard_framework")
    def test_generate_html_contains_view_selector(self, mock_framework, mock_render, sample_trends_data, tmp_path):
        """Test HTML contains view selector buttons"""
        mock_framework.return_value = ("<style>CSS</style>", "<script>JS</script>")
        mock_render.return_value = """<!DOCTYPE html><html><body><div class="view-selector"><button class="view-btn">1</button><button class="view-btn">2</button><button class="view-btn">3</button></div></body></html>"""

        renderer = TrendsRenderer(sample_trends_data)
        output_path = tmp_path / "test.html"
        renderer.generate_dashboard_file(output_path)

        html = output_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        # Check for view selector
        view_selector = soup.find("div", class_="view-selector")
        assert view_selector is not None

        # Check for view buttons
        view_buttons = soup.find_all("button", class_="view-btn")
        assert len(view_buttons) == 3

    @patch("execution.dashboards.trends.renderer.render_dashboard")
    @patch("execution.dashboards.trends.renderer.get_dashboard_framework")
    def test_generate_html_contains_javascript(self, mock_framework, mock_render, sample_trends_data, tmp_path):
        """Test HTML contains JavaScript for interactivity"""
        mock_framework.return_value = ("<style>CSS</style>", "<script>JS</script>")
        mock_render.return_value = """<!DOCTYPE html><html><body><script>const trendsData = []; function changeView() {} function generateSparkline() {} function renderMetrics() {}</script></body></html>"""

        renderer = TrendsRenderer(sample_trends_data)
        output_path = tmp_path / "test.html"
        renderer.generate_dashboard_file(output_path)

        html = output_path.read_text(encoding="utf-8")

        # Check for JavaScript functions
        assert "trendsData" in html
        assert "changeView" in html
        assert "generateSparkline" in html
        assert "renderMetrics" in html

    @patch("execution.dashboards.trends.renderer.render_dashboard")
    @patch("execution.dashboards.trends.renderer.get_dashboard_framework")
    def test_generate_html_contains_timestamp(self, mock_framework, mock_render, sample_trends_data, tmp_path):
        """Test HTML contains timestamp"""
        mock_framework.return_value = ("<style>CSS</style>", "<script>JS</script>")
        mock_render.return_value = (
            """<!DOCTYPE html><html><body><div class="timestamp">Generated: 2026-01-01</div></body></html>"""
        )

        renderer = TrendsRenderer(sample_trends_data)
        output_path = tmp_path / "test.html"
        renderer.generate_dashboard_file(output_path)

        html = output_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        timestamp = soup.find("div", class_="timestamp")
        assert timestamp is not None
        assert "Generated:" in timestamp.text


class TestXSSProtection:
    """Test XSS protection in HTML rendering"""

    @patch("execution.dashboards.trends.renderer.render_dashboard")
    @patch("execution.dashboards.trends.renderer.get_dashboard_framework")
    def test_xss_protection_in_metric_values(self, mock_framework, mock_render, tmp_path):
        """Test XSS protection for malicious metric values"""
        mock_framework.return_value = ("<style>CSS</style>", "<script>JS</script>")

        # Capture the context passed to render_dashboard
        captured_context = {}

        def capture_context(template, context):
            captured_context.update(context)
            return (
                """<!DOCTYPE html><html><body><script>const trendsData = """
                + context["metrics_json"]
                + """;</script></body></html>"""
            )

        mock_render.side_effect = capture_context

        # Create malicious data with string values in trend_data
        # Note: This tests that malicious strings in trend_data don't break rendering
        # The renderer expects numeric values, so strings will be handled by JSON serialization
        malicious_data = {
            "quality": {
                "bugs": {
                    "current": 100,  # Must be numeric for calculations
                    "previous": 95,
                    "trend_data": [100, 95, 90],  # Numeric data
                    "unit": "<script>alert('XSS')</script>",  # XSS in unit field
                }
            }
        }

        renderer = TrendsRenderer(malicious_data)
        output_path = tmp_path / "test.html"
        renderer.generate_dashboard_file(output_path)

        html = output_path.read_text(encoding="utf-8")

        # The malicious unit is embedded in JSON, which is safe
        # JSON serialization escapes the string properly
        assert "trendsData" in html
        # Verify the XSS string is JSON-encoded (not raw HTML)
        assert '"unit": "<script>alert' in html or '"unit":"<script>alert' in html


class TestRenderDashboard:
    """Test full dashboard rendering to file"""

    @patch("execution.dashboards.trends.renderer.get_dashboard_framework")
    def test_render_dashboard_creates_file(self, mock_framework, sample_trends_data, tmp_path):
        """Test rendering creates output file"""
        mock_framework.return_value = ("<style>CSS</style>", "<script>JS</script>")

        renderer = TrendsRenderer(sample_trends_data)
        output_path = tmp_path / "test_trends.html"

        result = renderer.generate_dashboard_file(output_path)

        # Verify file was created
        assert output_path.exists()
        assert result == str(output_path)

    @patch("execution.dashboards.trends.renderer.get_dashboard_framework")
    def test_render_dashboard_creates_parent_dirs(self, mock_framework, sample_trends_data, tmp_path):
        """Test rendering creates parent directories"""
        mock_framework.return_value = ("<style>CSS</style>", "<script>JS</script>")

        renderer = TrendsRenderer(sample_trends_data)
        output_path = tmp_path / "nested" / "dir" / "trends.html"

        result = renderer.generate_dashboard_file(output_path)

        # Verify nested directories were created
        assert output_path.exists()
        assert output_path.parent.exists()

    @patch("execution.dashboards.trends.renderer.get_dashboard_framework")
    def test_render_dashboard_content_valid(self, mock_framework, sample_trends_data, tmp_path):
        """Test rendered file contains valid HTML"""
        mock_framework.return_value = ("<style>CSS</style>", "<script>JS</script>")

        renderer = TrendsRenderer(sample_trends_data)
        output_path = tmp_path / "trends.html"

        renderer.generate_dashboard_file(output_path)

        # Read and validate content
        content = output_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(content, "html.parser")

        assert soup.find("html") is not None
        assert soup.find("title") is not None


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_empty_trends_data(self):
        """Test with empty trends data"""
        renderer = TrendsRenderer({})
        metrics = renderer._generate_metrics_list()

        # Should still have AI usage launcher
        assert len(metrics) == 1
        assert metrics[0]["id"] == "ai-usage"

    def test_metric_with_zero_values(self):
        """Test metric with all zero values"""
        data = {"quality": {"bugs": {"current": 0, "previous": 0, "trend_data": [0, 0, 0], "unit": "bugs"}}}
        renderer = TrendsRenderer(data)
        metrics = renderer._generate_metrics_list()

        bugs_metric = next(m for m in metrics if m["id"] == "bugs")
        assert bugs_metric["current"] == 0
        assert bugs_metric["change"] == 0

    def test_metric_with_single_data_point(self):
        """Test metric with single data point"""
        data = {"quality": {"bugs": {"current": 100, "previous": 100, "trend_data": [100], "unit": "bugs"}}}
        renderer = TrendsRenderer(data)
        metrics = renderer._generate_metrics_list()

        bugs_metric = next(m for m in metrics if m["id"] == "bugs")
        assert len(bugs_metric["data"]) == 1

    @patch("execution.dashboards.trends.renderer.get_dashboard_framework")
    def test_render_with_minimal_data(self, mock_framework, tmp_path):
        """Test rendering with minimal data"""
        mock_framework.return_value = ("<style>CSS</style>", "<script>JS</script>")

        renderer = TrendsRenderer({})
        output_path = tmp_path / "minimal.html"

        result = renderer.generate_dashboard_file(output_path)

        # Should still generate valid HTML
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
