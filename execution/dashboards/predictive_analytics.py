"""
Predictive Analytics Dashboard — execution/dashboards/predictive_analytics.py

Shows pre-computed scenario comparison: BAU vs Accelerated vs other scenarios.
All Plotly values coerced to float() (security requirement).
4-stage pipeline: Load → Calculate → Build Context → Render.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

from execution.core import get_logger
from execution.dashboards.renderer import render_dashboard
from execution.domain.intelligence import ScenarioResult
from execution.framework import get_dashboard_framework

logger = get_logger(__name__)

OUTPUT_PATH = Path(".tmp/observatory/dashboards/predictive_analytics.html")

# ---------------------------------------------------------------------------
# Stage 1 — Load Data
# ---------------------------------------------------------------------------


def _load_scenario_results(
    base_dir: Path = Path("data/insights"),
) -> list[ScenarioResult]:
    """
    Load scenario results from JSON files matching scenario_results_*.json.

    Reads all files matching ``scenario_results_*.json`` within base_dir and
    deserialises each entry into a ScenarioResult domain object using
    ScenarioResult.from_dict(). Returns an empty list when the directory does
    not exist or contains no valid data.

    Args:
        base_dir: Directory containing scenario result JSON files.

    Returns:
        List of ScenarioResult objects, or empty list if not available.
    """
    if not base_dir.exists():
        logger.info(
            "Scenario results directory not found — skipping",
            extra={"path": str(base_dir)},
        )
        return []

    scenarios: list[ScenarioResult] = []
    for json_file in sorted(base_dir.glob("scenario_results_*.json")):
        try:
            raw = json.loads(json_file.read_text(encoding="utf-8"))
            entries = raw if isinstance(raw, list) else raw.get("scenarios", [])
            for entry in entries:
                scenarios.append(ScenarioResult.from_dict(entry))
        except (KeyError, ValueError, OSError) as exc:
            logger.warning(
                "Could not parse scenario results file",
                extra={"file": str(json_file), "error": str(exc)},
            )

    logger.info("Scenario results loaded", extra={"count": len(scenarios)})
    return scenarios


# ---------------------------------------------------------------------------
# Stage 1b — Build Scenario Comparison Chart (inline; no separate file needed)
# ---------------------------------------------------------------------------


def _build_scenario_comparison_chart(
    scenarios: list[ScenarioResult],
) -> str:
    """
    Build a grouped bar chart comparing P50 outcomes across scenarios.

    X-axis: scenario names.
    Y-axis: P50 value at the maximum horizon week.
    Error bars show the P10→P50 (lower) and P50→P90 (upper) spread.

    All values are coerced to float() before being passed to go.Figure()
    (security requirement).

    Args:
        scenarios: List of ScenarioResult objects to compare.

    Returns:
        HTML string for the Plotly chart div, or empty string if no scenarios.
    """
    if not scenarios:
        return ""

    names: list[str] = []
    p50_values: list[float] = []
    error_lower: list[float] = []
    error_upper: list[float] = []
    prob_values: list[float] = []

    for sr in scenarios:
        if not sr.forecast:
            continue
        horizon_point = max(sr.forecast, key=lambda p: p.week)
        p10 = float(horizon_point.p10)
        p50 = float(horizon_point.p50)
        p90 = float(horizon_point.p90)
        names.append(str(sr.scenario_name))
        p50_values.append(p50)
        error_lower.append(p50 - p10)
        error_upper.append(p90 - p50)
        prob_values.append(float(sr.probability_of_improvement))

    if not names:
        return ""

    bar_colors = ["#10b981" if p >= 0.6 else "#f59e0b" if p >= 0.4 else "#ef4444" for p in prob_values]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=names,
            y=p50_values,
            name="P50 at Horizon",
            marker_color=bar_colors,
            error_y={
                "type": "data",
                "symmetric": False,
                "array": error_upper,
                "arrayminus": error_lower,
                "color": "#94a3b8",
                "thickness": 1.5,
                "width": 6,
            },
            hovertemplate=("<b>%{x}</b><br>" "P50: %{y:.1f}<br>" "<extra></extra>"),
        )
    )

    fig.update_layout(
        plot_bgcolor="#1e293b",
        paper_bgcolor="#1e293b",
        font={"color": "#e2e8f0", "size": 11},
        height=340,
        margin={"l": 50, "r": 20, "t": 30, "b": 50},
        xaxis={
            "gridcolor": "#334155",
            "linecolor": "#334155",
            "tickfont": {"color": "#94a3b8", "size": 11},
            "title": {"text": "Scenario", "font": {"color": "#94a3b8", "size": 11}},
        },
        yaxis={
            "gridcolor": "#334155",
            "linecolor": "#334155",
            "tickfont": {"color": "#94a3b8", "size": 11},
            "title": {"text": "P50 Value at Horizon", "font": {"color": "#94a3b8", "size": 11}},
        },
        showlegend=False,
        bargap=0.35,
    )

    return str(
        fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            div_id="chart_scenario_comparison",
        )
    )


# ---------------------------------------------------------------------------
# Stage 2 — Calculate Summary
# ---------------------------------------------------------------------------


def _calculate_summary(scenarios: list[ScenarioResult]) -> dict[str, Any]:
    """
    Compute dashboard-level summary from loaded scenario results.

    Args:
        scenarios: All loaded ScenarioResult objects.

    Returns:
        Summary dict with keys:
            has_data            – True when scenarios is non-empty
            scenario_count      – total number of loaded scenarios
            best_scenario_name  – scenario with highest probability_of_improvement
            best_probability    – that scenario's probability_of_improvement (0.0–1.0)
            scenarios           – the original list (for template iteration)
    """
    if not scenarios:
        return {
            "has_data": False,
            "scenario_count": 0,
            "best_scenario_name": "—",
            "best_probability": 0.0,
            "scenarios": [],
        }

    best = max(scenarios, key=lambda s: s.probability_of_improvement)

    return {
        "has_data": True,
        "scenario_count": len(scenarios),
        "best_scenario_name": best.scenario_name,
        "best_probability": round(float(best.probability_of_improvement), 3),
        "scenarios": scenarios,
    }


# ---------------------------------------------------------------------------
# Stage 3 — Build Context
# ---------------------------------------------------------------------------


def _build_context(summary: dict[str, Any], chart_html: str) -> dict[str, Any]:
    """
    Build the full Jinja2 template context for the Predictive Analytics dashboard.

    Calls ``get_dashboard_framework()`` and includes both ``framework_css``
    and ``framework_js`` as required by the dashboard architecture standard.

    Args:
        summary: Output of _calculate_summary().
        chart_html: Pre-built Plotly comparison chart HTML (may be empty).

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

    return {
        "framework_css": framework_css,  # REQUIRED — do not remove
        "framework_js": framework_js,  # REQUIRED — do not remove
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "has_data": summary["has_data"],
        "scenario_count": summary["scenario_count"],
        "best_scenario_name": summary["best_scenario_name"],
        "best_probability": summary["best_probability"],
        "scenarios": summary["scenarios"],
        "scenario_chart_html": chart_html,
    }


# ---------------------------------------------------------------------------
# Stage 4 — Render (main entry point)
# ---------------------------------------------------------------------------


def generate_predictive_analytics(output_dir: Path | None = None) -> str:
    """
    Generate the Predictive Analytics Dashboard HTML.

    Orchestrates the 4-stage pipeline:
        [1/4] Load scenario results from data/insights/
        [2/4] Calculate scenario-level summary metrics
        [3/4] Build template context (framework CSS/JS, charts, KPIs)
        [4/4] Render Jinja2 template → HTML string

    Data loading is graceful — all stages return empty/zero defaults when
    the intelligence pipeline has not yet run.

    Args:
        output_dir: Optional directory to write the generated HTML file.
            When provided the file is written as ``predictive_analytics.html``
            inside this directory.

    Returns:
        Generated HTML string.
    """
    logger.info("Generating Predictive Analytics Dashboard")

    # [1/4] Load data
    logger.info("Loading scenario results")
    scenarios = _load_scenario_results()

    # Build chart before summary so we can pass it separately
    chart_html = _build_scenario_comparison_chart(scenarios)

    logger.info(
        "Data loaded",
        extra={
            "scenario_count": len(scenarios),
            "has_chart": bool(chart_html),
        },
    )

    # [2/4] Calculate summary
    logger.info("Calculating scenario summary")
    summary = _calculate_summary(scenarios)

    # [3/4] Build context
    logger.info("Building template context")
    context = _build_context(summary, chart_html)

    # [4/4] Render
    logger.info("Rendering HTML template")
    html = render_dashboard("dashboards/predictive_analytics.html", context)

    # Optionally write to disk
    if output_dir is not None:
        output_path = output_dir / "predictive_analytics.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info(
            "Predictive analytics dashboard written to file",
            extra={"path": str(output_path)},
        )

    logger.info(
        "Predictive Analytics Dashboard generated",
        extra={"html_size": len(html)},
    )
    return html


# ---------------------------------------------------------------------------
# __main__ entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Generate the Predictive Analytics Dashboard and write to the default output path."""
    logger.info("Predictive Analytics Dashboard — running standalone")
    try:
        output_dir = OUTPUT_PATH.parent
        html = generate_predictive_analytics(output_dir=output_dir)

        if OUTPUT_PATH.exists():
            file_size = OUTPUT_PATH.stat().st_size
            logger.info(
                "Predictive analytics dashboard generated successfully",
                extra={
                    "output": str(OUTPUT_PATH),
                    "file_size": file_size,
                    "html_size": len(html),
                },
            )
        else:
            logger.info(
                "Predictive analytics HTML generated (in-memory only)",
                extra={"html_size": len(html)},
            )

    except OSError as exc:
        logger.error(
            "Failed to write predictive analytics dashboard",
            extra={"error": str(exc)},
        )
        raise


if __name__ == "__main__":
    main()
