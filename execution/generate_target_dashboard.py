"""
Generate Aggregated 70% Reduction Target Dashboard

⚠️  DEPRECATED: This module is a compatibility wrapper.
    Use: execution.dashboards.targets.generate_targets_dashboard() instead

Creates a simple, on-demand dashboard showing progress toward 70% reduction targets
for both ArmorCode security vulnerabilities and Azure DevOps bugs.

Usage:
    python generate_target_dashboard.py
    python generate_target_dashboard.py --output-file custom_dashboard.html
"""

import argparse
import logging
import sys
import warnings
from datetime import datetime
from pathlib import Path

# Import refactored implementation
try:
    from execution.dashboards.targets import generate_targets_dashboard
except ModuleNotFoundError:
    from dashboards.targets import generate_targets_dashboard  # type: ignore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'.tmp/target_dashboard_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def main():
    """
    Main execution - wraps refactored generate_targets_dashboard()

    ⚠️  DEPRECATED: This entry point is maintained for backwards compatibility.
        New code should import and call generate_targets_dashboard() directly:

        from execution.dashboards.targets import generate_targets_dashboard
        html = generate_targets_dashboard(output_path)
    """
    # Issue deprecation warning
    warnings.warn(
        "generate_target_dashboard.py is deprecated. "
        "Use: from execution.dashboards.targets import generate_targets_dashboard",
        DeprecationWarning,
        stacklevel=2,
    )

    try:
        parser = argparse.ArgumentParser(description="Generate 70% reduction target dashboard")
        parser.add_argument(
            "--output-file", default=".tmp/observatory/dashboards/target_dashboard.html", help="Output HTML file path"
        )
        args = parser.parse_args()

        logger.info("=" * 70)
        logger.info("DEPRECATION WARNING")
        logger.info("This script wraps the refactored dashboard implementation.")
        logger.info("Use: from execution.dashboards.targets import generate_targets_dashboard")
        logger.info("=" * 70)

        # Convert string path to Path object
        output_path = Path(args.output_file)

        # Call refactored implementation
        generate_targets_dashboard(output_path)

        logger.info("=" * 70)
        logger.info("Dashboard generated successfully!")
        logger.info(f"Output: {args.output_file}")
        logger.info("=" * 70)

        sys.exit(0)

    except Exception as e:
        logger.error(f"Failed to generate dashboard: {e}", exc_info=True)
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


# Legacy function stubs for backwards compatibility
# These maintain the old API but delegate to the refactored module


def load_baseline(file_path: str, system_name: str) -> dict:
    """
    ⚠️  DEPRECATED: This function is maintained for backwards compatibility only.

    Use the refactored module instead:
        from execution.dashboards.targets import _load_baselines
    """
    import json

    warnings.warn(
        "load_baseline() is deprecated. Use execution.dashboards.targets._load_baselines()",
        DeprecationWarning,
        stacklevel=2,
    )

    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


def query_current_ado_bugs() -> int:
    """
    ⚠️  DEPRECATED: This function is maintained for backwards compatibility only.

    Use the refactored module instead:
        from execution.dashboards.targets import _query_current_ado_bugs
    """
    warnings.warn(
        "query_current_ado_bugs() is deprecated. Use execution.dashboards.targets._query_current_ado_bugs()",
        DeprecationWarning,
        stacklevel=2,
    )

    from execution.dashboards.targets import _query_current_ado_bugs

    return _query_current_ado_bugs()


def query_current_armorcode_vulns() -> int:
    """
    ⚠️  DEPRECATED: This function is maintained for backwards compatibility only.

    Use the refactored module instead:
        from execution.dashboards.targets import _query_current_armorcode_vulns
    """
    warnings.warn(
        "query_current_armorcode_vulns() is deprecated. "
        "Use execution.dashboards.targets._query_current_armorcode_vulns()",
        DeprecationWarning,
        stacklevel=2,
    )

    from execution.dashboards.targets import _query_current_armorcode_vulns

    return _query_current_armorcode_vulns()


def calculate_metrics(baseline_count: int, target_count: int, current_count: int, weeks_to_target: int) -> dict:
    """
    ⚠️  DEPRECATED: This function is maintained for backwards compatibility only.

    Use the refactored module instead:
        from execution.dashboards.targets import _calculate_metrics
    """
    warnings.warn(
        "calculate_metrics() is deprecated. Use execution.dashboards.targets._calculate_metrics()",
        DeprecationWarning,
        stacklevel=2,
    )

    from execution.dashboards.targets import _calculate_metrics

    return _calculate_metrics(baseline_count, target_count, current_count, weeks_to_target)


def generate_html(security_metrics: dict, bugs_metrics: dict) -> str:
    """
    ⚠️  DEPRECATED: This function is maintained for backwards compatibility only.

    The refactored implementation uses Jinja2 templates instead of inline HTML generation.

    Use the refactored module instead:
        from execution.dashboards.targets import generate_targets_dashboard
    """
    warnings.warn(
        "generate_html() is deprecated. HTML generation now uses Jinja2 templates. "
        "Use execution.dashboards.targets.generate_targets_dashboard()",
        DeprecationWarning,
        stacklevel=2,
    )

    # This legacy function cannot easily delegate to the new implementation
    # because it had a different interface. Return error message.
    raise NotImplementedError(
        "generate_html() is deprecated and cannot be used with the refactored implementation. "
        "Use execution.dashboards.targets.generate_targets_dashboard() instead."
    )


if __name__ == "__main__":
    main()
