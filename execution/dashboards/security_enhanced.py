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

try:
    from ..collectors.armorcode_loader import ArmorCodeLoader
    from ..collectors.armorcode_vulnerability_loader import ArmorCodeVulnerabilityLoader
    from ..dashboard_framework import get_dashboard_framework
    from ..dashboards.security_detail_page import generate_product_detail_page
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from collectors.armorcode_loader import ArmorCodeLoader  # type: ignore[no-redef]
    from collectors.armorcode_vulnerability_loader import ArmorCodeVulnerabilityLoader  # type: ignore[no-redef]
    from dashboard_framework import get_dashboard_framework  # type: ignore[no-redef]
    from dashboards.security_detail_page import generate_product_detail_page  # type: ignore[no-redef]


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
    print("  ✓ Product summary table")
    print("  ✓ Clickable 'View' buttons open detail pages")
    print("  ✓ Detail pages with full vulnerability lists")
    print("  ✓ Aging heatmap per product")
    print("  ✓ Search, filter, and Excel export")
    print("  ✓ Dark mode with toggle")
    print("=" * 60)

    return main_html, detail_pages_generated


def _generate_main_dashboard_html(metrics_by_product: dict, vulns_by_product: dict) -> str:
    """Generate main dashboard HTML with product summary table"""

    # Get framework CSS/JS
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#1e293b",
        header_gradient_end="#0f172a",
        include_table_scroll=True,
        include_expandable_rows=False,
        include_glossary=False,
    )

    # Calculate totals
    total_vulns = sum(m.total_vulnerabilities for m in metrics_by_product.values())
    total_critical = sum(m.critical for m in metrics_by_product.values())
    total_high = sum(m.high for m in metrics_by_product.values())

    # Overall status
    if total_critical == 0 and total_high <= 10:
        status_color = "#10b981"
        status_text = "HEALTHY"
    elif total_critical <= 5:
        status_color = "#f59e0b"
        status_text = "CAUTION"
    else:
        status_color = "#ef4444"
        status_text = "ACTION NEEDED"

    # Generate product table rows
    product_rows = []
    for product_name, metrics in sorted(metrics_by_product.items()):
        if metrics.total_vulnerabilities == 0:
            continue

        safe_filename = _sanitize_filename(product_name)
        detail_link = f"security_detail_{safe_filename}.html"

        # Status indicator
        if metrics.critical >= 5:
            status_indicator = '<span class="status-critical">⚠️ CRITICAL</span>'
        elif metrics.critical > 0:
            status_indicator = '<span class="status-high">⚠ High Risk</span>'
        elif metrics.high >= 10:
            status_indicator = '<span class="status-medium">⚠ Monitor</span>'
        else:
            status_indicator = '<span class="status-ok">✓ OK</span>'

        # Get vulnerability count from live data
        product_vulns = vulns_by_product.get(product_name, [])
        vuln_count = len(product_vulns)

        product_rows.append(f"""
            <tr>
                <td class="product-name">{_escape_html(product_name)}</td>
                <td class="count">{vuln_count}</td>
                <td class="count critical">{metrics.critical}</td>
                <td class="count high">{metrics.high}</td>
                <td class="actions">
                    <a href="{detail_link}" target="_blank" class="view-btn">View Details →</a>
                </td>
                <td class="status">{status_indicator}</td>
            </tr>
        """)

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Security Dashboard - {datetime.now().strftime('%Y-%m-%d')}</title>
    {framework_css}
    <style>
        .executive-summary {{
            background: var(--bg-secondary);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .status-badge {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 600;
            background: {status_color};
            color: white;
            margin-bottom: 20px;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-top: 16px;
        }}

        .summary-card {{
            background: var(--bg-tertiary);
            padding: 16px;
            border-radius: 8px;
            border-left: 4px solid #ef4444;
        }}

        .summary-card .label {{
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }}

        .summary-card .value {{
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .product-name {{
            font-weight: 600;
            color: var(--text-primary);
        }}

        .count {{
            text-align: center;
            font-weight: 600;
            font-variant-numeric: tabular-nums;
        }}

        .count.critical {{
            color: #ef4444;
            font-size: 1.1rem;
        }}

        .count.high {{
            color: #f59e0b;
            font-size: 1.1rem;
        }}

        .actions {{
            text-align: center;
        }}

        .view-btn {{
            display: inline-block;
            padding: 6px 12px;
            background: #3b82f6;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-size: 0.9rem;
            font-weight: 600;
            transition: all 0.2s ease;
        }}

        .view-btn:hover {{
            background: #2563eb;
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(59, 130, 246, 0.3);
        }}

        .status {{
            text-align: center;
        }}

        .status-critical {{
            color: #ef4444;
            font-weight: 700;
        }}

        .status-high {{
            color: #f59e0b;
            font-weight: 600;
        }}

        .status-medium {{
            color: #eab308;
            font-weight: 600;
        }}

        .status-ok {{
            color: #10b981;
            font-weight: 600;
        }}

        .section-title {{
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 16px;
            color: var(--text-primary);
        }}
    </style>
</head>
<body>
    <!-- Header -->
    <div class="header">
        <div class="header-content">
            <h1>🛡️ Security Dashboard</h1>
            <p class="subtitle">Critical & High Severity Vulnerabilities - {datetime.now().strftime('%Y-%m-%d')}</p>
        </div>
    </div>

    <!-- Executive Summary -->
    <div class="executive-summary">
        <div class="status-badge">{status_text}</div>
        <h2 class="section-title">Portfolio Summary</h2>
        <div class="summary-grid">
            <div class="summary-card">
                <div class="label">Total Findings</div>
                <div class="value">{total_vulns}</div>
            </div>
            <div class="summary-card">
                <div class="label">Critical</div>
                <div class="value" style="color: #ef4444;">{total_critical}</div>
            </div>
            <div class="summary-card">
                <div class="label">High</div>
                <div class="value" style="color: #f59e0b;">{total_high}</div>
            </div>
            <div class="summary-card">
                <div class="label">Products</div>
                <div class="value">{len(product_rows)}</div>
            </div>
        </div>
    </div>

    <!-- Product Table -->
    <div class="table-container">
        <h2 class="section-title" style="padding: 20px 20px 0;">Products with Vulnerabilities</h2>
        <table>
            <thead>
                <tr>
                    <th>Product</th>
                    <th>Total</th>
                    <th>Critical</th>
                    <th>High</th>
                    <th>Actions</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
{"".join(product_rows)}
            </tbody>
        </table>
    </div>

    <div class="footer">
        <p>Generated by Engineering Metrics Platform | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        <p>Click "View Details" to see individual vulnerabilities, aging heatmap, and export options</p>
    </div>

    {framework_js}
</body>
</html>"""


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
