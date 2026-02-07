"""
Card components for dashboards

Provides reusable metric and summary card HTML generators.
"""

from typing import Optional


def metric_card(
    title: str,
    value: str,
    subtitle: str = "",
    trend: str = "",
    css_class: str = ""
) -> str:
    """
    Generate a metric card HTML component.

    Args:
        title: Card title
        value: Main value to display (large text)
        subtitle: Optional subtitle or description
        trend: Optional trend indicator (↑, ↓, →, or custom text)
        css_class: Optional CSS class for styling (e.g., 'rag-green')

    Returns:
        HTML string for metric card

    Example:
        html = metric_card(
            title="Open Bugs",
            value="42",
            subtitle="5 fewer than last week",
            trend="↓",
            css_class="rag-green"
        )
    """
    trend_html = f'<span class="trend">{trend}</span>' if trend else ''
    subtitle_html = f'<div class="metric-unit">{subtitle}</div>' if subtitle else ''

    return f'''
    <div class="summary-card {css_class}">
        <div class="metric-label">{title}</div>
        <div class="metric-value">{value} {trend_html}</div>
        {subtitle_html}
    </div>
    '''


def summary_card(
    title: str,
    value: str,
    css_class: str = "",
    subtitle: str = ""
) -> str:
    """
    Generate a summary card HTML component (for executive dashboard).

    Args:
        title: Card title
        value: Value to display
        css_class: Optional CSS class (e.g., 'critical', 'high', 'good')
        subtitle: Optional subtitle

    Returns:
        HTML string for summary card

    Example:
        html = summary_card(
            title="Critical Vulnerabilities",
            value="3",
            css_class="critical",
            subtitle="Immediate attention required"
        )
    """
    subtitle_html = f'<div class="card-subtitle">{subtitle}</div>' if subtitle else ''

    return f'''
    <div class="summary-card {css_class}">
        <h3 class="card-title">{title}</h3>
        <div class="card-value">{value}</div>
        {subtitle_html}
    </div>
    '''


def rag_status_badge(status: str) -> str:
    """
    Generate a RAG (Red-Amber-Green) status badge.

    Args:
        status: Status text ('good', 'warning', 'critical', 'action')

    Returns:
        HTML string for status badge

    Example:
        badge = rag_status_badge('critical')
        # Returns: <span class="status-badge status-action">CRITICAL</span>
    """
    status_lower = status.lower()

    css_class_map = {
        'good': 'status-good',
        'ok': 'status-good',
        'green': 'status-good',
        'warning': 'status-caution',
        'caution': 'status-caution',
        'amber': 'status-caution',
        'critical': 'status-action',
        'action': 'status-action',
        'red': 'status-action',
        'inactive': 'status-inactive',
        'unknown': 'status-inactive',
    }

    css_class = css_class_map.get(status_lower, 'status-inactive')
    display_text = status.upper()

    return f'<span class="status-badge {css_class}">{display_text}</span>'


def attention_item_card(
    severity: str,
    category: str,
    message: str
) -> str:
    """
    Generate an attention item card for executive dashboard.

    Args:
        severity: 'high', 'medium', or 'low'
        category: Category (e.g., 'Security', 'Quality', 'Flow')
        message: Descriptive message

    Returns:
        HTML string for attention item

    Example:
        card = attention_item_card(
            severity='high',
            category='Security',
            message='5 critical vulnerabilities need immediate attention'
        )
    """
    severity_map = {
        'high': 'rag-red',
        'medium': 'rag-amber',
        'low': 'rag-green'
    }

    css_class = severity_map.get(severity.lower(), '')

    return f'''
    <div class="attention-item {css_class}">
        <div class="attention-category">{category}</div>
        <div class="attention-message">{message}</div>
    </div>
    '''
