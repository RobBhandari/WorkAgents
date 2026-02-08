"""
Target Dashboard Generator - Refactored

Generates 70% reduction target tracking dashboard using:
    - Jinja2 templates (XSS-safe)
    - Clean separation of data loading and presentation
    - Reusable metric calculation functions

This replaces the original 633-line generate_target_dashboard.py with a
clean, maintainable implementation of ~200 lines.

Usage:
    from execution.dashboards.targets import generate_targets_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/target_dashboard.html')
    generate_targets_dashboard(output_path)
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Import dependencies
try:
    from ..dashboard_framework import get_dashboard_framework
    from ..dashboards.renderer import render_dashboard
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from dashboard_framework import get_dashboard_framework  # type: ignore[no-redef]
    from dashboards.renderer import render_dashboard  # type: ignore[no-redef]

# Configure logging
logger = logging.getLogger(__name__)


def generate_targets_dashboard(output_path: Path | None = None) -> str:
    """
    Generate 70% reduction target tracking dashboard HTML.

    This is the main entry point for generating the targets dashboard.
    It loads baseline data, queries current state, calculates progress,
    and renders the HTML template.

    Args:
        output_path: Optional path to write HTML file

    Returns:
        Generated HTML string

    Raises:
        FileNotFoundError: If baseline files or history files don't exist

    Example:
        from pathlib import Path
        html = generate_targets_dashboard(
            Path('.tmp/observatory/dashboards/target_dashboard.html')
        )
        print(f"Generated dashboard with {len(html)} characters")
    """
    print("[INFO] Generating 70% Reduction Target Dashboard...")

    # Step 1: Load baseline data
    print("[1/5] Loading baseline data...")
    baselines = _load_baselines()

    # Step 2: Query current state
    print("[2/5] Querying current metrics...")
    current_state = _query_current_state()

    # Step 3: Calculate summary metrics
    print("[3/5] Calculating progress metrics...")
    summary_stats = _calculate_summary(baselines, current_state)

    # Step 4: Prepare template context
    print("[4/5] Preparing dashboard components...")
    context = _build_context(summary_stats)

    # Step 5: Render template
    print("[5/5] Rendering HTML template...")
    html = render_dashboard("dashboards/targets_dashboard.html", context)

    # Write to file if specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        print(f"[SUCCESS] Dashboard written to: {output_path}")

    # Print summary to console
    _print_summary(summary_stats)

    print(f"[SUCCESS] Generated {len(html):,} characters of HTML")
    return html


def _load_baselines() -> dict[str, dict]:
    """
    Load baseline data from JSON files.

    Returns:
        Dictionary with baseline data for security and bugs

    Raises:
        FileNotFoundError: If baseline files don't exist
    """
    security_baseline_path = Path("data/armorcode_baseline.json")
    bugs_baseline_path = Path("data/baseline.json")

    if not security_baseline_path.exists():
        raise FileNotFoundError(f"Security baseline not found: {security_baseline_path}")

    if not bugs_baseline_path.exists():
        raise FileNotFoundError(f"Bugs baseline not found: {bugs_baseline_path}")

    with open(security_baseline_path, encoding="utf-8") as f:
        security_baseline = json.load(f)

    with open(bugs_baseline_path, encoding="utf-8") as f:
        bugs_baseline = json.load(f)

    logger.info(f"Loaded security baseline: {security_baseline_path}")
    logger.info(f"Loaded bugs baseline: {bugs_baseline_path}")

    return {"security": security_baseline, "bugs": bugs_baseline}


def _query_current_state() -> dict[str, int]:
    """
    Query current vulnerability and bug counts from history files.

    Returns:
        Dictionary with current counts for security and bugs

    Raises:
        FileNotFoundError: If history files don't exist
    """
    # Query security vulnerabilities from security_history.json
    security_count = _query_current_armorcode_vulns()

    # Query bugs from quality_history.json
    bugs_count = _query_current_ado_bugs()

    return {"security": security_count, "bugs": bugs_count}


def _query_current_armorcode_vulns() -> int:
    """
    Query current HIGH + CRITICAL vulnerabilities from security_history.json.

    Returns:
        Current vulnerability count

    Raises:
        FileNotFoundError: If security_history.json doesn't exist
        ValueError: If data is malformed
    """
    security_history_file = Path(".tmp/observatory/security_history.json")

    if not security_history_file.exists():
        logger.warning(f"Security history file not found: {security_history_file}")
        logger.warning("Run: python execution/armorcode_weekly_query.py")
        raise FileNotFoundError(f"Security history not found: {security_history_file}")

    with open(security_history_file, encoding="utf-8") as f:
        data = json.load(f)

    # Get latest week's data
    if not data.get("weeks") or len(data["weeks"]) == 0:
        raise ValueError("No weeks data found in security_history.json")

    latest_week = data["weeks"][-1]
    metrics = latest_week["metrics"]

    # Get total HIGH + CRITICAL vulnerabilities
    total_vulns: int = metrics["current_total"]

    logger.info(f"Current ArmorCode vulnerabilities: {total_vulns}")
    logger.info(f"  Week: {latest_week['week_date']}")
    logger.info(f"  Critical: {metrics['severity_breakdown']['critical']}")
    logger.info(f"  High: {metrics['severity_breakdown']['high']}")

    return total_vulns


def _query_current_ado_bugs() -> int:
    """
    Query current open bugs from quality_history.json.

    Returns:
        Current bug count

    Raises:
        FileNotFoundError: If quality_history.json doesn't exist
        ValueError: If data is malformed
    """
    quality_history_file = Path(".tmp/observatory/quality_history.json")

    if not quality_history_file.exists():
        logger.warning(f"Quality history file not found: {quality_history_file}")
        logger.warning("Run: python execution/ado_quality_metrics.py")
        raise FileNotFoundError(f"Quality history not found: {quality_history_file}")

    with open(quality_history_file, encoding="utf-8") as f:
        data = json.load(f)

    # Get latest week's data
    if not data.get("weeks") or len(data["weeks"]) == 0:
        raise ValueError("No weeks data found in quality_history.json")

    latest_week = data["weeks"][-1]

    # Sum open_bugs_count across all projects
    total_bugs: int = sum(p["open_bugs_count"] for p in latest_week["projects"])

    logger.info(f"Current ADO bugs: {total_bugs}")
    logger.info(f"  Week: {latest_week['week_date']}")
    logger.info(f"  Projects: {len(latest_week['projects'])}")

    return total_bugs


def _calculate_summary(baselines: dict[str, dict], current_state: dict[str, int]) -> dict[str, dict]:
    """
    Calculate progress metrics for both security and bugs.

    Args:
        baselines: Baseline data dictionary
        current_state: Current counts dictionary

    Returns:
        Dictionary with calculated metrics for both security and bugs
    """
    # Calculate security metrics
    security_metrics = _calculate_metrics(
        baseline_count=baselines["security"]["total_vulnerabilities"],
        target_count=baselines["security"]["target_vulnerabilities"],
        current_count=current_state["security"],
        weeks_to_target=baselines["security"]["weeks_to_target"],
    )

    # Calculate bugs metrics
    bugs_metrics = _calculate_metrics(
        baseline_count=baselines["bugs"]["open_count"],
        target_count=baselines["bugs"]["target_count"],
        current_count=current_state["bugs"],
        weeks_to_target=baselines["bugs"]["weeks_to_target"],
    )

    return {"security": security_metrics, "bugs": bugs_metrics}


def _calculate_metrics(baseline_count: int, target_count: int, current_count: int, weeks_to_target: int) -> dict[str, int | float | str]:
    """
    Calculate progress metrics for target tracking.

    Focuses on fixed baseline → target tracking:
    - Baseline (Dec 1, 2025): Starting point
    - Current: Where we are now
    - Target (June 30, 2026): End goal (70% reduction)

    Args:
        baseline_count: Starting count from baseline
        target_count: Target count (70% reduction)
        current_count: Current count
        weeks_to_target: Weeks from baseline to target date

    Returns:
        Dictionary with calculated metrics including progress percentage,
        remaining days, and required weekly burn rate
    """
    # Progress from baseline (can be negative if count increased)
    total_reduction_needed = baseline_count - target_count
    progress_from_baseline = baseline_count - current_count
    progress_pct = (progress_from_baseline / total_reduction_needed * 100) if total_reduction_needed > 0 else 0

    # Days/weeks remaining to target date
    target_date = datetime.strptime("2026-06-30", "%Y-%m-%d")
    today = datetime.now()
    days_remaining = (target_date - today).days
    weeks_remaining = days_remaining / 7

    # Remaining work to hit target
    remaining_to_target = current_count - target_count

    # Required weekly burn FROM CURRENT POSITION to hit target
    required_weekly_burn = remaining_to_target / weeks_remaining if weeks_remaining > 0 else 0

    # Status determination based on progress percentage
    if progress_pct >= 100:
        status = "TARGET MET"
        status_color = "#10b981"  # Green
    elif progress_pct >= 70:
        status = "ON TRACK"
        status_color = "#10b981"  # Green
    elif progress_pct >= 40:
        status = "BEHIND SCHEDULE"
        status_color = "#f59e0b"  # Amber
    else:
        status = "AT RISK"
        status_color = "#ef4444"  # Red

    return {
        "baseline_count": baseline_count,
        "current_count": current_count,
        "target_count": target_count,
        "progress_from_baseline": progress_from_baseline,
        "progress_pct": round(progress_pct, 1),
        "days_remaining": days_remaining,
        "weeks_remaining": round(weeks_remaining, 1),
        "required_weekly_burn": round(required_weekly_burn, 2),
        "status": status,
        "status_color": status_color,
        "remaining_to_target": remaining_to_target,
    }


def _build_context(summary_stats: dict[str, dict]) -> dict[str, str | dict | bool]:
    """
    Build template context with all dashboard data.

    Args:
        summary_stats: Calculated summary statistics

    Returns:
        Dictionary for template rendering
    """
    # Get dashboard framework (CSS/JS)
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#1e40af",
        header_gradient_end="#1e3a8a",
        include_table_scroll=False,
        include_expandable_rows=False,
        include_glossary=False,
    )

    # Build context with security and bugs metrics
    context = {
        "framework_css": framework_css,
        "framework_js": framework_js,
        "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "security": summary_stats["security"],
        "bugs": summary_stats["bugs"],
        "show_glossary": False,
    }

    return context


def _print_summary(summary_stats: dict[str, dict]) -> None:
    """
    Print summary statistics to console.

    Args:
        summary_stats: Summary statistics dictionary
    """
    security = summary_stats["security"]
    bugs = summary_stats["bugs"]

    print(f"\n{'=' * 70}")
    print("70% REDUCTION TARGET DASHBOARD")
    print(f"{'=' * 70}")
    print("\nSecurity Vulnerabilities:")
    print(f"  Current: {security['current_count']} ({security['progress_pct']}% progress)")
    print(f"  Status: {security['status']}")
    print("\nBugs:")
    print(f"  Current: {bugs['current_count']} ({bugs['progress_pct']}% progress)")
    print(f"  Status: {bugs['status']}")
    print(f"{'=' * 70}\n")


# Main execution for testing
if __name__ == "__main__":
    print("Target Dashboard Generator - Self Test")
    print("=" * 60)

    # Configure logging for testing
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    try:
        output_path = Path(".tmp/observatory/dashboards/target_dashboard.html")
        html = generate_targets_dashboard(output_path)

        print("\n" + "=" * 60)
        print("[SUCCESS] Target dashboard generated!")
        print(f"[OUTPUT] {output_path}")
        print(f"[SIZE] {len(html):,} characters")

        # Verify output
        if output_path.exists():
            file_size = output_path.stat().st_size
            print(f"[FILE] {file_size:,} bytes on disk")
        else:
            print("[WARNING] Output file not created")

    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        print("\n[INFO] Run data collection first:")
        print("  python execution/armorcode_weekly_query.py")
        print("  python execution/ado_quality_metrics.py")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()
