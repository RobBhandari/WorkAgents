# ADR-003: Constants Extraction Module

## Status
Accepted (Phase 1)

## Date
2026-02-10

## Context

Magic numbers and hardcoded configuration values were scattered across 20+ files in the codebase. This created several problems:

* **No single source of truth**: Same constant defined differently in multiple places (e.g., `AGING_THRESHOLD = 30` in one file, `30` hardcoded in another)
* **Maintenance burden**: Changing a threshold required finding and updating all occurrences
* **Inconsistent behavior**: Different modules used different thresholds for the same concept
* **Poor documentation**: No central place documenting what thresholds mean or why they were chosen
* **Testing difficulty**: Hard to test behavior with different threshold values
* **Configuration drift**: Production and development environments had different hardcoded values

Examples of magic numbers found across the codebase:
```python
# In flow_collector.py:
if lead_time_days > 365:  # What does 365 mean? Why 365?
    cleanup_count += 1

# In quality_dashboard.py:
if bug_age > 30:  # Is this the same 30 as elsewhere?
    aging_bugs.append(bug)

# In armorcode_collector.py:
PAGE_SIZE = 100  # Defined multiple times
MAX_PAGES = 100
```

## Decision

Create a centralized `execution/domain/constants.py` module with type-safe, immutable configuration constants organized into logical groups:

1. **`FlowMetricsConfig`** - Flow efficiency thresholds (lead time, aging, percentiles)
2. **`APIConfig`** - API pagination, timeouts, and limits
3. **`QualityThresholds`** - Quality-related alerting thresholds
4. **`SamplingConfig`** - Data sampling strategies for performance
5. **`CleanupIndicators`** - Cleanup effort detection thresholds
6. **`HistoryRetention`** - Data retention policies

**Key design principles:**
* Use `@dataclass(frozen=True)` for immutability
* Document each constant with docstrings explaining purpose and rationale
* Provide singleton instances for easy import
* Group related constants into logical classes
* Use descriptive names (not `THRESHOLD_1`, `THRESHOLD_2`)

**Implementation:**
```python
from execution.domain.constants import flow_metrics, api_config

# Clear, documented usage
if lead_time_days > flow_metrics.CLEANUP_THRESHOLD_DAYS:
    cleanup_count += 1

# API configuration
PAGE_SIZE = api_config.ARMORCODE_PAGE_SIZE
```

## Consequences

### Positive

* **Single source of truth**: All constants defined once in one place
* **Self-documenting**: Each constant has a docstring explaining its purpose
* **Type-safe**: Frozen dataclasses prevent accidental modification
* **Easy to change**: Update threshold in one place, all modules use new value
* **Testable**: Can mock constants for testing different scenarios
* **Immutable**: `frozen=True` prevents accidental mutation at runtime
* **Discoverable**: IDE autocomplete shows all available constants
* **Versioned**: Changes to constants are tracked in git history

### Negative

* **Import dependency**: All modules depend on constants module
* **Migration effort**: Required updating 20+ files to use constants
* **Less flexibility**: Can't easily have per-environment constants (requires additional config layer)
* **Potential performance overhead**: Extra import (negligible in practice)

## Alternatives Considered

### Option A: Environment variables for all configuration
**Rejected**: Environment variables are strings, require parsing, and lack type safety. Better for secrets and deployment-specific config, not for application constants.

### Option B: Configuration file (YAML/JSON)
**Rejected**: Adds complexity (file I/O, parsing). Python dataclasses provide better type safety and IDE support. Configuration files better for deployment-specific values, not application logic constants.

### Option C: Keep magic numbers, add comments
**Rejected**: Comments don't enforce single source of truth. Duplication still exists and values can drift.

### Option D: Create separate constants file per module
**Rejected**: Scatters constants across multiple files, loses centralization benefits. Constants often used across multiple modules.

## Implementation Details

### Dataclass Structure

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class FlowMetricsConfig:
    """Flow metrics calculation constants."""

    CLEANUP_THRESHOLD_DAYS: int = 365
    """Lead time threshold to classify work as cleanup (items open >365 days)"""

    AGING_THRESHOLD_DAYS: int = 30
    """Age threshold for identifying aging work items (open >30 days)"""

    P95_PERCENTILE: int = 95
    """95th percentile (tail latency)"""

# Singleton instance for easy import
flow_metrics = FlowMetricsConfig()
```

### Usage Pattern

```python
# Import singleton instance
from execution.domain.constants import flow_metrics, quality_thresholds

# Use descriptive constant names
if bug_age > quality_thresholds.STALE_BUG_DAYS:
    stale_bugs.append(bug)

if lead_time > flow_metrics.CLEANUP_THRESHOLD_DAYS:
    cleanup_items.append(item)
```

## Migration Examples

### Before (Magic Numbers)
```python
# Scattered magic numbers, no documentation
if lead_time_days > 365:
    cleanup_count += 1

if age_days > 30:
    aging_items.append(item)

PAGE_SIZE = 100  # Defined in 5 different files
```

### After (Centralized Constants)
```python
from execution.domain.constants import flow_metrics, api_config

# Clear, documented, single source of truth
if lead_time_days > flow_metrics.CLEANUP_THRESHOLD_DAYS:
    cleanup_count += 1

if age_days > flow_metrics.AGING_THRESHOLD_DAYS:
    aging_items.append(item)

PAGE_SIZE = api_config.ARMORCODE_PAGE_SIZE
```

## Impact Metrics

* **Constants centralized**: 45+ magic numbers replaced with named constants
* **Files updated**: 20+ collectors and dashboards migrated
* **Documentation added**: Each constant has a docstring explaining purpose
* **Inconsistencies fixed**: Found and resolved 6 instances where different modules used different values for the same concept

## Testing Benefits

Constants module enables easier testing of threshold behavior:

```python
def test_cleanup_detection_with_custom_threshold(monkeypatch):
    """Test cleanup detection with different threshold."""
    # Can mock constants for testing
    monkeypatch.setattr("execution.domain.constants.flow_metrics.CLEANUP_THRESHOLD_DAYS", 180)

    result = detect_cleanup_effort(lead_times=[200, 150, 100])
    assert result.cleanup_count == 1  # Only 200 exceeds 180
```

## Future Enhancements

* **Environment overrides**: Allow environment variables to override default constants for deployment-specific tuning
* **Configuration validation**: Add validation to ensure constants are within reasonable ranges
* **Dynamic configuration**: Load constants from database or config service for runtime changes (requires careful caching)

## Related Decisions

* See ADR-002 for datetime utilities (uses constants for threshold values)
* See ADR-004 for error handling patterns (uses constants for retry limits)
