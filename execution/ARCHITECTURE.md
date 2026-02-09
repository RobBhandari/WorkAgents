# Architecture Overview - Engineering Metrics Platform

## System Purpose

The Engineering Metrics Platform is an internal tool for tracking and visualizing software engineering metrics across security, quality, and flow dimensions. It collects data from Azure DevOps and ArmorCode, processes it into actionable insights, and presents it through mobile-responsive HTML dashboards.

---

## High-Level Architecture

### Three-Layer Design

```
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 1: DIRECTIVES                      │
│  Natural language SOPs defining what to do and how          │
│  Location: directives/*.md                                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                 LAYER 2: ORCHESTRATION (AI)                 │
│  Decision making, tool selection, error handling            │
│  (Not part of codebase - external agent)                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│               LAYER 3: EXECUTION (This Codebase)            │
│  Deterministic Python scripts for data collection,          │
│  processing, and dashboard generation                       │
│  Location: execution/                                       │
└─────────────────────────────────────────────────────────────┘
```

**Why this works**: AI agents are probabilistic and make mistakes. Business logic requires consistency. By pushing complexity into deterministic Python code, we get the best of both worlds:
- AI handles decision-making and adaptation
- Python handles reliable execution

---

## Module Structure

### Current Directory Layout

```
c:\DEV\Agentic-Test/
├── execution/                      # All Python code lives here
│   ├── core/                       # Infrastructure utilities
│   │   ├── config.py              # Re-export from secure_config
│   │   ├── http.py                # Re-export from http_client
│   │   └── security.py            # Re-export from security_utils
│   │
│   ├── domain/                     # Domain models (dataclasses)
│   │   ├── metrics.py             # Base metric classes
│   │   ├── quality.py             # Bug, QualityMetrics
│   │   ├── security.py            # Vulnerability, SecurityMetrics
│   │   └── flow.py                # FlowMetrics, LeadTime
│   │
│   ├── collectors/                 # Data collection from external systems
│   │   ├── ado_quality_metrics.py
│   │   ├── ado_flow_metrics.py
│   │   ├── armorcode_weekly_query.py
│   │   └── armorcode_loader.py
│   │
│   ├── dashboards/                 # Dashboard generation
│   │   ├── framework.py           # Shared CSS/JS (mobile-responsive)
│   │   ├── renderer.py            # Jinja2 template rendering
│   │   ├── components/            # Reusable HTML components
│   │   │   ├── cards.py
│   │   │   ├── tables.py
│   │   │   └── charts.py
│   │   ├── security.py            # Security dashboard
│   │   ├── executive.py           # Executive summary
│   │   └── trends.py              # Trends dashboard
│   │
│   ├── reports/                    # Email report senders
│   │   ├── send_armorcode_report.py
│   │   └── send_doe_report.py
│   │
│   ├── experiments/                # Exploration scripts (not production)
│   │   ├── explore_armorcode_api.py
│   │   └── analyze_work_type_breakdown.py
│   │
│   ├── archive/                    # Old versions (reference only)
│   │   ├── armorcode_baseline_v2.py
│   │   └── armorcode_generate_report_old.py
│   │
│   ├── secure_config.py            # Centralized secure configuration
│   ├── http_client.py              # Secure HTTP wrapper
│   ├── security_utils.py           # Input validation utilities
│   ├── dashboard_framework.py      # Shared dashboard CSS/JS
│   └── [legacy root-level scripts] # Backward compatibility wrappers
│
├── templates/                      # Jinja2 HTML templates
│   └── dashboards/
│       ├── base_dashboard.html
│       ├── security_dashboard.html
│       └── executive_summary.html
│
├── tests/                          # Pytest unit/integration tests
│   ├── domain/
│   ├── collectors/
│   └── dashboards/
│
├── data/                           # Persistent data (baselines, history)
│   ├── armorcode_baseline.json    # Immutable baseline (Jan 1, 2026)
│   └── baseline.json              # ADO bugs baseline
│
├── .tmp/                           # Temporary/intermediate files
│   └── observatory/
│       ├── security_history.json
│       ├── quality_history.json
│       └── dashboards/*.html      # Generated dashboards
│
├── directives/                     # Natural language SOPs
├── .env                            # Environment variables (git-ignored)
└── requirements.txt                # Python dependencies
```

---

## Data Flow

### 1. Data Collection

```
┌─────────────────┐       ┌──────────────────┐
│  Azure DevOps   │◄──────┤  ADO Collectors  │
│  (Work Items)   │       │  - Bugs          │
└─────────────────┘       │  - Flow Metrics  │
                          │  - Quality       │
                          └──────────────────┘
                                   │
                                   ▼
┌─────────────────┐       ┌──────────────────┐
│   ArmorCode     │◄──────┤ ArmorCode Query  │
│ (Vulnerabilities│       │   (GraphQL)      │
└─────────────────┘       └──────────────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │  History Files   │
                          │  (.tmp/          │
                          │   observatory/)  │
                          └──────────────────┘
```

**Collectors run on schedule** (daily/weekly via Azure Functions or GitHub Actions)

---

### 2. Dashboard Generation

```
┌──────────────────┐
│ History Files    │
│ (JSON)           │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Data Loaders     │
│ (collectors/)    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Domain Models    │
│ (dataclasses)    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐       ┌──────────────────┐
│ Dashboard Logic  │──────►│ Jinja2 Templates │
│ (dashboards/)    │       │ (templates/)     │
└────────┬─────────┘       └──────────────────┘
         │
         ▼
┌──────────────────┐
│ HTML Files       │
│ (.tmp/           │
│  observatory/    │
│  dashboards/)    │
└──────────────────┘
```

**Dashboards are static HTML** - no server required, can be hosted on Azure Static Web Apps

---

### 3. Report Distribution

```
┌──────────────────┐
│ Generated HTML   │
│ Dashboards       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Email Sender     │
│ (Microsoft Graph │
│  API)            │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Stakeholders     │
│ (Email)          │
└──────────────────┘
```

---

## Key Design Patterns

### 1. Configuration Management

**Pattern**: Centralized, validated configuration with fail-fast behavior

```python
from secure_config import get_config

config = get_config()
ado_config = config.get_ado_config()  # Validates on access
```

**Benefits**:
- No scattered `os.getenv()` calls
- Validation happens once at startup
- Type-safe configuration objects
- Placeholder detection (catches "your_pat_here")

**Implementation**: [secure_config.py](secure_config.py)

---

### 2. Secure HTTP Client

**Pattern**: Wrapper around requests with enforced security

```python
from http_client import get, post

response = get(api_url)  # verify=True, timeout=30 (automatic)
```

**Benefits**:
- SSL verification always enabled
- Consistent timeout handling
- No risk of `verify=False` in codebase
- Single place to add logging/monitoring

**Implementation**: [http_client.py](http_client.py)

---

### 3. Domain Models

**Pattern**: Dataclasses with computed properties

```python
@dataclass
class Bug:
    id: int
    state: str

    @property
    def is_open(self) -> bool:
        return self.state not in ['Closed', 'Resolved']
```

**Benefits**:
- Type-safe data structures
- IDE autocomplete
- Clear contracts
- Easy to test

**Implementation**: [domain/](domain/)

---

### 4. Template-Based Rendering

**Pattern**: Jinja2 templates with auto-escaping

```python
from dashboards.renderer import render_dashboard

html = render_dashboard('dashboards/security.html', context)
```

**Benefits**:
- XSS protection (auto-escaping)
- Separation of logic and presentation
- Easy to iterate on design
- Reusable components

**Implementation**: [dashboards/renderer.py](dashboards/renderer.py), [templates/](../templates/)

---

### 5. Mobile-Responsive Framework

**Pattern**: Shared CSS/JS framework for consistency

```python
from dashboards.framework import get_dashboard_framework

css, js = get_dashboard_framework(
    header_gradient_start='#8b5cf6',
    include_table_scroll=True
)
```

**Benefits**:
- Consistent look & feel across all dashboards
- Mobile-first responsive design
- Dark/light theme toggle
- Touch-friendly interactions

**Implementation**: [dashboard_framework.py](dashboard_framework.py)

---

## Security Architecture

### Input Validation Layer

All external inputs are validated before use:

```
┌──────────────┐
│ User Input   │
│ API Data     │
└──────┬───────┘
       │
       ▼
┌──────────────────────┐
│ Validation Layer     │
│ - WIQLValidator      │
│ - HTMLSanitizer      │
│ - PathValidator      │
└──────┬───────────────┘
       │
       ▼
┌──────────────┐
│ Safe Usage   │
│ in Queries   │
└──────────────┘
```

**Example**:
```python
from security_utils import WIQLValidator

safe_project = WIQLValidator.validate_project_name(user_input)
query = f"WHERE [System.TeamProject] = '{safe_project}'"
```

**Prevents**:
- SQL/WIQL injection
- XSS attacks
- Path traversal
- Command injection

**Implementation**: [security_utils.py](security_utils.py)

---

## Testing Strategy

### Test Pyramid

```
        ┌────────────┐
        │   E2E      │  ← Few, expensive (full dashboard generation)
        └────────────┘
      ┌──────────────┐
      │ Integration  │  ← Some (API mocking, data loaders)
      └──────────────┘
    ┌──────────────────┐
    │   Unit Tests     │  ← Many, fast (domain models, validators)
    └──────────────────┘
```

**Test Structure**:
```
tests/
├── domain/           # Unit tests for dataclasses
├── collectors/       # Integration tests with mocks
├── dashboards/       # Component tests
└── conftest.py       # Shared fixtures
```

**Coverage Target**: >40% (currently ~5%)

---

## Deployment Model

### Local Development

```bash
# Setup
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Run collectors
python execution/ado_quality_metrics.py
python execution/armorcode_weekly_query.py

# Generate dashboards
python execution/generate_security_dashboard.py

# View output
.tmp/observatory/dashboards/security.html
```

### Azure Deployment

**Option 1: Azure Functions** (scheduled collectors)
- Timer triggers (daily/weekly)
- Outputs to Blob Storage
- Email via Microsoft Graph API

**Option 2: GitHub Actions** (CI/CD)
- Scheduled workflows
- Artifacts published to Azure Static Web Apps
- No server required

---

## Performance Characteristics

### Data Collection

- **ADO queries**: 2-5 seconds per project (batched)
- **ArmorCode GraphQL**: 10-30 seconds (pagination)
- **Total collection time**: 1-2 minutes for all metrics

### Dashboard Generation

- **Template rendering**: <100ms per dashboard
- **Data processing**: 200-500ms (percentile calculations)
- **Total generation time**: <5 seconds for all dashboards

### File Sizes

- **History JSON**: 50-200 KB per week
- **Generated HTML**: 100-500 KB per dashboard
- **Static assets**: 0 (inline CSS/JS)

---

## Evolution & Deprecation

### Backward Compatibility Strategy

Old scripts remain as wrappers:

```python
# execution/generate_security_dashboard.py (OLD)
import warnings
from dashboards.security import generate_security_dashboard as _new

def main():
    warnings.warn("Use execution.dashboards.security", DeprecationWarning)
    _new(output_path)
```

This allows gradual migration without breaking existing workflows.

### Refactoring Roadmap

1. **Phase 1 (Weeks 1-2)**: Stop the bleeding
   - Pre-commit hooks ✅
   - Quarantine experiments ✅
   - Archive old versions ✅

2. **Phase 2 (Weeks 3-6)**: Build foundations
   - Package structure
   - Domain models
   - Jinja2 templates
   - Test infrastructure

3. **Phase 3 (Weeks 7-12)**: Reduce complexity
   - Refactor God Objects (<500 lines each)
   - Migrate security wrappers
   - Type hints

4. **Phase 4 (Week 13)**: Verification
   - Integration testing
   - Documentation updates
   - Production deployment

---

## Key Principles

1. **Security First**: Validate inputs, enforce HTTPS, escape outputs
2. **Fail Fast**: Invalid config should crash immediately
3. **Testable**: Pure functions, dependency injection, mocks
4. **Pragmatic**: Incremental improvements, backward compatibility
5. **Type-Safe**: Use dataclasses and type hints for new code
6. **Modular**: Small, focused modules with clear responsibilities

---

## Reference Documents

- **Contributing Guidelines**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Main README**: [../README.md](../README.md)
- **Security Utilities**: [security_utils.py](security_utils.py)
- **Configuration**: [secure_config.py](secure_config.py)
- **Dashboard Framework**: [dashboard_framework.py](dashboard_framework.py)

---

**Last Updated**: 2026-02-07
**Version**: 2.0 (Refactoring in progress)
