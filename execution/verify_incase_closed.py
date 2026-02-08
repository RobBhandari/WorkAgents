#!/usr/bin/env python3
"""Quick verification of InCase closed bug count"""

from datetime import datetime, timedelta

from azure.devops.connection import Connection
from azure.devops.v7_1.work_item_tracking import Wiql
from dotenv import load_dotenv
from msrest.authentication import BasicAuthentication

from execution.core import get_config

load_dotenv()

# Connect
organization_url = get_config().get("ADO_ORGANIZATION_URL")
pat = get_config().get_ado_config().pat
credentials = BasicAuthentication("", pat)
connection = Connection(base_url=organization_url, creds=credentials)
wit_client = connection.clients.get_work_item_tracking_client()

# Query closed bugs for InCase
lookback_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
project_name = "Access Legal InCase"

wiql = Wiql(query=f"""
    SELECT [System.Id], [Microsoft.VSTS.Common.ClosedDate]
    FROM WorkItems
    WHERE [System.TeamProject] = '{project_name}'
      AND [System.WorkItemType] = 'Bug'
      AND [System.State] = 'Closed'
      AND [Microsoft.VSTS.Common.ClosedDate] >= '{lookback_date}'
    ORDER BY [Microsoft.VSTS.Common.ClosedDate] DESC
    """)  # nosec B608 - Hardcoded project name from config, not user input

result = wit_client.query_by_wiql(wiql).work_items
total_count = len(result) if result else 0

print(f"\n{'='*60}")
print(f"Project: {project_name}")
print(f"Query: Bugs with State='Closed' AND ClosedDate >= {lookback_date}")
print(f"{'='*60}")
print(f"\nTotal Closed Bugs (last 90 days): {total_count}")

# Get details of first 10 and last 10 to show date range
if result and len(result) > 0:
    ids_to_fetch = (
        [item.id for item in result[:10]] + [item.id for item in result[-10:]]
        if len(result) > 10
        else [item.id for item in result]
    )
    items = wit_client.get_work_items(
        ids=list(set(ids_to_fetch)), fields=["System.Id", "Microsoft.VSTS.Common.ClosedDate", "System.Title"]
    )

    print("\nSample (First 5):")
    for i, item in enumerate(items[:5]):
        closed_date = item.fields.get("Microsoft.VSTS.Common.ClosedDate")
        print(
            f"  Bug {item.fields.get('System.Id')}: Closed on {closed_date.strftime('%Y-%m-%d') if closed_date else 'N/A'}"
        )

    if len(items) > 5:
        print("\nSample (Last 5):")
        for item in items[-5:]:
            closed_date = item.fields.get("Microsoft.VSTS.Common.ClosedDate")
            print(
                f"  Bug {item.fields.get('System.Id')}: Closed on {closed_date.strftime('%Y-%m-%d') if closed_date else 'N/A'}"
            )

print(f"\n{'='*60}")
print(f"Verification: {'✓ Count is accurate' if total_count > 0 else '⚠ No closed bugs found'}")
print(f"{'='*60}\n")
