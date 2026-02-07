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
        print(f"{product_name}: {metrics.critical_high_count} critical/high")
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Import domain models
try:
    from ..domain.security import SecurityMetrics, Vulnerability
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from domain.security import SecurityMetrics, Vulnerability  # type: ignore[no-redef]


class ArmorCodeLoader:
    """
    Loads ArmorCode security data from history files.

    Attributes:
        history_file: Path to security_history.json file
    """

    def __init__(self, history_file: Optional[Path] = None):
        """
        Initialize ArmorCode loader.

        Args:
            history_file: Path to history file (defaults to .tmp/observatory/security_history.json)
        """
        if history_file is None:
            self.history_file = Path('.tmp/observatory/security_history.json')
        else:
            self.history_file = Path(history_file)

    def load_latest_metrics(self) -> Dict[str, SecurityMetrics]:
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
        with open(self.history_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Validate structure
        if not data.get('weeks') or len(data['weeks']) == 0:
            raise ValueError(
                f"No weeks data found in {self.history_file}\n"
                f"History file may be corrupted or empty."
            )

        # Get latest week's data
        latest_week = data['weeks'][-1]
        week_ending = latest_week.get('week_ending', 'Unknown')
        metrics = latest_week.get('metrics', {})
        product_breakdown = metrics.get('product_breakdown', {})

        print(f"[INFO] Loading security data for week ending: {week_ending}")
        print(f"[INFO] Found {len(product_breakdown)} products")

        # Convert to SecurityMetrics domain models
        metrics_by_product = {}
        for product_name, counts in product_breakdown.items():
            security_metrics = SecurityMetrics(
                timestamp=datetime.now(),
                project=product_name,
                total_vulnerabilities=counts.get('total', 0),
                critical=counts.get('critical', 0),
                high=counts.get('high', 0),
                medium=counts.get('medium', 0),
                low=counts.get('low', 0)
            )
            metrics_by_product[product_name] = security_metrics

        return metrics_by_product

    def load_all_weeks(self) -> List[Dict]:
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

        with open(self.history_file, 'r', encoding='utf-8') as f:
            data: Dict = json.load(f)

        weeks: List[Dict] = data.get('weeks', [])
        return weeks

    def get_product_names(self) -> List[str]:
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
def load_security_metrics(history_file: Optional[Path] = None) -> Dict[str, SecurityMetrics]:
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
if __name__ == '__main__':
    print("ArmorCode Loader - Self Test")
    print("=" * 60)

    try:
        loader = ArmorCodeLoader()
        print(f"\n[TEST] Loading from: {loader.history_file}")

        # Test loading latest metrics
        metrics = loader.load_latest_metrics()
        print(f"[OK] Loaded {len(metrics)} products")

        # Show summary
        total_vulns = sum(m.total_vulnerabilities for m in metrics.values())
        total_critical = sum(m.critical for m in metrics.values())
        total_high = sum(m.high for m in metrics.values())

        print(f"\n[SUMMARY]")
        print(f"  Total vulnerabilities: {total_vulns}")
        print(f"  Critical: {total_critical}")
        print(f"  High: {total_high}")
        print(f"  Critical+High: {total_critical + total_high}")

        # Show products with critical vulnerabilities
        critical_products = [
            name for name, m in metrics.items() if m.has_critical
        ]
        if critical_products:
            print(f"\n[ALERT] Products with critical vulnerabilities:")
            for product in critical_products:
                m = metrics[product]
                print(f"  - {product}: {m.critical} critical, {m.high} high")

        print("\n" + "=" * 60)
        print("[SUCCESS] ArmorCode loader working correctly!")

    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        print("\n[INFO] Run this first:")
        print("  python execution/armorcode_weekly_query.py")

    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
