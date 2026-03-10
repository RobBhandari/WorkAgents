# MEMORY.md

Current state of the **Engineering Intelligence Observatory** project.

This document allows new AI sessions and developers to quickly understand
what exists, how the system works, and what is currently being built.

---

# Project Purpose

The Engineering Intelligence Observatory tracks engineering health across
products using historical metrics, trend analysis, automated signals,
and dashboards.

The goal is to provide leadership with **clear engineering intelligence**
rather than raw operational metrics.

---

# System Data Flow

Collectors
↓
Historical Metrics (.tmp/observatory)
↓
Trend Pipeline
↓
API Endpoints
↓
Dashboards / Frontend

---

# Historical Data

Metrics are stored as weekly history files.

Location:

.tmp/observatory/

Examples:

quality_history.json
security_history.json
flow_history.json
deployment_history.json
collaboration_history.json
ownership_history.json
risk_history.json
exploitable_history.json

These files provide the time-series data used by the trends pipeline.

---

# Core Trend Pipeline

Primary orchestration function:

execution/dashboards/trends/pipeline.py

Function:

build_trends_context()

Responsibilities:

• load historical metrics
• calculate trends
• generate dashboard metric cards
• assemble API response payloads

This pipeline powers both dashboards and API endpoints.

---

# Working API Endpoints

Executive trends dashboard:

GET /api/v1/dashboards/executive-trends

Returns:

metrics
alerts
timestamp

Authentication: HTTP Basic.

---

# Frontend Prototype

React dashboard prototype located in:

frontend/

Stack:

React
Vite
TypeScript

Currently displays:

• metric cards
• sparkline trend charts
• alerts panel

Frontend currently consumes the executive trends API.

---

# Metric IDs (Executive Trends Payload)

deployment      → build success rate
flow            → lead time P85
security        → code + cloud vulnerabilities
security-infra  → infrastructure vulnerabilities
bugs            → open bug backlog
ownership       → unassigned work percentage
exploitable     → CISA KEV exploitable vulnerabilities
ai-usage        → AI usage dashboard

These IDs appear in the API payload returned by the trends pipeline.

---

# Current Work

Implementing **Signal v1 intelligence layer**.

Goal:

Automatically detect important engineering changes across key metrics.

Example signals:

• threshold breaches
• sustained metric increases
• baseline deviations
• recovery trends

---

# Planned Signals API

Endpoint:

GET /api/v1/intelligence/signals

Returns:

generated_at
signal_count
signals[]

Signals are derived from the metrics returned by the executive trends pipeline.

---

# Next Milestones

1. Complete Signal v1 engine
2. Add Signals panel to React dashboard
3. Introduce Engineering Health score
4. Generate weekly leadership briefing
5. Add AI-generated insights layer

---

# Documentation

AI guidance and repository rules:

CLAUDE.md

System architecture documentation:

docs/architecture.md

These files should be read at the start of any new development session.
