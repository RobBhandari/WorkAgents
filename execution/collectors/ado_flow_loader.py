"""
ADO Flow Metrics Loader

Loads flow metrics (cycle time, lead time) from history file for API consumption.
"""

from datetime import datetime
from pathlib import Path
import json

from execution.domain.flow import FlowMetrics
from execution.core import get_logger

logger = get_logger(__name__)


class ADOFlowLoader:
    """Load flow metrics from ADO history data."""

    def __init__(self, history_file: Path | None = None):
        """
        Initialize loader.

        Args:
            history_file: Path to flow history JSON file (default: .tmp/observatory/flow_history.json)
        """
        self.history_file = history_file or Path(".tmp/observatory/flow_history.json")

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
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not data.get("weeks"):
                raise ValueError("No weeks data in history file")

            # Get latest week
            latest_week = data["weeks"][-1]
            metrics_data = latest_week.get("metrics", {})

            logger.info(
                "Loaded latest flow metrics",
                extra={
                    "week_ending": latest_week.get("week_ending"),
                    "cycle_time_p50": metrics_data.get("cycle_time_p50")
                }
            )

            return FlowMetrics(
                timestamp=datetime.fromisoformat(latest_week["week_ending"]),
                project=data.get("project", "Unknown"),
                cycle_time_p50=metrics_data.get("cycle_time_p50", 0.0),
                cycle_time_p85=metrics_data.get("cycle_time_p85", 0.0),
                cycle_time_p95=metrics_data.get("cycle_time_p95", 0.0),
                lead_time_p50=metrics_data.get("lead_time_p50", 0.0),
                lead_time_p85=metrics_data.get("lead_time_p85", 0.0),
                lead_time_p95=metrics_data.get("lead_time_p95", 0.0),
                work_items_completed=metrics_data.get("work_items_completed", 0),
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
                "work_items_completed": metrics.work_items_completed,
            }
        )

        logger.info("=" * 60)
        logger.info("✅ Self-test PASSED")

    except Exception as e:
        logger.error("❌ Self-test FAILED", exc_info=True)
        exit(1)
