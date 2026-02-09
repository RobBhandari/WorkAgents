"""
Dashboard Components - Reusable HTML building blocks

This package provides reusable functions for generating HTML components:
    - cards: Metric cards, summary cards
    - tables: Data tables with sorting
    - charts: Sparklines, trend indicators

Usage:
    from execution.dashboards.components.cards import metric_card
    from execution.dashboards.components.tables import data_table

    card_html = metric_card("Open Bugs", "42", trend="↓")
    table_html = data_table(["Name", "Value"], [["Item", "10"]])
"""

from .cards import metric_card, summary_card
from .charts import sparkline, trend_indicator
from .tables import data_table

__all__ = [
    "metric_card",
    "summary_card",
    "data_table",
    "sparkline",
    "trend_indicator",
]
