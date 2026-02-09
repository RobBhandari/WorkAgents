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
    Generate enhanced security dashboard with expandable rows.

    Args:
        output_dir: Directory to write HTML files (defaults to .tmp/observatory/dashboards)

    Returns:
        Tuple of (main_dashboard_html, 0) - detail pages no longer generated

    Example:
        html, _ = generate_security_dashboard_enhanced()
        print(f"Generated dashboard with expandable rows")
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

    # Step 4: Summary
    print("\n[4/5] Summary")
    print(f"      Main dashboard: {len(main_html):,} bytes")
    print("      Using expandable rows (no separate detail pages)")

    print("\n" + "=" * 60)
    print("[SUCCESS] Security dashboard generated!")
    print(f"  Main: {main_file}")
    print(f"\nOpen: start {main_file}")
    print("\nFeatures:")
    print("  [X] Product summary table with expandable rows")
    print("  [X] Click rows to expand vulnerability details inline")
    print("  [X] Aging metrics displayed in expanded rows")
    print("  [X] Collapsible vulnerability table with search/filter")
    print("  [X] Dark mode with toggle")
    print("=" * 60)

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
        summary_card("Total Findings", str(summary_stats["total_vulns"])),
        summary_card("Critical", str(summary_stats["total_critical"]), css_class="critical"),
        summary_card("High", str(summary_stats["total_high"]), css_class="high"),
        summary_card("Products", str(summary_stats["products_with_vulns"])),
    ]

    # Build product rows with expandable content
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

        # Get vulnerabilities for this product
        vulns = vulns_by_product.get(product_name, [])

        # Generate expanded content HTML
        expanded_html = _generate_expanded_content(product_name, metrics, vulns)

        products.append(
            {
                "name": product_name,
                "total": metrics.total_vulnerabilities,
                "critical": metrics.critical,
                "high": metrics.high,
                "medium": metrics.medium,
                "status": status,
                "status_class": status_class,
                "expanded_html": expanded_html,
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


def _generate_expanded_content(product_name: str, metrics, vulnerabilities: list) -> str:
    """
    Generate HTML for expanded row content with aging metrics + collapsible vulnerabilities.

    Args:
        product_name: Product name
        metrics: SecurityMetrics object
        vulnerabilities: List of VulnerabilityDetail objects

    Returns:
        HTML string for expanded row content
    """
    # Part 1: Aging Metrics Section
    aging_html = f"""
    <div class="detail-section">
        <h4>📊 Vulnerability Metrics</h4>
        <div class="metrics-grid">
            <div class="metric-box">
                <div class="metric-label">Total Findings</div>
                <div class="metric-value">{metrics.total_vulnerabilities}</div>
            </div>
            <div class="metric-box critical">
                <div class="metric-label">Critical</div>
                <div class="metric-value">{metrics.critical}</div>
            </div>
            <div class="metric-box high">
                <div class="metric-label">High</div>
                <div class="metric-value">{metrics.high}</div>
            </div>
            <div class="metric-box medium">
                <div class="metric-label">Medium</div>
                <div class="metric-value">{metrics.medium or 0}</div>
            </div>
            <div class="metric-box low">
                <div class="metric-label">Low</div>
                <div class="metric-value">{metrics.low or 0}</div>
            </div>
        </div>
    </div>
    """

    # Part 2: Collapsible Vulnerabilities Section
    if not vulnerabilities:
        vulns_section = """
        <div class="detail-section">
            <div class="collapsible-header">
                <h4>No Vulnerabilities Found</h4>
            </div>
        </div>
        """
    else:
        vuln_rows_html = _generate_vulnerability_table_rows(vulnerabilities)
        vulns_section = f"""
        <div class="detail-section">
            <div class="collapsible-header" onclick="toggleVulnerabilities(this)">
                <span class="chevron">▶</span>
                <h4>Show Vulnerabilities ({len(vulnerabilities)})</h4>
            </div>
            <div class="collapsible-content" style="display: none;">
                <div class="vuln-filters">
                    <input type="text" placeholder="Search vulnerabilities..."
                           onkeyup="filterVulnerabilities(this)">
                    <button class="active" onclick="filterSeverity(this, 'all')">All ({len(vulnerabilities)})</button>
                    <button onclick="filterSeverity(this, 'critical')">Critical</button>
                    <button onclick="filterSeverity(this, 'high')">High</button>
                    <button onclick="filterSeverity(this, 'medium')">Medium</button>
                    <button onclick="filterSeverity(this, 'low')">Low</button>
                </div>
                <table class="vuln-table">
                    <thead>
                        <tr>
                            <th>Severity</th>
                            <th>Status</th>
                            <th>Age (Days)</th>
                            <th>Title</th>
                            <th>Description</th>
                            <th>ID</th>
                        </tr>
                    </thead>
                    <tbody>
                        {vuln_rows_html}
                    </tbody>
                </table>
            </div>
        </div>
        """

    return aging_html + vulns_section


def _generate_vulnerability_table_rows(vulnerabilities: list) -> str:
    """
    Generate HTML table rows for vulnerabilities.

    Args:
        vulnerabilities: List of VulnerabilityDetail or Vulnerability objects

    Returns:
        HTML string with table rows
    """
    rows = []
    for vuln in vulnerabilities:
        severity_class = vuln.severity.lower()
        # Get description - VulnerabilityDetail has description, Vulnerability doesn't
        desc_text = getattr(vuln, "description", "") or ""
        desc = _escape_html(desc_text)
        desc_short = desc[:100] + "..." if len(desc) > 100 else desc

        row = f"""
        <tr data-severity="{severity_class}">
            <td><span class="badge badge-{severity_class}">{_escape_html(vuln.severity)}</span></td>
            <td>{_escape_html(vuln.status)}</td>
            <td>{vuln.age_days}</td>
            <td>{_escape_html(vuln.title or "")}</td>
            <td class="description">{desc_short}</td>
            <td class="vuln-id">{_escape_html(vuln.id)}</td>
        </tr>
        """
        rows.append(row)

    return "\n".join(rows)


def main():
    """Command-line entry point"""
    output_dir = Path(".tmp/observatory/dashboards")
    generate_security_dashboard_enhanced(output_dir)


if __name__ == "__main__":
    main()
