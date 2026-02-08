#!/usr/bin/env python3
"""
Work Type Breakdown Analysis - Show what teams are actually working on

Analyzes:
1. Open items (current WIP) - by work type
2. Closed items (last 90 days) - by work type
3. What % would be MISSING if we only track bugs

Shows: Are teams spending time on Bugs, Stories, Tasks, or what?
"""

import os
import sys
from collections import Counter
from datetime import datetime, timedelta

from azure.devops.connection import Connection
from azure.devops.v7_1.work_item_tracking import Wiql
from dotenv import load_dotenv
from msrest.authentication import BasicAuthentication

load_dotenv()


def get_ado_connection():
    """Get ADO connection"""
    organization_url = os.getenv('ADO_ORGANIZATION_URL')
    pat = os.getenv('ADO_PAT')

    if not organization_url or not pat:
        raise ValueError("ADO_ORGANIZATION_URL and ADO_PAT must be set in .env file")

    credentials = BasicAuthentication('', pat)
    connection = Connection(base_url=organization_url, creds=credentials)
    return connection


def analyze_project_work_types(wit_client, project_name: str):
    """
    Analyze work type distribution for Flow-relevant items.
    """
    print(f"\n{'='*80}")
    print(f"PROJECT: {project_name}")
    print(f"{'='*80}\n")

    lookback_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

    # Query 1: Open items (Flow WIP)
    wiql_open = Wiql(
        query=f"""
        SELECT [System.Id], [System.WorkItemType]
        FROM WorkItems
        WHERE [System.TeamProject] = '{project_name}'
          AND [System.State] NOT IN ('Closed', 'Removed')
        """  # nosec B608 - Experimental script, not production code
    )

    # Query 2: Closed in last 90 days (Flow lead time)
    wiql_closed = Wiql(
        query=f"""
        SELECT [System.Id], [System.WorkItemType]
        FROM WorkItems
        WHERE [System.TeamProject] = '{project_name}'
          AND [System.State] = 'Closed'
          AND [Microsoft.VSTS.Common.ClosedDate] >= '{lookback_date}'
        """  # nosec B608 - Experimental script, not production code
    )

    try:
        # Get open items
        print("Analyzing OPEN items (current WIP)...")
        open_result = wit_client.query_by_wiql(wiql_open).work_items
        open_count = len(open_result) if open_result else 0

        if open_count > 0:
            # Fetch work types in batches
            open_types = Counter()
            for i in range(0, len(open_result), 200):
                batch_ids = [item.id for item in open_result[i:i+200]]
                batch_items = wit_client.get_work_items(
                    ids=batch_ids,
                    fields=['System.WorkItemType']
                )
                for item in batch_items:
                    work_type = item.fields.get('System.WorkItemType', 'Unknown')
                    open_types[work_type] += 1

            print(f"  Total: {open_count:,} open items\n")
            print("  Breakdown:")
            for wtype, count in open_types.most_common():
                pct = (count / open_count * 100)
                print(f"    {wtype:<20} {count:>6,} ({pct:>5.1f}%)")

            bugs_pct = (open_types.get('Bug', 0) / open_count * 100)
            missing_pct = 100 - bugs_pct
            print("\n  ⚠️  If tracking BUGS ONLY:")
            print(f"    Would track: {open_types.get('Bug', 0):,} items ({bugs_pct:.1f}%)")
            print(f"    Would MISS:  {open_count - open_types.get('Bug', 0):,} items ({missing_pct:.1f}%)")

        else:
            print("  No open items found\n")

        # Get closed items
        print("\nAnalyzing CLOSED items (last 90 days - Lead Time data)...")
        closed_result = wit_client.query_by_wiql(wiql_closed).work_items
        closed_count = len(closed_result) if closed_result else 0

        if closed_count > 0:
            # Fetch work types in batches
            closed_types = Counter()
            for i in range(0, len(closed_result), 200):
                batch_ids = [item.id for item in closed_result[i:i+200]]
                batch_items = wit_client.get_work_items(
                    ids=batch_ids,
                    fields=['System.WorkItemType']
                )
                for item in batch_items:
                    work_type = item.fields.get('System.WorkItemType', 'Unknown')
                    closed_types[work_type] += 1

            print(f"  Total: {closed_count:,} closed items\n")
            print("  Breakdown:")
            for wtype, count in closed_types.most_common():
                pct = (count / closed_count * 100)
                print(f"    {wtype:<20} {count:>6,} ({pct:>5.1f}%)")

            bugs_pct = (closed_types.get('Bug', 0) / closed_count * 100)
            missing_pct = 100 - bugs_pct
            print("\n  ⚠️  If tracking BUGS ONLY:")
            print(f"    Would track: {closed_types.get('Bug', 0):,} items ({bugs_pct:.1f}%)")
            print(f"    Would MISS:  {closed_count - closed_types.get('Bug', 0):,} items ({missing_pct:.1f}%)")

        else:
            print("  No closed items in last 90 days\n")

        return {
            'project_name': project_name,
            'open_count': open_count,
            'open_types': dict(open_types) if open_count > 0 else {},
            'closed_count': closed_count,
            'closed_types': dict(closed_types) if closed_count > 0 else {}
        }

    except Exception as e:
        print(f"  [ERROR] Failed to analyze: {e}\n")
        return None


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    print("="*80)
    print("WORK TYPE BREAKDOWN ANALYSIS - What are teams actually working on?")
    print("="*80)

    # Load discovered projects
    try:
        import json
        with open(".tmp/observatory/ado_structure.json", encoding='utf-8') as f:
            discovery_data = json.load(f)
        projects = discovery_data['projects']
        print(f"\nAnalyzing {len(projects)} projects\n")
    except FileNotFoundError:
        print("\n[ERROR] Project discovery file not found.")
        exit(1)

    # Connect to ADO
    try:
        connection = get_ado_connection()
        wit_client = connection.clients.get_work_item_tracking_client()
    except Exception as e:
        print(f"[ERROR] Failed to connect to ADO: {e}")
        exit(1)

    # Analyze each project
    results = []
    for project in projects:
        result = analyze_project_work_types(wit_client, project['project_name'])
        if result:
            results.append(result)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY - ACROSS ALL PROJECTS")
    print("="*80)

    total_open = sum(r['open_count'] for r in results)
    total_closed = sum(r['closed_count'] for r in results)

    # Aggregate work types
    all_open_types = Counter()
    all_closed_types = Counter()

    for r in results:
        for wtype, count in r['open_types'].items():
            all_open_types[wtype] += count
        for wtype, count in r['closed_types'].items():
            all_closed_types[wtype] += count

    print(f"\nOPEN ITEMS (Current WIP): {total_open:,} total")
    for wtype, count in all_open_types.most_common():
        pct = (count / total_open * 100) if total_open > 0 else 0
        print(f"  {wtype:<20} {count:>6,} ({pct:>5.1f}%)")

    if total_open > 0:
        bugs_open = all_open_types.get('Bug', 0)
        bugs_pct = (bugs_open / total_open * 100)
        print(f"\n⚠️  BUGS-ONLY would track: {bugs_open:,} / {total_open:,} ({bugs_pct:.1f}%)")
        print(f"    MISSING: {total_open - bugs_open:,} items ({100-bugs_pct:.1f}%)")

    print(f"\n\nCLOSED ITEMS (Last 90 days - Lead Time): {total_closed:,} total")
    for wtype, count in all_closed_types.most_common():
        pct = (count / total_closed * 100) if total_closed > 0 else 0
        print(f"  {wtype:<20} {count:>6,} ({pct:>5.1f}%)")

    if total_closed > 0:
        bugs_closed = all_closed_types.get('Bug', 0)
        bugs_pct = (bugs_closed / total_closed * 100)
        print(f"\n⚠️  BUGS-ONLY would track: {bugs_closed:,} / {total_closed:,} ({bugs_pct:.1f}%)")
        print(f"    MISSING: {total_closed - bugs_closed:,} items ({100-bugs_pct:.1f}%)")

    print("\n" + "="*80)
    print("DECISION POINT:")
    print("="*80)
    print("\nBased on this data:")
    print("  • Should Flow Dashboard track BUGS ONLY?")
    print("  • Or should it track ALL work types?")
    print("  • Or should it show SEPARATE metrics for each type?")
    print("\nThis data shows what % of team work you'd be missing with bugs-only.\n")
