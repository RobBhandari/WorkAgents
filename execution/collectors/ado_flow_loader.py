"""
ADO Flow Metrics Loader

Loads flow metrics (cycle time, lead time) from history file for API consumption.
"""

import json
import pathlib
from datetime import datetime
from typing import Optional

from execution.core import get_logger
from execution.domain.flow import FlowMetrics

logger = get_logger(__name__)


class ADOFlowLoader:
    """Load flow metrics from ADO history data."""

    def __init__(self, history_file: "pathlib.Path | None" = None):
        """
        Initialize loader.

        Args:
            history_file: Path to flow history JSON file (default: .tmp/observatory/flow_history.json)
        """
        self.history_file = history_file or pathlib.Path(".tmp/observatory/flow_history.json")

    def load_latest_metrics(self) -> FlowMetrics:
        """
        Load latest flow metrics.

        Returns:
            FlowMetrics instance with latest data

        Raises:
            FileNotFoundError: If history file doesn't exist
            ValueError: If history data is invalid
        """
        if not self.history_file.exists():
            logger.error("Flow history file not found", extra={"file_path": str(self.history_file)})
            raise FileNotFoundError(f"Flow history not found: {self.history_file}")

        try:
            with open(self.history_file, encoding="utf-8") as f:
                data = json.load(f)

            if not data.get("weeks"):
                raise ValueError("No weeks data in history file")

            latest_week = data["weeks"][-1]
            week_date = latest_week.get("week_date") or latest_week.get("week_ending")

            if "projects" in latest_week:
                return self._parse_projects_format(data, latest_week, week_date)
            return self._parse_legacy_format(data, latest_week, week_date)

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in flow history file", exc_info=True)
            raise ValueError(f"Invalid JSON in history file: {e}")
        except (KeyError, IndexError) as e:
            logger.error("Missing required fields in flow history", exc_info=True)
            raise ValueError(f"Invalid history data structure: {e}")

    def _collect_percentile(self, projects: list, work_type: str, metric_key: str, percentile: str) -> list[float]:
        """Collect a single percentile value from each project that has it."""
        values = []
        for proj in projects:
            wt = proj.get("work_type_metrics", {}).get(work_type, {})
            section = wt.get(metric_key, {})
            # dual_metrics.operational is nested one level deeper
            if metric_key == "dual_metrics":
                section = section.get("operational", {})
            val = section.get(percentile)
            if val:
                values.append(val)
        return values

    @staticmethod
    def _avg(values: list[float]) -> float:
        """Return the simple average of a list, or 0.0 if empty."""
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _sum_throughput(projects: list, work_type: str) -> int:
        """Sum closed_count throughput across all projects for a work type."""
        total = 0
        for proj in projects:
            wt = proj.get("work_type_metrics", {}).get(work_type, {})
            total += wt.get("throughput", {}).get("closed_count", 0)
        return total

    def _parse_projects_format(self, data: dict, latest_week: dict, week_date: str) -> FlowMetrics:
        """Parse the new format that contains a 'projects' array in each week."""
        projects = latest_week["projects"]

        cycle_time_p50 = self._avg(self._collect_percentile(projects, "Bug", "dual_metrics", "p50"))
        cycle_time_p85 = self._avg(self._collect_percentile(projects, "Bug", "dual_metrics", "p85"))
        cycle_time_p95 = self._avg(self._collect_percentile(projects, "Bug", "dual_metrics", "p95"))
        lead_time_p50 = self._avg(self._collect_percentile(projects, "Bug", "lead_time", "p50"))
        lead_time_p85 = self._avg(self._collect_percentile(projects, "Bug", "lead_time", "p85"))
        lead_time_p95 = self._avg(self._collect_percentile(projects, "Bug", "lead_time", "p95"))
        throughput = self._sum_throughput(projects, "Bug")

        logger.info(
            "Loaded latest flow metrics",
            extra={
                "week_date": week_date,
                "cycle_time_p50": cycle_time_p50,
                "projects": len(projects),
            },
        )

        return FlowMetrics(
            timestamp=datetime.fromisoformat(week_date),
            project=data.get("project", "Aggregated"),
            cycle_time_p50=cycle_time_p50,
            cycle_time_p85=cycle_time_p85,
            cycle_time_p95=cycle_time_p95,
            lead_time_p50=lead_time_p50,
            lead_time_p85=lead_time_p85,
            lead_time_p95=lead_time_p95,
            throughput=throughput,
        )

    def _parse_legacy_format(self, data: dict, latest_week: dict, week_date: str) -> FlowMetrics:
        """Parse the old flat format where metrics are stored directly in the week."""
        metrics_data = latest_week.get("metrics", {})

        logger.info(
            "Loaded latest flow metrics",
            extra={
                "week_date": week_date,
                "cycle_time_p50": metrics_data.get("cycle_time_p50"),
            },
        )

        return FlowMetrics(
            timestamp=datetime.fromisoformat(week_date),
            project=data.get("project", "Unknown"),
            cycle_time_p50=metrics_data.get("cycle_time_p50", 0.0),
            cycle_time_p85=metrics_data.get("cycle_time_p85", 0.0),
            cycle_time_p95=metrics_data.get("cycle_time_p95", 0.0),
            lead_time_p50=metrics_data.get("lead_time_p50", 0.0),
            lead_time_p85=metrics_data.get("lead_time_p85", 0.0),
            lead_time_p95=metrics_data.get("lead_time_p95", 0.0),
            throughput=metrics_data.get("throughput", 0),
        )


# Self-test
if __name__ == "__main__":
    from execution.core import setup_logging

    setup_logging(level="INFO", json_output=False)

    logger.info("ADO Flow Loader - Self Test")
    logger.info("=" * 60)

    try:
        loader = ADOFlowLoader()
        logger.info("Loading from history file", extra={"file_path": str(loader.history_file)})

        metrics = loader.load_latest_metrics()

        logger.info(
            "Flow metrics loaded successfully",
            extra={
                "project": metrics.project,
                "cycle_time_p50": metrics.cycle_time_p50,
                "cycle_time_p85": metrics.cycle_time_p85,
                "lead_time_p50": metrics.lead_time_p50,
                "throughput": metrics.throughput,
            },
        )

        logger.info("=" * 60)
        logger.info("✅ Self-test PASSED")

    except Exception as e:
        logger.error("❌ Self-test FAILED", exc_info=True)
        exit(1)
