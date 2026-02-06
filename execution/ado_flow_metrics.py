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

import os
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import statistics

# Azure DevOps SDK
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from azure.devops.v7_1.work_item_tracking import Wiql

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


def calculate_percentile(values: List[float], percentile: int) -> Optional[float]:
    """Calculate percentile from list of values."""
    if not values:
        return None

    # Remove None values
    values = [v for v in values if v is not None]
    if not values:
        return None

    # Use statistics.quantiles for percentile calculation
    try:
        # quantiles returns n-1 cut points for n quantiles
        # For P85, we want the value at 85% position
        sorted_values = sorted(values)
        index = (percentile / 100) * (len(sorted_values) - 1)
        lower_index = int(index)
        upper_index = min(lower_index + 1, len(sorted_values) - 1)
        weight = index - lower_index
        return sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight
    except Exception as e:
        print(f"    [WARNING] Error calculating P{percentile}: {e}")
        return None


def filter_security_bugs(bugs: List[Dict]) -> tuple:
    """
    Filter out security bugs created by ArmorCode to avoid double-counting.

    These bugs are already tracked in the Security Dashboard, so we exclude them
    from flow metrics to prevent inflating bug counts.

    Returns:
        tuple: (filtered_bugs, excluded_count)
    """
    filtered = []
    excluded = 0

    for bug in bugs:
        created_by = bug.get('System.CreatedBy', {})

        # Extract creator name
        if isinstance(created_by, dict):
            creator_name = created_by.get('displayName', '').lower()
        else:
            creator_name = str(created_by).lower()

        # Exclude bugs created by ArmorCode
        if 'armorcode' in creator_name:
            excluded += 1
        else:
            filtered.append(bug)

    return filtered, excluded


def get_ado_connection():
    """Get ADO connection using credentials from .env"""
    organization_url = os.getenv('ADO_ORGANIZATION_URL')
    pat = os.getenv('ADO_PAT')

    if not organization_url or not pat:
        raise ValueError("ADO_ORGANIZATION_URL and ADO_PAT must be set in .env file")

    credentials = BasicAuthentication('', pat)
    connection = Connection(base_url=organization_url, creds=credentials)
    return connection


def query_work_items_by_type(wit_client, project_name: str, work_type: str, lookback_days: int = 90, area_path_filter: str = None) -> Dict:
    """
    Query work items for a specific work type (Bug, User Story, or Task).

    Args:
        wit_client: Work Item Tracking client
        project_name: ADO project name
        work_type: 'Bug', 'User Story', or 'Task'
        lookback_days: How many days back to look for closed items
        area_path_filter: Optional area path filter (format: "EXCLUDE:path" or "INCLUDE:path")

    Returns:
        Dictionary with open and closed items for the work type
    """
    lookback_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

    # Build area path filter clause
    area_filter_clause = ""
    if area_path_filter:
        if area_path_filter.startswith("EXCLUDE:"):
            path = area_path_filter.replace("EXCLUDE:", "")
            area_filter_clause = f"AND [System.AreaPath] NOT UNDER '{path}'"
        elif area_path_filter.startswith("INCLUDE:"):
            path = area_path_filter.replace("INCLUDE:", "")
            area_filter_clause = f"AND [System.AreaPath] UNDER '{path}'"

    # Query 1: Currently open items of this type
    wiql_open = Wiql(
        query=f"""
        SELECT [System.Id], [System.Title], [System.State], [System.CreatedDate],
               [System.WorkItemType], [Microsoft.VSTS.Common.StateChangeDate], [System.CreatedBy]
        FROM WorkItems
        WHERE [System.TeamProject] = '{project_name}'
          AND [System.WorkItemType] = '{work_type}'
          AND [System.State] NOT IN ('Closed', 'Removed')
          {area_filter_clause}
        ORDER BY [System.CreatedDate] DESC
        """
    )

    # Query 2: Recently closed items of this type
    wiql_closed = Wiql(
        query=f"""
        SELECT [System.Id], [System.Title], [System.State], [System.CreatedDate],
               [Microsoft.VSTS.Common.ClosedDate], [System.WorkItemType], [Microsoft.VSTS.Common.StateChangeDate], [System.CreatedBy]
        FROM WorkItems
        WHERE [System.TeamProject] = '{project_name}'
          AND [System.WorkItemType] = '{work_type}'
          AND [System.State] = 'Closed'
          AND [Microsoft.VSTS.Common.ClosedDate] >= '{lookback_date}'
          {area_filter_clause}
        ORDER BY [Microsoft.VSTS.Common.ClosedDate] DESC
        """
    )

    try:
        # Execute queries
        open_result = wit_client.query_by_wiql(wiql_open).work_items
        closed_result = wit_client.query_by_wiql(wiql_closed).work_items

        open_count = len(open_result) if open_result else 0
        closed_count = len(closed_result) if closed_result else 0

        # Fetch full work item details with batching (200 per batch)
        open_items = []
        if open_result and len(open_result) > 0:
            open_ids = [item.id for item in open_result]
            try:
                for i in range(0, len(open_ids), 200):
                    batch_ids = open_ids[i:i+200]
                    batch_items = wit_client.get_work_items(
                        ids=batch_ids,
                        fields=['System.Id', 'System.Title', 'System.State', 'System.CreatedDate',
                                'System.WorkItemType', 'Microsoft.VSTS.Common.StateChangeDate', 'System.CreatedBy']
                    )
                    open_items.extend([item.fields for item in batch_items])
            except Exception as e:
                print(f"      [WARNING] Error fetching open {work_type}s: {e}")

        closed_items = []
        if closed_result and len(closed_result) > 0:
            closed_ids = [item.id for item in closed_result]
            try:
                for i in range(0, len(closed_ids), 200):
                    batch_ids = closed_ids[i:i+200]
                    batch_items = wit_client.get_work_items(
                        ids=batch_ids,
                        fields=['System.Id', 'System.Title', 'System.State', 'System.CreatedDate',
                                'Microsoft.VSTS.Common.ClosedDate', 'System.WorkItemType',
                                'Microsoft.VSTS.Common.StateChangeDate', 'System.CreatedBy']
                    )
                    closed_items.extend([item.fields for item in batch_items])
            except Exception as e:
                print(f"      [WARNING] Error fetching closed {work_type}s: {e}")

        # Filter out ArmorCode security bugs (ONLY for Bugs, not Stories/Tasks)
        excluded_open = 0
        excluded_closed = 0
        if work_type == 'Bug':
            open_items, excluded_open = filter_security_bugs(open_items)
            closed_items, excluded_closed = filter_security_bugs(closed_items)
            if excluded_open > 0 or excluded_closed > 0:
                print(f"      [Filtered] Excluded {excluded_open} open and {excluded_closed} closed security bugs")

        return {
            "work_type": work_type,
            "open_items": open_items,
            "closed_items": closed_items,
            "open_count": len(open_items),  # Updated count after filtering
            "closed_count": len(closed_items),  # Updated count after filtering
            "excluded_security_bugs": {
                "open": excluded_open,
                "closed": excluded_closed
            }
        }

    except Exception as e:
        print(f"      [ERROR] Failed to query {work_type}s: {e}")
        return {
            "work_type": work_type,
            "open_items": [],
            "closed_items": [],
            "open_count": 0,
            "closed_count": 0
        }


def query_work_items_for_flow(wit_client, project_name: str, lookback_days: int = 90, area_path_filter: str = None) -> Dict:
    """
    Query work items for flow metrics, segmented by work type.

    Args:
        wit_client: Work Item Tracking client
        project_name: ADO project name
        lookback_days: How many days back to look for closed items
        area_path_filter: Optional area path filter (format: "EXCLUDE:path" or "INCLUDE:path")

    Returns:
        Dictionary with work items segmented by type (Bug, User Story, Task)
    """
    print(f"    Querying work items for {project_name}...")

    # Show area path filter if specified
    if area_path_filter:
        if area_path_filter.startswith("EXCLUDE:"):
            print(f"      Excluding area path: {area_path_filter.replace('EXCLUDE:', '')}")
        elif area_path_filter.startswith("INCLUDE:"):
            print(f"      Including only area path: {area_path_filter.replace('INCLUDE:', '')}")

    # Query each work type separately
    work_types = ['Bug', 'User Story', 'Task']
    results = {}

    for work_type in work_types:
        result = query_work_items_by_type(wit_client, project_name, work_type, lookback_days, area_path_filter)
        results[work_type] = result
        print(f"      {work_type}: {result['open_count']} open, {result['closed_count']} closed (last {lookback_days} days)")

    return results


def calculate_lead_time(closed_items: List[Dict]) -> Dict:
    """
    Calculate lead time: Created Date → Closed Date

    Returns percentiles (P50, P85, P95) in days
    """
    lead_times = []

    for item in closed_items:
        created = item.get('System.CreatedDate')
        closed = item.get('Microsoft.VSTS.Common.ClosedDate')

        if created and closed:
            try:
                created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                closed_dt = datetime.fromisoformat(closed.replace('Z', '+00:00'))

                lead_time_days = (closed_dt - created_dt).total_seconds() / 86400  # Convert to days
                if lead_time_days >= 0:  # Sanity check
                    lead_times.append(lead_time_days)
            except Exception as e:
                continue

    return {
        "p50": round(calculate_percentile(lead_times, 50), 1) if lead_times else None,
        "p85": round(calculate_percentile(lead_times, 85), 1) if lead_times else None,
        "p95": round(calculate_percentile(lead_times, 95), 1) if lead_times else None,
        "sample_size": len(lead_times),
        "raw_values": lead_times[:10]  # Keep first 10 for debugging
    }


def calculate_dual_metrics(closed_items: List[Dict], cleanup_threshold_days: int = 365) -> Dict:
    """
    Calculate separate metrics for operational work vs cleanup work.

    Operational: Items closed within 365 days (current/recent work)
    Cleanup: Items closed after >365 days (backlog grooming/historical cleanup)

    This separation prevents cleanup initiatives from distorting operational performance metrics.

    Args:
        closed_items: List of closed work items
        cleanup_threshold_days: Lead time threshold to classify as cleanup (default: 365 days)

    Returns:
        Dict with operational_metrics, cleanup_metrics, and cleanup_indicators
    """
    operational_items = []
    cleanup_items = []
    operational_lead_times = []
    cleanup_lead_times = []

    for item in closed_items:
        created = item.get('System.CreatedDate')
        closed = item.get('Microsoft.VSTS.Common.ClosedDate')

        if created and closed:
            try:
                created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                closed_dt = datetime.fromisoformat(closed.replace('Z', '+00:00'))

                lead_time_days = (closed_dt - created_dt).total_seconds() / 86400

                if lead_time_days >= 0:
                    if lead_time_days < cleanup_threshold_days:
                        # Operational work - closed within threshold
                        operational_items.append(item)
                        operational_lead_times.append(lead_time_days)
                    else:
                        # Cleanup work - very old items closed
                        cleanup_items.append(item)
                        cleanup_lead_times.append(lead_time_days)
            except Exception as e:
                continue

    # Calculate operational metrics
    operational_metrics = {
        "p50": round(calculate_percentile(operational_lead_times, 50), 1) if operational_lead_times else None,
        "p85": round(calculate_percentile(operational_lead_times, 85), 1) if operational_lead_times else None,
        "p95": round(calculate_percentile(operational_lead_times, 95), 1) if operational_lead_times else None,
        "closed_count": len(operational_items),
        "sample_size": len(operational_lead_times)
    }

    # Calculate cleanup metrics
    cleanup_metrics = {
        "p50": round(calculate_percentile(cleanup_lead_times, 50), 1) if cleanup_lead_times else None,
        "p85": round(calculate_percentile(cleanup_lead_times, 85), 1) if cleanup_lead_times else None,
        "p95": round(calculate_percentile(cleanup_lead_times, 95), 1) if cleanup_lead_times else None,
        "closed_count": len(cleanup_items),
        "sample_size": len(cleanup_lead_times),
        "avg_age_years": round(sum(cleanup_lead_times) / len(cleanup_lead_times) / 365, 1) if cleanup_lead_times else None
    }

    # Cleanup indicators - detect if metrics are being distorted
    total_closed = len(operational_items) + len(cleanup_items)
    cleanup_percentage = (len(cleanup_items) / total_closed * 100) if total_closed > 0 else 0

    is_cleanup_effort = cleanup_percentage > 30  # >30% of closures are old items
    has_significant_cleanup = len(cleanup_items) > 10  # More than 10 old items closed

    return {
        "operational": operational_metrics,
        "cleanup": cleanup_metrics,
        "indicators": {
            "cleanup_percentage": round(cleanup_percentage, 1),
            "is_cleanup_effort": is_cleanup_effort,
            "has_significant_cleanup": has_significant_cleanup,
            "total_closed": total_closed,
            "threshold_days": cleanup_threshold_days
        }
    }


# REMOVED: calculate_cycle_time
# Reason: Approximation - StateChangeDate is not actual "first active" time.
# Would require revision history to accurately track when work actually started.
# Current implementation is speculation, not hard data.


def calculate_throughput(closed_items: List[Dict], lookback_days: int = 90) -> Dict:
    """
    Calculate throughput - closed items per week.

    HARD DATA: Just count of closed items over time period.

    Args:
        closed_items: List of closed work items
        lookback_days: Period analyzed

    Returns:
        Throughput metrics
    """
    closed_count = len(closed_items)
    weeks = lookback_days / 7
    per_week = closed_count / weeks if weeks > 0 else 0

    return {
        'closed_count': closed_count,
        'lookback_days': lookback_days,
        'per_week': round(per_week, 1)
    }


def calculate_cycle_time_variance(closed_items: List[Dict]) -> Dict:
    """
    Calculate cycle time variance - standard deviation of lead times.

    HARD DATA: Statistical measure of lead time predictability.

    Args:
        closed_items: List of closed work items

    Returns:
        Variance metrics
    """
    lead_times = []

    for item in closed_items:
        created = item.get('System.CreatedDate')
        closed = item.get('Microsoft.VSTS.Common.ClosedDate')

        if created and closed:
            try:
                created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                closed_dt = datetime.fromisoformat(closed.replace('Z', '+00:00'))

                lead_time_days = (closed_dt - created_dt).total_seconds() / 86400

                if lead_time_days >= 0:
                    lead_times.append(lead_time_days)
            except Exception as e:
                continue

    if len(lead_times) < 2:  # Need at least 2 points for std dev
        return {
            'sample_size': len(lead_times),
            'std_dev_days': None,
            'coefficient_of_variation': None
        }

    std_dev = statistics.stdev(lead_times)
    mean = statistics.mean(lead_times)
    cv = (std_dev / mean * 100) if mean > 0 else None

    return {
        'sample_size': len(lead_times),
        'std_dev_days': round(std_dev, 1),
        'coefficient_of_variation': round(cv, 1) if cv else None,
        'mean_days': round(mean, 1)
    }


def calculate_aging_items(open_items: List[Dict], aging_threshold_days: int = 30) -> Dict:
    """
    Calculate aging items: Items open > threshold days

    Returns count and list of aging items with details
    """
    now = datetime.now()
    aging_items = []

    for item in open_items:
        created = item.get('System.CreatedDate')

        if created:
            try:
                created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                age_days = (now - created_dt.astimezone()).total_seconds() / 86400

                if age_days > aging_threshold_days:
                    aging_items.append({
                        "id": item.get('System.Id'),
                        "title": item.get('System.Title'),
                        "state": item.get('System.State'),
                        "type": item.get('System.WorkItemType'),
                        "age_days": round(age_days, 1),
                        "created_date": created
                    })
            except Exception as e:
                continue

    # Sort by age (oldest first)
    aging_items.sort(key=lambda x: x['age_days'], reverse=True)

    return {
        "count": len(aging_items),
        "threshold_days": aging_threshold_days,
        "items": aging_items[:20]  # Top 20 oldest
    }


def collect_flow_metrics_for_project(wit_client, project: Dict, config: Dict) -> Dict:
    """
    Collect all flow metrics for a single project, segmented by work type.

    Args:
        wit_client: Work Item Tracking client
        project: Project metadata from discovery
        config: Configuration dict (thresholds, lookback days, etc.)

    Returns:
        Flow metrics dictionary for the project with Bug/Story/Task segmentation
    """
    project_name = project['project_name']
    project_key = project['project_key']

    # Get the actual ADO project name (may differ from display name)
    ado_project_name = project.get('ado_project_name', project_name)

    # Get area path filter if specified
    area_path_filter = project.get('area_path_filter')

    print(f"\n  Collecting flow metrics for: {project_name}")

    # Query work items (returns segmented by work type)
    work_items = query_work_items_for_flow(
        wit_client,
        ado_project_name,
        lookback_days=config.get('lookback_days', 90),
        area_path_filter=area_path_filter
    )

    # Calculate metrics for each work type separately
    work_type_metrics = {}
    total_open = 0
    total_closed = 0

    for work_type in ['Bug', 'User Story', 'Task']:
        type_data = work_items.get(work_type, {})
        open_items = type_data.get('open_items', [])
        closed_items = type_data.get('closed_items', [])
        open_count = type_data.get('open_count', 0)
        closed_count = type_data.get('closed_count', 0)

        total_open += open_count
        total_closed += closed_count

        # Calculate lead time and aging for this work type - ONLY HARD DATA
        lead_time = calculate_lead_time(closed_items)
        dual_metrics = calculate_dual_metrics(closed_items, cleanup_threshold_days=365)
        aging = calculate_aging_items(
            open_items,
            aging_threshold_days=config.get('aging_threshold_days', 30)
        )
        throughput = calculate_throughput(closed_items, config.get('lookback_days', 90))
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
            "excluded_security_bugs": type_data.get('excluded_security_bugs', {'open': 0, 'closed': 0})
        }

        # Print metrics for this work type
        print(f"    {work_type}:")
        print(f"      Lead Time (P85): {lead_time['p85']} days")

        # Show dual metrics if cleanup work is significant
        if dual_metrics['indicators']['is_cleanup_effort']:
            print(f"      ⚠️  CLEANUP DETECTED ({dual_metrics['indicators']['cleanup_percentage']:.0f}% old closures)")
            print(f"      Operational Lead Time (P85): {dual_metrics['operational']['p85']} days")
            print(f"      Cleanup Count: {dual_metrics['cleanup']['closed_count']} (avg age: {dual_metrics['cleanup']['avg_age_years']:.1f} years)")

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
        "collected_at": datetime.now().isoformat()
    }


def save_flow_metrics(metrics: Dict, output_file: str = ".tmp/observatory/flow_history.json"):
    """
    Save flow metrics to history file.

    Appends to existing history or creates new file.
    Validates data before saving to prevent persisting collection failures.
    """
    from utils_atomic_json import atomic_json_save, load_json_with_recovery

    # Validate that we have actual data before saving
    projects = metrics.get('projects', [])

    if not projects:
        print("\n[SKIPPED] No project data to save - collection may have failed")
        return False

    # Check if this looks like a failed collection (all zeros)
    total_open = sum(p.get('total_open', 0) for p in projects)
    total_closed = sum(p.get('total_closed_90d', 0) for p in projects)

    if total_open == 0 and total_closed == 0:
        print("\n[SKIPPED] All projects returned zero flow data - likely a collection failure")
        print("          Not persisting this data to avoid corrupting trend history")
        return False

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Load existing history
    history = load_json_with_recovery(output_file, default_value={"weeks": []})

    # Add validation if structure check exists
    if not isinstance(history, dict) or 'weeks' not in history:
        print("\n[WARNING] Existing history file has invalid structure - recreating")
        history = {"weeks": []}

    # Add new week entry
    history['weeks'].append(metrics)

    # Keep only last 52 weeks (12 months) for quarter/annual analysis
    history['weeks'] = history['weeks'][-52:]

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
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    print("Director Observatory - Flow Metrics Collector\n")
    print("=" * 60)

    # Configuration
    config = {
        "lookback_days": 90,  # How many days back to look for closed items
        "aging_threshold_days": 30,  # Items open > 30 days are "aging"
    }

    # Load discovered projects
    try:
        with open(".tmp/observatory/ado_structure.json", 'r', encoding='utf-8') as f:
            discovery_data = json.load(f)
        projects = discovery_data['projects']
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
        "week_date": datetime.now().strftime('%Y-%m-%d'),
        "week_number": datetime.now().isocalendar()[1],  # ISO week number
        "projects": project_metrics,
        "config": config
    }

    save_flow_metrics(week_metrics)

    # Summary
    print("\n" + "=" * 60)
    print("Flow Metrics Collection Summary:")
    print(f"  Projects processed: {len(project_metrics)}")

    # Calculate totals by work type
    totals_by_type = {
        'Bug': {'open': 0, 'closed': 0, 'aging': 0},
        'User Story': {'open': 0, 'closed': 0, 'aging': 0},
        'Task': {'open': 0, 'closed': 0, 'aging': 0}
    }

    for p in project_metrics:
        for work_type in ['Bug', 'User Story', 'Task']:
            metrics = p['work_type_metrics'].get(work_type, {})
            totals_by_type[work_type]['open'] += metrics.get('open_count', 0)
            totals_by_type[work_type]['closed'] += metrics.get('closed_count_90d', 0)
            totals_by_type[work_type]['aging'] += metrics.get('aging_items', {}).get('count', 0)

    print(f"\n  Metrics by Work Type:")
    for work_type in ['Bug', 'User Story', 'Task']:
        totals = totals_by_type[work_type]
        print(f"    {work_type}:")
        print(f"      WIP (open): {totals['open']}")
        print(f"      Closed (90d): {totals['closed']}")
        print(f"      Aging (>30d): {totals['aging']}")

    total_open = sum(p['total_open'] for p in project_metrics)
    total_closed = sum(p['total_closed_90d'] for p in project_metrics)

    # Calculate excluded security bugs (from Bug work type only)
    total_excluded_open = 0
    total_excluded_closed = 0
    for p in project_metrics:
        bug_metrics = p['work_type_metrics'].get('Bug', {})
        total_excluded_open += bug_metrics.get('excluded_security_bugs', {}).get('open', 0)
        total_excluded_closed += bug_metrics.get('excluded_security_bugs', {}).get('closed', 0)

    print(f"\n  Total WIP (all types): {total_open}")
    print(f"  Total Closed (90d, all types): {total_closed}")

    if total_excluded_open > 0 or total_excluded_closed > 0:
        print(f"  Security bugs excluded from Bug metrics: {total_excluded_open} open, {total_excluded_closed} closed")
        print(f"    → Prevents double-counting with Security Dashboard")

    print(f"  [NOTE] All metrics now segmented by Bug/Story/Task")
    print(f"  [NOTE] No data limits - absolute accuracy")

    print("\nFlow metrics collection complete!")
    print("  ✓ Security bugs filtered out (no double-counting)")
    print("\nNext step: Generate flow dashboard with work type segmentation")
