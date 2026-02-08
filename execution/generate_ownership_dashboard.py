#!/usr/bin/env python3
"""
DEPRECATED: Ownership Dashboard Generator

This file has been refactored into execution/dashboards/ownership.py (631 → ~200 lines, 68% reduction)

🔄 Migration Guide:
    OLD: from execution.generate_ownership_dashboard import main
         main()

    NEW: from execution.dashboards.ownership import generate_ownership_dashboard
         from pathlib import Path
         output_path = Path('.tmp/observatory/dashboards/ownership_dashboard.html')
         generate_ownership_dashboard(output_path)

⚠️  This wrapper will be removed in a future version.
    Please update your code to use execution.dashboards.ownership directly.

Benefits of new implementation:
    ✓ 68% code reduction (631 → 200 lines)
    ✓ Jinja2 templates (XSS-safe, maintainable)
    ✓ Clean separation of concerns
    ✓ Comprehensive test coverage
    ✓ Follows security.py pattern
"""

import sys
import warnings
from pathlib import Path

# Show deprecation warning
warnings.warn(
    "generate_ownership_dashboard.py is deprecated. "
    "Use 'from execution.dashboards.ownership import generate_ownership_dashboard' instead. "
    "See file docstring for migration guide.",
    DeprecationWarning,
    stacklevel=2,
)

# Import new implementation
from execution.dashboards.ownership import generate_ownership_dashboard


def main():
    """
    DEPRECATED: Main entry point

    This function is maintained for backward compatibility only.
    Please use the new generate_ownership_dashboard() function directly.
    """
    # Set UTF-8 encoding for Windows
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    print("⚠️  DEPRECATION WARNING ⚠️")
    print("=" * 60)
    print("This file has been refactored into execution/dashboards/ownership.py")
    print("Please update your imports:")
    print("  from execution.dashboards.ownership import generate_ownership_dashboard")
    print("=" * 60)
    print()

    print("Ownership Dashboard Generator\n")
    print("=" * 60)

    try:
        # Use new implementation
        output_path = Path(".tmp/observatory/dashboards/ownership_dashboard.html")
        html = generate_ownership_dashboard(output_path)

        print("\nFeatures:")
        print("  ✓ Modern design with blue accents")
        print("  ✓ Unassigned work tracking")
        print("  ✓ Work type breakdown with RAG status")
        print("  ✓ Area unassigned statistics")
        print("  ✓ Expandable project drill-down")
        print("  ✓ Dark/light theme toggle")
        print("  ✓ 68% code reduction (631 → 200 lines)")

    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        print("\n[INFO] Run data collection first:")
        print("  python execution/ado_ownership_metrics.py")
        exit(1)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
