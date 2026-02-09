"""
Tests for execution.framework.components module
"""

import pytest

from execution.framework.components import get_layout_components, get_metric_components, get_theme_toggle_styles


class TestLayoutComponents:
    """Test layout component styles"""

    def test_get_layout_components_header(self):
        """Test header component styles"""
        css = get_layout_components()
        assert ".header {" in css
        assert "linear-gradient" in css
        assert "var(--header-gradient-start)" in css

    def test_get_layout_components_card(self):
        """Test card component styles"""
        css = get_layout_components()
        assert ".card {" in css
        assert "background: var(--bg-secondary)" in css
        assert "border-radius:" in css

    def test_get_layout_components_responsive(self):
        """Test responsive layout styles"""
        css = get_layout_components()
        assert "@media (min-width: 480px)" in css
        assert "@media (min-width: 768px)" in css
        assert "@media (min-width: 1024px)" in css


class TestMetricComponents:
    """Test metric component styles"""

    def test_get_metric_components_grid(self):
        """Test summary grid styles"""
        css = get_metric_components()
        assert ".summary-grid {" in css
        assert "display: grid;" in css
        assert "grid-template-columns: 1fr;" in css

    def test_get_metric_components_rag_colors(self):
        """Test RAG status colors"""
        css = get_metric_components()
        assert ".rag-green {" in css
        assert ".rag-amber {" in css
        assert ".rag-red {" in css
        assert "var(--color-rag-green)" in css

    def test_get_metric_components_responsive_grid(self):
        """Test responsive grid breakpoints"""
        css = get_metric_components()
        assert "repeat(2, 1fr)" in css  # phablet
        assert "repeat(3, 1fr)" in css  # tablet
        assert "repeat(auto-fit, minmax(200px, 1fr))" in css  # desktop


class TestThemeToggle:
    """Test theme toggle styles"""

    def test_get_theme_toggle_styles_button(self):
        """Test theme toggle button styles"""
        css = get_theme_toggle_styles()
        assert ".theme-toggle {" in css
        assert "position: fixed;" in css
        assert "min-width: 44px;" in css
        assert "min-height: 44px;" in css

    def test_get_theme_toggle_styles_touch_friendly(self):
        """Test touch-friendly interaction styles"""
        css = get_theme_toggle_styles()
        assert "@media (hover: hover) and (pointer: fine)" in css
        assert "@media (hover: none) and (pointer: coarse)" in css
        assert "-webkit-tap-highlight-color: transparent" in css
