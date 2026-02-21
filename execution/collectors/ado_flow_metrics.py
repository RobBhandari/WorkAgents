#!/usr/bin/env python3
"""
ADO Flow Metrics Collector for Director Observatory

Collects engineering flow metrics at project level:
- Lead Time (P50, P85, P95): Created Date → Closed Date
- Cycle Time (P50, P85, P95): First Active → Closed Date
- WIP (Work in Progress): Current open items
- Aging Items: Items open > threshold days

Read-only operation - does not modify any existing data.

Migrated to Azure DevOps REST API v7.1 (replaces SDK).
"""

import asyncio
import json
import os
import sys
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv

from execution.collectors.ado_rest_client import get_ado_rest_client
from execution.collectors.flow_metrics_calculations import (
    calculate_aging_items,
    calculate_cycle_time_variance,
    calculate_dual_metrics,
    calculate_lead_time,
    calculate_throughput,
)
from execution.collectors.flow_metrics_queries import query_work_items_for_flow
from execution.core.collector_metrics import track_collector_performance
from execution.domain.constants import flow_metrics, history_retention

load_dotenv()


async def collect_flow_metrics_for_project(rest_client, project: dict, config: dict) -> dict:
    """
    Collect all flow metrics for a single project, segmented by work type.

    Args:
        rest_client: Azure DevOps REST API client
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

    # Query work items (returns segmented by work type) - CONCURRENT EXECUTION
    work_items = await query_work_items_for_flow(
        rest_client,
        ado_project_name,
        lookback_days=config.get("lookback_days", flow_metrics.LOOKBACK_DAYS),
        area_path_filter=area_path_filter,
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
        dual_metrics = calculate_dual_metrics(closed_items)
        aging = calculate_aging_items(
            open_items, aging_threshold_days=config.get("aging_threshold_days", flow_metrics.AGING_THRESHOLD_DAYS)
        )
        throughput = calculate_throughput(closed_items, config.get("lookback_days", flow_metrics.LOOKBACK_DAYS))
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


def _strip_detail_lists_for_history(project: dict) -> dict:
    """Remove detail lists containing work item titles before persisting to history.

    History files are only used for trend sparklines — they need aggregate
    numbers, not individual work item titles or debug values.

    Fields removed per work type:
    - aging_items.items: individual work item titles (can contain customer/client names)
    - lead_time.raw_values: debug lead time samples
    """
    import copy

    p = copy.deepcopy(project)
    for wtype_data in p.get("work_type_metrics", {}).values():
        wtype_data.get("aging_items", {}).pop("items", None)
        wtype_data.get("lead_time", {}).pop("raw_values", None)
    return p


def save_flow_metrics(metrics: dict, output_file: str = ".tmp/observatory/flow_history.json") -> bool:
    """
    Save flow metrics to history file.

    Appends to existing history or creates new file.
    Validates data before saving to prevent persisting collection failures.
    """
    from execution.utils_atomic_json import atomic_json_save, load_json_with_recovery

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

    # Strip detail lists before persisting — history is for trend sparklines only
    stripped_projects = [_strip_detail_lists_for_history(p) for p in metrics.get("projects", [])]
    history_entry = {**metrics, "projects": stripped_projects}

    # Add new week entry
    history["weeks"].append(history_entry)

    # Keep only last N weeks for quarter/annual analysis
    history["weeks"] = history["weeks"][-history_retention.WEEKS_TO_RETAIN :]

    # Save updated history
    try:
        atomic_json_save(history, output_file)
        print(f"\n[SAVED] Flow metrics saved to: {output_file}")
        print(f"        History now contains {len(history['weeks'])} week(s)")
        return True
    except Exception as e:
        print(f"\n[ERROR] Failed to save Flow metrics: {e}")
        return False


class FlowCollector:
    """Flow metrics collector using BaseCollector infrastructure"""

    def __init__(self):
        from execution.collectors.base import BaseCollector

        class _BaseHelper(BaseCollector):
            async def collect(self, project, rest_client):
                pass

            def save_metrics(self, results):
                pass

        self._base = _BaseHelper(name="flow", lookback_days=90)
        self.config = {
            "lookback_days": flow_metrics.LOOKBACK_DAYS,
            "aging_threshold_days": flow_metrics.AGING_THRESHOLD_DAYS,
        }

    async def run(self) -> bool:
        with track_collector_performance("flow") as tracker:
            print("Director Observatory - Flow Metrics Collector (REST API)")
            print("=" * 60)

            discovery_data = self._base.load_discovery_data()
            projects = discovery_data.get("projects", [])
            tracker.project_count = len(projects)

            if not projects:
                return False

            rest_client = self._base.get_rest_client()

            print("\nCollecting flow metrics (concurrent execution)...")
            print("=" * 60)

            tasks = [collect_flow_metrics_for_project(rest_client, project, self.config) for project in projects]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            project_metrics: list[dict] = []
            for project, result in zip(projects, results, strict=True):
                if isinstance(result, Exception):
                    print(f"  [ERROR] Failed to collect metrics for {project['project_name']}: {result}")
                else:
                    project_metrics.append(result)  # type: ignore[arg-type]

            week_metrics = {
                "week_date": datetime.now().strftime("%Y-%m-%d"),
                "week_number": datetime.now().isocalendar()[1],
                "projects": project_metrics,
                "config": self.config,
            }

            success = save_flow_metrics(week_metrics)
            tracker.success = success
            self._log_summary(project_metrics)
            return success

    def _log_summary(self, project_metrics: list[dict]) -> None:
        print("\n" + "=" * 60)
        print("Flow Metrics Collection Summary:")
        print(f"  Projects processed: {len(project_metrics)}")
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
        total_excluded_open = sum(
            p["work_type_metrics"].get("Bug", {}).get("excluded_security_bugs", {}).get("open", 0)
            for p in project_metrics
        )
        total_excluded_closed = sum(
            p["work_type_metrics"].get("Bug", {}).get("excluded_security_bugs", {}).get("closed", 0)
            for p in project_metrics
        )
        print(f"\n  Total WIP (all types): {total_open}")
        print(f"  Total Closed (90d, all types): {total_closed}")
        if total_excluded_open > 0 or total_excluded_closed > 0:
            print(
                f"  Security bugs excluded from Bug metrics: {total_excluded_open} open, {total_excluded_closed} closed"
            )
            print("    → Prevents double-counting with Security Dashboard")
        print("  [NOTE] All metrics now segmented by Bug/Story/Task")
        print("  [NOTE] No data limits - absolute accuracy")
        print("\nFlow metrics collection complete (REST API + concurrent execution)!")
        print("  ✓ Security bugs filtered out (no double-counting)")
        print("  ✓ Concurrent collection for maximum speed")
        print("\nNext step: Generate flow dashboard with work type segmentation")


async def main() -> None:
    collector = FlowCollector()
    await collector.run()


if __name__ == "__main__":
    asyncio.run(main())
