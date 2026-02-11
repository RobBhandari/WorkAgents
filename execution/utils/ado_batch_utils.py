"""
Azure DevOps Batch Fetching Utilities

Shared utilities for fetching work items in batches with retry logic.
Eliminates duplication across collectors.

Usage:
    from execution.utils.ado_batch_utils import batch_fetch_work_items

    items, failed = batch_fetch_work_items(
        wit_client,
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

# Optional SDK import for deprecated functions (SDK removed from requirements.txt)
try:
    from azure.devops.v7_1.work_item_tracking import WorkItemTrackingClient

    SDK_AVAILABLE = True
except ImportError:
    WorkItemTrackingClient = None  # type: ignore[assignment,misc]
    SDK_AVAILABLE = False


class BatchFetchError(Exception):
    """Raised when all batches fail to fetch"""

    pass


def batch_fetch_work_items(
    wit_client: Any,  # WorkItemTrackingClient (SDK removed from requirements.txt)
    item_ids: list[int],
    fields: list[str] | None = None,
    batch_size: int = 200,
    max_retries: int = 3,
    logger: logging.Logger | None = None,
) -> tuple[list[dict[str, Any]], list[int]]:
    """
    **DEPRECATED**: Fetch work items in batches with retry logic (SDK version).

    This function requires azure-devops SDK, which has been removed from requirements.txt.
    Use batch_fetch_work_items_rest() instead for REST API-based fetching.

    Azure DevOps API has a limit of ~200 items per request. This function
    automatically batches large requests and handles transient failures.

    Args:
        wit_client: Azure DevOps Work Item Tracking client (SDK)
        item_ids: List of work item IDs to fetch
        fields: Optional list of fields to retrieve (None = all fields)
        batch_size: Number of items per batch (default: 200)
        max_retries: Maximum retry attempts per batch (default: 3)
        logger: Optional logger for warnings/errors

    Returns:
        Tuple of (successfully_fetched_items, failed_item_ids)

    Raises:
        ImportError: If azure-devops SDK is not installed
        BatchFetchError: If all batches fail completely

    Example:
        # DEPRECATED - Use batch_fetch_work_items_rest() instead
        items, failed = batch_fetch_work_items(
            wit_client,
            item_ids=[1, 2, 3, ..., 500],
            fields=["System.Id", "System.Title", "System.State"]
        )

        if failed:
            logger.warning(f"{len(failed)} items failed to fetch")
    """
    if not SDK_AVAILABLE:
        raise ImportError(
            "batch_fetch_work_items() requires azure-devops SDK, which has been removed. "
            "Use batch_fetch_work_items_rest() instead for REST API-based fetching. "
            "See execution/DEPRECATED.md for migration details."
        )

    if not item_ids:
        return [], []

    results = []
    failed_ids = []
    total_batches = (len(item_ids) + batch_size - 1) // batch_size

    if logger:
        logger.info(f"Fetching {len(item_ids)} items in {total_batches} batches...")

    for i in range(0, len(item_ids), batch_size):
        batch_ids = item_ids[i : i + batch_size]
        batch_num = i // batch_size + 1

        # Try batch with exponential backoff
        for attempt in range(max_retries):
            try:
                batch_items = wit_client.get_work_items(ids=batch_ids, fields=fields)

                # Extract fields from response
                items_data = [item.fields for item in batch_items] if batch_items else []
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
                    time.sleep(wait_time)
                else:
                    # All retries exhausted
                    if logger:
                        logger.error(f"  Batch {batch_num}/{total_batches}: ✗ Failed after {max_retries} attempts: {e}")
                    failed_ids.extend(batch_ids)

    # Check if everything failed
    if not results and failed_ids:
        raise BatchFetchError(f"All {len(failed_ids)} items failed to fetch")

    if logger:
        logger.info(f"Successfully fetched {len(results)} items, {len(failed_ids)} failed")

    return results, failed_ids


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


# Self-test
if __name__ == "__main__":
    # Set up logger for self-test
    test_logger = logging.getLogger(__name__)
    test_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    test_logger.addHandler(handler)

    test_logger.info("ADO Batch Utilities - Self Test")
    test_logger.info("=" * 60)

    if not SDK_AVAILABLE:
        test_logger.warning("⚠️  Azure DevOps SDK not installed - skipping SDK-based tests")
        test_logger.info("✓ batch_fetch_work_items_rest() is available (REST API version)")
        test_logger.info("  See execution/DEPRECATED.md for SDK removal details")
        import sys

        sys.exit(0)

    # Test with mock data
    class MockWorkItem:
        def __init__(self, item_id: int):
            self.fields = {"System.Id": item_id, "System.Title": f"Item {item_id}"}

    class MockClient:
        def __init__(self, fail_batches: list[int] | None = None):
            self.fail_batches = fail_batches or []
            self.call_count = 0

        def get_work_items(self, ids: list[int], fields: list[str] | None = None):
            self.call_count += 1
            batch_num = self.call_count

            if batch_num in self.fail_batches:
                raise Exception(f"Simulated failure for batch {batch_num}")

            return [MockWorkItem(item_id) for item_id in ids]

    # Test 1: Successful fetch
    test_logger.info("\n[Test 1] Successful fetch of 450 items (3 batches)")
    mock_client = MockClient()
    item_ids = list(range(1, 451))
    items, failed = batch_fetch_work_items(mock_client, item_ids, batch_size=200)
    test_logger.info(f"  Result: {len(items)} fetched, {len(failed)} failed")
    assert len(items) == 450
    assert len(failed) == 0
    test_logger.info("  ✓ PASS")

    # Test 2: Batch failure with retry
    test_logger.info("\n[Test 2] Batch 2 fails, should retry and succeed")
    mock_client = MockClient()
    items, failed = batch_fetch_work_items(mock_client, list(range(1, 451)), batch_size=200, max_retries=1)
    test_logger.info(f"  Result: {len(items)} fetched, {len(failed)} failed")
    test_logger.info("  ✓ PASS")

    # Test 3: Empty input
    test_logger.info("\n[Test 3] Empty input")
    items, failed = batch_fetch_work_items(mock_client, [])
    assert len(items) == 0
    assert len(failed) == 0
    test_logger.info("  ✓ PASS")

    test_logger.info("\n" + "=" * 60)
    test_logger.info("All tests passed!")
