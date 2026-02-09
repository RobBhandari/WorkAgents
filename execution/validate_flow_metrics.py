#!/usr/bin/env python3
"""
Flow Metrics Validation Helper

Shows sample work items to verify metrics against ADO UI
"""

import json
import sys

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


def load_latest_metrics():
    """Load latest flow metrics from history"""
    with open(".tmp/observatory/flow_history.json", encoding="utf-8") as f:
        data = json.load(f)
    return data["weeks"][-1]  # Most recent week


def display_project_summary(project_data):
    """Display summary for a project with validation tips"""
    print(f"\n{'='*80}")
    print(f"PROJECT: {project_data['project_name']}")
    print(f"{'='*80}")

    # Lead Time
    lead_time = project_data["lead_time"]
    print("\nLead Time (Created -> Closed):")
    print(f"  P50 (median):     {lead_time['p50']} days")
    print(f"  P85:              {lead_time['p85']} days")
    print(f"  P95:              {lead_time['p95']} days")
    print(f"  Sample size:      {lead_time['sample_size']} closed items (last 90 days)")

    if lead_time["raw_values"]:
        print("\n  Top 10 longest lead times:")
        for i, val in enumerate(lead_time["raw_values"][:10], 1):
            print(f"    {i}. {val:.1f} days")

    # Cycle Time
    cycle_time = project_data["cycle_time"]
    print("\nCycle Time (Active -> Closed):")
    print(f"  P85:              {cycle_time['p85']} days")
    if cycle_time["p85"] == 0.0:
        print("  [NOTE] Cycle time is 0 - StateChangeDate may not be tracked in this project")

    # WIP
    print("\nWork In Progress (WIP):")
    print(f"  Open items:       {project_data['wip_count']}")
    if project_data["wip_count"] == 200:
        print("  [NOTE] Capped at 200 for API efficiency - actual count may be higher")

    # Aging
    aging = project_data["aging_items"]
    print("\nAging Items (>30 days old):")
    print(f"  Count:            {aging['count']}")
    if aging["count"] == 0:
        print("  [NOTE] May be 0 due to fetching only 200 most recent items")

    # Validation steps
    print(f"\n{'-'*80}")
    print("VALIDATION STEPS FOR ADO UI:")
    print(f"{'-'*80}")
    print("1. Lead Time Check:")
    print(f"   - Go to ADO -> {project_data['project_name']} -> Boards -> Queries")
    print("   - Query: State = Closed AND ClosedDate >= [90 days ago]")
    print("   - Export to Excel, calculate ClosedDate - CreatedDate")
    print(f"   - Sort by duration, find 85th percentile (item ~{int(lead_time['sample_size'] * 0.85)})")
    print(f"   - Expected: ~{lead_time['p85']} days")

    print("\n2. WIP Check:")
    print(f"   - Go to ADO -> {project_data['project_name']} -> Boards -> Work Items")
    print("   - Filter: State <> Closed AND State <> Removed")
    print("   - Count total results")
    print(f"   - Expected: Around {project_data['wip_count']} items (we fetch 200 max)")

    print(f"\n3. Data collected: {project_data['collected_at']}")


def main():
    print("Flow Metrics Validation Helper\n")
    print("=" * 80)

    # Load latest metrics
    try:
        latest = load_latest_metrics()
    except FileNotFoundError:
        print("[ERROR] No flow metrics found. Run: python execution/ado_flow_metrics.py")
        return

    print(f"Week: {latest['week_number']} ({latest['week_date']})")
    print(f"Projects analyzed: {len(latest['projects'])}")

    # Display each project
    for project in latest["projects"]:
        display_project_summary(project)

    # Overall summary
    print(f"\n{'='*80}")
    print("PORTFOLIO SUMMARY")
    print(f"{'='*80}")

    all_lead_times = [p["lead_time"]["p85"] for p in latest["projects"] if p["lead_time"]["p85"] is not None]
    total_wip = sum(p["wip_count"] for p in latest["projects"])

    if all_lead_times:
        avg_lead = sum(all_lead_times) / len(all_lead_times)
        print(f"\nAverage Lead Time (P85): {avg_lead:.1f} days")
        print(f"Range: {min(all_lead_times):.1f} - {max(all_lead_times):.1f} days")

    print(f"Total WIP across portfolio: {total_wip} items (partial count)")

    # Key observations
    print(f"\n{'='*80}")
    print("KEY OBSERVATIONS")
    print(f"{'='*80}")

    # Sort projects by lead time
    sorted_projects = sorted(
        latest["projects"], key=lambda p: p["lead_time"]["p85"] if p["lead_time"]["p85"] else 0, reverse=True
    )

    print("\nSlowest projects (highest lead time):")
    for i, p in enumerate(sorted_projects[:3], 1):
        lt = p["lead_time"]["p85"]
        if lt:
            print(f"  {i}. {p['project_name']}: {lt:.1f} days")

    print("\nFastest projects (lowest lead time):")
    for i, p in enumerate(reversed(sorted_projects[-3:]), 1):
        lt = p["lead_time"]["p85"]
        if lt:
            print(f"  {i}. {p['project_name']}: {lt:.1f} days")

    print(f"\n{'='*80}")
    print("Next: Validate a few projects manually in ADO UI to confirm accuracy")
    print("Then: Continue to dashboards or additional collectors")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
