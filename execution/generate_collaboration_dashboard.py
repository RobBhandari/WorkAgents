#!/usr/bin/env python3
"""
Collaboration Dashboard Generator - DEPRECATED WRAPPER

⚠️ DEPRECATED: This module is a compatibility wrapper only.
Use execution.dashboards.collaboration instead.

This file remains for backwards compatibility but delegates all work to the
refactored execution.dashboards.collaboration module.

Original: 533 lines
Refactored: ~170 lines (68% reduction)

Migration:
    OLD: from execution.generate_collaboration_dashboard import generate_collaboration_dashboard
    NEW: from execution.dashboards.collaboration import generate_collaboration_dashboard
"""

import sys
import warnings
from pathlib import Path

# Import the refactored module
from execution.dashboards.collaboration import generate_collaboration_dashboard as _generate

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


def generate_collaboration_dashboard():
    """
    Generate the collaboration dashboard HTML.

    DEPRECATED: This function is a wrapper for backwards compatibility.
    Use execution.dashboards.collaboration.generate_collaboration_dashboard() instead.

    Returns:
        str: Path to generated dashboard HTML file
    """
    warnings.warn(
        "generate_collaboration_dashboard() is deprecated. "
        "Use execution.dashboards.collaboration.generate_collaboration_dashboard() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    output_dir = Path(".tmp/observatory/dashboards")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "collaboration_dashboard.html"

    # Delegate to refactored module
    _generate(output_file)

    return str(output_file)


if __name__ == "__main__":
    print("=" * 60)
    print("Collaboration Dashboard Generator (DEPRECATED WRAPPER)")
    print("=" * 60)
    print()
    print("⚠️  WARNING: This wrapper is deprecated!")
    print("   Use: python -m execution.dashboards.collaboration")
    print()
    print("=" * 60)
    print()

    try:
        output_path = generate_collaboration_dashboard()
        print("\nDashboard ready!")
        print(f"Open: {output_path}")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Failed to generate dashboard: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
