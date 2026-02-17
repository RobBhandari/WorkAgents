"""
Executive Summary Dashboard Generator - Refactored

Generates executive-level health dashboard combining:
    - Quality metrics (bugs, flow)
    - Security metrics (vulnerabilities)
    - Target progress (70% reduction)
    - Attention items

Queries APIs directly for fresh current metrics.

This replaces the original 1483-line generate_executive_summary.py with a
clean, maintainable implementation querying APIs directly.

Usage:
    import asyncio
    from execution.dashboards.executive import generate_executive_summary
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/executive.html')
    html = asyncio.run(generate_executive_summary(output_path))
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

# Import infrastructure and domain models
from execution.collectors.ado_flow_metrics import collect_flow_metrics_for_project
from execution.collectors.ado_quality_metrics import collect_quality_metrics_for_project
from execution.collectors.ado_rest_client import get_ado_rest_client
from execution.collectors.armorcode_vulnerability_loader import ArmorCodeVulnerabilityLoader
from execution.core import get_logger
from execution.dashboards.components.cards import metric_card
from execution.dashboards.components.charts import trend_indicator
from execution.dashboards.renderer import render_dashboard
from execution.domain.constants import flow_metrics
from execution.framework import get_dashboard_framework
from execution.utils.error_handling import log_and_return_default
from execution.utils_atomic_json import load_json_with_recovery

logger = get_logger(__name__)


class ExecutiveSummaryGenerator:
    """
    Generates executive summary dashboard from multiple API sources.

    Queries APIs directly for current metrics across quality, security, and flow.
    Combines into a single high-level health view for directors and executives.
    """

    def __init__(self) -> None:
        """Initialize generator with baseline file paths"""
        self.baseline_bugs_file = Path("data/baseline.json")
        self.baseline_vulns_file = Path("data/armorcode_baseline.json")
        self.discovery_file = Path(".tmp/observatory/ado_structure.json")

    async def generate(self, output_path: Path | None = None) -> str:
        """
        Generate executive summary HTML by querying APIs.

        Args:
            output_path: Optional path to write HTML file

        Returns:
            Generated HTML string
        """
        logger.info("Generating executive summary (querying APIs directly)")

        # Step 1: Query all data sources from APIs
        logger.info("Querying metrics from all API sources")
        all_data = await self._query_all_data()

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

    async def _query_all_data(self) -> dict[str, Any]:
        """Query data from all API sources concurrently"""
        # Execute all queries concurrently
        quality_task = self._query_quality_data()
        security_task = self._query_security_data()
        flow_task = self._query_flow_data()

        results = await asyncio.gather(quality_task, security_task, flow_task, return_exceptions=True)
        quality_data: dict[str, Any] | None | BaseException = results[0]
        security_data: dict[str, Any] | None | BaseException = results[1]
        flow_data: dict[str, Any] | None | BaseException = results[2]

        # Handle exceptions
        quality_result: dict[str, Any] | None = None
        if isinstance(quality_data, Exception):
            logger.error("Failed to query quality data", extra={"error": str(quality_data)})
        elif isinstance(quality_data, dict):
            quality_result = quality_data

        security_result: dict[str, Any] | None = None
        if isinstance(security_data, Exception):
            logger.error("Failed to query security data", extra={"error": str(security_data)})
        elif isinstance(security_data, dict):
            security_result = security_data

        flow_result: dict[str, Any] | None = None
        if isinstance(flow_data, Exception):
            logger.error("Failed to query flow data", extra={"error": str(flow_data)})
        elif isinstance(flow_data, dict):
            flow_result = flow_data

        return {"quality": quality_result, "security": security_result, "flow": flow_result}

    async def _query_quality_data(self) -> dict[str, Any] | None:
        """Query quality/bug metrics from ADO API"""
        try:
            logger.info("Querying quality metrics from Azure DevOps API")

            # Load discovery data
            if not self.discovery_file.exists():
                logger.warning(f"Discovery data not found: {self.discovery_file}")
                return None

            discovery_data = load_json_with_recovery(str(self.discovery_file))
            projects = discovery_data.get("projects", [])

            if not projects:
                logger.warning("No projects found in discovery data")
                return None

            # Get REST client and config
            rest_client = get_ado_rest_client()
            config = {"lookback_days": 90}

            # Query metrics for all projects concurrently
            tasks = [collect_quality_metrics_for_project(rest_client, project, config) for project in projects]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and aggregate
            project_metrics: list[dict[str, Any]] = []
            for project, result in zip(projects, results, strict=True):
                if isinstance(result, Exception):
                    logger.warning(f"Failed quality query for {project.get('project_name')}: {result}")
                elif isinstance(result, dict):
                    project_metrics.append(result)

            if not project_metrics:
                return None

            # Aggregate across projects
            total_open = sum(p.get("open_bugs_count", 0) for p in project_metrics)
            total_closed = sum(p.get("closed_last_week", 0) for p in project_metrics)
            total_created = sum(p.get("created_last_week", 0) for p in project_metrics)

            logger.info(
                "Quality data queried",
                extra={"open_bugs": total_open, "closed": total_closed, "created": total_created},
            )

            return {
                "open_bugs": total_open,
                "closed_this_week": total_closed,
                "created_this_week": total_created,
                "net_change": total_closed - total_created,
            }

        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            return log_and_return_default(  # type: ignore[no-any-return]
                logger, e, context={"source": "ADO Quality API"}, default_value=None, error_type="Quality data query"
            )

    async def _query_security_data(self) -> dict[str, Any] | None:
        """Query security vulnerability metrics from ArmorCode API (Production only)"""
        try:
            logger.info("Querying security metrics from ArmorCode API (Production only)")

            # Load baseline to get product list
            if not self.baseline_vulns_file.exists():
                logger.warning(f"Baseline file not found: {self.baseline_vulns_file}")
                return None

            with open(self.baseline_vulns_file, encoding="utf-8") as f:
                baseline_data = json.load(f)

            products = list(baseline_data.get("products", {}).keys())
            if not products:
                logger.warning("No products found in baseline")
                return None

            # Query ArmorCode API for Production vulnerabilities only
            loader = ArmorCodeVulnerabilityLoader()
            vulnerabilities = loader.load_vulnerabilities_for_products(products, filter_environment=True)

            logger.info(f"Retrieved {len(vulnerabilities)} Production vulnerabilities from ArmorCode API")

            # Count by severity
            total_critical = sum(1 for v in vulnerabilities if v.severity == "CRITICAL")
            total_high = sum(1 for v in vulnerabilities if v.severity == "HIGH")
            total_medium = sum(1 for v in vulnerabilities if v.severity == "MEDIUM")
            total_low = sum(1 for v in vulnerabilities if v.severity == "LOW")

            logger.info(
                "Security data queried",
                extra={"critical": total_critical, "high": total_high, "total": len(vulnerabilities)},
            )

            return {
                "total_vulnerabilities": len(vulnerabilities),
                "critical": total_critical,
                "high": total_high,
                "medium": total_medium,
                "low": total_low,
                "critical_high": total_critical + total_high,
            }

        except (OSError, json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
            return log_and_return_default(  # type: ignore[no-any-return]
                logger,
                e,
                context={"source": "ArmorCode API"},
                default_value=None,
                error_type="Security data query",
            )

    async def _query_flow_data(self) -> dict[str, Any] | None:
        """Query flow/velocity metrics from ADO API"""
        try:
            logger.info("Querying flow metrics from Azure DevOps API")

            # Load discovery data
            if not self.discovery_file.exists():
                logger.warning(f"Discovery data not found: {self.discovery_file}")
                return None

            discovery_data = load_json_with_recovery(str(self.discovery_file))
            projects = discovery_data.get("projects", [])

            if not projects:
                logger.warning("No projects found in discovery data")
                return None

            # Get REST client and config
            rest_client = get_ado_rest_client()
            config = {
                "lookback_days": flow_metrics.LOOKBACK_DAYS,
                "aging_threshold_days": flow_metrics.AGING_THRESHOLD_DAYS,
            }

            # Query metrics for all projects concurrently
            tasks = [collect_flow_metrics_for_project(rest_client, project, config) for project in projects]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and aggregate
            project_metrics: list[dict[str, Any]] = []
            for project, result in zip(projects, results, strict=True):
                if isinstance(result, Exception):
                    logger.warning(f"Failed flow query for {project.get('project_name')}: {result}")
                elif isinstance(result, dict):
                    project_metrics.append(result)

            if not project_metrics:
                return None

            # Aggregate lead times across projects
            all_lead_times = []
            for proj in project_metrics:
                if proj.get("lead_time_p50"):
                    all_lead_times.append(proj["lead_time_p50"])

            avg_lead_time = sum(all_lead_times) / len(all_lead_times) if all_lead_times else None

            logger.info("Flow data queried", extra={"avg_lead_time_p50": avg_lead_time})

            return {"avg_lead_time_p50": avg_lead_time}

        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            return log_and_return_default(  # type: ignore[no-any-return]
                logger, e, context={"source": "ADO Flow API"}, default_value=None, error_type="Flow data query"
            )

    def _calculate_target_progress(self, all_data: dict[str, Any]) -> dict[str, Any] | None:
        """Calculate 70% reduction target progress"""
        quality = all_data.get("quality")
        security = all_data.get("security")

        if not quality or not security:
            return None

        # Load baselines
        baseline_bugs = 0
        baseline_vulns = 0

        try:
            if self.baseline_bugs_file.exists():
                with open(self.baseline_bugs_file, encoding="utf-8") as f:
                    baseline_bugs = json.load(f).get("open_count", 0)

            if self.baseline_vulns_file.exists():
                with open(self.baseline_vulns_file, encoding="utf-8") as f:
                    baseline_vulns = json.load(f).get("total_vulnerabilities", 0)
        except (OSError, json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load baseline data: {e}")
            return None

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

    def _identify_attention_items(self, all_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Identify items requiring executive attention"""
        items: list[dict[str, Any]] = []

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

    def _build_context(
        self, all_data: dict[str, Any], target_progress: dict[str, Any] | None, attention_items: list[dict[str, Any]]
    ) -> dict[str, Any]:
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
        }

    def _build_metric_cards(self, all_data: dict[str, Any]) -> list[str]:
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

    def _build_health_areas(self, all_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Build health status by area"""
        areas: list[dict[str, Any]] = []

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
async def generate_executive_summary(output_path: Path | None = None) -> str:
    """Generate executive summary dashboard by querying APIs directly"""
    generator = ExecutiveSummaryGenerator()
    return await generator.generate(output_path)


# Self-test
if __name__ == "__main__":
    logger.info("Executive Summary Generator - Self Test")

    try:
        output_path = Path(".tmp/observatory/dashboards/executive.html")
        html = asyncio.run(generate_executive_summary(output_path))

        logger.info(
            "Executive summary generated successfully", extra={"output": str(output_path), "html_size": len(html)}
        )

    except (OSError, ValueError, KeyError) as e:
        logger.error("Dashboard generation failed", extra={"error": str(e)}, exc_info=True)
        raise
