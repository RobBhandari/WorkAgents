"""
Jinja2 Template Engine for Safe HTML Generation

Provides centralized template loading and rendering with automatic XSS protection.
Replaces manual HTML string building with secure template-based rendering.

Usage:
    from execution.template_engine import render_template

    html = render_template('components/card.html',
                          title="Dashboard",
                          value=42)

Security Features:
    - Automatic HTML escaping (prevents XSS attacks)
    - Template validation
    - Centralized template management
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


class TemplateEngine:
    """
    Centralized template engine with security features.
    """

    def __init__(self, template_dir: Path | str = None):
        """
        Initialize template engine.

        Args:
            template_dir: Directory containing templates (default: execution/templates)
        """
        if template_dir is None:
            # Default to templates directory in execution folder
            template_dir = Path(__file__).parent / "templates"

        self.template_dir = Path(template_dir)

        # Create Jinja2 environment with security settings
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(["html", "xml"]),  # Auto-escape HTML
            trim_blocks=True,  # Remove first newline after template tag
            lstrip_blocks=True,  # Strip leading spaces/tabs from start of line
        )

    def render(self, template_name: str, **context: Any) -> str:
        """
        Render a template with given context.

        Args:
            template_name: Name of template file (relative to templates dir)
            **context: Template variables

        Returns:
            Rendered HTML string

        Example:
            html = engine.render('card.html', title="Metrics", value=100)
        """
        template = self.env.get_template(template_name)
        return template.render(**context)


# Global template engine instance
_engine: TemplateEngine | None = None


def get_template_engine() -> TemplateEngine:
    """
    Get the global template engine instance (singleton pattern).

    Returns:
        TemplateEngine: The template engine
    """
    global _engine
    if _engine is None:
        _engine = TemplateEngine()
    return _engine


def render_template(template_name: str, **context: Any) -> str:
    """
    Convenience function to render a template.

    Args:
        template_name: Name of template file
        **context: Template variables

    Returns:
        Rendered HTML string

    Example:
        from execution.template_engine import render_template

        html = render_template('components/card.html',
                              title="Quality Metrics",
                              value=95,
                              unit="%")
    """
    engine = get_template_engine()
    return engine.render(template_name, **context)
