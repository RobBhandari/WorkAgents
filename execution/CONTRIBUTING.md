# Contributing Guidelines - Engineering Metrics Platform

## Overview

This document defines the development standards and patterns for the Engineering Metrics Platform. Following these guidelines ensures code quality, security, and maintainability.

---

## Security-First Development

### 1. Configuration Management

**❌ DON'T**: Use `os.getenv()` directly
```python
# BAD - No validation, weak error handling
api_key = os.getenv('ADO_PAT')
if not api_key:
    print("Warning: No API key")
```

**✅ DO**: Use `secure_config` with validation
```python
# GOOD - Validated, type-safe, fail-fast
from secure_config import get_config

config = get_config()
ado_config = config.get_ado_config()  # Raises ConfigurationError if invalid
pat = ado_config.pat
```

**Benefits**:
- Strict validation (format, placeholders, HTTPS enforcement)
- Type-safe dataclasses
- Fail-fast on misconfiguration
- Centralized config management

---

### 2. HTTP Requests

**❌ DON'T**: Import `requests` directly
```python
# BAD - SSL verification can be disabled, no timeout
import requests
response = requests.get(url, verify=False)  # Security vulnerability!
```

**✅ DO**: Use `http_client` wrapper
```python
# GOOD - SSL always verified, timeout enforced
from http_client import get, post

response = get(url)  # verify=True, timeout=30 (automatic)
```

**Benefits**:
- SSL verification enforced (prevent MITM attacks)
- Default timeouts (prevent hanging)
- Consistent error handling
- Audit trail of all HTTP calls

---

### 3. Input Validation

**❌ DON'T**: Use raw user input in queries
```python
# BAD - SQL/WIQL injection vulnerability
project = user_input
query = f"SELECT * FROM WorkItems WHERE [System.TeamProject] = '{project}'"
```

**✅ DO**: Use validation utilities
```python
# GOOD - Validated against whitelist
from security_utils import WIQLValidator

safe_project = WIQLValidator.validate_project_name(user_input)
query = f"SELECT * FROM WorkItems WHERE [System.TeamProject] = '{safe_project}'"
```

**Available validators**:
- `WIQLValidator.validate_project_name()`
- `WIQLValidator.validate_work_item_type()`
- `WIQLValidator.validate_date_iso8601()`
- `HTMLSanitizer.escape_html()`
- `PathValidator.validate_filename()`

---

### 4. HTML Generation

**❌ DON'T**: Build HTML with f-strings
```python
# BAD - XSS vulnerability, hard to maintain
html = f"""
<div class="card">
    <h2>{user_title}</h2>
    <p>{user_content}</p>
</div>
"""
```

**✅ DO**: Use Jinja2 templates
```python
# GOOD - Auto-escaped, maintainable, testable
from dashboards.renderer import render_dashboard

context = {
    'title': user_title,
    'content': user_content
}
html = render_dashboard('dashboards/my_template.html', context)
```

**Template location**: `templates/dashboards/`

**Benefits**:
- Automatic XSS protection (auto-escaping)
- Separation of logic and presentation
- Easy to test and iterate
- Reusable components

---

## Code Organization

### File Naming Conventions

**Production Code** (execution/):
- `ado_*.py` - Azure DevOps integrations
- `armorcode_*.py` - ArmorCode integrations
- `generate_*.py` - Dashboard generators (legacy wrappers)
- `send_*.py` - Email report senders

**Experiments** (execution/experiments/):
- `explore_*.py` - API exploration scripts
- `experiment_*.py` - Prototypes and POCs
- `analyze_*.py` - One-off data analysis

**Tests** (tests/):
- `test_*.py` - Real pytest unit/integration tests
- **NOT** for exploration scripts!

**Archived** (execution/archive/):
- Old versions (`*_v2.py`, `*_old.py`)
- Historical reference only

---

### Package Structure

```
execution/
├── core/               # Infrastructure (config, HTTP, security)
├── domain/             # Domain models (Bug, Vulnerability, Metrics)
├── collectors/         # Data collection from ADO/ArmorCode
├── dashboards/         # Dashboard generation
│   ├── components/    # Reusable HTML components
│   └── framework.py   # Shared CSS/JS
├── reports/            # Email senders
├── experiments/        # Exploration scripts
└── archive/            # Old versions
```

**Import examples**:
```python
# Infrastructure
from execution.config import get_config
from execution.http_client import get, post

# Domain models
from execution.domain.quality import Bug, QualityMetrics
from execution.domain.security import Vulnerability, SecurityMetrics

# Components
from execution.dashboards.components.cards import metric_card
from execution.dashboards.renderer import render_dashboard
```

---

## Development Workflow

### 1. Setup Pre-commit Hooks

```bash
# Install pre-commit (one-time)
pip install pre-commit

# Install git hooks
pre-commit install

# Run manually (optional)
pre-commit run --all-files
```

This will automatically check:
- ✅ Code formatting (black)
- ✅ Linting (ruff)
- ✅ Type checking (mypy)
- ✅ Security wrapper usage
- ✅ Trailing whitespace, YAML syntax, etc.

---

### 2. Running Tests

```bash
# Run all tests with coverage
pytest tests/ -v --cov

# Run specific test file
pytest tests/domain/test_quality.py

# Run with specific marker
pytest -m unit  # Only unit tests
pytest -m "not slow"  # Skip slow tests
```

---

### 3. Type Checking

```bash
# Check type hints
mypy execution/domain  # Strict checking for new code
mypy execution/  # All code (gradual adoption)
```

**Adding type hints**:
```python
from typing import List, Dict, Optional
from execution.domain.security import Vulnerability

def load_vulnerabilities(product_id: str) -> List[Vulnerability]:
    """Load vulnerabilities for a product"""
    # Implementation
```

---

### 4. Code Formatting

```bash
# Format code (automatically run by pre-commit)
black execution/
ruff --fix execution/
```

---

## Writing Tests

### Unit Tests

```python
# tests/domain/test_security.py
from execution.domain.security import Vulnerability

class TestVulnerability:
    def test_is_critical_or_high(self):
        vuln = Vulnerability(
            id="VUL-123",
            title="SQL Injection",
            severity="CRITICAL",
            product="API"
        )
        assert vuln.is_critical_or_high is True
```

### Integration Tests

```python
# tests/collectors/test_armorcode_loader.py
import pytest

@pytest.mark.integration
class TestArmorCodeLoader:
    def test_load_latest_metrics(self, tmp_path):
        # Setup test data
        # Run loader
        # Assert results
```

---

## Common Patterns

### Domain Models (Dataclasses)

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Bug:
    """Represents a bug work item"""
    id: int
    title: str
    state: str
    age_days: int

    @property
    def is_open(self) -> bool:
        """Check if bug is open"""
        return self.state not in ['Closed', 'Resolved']
```

### Dashboard Components

```python
from execution.dashboards.components.cards import metric_card

# Generate reusable metric card
card_html = metric_card(
    title="Open Bugs",
    value="42",
    subtitle="↓ 5 from last week",
    trend="↓"
)
```

### Error Handling

```python
# Specific exceptions, not broad catch-all
try:
    response = get(api_url)
    response.raise_for_status()
except requests.HTTPError as e:
    logger.error(f"API call failed: {e}", exc_info=True)
    raise
except requests.Timeout:
    logger.warning(f"API timeout after 30s: {api_url}")
    return None
```

---

## Deprecation Process

When deprecating old code:

1. **Create new implementation** in proper package location
2. **Update old file** to wrapper that calls new implementation
3. **Add deprecation warning**:
   ```python
   import warnings
   from dashboards.security import generate_security_dashboard as _new

   def main():
       warnings.warn(
           "execution/generate_security_dashboard.py is deprecated. "
           "Use 'from execution.dashboards.security import generate_security_dashboard'",
           DeprecationWarning,
           stacklevel=2
       )
       _new(output_path)
   ```
4. **Update documentation** with migration path
5. **After 1 release cycle**, move old file to `archive/`

---

## Code Review Checklist

Before submitting code:

- [ ] Pre-commit hooks pass
- [ ] Tests added/updated and passing
- [ ] Type hints added to new functions
- [ ] Using `secure_config` instead of `os.getenv()`
- [ ] Using `http_client` instead of `requests`
- [ ] HTML generated with Jinja2 templates (not f-strings)
- [ ] Input validated before use in queries
- [ ] Error handling specific (not bare `except Exception`)
- [ ] Documentation updated (if public API changed)
- [ ] No sensitive data in code/comments

---

## Getting Help

- **Architecture questions**: See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Security utilities**: See [execution/security_utils.py](security_utils.py)
- **Dashboard framework**: See [execution/dashboard_framework.py](dashboard_framework.py)
- **Configuration**: See [execution/secure_config.py](secure_config.py)

---

## Summary: Quick Reference

| Task | Use This | NOT This |
|------|----------|----------|
| Get config | `get_config().get_ado_config()` | `os.getenv('ADO_PAT')` |
| HTTP request | `from http_client import get` | `import requests` |
| HTML generation | Jinja2 templates | f-strings |
| Input validation | `WIQLValidator.validate_*()` | Raw user input |
| Tests | `tests/test_*.py` | `execution/test_*.py` |
| Experiments | `execution/experiments/` | `execution/` |

**Remember**: Security first, test thoroughly, document clearly. 🛡️
