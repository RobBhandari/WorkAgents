"""
Tests for execution.framework.base_styles module
"""

import pytest

from execution.framework.base_styles import get_base_styles, get_reset_docs


class TestBaseStyles:
    """Test base styles generation"""

    def test_get_base_styles_contains_reset(self):
        """Test that CSS reset is included"""
        css = get_base_styles()
        assert "margin: 0;" in css
        assert "padding: 0;" in css
        assert "box-sizing: border-box;" in css

    def test_get_base_styles_contains_typography(self):
        """Test that typography scale is included"""
        css = get_base_styles()
        assert "h1 {" in css
        assert "h2 {" in css
        assert "h3 {" in css
        assert "font-size: 1.5rem" in css  # h1 mobile

    def test_get_base_styles_responsive_breakpoints(self):
        """Test that responsive breakpoints are included"""
        css = get_base_styles()
        assert "@media (min-width: 480px)" in css
        assert "@media (min-width: 768px)" in css
        assert "@media (min-width: 1024px)" in css

    def test_get_base_styles_contains_body(self):
        """Test that body styles are included"""
        css = get_base_styles()
        assert "body {" in css
        assert "font-family:" in css
        assert "background: var(--bg-primary)" in css

    def test_reset_docs_structure(self):
        """Test reset documentation structure"""
        docs = get_reset_docs()
        assert "reset" in docs
        assert "mobile_first" in docs
        assert "breakpoints" in docs
        assert "typography_scale" in docs
        assert docs["breakpoints"]["mobile"] == "320px - 479px (default)"
