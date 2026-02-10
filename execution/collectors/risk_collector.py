#!/usr/bin/env python3
"""
ADO Risk Collector

Orchestrates multiple risk metric queries using the Command pattern.
Provides a unified interface for collecting all risk-related metrics from Azure DevOps.

Usage:
    from execution.collectors.risk_collector import ADORiskCollector

    collector = ADORiskCollector(wit_client)
    metrics = collector.collect_metrics(
        project_name="MyProject",
        area_path_filter="EXCLUDE:MyProject\\Archive"
    )
"""

from typing import Any

from execution.collectors.risk_queries import (
    BlockedBugsQuery,
    HighPriorityBugsQuery,
    MissingTestsQuery,
    StaleBugsQuery,
)
from execution.core.logging_config import get_logger

logger = get_logger(__name__)


class ADORiskCollector:
    """
    Orchestrates risk metric queries using the Command pattern.

    Manages a collection of risk query classes and provides a unified interface
    for executing them across projects. Supports configurable query selection
    and error handling.

    Attributes:
        wit_client: Azure DevOps Work Item Tracking client
        queries: List of query instances to execute
        stale_threshold_days: Threshold for identifying stale bugs
    """

    def __init__(
        self,
        wit_client: Any,
        stale_threshold_days: int = 30,
        enable_high_priority: bool = True,
        enable_stale: bool = True,
        enable_blocked: bool = True,
        enable_missing_tests: bool = True,
    ) -> None:
        """
        Initialize risk collector with query configuration.

        Args:
            wit_client: Azure DevOps Work Item Tracking client
            stale_threshold_days: Days threshold for stale bugs (default: 30)
            enable_high_priority: Include high-priority bugs query (default: True)
            enable_stale: Include stale bugs query (default: True)
            enable_blocked: Include blocked bugs query (default: True)
            enable_missing_tests: Include missing tests query (default: True)
        """
        self.wit_client = wit_client
        self.stale_threshold_days = stale_threshold_days
        self.queries: list[Any] = []

        # Build query list based on configuration
        if enable_high_priority:
            self.queries.append(HighPriorityBugsQuery(wit_client))

        if enable_stale:
            self.queries.append(StaleBugsQuery(wit_client, stale_threshold_days=stale_threshold_days))

        if enable_blocked:
            self.queries.append(BlockedBugsQuery(wit_client))

        if enable_missing_tests:
            self.queries.append(MissingTestsQuery(wit_client))

        logger.info(f"Initialized ADORiskCollector with {len(self.queries)} queries")

    def collect_metrics(self, project_name: str, area_path_filter: str | None = None) -> dict:
        """
        Execute all configured queries and collect risk metrics.

        Args:
            project_name: ADO project name
            area_path_filter: Optional area path filter (format: "EXCLUDE:path" or "INCLUDE:path")

        Returns:
            Dictionary with aggregated risk metrics:
            {
                "project": str,
                "high_priority_bugs": {...},
                "stale_bugs": {...},
                "blocked_bugs": {...},
                "missing_tests": {...},
                "summary": {
                    "total_risk_items": int,
                    "queries_executed": int,
                    "queries_failed": int
                }
            }
        """
        logger.info(f"Collecting risk metrics for project: {project_name}")

        results: dict[str, Any] = {"project": project_name}
        errors: list[dict] = []
        total_risk_items = 0

        # Execute each query
        for query in self.queries:
            query_name = query.__class__.__name__.replace("Query", "").lower()

            try:
                logger.debug(f"Executing {query_name} query")
                result = query.execute(project_name=project_name, area_path_filter=area_path_filter)

                results[query_name] = result
                total_risk_items += result.get("count", 0)

                logger.info(
                    f"{query_name} query completed",
                    extra={"query": query_name, "count": result.get("count", 0), "project": project_name},
                )

            except Exception as e:
                error_info = {"query": query_name, "error": str(e), "error_type": e.__class__.__name__}

                errors.append(error_info)
                results[query_name] = {
                    "error": str(e),
                    "error_type": e.__class__.__name__,
                }

                logger.error(
                    f"{query_name} query failed",
                    extra={"query": query_name, "project": project_name, "error": str(e)},
                    exc_info=True,
                )

        # Add summary
        results["summary"] = {
            "total_risk_items": total_risk_items,
            "queries_executed": len(self.queries),
            "queries_failed": len(errors),
        }

        if errors:
            results["errors"] = errors
            logger.warning(
                f"Risk collection completed with {len(errors)} errors",
                extra={"project": project_name, "error_count": len(errors)},
            )
        else:
            logger.info(
                "Risk collection completed successfully",
                extra={
                    "project": project_name,
                    "total_risk_items": total_risk_items,
                    "queries_executed": len(self.queries),
                },
            )

        return results

    def collect_for_multiple_projects(
        self, projects: list[dict], area_path_filter_key: str = "area_path_filter"
    ) -> list[dict]:
        """
        Collect risk metrics for multiple projects.

        Args:
            projects: List of project dicts with at least 'project_name' key
            area_path_filter_key: Key name for area path filter in project dict (default: 'area_path_filter')

        Returns:
            List of risk metrics for each project
        """
        logger.info(f"Collecting risk metrics for {len(projects)} projects")

        results = []
        for project in projects:
            project_name = project.get("project_name")
            if not project_name:
                logger.warning("Skipping project with no name", extra={"project": project})
                continue

            area_filter = project.get(area_path_filter_key)

            try:
                metrics = self.collect_metrics(project_name=project_name, area_path_filter=area_filter)
                results.append(metrics)
            except Exception as e:
                logger.error(
                    f"Failed to collect metrics for project {project_name}",
                    extra={"project": project_name, "error": str(e)},
                    exc_info=True,
                )
                # Add error result
                results.append(
                    {
                        "project": project_name,
                        "error": str(e),
                        "error_type": e.__class__.__name__,
                    }
                )

        logger.info(
            "Multi-project collection completed",
            extra={"projects_attempted": len(projects), "projects_succeeded": len(results)},
        )

        return results

    def get_query_names(self) -> list[str]:
        """
        Get list of query names that will be executed.

        Returns:
            List of query class names
        """
        return [query.__class__.__name__ for query in self.queries]
