"""
Forecast Chart Component

Provides interactive Plotly trend chart HTML generators for embedding in dashboards.
Uses plotly.graph_objects for precise control over styling and layout.

Security note:
    fig.to_html(full_html=False, include_plotlyjs=False) output is injected
    with | safe in Jinja2 templates. This is acceptable because all data
    (weekly_values, week_labels) is server-controlled — sourced from pre-validated
    history JSON files, not from any user input. This is consistent with the
    existing {{ card | safe }} pattern used throughout dashboard templates.
"""

from __future__ import annotations

import plotly.graph_objects as go

# Color constants from the intelligence platform color system
COLOR_GOOD = "#10b981"
COLOR_CAUTION = "#f59e0b"
COLOR_ACTION = "#ef4444"
COLOR_FORECAST = "#6366f1"

# Dark theme background colors
_BG_CARD = "#1e293b"
_BG_ELEVATED = "#334155"
_TEXT_PRIMARY = "#e2e8f0"
_TEXT_SECONDARY = "#94a3b8"


def build_trend_chart(
    weekly_values: list[float],
    week_labels: list[str],
    metric_name: str,
    *,
    color: str = COLOR_FORECAST,
    height: int = 250,
) -> str:
    """
    Generate interactive Plotly trend chart HTML div.

    Uses fig.to_html(full_html=False, include_plotlyjs=False).
    Output is safe to inject with | safe — data is server-controlled:
    weekly_values comes from pre-validated history JSON (float-coerced),
    not from any user input.

    Args:
        weekly_values: Historical values (coerced to float internally)
        week_labels: Week label strings for x-axis
        metric_name: Display name for the chart title/tooltip
        color: Line color (hex)
        height: Chart height in pixels

    Returns:
        HTML string containing plotly div (no <script> tags needed —
        plotly.js is loaded via CDN in base_dashboard.html)
    """
    if not weekly_values:
        return ""

    # Coerce all values to float (handles ints from JSON)
    coerced_values = [float(v) for v in weekly_values]

    fig = go.Figure()

    # Main trend line
    fig.add_trace(
        go.Scatter(
            x=week_labels,
            y=coerced_values,
            name=metric_name,
            mode="lines+markers",
            line={"color": color, "width": 2},
            marker={"color": color, "size": 5},
            hovertemplate=f"{metric_name}: %{{y:.1f}}<br>%{{x}}<extra></extra>",
        )
    )

    fig.update_layout(
        plot_bgcolor=_BG_CARD,
        paper_bgcolor=_BG_CARD,
        font={"color": _TEXT_PRIMARY, "size": 11},
        height=height,
        margin={"l": 45, "r": 15, "t": 15, "b": 40},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "font": {"color": _TEXT_SECONDARY, "size": 10},
        },
        xaxis={
            "gridcolor": _BG_ELEVATED,
            "linecolor": _BG_ELEVATED,
            "tickfont": {"color": _TEXT_SECONDARY, "size": 10},
            "tickangle": -30,
        },
        yaxis={
            "gridcolor": _BG_ELEVATED,
            "linecolor": _BG_ELEVATED,
            "tickfont": {"color": _TEXT_SECONDARY, "size": 10},
        },
        hovermode="x unified",
    )

    div_id = f"chart_{metric_name.lower().replace(' ', '_').replace('(', '').replace(')', '')}"

    return str(
        fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            div_id=div_id,
        )
    )


def build_mini_trend_chart(
    weekly_values: list[float],
    week_labels: list[str],
    metric_name: str,
    *,
    height: int = 120,
) -> str:
    """
    Generate compact Plotly trend chart HTML div for summary cards.

    Uses fig.to_html(full_html=False, include_plotlyjs=False).
    Output is safe to inject with | safe — data is server-controlled:
    weekly_values comes from pre-validated history JSON (float-coerced),
    not from any user input.

    Args:
        weekly_values: Historical values (coerced to float internally)
        week_labels: Week label strings for x-axis
        metric_name: Display name for the chart title/tooltip
        height: Chart height in pixels (default 120 for compact display)

    Returns:
        HTML string containing compact plotly div (no <script> tags needed —
        plotly.js is loaded via CDN in base_dashboard.html)
    """
    if not weekly_values:
        return ""

    # Coerce all values to float (handles ints from JSON)
    coerced_values = [float(v) for v in weekly_values]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=week_labels,
            y=coerced_values,
            name=metric_name,
            mode="lines",
            line={"color": COLOR_FORECAST, "width": 1.5},
            hovertemplate="%{y:.1f}<extra></extra>",
            showlegend=False,
        )
    )

    fig.update_layout(
        plot_bgcolor=_BG_CARD,
        paper_bgcolor=_BG_CARD,
        font={"color": _TEXT_PRIMARY, "size": 9},
        height=height,
        margin={"l": 30, "r": 5, "t": 5, "b": 20},
        xaxis={
            "gridcolor": _BG_ELEVATED,
            "linecolor": _BG_ELEVATED,
            "tickfont": {"color": _TEXT_SECONDARY, "size": 8},
            "showticklabels": False,
        },
        yaxis={
            "gridcolor": _BG_ELEVATED,
            "linecolor": _BG_ELEVATED,
            "tickfont": {"color": _TEXT_SECONDARY, "size": 8},
        },
        hovermode="x unified",
    )

    div_id = f"mini_chart_{metric_name.lower().replace(' ', '_').replace('(', '').replace(')', '')}"

    return str(
        fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            div_id=div_id,
        )
    )
