"""
Correlation Heatmap Dashboard — execution/dashboards/correlation_heatmap.py

Shows cross-metric Pearson correlation heatmap (up to 8 metrics x 8 metrics).
Uses DuckDB feature store from data/features/.
4-stage pipeline: Load → Calculate → Build Context → Render.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

from execution.core import get_logger
from execution.dashboards.renderer import render_dashboard
from execution.framework import get_dashboard_framework

# NOTE: correlation_analyzer is written by the ML Agent concurrently.
# The import is kept unconditional — CI will succeed once all agents complete.
from execution.intelligence.correlation_analyzer import compute_correlation_matrix

logger = get_logger(__name__)

OUTPUT_PATH = Path(".tmp/observatory/dashboards/correlation_heatmap.html")

# ---------------------------------------------------------------------------
# Stage 1 — Load Data
# ---------------------------------------------------------------------------


def _load_correlation_matrix(
    feature_dir: Path = Path("data/features"),
) -> dict[str, dict[str, float]]:
    """
    Load or compute the cross-metric Pearson correlation matrix.

    Calls compute_correlation_matrix(feature_dir=feature_dir) and returns
    the result.  Returns an empty dict when:
      - feature_dir has no Parquet files
      - compute_correlation_matrix raises ValueError (no features available)
      - any OSError is encountered

    Args:
        feature_dir: Directory containing DuckDB Parquet feature files.

    Returns:
        Nested dict: {metric_a: {metric_b: correlation_float}}, or {} if
        no data is available.
    """
    try:
        matrix: dict[str, dict[str, float]] = compute_correlation_matrix(feature_dir=feature_dir)
        logger.info(
            "Correlation matrix loaded",
            extra={"metric_count": len(matrix)},
        )
        return matrix
    except ValueError as exc:
        logger.info(
            "No feature data available for correlation matrix",
            extra={"error": str(exc)},
        )
        return {}
    except OSError as exc:
        logger.warning(
            "Could not load correlation matrix",
            extra={"error": str(exc)},
        )
        return {}


# ---------------------------------------------------------------------------
# Stage 1b — Build Correlation Heatmap Chart
# ---------------------------------------------------------------------------


def _build_correlation_heatmap_chart(
    matrix: dict[str, dict[str, float]],
) -> str:
    """
    Build a Plotly go.Heatmap from the correlation matrix.

    - All values coerced to float()
    - colorscale="RdBu_r", zmid=0, zmin=-1, zmax=1
    - Cell annotations show the correlation value rounded to 2 decimal places.
    - Returns empty string if the matrix is empty.

    Args:
        matrix: Nested dict {metric_a: {metric_b: pearson_r}}.

    Returns:
        HTML string for the Plotly heatmap div, or empty string if no data.
    """
    if not matrix:
        return ""

    metrics = list(matrix.keys())

    # Build z-values matrix and annotation text
    z_values: list[list[float]] = []
    annotation_text: list[list[str]] = []

    for metric_row in metrics:
        row_vals: list[float] = []
        row_text: list[str] = []
        for metric_col in metrics:
            raw = matrix.get(metric_row, {}).get(metric_col, 0.0)
            val = float(raw)
            row_vals.append(val)
            row_text.append(f"{val:.2f}")
        z_values.append(row_vals)
        annotation_text.append(row_text)

    # Build annotation objects for each cell
    annotations = []
    for row_idx, metric_row in enumerate(metrics):
        for col_idx, metric_col in enumerate(metrics):
            val = z_values[row_idx][col_idx]
            font_color = "#0f172a" if abs(val) > 0.6 else "#e2e8f0"
            annotations.append(
                {
                    "x": metric_col,
                    "y": metric_row,
                    "text": f"{val:.2f}",
                    "showarrow": False,
                    "font": {"color": font_color, "size": 10},
                }
            )

    # Derive a readable label from metric names
    display_labels = [m.replace("_", " ").title() for m in metrics]

    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=display_labels,
            y=display_labels,
            colorscale="RdBu_r",
            zmid=float(0),
            zmin=float(-1),
            zmax=float(1),
            colorbar={
                "title": {"text": "Pearson r", "side": "right"},
                "tickvals": [-1, -0.5, 0, 0.5, 1],
                "ticktext": ["-1", "-0.5", "0", "+0.5", "+1"],
                "tickfont": {"color": "#94a3b8", "size": 10},
                "titlefont": {"color": "#94a3b8", "size": 11},
            },
            hovertemplate=("<b>%{y}</b> vs <b>%{x}</b><br>" "Pearson r: %{z:.3f}<extra></extra>"),
        )
    )

    fig.update_layout(
        plot_bgcolor="#1e293b",
        paper_bgcolor="#1e293b",
        font={"color": "#e2e8f0", "size": 11},
        height=520,
        margin={"l": 120, "r": 60, "t": 30, "b": 120},
        xaxis={
            "tickfont": {"color": "#94a3b8", "size": 10},
            "tickangle": -40,
            "side": "bottom",
        },
        yaxis={
            "tickfont": {"color": "#94a3b8", "size": 10},
        },
        annotations=annotations,
    )

    return str(
        fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            div_id="chart_correlation_heatmap",
        )
    )


# ---------------------------------------------------------------------------
# Stage 2 — Calculate Summary
# ---------------------------------------------------------------------------


def _calculate_summary(
    matrix: dict[str, dict[str, float]],
) -> dict[str, Any]:
    """
    Compute dashboard-level summary from the correlation matrix.

    Args:
        matrix: Nested dict {metric_a: {metric_b: pearson_r}}.

    Returns:
        Summary dict with keys:
            has_data            – True when matrix is non-empty
            metric_count        – number of distinct metrics in the matrix
            strong_correlations – top-5 pairs with |r| >= 0.5 (excluding self)
            matrix              – the full correlation dict (for template use)
    """
    if not matrix:
        return {
            "has_data": False,
            "metric_count": 0,
            "strong_correlations": [],
            "matrix": {},
        }

    metrics = list(matrix.keys())

    # Collect all unique off-diagonal pairs with |r| >= 0.5
    seen: set[frozenset[str]] = set()
    strong: list[tuple[str, str, float]] = []

    for metric_a in metrics:
        for metric_b, val in matrix.get(metric_a, {}).items():
            if metric_a == metric_b:
                continue
            pair_key = frozenset({metric_a, metric_b})
            if pair_key in seen:
                continue
            seen.add(pair_key)
            r = float(val)
            if abs(r) >= 0.5:
                strong.append((metric_a, metric_b, r))

    # Sort by absolute value descending, keep top 5
    strong.sort(key=lambda t: abs(t[2]), reverse=True)
    top_strong = strong[:5]

    return {
        "has_data": True,
        "metric_count": len(metrics),
        "strong_correlations": top_strong,
        "matrix": matrix,
    }


# ---------------------------------------------------------------------------
# Stage 3 — Build Context
# ---------------------------------------------------------------------------


def _build_context(
    summary: dict[str, Any],
    heatmap_html: str,
) -> dict[str, Any]:
    """
    Build the full Jinja2 template context for the Correlation Heatmap dashboard.

    Calls ``get_dashboard_framework()`` and includes both ``framework_css``
    and ``framework_js`` as required by the dashboard architecture standard.

    Args:
        summary: Output of _calculate_summary().
        heatmap_html: Pre-built Plotly heatmap HTML (may be empty).

    Returns:
        Context dict ready for render_dashboard().
    """
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#0f172a",
        header_gradient_end="#0f172a",
        include_table_scroll=False,
        include_expandable_rows=False,
        include_glossary=True,
    )

    return {
        "framework_css": framework_css,  # REQUIRED — do not remove
        "framework_js": framework_js,  # REQUIRED — do not remove
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "has_data": summary["has_data"],
        "metric_count": summary["metric_count"],
        "strong_correlations": summary["strong_correlations"],
        "matrix": summary["matrix"],
        "heatmap_html": heatmap_html,
    }


# ---------------------------------------------------------------------------
# Stage 4 — Render (main entry point)
# ---------------------------------------------------------------------------


def generate_correlation_heatmap(output_dir: Path | None = None) -> str:
    """
    Generate the Correlation Heatmap Dashboard HTML.

    Orchestrates the 4-stage pipeline:
        [1/4] Load or compute the cross-metric correlation matrix
        [2/4] Calculate summary (metric count, strong pairs)
        [3/4] Build template context (framework CSS/JS, heatmap chart)
        [4/4] Render Jinja2 template → HTML string

    Data loading is graceful — all stages return empty/zero defaults when
    the intelligence pipeline has not yet run.

    Args:
        output_dir: Optional directory to write the generated HTML file.
            When provided the file is written as ``correlation_heatmap.html``
            inside this directory.

    Returns:
        Generated HTML string.
    """
    logger.info("Generating Correlation Heatmap Dashboard")

    # [1/4] Load data
    logger.info("Loading correlation matrix")
    matrix = _load_correlation_matrix()
    heatmap_html = _build_correlation_heatmap_chart(matrix)

    logger.info(
        "Data loaded",
        extra={
            "metric_count": len(matrix),
            "has_heatmap": bool(heatmap_html),
        },
    )

    # [2/4] Calculate summary
    logger.info("Calculating correlation summary")
    summary = _calculate_summary(matrix)

    # [3/4] Build context
    logger.info("Building template context")
    context = _build_context(summary, heatmap_html)

    # [4/4] Render
    logger.info("Rendering HTML template")
    html = render_dashboard("dashboards/correlation_heatmap.html", context)

    # Optionally write to disk
    if output_dir is not None:
        output_path = output_dir / "correlation_heatmap.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info(
            "Correlation heatmap dashboard written to file",
            extra={"path": str(output_path)},
        )

    logger.info(
        "Correlation Heatmap Dashboard generated",
        extra={"html_size": len(html)},
    )
    return html


# ---------------------------------------------------------------------------
# __main__ entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Generate the Correlation Heatmap Dashboard and write to the default output path."""
    logger.info("Correlation Heatmap Dashboard — running standalone")
    try:
        output_dir = OUTPUT_PATH.parent
        html = generate_correlation_heatmap(output_dir=output_dir)

        if OUTPUT_PATH.exists():
            file_size = OUTPUT_PATH.stat().st_size
            logger.info(
                "Correlation heatmap dashboard generated successfully",
                extra={
                    "output": str(OUTPUT_PATH),
                    "file_size": file_size,
                    "html_size": len(html),
                },
            )
        else:
            logger.info(
                "Correlation heatmap HTML generated (in-memory only)",
                extra={"html_size": len(html)},
            )

    except OSError as exc:
        logger.error(
            "Failed to write correlation heatmap dashboard",
            extra={"error": str(exc)},
        )
        raise


if __name__ == "__main__":
    main()
