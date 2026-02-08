#!/usr/bin/env python3
"""
Deployment Dashboard Generator - DEPRECATED

⚠️  DEPRECATED: This file is maintained for backwards compatibility only.
    New code should use: execution.dashboards.deployment.generate_deployment_dashboard()

This wrapper delegates to the refactored implementation in:
    execution/dashboards/deployment.py

Migration completed: 2026-02-08
Original: 436 lines → Refactored: ~140 lines (68% reduction)
"""

import sys
from pathlib import Path

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

# Import refactored implementation
try:
    from execution.dashboards.deployment import generate_deployment_dashboard as _generate_dashboard
except ImportError:
    from dashboards.deployment import generate_deployment_dashboard as _generate_dashboard  # type: ignore[no-redef]


def generate_deployment_dashboard():
    """
    Generate the deployment dashboard HTML.

    ⚠️  DEPRECATED: Use execution.dashboards.deployment.generate_deployment_dashboard() instead.

    This wrapper maintains backwards compatibility with existing code.
    """
    output_dir = Path(".tmp/observatory/dashboards")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "deployment_dashboard.html"

    # Delegate to refactored implementation
    _generate_dashboard(output_file)

    return str(output_file)


if __name__ == "__main__":
    print("=" * 60)
    print("Deployment Dashboard Generator")
    print("=" * 60)

    try:
        output_path = generate_deployment_dashboard()
        print("\nDashboard ready!")
        print(f"Open: {output_path}")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Failed to generate dashboard: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
