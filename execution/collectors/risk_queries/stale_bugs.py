#!/usr/bin/env python3
"""
Stale Bugs Query

Query class for collecting stale/aging bugs from Azure DevOps.
Part of risk metrics collection - stale bugs represent technical debt and delivery risk.

Command Pattern:
    query = StaleBugsQuery(wit_client, stale_threshold_days=30)
    result = query.execute(project_name="MyProject", area_path_filter="EXCLUDE:path")
"""

from datetime import datetime, timedelta
from typing import Any

from azure.devops.exceptions import AzureDevOpsServiceError
from azure.devops.v7_1.work_item_tracking import Wiql

from execution.collectors.security_bug_filter import filter_security_bugs
from execution.core.logging_config import get_logger
from execution.security_utils import WIQLValidator
from execution.utils.ado_batch_utils import BatchFetchError, batch_fetch_work_items

logger = get_logger(__name__)


class StaleBugsQuery:
    """
    Query for stale/aging bugs from Azure DevOps.

    Collects bugs that have been open for longer than threshold days.
    Filters out security bugs created by ArmorCode to prevent double-counting.

    Attributes:
        wit_client: Azure DevOps Work Item Tracking client
        stale_threshold_days: Number of days after which a bug is considered stale
    """

    def __init__(self, wit_client: Any, stale_threshold_days: int = 30) -> None:
        """
        Initialize query with ADO client and threshold.

        Args:
            wit_client: Azure DevOps Work Item Tracking client
            stale_threshold_days: Number of days after which a bug is considered stale (default: 30)
        """
        self.wit_client = wit_client
        self.stale_threshold_days = stale_threshold_days

    def build_wiql(self, project_name: str, stale_date: str, area_filter_clause: str = "") -> str:
        """
        Build WIQL query string for stale bugs.

        Args:
            project_name: ADO project name (must be validated)
            stale_date: ISO date string for stale threshold (bugs created before this date)
            area_filter_clause: Optional WIQL clause for area path filtering

        Returns:
            WIQL query string for stale bugs
        """
        # Project name and date must already be validated by caller
        query = f"""
        SELECT [System.Id], [System.Title], [System.State], [System.CreatedDate],
               [Microsoft.VSTS.Common.Priority], [Microsoft.VSTS.Common.Severity],
               [System.Tags], [System.CreatedBy], [Microsoft.VSTS.Common.StateChangeDate]
        FROM WorkItems
        WHERE [System.TeamProject] = '{project_name}'
          AND [System.WorkItemType] = 'Bug'
          AND [System.State] NOT IN ('Closed', 'Removed')
          AND [System.CreatedDate] < '{stale_date}'
          {area_filter_clause}
        ORDER BY [System.CreatedDate] ASC
        """  # nosec B608 - project_name and stale_date validated by WIQLValidator in execute()
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

    def _calculate_bug_age_days(self, bug: dict) -> int:
        """
        Calculate how many days a bug has been open.

        Args:
            bug: Bug dictionary with System.CreatedDate field

        Returns:
            Number of days the bug has been open
        """
        created_date_str = bug.get("System.CreatedDate")
        if not created_date_str:
            return 0

        try:
            # Parse ISO datetime string
            if isinstance(created_date_str, str):
                created_date = datetime.fromisoformat(created_date_str.replace("Z", "+00:00"))
            else:
                created_date = created_date_str

            # Calculate age in days
            age_delta = datetime.now(created_date.tzinfo) - created_date
            return age_delta.days
        except (ValueError, AttributeError, TypeError) as e:
            logger.warning(f"Error calculating bug age: {e}", extra={"bug_id": bug.get("System.Id")})
            return 0

    def execute(self, project_name: str, area_path_filter: str | None = None) -> dict:
        """
        Execute WIQL query for stale bugs.

        Args:
            project_name: ADO project name
            area_path_filter: Optional area path filter (format: "EXCLUDE:path" or "INCLUDE:path")

        Returns:
            Dictionary with query results:
            {
                "project": str,
                "stale_bugs": list[dict],  # Each bug includes "age_days" field
                "count": int,
                "stale_threshold_days": int,
                "avg_age_days": float,
                "oldest_bug_days": int,
                "excluded_security_bugs": int,
                "queried_at": str
            }

        Raises:
            AzureDevOpsServiceError: If ADO query fails
            BatchFetchError: If batch fetching fails
        """
        logger.info(f"Querying stale bugs (>{self.stale_threshold_days} days old) for project: {project_name}")

        # Validate inputs to prevent WIQL injection
        safe_project = WIQLValidator.validate_project_name(project_name)

        # Calculate stale date threshold
        stale_date = (datetime.now() - timedelta(days=self.stale_threshold_days)).strftime("%Y-%m-%d")
        safe_stale_date = WIQLValidator.validate_date_iso8601(stale_date)

        # Build area path filter clause (validates area paths internally)
        area_filter_clause = self._build_area_filter_clause(area_path_filter)

        # Build and execute WIQL query
        wiql_query = self.build_wiql(safe_project, safe_stale_date, area_filter_clause)
        wiql = Wiql(query=wiql_query)

        try:
            # Execute query
            query_result = self.wit_client.query_by_wiql(wiql).work_items

            if not query_result or len(query_result) == 0:
                logger.info(f"No stale bugs found for project: {project_name}")
                return {
                    "project": project_name,
                    "stale_bugs": [],
                    "count": 0,
                    "stale_threshold_days": self.stale_threshold_days,
                    "avg_age_days": 0.0,
                    "oldest_bug_days": 0,
                    "excluded_security_bugs": 0,
                    "queried_at": datetime.now().isoformat(),
                }

            logger.info(f"Found {len(query_result)} stale bugs")

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
                    "Microsoft.VSTS.Common.StateChangeDate",
                ],
                logger=logger,
            )

            if failed_ids:
                logger.warning(f"Failed to fetch {len(failed_ids)} out of {len(bug_ids)} stale bugs")

            # Filter out ArmorCode security bugs to prevent double-counting
            filtered_bugs, excluded_count = filter_security_bugs(bugs)

            if excluded_count > 0:
                logger.info(f"Excluded {excluded_count} security bugs from stale bug count")

            # Calculate age for each bug and add to result
            for bug in filtered_bugs:
                bug["age_days"] = self._calculate_bug_age_days(bug)

            # Calculate statistics
            age_values = [bug["age_days"] for bug in filtered_bugs if bug["age_days"] > 0]
            avg_age_days = sum(age_values) / len(age_values) if age_values else 0.0
            oldest_bug_days = max(age_values) if age_values else 0

            result = {
                "project": project_name,
                "stale_bugs": filtered_bugs,
                "count": len(filtered_bugs),
                "stale_threshold_days": self.stale_threshold_days,
                "avg_age_days": round(avg_age_days, 1),
                "oldest_bug_days": oldest_bug_days,
                "excluded_security_bugs": excluded_count,
                "queried_at": datetime.now().isoformat(),
            }

            logger.info(
                f"Stale bugs collected: {len(filtered_bugs)} total "
                f"(avg age: {result['avg_age_days']} days, oldest: {oldest_bug_days} days)"
            )

            return result

        except AzureDevOpsServiceError as e:
            logger.error(f"ADO API error querying stale bugs: {e}", extra={"project": project_name})
            raise
        except BatchFetchError as e:
            logger.error(f"Batch fetch error for stale bugs: {e}", extra={"project": project_name})
            raise
        except Exception as e:
            logger.error(f"Unexpected error querying stale bugs: {e}", extra={"project": project_name})
            raise
