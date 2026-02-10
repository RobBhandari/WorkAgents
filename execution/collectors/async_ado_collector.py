#!/usr/bin/env python3
"""
Async ADO Collector - Direct REST API with true async/await

Migrated from SDK thread pool wrapper to true async REST API calls.

Performance:
- All collectors now use Azure DevOps REST API v7.1
- True concurrent execution with asyncio (no thread pool needed)
- HTTP/2 multiplexing for optimal network performance
- Sequential: 5 projects × 10s = 50 seconds
- Async: max(10s) = 10 seconds
- Speedup: 3-10x depending on collector

Breaking Changes from Previous Version:
- No longer uses ThreadPoolExecutor (REST API is truly async)
- Requires rest_client instead of connection
- All collector methods are now pure async (not wrapped)
"""

import asyncio
import sys
from datetime import datetime

from execution.collectors.ado_rest_client import AzureDevOpsRESTClient, get_ado_rest_client
from execution.core import get_logger
from execution.utils.error_handling import log_and_continue

logger = get_logger(__name__)


class AsyncADOCollector:
    """Async Azure DevOps collector using native REST API"""

    def __init__(self, rest_client: AzureDevOpsRESTClient | None = None):
        """
        Initialize async ADO collector.

        Args:
            rest_client: Azure DevOps REST API client (optional, will create if not provided)
        """
        self.rest_client = rest_client or get_ado_rest_client()

    async def collect_quality_metrics_for_project(self, project: dict, config: dict) -> dict:
        """
        Collect quality metrics for single project (true async).

        Args:
            project: Project metadata
            config: Configuration dict

        Returns:
            Quality metrics for the project
        """
        from execution.collectors.ado_quality_metrics import collect_quality_metrics_for_project

        # Direct async call (no thread wrapping needed - REST API is truly async)
        result: dict = await collect_quality_metrics_for_project(self.rest_client, project, config)
        return result

    async def collect_flow_metrics_for_project(self, project: dict, config: dict) -> dict:
        """
        Collect flow metrics for single project (true async).

        Args:
            project: Project metadata
            config: Configuration dict

        Returns:
            Flow metrics for the project
        """
        from execution.collectors.ado_flow_metrics import collect_flow_metrics_for_project

        # Direct async call (no thread wrapping needed - REST API is truly async)
        result: dict = await collect_flow_metrics_for_project(self.rest_client, project, config)
        return result

    async def collect_deployment_metrics_for_project(self, project: dict, config: dict) -> dict:
        """
        Collect deployment metrics for single project (true async).

        Args:
            project: Project metadata
            config: Configuration dict

        Returns:
            Deployment metrics for the project
        """
        from execution.collectors.ado_deployment_metrics import collect_deployment_metrics_for_project

        result: dict = await collect_deployment_metrics_for_project(self.rest_client, project, config)
        return result

    async def collect_ownership_metrics_for_project(self, project: dict, config: dict) -> dict:
        """
        Collect ownership metrics for single project (true async).

        Args:
            project: Project metadata
            config: Configuration dict

        Returns:
            Ownership metrics for the project
        """
        from execution.collectors.ado_ownership_metrics import collect_ownership_metrics_for_project

        result: dict = await collect_ownership_metrics_for_project(self.rest_client, project, config)
        return result

    async def collect_collaboration_metrics_for_project(self, project: dict, config: dict) -> dict:
        """
        Collect collaboration metrics for single project (true async).

        Args:
            project: Project metadata
            config: Configuration dict

        Returns:
            Collaboration metrics for the project
        """
        from execution.collectors.ado_collaboration_metrics import collect_collaboration_metrics_for_project

        result: dict = await collect_collaboration_metrics_for_project(self.rest_client, project, config)
        return result

    async def collect_risk_metrics_for_project(self, project: dict, config: dict) -> dict:
        """
        Collect risk metrics for single project (true async).

        Args:
            project: Project metadata
            config: Configuration dict

        Returns:
            Risk metrics for the project
        """
        from execution.collectors.ado_risk_metrics import collect_risk_metrics_for_project

        result: dict = await collect_risk_metrics_for_project(self.rest_client, project, config)
        return result

    async def collect_all_projects(
        self, projects: list[dict], config: dict, collector_type: str = "quality"
    ) -> list[dict]:
        """
        Collect metrics for all projects concurrently.

        Args:
            projects: List of project configs
            config: Collection config
            collector_type: "quality", "flow", "deployment", "ownership", "collaboration", or "risk"

        Returns:
            List of project metrics
        """
        logger.info(f"Collecting {collector_type} metrics for {len(projects)} projects (async REST API)")

        # Select collector method
        if collector_type == "quality":
            tasks = [self.collect_quality_metrics_for_project(project, config) for project in projects]
        elif collector_type == "flow":
            tasks = [self.collect_flow_metrics_for_project(project, config) for project in projects]
        elif collector_type == "deployment":
            tasks = [self.collect_deployment_metrics_for_project(project, config) for project in projects]
        elif collector_type == "ownership":
            tasks = [self.collect_ownership_metrics_for_project(project, config) for project in projects]
        elif collector_type == "collaboration":
            tasks = [self.collect_collaboration_metrics_for_project(project, config) for project in projects]
        elif collector_type == "risk":
            tasks = [self.collect_risk_metrics_for_project(project, config) for project in projects]
        else:
            raise ValueError(f"Unknown collector type: {collector_type}")

        start = datetime.now()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        duration = (datetime.now() - start).total_seconds()

        # Filter out exceptions
        metrics: list[dict] = []
        errors = 0
        for project, result in zip(projects, results, strict=True):
            if isinstance(result, Exception):
                logger.error(f"Failed to collect {collector_type} metrics for {project['project_name']}: {result}")
                errors += 1
            elif isinstance(result, dict):
                metrics.append(result)
            else:
                logger.error(f"Unexpected result type for {project['project_name']}: {type(result)}")
                errors += 1

        logger.info(
            f"Collected {collector_type} metrics for {len(metrics)} projects in {duration:.2f}s "
            f"({errors} errors, {len(metrics) / duration if duration > 0 else 0:.2f} projects/sec)"
        )

        return metrics


async def main_quality():
    """Async main for quality metrics"""
    import json

    from execution.collectors.ado_quality_metrics import save_quality_metrics

    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    logger.info("=" * 60)
    logger.info("Async ADO Quality Metrics Collector Starting (REST API)")
    logger.info("=" * 60)

    # Load projects
    try:
        with open(".tmp/observatory/ado_structure.json", encoding="utf-8") as f:
            discovery_data = json.load(f)
        projects = discovery_data["projects"]
        logger.info(f"Loaded {len(projects)} projects")
    except FileNotFoundError:
        logger.error("Project discovery file not found. Run: python execution/discover_projects.py")
        return 1

    # Connect to ADO REST API
    try:
        rest_client = get_ado_rest_client()
        logger.info("Connected to Azure DevOps REST API")
    except Exception as e:
        log_and_continue(logger, e, {"operation": "connect_ado"}, "Azure DevOps connection")  # type: ignore[arg-type]
        return 1

    # Create async collector
    collector = AsyncADOCollector(rest_client)

    # Collect quality metrics concurrently
    config = {"lookback_days": 90}
    project_metrics = await collector.collect_all_projects(projects, config, collector_type="quality")

    # Save results
    week_metrics = {
        "week_date": datetime.now().strftime("%Y-%m-%d"),
        "week_number": datetime.now().isocalendar()[1],
        "projects": project_metrics,
        "config": {**config, "async": True, "rest_api": True},
    }

    saved = save_quality_metrics(week_metrics)

    if saved:
        logger.info("=" * 60)
        logger.info(f"Async collection complete ({len(project_metrics)} projects)")
        logger.info("=" * 60)
        return 0
    else:
        logger.error("Failed to save metrics")
        return 1


async def main_flow():
    """Async main for flow metrics"""
    import json

    from execution.collectors.ado_flow_metrics import save_flow_metrics

    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    logger.info("=" * 60)
    logger.info("Async ADO Flow Metrics Collector Starting (REST API)")
    logger.info("=" * 60)

    # Load projects
    try:
        with open(".tmp/observatory/ado_structure.json", encoding="utf-8") as f:
            discovery_data = json.load(f)
        projects = discovery_data["projects"]
        logger.info(f"Loaded {len(projects)} projects")
    except FileNotFoundError:
        logger.error("Project discovery file not found. Run: python execution/discover_projects.py")
        return 1

    # Connect to ADO REST API
    try:
        rest_client = get_ado_rest_client()
        logger.info("Connected to Azure DevOps REST API")
    except Exception as e:
        log_and_continue(logger, e, {"operation": "connect_ado"}, "Azure DevOps connection")  # type: ignore[arg-type]
        return 1

    # Create async collector
    collector = AsyncADOCollector(rest_client)

    # Collect flow metrics concurrently
    config = {"lookback_days": 90, "aging_threshold_days": 30}
    project_metrics = await collector.collect_all_projects(projects, config, collector_type="flow")

    # Save results
    week_metrics = {
        "week_date": datetime.now().strftime("%Y-%m-%d"),
        "week_number": datetime.now().isocalendar()[1],
        "projects": project_metrics,
        "config": {**config, "async": True, "rest_api": True},
    }

    saved = save_flow_metrics(week_metrics)

    if saved:
        logger.info("=" * 60)
        logger.info(f"Async collection complete ({len(project_metrics)} projects)")
        logger.info("=" * 60)
        return 0
    else:
        logger.error("Failed to save metrics")
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Async ADO Metrics Collector (REST API)")
    parser.add_argument("--type", choices=["quality", "flow"], default="quality", help="Metrics type to collect")
    args = parser.parse_args()

    if args.type == "quality":
        sys.exit(asyncio.run(main_quality()))
    elif args.type == "flow":
        sys.exit(asyncio.run(main_flow()))
