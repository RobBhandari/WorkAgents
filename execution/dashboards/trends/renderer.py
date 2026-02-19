#!/usr/bin/env python3
"""
TrendsRenderer - HTML rendering for Executive Trends Dashboard

Handles all HTML generation, template context building, and visual rendering
for the Executive Trends Dashboard showing 8 key metrics with sparklines.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from execution.dashboards.renderer import render_dashboard
from execution.framework import get_dashboard_framework


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

        # 3. Security Vulnerabilities
        security = self.trends_data.get("security", {})
        if security:
            vulns = security.get("vulnerabilities", {})
            arrow, css_class, change = self._get_trend_indicator(vulns["current"], vulns["previous"], "down")
            rag_color = self._get_rag_color(vulns["current"], "total_vulns")
            metrics.append(
                {
                    "id": "security",
                    "icon": "🔒",
                    "title": "Security Vulnerabilities",
                    "description": "Track vulnerability trends and security debt. Translate scanner noise into engineering action.",
                    "current": vulns["current"],
                    "unit": vulns["unit"],
                    "change": change,
                    "changeLabel": "vs last week",
                    "data": vulns["trend_data"],
                    "arrow": arrow,
                    "cssClass": css_class,
                    "ragColor": rag_color,
                    "dashboardUrl": "security_dashboard.html",
                }
            )

        # 4. Exploitable Vulns
        exploitable = self.trends_data.get("exploitable", {})
        if exploitable:
            exp = exploitable.get("exploitable", {})
            arrow, css_class, change = self._get_trend_indicator(exp["current"], exp["previous"], "down")
            rag_color = (
                "#ef4444" if exp["current_critical"] > 0 else ("#f59e0b" if exp["current_high"] > 0 else "#10b981")
            )
            metrics.append(
                {
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
            )

        # 5. Open Bugs
        quality = self.trends_data.get("quality", {})
        if quality:
            bugs = quality.get("bugs", {})
            arrow, css_class, change = self._get_trend_indicator(bugs["current"], bugs["previous"], "down")
            rag_color = self._get_rag_color(bugs["current"], "bugs")
            metrics.append(
                {
                    "id": "bugs",
                    "icon": "🐛",
                    "title": "Open Bugs",
                    "description": "Track bug resolution speed and open bug trends. Measure how quickly issues are fixed across teams.",
                    "current": bugs["current"],
                    "unit": bugs["unit"],
                    "change": change,
                    "changeLabel": "vs last week",
                    "data": bugs["trend_data"],
                    "arrow": arrow,
                    "cssClass": css_class,
                    "ragColor": rag_color,
                    "dashboardUrl": "quality_dashboard.html",
                }
            )

        # 5. Lead Time
        flow = self.trends_data.get("flow", {})
        if flow:
            lead_time = flow.get("lead_time", {})
            arrow, css_class, change = self._get_trend_indicator(lead_time["current"], lead_time["previous"], "down")
            rag_color = self._get_rag_color(lead_time["current"], "lead_time")
            metrics.append(
                {
                    "id": "flow",
                    "icon": "🔄",
                    "title": "Lead Time (P85)",
                    "description": "Measure delivery speed, work in progress, and throughput across teams. See bottlenecks before they become problems.",
                    "current": lead_time["current"],
                    "unit": lead_time["unit"],
                    "change": round(change, 1),
                    "changeLabel": "vs last week",
                    "data": lead_time["trend_data"],
                    "arrow": arrow,
                    "cssClass": css_class,
                    "ragColor": rag_color,
                    "dashboardUrl": "flow_dashboard.html",
                }
            )

        # 6. Build Success Rate
        deployment = self.trends_data.get("deployment", {})
        if deployment:
            build_success = deployment.get("build_success", {})
            arrow, css_class, change = self._get_trend_indicator(
                build_success["current"], build_success["previous"], "up"
            )
            rag_color = self._get_rag_color(build_success["current"], "success_rate")
            metrics.append(
                {
                    "id": "deployment",
                    "icon": "🚀",
                    "title": "Build Success Rate",
                    "description": "Track deployment frequency, build success rates, and lead time for changes. Measure DevOps performance.",
                    "current": build_success["current"],
                    "unit": build_success["unit"],
                    "change": round(change, 1),
                    "changeLabel": "vs last week",
                    "data": build_success["trend_data"],
                    "arrow": arrow,
                    "cssClass": css_class,
                    "ragColor": rag_color,
                    "dashboardUrl": "deployment_dashboard.html",
                }
            )

        # 7. PR Merge Time
        collaboration = self.trends_data.get("collaboration", {})
        if collaboration:
            pr_merge = collaboration.get("pr_merge_time", {})
            arrow, css_class, change = self._get_trend_indicator(pr_merge["current"], pr_merge["previous"], "down")
            rag_color = self._get_rag_color(pr_merge["current"], "merge_time")
            metrics.append(
                {
                    "id": "collaboration",
                    "icon": "🤝",
                    "title": "PR Merge Time",
                    "description": "Monitor code review efficiency, PR merge times, and review iterations. Optimize team collaboration.",
                    "current": pr_merge["current"],
                    "unit": pr_merge["unit"],
                    "change": round(change, 1),
                    "changeLabel": "vs last week",
                    "data": pr_merge["trend_data"],
                    "arrow": arrow,
                    "cssClass": css_class,
                    "ragColor": rag_color,
                    "dashboardUrl": "collaboration_dashboard.html",
                }
            )

        # 8. Work Unassigned
        ownership = self.trends_data.get("ownership", {})
        if ownership:
            unassigned = ownership.get("work_unassigned", {})
            arrow, css_class, change = self._get_trend_indicator(unassigned["current"], unassigned["previous"], "down")
            rag_color = self._get_rag_color(unassigned["current"], "unassigned")
            metrics.append(
                {
                    "id": "ownership",
                    "icon": "👤",
                    "title": "Work Unassigned",
                    "description": "Track work assignment clarity and orphan areas. Identify ownership gaps early.",
                    "current": unassigned["current"],
                    "unit": unassigned["unit"],
                    "change": round(change, 1),
                    "changeLabel": "vs last week",
                    "data": unassigned["trend_data"],
                    "arrow": arrow,
                    "cssClass": css_class,
                    "ragColor": rag_color,
                    "dashboardUrl": "ownership_dashboard.html",
                }
            )

        # 9. Total Commits (Risk)
        risk = self.trends_data.get("risk", {})
        if risk:
            commits = risk.get("total_commits", {})
            arrow, css_class, change = self._get_trend_indicator(commits["current"], commits["previous"], "stable")
            rag_color = self._get_rag_color(commits["current"], "commits")
            metrics.append(
                {
                    "id": "risk",
                    "icon": "📊",
                    "title": "Total Commits",
                    "description": "Track code change activity and commit patterns. Understand delivery risk through Git metrics.",
                    "current": commits["current"],
                    "unit": commits["unit"],
                    "change": change,
                    "changeLabel": "vs last week",
                    "data": commits["trend_data"],
                    "arrow": arrow,
                    "cssClass": css_class,
                    "ragColor": rag_color,
                    "dashboardUrl": "risk_dashboard.html",
                }
            )

        return metrics

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
        if value == "N/A" or value is None:
            return "#94a3b8"  # Gray for N/A

        try:
            if metric_type == "lead_time":
                # Lower is better: <30 days green, 30-60 amber, >60 red
                val = float(value)
                if val < 30:
                    return "#10b981"  # Green
                elif val < 60:
                    return "#f59e0b"  # Amber
                else:
                    return "#ef4444"  # Red

            elif metric_type == "mttr":
                # Lower is better: <7 days green, 7-14 days amber, >14 days red
                val = float(value)
                if val < 7:
                    return "#10b981"
                elif val < 14:
                    return "#f59e0b"
                else:
                    return "#ef4444"

            elif metric_type == "total_vulns":
                # Lower is better: <150 green, 150-250 amber, >250 red
                val = int(value)
                if val < 150:
                    return "#10b981"
                elif val < 250:
                    return "#f59e0b"
                else:
                    return "#ef4444"

            elif metric_type == "bugs":
                # Lower is better: <100 green, 100-200 amber, >200 red
                val = int(value)
                if val < 100:
                    return "#10b981"
                elif val < 200:
                    return "#f59e0b"
                else:
                    return "#ef4444"

            elif metric_type == "success_rate":
                # Higher is better: >90% green, 70-90% amber, <70% red
                val = float(value)
                if val >= 90:
                    return "#10b981"
                elif val >= 70:
                    return "#f59e0b"
                else:
                    return "#ef4444"

            elif metric_type == "merge_time":
                # Lower is better: <4h green, 4-24h amber, >24h red
                val = float(value)
                if val < 4:
                    return "#10b981"
                elif val < 24:
                    return "#f59e0b"
                else:
                    return "#ef4444"

            elif metric_type == "unassigned":
                # Lower is better: <20% green, 20-40% amber, >40% red
                val = float(value)
                if val < 20:
                    return "#10b981"
                elif val < 40:
                    return "#f59e0b"
                else:
                    return "#ef4444"

            elif metric_type == "target_progress":
                # Higher is better: >=70% green, 40-70% amber, <40% red
                val = float(value)
                if val >= 70:
                    return "#10b981"
                elif val >= 40:
                    return "#f59e0b"
                else:
                    return "#ef4444"

            elif metric_type == "commits":
                # Neutral metric - no RAG thresholds
                return "#6366f1"  # Purple

            return "#6366f1"  # Default purple
        except (ValueError, TypeError):
            return "#94a3b8"  # Gray for invalid values
