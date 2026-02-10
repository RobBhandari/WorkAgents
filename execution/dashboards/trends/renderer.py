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

    def render_dashboard(self, output_path: Path) -> str:
        """Render full dashboard to HTML file

        Args:
            output_path: Path where HTML file should be written

        Returns:
            Path to generated HTML file as string
        """
        html_content = self._generate_html()

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
            header_gradient_start="#667eea",
            header_gradient_end="#764ba2",
            include_table_scroll=True,
            include_expandable_rows=False,
            include_glossary=False,
        )

        return {
            "metrics": metrics_list,
            "metrics_json": json.dumps(metrics_list, indent=4),
            "framework_css": framework_css,
            "framework_js": framework_js,
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

        # 4. Open Bugs
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

    def _generate_html(self) -> str:
        """Generate complete HTML dashboard with embedded styles and JavaScript

        Returns:
            Complete HTML document as string
        """
        context = self.build_context()
        now = datetime.now()

        html = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Executive Trends - Director Observatory</title>
    {context['framework_css']}
    <style>
        /* Dashboard-specific styles */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}

        @media (max-width: 1024px) {{
            .metrics-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .metric-card {{
            background: var(--bg-secondary);
            padding: 24px;
            border-radius: 12px;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .forecast-banner {{
            --bg-primary: #f9fafb;
            --bg-secondary: #ffffff;
            --bg-card: #ffffff;
            --text-primary: #1f2937;
            --text-secondary: #6b7280;
            --border-color: #e5e7eb;
            --shadow: rgba(0,0,0,0.1);
        }}

        [data-theme="dark"] {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #1e293b;
            --text-primary: #f1f5f9;
            --text-secondary: #cbd5e1;
            --border-color: #475569;
            --shadow: rgba(0,0,0,0.3);
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-primary);
            padding: 20px;
            color: var(--text-primary);
            transition: all 0.3s ease;
        }}

        .container {{
            max-width: 1600px;
            margin: 0 auto;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}

        .header h1 {{
            font-size: 2rem;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .header p {{
            opacity: 0.9;
            font-size: 1rem;
        }}

        .theme-toggle {{
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
            background: var(--bg-secondary);
            border: 2px solid var(--border-color);
            border-radius: 50px;
            padding: 10px 20px;
            cursor: pointer;
            font-size: 1.2rem;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .view-selector {{
            display: flex;
            gap: 10px;
            margin-bottom: 25px;
            align-items: center;
        }}

        .view-label {{
            font-weight: 600;
            color: var(--text-primary);
        }}

        .view-btn {{
            background: var(--bg-card);
            border: 2px solid var(--border-color);
            border-radius: 8px;
            padding: 8px 20px;
            cursor: pointer;
            font-size: 0.9rem;
            color: var(--text-primary);
            transition: all 0.2s ease;
        }}

        .view-btn:hover {{
            border-color: #667eea;
        }}

        .view-btn.active {{
            background: #667eea;
            border-color: #667eea;
            color: white;
            font-weight: 600;
        }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}

        @media (max-width: 1400px) {{
            .metrics-grid {{
                grid-template-columns: repeat(3, 1fr);
            }}
        }}

        @media (max-width: 1024px) {{
            .metrics-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

        @media (max-width: 640px) {{
            .metrics-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .metric-card-link {{
            display: block;
            text-decoration: none;
            color: inherit;
            height: 100%;
        }}

        .metric-card {{
            background: var(--bg-card);
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 12px var(--shadow);
            border-left: 4px solid #667eea;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            cursor: pointer;
            height: 100%;
        }}

        .metric-card:hover {{
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 20px 40px rgba(102, 126, 234, 0.25);
            border-left-color: #764ba2;
            border-left-width: 6px;
        }}

        .metric-card:active {{
            transform: translateY(-4px) scale(1.01);
        }}

        .metric-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}

        .metric-title {{
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .metric-icon {{
            font-size: 1.2rem;
        }}

        .trend-indicator {{
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            gap: 5px;
        }}

        .trend-up {{ color: #ef4444; }}
        .trend-down {{ color: #10b981; }}
        .trend-stable {{ color: #f59e0b; }}

        .metric-description {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-bottom: 12px;
            line-height: 1.4;
            opacity: 0.9;
        }}

        .metric-value {{
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 8px;
        }}

        .metric-change {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 15px;
        }}

        .sparkline-container {{
            height: 60px;
            margin-top: 15px;
            position: relative;
        }}

        .sparkline {{
            width: 100%;
            height: 100%;
        }}

        .sparkline-tooltip {{
            position: absolute;
            background: var(--bg-secondary);
            border: 2px solid #667eea;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-primary);
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s ease;
            white-space: nowrap;
            z-index: 100;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .sparkline-tooltip.visible {{
            opacity: 1;
        }}

        .timestamp {{
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.9rem;
            margin-top: 30px;
        }}
    </style>
</head>
<body>
    <button class="theme-toggle" onclick="toggleTheme()">🌓</button>

    <div class="container">
        <div class="header">
            <h1>Executive Trends Dashboard</h1>
            <p>Engineering Health Metrics</p>
        </div>

        <!-- View Selector -->
        <div class="view-selector">
            <span class="view-label">View:</span>
            <button class="view-btn" onclick="changeView(4)">1 Month</button>
            <button class="view-btn active" onclick="changeView(12)">3 Months</button>
            <button class="view-btn" onclick="changeView(24)">6 Months</button>
        </div>

        <div class="metrics-grid" id="metrics-container">
            <!-- Metrics will be dynamically generated here -->
        </div>

        <div class="timestamp">
            Generated: {now.strftime('%B %d, %Y at %H:%M')} • Data from Observatory history files
        </div>
    </div>

    {context['framework_js']}
    <script>
        const trendsData = {context['metrics_json']};
        let currentView = 12; // Default to 12 weeks

        function changeView(weeks) {{
            currentView = weeks;

            // Update button states
            document.querySelectorAll('.view-btn').forEach(btn => {{
                btn.classList.remove('active');
            }});
            event.target.classList.add('active');

            // Re-render metrics with new view
            renderMetrics();
        }}

        function generateSparkline(data, containerId, unit) {{
            const container = document.getElementById(containerId);
            if (!container) {{
                console.warn('Container not found:', containerId);
                return;
            }}

            // Slice data based on current view
            const viewData = data.slice(-currentView);

            // Validate data
            if (!viewData || viewData.length === 0) {{
                console.warn('No data for sparkline:', containerId);
                return;
            }}

            const width = container.offsetWidth;
            const height = 60;

            // Check if container has width
            if (width === 0) {{
                console.warn('Container has no width:', containerId);
                return;
            }}

            const max = Math.max(...viewData);
            const min = Math.min(...viewData);
            const range = max - min || 1;

            // Validate calculated values
            if (!isFinite(max) || !isFinite(min) || !isFinite(range)) {{
                console.error('Invalid data values for sparkline:', containerId, {{ max, min, range, viewData }});
                return;
            }}

            // Create tooltip
            const tooltip = document.createElement('div');
            tooltip.className = 'sparkline-tooltip';
            container.appendChild(tooltip);

            const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svg.setAttribute('width', width);
            svg.setAttribute('height', height);
            svg.setAttribute('class', 'sparkline');

            const points = viewData.map((value, index) => {{
                const x = viewData.length > 1 ? (index / (viewData.length - 1)) * width : width / 2;
                const y = height - ((value - min) / range) * (height - 10) - 5;
                return `${{x}},${{y}}`;
            }}).join(' ');

            // Gradient background
            const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            const gradient = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
            gradient.setAttribute('id', `gradient-${{containerId}}`);
            gradient.setAttribute('x1', '0%');
            gradient.setAttribute('y1', '0%');
            gradient.setAttribute('x2', '0%');
            gradient.setAttribute('y2', '100%');

            const stop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
            stop1.setAttribute('offset', '0%');
            stop1.setAttribute('style', 'stop-color:rgba(102,126,234,0.3);stop-opacity:1');

            const stop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
            stop2.setAttribute('offset', '100%');
            stop2.setAttribute('style', 'stop-color:rgba(102,126,234,0);stop-opacity:1');

            gradient.appendChild(stop1);
            gradient.appendChild(stop2);
            defs.appendChild(gradient);
            svg.appendChild(defs);

            // Area
            const area = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
            area.setAttribute('points', `0,${{height}} ${{points}} ${{width}},${{height}}`);
            area.setAttribute('fill', `url(#gradient-${{containerId}})`);
            svg.appendChild(area);

            // Line
            const polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
            polyline.setAttribute('points', points);
            polyline.setAttribute('fill', 'none');
            polyline.setAttribute('stroke', '#667eea');
            polyline.setAttribute('stroke-width', '2');
            svg.appendChild(polyline);

            // Dots with hover tooltips
            viewData.forEach((value, index) => {{
                const x = (index / (viewData.length - 1)) * width;
                const y = height - ((value - min) / range) * (height - 10) - 5;

                // Create invisible larger hit area for easier targeting
                const hitArea = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                hitArea.setAttribute('cx', x);
                hitArea.setAttribute('cy', y);
                hitArea.setAttribute('r', '12');
                hitArea.setAttribute('fill', 'transparent');
                hitArea.style.cursor = 'pointer';

                // Create visible circle
                const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                circle.setAttribute('cx', x);
                circle.setAttribute('cy', y);
                circle.setAttribute('r', '4');
                circle.setAttribute('fill', '#667eea');
                circle.style.transition = 'r 0.2s ease';
                circle.style.pointerEvents = 'none'; // Let hit area handle events

                // Hover effects on hit area
                hitArea.addEventListener('mouseenter', (e) => {{
                    circle.setAttribute('r', '6');
                    tooltip.textContent = `${{value}} ${{unit}}`;
                    tooltip.classList.add('visible');

                    // Position tooltip
                    const containerRect = container.getBoundingClientRect();
                    const circleRect = circle.getBoundingClientRect();
                    tooltip.style.left = (circleRect.left - containerRect.left + circleRect.width / 2 - tooltip.offsetWidth / 2) + 'px';
                    tooltip.style.top = (circleRect.top - containerRect.top - tooltip.offsetHeight - 8) + 'px';
                }});

                hitArea.addEventListener('mouseleave', () => {{
                    circle.setAttribute('r', '4');
                    tooltip.classList.remove('visible');
                }});

                svg.appendChild(hitArea);
                svg.appendChild(circle);
            }});

            container.appendChild(svg);
        }}

        function renderMetrics() {{
            const container = document.getElementById('metrics-container');
            container.innerHTML = '';

            trendsData.forEach(metric => {{
                const containerId = `sparkline-${{metric.id}}`;

                // Create clickable link wrapper
                const link = document.createElement('a');
                link.href = metric.dashboardUrl;
                link.className = 'metric-card-link';

                const card = document.createElement('div');
                card.className = 'metric-card';
                card.innerHTML = `
                    <div class="metric-header">
                        <div class="metric-title">
                            <span class="metric-icon">${{metric.icon}}</span>
                            ${{metric.title}}
                        </div>
                        <div class="trend-indicator ${{metric.cssClass}}">
                            ${{metric.arrow}}
                        </div>
                    </div>
                    <div class="metric-description">${{metric.description}}</div>
                    <div class="metric-value" style="color: ${{metric.ragColor}};">${{metric.current}} <span style="font-size: 1rem; font-weight: normal; color: var(--text-secondary);">${{metric.unit}}</span></div>
                    <div class="metric-change">
                        ${{metric.change > 0 ? '+' : ''}}${{metric.change}} ${{metric.changeLabel}}
                    </div>
                    <div class="sparkline-container" id="${{containerId}}"></div>
                `;

                link.appendChild(card);
                container.appendChild(link);

                // Generate sparkline after DOM is updated
                setTimeout(() => generateSparkline(metric.data, containerId, metric.unit), 0);
            }});
        }}

        // Initialize
        renderMetrics();
    </script>
</body>
</html>
"""

        return html
