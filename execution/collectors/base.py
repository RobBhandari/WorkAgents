#!/usr/bin/env python3
"""
Base Collector for Director Observatory

Provides shared infrastructure for all ADO metric collectors:
- Platform setup (Windows UTF-8 encoding)
- Discovery data loading
- ADO REST client initialization
- Concurrent metric collection
- Performance tracking integration

All collectors should inherit from BaseCollector to ensure consistency.
"""

import asyncio
import json
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

from execution.collectors.ado_rest_client import AzureDevOpsRESTClient, get_ado_rest_client
from execution.core import get_logger
from execution.core.collector_metrics import track_collector_performance
from execution.utils.error_handling import log_and_raise


class BaseCollector(ABC):
    """Base class for all ADO collectors with shared infrastructure

    Eliminates ~70 lines of boilerplate per collector by centralizing:
    - Windows console encoding setup
    - Discovery data loading with error handling
    - ADO REST client initialization
    - Concurrent collection orchestration
    - Performance tracking integration

    Subclasses must implement:
    - collect(): Collection logic for a single project
    - save_metrics(): Persistence logic for collected metrics
    """

    def __init__(self, name: str, lookback_days: int = 90):
        """Initialize collector with common configuration

        Args:
            name: Collector name (e.g., "ownership", "quality")
            lookback_days: How many days of history to collect
        """
        self.name = name
        self.config = {"lookback_days": lookback_days}
        self.logger = get_logger(name)
        self.setup_platform()

    @staticmethod
    def setup_platform() -> None:
        """Configure Windows UTF-8 encoding for console output

        Windows console defaults to cp1252 encoding which causes issues
        with special characters in ADO data (user names, descriptions).
        This sets UTF-8 encoding for both stdout and stderr.
        """
        if sys.platform == "win32":
            import codecs

            sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
            sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    def load_discovery_data(self, path: str = ".tmp/observatory/ado_structure.json") -> dict[str, Any]:
        """Load ADO project structure from discovery file

        Args:
            path: Path to discovery JSON file

        Returns:
            Dictionary with "projects" key containing list of project names

        Raises:
            SystemExit: If file not found or invalid JSON
        """
        try:
            with open(path, encoding="utf-8") as f:
                discovery_data: dict[str, Any] = json.load(f)
            projects = discovery_data.get("projects", [])
            self.logger.info(f"Loaded {len(projects)} projects from discovery")
            return discovery_data
        except FileNotFoundError as e:
            log_and_raise(
                self.logger,
                e,
                context={
                    "file_path": path,
                    "hint": "Run: python execution/discover_projects.py",
                },
                error_type="Project discovery file not found",
            )
            sys.exit(1)
        except json.JSONDecodeError as e:
            log_and_raise(
                self.logger,
                e,
                context={"file_path": path},
                error_type="Invalid JSON in discovery file",
            )
            sys.exit(1)

    def get_rest_client(self) -> AzureDevOpsRESTClient:
        """Get configured ADO REST client

        Returns:
            Initialized AzureDevOpsRESTClient instance

        Raises:
            SystemExit: If client initialization fails
        """
        self.logger.info("Connecting to Azure DevOps REST API...")
        try:
            rest_client = get_ado_rest_client()
            self.logger.info("[SUCCESS] Connected to ADO REST API")
            return rest_client
        except ValueError as e:
            log_and_raise(
                self.logger,
                e,
                context={"operation": "ADO REST client initialization"},
                error_type="ADO REST client failed",
            )
            sys.exit(1)

    async def run_concurrent_collection(self, projects: list[str], collect_fn: Callable, *args) -> list[Any]:
        """Run collection tasks concurrently for all projects

        Args:
            projects: List of project names to collect from
            collect_fn: Async function to call for each project
            *args: Additional arguments to pass to collect_fn

        Returns:
            List of results (or exceptions) from collection tasks
        """
        self.logger.info(f"Collecting {self.name} metrics (concurrent execution)...")
        self.logger.info("=" * 60)

        tasks = [collect_fn(project, *args) for project in projects]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log summary
        success_count = len([r for r in results if not isinstance(r, Exception)])
        error_count = len(results) - success_count
        self.logger.info(f"\nCollection complete: {success_count} succeeded, {error_count} failed")

        return results

    @abstractmethod
    async def collect(self, project: str, rest_client: AzureDevOpsRESTClient) -> Any:
        """Collect metrics for a single project

        Args:
            project: Project name to collect from
            rest_client: ADO REST client instance

        Returns:
            Collected metrics (domain model instance)

        Note:
            This method should handle project-level errors gracefully
            and return partial results or None if collection fails.
        """
        pass

    @abstractmethod
    def save_metrics(self, results: list[Any]) -> bool:
        """Save collected metrics to storage

        Args:
            results: List of metric results from collect()

        Returns:
            True if save succeeded, False otherwise

        Note:
            This method should filter out exceptions from results
            and save only successful metric collections.
        """
        pass

    async def run(self) -> bool:
        """Main execution flow with performance tracking

        Orchestrates the complete collection workflow:
        1. Load discovery data
        2. Initialize REST client
        3. Collect metrics concurrently
        4. Save metrics
        5. Track performance

        Returns:
            True if collection and save succeeded, False otherwise
        """
        with track_collector_performance(self.name) as tracker:
            self.logger.info(f"Director Observatory - {self.name.title()} Metrics Collector (REST API)")
            self.logger.info("=" * 60)

            # Load projects
            discovery_data = self.load_discovery_data()
            projects = discovery_data.get("projects", [])
            tracker.project_count = len(projects)

            if not projects:
                self.logger.warning("No projects found in discovery data")
                return False

            # Get REST client
            rest_client = self.get_rest_client()

            # Collect metrics
            results = await self.run_concurrent_collection(projects, self.collect, rest_client)

            # Save results
            save_success = self.save_metrics(results)

            # Update tracker
            tracker.success = save_success

            if save_success:
                self.logger.info(f"\n[SUCCESS] {self.name.title()} metrics collection complete")
            else:
                self.logger.error(f"\n[FAILED] {self.name.title()} metrics collection failed")

            return save_success
