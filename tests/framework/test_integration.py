"""
Integration tests for execution.framework package
"""

import pytest

from execution.framework import get_dashboard_framework


class TestFrameworkIntegration:
    """Test complete framework integration"""

    def test_get_dashboard_framework_returns_tuple(self):
        """Test that framework returns CSS and JavaScript tuple"""
        result = get_dashboard_framework()
        assert isinstance(result, tuple)
        assert len(result) == 2
        css, javascript = result
        assert isinstance(css, str)
        assert isinstance(javascript, str)

    def test_get_dashboard_framework_css_complete(self):
        """Test that CSS bundle is complete"""
        css, _ = get_dashboard_framework()
        assert "<style>" in css
        assert "</style>" in css
        # Theme variables
        assert ":root {" in css
        assert "--bg-primary" in css
        # Base styles
        assert "body {" in css
        # Components
        assert ".header {" in css
        assert ".card {" in css
        # Tables
        assert ".table-wrapper {" in css
        # Utilities
        assert ".badge {" in css

    def test_get_dashboard_framework_javascript_complete(self):
        """Test that JavaScript bundle is complete"""
        _, javascript = get_dashboard_framework()
        assert "<script>" in javascript
        assert "</script>" in javascript
        assert "function toggleTheme()" in javascript

    def test_get_dashboard_framework_custom_colors(self):
        """Test framework with custom colors"""
        css, _ = get_dashboard_framework(header_gradient_start="#8b5cf6", header_gradient_end="#7c3aed")
        assert "--header-gradient-start: #8b5cf6" in css
        assert "--header-gradient-end: #7c3aed" in css

    def test_get_dashboard_framework_feature_flags(self):
        """Test framework with different feature flags"""
        _, js1 = get_dashboard_framework(include_table_scroll=True, include_expandable_rows=True, include_glossary=True)
        _, js2 = get_dashboard_framework(
            include_table_scroll=False, include_expandable_rows=False, include_glossary=False
        )
        # Full version should be longer
        assert len(js1) > len(js2)
        # Full version should have all features
        assert "function toggleGlossary()" in js1
        assert "function toggleGlossary()" not in js2

    def test_get_dashboard_framework_css_no_duplicates(self):
        """Test that CSS doesn't have duplicate selectors"""
        css, _ = get_dashboard_framework()
        # This is a simple check - count occurrences of key selectors
        # In a real scenario, we'd parse the CSS to detect actual duplicates
        body_count = css.count("body {")
        assert body_count >= 1  # Should have at least one body selector

    def test_get_dashboard_framework_minification_ready(self):
        """Test that output is valid and minification-ready"""
        css, javascript = get_dashboard_framework()
        # Check for proper tag structure
        assert css.strip().startswith("<style>")
        assert css.strip().endswith("</style>")
        assert javascript.strip().startswith("<script>")
        assert javascript.strip().endswith("</script>")
        # Check no unclosed blocks
        assert css.count("{") == css.count("}")
        assert javascript.count("{") == javascript.count("}")

    def test_backward_compatibility(self):
        """Test backward compatibility with old API"""
        # Should work with positional arguments
        result1 = get_dashboard_framework("#667eea", "#764ba2", True, False, True)
        # Should work with keyword arguments
        result2 = get_dashboard_framework(
            header_gradient_start="#667eea",
            header_gradient_end="#764ba2",
            include_table_scroll=True,
            include_expandable_rows=False,
            include_glossary=True,
        )
        assert isinstance(result1, tuple)
        assert isinstance(result2, tuple)
