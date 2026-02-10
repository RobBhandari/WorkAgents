# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records documenting significant architectural decisions made during the platform's evolution.

## Overview

ADRs capture the context, decision, and consequences of important architectural choices. They help:

* **Document the "why"**: Explain why we made certain decisions and what alternatives were considered
* **Onboard new developers**: Provide historical context for current architecture
* **Avoid repeating mistakes**: Learn from past decisions and their trade-offs
* **Enable informed changes**: Understand consequences before modifying architecture

## ADR Index

### Phase 1 Refactorings (Foundation)

* **[ADR-001: Structured Logging](ADR-001-structured-logging.md)** - Replace print() statements with Python logging module for production-ready observability
* **[ADR-002: Datetime Utilities](ADR-002-datetime-utilities.md)** - Centralized datetime parsing and calculation to eliminate duplication across 15+ files
* **[ADR-003: Constants Extraction](ADR-003-constants-extraction.md)** - Extract magic numbers into type-safe constants module for maintainability

### Phase 2 Refactorings (Quality)

* **[ADR-004: Error Handling Patterns](ADR-004-error-handling-patterns.md)** - Replace bare `except Exception:` blocks with structured error handling utilities

### Phase 3 Refactorings (Architecture)

* **[ADR-005: God File Decomposition](ADR-005-god-file-decomposition.md)** - Decompose 1,800+ line god files into focused modules following Single Responsibility Principle
* **[ADR-006: Dashboard Pipeline Pattern](ADR-006-dashboard-pipeline-pattern.md)** - Standardize all dashboards on 4-stage pipeline (Load → Calculate → Build → Render)
* **[ADR-007: Command Pattern for Risk Queries](ADR-007-command-pattern-risk-queries.md)** - Extract query logic into reusable, composable query functions

### Infrastructure Decisions (Phases 5-7)

See `docs/architecture/decisions.rst` for infrastructure-related ADRs:

* **ADR-001: Security Wrappers** (Phase 5) - Centralized security wrappers for config and HTTP
* **ADR-002: Type Safety with Python 3.11+** (Phase 6) - Adopt modern type hints and MyPy enforcement
* **ADR-003: Jinja2 Templates over F-Strings** (Phase 2) - Migrate to Jinja2 for XSS protection
* **ADR-004: Dataclasses over Pydantic** (Phase 2) - Use stdlib dataclasses for domain models
* **ADR-005: GitHub Actions for CI/CD** (Phase 7) - Native GitHub Actions for quality gates
* **ADR-006: Non-Blocking Quality Checks** (Phase 7) - Pragmatic approach to CI enforcement

## ADR Format

Each ADR follows this structure:

```markdown
# ADR-XXX: Title

## Status
Accepted | Deprecated | Superseded

## Date
YYYY-MM-DD

## Context
What problem were we solving? What were the driving forces?

## Decision
What did we decide to do?

## Consequences

### Positive
What benefits do we gain?

### Negative
What trade-offs exist?

## Alternatives Considered
What other options did we evaluate and why were they rejected?

## Implementation Details
Technical details, code examples, patterns

## Impact Metrics
Measurable impact (lines changed, files updated, performance)

## Related Decisions
Links to related ADRs
```

## How to Use ADRs

### When to Create an ADR

Create an ADR when making decisions that:

* Affect multiple modules or the entire codebase
* Have significant trade-offs
* Will be hard to reverse later
* Require coordination across team members
* Might be questioned by future developers

### When NOT to Create an ADR

Skip ADRs for:

* Minor implementation details (variable naming, code style)
* Obvious choices with no alternatives
* Temporary workarounds or experiments
* Decisions that only affect a single module

### Reading ADRs

**For new developers:**
1. Start with Phase 1 ADRs to understand foundation decisions
2. Read Phase 2-3 ADRs to understand code organization patterns
3. Refer to specific ADRs when working on related modules

**For experienced developers:**
1. Review ADRs before making significant architectural changes
2. Reference ADRs in code reviews to ensure consistency
3. Update or supersede ADRs when decisions change

## ADR Lifecycle

1. **Proposed**: Under discussion, not yet implemented
2. **Accepted**: Decision made and implemented
3. **Deprecated**: No longer recommended, but code still exists
4. **Superseded**: Replaced by newer decision (link to replacement ADR)

## Contributing

When adding new ADRs:

1. Use the next available ADR number
2. Follow the ADR template format
3. Include concrete examples and code snippets
4. Document measurable impact when possible
5. Link to related ADRs and code
6. Update this README.md index

## References

* [Architecture Decision Records (ADR) by Michael Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
* [ADR GitHub Organization](https://adr.github.io/)
* [Markdown Architectural Decision Records (MADR)](https://adr.github.io/madr/)

## Quick Links

* [Full Architecture Documentation](../architecture/overview.rst)
* [Infrastructure ADRs](../architecture/decisions.rst)
* [Development Guidelines](../../CONTRIBUTING.md)
* [Project README](../../README.md)
