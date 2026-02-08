#!/usr/bin/env python3
"""
ADO Flow Metrics Collector for Director Observatory

Collects engineering flow metrics at project level:
- Lead Time (P50, P85, P95): Created Date → Closed Date
- Cycle Time (P50, P85, P95): First Active → Closed Date
- WIP (Work in Progress): Current open items
- Aging Items: Items open > threshold days

Read-only operation - does not modify any existing data.
"""

import json
import os
import sys
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv

from execution.collectors.ado_connection import get_ado_connection
from execution.collectors.flow_metrics_calculations import (
    calculate_aging_items,
    calculate_cycle_time_variance,
    calculate_dual_metrics,
    calculate_lead_time,
    calculate_throughput,
)
from execution.collectors.flow_metrics_queries import query_work_items_for_flow

load_dotenv()


def collect_flow_metrics_for_project(wit_client, project: dict, config: dict) -> dict:
    """
    Collect all flow metrics for a single project, segmented by work type.

    Args:
        wit_client: Work Item Tracking client
        project: Project metadata from discovery
        config: Configuration dict (thresholds, lookback days, etc.)

    Returns:
        Flow metrics dictionary for the project with Bug/Story/Task segmentation
    """
    project_name = project["project_name"]
    project_key = project["project_key"]

    # Get the actual ADO project name (may differ from display name)
    ado_project_name = project.get("ado_project_name", project_name)

    # Get area path filter if specified
    area_path_filter = project.get("area_path_filter")

    print(f"\n  Collecting flow metrics for: {project_name}")

    # Query work items (returns segmented by work type)
    work_items = query_work_items_for_flow(
        wit_client, ado_project_name, lookback_days=config.get("lookback_days", 90), area_path_filter=area_path_filter
    )

    # Calculate metrics for each work type separately
    work_type_metrics = {}
    total_open = 0
    total_closed = 0

    for work_type in ["Bug", "User Story", "Task"]:
        type_data = work_items.get(work_type, {})
        open_items = type_data.get("open_items", [])
        closed_items = type_data.get("closed_items", [])
        open_count = type_data.get("open_count", 0)
        closed_count = type_data.get("closed_count", 0)

        total_open += open_count
        total_closed += closed_count

        # Calculate lead time and aging for this work type - ONLY HARD DATA
        lead_time = calculate_lead_time(closed_items)
        dual_metrics = calculate_dual_metrics(closed_items, cleanup_threshold_days=365)
        aging = calculate_aging_items(open_items, aging_threshold_days=config.get("aging_threshold_days", 30))
        throughput = calculate_throughput(closed_items, config.get("lookback_days", 90))
        variance = calculate_cycle_time_variance(closed_items)

        work_type_metrics[work_type] = {
            "open_count": open_count,
            "closed_count_90d": closed_count,
            "wip": open_count,  # WIP = open items
            "lead_time": lead_time,
            "dual_metrics": dual_metrics,  # NEW: Operational vs Cleanup metrics
            "aging_items": aging,
            "throughput": throughput,  # NEW: Closed items per week
            "cycle_time_variance": variance,  # NEW: Predictability measure
            "excluded_security_bugs": type_data.get("excluded_security_bugs", {"open": 0, "closed": 0}),
        }

        # Print metrics for this work type
        print(f"    {work_type}:")
        print(f"      Lead Time (P85): {lead_time['p85']} days")

        # Show dual metrics if cleanup work is significant
        if dual_metrics["indicators"]["is_cleanup_effort"]:
            print(f"      ⚠️  CLEANUP DETECTED ({dual_metrics['indicators']['cleanup_percentage']:.0f}% old closures)")
            print(f"      Operational Lead Time (P85): {dual_metrics['operational']['p85']} days")
            print(
                f"      Cleanup Count: {dual_metrics['cleanup']['closed_count']} (avg age: {dual_metrics['cleanup']['avg_age_years']:.1f} years)"
            )

        print(f"      WIP: {open_count}")
        print(f"      Aging (>{aging['threshold_days']}d): {aging['count']} items")
        print(f"      Throughput: {throughput['per_week']} items/week")
        print(f"      Cycle Time StdDev: {variance['std_dev_days']} days (CV: {variance['coefficient_of_variation']}%)")

    return {
        "project_key": project_key,
        "project_name": project_name,
        "work_type_metrics": work_type_metrics,
        "total_open": total_open,
        "total_closed_90d": total_closed,
        "collected_at": datetime.now().isoformat(),
    }


def save_flow_metrics(metrics: dict, output_file: str = ".tmp/observatory/flow_history.json") -> bool:
    """
    Save flow metrics to history file.

    Appends to existing history or creates new file.
    Validates data before saving to prevent persisting collection failures.
    """
    from utils_atomic_json import atomic_json_save, load_json_with_recovery

    # Validate that we have actual data before saving
    projects = metrics.get("projects", [])

    if not projects:
        print("\n[SKIPPED] No project data to save - collection may have failed")
        return False

    # Check if this looks like a failed collection (all zeros)
    total_open = sum(p.get("total_open", 0) for p in projects)
    total_closed = sum(p.get("total_closed_90d", 0) for p in projects)

    if total_open == 0 and total_closed == 0:
        print("\n[SKIPPED] All projects returned zero flow data - likely a collection failure")
        print("          Not persisting this data to avoid corrupting trend history")
        return False

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Load existing history
    history = load_json_with_recovery(output_file, default_value={"weeks": []})

    # Add validation if structure check exists
    if not isinstance(history, dict) or "weeks" not in history:
        print("\n[WARNING] Existing history file has invalid structure - recreating")
        history = {"weeks": []}

    # Add new week entry
    history["weeks"].append(metrics)

    # Keep only last 52 weeks (12 months) for quarter/annual analysis
    history["weeks"] = history["weeks"][-52:]

    # Save updated history
    try:
        atomic_json_save(history, output_file)
        print(f"\n[SAVED] Flow metrics saved to: {output_file}")
        print(f"        History now contains {len(history['weeks'])} week(s)")
        return True
    except Exception as e:
        print(f"\n[ERROR] Failed to save Flow metrics: {e}")
        return False


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    print("Director Observatory - Flow Metrics Collector\n")
    print("=" * 60)

    # Configuration
    config = {
        "lookback_days": 90,  # How many days back to look for closed items
        "aging_threshold_days": 30,  # Items open > 30 days are "aging"
    }

    # Load discovered projects
    try:
        with open(".tmp/observatory/ado_structure.json", encoding="utf-8") as f:
            discovery_data = json.load(f)
        projects = discovery_data["projects"]
        print(f"Loaded {len(projects)} projects from discovery")
    except FileNotFoundError:
        print("[ERROR] Project discovery file not found.")
        print("Run: python execution/discover_projects.py")
        exit(1)

    # Connect to ADO
    print("\nConnecting to Azure DevOps...")
    try:
        connection = get_ado_connection()
        wit_client = connection.clients.get_work_item_tracking_client()
        print("[SUCCESS] Connected to ADO")
    except Exception as e:
        print(f"[ERROR] Failed to connect to ADO: {e}")
        exit(1)

    # Collect metrics for all projects
    print("\nCollecting flow metrics...")
    print("=" * 60)

    project_metrics = []
    for project in projects:
        try:
            metrics = collect_flow_metrics_for_project(wit_client, project, config)
            project_metrics.append(metrics)
        except Exception as e:
            print(f"  [ERROR] Failed to collect metrics for {project['project_name']}: {e}")
            continue

    # Save results
    week_metrics = {
        "week_date": datetime.now().strftime("%Y-%m-%d"),
        "week_number": datetime.now().isocalendar()[1],  # ISO week number
        "projects": project_metrics,
        "config": config,
    }

    save_flow_metrics(week_metrics)

    # Summary
    print("\n" + "=" * 60)
    print("Flow Metrics Collection Summary:")
    print(f"  Projects processed: {len(project_metrics)}")

    # Calculate totals by work type
    totals_by_type = {
        "Bug": {"open": 0, "closed": 0, "aging": 0},
        "User Story": {"open": 0, "closed": 0, "aging": 0},
        "Task": {"open": 0, "closed": 0, "aging": 0},
    }

    for p in project_metrics:
        for work_type in ["Bug", "User Story", "Task"]:
            metrics = p["work_type_metrics"].get(work_type, {})
            totals_by_type[work_type]["open"] += metrics.get("open_count", 0)
            totals_by_type[work_type]["closed"] += metrics.get("closed_count_90d", 0)
            totals_by_type[work_type]["aging"] += metrics.get("aging_items", {}).get("count", 0)

    print("\n  Metrics by Work Type:")
    for work_type in ["Bug", "User Story", "Task"]:
        totals = totals_by_type[work_type]
        print(f"    {work_type}:")
        print(f"      WIP (open): {totals['open']}")
        print(f"      Closed (90d): {totals['closed']}")
        print(f"      Aging (>30d): {totals['aging']}")

    total_open = sum(p["total_open"] for p in project_metrics)
    total_closed = sum(p["total_closed_90d"] for p in project_metrics)

    # Calculate excluded security bugs (from Bug work type only)
    total_excluded_open = 0
    total_excluded_closed = 0
    for p in project_metrics:
        bug_metrics = p["work_type_metrics"].get("Bug", {})
        total_excluded_open += bug_metrics.get("excluded_security_bugs", {}).get("open", 0)
        total_excluded_closed += bug_metrics.get("excluded_security_bugs", {}).get("closed", 0)

    print(f"\n  Total WIP (all types): {total_open}")
    print(f"  Total Closed (90d, all types): {total_closed}")

    if total_excluded_open > 0 or total_excluded_closed > 0:
        print(f"  Security bugs excluded from Bug metrics: {total_excluded_open} open, {total_excluded_closed} closed")
        print("    → Prevents double-counting with Security Dashboard")

    print("  [NOTE] All metrics now segmented by Bug/Story/Task")
    print("  [NOTE] No data limits - absolute accuracy")

    print("\nFlow metrics collection complete!")
    print("  ✓ Security bugs filtered out (no double-counting)")
    print("\nNext step: Generate flow dashboard with work type segmentation")
