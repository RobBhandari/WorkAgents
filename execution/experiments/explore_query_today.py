"""Test the ADO query with today's date to verify it returns ~320 bugs"""

import os
import sys
from datetime import datetime

from azure.devops.connection import Connection
from dotenv import load_dotenv
from msrest.authentication import BasicAuthentication

load_dotenv()

def test_query(as_of_date: str):
    """Test the query with a specific date"""
    organization_url = os.getenv('ADO_ORGANIZATION_URL')
    project_name = os.getenv('ADO_PROJECT_NAME', 'Access Legal Case Management')
    pat = os.getenv('ADO_PAT')

    credentials = BasicAuthentication('', pat)
    connection = Connection(base_url=organization_url, creds=credentials)
    wit_client = connection.clients.get_work_item_tracking_client()

    # Test the exact query
    wiql_query = f"""
    SELECT [System.Id]
    FROM WorkItems
    WHERE [System.TeamProject] = '{project_name}'
    AND [System.WorkItemType] = 'Bug'
    AND [System.CreatedDate] <= '{as_of_date}'
    AND (
        [System.State] <> 'Closed'
        OR [Microsoft.VSTS.Common.ClosedDate] > '{as_of_date}'
        OR [Microsoft.VSTS.Common.ClosedDate] = ''
    )
    """

    print(f"\nTesting query for date: {as_of_date}")
    print(f"Project: {project_name}")
    print("-" * 70)

    wiql_results = wit_client.query_by_wiql(wiql={'query': wiql_query})
    count = len(wiql_results.work_items) if wiql_results.work_items else 0

    print(f"Result: {count} bugs")
    print("-" * 70)

    return count

if __name__ == '__main__':
    # Test with today's date (should return ~320)
    today = datetime.now().strftime('%Y-%m-%d')
    count_today = test_query(today)

    print(f"\n✓ Today ({today}): {count_today} bugs")

    # Test with Dec 1, 2025
    count_dec1 = test_query('2025-12-01')
    print(f"✓ Dec 1, 2025: {count_dec1} bugs")

    # Test with Jan 1, 2026
    count_jan1 = test_query('2026-01-01')
    print(f"✓ Jan 1, 2026: {count_jan1} bugs")

    print(f"\n{'='*70}")
    print("Analysis:")
    print(f"{'='*70}")
    if count_today < 350:
        print(f"✓ Today's count ({count_today}) looks correct (~320 expected)")
    else:
        print(f"✗ Today's count ({count_today}) is too high!")

    print(f"\nChange from Dec 1 to Jan 1: {count_dec1} → {count_jan1} ({count_jan1 - count_dec1:+d} bugs)")
    print(f"Change from Jan 1 to Today: {count_jan1} → {count_today} ({count_today - count_jan1:+d} bugs)")
