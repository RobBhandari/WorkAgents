#!/usr/bin/env python3
"""
Executive Summary Dashboard Generator (Legacy Wrapper)

⚠️ DEPRECATED: This file is a backward compatibility wrapper.

For new code, use:
    from execution.dashboards.executive import generate_executive_summary

Original implementation: 1483 lines
New implementation: ~350 lines (see execution/dashboards/executive.py)

This wrapper delegates to the refactored implementation while maintaining
backward compatibility with existing scripts and workflows.

Changelog:
    - 2026-02-07: Refactored to use domain models, components, and templates
    - Original: Monolithic 1483-line script with complex data aggregation
"""

import warnings
import sys
from pathlib import Path

# Show deprecation warning
warnings.warn(
    "\n" + "=" * 70 + "\n"
    "generate_executive_summary.py is deprecated!\n"
    "\n"
    "Please update your code to use:\n"
    "    from execution.dashboards.executive import generate_executive_summary\n"
    "\n"
    "This wrapper will be removed in v3.0\n"
    + "=" * 70,
    DeprecationWarning,
    stacklevel=2
)

# Import new implementation
try:
    from dashboards.executive import generate_executive_summary as _new_implementation
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from dashboards.executive import generate_executive_summary as _new_implementation


def main():
    """
    Main entry point - delegates to new implementation.

    Maintains backward compatibility by:
    1. Using same default output path
    2. Same console output format
    3. Same error handling
    """
    print("[LEGACY WRAPPER] Calling refactored implementation...")
    print("[INFO] Update your code to import from execution.dashboards.executive")
    print()

    # Call new implementation with same default path
    output_path = Path('.tmp/observatory/dashboards/executive.html')

    try:
        html = _new_implementation(output_path)
        return 0

    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        print("\n[INFO] Run data collection first:", file=sys.stderr)
        print("  python execution/ado_quality_metrics.py", file=sys.stderr)
        print("  python execution/armorcode_weekly_query.py", file=sys.stderr)
        print("  python execution/ado_flow_metrics.py", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
