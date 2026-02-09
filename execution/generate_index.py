#!/usr/bin/env python3
"""
Generate index.html for Observatory dashboards.

⚠️ DEPRECATED: This script is deprecated. Use generate_dashboard_launcher.py instead.

The landing page is now a dashboard launcher with cards for all dashboards,
not a copy of trends.html.

For new code, use:
    from execution.generate_dashboard_launcher import generate_dashboard_launcher
    generate_dashboard_launcher()
"""

import warnings
from pathlib import Path

warnings.warn(
    "\n" + "=" * 70 + "\n"
    "generate_index.py is deprecated!\n"
    "\n"
    "The landing page is now a dashboard launcher with cards.\n"
    "Please use: python -m execution.generate_dashboard_launcher\n"
    "\n"
    "This wrapper will be removed in v3.0\n" + "=" * 70,
    DeprecationWarning,
    stacklevel=2,
)


def generate_index_html():
    """Deprecated - delegates to generate_dashboard_launcher."""
    print("[DEPRECATED] Calling generate_dashboard_launcher instead...")

    try:
        from execution.generate_dashboard_launcher import generate_dashboard_launcher
        generate_dashboard_launcher()
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(generate_index_html())
