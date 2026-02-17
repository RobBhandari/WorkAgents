Dashboard Generation
====================

Dashboard generators create HTML reports using Jinja2 templates and domain models.

Dashboard Framework
-------------------

.. automodule:: execution.framework
   :members:
   :undoc-members:
   :show-inheritance:

Security Dashboard
------------------

.. automodule:: execution.dashboards.security
   :members:
   :undoc-members:
   :show-inheritance:

**Usage Example:**

.. code-block:: python

   from execution.dashboards.security import generate_security_dashboard
   from pathlib import Path

   # Generate dashboard
   output_path = Path('.tmp/observatory/dashboards/security.html')
   html = generate_security_dashboard(output_path)

   print(f"✅ Dashboard generated: {output_path}")

Executive Dashboard
-------------------

.. automodule:: execution.dashboards.executive
   :members:
   :undoc-members:
   :show-inheritance:

Trends Dashboard
----------------

.. automodule:: execution.dashboards.trends
   :members:
   :undoc-members:
   :show-inheritance:

Dashboard Components
--------------------

Reusable HTML component functions.

Cards
~~~~~

.. automodule:: execution.dashboards.components.cards
   :members:
   :undoc-members:

Tables
~~~~~~

.. automodule:: execution.dashboards.components.tables
   :members:
   :undoc-members:

Charts
~~~~~~

.. automodule:: execution.dashboards.components.charts
   :members:
   :undoc-members:
