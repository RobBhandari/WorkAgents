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

            # Get latest week
            latest_week = data["weeks"][-1]

            # Get week_date (new format) or fall back to week_ending (old format)
            week_date = latest_week.get("week_date") or latest_week.get("week_ending")

            # Support both old format (direct metrics) and new format (projects array)
            if "projects" in latest_week:
                # New format: aggregate Bug metrics from all projects
                projects = latest_week["projects"]

                # Aggregate flow metrics from Bug work items across projects
                total_cycle_p50 = []
                total_cycle_p85 = []
                total_cycle_p95 = []
                total_lead_p50 = []
                total_lead_p85 = []
                total_lead_p95 = []
                total_completed = 0

                for proj in projects:
                    bug_metrics = proj.get("work_type_metrics", {}).get("Bug", {})

                    # Use dual_metrics.operational for cycle time (if available)
                    if bug_metrics.get("dual_metrics", {}).get("operational"):
                        operational = bug_metrics["dual_metrics"]["operational"]
                        if operational.get("p50"):
                            total_cycle_p50.append(operational["p50"])
                        if operational.get("p85"):
                            total_cycle_p85.append(operational["p85"])
                        if operational.get("p95"):
                            total_cycle_p95.append(operational["p95"])

                    # Use lead_time for lead time metrics
                    if bug_metrics.get("lead_time"):
                        lead_time = bug_metrics["lead_time"]
                        if lead_time.get("p50"):
                            total_lead_p50.append(lead_time["p50"])
                        if lead_time.get("p85"):
                            total_lead_p85.append(lead_time["p85"])
                        if lead_time.get("p95"):
                            total_lead_p95.append(lead_time["p95"])

                    # Use throughput for work items completed
                    if bug_metrics.get("throughput", {}).get("closed_count"):
                        total_completed += bug_metrics["throughput"]["closed_count"]

                # Calculate averages (simple average across projects)
                cycle_time_p50 = sum(total_cycle_p50) / len(total_cycle_p50) if total_cycle_p50 else 0.0
                cycle_time_p85 = sum(total_cycle_p85) / len(total_cycle_p85) if total_cycle_p85 else 0.0
                cycle_time_p95 = sum(total_cycle_p95) / len(total_cycle_p95) if total_cycle_p95 else 0.0
                lead_time_p50 = sum(total_lead_p50) / len(total_lead_p50) if total_lead_p50 else 0.0
                lead_time_p85 = sum(total_lead_p85) / len(total_lead_p85) if total_lead_p85 else 0.0
                lead_time_p95 = sum(total_lead_p95) / len(total_lead_p95) if total_lead_p95 else 0.0

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
                    throughput=total_completed,
                )
            else:
                # Old format: direct metrics in week
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

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in flow history file", exc_info=True)
            raise ValueError(f"Invalid JSON in history file: {e}")
        except (KeyError, IndexError) as e:
            logger.error("Missing required fields in flow history", exc_info=True)
            raise ValueError(f"Invalid history data structure: {e}")


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
