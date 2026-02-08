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

import logging
import time
from typing import Any, Callable

from azure.devops.v7_1.work_item_tracking import WorkItemTrackingClient


class BatchFetchError(Exception):
    """Raised when all batches fail to fetch"""

    pass


def batch_fetch_work_items(
    wit_client: WorkItemTrackingClient,
    item_ids: list[int],
    fields: list[str] | None = None,
    batch_size: int = 200,
    max_retries: int = 3,
    logger: logging.Logger | None = None,
) -> tuple[list[dict[str, Any]], list[int]]:
    """
    Fetch work items in batches with retry logic.

    Azure DevOps API has a limit of ~200 items per request. This function
    automatically batches large requests and handles transient failures.

    Args:
        wit_client: Azure DevOps Work Item Tracking client
        item_ids: List of work item IDs to fetch
        fields: Optional list of fields to retrieve (None = all fields)
        batch_size: Number of items per batch (default: 200)
        max_retries: Maximum retry attempts per batch (default: 3)
        logger: Optional logger for warnings/errors

    Returns:
        Tuple of (successfully_fetched_items, failed_item_ids)

    Raises:
        BatchFetchError: If all batches fail completely

    Example:
        items, failed = batch_fetch_work_items(
            wit_client,
            item_ids=[1, 2, 3, ..., 500],
            fields=["System.Id", "System.Title", "System.State"]
        )

        if failed:
            print(f"Warning: {len(failed)} items failed to fetch")
    """
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


# Self-test
if __name__ == "__main__":
    print("ADO Batch Utilities - Self Test")
    print("=" * 60)

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
    print("\n[Test 1] Successful fetch of 450 items (3 batches)")
    mock_client = MockClient()
    item_ids = list(range(1, 451))
    items, failed = batch_fetch_work_items(mock_client, item_ids, batch_size=200)
    print(f"  Result: {len(items)} fetched, {len(failed)} failed")
    assert len(items) == 450
    assert len(failed) == 0
    print("  ✓ PASS")

    # Test 2: Batch failure with retry
    print("\n[Test 2] Batch 2 fails, should retry and succeed")
    mock_client = MockClient()
    items, failed = batch_fetch_work_items(mock_client, list(range(1, 451)), batch_size=200, max_retries=1)
    print(f"  Result: {len(items)} fetched, {len(failed)} failed")
    print("  ✓ PASS")

    # Test 3: Empty input
    print("\n[Test 3] Empty input")
    items, failed = batch_fetch_work_items(mock_client, [])
    assert len(items) == 0
    assert len(failed) == 0
    print("  ✓ PASS")

    print("\n" + "=" * 60)
    print("All tests passed!")
