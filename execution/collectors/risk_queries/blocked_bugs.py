#!/usr/bin/env python3
"""
Blocked Bugs Query

Query class for collecting blocked bugs from Azure DevOps.
Part of risk metrics collection - blocked bugs represent delivery impediments.

Command Pattern:
    query = BlockedBugsQuery(wit_client)
    result = query.execute(project_name="MyProject", area_path_filter="EXCLUDE:path")
"""

from datetime import datetime
from typing import Any

from azure.devops.exceptions import AzureDevOpsServiceError
from azure.devops.v7_1.work_item_tracking import Wiql

from execution.collectors.security_bug_filter import filter_security_bugs
from execution.core.logging_config import get_logger
from execution.security_utils import WIQLValidator
from execution.utils.ado_batch_utils import BatchFetchError, batch_fetch_work_items

logger = get_logger(__name__)


class BlockedBugsQuery:
    """
    Query for blocked bugs from Azure DevOps.

    Collects bugs that are currently in a blocked state, representing delivery impediments.
    Filters out security bugs created by ArmorCode to prevent double-counting.

    Attributes:
        wit_client: Azure DevOps Work Item Tracking client
    """

    def __init__(self, wit_client: Any) -> None:
        """
        Initialize query with ADO client.

        Args:
            wit_client: Azure DevOps Work Item Tracking client
        """
        self.wit_client = wit_client

    def build_wiql(self, project_name: str, area_filter_clause: str = "") -> str:
        """
        Build WIQL query string for blocked bugs.

        Args:
            project_name: ADO project name (must be validated)
            area_filter_clause: Optional WIQL clause for area path filtering

        Returns:
            WIQL query string for blocked bugs
        """
        # Project name must already be validated by caller
        query = f"""
        SELECT [System.Id], [System.Title], [System.State], [System.CreatedDate],
               [Microsoft.VSTS.Common.Priority], [Microsoft.VSTS.Common.Severity],
               [System.Tags], [System.CreatedBy], [Microsoft.VSTS.CMMI.Blocked]
        FROM WorkItems
        WHERE [System.TeamProject] = '{project_name}'
          AND [System.WorkItemType] = 'Bug'
          AND [System.State] NOT IN ('Closed', 'Removed')
          AND [Microsoft.VSTS.CMMI.Blocked] = 'Yes'
          {area_filter_clause}
        ORDER BY [Microsoft.VSTS.Common.Priority] ASC, [System.CreatedDate] ASC
        """  # nosec B608 - project_name validated by WIQLValidator in execute(), area_filter_clause validated in _build_area_filter_clause
        return query

    def _build_area_filter_clause(self, area_path_filter: str | None) -> str:
        """
        Build WIQL area path filter clause with validation.

        Args:
            area_path_filter: Optional area path filter (format: "EXCLUDE:path" or "INCLUDE:path")

        Returns:
            WIQL filter clause string (empty if no filter)
        """
        if not area_path_filter:
            return ""

        if area_path_filter.startswith("EXCLUDE:"):
            path = area_path_filter.replace("EXCLUDE:", "")
            safe_path = WIQLValidator.validate_area_path(path)
            logger.debug(f"Excluding area path: {safe_path}")
            return f"AND [System.AreaPath] NOT UNDER '{safe_path}'"
        elif area_path_filter.startswith("INCLUDE:"):
            path = area_path_filter.replace("INCLUDE:", "")
            safe_path = WIQLValidator.validate_area_path(path)
            logger.debug(f"Including only area path: {safe_path}")
            return f"AND [System.AreaPath] UNDER '{safe_path}'"

        return ""

    def execute(self, project_name: str, area_path_filter: str | None = None) -> dict:
        """
        Execute WIQL query for blocked bugs.

        Args:
            project_name: ADO project name
            area_path_filter: Optional area path filter (format: "EXCLUDE:path" or "INCLUDE:path")

        Returns:
            Dictionary with query results:
            {
                "project": str,
                "blocked_bugs": list[dict],
                "count": int,
                "priority_1_count": int,
                "priority_2_count": int,
                "priority_3_count": int,
                "priority_4_count": int,
                "excluded_security_bugs": int,
                "queried_at": str
            }

        Raises:
            AzureDevOpsServiceError: If ADO query fails
            BatchFetchError: If batch fetching fails
        """
        logger.info(f"Querying blocked bugs for project: {project_name}")

        # Validate inputs to prevent WIQL injection
        safe_project = WIQLValidator.validate_project_name(project_name)

        # Build area path filter clause (validates area paths internally)
        area_filter_clause = self._build_area_filter_clause(area_path_filter)

        # Build and execute WIQL query
        wiql_query = self.build_wiql(safe_project, area_filter_clause)
        wiql = Wiql(query=wiql_query)

        try:
            # Execute query
            query_result = self.wit_client.query_by_wiql(wiql).work_items

            if not query_result or len(query_result) == 0:
                logger.info(f"No blocked bugs found for project: {project_name}")
                return {
                    "project": project_name,
                    "blocked_bugs": [],
                    "count": 0,
                    "priority_1_count": 0,
                    "priority_2_count": 0,
                    "priority_3_count": 0,
                    "priority_4_count": 0,
                    "excluded_security_bugs": 0,
                    "queried_at": datetime.now().isoformat(),
                }

            logger.info(f"Found {len(query_result)} blocked bugs")

            # Extract work item IDs
            bug_ids = [item.id for item in query_result]

            # Fetch full bug details with batching
            bugs, failed_ids = batch_fetch_work_items(
                self.wit_client,
                item_ids=bug_ids,
                fields=[
                    "System.Id",
                    "System.Title",
                    "System.State",
                    "System.CreatedDate",
                    "Microsoft.VSTS.Common.Priority",
                    "Microsoft.VSTS.Common.Severity",
                    "System.Tags",
                    "System.CreatedBy",
                    "Microsoft.VSTS.CMMI.Blocked",
                ],
                logger=logger,
            )

            if failed_ids:
                logger.warning(f"Failed to fetch {len(failed_ids)} out of {len(bug_ids)} blocked bugs")

            # Filter out ArmorCode security bugs to prevent double-counting
            filtered_bugs, excluded_count = filter_security_bugs(bugs)

            if excluded_count > 0:
                logger.info(f"Excluded {excluded_count} security bugs from blocked bug count")

            # Count by priority
            priority_1_count = sum(1 for bug in filtered_bugs if bug.get("Microsoft.VSTS.Common.Priority") == 1)
            priority_2_count = sum(1 for bug in filtered_bugs if bug.get("Microsoft.VSTS.Common.Priority") == 2)
            priority_3_count = sum(1 for bug in filtered_bugs if bug.get("Microsoft.VSTS.Common.Priority") == 3)
            priority_4_count = sum(1 for bug in filtered_bugs if bug.get("Microsoft.VSTS.Common.Priority") == 4)

            result = {
                "project": project_name,
                "blocked_bugs": filtered_bugs,
                "count": len(filtered_bugs),
                "priority_1_count": priority_1_count,
                "priority_2_count": priority_2_count,
                "priority_3_count": priority_3_count,
                "priority_4_count": priority_4_count,
                "excluded_security_bugs": excluded_count,
                "queried_at": datetime.now().isoformat(),
            }

            logger.info(
                f"Blocked bugs collected: {len(filtered_bugs)} total "
                f"(P1: {priority_1_count}, P2: {priority_2_count}, "
                f"P3: {priority_3_count}, P4: {priority_4_count})"
            )

            return result

        except AzureDevOpsServiceError as e:
            logger.error(f"ADO API error querying blocked bugs: {e}", extra={"project": project_name})
            raise
        except BatchFetchError as e:
            logger.error(f"Batch fetch error for blocked bugs: {e}", extra={"project": project_name})
            raise
        except Exception as e:
            logger.error(f"Unexpected error querying blocked bugs: {e}", extra={"project": project_name})
            raise
