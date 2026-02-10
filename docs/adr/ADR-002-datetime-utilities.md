# ADR-002: Centralized Datetime Utilities

## Status
Accepted (Phase 1)

## Date
2026-02-10

## Context

Datetime parsing and calculation logic was duplicated across 15+ files in collectors and dashboards. Each module implemented its own version of:

* Parsing Azure DevOps timestamps (with 'Z' suffix)
* Calculating lead time between two timestamps
* Calculating age from creation to now
* Handling timezone-aware vs naive datetimes

This duplication caused multiple problems:

* **Inconsistent behavior**: Different modules handled edge cases differently (None values, invalid formats)
* **Code duplication**: Same parsing logic copy-pasted 15+ times
* **Testing burden**: Each module needed duplicate tests for datetime logic
* **Bug multiplication**: A bug in one implementation wouldn't be fixed in others
* **Maintenance overhead**: Changes to datetime handling required updating multiple files
* **Performance**: Repeated timezone conversions without caching

Example of duplicated code across modules:
```python
# In collector A:
if created_str:
    created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))

# In collector B:
if created_str and "Z" in created_str:
    created_dt = datetime.fromisoformat(created_str[:-1] + "+00:00")

# In dashboard C:
created_dt = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%SZ")
```

## Decision

Create a centralized `execution/utils/datetime_utils.py` module with four core utilities:

1. **`parse_ado_timestamp()`** - Parse Azure DevOps ISO timestamps with 'Z' suffix
2. **`calculate_lead_time_days()`** - Calculate lead time between creation and closure
3. **`calculate_age_days()`** - Calculate age from creation to now
4. **`parse_iso_timestamp()`** - Generic ISO 8601 parsing (with/without 'Z')

**Key design principles:**
* All functions handle `None` gracefully (return `None`)
* All functions validate input types and raise `ValueError` on invalid formats
* All functions use timezone-aware datetimes (UTC)
* All functions document their behavior with docstrings and examples
* All functions include sanity checks (no negative lead times/ages)

**Implementation:**
```python
from execution.utils.datetime_utils import parse_ado_timestamp, calculate_lead_time_days

# Unified parsing
created_dt = parse_ado_timestamp(item["System.CreatedDate"])

# Unified lead time calculation
lead_time = calculate_lead_time_days(
    created=item["System.CreatedDate"],
    closed=item["Microsoft.VSTS.Common.ClosedDate"]
)
```

## Consequences

### Positive

* **Single source of truth**: One implementation used everywhere
* **Consistent behavior**: Edge cases handled uniformly across all modules
* **Easier testing**: Test utilities once, not 15+ times
* **Bug fixes propagate**: Fix once, all modules benefit
* **Reduced code volume**: Eliminated ~200 lines of duplicate code
* **Better maintainability**: Changes to datetime logic require updating one file
* **Type safety**: Fully typed with Python 3.11+ hints for MyPy validation
* **Self-documenting**: Comprehensive docstrings with examples

### Negative

* **Slight indirection**: Must import from utils module
* **Migration effort**: Required updating 15+ files to use new utilities
* **Learning curve**: New developers must discover datetime_utils module

## Alternatives Considered

### Option A: Use third-party library (pendulum, arrow)
**Rejected**: Python's standard `datetime` module is sufficient for our needs. Adding external dependencies increases maintenance burden and deployment size.

### Option B: Keep duplication, standardize via linting
**Rejected**: Linting can't enforce logic correctness, only style. Duplication still exists and bugs multiply.

### Option C: Create datetime wrapper class
**Rejected**: Overengineered for our use case. Functions are simpler and more composable than a class.

## Implementation Details

### Function Signatures

```python
def parse_ado_timestamp(timestamp_str: str | None) -> datetime | None:
    """Parse Azure DevOps ISO timestamp with 'Z' suffix."""

def calculate_lead_time_days(created: str | None, closed: str | None) -> float | None:
    """Calculate lead time in days between creation and closure."""

def calculate_age_days(created: str | None, reference_time: datetime | None = None) -> float | None:
    """Calculate age in days from creation to reference time (default: now)."""

def parse_iso_timestamp(timestamp_str: str | None) -> datetime | None:
    """Parse generic ISO 8601 timestamp (with or without 'Z')."""
```

### Error Handling

All functions follow consistent error handling:
* Return `None` for `None` input (graceful degradation)
* Raise `ValueError` for invalid formats (explicit errors)
* Return `None` for negative lead times/ages (data quality issues)

## Usage Examples

### Before (Duplicated Code)
```python
# In ado_quality_metrics.py:
if created_str:
    try:
        created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        age_days = (datetime.now(UTC) - created_dt).total_seconds() / 86400
    except ValueError:
        age_days = None

# In flow_collector.py:
if created_str and closed_str:
    try:
        created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        closed = datetime.fromisoformat(closed_str.replace("Z", "+00:00"))
        lead_time = (closed - created).total_seconds() / 86400
    except ValueError:
        lead_time = None
```

### After (Centralized Utilities)
```python
from execution.utils.datetime_utils import parse_ado_timestamp, calculate_age_days, calculate_lead_time_days

# Clean, simple, consistent
age_days = calculate_age_days(item["System.CreatedDate"])
lead_time = calculate_lead_time_days(
    created=item["System.CreatedDate"],
    closed=item["Microsoft.VSTS.Common.ClosedDate"]
)
```

## Impact Metrics

* **Code reduction**: Eliminated ~200 lines of duplicate datetime logic
* **Files updated**: 15 collectors and dashboards migrated to use utilities
* **Test coverage**: Added 12 comprehensive unit tests for datetime_utils
* **Bug fixes**: Fixed 3 edge case bugs during consolidation (timezone handling, None checks)

## Related Decisions

* See ADR-003 for constants extraction (includes datetime-related thresholds)
* See ADR-004 for error handling patterns (datetime utilities integrate with structured logging)
