#!/usr/bin/env python3
"""
Flow Metrics Query Functions

Functions for querying Azure DevOps work items for flow metrics.
Handles WIQL queries, batching, and security bug filtering.
"""

from datetime import datetime, timedelta

from azure.devops.v7_1.work_item_tracking import Wiql

from execution.collectors.security_bug_filter import filter_security_bugs
from execution.security_utils import WIQLValidator


def query_work_items_by_type(
    wit_client, project_name: str, work_type: str, lookback_days: int = 90, area_path_filter: str | None = None
) -> dict:
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
    lookback_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    # Validate inputs to prevent WIQL injection
    safe_project = WIQLValidator.validate_project_name(project_name)
    safe_work_type = WIQLValidator.validate_work_item_type(work_type)
    safe_lookback_date = WIQLValidator.validate_date_iso8601(lookback_date)

    # Build area path filter clause with validation
    area_filter_clause = ""
    if area_path_filter:
        if area_path_filter.startswith("EXCLUDE:"):
            path = area_path_filter.replace("EXCLUDE:", "")
            safe_path = WIQLValidator.validate_area_path(path)
            area_filter_clause = f"AND [System.AreaPath] NOT UNDER '{safe_path}'"
        elif area_path_filter.startswith("INCLUDE:"):
            path = area_path_filter.replace("INCLUDE:", "")
            safe_path = WIQLValidator.validate_area_path(path)
            area_filter_clause = f"AND [System.AreaPath] UNDER '{safe_path}'"

    # Query 1: Currently open items of this type
    query_open = f"""
        SELECT [System.Id], [System.Title], [System.State], [System.CreatedDate],
               [System.WorkItemType], [Microsoft.VSTS.Common.StateChangeDate], [System.CreatedBy]
        FROM WorkItems
        WHERE [System.TeamProject] = '{safe_project}'
          AND [System.WorkItemType] = '{safe_work_type}'
          AND [System.State] NOT IN ('Closed', 'Removed')
          {area_filter_clause}
        ORDER BY [System.CreatedDate] DESC
        """  # nosec B608 - Input validated by WIQLValidator on lines 36-38
    wiql_open = Wiql(query=query_open)

    # Query 2: Recently closed items of this type
    query_closed = f"""
        SELECT [System.Id], [System.Title], [System.State], [System.CreatedDate],
               [Microsoft.VSTS.Common.ClosedDate], [System.WorkItemType], [Microsoft.VSTS.Common.StateChangeDate], [System.CreatedBy]
        FROM WorkItems
        WHERE [System.TeamProject] = '{safe_project}'
          AND [System.WorkItemType] = '{safe_work_type}'
          AND [System.State] = 'Closed'
          AND [Microsoft.VSTS.Common.ClosedDate] >= '{safe_lookback_date}'
          {area_filter_clause}
        ORDER BY [Microsoft.VSTS.Common.ClosedDate] DESC
        """  # nosec B608 - Input validated by WIQLValidator on lines 36-38
    wiql_closed = Wiql(query=query_closed)

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
                    batch_ids = open_ids[i : i + 200]
                    batch_items = wit_client.get_work_items(
                        ids=batch_ids,
                        fields=[
                            "System.Id",
                            "System.Title",
                            "System.State",
                            "System.CreatedDate",
                            "System.WorkItemType",
                            "Microsoft.VSTS.Common.StateChangeDate",
                            "System.CreatedBy",
                        ],
                    )
                    open_items.extend([item.fields for item in batch_items])
            except Exception as e:
                print(f"      [WARNING] Error fetching open {work_type}s: {e}")

        closed_items = []
        if closed_result and len(closed_result) > 0:
            closed_ids = [item.id for item in closed_result]
            try:
                for i in range(0, len(closed_ids), 200):
                    batch_ids = closed_ids[i : i + 200]
                    batch_items = wit_client.get_work_items(
                        ids=batch_ids,
                        fields=[
                            "System.Id",
                            "System.Title",
                            "System.State",
                            "System.CreatedDate",
                            "Microsoft.VSTS.Common.ClosedDate",
                            "System.WorkItemType",
                            "Microsoft.VSTS.Common.StateChangeDate",
                            "System.CreatedBy",
                        ],
                    )
                    closed_items.extend([item.fields for item in batch_items])
            except Exception as e:
                print(f"      [WARNING] Error fetching closed {work_type}s: {e}")

        # Filter out ArmorCode security bugs (ONLY for Bugs, not Stories/Tasks)
        excluded_open = 0
        excluded_closed = 0
        if work_type == "Bug":
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
            "excluded_security_bugs": {"open": excluded_open, "closed": excluded_closed},
        }

    except Exception as e:
        print(f"      [ERROR] Failed to query {work_type}s: {e}")
        return {"work_type": work_type, "open_items": [], "closed_items": [], "open_count": 0, "closed_count": 0}


def query_work_items_for_flow(
    wit_client, project_name: str, lookback_days: int = 90, area_path_filter: str | None = None
) -> dict:
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
    work_types = ["Bug", "User Story", "Task"]
    results = {}

    for work_type in work_types:
        result = query_work_items_by_type(wit_client, project_name, work_type, lookback_days, area_path_filter)
        results[work_type] = result
        print(
            f"      {work_type}: {result['open_count']} open, {result['closed_count']} closed (last {lookback_days} days)"
        )

    return results
