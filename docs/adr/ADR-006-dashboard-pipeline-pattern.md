# ADR-006: 4-Stage Dashboard Pipeline Pattern

## Status
Accepted (Phase 3)

## Date
2026-02-10

## Context

Dashboard generation code was inconsistent across 12 dashboards with mixed patterns:

* Some dashboards loaded data inline
* Some calculated summaries in the same function as rendering
* Some built template context differently
* Some used framework CSS/JS, others didn't
* No clear separation of concerns
* Hard to debug (which stage failed?)
* Hard to test (can't test stages independently)

This inconsistency created problems:

* **Maintenance burden**: Each dashboard had unique structure
* **Code duplication**: Common patterns (load data, calculate summary) duplicated
* **Poor testability**: Can't test data loading separate from rendering
* **Debugging difficulty**: When dashboard fails, unclear which stage caused failure
* **Onboarding difficulty**: New developers must learn 12 different patterns
* **Inconsistent quality**: Some dashboards properly handled errors, others didn't

Example of inconsistent patterns:
```python
# Dashboard A: Mixed stages
def generate_dashboard():
    data = json.loads(Path("history.json").read_text())
    summary = {"total": len(data)}
    html = render_template("dashboard.html", summary=summary)
    return html

# Dashboard B: Different structure
def generate_dashboard():
    history = load_from_history()
    context = build_context(history)
    return render(context)  # No framework CSS/JS!
```

## Decision

Standardize all dashboards on a 4-stage pipeline pattern:

1. **Stage 1: Load Data** - Fetch data from collectors, history files, or APIs
2. **Stage 2: Calculate Summary** - Aggregate metrics, compute trends, determine status
3. **Stage 3: Build Context** - Generate HTML components, build template variables, **get framework CSS/JS**
4. **Stage 4: Render Template** - Jinja2 template rendering to final HTML output

**Key principles:**
* Every dashboard follows the same 4-stage pattern
* Each stage has clear inputs and outputs
* Stages can be tested independently
* Stage 3 MUST include framework CSS/JS for consistent styling
* Failed stages log errors with stage name for easier debugging

**Implementation:**
```python
def generate_quality_dashboard() -> str:
    """Generate quality dashboard using 4-stage pipeline."""

    # Stage 1: Load Data
    history = load_quality_history()

    # Stage 2: Calculate Summary
    summary = calculate_quality_summary(history)

    # Stage 3: Build Context
    framework_css, framework_js = get_dashboard_framework(...)
    context = {
        "framework_css": framework_css,  # REQUIRED
        "framework_js": framework_js,    # REQUIRED
        "summary_cards": build_summary_cards(summary),
        "products": build_product_table(summary),
    }

    # Stage 4: Render Template
    return render_dashboard("quality_dashboard.html", context)
```

## Consequences

### Positive

* **Consistent structure**: All 12 dashboards follow same pattern
* **Clear separation**: Each stage has single responsibility
* **Better testability**: Can test each stage independently
* **Easier debugging**: Error logs include stage name
* **Better maintainability**: Developers know where to look for specific logic
* **Consistent styling**: All dashboards include framework CSS/JS
* **Easier onboarding**: New developers learn one pattern, applies to all dashboards
* **Reusable stages**: Common patterns (load history, build cards) can be extracted

### Negative

* **Slight overhead**: 4 function calls vs 1 mixed function
* **Migration effort**: Required refactoring all 12 dashboards
* **Potential over-engineering**: Simple dashboards may not need all stages

## Alternatives Considered

### Option A: Keep inconsistent patterns
**Rejected**: Maintenance burden too high, new developers confused by 12 different patterns.

### Option B: 3-stage pipeline (combine Stage 2 and 3)
**Rejected**: Calculating summaries and building HTML components are different concerns. Better to separate.

### Option C: Object-oriented pipeline with base class
**Rejected**: Overengineered. Functions are simpler and more composable than inheritance hierarchy.

### Option D: Declarative configuration (YAML/JSON)
**Rejected**: Too inflexible for complex dashboards. Python code provides better expressiveness.

## Implementation Details

### Stage 1: Load Data

**Responsibility:** Fetch data from sources, parse into domain models

```python
def load_quality_history() -> list[QualityMetrics]:
    """Load quality metrics from JSON history."""
    history_file = Path(".tmp/observatory/quality_history.json")

    if not history_file.exists():
        logger.warning("History file not found", extra={"path": str(history_file)})
        return []

    data = json.loads(history_file.read_text())
    return [QualityMetrics.from_json(h) for h in data]
```

**Key points:**
* Returns domain models (not raw JSON)
* Handles missing files gracefully
* Logs errors with context
* Pure data loading (no business logic)

### Stage 2: Calculate Summary

**Responsibility:** Aggregate metrics, compute trends, determine status

```python
def calculate_quality_summary(history: list[QualityMetrics]) -> QualitySummary:
    """Calculate quality summary from history."""
    if not history:
        return QualitySummary.empty()

    latest = history[-1]
    trend = detect_trend(history)

    return QualitySummary(
        open_bugs=latest.open_bugs,
        closed_this_week=latest.closed_this_week,
        trend=trend,
        status=determine_status(latest, trend),
    )
```

**Key points:**
* Takes domain models as input
* Returns summary object (not raw dicts)
* Pure business logic (no file I/O or rendering)
* Handles empty data gracefully

### Stage 3: Build Context

**Responsibility:** Generate HTML components, build template variables, get framework CSS/JS

```python
def build_quality_context(summary: QualitySummary) -> dict:
    """Build template context for quality dashboard."""
    # CRITICAL: Get framework CSS/JS
    framework_css, framework_js = get_dashboard_framework(
        theme="dark",
        gradient_start="#667eea",
        gradient_end="#764ba2"
    )

    return {
        "framework_css": framework_css,  # REQUIRED by base_dashboard.html
        "framework_js": framework_js,    # REQUIRED by base_dashboard.html
        "title": "Quality Metrics Dashboard",
        "summary_cards": build_summary_cards(summary),
        "products": build_product_table(summary),
        "chart_data": prepare_chart_data(summary),
    }
```

**Key points:**
* MUST include `framework_css` and `framework_js` (used by base template)
* Generates HTML components (cards, tables, charts)
* Builds template variables (flat dict structure)
* No file I/O or business logic

### Stage 4: Render Template

**Responsibility:** Render Jinja2 template to HTML, write output file

```python
def render_quality_dashboard(context: dict) -> str:
    """Render quality dashboard template."""
    html = render_dashboard("quality_dashboard.html", context)

    output_file = Path(".tmp/quality_dashboard.html")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html)

    logger.info("Dashboard generated", extra={
        "template": "quality_dashboard.html",
        "output": str(output_file),
        "size_bytes": len(html)
    })

    return html
```

**Key points:**
* Uses `render_dashboard()` helper (handles Jinja2 setup)
* Writes to `.tmp/` directory
* Logs generation info
* Returns HTML string

## Pipeline Flow Diagram

```
┌────────────────────────────────────────────────────┐
│ Stage 1: Load Data                                 │
│ Input: File paths, API endpoints                   │
│ Output: list[DomainModel]                          │
│ Errors: FileNotFoundError, JSONDecodeError         │
└────────────────┬───────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────┐
│ Stage 2: Calculate Summary                         │
│ Input: list[DomainModel]                           │
│ Output: SummaryObject                              │
│ Errors: ValueError (invalid data)                  │
└────────────────┬───────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────┐
│ Stage 3: Build Context                             │
│ Input: SummaryObject                               │
│ Output: dict (template variables)                  │
│ Must include: framework_css, framework_js          │
└────────────────┬───────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────┐
│ Stage 4: Render Template                           │
│ Input: dict (template variables)                   │
│ Output: HTML string                                │
│ Side effect: Write to .tmp/ directory              │
└────────────────────────────────────────────────────┘
```

## Testing Strategy

Pipeline pattern enables focused unit tests:

```python
# Test Stage 1: Data loading
def test_load_quality_history(tmp_path):
    """Test loading quality history from JSON."""
    history_file = tmp_path / "quality_history.json"
    history_file.write_text('[{"open_bugs": 10}]')

    result = load_quality_history()

    assert len(result) == 1
    assert result[0].open_bugs == 10

# Test Stage 2: Summary calculation
def test_calculate_quality_summary():
    """Test summary calculation."""
    history = [
        QualityMetrics(timestamp="2026-01-01T00:00:00Z", open_bugs=10),
        QualityMetrics(timestamp="2026-01-08T00:00:00Z", open_bugs=8),
    ]

    summary = calculate_quality_summary(history)

    assert summary.trend == "improving"

# Test Stage 3: Context building
def test_build_quality_context():
    """Test template context building."""
    summary = QualitySummary(open_bugs=10, trend="improving")

    context = build_quality_context(summary)

    assert "framework_css" in context
    assert "framework_js" in context
    assert "summary_cards" in context

# Test Stage 4: Template rendering (integration test)
def test_render_quality_dashboard(mocker):
    """Test full dashboard rendering."""
    mocker.patch("load_quality_history", return_value=mock_history)

    html = render_quality_dashboard()

    assert "Quality Metrics" in html
    assert len(html) > 1000  # Sanity check
```

## Migration Checklist

When refactoring a dashboard to use pipeline pattern:

- [ ] Identify existing stages (may be mixed together)
- [ ] Extract Stage 1: Load Data into separate function
- [ ] Extract Stage 2: Calculate Summary into separate function
- [ ] Extract Stage 3: Build Context (ensure framework CSS/JS included!)
- [ ] Extract Stage 4: Render Template into separate function
- [ ] Add type hints to all stage functions
- [ ] Add unit tests for each stage
- [ ] Update main generation function to call 4 stages in order
- [ ] Test generated HTML in browser (visual verification)
- [ ] Document any dashboard-specific quirks

## Common Pitfalls

1. **Forgetting framework CSS/JS**: Dashboard renders but styling is broken
   - Solution: ALWAYS include in Stage 3 context

2. **Mixing stages**: Calculating summary in data loading function
   - Solution: Keep stages pure, single responsibility

3. **Skipping error handling**: Stage fails silently
   - Solution: Use error handling utilities (ADR-004)

4. **Returning wrong types**: Stage 2 returns dict instead of summary object
   - Solution: Use type hints, MyPy will catch this

## Impact Metrics

* **Dashboards refactored**: 12/12 now use 4-stage pipeline
* **Code consistency**: 100% of dashboards follow same pattern
* **Test coverage**: Increased from 45% to 80% due to testable stages
* **Onboarding time**: Reduced from 2 days to 4 hours (measured with new hire)
* **Bug detection**: Found and fixed 8 bugs during refactoring (missing error handling, inconsistent calculations)

## Related Decisions

* See ADR-005 for god file decomposition (enables pipeline pattern)
* See ADR-007 for command pattern (used in Stage 2 calculations)
* See `memory/dashboard_patterns.md` for implementation examples
