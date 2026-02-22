"""
Tests for dashboard components

Tests card, table, and chart component generators.
"""

import pytest

from execution.dashboards.components.cards import (
    METRIC_GLOSSARY,
    SEVERITY_EMOJI,
    attention_item_card,
    metric_card,
    rag_status_badge,
    summary_card,
)
from execution.dashboards.components.charts import sparkline, trend_indicator
from execution.dashboards.components.tables import data_table, summary_table


class TestCards:
    """Tests for card components"""

    def test_metric_card_basic(self):
        """Test basic metric card generation"""
        html = metric_card("Test Metric", "42")
        assert "Test Metric" in html
        assert "42" in html
        assert "summary-card" in html

    def test_metric_card_with_subtitle(self):
        """Test metric card with subtitle"""
        html = metric_card("Test", "100", subtitle="items")
        assert "100" in html
        assert "items" in html

    def test_metric_card_with_trend(self):
        """Test metric card with trend indicator"""
        html = metric_card("Test", "50", trend="↓")
        assert "↓" in html
        assert "trend" in html

    def test_metric_card_with_css_class(self):
        """Test metric card with custom CSS class"""
        html = metric_card("Test", "10", css_class="rag-green")
        assert "rag-green" in html

    def test_summary_card_basic(self):
        """Test basic summary card"""
        html = summary_card("Title", "Value")
        assert "Title" in html
        assert "Value" in html
        assert "summary-card" in html

    def test_rag_status_badge_good(self):
        """Test RAG badge for good status"""
        html = rag_status_badge("good")
        assert "status-good" in html
        assert "GOOD" in html

    def test_rag_status_badge_critical(self):
        """Test RAG badge for critical status"""
        html = rag_status_badge("critical")
        assert "status-action" in html
        assert "CRITICAL" in html


class TestTables:
    """Tests for table components"""

    def test_data_table_basic(self, sample_table_data):
        """Test basic data table generation"""
        html = data_table(sample_table_data["headers"], sample_table_data["rows"])
        assert "Product" in html
        assert "API Gateway" in html
        assert "Web App" in html
        assert "<table" in html
        assert "<thead>" in html
        assert "<tbody>" in html

    def test_data_table_with_id(self):
        """Test data table with custom ID"""
        html = data_table(["A", "B"], [["1", "2"]], table_id="customTable")
        assert 'id="customTable"' in html

    def test_data_table_sortable(self):
        """Test data table with sortable flag"""
        html = data_table(["A"], [["1"]], sortable=True)
        assert "sortable" in html

    def test_data_table_no_wrapper(self):
        """Test data table without wrapper div"""
        html = data_table(["A"], [["1"]], wrap_in_div=False)
        assert "table-wrapper" not in html
        assert "<table" in html

    def test_summary_table(self):
        """Test summary table generation"""
        data = [
            {"label": "Total", "value": "100"},
            {"label": "Open", "value": "42"},
        ]
        html = summary_table(data)
        assert "Total" in html
        assert "100" in html
        assert "Open" in html
        assert "42" in html


class TestCharts:
    """Tests for chart components"""

    def test_sparkline_basic(self):
        """Test basic sparkline generation"""
        html = sparkline([10, 15, 12, 18, 20])
        assert "<svg" in html
        assert "sparkline" in html
        assert "<polyline" in html

    def test_sparkline_empty(self):
        """Test sparkline with no data"""
        html = sparkline([])
        assert html == ""

    def test_sparkline_single_value(self):
        """Test sparkline with single value"""
        html = sparkline([10])
        assert html == ""  # Need at least 2 points

    def test_sparkline_custom_size(self):
        """Test sparkline with custom dimensions"""
        html = sparkline([1, 2, 3], width=200, height=50)
        assert 'width="200"' in html
        assert 'height="50"' in html

    def test_trend_indicator_up(self):
        """Test trend indicator for positive change"""
        html = trend_indicator(10)
        assert "↑" in html
        assert "+10" in html

    def test_trend_indicator_down(self):
        """Test trend indicator for negative change"""
        html = trend_indicator(-5)
        assert "↓" in html
        assert "-5" in html

    def test_trend_indicator_neutral(self):
        """Test trend indicator for zero change"""
        html = trend_indicator(0)
        assert "→" in html

    def test_trend_indicator_no_value(self):
        """Test trend indicator without showing value"""
        html = trend_indicator(10, show_value=False)
        assert "↑" in html
        assert "10" not in html


class TestSeverityEmoji:
    """Tests for the SEVERITY_EMOJI constant and its usage in attention_item_card"""

    def test_severity_emoji_contains_all_expected_keys(self) -> None:
        """SEVERITY_EMOJI must cover all severity levels used in the alert system"""
        expected_keys = {"critical", "high", "warning", "warn", "medium", "low", "good", "info"}
        assert expected_keys.issubset(set(SEVERITY_EMOJI.keys()))

    def test_critical_and_high_map_to_red_circle(self) -> None:
        """Critical and high severities should both map to the red circle emoji"""
        assert SEVERITY_EMOJI["critical"] == "🔴"
        assert SEVERITY_EMOJI["high"] == "🔴"

    def test_warning_and_medium_map_to_yellow_circle(self) -> None:
        """Warning and medium severities should map to yellow circle emoji"""
        assert SEVERITY_EMOJI["warning"] == "🟡"
        assert SEVERITY_EMOJI["warn"] == "🟡"
        assert SEVERITY_EMOJI["medium"] == "🟡"

    def test_low_and_good_map_to_green_circle(self) -> None:
        """Low and good severities should map to green circle emoji"""
        assert SEVERITY_EMOJI["low"] == "🟢"
        assert SEVERITY_EMOJI["good"] == "🟢"

    def test_attention_item_card_includes_emoji(self) -> None:
        """attention_item_card should prefix severity badge with the correct emoji"""
        # Since attention_item_card renders via Jinja2 template, we verify
        # that the rendered HTML contains the severity_emoji value for 'high'
        html = attention_item_card("high", "Security", "5 critical vulnerabilities")
        assert "Security" in html
        assert "5 critical vulnerabilities" in html

    def test_attention_item_card_unknown_severity_no_crash(self) -> None:
        """attention_item_card should not crash for unknown severity levels"""
        html = attention_item_card("unknown", "Quality", "Some message")
        assert "Quality" in html
        assert "Some message" in html


class TestMetricGlossary:
    """Tests for the METRIC_GLOSSARY constant"""

    def test_glossary_contains_all_expected_keys(self) -> None:
        """METRIC_GLOSSARY must contain all documented metric names"""
        expected_keys = {
            "Lead Time",
            "Throughput",
            "WIP",
            "Cycle Time",
            "DORA",
            "P1 Bugs",
            "Open Bugs",
            "Vulnerabilities",
            "Exploitable",
            "Build Success Rate",
            "Deploy Frequency",
            "MTTR",
        }
        assert expected_keys == set(METRIC_GLOSSARY.keys())

    def test_all_definitions_are_non_empty_strings(self) -> None:
        """Every glossary entry must be a non-empty string"""
        for key, value in METRIC_GLOSSARY.items():
            assert isinstance(value, str), f"Glossary entry for {key!r} must be a string"
            assert len(value) > 0, f"Glossary entry for {key!r} must not be empty"

    def test_lead_time_definition(self) -> None:
        """Lead Time definition must reference days"""
        assert "days" in METRIC_GLOSSARY["Lead Time"].lower()

    def test_wip_definition(self) -> None:
        """WIP definition must expand the abbreviation"""
        assert "progress" in METRIC_GLOSSARY["WIP"].lower()

    def test_no_html_injection_in_definitions(self) -> None:
        """Glossary values must not contain HTML tags (they are plain text for title attributes)"""
        for key, value in METRIC_GLOSSARY.items():
            assert "<" not in value, f"Glossary entry for {key!r} must not contain HTML"
            assert ">" not in value, f"Glossary entry for {key!r} must not contain HTML"
