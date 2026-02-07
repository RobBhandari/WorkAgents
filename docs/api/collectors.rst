Data Collectors
===============

Collectors fetch data from external sources and transform it into domain models.

Azure DevOps Collectors
------------------------

Quality Metrics Collector
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: execution.collectors.ado_quality_metrics
   :members:
   :undoc-members:
   :show-inheritance:

Flow Metrics Collector
~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: execution.collectors.ado_flow_metrics
   :members:
   :undoc-members:
   :show-inheritance:

ArmorCode Collectors
--------------------

Security Data Loader
~~~~~~~~~~~~~~~~~~~~

.. automodule:: execution.collectors.armorcode_loader
   :members:
   :undoc-members:
   :show-inheritance:

**Usage Example:**

.. code-block:: python

   from execution.collectors.armorcode_loader import ArmorCodeLoader
   from pathlib import Path

   # Initialize loader
   loader = ArmorCodeLoader(
       history_file=Path('.tmp/observatory/security_history.json')
   )

   # Load latest metrics by product
   metrics_by_product = loader.load_latest_metrics()

   for product_name, metrics in metrics_by_product.items():
       print(f"{product_name}: {metrics.total_vulnerabilities} vulns")
       if metrics.has_critical_vulnerabilities:
           print(f"  🚨 {metrics.critical} critical!")

   # Load all historical data
   all_weeks = loader.load_all_weeks()
   print(f"Historical data: {len(all_weeks)} weeks")
