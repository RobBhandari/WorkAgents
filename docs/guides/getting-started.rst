Getting Started
===============

This guide walks you through setting up and using the Engineering Metrics Platform.

Prerequisites
-------------

* Python 3.11 or higher
* Git
* Access to Azure DevOps and/or ArmorCode (for data collection)

Installation
------------

1. **Clone the repository:**

.. code-block:: bash

   git clone https://github.com/RobBhandari/WorkAgents.git
   cd WorkAgents

2. **Create virtual environment:**

.. code-block:: bash

   python -m venv .venv

   # Windows
   .venv\Scripts\activate

   # Linux/Mac
   source .venv/bin/activate

3. **Install dependencies:**

.. code-block:: bash

   pip install -r requirements.txt

Configuration
-------------

1. **Copy environment template:**

.. code-block:: bash

   cp .env.template .env

2. **Edit** ``.env`` **with your credentials:**

.. code-block:: bash

   # Azure DevOps
   ADO_PAT=your_personal_access_token
   ADO_ORGANIZATION=your-org-name
   ADO_PROJECT=YourProject

   # ArmorCode
   ARMORCODE_API_KEY=your_api_key
   ARMORCODE_TENANT=your_tenant_id

   # Email (optional)
   SMTP_SERVER=smtp.office365.com
   SMTP_PORT=587
   EMAIL_FROM=metrics@yourcompany.com
   EMAIL_PASSWORD=your_email_password

3. **Verify configuration:**

.. code-block:: python

   from execution.secure_config import get_config

   config = get_config()
   print("✅ Configuration loaded successfully")

First Steps
-----------

Collect Quality Metrics
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   python execution/ado_quality_metrics.py

This will:
* Query Azure DevOps for bug data
* Calculate quality metrics
* Save results to ``.tmp/observatory/quality_history.json``

Generate Dashboard
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   python execution/generate_security_dashboard.py

This will:
* Load historical metric data
* Generate HTML dashboard
* Save to ``.tmp/observatory/dashboards/security.html``

View Dashboard
~~~~~~~~~~~~~~

Open the generated HTML file in your browser:

.. code-block:: bash

   # Windows
   start .tmp/observatory/dashboards/security.html

   # Mac
   open .tmp/observatory/dashboards/security.html

   # Linux
   xdg-open .tmp/observatory/dashboards/security.html

Automated Daily Refresh
~~~~~~~~~~~~~~~~~~~~~~~~

The platform includes a scheduled job that runs daily at 6am to refresh all metrics and dashboards. See ``.github/workflows/refresh-dashboards.yml`` for details.

Next Steps
----------

* Read :doc:`configuration` for advanced setup
* Read :doc:`development` to contribute code
* Review ``execution/ARCHITECTURE.md`` for system design
* Review ``execution/CONTRIBUTING.md`` for coding standards
