#!/usr/bin/env python3
"""
Tests for Error Handling Utility Module

Tests all four core utilities:
1. log_and_continue() - Continue execution after logging
2. log_and_return_default() - Return default value after logging
3. log_and_raise() - Log and re-raise exception
4. with_retry() - Retry decorator with exponential backoff

Target: >95% test coverage
"""

import logging
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from execution.utils.error_handling import (
    log_and_continue,
    log_and_raise,
    log_and_return_default,
    with_retry,
)


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing log calls."""
    return MagicMock(spec=logging.Logger)


class TestLogAndContinue:
    """Test suite for log_and_continue() function."""

    def test_logs_at_warning_level(self, mock_logger):
        """Test that log_and_continue logs at WARNING level."""
        error = ValueError("test error")
        context = {"item_id": 123}

        log_and_continue(mock_logger, error, context, "Test operation")

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args

        # Check message
        assert "Test operation failed" in call_args[0][0]
        assert "test error" in call_args[0][0]

    def test_includes_structured_context(self, mock_logger):
        """Test that structured context is included in log extra."""
        error = ValueError("test error")
        context = {"item_id": 123, "timestamp": "2026-02-10T10:00:00Z"}

        log_and_continue(mock_logger, error, context, "Parse operation")

        call_args = mock_logger.warning.call_args
        extra = call_args[1]["extra"]

        assert extra["error_type"] == "Parse operation"
        assert extra["exception_class"] == "ValueError"
        assert extra["context"] == context

    def test_handles_different_exception_types(self, mock_logger):
        """Test with different exception types (ValueError, ConnectionError, etc.)."""
        exceptions = [
            ValueError("value error"),
            ConnectionError("connection failed"),
            AttributeError("attribute missing"),
        ]

        for exc in exceptions:
            log_and_continue(mock_logger, exc, {"test": "data"}, "Operation")

            call_args = mock_logger.warning.call_args
            extra = call_args[1]["extra"]
            assert extra["exception_class"] == exc.__class__.__name__

    def test_does_not_raise_exception(self, mock_logger):
        """Test that log_and_continue does NOT raise the exception."""
        error = ValueError("test error")
        context = {"item_id": 123}

        # Should not raise
        log_and_continue(mock_logger, error, context, "Test")

        # Should only log, not raise
        mock_logger.warning.assert_called_once()

    def test_default_error_type(self, mock_logger):
        """Test default error_type parameter is 'Operation'."""
        error = ValueError("test error")
        context = {"item_id": 123}

        log_and_continue(mock_logger, error, context)

        call_args = mock_logger.warning.call_args
        extra = call_args[1]["extra"]
        assert extra["error_type"] == "Operation"


class TestLogAndReturnDefault:
    """Test suite for log_and_return_default() function."""

    def test_returns_default_value(self, mock_logger):
        """Test that it returns the specified default value."""
        error = FileNotFoundError("file not found")
        context = {"file_path": "/path/to/file"}
        default: list = []

        result = log_and_return_default(mock_logger, error, context, default, "File load")

        assert result == []
        assert result is default

    def test_returns_different_default_values(self, mock_logger):
        """Test with different default values (None, [], {}, 0)."""
        test_cases: list[tuple[Any, Any]] = [
            (None, None),
            ([], []),
            ({}, {}),
            (0, 0),
            ("default", "default"),
        ]

        for default_value, expected in test_cases:
            result = log_and_return_default(
                mock_logger,
                ValueError("error"),
                {"test": "context"},
                default_value,
                "Operation",
            )
            assert result == expected

    def test_logs_error(self, mock_logger):
        """Test that the error is logged at WARNING level."""
        error = FileNotFoundError("file not found")
        context = {"file_path": "/path/to/file"}

        log_and_return_default(mock_logger, error, context, [], "File load")

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert "File load failed" in call_args[0][0]

    def test_includes_structured_context(self, mock_logger):
        """Test that structured context is logged."""
        error = FileNotFoundError("file not found")
        context = {"file_path": "/path/to/file", "attempt": 1}

        log_and_return_default(mock_logger, error, context, [], "File load")

        call_args = mock_logger.warning.call_args
        extra = call_args[1]["extra"]

        assert extra["error_type"] == "File load"
        assert extra["exception_class"] == "FileNotFoundError"
        assert extra["context"] == context
        assert "default_value" in extra

    def test_default_value_none(self, mock_logger):
        """Test default_value defaults to None."""
        error = ValueError("error")
        context: dict[str, Any] = {}

        result = log_and_return_default(mock_logger, error, context)

        assert result is None


class TestLogAndRaise:
    """Test suite for log_and_raise() function."""

    def test_logs_at_error_level(self, mock_logger):
        """Test that log_and_raise logs at ERROR level with exc_info=True."""
        error = ValueError("critical error")
        context = {"operation": "db_write"}

        with pytest.raises(ValueError):
            log_and_raise(mock_logger, error, context, "Database operation")

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args

        # Check exc_info is True
        assert call_args[1]["exc_info"] is True

    def test_reraises_exception(self, mock_logger):
        """Test that log_and_raise RE-RAISES the exception."""
        error = ValueError("critical error")
        context = {"operation": "test"}

        with pytest.raises(ValueError) as exc_info:
            log_and_raise(mock_logger, error, context, "Test operation")

        # Should be the same exception object
        assert exc_info.value is error

    def test_logs_context_before_raising(self, mock_logger):
        """Test that context is logged before raising."""
        error = ConnectionError("connection failed")
        context = {"host": "api.example.com", "port": 443}

        with pytest.raises(ConnectionError):
            log_and_raise(mock_logger, error, context, "API connection")

        call_args = mock_logger.error.call_args
        extra = call_args[1]["extra"]

        assert extra["error_type"] == "API connection"
        assert extra["exception_class"] == "ConnectionError"
        assert extra["context"] == context

    def test_different_exception_types(self, mock_logger):
        """Test with various exception types."""
        exceptions = [
            ValueError("value error"),
            RuntimeError("runtime error"),
            KeyError("key error"),
        ]

        for exc in exceptions:
            with pytest.raises(exc.__class__):
                log_and_raise(mock_logger, exc, {"test": "data"}, "Operation")


class TestWithRetry:
    """Test suite for with_retry() decorator."""

    def test_successful_call_first_attempt(self, mock_logger):
        """Test that successful call on first attempt does not retry."""
        call_count = 0

        @with_retry(max_attempts=3)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()

        assert result == "success"
        assert call_count == 1

    def test_successful_after_failures(self):
        """Test successful call after 2 failures."""
        call_count = 0

        @with_retry(max_attempts=3, backoff_seconds=0.01)
        def eventually_successful():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temporary failure")
            return "success"

        result = eventually_successful()

        assert result == "success"
        assert call_count == 3

    def test_exhausts_all_retries(self):
        """Test exhausting all retries and raising exception."""
        call_count = 0

        @with_retry(max_attempts=3, backoff_seconds=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("permanent failure")

        with pytest.raises(ConnectionError) as exc_info:
            always_fails()

        assert "permanent failure" in str(exc_info.value)
        assert call_count == 3

    @patch("time.sleep")
    def test_exponential_backoff_timing(self, mock_sleep):
        """Test exponential backoff timing (mock time.sleep)."""
        call_count = 0

        @with_retry(max_attempts=4, backoff_seconds=1.0)
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise ConnectionError("retry me")
            return "success"

        result = failing_func()

        assert result == "success"

        # Check sleep calls: 1s, 2s, 4s (exponential backoff)
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_calls == [1.0, 2.0, 4.0]

    def test_catches_specific_exception_types(self):
        """Test with specific exception types tuple."""
        call_count = 0

        @with_retry(
            max_attempts=3,
            backoff_seconds=0.01,
            exceptions=(ConnectionError, TimeoutError),
        )
        def network_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("connection error")
            elif call_count == 2:
                raise TimeoutError("timeout")
            return "success"

        result = network_func()

        assert result == "success"
        assert call_count == 3

    def test_does_not_catch_unspecified_exceptions(self):
        """Test that unspecified exceptions are not caught."""

        @with_retry(max_attempts=3, exceptions=(ConnectionError,))
        def raises_value_error():
            raise ValueError("not retryable")

        # Should raise immediately, not retry
        with pytest.raises(ValueError):
            raises_value_error()

    def test_preserves_function_metadata(self):
        """Test that decorator preserves function metadata using functools.wraps."""

        @with_retry(max_attempts=3)
        def documented_func():
            """This is a docstring."""
            return "success"

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is a docstring."

    def test_works_with_function_arguments(self):
        """Test that decorator works with functions that take arguments."""
        call_count = 0

        @with_retry(max_attempts=3, backoff_seconds=0.01)
        def func_with_args(x: int, y: int, z: int = 0) -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("retry")
            return x + y + z

        result = func_with_args(1, 2, z=3)

        assert result == 6
        assert call_count == 2

    def test_default_parameters(self):
        """Test decorator with default parameters."""
        call_count = 0

        @with_retry()  # All defaults: max_attempts=3, backoff_seconds=1.0, exceptions=(Exception,)
        def func_with_defaults():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("retry")
            return "success"

        with patch("time.sleep"):  # Mock sleep to speed up test
            result = func_with_defaults()

        assert result == "success"
        assert call_count == 2


class TestIntegration:
    """Integration tests combining multiple error handling patterns."""

    def test_retry_with_log_and_return_default(self, mock_logger):
        """Test combining retry decorator with log_and_return_default."""
        call_count = 0

        @with_retry(max_attempts=2, backoff_seconds=0.01, exceptions=(ConnectionError,))
        def fetch_with_fallback():
            nonlocal call_count
            call_count += 1
            # Retry exhausts, then we handle with log_and_return_default
            raise ConnectionError("network error")

        try:
            fetch_with_fallback()
        except ConnectionError as e:
            result = log_and_return_default(
                mock_logger,
                e,
                context={"attempts": call_count},
                default_value={},
                error_type="API fetch",
            )

        assert result == {}
        assert call_count == 2  # Retried twice (max_attempts=2)
        mock_logger.warning.assert_called()

    def test_nested_error_handling(self, mock_logger):
        """Test nested error handling scenarios."""
        errors = []

        for i in range(3):
            try:
                if i == 1:
                    raise ValueError(f"error {i}")
                result = i * 2
            except ValueError as e:
                log_and_continue(mock_logger, e, {"index": i}, "Processing")
                errors.append(i)
                continue

        assert errors == [1]
        assert mock_logger.warning.call_count == 1
