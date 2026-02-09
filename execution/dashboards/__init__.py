"""
Dashboard Generation - Create HTML visualizations

This package contains:
    - framework: Shared mobile-responsive CSS/JS
    - renderer: Jinja2 template rendering
    - components: Reusable HTML components (cards, tables, charts)
    - Dashboard generators (security, executive, trends, etc.)

Usage:
    from execution.dashboards.renderer import render_dashboard
    from execution.dashboards.components.cards import metric_card

    html = render_dashboard('dashboards/security.html', context)
"""

__all__ = []
