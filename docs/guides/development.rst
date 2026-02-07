Development Guide
=================

Contributing to the Engineering Metrics Platform.

Development Setup
-----------------

1. **Fork and clone the repository:**

.. code-block:: bash

   git clone https://github.com/YOUR_USERNAME/WorkAgents.git
   cd WorkAgents

2. **Create virtual environment:**

.. code-block:: bash

   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows

3. **Install development dependencies:**

.. code-block:: bash

   pip install -r requirements.txt
   pip install pytest pytest-cov ruff black mypy

4. **Install pre-commit hooks:**

.. code-block:: bash

   pip install pre-commit
   pre-commit install

Code Quality Standards
----------------------

This project maintains **A-grade** code quality (85/100) through:

* ✅ Type safety (MyPy)
* ✅ Linting (Ruff)
* ✅ Formatting (Black)
* ✅ Security scanning (Bandit)
* ✅ Test coverage (>40% overall, >90% for new code)

Running Quality Checks
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Lint code
   ruff check execution/ tests/

   # Format code
   black execution/ tests/

   # Type check
   mypy execution/domain execution/dashboards execution/collectors

   # Run tests
   pytest tests/ -v --cov

   # Security scan
   bandit -r execution/domain execution/dashboards/components execution/collectors

Architecture Guidelines
-----------------------

3-Layer Architecture
~~~~~~~~~~~~~~~~~~~~

Follow the clean 3-layer architecture:

.. code-block::

   execution/
   ├── core/           # Infrastructure (shared utilities)
   ├── domain/         # Business logic (pure, testable)
   ├── collectors/     # Data ingestion (external APIs)
   ├── dashboards/     # Presentation (HTML generation)
   └── reports/        # Delivery (email, notifications)

**Rules:**

* Domain models are **pure** (no external dependencies)
* Collectors transform external data → domain models
* Dashboards transform domain models → HTML
* Use dependency injection for testability

Security Wrappers
~~~~~~~~~~~~~~~~~

**Always use security wrappers:**

.. code-block:: python

   # ❌ DON'T
   import os
   import requests
   pat = os.getenv('ADO_PAT')
   response = requests.get(url)

   # ✅ DO
   from execution.secure_config import get_config
   from execution.http_client import get

   config = get_config()
   ado_config = config.get_ado_config()
   response = get(url, headers={'Authorization': f'Bearer {ado_config.pat}'})

Type Hints
~~~~~~~~~~

All new code **must** have type hints:

.. code-block:: python

   # ✅ Good - Modern Python 3.11+ syntax
   def calculate_metric(values: list[float]) -> float | None:
       if not values:
           return None
       return sum(values) / len(values)

   # ❌ Bad - No type hints
   def calculate_metric(values):
       if not values:
           return None
       return sum(values) / len(values)

Testing Guidelines
------------------

Writing Tests
~~~~~~~~~~~~~

Follow the AAA pattern (Arrange, Act, Assert):

.. code-block:: python

   def test_quality_metrics_is_improving():
       """Test is_improving property when net_change is negative"""
       # Arrange
       metrics = QualityMetrics(
           timestamp=datetime.now(),
           project="Test",
           open_bugs=50,
           closed_this_week=10,
           created_this_week=5,
           net_change=-5
       )

       # Act
       result = metrics.is_improving

       # Assert
       assert result is True

Test Coverage Requirements
~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **New domain models**: >90% coverage required
* **New collectors**: >70% coverage required
* **New dashboards**: >60% coverage required
* **Overall project**: >40% (gradually increasing)

Running Tests
~~~~~~~~~~~~~

.. code-block:: bash

   # Run all tests
   pytest tests/ -v

   # Run specific test file
   pytest tests/domain/test_quality.py -v

   # Run with coverage
   pytest tests/ --cov=execution --cov-report=html

   # View coverage report
   open htmlcov/index.html

Git Workflow
------------

Branch Naming
~~~~~~~~~~~~~

.. code-block:: bash

   feature/add-deployment-metrics    # New features
   fix/security-dashboard-crash      # Bug fixes
   refactor/simplify-ado-collector   # Code improvements
   docs/update-api-reference         # Documentation

Commit Messages
~~~~~~~~~~~~~~~

Follow conventional commits:

.. code-block:: bash

   feat: Add deployment frequency metric
   fix: Resolve division by zero in aging_percentage()
   refactor: Extract email sending to separate module
   docs: Document ArmorCode collector API
   test: Add comprehensive tests for FlowMetrics

Pull Request Process
~~~~~~~~~~~~~~~~~~~~~

1. **Create feature branch:**

.. code-block:: bash

   git checkout -b feature/my-feature

2. **Make changes and commit:**

.. code-block:: bash

   git add .
   git commit -m "feat: Add my feature"

3. **Push and create PR:**

.. code-block:: bash

   git push origin feature/my-feature
   # Create PR on GitHub

4. **CI checks must pass:**

   * ✅ Tests pass (162+ tests)
   * ✅ Coverage >40%
   * ⚠️ Ruff/Black/MyPy warnings logged (non-blocking)
   * ✅ Bandit security scan passes

5. **After approval, squash and merge**

Adding New Metrics
------------------

1. **Create domain model** in ``execution/domain/``:

.. code-block:: python

   from dataclasses import dataclass
   from .metrics import MetricSnapshot

   @dataclass(kw_only=True)
   class DeploymentMetrics(MetricSnapshot):
       """Deployment frequency and success metrics"""
       deployments_this_week: int
       successful_deployments: int
       failed_deployments: int

       @property
       def success_rate(self) -> float | None:
           if self.deployments_this_week == 0:
               return None
           return (self.successful_deployments / self.deployments_this_week) * 100

2. **Add tests** in ``tests/domain/test_deployment.py``:

.. code-block:: python

   def test_deployment_metrics_success_rate():
       metrics = DeploymentMetrics(
           timestamp=datetime.now(),
           project="Test",
           deployments_this_week=10,
           successful_deployments=9,
           failed_deployments=1
       )
       assert metrics.success_rate == 90.0

3. **Create collector** in ``execution/collectors/``:

.. code-block:: python

   from execution.domain.deployment import DeploymentMetrics

   def collect_deployment_metrics() -> DeploymentMetrics:
       # Query deployment data from source
       # Transform to domain model
       # Return metrics

4. **Update dashboard** to display new metric

5. **Document** in Sphinx (add to ``docs/api/domain.rst``)

Common Tasks
------------

Regenerate Documentation
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   cd docs
   make clean
   make html
   open _build/html/index.html

Update Dependencies
~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Update all dependencies
   pip install --upgrade -r requirements.txt

   # Update specific package
   pip install --upgrade requests

   # Freeze updated versions
   pip freeze > requirements.txt

Debug Tests
~~~~~~~~~~~

.. code-block:: bash

   # Run with verbose output
   pytest tests/domain/test_quality.py -vv

   # Run single test
   pytest tests/domain/test_quality.py::TestBug::test_bug_is_aging -vv

   # Drop into debugger on failure
   pytest tests/ --pdb

Getting Help
------------

* **Documentation**: https://robbhandari.github.io/WorkAgents/
* **Issues**: https://github.com/RobBhandari/WorkAgents/issues
* **Architecture**: ``execution/ARCHITECTURE.md``
* **Contributing**: ``execution/CONTRIBUTING.md``
