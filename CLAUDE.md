# Security & Architecture Requirements

> **IMPORTANT**: These are STRICT, NON-NEGOTIABLE rules that must be followed for all code changes.

## 🎯 Working Conventions

### 🚦 MANDATORY Pre-Flight Checklist (READ THIS FIRST)

**Before making ANY code changes, you MUST complete ALL steps below. This is NON-NEGOTIABLE.**

#### Step 1: Read Documentation
- Read `CLAUDE.md` (this file) completely - verify you understand all rules
- Check `memory/dashboard_patterns.md` for UX conventions (if dashboard work)
- Check `memory/security_architecture.md` for security patterns (if security work)
- Read any other memory files relevant to this task area

#### Step 2: Understand Existing Patterns
- Use Grep to find 2-3 examples of similar existing implementations
- Read those files to understand the current pattern
- Verify dependencies actually used (e.g., httpx vs aiohttp, exact env var names)
- Check import patterns - are they using absolute imports from `execution.`?

#### Step 3: State Your Understanding
**STOP and output this summary BEFORE writing any code:**

```
## Pre-Flight Summary

**What I understand you're asking for:**
- [bullet point summary of the task]

**Existing patterns I found:**
- [file:line_number] - [what pattern this shows]
- [file:line_number] - [what pattern this shows]

**Files I plan to modify:**
- [file1] - [what changes]
- [file2] - [what changes]

**Dependencies/libraries I'll use:**
- [list actual dependencies from requirements.txt or existing code]

**Assumptions I'm making:**
- [list ANY assumptions - if none, say "No assumptions"]

**Questions/Ambiguities:**
- [anything unclear? If nothing, say "No ambiguities"]

Waiting for your confirmation to proceed...
```

#### Step 4: Wait for Approval
- Do NOT proceed until the user confirms your understanding
- If the user says "go ahead", proceed to implementation
- If the user corrects anything, update your understanding and confirm again

---

### Before Implementation
- **ALWAYS** check existing documentation and pattern files (`dashboard_patterns.md`, `CLAUDE.md`, memory files) for established conventions and UX standards
- **NEVER** assume patterns - always verify existing patterns first
- When asked to analyze a document or external input, focus on THAT input - do not explore the codebase unless explicitly asked

### Scope Management
- When asked to make "minimal" or "cosmetic" changes, preserve ALL existing functionality, data, and features
- Do NOT remove or simplify logic unless explicitly asked
- When in doubt, ask before removing anything

### Analysis & Classification
- When analyzing code (deprecated scripts, dependencies, security alerts), do NOT immediately classify items as "critical" or "false positive" without thorough evidence
- Present findings as preliminary and verify before making strong claims

## 🔧 Tech Stack

### HTTP Library
- **ALWAYS** use `httpx` for HTTP requests
- **NEVER** suggest or introduce `aiohttp` as a dependency

### Environment Variables
- Use `ARMORCODE_BASE_URL` (not `ARMORCODE_API_URL`)
- **ALWAYS** verify exact env var names from existing workflow files before referencing them

### Testing
- Use `pytest` for Python tests
- Run full test suite before committing

## ☁️ Azure / Infrastructure

### Azure Configuration
- Do NOT promise immediate results for Azure AD changes
- Admin consent, app registrations often require admin approval and propagation time
- **ALWAYS** caveat with potential delays and verification steps

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

## ✅ Quality Gates (ALL 7 Must Pass)

**Before EVERY commit, run ALL checks:**

```bash
# Check 1: Black formatting
black --check execution/domain execution/dashboards/components execution/collectors scripts/ tests/

# Check 2: Ruff linting
ruff check execution/ scripts/ tests/

# Check 3: Type hints (MyPy)
mypy execution/ scripts/ tests/

# Check 4: Unit tests (pytest)
pytest tests/ -v

# Check 5: Security scan (Bandit)
bandit -r execution/ -ll

# Check 6: Documentation build (Sphinx)
export PYTHONPATH=".:${PYTHONPATH}" && cd docs && sphinx-build -b html . _build/html

# Check 7: Template Security (prevents XSS regressions)
# Verify autoescape is enabled in template_engine.py
grep -q 'autoescape=select_autoescape' execution/template_engine.py || { echo "❌ FAIL: Autoescape not configured"; exit 1; }
# Check for disabled autoescape in templates
! grep -r "autoescape false" templates/ || { echo "❌ FAIL: Found disabled autoescape"; exit 1; }
# Verify no inline scripts with template variables (XSS risk)
! grep -r '<script>.*{{' templates/ || { echo "⚠️  WARNING: Inline scripts with variables - review for XSS"; exit 1; }
echo "✅ Template security check passed"
```

**If ANY check fails:**
1. Fix the issue IMMEDIATELY in the SAME commit
2. Do NOT commit until ALL 7 checks pass
3. Do NOT use `--no-verify` or skip hooks

---

## 🧪 Testing Requirements

### Test-Driven Development (TDD) - MANDATORY

**CRITICAL**: Writing tests is NOT optional. Follow this workflow for ALL code changes:

#### Code + Test Workflow (ALWAYS Follow)

1. **Before Writing Code**:
   - Write the test FIRST (or immediately after writing the function)
   - Think about edge cases, error conditions, and expected behavior
   - Consider: "What would catch this bug if I made a mistake?"

2. **Test Case Requirements**:
   - **Happy path**: Normal operation with valid inputs
   - **Edge cases**: Empty inputs, nulls, boundary values
   - **Error conditions**: Invalid inputs, missing files, network failures
   - **Data structure variations**: Test dictionaries, lists, nested structures
   - **Key vs Value processing**: If processing dicts, test BOTH keys and values

3. **Test File Location**:
   - `execution/` code → `tests/` (mirror directory structure)
   - `scripts/` code → `tests/scripts/` (MUST be tested despite being in scripts/)
   - Utilities in `execution/utils/` → `tests/utils/`

4. **Coverage Requirements**:
   - **New code**: >80% coverage (no exceptions)
   - **Modified code**: Update existing tests + maintain coverage
   - **Bug fixes**: Add regression test that would have caught the bug

5. **Example - What Proper Testing Catches**:
   ```python
   # BAD - No test for dictionary keys
   def transform_data(data):
       return {k: process(v) for k, v in data.items()}  # Only processes VALUES

   # GOOD - Test would catch this
   def test_transform_dictionary_keys():
       data = {"Product A": {"count": 5}}
       result = transform_data(data)
       assert "Product A" not in result  # Would FAIL if keys not processed
       assert "Real Name" in result      # Forces correct implementation
   ```

#### Real Example from This Codebase

**Bug**: De-genericization only processed dictionary VALUES, not KEYS
**Impact**: Product names in keys (like `{"Product G": {...}}`) weren't converted
**Root Cause**: No test for dictionary key processing
**Lesson**: If we'd written this test first, bug would never have existed

**Test that would have caught it**:
```python
def test_translate_dictionary_keys_and_values():
    """Ensure BOTH keys and values are translated in nested dicts"""
    mapping = {"Product G": "Access Diversity"}
    data = {
        "product_breakdown": {
            "Product G": {"status": "Good"},  # Key must be translated
        }
    }
    result = translate_value(data, mapping, {}, "reverse")

    # These assertions would have FAILED with old code
    assert "Access Diversity" in result["product_breakdown"]
    assert "Product G" not in result["product_breakdown"]
```

### Test Coverage
- **ALWAYS** write tests for new features
- **ALWAYS** update tests when modifying function signatures
- Mock external dependencies (file I/O, API calls, `Path.exists()`)
- Run tests locally BEFORE committing: `pytest tests/ -v --cov=execution`

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

## 📊 Dashboard Development Protocol

### For New Dashboard Creation

When asked to create a new dashboard, follow this protocol:

#### Phase 1: Requirements Clarification
**STOP and ask these questions if not already specified:**
- What data source? (ADO API, ArmorCode API, existing collector?)
- What metrics to display? (be specific - don't assume)
- What UX patterns? (expandable rows, heatmaps, simple cards?)
- What status indicators? (RAG badges, numeric thresholds?)

#### Phase 2: Pre-Flight (Use Standard Checklist Above)
- Read `memory/dashboard_patterns.md` for UX conventions
- Grep for similar dashboards (e.g., `execution/dashboards/*_dashboard.py`)
- Verify the 4-stage pipeline pattern in existing dashboards
- Check what components are available in `execution/dashboards/components/`

#### Phase 3: Scope Boundaries
**State this explicitly before coding:**

```
## Dashboard Scope

**Files to CREATE:**
- execution/dashboards/[name]_dashboard.py
- templates/dashboards/[name]_dashboard.html
- execution/domain/[domain].py (if new domain model needed)
- tests/dashboards/test_[name]_dashboard.py

**Files to MODIFY:**
- (list any existing files that need updates, or "None")

**Will NOT create:**
- New collectors (will use existing: [name])
- New framework CSS/JS (will use existing framework)
- New deployment workflows (will use existing refresh-dashboards.yml)

**Visual Design:**
- Header gradient: #667eea → #764ba2 (standard purple)
- Status badges: Use existing status-good/caution/action classes
- Layout: [describe - e.g., "summary cards + expandable detail table"]

Confirm before I proceed?
```

#### Phase 4: Implementation (Follow 4-Stage Pipeline)
1. **Domain Model**: Create in `execution/domain/` inheriting `MetricSnapshot`
2. **Generator**: Create in `execution/dashboards/` following 4-stage pattern
3. **Template**: Create in `templates/dashboards/` extending `base_dashboard.html`
4. **Tests**: Create in `tests/dashboards/` with fixtures matching JSON structure

#### Phase 5: Verification Checklist
**Before showing results, verify:**
- [ ] Generator uses absolute imports from `execution.`
- [ ] Generator calls `get_dashboard_framework()` in build_context
- [ ] Template context includes `framework_css` and `framework_js`
- [ ] Domain model has `from_json()` factory method
- [ ] Domain model has `@property` for status and status_class
- [ ] Tests written with mocked file I/O
- [ ] Run: `pytest tests/dashboards/test_[name]_dashboard.py -v` → ALL PASS
- [ ] Generate the dashboard and visually inspect HTML in browser
- [ ] Check file sizes: generator < 500 lines, domain model < 200 lines

### For Dashboard Modifications

When asked to modify an existing dashboard:

#### Scope Template
**Always start with:**

```
## Modification Scope

**TASK:** [what you're changing]

**Files to MODIFY:**
- [specific files]

**Will PRESERVE:**
- All existing data/metrics
- All existing interactive features
- Current layout structure
- Framework CSS/JS integration

**Will CHANGE ONLY:**
- [be very specific]

**Will NOT:**
- Remove any data columns/metrics unless explicitly asked
- Change other dashboards
- Modify framework files
- Add new dependencies

**Verification Plan:**
- Run tests: pytest tests/dashboards/test_[name].py -v
- Visual check: Open HTML in browser, verify [specific behaviors]
- Compare before/after: Ensure no data loss

Proceed?
```

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

### Pre-Commit Workflow
- **ALWAYS** run the test suite before committing: `pytest tests/ -v`
- **ALWAYS** confirm commit AND push status before ending a session
- All 7 quality gates must pass (Black, Ruff, MyPy, pytest, Bandit, Sphinx, Template Security)

### Commit Standards
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
