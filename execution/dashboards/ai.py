"""
AI Contributions Dashboard Generator - Refactored

Generates AI vs Human contributions dashboard showing:
    - Devin AI vs Human PR contributions
    - Top contributors analysis
    - Project-level breakdown
    - Recent AI PR activity

This replaces the original 708-line generate_ai_dashboard.py with a
clean, maintainable implementation of ~220 lines.

Usage:
    from execution.dashboards.ai import generate_ai_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/ai_contributions.html')
    generate_ai_dashboard(output_path)
"""

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

# Import dependencies
try:
    from ..dashboard_framework import get_dashboard_framework
    from ..dashboards.renderer import render_dashboard
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from dashboard_framework import get_dashboard_framework  # type: ignore[no-redef]
    from dashboards.renderer import render_dashboard  # type: ignore[no-redef]


def generate_ai_dashboard(output_path: Path | None = None) -> str:
    """
    Generate AI contributions dashboard HTML.

    This is the main entry point for generating the AI dashboard.
    It loads data, processes it, and renders the HTML template.

    Args:
        output_path: Optional path to write HTML file

    Returns:
        Generated HTML string

    Raises:
        FileNotFoundError: If required data files don't exist

    Example:
        from pathlib import Path
        html = generate_ai_dashboard(
            Path('.tmp/observatory/dashboards/ai_contributions.html')
        )
        print(f"Generated dashboard with {len(html)} characters")
    """
    print("[INFO] Generating AI Contributions Dashboard...")

    # Step 1: Load data
    print("[1/4] Loading Devin analysis and risk metrics...")
    analysis = _load_devin_analysis()
    risk_data = _load_risk_metrics()
    author_stats = _get_author_stats(risk_data)
    project_stats = _get_project_stats(risk_data)
    print(f"      Loaded {len(author_stats)} authors, {len(project_stats)} projects")

    # Step 2: Calculate summary statistics
    print("[2/4] Calculating summary metrics...")
    summary_stats = _calculate_summary(analysis, author_stats, project_stats)

    # Step 3: Prepare template context
    print("[3/4] Preparing dashboard components...")
    context = _build_context(analysis, author_stats, project_stats, summary_stats)

    # Step 4: Render template
    print("[4/4] Rendering HTML template...")
    html = render_dashboard("dashboards/ai_dashboard.html", context)

    # Write to file if specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        print(f"[SUCCESS] Dashboard written to: {output_path}")

    print(f"[SUCCESS] Generated {len(html):,} characters of HTML")
    return html


def _load_devin_analysis() -> dict[str, Any]:
    """
    Load Devin analysis from JSON file.

    Returns:
        Dictionary with Devin PR analysis

    Raises:
        FileNotFoundError: If analysis file doesn't exist
    """
    analysis_file = ".tmp/observatory/devin_analysis.json"

    if not os.path.exists(analysis_file):
        raise FileNotFoundError(
            f"Devin analysis file not found: {analysis_file}\nRun: py execution/analyze_devin_prs.py"
        )

    with open(analysis_file, encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
        return result


def _load_risk_metrics() -> dict[str, Any] | None:
    """
    Load risk metrics for author stats (optional).

    Returns:
        Risk data dictionary or None if not available
    """
    risk_file = ".tmp/observatory/risk_history.json"

    if not os.path.exists(risk_file):
        return None

    with open(risk_file, encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
        return result


def _get_author_stats(risk_data: dict[str, Any] | None) -> dict[str, int]:
    """
    Calculate author contribution statistics from risk data.

    Args:
        risk_data: Risk metrics dictionary

    Returns:
        Dictionary mapping author name to PR count
    """
    if not risk_data or "weeks" not in risk_data:
        return {}

    latest_week = risk_data["weeks"][-1]
    author_stats: dict[str, int] = defaultdict(int)

    for project in latest_week.get("projects", []):
        raw_prs = project.get("raw_prs", [])
        for pr in raw_prs:
            author = pr.get("created_by", "Unknown")
            author_stats[author] += 1

    return dict(author_stats)


def _get_project_stats(risk_data: dict[str, Any] | None) -> dict[str, dict[str, int]]:
    """
    Calculate per-project Devin contribution stats.

    Args:
        risk_data: Risk metrics dictionary

    Returns:
        Dictionary mapping project name to stats (total, devin count)
    """
    if not risk_data or "weeks" not in risk_data:
        return {}

    latest_week = risk_data["weeks"][-1]
    project_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "devin": 0})

    for project in latest_week.get("projects", []):
        project_name = project["project_name"]
        raw_prs = project.get("raw_prs", [])

        for pr in raw_prs:
            project_stats[project_name]["total"] += 1
            author = pr.get("created_by", "").lower()
            if "devin" in author:
                project_stats[project_name]["devin"] += 1

    return dict(project_stats)


def _calculate_summary(analysis: dict[str, Any], author_stats: dict[str, int], project_stats: dict[str, dict[str, int]]) -> dict[str, Any]:
    """
    Calculate summary statistics for the dashboard.

    Args:
        analysis: Devin PR analysis data
        author_stats: Author contribution statistics
        project_stats: Project contribution statistics

    Returns:
        Dictionary with summary statistics
    """
    summary = analysis["summary"]

    return {
        "total_prs": summary["total_prs"],
        "devin_prs": summary["devin_prs"],
        "human_prs": summary["human_prs"],
        "devin_percentage": summary["devin_percentage"],
        "author_count": len(author_stats),
        "project_count": len(project_stats),
    }


def _build_context(analysis: dict[str, Any], author_stats: dict[str, int], project_stats: dict[str, dict[str, int]], summary_stats: dict[str, Any]) -> dict[str, Any]:
    """
    Build template context with all dashboard data.

    Args:
        analysis: Devin PR analysis
        author_stats: Author statistics
        project_stats: Project statistics
        summary_stats: Calculated summary statistics

    Returns:
        Dictionary for template rendering
    """
    # Get dashboard framework (CSS/JS)
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#8b5cf6",
        header_gradient_end="#7c3aed",
        include_table_scroll=True,
        include_glossary=False,  # AI dashboard has custom methodology section
    )

    # Build chart data
    top_authors = sorted(author_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    author_labels = [author for author, _ in top_authors]
    author_counts = [count for _, count in top_authors]

    # Build project breakdown data
    project_items = []
    for project, stats in sorted(project_stats.items(), key=lambda x: x[1]["total"], reverse=True):
        if stats["total"] > 0:
            project_items.append(
                {
                    "name": project,
                    "total": stats["total"],
                    "devin": stats["devin"],
                    "human": stats["total"] - stats["devin"],
                    "devin_pct": round(stats["devin"] / stats["total"] * 100, 1),
                }
            )

    # Build recent PRs table rows
    recent_prs = []
    for pr in analysis.get("devin_prs", [])[:15]:  # Show 15 most recent
        recent_prs.append(
            {
                "pr_id": pr["pr_id"],
                "project": pr["project"],
                "title": pr["title"],
                "created_by": pr["created_by"],
                "commit_count": pr["commit_count"],
                "created_date": pr["created_date"][:10] if pr.get("created_date") else "N/A",
            }
        )

    # Build context
    context = {
        "framework_css": framework_css,
        "framework_js": framework_js,
        "summary_stats": summary_stats,
        "author_labels": author_labels,
        "author_counts": author_counts,
        "project_items": project_items,
        "recent_prs": recent_prs,
    }

    return context


# Main execution for testing
if __name__ == "__main__":
    print("AI Contributions Dashboard Generator - Self Test")
    print("=" * 60)

    try:
        output_path = Path(".tmp/observatory/dashboards/ai_contributions.html")
        html = generate_ai_dashboard(output_path)

        print("\n" + "=" * 60)
        print("[SUCCESS] AI dashboard generated!")
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
        print("  python execution/analyze_devin_prs.py")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()
