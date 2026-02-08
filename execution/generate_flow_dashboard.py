#!/usr/bin/env python3
"""
Flow Dashboard Generator - DEPRECATED

⚠️ DEPRECATION NOTICE ⚠️

This file is deprecated and maintained only for backward compatibility.
Please use the new refactored implementation:

    from execution.dashboards.flow import generate_flow_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/flow_dashboard.html')
    generate_flow_dashboard(output_path)

The new implementation provides:
- Jinja2 templates (XSS protection)
- Cleaner separation of concerns
- 42% smaller codebase (511 vs 888 lines Python)
- Better maintainability
- All HTML moved to templates

This wrapper will be removed in a future release.
"""

import sys
import warnings
from pathlib import Path

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


def calculate_composite_flow_status(p85_lead_time, p50_lead_time):
    """
    DEPRECATED: Use execution.dashboards.flow._calculate_status() instead.

    This function is provided for backward compatibility only.
    """
    warnings.warn(
        "calculate_composite_flow_status() is deprecated. "
        "Use execution.dashboards.flow._calculate_status() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    from execution.dashboards.flow import _calculate_status

    return _calculate_status(p85_lead_time, p50_lead_time)


def load_flow_data():
    """
    DEPRECATED: Use execution.dashboards.flow.FlowDataLoader instead.

    This function is provided for backward compatibility only.
    """
    warnings.warn(
        "load_flow_data() is deprecated. " "Use execution.dashboards.flow.FlowDataLoader.load_latest_week() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    from execution.dashboards.flow import FlowDataLoader

    loader = FlowDataLoader()
    return loader.load_latest_week()


def generate_html(flow_data):
    """
    DEPRECATED: Use execution.dashboards.flow.generate_flow_dashboard() instead.

    This function is provided for backward compatibility only.
    The flow_data parameter is ignored - data is loaded internally.
    """
    warnings.warn(
        "generate_html() is deprecated. " "Use execution.dashboards.flow.generate_flow_dashboard() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    from execution.dashboards.flow import generate_flow_dashboard

    # Generate without output path (returns HTML string)
    return generate_flow_dashboard()


def main():
    """
    DEPRECATED: Use execution.dashboards.flow module directly.

    This function is provided for backward compatibility only.
    """
    warnings.warn(
        "This module is deprecated. Use: python -m execution.dashboards.flow",
        DeprecationWarning,
        stacklevel=2,
    )

    print("=" * 60)
    print("⚠️  DEPRECATION WARNING")
    print("=" * 60)
    print()
    print("This file (generate_flow_dashboard.py) is deprecated.")
    print("Please use the new implementation:")
    print()
    print("  from execution.dashboards.flow import generate_flow_dashboard")
    print("  from pathlib import Path")
    print()
    print("  output_path = Path('.tmp/observatory/dashboards/flow_dashboard.html')")
    print("  generate_flow_dashboard(output_path)")
    print()
    print("=" * 60)
    print()
    print("Continuing with deprecated implementation for now...")
    print()

    try:
        from execution.dashboards.flow import generate_flow_dashboard

        output_path = Path(".tmp/observatory/dashboards/flow_dashboard.html")
        html = generate_flow_dashboard(output_path)

        print()
        print("=" * 60)
        print("[SUCCESS] Flow dashboard generated!")
        print(f"[OUTPUT] {output_path}")
        print(f"[SIZE] {len(html):,} characters")

        if output_path.exists():
            file_size = output_path.stat().st_size
            print(f"[FILE] {file_size:,} bytes on disk")

        print()
        print("⚠️  Remember to update your code to use the new module!")
        print("=" * 60)

    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        print("\n[INFO] Run data collection first:")
        print("  python execution/collectors/ado_flow_metrics.py")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
