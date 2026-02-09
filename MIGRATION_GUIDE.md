# Migration Guide - Dashboard Refactoring v2.0

## Overview

This guide helps you migrate from the legacy monolithic dashboard generators to the new modular architecture. All legacy scripts still work (via deprecation wrappers), so migration can happen gradually.

## What Changed?

### Before (Legacy)
```python
# Monolithic 1833-line file with inline HTML
python execution/generate_security_dashboard.py
```

### After (New)
```python
# Modular 290-line generator with templates
from execution.dashboards.security import generate_security_dashboard
from pathlib import Path

output_path = Path('.tmp/observatory/dashboards/security.html')
generate_security_dashboard(output_path)
```

## Breaking Changes

**None!** All legacy entry points continue to work via backward compatibility wrappers.

## Deprecation Timeline

| Version | Status | Legacy Scripts |
|---------|--------|----------------|
| v2.0 (Current) | ✅ Working | Show DeprecationWarning |
| v2.5 (March 2026) | ⚠️ Warning | Show FutureWarning |
| v3.0 (June 2026) | ❌ Removed | Raise ImportError |

## Migration Checklist

### For Script Users

If you **run** the dashboard scripts:

✅ **No action required** - Scripts work as before, just show a deprecation warning

Optional: Suppress warnings by updating imports:
```python
# Old (still works)
import sys
sys.path.insert(0, 'execution')
from generate_security_dashboard import main
main()

# New (recommended)
from execution.dashboards.security import generate_security_dashboard
generate_security_dashboard()
```

### For Code Importers

If you **import** functions from the dashboard generators:

⚠️ **Action required** - Update your imports

**Security Dashboard:**
```python
# Old
from execution.generate_security_dashboard import generate_html
from execution.generate_security_dashboard import load_history

# New
from execution.dashboards.security import generate_security_dashboard
from execution.collectors.armorcode_loader import ArmorCodeLoader

loader = ArmorCodeLoader()
metrics = loader.load_latest_metrics()
html = generate_security_dashboard()
```

**Executive Summary:**
```python
# Old
from execution.generate_executive_summary import generate_html
from execution.generate_executive_summary import load_all_data

# New
from execution.dashboards.executive import generate_executive_summary
from execution.dashboards.executive import ExecutiveSummaryGenerator

generator = ExecutiveSummaryGenerator()
html = generator.generate()
```

**Trends Dashboard:**
```python
# Old
from execution.generate_trends_dashboard import generate_html
from execution.generate_trends_dashboard import extract_trends_from_quality

# New
from execution.dashboards.trends import generate_trends_dashboard
from execution.dashboards.trends import TrendsDashboardGenerator

generator = TrendsDashboardGenerator(weeks=12)
html = generator.generate()
```

### For Template Customizers

If you **modify** dashboard HTML:

⚠️ **Action required** - Update template files instead of Python strings

**Before:**
```python
# Editing Python file with 1833 lines of HTML strings
html = f"""
<div class="card">
    <h2>{title}</h2>
    ...
"""
```

**After:**
```jinja2
{# Editing Jinja2 template with XSS protection #}
{# templates/dashboards/security_dashboard.html #}
<div class="card">
    <h2>{{ title }}</h2>
    ...
</div>
```

Templates are located in:
- `templates/dashboards/security_dashboard.html`
- `templates/dashboards/executive_summary.html`
- `templates/dashboards/trends_dashboard.html`
- `templates/dashboards/base_dashboard.html` (shared layout)

### For Data Processors

If you **process** dashboard data:

✅ **Improved** - Use domain models for type safety

**Before:**
```python
# Working with dicts and manual validation
metrics = load_data()
if 'critical' in metrics and metrics['critical'] > 0:
    print(f"Critical: {metrics['critical']}")
```

**After:**
```python
# Type-safe domain models with computed properties
from execution.domain.security import SecurityMetrics
from execution.collectors.armorcode_loader import ArmorCodeLoader

loader = ArmorCodeLoader()
metrics = loader.load_latest_metrics()  # Dict[str, SecurityMetrics]

for product, m in metrics.items():
    if m.has_critical:  # Property, not dict key
        print(f"{product}: {m.critical} critical")
```

## New Architecture Benefits

### 1. Domain Models (Type Safety)

```python
from execution.domain.security import SecurityMetrics, Vulnerability
from execution.domain.quality import QualityMetrics, Bug
from execution.domain.flow import FlowMetrics

# Autocomplete, type checking, computed properties
metrics = SecurityMetrics(
    timestamp=datetime.now(),
    total_vulnerabilities=150,
    critical=5,
    high=20
)

print(metrics.critical_high_count)  # 25 (computed property)
print(metrics.has_critical)  # True (boolean property)
```

### 2. Reusable Components

```python
from execution.dashboards.components.cards import metric_card
from execution.dashboards.components.tables import data_table
from execution.dashboards.components.charts import sparkline

# Generate consistent HTML across dashboards
card_html = metric_card(
    title="Critical Vulnerabilities",
    value="5",
    subtitle="Requires immediate attention",
    css_class="rag-red"
)

# Sparklines for trends
sparkline_svg = sparkline(
    values=[100, 95, 92, 88, 85],
    width=200,
    height=60,
    color="#ef4444"
)
```

### 3. Jinja2 Templates (XSS Protection)

```jinja2
{# Automatic HTML escaping prevents injection attacks #}
<div class="product-name">
    {{ product_name }}  {# Auto-escaped #}
</div>

{# Trusted HTML marked as safe #}
<div class="sparkline">
    {{ sparkline_html|safe }}
</div>

{# Template inheritance for consistency #}
{% extends "dashboards/base_dashboard.html" %}

{% block content %}
    {# Your dashboard content #}
{% endblock %}
```

### 4. Clear Package Structure

```
execution/
├── core/              # Infrastructure (secure_config, http_client)
├── domain/            # Domain models (quality, security, flow)
├── collectors/        # Data loading (armorcode_loader, ado_loader)
├── dashboards/        # Dashboard generators
│   ├── components/   # Reusable HTML components
│   ├── security.py
│   ├── executive.py
│   └── trends.py
└── reports/           # Email senders
```

## Migration Examples

### Example 1: Simple Script Execution

**Legacy (still works):**
```bash
python execution/generate_security_dashboard.py
```

**New (recommended):**
```bash
python -m execution.dashboards.security
```

**Python code:**
```python
from execution.dashboards.security import generate_security_dashboard
from pathlib import Path

generate_security_dashboard(Path('.tmp/observatory/dashboards/security.html'))
```

### Example 2: Custom Dashboard

**Legacy approach:**
```python
# Copy-paste 1833 lines, modify HTML strings
def my_custom_dashboard():
    html = f"""
    <!DOCTYPE html>
    <html>... 1833 lines ...
    """
    return html
```

**New approach:**
```python
# Create custom template, use components
from execution.dashboards.renderer import render_dashboard
from execution.dashboards.components.cards import metric_card
from execution.dashboard_framework import get_dashboard_framework

def my_custom_dashboard():
    framework_css, framework_js = get_dashboard_framework()

    context = {
        'framework_css': framework_css,
        'framework_js': framework_js,
        'metric_cards': [
            metric_card("My Metric", "42", "Great!"),
        ]
    }

    return render_dashboard('dashboards/my_custom.html', context)
```

### Example 3: Data Loading

**Legacy:**
```python
import json

with open('.tmp/observatory/security_history.json') as f:
    data = json.load(f)

# Manual parsing, no validation
latest = data['weeks'][-1]
critical = latest['metrics']['critical']
```

**New:**
```python
from execution.collectors.armorcode_loader import ArmorCodeLoader

loader = ArmorCodeLoader()
metrics = loader.load_latest_metrics()  # Type-safe

# Validated domain models
for product, m in metrics.items():
    print(f"{product}: {m.critical} critical")
```

## Testing Your Migration

### 1. Run Legacy Scripts (Verify No Breaking Changes)

```bash
python execution/generate_security_dashboard.py
python execution/generate_executive_summary.py
python execution/generate_trends_dashboard.py
```

All should work with deprecation warnings.

### 2. Compare HTML Output

```bash
# Generate with legacy wrapper
python execution/generate_security_dashboard.py
mv .tmp/observatory/dashboards/security.html security_legacy.html

# Generate with new implementation
python -m execution.dashboards.security
mv .tmp/observatory/dashboards/security.html security_new.html

# Compare (should be nearly identical)
diff security_legacy.html security_new.html
```

### 3. Run Test Suite

```bash
pytest tests/ -v
```

Should have 30+ tests passing with >40% coverage.

### 4. Integration Test

```bash
python execution/refresh_all_dashboards.py
```

All dashboards should generate successfully.

## Common Issues

### Issue: Import Error

```python
ModuleNotFoundError: No module named 'execution.dashboards'
```

**Solution:** Ensure you're running from project root and package structure exists:
```bash
python -c "import execution.dashboards; print('OK')"
```

### Issue: Template Not Found

```python
jinja2.exceptions.TemplateNotFound: dashboards/security_dashboard.html
```

**Solution:** Check template exists:
```bash
ls templates/dashboards/security_dashboard.html
```

### Issue: Deprecation Warning Spam

```python
DeprecationWarning: generate_security_dashboard.py is deprecated!
```

**Solution:** Update imports to new modules or suppress warnings:
```python
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
```

## Getting Help

1. **Architecture docs:** [execution/ARCHITECTURE.md](execution/ARCHITECTURE.md)
2. **Contributing guide:** [execution/CONTRIBUTING.md](execution/CONTRIBUTING.md)
3. **Examples:** See `tests/dashboards/` for usage examples
4. **Original implementations:** Archived in `execution/archive/` for reference

## Summary

| Migration Path | Effort | Timeline |
|----------------|--------|----------|
| **Do Nothing** | None | Works forever (via wrappers) |
| **Suppress Warnings** | 1 line | Immediate |
| **Update Imports** | 5 minutes | Before v3.0 (June 2026) |
| **Use Domain Models** | 1 hour | Optional (recommended) |
| **Customize Templates** | 2 hours | Optional (when needed) |

**Recommendation:** Update imports gradually. Start with new code, migrate old code opportunistically.
