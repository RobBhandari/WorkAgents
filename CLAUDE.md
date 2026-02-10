# Security & Architecture Requirements

> **IMPORTANT**: These are STRICT, NON-NEGOTIABLE rules that must be followed for all code changes.

## 🔒 Security Rules

### Input Validation & Sanitization
- **ALWAYS** validate user input at API boundaries before processing
- **NEVER** trust data from external sources (ADO API, user uploads, environment variables) without validation
- **ALWAYS** use parameterized queries for database operations (prevent SQL injection)
- **ALWAYS** sanitize data before rendering in HTML (prevent XSS)

### Error Handling
- **NEVER** use bare `except:` blocks - always catch specific exceptions
- **NEVER** use `except Exception:` without re-raising or logging with context
- **ALWAYS** log security-relevant errors with sufficient context for auditing
- **NEVER** expose internal error details (stack traces, file paths, credentials) to end users
- **ALWAYS** use structured error handling from `execution/errors/`

### Secrets & Credentials
- **NEVER** hardcode credentials, tokens, or API keys in source code
- **ALWAYS** use environment variables for secrets (loaded via `.env`)
- **NEVER** log sensitive data (passwords, tokens, PII)
- **ALWAYS** add credential files to `.gitignore` (already enforced)

### Authentication & Authorization
- **ALWAYS** verify user permissions before sensitive operations
- **ALWAYS** validate Azure AD tokens for protected endpoints
- **NEVER** bypass authentication checks in production code

### Security Scanning
- **ALWAYS** run Bandit security scan before committing: `bandit -r execution/ -ll`
- Fix all HIGH and MEDIUM severity issues immediately

---

## 🏗️ Architecture Patterns

### Clean Architecture (4-Stage Pipeline)

**ALL dashboards MUST follow this pattern:**

```python
# 1. LOAD DATA - Collector → JSON history → Domain models
def load_data(history_path: Path) -> list[MetricSnapshot]:
    data = json.loads(history_path.read_text())
    return [DomainModel.from_json(item) for item in data]

# 2. CALCULATE SUMMARY - Aggregate metrics, compute totals, determine status
def calculate_summary(data: list[MetricSnapshot]) -> dict:
    return {
        "total": len(data),
        "status": "Good" if condition else "Action Needed",
    }

# 3. BUILD CONTEXT - Generate HTML components, build template variables
def build_context(summary: dict) -> dict:
    framework_css, framework_js = get_dashboard_framework(...)
    return {
        "framework_css": framework_css,  # REQUIRED
        "framework_js": framework_js,    # REQUIRED
        "summary_cards": [...],
    }

# 4. RENDER TEMPLATE - Jinja2 template → Final HTML output
def generate_dashboard() -> str:
    context = build_context(...)
    return render_dashboard("template_name.html", context)
```

### Domain Model Requirements

**ALL domain models MUST:**
- Inherit from `MetricSnapshot` (provides `timestamp` field)
- Use `@dataclass(kw_only=True)` decorator
- Implement `from_json(data: dict)` factory method
- Include computed `@property` methods for status and CSS classes

```python
from dataclasses import dataclass
from execution.domain.base import MetricSnapshot

@dataclass(kw_only=True)
class MyMetrics(MetricSnapshot):
    value: int

    @property
    def status(self) -> str:
        return "Good" if self.value > 100 else "Action Needed"

    @property
    def status_class(self) -> str:
        return "good" if self.status == "Good" else "action"

def from_json(data: dict) -> MyMetrics:
    return MyMetrics(
        timestamp=data["timestamp"],
        value=data["value"]
    )
```

### Import Patterns (STRICT)

- **ALWAYS** use absolute imports: `from execution.module import function`
- **NEVER** use relative imports: `from ..module import function`
- **NEVER** use `sys.path` manipulation
- **NEVER** use defensive `try/except ImportError` blocks

### File Size & Complexity Limits

- **Maximum file size**: 500 lines (enforced by CI Architecture Patterns check)
- **Maximum function complexity**: McCabe score < 10
- If file exceeds limits, refactor into smaller modules

---

## ✅ Quality Gates (ALL 6 Must Pass)

**Before EVERY commit, run ALL checks:**

```bash
# Check 1: Black formatting
black --check execution/domain execution/dashboards/components execution/collectors tests/

# Check 2: Ruff linting
ruff check execution/ tests/

# Check 3: Type hints (MyPy)
mypy execution/ tests/

# Check 4: Unit tests (pytest)
pytest tests/ -v

# Check 5: Security scan (Bandit)
bandit -r execution/ -ll

# Check 6: Documentation build (Sphinx)
export PYTHONPATH=".:${PYTHONPATH}" && cd docs && sphinx-build -b html . _build/html
```

**If ANY check fails:**
1. Fix the issue IMMEDIATELY in the SAME commit
2. Do NOT commit until ALL 6 checks pass
3. Do NOT use `--no-verify` or skip hooks

---

## 🧪 Testing Requirements

### Test Coverage
- **ALWAYS** write tests for new features
- **ALWAYS** update tests when modifying function signatures
- Mock external dependencies (file I/O, API calls, `Path.exists()`)

### Test Structure
```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def sample_data() -> dict:
    """Match JSON structure from collectors"""
    return {"timestamp": "2026-01-01T00:00:00Z", "value": 100}

def test_load_data(sample_data):
    """Test data loading from JSON"""
    # Arrange, Act, Assert pattern
    pass

def test_calculate_summary(sample_data):
    """Test summary calculations"""
    pass
```

---

## 🎨 Dashboard Styling Consistency

### Framework Usage (REQUIRED)
- **ALWAYS** call `get_dashboard_framework()` in Stage 3 (Build Context)
- **ALWAYS** include `framework_css` and `framework_js` in template context
- **NEVER** override `.summary-card .value` styles in individual dashboards

### Standard Header Gradient
Use this for new dashboards (consistency across 3/12 dashboards):
```python
header_gradient_start="#667eea"  # purple-blue
header_gradient_end="#764ba2"    # purple
```

### Visual Verification (MANDATORY)
- **ALWAYS** open generated HTML in browser before committing
- **NEVER** rely solely on file size or pytest for dashboard changes
- Verify styling, layout, and interactive features work correctly

---

## 🚀 Deployment & GitHub Actions

### Dashboard Deployment (MANUAL TRIGGER REQUIRED)

**CRITICAL**: `refresh-dashboards.yml` does NOT auto-trigger on push.

**After committing dashboard changes:**
1. Go to: https://github.com/RobBhandari/WorkAgents/actions
2. Click "Refresh Observatory Dashboards"
3. Click "Run workflow" button
4. Select `main` branch
5. Click "Run workflow" to confirm

**OR wait for scheduled run:** Daily at 6 AM UTC

---

## 📁 File Naming Conventions

| Component | Path | Example |
|-----------|------|---------|
| Generator | `execution/dashboards/<name>.py` | `deployment_dashboard.py` |
| Template | `templates/dashboards/<name>_dashboard.html` | `deployment_dashboard.html` |
| Domain | `execution/domain/<domain>.py` | `deployment.py` |
| Collector | `execution/collectors/<service>_<metric>.py` | `ado_deployments.py` |
| Tests | `tests/dashboards/test_<name>.py` | `test_deployment_dashboard.py` |

---

## 🔄 Git Workflow

- **Branch**: `main` (no feature branches)
- **Commit Style**: Conventional commits (`feat:`, `fix:`, `chore:`, `refactor:`)
- **Co-Authored-By**: Always include in commit messages
- **Rebase**: Pull with rebase if remote ahead (`git pull --rebase`)

---

## 🚨 Common Security Vulnerabilities to Avoid

### Command Injection
```python
# ❌ BAD - vulnerable to injection
os.system(f"curl {user_input}")

# ✅ GOOD - use subprocess with list args
subprocess.run(["curl", user_input], check=True)
```

### Path Traversal
```python
# ❌ BAD - allows ../../../etc/passwd
file_path = base_dir / user_input

# ✅ GOOD - validate and resolve
file_path = (base_dir / user_input).resolve()
if not file_path.is_relative_to(base_dir):
    raise SecurityError("Invalid path")
```

### XSS in Templates
```python
# ❌ BAD - raw HTML insertion
{{ user_input | safe }}

# ✅ GOOD - auto-escaped by Jinja2
{{ user_input }}
```

---

## 📚 Additional Resources

- **Dashboard Patterns**: See `memory/dashboard_patterns.md` for detailed examples
- **Security Patterns**: See `memory/security_architecture.md` for comprehensive guide
- **OWASP Top 10**: https://owasp.org/www-project-top-ten/
