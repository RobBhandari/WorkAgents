"""
Tests for execution.framework.responsive module
"""

import pytest

from execution.framework.responsive import get_accessibility_guidelines, get_responsive_breakpoints, get_utility_styles


class TestUtilityStyles:
    """Test utility styles"""

    def test_get_utility_styles_badges(self):
        """Test badge styles"""
        css = get_utility_styles()
        assert ".status-badge {" in css
        assert ".badge {" in css
        assert ".badge-success {" in css

    def test_get_utility_styles_rag_status(self):
        """Test RAG status utility classes"""
        css = get_utility_styles()
        assert ".status-good" in css
        assert ".status-caution" in css
        assert ".status-action" in css
        assert "var(--color-rag-green)" in css

    def test_get_utility_styles_accessibility(self):
        """Test accessibility features"""
        css = get_utility_styles()
        assert "*:focus-visible {" in css
        assert "outline: 3px solid" in css
        assert "@media (prefers-reduced-motion: reduce)" in css

    def test_get_utility_styles_print(self):
        """Test print styles"""
        css = get_utility_styles()
        assert "@media print {" in css
        assert "page-break-inside: avoid" in css

    def test_get_utility_styles_touch(self):
        """Test touch device optimizations"""
        css = get_utility_styles()
        assert "@media (hover: none) and (pointer: coarse)" in css
        assert "-webkit-tap-highlight-color" in css


class TestResponsiveBreakpoints:
    """Test responsive breakpoint documentation"""

    def test_get_responsive_breakpoints_structure(self):
        """Test breakpoint documentation structure"""
        docs = get_responsive_breakpoints()
        assert "breakpoints" in docs
        assert "mobile_first_strategy" in docs
        assert "touch_optimization" in docs

    def test_get_responsive_breakpoints_values(self):
        """Test breakpoint values"""
        docs = get_responsive_breakpoints()
        breakpoints = docs["breakpoints"]
        assert breakpoints["mobile"]["range"] == "320px - 479px"
        assert breakpoints["tablet"]["query"] == "@media (min-width: 768px)"


class TestAccessibilityGuidelines:
    """Test accessibility guidelines documentation"""

    def test_get_accessibility_guidelines_structure(self):
        """Test accessibility guidelines structure"""
        docs = get_accessibility_guidelines()
        assert "focus_indicators" in docs
        assert "reduced_motion" in docs
        assert "color_contrast" in docs
        assert "touch_targets" in docs
        assert "screen_reader_support" in docs

    def test_get_accessibility_guidelines_values(self):
        """Test accessibility guideline values"""
        docs = get_accessibility_guidelines()
        assert docs["touch_targets"]["minimum_size"] == "44x44px for all interactive elements"
        assert "4.5:1" in docs["color_contrast"]["text_primary"]
