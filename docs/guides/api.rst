REST API Guide
==============

Programmatic access to engineering metrics via HTTP.

Overview
--------

The REST API provides JSON endpoints for:

* **Quality metrics**: Open bugs, closure rate, P1/P2 counts
* **Security metrics**: Vulnerabilities by severity and product
* **Flow metrics**: Cycle time and lead time percentiles
* **Dashboards**: List and metadata

Quick Start
-----------

Start the API Server
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Development (auto-reload)
   uvicorn execution.api.app:app --reload --port 8000

   # Production (multiple workers)
   uvicorn execution.api.app:app --host 0.0.0.0 --port 8000 --workers 4

**Access API Documentation:**

* Swagger UI: http://localhost:8000/docs
* ReDoc: http://localhost:8000/redoc

Authentication
--------------

All endpoints require HTTP Basic authentication.

Configure Credentials
~~~~~~~~~~~~~~~~~~~~~

Set environment variables:

.. code-block:: bash

   export API_USERNAME=admin
   export API_PASSWORD=your_secure_password

Or in ``.env`` file:

.. code-block:: bash

   API_USERNAME=admin
   API_PASSWORD=your_secure_password

Making Authenticated Requests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Python (requests library):**

.. code-block:: python

   import requests
   from requests.auth import HTTPBasicAuth

   response = requests.get(
       "http://localhost:8000/api/v1/metrics/quality/latest",
       auth=HTTPBasicAuth("admin", "your_password")
   )

   metrics = response.json()
   print(f"Open bugs: {metrics['open_bugs']}")

**curl:**

.. code-block:: bash

   curl -u admin:your_password http://localhost:8000/api/v1/metrics/quality/latest

**PowerShell:**

.. code-block:: powershell

   $cred = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:your_password"))
   $headers = @{ Authorization = "Basic $cred" }
   Invoke-RestMethod -Uri "http://localhost:8000/api/v1/metrics/quality/latest" -Headers $headers

Endpoints
---------

Health Check
~~~~~~~~~~~~

**GET /health**

Check API health and data freshness (no authentication required).

.. code-block:: bash

   curl http://localhost:8000/health

**Response:**

.. code-block:: json

   {
     "status": "healthy",
     "timestamp": "2026-02-07T10:00:00",
     "version": "2.0.0",
     "data_freshness": {
       "quality": {"fresh": true, "age_hours": 12.5},
       "security": {"fresh": true, "age_hours": 13.2},
       "flow": {"fresh": true, "age_hours": 11.8}
     }
   }

Quality Metrics
~~~~~~~~~~~~~~~

**GET /api/v1/metrics/quality/latest**

Get latest quality metrics.

.. code-block:: python

   import requests
   from requests.auth import HTTPBasicAuth

   response = requests.get(
       "http://localhost:8000/api/v1/metrics/quality/latest",
       auth=HTTPBasicAuth("admin", "password")
   )

   data = response.json()
   print(f"Open bugs: {data['open_bugs']}")
   print(f"Closed this week: {data['closed_this_week']}")
   print(f"Closure rate: {data['closure_rate']}%")

**Response:**

.. code-block:: json

   {
     "timestamp": "2026-02-07T06:00:00",
     "project": "MyApp",
     "open_bugs": 156,
     "closed_this_week": 23,
     "net_change": -5,
     "closure_rate": 85.2,
     "p1_count": 8,
     "p2_count": 42
   }

**GET /api/v1/metrics/quality/history?weeks=12**

Get historical quality metrics.

.. code-block:: python

   response = requests.get(
       "http://localhost:8000/api/v1/metrics/quality/history?weeks=12",
       auth=HTTPBasicAuth("admin", "password")
   )

   history = response.json()
   for week in history['weeks']:
       print(f"{week['week_ending']}: {week['metrics']['open_bugs']} bugs")

Security Metrics
~~~~~~~~~~~~~~~~

**GET /api/v1/metrics/security/latest**

Get latest security metrics across all products.

.. code-block:: python

   response = requests.get(
       "http://localhost:8000/api/v1/metrics/security/latest",
       auth=HTTPBasicAuth("admin", "password")
   )

   data = response.json()
   print(f"Total vulnerabilities: {data['total_vulnerabilities']}")
   print(f"Critical: {data['critical']}")
   print(f"High: {data['high']}")

   for product in data['products']:
       print(f"  {product['name']}: {product['total']} vulns")

**Response:**

.. code-block:: json

   {
     "timestamp": "2026-02-07T06:00:00",
     "total_vulnerabilities": 842,
     "critical": 12,
     "high": 89,
     "product_count": 15,
     "products": [
       {"name": "Product A", "total": 145, "critical": 3, "high": 18},
       {"name": "Product B", "total": 98, "critical": 0, "high": 12}
     ]
   }

**GET /api/v1/metrics/security/product/{product_name}**

Get security metrics for specific product.

.. code-block:: python

   response = requests.get(
       "http://localhost:8000/api/v1/metrics/security/product/Product%20A",
       auth=HTTPBasicAuth("admin", "password")
   )

   product = response.json()
   print(f"{product['product']}: {product['total_vulnerabilities']} vulns")

Flow Metrics
~~~~~~~~~~~~

**GET /api/v1/metrics/flow/latest**

Get latest flow metrics (cycle time, lead time).

.. code-block:: python

   response = requests.get(
       "http://localhost:8000/api/v1/metrics/flow/latest",
       auth=HTTPBasicAuth("admin", "password")
   )

   data = response.json()
   print(f"Cycle time P50: {data['cycle_time_p50']} days")
   print(f"Cycle time P85: {data['cycle_time_p85']} days")
   print(f"Lead time P50: {data['lead_time_p50']} days")

**Response:**

.. code-block:: json

   {
     "timestamp": "2026-02-07T06:00:00",
     "project": "MyApp",
     "cycle_time_p50": 3.2,
     "cycle_time_p85": 8.5,
     "cycle_time_p95": 15.3,
     "lead_time_p50": 5.8,
     "lead_time_p85": 12.4,
     "lead_time_p95": 22.1,
     "work_items_completed": 145
   }

Dashboards
~~~~~~~~~~

**GET /api/v1/dashboards/list**

List available dashboards.

.. code-block:: python

   response = requests.get(
       "http://localhost:8000/api/v1/dashboards/list",
       auth=HTTPBasicAuth("admin", "password")
   )

   dashboards = response.json()
   for dash in dashboards['dashboards']:
       print(f"{dash['name']}: {dash['size_kb']} KB, modified {dash['last_modified']}")

**Response:**

.. code-block:: json

   {
     "dashboards": [
       {
         "name": "security",
         "filename": "security.html",
         "size_kb": 245.3,
         "last_modified": "2026-02-07T06:15:00"
       },
       {
         "name": "executive_summary",
         "filename": "executive_summary.html",
         "size_kb": 189.7,
         "last_modified": "2026-02-07T06:16:00"
       }
     ],
     "count": 2
   }

Use Cases
---------

Integrate with BI Tools
~~~~~~~~~~~~~~~~~~~~~~~

**Power BI:**

1. Get Data → Web
2. URL: ``http://localhost:8000/api/v1/metrics/quality/history?weeks=52``
3. Authentication: Basic
4. Refresh daily after 6am collection

**Tableau:**

1. Connect → Web Data Connector
2. URL: ``http://localhost:8000/api/v1/metrics/security/latest``
3. Authentication: Username/Password

Build Custom Dashboards
~~~~~~~~~~~~~~~~~~~~~~~~

**React dashboard:**

.. code-block:: javascript

   async function fetchQualityMetrics() {
     const response = await fetch('http://localhost:8000/api/v1/metrics/quality/latest', {
       headers: {
         'Authorization': 'Basic ' + btoa('admin:password')
       }
     });
     const data = await response.json();
     return data;
   }

Automated Monitoring
~~~~~~~~~~~~~~~~~~~~

**Daily Slack report:**

.. code-block:: python

   import requests
   from requests.auth import HTTPBasicAuth

   # Fetch metrics
   response = requests.get(
       "http://localhost:8000/api/v1/metrics/quality/latest",
       auth=HTTPBasicAuth("admin", "password")
   )
   metrics = response.json()

   # Send to Slack
   slack_webhook = "https://hooks.slack.com/services/..."
   message = {
       "text": f"📊 Daily Metrics Report\n"
               f"Open bugs: {metrics['open_bugs']}\n"
               f"Closed this week: {metrics['closed_this_week']}\n"
               f"Net change: {metrics['net_change']}"
   }
   requests.post(slack_webhook, json=message)

Error Handling
--------------

HTTP Status Codes
~~~~~~~~~~~~~~~~~

* ``200 OK``: Success (health endpoint always returns 200 even with stale data)
* ``401 Unauthorized``: Invalid credentials
* ``404 Not Found``: Resource not found (data not collected yet)
* ``500 Internal Server Error``: Server error

Example Error Response
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: json

   {
     "detail": "Quality metrics data not found. Run collectors first."
   }

**Handle errors in Python:**

.. code-block:: python

   try:
       response = requests.get(url, auth=auth)
       response.raise_for_status()  # Raise exception for 4xx/5xx
       data = response.json()
   except requests.exceptions.HTTPError as e:
       if response.status_code == 404:
           print("Data not found. Run collectors first.")
       elif response.status_code == 401:
           print("Invalid credentials")
       else:
           print(f"HTTP error: {e}")
   except requests.exceptions.RequestException as e:
       print(f"Request failed: {e}")

Deployment
----------

Production Deployment
~~~~~~~~~~~~~~~~~~~~~

**Using systemd (Linux):**

Create ``/etc/systemd/system/metrics-api.service``:

.. code-block:: ini

   [Unit]
   Description=Engineering Metrics API
   After=network.target

   [Service]
   User=metrics
   WorkingDirectory=/opt/metrics-platform
   Environment="PATH=/opt/metrics-platform/venv/bin"
   ExecStart=/opt/metrics-platform/venv/bin/uvicorn execution.api.app:app --host 0.0.0.0 --port 8000 --workers 4
   Restart=always

   [Install]
   WantedBy=multi-user.target

Enable and start:

.. code-block:: bash

   sudo systemctl enable metrics-api
   sudo systemctl start metrics-api

**Using Docker:**

.. code-block:: dockerfile

   FROM python:3.11-slim

   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   COPY execution/ execution/
   COPY .tmp/ .tmp/

   EXPOSE 8000

   CMD ["uvicorn", "execution.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

Build and run:

.. code-block:: bash

   docker build -t metrics-api .
   docker run -d -p 8000:8000 --env-file .env metrics-api

Reverse Proxy (nginx)
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: nginx

   server {
       listen 80;
       server_name metrics.company.com;

       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }

Security Best Practices
-----------------------

**Do:**

1. Use HTTPS in production (terminate at reverse proxy)
2. Use strong passwords for API_PASSWORD
3. Rotate credentials regularly
4. Use API keys or OAuth2 for production (upgrade from Basic auth)
5. Rate limit API endpoints
6. Monitor authentication failures

**Don't:**

1. Expose API directly to internet without authentication
2. Commit credentials to git
3. Use default password ``changeme`` in production
4. Share credentials across teams (use separate accounts)

See Also
--------

* :doc:`getting-started` - Setup guide
* :doc:`configuration` - Environment variables
* :doc:`observability` - Monitoring and alerts
* Swagger UI: http://localhost:8000/docs (interactive API testing)
