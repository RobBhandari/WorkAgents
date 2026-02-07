"""Test query using only ClosedDate for historical filtering"""

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

def test_query(as_of_date: str, label: str):
    """Test query using only ClosedDate"""
    # Query: bugs created before date AND (not yet closed OR closed after date)
    query = f"""
    SELECT [System.Id]
    FROM WorkItems
    WHERE [System.TeamProject] = '{project_name}'
    AND [System.WorkItemType] = 'Bug'
    AND [System.CreatedDate] <= '{as_of_date}'
    AND NOT [Microsoft.VSTS.Common.ClosedDate] <= '{as_of_date}'
    """

    print(f"\n{label} ({as_of_date}):")
    print("-" * 70)
    try:
        results = wit_client.query_by_wiql(wiql={'query': query})
        count = len(results.work_items) if results.work_items else 0
        print(f"Result: {count} bugs")
        return count
    except Exception as e:
        print(f"Error: {e}")
        return None

# Test with different dates
test_query('2025-12-01', 'Dec 1, 2025')
test_query('2026-01-01', 'Jan 1, 2026')
test_query('2026-02-04', 'Feb 4, 2026 (today)')

print("\n" + "=" * 70)
print("Note: Using 'NOT [ClosedDate] <=' to include bugs closed after date")
print("      or never closed")
print("=" * 70)
