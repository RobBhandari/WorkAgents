#!/usr/bin/env python3
"""
ADO Ownership Metrics Collector for Director Observatory

Collects ownership and assignment metrics at project level:
- Unassigned Items: Work without an owner
- Thrash Index: Items reassigned multiple times
- Assignment Distribution: Load balance across team
- Orphan Areas: Areas/services without clear ownership

Read-only operation - does not modify any existing data.
"""

from execution.core import get_config
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


def get_ado_connection():
    """Get ADO connection using credentials from .env"""
    organization_url = get_config().get("ADO_ORGANIZATION_URL")
    pat = get_config().get_ado_config().pat

    if not organization_url or not pat:
        raise ValueError("ADO_ORGANIZATION_URL and ADO_PAT must be set in .env file")

    credentials = BasicAuthentication('', pat)
    connection = Connection(base_url=organization_url, creds=credentials)
    return connection


def query_work_items_for_ownership(wit_client, project_name: str, area_path_filter: str = None) -> Dict:
    """
    Query work items for ownership analysis.

    Args:
        wit_client: Work Item Tracking client
        project_name: ADO project name
        area_path_filter: Optional area path filter (format: "EXCLUDE:path" or "INCLUDE:path")

    Returns:
        Dictionary with work items
    """
    print(f"    Querying work items for ownership analysis...")

    # Build area path filter clause
    area_filter_clause = ""
    if area_path_filter:
        if area_path_filter.startswith("EXCLUDE:"):
            path = area_path_filter.replace("EXCLUDE:", "")
            area_filter_clause = f"AND [System.AreaPath] NOT UNDER '{path}'"
            print(f"      Excluding area path: {path}")
        elif area_path_filter.startswith("INCLUDE:"):
            path = area_path_filter.replace("INCLUDE:", "")
            area_filter_clause = f"AND [System.AreaPath] UNDER '{path}'"
            print(f"      Including only area path: {path}")

    # Query: Actionable work items only (New, Active, In Progress)
    # Excludes: Resolved (functionally done), Closed, Removed
    # Focuses on: Bugs, User Stories, Tasks (not Epics/Features which are planning items)
    wiql_open = Wiql(
        query=f"""
        SELECT [System.Id], [System.Title], [System.State], [System.CreatedDate],
               [System.WorkItemType], [System.AssignedTo], [System.AreaPath],
               [System.ChangedDate]
        FROM WorkItems
        WHERE [System.TeamProject] = '{project_name}'
          AND [System.State] IN ('New', 'Active', 'In Progress', 'Committed')
          AND [System.WorkItemType] IN ('Bug', 'User Story', 'Task')
          {area_filter_clause}
        ORDER BY [System.CreatedDate] DESC
        """
    )

    try:
        # Execute query
        open_result = wit_client.query_by_wiql(wiql_open).work_items

        print(f"      Found {len(open_result) if open_result else 0} actionable items")

        # Fetch full work item details for ALL items
        open_items = []
        if open_result and len(open_result) > 0:
            # Fetch ALL items (ADO API limit per batch is ~200, so we'll batch)
            open_ids = [item.id for item in open_result]

            # Batch in chunks of 200 to avoid API errors
            for i in range(0, len(open_ids), 200):
                batch_ids = open_ids[i:i+200]
                try:
                    batch_items = wit_client.get_work_items(
                        ids=batch_ids,
                        fields=['System.Id', 'System.Title', 'System.State', 'System.CreatedDate',
                                'System.WorkItemType', 'System.AssignedTo', 'System.AreaPath',
                                'System.ChangedDate']
                    )
                    open_items.extend([item.fields for item in batch_items])
                except Exception as e:
                    print(f"      [WARNING] Error fetching batch {i//200 + 1}: {e}")

        print(f"      Fetched {len(open_items)} items for analysis")

        return {
            "open_items": open_items,
            "total_count": len(open_items)  # Use actual fetched count, not query count
        }

    except Exception as e:
        print(f"      [ERROR] Failed to query work items: {e}")
        return {
            "open_items": [],
            "total_count": 0
        }


def calculate_unassigned_items(open_items: List[Dict]) -> Dict:
    """
    Calculate count and details of unassigned work items.

    Args:
        open_items: List of open work items

    Returns:
        Unassigned items metrics
    """
    unassigned_items = []

    for item in open_items:
        assigned_to = item.get('System.AssignedTo')

        # Check if item is unassigned (no AssignedTo or empty)
        if not assigned_to or (isinstance(assigned_to, dict) and not assigned_to.get('displayName')):
            unassigned_items.append({
                "id": item.get('System.Id'),
                "title": item.get('System.Title'),
                "type": item.get('System.WorkItemType'),
                "state": item.get('System.State'),
                "area_path": item.get('System.AreaPath'),
                "created_date": item.get('System.CreatedDate')
            })

    total_items = len(open_items)
    unassigned_count = len(unassigned_items)
    unassigned_pct = (unassigned_count / total_items * 100) if total_items > 0 else 0

    return {
        "unassigned_count": unassigned_count,
        "total_items": total_items,
        "unassigned_pct": round(unassigned_pct, 1),
        "items": unassigned_items[:20],  # Top 20 for reference
        "by_type": {
            "bugs": sum(1 for item in unassigned_items if item['type'] == 'Bug'),
            "features": sum(1 for item in unassigned_items if item['type'] in ['Feature', 'User Story']),
            "tasks": sum(1 for item in unassigned_items if item['type'] == 'Task')
        }
    }


def calculate_work_type_segmentation(open_items: List[Dict]) -> Dict:
    """
    Calculate detailed work type breakdown with assignment rates.

    Shows: How many Bugs/Stories/Tasks exist and what % are unassigned for each.

    Args:
        open_items: List of open work items

    Returns:
        Work type segmentation with assignment rates
    """
    from collections import defaultdict

    type_totals = defaultdict(int)
    type_unassigned = defaultdict(int)

    for item in open_items:
        work_type = item.get('System.WorkItemType', 'Unknown')
        assigned_to = item.get('System.AssignedTo')

        type_totals[work_type] += 1

        # Check if unassigned
        if not assigned_to or (isinstance(assigned_to, dict) and not assigned_to.get('displayName')):
            type_unassigned[work_type] += 1

    # Build segmentation for primary work types
    segmentation = {}
    primary_types = ['Bug', 'User Story', 'Task']

    for wtype in primary_types:
        total = type_totals.get(wtype, 0)
        unassigned = type_unassigned.get(wtype, 0)
        unassigned_pct = (unassigned / total * 100) if total > 0 else 0

        segmentation[wtype] = {
            'total': total,
            'unassigned': unassigned,
            'assigned': total - unassigned,
            'unassigned_pct': round(unassigned_pct, 1)
        }

    # Add "Other" category for all other types
    other_types = [t for t in type_totals.keys() if t not in primary_types]
    other_total = sum(type_totals[t] for t in other_types)
    other_unassigned = sum(type_unassigned[t] for t in other_types)
    other_unassigned_pct = (other_unassigned / other_total * 100) if other_total > 0 else 0

    segmentation['Other'] = {
        'total': other_total,
        'unassigned': other_unassigned,
        'assigned': other_total - other_unassigned,
        'unassigned_pct': round(other_unassigned_pct, 1),
        'types_included': other_types
    }

    return segmentation


def calculate_assignment_distribution(open_items: List[Dict]) -> Dict:
    """
    Calculate how work is distributed across assignees.

    Args:
        open_items: List of open work items

    Returns:
        Assignment distribution metrics
    """
    assignee_counts = {}

    for item in open_items:
        assigned_to = item.get('System.AssignedTo')

        # Extract assignee name
        if assigned_to:
            if isinstance(assigned_to, dict):
                assignee_name = assigned_to.get('displayName', 'Unassigned')
            else:
                assignee_name = assigned_to
        else:
            assignee_name = 'Unassigned'

        if assignee_name not in assignee_counts:
            assignee_counts[assignee_name] = 0

        assignee_counts[assignee_name] += 1

    # Sort by count (descending)
    sorted_assignees = sorted(assignee_counts.items(), key=lambda x: x[1], reverse=True)

    # Calculate load imbalance
    if len(sorted_assignees) > 1:
        max_load = sorted_assignees[0][1]
        min_load = sorted_assignees[-1][1] if sorted_assignees[-1][0] != 'Unassigned' else sorted_assignees[-2][1] if len(sorted_assignees) > 1 else 0
        load_imbalance_ratio = max_load / min_load if min_load > 0 else None
    else:
        load_imbalance_ratio = None

    return {
        "assignee_count": len(assignee_counts) - (1 if 'Unassigned' in assignee_counts else 0),
        "top_assignees": sorted_assignees[:10],  # Top 10 loaded
        "load_imbalance_ratio": round(load_imbalance_ratio, 2) if load_imbalance_ratio else None
    }


def calculate_area_unassigned_stats(open_items: List[Dict]) -> Dict:
    """
    Calculate unassigned work statistics by area path.

    HARD DATA ONLY - No classification, no thresholds, no labels.
    Just raw counts and percentages.

    Args:
        open_items: List of open work items

    Returns:
        Area unassigned statistics (raw data)
    """
    area_stats = {}

    for item in open_items:
        area_path = item.get('System.AreaPath', 'Unknown')
        assigned_to = item.get('System.AssignedTo')

        is_assigned = assigned_to and (not isinstance(assigned_to, dict) or assigned_to.get('displayName'))

        if area_path not in area_stats:
            area_stats[area_path] = {
                "total": 0,
                "unassigned": 0
            }

        area_stats[area_path]["total"] += 1
        if not is_assigned:
            area_stats[area_path]["unassigned"] += 1

    # Convert to list with percentages (NO FILTERING, NO THRESHOLDS)
    area_list = []
    for area, stats in area_stats.items():
        unassigned_pct = (stats["unassigned"] / stats["total"] * 100) if stats["total"] > 0 else 0

        area_list.append({
            "area_path": area,
            "total_items": stats["total"],
            "unassigned_items": stats["unassigned"],
            "unassigned_pct": round(unassigned_pct, 1)
        })

    # Sort by unassigned percentage (highest first) - NO LIMIT
    area_list.sort(key=lambda x: x['unassigned_pct'], reverse=True)

    return {
        "area_count": len(area_list),
        "areas": area_list  # All areas, no filtering
    }


def calculate_developer_active_days(git_client, project_name: str, days: int = 90) -> Dict:
    """
    Calculate developer active days - count of unique commit dates per developer.

    HARD DATA: Actual commit dates from Git history.

    Args:
        git_client: Git client
        project_name: ADO project name
        days: Lookback period

    Returns:
        Developer active days metrics
    """
    from collections import defaultdict

    lookback_date = datetime.now() - timedelta(days=days)

    try:
        # Get all repositories
        repos = git_client.get_repositories(project=project_name)

        developer_dates = defaultdict(set)  # dev -> set of dates
        total_commits = 0

        for repo in repos:
            try:
                from azure.devops.v7_1.git.models import GitQueryCommitsCriteria

                search_criteria = GitQueryCommitsCriteria(
                    from_date=lookback_date.isoformat()
                )

                commits = git_client.get_commits(
                    repository_id=repo.id,
                    project=project_name,
                    search_criteria=search_criteria
                )

                for commit in commits:
                    if commit.author:
                        author_name = commit.author.name
                        commit_date = commit.author.date.date() if commit.author.date else None

                        if commit_date:
                            developer_dates[author_name].add(commit_date)
                            total_commits += 1

            except Exception as e:
                continue

        # Calculate active days per developer
        developer_stats = []
        for dev, dates in developer_dates.items():
            active_days = len(dates)
            developer_stats.append({
                'developer': dev,
                'active_days': active_days,
                'commits': sum(1 for d in dates)  # This is approximate
            })

        # Sort by active days
        developer_stats.sort(key=lambda x: x['active_days'], reverse=True)

        return {
            'sample_size': len(developer_stats),
            'total_commits': total_commits,
            'lookback_days': days,
            'developers': developer_stats[:20],  # Top 20
            'avg_active_days': round(sum(d['active_days'] for d in developer_stats) / len(developer_stats), 1) if developer_stats else None
        }

    except Exception as e:
        print(f"      [WARNING] Could not calculate developer active days: {e}")
        return {
            'sample_size': 0,
            'total_commits': 0,
            'lookback_days': days,
            'developers': [],
            'avg_active_days': None
        }


def collect_ownership_metrics_for_project(connection, project: Dict, config: Dict) -> Dict:
    """
    Collect all ownership metrics for a single project.

    Args:
        connection: ADO connection
        project: Project metadata from discovery
        config: Configuration dict

    Returns:
        Ownership metrics dictionary for the project
    """
    project_name = project['project_name']
    project_key = project['project_key']

    # Get the actual ADO project name (may differ from display name)
    ado_project_name = project.get('ado_project_name', project_name)

    # Get area path filter if specified
    area_path_filter = project.get('area_path_filter')

    print(f"\n  Collecting ownership metrics for: {project_name}")

    wit_client = connection.clients.get_work_item_tracking_client()
    git_client = connection.clients.get_git_client()

    # Query work items
    work_items = query_work_items_for_ownership(wit_client, ado_project_name, area_path_filter)

    # Calculate metrics - HARD DATA ONLY
    unassigned = calculate_unassigned_items(work_items['open_items'])
    distribution = calculate_assignment_distribution(work_items['open_items'])
    area_stats = calculate_area_unassigned_stats(work_items['open_items'])
    work_type_segmentation = calculate_work_type_segmentation(work_items['open_items'])
    developer_activity = calculate_developer_active_days(git_client, ado_project_name, config.get('lookback_days', 90))

    print(f"    Unassigned: {unassigned['unassigned_count']} ({unassigned['unassigned_pct']}%)")
    print(f"    Assignees: {distribution['assignee_count']}")
    print(f"    Areas tracked: {area_stats['area_count']}")
    print(f"    Active Developers: {developer_activity['sample_size']} (avg {developer_activity['avg_active_days']} days)")

    return {
        "project_key": project_key,
        "project_name": project_name,
        "unassigned": unassigned,
        "assignment_distribution": distribution,
        "area_unassigned_stats": area_stats,
        "work_type_segmentation": work_type_segmentation,
        "developer_active_days": developer_activity,  # NEW
        "total_items_analyzed": work_items['total_count'],
        "collected_at": datetime.now().isoformat()
    }


def save_ownership_metrics(metrics: Dict, output_file: str = ".tmp/observatory/ownership_history.json"):
    """
    Save ownership metrics to history file using atomic writes.

    Appends to existing history or creates new file.
    Validates data before saving to prevent persisting collection failures.
    Uses atomic file operations to prevent corruption.
    """
    from utils_atomic_json import atomic_json_save, load_json_with_recovery

    # Validate that we have actual data before saving
    projects = metrics.get('projects', [])

    if not projects:
        print("\n[SKIPPED] No project data to save - collection may have failed")
        return False

    # Check if this looks like a failed collection (all zeros)
    total_items = sum(p.get('total_items_analyzed', 0) for p in projects)
    total_assignees = sum(p.get('assignment_distribution', {}).get('assignee_count', 0) for p in projects)

    if total_items == 0 and total_assignees == 0:
        print("\n[SKIPPED] All projects returned zero ownership data - likely a collection failure")
        print("          Not persisting this data to avoid corrupting trend history")
        return False

    # Load existing history (with automatic corruption recovery)
    history = load_json_with_recovery(output_file, default_value={"weeks": []})

    # Validate structure
    if not isinstance(history, dict) or 'weeks' not in history:
        print("\n[WARNING] Existing history file has invalid structure - recreating")
        history = {"weeks": []}

    # Add new week entry
    history['weeks'].append(metrics)

    # Keep only last 52 weeks (12 months) for quarter/annual analysis
    history['weeks'] = history['weeks'][-52:]

    # Save using atomic write to prevent corruption
    try:
        atomic_json_save(history, output_file)
        print(f"\n[SAVED] Ownership metrics saved to: {output_file}")
        print(f"        History now contains {len(history['weeks'])} week(s)")
        return True
    except Exception as e:
        print(f"\n[ERROR] Failed to save ownership metrics: {e}")
        return False


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    print("Director Observatory - Ownership Metrics Collector\n")
    print("=" * 60)

    # Configuration
    config = {
        'lookback_days': 90
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
        print("[SUCCESS] Connected to ADO")
    except Exception as e:
        print(f"[ERROR] Failed to connect to ADO: {e}")
        exit(1)

    # Collect metrics for all projects
    print("\nCollecting ownership metrics...")
    print("=" * 60)

    project_metrics = []
    for project in projects:
        try:
            metrics = collect_ownership_metrics_for_project(connection, project, config)
            project_metrics.append(metrics)
        except Exception as e:
            print(f"  [ERROR] Failed to collect metrics for {project['project_name']}: {e}")
            continue

    # Save results
    week_metrics = {
        "week_date": datetime.now().strftime('%Y-%m-%d'),
        "week_number": datetime.now().isocalendar()[1],
        "projects": project_metrics,
        "config": config
    }

    save_ownership_metrics(week_metrics)

    # Summary
    print("\n" + "=" * 60)
    print("Ownership Metrics Collection Summary:")
    print(f"  Projects processed: {len(project_metrics)}")

    total_unassigned = sum(p['unassigned']['unassigned_count'] for p in project_metrics)
    total_items = sum(p['total_items_analyzed'] for p in project_metrics)
    overall_unassigned_pct = (total_unassigned / total_items * 100) if total_items > 0 else 0

    print(f"  Total items analyzed: {total_items}")
    print(f"  Total unassigned: {total_unassigned} ({overall_unassigned_pct:.1f}%)")

    print("\nOwnership metrics collection complete!")
    print("  ✓ Only hard data - no thresholds or classifications")
    print("\nNext step: Generate ownership dashboard")
