"""
Generate Quality Dashboard - Minimalist Design

Creates quality_dashboard_minimalist.html with clean, modern styling:
- Inter font with OpenType features
- Solid slate color palette
- Complete dark/light theme support
- No transparent backgrounds

Usage:
    python generate_quality_minimalist.py
"""

from pathlib import Path

from execution.dashboards.quality import generate_quality_dashboard


def generate_quality_minimalist():
    """Generate quality dashboard with minimalist template."""
    # Import necessary modules
    from execution.dashboards.renderer import render_dashboard
    from execution.dashboards.quality import _load_quality_data, _calculate_summary, _build_context

    print("Loading quality data...")
    quality_data = _load_quality_data()

    print("Calculating summary metrics...")
    summary_stats = _calculate_summary(quality_data["projects"])

    print("Building dashboard context...")
    context = _build_context(quality_data, summary_stats)

    print("Rendering minimalist template...")
    html = render_dashboard("dashboards/quality_dashboard_minimalist.html", context)

    # Write output
    output_path = Path(".tmp/observatory/dashboards/quality_MINIMALIST.html")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    print(f"[OK] Generated: {output_path}")
    print(f"  Size: {len(html):,} bytes")
    return html


if __name__ == "__main__":
    generate_quality_minimalist()
