# ADR-001: Structured Logging

## Status
Accepted (Phase 1)

## Date
2026-02-10

## Context

The codebase contained over 50 bare `print()` statements scattered across collectors, dashboards, and utilities. This created multiple problems:

* **No log levels**: Everything was printed at the same priority, making it impossible to filter by severity
* **No timestamps**: Couldn't tell when events occurred or how long operations took
* **No context**: Lacked structured data (request IDs, user context, operation metadata)
* **Not production-ready**: Print statements don't integrate with centralized logging systems (CloudWatch, Splunk, etc.)
* **Poor debugging**: No ability to trace operations across modules or correlate events
* **No log rotation**: Output would grow unbounded in production

Example of problematic code:
```python
# No context, no timestamp, no severity
print("Fetching quality metrics...")
print(f"Found {len(bugs)} bugs")
```

## Decision

Replace all `print()` statements with Python's standard `logging` module using structured logging patterns:

* Use `logging.getLogger(__name__)` for module-level loggers
* Apply appropriate log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`
* Include structured context using `extra={}` parameter for JSON logging
* Configure centralized logging with timestamps, module names, and levels
* Use `logger.info()` for normal operations, `logger.warning()` for issues, `logger.error()` for failures

**Implementation:**
```python
import logging

logger = logging.getLogger(__name__)

# Structured logging with context
logger.info("Fetching quality metrics", extra={"source": "azure_devops"})
logger.info("Quality metrics retrieved", extra={
    "bug_count": len(bugs),
    "open_bugs": open_count,
    "closed_bugs": closed_count
})
```

## Consequences

### Positive

* **Filterable by severity**: Can filter logs by level (show only warnings/errors in production)
* **Timestamps included**: Every log entry has a precise timestamp
* **Structured context**: Can log structured data (JSON) for log aggregation systems
* **Production-ready**: Integrates with standard logging infrastructure (CloudWatch, Splunk, ELK)
* **Better debugging**: Can trace operations across modules using correlation IDs
* **Configurable output**: Can redirect logs to files, syslog, or cloud services without code changes
* **Performance monitoring**: Can measure operation duration using log timestamps

### Negative

* **Migration effort**: Required updating 50+ print statements across 20 files
* **Slightly more verbose**: `logger.info()` is longer than `print()`
* **Configuration required**: Need to configure logging handlers and formatters
* **Learning curve**: New developers must learn logging best practices

## Alternatives Considered

### Option A: Keep print() statements
**Rejected**: Not production-ready, lacks structured logging capabilities, no integration with monitoring systems.

### Option B: Use third-party logging library (structlog, loguru)
**Rejected**: Python's standard `logging` module is sufficient, well-documented, and has zero external dependencies. Adding a third-party library increases maintenance burden.

### Option C: Hybrid approach (print for development, logging for production)
**Rejected**: Inconsistent, hard to maintain, leads to divergence between dev and prod environments.

## Compliance

Enforced through:
* Code reviews (check for `print()` statements in new code)
* Linting rules (can add custom rule to detect print statements)
* Developer guidelines in `CONTRIBUTING.md`

## Examples

Before:
```python
print("Fetching bugs from Azure DevOps...")
print(f"Found {len(bugs)} bugs")
print(f"ERROR: Failed to fetch bugs: {e}")
```

After:
```python
logger.info("Fetching bugs from Azure DevOps", extra={"source": "ado"})
logger.info("Bugs retrieved successfully", extra={
    "bug_count": len(bugs),
    "project": "WorkAgents"
})
logger.error("Failed to fetch bugs", exc_info=True, extra={
    "error": str(e),
    "project": "WorkAgents"
})
```

## Related Decisions

* See ADR-004 for error handling patterns that integrate with structured logging
* See `execution/utils/error_handling.py` for logging utilities
