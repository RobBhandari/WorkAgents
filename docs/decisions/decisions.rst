Architecture Decision Records (ADRs)
====================================

This document records significant architectural decisions made during the platform's evolution.

.. note::

   **Comprehensive ADR Documentation**: For detailed Architecture Decision Records documenting Phases 1-3 refactorings, see the `docs/adr/ directory <../adr/README.md>`_.

   The ADRs in this file cover infrastructure decisions (Phases 5-7). For refactoring decisions including:

   * Structured logging (ADR-001)
   * Datetime utilities (ADR-002)
   * Constants extraction (ADR-003)
   * Error handling patterns (ADR-004)
   * God file decomposition (ADR-005)
   * Dashboard pipeline pattern (ADR-006)
   * Command pattern for queries (ADR-007)

   Please refer to the `ADR directory index <../adr/README.md>`_.

ADR-001: Security Wrappers
---------------------------

**Status**: Accepted (Phase 5)

**Date**: 2026-02-07

**Context**

The codebase had 168 direct ``os.getenv()`` calls and 41 ``import requests`` statements, creating:

* **Security risks**: No validation, credentials in logs
* **Reliability issues**: No retry logic, no error handling
* **Maintenance burden**: Scattered configuration access

**Decision**

Create centralized security wrappers:

* ``secure_config.py``: Validated configuration management
* ``http_client.py``: Secure HTTP client with retries
* ``security_utils.py``: Credential masking utilities

**Consequences**

✅ **Positive:**

* All credentials validated at startup
* Automatic credential masking in logs
* Built-in retry logic with exponential backoff
* Centralized error handling
* Easier to add new configuration sources

⚠️ **Negative:**

* Migration effort (30 files updated)
* Slight increase in code verbosity
* New developers must learn wrapper APIs

**Compliance**

Enforced by:

* Pre-commit hook (``check-security-wrappers.py``)
* GitHub Actions CI check (non-blocking warnings)

ADR-002: Type Safety with Python 3.11+
---------------------------------------

**Status**: Accepted (Phase 6)

**Date**: 2026-02-07

**Context**

The codebase had minimal type hints, leading to:

* Runtime errors from type mismatches
* Poor IDE autocomplete
* Difficult refactoring
* Unclear APIs

**Decision**

Adopt Python 3.11+ type hints throughout:

* Use modern syntax (``list[T]``, ``X | None``)
* Enforce with MyPy in CI
* Require type hints for all new domain code
* Gradual adoption for legacy code

**Example**

.. code-block:: python

   # Modern Python 3.11+ syntax
   def calculate_rate(closed: int, total: int) -> float | None:
       if total == 0:
           return None
       return (closed / total) * 100

**Consequences**

✅ **Positive:**

* Caught 30+ bugs during implementation
* Better IDE experience (autocomplete, jump-to-definition)
* Self-documenting code
* Easier onboarding

⚠️ **Negative:**

* Slight verbosity increase
* MyPy learning curve
* Legacy code remains untyped

**Metrics**

* **Domain layer**: 100% type coverage
* **Collectors**: 70% type coverage
* **Legacy code**: <10% type coverage

ADR-003: Jinja2 Templates over F-Strings
-----------------------------------------

**Status**: Accepted (Phase 2)

**Date**: 2025-12-15

**Context**

Original dashboard generation used f-string HTML concatenation:

.. code-block:: python

   html = f"""
   <div class="card">
       <h2>{title}</h2>
       <p>{data}</p>
   </div>
   """

**Problems:**

* XSS vulnerabilities (no escaping)
* Mixing logic and presentation
* Hard to maintain large dashboards
* No syntax highlighting

**Decision**

Migrate to Jinja2 templates:

* Store templates in ``templates/dashboards/``
* Use ``dashboards/renderer.py`` for rendering
* Enable auto-escaping for XSS protection

**Example**

.. code-block:: html+jinja

   {# templates/dashboards/security_dashboard.html #}
   {% extends "dashboards/base_dashboard.html" %}

   {% block content %}
   <div class="summary">
       {% for product in products %}
       <div class="card">
           <h3>{{ product.name }}</h3>
           <p>{{ product.total }} vulnerabilities</p>
       </div>
       {% endfor %}
   </div>
   {% endblock %}

**Consequences**

✅ **Positive:**

* Auto-escaping prevents XSS
* Separation of concerns (HTML vs Python)
* Easier for designers to modify
* Template inheritance reduces duplication
* Syntax highlighting in editors

⚠️ **Negative:**

* Additional dependency (Jinja2)
* Template debugging is harder
* Two-language system (Python + Jinja)

ADR-004: Dataclasses over Pydantic
-----------------------------------

**Status**: Accepted (Phase 2)

**Date**: 2025-12-15

**Context**

Need for type-safe domain models. Two options:

1. **Pydantic**: Full-featured validation, serialization
2. **Dataclasses**: Stdlib, lightweight, Python 3.10+ features

**Decision**

Use Python dataclasses for domain models.

**Rationale:**

* Stdlib (no external dependency)
* Sufficient for our validation needs
* Python 3.10+ ``kw_only`` feature enables flexible field ordering
* Lighter weight (no runtime overhead)
* Better type checking with MyPy

**Example**

.. code-block:: python

   from dataclasses import dataclass
   from .metrics import MetricSnapshot

   @dataclass(kw_only=True)
   class QualityMetrics(MetricSnapshot):
       open_bugs: int
       closed_this_week: int
       net_change: int

**Consequences**

✅ **Positive:**

* Zero external dependencies for domain layer
* Excellent MyPy support
* Minimal runtime overhead
* Familiar to Python developers

⚠️ **Negative:**

* Manual validation logic
* No built-in serialization
* Less feature-rich than Pydantic

**When to reconsider:**

* Need complex validation rules
* Need JSON schema generation
* Need automatic API documentation

ADR-005: GitHub Actions for CI/CD
----------------------------------

**Status**: Accepted (Phase 7)

**Date**: 2026-02-07

**Context**

Need for automated testing and quality checks. Options:

1. **GitHub Actions**: Native, free for public repos
2. **Jenkins**: Self-hosted, flexible
3. **CircleCI**: SaaS, paid

**Decision**

Use GitHub Actions for CI/CD.

**Rationale:**

* Native integration with GitHub
* Free for public repositories
* YAML configuration in repo
* Marketplace with reusable actions
* Dependabot integration

**Implementation**

.. code-block:: yaml

   # .github/workflows/ci-quality-gates.yml
   jobs:
     code-quality:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v4
           with:
             python-version: '3.11'
             cache: 'pip'
         - run: ruff check execution/ tests/
         - run: black --check execution/ tests/

**Consequences**

✅ **Positive:**

* Fast feedback on PRs
* Consistent quality enforcement
* No infrastructure to maintain
* Easy to extend with new checks

⚠️ **Negative:**

* Vendor lock-in to GitHub
* Linux-only runners (free tier)
* Queue times during peak hours

ADR-006: Non-Blocking Quality Checks (Pragmatic)
-------------------------------------------------

**Status**: Accepted (Phase 7)

**Date**: 2026-02-07

**Context**

CI repeatedly failing due to formatting/linting warnings in modular code, blocking forward progress to A-grade.

**Decision**

Make quality checks non-blocking (warnings only):

* Ruff/Black/MyPy: Log warnings, don't fail
* Architecture/Security: Log warnings, don't fail
* **Tests remain strict** (must pass)
* **Security scan remains strict** (must pass)

**Rationale:**

* Unblock progress to Phase 8 (Documentation)
* Quality checks still run and log warnings
* Can fix warnings incrementally
* User decision: "relax CI now → Phase 8 → fix later"

**Implementation**

.. code-block:: yaml

   - name: Run Ruff linter
     run: |
       ruff check execution/domain ... || echo "⚠️ Ruff warnings (non-blocking)"
       echo "✅ Code quality check completed"

**Consequences**

✅ **Positive:**

* Forward progress to A-grade
* Still have visibility into quality issues
* Can fix issues incrementally

⚠️ **Negative:**

* Quality drift risk if warnings ignored
* Must remember to tighten checks later

**Future Plan:**

After Phase 8 completion:

1. Fix all Ruff/Black warnings in modular code
2. Re-enable strict checks (remove ``|| echo``)
3. Update CI summary message

ADR Template
------------

Use this template for future decisions:

.. code-block:: rst

   ADR-XXX: Decision Title
   -----------------------

   **Status**: [Proposed | Accepted | Deprecated | Superseded]

   **Date**: YYYY-MM-DD

   **Context**

   What is the issue or problem? What are the driving forces?

   **Decision**

   What is the decision? What are we doing?

   **Consequences**

   ✅ **Positive:**

   * What are the benefits?

   ⚠️ **Negative:**

   * What are the trade-offs?

   **Alternatives Considered**

   * Option A: Why rejected?
   * Option B: Why rejected?

Refactoring ADRs (Phases 1-3)
-----------------------------

For detailed ADRs documenting code quality and architecture refactorings, see:

* `ADR-001: Structured Logging <../adr/ADR-001-structured-logging.md>`_ (Phase 1)
* `ADR-002: Datetime Utilities <../adr/ADR-002-datetime-utilities.md>`_ (Phase 1)
* `ADR-003: Constants Extraction <../adr/ADR-003-constants-extraction.md>`_ (Phase 1)
* `ADR-004: Error Handling Patterns <../adr/ADR-004-error-handling-patterns.md>`_ (Phase 2)
* `ADR-005: God File Decomposition <../adr/ADR-005-god-file-decomposition.md>`_ (Phase 3)
* `ADR-006: Dashboard Pipeline Pattern <../adr/ADR-006-dashboard-pipeline-pattern.md>`_ (Phase 3)
* `ADR-007: Command Pattern for Queries <../adr/ADR-007-command-pattern-risk-queries.md>`_ (Phase 3)

**Full ADR Index:** `docs/adr/README.md <../adr/README.md>`_

See Also
--------

* ``execution/ARCHITECTURE.md`` - Technical architecture
* ``execution/CONTRIBUTING.md`` - Development guidelines
* :doc:`overview` - Architecture overview
* `ADR Directory <../adr/README.md>`_ - Complete ADR documentation
