"""
Mobile-Responsive Dashboard Framework

Organized package structure for the Observatory dashboard framework.
Provides shared CSS and JavaScript for all dashboards.

Package Structure:
    - theme.py: Theme variables and color palette
    - base_styles.py: CSS reset and typography
    - components.py: UI components (cards, headers, metrics)
    - tables.py: Table styles and collapsible sections
    - responsive.py: Utilities, badges, accessibility
    - javascript.py: Interactive functionality

Usage::

    from execution.framework import get_dashboard_framework

    css, javascript = get_dashboard_framework(
        header_gradient_start='#8b5cf6',
        header_gradient_end='#7c3aed',
        include_table_scroll=True,
        include_expandable_rows=True,
        include_glossary=True
    )
"""

from .base_styles import get_base_styles
from .components import get_layout_components, get_metric_components, get_theme_toggle_styles
from .javascript import get_dashboard_javascript
from .responsive import get_utility_styles
from .tables import get_collapsible_styles, get_table_styles
from .theme import get_theme_variables


def get_dashboard_framework(
    header_gradient_start="#667eea",
    header_gradient_end="#764ba2",
    include_table_scroll=True,
    include_expandable_rows=False,
    include_glossary=True,
):
    """
    Returns complete mobile-responsive CSS + JavaScript framework.

    This is the main entry point that coordinates all submodules to generate
    a complete dashboard framework bundle.

    Args:
        header_gradient_start: Start color for header gradient (default: #667eea)
        header_gradient_end: End color for header gradient (default: #764ba2)
        include_table_scroll: Include table scroll detection script (default: True)
        include_expandable_rows: Include expandable row functionality (default: False)
        include_glossary: Include glossary toggle functionality (default: True)

    Returns:
        Tuple of (css_string, javascript_string) ready to inject into HTML

    Example::

        css, js = get_dashboard_framework(
            header_gradient_start='#6366f1',
            header_gradient_end='#4f46e5',
            include_table_scroll=True
        )
    """
    # Build CSS by combining all style modules
    css = f"""
    <style>
    {get_theme_variables(header_gradient_start, header_gradient_end)}
    {get_base_styles()}
    {get_layout_components()}
    {get_metric_components()}
    {get_theme_toggle_styles()}
    {get_table_styles()}
    {get_collapsible_styles()}
    {get_utility_styles()}
    </style>
    """

    # Build JavaScript based on feature flags
    javascript = get_dashboard_javascript(
        include_table_scroll=include_table_scroll,
        include_expandable_rows=include_expandable_rows,
        include_glossary=include_glossary,
    )

    return css, javascript


# Backward compatibility: Export individual functions if needed
__all__ = [
    "get_dashboard_framework",
    "get_theme_variables",
    "get_base_styles",
    "get_layout_components",
    "get_metric_components",
    "get_theme_toggle_styles",
    "get_table_styles",
    "get_collapsible_styles",
    "get_utility_styles",
    "get_dashboard_javascript",
]
