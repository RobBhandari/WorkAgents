#!/usr/bin/env python3
"""
DEPRECATED: AI Contributions Dashboard Generator

This file has been refactored into execution/dashboards/ai.py (708 → ~220 lines, 68% reduction)

🔄 Migration Guide:
    OLD: from execution.generate_ai_dashboard import main
         main()

    NEW: from execution.dashboards.ai import generate_ai_dashboard
         from pathlib import Path
         output_path = Path('.tmp/observatory/dashboards/ai_contributions.html')
         generate_ai_dashboard(output_path)

⚠️  This wrapper will be removed in a future version.
    Please update your code to use execution.dashboards.ai directly.

Benefits of new implementation:
    ✓ 68% code reduction (708 → 220 lines)
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
    "generate_ai_dashboard.py is deprecated. "
    "Use 'from execution.dashboards.ai import generate_ai_dashboard' instead. "
    "See file docstring for migration guide.",
    DeprecationWarning,
    stacklevel=2,
)

# Import new implementation
from execution.dashboards.ai import generate_ai_dashboard


def save_dashboard(html, output_file=".tmp/observatory/dashboards/ai_contributions.html"):
    """
    DEPRECATED: Save the dashboard HTML

    This function is maintained for backward compatibility only.
    The new generate_ai_dashboard() function handles file writing internally.
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    print("\n[SUCCESS] AI Contributions Dashboard generated!")
    print(f"  Location: {output_file}")
    print(f"  Size: {len(html):,} bytes")
    print(f"\nOpen in browser: start {output_file}")


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    print("⚠️  DEPRECATION WARNING ⚠️")
    print("=" * 60)
    print("This file has been refactored into execution/dashboards/ai.py")
    print("Please update your imports:")
    print("  from execution.dashboards.ai import generate_ai_dashboard")
    print("=" * 60)
    print()

    print("AI Contributions Dashboard Generator")
    print("=" * 60)

    try:
        # Use new implementation
        output_path = Path(".tmp/observatory/dashboards/ai_contributions.html")
        html = generate_ai_dashboard(output_path)

        print("\nFeatures:")
        print("  ✓ AI vs Human contribution pie chart")
        print("  ✓ Top contributors bar chart")
        print("  ✓ Project-level breakdown")
        print("  ✓ Recent Devin PRs table")
        print("  ✓ Dark/light theme toggle")
        print("  ✓ 68% code reduction (708 → 220 lines)")

    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        print("\n[INFO] Run data collection first:")
        print("  python execution/analyze_devin_prs.py")
        exit(1)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()
        exit(1)
