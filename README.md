# Agentic 3-Layer Architecture

[![CI Quality Gates](https://github.com/RobBhandari/WorkAgents/actions/workflows/ci-quality-gates.yml/badge.svg)](https://github.com/RobBhandari/WorkAgents/actions/workflows/ci-quality-gates.yml)
[![Dashboard Refresh](https://github.com/RobBhandari/WorkAgents/actions/workflows/refresh-dashboards.yml/badge.svg)](https://github.com/RobBhandari/WorkAgents/actions/workflows/refresh-dashboards.yml)
[![Test Coverage](https://img.shields.io/badge/coverage-6%25-yellow)](htmlcov/index.html)
[![Code Quality](https://img.shields.io/badge/grade-B+-blue)](#)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

A robust system for AI agent orchestration that separates concerns into three layers: Directives (what to do), Orchestration (decision making), and Execution (deterministic work).

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/RobBhandari/WorkAgents.git
   cd WorkAgents
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run tests:
   ```bash
   pytest tests/ -v
   ```

### Running Dashboards

Generate dashboards using module execution:

```bash
python execution/dashboards/quality.py
python execution/dashboards/security_enhanced.py
python execution/dashboards/deployment.py
```

### Architecture

- `execution/dashboards/` - Dashboard generators (use absolute imports)
- `execution/domain/` - Type-safe domain models
- `execution/collectors/` - Data collection from APIs
- `execution/framework/` - UI framework (CSS/JS)
- `execution/security/` - Security validators

## Architecture Overview

This system is designed to maximize reliability when working with AI agents. LLMs are probabilistic, but business logic requires consistency. This architecture solves that mismatch.

### The 3 Layers

**Layer 1: Directive (What to do)**
- Natural language SOPs written in Markdown
- Located in [`directives/`](directives/)
- Define goals, inputs, tools, outputs, and edge cases
- Instructions like you'd give a mid-level employee

**Layer 2: Orchestration (Decision making)**
- The AI agent layer (Claude, GPT, etc.)
- Reads directives, calls execution tools, handles errors
- Makes intelligent routing decisions
- Updates directives with learnings

**Layer 3: Execution (Doing the work)**
- Deterministic Python scripts in [`execution/`](execution/)
- Handle API calls, data processing, file operations
- Reliable, testable, fast
- Use environment variables from [.env](.env)

### Why This Works

If you let the AI do everything itself, errors compound:
- 90% accuracy per step = 59% success over 5 steps

The solution: Push complexity into deterministic code. The AI focuses only on decision-making.

## Quick Start

### 1. Setup Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate it
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Edit [`.env`](.env) and add your API keys:

```bash
OPENAI_API_KEY=your_actual_key_here
ANTHROPIC_API_KEY=your_actual_key_here
```

### 3. Run an Example

Try the website scraping example:

```bash
python execution/scrape_single_site.py "https://example.com"
```

Results will be saved to `.tmp/scraped_data_[timestamp].json`

## Directory Structure

```
Agentic-Test/
├── .tmp/                           # Temporary/intermediate files (git-ignored)
├── directives/                     # Markdown SOPs
│   ├── _template.md               # Template for new directives
│   └── scrape_website.md          # Example directive
├── execution/                      # Python scripts (modular architecture)
│   ├── core/                      # Infrastructure (config, HTTP, security)
│   ├── domain/                    # Domain models (Bug, Vulnerability, Metrics)
│   ├── collectors/                # Data collection (ADO, ArmorCode)
│   ├── dashboards/                # Dashboard generators
│   │   ├── components/           # Reusable HTML components
│   │   ├── security.py           # Security dashboard (290 lines)
│   │   ├── executive.py          # Executive summary (350 lines)
│   │   └── trends.py             # Trends dashboard (450 lines)
│   ├── reports/                   # Email senders
│   ├── experiments/               # Exploration scripts
│   └── archive/                   # Old versions
├── templates/                      # Jinja2 templates
│   └── dashboards/                # Dashboard HTML templates
├── tests/                          # Pytest test suite
│   ├── domain/                    # Domain model tests
│   └── dashboards/                # Dashboard tests
├── .env                           # Environment variables (git-ignored)
├── .gitignore                     # Git exclusions
├── requirements.txt               # Python dependencies
├── AGENTS.md                      # Full architecture documentation
├── CONTRIBUTING.md                # Development guidelines
├── MIGRATION_GUIDE.md             # v2.0 refactoring guide
└── README.md                      # This file
```

## Creating New Directives

1. Copy [`directives/_template.md`](directives/_template.md)
2. Fill in the sections:
   - **Goal**: What does this accomplish?
   - **Inputs**: What data is needed?
   - **Tools/Scripts**: Which scripts to call?
   - **Outputs**: What gets produced?
   - **Edge Cases**: What can go wrong?
3. Save with a descriptive name (e.g., `process_data.md`)

## Creating New Execution Scripts

1. Copy [`execution/_template.py`](execution/_template.py)
2. Implement your logic following the template structure:
   - Load environment variables with `dotenv`
   - Set up logging
   - Parse command-line arguments with `argparse`
   - Add proper error handling
   - Return structured outputs
3. Test thoroughly before using in production
4. Document in the corresponding directive

## Operating Principles

### 1. Check for Tools First
Before writing a new script, check `execution/` directory per your directive. Only create new scripts if none exist.

### 2. Self-Anneal When Things Break
When errors occur:
1. Read error message and stack trace
2. Fix the script and test again
3. Update the directive with learnings
4. System is now stronger

Example: Hit an API rate limit → investigate API → find batch endpoint → rewrite script → test → update directive

### 3. Update Directives as You Learn
Directives are living documents. When you discover:
- API constraints or quirks
- Better approaches
- Common errors
- Timing expectations

Update the directive! But don't overwrite without asking unless explicitly instructed.

## Google OAuth Setup

If you need Google Sheets, Slides, or other Google APIs:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the APIs you need (Sheets, Slides, Drive, etc.)
4. Create OAuth 2.0 credentials
5. Download credentials as `credentials.json` in project root
6. First run will prompt for authorization and create `token.json`

Both files are in [`.gitignore`](.gitignore) to keep credentials safe.

## File Organization Best Practices

### Deliverables vs Intermediates

**Deliverables**: Cloud-based outputs accessible to users
- Google Sheets
- Google Slides
- Database records
- External APIs

**Intermediates**: Temporary files needed during processing
- All go in `.tmp/` directory
- Never committed to Git
- Can be deleted and regenerated

**Key principle**: Local files are only for processing. Deliverables live in cloud services where users can access them.

## Example Workflow

1. User requests: "Scrape competitor websites and create a summary"

2. AI agent reads `directives/scrape_website.md`

3. Agent determines inputs needed and calls:
   ```bash
   python execution/scrape_single_site.py "https://competitor1.com"
   python execution/scrape_single_site.py "https://competitor2.com"
   ```

4. Scripts save data to `.tmp/`

5. Agent processes data and creates deliverable (e.g., Google Sheet)

6. If errors occur:
   - Agent fixes the script
   - Tests again
   - Updates directive with learnings

## Troubleshooting

### Import Errors
Make sure virtual environment is activated and dependencies are installed:
```bash
pip install -r requirements.txt
```

### Missing API Keys
Check [`.env`](.env) file has your actual API keys (not placeholders)

### Permission Errors
Ensure `.tmp/` directory exists and is writable:
```bash
mkdir .tmp
```

### Rate Limiting
Scripts include exponential backoff for rate limits. If issues persist, check the directive for timing guidance.

## Best Practices

1. **Always use execution scripts** - Don't let AI do complex operations directly
2. **Log everything** - Scripts save logs to `.tmp/` for debugging
3. **Update directives** - Document learnings as you go
4. **Test scripts independently** - Ensure they work before using in workflows
5. **Use version control** - Commit working scripts and directives
6. **Keep .tmp/ clean** - Intermediate files are regenerated, don't rely on them

## Contributing

When adding new capabilities:

1. Create the execution script first
2. Test it thoroughly
3. Create the directive documenting how to use it
4. Add any new dependencies to `requirements.txt`
5. Update this README if needed

## ArmorCode Vulnerability Tracking

A complete system for tracking HIGH and CRITICAL vulnerabilities with 70% reduction goal tracking.

### Quick Start

1. **Get API Key**: ArmorCode UI → Manage → Integrations → ArmorCode API → Create New Key
2. **Configure** [`.env`](.env):
   ```bash
   ARMORCODE_API_KEY=your_api_key_here
   ARMORCODE_PRODUCTS=Product1,Product2
   ARMORCODE_EMAIL_RECIPIENTS=your_email@company.com
   ```
3. **Discover Products**:
   ```bash
   python execution/armorcode_list_products.py
   ```
4. **Create Baseline** (one-time, Jan 1 2026 snapshot):
   ```bash
   python execution/armorcode_baseline.py
   ```
5. **Run Full Report**:
   ```bash
   cd execution
   run_armorcode_report.bat
   ```

### What It Does

- **Baseline**: Immutable snapshot of vulnerabilities on 2026-01-01
- **Goal**: 70% reduction by 2026-06-30
- **Tracking**: Compares current state to baseline, shows progress %
- **Reports**: HTML report with executive summary, trend chart, vulnerability table
- **Delivery**: Automated email with HTML attachment via Microsoft Graph API
- **Scheduling**: Windows Task Scheduler for recurring reports

### Files Created

- **Directive**: [directives/armorcode_vulnerabilities.md](directives/armorcode_vulnerabilities.md)
- **Scripts**:
  - [execution/armorcode_list_products.py](execution/armorcode_list_products.py) - Product discovery
  - [execution/armorcode_baseline.py](execution/armorcode_baseline.py) - Baseline creation
  - [execution/armorcode_query_vulns.py](execution/armorcode_query_vulns.py) - Query & comparison
  - [execution/armorcode_report_to_html.py](execution/armorcode_report_to_html.py) - HTML generation
  - [execution/send_armorcode_report.py](execution/send_armorcode_report.py) - Email delivery
  - [execution/run_armorcode_report.bat](execution/run_armorcode_report.bat) - Full workflow

### Key Features

- **REST API Direct**: No SDK dependency, uses `requests` library
- **Smart Endpoint Discovery**: Tries multiple API endpoints automatically
- **Historical Tracking**: Builds trend data over time
- **Immutable Baseline**: Prevents accidental overwrites
- **Progress Metrics**: Shows reduction %, progress to goal %, timeline

See [directives/armorcode_vulnerabilities.md](directives/armorcode_vulnerabilities.md) for complete documentation.

## Engineering Metrics Dashboard System

A comprehensive metrics platform for tracking engineering health across quality, security, flow, deployment, collaboration, and ownership dimensions.

### Architecture (v2.0 - Refactored)

The dashboard system has been refactored from monolithic scripts (4,667 lines) to a modular architecture (1,090 lines):

**Domain Models** - Type-safe data structures:
```python
from execution.domain.security import SecurityMetrics
from execution.domain.quality import QualityMetrics
from execution.domain.flow import FlowMetrics

# Autocomplete, validation, computed properties
metrics = SecurityMetrics(critical=5, high=20)
print(metrics.critical_high_count)  # 25 (computed)
print(metrics.has_critical)  # True (property)
```

**Reusable Components**:
```python
from execution.dashboards.components.cards import metric_card
from execution.dashboards.components.charts import sparkline

card = metric_card("Critical Vulnerabilities", "5", "High priority")
chart = sparkline([100, 95, 90, 85], width=200, height=60)
```

**Jinja2 Templates** - XSS-safe rendering:
```python
from execution.dashboards.renderer import render_dashboard

context = {'title': 'Dashboard', 'metrics': metrics}
html = render_dashboard('dashboards/security_dashboard.html', context)
```

### Available Dashboards

1. **Security Dashboard** - ArmorCode vulnerability tracking
   ```bash
   python -m execution.dashboards.security
   ```

2. **Executive Summary** - High-level health overview
   ```bash
   python -m execution.dashboards.executive
   ```

3. **Trends Dashboard** - 12-week historical trends
   ```bash
   python -m execution.dashboards.trends
   ```

### Legacy Scripts (Backward Compatible)

All original entry points still work via deprecation wrappers:
```bash
python execution/generate_security_dashboard.py      # Still works
python execution/generate_executive_summary.py       # Still works
python execution/generate_trends_dashboard.py        # Still works
```

See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for migration details.

### Key Features

- **Type Safety**: Domain models with dataclasses
- **XSS Protection**: Auto-escaped Jinja2 templates
- **Reusable Components**: Cards, tables, charts
- **Mobile Responsive**: Works on all devices
- **Dark Mode**: Automatic theme switching
- **70% Reduction Tracking**: Progress toward security/quality goals
- **Burn Rate Analysis**: Velocity metrics and forecasting
- **Historical Trends**: 12-week sparklines with week-over-week changes

### Refactoring Results

| Dashboard | Before | After | Reduction |
|-----------|--------|-------|-----------|
| Security | 1,833 lines | 290 lines | 84% |
| Executive | 1,483 lines | 350 lines | 76% |
| Trends | 1,351 lines | 450 lines | 67% |
| **Total** | **4,667 lines** | **1,090 lines** | **77%** |

## Additional Resources

- Full architecture details: [AGENTS.md](AGENTS.md)
- Development guidelines: [execution/CONTRIBUTING.md](execution/CONTRIBUTING.md)
- Architecture overview: [execution/ARCHITECTURE.md](execution/ARCHITECTURE.md)
- Migration guide (v2.0): [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- Directive template: [directives/_template.md](directives/_template.md)
- Script template: [execution/_template.py](execution/_template.py)
- Example directive: [directives/scrape_website.md](directives/scrape_website.md)
- Example script: [execution/scrape_single_site.py](execution/scrape_single_site.py)
- ArmorCode tracking: [directives/armorcode_vulnerabilities.md](directives/armorcode_vulnerabilities.md)

## Summary

You (the AI agent) sit between human intent (directives) and deterministic execution (Python scripts).

Your role:
- Read instructions from directives
- Make intelligent decisions
- Call execution tools in the right order
- Handle errors gracefully
- Continuously improve the system

**Be pragmatic. Be reliable. Self-anneal.**
