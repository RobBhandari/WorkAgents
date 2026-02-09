Configuration Guide
===================

Detailed configuration options for the Engineering Metrics Platform.

Environment Variables
---------------------

Azure DevOps
~~~~~~~~~~~~

Required for quality and flow metrics collection:

.. code-block:: bash

   # Authentication
   ADO_PAT=your_personal_access_token    # Required: PAT with Work Items (Read) scope

   # Organization settings
   ADO_ORGANIZATION=your-org-name        # Required: Your Azure DevOps organization
   ADO_PROJECT=YourProject               # Required: Project name

   # Optional: Query customization
   ADO_AREA_PATH=YourProject\Team       # Optional: Filter by area path
   ADO_ITERATION_PATH=Sprint-*           # Optional: Filter by iteration

**Getting an Azure DevOps PAT:**

1. Go to https://dev.azure.com/{your-org}/_usersSettings/tokens
2. Click "New Token"
3. Set scopes: ``Work Items`` → ``Read``
4. Copy the token immediately (won't be shown again)

ArmorCode
~~~~~~~~~

Required for security metrics collection:

.. code-block:: bash

   # Authentication
   ARMORCODE_API_KEY=your_api_key        # Required: API key from ArmorCode
   ARMORCODE_TENANT=your_tenant_id       # Required: Your tenant identifier

   # Optional: Configuration
   ARMORCODE_ENVIRONMENT=production      # Optional: Environment filter
   ARMORCODE_PRODUCTS=*                  # Optional: Product filter (comma-separated)

**Getting an ArmorCode API Key:**

1. Log into ArmorCode
2. Go to Settings → API Keys
3. Generate new key with ``Read`` permissions

Email Configuration
~~~~~~~~~~~~~~~~~~~

Optional, for sending metric reports via email:

.. code-block:: bash

   # SMTP server
   SMTP_SERVER=smtp.office365.com        # SMTP server address
   SMTP_PORT=587                         # SMTP port (usually 587 for TLS)

   # Authentication
   EMAIL_FROM=metrics@yourcompany.com    # Sender email address
   EMAIL_PASSWORD=your_email_password    # Sender password or app-specific password

   # Recipients
   EMAIL_TO=team@yourcompany.com         # Comma-separated recipient list

**Office 365 Setup:**

1. Go to https://account.microsoft.com/security
2. Enable "App passwords"
3. Generate app password for "Mail"
4. Use app password in ``EMAIL_PASSWORD``

Configuration Validation
------------------------

Run the validation script to check your configuration:

.. code-block:: python

   from execution.secure_config import get_config

   config = get_config()

   # Validate ADO config
   try:
       ado_config = config.get_ado_config()
       print(f"✅ ADO Organization: {ado_config.organization}")
       print(f"✅ ADO Project: {ado_config.project}")
       print(f"✅ ADO PAT: {'*' * 10}{ado_config.pat[-4:]}")
   except Exception as e:
       print(f"❌ ADO config error: {e}")

   # Validate ArmorCode config
   try:
       armor_config = config.get_armorcode_config()
       print(f"✅ ArmorCode Tenant: {armor_config.tenant}")
       print(f"✅ ArmorCode API Key: {'*' * 10}{armor_config.api_key[-4:]}")
   except Exception as e:
       print(f"❌ ArmorCode config error: {e}")

Advanced Configuration
----------------------

Custom Data Paths
~~~~~~~~~~~~~~~~~

By default, data is stored in ``.tmp/observatory/``. To customize:

.. code-block:: python

   from pathlib import Path
   from execution.collectors.ado_quality_metrics import collect_quality_metrics

   # Custom output path
   custom_path = Path('/custom/path/quality_history.json')
   metrics = collect_quality_metrics(output_file=custom_path)

Custom Queries
~~~~~~~~~~~~~~

Customize Azure DevOps queries in your collector code:

.. code-block:: python

   from execution.collectors.ado_quality_metrics import ADOQualityCollector

   collector = ADOQualityCollector()

   # Custom WIQL query
   custom_query = """
       SELECT [System.Id], [System.Title], [System.State]
       FROM WorkItems
       WHERE [System.WorkItemType] = 'Bug'
         AND [System.State] <> 'Closed'
         AND [System.AreaPath] UNDER 'MyProject\MyTeam'
         AND [System.CreatedDate] >= @StartOfYear
       ORDER BY [System.Priority] ASC
   """

   bugs = collector.query_bugs(wiql=custom_query)

Security Best Practices
-----------------------

**✅ DO:**

* Store credentials in ``.env`` file (never commit to git)
* Use ``.env.template`` as a reference (commit this)
* Rotate credentials regularly
* Use minimum required permissions for PATs
* Enable MFA on all accounts

**❌ DON'T:**

* Hardcode credentials in code
* Commit ``.env`` to version control
* Share credentials via email or chat
* Use personal credentials for shared accounts
* Grant more permissions than needed

Troubleshooting
---------------

"Configuration not found" Error
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block::

   ConfigurationError: ADO_PAT not found in environment

**Solution:** Ensure ``.env`` file exists and contains required variables.

"Authentication failed" Error
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block::

   AuthenticationError: 401 Unauthorized

**Solution:** 

1. Verify PAT is still valid (they expire)
2. Check PAT has correct scopes
3. Verify organization/project names are correct

"Rate limit exceeded" Error
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block::

   RateLimitError: 429 Too Many Requests

**Solution:** The HTTP client will automatically retry with backoff. If persistent, increase delay between requests in ``http_client.py``.
