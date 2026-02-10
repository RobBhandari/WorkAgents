# ADR-004: Error Handling Patterns and Utilities

## Status
Accepted (Phase 2)

## Date
2026-02-10

## Context

The codebase contained 30+ instances of bare `except Exception:` blocks with inconsistent error handling:

* **Bare exception catching**: `except Exception:` catches everything, including system exits and keyboard interrupts
* **No context logging**: Errors logged without information about what operation failed
* **Inconsistent strategies**: Some code continued on error, some returned defaults, some re-raised
* **Loss of stack traces**: Many error handlers didn't log `exc_info=True`, losing valuable debugging information
* **No retry logic**: Transient failures (network timeouts, rate limits) caused permanent failures
* **Poor debugging**: Couldn't trace what input caused failures or which operation failed

Examples of problematic error handling:
```python
# No context, swallows all exceptions
try:
    data = fetch_from_api()
except Exception:
    print("Error fetching data")
    data = []

# Loses stack trace
try:
    process_item(item)
except Exception as e:
    print(f"Error: {e}")
    continue

# No differentiation between expected and unexpected errors
try:
    parse_date(timestamp)
except Exception:
    return None  # Was this a parsing error or a system failure?
```

## Decision

Create a centralized `execution/utils/error_handling.py` module with four reusable error handling patterns:

1. **`log_and_continue()`** - Log error with context and continue execution (for expected failures)
2. **`log_and_return_default()`** - Log error and return a default value (for functions)
3. **`log_and_raise()`** - Log error with context and re-raise (for unexpected errors)
4. **`with_retry()`** - Decorator for retry logic with exponential backoff (for transient failures)

**Key design principles:**
* Always log structured context (what failed, what data caused failure)
* Differentiate between expected failures (continue) and unexpected failures (re-raise)
* Use specific exception types, not bare `Exception`
* Include `exc_info=True` for unexpected errors to preserve stack traces
* Provide retry logic for transient failures (network, rate limits)

**Implementation:**
```python
from execution.utils.error_handling import log_and_continue, with_retry

# Handle expected parsing failures
for item in items:
    try:
        value = parse_value(item)
    except ValueError as e:
        log_and_continue(logger, e, {"item_id": item.id}, "Value parsing")
        continue

# Retry transient network failures
@with_retry(max_attempts=3, exceptions=(ConnectionError, TimeoutError))
def fetch_from_api(url: str) -> dict:
    return requests.get(url).json()
```

## Consequences

### Positive

* **Structured error logging**: All errors logged with context (operation, data, error type)
* **Stack traces preserved**: Use `exc_info=True` for unexpected errors
* **Consistent patterns**: Four clear patterns cover all error handling scenarios
* **Better debugging**: Context reveals what input caused failure and which operation failed
* **Transient failure handling**: Retry logic prevents permanent failures from temporary issues
* **Type-safe**: Catch specific exception types, not bare `Exception`
* **Maintainable**: Centralized error handling logic, not duplicated across modules
* **Production-ready**: Integrates with structured logging for alerting and monitoring

### Negative

* **Migration effort**: Required updating 30+ error handling blocks across 15 files
* **Slightly more verbose**: `log_and_continue()` is longer than bare `except Exception:`
* **Learning curve**: Developers must choose appropriate pattern for their use case
* **Potential over-logging**: Must be careful not to log too verbosely in hot paths

## Alternatives Considered

### Option A: Keep bare except Exception blocks
**Rejected**: Catches too much (system exits, keyboard interrupts), loses context, inconsistent behavior.

### Option B: Use third-party error handling library (tenacity, backoff)
**Rejected**: Python's standard library is sufficient. Retry decorator can be implemented in 50 lines. Adding external dependencies increases maintenance burden.

### Option C: Create custom exception hierarchy
**Rejected**: Overengineered for our use case. Standard Python exceptions (ValueError, ConnectionError) are sufficient and well-understood.

### Option D: Use context managers for error handling
**Rejected**: Context managers add boilerplate and don't improve clarity. Function-based utilities are simpler and more composable.

## Implementation Details

### Four Error Handling Patterns

```python
# Pattern 1: Log and continue (expected failures in loops)
for item in items:
    try:
        process(item)
    except ValueError as e:
        log_and_continue(logger, e, {"item_id": item.id}, "Processing")
        continue

# Pattern 2: Log and return default (functions with fallback values)
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

# Pattern 3: Log and raise (unexpected errors that should bubble up)
try:
    critical_operation()
except Exception as e:
    log_and_raise(logger, e, {"operation": "critical_op"}, "Critical operation")

# Pattern 4: Retry with backoff (transient network failures)
@with_retry(max_attempts=3, backoff_seconds=2.0, exceptions=(ConnectionError, TimeoutError))
def fetch_data(url: str) -> dict:
    return requests.get(url).json()
```

### Structured Logging Integration

All utilities use structured logging with `extra={}` for context:

```python
def log_and_continue(logger, error, context, error_type):
    logger.warning(
        f"{error_type} failed: {error}",
        extra={
            "error_type": error_type,
            "exception_class": error.__class__.__name__,
            "context": context,
        },
    )
```

This enables:
* Filtering by error type in log aggregation systems
* Correlating errors across modules
* Alerting on specific error patterns
* Debugging with full context

## Migration Examples

### Before (Bare Exception Handling)
```python
# No context, catches everything, no stack trace
try:
    created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
except Exception:
    print(f"Error parsing date: {created_str}")
    continue

# Silent failure, loses error information
try:
    data = fetch_from_api(url)
except Exception:
    data = []

# No retry on transient failures
try:
    response = requests.get(url, timeout=30)
except Exception as e:
    print(f"Error: {e}")
    return None
```

### After (Structured Error Handling)
```python
from execution.utils.error_handling import log_and_continue, log_and_return_default, with_retry

# Structured context, specific exception, continue gracefully
try:
    created_dt = parse_ado_timestamp(created_str)
except ValueError as e:
    log_and_continue(
        logger, e,
        context={"item_id": item.id, "timestamp": created_str},
        error_type="Date parsing"
    )
    continue

# Log with context, return default value
try:
    data = fetch_from_api(url)
except ConnectionError as e:
    data = log_and_return_default(
        logger, e,
        context={"url": url},
        default_value=[],
        error_type="API fetch"
    )

# Automatic retry with exponential backoff
@with_retry(max_attempts=3, backoff_seconds=2.0, exceptions=(ConnectionError, TimeoutError))
def fetch_from_api(url: str) -> dict:
    return requests.get(url, timeout=30).json()
```

## Impact Metrics

* **Error handling blocks updated**: 30+ bare `except Exception:` replaced with specific patterns
* **Files updated**: 15 collectors and dashboards
* **Specific exceptions**: Replaced bare `Exception` with specific types (ValueError, FileNotFoundError, ConnectionError)
* **Context added**: All errors now logged with structured context (operation, data, error type)
* **Retry logic**: Added retry logic to 8 network-calling functions

## Testing Benefits

Error handling utilities enable better testing:

```python
def test_error_handling_with_invalid_data(caplog):
    """Test that invalid data is handled gracefully."""
    items = [valid_item, invalid_item, valid_item]

    results = process_items(items)

    # Should process valid items despite invalid one
    assert len(results) == 2

    # Should log error with context
    assert "Value parsing failed" in caplog.text
    assert "item_id" in caplog.text
```

## Best Practices

1. **Choose specific exceptions**: Use `ValueError`, `FileNotFoundError`, `ConnectionError` instead of bare `Exception`
2. **Include context**: Always provide context dict with relevant data (IDs, paths, URLs)
3. **Use appropriate pattern**:
   - Expected failures in loops → `log_and_continue()`
   - Functions with fallback → `log_and_return_default()`
   - Unexpected errors → `log_and_raise()`
   - Transient failures → `@with_retry()`
4. **Don't over-catch**: Only catch exceptions you can handle
5. **Preserve stack traces**: Use `exc_info=True` for unexpected errors

## Related Decisions

* See ADR-001 for structured logging (error handling integrates with logging)
* See ADR-002 for datetime utilities (raise `ValueError` on invalid formats)
* See `execution/utils/error_handling.py` for implementation
