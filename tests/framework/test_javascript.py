"""
Tests for execution.framework.javascript module
"""

import pytest

from execution.framework.javascript import (
    get_dashboard_javascript,
    get_expandable_row_script,
    get_glossary_toggle_script,
    get_javascript_docs,
    get_table_scroll_script,
    get_theme_toggle_script,
)


class TestThemeToggleScript:
    """Test theme toggle JavaScript"""

    def test_get_theme_toggle_script_functions(self):
        """Test theme toggle script contains required functions"""
        js = get_theme_toggle_script()
        assert "function toggleTheme()" in js
        assert "function updateThemeIcon(theme)" in js
        assert "localStorage.setItem('theme'" in js
        assert "localStorage.getItem('theme')" in js

    def test_get_theme_toggle_script_default_theme(self):
        """Test default theme is dark"""
        js = get_theme_toggle_script()
        assert "|| 'dark'" in js


class TestGlossaryToggleScript:
    """Test glossary toggle JavaScript"""

    def test_get_glossary_toggle_script_function(self):
        """Test glossary toggle script contains function"""
        js = get_glossary_toggle_script()
        assert "function toggleGlossary()" in js
        assert "classList.toggle('expanded')" in js


class TestTableScrollScript:
    """Test table scroll detection JavaScript"""

    def test_get_table_scroll_script_selector(self):
        """Test table scroll script targets correct element"""
        js = get_table_scroll_script()
        assert "querySelectorAll('.table-wrapper')" in js
        assert "function checkScroll()" in js

    def test_get_table_scroll_script_events(self):
        """Test table scroll script event listeners"""
        js = get_table_scroll_script()
        assert "addEventListener('scroll'" in js
        assert "addEventListener('resize'" in js


class TestExpandableRowScript:
    """Test expandable row JavaScript"""

    def test_get_expandable_row_script_function(self):
        """Test expandable row script contains function"""
        js = get_expandable_row_script()
        assert "function toggleDetail(detailId, rowElement)" in js
        assert "classList.contains('show')" in js
        assert "classList.add('show')" in js
        assert "classList.remove('show')" in js


class TestDashboardJavascript:
    """Test dashboard JavaScript bundle"""

    def test_get_dashboard_javascript_default(self):
        """Test default JavaScript bundle"""
        js = get_dashboard_javascript()
        assert "<script>" in js
        assert "</script>" in js
        assert "function toggleTheme()" in js  # Always included

    def test_get_dashboard_javascript_all_features(self):
        """Test JavaScript bundle with all features"""
        js = get_dashboard_javascript(include_table_scroll=True, include_expandable_rows=True, include_glossary=True)
        assert "function toggleTheme()" in js
        assert "function toggleGlossary()" in js
        assert "querySelectorAll('.table-wrapper')" in js
        assert "function toggleDetail(" in js

    def test_get_dashboard_javascript_minimal(self):
        """Test minimal JavaScript bundle"""
        js = get_dashboard_javascript(include_table_scroll=False, include_expandable_rows=False, include_glossary=False)
        assert "function toggleTheme()" in js  # Always included
        assert "function toggleGlossary()" not in js
        assert "querySelectorAll('.table-wrapper')" not in js
        assert "function toggleDetail(" not in js


class TestJavascriptDocs:
    """Test JavaScript documentation"""

    def test_get_javascript_docs_structure(self):
        """Test JavaScript documentation structure"""
        docs = get_javascript_docs()
        assert "theme_toggle" in docs
        assert "glossary_toggle" in docs
        assert "table_scroll" in docs
        assert "expandable_rows" in docs

    def test_get_javascript_docs_values(self):
        """Test JavaScript documentation values"""
        docs = get_javascript_docs()
        theme_toggle = docs["theme_toggle"]
        assert "toggleTheme()" in theme_toggle["functions"]
        assert theme_toggle["default"] == "Dark mode"
