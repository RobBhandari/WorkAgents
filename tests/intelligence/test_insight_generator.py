"""
Tests for execution/intelligence/insight_generator.py

Covers template generation, LLM stub, fallback logic, and MetricInsight model.
All tests use synthetic data — no network calls, no file I/O.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from execution.domain.intelligence import MetricInsight
from execution.intelligence.insight_generator import (
    INSIGHT_TEMPLATES,
    generate_insight,
    generate_llm_insight,
    generate_template_insight,
)

_TS = datetime(2025, 10, 6)

# ---------------------------------------------------------------------------
# generate_template_insight tests
# ---------------------------------------------------------------------------


def test_generate_template_insight_valid_key_returns_text() -> None:
    """A known template_key with matching context should produce non-empty text."""
    context = {
        "metric": "open_bugs",
        "delta_pct": 15.3,
        "top_dimension": "Product_A",
        "dim_delta": 12.5,
    }
    insight = generate_template_insight("anomaly_spike", context, "open_bugs")
    assert isinstance(insight, MetricInsight)
    assert insight.source == "template"
    assert insight.metric == "open_bugs"
    assert insight.template_key == "anomaly_spike"
    assert len(insight.text) > 0
    # Numeric values must appear in the rendered text
    assert "15.3" in insight.text
    assert "Product_A" in insight.text


def test_generate_template_insight_all_templates_render() -> None:
    """Every template in INSIGHT_TEMPLATES should render without error with full context."""
    full_context: dict[str, object] = {
        "metric": "open_bugs",
        "delta_pct": 10.0,
        "top_dimension": "Product_A",
        "dim_delta": 5.0,
        "prior_direction": "improving",
        "prior_weeks": 4,
        "miss_amount": 50.0,
        "product": "Product_A",
        "improvement": 8.5,
    }
    for key in INSIGHT_TEMPLATES:
        insight = generate_template_insight(key, full_context, "open_bugs")
        assert isinstance(insight.text, str)
        assert len(insight.text) > 0


def test_generate_template_insight_unknown_key_falls_back_gracefully() -> None:
    """An unknown template_key should NOT raise — it should return a fallback message."""
    insight = generate_template_insight("not_a_real_key", {}, "open_bugs")
    assert isinstance(insight, MetricInsight)
    assert insight.template_key == "not_a_real_key"
    assert "open_bugs" in insight.text


def test_generate_template_insight_missing_placeholder_falls_back() -> None:
    """Missing context keys that cause KeyError should fall back gracefully."""
    # anomaly_spike requires delta_pct, top_dimension, dim_delta — provide none
    insight = generate_template_insight("anomaly_spike", {}, "open_bugs")
    assert isinstance(insight, MetricInsight)
    assert insight.source == "template"
    # Should contain the metric name in fallback message
    assert "open_bugs" in insight.text


def test_generate_template_insight_severity_preserved() -> None:
    """The severity parameter must be reflected in the returned MetricInsight."""
    insight = generate_template_insight(
        "stable",
        {"metric": "open_bugs"},
        "open_bugs",
        severity="warning",
    )
    assert insight.severity == "warning"


def test_generate_template_insight_coerces_numeric_strings() -> None:
    """
    Context values that are numeric strings should be coerced to float
    so that format specs like {delta_pct:.1f} work correctly.
    """
    context: dict[str, object] = {
        "metric": "open_bugs",
        "delta_pct": "15.3",  # string — should be coerced
        "top_dimension": "Product_A",
        "dim_delta": "12",  # string — should be coerced
    }
    insight = generate_template_insight("anomaly_spike", context, "open_bugs")
    # The text should contain the formatted float values
    assert "15.3" in insight.text


# ---------------------------------------------------------------------------
# generate_llm_insight tests
# ---------------------------------------------------------------------------


def test_generate_llm_insight_returns_empty_when_no_api_key() -> None:
    """Without ANTHROPIC_API_KEY, generate_llm_insight returns text=''."""
    with patch.dict("os.environ", {}, clear=True):
        # Ensure ANTHROPIC_API_KEY is absent
        import os

        os.environ.pop("ANTHROPIC_API_KEY", None)
        insight = generate_llm_insight("anomaly_spike", {}, "open_bugs")
    assert isinstance(insight, MetricInsight)
    assert insight.text == ""
    assert insight.source == "llm"
    assert insight.metric == "open_bugs"
    assert insight.template_key == "anomaly_spike"


def test_generate_llm_insight_calls_api_when_key_present() -> None:
    """When ANTHROPIC_API_KEY is set, calls Anthropic and returns non-empty text."""
    mock_text_block = MagicMock()
    mock_text_block.text = "Two-sentence insight here. Recommended action: fix it."
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [mock_text_block]

    mock_anthropic_module = MagicMock()
    mock_anthropic_module.Anthropic.return_value = mock_client

    import sys

    with patch.dict("sys.modules", {"anthropic": mock_anthropic_module}):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            insight = generate_llm_insight(
                "anomaly_spike",
                {"delta_pct": 15.3, "top_dimension": "Product_A"},
                "open_bugs",
            )

    assert isinstance(insight, MetricInsight)
    assert insight.text == "Two-sentence insight here. Recommended action: fix it."
    assert insight.source == "llm"


def test_generate_llm_insight_returns_empty_on_api_error() -> None:
    """If the Anthropic API raises, generate_llm_insight returns text='' (no raise)."""
    mock_anthropic_module = MagicMock()
    mock_anthropic_module.Anthropic.side_effect = RuntimeError("API unavailable")

    import sys

    with patch.dict("sys.modules", {"anthropic": mock_anthropic_module}):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            insight = generate_llm_insight("stable", {}, "vulnerabilities")

    assert isinstance(insight, MetricInsight)
    assert insight.text == ""
    assert insight.source == "llm"


def test_generate_llm_insight_does_not_raise_for_unknown_key() -> None:
    """Should never raise regardless of template_key when API key is absent."""
    with patch.dict("os.environ", {}, clear=True):
        import os

        os.environ.pop("ANTHROPIC_API_KEY", None)
        insight = generate_llm_insight("unknown_key", {"x": 123}, "some_metric")
    assert isinstance(insight, MetricInsight)


# ---------------------------------------------------------------------------
# generate_insight routing tests
# ---------------------------------------------------------------------------


def test_generate_insight_uses_template_by_default() -> None:
    """With use_llm=False (default), should always use template path."""
    context: dict[str, object] = {"metric": "open_bugs"}
    insight = generate_insight("stable", context, "open_bugs", use_llm=False)
    assert insight.source == "template"
    assert len(insight.text) > 0


def test_generate_insight_falls_back_to_template_when_llm_empty() -> None:
    """
    When use_llm=True but LLM stub returns text="", the function must
    fall back to the template implementation.
    """
    context: dict[str, object] = {"metric": "open_bugs"}
    insight = generate_insight("stable", context, "open_bugs", use_llm=True)
    # Should fall back to template because LLM stub returns ""
    assert insight.source == "template"
    assert len(insight.text) > 0


def test_generate_insight_severity_propagated_to_template() -> None:
    """Severity must be propagated through to the template-generated insight."""
    insight = generate_insight(
        "stable",
        {"metric": "open_bugs"},
        "open_bugs",
        severity="critical",
        use_llm=False,
    )
    assert insight.severity == "critical"


# ---------------------------------------------------------------------------
# MetricInsight model tests
# ---------------------------------------------------------------------------


def test_metric_insight_severity_emoji_info() -> None:
    """'info' severity should return the lightbulb emoji."""
    insight = MetricInsight(timestamp=_TS, metric="m", template_key="k", text="t", severity="info")
    assert insight.severity_emoji == "💡"


def test_metric_insight_severity_emoji_warning() -> None:
    """'warning' severity should return the warning emoji."""
    insight = MetricInsight(timestamp=_TS, metric="m", template_key="k", text="t", severity="warning")
    assert insight.severity_emoji == "⚠️"


def test_metric_insight_severity_emoji_critical() -> None:
    """'critical' severity should return the red circle emoji."""
    insight = MetricInsight(timestamp=_TS, metric="m", template_key="k", text="t", severity="critical")
    assert insight.severity_emoji == "🔴"


def test_metric_insight_severity_emoji_unknown() -> None:
    """Unknown severity values should fall back to the lightbulb emoji."""
    insight = MetricInsight(timestamp=_TS, metric="m", template_key="k", text="t", severity="unknown_level")
    assert insight.severity_emoji == "💡"


def test_metric_insight_from_dict_roundtrip() -> None:
    """from_dict should reconstruct all fields faithfully."""
    data = {
        "metric": "open_bugs",
        "template_key": "anomaly_spike",
        "text": "Some insight text",
        "severity": "warning",
        "source": "template",
    }
    insight = MetricInsight.from_dict(data)
    assert insight.metric == "open_bugs"
    assert insight.template_key == "anomaly_spike"
    assert insight.text == "Some insight text"
    assert insight.severity == "warning"
    assert insight.source == "template"


def test_metric_insight_from_dict_defaults() -> None:
    """from_dict should apply defaults for optional keys."""
    data = {
        "metric": "vulnerabilities",
        "template_key": "stable",
        "text": "Stable.",
    }
    insight = MetricInsight.from_dict(data)
    assert insight.severity == "info"
    assert insight.source == "template"
