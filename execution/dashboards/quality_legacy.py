"""
Quality Dashboard HTML Generation

Generates HTML components for the quality dashboard via Jinja2 templates.
"""

from typing import Any

from execution.template_engine import render_template


def build_summary_cards(summary_stats: dict[str, Any]) -> str:
    """
    Build summary metric cards HTML.

    Args:
        summary_stats: Summary statistics dictionary

    Returns:
        Rendered HTML string for summary cards
    """
    cards = [
        {
            "label": "MTTR (Mean Time To Repair)",
            "value": f"{summary_stats['avg_mttr']:.1f}",
            "unit": "days",
            "explanation": "Average time from bug creation to closure",
            "border_color": None,
        },
        {
            "label": "Total Bugs Analyzed",
            "value": f"{summary_stats['total_bugs']:,}",
            "unit": None,
            "explanation": "Bugs analyzed in last 90 days",
            "border_color": "#3b82f6",
        },
        {
            "label": "Open Bugs",
            "value": f"{summary_stats['total_open']:,}",
            "unit": None,
            "explanation": "Currently open bugs across all projects",
            "border_color": "#f59e0b",
        },
        {
            "label": "Security Bugs Excluded",
            "value": f"{summary_stats['total_excluded']:,}",
            "unit": None,
            "explanation": "ArmorCode bugs excluded to prevent double-counting",
            "border_color": "#10b981",
        },
    ]
    return render_template("dashboards/quality_summary_cards.html", cards=cards)


def generate_distribution_section(title: str, distribution: dict[str, Any], bucket_type: str, unit: str) -> str:
    """
    Generate a distribution section with colored buckets.

    Args:
        title: Section title
        distribution: Distribution data
        bucket_type: Type of bucket (bug_age or mttr)
        unit: Unit label (e.g., "bugs")

    Returns:
        HTML string for distribution section
    """
    if bucket_type == "bug_age":
        bucket_keys = [
            ("0-7 Days", "0-7_days"),
            ("8-30 Days", "8-30_days"),
            ("31-90 Days", "31-90_days"),
            ("90+ Days", "90+_days"),
        ]
    else:  # mttr
        bucket_keys = [
            ("0-1 Days", "0-1_days"),
            ("1-7 Days", "1-7_days"),
            ("7-30 Days", "7-30_days"),
            ("30+ Days", "30+_days"),
        ]

    buckets = []
    for label, key in bucket_keys:
        count = distribution.get(key, 0)
        rag_class, rag_color = get_distribution_bucket_rag_status(bucket_type, key)
        buckets.append(
            {
                "label": label,
                "value": f"{count} {unit}",
                "rag_class": rag_class,
                "rag_color": rag_color,
            }
        )

    return render_template(
        "dashboards/quality_distribution_section.html",
        title=title,
        buckets=buckets,
    )


def get_distribution_bucket_rag_status(bucket_type: str, bucket_name: str) -> tuple[str, str]:
    """Determine RAG status for distribution buckets.

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
