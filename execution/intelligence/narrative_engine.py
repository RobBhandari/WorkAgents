"""
Narrative Engine — execution/intelligence/narrative_engine.py

Generates a Weekly Strategic Intelligence Report by assembling
MetricInsight objects from insight_generator.py and rendering them
as an executive HTML summary.

Falls back to template-based insights when ANTHROPIC_API_KEY is absent.

Security:
- All metric names validated against VALID_METRICS before any prompt
  interpolation.
- Numeric context values coerced via local _coerce_context() helper
  (mirrors insight_generator._coerce_numeric_context — not imported as
  a private symbol).
- LLM output is never marked safe in templates; inserted as auto-escaped
  Jinja2 variables only.
- ANTHROPIC_API_KEY is read from environment only — never logged.
- All history file paths built from internal constants only.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from execution.core.logging_config import get_logger
from execution.dashboards.renderer import render_dashboard
from execution.domain.intelligence import MetricInsight
from execution.intelligence.feature_engineering import VALID_METRICS
from execution.intelligence.insight_generator import generate_insight

logger: logging.Logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# History file mapping (internal constants only — no user-supplied paths)
# ---------------------------------------------------------------------------

_HISTORY_DIR: Path = Path(".tmp/observatory")

_HISTORY_FILES: dict[str, Path] = {
    "quality": _HISTORY_DIR / "quality_history.json",
    "security": _HISTORY_DIR / "security_history.json",
    "deployment": _HISTORY_DIR / "deployment_history.json",
    "flow": _HISTORY_DIR / "flow_history.json",
    "ownership": _HISTORY_DIR / "ownership_history.json",
    "risk": _HISTORY_DIR / "risk_history.json",
    "collaboration": _HISTORY_DIR / "collaboration_history.json",
    "exploitable": _HISTORY_DIR / "exploitable_history.json",
}

_REPORT_OUTPUT_DIR: Path = Path(".tmp/observatory/dashboards")

# Severity thresholds: delta_pct magnitude → severity label
_SEVERITY_SPIKE_THRESHOLD: float = 15.0
_SEVERITY_WARNING_THRESHOLD: float = 5.0

# ---------------------------------------------------------------------------
# Local numeric coercion helper
# (mirrors insight_generator._coerce_numeric_context — not imported as
# a private symbol per architecture rules)
# ---------------------------------------------------------------------------


def _coerce_context(context: dict[str, object]) -> dict[str, object]:
    """
    Return a copy of ``context`` with all numeric-looking values coerced to float.

    String values that parse as floats are converted; non-numeric strings are
    kept as-is (safe for str.format_map without eval/exec).

    Security rationale: coercing numbers prevents prompt-injection through
    format-string manipulation.
    """
    safe: dict[str, object] = {}
    for key, val in context.items():
        if isinstance(val, (int, float)):
            safe[key] = float(val)
        elif isinstance(val, str):
            try:
                safe[key] = float(val)
            except ValueError:
                safe[key] = val
        else:
            safe[key] = val
    return safe


# ---------------------------------------------------------------------------
# Stage 1 — Load metric context from history files
# ---------------------------------------------------------------------------


def _load_metric_context(metric: str) -> dict[str, object]:
    """
    Load the latest week's data for a metric from its history file.

    Security: validates metric against VALID_METRICS before building
    any file path.

    Args:
        metric: Metric name — must be in VALID_METRICS.

    Returns:
        Context dict with keys: metric, delta_pct, top_dimension, dim_delta.
        Returns empty dict on any failure (missing file, bad JSON, unknown metric).
    """
    if metric not in VALID_METRICS:
        logger.warning(
            "Metric not in VALID_METRICS — skipping context load",
            extra={"metric": metric},
        )
        return {}

    history_path = _HISTORY_FILES.get(metric)
    if history_path is None:
        logger.debug(
            "No history file mapping for metric",
            extra={"metric": metric},
        )
        return {}

    try:
        raw = json.loads(history_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug(
            "Could not load history file for metric",
            extra={"metric": metric, "path": str(history_path), "error": str(exc)},
        )
        return {}

    weeks = raw.get("weeks", [])
    if not weeks:
        return {"metric": metric, "delta_pct": 0.0, "top_dimension": "", "dim_delta": 0.0}

    latest: dict = weeks[-1] if isinstance(weeks, list) else {}

    # Extract a simple numeric signal — different history schemas expose
    # different keys; use safe .get() with 0.0 defaults throughout.
    delta_pct: float = float(latest.get("delta_pct", latest.get("change_pct", 0.0)))
    top_dimension: str = str(latest.get("top_dimension", latest.get("top_project", "")))
    dim_delta: float = float(latest.get("dim_delta", latest.get("top_delta", 0.0)))

    return _coerce_context(
        {
            "metric": metric,
            "delta_pct": delta_pct,
            "top_dimension": top_dimension,
            "dim_delta": dim_delta,
        }
    )


# ---------------------------------------------------------------------------
# Stage 2 — Generate MetricInsight objects
# ---------------------------------------------------------------------------


def _pick_template_key(context: dict[str, object]) -> str:
    """Choose an insight template key based on delta_pct magnitude."""
    abs_delta = abs(float(context.get("delta_pct", 0.0)))  # type: ignore[arg-type]
    if abs_delta >= _SEVERITY_SPIKE_THRESHOLD:
        return "anomaly_spike"
    if abs_delta >= _SEVERITY_WARNING_THRESHOLD:
        return "trend_reversal"
    return "stable"


def _pick_severity(context: dict[str, object]) -> str:
    """Map context delta magnitude to a severity label."""
    delta = abs(float(context.get("delta_pct", 0.0)))  # type: ignore[arg-type]
    if delta >= _SEVERITY_SPIKE_THRESHOLD:
        return "critical"
    if delta >= _SEVERITY_WARNING_THRESHOLD:
        return "warning"
    return "info"


def _generate_metric_insights(use_llm: bool = False) -> list[MetricInsight]:
    """
    Generate one MetricInsight per supported metric.

    Only processes metrics that have a corresponding entry in _HISTORY_FILES.
    All metric names are validated against VALID_METRICS before use.

    Args:
        use_llm: If True, attempt LLM insight generation (falls back to
                 template if API key absent or call fails).

    Returns:
        List of MetricInsight objects (one per supported metric).
    """
    insights: list[MetricInsight] = []

    for metric in sorted(VALID_METRICS):  # Deterministic ordering
        if metric not in _HISTORY_FILES:
            logger.debug(
                "Metric has no history file mapping — skipping",
                extra={"metric": metric},
            )
            continue

        context = _load_metric_context(metric)
        template_key = _pick_template_key(context)
        severity = _pick_severity(context)

        insight = generate_insight(
            template_key=template_key,
            context=context,
            metric=metric,
            severity=severity,
            use_llm=use_llm,
        )
        insights.append(insight)
        logger.debug(
            "Insight generated",
            extra={"metric": metric, "template_key": template_key, "severity": severity},
        )

    logger.info("Metric insights generated", extra={"count": len(insights)})
    return insights


# ---------------------------------------------------------------------------
# Stage 3 — Build template context
# ---------------------------------------------------------------------------

_SEVERITY_COLORS: dict[str, tuple[str, str]] = {
    "critical": ("rgba(239,68,68,0.2)", "#ef4444"),
    "warning": ("rgba(245,158,11,0.2)", "#f59e0b"),
    "info": ("rgba(16,185,129,0.2)", "#10b981"),
}


def _build_report_context(
    insights: list[MetricInsight],
    report_date: datetime,
) -> dict[str, object]:
    """
    Build the Jinja2 template context for the intelligence report.

    All insight text is passed as a plain string — it is auto-escaped by
    Jinja2 and never marked as safe.

    Args:
        insights:    List of MetricInsight objects.
        report_date: Date for the report header.

    Returns:
        Context dict for render_dashboard().
    """
    week_num = report_date.isocalendar()[1]
    year = report_date.year
    gen_ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    by_severity: dict[str, int] = {"critical": 0, "warning": 0, "info": 0}
    for ins in insights:
        by_severity[ins.severity] = by_severity.get(ins.severity, 0) + 1

    insight_rows = []
    for ins in insights:
        bg, color = _SEVERITY_COLORS.get(ins.severity, ("rgba(148,163,184,0.15)", "#94a3b8"))
        insight_rows.append(
            {
                "metric_display": ins.metric.replace("_", " ").title(),
                "text": ins.text,  # auto-escaped by Jinja2 — NOT marked safe
                "severity_upper": ins.severity.upper(),
                "badge_bg": bg,
                "badge_color": color,
                "source": ins.source,
            }
        )

    return {
        "week_num": week_num,
        "year": year,
        "report_date_display": report_date.strftime("%B %d, %Y"),
        "gen_ts": gen_ts,
        "total_insights": len(insights),
        "critical_count": by_severity.get("critical", 0),
        "warning_count": by_severity.get("warning", 0),
        "info_count": by_severity.get("info", 0),
        "insight_rows": insight_rows,
    }


# ---------------------------------------------------------------------------
# Stage 4 — Public entry point
# ---------------------------------------------------------------------------


def generate_report(
    use_llm: bool = False,
    output_dir: Path | None = None,
    report_date: datetime | None = None,
) -> str:
    """
    Generate the Weekly Strategic Intelligence Report.

    Writes two files to ``output_dir``:
    - ``intelligence_report_YYYY-MM-DD.html`` (dated archive copy)
    - ``intelligence_report_latest.html`` (stable URL, overwritten each run)

    Args:
        use_llm:     If True, attempt LLM insight generation (default False).
        output_dir:  Override output directory
                     (default: .tmp/observatory/dashboards/).
        report_date: Override report date (default: datetime.now()).

    Returns:
        Rendered HTML string of the report.
    """
    effective_date = report_date if report_date is not None else datetime.now()
    effective_output_dir = output_dir if output_dir is not None else _REPORT_OUTPUT_DIR

    logger.info(
        "Generating weekly intelligence report",
        extra={
            "report_date": effective_date.isoformat(),
            "use_llm": use_llm,
            "output_dir": str(effective_output_dir),
        },
    )

    insights = _generate_metric_insights(use_llm=use_llm)
    context = _build_report_context(insights, effective_date)
    html = render_dashboard("intelligence/intelligence_report.html", context, inject_defaults=False)

    # Write output files
    try:
        effective_output_dir.mkdir(parents=True, exist_ok=True)
        date_str = effective_date.strftime("%Y-%m-%d")

        dated_path = effective_output_dir / f"intelligence_report_{date_str}.html"
        dated_path.write_text(html, encoding="utf-8")
        logger.info("Intelligence report written (dated)", extra={"path": str(dated_path)})

        latest_path = effective_output_dir / "intelligence_report_latest.html"
        latest_path.write_text(html, encoding="utf-8")
        logger.info("Intelligence report written (latest)", extra={"path": str(latest_path)})

    except OSError as exc:
        logger.error(
            "Failed to write intelligence report files",
            extra={"error": str(exc), "output_dir": str(effective_output_dir)},
        )

    logger.info(
        "Intelligence report complete",
        extra={"insights": len(insights), "html_size": len(html)},
    )
    return html


# ---------------------------------------------------------------------------
# __main__ entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Generate the Weekly Intelligence Report and write to default output path."""
    logger.info("Narrative Engine — running standalone")
    use_llm = bool(os.environ.get("ANTHROPIC_API_KEY"))
    try:
        html = generate_report(use_llm=use_llm)
        logger.info("Report generated successfully", extra={"html_size": len(html)})
    except OSError as exc:
        logger.error("Report generation failed", extra={"error": str(exc)})
        raise


if __name__ == "__main__":
    main()
