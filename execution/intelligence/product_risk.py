"""
Product Risk v1 — Per-product risk scoring from active alert data.

PROVISIONAL: Derived from alert severity counts in the active_alerts list
returned by build_trends_context(). Equal-weight severity scoring:
    critical -> 3 points
    warn     -> 1 point
    medium   -> 1 point

Products sorted descending by score, then alphabetically for ties.
Metrics with missing/empty project_name are skipped.
Excluded from response: products with score == 0.

Public entry point: build_product_risk_response(alerts) -> dict
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

_SEVERITY_POINTS: dict[str, int] = {
    "critical": 3,
    "warn": 1,
    "medium": 1,
}


def build_product_risk_response(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute per-product risk scores from active alert data.

    Args:
        alerts: The active_alerts list from build_trends_context().
                Each entry must contain project_name, dashboard, severity.

    Returns:
        Dict with generated_at, total_alerts, products (sorted by score desc).
        Always returns a valid payload — never raises for well-formed input (list[dict]).
    """
    if not alerts:
        alerts = []
    product_scores: dict[str, int] = {}
    product_counts: dict[str, dict[str, int]] = {}
    product_domains: dict[str, set[str]] = {}
    valid_alert_count = 0

    for alert in alerts:
        project_name = alert.get("project_name") or ""
        if not project_name:
            continue

        valid_alert_count += 1
        severity = alert.get("severity", "")
        dashboard = alert.get("dashboard", "")

        if project_name not in product_scores:
            product_scores[project_name] = 0
            product_counts[project_name] = {"critical": 0, "warn": 0, "medium": 0}
            product_domains[project_name] = set()

        points = _SEVERITY_POINTS.get(severity, 0)
        product_scores[project_name] += points
        if severity in product_counts[project_name]:
            product_counts[project_name][severity] += 1
        if dashboard:
            product_domains[project_name].add(dashboard)

    products = []
    for name, score in product_scores.items():
        if score == 0:
            continue
        counts = product_counts[name]
        products.append(
            {
                "product": name,
                "score": score,
                "critical": counts["critical"],
                "warn": counts["warn"],
                "medium": counts["medium"],
                "domains": sorted(product_domains[name]),
            }
        )

    def _sort_key(p: dict[str, Any]) -> tuple[int, str]:
        return (-int(p["score"]), str(p["product"]))

    products.sort(key=_sort_key)

    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "total_alerts": valid_alert_count,
        "products": products,
    }
