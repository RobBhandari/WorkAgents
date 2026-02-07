"""
ArmorCode Data Loader

Loads and transforms ArmorCode security data from history files.
Converts raw JSON data into domain model instances.

Usage:
    from execution.collectors.armorcode_loader import ArmorCodeLoader
    from execution.domain.security import SecurityMetrics

    loader = ArmorCodeLoader()
    metrics_by_product = loader.load_latest_metrics()

    for product_name, metrics in metrics_by_product.items():
        logger.info("Product metrics", extra={"product": product_name, "critical_high": metrics.critical_high_count})
"""

import json
import pathlib
from datetime import datetime
from typing import Optional

# Structured logging
from execution.core.logging_config import get_logger

logger = get_logger(__name__)

# Import domain models
try:
    from ..domain.security import SecurityMetrics, Vulnerability
except ImportError:
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    from domain.security import SecurityMetrics  # type: ignore[no-redef]


class ArmorCodeLoader:
    """
    Loads ArmorCode security data from history files.

    Attributes:
        history_file: Path to security_history.json file
    """

    def __init__(self, history_file: "pathlib.Path | None" = None):
        """
        Initialize ArmorCode loader.

        Args:
            history_file: Path to history file (defaults to .tmp/observatory/security_history.json)
        """
        if history_file is None:
            self.history_file = pathlib.Path(".tmp/observatory/security_history.json")
        else:
            self.history_file = pathlib.Path(history_file)

    def load_latest_metrics(self) -> dict[str, SecurityMetrics]:
        """
        Load latest security metrics by product from history file.

        Returns:
            Dictionary mapping product names to SecurityMetrics instances

        Raises:
            FileNotFoundError: If history file doesn't exist
            ValueError: If history file has invalid format

        Example:
            loader = ArmorCodeLoader()
            metrics = loader.load_latest_metrics()

            for product, metric in metrics.items():
                if metric.has_critical:
                    print(f"ALERT: {product} has {metric.critical} critical vulns")
        """
        if not self.history_file.exists():
            raise FileNotFoundError(
                f"Security history file not found: {self.history_file}\n"
                f"Run armorcode_weekly_query.py first to collect data."
            )

        # Load JSON data
        with open(self.history_file, encoding="utf-8") as f:
            data = json.load(f)

        # Validate structure
        if not data.get("weeks") or len(data["weeks"]) == 0:
            raise ValueError(f"No weeks data found in {self.history_file}\n" f"History file may be corrupted or empty.")

        # Get latest week's data
        latest_week = data["weeks"][-1]
        # Support both week_date (new format) and week_ending (old format)
        week_ending = latest_week.get("week_date") or latest_week.get("week_ending", "Unknown")
        metrics = latest_week.get("metrics", {})
        product_breakdown = metrics.get("product_breakdown", {})

        logger.info(
            "Loading security data",
            extra={"week_ending": week_ending, "product_count": len(product_breakdown)},
        )

        # Convert to SecurityMetrics domain models
        metrics_by_product = {}
        for product_name, counts in product_breakdown.items():
            security_metrics = SecurityMetrics(
                timestamp=datetime.now(),
                project=product_name,
                total_vulnerabilities=counts.get("total", 0),
                critical=counts.get("critical", 0),
                high=counts.get("high", 0),
                medium=counts.get("medium", 0),
                low=counts.get("low", 0),
            )
            metrics_by_product[product_name] = security_metrics

        return metrics_by_product

    def load_all_weeks(self) -> list[dict]:
        """
        Load all historical weeks of security data.

        Returns:
            List of week dictionaries with metrics

        Example:
            loader = ArmorCodeLoader()
            weeks = loader.load_all_weeks()
            print(f"Loaded {len(weeks)} weeks of history")
        """
        if not self.history_file.exists():
            raise FileNotFoundError(f"History file not found: {self.history_file}")

        with open(self.history_file, encoding="utf-8") as f:
            data: dict = json.load(f)

        weeks: list[dict] = data.get("weeks", [])
        return weeks

    def get_product_names(self) -> list[str]:
        """
        Get list of all product names in latest data.

        Returns:
            Sorted list of product names

        Example:
            loader = ArmorCodeLoader()
            products = loader.get_product_names()
            print(f"Tracking {len(products)} products: {', '.join(products)}")
        """
        metrics = self.load_latest_metrics()
        return sorted(metrics.keys())


# Convenience function for quick access
def load_security_metrics(history_file: "pathlib.Path | None" = None) -> dict[str, SecurityMetrics]:
    """
    Convenience function to load latest security metrics.

    Args:
        history_file: Optional path to history file

    Returns:
        Dictionary of product name -> SecurityMetrics

    Example:
        metrics = load_security_metrics()
        total_critical = sum(m.critical for m in metrics.values())
    """
    loader = ArmorCodeLoader(history_file)
    return loader.load_latest_metrics()


# Self-test when run directly
if __name__ == "__main__":
    from execution.core.logging_config import setup_logging

    # Setup human-readable logging for self-test
    setup_logging(level="INFO", json_output=False)

    logger.info("ArmorCode Loader - Self Test")
    logger.info("=" * 60)

    try:
        loader = ArmorCodeLoader()
        logger.info("Loading from history file", extra={"file_path": str(loader.history_file)})

        # Test loading latest metrics
        metrics = loader.load_latest_metrics()
        logger.info("Metrics loaded", extra={"product_count": len(metrics)})

        # Show summary
        total_vulns = sum(m.total_vulnerabilities for m in metrics.values())
        total_critical = sum(m.critical for m in metrics.values())
        total_high = sum(m.high for m in metrics.values())

        logger.info(
            "Security metrics summary",
            extra={
                "total_vulnerabilities": total_vulns,
                "critical": total_critical,
                "high": total_high,
                "critical_high": total_critical + total_high,
            },
        )

        # Show products with critical vulnerabilities
        critical_products = [name for name, m in metrics.items() if m.has_critical]
        if critical_products:
            logger.warning(
                f"Found {len(critical_products)} products with critical vulnerabilities",
                extra={
                    "critical_product_count": len(critical_products),
                    "critical_products": [
                        {"name": product, "critical": metrics[product].critical, "high": metrics[product].high}
                        for product in critical_products
                    ],
                },
            )

        logger.info("=" * 60)
        logger.info("ArmorCode loader working correctly!")

    except FileNotFoundError as e:
        logger.error("Security history file not found", extra={"error": str(e)})
        logger.info("Run this first: python execution/armorcode_weekly_query.py")

    except Exception as e:
        logger.error("Unexpected error during self-test", exc_info=True, extra={"error": str(e)})
