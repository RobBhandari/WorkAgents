# CLAUDE.md

Guidelines for AI assistants working in this repository.

This repository is developed incrementally with strict engineering discipline.
All AI contributors must follow the rules below before making any changes.

---

# Core Principle

**Never change working code without first understanding existing patterns.**

Before writing new code, AI assistants must verify how the current system works
and ensure new work follows the established architecture.

---

# Required Workflow

AI assistants must follow this order of operations:

1. **Read-only analysis**

   * Understand the existing implementation
   * Identify patterns already used in the repository
   * Verify architecture assumptions

2. **Propose the plan**

   * List files that would change
   * Explain why changes are required
   * Confirm compatibility with existing architecture

3. **Wait for approval**

4. **Provide a patch only**

   * Unified diff format
   * Minimal changes
   * No unrelated edits

---

# Architecture Rules

### Prefer additive changes

Existing behaviour must remain unchanged whenever possible.

### Do not refactor without approval

Refactors should only occur when explicitly requested.

### Follow existing patterns

Before implementing new logic, check how similar functionality is implemented elsewhere.

### Keep modules small and focused

Avoid creating large monolithic modules.

---

# Error Handling

All API endpoints must:

* return appropriate HTTP status codes
* log unexpected errors
* avoid exposing internal stack traces to clients

Typical error handling pattern:

* 401 → authentication failure
* 404 → requested data not available
* 500 → unexpected internal error

---

# Testing Requirements

New backend logic must include tests.

Expected coverage:

* unit tests for internal logic
* API endpoint tests
* edge case validation

Tests must not depend on external services or network access.

Mocks should be used where appropriate.

---

# Security Rules

Authentication must never be bypassed.

Credentials must only come from environment variables loaded from:

.env

Secrets must **never be committed to the repository**.

API authentication is implemented using HTTP Basic.

---

# Observability

Important operations should produce structured logs.

Logging guidelines:

* avoid excessive logging inside tight loops
* log errors with stack traces for debugging
* include contextual fields where useful

---

# Project Context

This repository contains the **Engineering Intelligence Observatory**.

Purpose:

Track engineering health across products using:

* historical metrics
* trend analysis
* signals detection
* dashboards

Primary data flow:

collectors → history files → trends pipeline → API → dashboards

---

# Primary Modules

Collectors:

execution/collectors/

Trend pipeline:

execution/dashboards/trends/

API:

execution/api/

Signals engine:

execution/intelligence/

Frontend prototype:

frontend/

---

# Historical Data

Historical metrics are stored as weekly JSON files:

.tmp/observatory/*_history.json

These files provide the time-series data used by the trends pipeline.

---

# Core Pipeline

Primary orchestration function:

execution/dashboards/trends/pipeline.py

Function:

build_trends_context()

Responsibilities:

* load historical metrics
* calculate trends
* assemble dashboard context
* provide data for API endpoints and dashboards

---

# Existing API Endpoints

Executive trends dashboard:

GET /api/v1/dashboards/executive-trends

Returns:

* metric cards
* active alerts
* timestamp

Authentication: HTTP Basic.

---

# Signals Engine

The system is currently implementing **Signal v1**.

Endpoint:

GET /api/v1/intelligence/signals

Purpose:

Detect meaningful engineering changes such as:

* threshold br
