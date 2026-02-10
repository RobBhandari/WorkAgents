"""
Tests for Security Detail Page Generator

Tests cover:
- Product detail page generation
- Vulnerability row generation
- Severity filtering and sorting
- HTML escaping
- CSS styles generation
- JavaScript functionality code
- Edge cases (empty data, long text, special characters)
- Theme toggle rendering
- Export functionality rendering
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from execution.collectors.armorcode_vulnerability_loader import VulnerabilityDetail
from execution.dashboards.security_detail_page import (
    _escape_html,
    _generate_vulnerability_rows,
    _get_detail_page_javascript,
    _get_detail_page_styles,
    generate_product_detail_page,
)


@pytest.fixture
def sample_vulnerabilities():
    """Sample vulnerability list for testing"""
    return [
        VulnerabilityDetail(
            id="vuln-001-abc123",
            title="SQL Injection in Login Form",
            description="Critical SQL injection vulnerability in authentication endpoint",
            severity="CRITICAL",
            status="OPEN",
            created_at="2025-12-25T00:00:00Z",
            product="Web Application",
            age_days=45,
        ),
        VulnerabilityDetail(
            id="vuln-002-def456",
            title="XSS in User Profile",
            description="Cross-site scripting vulnerability in user profile page",
            severity="HIGH",
            status="CONFIRMED",
            created_at="2026-01-09T00:00:00Z",
            product="Web Application",
            age_days=30,
        ),
        VulnerabilityDetail(
            id="vuln-003-ghi789",
            title="Remote Code Execution",
            description="Remote code execution vulnerability in file upload handler",
            severity="CRITICAL",
            status="OPEN",
            created_at="2025-11-12T00:00:00Z",
            product="Web Application",
            age_days=90,
        ),
        VulnerabilityDetail(
            id="vuln-004-jkl012",
            title="Information Disclosure",
            description="Sensitive information disclosure in API response",
            severity="MEDIUM",
            status="OPEN",
            created_at="2026-02-03T00:00:00Z",
            product="Web Application",
            age_days=5,
        ),
    ]


@pytest.fixture
def sample_vulnerability_with_long_text():
    """Vulnerability with long title and description for truncation testing"""
    return VulnerabilityDetail(
        id="vuln-long-123456789",
        title="A" * 150,  # 150 characters (should be truncated at 100)
        description="B" * 250,  # 250 characters (should be truncated at 200)
        severity="HIGH",
        status="OPEN",
        created_at="2026-01-30T00:00:00Z",
        product="Test Product",
        age_days=10,
    )


@pytest.fixture
def sample_vulnerability_with_html():
    """Vulnerability with HTML characters that need escaping"""
    return VulnerabilityDetail(
        id="vuln-html-123",
        title='<script>alert("XSS")</script>',
        description='<img src="x" onerror="alert(1)">',
        severity="HIGH",
        status="OPEN",
        created_at="2026-02-05T00:00:00Z",
        product="Test Product",
        age_days=5,
    )


class TestGenerateProductDetailPage:
    """Tests for main detail page generation function"""

    def test_generate_page_with_vulnerabilities(self, sample_vulnerabilities):
        """Should generate complete HTML page with all vulnerabilities"""
        html = generate_product_detail_page("Test Product", "prod-123", sample_vulnerabilities)

        assert isinstance(html, str)
        assert len(html) > 0
        assert "<!DOCTYPE html>" in html
        assert "Test Product" in html
        assert "prod-123" in html

    def test_generate_page_with_query_date(self, sample_vulnerabilities):
        """Should include query date in page"""
        query_date = "2026-02-08"
        html = generate_product_detail_page("Test Product", "prod-123", sample_vulnerabilities, query_date)

        assert query_date in html
        assert "Security Vulnerability Report" in html

    def test_generate_page_defaults_to_today(self, sample_vulnerabilities):
        """Should default to today's date if query_date not provided"""
        today = datetime.now().strftime("%Y-%m-%d")
        html = generate_product_detail_page("Test Product", "prod-123", sample_vulnerabilities)

        assert today in html

    def test_page_includes_header_stats(self, sample_vulnerabilities):
        """Should calculate and display summary statistics"""
        html = generate_product_detail_page("Test Product", "prod-123", sample_vulnerabilities)

        # Total: 4, Critical: 2, High: 1, Open: 3, Confirmed: 1
        assert "4" in html  # Total
        assert ">2<" in html  # Critical count
        assert ">1<" in html  # High count
        assert ">3<" in html  # Open count
        assert ">1<" in html  # Confirmed count

    def test_page_includes_theme_toggle(self, sample_vulnerabilities):
        """Should include theme toggle button"""
        html = generate_product_detail_page("Test Product", "prod-123", sample_vulnerabilities)

        assert "theme-toggle" in html
        assert "toggleTheme()" in html
        assert "theme-icon" in html
        assert "theme-label" in html

    def test_page_includes_search_and_filters(self, sample_vulnerabilities):
        """Should include search input and filter buttons"""
        html = generate_product_detail_page("Test Product", "prod-123", sample_vulnerabilities)

        assert "searchInput" in html
        assert "filterTable()" in html
        assert "filterBySeverity" in html
        assert "filter-btn" in html

    def test_page_includes_export_button(self, sample_vulnerabilities):
        """Should include Excel export button"""
        html = generate_product_detail_page("Test Product", "prod-123", sample_vulnerabilities)

        assert "export-btn" in html
        assert "exportToExcel()" in html
        assert "Export to Excel" in html

    def test_page_includes_aging_heatmap(self, sample_vulnerabilities):
        """Should include aging heatmap component"""
        with patch("execution.dashboards.security_detail_page.generate_aging_heatmap") as mock_heatmap:
            mock_heatmap.return_value = "<div class='heatmap'>Test Heatmap</div>"

            html = generate_product_detail_page("Test Product", "prod-123", sample_vulnerabilities)

            assert "Test Heatmap" in html
            mock_heatmap.assert_called_once_with(sample_vulnerabilities)

    def test_page_includes_vulnerability_table(self, sample_vulnerabilities):
        """Should include sortable vulnerability table"""
        html = generate_product_detail_page("Test Product", "prod-123", sample_vulnerabilities)

        assert "vulnTable" in html
        assert "sortTable" in html
        assert "SQL Injection" in html
        assert "XSS in User Profile" in html

    def test_page_includes_footer(self, sample_vulnerabilities):
        """Should include footer with generation timestamp"""
        html = generate_product_detail_page("Test Product", "prod-123", sample_vulnerabilities)

        assert "footer" in html
        assert "Engineering Metrics Platform" in html
        assert "Product ID: prod-123" in html

    def test_page_with_empty_vulnerabilities(self):
        """Should handle empty vulnerability list"""
        html = generate_product_detail_page("Empty Product", "prod-999", [])

        assert "Empty Product" in html
        assert "prod-999" in html
        assert ">0<" in html  # All counts should be 0

    def test_vulnerabilities_sorted_by_severity_and_age(self, sample_vulnerabilities):
        """Should sort vulnerabilities by severity (CRITICAL first) then age (oldest first)"""
        html = generate_product_detail_page("Test Product", "prod-123", sample_vulnerabilities)

        # Critical vulnerabilities should appear first
        # vuln-003 (90 days, CRITICAL) should come before vuln-001 (45 days, CRITICAL)
        critical_90_pos = html.find("Remote Code Execution")
        critical_45_pos = html.find("SQL Injection")
        high_30_pos = html.find("XSS in User Profile")

        assert critical_90_pos < critical_45_pos  # Oldest CRITICAL first
        assert critical_45_pos < high_30_pos  # CRITICAL before HIGH

    def test_page_includes_xlsx_library(self, sample_vulnerabilities):
        """Should include XLSX library for Excel export"""
        html = generate_product_detail_page("Test Product", "prod-123", sample_vulnerabilities)

        assert "xlsx.full.min.js" in html
        assert "cdnjs.cloudflare.com" in html

    def test_page_uses_dark_theme_by_default(self, sample_vulnerabilities):
        """Should set dark theme by default"""
        html = generate_product_detail_page("Test Product", "prod-123", sample_vulnerabilities)

        assert 'data-theme="dark"' in html


class TestGenerateVulnerabilityRows:
    """Tests for vulnerability table row generation"""

    def test_generate_rows_for_vulnerabilities(self, sample_vulnerabilities):
        """Should generate HTML rows for each vulnerability"""
        rows_html = _generate_vulnerability_rows(sample_vulnerabilities)

        assert isinstance(rows_html, str)
        assert "<tr>" in rows_html
        assert "<td" in rows_html
        assert "SQL Injection" in rows_html
        assert "XSS" in rows_html

    def test_row_includes_severity_badge(self, sample_vulnerabilities):
        """Should include severity badge with appropriate class"""
        rows_html = _generate_vulnerability_rows(sample_vulnerabilities)

        assert 'class="severity critical"' in rows_html
        assert 'class="severity high"' in rows_html

    def test_row_includes_status_badge(self, sample_vulnerabilities):
        """Should include status badge with appropriate class"""
        rows_html = _generate_vulnerability_rows(sample_vulnerabilities)

        assert 'class="status open"' in rows_html
        assert 'class="status confirmed"' in rows_html

    def test_row_includes_age_days(self, sample_vulnerabilities):
        """Should display age in days"""
        rows_html = _generate_vulnerability_rows(sample_vulnerabilities)

        assert ">45<" in rows_html
        assert ">30<" in rows_html
        assert ">90<" in rows_html

    def test_row_truncates_long_title(self, sample_vulnerability_with_long_text):
        """Should truncate titles longer than 100 characters"""
        rows_html = _generate_vulnerability_rows([sample_vulnerability_with_long_text])

        # Title should be truncated to 100 chars + "..."
        assert "A" * 100 + "..." in rows_html
        assert "A" * 150 not in rows_html

    def test_row_truncates_long_description(self, sample_vulnerability_with_long_text):
        """Should truncate descriptions longer than 200 characters"""
        rows_html = _generate_vulnerability_rows([sample_vulnerability_with_long_text])

        # Description should be truncated to 200 chars + "..."
        assert "B" * 200 + "..." in rows_html
        assert "B" * 250 not in rows_html

    def test_row_truncates_vulnerability_id(self, sample_vulnerabilities):
        """Should truncate ID to first 8 characters"""
        rows_html = _generate_vulnerability_rows(sample_vulnerabilities)

        # IDs should be truncated to 8 chars + "..."
        assert "vuln-001..." in rows_html or "vuln-001-abc..." in rows_html
        assert "vuln-002..." in rows_html or "vuln-002-def..." in rows_html

    def test_row_escapes_html_in_title(self, sample_vulnerability_with_html):
        """Should escape HTML characters in title"""
        rows_html = _generate_vulnerability_rows([sample_vulnerability_with_html])

        assert "&lt;script&gt;" in rows_html
        assert "&quot;" in rows_html or "&#x27;" in rows_html
        assert "<script>" not in rows_html  # Raw script tag should NOT be present

    def test_row_escapes_html_in_description(self, sample_vulnerability_with_html):
        """Should escape HTML characters in description"""
        rows_html = _generate_vulnerability_rows([sample_vulnerability_with_html])

        assert "&lt;img" in rows_html
        assert "&gt;" in rows_html
        assert 'onerror="alert' not in rows_html  # Raw JavaScript should not be present

    def test_empty_vulnerabilities_returns_empty_string(self):
        """Should return empty string for empty list"""
        rows_html = _generate_vulnerability_rows([])

        assert rows_html == ""


class TestEscapeHtml:
    """Tests for HTML character escaping"""

    def test_escape_ampersand(self):
        """Should escape & to &amp;"""
        assert _escape_html("A & B") == "A &amp; B"

    def test_escape_less_than(self):
        """Should escape < to &lt;"""
        assert _escape_html("A < B") == "A &lt; B"

    def test_escape_greater_than(self):
        """Should escape > to &gt;"""
        assert _escape_html("A > B") == "A &gt; B"

    def test_escape_double_quote(self):
        """Should escape \" to &quot;"""
        assert _escape_html('A "B" C') == "A &quot;B&quot; C"

    def test_escape_single_quote(self):
        """Should escape ' to &#x27;"""
        assert _escape_html("A 'B' C") == "A &#x27;B&#x27; C"

    def test_escape_all_characters(self):
        """Should escape multiple special characters"""
        result = _escape_html('<script>alert("XSS & stuff")</script>')
        assert "&lt;script&gt;" in result
        assert "&quot;" in result
        assert "&amp;" in result

    def test_escape_empty_string(self):
        """Should handle empty string"""
        assert _escape_html("") == ""

    def test_escape_none_returns_empty(self):
        """Should return empty string for None"""
        assert _escape_html(None) == ""  # type: ignore[arg-type]

    def test_escape_already_escaped(self):
        """Should double-escape already escaped content"""
        result = _escape_html("&amp;")
        assert result == "&amp;amp;"

    def test_escape_normal_text_unchanged(self):
        """Should not modify text without special characters"""
        text = "Normal vulnerability description with no special chars"
        assert _escape_html(text) == text


class TestGetDetailPageStyles:
    """Tests for CSS styles generation"""

    def test_returns_css_string(self):
        """Should return CSS styles as string"""
        styles = _get_detail_page_styles()

        assert isinstance(styles, str)
        assert len(styles) > 0

    def test_includes_theme_variables(self):
        """Should include CSS custom properties for theming"""
        styles = _get_detail_page_styles()

        assert ":root" in styles
        assert '[data-theme="dark"]' in styles
        assert "--bg-primary" in styles
        assert "--text-primary" in styles

    def test_includes_dark_theme_colors(self):
        """Should define dark theme color palette"""
        styles = _get_detail_page_styles()

        assert "#0f172a" in styles  # Dark bg
        assert "#1e293b" in styles  # Dark secondary

    def test_includes_light_theme_colors(self):
        """Should define light theme color palette"""
        styles = _get_detail_page_styles()

        assert "#f9fafb" in styles  # Light bg
        assert "#1f2937" in styles  # Light text

    def test_includes_theme_toggle_styles(self):
        """Should include theme toggle button styles"""
        styles = _get_detail_page_styles()

        assert ".theme-toggle" in styles

    def test_includes_header_styles(self):
        """Should include header section styles"""
        styles = _get_detail_page_styles()

        assert ".header" in styles
        assert ".header-stats" in styles
        assert ".stat" in styles

    def test_includes_table_styles(self):
        """Should include table and row styles"""
        styles = _get_detail_page_styles()

        assert "table" in styles
        assert "thead" in styles
        assert "tbody" in styles

    def test_includes_severity_badge_styles(self):
        """Should include severity badge colors"""
        styles = _get_detail_page_styles()

        assert ".severity.critical" in styles
        assert ".severity.high" in styles

    def test_includes_filter_button_styles(self):
        """Should include filter button styles"""
        styles = _get_detail_page_styles()

        assert ".filter-btn" in styles
        assert ".filter-btn.active" in styles

    def test_includes_aging_heatmap_styles(self):
        """Should include aging heatmap styles from component"""
        with patch("execution.dashboards.security_detail_page.get_aging_heatmap_styles") as mock_heatmap_styles:
            mock_heatmap_styles.return_value = ".heatmap { color: red; }"

            styles = _get_detail_page_styles()

            assert ".heatmap { color: red; }" in styles
            mock_heatmap_styles.assert_called_once()

    def test_includes_responsive_styles(self):
        """Should include responsive design elements"""
        styles = _get_detail_page_styles()

        # Check for flexible layouts
        assert "flex" in styles or "display:" in styles

    def test_includes_footer_styles(self):
        """Should include footer styles"""
        styles = _get_detail_page_styles()

        assert ".footer" in styles


class TestGetDetailPageJavascript:
    """Tests for JavaScript functionality generation"""

    def test_returns_javascript_string(self):
        """Should return JavaScript code as string"""
        js = _get_detail_page_javascript()

        assert isinstance(js, str)
        assert len(js) > 0

    def test_includes_theme_toggle_function(self):
        """Should include toggleTheme function"""
        js = _get_detail_page_javascript()

        assert "function toggleTheme()" in js
        assert "data-theme" in js
        assert "theme-icon" in js
        assert "theme-label" in js

    def test_theme_toggle_switches_between_dark_and_light(self):
        """Should toggle between dark and light themes"""
        js = _get_detail_page_javascript()

        assert "'dark'" in js and "'light'" in js
        assert "🌙" in js
        assert "☀️" in js

    def test_includes_filter_table_function(self):
        """Should include filterTable search function"""
        js = _get_detail_page_javascript()

        assert "function filterTable()" in js
        assert "searchInput" in js
        assert "toLowerCase()" in js

    def test_includes_filter_by_severity_function(self):
        """Should include filterBySeverity function"""
        js = _get_detail_page_javascript()

        assert "function filterBySeverity(severity)" in js
        assert "currentFilter" in js

    def test_filter_by_severity_handles_all_filter(self):
        """Should handle 'ALL' severity filter"""
        js = _get_detail_page_javascript()

        assert "'ALL'" in js

    def test_includes_sort_table_function(self):
        """Should include sortTable function"""
        js = _get_detail_page_javascript()

        assert "function sortTable(columnIndex)" in js
        assert "sort(" in js

    def test_sort_handles_numeric_age_column(self):
        """Should handle numeric sorting for age column"""
        js = _get_detail_page_javascript()

        assert "columnIndex === 2" in js  # Age column
        assert "parseInt" in js

    def test_sort_handles_string_columns(self):
        """Should handle string sorting for text columns"""
        js = _get_detail_page_javascript()

        assert "localeCompare" in js

    def test_includes_export_to_excel_function(self):
        """Should include exportToExcel function"""
        js = _get_detail_page_javascript()

        assert "function exportToExcel()" in js
        assert "XLSX" in js
        assert "table_to_book" in js
        assert "writeFile" in js

    def test_export_uses_date_in_filename(self):
        """Should include date in Excel export filename"""
        js = _get_detail_page_javascript()

        assert "toISOString()" in js
        assert ".xlsx" in js


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    def test_vulnerability_with_no_cve_id(self):
        """Should handle vulnerabilities without CVE ID"""
        vuln = VulnerabilityDetail(
            id="vuln-no-cve",
            title="No CVE Vulnerability",
            description="This vulnerability has no CVE identifier",
            severity="HIGH",
            status="OPEN",
            created_at="2026-01-30T00:00:00Z",
            product="Test",
            age_days=10,
        )

        rows_html = _generate_vulnerability_rows([vuln])
        assert "No CVE Vulnerability" in rows_html

    def test_vulnerability_with_zero_age(self):
        """Should handle vulnerabilities with 0 age days"""
        vuln = VulnerabilityDetail(
            id="vuln-new",
            title="Brand New Vulnerability",
            description="This vulnerability was just discovered",
            severity="CRITICAL",
            status="OPEN",
            created_at="2026-02-10T00:00:00Z",
            product="Test",
            age_days=0,
        )

        rows_html = _generate_vulnerability_rows([vuln])
        assert ">0<" in rows_html

    def test_vulnerability_with_very_long_id(self):
        """Should truncate very long vulnerability IDs"""
        vuln = VulnerabilityDetail(
            id="vuln-" + "x" * 100,  # Very long ID
            title="Test",
            description="Test description",
            severity="HIGH",
            status="OPEN",
            created_at="2026-02-05T00:00:00Z",
            product="Test",
            age_days=5,
        )

        rows_html = _generate_vulnerability_rows([vuln])
        # Should truncate to 8 chars
        assert "vuln-xxx..." in rows_html

    def test_product_name_with_special_characters(self):
        """Should handle product names with special characters"""
        html = generate_product_detail_page("Product & Co. <Test>", "prod-123", [])

        # Product name in title/header - may or may not be escaped depending on context
        assert "Product" in html

    def test_large_number_of_vulnerabilities(self):
        """Should handle large number of vulnerabilities"""
        vulns = [
            VulnerabilityDetail(
                id=f"vuln-{i:04d}",
                title=f"Vulnerability {i}",
                description=f"Description for vulnerability {i}",
                severity="HIGH" if i % 2 == 0 else "MEDIUM",
                status="OPEN",
                created_at="2026-02-05T00:00:00Z",
                product="Test",
                age_days=i,
            )
            for i in range(100)
        ]

        html = generate_product_detail_page("Test Product", "prod-123", vulns)
        assert len(html) > 0
        assert "100" in html  # Total count

    def test_mixed_severity_levels(self):
        """Should handle all severity levels"""
        vulns = [
            VulnerabilityDetail(
                id=f"vuln-{sev}",
                title=f"{sev} Vulnerability",
                description=f"A {sev} severity vulnerability",
                severity=sev,
                status="OPEN",
                created_at="2026-01-30T00:00:00Z",
                product="Test",
                age_days=10,
            )
            for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        ]

        rows_html = _generate_vulnerability_rows(vulns)
        assert "CRITICAL" in rows_html
        assert "HIGH" in rows_html
        assert "MEDIUM" in rows_html
        assert "LOW" in rows_html

    def test_mixed_status_values(self):
        """Should handle various status values"""
        statuses = ["OPEN", "CONFIRMED", "IN_PROGRESS", "RESOLVED", "CLOSED"]
        vulns = [
            VulnerabilityDetail(
                id=f"vuln-{i}",
                title=f"Vuln {status}",
                description=f"Vulnerability with {status} status",
                severity="HIGH",
                status=status,
                created_at="2026-01-30T00:00:00Z",
                product="Test",
                age_days=10,
            )
            for i, status in enumerate(statuses)
        ]

        rows_html = _generate_vulnerability_rows(vulns)
        for status in statuses:
            assert status in rows_html

    def test_empty_product_name(self):
        """Should handle empty product name"""
        html = generate_product_detail_page("", "prod-123", [])
        assert "prod-123" in html

    def test_empty_product_id(self):
        """Should handle empty product ID"""
        html = generate_product_detail_page("Test Product", "", [])
        assert "Test Product" in html
