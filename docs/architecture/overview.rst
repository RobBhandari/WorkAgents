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
   │  (REST Clients, Collectors, HTTP/2, Config)             │
   │                                                          │
   │  ┌──────────────────────────────────────────────┐      │
   │  │  Async/Await Architecture (asyncio.gather)   │      │
   │  │  - Concurrent project collection             │      │
   │  │  - HTTP/2 connection pooling                 │      │
   │  │  - 3-50x faster than legacy SDK              │      │
   │  └──────────────────────────────────────────────┘      │
   └──────────────────┬──────────────────┬───────────────────┘
                      │                  │
                      │                  │
         ┌────────────▼──────────┐  ┌────▼────────┐
         │  Azure DevOps         │  │ ArmorCode   │
         │  REST API v7.1        │  │ REST API    │
         │  (Quality+Flow+Deploy)│  │ (Security)  │
         └───────────────────────┘  └─────────────┘

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

**Azure DevOps REST API Client** (migrated from SDK):

* ``ado_rest_client.py``: Complete REST API v7.1 client with async/await

  - Work Item Tracking, Build, Git, Test APIs
  - HTTP/2 multiplexing with connection pooling
  - Retry logic, error handling, timeout management
  - 3-50x faster than legacy SDK (concurrent execution)

* ``ado_rest_transformers.py``: REST response transformers

  - Converts REST JSON to SDK-compatible format
  - Maintains backward compatibility for dashboards
  - Zero breaking changes during migration

**Data Collectors** (async/await pattern):

* Quality metrics, flow metrics, deployment metrics
* Ownership, collaboration, risk metrics
* Concurrent project processing via ``asyncio.gather()``
* Historical data loaders for trend analysis

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

Azure DevOps REST API Migration
--------------------------------

**Status**: ✅ Complete (February 2026)

The platform has been fully migrated from the Azure DevOps Python SDK to direct REST API v7.1 calls.

Migration Benefits
~~~~~~~~~~~~~~~~~~

**Security**:

* ✅ Resolved H-1 severity vulnerability from beta SDK dependency
* ✅ Eliminated 10+ transitive dependencies with security risks
* ✅ Direct REST API calls maintained by Microsoft with security patches

**Performance**:

* ✅ **3-50x faster** via async/await concurrent execution
* ✅ HTTP/2 multiplexing for parallel requests
* ✅ Connection pooling reduces overhead
* ✅ Average collection time: 30 min → 2 min (15x improvement)

**Maintainability**:

* ✅ No beta/unmaintained dependencies
* ✅ Full control over HTTP behavior (retries, timeouts, pooling)
* ✅ Easier to debug with REST client source code
* ✅ Backward compatible - zero breaking changes for dashboards

Async Architecture Pattern
~~~~~~~~~~~~~~~~~~~~~~~~~~~

All data collectors use async/await for concurrent execution:

.. code-block:: python

   # Concurrent project collection
   async def collect_all_projects(rest_client, projects):
       tasks = [
           collect_metrics(rest_client, project)
           for project in projects
       ]
       results = await asyncio.gather(*tasks, return_exceptions=True)
       return results

   # HTTP/2 connection pooling
   rest_client = get_ado_rest_client()  # Reuses connections

**Key Components**:

* ``ado_rest_client.py``: Complete REST API v7.1 implementation (650 lines)
* ``ado_rest_transformers.py``: Response transformers for backward compatibility (450 lines)
* ``async_ado_collector.py``: Unified async wrapper for all collectors

Migration Documentation
~~~~~~~~~~~~~~~~~~~~~~~~

For detailed migration patterns and lessons learned:

* **Migration Guide**: ``docs/MIGRATION_GUIDE_SDK_TO_REST.md`` - Step-by-step patterns
* **Deprecated Files**: ``execution/DEPRECATED.md`` - SDK-dependent scripts (not used in production)
* **Performance Benchmarks**: See migration guide for detailed before/after metrics

See Also
--------

* :doc:`decisions` - Architecture Decision Records
* ``execution/ARCHITECTURE.md`` - Technical architecture doc
