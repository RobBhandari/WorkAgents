#!/usr/bin/env python3
"""
Flow Metrics Query Functions

Functions for querying Azure DevOps work items for flow metrics.
Handles WIQL queries, batching, and security bug filtering.

Migrated to Azure DevOps REST API v7.1 (replaces SDK).
"""

import asyncio
from datetime import datetime, timedelta

from execution.collectors.ado_rest_client import AzureDevOpsRESTClient
from execution.collectors.ado_rest_transformers import WorkItemTransformer
from execution.collectors.security_bug_filter import filter_security_bugs
from execution.core.logging_config import get_logger
from execution.security_utils import WIQLValidator

logger = get_logger(__name__)


async def query_work_items_by_type(
    rest_client: AzureDevOpsRESTClient,
    project_name: str,
    work_type: str,
    lookback_days: int = 90,
    area_path_filter: str | None = None,
) -> dict:
    """
    Query work items for a specific work type (Bug, User Story, or Task).

    Executes two WIQL queries:
    1. Currently open work items of the specified type
    2. Recently closed work items (within lookback period)

    Security bugs (created by ArmorCode) are automatically filtered out from Bug queries
    to prevent double-counting with the Security Dashboard.

    :param rest_client: Azure DevOps REST API client
    :param project_name: ADO project name (validated for WIQL injection)
    :param work_type: Work item type ('Bug', 'User Story', or 'Task')
    :param lookback_days: Days to look back for closed items (default: 90)
    :param area_path_filter: Optional area path filter:
        - "EXCLUDE:path" - Exclude work items under path
        - "INCLUDE:path" - Include only work items under path
    :returns: Dictionary with query results::

        {
            "work_type": str,
            "open_items": list[dict],      # Open work items
            "closed_items": list[dict],    # Recently closed work items
            "open_count": int,             # Count after filtering
            "closed_count": int,           # Count after filtering
            "excluded_security_bugs": {"open": int, "closed": int}
        }

    :raises httpx.HTTPStatusError: If ADO API call fails
    :raises ValueError: If project_name or work_type contains invalid characters

    Example:
        >>> from execution.collectors.ado_rest_client import get_ado_rest_client
        >>> rest_client = get_ado_rest_client()
        >>> result = await query_work_items_by_type(rest_client, "MyProject", "Bug", lookback_days=30)
        >>> print(f"Found {result['open_count']} open bugs")
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
        """  # nosec B608 - Input validated by WIQLValidator on lines 60-62

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
        """  # nosec B608 - Input validated by WIQLValidator on lines 60-62

    try:
        # Execute queries concurrently (REST API)
        open_response, closed_response = await asyncio.gather(
            rest_client.query_by_wiql(project=safe_project, wiql_query=query_open),
            rest_client.query_by_wiql(project=safe_project, wiql_query=query_closed),
        )

        # Transform WIQL responses to SDK format
        open_wiql = WorkItemTransformer.transform_wiql_response(open_response)
        closed_wiql = WorkItemTransformer.transform_wiql_response(closed_response)

        open_count = len(open_wiql.work_items) if open_wiql.work_items else 0
        closed_count = len(closed_wiql.work_items) if closed_wiql.work_items else 0

        # Fetch full work item details with batching (200 per batch) - CONCURRENT
        open_items = []
        if open_wiql.work_items and len(open_wiql.work_items) > 0:
            open_ids = [item.id for item in open_wiql.work_items]
            try:
                # Create batch tasks for concurrent execution
                batch_tasks = []
                for i in range(0, len(open_ids), 200):
                    batch_ids = open_ids[i : i + 200]
                    batch_tasks.append(
                        rest_client.get_work_items(
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
                    )
                # Execute all batches concurrently
                batch_responses = await asyncio.gather(*batch_tasks)
                # Transform and combine results
                for response in batch_responses:
                    items = WorkItemTransformer.transform_work_items_response(response)
                    open_items.extend(items)
            except Exception as e:
                logger.warning("Error fetching open work items", extra={"work_type": work_type, "error": str(e)})

        closed_items = []
        if closed_wiql.work_items and len(closed_wiql.work_items) > 0:
            closed_ids = [item.id for item in closed_wiql.work_items]
            try:
                # Create batch tasks for concurrent execution
                batch_tasks = []
                for i in range(0, len(closed_ids), 200):
                    batch_ids = closed_ids[i : i + 200]
                    batch_tasks.append(
                        rest_client.get_work_items(
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
                    )
                # Execute all batches concurrently
                batch_responses = await asyncio.gather(*batch_tasks)
                # Transform and combine results
                for response in batch_responses:
                    items = WorkItemTransformer.transform_work_items_response(response)
                    closed_items.extend(items)
            except Exception as e:
                logger.warning("Error fetching closed work items", extra={"work_type": work_type, "error": str(e)})

        # Filter out ArmorCode security bugs (ONLY for Bugs, not Stories/Tasks)
        excluded_open = 0
        excluded_closed = 0
        if work_type == "Bug":
            open_items, excluded_open = filter_security_bugs(open_items)
            closed_items, excluded_closed = filter_security_bugs(closed_items)
            if excluded_open > 0 or excluded_closed > 0:
                logger.info(
                    "Security bugs filtered", extra={"excluded_open": excluded_open, "excluded_closed": excluded_closed}
                )

        return {
            "work_type": work_type,
            "open_items": open_items,
            "closed_items": closed_items,
            "open_count": len(open_items),  # Updated count after filtering
            "closed_count": len(closed_items),  # Updated count after filtering
            "excluded_security_bugs": {"open": excluded_open, "closed": excluded_closed},
        }

    except Exception as e:
        logger.error("Failed to query work items", extra={"work_type": work_type, "error": str(e)})
        return {"work_type": work_type, "open_items": [], "closed_items": [], "open_count": 0, "closed_count": 0}


async def query_work_items_for_flow(
    rest_client: AzureDevOpsRESTClient,
    project_name: str,
    lookback_days: int = 90,
    area_path_filter: str | None = None,
) -> dict[str, dict]:
    """
    Query work items for flow metrics, segmented by work type.

    Queries all three standard work types (Bug, User Story, Task) CONCURRENTLY
    and returns separate results for each type. This enables work-type-specific flow analysis.

    :param rest_client: Azure DevOps REST API client
    :param project_name: ADO project name
    :param lookback_days: Days to look back for closed items (default: 90)
    :param area_path_filter: Optional area path filter (format: "EXCLUDE:path" or "INCLUDE:path")
    :returns: Dictionary mapping work type to query results::

        {
            "Bug": {...},         # Result from query_work_items_by_type()
            "User Story": {...},  # Result from query_work_items_by_type()
            "Task": {...}         # Result from query_work_items_by_type()
        }

    :raises httpx.HTTPStatusError: If ADO API calls fail

    Example:
        >>> from execution.collectors.ado_rest_client import get_ado_rest_client
        >>> rest_client = get_ado_rest_client()
        >>> results = await query_work_items_for_flow(rest_client, "MyProject")
        >>> print(f"Open bugs: {results['Bug']['open_count']}")
        >>> print(f"Open stories: {results['User Story']['open_count']}")
    """
    logger.info("Querying work items", extra={"project": project_name})

    # Show area path filter if specified
    if area_path_filter:
        if area_path_filter.startswith("EXCLUDE:"):
            logger.info("Excluding area path", extra={"area_path": area_path_filter.replace("EXCLUDE:", "")})
        elif area_path_filter.startswith("INCLUDE:"):
            logger.info("Including only area path", extra={"area_path": area_path_filter.replace("INCLUDE:", "")})

    # Query all work types CONCURRENTLY (3x faster than sequential)
    work_types = ["Bug", "User Story", "Task"]

    # Create tasks for all work types
    tasks = [
        query_work_items_by_type(rest_client, project_name, work_type, lookback_days, area_path_filter)
        for work_type in work_types
    ]

    # Execute concurrently
    results_list = await asyncio.gather(*tasks)

    # Combine results into dictionary
    results = {}
    for work_type, result in zip(work_types, results_list, strict=True):
        results[work_type] = result
        logger.info(
            "Work items queried",
            extra={
                "work_type": work_type,
                "open_count": result["open_count"],
                "closed_count": result["closed_count"],
                "lookback_days": lookback_days,
            },
        )

    return results
