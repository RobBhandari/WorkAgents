#!/usr/bin/env python3
"""
Engineering Health Dashboard Generator

Predictive analytics dashboard combining per-product:
  - 4-week bug count forecast with confidence intervals
  - Security vulnerability posture score
  - Composite 0-100 health score (Healthy / At Risk / Critical)
  - Anomaly detection: critical banner + per-product warning flags

Reads from:
  .tmp/observatory/quality_history.json
  .tmp/observatory/security_history.json
  .tmp/observatory/exploitable_history.json
  data/security_targets.json

Writes to: .tmp/observatory/dashboards/health_dashboard.html

Usage:
    python -m execution.dashboards.health_dashboard
"""

import json
from datetime import datetime
from pathlib import Path

from execution.core import get_logger
from execution.dashboards.components.cards import metric_card
from execution.dashboards.renderer import render_dashboard
from execution.domain.health import OrgHealthSummary, ProductHealth
from execution.framework import get_dashboard_framework
from execution.ml.health_scorer import HealthScorer

logger = get_logger(__name__)

OUTPUT_PATH = Path(".tmp/observatory/dashboards/health_dashboard.html")
_NAME_MAPPING_FILE = Path(".product_mapping.json")


def _load_name_mapping() -> dict[str, str]:
    """Load generic→real product name mapping from .product_mapping.json (if present)."""
    if _NAME_MAPPING_FILE.exists():
        return dict(json.loads(_NAME_MAPPING_FILE.read_text(encoding="utf-8")))
    return {}


def _apply_name_mapping(
    products: list[ProductHealth],
    summary: OrgHealthSummary,
    mapping: dict[str, str],
) -> tuple[list[ProductHealth], OrgHealthSummary]:
    """Translate generic product names (Product A …) to real names in-place."""
    if not mapping:
        return products, summary

    for p in products:
        p.product_name = mapping.get(p.product_name, p.product_name)
        if p.anomaly_description:
            for generic, real in mapping.items():
                p.anomaly_description = p.anomaly_description.replace(generic, real)

    summary.critical_anomalies = [mapping.get(n, n) for n in summary.critical_anomalies]
    summary.warning_anomalies = [mapping.get(n, n) for n in summary.warning_anomalies]
    return products, summary


# ---------------------------------------------------------------------------
# Stage 1 — Load Data
# ---------------------------------------------------------------------------


def _load_data() -> tuple[list[ProductHealth], OrgHealthSummary]:
    """
    Run HealthScorer and translate product names to real names.

    Returns:
        Tuple of (list[ProductHealth] sorted worst-first, OrgHealthSummary)
    """
    logger.info("Running health scorer...")
    scorer = HealthScorer()
    products, summary = scorer.score_all_products()

    mapping = _load_name_mapping()
    if mapping:
        products, summary = _apply_name_mapping(products, summary, mapping)
        logger.info("Product names translated to real names", extra={"mapped": len(mapping)})
    else:
        logger.info("No .product_mapping.json found - showing generic names")

    logger.info(
        "Health scoring done",
        extra={"products": len(products), "overall_score": summary.overall_score},
    )
    return products, summary


# ---------------------------------------------------------------------------
# Stage 2 — Calculate Summary
# ---------------------------------------------------------------------------


def _calculate_display_summary(products: list[ProductHealth], org: OrgHealthSummary) -> dict:
    """
    Build display-level aggregates for summary cards and anomaly banner.

    Returns:
        Dict with values ready for template rendering
    """
    total = org.total_products or 1  # Avoid division by zero in template

    # Score colour class for the org score card
    if org.overall_score >= 70:
        score_class = "rag-green"
    elif org.overall_score >= 40:
        score_class = "rag-amber"
    else:
        score_class = "rag-red"

    # Security trajectory → colour
    traj_class = {
        "On Track": "rag-green",
        "At Risk": "rag-amber",
        "Behind": "rag-red",
    }.get(org.org_security_trajectory, "rag-amber")

    # Shortfall text
    shortfall = org.security_predicted_shortfall
    if shortfall <= 0:
        shortfall_text = f"{abs(shortfall)} ahead of target"
    else:
        shortfall_text = f"{shortfall} above target"

    return {
        "score_class": score_class,
        "traj_class": traj_class,
        "shortfall_text": shortfall_text,
        "total_products": total,
        "has_critical_anomaly": org.has_critical_anomaly,
        "critical_anomaly_names": ", ".join(org.critical_anomalies),
        "warning_anomaly_names": ", ".join(org.warning_anomalies),
    }


# ---------------------------------------------------------------------------
# Stage 3 — Build Context
# ---------------------------------------------------------------------------


def _build_summary_cards(org: OrgHealthSummary, display: dict) -> list[str]:
    """Generate four top-level summary cards."""
    healthy_pct = round(org.healthy_count / display["total_products"] * 100) if display["total_products"] else 0

    cards = [
        metric_card(
            title="Org Health Score",
            value=str(round(org.overall_score)),
            subtitle=f"{org.overall_status} • median across {org.total_products} products",
            css_class=display["score_class"],
        ),
        metric_card(
            title="Healthy Products",
            value=f"{org.healthy_count}/{org.total_products}",
            subtitle=f"{healthy_pct}% of portfolio scoring ≥ 70",
            css_class="rag-green" if healthy_pct >= 60 else "rag-amber",
        ),
        metric_card(
            title="Active Anomalies",
            value=str(len(org.critical_anomalies) + len(org.warning_anomalies)),
            subtitle=f"{len(org.critical_anomalies)} critical, {len(org.warning_anomalies)} warning this week",
            css_class=(
                "rag-red" if org.has_critical_anomaly else ("rag-amber" if org.warning_anomalies else "rag-green")
            ),
        ),
        metric_card(
            title="Target Probability",
            value=f"{org.security_target_probability:.0f}%",
            subtitle=f"P(hit June 30 security target) • {org.org_security_trajectory}",
            css_class=display["traj_class"],
        ),
    ]
    return cards


def _build_product_rows(products: list[ProductHealth]) -> list[dict]:
    """Build structured row dicts for the product health table."""
    rows = []
    for p in products:
        # Anomaly badge text
        if p.anomaly_severity == "critical":
            anomaly_badge = '<span class="status-badge status-action">⚠ Critical Spike</span>'
        elif p.anomaly_severity == "warning":
            anomaly_badge = '<span class="status-badge status-caution">⚠ Warning</span>'
        else:
            anomaly_badge = '<span class="status-badge status-good">Normal</span>'

        # Forecast text
        if p.bug_forecast_4wk is not None:
            if p.bug_ci_lower is not None and p.bug_ci_upper is not None:
                forecast_text = f"{p.bug_forecast_4wk} (CI: {p.bug_ci_lower}–{p.bug_ci_upper})"
            else:
                forecast_text = str(p.bug_forecast_4wk)
        else:
            forecast_text = "—"

        # Security detail: exploitable vulns
        exploit_text = str(p.exploitable_total) if p.exploitable_total > 0 else "0 (clean)"

        rows.append(
            {
                "product_name": p.product_name,
                "health_score": round(p.health_score),
                "health_status": p.health_status,
                "status_class": p.status_class,
                "bug_score": round(p.bug_score, 1),
                "security_score": round(p.security_score, 1),
                "current_bugs": p.current_bug_count,
                "bug_trend": p.bug_trend,
                "trend_arrow": p.trend_arrow,
                "trend_class": p.trend_class,
                "forecast_4wk": forecast_text,
                "anomaly_badge": anomaly_badge,
                "has_anomaly": p.has_anomaly,
                "anomaly_description": p.anomaly_description or "",
                "exploitable_total": exploit_text,
            }
        )
    return rows


def _build_context(products: list[ProductHealth], org: OrgHealthSummary) -> dict:
    """
    Stage 3: Assemble complete template context.

    Returns:
        Dict with all variables required by health_dashboard.html
    """
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#667eea",
        header_gradient_end="#764ba2",
        include_table_scroll=True,
        include_expandable_rows=True,
        include_glossary=True,
    )

    display = _calculate_display_summary(products, org)
    summary_cards = _build_summary_cards(org, display)
    product_rows = _build_product_rows(products)

    # Org security detail (for footer/callout section)
    shortfall = org.security_predicted_shortfall
    if shortfall <= 0:
        security_callout = (
            f"Security forecast: predicted {org.security_predicted_count_june30} vulns on June 30 "
            f"({abs(shortfall)} below target of {org.security_target_count}). "
            f"P(on track) = {org.security_target_probability:.0f}%."
        )
    else:
        security_callout = (
            f"Security forecast: predicted {org.security_predicted_count_june30} vulns on June 30 "
            f"({shortfall} above target of {org.security_target_count}). "
            f"P(on track) = {org.security_target_probability:.0f}%."
        )

    return {
        "framework_css": framework_css,
        "framework_js": framework_js,
        "summary_cards": summary_cards,
        "product_rows": product_rows,
        "org": {
            "overall_score": round(org.overall_score),
            "overall_status": org.overall_status,
            "healthy_count": org.healthy_count,
            "at_risk_count": org.at_risk_count,
            "critical_count": org.critical_count,
            "total_products": org.total_products,
            "has_critical_anomaly": org.has_critical_anomaly,
            "critical_anomaly_names": display["critical_anomaly_names"],
            "warning_anomaly_names": display["warning_anomaly_names"],
            "security_target_probability": org.security_target_probability,
            "org_security_trajectory": org.org_security_trajectory,
            "security_callout": security_callout,
            "shortfall_text": display["shortfall_text"],
        },
        "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ---------------------------------------------------------------------------
# Stage 4 — Render & Write
# ---------------------------------------------------------------------------


def generate_health_dashboard(output_path: Path | None = None) -> str:
    """
    Full 4-stage pipeline: score → summarise → build context → render HTML.

    Args:
        output_path: Where to write the dashboard HTML (default: OUTPUT_PATH)

    Returns:
        Rendered HTML string
    """
    out = output_path or OUTPUT_PATH

    # Stage 1
    products, org_summary = _load_data()

    # Stage 2+3
    context = _build_context(products, org_summary)

    # Stage 4
    html = render_dashboard("dashboards/health_dashboard.html", context)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    logger.info("Health dashboard written", extra={"path": str(out), "size_kb": round(len(html) / 1024, 1)})
    return html


if __name__ == "__main__":
    from execution.core import setup_logging

    setup_logging(level="INFO", json_output=False)
    generate_health_dashboard()
