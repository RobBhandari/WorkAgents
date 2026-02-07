"""
ADO Quality Metrics Loader

Loads quality metrics from history file for API consumption.
"""

import json
import pathlib
from datetime import datetime
from typing import Optional

from execution.core import get_logger
from execution.domain.quality import QualityMetrics

logger = get_logger(__name__)

# Export Path for test mocking compatibility
Path = pathlib.Path


class ADOQualityLoader:
    """Load quality metrics from ADO history data."""

    def __init__(self, history_file: "Optional[pathlib.Path]" = None):
        """
        Initialize loader.

        Args:
            history_file: Path to quality history JSON file (default: .tmp/observatory/quality_history.json)
        """
        self.history_file = history_file or pathlib.Path(".tmp/observatory/quality_history.json")

    def load_latest_metrics(self) -> QualityMetrics:
        """
        Load latest quality metrics.

        Returns:
            QualityMetrics instance with latest data

        Raises:
            FileNotFoundError: If history file doesn't exist
            ValueError: If history data is invalid
        """
        if not self.history_file.exists():
            logger.error("Quality history file not found", extra={"file_path": str(self.history_file)})
            raise FileNotFoundError(f"Quality history not found: {self.history_file}")

        try:
            with open(self.history_file, encoding="utf-8") as f:
                data = json.load(f)

            if not data.get("weeks"):
                raise ValueError("No weeks data in history file")

            # Get latest week
            latest_week = data["weeks"][-1]

            # Support both old format (direct metrics) and new format (projects array)
            if "projects" in latest_week:
                # New format: aggregate data from all projects
                projects = latest_week["projects"]
                total_open_bugs = sum(p.get("open_bugs_count", 0) for p in projects)
                total_closed = sum(p.get("total_bugs_analyzed", 0) for p in projects)

                # Get week_date (new format) or fall back to week_ending (old format)
                week_date = latest_week.get("week_date") or latest_week.get("week_ending")

                logger.info(
                    "Loaded latest quality metrics",
                    extra={"week_date": week_date, "open_bugs": total_open_bugs, "projects": len(projects)},
                )

                return QualityMetrics(
                    timestamp=datetime.fromisoformat(week_date),
                    project=data.get("project", "Aggregated"),
                    open_bugs=total_open_bugs,
                    closed_this_week=total_closed,
                    created_this_week=0,  # Not available in new format
                    net_change=0,  # Not directly available in new format
                    p1_count=0,  # Not available in new format
                    p2_count=0,  # Not available in new format
                )
            else:
                # Old format: direct metrics in week
                metrics_data = latest_week.get("metrics", {})
                week_date = latest_week.get("week_date") or latest_week.get("week_ending")

                logger.info(
                    "Loaded latest quality metrics",
                    extra={"week_date": week_date, "open_bugs": metrics_data.get("open_bugs", 0)},
                )

                return QualityMetrics(
                    timestamp=datetime.fromisoformat(week_date),
                    project=data.get("project", "Unknown"),
                    open_bugs=metrics_data.get("open_bugs", 0),
                    closed_this_week=metrics_data.get("closed_this_week", 0),
                    created_this_week=metrics_data.get("created_this_week", 0),
                    net_change=metrics_data.get("net_change", 0),
                    p1_count=metrics_data.get("p1_count", 0),
                    p2_count=metrics_data.get("p2_count", 0),
                )

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in quality history file", exc_info=True)
            raise ValueError(f"Invalid JSON in history file: {e}")
        except (KeyError, IndexError) as e:
            logger.error("Missing required fields in quality history", exc_info=True)
            raise ValueError(f"Invalid history data structure: {e}")


# Self-test
if __name__ == "__main__":
    from execution.core import setup_logging

    setup_logging(level="INFO", json_output=False)

    logger.info("ADO Quality Loader - Self Test")
    logger.info("=" * 60)

    try:
        loader = ADOQualityLoader()
        logger.info("Loading from history file", extra={"file_path": str(loader.history_file)})

        metrics = loader.load_latest_metrics()

        logger.info(
            "Quality metrics loaded successfully",
            extra={
                "project": metrics.project,
                "open_bugs": metrics.open_bugs,
                "closed_this_week": metrics.closed_this_week,
                "net_change": metrics.net_change,
                "closure_rate": metrics.closure_rate,
            },
        )

        logger.info("=" * 60)
        logger.info("✅ Self-test PASSED")

    except Exception as e:
        logger.error("❌ Self-test FAILED", exc_info=True)
        exit(1)
