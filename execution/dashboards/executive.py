"""
Executive Summary Dashboard Generator - Refactored

Generates executive-level health dashboard combining:
    - Quality metrics (bugs, flow)
    - Security metrics (vulnerabilities)
    - Target progress (70% reduction)
    - Attention items and trends

This replaces the original 1483-line generate_executive_summary.py with a
clean, maintainable implementation of ~350 lines.

Usage:
    from execution.dashboards.executive import generate_executive_summary
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/executive.html')
    generate_executive_summary(output_path)
"""

import json
from datetime import datetime
from pathlib import Path

# Import infrastructure and domain models
from execution.collectors.armorcode_loader import ArmorCodeLoader
from execution.core import get_logger
from execution.dashboards.components.cards import attention_item_card, metric_card
from execution.dashboards.components.charts import sparkline, trend_indicator
from execution.dashboards.renderer import render_dashboard
from execution.domain.flow import FlowMetrics
from execution.domain.quality import QualityMetrics
from execution.domain.security import SecurityMetrics
from execution.framework import get_dashboard_framework

logger = get_logger(__name__)


class ExecutiveSummaryGenerator:
    """
    Generates executive summary dashboard from multiple data sources.

    Combines quality, security, and flow metrics into a single
    high-level health view for directors and executives.
    """

    def __init__(self):
        """Initialize generator with file paths"""
        self.quality_file = Path(".tmp/observatory/quality_history.json")
        self.security_file = Path(".tmp/observatory/security_history.json")
        self.flow_file = Path(".tmp/observatory/flow_history.json")
        self.baseline_bugs_file = Path("data/baseline.json")
        self.baseline_vulns_file = Path("data/armorcode_baseline.json")

    def generate(self, output_path: Path | None = None) -> str:
        """
        Generate executive summary HTML.

        Args:
            output_path: Optional path to write HTML file

        Returns:
            Generated HTML string
        """
        logger.info("Generating executive summary")

        # Step 1: Load all data sources
        logger.info("Loading metrics from all sources")
        all_data = self._load_all_data()

        # Step 2: Calculate target progress
        logger.info("Calculating 70% reduction target progress")
        target_progress = self._calculate_target_progress(all_data)

        # Step 3: Identify attention items
        logger.info("Identifying items requiring attention")
        attention_items = self._identify_attention_items(all_data)

        # Step 4: Build and render dashboard
        logger.info("Rendering executive dashboard")
        context = self._build_context(all_data, target_progress, attention_items)
        html = render_dashboard("dashboards/executive_summary.html", context)

        # Write to file if specified
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html, encoding="utf-8")
            logger.info("Dashboard written to file", extra={"path": str(output_path)})

        logger.info("Executive summary generated", extra={"html_size": len(html)})
        return html

    def _load_all_data(self) -> dict:
        """Load data from all sources"""
        data = {
            "quality": self._load_quality_data(),
            "security": self._load_security_data(),
            "flow": self._load_flow_data(),
        }
        return data

    def _load_quality_data(self) -> dict | None:
        """Load quality/bug metrics"""
        if not self.quality_file.exists():
            logger.warning("Quality history not found")
            return None

        try:
            with open(self.quality_file, encoding="utf-8") as f:
                data = json.load(f)
            weeks = data.get("weeks", [])
            if not weeks:
                return None

            latest = weeks[-1]
            projects = latest.get("projects", [])

            # Aggregate across projects
            total_open = sum(p.get("open_bugs_count", 0) for p in projects)
            total_closed = sum(p.get("closed_last_week", 0) for p in projects)
            total_created = sum(p.get("created_last_week", 0) for p in projects)

            return {
                "open_bugs": total_open,
                "closed_this_week": total_closed,
                "created_this_week": total_created,
                "net_change": total_closed - total_created,
                "weeks": weeks,
            }
        except Exception as e:
            logger.warning(f"Error loading quality data: {e}")
            return None

    def _load_security_data(self) -> dict | None:
        """Load security vulnerability metrics"""
        try:
            loader = ArmorCodeLoader(self.security_file)
            metrics = loader.load_latest_metrics()

            # Aggregate across products
            total_vulns = sum(m.total_vulnerabilities for m in metrics.values())
            total_critical = sum(m.critical for m in metrics.values())
            total_high = sum(m.high for m in metrics.values())

            return {
                "total_vulnerabilities": total_vulns,
                "critical": total_critical,
                "high": total_high,
                "critical_high": total_critical + total_high,
                "products": metrics,
            }
        except FileNotFoundError:
            logger.warning("Security history not found")
            return None
        except Exception as e:
            logger.warning(f"Error loading security data: {e}")
            return None

    def _load_flow_data(self) -> dict | None:
        """Load flow/velocity metrics"""
        if not self.flow_file.exists():
            logger.warning("Flow history not found")
            return None

        try:
            with open(self.flow_file, encoding="utf-8") as f:
                data = json.load(f)
            weeks = data.get("weeks", [])
            if not weeks:
                return None

            latest = weeks[-1]
            projects = latest.get("projects", [])

            # Aggregate lead times
            all_lead_times = []
            for proj in projects:
                if proj.get("lead_time_p50"):
                    all_lead_times.append(proj["lead_time_p50"])

            avg_lead_time = sum(all_lead_times) / len(all_lead_times) if all_lead_times else None

            return {"avg_lead_time_p50": avg_lead_time, "projects": projects, "weeks": weeks}
        except Exception as e:
            logger.warning(f"Error loading flow data: {e}")
            return None

    def _calculate_target_progress(self, all_data: dict) -> dict | None:
        """Calculate 70% reduction target progress"""
        quality = all_data.get("quality")
        security = all_data.get("security")

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

        # Current counts
        current_bugs = quality["open_bugs"]
        current_vulns = security["critical_high"]

        # Targets (30% of baseline = 70% reduction)
        target_bugs = round(baseline_bugs * 0.3)
        target_vulns = round(baseline_vulns * 0.3)

        # Progress calculations
        bugs_progress = self._calc_progress(baseline_bugs, current_bugs, target_bugs)
        vulns_progress = self._calc_progress(baseline_vulns, current_vulns, target_vulns)

        overall = (bugs_progress + vulns_progress) / 2

        return {
            "bugs_progress": bugs_progress,
            "vulns_progress": vulns_progress,
            "overall": overall,
            "baseline_bugs": baseline_bugs,
            "current_bugs": current_bugs,
            "target_bugs": target_bugs,
            "baseline_vulns": baseline_vulns,
            "current_vulns": current_vulns,
            "target_vulns": target_vulns,
        }

    def _calc_progress(self, baseline: int, current: int, target: int) -> float:
        """Calculate reduction progress percentage"""
        if baseline <= target:
            return 100.0
        reduction_needed = baseline - target
        reduction_achieved = baseline - current
        progress = (reduction_achieved / reduction_needed) * 100
        return max(0, min(100, progress))  # Clamp to 0-100

    def _identify_attention_items(self, all_data: dict) -> list[dict]:
        """Identify items requiring executive attention"""
        items = []

        quality = all_data.get("quality")
        security = all_data.get("security")
        flow = all_data.get("flow")

        # Critical security vulnerabilities
        if security and security["critical"] > 0:
            items.append(
                {
                    "severity": "high",
                    "category": "Security",
                    "message": f"{security['critical']} critical vulnerabilities require immediate attention",
                    "action": "Review with security team",
                }
            )

        # Growing bug backlog
        if quality and quality["net_change"] > 10:
            items.append(
                {
                    "severity": "medium",
                    "category": "Quality",
                    "message": f"Bug backlog increased by {quality['net_change']} this week",
                    "action": "Review with engineering managers",
                }
            )

        # Slow delivery
        if flow and flow["avg_lead_time_p50"] and flow["avg_lead_time_p50"] > 14:
            items.append(
                {
                    "severity": "medium",
                    "category": "Flow",
                    "message": f"Average lead time is {flow['avg_lead_time_p50']:.1f} days (target: <14 days)",
                    "action": "Review blockers with teams",
                }
            )

        return items

    def _build_context(self, all_data: dict, target_progress: dict | None, attention_items: list[dict]) -> dict:
        """Build template context"""
        # Get framework
        framework_css, framework_js = get_dashboard_framework(
            header_gradient_start="#667eea", header_gradient_end="#764ba2", include_table_scroll=True
        )

        # Build metric cards
        metric_cards = self._build_metric_cards(all_data)

        # Build health areas
        health_areas = self._build_health_areas(all_data)

        return {
            "framework_css": framework_css,
            "framework_js": framework_js,
            "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target_progress": target_progress,
            "metric_cards": metric_cards,
            "attention_items": attention_items,
            "health_areas": health_areas,
            "trends": [],  # TODO: Implement trend sparklines
        }

    def _build_metric_cards(self, all_data: dict) -> list[str]:
        """Build metric cards"""
        cards = []

        quality = all_data.get("quality")
        security = all_data.get("security")
        flow = all_data.get("flow")

        if quality:
            trend = "↓" if quality["net_change"] < 0 else "↑"
            css_class = "rag-green" if quality["net_change"] < 0 else "rag-red"
            cards.append(
                metric_card(
                    "Open Bugs",
                    str(quality["open_bugs"]),
                    subtitle=f"{quality['net_change']:+d} this week",
                    trend=trend,
                    css_class=css_class,
                )
            )

        if security:
            css_class = "rag-red" if security["critical"] > 0 else "rag-green"
            cards.append(
                metric_card(
                    "Critical Vulnerabilities",
                    str(security["critical"]),
                    subtitle=f"{security['high']} high",
                    css_class=css_class,
                )
            )

        if flow and flow["avg_lead_time_p50"]:
            css_class = "rag-green" if flow["avg_lead_time_p50"] <= 14 else "rag-amber"
            cards.append(
                metric_card(
                    "Avg Lead Time",
                    f"{flow['avg_lead_time_p50']:.1f}d",
                    subtitle="P50 delivery time",
                    css_class=css_class,
                )
            )

        return cards

    def _build_health_areas(self, all_data: dict) -> list[dict]:
        """Build health status by area"""
        areas = []

        quality = all_data.get("quality")
        if quality:
            status = "Good" if quality["net_change"] < 0 else "Attention"
            status_class = "good" if quality["net_change"] < 0 else "caution"
            areas.append(
                {
                    "name": "Quality",
                    "status": status,
                    "status_class": status_class,
                    "key_metric": f"{quality['open_bugs']} open bugs",
                    "trend": trend_indicator(quality["net_change"]),
                }
            )

        security = all_data.get("security")
        if security:
            if security["critical"] > 0:
                status = "Critical"
                status_class = "action"
            elif security["high"] > 5:
                status = "Attention"
                status_class = "caution"
            else:
                status = "Good"
                status_class = "good"

            areas.append(
                {
                    "name": "Security",
                    "status": status,
                    "status_class": status_class,
                    "key_metric": f"{security['critical_high']} critical/high",
                    "trend": "—",
                }
            )

        return areas


# Convenience function
def generate_executive_summary(output_path: Path | None = None) -> str:
    """Generate executive summary dashboard"""
    generator = ExecutiveSummaryGenerator()
    return generator.generate(output_path)


# Self-test
if __name__ == "__main__":
    logger.info("Executive Summary Generator - Self Test")

    try:
        output_path = Path(".tmp/observatory/dashboards/executive.html")
        html = generate_executive_summary(output_path)

        logger.info(
            "Executive summary generated successfully", extra={"output": str(output_path), "html_size": len(html)}
        )

    except Exception as e:
        logger.error("Dashboard generation failed", extra={"error": str(e)}, exc_info=True)
