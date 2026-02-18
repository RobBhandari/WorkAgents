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

    logger.info("Querying ArmorCode API for Production vulnerabilities")
    vuln_loader = ArmorCodeVulnerabilityLoader()
    vulnerabilities = vuln_loader.load_vulnerabilities_for_products(products, filter_environment=True)
    logger.info(f"Retrieved {len(vulnerabilities)} Production vulnerabilities from ArmorCode API")

    # Step 2: Convert vulnerabilities to metrics by product
    logger.info("Converting vulnerabilities to metrics by product")
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

    # Step 3: Group vulnerabilities by product for expandable rows
    vulns_by_product = vuln_loader.group_by_product(vulnerabilities)
    logger.info("Vulnerabilities grouped by product")

    # Step 4: Generate main dashboard HTML
    logger.info("Generating main dashboard")
    main_html = _generate_main_dashboard_html(metrics_by_product, vulns_by_product)

    # Write main dashboard
    main_file = output_dir / "security_dashboard.html"
    main_file.write_text(main_html, encoding="utf-8")
    logger.info("Main dashboard written", extra={"path": str(main_file)})

    # Step 4: Summary
    logger.info(
        "Security dashboard generated successfully",
        extra={
            "main_size": len(main_html),
            "features": [
                "Product summary table with expandable rows",
                "Click rows to expand vulnerability details inline",
                "Aging metrics displayed in expanded rows",
                "Collapsible vulnerability table with search/filter",
                "Dark mode with toggle",
            ],
        },
    )

    return main_html, 0  # No detail pages generated


def _generate_main_dashboard_html(metrics_by_product: dict, vulns_by_product: dict) -> str:
    """
    Generate main dashboard HTML using 4-stage pipeline.

    Stage 1: Load Data (already done - passed as parameters)
    Stage 2: Calculate Summary
    Stage 3: Build Context
    Stage 4: Render Template
    """
    # Stage 2: Calculate summary statistics
    summary_stats = _calculate_summary(metrics_by_product)

    # Stage 3: Build context for template
    context = _build_context(metrics_by_product, vulns_by_product, summary_stats)

    # Stage 4: Render template
    html = render_dashboard("dashboards/security_dashboard.html", context)
    return html


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
        "status": status,
        "status_text": status_text,
    }


def _build_context(metrics_by_product: dict, vulns_by_product: dict, summary_stats: dict) -> dict:
    """
    Stage 3: Build template context.

    Args:
        metrics_by_product: Dict of product name -> SecurityMetrics
        vulns_by_product: Dict of product name -> List of vulnerabilities
        summary_stats: Summary statistics from _calculate_summary()

    Returns:
        Dictionary with template variables
    """
    # Get framework CSS/JS (enable expandable rows)
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#667eea",
        header_gradient_end="#764ba2",
        include_table_scroll=True,
        include_expandable_rows=True,
        include_glossary=False,
    )

    # Build summary cards using component function
    summary_cards = [
        summary_card("Priority Findings", str(summary_stats["critical_high_total"])),
        summary_card("Critical", str(summary_stats["total_critical"]), css_class="critical"),
        summary_card("High", str(summary_stats["total_high"]), css_class="high"),
        summary_card("Products", str(summary_stats["products_with_vulns"])),
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

        # Get vulnerabilities for this product
        vulns = vulns_by_product.get(product_name, [])

        # Generate expanded content HTML
        expanded_html = _generate_bucket_expanded_content(vulns)

        products.append(
            {
                "name": product_name,
                "total": metrics.critical + metrics.high,
                "critical": metrics.critical,
                "high": metrics.high,
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


def _generate_bucket_expanded_content(vulnerabilities: list) -> str:
    """
    Generate expanded row HTML: inline expandable bucket rows within a single table.

    Each non-zero bucket is a clickable row that expands inline to show individual
    vulnerability details. Zero-total buckets are suppressed entirely.

    Args:
        vulnerabilities: List of VulnerabilityDetail objects for this product

    Returns:
        HTML string for the expanded row content
    """
    filtered = [v for v in vulnerabilities if v.severity.upper() in ("CRITICAL", "HIGH")]

    # Group by bucket
    buckets: dict[str, list] = {b: [] for b in BUCKET_ORDER}
    for vuln in filtered:
        bucket = SOURCE_BUCKET_MAP.get(vuln.source or "", "Other")
        buckets[bucket].append(vuln)

    # Build table body — only non-zero buckets
    table_body = ""
    for bucket_name in BUCKET_ORDER:
        vulns = buckets[bucket_name]
        total = len(vulns)
        if total == 0:
            continue  # Suppress zero-total rows

        critical = sum(1 for v in vulns if v.severity.upper() == "CRITICAL")
        high = total - critical
        crit_cls = ' class="critical"' if critical > 0 else ""
        high_cls = ' class="high"' if high > 0 else ""

        rows = []
        for v in vulns:
            sev = v.severity.lower()
            rows.append(
                f'<tr><td><span class="badge badge-{sev}">{_escape_html(v.severity)}</span></td>'
                f"<td>{_escape_html(v.status)}</td>"
                f"<td>{v.age_days}</td>"
                f"<td>{_escape_html(v.title or '')}</td>"
                f'<td class="vuln-id">{_escape_html(v.id)}</td></tr>'
            )
        vuln_rows = "\n".join(rows)

        table_body += (
            f'<tr class="bucket-row expandable" onclick="toggleBucketDetail(this)">'
            f'<td><span class="bucket-arrow">&#9658;</span> <strong>{bucket_name}</strong></td>'
            f"<td>{total}</td>"
            f"<td{crit_cls}>{critical}</td>"
            f"<td{high_cls}>{high}</td>"
            f"</tr>"
            f'<tr class="bucket-detail-row" style="display:none;">'
            f'<td colspan="4">'
            f'<table class="vuln-table">'
            f"<thead><tr><th>Severity</th><th>Status</th><th>Age (Days)</th><th>Title</th><th>ID</th></tr></thead>"
            f"<tbody>{vuln_rows}</tbody>"
            f"</table>"
            f"</td>"
            f"</tr>"
        )

    if not table_body:
        table_body = '<tr><td colspan="4" class="no-findings">' "No Critical or High findings" "</td></tr>"

    return f"""<div class="detail-section">
        <table class="bucket-summary-table">
            <thead><tr><th>Finding Type</th><th>Total</th><th>Critical</th><th>High</th></tr></thead>
            <tbody>{table_body}</tbody>
        </table>
    </div>"""


def main() -> None:
    """Command-line entry point"""
    output_dir = Path(".tmp/observatory/dashboards")
    generate_security_dashboard_enhanced(output_dir)


if __name__ == "__main__":
    main()
