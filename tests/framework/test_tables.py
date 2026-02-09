"""
Tests for execution.framework.tables module
"""

import pytest

from execution.framework.tables import get_collapsible_styles, get_table_styles


class TestTableStyles:
    """Test table styles"""

    def test_get_table_styles_wrapper(self):
        """Test table wrapper styles"""
        css = get_table_styles()
        assert ".table-wrapper {" in css
        assert "overflow-x: auto;" in css
        assert "-webkit-overflow-scrolling: touch;" in css

    def test_get_table_styles_scrollbar(self):
        """Test custom scrollbar styles"""
        css = get_table_styles()
        assert ".table-wrapper::-webkit-scrollbar" in css
        assert ".table-wrapper::-webkit-scrollbar-track" in css
        assert ".table-wrapper::-webkit-scrollbar-thumb" in css

    def test_get_table_styles_fade_gradient(self):
        """Test fade gradient indicator"""
        css = get_table_styles()
        assert ".table-wrapper::after {" in css
        assert "linear-gradient(to left" in css
        assert ".table-wrapper:not(.scrolled-end)::after" in css

    def test_get_table_styles_responsive(self):
        """Test responsive table styles"""
        css = get_table_styles()
        assert "min-width: 600px;" in css  # Force scroll on mobile
        assert "@media (min-width: 768px)" in css

    def test_get_table_styles_touch_interaction(self):
        """Test touch-friendly row interactions"""
        css = get_table_styles()
        assert "@media (hover: hover) and (pointer: fine)" in css
        assert "tbody tr:hover" in css
        assert "@media (hover: none) and (pointer: coarse)" in css
        assert "tbody tr:active" in css


class TestCollapsibleStyles:
    """Test collapsible component styles"""

    def test_get_collapsible_styles_glossary(self):
        """Test glossary collapsible section"""
        css = get_collapsible_styles()
        assert ".glossary {" in css
        assert ".glossary-header {" in css
        assert ".glossary-content {" in css
        assert "max-height: 0;" in css

    def test_get_collapsible_styles_expandable_rows(self):
        """Test expandable table row styles"""
        css = get_collapsible_styles()
        assert "tbody tr.data-row" in css
        assert "tr.detail-row" in css
        assert ".detail-content {" in css

    def test_get_collapsible_styles_animations(self):
        """Test animation styles"""
        css = get_collapsible_styles()
        assert "@keyframes slideDown" in css
        assert "transition:" in css
        assert "transform: rotate(90deg)" in css
