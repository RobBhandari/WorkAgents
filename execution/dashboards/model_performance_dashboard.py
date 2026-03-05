"""
Model Performance Dashboard Generator

Generates the Model Performance dashboard from data/model_performance.json.
Provides a single-pane view of ML model health, MAPE, accuracy, and drift
for all models in the predictive intelligence platform.

Usage:
    python -m execution.dashboards.model_performance_dashboard
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from execution.core import get_logger
from execution.dashboards.renderer import render_dashboard
from execution.framework import get_dashboard_framework

logger: logging.Logger = get_logger(__name__)

OUTPUT_PATH: Path = Path(".tmp/observatory/dashboards/model_performance_dashboard.html")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODEL_PERFORMANCE_PATH: Path = Path("data/model_performance.json")

# Allowlist of valid model names — used to filter untrusted JSON input
_VALID_MODEL_NAMES: frozenset[str] = frozenset(
    {
        "forecast_quality",
        "forecast_security",
        "forecast_deployment",
        "forecast_flow",
        "forecast_ownership",
        "health_classifier",
        "clustering",
    }
)


# ---------------------------------------------------------------------------
# Stage 1 — Load Data
# ---------------------------------------------------------------------------


def _load_data(
    data_path: Path = _MODEL_PERFORMANCE_PATH,
) -> tuple[list[dict[str, Any]], str]:
    """
    Load model performance records from JSON.

    Args:
        data_path: Path to model_performance.json
                   (default: data/model_performance.json).

    Returns:
        Tuple of (models_list, last_updated_str).
        Returns ([], "Unknown") on any I/O or parse failure.
    """
    try:
        raw: dict[str, Any] = json.loads(data_path.read_text(encoding="utf-8"))
        models: list[dict[str, Any]] = list(raw.get("models", []))
        last_updated: str = str(raw.get("last_updated") or "Unknown")
        logger.info(
            "Model performance data loaded",
            extra={"count": len(models), "last_updated": last_updated},
        )
        return models, last_updated
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "model_performance.json unavailable — returning empty state",
            extra={"path": str(data_path), "error": str(exc)},
        )
        return [], "Unknown"


# ---------------------------------------------------------------------------
# Stage 2 — Calculate Summary
# ---------------------------------------------------------------------------


def _calculate_summary(models: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute portfolio-level summary metrics from model records.

    Args:
        models: Raw model records from _load_data().

    Returns:
        Summary dict with keys: has_data, total_models, healthy_count,
        degraded_count, avg_mape, avg_classification_accuracy, portfolio_status.
    """
    has_data = len(models) > 0
    healthy = sum(1 for m in models if str(m.get("status", "")) in ("healthy", "pass"))
    degraded = len(models) - healthy

    mape_values: list[float] = [float(m["mape"]) for m in models if m.get("mape") is not None]
    acc_values: list[float] = [
        float(v) for m in models if (v := m.get("classification_accuracy") or m.get("accuracy")) is not None
    ]

    avg_mape: float | None = sum(mape_values) / len(mape_values) if mape_values else None
    avg_acc: float | None = sum(acc_values) / len(acc_values) if acc_values else None
    portfolio_status = _derive_portfolio_status(has_data, degraded, len(models))

    return {
        "has_data": has_data,
        "total_models": len(models),
        "healthy_count": healthy,
        "degraded_count": degraded,
        "avg_mape": avg_mape,
        "avg_classification_accuracy": avg_acc,
        "portfolio_status": portfolio_status,
    }


# ---------------------------------------------------------------------------
# Stage 3 — Build Context
# ---------------------------------------------------------------------------


def _derive_portfolio_status(has_data: bool, degraded: int, total: int) -> str:
    """Determine portfolio status label from model health counts."""
    if not has_data:
        return "No Data"
    if degraded == 0:
        return "Good"
    if degraded < total:
        return "Caution"
    return "Action Needed"


def _portfolio_status_class(status: str) -> str:
    """Map portfolio_status string to a CSS status class."""
    return {
        "Good": "status-good",
        "Caution": "status-caution",
        "Action Needed": "status-action",
        "No Data": "status-caution",
    }.get(status, "status-caution")


def _build_summary_cards(summary: dict[str, Any]) -> list[dict[str, str]]:
    """Build the five summary card dicts from the portfolio summary."""
    avg_mape_display = f"{summary['avg_mape']:.1%}" if summary["avg_mape"] is not None else "—"
    avg_acc_display = (
        f"{summary['avg_classification_accuracy']:.1%}" if summary["avg_classification_accuracy"] is not None else "—"
    )
    return [
        {
            "title": "Total Models",
            "value": str(summary["total_models"]),
            "status_class": "status-good" if summary["has_data"] else "status-caution",
            "description": "Models registered in the platform",
        },
        {
            "title": "Healthy",
            "value": str(summary["healthy_count"]),
            "status_class": "status-good" if summary["healthy_count"] > 0 else "status-caution",
            "description": "Models with status = healthy",
        },
        {
            "title": "Degraded",
            "value": str(summary["degraded_count"]),
            "status_class": "status-action" if summary["degraded_count"] > 0 else "status-good",
            "description": "Models requiring attention",
        },
        {
            "title": "Avg MAPE",
            "value": avg_mape_display,
            "status_class": "status-good",
            "description": "Mean absolute percent error (regression models)",
        },
        {
            "title": "Avg Accuracy",
            "value": avg_acc_display,
            "status_class": "status-good",
            "description": "Classification accuracy (classifier models)",
        },
    ]


def _build_model_rows(models: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build validated model detail rows, skipping unknown model names."""
    rows: list[dict[str, str]] = []
    for m in models:
        name = str(m.get("name", m.get("model_name", "")))
        if name not in _VALID_MODEL_NAMES:
            logger.warning(
                "Unknown model name in model_performance.json — skipping row",
                extra={"model_name": name},
            )
            continue

        raw_status = str(m.get("status", "unknown"))
        is_healthy = raw_status in ("healthy", "pass")
        mape_display = f"{float(m['mape']):.1%}" if m.get("mape") is not None else "—"
        acc_val = m.get("classification_accuracy") or m.get("accuracy")
        accuracy_display = f"{float(acc_val):.1%}" if acc_val is not None else "—"
        drift_raw = m.get("drift_score")
        drift_display = f"{float(drift_raw):.3f}" if drift_raw is not None else "—"

        rows.append(
            {
                "model_name": name,
                "algorithm": str(m.get("algorithm", "—")),
                "metric": str(m.get("metric", "—")),
                "mape_display": mape_display,
                "accuracy_display": accuracy_display,
                "drift_score": drift_display,
                "last_trained": str(m.get("last_trained", "—")),
                "status": raw_status,
                "status_class": "status-good" if is_healthy else "status-action",
            }
        )
    return rows


def _build_context(
    summary: dict[str, Any],
    models: list[dict[str, Any]],
    last_updated: str,
) -> dict[str, Any]:
    """
    Build the full Jinja2 template context for the Model Performance dashboard.

    Security: model names are validated against _VALID_MODEL_NAMES before
    being included in model_rows.  Unknown names are logged and skipped.

    Args:
        summary:      Output of _calculate_summary().
        models:       Raw model records from _load_data().
        last_updated: Timestamp string from the data file.

    Returns:
        Context dict ready for render_dashboard().
    """
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#0f172a",
        header_gradient_end="#0f172a",
        include_table_scroll=True,
        include_expandable_rows=False,
        include_glossary=True,
    )
    portfolio_sc = _portfolio_status_class(summary["portfolio_status"])
    summary_cards = _build_summary_cards(summary)
    model_rows = _build_model_rows(models)

    return {
        "framework_css": framework_css,  # REQUIRED — do not remove
        "framework_js": framework_js,  # REQUIRED — do not remove
        "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "last_updated": last_updated,
        "has_data": summary["has_data"],
        "portfolio_status": summary["portfolio_status"],
        "portfolio_status_class": portfolio_sc,
        "summary_cards": summary_cards,
        "model_rows": model_rows,
        "breadcrumbs": [
            {"label": "Observatory", "url": "../launcher.html"},
            {"label": "Model Performance", "url": "#"},
        ],
    }


# ---------------------------------------------------------------------------
# Stage 4 — Render (main entry point)
# ---------------------------------------------------------------------------


def generate_model_performance_dashboard(
    output_dir: Path | None = None,
) -> str:
    """
    Generate the Model Performance dashboard HTML.

    Orchestrates the 4-stage pipeline:
        [1/4] Load model performance records
        [2/4] Calculate portfolio-level summary
        [3/4] Build template context (framework CSS/JS, summary cards, model rows)
        [4/4] Render Jinja2 template → HTML string

    Data loading is graceful — all stages return empty/zero defaults when
    data/model_performance.json is empty or missing.

    Args:
        output_dir: Optional directory to write the generated HTML file.
            When provided the file is written as ``model_performance_dashboard.html``
            inside this directory.

    Returns:
        Generated HTML string.
    """
    logger.info("Generating Model Performance dashboard")

    # [1/4] Load data
    logger.info("Loading model performance data")
    models, last_updated = _load_data(_MODEL_PERFORMANCE_PATH)

    logger.info(
        "Data loaded",
        extra={"model_count": len(models), "last_updated": last_updated},
    )

    # [2/4] Calculate summary
    logger.info("Calculating portfolio summary")
    summary = _calculate_summary(models)

    logger.info(
        "Summary calculated",
        extra={
            "portfolio_status": summary["portfolio_status"],
            "healthy": summary["healthy_count"],
            "degraded": summary["degraded_count"],
        },
    )

    # [3/4] Build context
    logger.info("Building template context")
    context = _build_context(summary, models, last_updated)

    # [4/4] Render
    logger.info("Rendering HTML template")
    html = render_dashboard("dashboards/model_performance_dashboard.html", context)

    # Optionally write to disk
    if output_dir is not None:
        output_path = output_dir / "model_performance_dashboard.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info(
            "Model performance dashboard written to file",
            extra={"path": str(output_path)},
        )

    logger.info(
        "Model Performance dashboard generated",
        extra={"html_size": len(html)},
    )
    return html


# ---------------------------------------------------------------------------
# __main__ entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Generate the Model Performance dashboard and write to the default output path."""
    logger.info("Model Performance Dashboard — running standalone")
    try:
        output_dir = OUTPUT_PATH.parent
        html = generate_model_performance_dashboard(output_dir=output_dir)

        if OUTPUT_PATH.exists():
            file_size = OUTPUT_PATH.stat().st_size
            logger.info(
                "Dashboard generated successfully",
                extra={
                    "output": str(OUTPUT_PATH),
                    "file_size": file_size,
                    "html_size": len(html),
                },
            )
        else:
            logger.info(
                "Dashboard HTML generated (in-memory only)",
                extra={"html_size": len(html)},
            )

    except OSError as exc:
        logger.error(
            "Failed to write model performance dashboard",
            extra={"error": str(exc)},
        )
        raise


if __name__ == "__main__":
    main()
