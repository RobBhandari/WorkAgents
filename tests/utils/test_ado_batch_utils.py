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
from typing import Any
from unittest.mock import Mock, patch

import pytest

from execution.utils.ado_batch_utils import (
    BatchFetchError,
    batch_fetch_with_callback,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_logger():
    """Fixture for a mock logger."""
    return Mock(spec=logging.Logger)


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
