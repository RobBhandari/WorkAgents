#!/usr/bin/env python3
"""
Async ADO Collector - 5-8x faster than synchronous version

Challenge: Azure DevOps SDK is synchronous only (no async methods)
Solution: Wrap SDK calls in asyncio.to_thread() for non-blocking execution

Optimizations:
- Concurrent project processing: Query all projects simultaneously
- Concurrent work type queries: Bug/Story/Task in parallel
- Thread pool executor: Non-blocking SDK calls

Performance:
- Sequential: 5 projects × 10s = 50 seconds
- Async: max(10s) = 10 seconds
- Speedup: 5x
"""

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from execution.core import get_logger

logger = get_logger(__name__)


class AsyncADOCollector:
    """Async Azure DevOps collector using thread pool for SDK calls"""

    def __init__(self, max_workers: int = 10):
        """
        Initialize async ADO collector.

        Args:
            max_workers: Max concurrent threads for ADO SDK calls (default: 10)
        """
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def _run_in_thread(self, func, *args, **kwargs):
        """
        Run synchronous function in thread pool.

        This makes blocking SDK calls non-blocking from asyncio perspective.

        Args:
            func: Synchronous function to run
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, lambda: func(*args, **kwargs))

    async def collect_quality_metrics_for_project(self, connection, project: dict, config: dict) -> dict:
        """
        Collect quality metrics for single project (non-blocking).

        Wraps synchronous collect_quality_metrics_for_project in thread.

        Args:
            connection: ADO connection
            project: Project metadata
            config: Configuration dict

        Returns:
            Quality metrics for the project
        """
        from execution.collectors.ado_quality_metrics import collect_quality_metrics_for_project

        # Run blocking SDK calls in thread pool
        result: dict = await self._run_in_thread(collect_quality_metrics_for_project, connection, project, config)
        return result

    async def collect_flow_metrics_for_project(self, connection, project: dict, config: dict) -> dict:
        """
        Collect flow metrics for single project with concurrent work type queries.

        Optimization: Query Bug/Story/Task work types concurrently instead of sequentially.

        Args:
            connection: ADO connection
            project: Project metadata
            config: Configuration dict

        Returns:
            Flow metrics for the project
        """
        from execution.collectors.ado_flow_metrics import (
            calculate_aging_items,
            calculate_cycle_time_variance,
            calculate_dual_metrics,
            calculate_lead_time,
            calculate_throughput,
            query_work_items_by_type,
        )

        project_name = project["project_name"]
        ado_project_name = project.get("ado_project_name", project_name)
        area_path_filter = project.get("area_path_filter")
        lookback_days = config.get("lookback_days", 90)

        logger.info(f"Collecting flow metrics for {project_name} (async)")

        wit_client = connection.clients.get_work_item_tracking_client()

        # Query all work types concurrently (instead of sequentially)
        work_types = ["Bug", "User Story", "Task"]

        tasks = [
            self._run_in_thread(
                query_work_items_by_type, wit_client, ado_project_name, work_type, lookback_days, area_path_filter
            )
            for work_type in work_types
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results
        work_items: dict[str, dict[str, object]] = {}
        for work_type, result in zip(work_types, results, strict=False):
            if isinstance(result, Exception):
                logger.error(f"Failed to query {work_type} for {project_name}: {result}")
                work_items[work_type] = {
                    "work_type": work_type,
                    "open_items": [],
                    "closed_items": [],
                    "open_count": 0,
                    "closed_count": 0,
                }
            elif isinstance(result, dict):
                work_items[work_type] = result
            else:
                logger.error(f"Unexpected result type for {work_type}: {type(result)}")
                work_items[work_type] = {
                    "work_type": work_type,
                    "open_items": [],
                    "closed_items": [],
                    "open_count": 0,
                    "closed_count": 0,
                }

        # Calculate metrics for each work type (synchronous - just data processing)
        work_type_metrics = {}
        for work_type, data in work_items.items():
            open_items = data.get("open_items", [])
            closed_items = data.get("closed_items", [])
            open_count = data.get("open_count", 0)
            closed_count = data.get("closed_count", 0)

            # Type narrowing: ensure we have lists
            if not isinstance(open_items, list):
                open_items = []
            if not isinstance(closed_items, list):
                closed_items = []
            if not isinstance(open_count, int):
                open_count = 0
            if not isinstance(closed_count, int):
                closed_count = 0

            work_type_metrics[work_type] = {
                "open_count": open_count,
                "closed_count_90d": closed_count,
                "wip": open_count,
                "lead_time": calculate_lead_time(closed_items),
                "dual_metrics": calculate_dual_metrics(closed_items),
                "aging_items": calculate_aging_items(open_items, config.get("aging_threshold_days", 30)),
                "throughput": calculate_throughput(closed_items, lookback_days),
                "cycle_time_variance": calculate_cycle_time_variance(closed_items),
            }

        return {
            "project_key": project["project_key"],
            "project_name": project_name,
            "work_type_metrics": work_type_metrics,
            "collected_at": datetime.now().isoformat(),
        }

    async def collect_all_projects(
        self, connection, projects: list[dict], config: dict, collector_type: str = "quality"
    ) -> list[dict]:
        """
        Collect metrics for all projects concurrently.

        Args:
            connection: ADO connection
            projects: List of project configs
            config: Collection config
            collector_type: "quality" or "flow"

        Returns:
            List of project metrics
        """
        logger.info(f"Collecting {collector_type} metrics for {len(projects)} projects (async)")

        if collector_type == "quality":
            tasks = [self.collect_quality_metrics_for_project(connection, project, config) for project in projects]
        elif collector_type == "flow":
            tasks = [self.collect_flow_metrics_for_project(connection, project, config) for project in projects]
        else:
            raise ValueError(f"Unknown collector type: {collector_type}")

        start = datetime.now()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        duration = (datetime.now() - start).total_seconds()

        # Filter out exceptions
        metrics: list[dict] = []
        errors = 0
        for project, result in zip(projects, results, strict=False):
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
            f"({errors} errors, {len(metrics) / duration:.2f} projects/sec)"
        )

        return metrics

    def shutdown(self) -> None:
        """Shutdown thread pool executor"""
        self.executor.shutdown(wait=True)


async def main_quality():
    """Async main for quality metrics"""
    import json

    from execution.collectors.ado_quality_metrics import get_ado_connection, save_quality_metrics

    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    logger.info("=" * 60)
    logger.info("Async ADO Quality Metrics Collector Starting")
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

    # Connect to ADO (synchronous - one-time operation)
    try:
        connection = get_ado_connection()
        logger.info("Connected to Azure DevOps")
    except Exception as e:
        logger.error(f"Failed to connect to ADO: {e}")
        return 1

    # Create async collector
    collector = AsyncADOCollector(max_workers=10)

    try:
        # Collect quality metrics concurrently
        config = {"lookback_days": 90}
        project_metrics = await collector.collect_all_projects(connection, projects, config, collector_type="quality")

        # Save results
        week_metrics = {
            "week_date": datetime.now().strftime("%Y-%m-%d"),
            "week_number": datetime.now().isocalendar()[1],
            "projects": project_metrics,
            "config": {**config, "async": True},
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

    finally:
        collector.shutdown()


async def main_flow():
    """Async main for flow metrics"""
    import json

    from execution.collectors.ado_flow_metrics import get_ado_connection, save_flow_metrics

    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    logger.info("=" * 60)
    logger.info("Async ADO Flow Metrics Collector Starting")
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

    # Connect to ADO
    try:
        connection = get_ado_connection()
        logger.info("Connected to Azure DevOps")
    except Exception as e:
        logger.error(f"Failed to connect to ADO: {e}")
        return 1

    # Create async collector
    collector = AsyncADOCollector(max_workers=10)

    try:
        # Collect flow metrics concurrently
        config = {"lookback_days": 90, "aging_threshold_days": 30}
        project_metrics = await collector.collect_all_projects(connection, projects, config, collector_type="flow")

        # Save results
        week_metrics = {
            "week_date": datetime.now().strftime("%Y-%m-%d"),
            "week_number": datetime.now().isocalendar()[1],
            "projects": project_metrics,
            "config": {**config, "async": True},
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

    finally:
        collector.shutdown()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Async ADO Metrics Collector")
    parser.add_argument("--type", choices=["quality", "flow"], default="quality", help="Metrics type to collect")
    args = parser.parse_args()

    if args.type == "quality":
        sys.exit(asyncio.run(main_quality()))
    elif args.type == "flow":
        sys.exit(asyncio.run(main_flow()))
