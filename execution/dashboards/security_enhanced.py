#!/usr/bin/env python3
"""
Enhanced Security Dashboard Generator

Complete security dashboard with:
- Main summary table
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
from datetime import datetime
from pathlib import Path

from execution.collectors.armorcode_loader import ArmorCodeLoader
from execution.collectors.armorcode_vulnerability_loader import ArmorCodeVulnerabilityLoader
from execution.dashboards.components.cards import summary_card
from execution.dashboards.renderer import render_dashboard
from execution.dashboards.security_detail_page import generate_product_detail_page
from execution.framework import get_dashboard_framework


def generate_security_dashboard_enhanced(output_dir: Path | None = None) -> tuple[str, int]:
    """
    Generate enhanced security dashboard with drill-down pages.

    Args:
        output_dir: Directory to write HTML files (defaults to .tmp/observatory/dashboards)

    Returns:
        Tuple of (main_dashboard_html, num_detail_pages)

    Example:
        html, num_pages = generate_security_dashboard_enhanced()
        print(f"Generated dashboard with {num_pages} detail pages")
    """
    if output_dir is None:
        output_dir = Path(".tmp/observatory/dashboards")

    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("Enhanced Security Dashboard Generator")
    print("=" * 60)

    # Step 1: Load ArmorCode summary data
    print("\n[1/5] Loading ArmorCode summary data...")
    try:
        loader = ArmorCodeLoader()
        metrics_by_product = loader.load_latest_metrics()
        print(f"      Loaded {len(metrics_by_product)} products")
    except FileNotFoundError:
        print("[ERROR] No ArmorCode data found in security_history.json")
        print("Run: python execution/armorcode_enhanced_metrics.py")
        return "", 0

    # Step 2: Get product names with vulnerabilities
    product_names = [name for name, metrics in metrics_by_product.items() if metrics.total_vulnerabilities > 0]
    print(f"      Products with vulnerabilities: {len(product_names)}")

    # Step 3: Query individual vulnerabilities via GraphQL
    print("\n[2/5] Querying individual vulnerability details via GraphQL...")
    vuln_loader = ArmorCodeVulnerabilityLoader()
    vulnerabilities = vuln_loader.load_vulnerabilities_for_products(product_names)
    print(f"      Retrieved {len(vulnerabilities)} vulnerability details")

    # Group vulnerabilities by product
    vulns_by_product = vuln_loader.group_by_product(vulnerabilities)

    # Step 4: Generate main dashboard HTML
    print("\n[3/5] Generating main dashboard...")
    main_html = _generate_main_dashboard_html(metrics_by_product, vulns_by_product)

    # Write main dashboard
    main_file = output_dir / "security_dashboard.html"
    main_file.write_text(main_html, encoding="utf-8")
    print(f"      Main dashboard: {main_file}")

    # Step 5: Generate individual product detail pages
    print("\n[4/5] Generating individual product detail pages...")
    query_date = datetime.now().strftime("%Y-%m-%d")

    # Get product IDs for detail pages
    product_id_map = vuln_loader.get_product_ids(product_names)

    detail_pages_generated = 0
    for product_name in product_names:
        product_vulns = vulns_by_product.get(product_name, [])
        product_id = product_id_map.get(product_name, "Unknown")

        # Generate detail page
        detail_html = generate_product_detail_page(product_name, product_id, product_vulns, query_date)

        # Save detail page with sanitized filename
        safe_filename = _sanitize_filename(product_name)
        detail_file = output_dir / f"security_detail_{safe_filename}.html"
        detail_file.write_text(detail_html, encoding="utf-8")

        print(f"      Generated: {detail_file.name} ({len(product_vulns)} vulnerabilities)")
        detail_pages_generated += 1

    # Step 6: Summary
    print("\n[5/5] Summary")
    print(f"      Main dashboard: {len(main_html):,} bytes")
    print(f"      Detail pages: {detail_pages_generated} files")

    print("\n" + "=" * 60)
    print("[SUCCESS] Security dashboard generated!")
    print(f"  Main: {main_file}")
    print(f"  Details: {detail_pages_generated} files")
    print(f"\nOpen: start {main_file}")
    print("\nFeatures:")
    print("  [X] Product summary table")
    print("  [X] Clickable 'View' buttons open detail pages")
    print("  [X] Detail pages with full vulnerability lists")
    print("  [X] Aging heatmap per product")
    print("  [X] Search, filter, and Excel export")
    print("  [X] Dark mode with toggle")
    print("=" * 60)

    return main_html, detail_pages_generated


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
    # Get framework CSS/JS
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#667eea",
        header_gradient_end="#764ba2",
        include_table_scroll=True,
        include_expandable_rows=False,
        include_glossary=False,
    )

    # Build summary cards using component function
    summary_cards = [
        summary_card("Total Findings", str(summary_stats["total_vulns"])),
        summary_card("Critical", str(summary_stats["total_critical"]), css_class="critical"),
        summary_card("High", str(summary_stats["total_high"]), css_class="high"),
        summary_card("Products", str(summary_stats["products_with_vulns"])),
    ]

    # Build product rows
    products = []
    for product_name, metrics in sorted(metrics_by_product.items()):
        if metrics.total_vulnerabilities == 0:
            continue

        # Determine status using standard status classes
        if metrics.critical >= 5:
            status = "Critical"
            status_class = "action"
        elif metrics.critical > 0:
            status = "High Risk"
            status_class = "caution"
        elif metrics.high >= 10:
            status = "Monitor"
            status_class = "caution"
        else:
            status = "OK"
            status_class = "good"

        products.append(
            {
                "name": product_name,
                "total": metrics.total_vulnerabilities,
                "critical": metrics.critical,
                "high": metrics.high,
                "medium": metrics.medium,
                "status": status,
                "status_class": status_class,
                "expandable": False,  # Security dashboard uses separate detail pages
                "details": None,
            }
        )

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


def main():
    """Command-line entry point"""
    output_dir = Path(".tmp/observatory/dashboards")
    generate_security_dashboard_enhanced(output_dir)


if __name__ == "__main__":
    main()
