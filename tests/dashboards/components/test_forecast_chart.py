"""
Tests for forecast_chart component

Tests the build_trend_chart and build_mini_trend_chart functions.
All tests use fixture data only — no file I/O or ADO API calls.
"""

import pytest

from execution.dashboards.components.forecast_chart import (
    build_mini_trend_chart,
    build_trend_chart,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_weekly_values() -> list[float]:
    """Typical weekly lead time values (in days) from history JSON."""
    return [266.8, 269.0, 271.5, 273.0, 273.7, 274.0, 273.3, 273.3]


@pytest.fixture
def sample_week_labels() -> list[str]:
    """Week label strings matching the fixture values."""
    return [
        "2026-02-04",
        "2026-02-06",
        "2026-02-08",
        "2026-02-10",
        "2026-02-12",
        "2026-02-14",
        "2026-02-18",
        "2026-02-22",
    ]


@pytest.fixture
def int_weekly_values() -> list[int]:
    """Integer values as they might come from JSON parsing."""
    return [100, 120, 115, 130, 125]


@pytest.fixture
def single_weekly_value() -> list[float]:
    """Single data point edge case."""
    return [273.3]


# ---------------------------------------------------------------------------
# build_trend_chart — happy path
# ---------------------------------------------------------------------------


class TestBuildTrendChart:
    """Tests for the full-size trend chart."""

    def test_returns_string(self, sample_weekly_values, sample_week_labels):
        """Return type must be str."""
        result = build_trend_chart(sample_weekly_values, sample_week_labels, "Avg Lead Time")
        assert isinstance(result, str)

    def test_contains_div(self, sample_weekly_values, sample_week_labels):
        """Output must contain an HTML div (Plotly embeds as a div)."""
        result = build_trend_chart(sample_weekly_values, sample_week_labels, "Avg Lead Time")
        assert "<div" in result

    def test_no_full_html_tags(self, sample_weekly_values, sample_week_labels):
        """full_html=False means no <html> or <body> tags."""
        result = build_trend_chart(sample_weekly_values, sample_week_labels, "Avg Lead Time")
        assert "<html>" not in result
        assert "<body>" not in result

    def test_no_plotlyjs_script(self, sample_weekly_values, sample_week_labels):
        """include_plotlyjs=False means no inline Plotly bundle is embedded.

        When include_plotlyjs=True, Plotly embeds the full JS bundle (100KB+)
        starting with 'define("plotly"'. With include_plotlyjs=False, the
        chart relies on the CDN version loaded in base_dashboard.html instead.
        """
        result = build_trend_chart(sample_weekly_values, sample_week_labels, "Avg Lead Time")
        # Full bundle would contain 'define("plotly"' or 'window.Plotly='
        # These are absent when relying on an externally loaded Plotly CDN.
        assert 'define("plotly"' not in result
        assert "window.Plotly=" not in result

    def test_div_id_contains_metric_name(self, sample_weekly_values, sample_week_labels):
        """div_id should be derived from metric_name."""
        result = build_trend_chart(sample_weekly_values, sample_week_labels, "Lead Time")
        assert "lead_time" in result

    def test_default_height_applied(self, sample_weekly_values, sample_week_labels):
        """Default height (250px) should appear in layout config."""
        result = build_trend_chart(sample_weekly_values, sample_week_labels, "Lead Time")
        assert "250" in result

    def test_custom_height_applied(self, sample_weekly_values, sample_week_labels):
        """Custom height should appear in layout config."""
        result = build_trend_chart(sample_weekly_values, sample_week_labels, "Lead Time", height=400)
        assert "400" in result

    def test_custom_color_applied(self, sample_weekly_values, sample_week_labels):
        """Custom line color should appear in the output."""
        result = build_trend_chart(sample_weekly_values, sample_week_labels, "Lead Time", color="#10b981")
        assert "#10b981" in result or "10b981" in result

    def test_dark_theme_background(self, sample_weekly_values, sample_week_labels):
        """Dark background colors should appear in layout."""
        result = build_trend_chart(sample_weekly_values, sample_week_labels, "Lead Time")
        # bg_card color for plot_bgcolor and paper_bgcolor
        assert "1e293b" in result

    # ---------------------------------------------------------------------------
    # Edge cases
    # ---------------------------------------------------------------------------

    def test_empty_values_returns_empty_string(self, sample_week_labels):
        """Empty weekly_values should return empty string (graceful degradation)."""
        result = build_trend_chart([], sample_week_labels, "Lead Time")
        assert result == ""

    def test_single_value_returns_div(self, single_weekly_value):
        """Single data point should still render a chart (not crash)."""
        result = build_trend_chart(single_weekly_value, ["2026-02-22"], "Lead Time")
        assert isinstance(result, str)
        assert "<div" in result

    def test_int_values_coerced_to_float(self, int_weekly_values, sample_week_labels):
        """Integer values from JSON should be handled without error."""
        labels = sample_week_labels[: len(int_weekly_values)]
        result = build_trend_chart(int_weekly_values, labels, "WIP Total")
        assert isinstance(result, str)
        assert "<div" in result

    def test_metric_name_with_spaces(self, sample_weekly_values, sample_week_labels):
        """Metric names with spaces should produce a valid div_id (spaces replaced)."""
        result = build_trend_chart(sample_weekly_values, sample_week_labels, "Avg Lead Time Days")
        # spaces become underscores in div_id
        assert "avg_lead_time_days" in result

    def test_metric_name_with_parentheses(self, sample_weekly_values, sample_week_labels):
        """Metric names with parentheses should produce a valid div_id."""
        result = build_trend_chart(sample_weekly_values, sample_week_labels, "Lead Time (P85)")
        assert "<div" in result
        # parentheses stripped in div_id
        assert "(" not in result.split('id="')[1].split('"')[0]


# ---------------------------------------------------------------------------
# build_mini_trend_chart
# ---------------------------------------------------------------------------


class TestBuildMiniTrendChart:
    """Tests for the compact mini trend chart."""

    def test_returns_string(self, sample_weekly_values, sample_week_labels):
        """Return type must be str."""
        result = build_mini_trend_chart(sample_weekly_values, sample_week_labels, "Lead Time")
        assert isinstance(result, str)

    def test_contains_div(self, sample_weekly_values, sample_week_labels):
        """Output must contain an HTML div."""
        result = build_mini_trend_chart(sample_weekly_values, sample_week_labels, "Lead Time")
        assert "<div" in result

    def test_default_height_120(self, sample_weekly_values, sample_week_labels):
        """Default mini height should be 120px."""
        result = build_mini_trend_chart(sample_weekly_values, sample_week_labels, "Lead Time")
        assert "120" in result

    def test_custom_height_applied(self, sample_weekly_values, sample_week_labels):
        """Custom height should be applied."""
        result = build_mini_trend_chart(sample_weekly_values, sample_week_labels, "Lead Time", height=80)
        assert "80" in result

    def test_mini_chart_smaller_than_full(self, sample_weekly_values, sample_week_labels):
        """Mini chart default height (120) is smaller than full chart default (250)."""
        full_result = build_trend_chart(sample_weekly_values, sample_week_labels, "Lead Time")
        mini_result = build_mini_trend_chart(sample_weekly_values, sample_week_labels, "Lead Time")
        # Both must be non-empty valid divs
        assert "<div" in full_result
        assert "<div" in mini_result
        # Mini uses height=120; full uses height=250
        assert "250" in full_result
        assert "120" in mini_result

    def test_empty_values_returns_empty_string(self, sample_week_labels):
        """Empty values should return empty string."""
        result = build_mini_trend_chart([], sample_week_labels, "Lead Time")
        assert result == ""

    def test_int_values_handled(self, int_weekly_values, sample_week_labels):
        """Integer values should be coerced to float without error."""
        labels = sample_week_labels[: len(int_weekly_values)]
        result = build_mini_trend_chart(int_weekly_values, labels, "WIP")
        assert isinstance(result, str)
        assert "<div" in result

    def test_mini_div_id_prefixed(self, sample_weekly_values, sample_week_labels):
        """Mini chart div_id should be prefixed with 'mini_chart_'."""
        result = build_mini_trend_chart(sample_weekly_values, sample_week_labels, "Lead Time")
        assert "mini_chart_lead_time" in result

    def test_single_value_handled(self, single_weekly_value):
        """Single data point should not crash."""
        result = build_mini_trend_chart(single_weekly_value, ["2026-02-22"], "WIP")
        assert isinstance(result, str)
        assert "<div" in result
