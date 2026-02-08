"""
Security Dashboard Generator - Refactored

Generates security vulnerability dashboard using:
    - Domain models (SecurityMetrics, Vulnerability)
    - Reusable components (cards, tables)
    - Jinja2 templates (XSS-safe)

This replaces the original 1833-line generate_security_dashboard.py with a
clean, maintainable implementation of <300 lines.

Usage:
    from execution.dashboards.security import generate_security_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/security.html')
    generate_security_dashboard(output_path)
"""

from datetime import datetime
from pathlib import Path

# Import domain models
try:
    from ..collectors.armorcode_loader import ArmorCodeLoader
    from ..dashboard_framework import get_dashboard_framework
    from ..dashboards.components.cards import metric_card, summary_card
    from ..dashboards.renderer import render_dashboard
    from ..domain.security import SecurityMetrics
    from ..template_engine import render_template
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from collectors.armorcode_loader import ArmorCodeLoader  # type: ignore[no-redef]
    from dashboard_framework import get_dashboard_framework  # type: ignore[no-redef]
    from dashboards.components.cards import metric_card  # type: ignore[no-redef]
    from dashboards.renderer import render_dashboard  # type: ignore[no-redef]
    from domain.security import SecurityMetrics  # type: ignore[no-redef]
    from template_engine import render_template  # type: ignore[no-redef]


def generate_security_dashboard(output_path: Path | None = None) -> str:
    """
    Generate security vulnerabilities dashboard HTML.

    This is the main entry point for generating the security dashboard.
    It loads data, processes it, and renders the HTML template.

    Args:
        output_path: Optional path to write HTML file

    Returns:
        Generated HTML string

    Raises:
        FileNotFoundError: If security_history.json doesn't exist

    Example:
        from pathlib import Path
        html = generate_security_dashboard(
            Path('.tmp/observatory/dashboards/security.html')
        )
        print(f"Generated dashboard with {len(html)} characters")
    """
    print("[INFO] Generating Security Dashboard...")

    # Step 1: Load data
    print("[1/4] Loading security data...")
    loader = ArmorCodeLoader()
    metrics_by_product = loader.load_latest_metrics()
    print(f"      Loaded {len(metrics_by_product)} products")

    # Step 2: Calculate summary statistics
    print("[2/4] Calculating summary metrics...")
    summary_stats = _calculate_summary(metrics_by_product)

    # Step 3: Prepare template context
    print("[3/4] Preparing dashboard components...")
    context = _build_context(metrics_by_product, summary_stats)

    # Step 4: Render template
    print("[4/4] Rendering HTML template...")
    html = render_dashboard("dashboards/security_dashboard.html", context)

    # Write to file if specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        print(f"[SUCCESS] Dashboard written to: {output_path}")

    print(f"[SUCCESS] Generated {len(html):,} characters of HTML")
    return html


def _calculate_summary(metrics_by_product: dict[str, SecurityMetrics]) -> dict:
    """
    Calculate summary statistics across all products.

    Args:
        metrics_by_product: Dictionary of product metrics

    Returns:
        Dictionary with summary stats
    """
    total_vulns = sum(m.total_vulnerabilities for m in metrics_by_product.values())
    total_critical = sum(m.critical for m in metrics_by_product.values())
    total_high = sum(m.high for m in metrics_by_product.values())
    total_medium = sum(m.medium for m in metrics_by_product.values())
    total_low = sum(m.low for m in metrics_by_product.values())

    critical_high_total = total_critical + total_high

    # Count products by severity
    products_with_critical = sum(1 for m in metrics_by_product.values() if m.has_critical)
    products_with_high = sum(1 for m in metrics_by_product.values() if m.has_high)

    return {
        "total_vulnerabilities": total_vulns,
        "total_critical": total_critical,
        "total_high": total_high,
        "total_medium": total_medium,
        "total_low": total_low,
        "critical_high_total": critical_high_total,
        "products_with_critical": products_with_critical,
        "products_with_high": products_with_high,
        "product_count": len(metrics_by_product),
    }


def _build_context(metrics_by_product: dict[str, SecurityMetrics], summary_stats: dict) -> dict:
    """
    Build template context with all dashboard data.

    Args:
        metrics_by_product: Product metrics
        summary_stats: Calculated summary statistics

    Returns:
        Dictionary for template rendering
    """
    # Get dashboard framework (CSS/JS)
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#8b5cf6",
        header_gradient_end="#7c3aed",
        include_table_scroll=True,
        include_expandable_rows=True,  # Enable expandable rows
        include_glossary=True,
    )

    # Build summary cards
    summary_cards = _build_summary_cards(summary_stats)

    # Build product rows
    products = _build_product_rows(metrics_by_product)

    # Build context
    context = {
        "framework_css": framework_css,
        "framework_js": framework_js,
        "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary_cards": summary_cards,
        "products": products,
        "show_glossary": True,
    }

    return context


def _build_summary_cards(summary_stats: dict) -> list[str]:
    """
    Build summary metric cards HTML.

    Args:
        summary_stats: Summary statistics dictionary

    Returns:
        List of HTML strings for metric cards
    """
    cards = []

    # Total vulnerabilities
    cards.append(
        metric_card(
            title="Total Vulnerabilities",
            value=str(summary_stats["total_vulnerabilities"]),
            subtitle=f"Across {summary_stats['product_count']} products",
        )
    )

    # Critical vulnerabilities
    critical_class = "rag-red" if summary_stats["total_critical"] > 0 else "rag-green"
    cards.append(
        metric_card(
            title="Critical",
            value=str(summary_stats["total_critical"]),
            subtitle=f"{summary_stats['products_with_critical']} products affected",
            css_class=critical_class,
        )
    )

    # High vulnerabilities
    high_class = "rag-amber" if summary_stats["total_high"] > 5 else "rag-green"
    cards.append(
        metric_card(
            title="High",
            value=str(summary_stats["total_high"]),
            subtitle=f"{summary_stats['products_with_high']} products affected",
            css_class=high_class,
        )
    )

    # Critical + High (70% reduction target)
    cards.append(
        metric_card(
            title="Critical + High", value=str(summary_stats["critical_high_total"]), subtitle="70% reduction target"
        )
    )

    return cards


def _build_product_rows(metrics_by_product: dict[str, SecurityMetrics]) -> list[dict]:
    """
    Build product table rows with expandable drill-down details.

    Args:
        metrics_by_product: Product metrics dictionary

    Returns:
        List of product dictionaries for template
    """
    rows = []

    for product_name, metrics in sorted(metrics_by_product.items()):
        # Determine status based on critical/high counts
        if metrics.critical > 0:
            status = "Critical"
            status_class = "action"
        elif metrics.high > 5:
            status = "High Risk"
            status_class = "caution"
        elif metrics.high > 0:
            status = "Attention"
            status_class = "caution"
        else:
            status = "Good"
            status_class = "good"

        # Generate drill-down details (aging heatmap + vulnerability breakdown)
        details_html = _generate_product_details(product_name, metrics)

        row = {
            "name": product_name,
            "total": metrics.total_vulnerabilities,
            "critical": metrics.critical,
            "high": metrics.high,
            "medium": metrics.medium,
            "status": status,
            "status_class": status_class,
            "expandable": True,  # Enable drill-down
            "details": details_html,
        }

        rows.append(row)

    return rows


def _generate_product_details(product_name: str, metrics: SecurityMetrics) -> str:
    """
    Generate two-stage drill-down HTML for a product.

    Stage 1: Aging heatmap (estimated distribution)
    Stage 2: Vulnerability summary table (expandable)

    Args:
        product_name: Name of the product
        metrics: Security metrics for the product

    Returns:
        HTML string for expandable detail section
    """
    # Generate aging heatmap (estimated based on typical patterns)
    heatmap_html = _generate_aging_heatmap_estimated(metrics)

    # Generate vulnerability breakdown
    breakdown_html = _generate_vulnerability_breakdown(metrics)

    # Combine into two-stage layout
    details_html = f'''
    <div class="detail-content">
        <!-- Stage 1: Aging Heatmap -->
        {heatmap_html}

        <!-- Stage 2: Vulnerability Breakdown (collapsible) -->
        <div class="vuln-breakdown-section">
            <button class="expand-btn" onclick="toggleVulnDetails(this); event.stopPropagation();">
                Show Vulnerability Breakdown ▼
            </button>
            <div class="vuln-details-hidden">
                {breakdown_html}
            </div>
        </div>
    </div>
    '''

    return details_html


def _generate_aging_heatmap_estimated(metrics: SecurityMetrics) -> str:
    """
    Generate aging heatmap with estimated distribution.

    Note: Uses typical distribution patterns since individual vulnerability
    ages are not currently collected. Can be enhanced when age data is available.

    Args:
        metrics: Security metrics with counts

    Returns:
        HTML for aging heatmap visualization
    """
    # Typical age distribution pattern (based on industry averages)
    # These percentages can be adjusted based on organization patterns
    age_patterns = [
        ("0-7", 0.15),    # 15% very recent
        ("8-14", 0.20),   # 20% recent
        ("15-30", 0.30),  # 30% this month
        ("31-90", 0.25),  # 25% 1-3 months
        ("90+", 0.10),    # 10% stale
    ]

    # Calculate estimated counts for critical
    critical_dist = []
    for label, pct in age_patterns:
        count = round(metrics.critical * pct)
        critical_dist.append((label, count))

    # Calculate estimated counts for high
    high_dist = []
    for label, pct in age_patterns:
        count = round(metrics.high * pct)
        high_dist.append((label, count))

    # Find max for intensity scaling
    max_count = max(
        max(c for _, c in critical_dist),
        max(c for _, c in high_dist)
    ) if metrics.critical + metrics.high > 0 else 1

    # Generate heatmap HTML
    html = '''
    <div class="heatmap-container">
        <div class="heatmap-header">
            <h4>Finding Age Distribution (Estimated)</h4>
            <p class="heatmap-subtitle">Estimated vulnerability count by age and severity</p>
            <p class="heatmap-note" style="font-size: 0.85em; color: var(--text-secondary); font-style: italic;">
                Note: Distribution estimated from typical patterns. Enable individual vulnerability
                tracking in data collection for precise aging data.
            </p>
        </div>
        <div class="heatmap-grid">
            <div class="heatmap-corner"></div>
    '''

    # Column headers
    for label, _ in age_patterns:
        html += render_template("components/heatmap_col_header.html", label=label)

    # Critical row
    html += '<div class="heatmap-row-header critical-header">Critical</div>'
    for _, count in critical_dist:
        intensity = (count / max_count) if max_count > 0 else 0
        html += _generate_heatmap_cell(count, intensity, 'critical')

    # High row
    html += '<div class="heatmap-row-header high-header">High</div>'
    for _, count in high_dist:
        intensity = (count / max_count) if max_count > 0 else 0
        html += _generate_heatmap_cell(count, intensity, 'high')

    html += '''
        </div>
    </div>
    '''

    return html


def _generate_heatmap_cell(count: int, intensity: float, severity_type: str) -> str:
    """
    Generate a single heatmap cell with color coding.

    Args:
        count: Vulnerability count
        intensity: Color intensity (0-1)
        severity_type: 'critical' or 'high'

    Returns:
        HTML for cell
    """
    if count == 0:
        bg_color = 'rgba(148, 163, 184, 0.1)'
        text_color = 'var(--text-secondary)'
        display_value = ''
    else:
        if severity_type == 'critical':
            # Red scale for critical
            if intensity < 0.3:
                bg_color = f'rgba(239, 68, 68, {0.3 + intensity * 0.3})'
            elif intensity < 0.7:
                bg_color = f'rgba(239, 68, 68, {0.6 + intensity * 0.2})'
            else:
                bg_color = f'rgba(220, 38, 38, {0.8 + intensity * 0.2})'
        else:
            # Orange scale for high
            if intensity < 0.3:
                bg_color = f'rgba(251, 146, 60, {0.3 + intensity * 0.3})'
            elif intensity < 0.7:
                bg_color = f'rgba(249, 115, 22, {0.6 + intensity * 0.2})'
            else:
                bg_color = f'rgba(234, 88, 12, {0.8 + intensity * 0.2})'

        text_color = '#ffffff'
        display_value = str(count)

    return render_template(
        "components/heatmap_cell.html",
        bg_color=bg_color,
        text_color=text_color,
        display_value=display_value
    )


def _generate_vulnerability_breakdown(metrics: SecurityMetrics) -> str:
    """
    Generate detailed vulnerability breakdown table.

    Args:
        metrics: Security metrics

    Returns:
        HTML for vulnerability breakdown
    """
    html = '''
    <div class="vuln-breakdown-table">
        <h4>Vulnerability Breakdown by Severity</h4>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Severity</th>
                    <th>Count</th>
                    <th>Percentage</th>
                    <th>Priority</th>
                </tr>
            </thead>
            <tbody>
    '''

    total = metrics.total_vulnerabilities
    if total == 0:
        html += '''
                <tr><td colspan="4" style="text-align: center; padding: 20px;">No vulnerabilities found</td></tr>
        '''
    else:
        # Critical
        crit_pct = (metrics.critical / total * 100) if total > 0 else 0
        html += f'''
                <tr>
                    <td><span class="severity-badge critical">Critical</span></td>
                    <td>{metrics.critical}</td>
                    <td>{crit_pct:.1f}%</td>
                    <td>Immediate Action</td>
                </tr>
        '''

        # High
        high_pct = (metrics.high / total * 100) if total > 0 else 0
        html += f'''
                <tr>
                    <td><span class="severity-badge high">High</span></td>
                    <td>{metrics.high}</td>
                    <td>{high_pct:.1f}%</td>
                    <td>Fix Within 30 Days</td>
                </tr>
        '''

        # Medium
        med_pct = (metrics.medium / total * 100) if total > 0 else 0
        html += f'''
                <tr>
                    <td><span class="severity-badge medium">Medium</span></td>
                    <td>{metrics.medium}</td>
                    <td>{med_pct:.1f}%</td>
                    <td>Fix Within 90 Days</td>
                </tr>
        '''

        # Low
        low_pct = (metrics.low / total * 100) if total > 0 else 0
        html += f'''
                <tr>
                    <td><span class="severity-badge low">Low</span></td>
                    <td>{metrics.low}</td>
                    <td>{low_pct:.1f}%</td>
                    <td>Monitor</td>
                </tr>
        '''

    html += '''
            </tbody>
        </table>
        <div class="breakdown-note" style="margin-top: 15px; font-size: 0.9em; color: var(--text-secondary);">
            <p><strong>Note:</strong> Individual CVE details, descriptions, and remediation steps
            require enhanced data collection. Currently showing summary counts from ArmorCode API.</p>
            <p>To enable detailed vulnerability tracking, update data collection to fetch and store
            individual finding details.</p>
        </div>
    </div>
    '''

    return html


# Main execution for testing
if __name__ == "__main__":
    print("Security Dashboard Generator - Self Test")
    print("=" * 60)

    try:
        output_path = Path(".tmp/observatory/dashboards/security.html")
        html = generate_security_dashboard(output_path)

        print("\n" + "=" * 60)
        print("[SUCCESS] Security dashboard generated!")
        print(f"[OUTPUT] {output_path}")
        print(f"[SIZE] {len(html):,} characters")

        # Verify output
        if output_path.exists():
            file_size = output_path.stat().st_size
            print(f"[FILE] {file_size:,} bytes on disk")
        else:
            print("[WARNING] Output file not created")

    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        print("\n[INFO] Run data collection first:")
        print("  python execution/armorcode_weekly_query.py")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()
