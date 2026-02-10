# ADR-007: Command Pattern for Risk Query Decomposition

## Status
Accepted (Phase 3)

## Date
2026-02-10

## Context

The `risk.py` dashboard (1,800+ lines) contained complex query logic mixed with rendering:

* 15+ different risk queries embedded in single file
* Query logic duplicated across different functions
* Hard to test queries independently
* Couldn't reuse query logic in other contexts (API, CLI)
* Adding new queries required editing massive file
* Risk of breaking existing queries when adding new ones

Example of embedded query logic:
```python
def generate_risk_dashboard():
    # ... 200 lines of data loading ...

    # Query 1: High severity products (embedded logic)
    high_severity = [p for p in products if p["risk_score"] > 80]

    # Query 2: Trending up products (embedded logic)
    trending_up = [p for p in products if p["trend"] == "increasing" and p["delta"] > 5]

    # Query 3: Stale findings (embedded logic)
    stale = [f for f in findings if (datetime.now() - f["discovered"]).days > 90]

    # ... 1400 lines of rendering ...
```

Problems with embedded queries:

* **Not reusable**: Can't use query logic outside dashboard generation
* **Not testable**: Must generate entire dashboard to test one query
* **Not composable**: Can't combine queries (e.g., high severity AND trending up)
* **Hard to maintain**: Query logic scattered across 1,800-line file
* **Poor discoverability**: New developers must scan entire file to find queries

## Decision

Extract query logic into separate query modules using Command Pattern:

1. **Query Functions** - Each query is a function with clear input/output
2. **Query Module** - Organize queries by domain (risk queries, security queries)
3. **Composable Design** - Queries can be combined and reused
4. **Type-Safe** - Queries use domain models, not raw dicts

**Implementation:**
```python
# execution/queries/risk_queries.py
def query_high_severity_products(
    products: list[ProductRisk],
    threshold: int = 80
) -> list[ProductRisk]:
    """Query products with risk score above threshold."""
    return [p for p in products if p.risk_score > threshold]

def query_trending_up_products(
    products: list[ProductRisk],
    delta_threshold: int = 5
) -> list[ProductRisk]:
    """Query products with increasing risk trend."""
    return [
        p for p in products
        if p.trend == "increasing" and p.delta > delta_threshold
    ]

# Usage in dashboard
from execution.queries.risk_queries import query_high_severity_products

high_severity = query_high_severity_products(products, threshold=80)
```

**Key principles:**
* Each query is a pure function (no side effects)
* Queries take domain models as input, return filtered results
* Queries are composable (can chain/combine)
* Queries have clear, descriptive names
* Queries include default parameter values for common thresholds

## Consequences

### Positive

* **Reusable**: Query logic can be used in dashboards, APIs, CLI, notebooks
* **Testable**: Can test queries independently with mock data
* **Composable**: Can combine queries (e.g., `query_high_severity(query_trending_up(...))`)
* **Maintainable**: Queries organized in focused modules
* **Discoverable**: IDE autocomplete shows all available queries
* **Type-safe**: Queries use domain models, MyPy catches type errors
* **Self-documenting**: Function names describe what they query for
* **Easy to extend**: Add new query by adding new function

### Negative

* **Indirection**: Must import from query module
* **Migration effort**: Required extracting 15+ queries from god file
* **Potential duplication**: Similar queries across different domains
* **Learning curve**: Developers must know where to find queries

## Alternatives Considered

### Option A: Keep queries embedded in dashboard code
**Rejected**: Not reusable, not testable, poor maintainability.

### Option B: SQL-like query language
**Rejected**: Overengineered. Python functions provide sufficient expressiveness without DSL complexity.

### Option C: Object-oriented query builder
**Rejected**: More complex than functional approach. ORM-style query builders add cognitive overhead without benefits for our use case.

### Option D: GraphQL-style queries
**Rejected**: Too heavyweight for internal queries. GraphQL better for external API, not internal data filtering.

## Implementation Details

### Query Function Pattern

```python
from typing import Callable

def query_high_severity_products(
    products: list[ProductRisk],
    threshold: int = 80
) -> list[ProductRisk]:
    """
    Query products with risk score above threshold.

    Args:
        products: List of product risk data
        threshold: Minimum risk score (default: 80 = high severity)

    Returns:
        Filtered list of high-severity products

    Example:
        >>> products = [
        ...     ProductRisk(name="App1", risk_score=85),
        ...     ProductRisk(name="App2", risk_score=60)
        ... ]
        >>> high_risk = query_high_severity_products(products, threshold=80)
        >>> len(high_risk)
        1
    """
    return [p for p in products if p.risk_score > threshold]
```

**Key components:**
* **Type hints**: Clear input/output types for MyPy validation
* **Default parameters**: Sensible defaults for common use cases
* **Docstring**: Explains what query does, parameters, return value, includes example
* **Pure function**: No side effects, same inputs → same outputs

### Composable Queries

Queries can be combined for complex filtering:

```python
# Combine multiple queries
high_severity = query_high_severity_products(products, threshold=80)
trending = query_trending_up_products(high_severity, delta_threshold=5)
recent = query_recent_findings(trending, days=30)

# Or use pipe-style composition (with helper function)
result = pipe(
    products,
    lambda p: query_high_severity_products(p, 80),
    lambda p: query_trending_up_products(p, 5),
    lambda p: query_recent_findings(p, 30)
)
```

### Query Organization

Organize queries by domain in separate modules:

```
execution/queries/
├── __init__.py
├── risk_queries.py        # Risk-related queries
├── security_queries.py    # Security vulnerability queries
├── quality_queries.py     # Quality metrics queries
└── flow_queries.py        # Flow metrics queries
```

Each module contains 5-10 related query functions.

## Migration Examples

### Before (Embedded Query Logic)
```python
# dashboards/risk.py (1,800 lines)
def generate_risk_dashboard():
    products = load_products()

    # Embedded query logic (repeated in multiple places)
    high_severity = [
        p for p in products
        if p["risk_score"] > 80
    ]

    critical_products = [
        p for p in products
        if p["risk_score"] > 90 and p["status"] == "active"
    ]

    # ... 1600 more lines ...
```

### After (Extracted Query Functions)
```python
# execution/queries/risk_queries.py (~200 lines, focused)
def query_high_severity_products(
    products: list[ProductRisk],
    threshold: int = 80
) -> list[ProductRisk]:
    """Query products with risk score above threshold."""
    return [p for p in products if p.risk_score > threshold]

def query_critical_active_products(
    products: list[ProductRisk]
) -> list[ProductRisk]:
    """Query critical products with active status."""
    return [
        p for p in products
        if p.risk_score > 90 and p.status == "active"
    ]

# dashboards/trends/calculator.py (~300 lines, focused)
from execution.queries.risk_queries import (
    query_high_severity_products,
    query_critical_active_products
)

def calculate_risk_summary(products: list[ProductRisk]) -> RiskSummary:
    """Calculate risk summary using query functions."""
    high_severity = query_high_severity_products(products, threshold=80)
    critical = query_critical_active_products(products)

    return RiskSummary(
        high_severity_count=len(high_severity),
        critical_count=len(critical)
    )
```

## Testing Strategy

Query functions enable focused unit tests:

```python
# Test queries independently with mock data
def test_query_high_severity_products():
    """Test high severity product query."""
    products = [
        ProductRisk(name="App1", risk_score=85, status="active"),
        ProductRisk(name="App2", risk_score=60, status="active"),
        ProductRisk(name="App3", risk_score=95, status="active"),
    ]

    result = query_high_severity_products(products, threshold=80)

    assert len(result) == 2
    assert result[0].name == "App1"
    assert result[1].name == "App3"

def test_query_with_empty_input():
    """Test query handles empty input gracefully."""
    result = query_high_severity_products([], threshold=80)

    assert result == []

def test_query_composition():
    """Test combining multiple queries."""
    products = [
        ProductRisk(name="App1", risk_score=85, trend="increasing", delta=10),
        ProductRisk(name="App2", risk_score=85, trend="stable", delta=0),
        ProductRisk(name="App3", risk_score=60, trend="increasing", delta=10),
    ]

    # Combine queries: high severity AND trending up
    high_severity = query_high_severity_products(products, threshold=80)
    trending = query_trending_up_products(high_severity, delta_threshold=5)

    assert len(trending) == 1
    assert trending[0].name == "App1"
```

## Query Catalog

Common query patterns across domains:

**Filtering queries:**
* `query_by_threshold()` - Filter by numeric threshold
* `query_by_status()` - Filter by status field
* `query_by_date_range()` - Filter by timestamp range

**Aggregation queries:**
* `query_top_n()` - Get top N items by metric
* `query_group_by()` - Group items by field
* `query_percentile()` - Calculate percentile values

**Temporal queries:**
* `query_recent()` - Get items within N days
* `query_trending()` - Get items with trend direction
* `query_stale()` - Get items older than N days

## Impact Metrics

* **Queries extracted**: 15+ queries from god file
* **Query module lines**: ~200 lines (focused, testable)
* **Reuse count**: Queries used in 3 contexts (dashboards, API endpoints, CLI)
* **Test coverage**: 100% coverage on query functions (easy to test)
* **God file reduction**: Reduced `risk.py` from 1,800 to 250 lines

## Performance Considerations

Query functions use list comprehensions (efficient in Python):

```python
# Efficient: Single pass through list
high_severity = [p for p in products if p.risk_score > 80]

# Less efficient: Multiple passes (avoid this)
high_severity = filter(lambda p: p.risk_score > 80, products)
high_severity = [p for p in high_severity]  # Materializes twice
```

For large datasets (>10,000 items), consider:
* Early filtering (filter before complex operations)
* Generator expressions (for memory efficiency)
* Indexing (if same dataset queried repeatedly)

## Future Enhancements

* **Query caching**: Cache query results for repeated queries on same dataset
* **Query optimizer**: Detect inefficient query combinations and optimize
* **Query DSL**: Create higher-level query language if patterns emerge
* **Parallel queries**: Run independent queries in parallel for large datasets

## Related Decisions

* See ADR-005 for god file decomposition (enables query extraction)
* See ADR-006 for pipeline pattern (queries used in Stage 2: Calculate Summary)
* See `execution/queries/` for query implementations
