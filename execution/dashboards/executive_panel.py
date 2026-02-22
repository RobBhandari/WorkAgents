"""
Executive Intelligence Panel Dashboard Generator

Generates the Executive Intelligence Panel dashboard from risk scores,
forecasts, and feature data. This is the single-pane-of-glass view for
engineering leadership.

Usage:
    python -m execution.dashboards.executive_panel
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

from execution.core import get_logger
from execution.dashboards.components.forecast_chart import build_trend_chart
from execution.dashboards.renderer import render_dashboard
from execution.domain.intelligence import RiskScore
from execution.framework import get_dashboard_framework

logger = get_logger(__name__)

OUTPUT_PATH = Path(".tmp/observatory/dashboards/executive_panel.html")

# ---------------------------------------------------------------------------
# Stage 1 — Load Data
# ---------------------------------------------------------------------------


def _load_risk_scores(base_dir: Path = Path("data/insights")) -> list[RiskScore]:
    """
    Load risk scores from JSON files in base_dir.

    Reads all files matching ``risk_scores_*.json`` within base_dir and
    deserialises each entry into a RiskScore domain object. Returns an
    empty list when the directory does not exist or contains no valid data.

    Args:
        base_dir: Directory containing risk score JSON files.

    Returns:
        List of RiskScore objects, or empty list if not available.
    """
    if not base_dir.exists():
        logger.info("Risk scores directory not found — skipping", extra={"path": str(base_dir)})
        return []

    scores: list[RiskScore] = []
    for json_file in sorted(base_dir.glob("risk_scores_*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            entries = data if isinstance(data, list) else data.get("scores", [])
            for entry in entries:
                scores.append(
                    RiskScore(
                        project=str(entry["project"]),
                        total=float(entry["total"]),
                        components=[],
                    )
                )
        except (KeyError, ValueError, OSError) as exc:
            logger.warning(
                "Could not parse risk score file",
                extra={"file": str(json_file), "error": str(exc)},
            )

    logger.info("Risk scores loaded", extra={"count": len(scores)})
    return scores


def _load_forecasts_summary(base_dir: Path = Path("data/forecasts")) -> dict[str, Any]:
    """
    Load the latest forecast metadata from base_dir.

    Looks for a ``forecast_summary.json`` file.  Returns an empty dict
    when the directory or file does not exist.

    Args:
        base_dir: Directory containing forecast output files.

    Returns:
        Forecast summary dict, or empty dict if not available.
    """
    summary_path = base_dir / "forecast_summary.json"
    if not summary_path.exists():
        logger.info(
            "Forecast summary not found — skipping",
            extra={"path": str(summary_path)},
        )
        return {}

    try:
        data: dict[str, Any] = json.loads(summary_path.read_text(encoding="utf-8"))
        return data
    except (ValueError, OSError) as exc:
        logger.warning(
            "Could not parse forecast summary",
            extra={"path": str(summary_path), "error": str(exc)},
        )
        return {}


def _build_portfolio_trend_chart(feature_dir: Path = Path("data/features")) -> str:
    """
    Build a portfolio-level risk trend chart from feature history files.

    Reads ``portfolio_risk_history.json`` from feature_dir and produces a
    Plotly trend chart.  Returns an empty string when no data is available.

    All numeric values are coerced to ``float`` before being passed to
    Plotly (security requirement).

    Args:
        feature_dir: Directory containing feature/history JSON files.

    Returns:
        HTML string for the Plotly chart div, or empty string if unavailable.
    """
    history_path = feature_dir / "portfolio_risk_history.json"
    if not history_path.exists():
        logger.info(
            "Portfolio risk history not found — skipping trend chart",
            extra={"path": str(history_path)},
        )
        return ""

    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
    except (ValueError, OSError) as exc:
        logger.warning(
            "Could not load portfolio risk history",
            extra={"path": str(history_path), "error": str(exc)},
        )
        return ""

    if not entries:
        return ""

    # Coerce all values to float (security requirement)
    week_labels: list[str] = [str(e.get("date", "")) for e in entries]
    weekly_values: list[float] = [float(e.get("avg_risk", 0)) for e in entries]

    valid = [(lbl, val) for lbl, val in zip(week_labels, weekly_values, strict=True) if lbl]
    if not valid:
        return ""

    labels, values = zip(*valid, strict=False)
    return build_trend_chart(
        list(values),
        list(labels),
        "Avg Portfolio Risk Score",
        color="#6366f1",
        height=280,
    )


# ---------------------------------------------------------------------------
# Stage 1b — Risk gauge chart (inline; no separate file needed)
# ---------------------------------------------------------------------------


def _build_risk_gauge(score: float) -> str:
    """
    Build a Plotly gauge chart for the org-level risk score (0–100).

    All numeric values are coerced to ``float`` before being passed to
    Plotly (security requirement).

    Args:
        score: Composite risk score (0–100; higher = more risk).

    Returns:
        HTML string for the Plotly gauge div.
    """
    safe_score = float(score)
    color = "#10b981" if safe_score < 40 else "#f59e0b" if safe_score < 70 else "#ef4444"

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=safe_score,
            domain={"x": [0, 1], "y": [0, 1]},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#94a3b8"},
                "bar": {"color": color},
                "bgcolor": "#334155",
                "steps": [
                    {"range": [0, 40], "color": "rgba(16,185,129,0.1)"},
                    {"range": [40, 70], "color": "rgba(245,158,11,0.1)"},
                    {"range": [70, 100], "color": "rgba(239,68,68,0.1)"},
                ],
            },
            number={"font": {"color": color, "size": 48}},
        )
    )
    fig.update_layout(
        paper_bgcolor="#1e293b",
        font={"color": "#e2e8f0"},
        height=220,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
    )
    return str(fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_risk_gauge"))


# ---------------------------------------------------------------------------
# Stage 2 — Calculate Summary
# ---------------------------------------------------------------------------


def _calculate_summary(
    risk_scores: list[RiskScore],
    forecast_summary: dict[str, Any],
) -> dict[str, Any]:
    """
    Compute org-level summary from risk scores and forecast metadata.

    Args:
        risk_scores: All loaded RiskScore objects.
        forecast_summary: Raw forecast summary dict (may be empty).

    Returns:
        Summary dict with keys:
            org_risk_score  – average total score (0–100) across all projects
            critical_count  – projects with level == "critical"
            high_count      – projects with level == "high"
            total_count     – total number of projects scored
            top_risks       – top-3 RiskScore objects by total score (descending)
            org_trend       – "improving" | "worsening" | "stable"
            has_data        – True when risk_scores is non-empty
    """
    if not risk_scores:
        return {
            "org_risk_score": 0.0,
            "critical_count": 0,
            "high_count": 0,
            "total_count": 0,
            "top_risks": [],
            "org_trend": "stable",
            "has_data": False,
        }

    org_risk_score = sum(rs.total for rs in risk_scores) / len(risk_scores)
    critical_count = sum(1 for rs in risk_scores if rs.level == "critical")
    high_count = sum(1 for rs in risk_scores if rs.level == "high")
    top_risks = sorted(risk_scores, key=lambda rs: rs.total, reverse=True)[:3]

    # Derive org trend from forecast summary when available
    trend_value: str = forecast_summary.get("org_trend", "stable")
    if trend_value not in ("improving", "worsening", "stable"):
        trend_value = "stable"

    return {
        "org_risk_score": round(org_risk_score, 1),
        "critical_count": critical_count,
        "high_count": high_count,
        "total_count": len(risk_scores),
        "top_risks": top_risks,
        "org_trend": trend_value,
        "has_data": True,
    }


# ---------------------------------------------------------------------------
# Stage 3 — Build Context
# ---------------------------------------------------------------------------


def _build_context(summary: dict[str, Any], portfolio_trend_chart: str) -> dict[str, Any]:
    """
    Build the full Jinja2 template context for the Executive Panel.

    Calls ``get_dashboard_framework()`` and includes both ``framework_css``
    and ``framework_js`` as required by the dashboard architecture standard.

    Args:
        summary: Output of _calculate_summary().
        portfolio_trend_chart: Pre-built Plotly chart HTML (may be empty).

    Returns:
        Context dict ready for render_dashboard().
    """
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#0f172a",
        header_gradient_end="#0f172a",
        include_table_scroll=True,
        include_expandable_rows=True,
        include_glossary=True,
    )

    # Build risk gauge only when data is present
    risk_gauge_html = _build_risk_gauge(summary["org_risk_score"]) if summary["has_data"] else ""

    # Org trend display helpers
    trend = summary["org_trend"]
    trend_class = {
        "improving": "trend-improving",
        "worsening": "trend-worsening",
        "stable": "trend-stable",
    }.get(trend, "trend-stable")
    trend_arrow = {"improving": "↓", "worsening": "↑", "stable": "→"}.get(trend, "→")

    # Build KPI summary cards list (passed as dicts; template renders them)
    kpi_cards = [
        {
            "label": "Org Risk Score",
            "value": f"{summary['org_risk_score']:.0f}/100",
            "status_class": _risk_status_class(summary["org_risk_score"]),
            "description": "Average composite risk across all projects",
        },
        {
            "label": "Critical Projects",
            "value": str(summary["critical_count"]),
            "status_class": "status-action" if summary["critical_count"] > 0 else "status-good",
            "description": "Projects with risk score > 80",
        },
        {
            "label": "High Risk Projects",
            "value": str(summary["high_count"]),
            "status_class": "status-caution" if summary["high_count"] > 0 else "status-good",
            "description": "Projects with risk score 61–80",
        },
        {
            "label": "Total Projects",
            "value": str(summary["total_count"]),
            "status_class": "status-good",
            "description": "All projects with scored risk data",
        },
    ]

    return {
        "framework_css": framework_css,  # REQUIRED — do not remove
        "framework_js": framework_js,  # REQUIRED — do not remove
        "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "has_data": summary["has_data"],
        "org_risk_score": summary["org_risk_score"],
        "org_trend": trend,
        "trend_class": trend_class,
        "trend_arrow": trend_arrow,
        "kpi_cards": kpi_cards,
        "top_risks": summary["top_risks"],
        "risk_gauge_html": risk_gauge_html,
        "portfolio_trend_chart": portfolio_trend_chart,
    }


def _risk_status_class(score: float) -> str:
    """Map a numeric risk score to a CSS status class."""
    if score > 70:
        return "status-action"
    if score > 40:
        return "status-caution"
    return "status-good"


# ---------------------------------------------------------------------------
# Stage 4 — Render (main entry point)
# ---------------------------------------------------------------------------


def generate_executive_panel(output_dir: Path | None = None) -> str:
    """
    Generate the Executive Intelligence Panel HTML.

    Orchestrates the 4-stage pipeline:
        [1/4] Load risk scores, forecast summary, and feature history
        [2/4] Calculate org-level summary metrics
        [3/4] Build template context (framework CSS/JS, charts, KPI cards)
        [4/4] Render Jinja2 template → HTML string

    Data loading is graceful — all stages return empty/zero defaults when
    the intelligence pipeline has not yet run.

    Args:
        output_dir: Optional directory to write the generated HTML file.
            When provided the file is written as ``executive_panel.html``
            inside this directory.

    Returns:
        Generated HTML string.
    """
    logger.info("Generating Executive Intelligence Panel")

    # [1/4] Load data
    logger.info("Loading risk scores and forecasts")
    risk_scores = _load_risk_scores()
    forecast_summary = _load_forecasts_summary()
    portfolio_trend_chart = _build_portfolio_trend_chart()

    logger.info(
        "Data loaded",
        extra={
            "risk_scores": len(risk_scores),
            "forecast_summary_keys": list(forecast_summary.keys()),
            "has_trend_chart": bool(portfolio_trend_chart),
        },
    )

    # [2/4] Calculate summary
    logger.info("Calculating org-level summary")
    summary = _calculate_summary(risk_scores, forecast_summary)

    # [3/4] Build context
    logger.info("Building template context")
    context = _build_context(summary, portfolio_trend_chart)

    # [4/4] Render
    logger.info("Rendering HTML template")
    html = render_dashboard("dashboards/executive_panel.html", context)

    # Optionally write to disk
    if output_dir is not None:
        output_path = output_dir / "executive_panel.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info("Executive panel written to file", extra={"path": str(output_path)})

    logger.info("Executive Intelligence Panel generated", extra={"html_size": len(html)})
    return html


# ---------------------------------------------------------------------------
# __main__ entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Generate the Executive Intelligence Panel and write to the default output path."""
    logger.info("Executive Intelligence Panel — running standalone")
    try:
        output_dir = OUTPUT_PATH.parent
        html = generate_executive_panel(output_dir=output_dir)

        if OUTPUT_PATH.exists():
            file_size = OUTPUT_PATH.stat().st_size
            logger.info(
                "Executive panel generated successfully",
                extra={"output": str(OUTPUT_PATH), "file_size": file_size, "html_size": len(html)},
            )
        else:
            logger.info(
                "Executive panel HTML generated (in-memory only)",
                extra={"html_size": len(html)},
            )

    except OSError as exc:
        logger.error("Failed to write executive panel", extra={"error": str(exc)})
        raise


if __name__ == "__main__":
    main()
