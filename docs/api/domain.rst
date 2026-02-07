Domain Models
=============

The domain layer contains pure business logic and data models. All models are type-safe with Python 3.11+ type hints and validated with MyPy.

Base Metrics
------------

.. automodule:: execution.domain.metrics
   :members:
   :undoc-members:
   :show-inheritance:

Quality Metrics
---------------

Models for tracking software quality: bugs, defects, and resolution rates.

.. automodule:: execution.domain.quality
   :members:
   :undoc-members:
   :show-inheritance:

**Example Usage:**

.. code-block:: python

   from execution.domain.quality import Bug, QualityMetrics
   from datetime import datetime

   # Create a bug instance
   bug = Bug(
       id=12345,
       title="Login page throws 500 error",
       state="Active",
       priority=1,
       age_days=15,
       created_date=datetime.now(),
       area_path="MyApp\Backend\Auth"
   )

   # Check bug status
   if bug.is_high_priority:
       print(f"⚠️ High priority bug: {bug.title}")

   if bug.is_aging(threshold_days=30):
       print(f"🚨 Bug is aging: {bug.age_days} days old")

   # Create quality metrics snapshot
   metrics = QualityMetrics(
       timestamp=datetime.now(),
       project="MyApp",
       open_bugs=50,
       closed_this_week=10,
       created_this_week=5,
       net_change=-5,
       p1_count=2,
       p2_count=8
   )

   # Analyze quality
   if metrics.is_improving:
       print("✅ Quality improving (net bugs decreasing)")

   if metrics.has_critical_bugs:
       print(f"⚠️ {metrics.p1_count} critical bugs need attention")

   print(f"Closure rate: {metrics.closure_rate:.1f}%")

Security Metrics
----------------

Models for tracking security vulnerabilities and risk.

.. automodule:: execution.domain.security
   :members:
   :undoc-members:
   :show-inheritance:

**Example Usage:**

.. code-block:: python

   from execution.domain.security import Vulnerability, SecurityMetrics
   from datetime import datetime

   # Create vulnerability instance
   vuln = Vulnerability(
       id="VULN-12345",
       title="SQL Injection in user input",
       severity="CRITICAL",
       product="MyApp-Backend",
       asset="auth-service",
       created_date=datetime.now()
   )

   # Check severity
   if vuln.is_critical_or_high:
       print(f"🚨 High-severity vulnerability: {vuln.title}")

   # Create security metrics
   metrics = SecurityMetrics(
       timestamp=datetime.now(),
       project="MyApp",
       total_vulnerabilities=25,
       critical=2,
       high=8,
       medium=10,
       low=5
   )

   # Analyze security posture
   if metrics.has_critical_vulnerabilities:
       print(f"🚨 {metrics.critical} critical vulnerabilities")

   print(f"Risk score: {metrics.risk_score:.1f}")

Flow Metrics
------------

Models for tracking development flow: lead time, cycle time, and WIP.

.. automodule:: execution.domain.flow
   :members:
   :undoc-members:
   :show-inheritance:

**Example Usage:**

.. code-block:: python

   from execution.domain.flow import FlowMetrics
   from datetime import datetime

   # Create flow metrics
   metrics = FlowMetrics(
       timestamp=datetime.now(),
       project="MyApp",
       lead_time_p50=7.5,
       lead_time_p85=12.0,
       lead_time_p95=18.0,
       cycle_time_p50=4.2,
       cycle_time_p85=7.0,
       cycle_time_p95=10.5,
       wip_count=25,
       aging_items=5,
       throughput=12
   )

   # Analyze flow health
   if metrics.has_flow_issues():
       print("⚠️ Flow issues detected:")

       if metrics.has_high_variability():
           variability = metrics.lead_time_variability()
           print(f"  - High variability: {variability:.1f}x")

       if metrics.has_aging_issues():
           aging_pct = metrics.aging_percentage()
           print(f"  - Aging WIP: {aging_pct:.1f}%")

       if metrics.lead_time_p50 and metrics.lead_time_p50 > 14:
           print(f"  - Slow delivery: {metrics.lead_time_p50:.1f} days")

   print(f"Throughput: {metrics.throughput} items/week")

Trend Data
----------

Time series data model for tracking metric changes over time.

**Example Usage:**

.. code-block:: python

   from execution.domain.metrics import TrendData
   from datetime import datetime, timedelta

   # Create trend data
   start_date = datetime(2026, 1, 1)
   trend = TrendData(
       values=[50.0, 45.0, 42.0, 38.0],
       timestamps=[start_date + timedelta(weeks=i) for i in range(4)],
       label="Open Bugs"
   )

   # Analyze trends
   print(f"Latest: {trend.latest()}")  # 38.0
   print(f"WoW change: {trend.week_over_week_change()}")  # -4.0
   print(f"WoW % change: {trend.week_over_week_percent_change():.1f}%")  # -9.5%
   print(f"Total change: {trend.total_change()}")  # -12.0

   # Check if improving
   if trend.is_improving(lower_is_better=True):
       print("✅ Trend improving (bugs decreasing)")
