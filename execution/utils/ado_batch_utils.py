"""
Azure DevOps Batch Fetching Utilities

Shared utilities for fetching work items in batches with retry logic.
Eliminates duplication across collectors.

Usage:
    from execution.utils.ado_batch_utils import batch_fetch_work_items_rest

    items, failed = await batch_fetch_work_items_rest(
        rest_client,
        item_ids=[1, 2, 3, ...],
        fields=["System.Id", "System.Title"],
        logger=logger
    )
"""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any


class BatchFetchError(Exception):
    """Raised when all batches fail to fetch"""

    pass


def batch_fetch_with_callback(
    items: list[Any],
    fetch_fn: Callable[[list[Any]], list[Any]],
    batch_size: int = 200,
    max_retries: int = 3,
    logger: logging.Logger | None = None,
) -> tuple[list[Any], list[Any]]:
    """
    Generic batch fetcher with custom fetch function.

    NOTE: This function is still supported, but prefer async patterns with asyncio.gather()
    for better performance in REST API-based collectors.

    Useful for non-work-item batching (e.g., commits, PRs).

    Args:
        items: List of items to process
        fetch_fn: Function that takes a batch and returns results
        batch_size: Items per batch
        max_retries: Retry attempts
        logger: Optional logger

    Returns:
        Tuple of (successful_results, failed_items)

    Example:
        def fetch_commits(commit_ids):
            return git_client.get_commits(commit_ids)

        results, failed = batch_fetch_with_callback(
            commit_ids,
            fetch_commits,
            batch_size=50
        )
    """
    if not items:
        return [], []

    results = []
    failed_items = []
    total_batches = (len(items) + batch_size - 1) // batch_size

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        batch_num = i // batch_size + 1

        for attempt in range(max_retries):
            try:
                batch_results = fetch_fn(batch)
                results.extend(batch_results)

                if logger:
                    logger.debug(f"  Batch {batch_num}/{total_batches}: ✓ {len(batch_results)} items")
                break

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    if logger:
                        logger.warning(
                            f"  Batch {batch_num}/{total_batches} attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {wait_time}s..."
                        )
                    time.sleep(wait_time)
                else:
                    if logger:
                        logger.error(f"  Batch {batch_num}/{total_batches}: ✗ Failed after {max_retries} attempts")
                    failed_items.extend(batch)

    return results, failed_items


async def batch_fetch_work_items_rest(
    rest_client: Any,  # AzureDevOpsRESTClient
    item_ids: list[int],
    fields: list[str] | None = None,
    batch_size: int = 200,
    max_retries: int = 3,
    logger: logging.Logger | None = None,
) -> tuple[list[dict[str, Any]], list[int]]:
    """
    Fetch work items in batches using REST API with retry logic.

    Async version for Azure DevOps REST API client. Replaces SDK-based batch_fetch_work_items()
    during SDK → REST migration.

    Args:
        rest_client: Azure DevOps REST API client (AzureDevOpsRESTClient)
        item_ids: List of work item IDs to fetch
        fields: Optional list of fields to retrieve (None = all fields)
        batch_size: Number of items per batch (default: 200, Azure DevOps API limit)
        max_retries: Maximum retry attempts per batch (default: 3)
        logger: Optional logger for warnings/errors

    Returns:
        Tuple of (successfully_fetched_items, failed_item_ids)

    Raises:
        BatchFetchError: If all batches fail completely

    Example:
        from execution.collectors.ado_rest_client import get_ado_rest_client
        from execution.collectors.ado_rest_transformers import WorkItemTransformer

        client = get_ado_rest_client()
        items, failed = await batch_fetch_work_items_rest(
            client,
            item_ids=[1, 2, 3, ..., 500],
            fields=["System.Id", "System.Title", "System.State"]
        )

        # Transform REST response to SDK format
        transformed = WorkItemTransformer.transform_work_items_response({"value": items})
    """
    if not item_ids:
        return [], []

    results = []
    failed_ids = []
    total_batches = (len(item_ids) + batch_size - 1) // batch_size

    if logger:
        logger.info(f"Fetching {len(item_ids)} items in {total_batches} batches (REST API)...")

    for i in range(0, len(item_ids), batch_size):
        batch_ids = item_ids[i : i + batch_size]
        batch_num = i // batch_size + 1

        # Try batch with exponential backoff
        for attempt in range(max_retries):
            try:
                # REST API call
                response = await rest_client.get_work_items(ids=batch_ids, fields=fields)

                # Extract items from REST response
                items_data = response.get("value", [])
                results.extend(items_data)

                if logger:
                    logger.debug(f"  Batch {batch_num}/{total_batches}: ✓ {len(items_data)} items")
                break  # Success - exit retry loop

            except Exception as e:
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2**attempt
                    if logger:
                        logger.warning(
                            f"  Batch {batch_num}/{total_batches} attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {wait_time}s..."
                        )
                    await asyncio.sleep(wait_time)  # Async sleep
                else:
                    # All retries exhausted
                    if logger:
                        logger.error(f"  Batch {batch_num}/{total_batches}: ✗ Failed after {max_retries} attempts: {e}")
                    failed_ids.extend(batch_ids)

    # Check if everything failed
    if not results and failed_ids:
        raise BatchFetchError(f"All {len(failed_ids)} items failed to fetch")

    if logger:
        logger.info(f"Successfully fetched {len(results)} items (REST), {len(failed_ids)} failed")

    return results, failed_ids
