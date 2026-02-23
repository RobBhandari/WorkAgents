"""
Security Dashboard Helper Functions

Data calculation helpers extracted from security_enhanced.py to keep it
under the 500-line architectural limit.

Contains: grouping, counting, history patching, and summary calculation.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from execution.collectors.armorcode_vulnerability_loader import VulnerabilityDetail
from execution.core import get_logger
from execution.domain.security import SOURCE_BUCKET_MAP, SecurityMetrics

logger = get_logger(__name__)

# Inverse of SOURCE_BUCKET_MAP: bucket → list of source tool names
BUCKET_SOURCE_MAP: dict[str, list[str]] = {}
for _src, _bucket in SOURCE_BUCKET_MAP.items():
    BUCKET_SOURCE_MAP.setdefault(_bucket, []).append(_src)


def _group_findings_by_product(
    vulnerabilities: list[VulnerabilityDetail],
) -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
    """
    Group AQL findings into per-product count structures in a single O(n) pass.

    Replaces 8+ separate API calls (2 AQL severity counts + 6 AQL bucket counts).
    All three output structures are built simultaneously from the same record list.

    Returns:
        accurate_totals:          {product: {"critical": int, "high": int, "total": int}}
        bucket_counts_by_product: {product: {bucket: {"total": int, "critical": int, "high": int}}}
        aql_by_product:           {product: {"critical": int, "high": int}}
    """
    _accurate: dict[str, dict] = defaultdict(lambda: {"critical": 0, "high": 0, "total": 0})
    _buckets: dict[str, dict] = defaultdict(dict)
    _aql: dict[str, dict] = defaultdict(lambda: {"critical": 0, "high": 0})

    for vuln in vulnerabilities:
        product = vuln.product
        if not product:
            continue

        sev = (vuln.severity or "").upper()
        is_crit = sev == "CRITICAL"
        is_high = sev == "HIGH"

        _accurate[product]["total"] += 1
        if is_crit:
            _accurate[product]["critical"] += 1
            _aql[product]["critical"] += 1
        elif is_high:
            _accurate[product]["high"] += 1
            _aql[product]["high"] += 1

        bucket = SOURCE_BUCKET_MAP.get(vuln.source or "", "Other")
        product_buckets = _buckets[product]
        if bucket not in product_buckets:
            product_buckets[bucket] = {"total": 0, "critical": 0, "high": 0}
        product_buckets[bucket]["total"] += 1
        if is_crit:
            product_buckets[bucket]["critical"] += 1
        elif is_high:
            product_buckets[bucket]["high"] += 1

    return dict(_accurate), dict(_buckets), dict(_aql)


def _metrics_from_aql_counts(aql_by_product: dict[str, dict]) -> dict[str, SecurityMetrics]:
    """
    Build SecurityMetrics domain objects from AQL per-product counts.

    Medium/Low are always 0 since fetch_findings_aql() filters to Critical+High only.
    total_vulnerabilities == critical + high.
    """
    return {
        product: SecurityMetrics(
            timestamp=datetime.now(),
            project=product,
            total_vulnerabilities=counts.get("critical", 0) + counts.get("high", 0),
            critical=counts.get("critical", 0),
            high=counts.get("high", 0),
            medium=0,
            low=0,
        )
        for product, counts in aql_by_product.items()
    }


def _update_history_current_total(history_path: Path, critical: int, high: int) -> None:
    """Patch the latest history entry with the live-computed accurate total."""
    if not history_path.exists():
        return
    try:
        d = json.loads(history_path.read_text(encoding="utf-8"))
        if not d.get("weeks"):
            return

        new_total = critical + high

        # Sanity check: reject implausibly low counts to prevent transient API failures
        # corrupting the history (same issue as the 646 transient count from 2026-02-19)
        if len(d["weeks"]) >= 2:
            prev_total = d["weeks"][-2].get("metrics", {}).get("current_total", 0)
            if prev_total > 2000 and new_total < prev_total * 0.3:
                logger.warning(
                    "Security history patch REJECTED - count looks like transient API failure",
                    extra={"new_total": new_total, "prev_total": prev_total, "threshold": prev_total * 0.3},
                )
                return

        m = d["weeks"][-1].setdefault("metrics", {})
        m["current_total"] = new_total
        m.setdefault("severity_breakdown", {}).update({"critical": critical, "high": high, "total": new_total})
        history_path.write_text(json.dumps(d, indent=2), encoding="utf-8")
        logger.info(
            "Security history patched with live count",
            extra={"critical": critical, "high": high, "total": new_total},
        )
    except Exception as e:
        logger.warning("History patch skipped: %s", e)


def _patch_history_bucket_breakdown(
    history_path: Path,
    bucket_counts_by_product: dict[str, dict],
) -> None:
    """
    Patch the latest history entry with Code+Cloud and Infrastructure totals.

    Adds 'bucket_breakdown' key to weeks[-1].metrics:
        {"code_cloud": {"critical": int, "high": int, "total": int},
         "infrastructure": {"critical": int, "high": int, "total": int}}

    Historical weeks without this key are left untouched (callers handle gracefully).
    """
    if not history_path.exists():
        return
    try:
        d = json.loads(history_path.read_text(encoding="utf-8"))
        if not d.get("weeks"):
            return

        cc_critical, cc_high = 0, 0
        infra_critical, infra_high = 0, 0
        for product_buckets in bucket_counts_by_product.values():
            for bucket_name, counts in product_buckets.items():
                if bucket_name in ("CODE", "CLOUD"):
                    cc_critical += counts.get("critical", 0)
                    cc_high += counts.get("high", 0)
                elif bucket_name == "INFRASTRUCTURE":
                    infra_critical += counts.get("critical", 0)
                    infra_high += counts.get("high", 0)

        m = d["weeks"][-1].setdefault("metrics", {})
        m["bucket_breakdown"] = {
            "code_cloud": {
                "critical": cc_critical,
                "high": cc_high,
                "total": cc_critical + cc_high,
            },
            "infrastructure": {
                "critical": infra_critical,
                "high": infra_high,
                "total": infra_critical + infra_high,
            },
        }
        history_path.write_text(json.dumps(d, indent=2), encoding="utf-8")
        logger.info(
            "Security history patched with bucket breakdown",
            extra={
                "code_cloud_total": cc_critical + cc_high,
                "infra_total": infra_critical + infra_high,
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Bucket breakdown patch skipped: %s", e)


def _calculate_summary(metrics_by_product: dict) -> dict:
    """
    Stage 2: Calculate summary statistics.

    Args:
        metrics_by_product: Dict of product name -> SecurityMetrics

    Returns:
        Dictionary with summary statistics
    """
    total_vulns = sum(m.total_vulnerabilities for m in metrics_by_product.values())
    total_critical = sum(m.critical for m in metrics_by_product.values())
    total_high = sum(m.high for m in metrics_by_product.values())
    total_medium = sum(m.medium for m in metrics_by_product.values())

    products_with_vulns = sum(1 for m in metrics_by_product.values() if m.total_vulnerabilities > 0)

    critical_high_total = total_critical + total_high

    if total_critical == 0 and total_high <= 10:
        status = "good"
        status_text = "Healthy"
    elif total_critical <= 5:
        status = "caution"
        status_text = "Caution"
    else:
        status = "action"
        status_text = "Action Needed"

    return {
        "total_vulns": total_vulns,
        "total_critical": total_critical,
        "total_high": total_high,
        "total_medium": total_medium,
        "critical_high_total": critical_high_total,
        "products_with_vulns": products_with_vulns,
        "product_count": len(metrics_by_product),
        "status": status,
        "status_text": status_text,
    }
