Logging Guide
=============

The platform uses structured logging for production-grade observability.

Why Structured Logging?
------------------------

**Before** (print statements):

.. code-block:: python

   print(f"[INFO] Loading security data for week ending: {week_ending}")
   print(f"[INFO] Found {len(products)} products")

**Problems:**

* Not machine-readable
* No log levels
* Can't filter or search easily
* No context (timestamp, module, etc.)

**After** (structured logging):

.. code-block:: python

   logger.info(
       "Loading security data",
       extra={
           "week_ending": week_ending,
           "product_count": len(products)
       }
   )

**Benefits:**

* ✅ Machine-readable JSON
* ✅ Searchable fields (product_count, week_ending)
* ✅ Automatic context (timestamp, module, level)
* ✅ Log levels (DEBUG, INFO, WARNING, ERROR)
* ✅ Integration with log aggregation tools

Quick Start
-----------

Basic Usage
~~~~~~~~~~~

.. code-block:: python

   from execution.core.logging_config import get_logger

   logger = get_logger(__name__)

   # Simple message
   logger.info("Starting data collection")

   # With context
   logger.info(
       "Metrics collected",
       extra={
           "project": "MyApp",
           "bug_count": 42,
           "duration_ms": 1234
       }
   )

   # Error with exception
   try:
       risky_operation()
   except Exception as e:
       logger.error("Operation failed", exc_info=True, extra={"error": str(e)})

Log Levels
~~~~~~~~~~

.. code-block:: python

   logger.debug("Detailed diagnostic info")      # DEBUG: Verbose details
   logger.info("Normal operation")               # INFO: Routine events
   logger.warning("Unexpected but handled")      # WARNING: Potential issues
   logger.error("Error occurred")                # ERROR: Failures
   logger.critical("System down")                # CRITICAL: Severe failures

Configuration
-------------

Setup Logging
~~~~~~~~~~~~~

.. code-block:: python

   from execution.core.logging_config import setup_logging

   # Development (human-readable console)
   setup_logging(level="DEBUG", json_output=False)

   # Production (JSON to file)
   setup_logging(
       level="INFO",
       log_file=Path(".tmp/logs/app.log"),
       json_output=True
   )

Output Formats
~~~~~~~~~~~~~~

**Human-Readable (Console)**:

.. code-block:: text

   2026-02-07 16:30:45 | INFO     | execution.collectors.armorcode_loader | Loading security data
   2026-02-07 16:30:46 | WARNING  | execution.collectors.armorcode_loader | Found 2 products with critical vulnerabilities

**JSON (Production)**:

.. code-block:: json

   {
       "timestamp": "2026-02-07T16:30:45Z",
       "level": "INFO",
       "logger": "execution.collectors.armorcode_loader",
       "message": "Loading security data",
       "module": "armorcode_loader",
       "function": "load_latest_metrics",
       "line": 92,
       "week_ending": "2026-02-01",
       "product_count": 5
   }

Migration Guide
---------------

Replacing print()
~~~~~~~~~~~~~~~~~

**Before:**

.. code-block:: python

   print(f"[INFO] Processing {count} items")
   print(f"[ERROR] Failed to load file: {filename}")

**After:**

.. code-block:: python

   logger.info("Processing items", extra={"count": count})
   logger.error("Failed to load file", extra={"filename": filename})

Replacing Exception Printing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Before:**

.. code-block:: python

   except Exception as e:
       print(f"[ERROR] Unexpected error: {e}")
       traceback.print_exc()

**After:**

.. code-block:: python

   except Exception as e:
       logger.error("Unexpected error", exc_info=True, extra={"error": str(e)})

Context Fields
~~~~~~~~~~~~~~

Add relevant context to make logs searchable:

.. code-block:: python

   # Quality metrics
   logger.info(
       "Quality metrics collected",
       extra={
           "project": project_name,
           "open_bugs": metrics.open_bugs,
           "net_change": metrics.net_change,
           "is_improving": metrics.is_improving
       }
   )

   # Performance tracking
   logger.info(
       "Dashboard generated",
       extra={
           "dashboard_name": "security",
           "duration_ms": duration,
           "product_count": len(products)
       }
   )

Best Practices
--------------

Use Appropriate Log Levels
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # DEBUG: Diagnostic details (only in development)
   logger.debug("Processing item", extra={"item_id": item.id, "raw_data": raw})

   # INFO: Normal business events
   logger.info("Metrics collected", extra={"project": "MyApp", "count": 42})

   # WARNING: Unexpected but handled
   logger.warning("API rate limit approaching", extra={"remaining": 10, "reset_in": 60})

   # ERROR: Failures that need attention
   logger.error("Failed to fetch data", exc_info=True, extra={"url": url, "status": 500})

   # CRITICAL: System-level failures
   logger.critical("Database connection lost", extra={"retry_count": 3})

Include Structured Data
~~~~~~~~~~~~~~~~~~~~~~~

**✅ Good:**

.. code-block:: python

   logger.info(
       "Bug query completed",
       extra={
           "project": "MyApp",
           "bug_count": 42,
           "p1_count": 2,
           "duration_ms": 1234
       }
   )

**❌ Bad:**

.. code-block:: python

   logger.info(f"Found 42 bugs in MyApp (2 P1s) in 1234ms")

The good example allows filtering/searching by ``project="MyApp"`` or ``p1_count>0``.

Avoid Logging Secrets
~~~~~~~~~~~~~~~~~~~~~~

**❌ NEVER do this:**

.. code-block:: python

   logger.info("Connecting to API", extra={"api_key": api_key})  # SECURITY RISK!

**✅ Do this:**

.. code-block:: python

   logger.info("Connecting to API", extra={"api_key_prefix": api_key[:4] + "..."})

Production Configuration
------------------------

Log Rotation
~~~~~~~~~~~~

For production, use rotating file handlers:

.. code-block:: python

   from logging.handlers import RotatingFileHandler

   handler = RotatingFileHandler(
       "app.log",
       maxBytes=10 * 1024 * 1024,  # 10MB
       backupCount=5                 # Keep 5 old files
   )

Log Aggregation
~~~~~~~~~~~~~~~

JSON logs integrate easily with:

* **Datadog**: ``logs:`` field maps to log message
* **Splunk**: Parse JSON automatically
* **CloudWatch**: Use ``awslogs`` driver
* **ELK Stack**: Logstash JSON codec

Monitoring & Alerting
----------------------

Error Rate Alerts
~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Count ERROR and CRITICAL logs per minute
   # Alert if > 10 errors/min

Query Examples:

.. code-block:: text

   # Datadog
   logs("level:ERROR OR level:CRITICAL").rollup("count").last("1m") > 10

   # Splunk
   index=app level IN (ERROR, CRITICAL) | timechart span=1m count | where count > 10

Performance Tracking
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Track slow operations
   import time

   start = time.time()
   result = slow_operation()
   duration_ms = (time.time() - start) * 1000

   if duration_ms > 5000:
       logger.warning(
           "Slow operation detected",
           extra={
               "operation": "slow_operation",
               "duration_ms": duration_ms,
               "threshold_ms": 5000
           }
       )

Troubleshooting
---------------

Logs Not Appearing
~~~~~~~~~~~~~~~~~~

**Check log level:**

.. code-block:: python

   import logging
   print(logging.getLogger().level)  # Should be 10 (DEBUG), 20 (INFO), etc.

**Reset logging:**

.. code-block:: python

   from execution.core.logging_config import setup_logging
   setup_logging(level="DEBUG", json_output=False)

Too Much Noise
~~~~~~~~~~~~~~

**Suppress verbose libraries:**

.. code-block:: python

   import logging
   logging.getLogger("urllib3").setLevel(logging.WARNING)
   logging.getLogger("requests").setLevel(logging.WARNING)

Missing Context
~~~~~~~~~~~~~~~

**Always include relevant fields:**

.. code-block:: python

   # ❌ Not helpful
   logger.error("Query failed")

   # ✅ Helpful
   logger.error(
       "Query failed",
       exc_info=True,
       extra={
           "project": project_name,
           "query": query_text,
           "error_code": response.status_code
       }
   )

See Also
--------

* :doc:`development` - Code quality standards
* ``execution/core/logging_config.py`` - Logging implementation
* Python logging docs: https://docs.python.org/3/library/logging.html
