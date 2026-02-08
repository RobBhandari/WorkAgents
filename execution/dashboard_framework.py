"""
Mobile-Responsive Dashboard Framework (DEPRECATED)

⚠️  DEPRECATION NOTICE ⚠️
This module is deprecated and will be removed in a future release.
Please update your imports to use the new package structure:

    OLD: from execution.dashboard_framework import get_dashboard_framework
    NEW: from execution.framework import get_dashboard_framework

The new package provides better organization with separate modules:
    - execution.framework.theme: Theme variables and colors
    - execution.framework.base_styles: CSS reset and typography
    - execution.framework.components: UI components (cards, headers, metrics)
    - execution.framework.tables: Table styles and collapsible sections
    - execution.framework.responsive: Utilities, badges, accessibility
    - execution.framework.javascript: Interactive functionality

For now, this module continues to work by delegating to the new package.
"""

import warnings

from execution.framework import get_dashboard_framework as _new_get_dashboard_framework

# Show deprecation warning when this module is imported
warnings.warn(
    "execution.dashboard_framework is deprecated. "
    "Use 'from execution.framework import get_dashboard_framework' instead.",
    DeprecationWarning,
    stacklevel=2,
)


def get_dashboard_framework(
    header_gradient_start="#667eea",
    header_gradient_end="#764ba2",
    include_table_scroll=True,
    include_expandable_rows=False,
    include_glossary=True,
):
    """
    Returns complete mobile-responsive CSS + JavaScript framework.

    ⚠️  DEPRECATED: This function delegates to execution.framework.get_dashboard_framework
    Please update your imports to use the new package structure.

    Args:
        header_gradient_start: Start color for header gradient
        header_gradient_end: End color for header gradient
        include_table_scroll: Include table scroll detection script
        include_expandable_rows: Include expandable row functionality
        include_glossary: Include glossary toggle functionality

    Returns:
        Tuple of (css_string, javascript_string)
    """
    return _new_get_dashboard_framework(
        header_gradient_start=header_gradient_start,
        header_gradient_end=header_gradient_end,
        include_table_scroll=include_table_scroll,
        include_expandable_rows=include_expandable_rows,
        include_glossary=include_glossary,
    )


# Deprecated individual functions for backward compatibility
# These are no longer recommended but still work
def get_theme_variables():
    """DEPRECATED: Use execution.framework.theme.get_theme_variables instead"""
    from execution.framework.theme import get_theme_variables as _new_func

    return _new_func()


def get_base_styles():
    """DEPRECATED: Use execution.framework.base_styles.get_base_styles instead"""
    from execution.framework.base_styles import get_base_styles as _new_func

    return _new_func()


def get_layout_components():
    """DEPRECATED: Use execution.framework.components.get_layout_components instead"""
    from execution.framework.components import get_layout_components as _new_func

    return _new_func()


def get_table_styles():
    """DEPRECATED: Use execution.framework.tables.get_table_styles instead"""
    from execution.framework.tables import get_table_styles as _new_func

    return _new_func()


def get_theme_toggle_styles():
    """DEPRECATED: Use execution.framework.components.get_theme_toggle_styles instead"""
    from execution.framework.components import get_theme_toggle_styles as _new_func

    return _new_func()


def get_metric_components():
    """DEPRECATED: Use execution.framework.components.get_metric_components instead"""
    from execution.framework.components import get_metric_components as _new_func

    return _new_func()


def get_collapsible_styles():
    """DEPRECATED: Use execution.framework.tables.get_collapsible_styles instead"""
    from execution.framework.tables import get_collapsible_styles as _new_func

    return _new_func()


def get_utility_styles():
    """DEPRECATED: Use execution.framework.responsive.get_utility_styles instead"""
    from execution.framework.responsive import get_utility_styles as _new_func

    return _new_func()


def get_theme_toggle_script():
    """DEPRECATED: Use execution.framework.javascript.get_theme_toggle_script instead"""
    from execution.framework.javascript import get_theme_toggle_script as _new_func

    return _new_func()


def get_glossary_toggle_script():
    """DEPRECATED: Use execution.framework.javascript.get_glossary_toggle_script instead"""
    from execution.framework.javascript import get_glossary_toggle_script as _new_func

    return _new_func()


def get_table_scroll_script():
    """DEPRECATED: Use execution.framework.javascript.get_table_scroll_script instead"""
    from execution.framework.javascript import get_table_scroll_script as _new_func

    return _new_func()


def get_expandable_row_script():
    """DEPRECATED: Use execution.framework.javascript.get_expandable_row_script instead"""
    from execution.framework.javascript import get_expandable_row_script as _new_func

    return _new_func()


__all__ = [
    "get_dashboard_framework",
    "get_theme_variables",
    "get_base_styles",
    "get_layout_components",
    "get_table_styles",
    "get_theme_toggle_styles",
    "get_metric_components",
    "get_collapsible_styles",
    "get_utility_styles",
    "get_theme_toggle_script",
    "get_glossary_toggle_script",
    "get_table_scroll_script",
    "get_expandable_row_script",
]
