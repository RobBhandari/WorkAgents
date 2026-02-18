"""
Base Agent Class

Autonomous agent with skill integration, retry logic, and error handling.
All collector agents inherit from this base class.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from execution.core.collector_metrics import track_collector_performance

logger = structlog.get_logger(__name__)


class BaseAgent(ABC):
    """
    Base class for all autonomous collector agents.

    Provides common functionality:
    - Skill integration (MCP)
    - Retry logic with exponential backoff
    - Error handling and logging
    - Performance tracking
    - Discovery data loading
    """

    def __init__(self, name: str, config: dict | None = None):
        """
        Initialize base agent.

        Args:
            name: Agent name (e.g., "quality", "security")
            config: Optional configuration dict
        """
        self.name = name
        self.config = config or {}
        self.skills: dict[str, Any] = {}  # Will be populated by subclasses

    @abstractmethod
    async def collect(self, project: dict) -> dict:
        """
        Collect metrics for a single project.

        Subclasses must implement this method with their specific collection logic.

        Args:
            project: Project metadata from discovery

        Returns:
            Dictionary with collected metrics

        Raises:
            Exception: If collection fails
        """
        pass

    async def run(self) -> bool:
        """
        Execute agent collection with error handling and retry logic.

        Returns:
            True if collection succeeded, False otherwise
        """
        with track_collector_performance(self.name) as tracker:
            logger.info("agent_started", agent=self.name)

            try:
                # Load discovery data
                discovery_data = self.load_discovery_data()
                projects = discovery_data.get("projects", [])
                tracker.project_count = len(projects)

                if not projects:
                    logger.warning("no_projects_found", agent=self.name)
                    return False

                logger.info("projects_discovered", count=len(projects))

                # Collect metrics for all projects concurrently
                tasks = [self.collect_with_retry(project) for project in projects]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                project_metrics: list[dict] = []
                for project, result in zip(projects, results, strict=True):
                    if isinstance(result, Exception):
                        logger.error(
                            "collection_failed",
                            project=project["project_name"],
                            error=str(result),
                            exc_info=True,
                        )
                        tracker.errors += 1
                    else:
                        project_metrics.append(result)

                # Save metrics
                success = self.save_metrics(project_metrics)
                tracker.success = success

                logger.info(
                    "agent_completed",
                    agent=self.name,
                    projects_collected=len(project_metrics),
                    projects_failed=len(projects) - len(project_metrics),
                )

                return success

            except Exception as e:
                logger.error("agent_failed", agent=self.name, error=str(e), exc_info=True)
                return False

    async def collect_with_retry(self, project: dict, max_retries: int = 3, backoff_factor: int = 2) -> dict:
        """
        Collect metrics with retry logic.

        Args:
            project: Project metadata
            max_retries: Maximum number of retry attempts
            backoff_factor: Exponential backoff multiplier

        Returns:
            Collected metrics dictionary

        Raises:
            Exception: If all retries exhausted
        """
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                logger.info(
                    "collection_attempt",
                    project=project["project_name"],
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )

                result = await self.collect(project)

                # Validate result
                if not result:
                    raise ValueError("Empty result from collection")

                logger.info(
                    "collection_success",
                    project=project["project_name"],
                    attempt=attempt + 1,
                )

                return result

            except Exception as e:
                last_error = e
                logger.warning(
                    "collection_retry",
                    project=project["project_name"],
                    attempt=attempt + 1,
                    error=str(e),
                )

                if attempt < max_retries - 1:
                    # Exponential backoff
                    sleep_time = backoff_factor**attempt
                    logger.info("backoff_sleep", seconds=sleep_time)
                    await asyncio.sleep(sleep_time)

        # All retries exhausted
        logger.error(
            "collection_failed_all_retries",
            project=project["project_name"],
            error=str(last_error),
        )
        raise last_error  # type: ignore

    def load_discovery_data(self) -> dict:
        """
        Load project discovery data.

        Returns:
            Discovery data dictionary with projects list

        Raises:
            FileNotFoundError: If discovery file doesn't exist
            ValueError: If discovery data is invalid
        """
        discovery_path = Path(".tmp/observatory/ado_structure.json")

        if not discovery_path.exists():
            raise FileNotFoundError(
                f"Discovery file not found: {discovery_path}. "
                "Run project discovery first: python -m execution.collectors.ado_discover_projects"
            )

        import json

        try:
            data = json.loads(discovery_path.read_text())

            if not isinstance(data, dict) or "projects" not in data:
                raise ValueError("Invalid discovery data structure")

            return data

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in discovery file: {e}") from e

    @abstractmethod
    def save_metrics(self, metrics: list[dict]) -> bool:
        """
        Save collected metrics to history file.

        Subclasses must implement this method with their specific save logic.

        Args:
            metrics: List of project metrics dictionaries

        Returns:
            True if saved successfully, False otherwise
        """
        pass

    def get_ado_organization(self) -> str:
        """
        Get ADO organization name from environment.

        Returns:
            Organization name (e.g., "contoso")

        Raises:
            ValueError: If ADO_ORGANIZATION_URL not set
        """
        import os

        org_url = os.getenv("ADO_ORGANIZATION_URL")
        if not org_url:
            raise ValueError("ADO_ORGANIZATION_URL environment variable not set")

        # Extract organization name from URL
        # https://dev.azure.com/contoso -> contoso
        parts = org_url.rstrip("/").split("/")
        return parts[-1]
