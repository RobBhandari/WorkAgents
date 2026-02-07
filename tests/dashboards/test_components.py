"""
Tests for dashboard components

Tests card, table, and chart component generators.
"""

import pytest
from execution.dashboards.components.cards import metric_card, summary_card, rag_status_badge
from execution.dashboards.components.tables import data_table, summary_table
from execution.dashboards.components.charts import sparkline, trend_indicator


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
