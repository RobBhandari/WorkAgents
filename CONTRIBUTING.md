# Contributing Guidelines

## Import Style

**Always use absolute imports:**
```python
# GOOD
from execution.dashboards.renderer import render_dashboard
from execution.domain.quality import QualityMetrics

# BAD - DO NOT USE
from ..dashboards.renderer import render_dashboard
from .domain.quality import QualityMetrics
```

## Before Committing

Run all quality gates:

```bash
black execution/ tests/
ruff check execution/ tests/
mypy execution/ tests/
pytest tests/ --cov=execution
bandit -r execution/ -ll
```

## Code Organization

- Keep dashboards under 200 lines
- Use domain models for all data structures
- Write tests for all new functionality
- Follow existing patterns for consistency
