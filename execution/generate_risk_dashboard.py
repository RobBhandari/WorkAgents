#!/usr/bin/env python3
"""
Delivery Risk Dashboard Generator - DEPRECATED

⚠️ DEPRECATED: This file is deprecated and will be removed in a future version.
   Please use: execution.dashboards.risk.generate_risk_dashboard()

Creates a beautiful, self-contained HTML dashboard for delivery risk metrics.
Uses modern "mint" design with Chart.js for visualizations.

Focuses on work item-based risk signals (reopened bugs, change patterns).

Migration Guide:
    OLD: python execution/generate_risk_dashboard.py
    NEW: python -m execution.dashboards.risk

    OLD:
        from execution.generate_risk_dashboard import main
        main()

    NEW:
        from execution.dashboards.risk import generate_risk_dashboard
        from pathlib import Path
        generate_risk_dashboard(Path('.tmp/observatory/dashboards/risk_dashboard.html'))
"""

import os
import sys
import warnings
from pathlib import Path

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

# Issue deprecation warning
warnings.warn(
    "generate_risk_dashboard.py is deprecated. Use execution.dashboards.risk.generate_risk_dashboard() instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Import new implementation
# Add parent directory to path for direct script execution
if __name__ == "__main__":
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

try:
    from execution.dashboards.risk import generate_risk_dashboard
except ImportError:
    try:
        from dashboards.risk import generate_risk_dashboard
    except ImportError:
        print("[ERROR] Could not import refactored risk dashboard module")
        print("       Make sure execution package is in PYTHONPATH")
        sys.exit(1)


# Legacy functions kept for compatibility (but not used by new implementation)
# These can be removed after migration is complete


def main():
    """
    Main entry point (deprecated wrapper).

    This function now delegates to the new implementation.
    """
    print("⚠️  DEPRECATION WARNING: This script is deprecated.")
    print("   Please use: python -m execution.dashboards.risk\n")
    print("=" * 60)

    try:
        output_path = Path(".tmp/observatory/dashboards/risk_dashboard.html")
        html = generate_risk_dashboard(output_path)

        print("\n[SUCCESS] Dashboard generated!")
        print(f"  Location: {output_path}")
        print(f"  Size: {len(html):,} bytes")
        print(f"\nOpen in browser: start {output_path}")
        print("\nMigration Guide:")
        print("  OLD: python execution/generate_risk_dashboard.py")
        print("  NEW: python -m execution.dashboards.risk")

    except FileNotFoundError:
        print("[ERROR] No risk metrics found.")
        print("Run: python execution/ado_risk_metrics.py")
        return
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
