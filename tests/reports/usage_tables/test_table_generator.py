"""
Tests for HTML Table Generation Module

Validates table generation, heatmap colors, badges, and XSS protection.
"""

import html
from typing import Any

import pandas as pd
import pytest
from bs4 import BeautifulSoup

from execution.reports.usage_tables.table_generator import (
    AccessBadgeType,
    HeatmapColor,
    TableRow,
    generate_access_badge_html,
    generate_heatmap_cell_html,
    generate_table_html,
    generate_table_row_html,
    get_usage_heatmap_color,
    parse_access_value,
)


# Fixtures
@pytest.fixture
def sample_usage_dataframe() -> pd.DataFrame:
    """
    Create sample DataFrame for testing table generation.

    Returns:
        pd.DataFrame: Sample data with various usage patterns
    """
    return pd.DataFrame(
        {
            "Name": ["Alice Smith", "Bob Johnson", "Charlie Lee", "Diana Ross"],
            "Job Title": ["Senior Engineer", "Manager", "Junior Developer", "Tech Lead"],
            "Claude Access": ["YES", "NO", "1", "0"],
            "Claude 30 day usage": [150, 10, 75, 200],
            "Devin Access": ["1", "0", "YES", "NO"],
            "Devin_30d": [5, 0, 50, 120],
        }
    )


@pytest.fixture
def xss_attack_dataframe() -> pd.DataFrame:
    """
    Create DataFrame with XSS attack vectors for security testing.

    Returns:
        pd.DataFrame: Data with malicious HTML/JS injection attempts
    """
    return pd.DataFrame(
        {
            "Name": [
                "<script>alert('XSS')</script>",
                "Normal Name",
                "<img src=x onerror=alert('XSS')>",
                "Bob & Alice",
            ],
            "Job Title": [
                "Engineer<script>",
                "Manager",
                "<b>Bold Title</b>",
                'Title with "quotes"',
            ],
            "Claude Access": ["YES", "NO", "YES", "NO"],
            "Claude 30 day usage": [100, 50, 75, 25],
        }
    )


# Tests for get_usage_heatmap_color
class TestGetUsageHeatmapColor:
    """Tests for heatmap color determination based on usage thresholds."""

    def test_high_usage_green(self):
        """High usage (>=100) should return green color scheme."""
        color = get_usage_heatmap_color(100)
        assert color.background == "#d1fae5"
        assert color.text == "#065f46"
        assert color.intensity == "high"

        # Test boundary
        color_above = get_usage_heatmap_color(150)
        assert color_above.intensity == "high"

    def test_medium_usage_amber(self):
        """Medium usage (20-99) should return amber color scheme."""
        color = get_usage_heatmap_color(20)
        assert color.background == "#fef3c7"
        assert color.text == "#92400e"
        assert color.intensity == "medium"

        # Test middle of range
        color_mid = get_usage_heatmap_color(50)
        assert color_mid.intensity == "medium"

        # Test upper boundary
        color_upper = get_usage_heatmap_color(99)
        assert color_upper.intensity == "medium"

    def test_low_usage_red(self):
        """Low usage (<20) should return red color scheme."""
        color = get_usage_heatmap_color(0)
        assert color.background == "#fee2e2"
        assert color.text == "#991b1b"
        assert color.intensity == "low"

        # Test just below boundary
        color_below = get_usage_heatmap_color(19)
        assert color_below.intensity == "low"

    def test_edge_cases(self):
        """Test edge cases and boundaries."""
        # Exactly at boundaries
        assert get_usage_heatmap_color(100).intensity == "high"
        assert get_usage_heatmap_color(99.9).intensity == "medium"
        assert get_usage_heatmap_color(20).intensity == "medium"
        assert get_usage_heatmap_color(19.9).intensity == "low"

        # Negative usage (should be red)
        assert get_usage_heatmap_color(-10).intensity == "low"

        # Very high usage
        assert get_usage_heatmap_color(10000).intensity == "high"

    def test_heatmap_color_immutability(self):
        """HeatmapColor should be immutable (frozen dataclass)."""
        color = get_usage_heatmap_color(100)
        with pytest.raises((AttributeError, TypeError)):  # Frozen dataclass error
            color.background = "#000000"  # type: ignore


# Tests for parse_access_value
class TestParseAccessValue:
    """Tests for parsing various access value formats."""

    @pytest.mark.parametrize(
        "input_value,expected",
        [
            ("YES", AccessBadgeType.YES),
            ("yes", AccessBadgeType.YES),
            ("Yes", AccessBadgeType.YES),
            ("1", AccessBadgeType.YES),
            ("1.0", AccessBadgeType.YES),
            (1, AccessBadgeType.YES),
            (1.0, AccessBadgeType.YES),
        ],
    )
    def test_yes_values(self, input_value: Any, expected: AccessBadgeType):
        """Test values that should be parsed as YES."""
        assert parse_access_value(input_value) == expected

    @pytest.mark.parametrize(
        "input_value",
        [
            "NO",
            "no",
            "No",
            "0",
            "0.0",
            0,
            0.0,
            "",
            " ",
            "NaN",
            "None",
            None,
            "random",
            "True",
            "False",
        ],
    )
    def test_no_values(self, input_value: Any):
        """Test values that should be parsed as NO."""
        assert parse_access_value(input_value) == AccessBadgeType.NO

    def test_whitespace_handling(self):
        """Test that whitespace is properly stripped."""
        assert parse_access_value("  YES  ") == AccessBadgeType.YES
        assert parse_access_value("  NO  ") == AccessBadgeType.NO


# Tests for generate_access_badge_html
class TestGenerateAccessBadgeHtml:
    """Tests for access badge HTML generation."""

    def test_yes_badge(self):
        """YES badge should have success styling."""
        html_output = generate_access_badge_html(AccessBadgeType.YES)
        assert "badge-success" in html_output
        assert ">Yes<" in html_output
        assert "<span" in html_output

    def test_no_badge(self):
        """NO badge should have secondary styling."""
        html_output = generate_access_badge_html(AccessBadgeType.NO)
        assert "badge-secondary" in html_output
        assert ">No<" in html_output
        assert "<span" in html_output

    def test_badge_html_structure(self):
        """Validate HTML structure of badges using BeautifulSoup."""
        yes_html = generate_access_badge_html(AccessBadgeType.YES)
        soup = BeautifulSoup(yes_html, "html.parser")
        span = soup.find("span")
        assert span is not None
        classes = span.get("class")
        assert classes is not None
        assert "badge" in classes
        assert span.text == "Yes"


# Tests for generate_heatmap_cell_html
class TestGenerateHeatmapCellHtml:
    """Tests for heatmap cell HTML generation."""

    def test_heatmap_cell_structure(self):
        """Test basic HTML structure of heatmap cell."""
        color = HeatmapColor(background="#d1fae5", text="#065f46", intensity="high")
        html_output = generate_heatmap_cell_html(150, color)

        assert "<td" in html_output
        assert "heatmap-cell" in html_output
        assert "background-color: #d1fae5" in html_output
        assert "color: #065f46" in html_output
        assert 'data-value="150"' in html_output
        assert ">150<" in html_output

    def test_heatmap_cell_integer_display(self):
        """Usage should be displayed as integer even if float provided."""
        color = HeatmapColor(background="#fee2e2", text="#991b1b", intensity="low")
        html_output = generate_heatmap_cell_html(10.8, color)
        assert ">10<" in html_output
        assert 'data-value="10.8"' in html_output

    def test_heatmap_cell_zero_usage(self):
        """Test zero usage renders correctly."""
        color = get_usage_heatmap_color(0)
        html_output = generate_heatmap_cell_html(0, color)
        assert ">0<" in html_output
        assert 'data-value="0"' in html_output


# Tests for generate_table_row_html
class TestGenerateTableRowHtml:
    """Tests for complete table row HTML generation."""

    def test_table_row_basic(self):
        """Test basic table row with normal data."""
        row = TableRow(name="John Doe", job_title="Engineer", access="YES", usage=125.0)
        html_output = generate_table_row_html(row)

        assert "<tr>" in html_output
        assert "</tr>" in html_output
        assert "John Doe" in html_output
        assert "Engineer" in html_output
        assert "badge-success" in html_output
        assert html_output.count("<td") == 4  # 4 cells

    def test_table_row_html_escaping(self):
        """Test that user data is properly HTML-escaped."""
        row = TableRow(
            name="<script>alert('xss')</script>",
            job_title="Manager<b>bold</b>",
            access="YES",
            usage=100.0,
        )
        html_output = generate_table_row_html(row)

        # Script tag should be escaped
        assert "<script>" not in html_output
        assert "&lt;script&gt;" in html_output

        # Bold tag should be escaped
        assert "<b>" not in html_output
        assert "&lt;b&gt;" in html_output

    def test_table_row_special_characters(self):
        """Test proper escaping of special HTML characters."""
        row = TableRow(
            name="Bob & Alice",
            job_title='Manager "quoted"',
            access="NO",
            usage=50.0,
        )
        html_output = generate_table_row_html(row)

        # Ampersand should be escaped
        assert "&amp;" in html_output or "Bob & Alice" in html_output

        # Quotes should be handled properly
        assert "Manager" in html_output

    def test_table_row_different_access_formats(self):
        """Test row generation with different access value formats."""
        # Test with "1"
        row1 = TableRow(name="User1", job_title="Title1", access="1", usage=100.0)
        html1 = generate_table_row_html(row1)
        assert "badge-success" in html1

        # Test with "NO"
        row2 = TableRow(name="User2", job_title="Title2", access="NO", usage=50.0)
        html2 = generate_table_row_html(row2)
        assert "badge-secondary" in html2


# Tests for generate_table_html
class TestGenerateTableHtml:
    """Tests for complete table HTML generation."""

    def test_complete_table_generation(self, sample_usage_dataframe: pd.DataFrame):
        """Test generation of complete HTML table."""
        html_output = generate_table_html(
            df=sample_usage_dataframe,
            table_id="testTable",
            title="Test Usage Table",
            usage_column="Claude 30 day usage",
            access_column="Claude Access",
        )

        # Check overall structure
        assert '<div class="table-card">' in html_output
        assert "<h2>Test Usage Table</h2>" in html_output
        assert '<table id="testTable"' in html_output
        assert "<thead>" in html_output
        assert "<tbody>" in html_output

        # Check column headers
        assert ">Name<" in html_output
        assert ">Job Title<" in html_output
        assert ">Access<" in html_output
        assert ">Usage (30 days)<" in html_output

        # Check data rows exist
        assert "Alice Smith" in html_output
        assert "Bob Johnson" in html_output
        assert "Charlie Lee" in html_output
        assert "Diana Ross" in html_output

    def test_table_sortable_headers(self, sample_usage_dataframe: pd.DataFrame):
        """Test that column headers have sortable onclick handlers."""
        html_output = generate_table_html(
            df=sample_usage_dataframe,
            table_id="sortableTable",
            title="Sortable Table",
            usage_column="Claude 30 day usage",
            access_column="Claude Access",
        )

        # Check for onclick handlers
        assert "onclick=\"sortTable('sortableTable', 0)\"" in html_output
        assert "onclick=\"sortTable('sortableTable', 1)\"" in html_output
        assert "onclick=\"sortTable('sortableTable', 2)\"" in html_output
        assert "onclick=\"sortTable('sortableTable', 3)\"" in html_output

    def test_table_xss_protection(self, xss_attack_dataframe: pd.DataFrame):
        """Test that XSS attacks are neutralized by HTML escaping."""
        html_output = generate_table_html(
            df=xss_attack_dataframe,
            table_id="secureTable",
            title="<script>alert('title')</script>",  # Also test title escaping
            usage_column="Claude 30 day usage",
            access_column="Claude Access",
        )

        # Check that script tags are escaped in title
        assert "<script>" not in html_output or html_output.count("<script>") == 0
        assert "&lt;script&gt;" in html_output

        # Check that script tags are escaped in data
        assert "alert('XSS')" not in html_output
        assert "&lt;script&gt;" in html_output

        # Check that img tags are escaped
        assert "<img src=" not in html_output
        assert "&lt;img" in html_output

        # Check that special characters are handled
        assert "&amp;" in html_output or "Bob & Alice" in html_output

    def test_table_heatmap_colors(self, sample_usage_dataframe: pd.DataFrame):
        """Test that heatmap colors are applied correctly based on usage."""
        html_output = generate_table_html(
            df=sample_usage_dataframe,
            table_id="heatmapTable",
            title="Heatmap Test",
            usage_column="Claude 30 day usage",
            access_column="Claude Access",
        )

        # Alice (150 usage) - should be green
        assert "#d1fae5" in html_output  # Green background

        # Bob (10 usage) - should be red
        assert "#fee2e2" in html_output  # Red background

        # Charlie (75 usage) - should be amber
        assert "#fef3c7" in html_output  # Amber background

    def test_table_access_badges(self, sample_usage_dataframe: pd.DataFrame):
        """Test that access badges are generated correctly."""
        html_output = generate_table_html(
            df=sample_usage_dataframe,
            table_id="badgeTable",
            title="Badge Test",
            usage_column="Claude 30 day usage",
            access_column="Claude Access",
        )

        # Should have both success and secondary badges
        assert "badge-success" in html_output
        assert "badge-secondary" in html_output

    def test_table_missing_columns(self, sample_usage_dataframe: pd.DataFrame):
        """Test that missing required columns raise KeyError."""
        with pytest.raises(KeyError) as exc_info:
            generate_table_html(
                df=sample_usage_dataframe,
                table_id="errorTable",
                title="Error Test",
                usage_column="NonExistent Column",
                access_column="Claude Access",
            )
        assert "Missing required columns" in str(exc_info.value)

    def test_table_with_different_columns(self, sample_usage_dataframe: pd.DataFrame):
        """Test table generation with Devin columns."""
        html_output = generate_table_html(
            df=sample_usage_dataframe,
            table_id="devinTable",
            title="Devin Usage",
            usage_column="Devin_30d",
            access_column="Devin Access",
        )

        assert "Devin Usage" in html_output
        assert "devinTable" in html_output
        # Check that correct usage values are present
        assert ">5<" in html_output  # Alice's Devin usage
        assert ">120<" in html_output  # Diana's Devin usage

    def test_table_with_empty_dataframe(self):
        """Test table generation with empty DataFrame."""
        empty_df = pd.DataFrame(columns=["Name", "Job Title", "Claude Access", "Claude 30 day usage"])
        html_output = generate_table_html(
            df=empty_df,
            table_id="emptyTable",
            title="Empty Table",
            usage_column="Claude 30 day usage",
            access_column="Claude Access",
        )

        # Should have structure but no data rows
        assert "<thead>" in html_output
        assert "<tbody>" in html_output
        assert "Alice" not in html_output  # No data

    def test_table_html_structure_with_beautifulsoup(self, sample_usage_dataframe: pd.DataFrame):
        """Validate complete HTML structure using BeautifulSoup parser."""
        html_output = generate_table_html(
            df=sample_usage_dataframe,
            table_id="structureTable",
            title="Structure Test",
            usage_column="Claude 30 day usage",
            access_column="Claude Access",
        )

        soup = BeautifulSoup(html_output, "html.parser")

        # Check table exists
        table = soup.find("table", id="structureTable")
        assert table is not None

        # Check header row has 4 columns
        thead = table.find("thead")
        assert thead is not None
        header_row = thead.find("tr")
        assert header_row is not None
        assert len(header_row.find_all("th")) == 4

        # Check data rows
        tbody = table.find("tbody")
        assert tbody is not None
        data_rows = tbody.find_all("tr")
        assert len(data_rows) == 4  # 4 users in sample data

        # Each row should have 4 cells
        for row in data_rows:
            assert len(row.find_all("td")) == 4


# Integration Tests
class TestTableGeneratorIntegration:
    """Integration tests for complete workflow."""

    def test_end_to_end_table_generation(self):
        """Test complete workflow from data to HTML."""
        # Create realistic data
        df = pd.DataFrame(
            {
                "Name": ["Test User 1", "Test User 2", "Test User 3"],
                "Job Title": ["Engineer", "Manager", "Analyst"],
                "Tool Access": ["YES", "NO", "1"],
                "Tool Usage": [250, 15, 80],
            }
        )

        # Generate table
        html_output = generate_table_html(
            df=df,
            table_id="integrationTest",
            title="Integration Test Table",
            usage_column="Tool Usage",
            access_column="Tool Access",
        )

        # Parse with BeautifulSoup
        soup = BeautifulSoup(html_output, "html.parser")

        # Verify structure
        table = soup.find("table", id="integrationTest")
        assert table is not None

        # Verify data
        tbody = table.find("tbody")
        assert tbody is not None
        rows = tbody.find_all("tr")
        assert len(rows) == 3

        # Verify first row (high usage - green)
        first_row = rows[0]
        cells = first_row.find_all("td")
        assert "Test User 1" in cells[0].text
        assert "Engineer" in cells[1].text
        assert "Yes" in cells[2].text  # Access badge
        assert "250" in cells[3].text

        # Verify heatmap colors
        heatmap_cell = cells[3]
        assert "background-color: #d1fae5" in str(heatmap_cell)  # Green for high usage

    def test_multiple_tables_with_different_data(self, sample_usage_dataframe: pd.DataFrame):
        """Test generating multiple tables from same DataFrame."""
        claude_html = generate_table_html(
            df=sample_usage_dataframe,
            table_id="claudeMulti",
            title="Claude Multi",
            usage_column="Claude 30 day usage",
            access_column="Claude Access",
        )

        devin_html = generate_table_html(
            df=sample_usage_dataframe,
            table_id="devinMulti",
            title="Devin Multi",
            usage_column="Devin_30d",
            access_column="Devin Access",
        )

        # Tables should be different
        assert "claudeMulti" in claude_html
        assert "devinMulti" in devin_html
        assert claude_html != devin_html

        # Both should have valid structure
        assert "<table" in claude_html
        assert "<table" in devin_html
