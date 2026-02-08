"""
Flow Dashboard Generator - Refactored

Generates engineering flow dashboard using:
    - Direct JSON loading (multi-project, multi-work-type)
    - Reusable components (cards, badges)
    - Jinja2 templates (XSS-safe)

This replaces the original 888-line generate_flow_dashboard.py with a
clean, maintainable implementation split across flow.py and flow_helpers.py.

Usage:
    from execution.dashboards.flow import generate_flow_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/flow_dashboard.html')
    generate_flow_dashboard(output_path)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

# Import infrastructure
try:
    from ..dashboard_framework import get_dashboard_framework
    from ..dashboards.renderer import render_dashboard
    from .flow_helpers import (
        build_project_tables,
        build_summary_cards,
        build_work_type_cards,
        calculate_portfolio_summary,
    )
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from dashboard_framework import get_dashboard_framework  # type: ignore[no-redef]
    from dashboards.renderer import render_dashboard  # type: ignore[no-redef]
    from flow_helpers import (  # type: ignore[no-redef]
        build_project_tables,
        build_summary_cards,
        build_work_type_cards,
        calculate_portfolio_summary,
    )


class FlowDataLoader:
    """Load flow metrics from history JSON file."""

    def __init__(self, history_file: Path | None = None):
        """
        Initialize loader.

        Args:
            history_file: Optional path to flow_history.json (defaults to .tmp/observatory/flow_history.json)
        """
        self.history_file = history_file or Path(".tmp/observatory/flow_history.json")

    def load_latest_week(self) -> dict[str, Any]:
        """
        Load latest week data with all projects and work types.

        Returns:
            Dictionary with structure: {week_date, week_number, projects[...]}

        Raises:
            FileNotFoundError: If history file doesn't exist
            json.JSONDecodeError: If file contains invalid JSON
        """
        with open(self.history_file, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)

        if "weeks" not in data or not data["weeks"]:
            raise ValueError("No weeks data found in flow_history.json")

        result: dict[str, Any] = data["weeks"][-1]  # Most recent week
        return result


def generate_flow_dashboard(output_path: Path | None = None) -> str:
    """
    Generate flow dashboard HTML.

    4-stage process:
    [1/4] Load data from flow_history.json
    [2/4] Calculate portfolio-wide summary statistics
    [3/4] Build template context (cards, tables, framework)
    [4/4] Render template

    Args:
        output_path: Optional path to write HTML file

    Returns:
        Generated HTML string

    Raises:
        FileNotFoundError: If flow_history.json doesn't exist

    Example:
        from pathlib import Path
        html = generate_flow_dashboard(
            Path('.tmp/observatory/dashboards/flow_dashboard.html')
        )
        print(f"Generated dashboard with {len(html)} characters")
    """
    print("[INFO] Generating Flow Dashboard...")

    # [1/4] Load data
    print("[1/4] Loading flow data...")
    loader = FlowDataLoader()
    week_data = loader.load_latest_week()
    print(f"      Loaded {len(week_data.get('projects', []))} projects")

    # [2/4] Calculate summaries
    print("[2/4] Calculating portfolio metrics...")
    summary_stats = calculate_portfolio_summary(week_data)

    # [3/4] Build context
    print("[3/4] Preparing dashboard components...")
    context = _build_context(week_data, summary_stats)

    # [4/4] Render
    print("[4/4] Rendering HTML template...")
    html = render_dashboard("dashboards/flow_dashboard.html", context)

    # Write if path specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        print(f"[SUCCESS] Dashboard written to: {output_path}")

    print(f"[SUCCESS] Generated {len(html):,} characters of HTML")
    return html




def _build_context(week_data: dict[str, Any], summary_stats: dict[str, Any]) -> dict[str, Any]:
    """
    Build template context with all dashboard data.

    Args:
        week_data: Week data from flow_history.json
        summary_stats: Portfolio summary from _calculate_portfolio_summary()

    Returns:
        Context dict for template rendering
    """
    # Get framework
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#10b981",
        header_gradient_end="#059669",
        include_table_scroll=True,
        include_glossary=True,
    )

    # Build components
    summary_cards = build_summary_cards(summary_stats)
    work_type_cards = build_work_type_cards(summary_stats)
    work_types = build_project_tables(week_data, summary_stats)

    # Determine portfolio status
    avg_lead = summary_stats["avg_lead_time"]
    if avg_lead < 60:
        portfolio_status = "HEALTHY"
        portfolio_color = "#10b981"
    elif avg_lead < 150:
        portfolio_status = "CAUTION"
        portfolio_color = "#f59e0b"
    else:
        portfolio_status = "ACTION NEEDED"
        portfolio_color = "#f87171"

    return {
        "framework_css": framework_css,
        "framework_js": framework_js,
        "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "week_number": week_data.get("week_number", "N/A"),
        "week_date": week_data.get("week_date", "N/A"),
        "portfolio_status": portfolio_status,
        "portfolio_status_color": portfolio_color,
        "summary_cards": summary_cards,
        "work_type_cards": work_type_cards,
        "work_types": work_types,
        "project_count": summary_stats["project_count"],
    }


# Main for testing
if __name__ == "__main__":
    print("Flow Dashboard Generator - Self Test")
    print("=" * 60)

    try:
        output_path = Path(".tmp/observatory/dashboards/flow_dashboard.html")
        html = generate_flow_dashboard(output_path)

        print("\n" + "=" * 60)
        print("[SUCCESS] Flow dashboard generated!")
        print(f"[OUTPUT] {output_path}")
        print(f"[SIZE] {len(html):,} characters")

        if output_path.exists():
            file_size = output_path.stat().st_size
            print(f"[FILE] {file_size:,} bytes on disk")

    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        print("\n[INFO] Run data collection first:")
        print("  python execution/collectors/ado_flow_metrics.py")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()
