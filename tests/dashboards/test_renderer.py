"""
Tests for Template Rendering Utilities

Comprehensive tests for renderer.py to ensure critical infrastructure
used by all 12 dashboards is properly validated.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from execution.dashboards.renderer import (
    format_date,
    format_number,
    format_percent,
    get_jinja_environment,
    render_dashboard,
    trend_arrow,
)


class TestFormatNumber:
    """Tests for format_number() filter"""

    def test_thousands_separator(self):
        """Test thousands separator formatting"""
        assert format_number(1234567) == "1,234,567"
        assert format_number(1000) == "1,000"
        assert format_number(999) == "999"

    def test_decimals_zero(self):
        """Test integer formatting (default decimals=0)"""
        assert format_number(1234.56) == "1,234"  # Converts to int (truncates)
        assert format_number(1234.9) == "1,234"
        assert format_number(1234.1) == "1,234"

    def test_decimals_custom(self):
        """Test custom decimal places"""
        assert format_number(1234.56, decimals=2) == "1,234.56"
        assert format_number(1234.5, decimals=2) == "1,234.50"
        assert format_number(1234.567, decimals=1) == "1,234.6"

    def test_negative_numbers(self):
        """Test negative number formatting"""
        assert format_number(-1234567) == "-1,234,567"
        assert format_number(-1234.56, decimals=2) == "-1,234.56"

    def test_zero(self):
        """Test zero formatting"""
        assert format_number(0) == "0"
        assert format_number(0.0, decimals=2) == "0.00"

    def test_invalid_input_string(self):
        """Test invalid string input returns string"""
        assert format_number("not a number") == "not a number"
        assert format_number("abc123") == "abc123"

    def test_invalid_input_none(self):
        """Test None input returns string"""
        assert format_number(None) == "None"

    def test_string_numeric_input(self):
        """Test string numeric input gets converted"""
        assert format_number("1234.56") == "1,234"  # Converts to int (truncates)
        assert format_number("1234.56", decimals=2) == "1,234.56"


class TestFormatPercent:
    """Tests for format_percent() filter"""

    def test_default_decimals(self):
        """Test default single decimal place"""
        assert format_percent(65.432) == "65.4%"
        assert format_percent(100.0) == "100.0%"
        assert format_percent(0.0) == "0.0%"

    def test_custom_decimals(self):
        """Test custom decimal places"""
        assert format_percent(65.432, decimals=2) == "65.43%"
        assert format_percent(65.432, decimals=0) == "65%"
        assert format_percent(65.999, decimals=0) == "66%"

    def test_negative_percentage(self):
        """Test negative percentage formatting"""
        assert format_percent(-5.5) == "-5.5%"
        assert format_percent(-10.123, decimals=2) == "-10.12%"

    def test_invalid_input(self):
        """Test invalid input returns string"""
        assert format_percent("not a number") == "not a number"
        assert format_percent(None) == "None"

    def test_string_numeric_input(self):
        """Test string numeric input gets converted"""
        assert format_percent("65.432") == "65.4%"
        assert format_percent("100", decimals=0) == "100%"


class TestFormatDate:
    """Tests for format_date() filter"""

    def test_datetime_object_default_format(self):
        """Test datetime object with default format"""
        dt = datetime(2026, 2, 7, 14, 30, 45)
        assert format_date(dt) == "2026-02-07"

    def test_datetime_object_custom_format(self):
        """Test datetime object with custom format"""
        dt = datetime(2026, 2, 7, 14, 30, 45)
        assert format_date(dt, "%B %d, %Y") == "February 07, 2026"
        assert format_date(dt, "%Y-%m-%d %H:%M:%S") == "2026-02-07 14:30:45"
        assert format_date(dt, "%d/%m/%Y") == "07/02/2026"

    def test_iso_string_input(self):
        """Test ISO format string input"""
        iso_str = "2026-02-07T14:30:45"
        assert format_date(iso_str) == "2026-02-07"

    def test_iso_string_custom_format(self):
        """Test ISO string with custom format"""
        iso_str = "2026-02-07T14:30:45"
        assert format_date(iso_str, "%B %d, %Y") == "February 07, 2026"

    def test_invalid_date_string(self):
        """Test invalid date string returns original string"""
        invalid = "not a date"
        assert format_date(invalid) == "not a date"

    def test_invalid_input_none(self):
        """Test None input returns string"""
        assert format_date(None) == "None"

    def test_invalid_input_number(self):
        """Test numeric input returns string"""
        assert format_date(12345) == "12345"


class TestTrendArrow:
    """Tests for trend_arrow() filter"""

    def test_positive_value(self):
        """Test positive values return up arrow"""
        assert trend_arrow(10) == "↑"
        assert trend_arrow(0.1) == "↑"
        assert trend_arrow(999999) == "↑"

    def test_negative_value(self):
        """Test negative values return down arrow"""
        assert trend_arrow(-5) == "↓"
        assert trend_arrow(-0.01) == "↓"
        assert trend_arrow(-999999) == "↓"

    def test_zero_value(self):
        """Test zero returns right arrow"""
        assert trend_arrow(0) == "→"
        assert trend_arrow(0.0) == "→"


class TestGetJinjaEnvironment:
    """Tests for get_jinja_environment()"""

    def test_returns_environment(self):
        """Test returns configured Jinja2 Environment"""
        from jinja2 import Environment

        env = get_jinja_environment()
        assert isinstance(env, Environment)

    def test_singleton_pattern(self):
        """Test same environment instance is returned"""
        env1 = get_jinja_environment()
        env2 = get_jinja_environment()
        assert env1 is env2

    def test_custom_filters_registered(self):
        """Test custom filters are registered"""
        env = get_jinja_environment()
        assert "format_number" in env.filters
        assert "format_percent" in env.filters
        assert "format_date" in env.filters
        assert "trend_arrow" in env.filters

    def test_autoescape_enabled(self):
        """Test auto-escaping is enabled for HTML"""
        env = get_jinja_environment()
        # autoescape is a function, not a boolean
        assert callable(env.autoescape)

    def test_trim_blocks_enabled(self):
        """Test trim_blocks is enabled"""
        env = get_jinja_environment()
        assert env.trim_blocks is True

    def test_lstrip_blocks_enabled(self):
        """Test lstrip_blocks is enabled"""
        env = get_jinja_environment()
        assert env.lstrip_blocks is True


class TestRenderDashboard:
    """Tests for render_dashboard()"""

    @pytest.fixture
    def mock_template(self):
        """Create mock template"""
        template = MagicMock()
        template.render.return_value = "<html>Test Dashboard</html>"
        return template

    @pytest.fixture
    def mock_env(self, mock_template):
        """Create mock Jinja2 environment"""
        env = MagicMock()
        env.get_template.return_value = mock_template
        return env

    def test_injects_default_variables(self, mock_env, mock_template):
        """Test default variables are injected"""
        with patch("execution.dashboards.renderer.get_jinja_environment", return_value=mock_env):
            render_dashboard("test.html", {"custom": "value"})

            # Check render was called
            assert mock_template.render.called
            call_kwargs = mock_template.render.call_args[1]

            # Check default variables exist
            assert "generation_date" in call_kwargs
            assert "show_glossary" in call_kwargs
            assert call_kwargs["show_glossary"] is True

            # Check custom variable exists
            assert "custom" in call_kwargs
            assert call_kwargs["custom"] == "value"

    def test_user_context_takes_precedence(self, mock_env, mock_template):
        """Test user context overrides defaults"""
        with patch("execution.dashboards.renderer.get_jinja_environment", return_value=mock_env):
            render_dashboard("test.html", {"show_glossary": False})

            call_kwargs = mock_template.render.call_args[1]
            assert call_kwargs["show_glossary"] is False

    def test_inject_defaults_false(self, mock_env, mock_template):
        """Test disabling default injection"""
        with patch("execution.dashboards.renderer.get_jinja_environment", return_value=mock_env):
            render_dashboard("test.html", {"custom": "value"}, inject_defaults=False)

            call_kwargs = mock_template.render.call_args[1]

            # Defaults should NOT be present
            assert "generation_date" not in call_kwargs
            assert "show_glossary" not in call_kwargs

            # Custom variable should still be present
            assert "custom" in call_kwargs
            assert call_kwargs["custom"] == "value"

    def test_returns_rendered_html(self, mock_env, mock_template):
        """Test returns rendered HTML string"""
        with patch("execution.dashboards.renderer.get_jinja_environment", return_value=mock_env):
            result = render_dashboard("test.html", {})
            assert result == "<html>Test Dashboard</html>"

    def test_generation_date_format(self, mock_env, mock_template):
        """Test generation_date has correct format"""
        with patch("execution.dashboards.renderer.get_jinja_environment", return_value=mock_env):
            render_dashboard("test.html", {})

            call_kwargs = mock_template.render.call_args[1]
            gen_date = call_kwargs["generation_date"]

            # Should match YYYY-MM-DD HH:MM:SS format
            assert len(gen_date) == 19
            assert gen_date[4] == "-"
            assert gen_date[7] == "-"
            assert gen_date[10] == " "
            assert gen_date[13] == ":"
            assert gen_date[16] == ":"


class TestXSSProtection:
    """Tests for XSS protection via auto-escaping"""

    def test_autoescape_script_tags(self):
        """Test script tags are escaped in templates"""
        # Create a minimal test template
        template_dir = Path(__file__).parent.parent.parent / "templates"
        test_template_dir = template_dir / "test"
        test_template_dir.mkdir(exist_ok=True)

        test_template = test_template_dir / "xss_test.html"
        test_template.write_text("{{ malicious_input }}")

        try:
            # Render with malicious input
            html = render_dashboard(
                "test/xss_test.html",
                {"malicious_input": "<script>alert('XSS')</script>"},
                inject_defaults=False,
            )

            # Should be escaped
            assert "&lt;script&gt;" in html
            assert "<script>" not in html
        finally:
            # Cleanup
            test_template.unlink()
            test_template_dir.rmdir()

    def test_autoescape_html_attributes(self):
        """Test HTML attributes are escaped"""
        template_dir = Path(__file__).parent.parent.parent / "templates"
        test_template_dir = template_dir / "test"
        test_template_dir.mkdir(exist_ok=True)

        test_template = test_template_dir / "attr_test.html"
        test_template.write_text('<div title="{{ title }}"></div>')

        try:
            html = render_dashboard(
                "test/attr_test.html",
                {"title": '"><script>alert("XSS")</script><div "'},
                inject_defaults=False,
            )

            # Should be escaped - check for escaped script tag
            assert "&lt;script&gt;" in html
            assert '"><script>' not in html
        finally:
            # Cleanup
            test_template.unlink()
            test_template_dir.rmdir()


class TestFiltersInTemplates:
    """Integration tests for filters used in templates"""

    def test_format_number_filter_in_template(self):
        """Test format_number filter works in template"""
        template_dir = Path(__file__).parent.parent.parent / "templates"
        test_template_dir = template_dir / "test"
        test_template_dir.mkdir(exist_ok=True)

        test_template = test_template_dir / "format_number_filter_test.html"
        test_template.write_text("{{ value|format_number }}")

        try:
            html = render_dashboard("test/format_number_filter_test.html", {"value": 1234567}, inject_defaults=False)
            assert "1,234,567" in html
        finally:
            test_template.unlink()
            if not any(test_template_dir.iterdir()):
                test_template_dir.rmdir()

    def test_format_percent_filter_in_template(self):
        """Test format_percent filter works in template"""
        template_dir = Path(__file__).parent.parent.parent / "templates"
        test_template_dir = template_dir / "test"
        test_template_dir.mkdir(exist_ok=True)

        test_template = test_template_dir / "format_percent_filter_test.html"
        test_template.write_text("{{ value|format_percent(2) }}")

        try:
            html = render_dashboard("test/format_percent_filter_test.html", {"value": 65.432}, inject_defaults=False)
            assert "65.43%" in html
        finally:
            test_template.unlink()
            if not any(test_template_dir.iterdir()):
                test_template_dir.rmdir()

    def test_trend_arrow_filter_in_template(self):
        """Test trend_arrow filter works in template"""
        template_dir = Path(__file__).parent.parent.parent / "templates"
        test_template_dir = template_dir / "test"
        test_template_dir.mkdir(exist_ok=True)

        test_template = test_template_dir / "trend_arrow_filter_test.html"
        test_template.write_text("{{ value|trend_arrow }}")

        try:
            html = render_dashboard("test/trend_arrow_filter_test.html", {"value": -5}, inject_defaults=False)
            assert "↓" in html
        finally:
            test_template.unlink()
            if not any(test_template_dir.iterdir()):
                test_template_dir.rmdir()
