"""
Trends Dashboard Generator - Refactored

Generates 12-week trends dashboard showing:
    - Forecast banner with 70% reduction target progress
    - 8 key metrics with sparklines
    - Burn rate analysis
    - Week-over-week changes

This replaces the original 1351-line generate_trends_dashboard.py with a
clean, maintainable implementation of ~400 lines.

Usage:
    from execution.dashboards.trends import generate_trends_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/index.html')
    generate_trends_dashboard(output_path)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import cast

# Import infrastructure and components
from execution.core import get_logger
from execution.dashboards.components.charts import sparkline
from execution.dashboards.renderer import render_dashboard
from execution.domain.metrics import TrendData
from execution.framework import get_dashboard_framework
from execution.utils.error_handling import log_and_raise, log_and_return_default

logger = get_logger(__name__)


class TrendsDashboardGenerator:
    """
    Generates trends dashboard from historical data files.

    Combines quality, security, and flow metrics to show 12-week trends
    with sparklines and forecast analysis.
    """

    def __init__(self, weeks: int = 12) -> None:
        """
        Initialize generator.

        Args:
            weeks: Number of weeks of history to show (default: 12)
        """
        self.weeks = weeks
        self.quality_file = Path(".tmp/observatory/quality_history.json")
        self.security_file = Path(".tmp/observatory/security_history.json")
        self.flow_file = Path(".tmp/observatory/flow_history.json")
        self.baseline_bugs_file = Path("data/baseline.json")
        self.baseline_vulns_file = Path("data/armorcode_baseline.json")

    def generate(self, output_path: Path | None = None) -> str:
        """
        Generate trends dashboard HTML.

        Args:
            output_path: Optional path to write HTML file

        Returns:
            Generated HTML string
        """
        logger.info("Generating trends dashboard")

        # Step 1: Load all historical data
        logger.info("Loading historical data", extra={"weeks": self.weeks})
        historical_data = self._load_all_history()

        # Step 2: Calculate forecast
        logger.info("Calculating forecast and burn rate")
        forecast = self._calculate_forecast(historical_data)

        # Step 3: Build trend metrics
        logger.info("Building trend metrics with sparklines")
        trend_metrics = self._build_trend_metrics(historical_data)

        # Step 4: Render dashboard
        logger.info("Rendering trends dashboard")
        context = self._build_context(forecast, trend_metrics, historical_data)
        html = render_dashboard("dashboards/trends_dashboard.html", context)

        # Write to file if specified
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html, encoding="utf-8")
            logger.info("Dashboard written to file", extra={"path": str(output_path)})

        logger.info("Trends dashboard generated", extra={"html_size": len(html)})
        return html

    def _load_all_history(self) -> dict:
        """Load historical data from all sources"""
        return {
            "quality": self._load_history_file(self.quality_file),
            "security": self._load_history_file(self.security_file),
            "flow": self._load_history_file(self.flow_file),
        }

    def _load_history_file(self, file_path: Path) -> dict | None:
        """Load a single history JSON file"""
        if not file_path.exists():
            logger.warning("History file not found", extra={"file": file_path.name})
            return None

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            weeks = data.get("weeks", [])
            if not weeks:
                logger.warning("No weeks data in file", extra={"file": file_path.name})
                return None

            # Get last N weeks
            weeks_subset = weeks[-self.weeks :] if len(weeks) > self.weeks else weeks
            logger.info("History file loaded", extra={"file": file_path.name, "weeks_loaded": len(weeks_subset)})

            return {"weeks": weeks_subset, "all_weeks": weeks}

        except Exception as e:
            return cast(
                dict | None,
                log_and_return_default(
                    logger,
                    e,
                    context={"file": file_path.name, "operation": "load_history"},
                    default_value=None,
                    error_type="History file loading",
                ),
            )

    def _calculate_forecast(self, historical_data: dict) -> dict | None:
        """Calculate 70% reduction forecast"""
        quality = historical_data.get("quality")
        security = historical_data.get("security")

        if not quality or not security:
            return None

        # Load baselines
        baseline_bugs = 0
        baseline_vulns = 0

        if self.baseline_bugs_file.exists():
            with open(self.baseline_bugs_file) as f:
                baseline_bugs = json.load(f).get("open_count", 0)

        if self.baseline_vulns_file.exists():
            with open(self.baseline_vulns_file) as f:
                baseline_vulns = json.load(f).get("total_vulnerabilities", 0)

        if baseline_bugs == 0 or baseline_vulns == 0:
            return None

        # Get current counts from latest week
        latest_quality = quality["weeks"][-1]
        latest_security = security["weeks"][-1]

        current_bugs = sum(p.get("open_bugs_count", 0) for p in latest_quality.get("projects", []))
        current_vulns = latest_security.get("metrics", {}).get("current_total", 0)

        # Calculate targets (30% of baseline = 70% reduction)
        target_bugs = round(baseline_bugs * 0.3)
        target_vulns = round(baseline_vulns * 0.3)

        # Calculate progress
        bugs_progress = self._calc_progress(baseline_bugs, current_bugs, target_bugs)
        vulns_progress = self._calc_progress(baseline_vulns, current_vulns, target_vulns)
        overall_progress = (bugs_progress + vulns_progress) / 2

        # Calculate burn rate (items reduced per week)
        burn_rate = self._calculate_burn_rate(historical_data)

        # Calculate required rate to hit target
        weeks_remaining = 20  # Adjust based on target date
        items_to_reduce = (current_bugs + current_vulns) - (target_bugs + target_vulns)
        required_rate = round(items_to_reduce / weeks_remaining) if weeks_remaining > 0 else 0

        # Determine status
        if overall_progress >= 75:
            status = "On Track"
            status_class = "on-track"
            message = "Excellent progress! On track to meet 70% reduction target."
        elif overall_progress >= 50:
            status = "At Risk"
            status_class = "at-risk"
            message = f"Current burn rate ({burn_rate}/week) below required rate ({required_rate}/week)."
        else:
            status = "Off Track"
            status_class = "off-track"
            message = f"Urgent: Need to accelerate. Current rate {burn_rate}/week, need {required_rate}/week."

        return {
            "title": "70% Reduction Target",
            "status": status,
            "status_class": status_class,
            "progress": overall_progress,
            "weeks_remaining": weeks_remaining,
            "burn_rate": burn_rate,
            "required_rate": required_rate,
            "message": message,
        }

    def _calc_progress(self, baseline: int, current: int, target: int) -> float:
        """Calculate reduction progress percentage"""
        if baseline <= target:
            return 100.0
        reduction_needed = baseline - target
        reduction_achieved = baseline - current
        progress = (reduction_achieved / reduction_needed) * 100
        return max(0, min(100, progress))

    def _calculate_burn_rate(self, historical_data: dict) -> int:
        """Calculate average burn rate (items reduced per week) over last 4 weeks"""
        quality = historical_data.get("quality")
        if not quality or len(quality["weeks"]) < 2:
            return 0

        # Compare last 4 weeks
        recent_weeks = quality["weeks"][-4:]
        if len(recent_weeks) < 2:
            return 0

        first_week = recent_weeks[0]
        last_week = recent_weeks[-1]

        first_count = sum(p.get("open_bugs_count", 0) for p in first_week.get("projects", []))
        last_count = sum(p.get("open_bugs_count", 0) for p in last_week.get("projects", []))

        reduction = first_count - last_count
        weeks_span = len(recent_weeks)
        burn_rate = round(reduction / weeks_span) if weeks_span > 0 else 0

        return max(0, burn_rate)  # Return 0 if increasing

    def _build_trend_metrics(self, historical_data: dict) -> list[dict]:
        """Build trend metrics with sparklines"""
        metrics = []

        quality = historical_data.get("quality")
        security = historical_data.get("security")
        flow = historical_data.get("flow")

        # Metric 1: Open Bugs
        if quality:
            values = []
            for week in quality["weeks"]:
                total = sum(p.get("open_bugs_count", 0) for p in week.get("projects", []))
                values.append(float(total))

            if values:
                metrics.append(self._create_metric_card(title="Open Bugs", values=values, lower_is_better=True))

        # Metric 2: Critical Vulnerabilities
        if security:
            values = []
            for week in security["weeks"]:
                critical = week.get("metrics", {}).get("critical", 0)
                values.append(float(critical))

            if values:
                metrics.append(
                    self._create_metric_card(title="Critical Vulnerabilities", values=values, lower_is_better=True)
                )

        # Metric 3: High Vulnerabilities
        if security:
            values = []
            for week in security["weeks"]:
                high = week.get("metrics", {}).get("high", 0)
                values.append(float(high))

            if values:
                metrics.append(
                    self._create_metric_card(title="High Vulnerabilities", values=values, lower_is_better=True)
                )

        # Metric 4: Total Vulnerabilities
        if security:
            values = []
            for week in security["weeks"]:
                total = week.get("metrics", {}).get("current_total", 0)
                values.append(float(total))

            if values:
                metrics.append(
                    self._create_metric_card(title="Total Vulnerabilities", values=values, lower_is_better=True)
                )

        # Metric 5: Lead Time P50
        if flow:
            values = []
            for week in flow["weeks"]:
                # Aggregate across projects
                projects = week.get("projects", [])
                lead_times = [p.get("lead_time_p50", 0) for p in projects if p.get("lead_time_p50")]
                avg_lead = sum(lead_times) / len(lead_times) if lead_times else 0
                values.append(float(avg_lead))

            if values and any(v > 0 for v in values):
                metrics.append(
                    self._create_metric_card(
                        title="Avg Lead Time (P50)", values=values, lower_is_better=True, format_as="days"
                    )
                )

        # Metric 6: Bugs Created
        if quality:
            values = []
            for week in quality["weeks"]:
                total = sum(p.get("created_last_week", 0) for p in week.get("projects", []))
                values.append(float(total))

            if values:
                metrics.append(self._create_metric_card(title="Bugs Created", values=values, lower_is_better=True))

        # Metric 7: Bugs Closed
        if quality:
            values = []
            for week in quality["weeks"]:
                total = sum(p.get("closed_last_week", 0) for p in week.get("projects", []))
                values.append(float(total))

            if values:
                metrics.append(
                    self._create_metric_card(
                        title="Bugs Closed", values=values, lower_is_better=False  # Higher is better!
                    )
                )

        # Metric 8: Net Change
        if quality:
            values = []
            for week in quality["weeks"]:
                closed = sum(p.get("closed_last_week", 0) for p in week.get("projects", []))
                created = sum(p.get("created_last_week", 0) for p in week.get("projects", []))
                net = closed - created
                values.append(float(net))

            if values:
                metrics.append(
                    self._create_metric_card(
                        title="Net Change", values=values, lower_is_better=False  # Negative (closed > created) is good
                    )
                )

        return [m for m in metrics if m is not None]

    def _create_metric_card(
        self, title: str, values: list[float], lower_is_better: bool = True, format_as: str = "number"
    ) -> dict | None:
        """Create a metric card with sparkline"""
        if not values or len(values) < 2:
            return None

        current = values[-1]
        previous = values[-2]
        change = current - previous

        # Format current value
        if format_as == "days":
            current_str = f"{current:.1f}d"
        else:
            current_str = f"{int(current)}"

        # Determine if improving
        if lower_is_better:
            improving = change < 0
        else:
            improving = change > 0

        # Trend class and arrow
        if abs(change) < 0.1:
            change_class = "stable"
            trend_arrow = "→"
            change_text = "No change"
        elif improving:
            change_class = "improving"
            trend_arrow = "↓" if lower_is_better else "↑"
            change_text = f"{abs(change):.0f} better"
        else:
            change_class = "degrading"
            trend_arrow = "↑" if lower_is_better else "↓"
            change_text = f"{abs(change):.0f} worse"

        # Generate sparkline
        sparkline_html = sparkline(values, width=200, height=60)

        return {
            "title": title,
            "current_value": current_str,
            "sparkline": sparkline_html,
            "change_class": change_class,
            "trend_arrow": trend_arrow,
            "change_text": change_text,
            "weeks": len(values),
            "values": values,  # Raw data for client-side filtering
            "lower_is_better": lower_is_better,
        }

    def _build_context(self, forecast: dict | None, trend_metrics: list[dict], historical_data: dict) -> dict:
        """Build template context"""
        # Get framework
        framework_css, framework_js = get_dashboard_framework(
            header_gradient_start="#f59e0b", header_gradient_end="#d97706", include_table_scroll=False
        )

        # Build data status
        data_status = []
        for name, data in historical_data.items():
            data_status.append(
                {"name": name.capitalize(), "loaded": data is not None, "weeks": len(data["weeks"]) if data else 0}
            )

        return {
            "framework_css": framework_css,
            "framework_js": framework_js,
            "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "forecast": forecast,
            "trend_metrics": trend_metrics,
            "data_status": data_status,
        }


# Convenience function
def generate_trends_dashboard(output_path: Path | None = None, weeks: int = 12) -> str:
    """
    Generate trends dashboard.

    Args:
        output_path: Optional output path (defaults to .tmp/observatory/dashboards/index.html)
        weeks: Number of weeks to display (default: 12)

    Returns:
        Generated HTML string
    """
    if output_path is None:
        output_path = Path(".tmp/observatory/dashboards/index.html")
    generator = TrendsDashboardGenerator(weeks=weeks)
    return generator.generate(output_path)


# Self-test
if __name__ == "__main__":
    logger.info("Trends Dashboard Generator - Self Test")

    try:
        output_path = Path(".tmp/observatory/dashboards/index.html")
        html = generate_trends_dashboard(output_path)

        logger.info(
            "Trends dashboard generated successfully", extra={"output": str(output_path), "html_size": len(html)}
        )

    except Exception as e:
        log_and_raise(
            logger,
            e,
            context={"operation": "generate_trends_dashboard", "output": str(output_path)},
            error_type="Trends dashboard generation",
        )
