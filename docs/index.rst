Engineering Metrics Platform
============================

**Version:** 2.0.0 | **Status:** A-grade (85/100)

A modern, type-safe engineering metrics platform built on a clean 3-layer architecture.

.. image:: https://img.shields.io/badge/python-3.11+-blue.svg
   :target: https://www.python.org/downloads/
   :alt: Python 3.11+

.. image:: https://img.shields.io/badge/coverage-6%25-yellow
   :alt: Test Coverage

.. image:: https://img.shields.io/badge/grade-A-brightgreen
   :alt: Code Quality

Overview
--------

The Engineering Metrics Platform collects, processes, and visualizes software development metrics from multiple sources:

* **Quality Metrics**: Bug tracking, closure rates, aging analysis (Azure DevOps)
* **Security Metrics**: Vulnerability management, risk scoring (ArmorCode)
* **Flow Metrics**: Lead time, cycle time, WIP tracking (Azure DevOps)
* **Deployment Metrics**: Release frequency, deployment success rates

**Key Features:**

* ✅ Type-safe domain models with full MyPy coverage
* ✅ Security-hardened configuration and HTTP clients
* ✅ Automated dashboards with Jinja2 templates
* ✅ 162 comprehensive unit tests
* ✅ CI/CD with GitHub Actions
* ✅ Modular 3-layer architecture

Quick Start
-----------

Installation
~~~~~~~~~~~~

.. code-block:: bash

   git clone https://github.com/RobBhandari/WorkAgents.git
   cd WorkAgents
   pip install -r requirements.txt

Configuration
~~~~~~~~~~~~~

1. Copy ``.env.template`` to ``.env``
2. Configure your credentials:

.. code-block:: bash

   ADO_PAT=your_azure_devops_pat
   ARMORCODE_API_KEY=your_armorcode_key

Usage Example
~~~~~~~~~~~~~

.. code-block:: python

   from execution.domain.quality import QualityMetrics
   from execution.collectors.ado_quality_metrics import collect_quality_metrics
   from datetime import datetime

   # Collect quality metrics
   metrics = collect_quality_metrics()

   # Analyze
   if metrics.is_improving:
       print(f"✅ Bug count decreasing: {metrics.net_change}")

   if metrics.has_critical_bugs:
       print(f"⚠️ {metrics.p1_count} P1 bugs require attention")

Architecture
------------

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

Documentation
-------------

.. toctree::
   :maxdepth: 2
   :caption: API Reference:

   api/domain
   api/collectors
   api/dashboards
   api/core

.. toctree::
   :maxdepth: 2
   :caption: User Guide:

   guides/getting-started
   guides/configuration
   guides/development

.. toctree::
   :maxdepth: 1
   :caption: Architecture:

   architecture/overview
   architecture/decisions

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
