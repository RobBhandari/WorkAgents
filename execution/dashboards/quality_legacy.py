"""
Quality Dashboard Legacy HTML Generation

These functions generate HTML directly in Python code.
They are being kept for backward compatibility but should be
migrated to Jinja2 templates in the future.

TODO: Migrate these functions to use Jinja2 templates instead of inline HTML.
"""

from typing import Any

from execution.template_engine import render_template


def build_summary_cards(summary_stats: dict[str, Any]) -> list[str]:
    """
    Build summary metric cards HTML.

    LEGACY: Uses inline HTML generation. Should migrate to Jinja2 templates.

    Args:
        summary_stats: Summary statistics dictionary

    Returns:
        List of HTML strings for metric cards
    """
    cards = []

    # MTTR Card
    cards.append(f"""<div class="summary-card">
            <div class="label">MTTR (Mean Time To Repair)</div>
            <div class="value">{summary_stats['avg_mttr']:.1f}<span class="unit">days</span></div>
            <div class="explanation">Average time from bug creation to closure</div>
        </div>""")

    # Total Bugs Card
    cards.append(f"""<div class="summary-card" style="border-left-color: #3b82f6;">
            <div class="label">Total Bugs Analyzed</div>
            <div class="value">{summary_stats['total_bugs']:,}</div>
            <div class="explanation">Bugs analyzed in last 90 days</div>
        </div>""")

    # Open Bugs Card
    cards.append(f"""<div class="summary-card" style="border-left-color: #f59e0b;">
            <div class="label">Open Bugs</div>
            <div class="value">{summary_stats['total_open']:,}</div>
            <div class="explanation">Currently open bugs across all projects</div>
        </div>""")

    # Security Bugs Excluded Card
    cards.append(f"""<div class="summary-card" style="border-left-color: #10b981;">
            <div class="label">Security Bugs Excluded</div>
            <div class="value">{summary_stats['total_excluded']:,}</div>
            <div class="explanation">ArmorCode bugs excluded to prevent double-counting</div>
        </div>""")

    return cards


def generate_distribution_section(title: str, distribution: dict[str, Any], bucket_type: str, unit: str) -> str:
    """
    Generate a distribution section with colored buckets.

    LEGACY: Uses inline HTML generation. Should migrate to Jinja2 templates.

    Args:
        title: Section title
        distribution: Distribution data
        bucket_type: Type of bucket (bug_age or mttr)
        unit: Unit label (e.g., "bugs")

    Returns:
        HTML string for distribution section
    """
    html = '<div class="detail-section">'
    html += f"<h4>{title}</h4>"
    html += '<div class="detail-grid">'

    # Define bucket names based on type
    if bucket_type == "bug_age":
        buckets = [
            ("0-7 Days", "0-7_days"),
            ("8-30 Days", "8-30_days"),
            ("31-90 Days", "31-90_days"),
            ("90+ Days", "90+_days"),
        ]
    else:  # mttr
        buckets = [
            ("0-1 Days", "0-1_days"),
            ("1-7 Days", "1-7_days"),
            ("7-30 Days", "7-30_days"),
            ("30+ Days", "30+_days"),
        ]

    for label, key in buckets:
        count = distribution.get(key, 0)
        rag_class, rag_color = get_distribution_bucket_rag_status(bucket_type, key)
        html += render_template(
            "dashboards/detail_metric.html",
            rag_class=rag_class,
            rag_color=rag_color,
            label=label,
            value=f"{count} {unit}",
        )

    html += "</div></div>"
    return html


def get_distribution_bucket_rag_status(bucket_type: str, bucket_name: str) -> tuple[str, str]:
    """
    Determine RAG status for distribution buckets.

    Returns: (color_class, color_hex)
    """
    if bucket_type == "bug_age":
        if bucket_name in ["0-7_days", "8-30_days"]:
            return "rag-green", "#10b981"
        elif bucket_name == "31-90_days":
            return "rag-amber", "#f59e0b"
        elif bucket_name == "90+_days":
            return "rag-red", "#ef4444"
    elif bucket_type == "mttr":
        if bucket_name in ["0-1_days", "1-7_days"]:
            return "rag-green", "#10b981"
        elif bucket_name == "7-30_days":
            return "rag-amber", "#f59e0b"
        elif bucket_name == "30+_days":
            return "rag-red", "#ef4444"

    # Default
    return "rag-unknown", "#6b7280"
