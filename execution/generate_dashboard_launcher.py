#!/usr/bin/env python3
"""
Generate Dashboard Launcher (launcher.html)

Creates a hub page with cards for all available dashboards.
Note: index.html is reserved for Executive Trends Dashboard.
"""

import sys
from datetime import datetime
from pathlib import Path

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

from execution.dashboards.renderer import render_dashboard
from execution.framework import get_dashboard_framework


def generate_dashboard_launcher(output_path: Path | None = None) -> str:
    """
    Generate dashboard launcher HTML.

    Args:
        output_path: Optional path to write HTML file (defaults to launcher.html)

    Returns:
        Generated HTML string
    """
    if output_path is None:
        output_path = Path(".tmp/observatory/dashboards/launcher.html")

    # Define dashboard cards
    dashboards = [
        {
            "title": "Executive Trends",
            "filename": "trends.html",
            "icon": "📈",
            "description": "12-week historical trends and 70% reduction target progress",
            "status": None,
            "status_class": "",
        },
        {
            "title": "Quality",
            "filename": "quality_dashboard.html",
            "icon": "🐛",
            "description": "Bug metrics, closure rates, and aging analysis",
            "status": None,
            "status_class": "",
        },
        {
            "title": "Security",
            "filename": "security_dashboard.html",
            "icon": "🔒",
            "description": "Vulnerability tracking with drill-down by product",
            "status": None,
            "status_class": "",
        },
        {
            "title": "Exploitable Vulns",
            "filename": "exploitable_dashboard.html",
            "icon": "🎯",
            "description": "CISA KEV exploitable findings by product and source bucket",
            "status": None,
            "status_class": "",
        },
        {
            "title": "Flow",
            "filename": "flow_dashboard.html",
            "icon": "⚡",
            "description": "Lead time, cycle time, and WIP analysis",
            "status": None,
            "status_class": "",
        },
        {
            "title": "Risk",
            "filename": "risk_dashboard.html",
            "icon": "⚠️",
            "description": "Risk exposure and mitigation tracking",
            "status": None,
            "status_class": "",
        },
        {
            "title": "Deployment",
            "filename": "deployment_dashboard.html",
            "icon": "🚀",
            "description": "Deployment frequency and success rates",
            "status": None,
            "status_class": "",
        },
        {
            "title": "Ownership",
            "filename": "ownership_dashboard.html",
            "icon": "👥",
            "description": "Code ownership and contributor analysis",
            "status": None,
            "status_class": "",
        },
        {
            "title": "Collaboration",
            "filename": "collaboration_dashboard.html",
            "icon": "🤝",
            "description": "Team collaboration and communication metrics",
            "status": None,
            "status_class": "",
        },
        {
            "title": "Target Progress",
            "filename": "target_dashboard.html",
            "icon": "🎯",
            "description": "Progress toward organizational targets",
            "status": None,
            "status_class": "",
        },
        {
            "title": "AI Usage Report",
            "filename": "usage_tables_latest.html",
            "icon": "🤖",
            "description": "AI tool usage statistics and adoption metrics",
            "status": None,
            "status_class": "",
        },
    ]

    # Get framework CSS/JS
    framework_css, framework_js = get_dashboard_framework()

    # Build context
    context = {
        "dashboards": dashboards,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "framework_css": framework_css,
        "framework_js": framework_js,
    }

    # Render template
    html = render_dashboard("dashboards/index_launcher.html", context)

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    print(f"✅ Dashboard launcher generated: {output_path}")
    print(f"   {len(dashboards)} dashboards available")

    return html


if __name__ == "__main__":
    generate_dashboard_launcher()
