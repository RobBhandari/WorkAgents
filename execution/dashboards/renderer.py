"""
Template Rendering Utilities

Provides Jinja2-based template rendering for dashboards with:
    - Auto-escaping (XSS protection)
    - Custom filters
    - Template inheritance

Usage:
    from execution.dashboards.renderer import render_dashboard

    context = {
        'title': 'My Dashboard',
        'metrics': [...]
    }

    html = render_dashboard('dashboards/security_dashboard.html', context)
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from execution.core import get_logger
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = get_logger(__name__)

# Initialize Jinja2 environment (singleton)
_jinja_env: Environment | None = None


def get_jinja_environment() -> Environment:
    """
    Get or create the Jinja2 environment.

    Returns:
        Configured Jinja2 Environment instance
    """
    global _jinja_env

    if _jinja_env is None:
        # Find templates directory (relative to this file)
        template_dir = Path(__file__).parent.parent.parent / "templates"

        # Create environment with auto-escaping for security
        _jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        _jinja_env.filters["format_number"] = format_number
        _jinja_env.filters["format_percent"] = format_percent
        _jinja_env.filters["format_date"] = format_date
        _jinja_env.filters["trend_arrow"] = trend_arrow

    return _jinja_env


def render_dashboard(template_name: str, context: dict[str, Any], inject_defaults: bool = True) -> str:
    """
    Render a dashboard template with context.

    Args:
        template_name: Template file name (relative to templates/)
        context: Dictionary of template variables
        inject_defaults: Whether to inject default variables (generation_date, etc.)

    Returns:
        Rendered HTML string

    Example:
        html = render_dashboard('dashboards/security.html', {
            'products': [...],
            'summary_cards': [...]
        })
    """
    env = get_jinja_environment()
    template = env.get_template(template_name)

    # Inject default variables if requested
    if inject_defaults:
        defaults = {
            "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "show_glossary": True,
        }
        # Merge with user context (user context takes precedence)
        final_context = {**defaults, **context}
    else:
        final_context = context

    rendered: str = template.render(**final_context)
    return rendered


# Custom Jinja2 filters


def format_number(value: Any, decimals: int = 0) -> str:
    """
    Format number with thousand separators.

    Args:
        value: Numeric value
        decimals: Number of decimal places

    Returns:
        Formatted string

    Example:
        {{ 1234.56|format_number }} -> "1,235"
        {{ 1234.56|format_number(2) }} -> "1,234.56"
    """
    try:
        num = float(value)
        if decimals == 0:
            return f"{int(num):,}"
        else:
            return f"{num:,.{decimals}f}"
    except (ValueError, TypeError):
        return str(value)


def format_percent(value: Any, decimals: int = 1) -> str:
    """
    Format number as percentage.

    Args:
        value: Numeric value (0-100)
        decimals: Number of decimal places

    Returns:
        Formatted percentage string

    Example:
        {{ 65.432|format_percent }} -> "65.4%"
        {{ 65.432|format_percent(2) }} -> "65.43%"
    """
    try:
        num = float(value)
        return f"{num:.{decimals}f}%"
    except (ValueError, TypeError):
        return str(value)


def format_date(value: Any, format_str: str = "%Y-%m-%d") -> str:
    """
    Format datetime object as string.

    Args:
        value: datetime object or ISO string
        format_str: strftime format string

    Returns:
        Formatted date string

    Example:
        {{ some_date|format_date }} -> "2026-02-07"
        {{ some_date|format_date('%B %d, %Y') }} -> "February 07, 2026"
    """
    if isinstance(value, datetime):
        return value.strftime(format_str)
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
            return dt.strftime(format_str)
        except ValueError:
            return value
    else:
        return str(value)


def trend_arrow(value: float) -> str:
    """
    Convert numeric change to trend arrow.

    Args:
        value: Numeric change value

    Returns:
        Unicode arrow character

    Example:
        {{ -5|trend_arrow }} -> "↓"
        {{ 10|trend_arrow }} -> "↑"
        {{ 0|trend_arrow }} -> "→"
    """
    if value > 0:
        return "↑"
    elif value < 0:
        return "↓"
    else:
        return "→"


# Convenience function for testing
if __name__ == "__main__":
    """Test template rendering"""
    logger.info("Testing template renderer")

    context = {
        "summary_cards": [
            '<div class="summary-card">Test Card 1</div>',
            '<div class="summary-card">Test Card 2</div>',
        ],
        "products": [
            {
                "name": "Test Product",
                "total": 10,
                "critical": 2,
                "high": 5,
                "medium": 3,
                "status": "Action Required",
                "status_class": "action",
                "expandable": False,
            }
        ],
        "framework_css": "<style>/* Test CSS */</style>",
        "framework_js": "<script>/* Test JS */</script>",
    }

    html = render_dashboard("dashboards/security_dashboard.html", context)
    logger.info("Template rendered successfully", extra={"html_size": len(html)})
    logger.info("Preview", extra={"preview": html[:500]})
