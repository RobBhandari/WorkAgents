"""Test simple query for current non-closed bugs"""

import os

from azure.devops.connection import Connection
from dotenv import load_dotenv
from msrest.authentication import BasicAuthentication

load_dotenv()

organization_url = os.getenv('ADO_ORGANIZATION_URL')
project_name = os.getenv('ADO_PROJECT_NAME', 'Access Legal Case Management')
pat = os.getenv('ADO_PAT')

credentials = BasicAuthentication('', pat)
connection = Connection(base_url=organization_url, creds=credentials)
wit_client = connection.clients.get_work_item_tracking_client()

# Simple query: just non-closed bugs
simple_query = f"""
SELECT [System.Id]
FROM WorkItems
WHERE [System.TeamProject] = '{project_name}'
AND [System.WorkItemType] = 'Bug'
AND [System.State] <> 'Closed'
"""

print("Query: Current non-closed bugs")
print("-" * 70)
results = wit_client.query_by_wiql(wiql={'query': simple_query})
count = len(results.work_items) if results.work_items else 0
print(f"Result: {count} bugs")
print("-" * 70)

if 300 <= count <= 350:
    print("CORRECT - Count matches expected ~320")
else:
    print(f"WARNING - Expected ~320, got {count}")
