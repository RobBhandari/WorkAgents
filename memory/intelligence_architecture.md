# Intelligence Platform Architecture

**Status**: Designed 2026-02-22. Implementation begins with Phase A.
**Plan**: `C:\Users\Robin.Bhandari\.claude\plans\encapsulated-hugging-kahan.md`

---

## Agent Team Design

### Orchestrator (Main Claude Session)
**Role**: Plans, coordinates, reviews outputs, integrates modules, ensures quality gates pass.
**Does NOT**: Implement individual modules (delegates to specialized agents).

### Agent A: Data Engineer
**Skill**: `memory/skills/intelligence-ml-forecasting.md` (data sections)
**Owns**:
- `execution/intelligence/feature_engineering.py` — builds Parquet feature store from history JSON
- `execution/intelligence/duckdb_views.py` — analytical views over existing JSON files
**Dependencies**: Must complete before ML agents can start (they read from feature store)

### Agent B: ML/Forecasting Engineer
**Skill**: `memory/skills/intelligence-ml-forecasting.md`
**Owns**:
- `execution/intelligence/forecast_engine.py` — Prophet + ARIMA, P10/P50/P90 bands
- `execution/intelligence/anomaly_detector.py` — Isolation Forest upgrade (replaces z-score)
- `execution/intelligence/change_point_detector.py` — ruptures library
- `execution/intelligence/scenario_simulator.py` — Monte Carlo simulation
- `execution/intelligence/correlation_analyzer.py` — cross-metric lagged correlation
**Dependencies**: Needs Agent A's feature store. Can parallel with Agent C.

### Agent C: Intelligence Layer Engineer
**Skill**: `memory/skills/intelligence-layer.md`
**Owns**:
- `execution/intelligence/risk_scorer.py` — composite risk score (0-100)
- `execution/intelligence/opportunity_scorer.py` — opportunity detection
- `execution/intelligence/insight_generator.py` — template-based insight generation
- `execution/intelligence/alert_engine_predictive.py` — pre-threshold alerts
**Dependencies**: Needs Agent B's forecasts. Can parallel with Agent D.

### Agent D: Dashboard/UX Engineer
**Skill**: `memory/skills/intelligence-dashboard.md`
**Owns**:
- `execution/dashboards/executive_panel.py` — single-pane-of-glass CTO view
- `execution/dashboards/predictive_analytics.py` — forecast + scenario simulator
- `execution/dashboards/components/forecast_chart.py` — Plotly forecast band component
- `execution/dashboards/components/scenario_slider.py` — scenario simulator UI
- `execution/dashboards/components/correlation_heatmap.py`
- `execution/dashboards/components/kpi_card_enhanced.py`
- All corresponding templates in `templates/dashboards/`
**Dependencies**: Can start scaffold in parallel with Agent B; wires real data after Agent C.

### Agent E: LLM/Narrative Engineer
**Skill**: `memory/skills/intelligence-llm-insights.md`
**Owns**:
- `execution/intelligence/narrative_engine.py` — Claude Haiku API integration
- `scripts/generate_intelligence_report.py` — weekly HTML/PDF executive brief
**Dependencies**: Needs Agent C insights. Can parallel with late Phase C.

### Agent F: Security Expert
**Skill**: `memory/skills/intelligence-security-gate.md`
**Role**: Runs BEFORE each phase starts (threat model) and AFTER each phase ends (sign-off).
**Owns**: `memory/security_clearances.md` (audit trail)
**NOT an implementation agent** — a gating agent. Nothing ships without security sign-off.

### Agent G: Architecture Guardian
**Skill**: `memory/skills/intelligence-architecture-standards.md`
**Role**: Reviews every module output against 8-point checklist before merge.
**Owns**: `memory/architecture_log.md` (review log)
**NOT an implementation agent** — a review agent. Nothing ships without architecture sign-off.

### Agent H: Test/QA Engineer
**Skill**: `memory/skills/intelligence-testing.md`
**Owns**:
- `tests/intelligence/conftest.py` — shared fixtures
- `tests/intelligence/test_*.py` — all ML module tests
- Backtesting validation (MAPE checks)
- Model performance tracking (`data/model_performance.json`)
**Can run in parallel**: Tests can be written while implementation is in progress.

---

## Module Dependency Graph

```
JSON History Files
       │
       ▼
feature_engineering.py (Agent A)
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
forecast_engine.py (Agent B)      anomaly_detector.py (Agent B)
change_point_detector.py (B)      correlation_analyzer.py (B)
scenario_simulator.py (B)
       │
       ▼
risk_scorer.py (Agent C)
opportunity_scorer.py (C)
insight_generator.py (C)
alert_engine_predictive.py (C)
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
narrative_engine.py (Agent E)     executive_panel.py (Agent D)
generate_intelligence_report.py   predictive_analytics.py (D)
```

---

## New Files Inventory

### execution/intelligence/ (11 modules)
| File | Agent | Phase |
|---|---|---|
| `__init__.py` | Any | A |
| `feature_engineering.py` | A | B |
| `duckdb_views.py` | A | B |
| `forecast_engine.py` | B | B |
| `anomaly_detector.py` (upgrade) | B | B |
| `change_point_detector.py` | B | B |
| `scenario_simulator.py` | B | C |
| `correlation_analyzer.py` | B | C |
| `risk_scorer.py` | C | B |
| `opportunity_scorer.py` | C | C |
| `insight_generator.py` | C | C |
| `alert_engine_predictive.py` | C | C |
| `narrative_engine.py` | E | C |

### execution/dashboards/ (new + upgrades)
| File | Agent | Phase |
|---|---|---|
| `executive_panel.py` | D | B |
| `predictive_analytics.py` | D | C |
| `components/forecast_chart.py` | D | A |
| `components/scenario_slider.py` | D | C |
| `components/correlation_heatmap.py` | D | C |
| `components/kpi_card_enhanced.py` | D | A |

### execution/domain/
| File | Agent | Phase |
|---|---|---|
| `intelligence.py` | Any | A |

### tests/intelligence/ (mirrors execution/intelligence/)
All owned by Agent H (QA).

---

## Phased Rollout

### Phase A — Week 1-2 (Quick Wins)
**What ships**: Interactive Plotly charts on existing dashboards; emoji severity; root-cause hints on alerts; metric glossary tooltips.
**Security gate**: Threat model before; Bandit scan + XSS review after.
**Architecture gate**: Import + file size + test coverage review.

### Phase B — Week 3-6 (Intelligence Foundation)
**What ships**: Feature store (DuckDB/Parquet), Prophet forecasting, change-point detection, risk scorer, Executive Intelligence Panel.
**Milestone**: CTO can view executive panel with real forecast data.

### Phase C — Week 7-10 (Predictive Platform)
**What ships**: Scenario simulator, correlation heatmap, opportunity scorer, causal inference, LLM insights, predictive alerts.
**Milestone**: Weekly intelligence brief generated automatically.

### Phase D — Week 11-14 (Strategic Intelligence)
**What ships**: Full LLM report, clustering, classification, model performance monitoring, breadcrumb navigation.
**Final security sweep**: Pre-public sweep mirrors 2026-02-22 methodology.

---

## Key Architectural Decisions

| Decision | Rationale |
|---|---|
| DuckDB over PostgreSQL | Zero infrastructure; free; runs in-process; columnar analytics |
| Prophet over ARIMA | Handles seasonality; robust to missing data; better confidence intervals |
| Template-based insights first | No LLM dependency for MVP; add Claude Haiku as upgrade |
| All models retrain weekly | No stale weights; reproducible from feature store; no model server needed |
| Forecasts stored as JSON | Git-friendly; readable; consistent with existing history file pattern |
| Parquet for features | Columnar; fast I/O; DuckDB reads natively; versioned by date |
| Plotly static HTML export | No JS framework; works in existing Jinja2 templates; CDN-delivered |

---

## New .gitignore Additions Required

```gitignore
# Intelligence Platform — auto-generated ML outputs (add to .gitignore)
data/features/
data/forecasts/
data/insights/
```

---

## How to Invoke Agents

When implementing a Phase A/B/C/D task, invoke specialized agents using the Task tool:

```python
# Example: Invoke ML/Forecasting Agent for forecast_engine.py
Task(
    subagent_type="general-purpose",
    description="Implement forecast_engine.py",
    prompt=f"""
    Read memory/skills/intelligence-ml-forecasting.md first.

    Implement execution/intelligence/forecast_engine.py following the patterns in that skill file.

    Requirements:
    - Prophet-based forecasting for quality/security/deployment/flow metrics
    - Outputs: P10/P50/P90 confidence bands at weeks 1, 4, 13, 26
    - Backtesting: MAPE validation on holdout; log to data/model_performance.json
    - Minimum 12 data points; raise ValueError if insufficient
    - Full test suite in tests/intelligence/test_forecast_engine.py

    After implementing:
    - Run: pytest tests/intelligence/test_forecast_engine.py -v
    - Run: bandit execution/intelligence/forecast_engine.py -ll
    - Run: black --check execution/intelligence/forecast_engine.py
    - Report: file size, test count, coverage %, MAPE on synthetic data
    """
)
```

Always invoke Security Expert and Architecture Guardian as review agents after each module:

```python
# Example: Invoke Security Expert for sign-off
Task(
    subagent_type="general-purpose",
    description="Security review forecast_engine.py",
    prompt="""
    Read memory/skills/intelligence-security-gate.md first.

    Review execution/intelligence/forecast_engine.py for security issues.

    Run the full threat model checklist from the skill file.
    Run: bandit execution/intelligence/forecast_engine.py -ll
    Run: git ls-files data/features/ data/forecasts/

    Add sign-off entry to memory/security_clearances.md.
    """
)
```
