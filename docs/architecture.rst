Architecture
============

Introduction
------------

The Engineering Metrics Platform is built on a clean 3-layer architecture with strong typing, security-first design, and modular components. This document covers the technical architecture, package structure, and development practices.

Package Structure
-----------------

The project follows a clean package structure with absolute imports:

- All code lives under the ``execution`` package
- Use absolute imports: ``from execution.module import name``
- No relative imports or sys.path manipulation
- Imports work reliably without PYTHONPATH hacks

Import Pattern
--------------

**Always use absolute imports:**

.. code-block:: python

   # CORRECT
   from execution.dashboards.renderer import render_dashboard
   from execution.domain.quality import QualityMetrics
   from execution.framework import get_dashboard_framework

   # INCORRECT - Never use relative imports
   from ..dashboards.renderer import render_dashboard
   from .domain.quality import QualityMetrics

Development Setup
-----------------

To set up the development environment:

.. code-block:: bash

   git clone https://github.com/RobBhandari/WorkAgents.git
   cd WorkAgents
   pip install -r requirements.txt

Running Code
------------

Execute modules directly:

.. code-block:: bash

   python execution/dashboards/quality.py
   python execution/collectors/ado_quality_metrics.py
   python execution/api/app.py

Layer Architecture
------------------

The platform follows a clean 3-layer architecture:

.. code-block::

   execution/
   ├── core/           # Infrastructure (security wrappers)
   ├── domain/         # Business logic & models (type-safe)
   ├── collectors/     # Data ingestion from external sources
   ├── dashboards/     # HTML report generation
   └── reports/        # Email & notification delivery

**Design Principles:**

* **Security First**: All config via ``secure_config``, all HTTP via ``http_client``
* **Type Safety**: Python 3.11+ type hints, MyPy validation
* **Testability**: Domain models are pure, collectors are isolated
* **Modularity**: Clear boundaries, dependency injection

For more detailed information, see:

* :doc:`architecture/overview` - Detailed layer responsibilities
* :doc:`architecture/decisions` - Architecture Decision Records
