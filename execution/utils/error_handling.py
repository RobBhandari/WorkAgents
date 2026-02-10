#!/usr/bin/env python3
"""
Error Handling Utility Module

Provides reusable error handling patterns to replace bare `except Exception:` blocks
across the codebase. Promotes structured error logging with context and consistent
error handling strategies.

This module provides four core utilities:
1. log_and_continue() - Log error and continue execution (for expected failures)
2. log_and_return_default() - Log error and return a default value
3. log_and_raise() - Log error with context and re-raise (for unexpected errors)
4. with_retry() - Decorator for retry logic with exponential backoff

All functions use structured logging with contextual information to aid debugging.
"""

import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

# Type variable for generic function return types
T = TypeVar("T")


def log_and_continue(
    logger: logging.Logger,
    error: Exception,
    context: dict[str, Any],
    error_type: str = "Operation",
) -> None:
    """
    Log an error with structured context and continue execution gracefully.

    Use this when encountering expected errors that should not halt execution
    (e.g., parsing failures on individual items in a batch).

    Args:
        logger: Logger instance from logging.getLogger(__name__)
        error: The caught exception
        context: Structured data about what failed (item_id, timestamp, etc.)
        error_type: Human-readable description of the operation

    Example:
        try:
            created_dt = parse_ado_timestamp(created)
        except ValueError as e:
            log_and_continue(
                logger, e,
                context={"item_id": item.get("System.Id"), "timestamp": created},
                error_type="Date parsing"
            )
            continue
    """
    logger.warning(
        f"{error_type} failed: {error}",
        extra={
            "error_type": error_type,
            "exception_class": error.__class__.__name__,
            "context": context,
        },
    )


def log_and_return_default(
    logger: logging.Logger,
    error: Exception,
    context: dict[str, Any],
    default_value: Any = None,
    error_type: str = "Operation",
) -> Any:
    """
    Log an error and return a default value (for functions that need to return something).

    Use this when a function should return a default value on error rather than raising.

    Args:
        logger: Logger instance
        error: The caught exception
        context: Structured data about what failed
        default_value: Value to return on error (None, [], {}, etc.)
        error_type: Human-readable description

    Returns:
        default_value

    Example:
        try:
            return load_metrics_from_file(path)
        except FileNotFoundError as e:
            return log_and_return_default(
                logger, e,
                context={"file_path": str(path)},
                default_value=[],
                error_type="File loading"
            )
    """
    logger.warning(
        f"{error_type} failed, returning default value: {error}",
        extra={
            "error_type": error_type,
            "exception_class": error.__class__.__name__,
            "context": context,
            "default_value": str(default_value),
        },
    )
    return default_value


def log_and_raise(
    logger: logging.Logger,
    error: Exception,
    context: dict[str, Any],
    error_type: str = "Operation",
) -> None:
    """
    Log an error with context and re-raise it (for unexpected errors).

    Use this for unexpected errors that should halt execution and bubble up.

    Args:
        logger: Logger instance
        error: The caught exception
        context: Structured data about what failed
        error_type: Human-readable description

    Raises:
        The original exception after logging

    Example:
        try:
            result = critical_operation()
        except Exception as e:
            log_and_raise(
                logger, e,
                context={"operation": "critical_operation"},
                error_type="Critical operation"
            )
    """
    logger.error(
        f"{error_type} failed critically: {error}",
        exc_info=True,
        extra={
            "error_type": error_type,
            "exception_class": error.__class__.__name__,
            "context": context,
        },
    )
    raise error


def with_retry(
    max_attempts: int = 3,
    backoff_seconds: float = 1.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to retry a function with exponential backoff.

    Use this for network calls or other transient failures.

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        backoff_seconds: Initial backoff time, doubles each retry
        exceptions: Tuple of exception types to catch

    Example:
        @with_retry(max_attempts=3, backoff_seconds=2.0, exceptions=(ConnectionError, TimeoutError))
        def fetch_from_api(url: str) -> dict:
            return requests.get(url).json()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            logger = logging.getLogger(func.__module__)
            last_exception: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts",
                            exc_info=True,
                            extra={
                                "function": func.__name__,
                                "max_attempts": max_attempts,
                                "final_exception": e.__class__.__name__,
                            },
                        )
                        raise

                    # Calculate exponential backoff
                    wait_time = backoff_seconds * (2 ** (attempt - 1))

                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}), "
                        f"retrying in {wait_time:.1f}s: {e}",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "wait_time": wait_time,
                            "exception": e.__class__.__name__,
                        },
                    )

                    time.sleep(wait_time)

            # This should never be reached, but satisfies type checker
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic failed unexpectedly")

        return wrapper

    return decorator


"""
USAGE EXAMPLES
==============

# Example 1: Handle expected parsing failures in a loop
from execution.utils.error_handling import log_and_continue

logger = logging.getLogger(__name__)

for item in items:
    try:
        value = parse_value(item)
    except ValueError as e:
        log_and_continue(logger, e, {"item_id": item.id}, "Value parsing")
        continue


# Example 2: Return default value on file not found
from execution.utils.error_handling import log_and_return_default

def load_config(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as e:
        return log_and_return_default(
            logger, e,
            context={"path": str(path)},
            default_value={},
            error_type="Config loading"
        )


# Example 3: Re-raise unexpected errors
from execution.utils.error_handling import log_and_raise

try:
    critical_db_operation()
except Exception as e:
    log_and_raise(logger, e, {"operation": "db_write"}, "Database operation")


# Example 4: Retry network calls
from execution.utils.error_handling import with_retry

@with_retry(max_attempts=3, backoff_seconds=2.0, exceptions=(ConnectionError, TimeoutError))
def fetch_data(url: str) -> dict:
    return requests.get(url).json()


# Example 5: Combining patterns - retry with structured logging on final failure
@with_retry(max_attempts=3, exceptions=(ConnectionError,))
def fetch_with_fallback(url: str) -> dict:
    try:
        return requests.get(url).json()
    except Exception as e:
        return log_and_return_default(
            logger, e,
            context={"url": url},
            default_value={},
            error_type="API fetch"
        )
"""
