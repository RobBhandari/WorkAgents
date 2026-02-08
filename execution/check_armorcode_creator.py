#!/usr/bin/env python3
"""
Check if bugs are created by ArmorCode by examining the CreatedBy field
"""

import sys

from azure.devops.connection import Connection
from azure.devops.v7_0.work_item_tracking.models import Wiql
from dotenv import load_dotenv
from msrest.authentication import BasicAuthentication

from execution.core import get_config

# Load environment variables
load_dotenv()

org_url = get_config().get("AZURE_DEVOPS_ORG_URL")
pat = get_config().get("AZURE_DEVOPS_PAT")

if not org_url or not pat:
    print("ERROR: Missing Azure DevOps credentials")
    sys.exit(1)

print("Connecting to Azure DevOps...")
creds = BasicAuthentication("", pat)
connection = Connection(base_url=org_url, creds=creds)
wit_client = connection.clients.get_work_item_tracking_client()
print("[SUCCESS] Connected\n")

# Query bugs from Access Legal Case Management
project_name = "Access Legal Case Management"
print(f"Querying bugs from: {project_name}")

wiql = Wiql(query=f"""
    SELECT [System.Id], [System.Title], [System.CreatedBy], [System.CreatedDate], [System.Tags]
    FROM WorkItems
    WHERE [System.TeamProject] = '{project_name}'
      AND [System.WorkItemType] = 'Bug'
      AND [System.State] <> 'Removed'
    ORDER BY [System.CreatedDate] DESC
    """)  # nosec B608 - Hardcoded project name from config, not user input

result = wit_client.query_by_wiql(wiql)
print(f"Found {len(result.work_items)} bugs\n")

if result.work_items:
    # Get first 100 bugs
    ids = [item.id for item in result.work_items[:100]]
    bugs = wit_client.get_work_items(
        ids,
        fields=["System.Id", "System.Title", "System.CreatedBy", "System.CreatedDate", "System.State", "System.Tags"],
    )

    print("=" * 100)
    print("ANALYZING BUG CREATORS")
    print("=" * 100)

    armorcode_bugs = []
    creator_counts = {}

    for bug in bugs:
        bug_id = bug.id
        title = bug.fields.get("System.Title", "No title")
        created_by = bug.fields.get("System.CreatedBy", {})
        created_date = bug.fields.get("System.CreatedDate", "")
        state = bug.fields.get("System.State", "")
        tags = bug.fields.get("System.Tags", "")

        # Extract creator info
        if isinstance(created_by, dict):
            display_name = created_by.get("displayName", "Unknown")
            unique_name = created_by.get("uniqueName", "")
        else:
            display_name = str(created_by)
            unique_name = ""

        # Track creator counts
        creator_counts[display_name] = creator_counts.get(display_name, 0) + 1

        # Check if created by ArmorCode
        creator_lower = display_name.lower() + " " + unique_name.lower()
        if "armorcode" in creator_lower or "armor code" in creator_lower or "armor-code" in creator_lower:
            armorcode_bugs.append(
                {
                    "id": bug_id,
                    "title": title,
                    "creator": display_name,
                    "unique_name": unique_name,
                    "date": created_date,
                    "state": state,
                    "tags": tags,
                }
            )

    # Print results
    print(f"\n🔍 ARMORCODE-CREATED BUGS: {len(armorcode_bugs)}")
    print("=" * 100)

    if armorcode_bugs:
        print("\nFirst 10 ArmorCode-created bugs:")
        for i, bug in enumerate(armorcode_bugs[:10], 1):
            print(f"\n{i}. Bug #{bug['id']} - {bug['state']}")
            print(f"   Title: {bug['title'][:80]}")
            print(f"   Created By: {bug['creator']}")
            if bug["unique_name"]:
                print(f"   Email/Account: {bug['unique_name']}")
            print(f"   Created: {str(bug['date'])[:10]}")
            if bug["tags"]:
                print(f"   Tags: {bug['tags']}")
    else:
        print("  ✓ No bugs found with 'ArmorCode' in the creator field")

    # Show top bug creators
    print("\n" + "=" * 100)
    print("TOP BUG CREATORS (Top 15):")
    print("=" * 100)
    sorted_creators = sorted(creator_counts.items(), key=lambda x: x[1], reverse=True)
    for creator, count in sorted_creators[:15]:
        print(f"  {count:4d} bugs - {creator}")

    # Summary
    print("\n" + "=" * 100)
    print("SUMMARY:")
    print("=" * 100)
    print(f"Total bugs analyzed: {len(bugs)}")
    print(f"Bugs created by ArmorCode: {len(armorcode_bugs)}")

    if len(armorcode_bugs) > 0:
        pct = (len(armorcode_bugs) / len(bugs)) * 100
        print(f"Percentage: {pct:.1f}%")
        print(f"\n⚠️  WARNING: {len(armorcode_bugs)} security bugs detected!")
        print("   These should be EXCLUDED from quality metrics to avoid double-counting.")
        print("\n   Recommendation:")
        print("   - Update ado_quality_metrics.py to filter out bugs where CreatedBy contains 'ArmorCode'")
        print("   - Keep these bugs ONLY in the Security Dashboard")
    else:
        print("\n✓ No ArmorCode integration detected via CreatedBy field")
        print("  (ArmorCode may not be auto-creating bugs in ADO)")

else:
    print("No bugs found")
