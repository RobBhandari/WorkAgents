#!/usr/bin/env python3
"""
Tests for ado_batch_utils module

Tests batch fetching utilities for Azure DevOps work items with retry logic,
pagination, error handling, and exponential backoff.

Run with:
    pytest tests/utils/test_ado_batch_utils.py -v
    pytest tests/utils/test_ado_batch_utils.py -v --cov=execution.utils.ado_batch_utils
"""

import logging
import time
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from execution.utils.ado_batch_utils import (
    BatchFetchError,
    batch_fetch_with_callback,
    batch_fetch_work_items,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_logger():
    """Fixture for a mock logger."""
    return Mock(spec=logging.Logger)


@pytest.fixture
def mock_work_item():
    """Fixture for creating mock work items."""

    def _create_work_item(item_id: int, title: str | None = None) -> Mock:
        work_item = Mock()
        work_item.fields = {
            "System.Id": item_id,
            "System.Title": title or f"Item {item_id}",
            "System.State": "Active",
        }
        return work_item

    return _create_work_item


@pytest.fixture
def mock_wit_client(mock_work_item):
    """Fixture for a mock WorkItemTrackingClient."""
    client = Mock()

    def get_work_items_side_effect(ids: list[int], fields: list[str] | None = None):
        return [mock_work_item(item_id) for item_id in ids]

    client.get_work_items = Mock(side_effect=get_work_items_side_effect)
    return client


# ============================================================================
# Tests for batch_fetch_work_items - Basic Success Cases
# ============================================================================


class TestBatchFetchWorkItemsSuccess:
    """Tests for successful batch fetching scenarios."""

    def test_empty_input(self, mock_wit_client, mock_logger):
        """Test that empty input returns empty results."""
        items, failed = batch_fetch_work_items(mock_wit_client, [], logger=mock_logger)

        assert items == []
        assert failed == []
        mock_wit_client.get_work_items.assert_not_called()

    def test_single_item(self, mock_wit_client, mock_work_item, mock_logger):
        """Test fetching a single work item."""
        items, failed = batch_fetch_work_items(mock_wit_client, [123], logger=mock_logger)

        assert len(items) == 1
        assert len(failed) == 0
        assert items[0]["System.Id"] == 123
        mock_wit_client.get_work_items.assert_called_once()

    def test_single_batch_under_limit(self, mock_wit_client, mock_logger):
        """Test fetching work items within a single batch (< 200 items)."""
        item_ids = list(range(1, 151))  # 150 items

        items, failed = batch_fetch_work_items(mock_wit_client, item_ids, batch_size=200, logger=mock_logger)

        assert len(items) == 150
        assert len(failed) == 0
        mock_wit_client.get_work_items.assert_called_once_with(ids=item_ids, fields=None)

    def test_multiple_batches(self, mock_wit_client, mock_logger):
        """Test fetching work items across multiple batches."""
        item_ids = list(range(1, 451))  # 450 items = 3 batches of 200

        items, failed = batch_fetch_work_items(mock_wit_client, item_ids, batch_size=200, logger=mock_logger)

        assert len(items) == 450
        assert len(failed) == 0
        assert mock_wit_client.get_work_items.call_count == 3

    def test_exact_batch_boundary(self, mock_wit_client, mock_logger):
        """Test fetching exactly batch_size items (edge case)."""
        item_ids = list(range(1, 201))  # Exactly 200 items

        items, failed = batch_fetch_work_items(mock_wit_client, item_ids, batch_size=200, logger=mock_logger)

        assert len(items) == 200
        assert len(failed) == 0
        mock_wit_client.get_work_items.assert_called_once()

    def test_custom_batch_size(self, mock_wit_client, mock_logger):
        """Test using custom batch size."""
        item_ids = list(range(1, 251))  # 250 items

        items, failed = batch_fetch_work_items(mock_wit_client, item_ids, batch_size=100, logger=mock_logger)

        assert len(items) == 250
        assert len(failed) == 0
        assert mock_wit_client.get_work_items.call_count == 3  # 100, 100, 50

    def test_with_specific_fields(self, mock_wit_client, mock_logger):
        """Test fetching with specific fields filter."""
        item_ids = [1, 2, 3]
        fields = ["System.Id", "System.Title", "System.State"]

        items, failed = batch_fetch_work_items(mock_wit_client, item_ids, fields=fields, logger=mock_logger)

        assert len(items) == 3
        assert len(failed) == 0
        mock_wit_client.get_work_items.assert_called_once_with(ids=item_ids, fields=fields)

    def test_without_logger(self, mock_wit_client):
        """Test that function works without logger (no crash)."""
        item_ids = [1, 2, 3]

        items, failed = batch_fetch_work_items(mock_wit_client, item_ids, logger=None)

        assert len(items) == 3
        assert len(failed) == 0


# ============================================================================
# Tests for batch_fetch_work_items - Retry and Error Handling
# ============================================================================


class TestBatchFetchWorkItemsRetry:
    """Tests for retry logic and error handling."""

    def test_transient_failure_with_retry_success(self, mock_wit_client, mock_work_item, mock_logger):
        """Test that transient failures are retried successfully."""
        call_count = 0

        def side_effect_with_transient_failure(ids: list[int], fields: list[str] | None = None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Transient network error")
            return [mock_work_item(item_id) for item_id in ids]

        mock_wit_client.get_work_items = Mock(side_effect=side_effect_with_transient_failure)

        items, failed = batch_fetch_work_items(mock_wit_client, [1, 2, 3], max_retries=3, logger=mock_logger)

        assert len(items) == 3
        assert len(failed) == 0
        assert call_count == 2  # Failed once, succeeded on retry

    def test_all_retries_exhausted(self, mock_wit_client, mock_logger):
        """Test that batch fails after all retries are exhausted and raises exception."""
        mock_wit_client.get_work_items = Mock(side_effect=Exception("Persistent failure"))

        # Expect BatchFetchError when all items fail
        with pytest.raises(BatchFetchError, match="All 3 items failed to fetch"):
            batch_fetch_work_items(mock_wit_client, [1, 2, 3], max_retries=3, logger=mock_logger)

        assert mock_wit_client.get_work_items.call_count == 3  # 3 retry attempts

    def test_partial_batch_failure(self, mock_wit_client, mock_work_item, mock_logger):
        """Test that some batches succeed while others fail."""
        call_count = 0

        def side_effect_partial_failure(ids: list[int], fields: list[str] | None = None):
            nonlocal call_count
            call_count += 1
            # Fail batch 2 (items 101-200), succeed others
            if 101 in ids:
                raise Exception("Batch 2 failure")
            return [mock_work_item(item_id) for item_id in ids]

        mock_wit_client.get_work_items = Mock(side_effect=side_effect_partial_failure)

        items, failed = batch_fetch_work_items(
            mock_wit_client, list(range(1, 301)), batch_size=100, max_retries=2, logger=mock_logger
        )

        # Batch 1 (1-100) succeeds, Batch 2 (101-200) fails, Batch 3 (201-300) succeeds
        assert len(items) == 200  # 100 + 100
        assert len(failed) == 100  # Batch 2 items

    @patch("execution.utils.ado_batch_utils.time.sleep")
    def test_exponential_backoff(self, mock_sleep, mock_wit_client, mock_logger):
        """Test that exponential backoff is applied between retries."""
        mock_wit_client.get_work_items = Mock(side_effect=Exception("Persistent failure"))

        # Expect BatchFetchError when all items fail
        with pytest.raises(BatchFetchError):
            batch_fetch_work_items(mock_wit_client, [1, 2, 3], max_retries=3, logger=mock_logger)

        # Verify exponential backoff: 2^0=1s, 2^1=2s
        assert mock_sleep.call_count == 2  # Sleep after 1st and 2nd failures (not after 3rd)
        mock_sleep.assert_any_call(1)  # First retry: wait 1 second
        mock_sleep.assert_any_call(2)  # Second retry: wait 2 seconds

    def test_all_batches_fail_raises_exception(self, mock_wit_client, mock_logger):
        """Test that BatchFetchError is raised when all batches fail."""
        mock_wit_client.get_work_items = Mock(side_effect=Exception("Complete failure"))

        with pytest.raises(BatchFetchError, match="All 3 items failed to fetch"):
            batch_fetch_work_items(mock_wit_client, [1, 2, 3], max_retries=2, logger=mock_logger)

    def test_partial_success_does_not_raise(self, mock_wit_client, mock_work_item, mock_logger):
        """Test that partial success does not raise exception."""

        def side_effect_partial_success(ids: list[int], fields: list[str] | None = None):
            # Fail batch 2 (items 101-200) on all retry attempts
            if 101 in ids:
                raise Exception("Batch 2 failure")
            return [mock_work_item(item_id) for item_id in ids]

        mock_wit_client.get_work_items = Mock(side_effect=side_effect_partial_success)

        # Should not raise exception - partial success is acceptable
        items, failed = batch_fetch_work_items(
            mock_wit_client, list(range(1, 301)), batch_size=100, max_retries=2, logger=mock_logger
        )

        assert len(items) == 200  # Batches 1 and 3 succeeded (100 items each)
        assert len(failed) == 100  # Batch 2 failed (100 items)


# ============================================================================
# Tests for batch_fetch_work_items - Edge Cases
# ============================================================================


class TestBatchFetchWorkItemsEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_response_from_api(self, mock_wit_client, mock_logger):
        """Test handling of empty response from API (None)."""
        mock_wit_client.get_work_items = Mock(return_value=None)

        items, failed = batch_fetch_work_items(mock_wit_client, [1, 2, 3], logger=mock_logger)

        assert items == []
        assert failed == []

    def test_batch_size_of_one(self, mock_wit_client, mock_logger):
        """Test extreme batch size of 1 item per batch."""
        items, failed = batch_fetch_work_items(mock_wit_client, [1, 2, 3], batch_size=1, logger=mock_logger)

        assert len(items) == 3
        assert len(failed) == 0
        assert mock_wit_client.get_work_items.call_count == 3

    def test_very_large_batch_size(self, mock_wit_client, mock_logger):
        """Test very large batch size (larger than item count)."""
        item_ids = list(range(1, 51))

        items, failed = batch_fetch_work_items(mock_wit_client, item_ids, batch_size=10000, logger=mock_logger)

        assert len(items) == 50
        assert len(failed) == 0
        mock_wit_client.get_work_items.assert_called_once()

    def test_max_retries_zero(self, mock_wit_client, mock_logger):
        """Test with max_retries=1 (fail immediately, no retries)."""
        mock_wit_client.get_work_items = Mock(side_effect=Exception("Immediate failure"))

        # Expect BatchFetchError when all items fail
        with pytest.raises(BatchFetchError, match="All 3 items failed to fetch"):
            batch_fetch_work_items(mock_wit_client, [1, 2, 3], max_retries=1, logger=mock_logger)

        mock_wit_client.get_work_items.assert_called_once()  # No retries

    def test_single_item_per_batch_with_failures(self, mock_wit_client, mock_work_item, mock_logger):
        """Test batch size of 1 with some items failing."""
        call_count = 0

        def side_effect_selective_failure(ids: list[int], fields: list[str] | None = None):
            nonlocal call_count
            call_count += 1
            # Fail item 2
            if 2 in ids:
                raise Exception("Item 2 failure")
            return [mock_work_item(item_id) for item_id in ids]

        mock_wit_client.get_work_items = Mock(side_effect=side_effect_selective_failure)

        items, failed = batch_fetch_work_items(
            mock_wit_client, [1, 2, 3], batch_size=1, max_retries=2, logger=mock_logger
        )

        assert len(items) == 2  # Items 1 and 3 succeed
        assert len(failed) == 1  # Item 2 fails
        assert failed == [2]


# ============================================================================
# Tests for batch_fetch_with_callback - Generic Batch Fetcher
# ============================================================================


class TestBatchFetchWithCallback:
    """Tests for generic batch fetcher with custom callback."""

    def test_empty_input(self, mock_logger):
        """Test that empty input returns empty results."""

        def fetch_fn(items: list[Any]) -> list[Any]:
            return items

        results, failed = batch_fetch_with_callback([], fetch_fn, logger=mock_logger)

        assert results == []
        assert failed == []

    def test_single_batch_success(self, mock_logger):
        """Test successful single batch with callback."""

        def fetch_fn(items: list[int]) -> list[str]:
            return [f"Result {item}" for item in items]

        results, failed = batch_fetch_with_callback([1, 2, 3], fetch_fn, logger=mock_logger)

        assert len(results) == 3
        assert results == ["Result 1", "Result 2", "Result 3"]
        assert len(failed) == 0

    def test_multiple_batches_with_callback(self, mock_logger):
        """Test multiple batches with custom callback."""

        def fetch_fn(items: list[int]) -> list[int]:
            return [item * 2 for item in items]

        items = list(range(1, 251))  # 250 items
        results, failed = batch_fetch_with_callback(items, fetch_fn, batch_size=100, logger=mock_logger)

        assert len(results) == 250
        assert results[0] == 2  # First item doubled
        assert results[-1] == 500  # Last item doubled
        assert len(failed) == 0

    def test_callback_failure_with_retry(self, mock_logger):
        """Test callback failure with successful retry."""
        call_count = 0

        def fetch_fn_with_transient_failure(items: list[int]) -> list[int]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Transient callback failure")
            return items

        results, failed = batch_fetch_with_callback(
            [1, 2, 3], fetch_fn_with_transient_failure, max_retries=3, logger=mock_logger
        )

        assert len(results) == 3
        assert len(failed) == 0
        assert call_count == 2  # Failed once, succeeded on retry

    def test_callback_all_retries_exhausted(self, mock_logger):
        """Test callback failure after all retries."""

        def failing_fetch_fn(items: list[Any]) -> list[Any]:
            raise Exception("Persistent callback failure")

        results, failed = batch_fetch_with_callback([1, 2, 3], failing_fetch_fn, max_retries=2, logger=mock_logger)

        assert len(results) == 0
        assert len(failed) == 3
        assert failed == [1, 2, 3]

    def test_callback_partial_batch_failure(self, mock_logger):
        """Test that some batches succeed while others fail in callback."""

        def fetch_fn_partial_failure(items: list[int]) -> list[int]:
            # Determine which batch this is based on first item
            # Batch 1: 1-100, Batch 2: 101-200, Batch 3: 201-300
            if items[0] >= 101 and items[0] <= 200:
                # Fail batch 2 on all retry attempts
                raise Exception("Batch 2 failure")
            return items

        results, failed = batch_fetch_with_callback(
            list(range(1, 301)), fetch_fn_partial_failure, batch_size=100, max_retries=2, logger=mock_logger
        )

        assert len(results) == 200  # Batches 1 and 3 succeed
        assert len(failed) == 100  # Batch 2 fails

    @patch("execution.utils.ado_batch_utils.time.sleep")
    def test_callback_exponential_backoff(self, mock_sleep, mock_logger):
        """Test exponential backoff in callback retry."""

        def failing_fetch_fn(items: list[Any]) -> list[Any]:
            raise Exception("Callback failure")

        results, failed = batch_fetch_with_callback([1, 2, 3], failing_fetch_fn, max_retries=3, logger=mock_logger)

        assert mock_sleep.call_count == 2  # Sleep after 1st and 2nd failures
        mock_sleep.assert_any_call(1)  # First retry: 1 second
        mock_sleep.assert_any_call(2)  # Second retry: 2 seconds

    def test_callback_with_complex_objects(self, mock_logger):
        """Test callback with complex object types."""

        def fetch_fn(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [{"id": item["id"], "processed": True} for item in items]

        items = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}, {"id": 3, "name": "C"}]
        results, failed = batch_fetch_with_callback(items, fetch_fn, logger=mock_logger)

        assert len(results) == 3
        assert all(result["processed"] is True for result in results)
        assert len(failed) == 0

    def test_callback_without_logger(self):
        """Test callback works without logger."""

        def fetch_fn(items: list[int]) -> list[int]:
            return items

        results, failed = batch_fetch_with_callback([1, 2, 3], fetch_fn, logger=None)

        assert len(results) == 3
        assert len(failed) == 0


# ============================================================================
# Tests for BatchFetchError Exception
# ============================================================================


class TestBatchFetchError:
    """Tests for BatchFetchError exception class."""

    def test_batch_fetch_error_instantiation(self):
        """Test that BatchFetchError can be instantiated."""
        error = BatchFetchError("Test error message")
        assert str(error) == "Test error message"

    def test_batch_fetch_error_inheritance(self):
        """Test that BatchFetchError inherits from Exception."""
        error = BatchFetchError("Test")
        assert isinstance(error, Exception)

    def test_batch_fetch_error_raised_on_complete_failure(self, mock_wit_client, mock_logger):
        """Test that BatchFetchError is raised when all items fail."""
        mock_wit_client.get_work_items = Mock(side_effect=Exception("API error"))

        with pytest.raises(BatchFetchError) as exc_info:
            batch_fetch_work_items(mock_wit_client, [1, 2, 3], max_retries=1, logger=mock_logger)

        assert "All 3 items failed to fetch" in str(exc_info.value)


# ============================================================================
# Tests for Logger Integration
# ============================================================================


class TestLoggerIntegration:
    """Tests for proper logger integration."""

    def test_logger_info_messages(self, mock_wit_client, mock_logger):
        """Test that info messages are logged correctly."""
        item_ids = list(range(1, 451))  # 3 batches

        batch_fetch_work_items(mock_wit_client, item_ids, batch_size=200, logger=mock_logger)

        # Verify info logs
        assert mock_logger.info.call_count == 2  # Start and end messages
        mock_logger.info.assert_any_call("Fetching 450 items in 3 batches...")
        mock_logger.info.assert_any_call("Successfully fetched 450 items, 0 failed")

    def test_logger_warning_on_retry(self, mock_wit_client, mock_work_item, mock_logger):
        """Test that warnings are logged on retry attempts."""
        call_count = 0

        def side_effect_with_failure(ids: list[int], fields: list[str] | None = None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First attempt failed")
            return [mock_work_item(item_id) for item_id in ids]

        mock_wit_client.get_work_items = Mock(side_effect=side_effect_with_failure)

        batch_fetch_work_items(mock_wit_client, [1, 2, 3], max_retries=3, logger=mock_logger)

        # Verify warning was logged
        assert mock_logger.warning.call_count == 1

    def test_logger_error_on_exhausted_retries(self, mock_wit_client, mock_logger):
        """Test that errors are logged when retries are exhausted."""
        mock_wit_client.get_work_items = Mock(side_effect=Exception("Persistent failure"))

        # Expect BatchFetchError when all items fail
        with pytest.raises(BatchFetchError):
            batch_fetch_work_items(mock_wit_client, [1, 2, 3], max_retries=2, logger=mock_logger)

        # Verify error was logged
        assert mock_logger.error.call_count == 1
