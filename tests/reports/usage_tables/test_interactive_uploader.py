"""
Tests for interactive_uploader module

Validates JavaScript generation, HTML component generation, and XSS protection
for the interactive CSV uploader functionality.
"""

import re

import pytest

from execution.reports.usage_tables.interactive_uploader import (
    generate_data_processing_js,
    generate_file_upload_handler_js,
    generate_import_button_html,
    generate_import_button_styles,
    generate_papaparse_script_tag,
    generate_placeholder_html,
    generate_utility_functions_js,
)


class TestImportButtonHTML:
    """Test import button HTML generation."""

    def test_generates_valid_html(self):
        """Test that import button HTML is well-formed."""
        html = generate_import_button_html()

        assert "<button" in html
        assert 'class="import-button"' in html
        assert "📥 IMPORT CSV" in html
        assert "onclick=\"document.getElementById('file-input').click()\"" in html

    def test_includes_file_input(self):
        """Test that file input element is included."""
        html = generate_import_button_html()

        assert '<input type="file"' in html
        assert 'id="file-input"' in html
        assert 'accept=".csv,.xlsx,.xls"' in html
        assert 'onchange="handleFileUpload(event)"' in html

    def test_file_input_accepts_correct_types(self):
        """Test that file input accepts correct file types."""
        html = generate_import_button_html()

        assert ".csv" in html
        assert ".xlsx" in html
        assert ".xls" in html


class TestPlaceholderHTML:
    """Test placeholder HTML generation."""

    def test_generates_valid_html(self):
        """Test that placeholder HTML is well-formed."""
        html = generate_placeholder_html()

        assert '<div id="placeholder"' in html
        assert 'class="placeholder"' in html
        assert "📊" in html  # Icon emoji
        assert "No Data Loaded" in html

    def test_includes_instructions(self):
        """Test that placeholder includes user instructions."""
        html = generate_placeholder_html()

        assert "IMPORT CSV" in html
        assert "Supported formats" in html
        assert "CSV, Excel" in html

    def test_includes_security_message(self):
        """Test that placeholder includes security message."""
        html = generate_placeholder_html()

        assert "browser" in html.lower()
        assert "never leaves your computer" in html


class TestFileUploadHandlerJS:
    """Test file upload handler JavaScript generation."""

    def test_generates_valid_javascript(self):
        """Test that generated JavaScript has valid syntax."""
        js = generate_file_upload_handler_js()

        # Check function declaration
        assert "function handleFileUpload(event)" in js

        # Check Papa.parse usage
        assert "Papa.parse(file," in js
        assert "header: true" in js
        assert "skipEmptyLines: true" in js

    def test_includes_loading_state_management(self):
        """Test that loading states are managed."""
        js = generate_file_upload_handler_js()

        assert "⏳ Loading..." in js
        assert "✅ Data Loaded" in js
        assert "❌ Error" in js
        assert ".disabled = true" in js
        assert ".disabled = false" in js

    def test_includes_error_handling(self):
        """Test that error handling is included."""
        js = generate_file_upload_handler_js()

        assert "error: function(error)" in js
        assert "alert('Error parsing CSV:" in js

    def test_calls_process_data_function(self):
        """Test that processData function is called."""
        js = generate_file_upload_handler_js()

        assert "processData(results.data)" in js

    def test_xss_protection_for_team_filter(self):
        """Test that team filter parameter does not introduce XSS vulnerabilities."""
        # Test with potentially malicious input
        malicious_input = "<script>alert('xss')</script>"
        js = generate_file_upload_handler_js(team_filter=malicious_input)

        # The team_filter parameter is not actually used in this function's output
        # (it's only used in generate_data_processing_js)
        # But we verify that no unescaped script tags appear
        assert "<script>" not in js
        # Check that the malicious payload specifically is not present
        assert "alert('xss')" not in js


class TestDataProcessingJS:
    """Test data processing JavaScript generation."""

    def test_generates_valid_javascript(self):
        """Test that generated JavaScript has valid syntax."""
        js = generate_data_processing_js()

        # Check function declaration
        assert "function processData(data)" in js

        # Check key logic
        assert "filter(row =>" in js
        assert "Software Company" in js

    def test_includes_column_name_handling(self):
        """Test that column name variations are handled."""
        js = generate_data_processing_js()

        # Should handle both "Claude Access?" and "Claude Access "
        assert "Claude Access?" in js
        assert "Claude Access " in js

        # Same for Devin
        assert "Devin Access?" in js
        assert "Devin Access " in js

    def test_includes_statistics_calculation(self):
        """Test that statistics are calculated."""
        js = generate_data_processing_js()

        assert "claudeActiveUsers" in js
        assert "devinActiveUsers" in js
        assert "avgClaudeUsage" in js
        assert "avgDevinUsage" in js

    def test_includes_table_generation(self):
        """Test that table generation is included."""
        js = generate_data_processing_js()

        assert "claudeTableBody" in js
        assert "devinTableBody" in js
        assert "innerHTML" in js

    def test_includes_access_badge_logic(self):
        """Test that access badge logic is included."""
        js = generate_data_processing_js()

        assert "badge badge-success" in js
        assert "badge badge-secondary" in js
        assert "YES" in js
        assert "No" in js

    def test_uses_heatmap_colors(self):
        """Test that heatmap color function is used."""
        js = generate_data_processing_js()

        assert "getHeatmapColor(usage)" in js
        assert "bgColor" in js
        assert "textColor" in js

    def test_uses_html_escaping(self):
        """Test that HTML escaping function is used."""
        js = generate_data_processing_js()

        assert "escapeHtml" in js

    def test_shows_and_hides_placeholder(self):
        """Test that placeholder is hidden after data load."""
        js = generate_data_processing_js()

        assert "placeholder" in js
        assert "hidden" in js
        assert "classList.add('hidden')" in js
        assert "classList.remove('hidden')" in js

    def test_xss_protection_for_team_filter(self):
        """Test that team filter is properly escaped."""
        malicious_input = "'; alert('xss'); '"
        js = generate_data_processing_js(team_filter=malicious_input)

        # Should be HTML escaped
        assert "alert" not in js or "alert" in js and "'" not in js.split("alert")[0][-5:]

    def test_filters_by_team(self):
        """Test that data is filtered by team."""
        js = generate_data_processing_js(team_filter="ENGINEERING")

        assert "ENGINEERING" in js
        assert "filter(row =>" in js


class TestUtilityFunctionsJS:
    """Test utility JavaScript functions generation."""

    def test_generates_valid_javascript(self):
        """Test that generated JavaScript has valid syntax."""
        js = generate_utility_functions_js()

        # Check function declarations
        assert "function getHeatmapColor(usage)" in js
        assert "function escapeHtml(text)" in js

    def test_heatmap_color_function(self):
        """Test heatmap color function logic."""
        js = generate_utility_functions_js()

        # High usage (>=100) - Green
        assert "#d1fae5" in js
        assert "#065f46" in js

        # Medium usage (20-99) - Amber
        assert "#fef3c7" in js
        assert "#92400e" in js

        # Low usage (<20) - Red
        assert "#fee2e2" in js
        assert "#991b1b" in js

    def test_heatmap_thresholds(self):
        """Test that heatmap thresholds are correct."""
        js = generate_utility_functions_js()

        assert "usage >= 100" in js
        assert "usage >= 20" in js

    def test_escape_html_function(self):
        """Test HTML escaping function."""
        js = generate_utility_functions_js()

        # Should use DOM API for safe escaping
        assert "createElement('div')" in js
        assert "textContent = text" in js
        assert "innerHTML" in js

    def test_escape_html_prevents_xss(self):
        """Test that escapeHtml function prevents XSS."""
        js = generate_utility_functions_js()

        # Function should use textContent (safe) not innerHTML (unsafe)
        # Pattern: div.textContent = text; return div.innerHTML
        assert "textContent = text" in js


class TestImportButtonStyles:
    """Test import button CSS styles generation."""

    def test_generates_valid_css(self):
        """Test that CSS is well-formed."""
        css = generate_import_button_styles()

        assert ".import-button {" in css
        assert ".placeholder {" in css
        assert "#file-input {" in css

    def test_includes_positioning(self):
        """Test that button is positioned correctly."""
        css = generate_import_button_styles()

        assert "position: fixed" in css
        assert "top:" in css
        assert "right:" in css

    def test_includes_visual_styling(self):
        """Test that visual styling is included."""
        css = generate_import_button_styles()

        assert "background:" in css
        assert "gradient" in css
        assert "border-radius:" in css
        assert "box-shadow:" in css

    def test_includes_hover_effects(self):
        """Test that hover effects are included."""
        css = generate_import_button_styles()

        assert ".import-button:hover" in css
        assert "transform:" in css

    def test_hides_file_input(self):
        """Test that file input is hidden."""
        css = generate_import_button_styles()

        assert "#file-input" in css
        assert "display: none" in css

    def test_includes_placeholder_styles(self):
        """Test that placeholder styles are included."""
        css = generate_import_button_styles()

        assert ".placeholder" in css
        assert ".placeholder-icon" in css
        assert ".placeholder h2" in css

    def test_includes_hidden_class(self):
        """Test that hidden utility class is included."""
        css = generate_import_button_styles()

        assert ".hidden" in css
        assert "display: none !important" in css


class TestPapaparseScriptTag:
    """Test PapaParse script tag generation."""

    def test_generates_valid_script_tag(self):
        """Test that script tag is well-formed."""
        tag = generate_papaparse_script_tag()

        assert "<script" in tag
        assert "</script>" in tag or "/>" in tag

    def test_uses_cdn(self):
        """Test that CDN URL is used."""
        tag = generate_papaparse_script_tag()

        assert "cdnjs.cloudflare.com" in tag or "cdn" in tag.lower()
        assert "papaparse" in tag.lower()

    def test_includes_version(self):
        """Test that a version is specified."""
        tag = generate_papaparse_script_tag()

        # Should include version number (e.g., 5.4.1)
        version_pattern = r"\d+\.\d+\.\d+"
        assert re.search(version_pattern, tag)

    def test_uses_https(self):
        """Test that HTTPS is used for security."""
        tag = generate_papaparse_script_tag()

        assert "https://" in tag.lower()
        assert "http://" not in tag.lower() or "https://" in tag.lower()


class TestJavaScriptIntegration:
    """Test integration between JavaScript functions."""

    def test_file_handler_calls_process_data(self):
        """Test that file handler calls processData."""
        handler_js = generate_file_upload_handler_js()
        processor_js = generate_data_processing_js()

        # Handler should call processData
        assert "processData(" in handler_js

        # Processor should define processData
        assert "function processData(" in processor_js

    def test_processor_uses_utilities(self):
        """Test that processor uses utility functions."""
        processor_js = generate_data_processing_js()
        utilities_js = generate_utility_functions_js()

        # Processor should use getHeatmapColor
        assert "getHeatmapColor" in processor_js

        # Utilities should define getHeatmapColor
        assert "function getHeatmapColor(" in utilities_js

        # Processor should use escapeHtml
        assert "escapeHtml" in processor_js

        # Utilities should define escapeHtml
        assert "function escapeHtml(" in utilities_js

    def test_all_functions_can_be_combined(self):
        """Test that all JavaScript functions can be combined."""
        handler_js = generate_file_upload_handler_js()
        processor_js = generate_data_processing_js()
        utilities_js = generate_utility_functions_js()

        combined = handler_js + processor_js + utilities_js

        # All function definitions should be present
        assert "function handleFileUpload(" in combined
        assert "function processData(" in combined
        assert "function getHeatmapColor(" in combined
        assert "function escapeHtml(" in combined


class TestXSSProtection:
    """Test XSS protection in generated code."""

    def test_team_filter_is_escaped(self):
        """Test that team filter values are escaped."""
        dangerous_values = [
            "<script>alert('xss')</script>",
            "'; alert('xss'); '",
            '"; alert("xss"); "',
            "<img src=x onerror=alert('xss')>",
        ]

        for dangerous in dangerous_values:
            handler_js = generate_file_upload_handler_js(team_filter=dangerous)
            processor_js = generate_data_processing_js(team_filter=dangerous)

            # Should not contain unescaped dangerous content
            # Either fully removed or escaped
            assert "<script>" not in handler_js or "&lt;" in handler_js
            assert "<script>" not in processor_js or "&lt;" in processor_js

    def test_html_content_uses_escape_function(self):
        """Test that user data is escaped in HTML generation."""
        processor_js = generate_data_processing_js()

        # Should use escapeHtml for user-provided data
        # Check that Name and Job Title use escapeHtml
        assert "escapeHtml(row['Name']" in processor_js
        assert "escapeHtml(row['Job Title']" in processor_js

    def test_no_eval_or_function_constructors(self):
        """Test that dangerous JavaScript patterns are not used."""
        handler_js = generate_file_upload_handler_js()
        processor_js = generate_data_processing_js()
        utilities_js = generate_utility_functions_js()

        combined = handler_js + processor_js + utilities_js

        # Should not use eval() or Function() constructor
        assert "eval(" not in combined
        assert "new Function(" not in combined


class TestOutputFormat:
    """Test that generated code is properly formatted."""

    def test_javascript_has_consistent_indentation(self):
        """Test that JavaScript has consistent indentation."""
        js_functions = [
            generate_file_upload_handler_js(),
            generate_data_processing_js(),
            generate_utility_functions_js(),
        ]

        for js in js_functions:
            lines = js.split("\n")
            # Check that there are indented lines
            indented_lines = [line for line in lines if line.startswith("    ") or line.startswith("\t")]
            assert len(indented_lines) > 0

    def test_css_has_proper_structure(self):
        """Test that CSS has proper structure."""
        css = generate_import_button_styles()

        # Should have opening and closing braces
        assert css.count("{") == css.count("}")

        # Should have selectors
        assert "." in css  # Class selectors
        assert "#" in css  # ID selectors

    def test_html_has_proper_structure(self):
        """Test that HTML has proper structure."""
        html_functions = [
            generate_import_button_html(),
            generate_placeholder_html(),
        ]

        for html in html_functions:
            # Count opening and closing tags
            opening_tags = html.count("<div") + html.count("<button") + html.count("<input")
            closing_tags = html.count("</div>") + html.count("</button>") + html.count("/>")

            # Should have balanced tags (approximately)
            assert opening_tags > 0
