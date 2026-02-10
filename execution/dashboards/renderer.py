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

from jinja2 import Environment, FileSystemLoader, select_autoescape

from execution.core import get_logger

logger = get_logger(__name__)

# Initialize Jinja2 environment (singleton)
_jinja_env: Environment | None = None


def get_jinja_environment() -> Environment:
    """
    Get or create the Jinja2 environment (singleton pattern).

    Initializes Jinja2 with security-focused configuration:
    - Auto-escaping enabled for HTML/XML to prevent XSS
    - Custom filters for number/date formatting
    - Trim blocks and lstrip for clean output

    :returns: Configured Jinja2 Environment with custom filters registered
    :raises FileNotFoundError: If templates directory doesn't exist

    Example:
        >>> env = get_jinja_environment()
        >>> template = env.get_template('dashboards/security_dashboard.html')
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
    Render a dashboard template with context data.

    Main entry point for dashboard generation. Loads Jinja2 template,
    merges context with defaults, and returns rendered HTML.

    :param template_name: Template file name relative to templates/ directory
        (e.g., 'dashboards/security_dashboard.html')
    :param context: Dictionary of template variables (metrics, cards, etc.)
    :param inject_defaults: Whether to inject default variables like generation_date (default: True)
    :returns: Fully rendered HTML string with XSS-safe escaping
    :raises jinja2.TemplateNotFound: If template file doesn't exist
    :raises jinja2.TemplateSyntaxError: If template has syntax errors

    Example:
        >>> html = render_dashboard('dashboards/security_dashboard.html', {
        ...     'products': [...],
        ...     'summary_cards': [...]
        ... })
        >>> len(html) > 0
        True
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
    Format number with thousand separators (Jinja2 filter).

    Converts numeric values to human-readable strings with commas.
    Handles invalid inputs gracefully by returning string representation.

    :param value: Numeric value to format
    :param decimals: Number of decimal places (default: 0)
    :returns: Formatted string with thousand separators

    Example:
        >>> format_number(1234.56)
        '1,235'
        >>> format_number(1234.56, 2)
        '1,234.56'

        In Jinja2 template:
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
    Format number as percentage string (Jinja2 filter).

    :param value: Numeric value (0-100 scale)
    :param decimals: Number of decimal places (default: 1)
    :returns: Formatted percentage string with % symbol

    Example:
        >>> format_percent(65.432)
        '65.4%'
        >>> format_percent(65.432, 2)
        '65.43%'

        In Jinja2 template:
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
    Format datetime object as string (Jinja2 filter).

    Handles both datetime objects and ISO 8601 strings.

    :param value: datetime object or ISO format string
    :param format_str: strftime format string (default: "%Y-%m-%d")
    :returns: Formatted date string

    Example:
        >>> from datetime import datetime
        >>> dt = datetime(2026, 2, 7)
        >>> format_date(dt)
        '2026-02-07'
        >>> format_date(dt, '%B %d, %Y')
        'February 07, 2026'

        In Jinja2 template:
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
    Convert numeric change to trend arrow (Jinja2 filter).

    :param value: Numeric change value (positive, negative, or zero)
    :returns: Unicode arrow character (↑ for positive, ↓ for negative, → for zero)

    Example:
        >>> trend_arrow(-5)
        '↓'
        >>> trend_arrow(10)
        '↑'
        >>> trend_arrow(0)
        '→'

        In Jinja2 template:
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
