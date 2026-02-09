Architecture Overview
=====================

The Engineering Metrics Platform follows a clean 3-layer architecture designed for maintainability, testability, and security.

System Architecture
-------------------

::

   ┌─────────────────────────────────────────────────────────┐
   │                    Presentation Layer                    │
   │  (Dashboards, Reports, Email Notifications)             │
   └────────────────────┬────────────────────────────────────┘
                        │
                        │ Uses domain models
                        │
   ┌────────────────────▼────────────────────────────────────┐
   │                     Domain Layer                         │
   │  (Business Logic, Metrics Models, Pure Python)          │
   └────────────────────┬────────────────────────────────────┘
                        │
                        │ Populated by
                        │
   ┌────────────────────▼────────────────────────────────────┐
   │                  Infrastructure Layer                    │
   │  (Data Collectors, HTTP Client, Config Management)      │
   └──────────────────┬──────────────────┬───────────────────┘
                      │                  │
                      │                  │
         ┌────────────▼──────┐  ┌────────▼────────┐
         │  Azure DevOps     │  │   ArmorCode     │
         │  (Quality + Flow) │  │   (Security)    │
         └───────────────────┘  └─────────────────┘

Layer Responsibilities
----------------------

Infrastructure Layer
~~~~~~~~~~~~~~~~~~~~

**Purpose**: Handle external dependencies, I/O, and configuration.

**Components:**

* ``secure_config.py``: Centralized configuration management
* ``http_client.py``: Secure HTTP client with retries
* ``security_utils.py``: Credential masking, validation
* ``collectors/*.py``: Data fetching from external APIs

Domain Layer
~~~~~~~~~~~~

**Purpose**: Pure business logic and data models.

**Components:**

* ``metrics.py``: Base classes (MetricSnapshot, TrendData)
* ``quality.py``: Bug, QualityMetrics models
* ``security.py``: Vulnerability, SecurityMetrics models
* ``flow.py``: FlowMetrics models

Presentation Layer
~~~~~~~~~~~~~~~~~~

**Purpose**: Transform domain models into user-facing outputs.

**Components:**

* ``dashboards/``: Dashboard generators
* ``dashboards/components/``: Reusable HTML components
* ``reports/``: Email notification delivery

Design Principles
-----------------

Security-First Design
~~~~~~~~~~~~~~~~~~~~~

All external access goes through security wrappers for validation, logging, and retry logic.

Type Safety
~~~~~~~~~~~

All code uses Python 3.11+ type hints validated by MyPy.

Testability
~~~~~~~~~~~

Domain models are pure and easily testable without external dependencies.

See Also
--------

* :doc:`decisions` - Architecture Decision Records
* ``execution/ARCHITECTURE.md`` - Technical architecture doc
