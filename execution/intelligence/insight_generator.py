"""
Insight Generator — execution/intelligence/insight_generator.py

Generates text insights from metric data.
Phase C: Template-based only.  LLM integration is a stub (returns "" until
API key is set and full implementation lands in a future phase).

Security:
- All metric values coerced to float before string interpolation (prompt
  injection prevention — numeric coercion eliminates embedded commands).
- ANTHROPIC_API_KEY read from environment only (never hardcoded).
- Template strings use str.format_map() with a safe dict (no eval/exec).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from execution.core.logging_config import get_logger
from execution.domain.intelligence import MetricInsight

logger: logging.Logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

INSIGHT_TEMPLATES: dict[str, str] = {
    "anomaly_spike": (
        "⚠️ {metric} spiked {delta_pct:.1f}% this week. " "Primary driver: {top_dimension} ({dim_delta:+.1f}%)."
    ),
    "trend_reversal": (
        "🔄 {metric} trend reversed this week. " "Previously {prior_direction} for {prior_weeks} weeks."
    ),
    "target_risk": ("🎯 At current pace, {metric} target will be missed by " "approximately {miss_amount:.0f} units."),
    "opportunity": ("💡 {product} showing {improvement:.1f}% improvement — " "fastest mover this period."),
    "stable": "✅ {metric} is stable with no significant change this week.",
}

# Fallback text when template formatting fails
_FALLBACK_TEXT = "No insight available for {metric}."


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _coerce_numeric_context(context: dict[str, object]) -> dict[str, object]:
    """
    Return a copy of `context` with all numeric-looking values coerced to float.

    String values that parse as floats are converted; non-numeric strings are
    left as-is (they are safe for .format_map() without eval/exec).

    Security rationale: coercing numbers prevents prompt-injection through
    format-string manipulation (e.g. injecting format specifiers via a value
    that is later embedded in a template).
    """
    safe: dict[str, object] = {}
    for key, val in context.items():
        if isinstance(val, (int, float)):
            safe[key] = float(val)
        elif isinstance(val, str):
            # Attempt numeric coercion; keep as string if it fails
            try:
                safe[key] = float(val)
            except ValueError:
                safe[key] = val
        else:
            safe[key] = val
    return safe


def _format_template(template: str, context: dict[str, object], metric: str) -> str:
    """
    Apply context to a template string using str.format_map().

    Returns a fallback message if the formatting raises KeyError or ValueError
    (e.g. a required placeholder is missing from context).

    Security: uses str.format_map() — no eval/exec.
    """
    try:
        return template.format_map(context)
    except (KeyError, ValueError) as exc:
        logger.warning(
            "Template formatting failed — using fallback",
            extra={"metric": metric, "error": str(exc)},
        )
        return _FALLBACK_TEXT.format(metric=metric)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_template_insight(
    template_key: str,
    context: dict[str, object],
    metric: str,
    severity: str = "info",
) -> MetricInsight:
    """
    Generate a template-based MetricInsight.

    Validates `template_key` against INSIGHT_TEMPLATES.  Unknown keys produce a
    graceful fallback rather than raising an exception, so callers remain
    resilient against stale template references.

    Args:
        template_key: Key into INSIGHT_TEMPLATES (e.g. "anomaly_spike").
        context:      Dict of substitution values for the template placeholders.
        metric:       Metric name included in the resulting MetricInsight.
        severity:     "info" | "warning" | "critical" (default "info").

    Returns:
        MetricInsight with source="template".

    Security:
        All numeric values in `context` are coerced to float before
        str.format_map() is called (prompt injection prevention).
    """
    safe_context = _coerce_numeric_context(context)

    if template_key not in INSIGHT_TEMPLATES:
        logger.warning(
            "Unknown template_key — using fallback",
            extra={"template_key": template_key, "metric": metric},
        )
        text = _FALLBACK_TEXT.format(metric=metric)
    else:
        template = INSIGHT_TEMPLATES[template_key]
        text = _format_template(template, safe_context, metric)

    return MetricInsight(
        timestamp=datetime.now(),
        metric=metric,
        template_key=template_key,
        text=text,
        severity=severity,
        source="template",
    )


def generate_llm_insight(
    template_key: str,
    context: dict[str, object],
    metric: str,
) -> MetricInsight:
    """
    Generate a MetricInsight using the Claude Haiku API.

    Requires ANTHROPIC_API_KEY in the environment.  If the key is not set
    or the API call fails, returns an empty MetricInsight (caller's
    generate_insight() will fall back to the template path automatically).

    Security:
        - All numeric context values are coerced via _coerce_numeric_context()
          before string interpolation (prevents prompt injection).
        - System prompt and user prompt are always separate (never concatenated).
        - ANTHROPIC_API_KEY is read from environment only — never hardcoded.
        - Any exception from the API is caught and logged; empty text is returned.

    Args:
        template_key: Identifier for the insight type (e.g. "anomaly_spike").
        context:      Substitution values for context building.
        metric:       Metric name for the resulting MetricInsight.

    Returns:
        MetricInsight with non-empty text (source="llm") if API succeeds,
        or MetricInsight with text="" if key absent or API fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.debug(
            "ANTHROPIC_API_KEY not set — skipping LLM call",
            extra={"metric": metric, "template_key": template_key},
        )
        return MetricInsight(
            timestamp=datetime.now(),
            metric=metric,
            template_key=template_key,
            text="",
            source="llm",
        )

    # Coerce all numeric values before building the user prompt (SC-3: prompt injection prevention)
    safe_context = _coerce_numeric_context(context)
    context_lines = []
    for key, val in safe_context.items():
        if isinstance(val, float):
            context_lines.append(f"- {key}: {val:.2f}")
        else:
            context_lines.append(f"- {key}: {val}")
    context_str = "\n".join(context_lines) if context_lines else "No additional context."

    # System prompt and user prompt are always separate (never concatenated)
    system_prompt = "You are an engineering intelligence analyst. " "Write direct, specific, and actionable insights."
    user_prompt = (
        f"Metric: {metric}\n"
        f"Insight type: {template_key}\n"
        f"Context:\n{context_str}\n\n"
        "Write a 2-sentence executive insight. No hedging. "
        "End with one specific recommended action."
    )

    try:
        from anthropic import Anthropic  # lazy import — only needed when API key present

        client = Anthropic()
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = message.content[0].text.strip() if message.content else ""
    except Exception as exc:
        logger.warning(
            "LLM insight generation failed — returning empty text",
            extra={"metric": metric, "template_key": template_key, "error": str(exc)},
        )
        text = ""

    return MetricInsight(
        timestamp=datetime.now(),
        metric=metric,
        template_key=template_key,
        text=text,
        source="llm",
    )


def generate_insight(
    template_key: str,
    context: dict[str, object],
    metric: str,
    severity: str = "info",
    use_llm: bool = False,
) -> MetricInsight:
    """
    Generate a MetricInsight, choosing template vs LLM based on `use_llm`.

    If use_llm=True but the LLM stub returns empty text, falls back
    automatically to the template implementation.

    Args:
        template_key: Key into INSIGHT_TEMPLATES.
        context:      Substitution values for the template placeholders.
        metric:       Metric name for the resulting insight.
        severity:     "info" | "warning" | "critical" (default "info").
        use_llm:      If True, attempt LLM generation first (default False).

    Returns:
        MetricInsight from either the LLM (if non-empty) or the template.
    """
    if use_llm:
        llm_result = generate_llm_insight(template_key, context, metric)
        if llm_result.text:
            return llm_result
        logger.info(
            "LLM returned empty text — falling back to template",
            extra={"metric": metric, "template_key": template_key},
        )

    return generate_template_insight(template_key, context, metric, severity=severity)
