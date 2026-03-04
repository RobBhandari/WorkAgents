#!/usr/bin/env python3
"""
TrendsRenderer - HTML rendering for Executive Trends Dashboard

Handles all HTML generation, template context building, and visual rendering
for the Executive Trends Dashboard showing 8 key metrics with sparklines.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from execution.dashboards.components.cards import SEVERITY_EMOJI
from execution.dashboards.renderer import render_dashboard
from execution.dashboards.trends.calculator import TrendsCalculator
from execution.framework import get_dashboard_framework

logger = logging.getLogger(__name__)

_DB_PATH = Path(".tmp/observatory/observatory.db")


class TrendsRenderer:
    """Renders Executive Trends Dashboard HTML with sparklines and interactive features"""

    def __init__(self, trends_data: dict[str, Any], target_progress: dict[str, Any] | None = None):
        """Initialize renderer with trends data

        Args:
            trends_data: Dictionary containing trends from all dashboards
                        (quality, security, flow, deployment, collaboration, ownership, risk)
            target_progress: Optional target progress data with forecast information
        """
        self.trends_data = trends_data
        self.target_progress = target_progress

    def generate_dashboard_file(self, output_path: Path) -> str:
        """Render full dashboard to HTML file

        Args:
            output_path: Path where HTML file should be written

        Returns:
            Path to generated HTML file as string
        """
        context = self.build_context()
        html_content = render_dashboard("dashboards/trends_dashboard.html", context)

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write HTML to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return str(output_path)

    def build_context(self) -> dict[str, Any]:
        """Build Jinja2-style template context

        Returns:
            Dictionary with metrics data, framework CSS/JS, and metadata
        """
        metrics_list = self._generate_metrics_list()

        framework_css, framework_js = get_dashboard_framework(
            header_gradient_start="#0f172a",  # Flat slate background
            header_gradient_end="#0f172a",  # Flat slate background
            include_table_scroll=True,
            include_expandable_rows=False,
            include_glossary=False,
        )

        return {
            "metrics": metrics_list,
            "metrics_json": json.dumps(metrics_list, indent=4),
            "framework_css": framework_css,
            "framework_js": framework_js,
            "generation_date": datetime.now().strftime("%B %d, %Y at %H:%M"),
            "timestamp": datetime.now().strftime("%B %d, %Y at %H:%M"),
            "active_alerts": self._load_alerts(),
        }

    def _load_alerts(self) -> list[dict[str, Any]]:
        """Load active alerts from the analytics DB for template rendering.

        Returns an empty list if the DB does not exist (e.g. first run before ETL).
        Each dict has keys: dashboard, project_name, metric_name, severity, message.
        """
        if not _DB_PATH.exists():
            return []

        try:
            from execution.ml.alert_engine import AlertEngine

            engine = AlertEngine(db_path=_DB_PATH)
            alerts = engine.load_alerts(limit=100)
            return [
                {
                    "dashboard": a.dashboard,
                    "project_name": a.project_name,
                    "metric_name": a.metric_name,
                    "metric_date": a.metric_date,
                    "alert_type": a.alert_type,
                    "severity": a.severity,
                    "severity_emoji": SEVERITY_EMOJI.get(a.severity, ""),
                    "message": a.message,
                    "root_cause_hint": a.root_cause_hint,
                }
                for a in alerts
            ]
        except Exception:
            logger.warning("Could not load alerts from analytics DB", exc_info=True)
            return []

    def _build_standard_metric(
        self,
        metric_id: str,
        icon: str,
        title: str,
        description: str,
        data: dict[str, Any],
        rag_metric_type: str,
        good_direction: str,
        dashboard_url: str,
        round_change: bool = False,
    ) -> dict[str, Any]:
        """Build a standard metric dict from a trend data sub-dict."""
        arrow, css_class, change = self._get_trend_indicator(data["current"], data["previous"], good_direction)
        rag_color = self._get_rag_color(data["current"], rag_metric_type)
        return {
            "id": metric_id,
            "icon": icon,
            "title": title,
            "description": description,
            "current": data["current"],
            "unit": data["unit"],
            "change": round(change, 1) if round_change else change,
            "changeLabel": "vs last week",
            "data": data["trend_data"],
            "arrow": arrow,
            "cssClass": css_class,
            "ragColor": rag_color,
            "dashboardUrl": dashboard_url,
        }

    def _generate_metrics_list(self) -> list[dict[str, Any]]:
        """Generate list of metrics with trend data for JavaScript rendering

        Returns:
            List of metric dictionaries with sparkline data and metadata
        """
        metrics = []

        # 1. Target Progress
        if self.target_progress:
            arrow, css_class, change = self._get_trend_indicator(
                self.target_progress["current"], self.target_progress["previous"], "up"
            )
            rag_color = self._get_rag_color(self.target_progress["current"], "target_progress")
            metrics.append(
                {
                    "id": "target",
                    "icon": "🎯",
                    "title": "70% Reduction Target",
                    "description": "Track progress toward 70% reduction goals for security vulnerabilities and bugs. Combined progress from Dec 1, 2025 baseline through June 30, 2026.",
                    "current": self.target_progress["current"],
                    "unit": self.target_progress["unit"],
                    "change": round(change, 1),
                    "changeLabel": "vs last week",
                    "data": self.target_progress["trend_data"],
                    "arrow": arrow,
                    "cssClass": css_class,
                    "ragColor": rag_color,
                    "dashboardUrl": "target_dashboard.html",
                }
            )

        # 2. AI Usage Tracker (Static launcher - no trend data)
        metrics.append(
            {
                "id": "ai-usage",
                "icon": "🤖",
                "title": "AI Usage Tracker",
                "description": "Monitor Claude and Devin usage across team members. Track adoption and activity patterns.",
                "current": "",
                "unit": "",
                "change": "",
                "changeLabel": "",
                "data": [],  # Empty array - no sparkline needed for launcher
                "arrow": "",
                "cssClass": "trend-stable",
                "ragColor": "#6366f1",
                "dashboardUrl": "usage_tables_latest.html",
            }
        )

        self._append_standard_metrics(metrics)
        return metrics

    # Ordered list of (trends_data_key, sub_key, metric_id, icon, title, description,
    #                   rag_metric_type, good_direction, dashboard_url, round_change)
    _METRIC_CONFIGS: list[tuple[str, str, str, str, str, str, str, str, str, bool]] = [
        (
            "security_code_cloud",
            "vulnerabilities",
            "security",
            "🔒",
            "Security: Code & Cloud",
            "Code and cloud vulnerability trends (Mend, SonarQube, Prisma). Tracks the 70% reduction target.",
            "total_vulns",
            "down",
            "security_dashboard.html",
            False,
        ),
        (
            "security_infra",
            "vulnerabilities",
            "security-infra",
            "🛡️",
            "Security: Infrastructure",
            "Infrastructure vulnerability trends (Cortex XDR, Tenable, AppCheck, BitSight). Not included in 70% target.",
            "total_vulns",
            "down",
            "security_infrastructure_dashboard.html",
            False,
        ),
        (
            "quality",
            "bugs",
            "bugs",
            "🐛",
            "Open Bugs",
            "Track bug resolution speed and open bug trends. Measure how quickly issues are fixed across teams.",
            "bugs",
            "down",
            "quality_dashboard.html",
            False,
        ),
        (
            "flow",
            "lead_time",
            "flow",
            "🔄",
            "Lead Time (P85)",
            "Measure delivery speed, work in progress, and throughput across teams. See bottlenecks before they become problems.",
            "lead_time",
            "down",
            "flow_dashboard.html",
            True,
        ),
        (
            "deployment",
            "build_success",
            "deployment",
            "🚀",
            "Build Success Rate",
            "Track deployment frequency, build success rates, and lead time for changes. Measure DevOps performance.",
            "success_rate",
            "up",
            "deployment_dashboard.html",
            True,
        ),
        (
            "collaboration",
            "pr_merge_time",
            "collaboration",
            "🤝",
            "PR Merge Time",
            "Monitor code review efficiency, PR merge times, and review iterations. Optimize team collaboration.",
            "merge_time",
            "down",
            "collaboration_dashboard.html",
            True,
        ),
        (
            "ownership",
            "work_unassigned",
            "ownership",
            "👤",
            "Work Unassigned",
            "Track work assignment clarity and orphan areas. Identify ownership gaps early.",
            "unassigned",
            "down",
            "ownership_dashboard.html",
            True,
        ),
        (
            "risk",
            "total_commits",
            "risk",
            "📊",
            "Total Commits",
            "Track code change activity and commit patterns. Understand delivery risk through Git metrics.",
            "commits",
            "stable",
            "risk_dashboard.html",
            False,
        ),
    ]

    def _append_standard_metrics(self, metrics: list[dict[str, Any]]) -> None:
        """Append all data-driven metric cards to the metrics list.

        First handles the exploitable metric (custom RAG logic), then iterates
        _METRIC_CONFIGS for the remaining standard metrics.
        """
        # Exploitable Vulns (custom RAG logic — severity-based color)
        exploitable = self.trends_data.get("exploitable", {})
        if exploitable:
            metrics.append(self._build_exploitable_metric(exploitable["exploitable"]))

        # All remaining standard metrics
        for cfg in self._METRIC_CONFIGS:
            data_key, sub_key, metric_id, icon, title, description, rag_type, direction, url, round_chg = cfg
            source = self.trends_data.get(data_key, {})
            if source:
                metrics.append(
                    self._build_standard_metric(
                        metric_id,
                        icon,
                        title,
                        description,
                        source[sub_key],
                        rag_type,
                        direction,
                        url,
                        round_change=round_chg,
                    )
                )

    def _build_exploitable_metric(self, exp: dict[str, Any]) -> dict[str, Any]:
        """Build the Exploitable Vulns metric dict (custom severity-based RAG color)."""
        arrow, css_class, change = self._get_trend_indicator(exp["current"], exp["previous"], "down")
        rag_color = "#ef4444" if exp["current_critical"] > 0 else ("#f59e0b" if exp["current_high"] > 0 else "#10b981")
        return {
            "id": "exploitable",
            "icon": "🎯",
            "title": "Exploitable Vulns",
            "description": "CISA KEV exploitable findings by product. Critical = immediate action required.",
            "current": exp["current"],
            "unit": exp["unit"],
            "change": change,
            "changeLabel": "vs last week",
            "data": exp["trend_data"],
            "arrow": arrow,
            "cssClass": css_class,
            "ragColor": rag_color,
            "dashboardUrl": "exploitable_dashboard.html",
        }

    def _get_trend_indicator(
        self, current: float, previous: float, good_direction: str = "down"
    ) -> tuple[str, str, float]:
        """Get trend indicator (↑↓→) and CSS class

        Args:
            current: Current metric value
            previous: Previous metric value
            good_direction: Direction that is good ('up', 'down', or 'stable')

        Returns:
            Tuple of (arrow, css_class, change)
        """
        change = current - previous

        if abs(change) < 0.5:
            return ("→", "trend-stable", change)

        is_increasing = change > 0

        if good_direction == "down":
            if is_increasing:
                return ("↑", "trend-up", change)  # Red (bad)
            else:
                return ("↓", "trend-down", change)  # Green (good)
        else:  # good_direction == 'up'
            if is_increasing:
                return ("↑", "trend-down", change)  # Green (good)
            else:
                return ("↓", "trend-up", change)  # Red (bad)

    def _get_rag_color(self, value: Any, metric_type: str) -> str:
        """Determine RAG color based on metric value and type

        Args:
            value: Metric value to evaluate
            metric_type: Type of metric for threshold determination

        Returns:
            Hex color code for RAG status
        """
        return TrendsCalculator.get_rag_color(value, metric_type)
