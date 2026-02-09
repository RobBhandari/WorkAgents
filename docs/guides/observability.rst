Observability Guide
===================

Production-grade monitoring, error tracking, and alerting.

Overview
--------

The platform provides comprehensive observability through:

* **Error Tracking**: Sentry integration for production errors
* **Slack Notifications**: Real-time alerts for failures
* **Performance Monitoring**: Track slow operations
* **Data Freshness**: Alert on stale metrics
* **Dashboard Availability**: Monitor dashboard uptime

Quick Start
-----------

Basic Setup
~~~~~~~~~~~

.. code-block:: python

   from execution.core.observability import setup_observability

   # Initialize observability
   setup_observability(
       sentry_dsn="https://abc123@o123.ingest.sentry.io/456",
       slack_webhook_url="https://hooks.slack.com/services/T00/B00/xxx",
       environment="production"
   )

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # .env file
   SENTRY_DSN=https://abc123@o123.ingest.sentry.io/456
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00/B00/xxx

Then initialize without parameters:

.. code-block:: python

   setup_observability(environment="production")

Error Tracking (Sentry)
-----------------------

Installation
~~~~~~~~~~~~

.. code-block:: bash

   pip install sentry-sdk

Getting Sentry DSN
~~~~~~~~~~~~~~~~~~

1. Create account at https://sentry.io
2. Create new project
3. Copy DSN from Settings → Client Keys

Usage
~~~~~

**Automatic Error Capture:**

.. code-block:: python

   from execution.core.observability import setup_observability

   setup_observability(environment="production")

   # All uncaught exceptions are automatically sent to Sentry
   risky_operation()  # If this raises, Sentry captures it

**Manual Error Capture:**

.. code-block:: python

   from execution.core.observability import capture_exception

   try:
       result = fetch_data()
   except Exception as e:
       capture_exception(e, context={
           "operation": "data_fetch",
           "url": url,
           "retry_count": 3
       })
       raise  # Re-raise after capturing

**Logging Integration:**

All ERROR and CRITICAL logs are automatically sent to Sentry:

.. code-block:: python

   logger.error("Failed to generate dashboard", exc_info=True)
   # Automatically sent to Sentry with full stack trace

Slack Notifications
-------------------

Getting Webhook URL
~~~~~~~~~~~~~~~~~~~

1. Go to https://api.slack.com/apps
2. Create new app or select existing
3. Enable "Incoming Webhooks"
4. Add webhook to workspace
5. Copy webhook URL

Usage
~~~~~

**Simple Notification:**

.. code-block:: python

   from execution.core.observability import send_slack_notification

   send_slack_notification(
       "Deployment completed successfully",
       severity="info"
   )

**With Context:**

.. code-block:: python

   send_slack_notification(
       "Critical: 10 P1 bugs detected",
       severity="critical",
       context={
           "project": "MyApp",
           "p1_count": 10,
           "p2_count": 25
       }
   )

**Severity Levels:**

* ``info``: Green - Normal operations
* ``warning``: Orange - Attention needed
* ``error``: Red - Failures
* ``critical``: Dark Red - Severe issues

CI Failure Notifications
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from execution.core.observability import notify_ci_failure

   notify_ci_failure(
       job_name="unit-tests",
       error_message="Test test_quality_metrics FAILED",
       logs_url="https://github.com/user/repo/actions/runs/123"
   )

Performance Monitoring
----------------------

Track Slow Operations
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from execution.core.observability import track_performance

   with track_performance("dashboard_generation", alert_threshold_ms=3000) as ctx:
       ctx["project"] = "MyApp"
       generate_dashboard()
       ctx["size_kb"] = 245

**What Happens:**

* Logs duration for all operations
* Warns if exceeds threshold
* Sends Slack alert if exceeds 2x threshold
* Context fields included in logs

Real-World Example
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from execution.collectors.ado_quality_metrics import collect_quality_metrics

   with track_performance("quality_metrics_collection", alert_threshold_ms=5000) as ctx:
       metrics = collect_quality_metrics()
       ctx["bug_count"] = metrics.open_bugs
       ctx["api_calls"] = 42

   # Logs:
   # Performance: quality_metrics_collection
   #   duration_ms: 4231
   #   bug_count: 50
   #   api_calls: 42

Data Freshness Monitoring
--------------------------

Check if Metrics are Stale
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from execution.core.observability import check_data_freshness
   from pathlib import Path

   is_fresh, age_hours = check_data_freshness(
       Path(".tmp/observatory/quality_history.json"),
       max_age_hours=24.0
   )

   if not is_fresh:
       logger.warning(f"Quality metrics are {age_hours:.1f} hours old")

**Automatic Alerts:**

If data is stale:
* Logs WARNING
* Sends Slack notification (if configured)

Scheduled Health Checks
~~~~~~~~~~~~~~~~~~~~~~~

Run ``monitor_health.py`` periodically:

.. code-block:: bash

   # Every hour via cron (Linux/Mac)
   0 * * * * cd /path/to/repo && python execution/monitor_health.py

   # Every hour via Task Scheduler (Windows)
   schtasks /create /sc hourly /tn "Metrics Health Check" /tr "python C:\path\execution\monitor_health.py"

Dashboard Availability
----------------------

Check if Dashboards Exist
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from execution.core.observability import check_dashboard_availability
   from pathlib import Path

   if not check_dashboard_availability(
       Path(".tmp/observatory/dashboards/security.html")
   ):
       logger.error("Security dashboard unavailable!")

**What it Checks:**

* File exists
* File is not empty
* Logs size in KB
* Sends Slack alert if unavailable

Monitoring Script
~~~~~~~~~~~~~~~~~

The ``monitor_health.py`` script checks:

1. **Metrics freshness**: All history files < 25 hours old
2. **Dashboard availability**: All dashboards exist and valid

.. code-block:: bash

   python execution/monitor_health.py

   # Output:
   # ============================================================
   # Health Monitoring Check - Starting
   # ============================================================
   # Metrics freshness check complete (fresh: 3, stale: 0)
   # Dashboard availability check complete (available: 3, unavailable: 0)
   # ✅ Health Check PASSED - All systems operational

Production Setup
----------------

Complete Example
~~~~~~~~~~~~~~~~

.. code-block:: python

   from execution.core import setup_logging, setup_observability

   # Setup logging (JSON for production)
   setup_logging(
       level="INFO",
       log_file=Path("/var/log/metrics-platform/app.log"),
       json_output=True
   )

   # Setup observability
   setup_observability(
       environment="production",
       enable_sentry=True,
       enable_slack=True
   )

   # Your application code
   logger.info("Application started")

GitHub Actions Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~

Add to ``.github/workflows/ci-quality-gates.yml``:

.. code-block:: yaml

   - name: Notify Slack on Failure
     if: failure()
     run: |
       python -c "
       from execution.core.observability import setup_observability, notify_ci_failure
       import os
       setup_observability(environment='ci')
       notify_ci_failure(
           job_name='${{ github.job }}',
           error_message='CI job failed',
           logs_url='${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}'
       )
       "

Best Practices
--------------

Error Handling
~~~~~~~~~~~~~~

**✅ Good:**

.. code-block:: python

   try:
       result = risky_operation()
   except SpecificException as e:
       logger.error("Operation failed", exc_info=True)
       capture_exception(e, context={"operation": "risky_operation"})
       # Handle error appropriately
   except Exception as e:
       logger.critical("Unexpected error", exc_info=True)
       capture_exception(e)
       raise  # Re-raise unexpected errors

**❌ Bad:**

.. code-block:: python

   try:
       result = risky_operation()
   except Exception:
       pass  # Silently swallowing errors!

Performance Monitoring
~~~~~~~~~~~~~~~~~~~~~~

**Track Critical Operations:**

.. code-block:: python

   # Track expensive operations
   operations_to_monitor = [
       ("dashboard_generation", 5000),  # 5 second threshold
       ("api_batch_query", 10000),      # 10 second threshold
       ("report_generation", 3000),      # 3 second threshold
   ]

   for op_name, threshold in operations_to_monitor:
       with track_performance(op_name, alert_threshold_ms=threshold):
           perform_operation(op_name)

Alert Fatigue Prevention
~~~~~~~~~~~~~~~~~~~~~~~~

**Don't over-alert:**

.. code-block:: python

   # ❌ Bad - Alert on every normal operation
   send_slack_notification("Dashboard generated", severity="info")

   # ✅ Good - Only alert on issues
   if dashboard_generation_time > threshold:
       send_slack_notification(f"Slow dashboard generation: {time}ms", severity="warning")

Troubleshooting
---------------

Sentry Not Working
~~~~~~~~~~~~~~~~~~

**Check DSN:**

.. code-block:: python

   import os
   print(os.getenv("SENTRY_DSN"))  # Should output your DSN

**Verify SDK installed:**

.. code-block:: bash

   pip list | grep sentry
   # Should show: sentry-sdk

**Test manually:**

.. code-block:: python

   import sentry_sdk
   sentry_sdk.init(dsn="your_dsn")
   sentry_sdk.capture_message("Test from Python")

Slack Notifications Not Sending
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Check webhook URL:**

.. code-block:: python

   import os
   print(os.getenv("SLACK_WEBHOOK_URL"))  # Should start with https://hooks.slack.com

**Test manually:**

.. code-block:: python

   import requests
   requests.post(
       "your_webhook_url",
       json={"text": "Test from Python"}
   )

**Check logs:**

.. code-block:: python

   from execution.core import get_logger, setup_logging

   setup_logging(level="DEBUG")
   logger = get_logger(__name__)

   # Try sending
   send_slack_notification("Test", severity="info")
   # Check DEBUG logs for errors

No Alerts on Stale Data
~~~~~~~~~~~~~~~~~~~~~~~~

**Verify file paths:**

.. code-block:: python

   from pathlib import Path

   data_file = Path(".tmp/observatory/quality_history.json")
   print(f"Exists: {data_file.exists()}")
   print(f"Age: {(time.time() - data_file.stat().st_mtime) / 3600:.1f} hours")

**Run health check manually:**

.. code-block:: bash

   python execution/monitor_health.py

See Also
--------

* :doc:`logging` - Structured logging guide
* :doc:`development` - Development guidelines
* ``execution/core/observability.py`` - Observability implementation
* Sentry docs: https://docs.sentry.io/platforms/python/
* Slack webhooks: https://api.slack.com/messaging/webhooks
