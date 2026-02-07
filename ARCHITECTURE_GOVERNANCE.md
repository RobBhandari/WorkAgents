# Architecture Governance - Enforcement Mechanisms

## Overview

This document explains how architectural standards are **enforced** for all new code. The refactored architecture isn't just documentation—it's actively enforced through automated checks.

**Goal:** Prevent technical debt from accumulating by catching violations BEFORE they're committed.

---

## Enforcement Layers

### Layer 1: Pre-commit Hooks (Developer Machine) ⚡

**When:** Before every `git commit`
**Speed:** <5 seconds
**Scope:** Changed files only

```bash
# Install once
pip install pre-commit
pre-commit install

# Now runs automatically on every commit
git add myfile.py
git commit -m "Add new feature"  # ← Hooks run here!
```

**What's Checked:**
1. ✅ **Code Formatting** (Black, Ruff)
2. ✅ **Security Wrappers** (No `os.getenv()`, no `import requests`)
3. ✅ **Architecture Patterns** (Templates, domain models, file size)
4. ✅ **Type Hints** (Public functions must have types)
5. ✅ **File Size** (<500 lines per file)

**Example Output:**
```
Check Security Wrappers.....................................Failed
[X] execution/my_new_file.py:42
  Direct os.getenv() usage detected
  -> Use: from secure_config import get_config
  -> Then: config = get_config().get_ado_config()

Check Architecture Patterns.................................Failed
[HTML_IN_PYTHON] execution/dashboards/my_dashboard.py:100
  -> HTML generation detected in Python code. Use Jinja2 templates instead.

[FILE_TOO_LARGE] execution/my_script.py:1
  -> File has 612 lines (max: 500). Consider splitting into modules.
```

---

### Layer 2: GitHub Actions CI (Server-Side) 🔒

**When:** On every push/PR to main branch
**Speed:** 2-5 minutes
**Scope:** All production code

**Why Needed:** Developers can bypass pre-commit hooks (`git commit --no-verify`). CI catches everything.

```yaml
# .github/workflows/ci-quality-gates.yml
✅ Job 1: Code Quality (Ruff + Black)
✅ Job 2: Architecture Governance (Security + Patterns)
✅ Job 3: Type Checking (MyPy)
✅ Job 4: Unit Tests (>40% coverage required)
✅ Job 5: Security Scan (Bandit)
```

**Example PR Check:**
```
❌ Architecture Patterns Failed
   - security-wrappers.py:25 - Direct requests import
   - new_dashboard.py:100 - HTML in f-strings (use templates)

✅ All other checks passed
```

**PR cannot merge until all checks pass.**

---

## Enforced Standards

### 1. Security Wrappers (MANDATORY)

**Rule:** No direct `os.getenv()` or `import requests`

**Bad:**
```python
import os
import requests

api_key = os.getenv('ADO_PAT')  # ❌ REJECTED
response = requests.get(url)     # ❌ REJECTED
```

**Good:**
```python
from execution.core import get_config, get

config = get_config()            # ✅ APPROVED
api_key = config.get_ado_config().pat
response = get(url)              # ✅ APPROVED (SSL verified, timeout enforced)
```

**Why:** Prevents security vulnerabilities (MITM attacks, hanging requests, missing validation)

---

### 2. HTML Generation (MANDATORY)

**Rule:** Use Jinja2 templates, not f-strings

**Bad:**
```python
def generate_dashboard(title, content):
    html = f"""
    <html>
        <h1>{title}</h1>      <!-- ❌ XSS VULNERABLE -->
        <p>{content}</p>
    </html>
    """
    return html  # ❌ REJECTED
```

**Good:**
```python
from execution.dashboards.renderer import render_dashboard

def generate_dashboard(title, content):
    context = {'title': title, 'content': content}
    return render_dashboard('dashboards/my_template.html', context)  # ✅ APPROVED
```

**Why:** Prevents XSS vulnerabilities, separates logic from presentation

---

### 3. Domain Models (MANDATORY for dashboards)

**Rule:** Use type-safe domain models, not dictionaries

**Bad:**
```python
# ❌ REJECTED (in dashboard generators)
bug = {
    'id': 123,
    'title': 'Memory leak',
    'priority': 1
}
```

**Good:**
```python
from execution.domain.quality import Bug

# ✅ APPROVED
bug = Bug(
    id=123,
    title='Memory leak',
    priority=1
)
```

**Why:** Type safety, autocomplete, computed properties, validation

---

### 4. File Size Limits (ENFORCED)

**Rule:** Max 500 lines per file

**Enforcement:**
```python
# Pre-commit hook checks file size
if line_count > 500:
    print(f"❌ File has {line_count} lines (max: 500)")
    print("   Consider splitting into:")
    print("   - Domain model file")
    print("   - Data loader file")
    print("   - Dashboard generator file")
    exit(1)
```

**Why:** Prevents God Objects from forming

---

### 5. Type Hints (ENFORCED for new code)

**Rule:** Public functions must have type hints

**Bad:**
```python
def load_metrics(file_path):  # ❌ Missing types
    return json.load(open(file_path))
```

**Good:**
```python
from pathlib import Path
from typing import Dict, Any

def load_metrics(file_path: Path) -> Dict[str, Any]:  # ✅ Has types
    with open(file_path) as f:
        return json.load(f)
```

**Why:** Catch bugs at development time, not runtime

---

## Bypass Mechanisms (When You Need Them)

### Temporary Bypass (Use Sparingly)

```bash
# Skip pre-commit hooks (emergency only!)
git commit --no-verify

# But CI will still catch violations!
```

### Exclude Specific Files

```yaml
# .pre-commit-config.yaml
exclude: ^(execution/experiments/|tests/)
```

### Architecture Exceptions

If you genuinely need to violate a standard:

1. **Document in ADR** (`docs/adr/ADR-XXX-exception-reason.md`)
2. **Get team approval** (PR review)
3. **Add to exception list** (in hook config)

**Example:**
```python
# execution/special_case.py
# ADR-042: This file uses raw requests because it needs mTLS certificates
# that http_client doesn't support yet. See docs/adr/ADR-042.md
import requests  # noqa: architecture-exception
```

---

## How to Add New Patterns

### 1. Update Hook

Edit `hooks/check-architecture-patterns.py`:

```python
def check_new_pattern(file_path: Path) -> List[ArchitectureViolation]:
    """Check for new anti-pattern"""
    violations = []
    # Your check logic here
    return violations
```

### 2. Update CI

Edit `.github/workflows/ci-quality-gates.yml`:

```yaml
- name: Check New Pattern
  run: |
    python hooks/check-new-pattern.py execution/**/*.py
```

### 3. Update Documentation

Edit `execution/CONTRIBUTING.md` with examples.

---

## Enforcement Timeline

| Code Type | When Enforced | Strictness |
|-----------|---------------|------------|
| **New code** | Immediately | 🔴 Strict |
| **Modified files** | Gradually | 🟡 Warning |
| **Legacy code** | Not enforced | 🟢 Exempt |

**Philosophy:** We don't retroactively enforce on old code (that's what Phase 5-8 is for), but ALL NEW CODE must meet standards.

---

## Developer Workflow

### The Right Way ✅

```bash
# 1. Write code following patterns
vim execution/dashboards/new_feature.py

# 2. Pre-commit hooks check it
git add execution/dashboards/new_feature.py
git commit -m "Add new feature"
# → Hooks run automatically
# → If violations, commit is blocked
# → Fix issues, try again

# 3. CI validates on server
git push origin feature-branch
# → GitHub Actions runs
# → All checks pass
# → Ready for PR review
```

### The Wrong Way ❌

```bash
# 1. Write old-style code
cat > execution/new_dashboard.py << EOF
def generate():
    html = f"<html>{data}</html>"  # XSS vulnerable!
    return html
EOF

# 2. Try to commit
git commit -m "Add dashboard"
# ❌ BLOCKED by pre-commit hook
# [HTML_IN_PYTHON] Use Jinja2 templates instead

# 3. Try to bypass
git commit --no-verify  # Bypass hooks
git push
# ❌ BLOCKED by CI
# Architecture violations detected in PR checks
```

---

## Monitoring & Metrics

### Pre-commit Hook Stats

```bash
# See what's being checked
pre-commit run --all-files --verbose

# Output:
Check Security Wrappers............Passed (142 files)
Check Architecture Patterns........Passed (89 files)
Ruff...................................Passed
Black..................................Passed
```

### CI Dashboard

View enforcement stats in GitHub:
- **Actions** → **CI - Quality Gates**
- See pass/fail rates over time
- Identify common violations

### Coverage Trends

```bash
# Coverage must stay above 40%
pytest --cov=execution --cov-report=term

# Output:
execution/domain/          92%
execution/dashboards/      78%
execution/collectors/      45%
TOTAL:                     65%  ✅ PASS
```

---

## FAQ

### Q: What if pre-commit hooks are slow?

**A:** Hooks only check **changed files**, not entire codebase. Should be <5s.

### Q: Can I disable specific hooks?

**A:** Yes, but must document why:

```bash
SKIP=mypy git commit -m "Skip type checking"
```

### Q: What if CI fails but I need to merge urgently?

**A:**
1. Fix the violation (preferred)
2. Document exception in ADR
3. Get approval from tech lead
4. Create follow-up ticket to fix

### Q: How do I see what standards apply?

**A:** Three sources:
1. Pre-commit hook output (shows violations + fixes)
2. `execution/CONTRIBUTING.md` (guidelines)
3. This document (enforcement details)

### Q: Are experiments/tests enforced?

**A:** No. Only production code in:
- `execution/domain/`
- `execution/dashboards/`
- `execution/collectors/`
- `execution/core/`
- `execution/reports/`

---

## Summary

### ✅ What's Enforced NOW

- Security wrappers (no `os.getenv`, no `requests`)
- Architecture patterns (templates, domain models)
- File size limits (<500 lines)
- Type hints (public functions)
- Code formatting (Black, Ruff)
- Basic security (Bandit scan)
- Test coverage (>40%)

### 🚀 Coming Soon (Phase 5-8)

- Migrate existing code to standards
- Increase type coverage to 80%
- Increase test coverage to 70%
- Add API documentation generation
- Add Architecture Decision Records

### 🎯 Goal

**Prevent technical debt from accumulating while we pay down existing debt.**

New code follows the refactored architecture. Old code gets migrated gradually. No more God Objects!

---

## Getting Started

```bash
# 1. Install hooks
pip install pre-commit
pre-commit install

# 2. Test on all files (optional)
pre-commit run --all-files

# 3. Start coding!
# Hooks will guide you automatically
```

**Remember:** Hooks are your friend! They catch issues instantly, not during code review. 🚀
