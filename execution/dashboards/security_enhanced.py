#!/usr/bin/env python3
"""
Enhanced Security Dashboard Generator

Complete security dashboard with:
- Main summary table with VIEW buttons for drill-down
- Individual product detail pages
- Aging heatmap per product
- Live ArmorCode API queries
- Search, filter, and Excel export

This replaces the archived generate_security_dashboard_original.py with a
clean, maintainable implementation using modern architecture.

Usage:
    from execution.dashboards.security_enhanced import generate_security_dashboard_enhanced
    from pathlib import Path

    output_dir = Path('.tmp/observatory/dashboards')
    generate_security_dashboard_enhanced(output_dir)
"""

import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from execution.collectors.armorcode_vulnerability_loader import (
    ArmorCodeVulnerabilityLoader,
    VulnerabilityDetail,
)
from execution.core import get_logger
from execution.dashboards.components.cards import summary_card
from execution.dashboards.renderer import render_dashboard
from execution.domain.security import BUCKET_ORDER, SOURCE_BUCKET_MAP, SecurityMetrics
from execution.framework import get_dashboard_framework
from execution.secure_config import get_config
from execution.utils.error_handling import log_and_return_default

logger = get_logger(__name__)


def _load_baseline_products() -> list[str]:
    """
    Load product names from ArmorCode baseline file.

    Returns:
        List of product names to track

    Raises:
        FileNotFoundError: If baseline file doesn't exist
        ValueError: If baseline has invalid format
    """
    # Try data/ folder first (CI/CD), then .tmp/ (local dev)
    baseline_paths = [
        Path("data/armorcode_baseline.json"),
        Path(".tmp/armorcode_baseline.json"),
    ]

    for baseline_path in baseline_paths:
        if baseline_path.exists():
            logger.info(f"Loading baseline from {baseline_path}")
            with open(baseline_path, encoding="utf-8") as f:
                baseline = json.load(f)

            products: list[str] = baseline.get("products", [])
            if not products:
                raise ValueError(f"No products found in baseline: {baseline_path}")

            logger.info(f"Tracking {len(products)} products from baseline")
            return products

    raise FileNotFoundError(
        "ArmorCode baseline not found. Expected:\n"
        "  - data/armorcode_baseline.json (CI/CD)\n"
        "  - .tmp/armorcode_baseline.json (local dev)\n"
        "Run: python execution/armorcode_baseline.py"
    )


def _convert_vulnerabilities_to_metrics(
    vulnerabilities: list[VulnerabilityDetail],
) -> dict[str, SecurityMetrics]:
    """
    Convert list of vulnerabilities to SecurityMetrics by product.

    Args:
        vulnerabilities: List of vulnerability details from ArmorCode API

    Returns:
        Dictionary mapping product name to SecurityMetrics
    """
    # Group vulnerabilities by product and count by severity
    product_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0}
    )

    for vuln in vulnerabilities:
        product = vuln.product
        severity = vuln.severity.upper()

        product_counts[product]["total"] += 1
        if severity == "CRITICAL":
            product_counts[product]["critical"] += 1
        elif severity == "HIGH":
            product_counts[product]["high"] += 1
        elif severity == "MEDIUM":
            product_counts[product]["medium"] += 1
        elif severity == "LOW":
            product_counts[product]["low"] += 1

    # Convert to SecurityMetrics domain models
    metrics_by_product = {}
    for product_name, counts in product_counts.items():
        metrics = SecurityMetrics(
            timestamp=datetime.now(),
            project=product_name,
            total_vulnerabilities=counts["total"],
            critical=counts["critical"],
            high=counts["high"],
            medium=counts["medium"],
            low=counts["low"],
        )
        metrics_by_product[product_name] = metrics

    return metrics_by_product


def generate_security_dashboard_enhanced(output_dir: Path | None = None) -> tuple[str, int]:
    """
    Generate enhanced security dashboard with expandable rows.

    Args:
        output_dir: Directory to write HTML files (defaults to .tmp/observatory/dashboards)

    Returns:
        Tuple of (main_dashboard_html, 0) - detail pages no longer generated

    Example:
        html, _ = generate_security_dashboard_enhanced()
        logger.info("Dashboard generated with expandable rows")
    """
    if output_dir is None:
        output_dir = Path(".tmp/observatory/dashboards")

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Enhanced Security Dashboard Generator")

    # Step 1: Query ArmorCode API directly for fresh Production-only data
    logger.info("Loading product list from baseline")
    try:
        products = _load_baseline_products()
    except FileNotFoundError as e:
        logger.warning(
            "ArmorCode baseline not found, returning empty result",
            extra={
                "error_type": "Baseline loading",
                "exception_class": e.__class__.__name__,
                "context": {"output_dir": str(output_dir)},
                "default_value": "('', 0)",
            },
        )
        logger.info("Run: python execution/armorcode_baseline.py")
        return "", 0

    logger.info("Querying ArmorCode API (hybrid: capped detail + accurate counts)")
    vuln_loader = ArmorCodeVulnerabilityLoader()
    vulnerabilities, bucket_counts_by_product, accurate_totals = vuln_loader.load_vulnerabilities_hybrid(
        products, filter_environment=True, max_per_product=50
    )
    logger.info(f"Retrieved {len(vulnerabilities)} vulnerability details (capped at 50/product for display)")

    metrics_by_product = _convert_vulnerabilities_to_metrics(vulnerabilities)

    # Ensure all baseline products appear (even those with 0 Critical/High)
    for product_name in products:
        if product_name not in metrics_by_product:
            metrics_by_product[product_name] = SecurityMetrics(
                timestamp=datetime.now(),
                project=product_name,
                total_vulnerabilities=0,
                critical=0,
                high=0,
                medium=0,
                low=0,
            )
    logger.info("ArmorCode data loaded", extra={"product_count": len(metrics_by_product)})

    vulns_by_product = vuln_loader.group_by_product(vulnerabilities)

    # Override accurate_totals with Production-only AQL counts (2 API calls).
    # This ensures the header cards and history patch match target_dashboard.py and
    # show only Production environment findings — consistent with what teams care about.
    hierarchy = get_config().get_optional_env("ARMORCODE_HIERARCHY")
    if hierarchy:
        crit_aql = vuln_loader.count_by_severity_aql("Critical", hierarchy, environment="Production")
        high_aql = vuln_loader.count_by_severity_aql("High", hierarchy, environment="Production")
        prod_c = sum(crit_aql.values())
        prod_h = sum(high_aql.values())
        accurate_totals = {"_prod": {"critical": prod_c, "high": prod_h, "total": prod_c + prod_h}}
        logger.info(
            "Using Production-only AQL totals",
            extra={"critical": prod_c, "high": prod_h, "total": prod_c + prod_h},
        )
    else:
        logger.warning("ARMORCODE_HIERARCHY not set — totals include all environments")

    # Compute totals for header summary cards and history patch
    acc_c = sum(t.get("critical", 0) for t in accurate_totals.values())
    acc_h = sum(t.get("high", 0) for t in accurate_totals.values())

    main_html = _generate_main_dashboard_html(
        metrics_by_product, vulns_by_product, bucket_counts_by_product, accurate_totals
    )

    # Patch history JSON with the same value shown on the dashboard
    _update_history_current_total(Path(".tmp/observatory/security_history.json"), acc_c, acc_h)

    main_file = output_dir / "security_dashboard.html"
    main_file.write_text(main_html, encoding="utf-8")
    logger.info("Security dashboard written", extra={"path": str(main_file)})

    return main_html, 0  # No detail pages generated


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


def _generate_main_dashboard_html(
    metrics_by_product: dict,
    vulns_by_product: dict,
    bucket_counts_by_product: dict,
    accurate_totals: dict,
) -> str:
    """Generate main dashboard HTML using 4-stage pipeline."""
    summary_stats = _calculate_summary(metrics_by_product)
    context = _build_context(
        metrics_by_product, vulns_by_product, summary_stats, bucket_counts_by_product, accurate_totals
    )
    return render_dashboard("dashboards/security_dashboard.html", context)


def _calculate_summary(metrics_by_product: dict) -> dict:
    """
    Stage 2: Calculate summary statistics.

    Args:
        metrics_by_product: Dict of product name -> SecurityMetrics

    Returns:
        Dictionary with summary statistics
    """
    # Calculate totals
    total_vulns = sum(m.total_vulnerabilities for m in metrics_by_product.values())
    total_critical = sum(m.critical for m in metrics_by_product.values())
    total_high = sum(m.high for m in metrics_by_product.values())
    total_medium = sum(m.medium for m in metrics_by_product.values())

    # Count products with vulnerabilities
    products_with_vulns = sum(1 for m in metrics_by_product.values() if m.total_vulnerabilities > 0)

    # Calculate critical + high total
    critical_high_total = total_critical + total_high

    # Overall status determination
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


def _build_context(
    metrics_by_product: dict,
    vulns_by_product: dict,
    summary_stats: dict,
    bucket_counts_by_product: dict,
    accurate_totals: dict,
) -> dict:
    """Stage 3: Build template context."""
    # Get framework CSS/JS (enable expandable rows)
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#667eea",
        header_gradient_end="#764ba2",
        include_table_scroll=True,
        include_expandable_rows=True,
        include_glossary=False,
    )

    # Header totals from accurate_totals (same value used for history patch → consistent across dashboards)
    acc_critical = sum(t.get("critical", 0) for t in accurate_totals.values())
    acc_high = sum(t.get("high", 0) for t in accurate_totals.values())
    summary_cards = [
        summary_card("Priority Findings", str(acc_critical + acc_high)),
        summary_card("Critical", str(acc_critical), css_class="critical"),
        summary_card("High", str(acc_high), css_class="high"),
        summary_card("Products", str(summary_stats["product_count"])),
    ]

    # Build product rows with expandable content
    products = []
    for product_name, metrics in sorted(metrics_by_product.items()):
        # Determine status using standard status classes
        if metrics.critical >= 5:
            status = "Critical"
            status_class = "action"
            status_priority = 0  # Highest priority
        elif metrics.critical > 0:
            status = "High Risk"
            status_class = "caution"
            status_priority = 1
        elif metrics.high >= 10:
            status = "Monitor"
            status_class = "caution"
            status_priority = 2
        else:
            status = "OK"
            status_class = "good"
            status_priority = 3  # Lowest priority

        vulns = vulns_by_product.get(product_name, [])
        product_bucket_counts = bucket_counts_by_product.get(product_name)

        # Use accurate counts from API when fetched set is truncated (>500 total)
        if product_bucket_counts:
            display_critical = sum(b["critical"] for b in product_bucket_counts.values())
            display_high = sum(b["high"] for b in product_bucket_counts.values())
        else:
            display_critical = metrics.critical
            display_high = metrics.high

        expanded_html = _generate_bucket_expanded_content(vulns, bucket_counts=product_bucket_counts)

        products.append(
            {
                "name": product_name,
                "total": display_critical + display_high,
                "critical": display_critical,
                "high": display_high,
                "medium": metrics.medium,
                "status": status,
                "status_class": status_class,
                "status_priority": status_priority,
                "expanded_html": expanded_html,
            }
        )

    # Sort products by status priority (Critical→High Risk→Monitor→OK),
    # then by critical count (descending), then by product name
    products.sort(key=lambda p: (p["status_priority"], -p["critical"], p["name"]))

    return {
        "framework_css": framework_css,
        "framework_js": framework_js,
        "summary_cards": summary_cards,
        "products": products,
        "show_glossary": False,
    }


def _sanitize_filename(product_name: str) -> str:
    """Convert product name to safe filename"""
    # Replace spaces and special characters
    safe_name = product_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    # Remove other problematic characters
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in ("_", "-"))
    return safe_name


def _escape_html(text: str) -> str:
    """Escape HTML special characters"""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _generate_bucket_expanded_content(
    vulnerabilities: list,
    bucket_counts: dict | None = None,
) -> str:
    """
    Generate expanded row HTML: inline expandable bucket rows within a single table.

    Args:
        vulnerabilities: List of VulnerabilityDetail objects for this product (may be capped at 50)
        bucket_counts: Accurate {bucket: {total, critical, high}} from API count queries.
                      When None, counts are derived from the fetched vulnerabilities list.
    """
    filtered = [v for v in vulnerabilities if v.severity.upper() in ("CRITICAL", "HIGH")]

    # Group fetched vulns by bucket
    fetched_buckets: dict[str, list] = {b: [] for b in BUCKET_ORDER}
    for vuln in filtered:
        fetched_buckets[SOURCE_BUCKET_MAP.get(vuln.source or "", "Other")].append(vuln)

    # Determine which buckets are active: from accurate counts if available, else from fetched
    active_buckets = set(bucket_counts.keys()) if bucket_counts else {b for b, v in fetched_buckets.items() if v}

    thead = (
        "<thead><tr>"
        '<th class="sortable" onclick="sortBucketTable(this)">Severity <span class="sort-indicator"></span></th>'
        '<th class="sortable" onclick="sortBucketTable(this)">Source <span class="sort-indicator"></span></th>'
        '<th class="sortable" onclick="sortBucketTable(this)">Status <span class="sort-indicator"></span></th>'
        '<th class="sortable" data-type="number" onclick="sortBucketTable(this)">Age (Days) <span class="sort-indicator"></span></th>'
        '<th class="sortable" onclick="sortBucketTable(this)">Title <span class="sort-indicator"></span></th>'
        '<th class="sortable" onclick="sortBucketTable(this)">ID <span class="sort-indicator"></span></th>'
        "</tr></thead>"
    )

    table_body = ""
    for bucket_name in BUCKET_ORDER:
        if bucket_name not in active_buckets:
            continue

        vulns = fetched_buckets[bucket_name]
        fetched_count = len(vulns)

        # Use accurate counts if provided, else derive from fetched
        if bucket_counts and bucket_name in bucket_counts:
            acc = bucket_counts[bucket_name]
            total, critical, high = acc["total"], acc["critical"], acc["high"]
        else:
            total = fetched_count
            critical = sum(1 for v in vulns if v.severity.upper() == "CRITICAL")
            high = total - critical

        crit_cls = ' class="critical"' if critical > 0 else ""
        high_cls = ' class="high"' if high > 0 else ""

        # No fetched detail for this bucket (truncated beyond 50-record limit)
        if fetched_count == 0:
            table_body += (
                f'<tr class="bucket-row expandable" onclick="toggleBucketDetail(this)">'
                f'<td><span class="bucket-arrow">&#9658;</span> <strong>{bucket_name}</strong></td>'
                f"<td>{total}</td><td{crit_cls}>{critical}</td><td{high_cls}>{high}</td>"
                f'</tr><tr class="bucket-detail-row" style="display:none;">'
                f'<td colspan="4" class="vuln-table-note">'
                f"&#9888; Detail unavailable &mdash; findings are beyond the 50-result limit.</td></tr>"
            )
            continue

        # Truncation note when fetched < accurate total
        truncation_note = ""
        if fetched_count < total:
            truncation_note = (
                f'<p class="vuln-table-note">&#9888; Top {fetched_count:,} of {total:,} findings shown.</p>'
            )

        rows = []
        for idx, v in enumerate(vulns):
            sev = v.severity.lower()
            rows.append(
                f'<tr data-severity="{sev}" data-idx="{idx}">'
                f'<td><span class="badge badge-{sev}">{_escape_html(v.severity)}</span></td>'
                f'<td class="vuln-source">{_escape_html(v.source or "")}</td>'
                f"<td>{_escape_html(v.status)}</td>"
                f"<td>{v.age_days}</td>"
                f"<td>{_escape_html(v.title or '')}</td>"
                f'<td class="vuln-id">{_escape_html(v.id)}</td></tr>'
            )

        search_bar = (
            f'<div class="bucket-filter-bar">'
            f'<input type="text" class="bucket-search-input" placeholder="Search vulnerabilities..."'
            f' oninput="filterBucketVulns(this)">'
            f'<div class="bucket-filter-buttons">'
            f'<button class="active" data-sev="all" onclick="filterBucketSeverity(this,\'all\')">'
            f"All ({fetched_count})</button>"
            f'<button data-sev="critical" onclick="filterBucketSeverity(this,\'critical\')">'
            f"Critical ({sum(1 for v in vulns if v.severity.upper() == 'CRITICAL')})</button>"
            f'<button data-sev="high" onclick="filterBucketSeverity(this,\'high\')">'
            f"High ({sum(1 for v in vulns if v.severity.upper() == 'HIGH')})</button>"
            f"</div></div>"
        )

        table_body += (
            f'<tr class="bucket-row expandable" onclick="toggleBucketDetail(this)">'
            f'<td><span class="bucket-arrow">&#9658;</span> <strong>{bucket_name}</strong></td>'
            f"<td>{total}</td>"
            f"<td{crit_cls}>{critical}</td>"
            f"<td{high_cls}>{high}</td>"
            f"</tr>"
            f'<tr class="bucket-detail-row" style="display:none;">'
            f'<td colspan="4">{truncation_note}{search_bar}'
            f'<table class="vuln-table">{thead}<tbody>{"".join(rows)}</tbody></table>'
            f"</td></tr>"
        )

    if not table_body:
        table_body = '<tr><td colspan="4" class="no-findings">No Critical or High findings</td></tr>'

    return (
        '<div class="detail-section">'
        '<table class="bucket-summary-table">'
        "<thead><tr><th>Finding Type</th><th>Total</th><th>Critical</th><th>High</th></tr></thead>"
        f"<tbody>{table_body}</tbody>"
        "</table></div>"
    )


def main() -> None:
    """Command-line entry point"""
    output_dir = Path(".tmp/observatory/dashboards")
    generate_security_dashboard_enhanced(output_dir)


if __name__ == "__main__":
    main()
