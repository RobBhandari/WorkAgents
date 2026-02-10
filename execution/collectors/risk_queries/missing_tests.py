#!/usr/bin/env python3
"""
Missing Tests Query

Query class for collecting work items without test coverage from Azure DevOps.
Part of risk metrics collection - work items without tests represent quality risk.

Command Pattern:
    query = MissingTestsQuery(wit_client)
    result = query.execute(project_name="MyProject", area_path_filter="EXCLUDE:path")
"""

from datetime import datetime, timedelta
from typing import Any

from azure.devops.exceptions import AzureDevOpsServiceError
from azure.devops.v7_1.work_item_tracking import Wiql

from execution.core.logging_config import get_logger
from execution.security_utils import WIQLValidator
from execution.utils.ado_batch_utils import BatchFetchError, batch_fetch_work_items

logger = get_logger(__name__)


class MissingTestsQuery:
    """
    Query for work items without test coverage from Azure DevOps.

    Collects User Stories and Features that are closed/completed but have no linked Test Cases,
    representing potential quality risk from untested functionality.

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

    def build_wiql(self, project_name: str, lookback_date: str, area_filter_clause: str = "") -> str:
        """
        Build WIQL query string for work items without tests.

        Args:
            project_name: ADO project name (must be validated)
            lookback_date: ISO date string for lookback period (must be validated)
            area_filter_clause: Optional WIQL clause for area path filtering

        Returns:
            WIQL query string for work items without test coverage
        """
        # Project name and lookback_date must already be validated by caller
        query = f"""
        SELECT [System.Id], [System.Title], [System.State], [System.WorkItemType],
               [System.CreatedDate], [Microsoft.VSTS.Common.ClosedDate],
               [Microsoft.VSTS.Common.Priority], [System.CreatedBy]
        FROM WorkItems
        WHERE [System.TeamProject] = '{project_name}'
          AND [System.WorkItemType] IN ('User Story', 'Feature')
          AND [System.State] IN ('Closed', 'Done', 'Resolved')
          AND [Microsoft.VSTS.Common.ClosedDate] >= '{lookback_date}'
          {area_filter_clause}
        ORDER BY [Microsoft.VSTS.Common.ClosedDate] DESC
        """
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

    def _has_test_links(self, work_item_id: int) -> bool:
        """
        Check if a work item has any linked Test Cases.

        Args:
            work_item_id: Work item ID to check

        Returns:
            True if work item has test links, False otherwise
        """
        try:
            work_item = self.wit_client.get_work_item(work_item_id, expand="Relations")

            # Check if work item has any relations
            if not work_item.relations:
                return False

            # Check for Test Case links (relation type: Microsoft.VSTS.Common.TestedBy-Forward)
            for relation in work_item.relations:
                if hasattr(relation, "rel") and "TestedBy" in relation.rel:
                    return True

            return False

        except AzureDevOpsServiceError as e:
            logger.warning(f"Error checking test links for work item {work_item_id}: {e}")
            # If we can't determine, assume it has tests to be conservative
            return True
        except Exception as e:
            logger.warning(f"Unexpected error checking test links for work item {work_item_id}: {e}")
            return True

    def execute(self, project_name: str, lookback_days: int = 90, area_path_filter: str | None = None) -> dict:
        """
        Execute WIQL query for work items without test coverage.

        Args:
            project_name: ADO project name
            lookback_days: Number of days to look back for closed work items (default: 90)
            area_path_filter: Optional area path filter (format: "EXCLUDE:path" or "INCLUDE:path")

        Returns:
            Dictionary with query results:
            {
                "project": str,
                "work_items_without_tests": list[dict],
                "count": int,
                "user_story_count": int,
                "feature_count": int,
                "total_closed_items": int,
                "test_coverage_pct": float,
                "queried_at": str
            }

        Raises:
            AzureDevOpsServiceError: If ADO query fails
            BatchFetchError: If batch fetching fails
        """
        logger.info(f"Querying work items without tests for project: {project_name}")

        # Validate inputs to prevent WIQL injection
        safe_project = WIQLValidator.validate_project_name(project_name)
        lookback_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        safe_lookback_date = WIQLValidator.validate_date_iso8601(lookback_date)

        # Build area path filter clause (validates area paths internally)
        area_filter_clause = self._build_area_filter_clause(area_path_filter)

        # Build and execute WIQL query
        wiql_query = self.build_wiql(safe_project, safe_lookback_date, area_filter_clause)
        wiql = Wiql(query=wiql_query)

        try:
            # Execute query
            query_result = self.wit_client.query_by_wiql(wiql).work_items

            if not query_result or len(query_result) == 0:
                logger.info(f"No closed work items found for project: {project_name}")
                return {
                    "project": project_name,
                    "work_items_without_tests": [],
                    "count": 0,
                    "user_story_count": 0,
                    "feature_count": 0,
                    "total_closed_items": 0,
                    "test_coverage_pct": 100.0,
                    "queried_at": datetime.now().isoformat(),
                }

            total_closed_items = len(query_result)
            logger.info(f"Found {total_closed_items} closed work items")

            # Extract work item IDs
            item_ids = [item.id for item in query_result]

            # Fetch full work item details with batching
            work_items, failed_ids = batch_fetch_work_items(
                self.wit_client,
                item_ids=item_ids,
                fields=[
                    "System.Id",
                    "System.Title",
                    "System.State",
                    "System.WorkItemType",
                    "System.CreatedDate",
                    "Microsoft.VSTS.Common.ClosedDate",
                    "Microsoft.VSTS.Common.Priority",
                    "System.CreatedBy",
                ],
                logger=logger,
            )

            if failed_ids:
                logger.warning(f"Failed to fetch {len(failed_ids)} out of {len(item_ids)} work items")

            # Filter work items that don't have test links
            items_without_tests = []
            for work_item in work_items:
                item_id = work_item.get("System.Id")
                if item_id and not self._has_test_links(item_id):
                    items_without_tests.append(work_item)

            logger.info(
                f"Found {len(items_without_tests)} work items without tests "
                f"out of {total_closed_items} closed items"
            )

            # Count by work item type
            user_story_count = sum(1 for item in items_without_tests if item.get("System.WorkItemType") == "User Story")
            feature_count = sum(1 for item in items_without_tests if item.get("System.WorkItemType") == "Feature")

            # Calculate test coverage percentage
            items_with_tests = total_closed_items - len(items_without_tests)
            test_coverage_pct = (items_with_tests / total_closed_items * 100) if total_closed_items > 0 else 100.0

            result = {
                "project": project_name,
                "work_items_without_tests": items_without_tests,
                "count": len(items_without_tests),
                "user_story_count": user_story_count,
                "feature_count": feature_count,
                "total_closed_items": total_closed_items,
                "test_coverage_pct": round(test_coverage_pct, 1),
                "queried_at": datetime.now().isoformat(),
            }

            logger.info(
                f"Work items without tests collected: {len(items_without_tests)} total "
                f"({user_story_count} User Stories, {feature_count} Features) - "
                f"Test coverage: {test_coverage_pct:.1f}%"
            )

            return result

        except AzureDevOpsServiceError as e:
            logger.error(f"ADO API error querying work items without tests: {e}", extra={"project": project_name})
            raise
        except BatchFetchError as e:
            logger.error(f"Batch fetch error for work items without tests: {e}", extra={"project": project_name})
            raise
        except Exception as e:
            logger.error(f"Unexpected error querying work items without tests: {e}", extra={"project": project_name})
            raise
