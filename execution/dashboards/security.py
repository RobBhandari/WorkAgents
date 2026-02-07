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
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from collectors.armorcode_loader import ArmorCodeLoader  # type: ignore[no-redef]
    from dashboard_framework import get_dashboard_framework  # type: ignore[no-redef]
    from dashboards.components.cards import metric_card  # type: ignore[no-redef]
    from dashboards.renderer import render_dashboard  # type: ignore[no-redef]
    from domain.security import SecurityMetrics  # type: ignore[no-redef]


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
        include_expandable_rows=False,
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
    Build product table rows with status indicators.

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

        row = {
            "name": product_name,
            "total": metrics.total_vulnerabilities,
            "critical": metrics.critical,
            "high": metrics.high,
            "medium": metrics.medium,
            "status": status,
            "status_class": status_class,
            "expandable": False,  # Can add drill-down later
            "details": None,
        }

        rows.append(row)

    return rows


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
