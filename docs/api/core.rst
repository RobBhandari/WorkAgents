Core Infrastructure
===================

Core infrastructure provides security-hardened configuration and HTTP clients.

Secure Configuration
--------------------

.. automodule:: execution.secure_config
   :members:
   :undoc-members:
   :show-inheritance:

**Usage Example:**

.. code-block:: python

   from execution.secure_config import get_config

   # Get configuration singleton
   config = get_config()

   # Azure DevOps configuration
   ado_config = config.get_ado_config()
   print(f"Organization: {ado_config.organization}")
   print(f"PAT loaded: {'✅' if ado_config.pat else '❌'}")

   # ArmorCode configuration
   armor_config = config.get_armorcode_config()
   print(f"API Key loaded: {'✅' if armor_config.api_key else '❌'}")

   # Email configuration
   email_config = config.get_email_config()
   print(f"SMTP configured: {'✅' if email_config.smtp_server else '❌'}")

HTTP Client
-----------

.. automodule:: execution.http_client
   :members:
   :undoc-members:
   :show-inheritance:

**Usage Example:**

.. code-block:: python

   from execution.http_client import get, post

   # Secure GET request with automatic retries
   response = get(
       url="https://api.example.com/data",
       headers={"Authorization": f"Bearer {token}"}
   )

   if response.status_code == 200:
       data = response.json()
       print(f"✅ Retrieved {len(data)} items")

   # POST request with JSON body
   response = post(
       url="https://api.example.com/items",
       json={"name": "New Item", "value": 42}
   )

Security Utilities
------------------

.. automodule:: execution.security_utils
   :members:
   :undoc-members:
   :show-inheritance:

**Key Features:**

* **Credential masking**: Automatically redacts sensitive data in logs
* **Request validation**: Validates URLs and headers before sending
* **Rate limiting**: Built-in retry logic with exponential backoff
* **TLS validation**: Enforces HTTPS for production endpoints

Best Practices
--------------

**❌ Never do this:**

.. code-block:: python

   import os
   import requests

   # Direct environment access (insecure, not validated)
   pat = os.getenv('ADO_PAT')

   # Direct requests usage (no retries, no logging)
   response = requests.get(url, headers={'Authorization': pat})

**✅ Always do this:**

.. code-block:: python

   from execution.secure_config import get_config
   from execution.http_client import get

   # Validated, secure configuration
   config = get_config()
   ado_config = config.get_ado_config()

   # Secure HTTP client with retries and logging
   response = get(url, headers={'Authorization': f'Bearer {ado_config.pat}'})
