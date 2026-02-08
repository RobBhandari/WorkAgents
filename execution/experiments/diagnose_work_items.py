#!/usr/bin/env python3
"""
Work Item Diagnostic Tool - Analyze what's in the 11,000+ items

Provides breakdown by:
- State (New, Active, Closed, etc.)
- Work Item Type (Bug, Task, Story, Feature, Epic)
- Iteration assignment (in sprint vs backlog)
- Age distribution
- Activity patterns
- Assignment status
- Priority

Helps determine optimal filters for committed work vs backlog noise.
"""

import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from azure.devops.connection import Connection
from azure.devops.v7_1.work_item_tracking import Wiql
from dotenv import load_dotenv
from msrest.authentication import BasicAuthentication

load_dotenv()


def get_ado_connection():
    """Get ADO connection using credentials from .env"""
    organization_url = os.getenv('ADO_ORGANIZATION_URL')
    pat = os.getenv('ADO_PAT')

    if not organization_url or not pat:
        raise ValueError("ADO_ORGANIZATION_URL and ADO_PAT must be set in .env file")

    credentials = BasicAuthentication('', pat)
    connection = Connection(base_url=organization_url, creds=credentials)
    return connection


def analyze_project_work_items(wit_client, project_name: str):
    """
    Analyze ALL work items in a project to understand composition.
    """
    print(f"\n{'='*80}")
    print(f"ANALYZING PROJECT: {project_name}")
    print(f"{'='*80}\n")

    # Query ALL work items (no filters except project)
    wiql = Wiql(
        query=f"""
        SELECT [System.Id], [System.WorkItemType], [System.State],
               [System.CreatedDate], [System.ChangedDate], [System.AssignedTo],
               [System.IterationPath], [Microsoft.VSTS.Common.Priority]
        FROM WorkItems
        WHERE [System.TeamProject] = '{project_name}'
        ORDER BY [System.CreatedDate] DESC
        """  # nosec B608 - Experimental script, not production code
    )

    try:
        print("Querying all work items...")
        result = wit_client.query_by_wiql(wiql).work_items

        if not result or len(result) == 0:
            print(f"  [WARNING] No work items found in project {project_name}")
            return None

        total_count = len(result)
        print(f"  Found {total_count:,} total work items\n")

        # Fetch full details in batches
        print("Fetching work item details...")
        all_items = []
        batch_size = 200

        for i in range(0, len(result), batch_size):
            batch_ids = [item.id for item in result[i:i+batch_size]]
            try:
                batch_items = wit_client.get_work_items(
                    ids=batch_ids,
                    fields=[
                        'System.Id', 'System.WorkItemType', 'System.State',
                        'System.CreatedDate', 'System.ChangedDate', 'System.AssignedTo',
                        'System.IterationPath', 'Microsoft.VSTS.Common.Priority',
                        'System.Title'
                    ]
                )
                all_items.extend([item.fields for item in batch_items])
                print(f"  Fetched {len(all_items):,} / {total_count:,} items...", end='\r')
            except Exception as e:
                print(f"\n  [WARNING] Error fetching batch: {e}")
                continue

        print(f"\n  Successfully fetched {len(all_items):,} items\n")

        # Analyze the items
        analyze_and_report(all_items, project_name)

    except Exception as e:
        print(f"  [ERROR] Failed to query work items: {e}")
        return None


def analyze_and_report(items, project_name):
    """
    Analyze work items and generate diagnostic report.
    """
    now = datetime.now()

    # Initialize counters
    state_counts = Counter()
    type_counts = Counter()
    priority_counts = Counter()
    iteration_counts = {'Has Sprint': 0, 'Backlog (No Sprint)': 0}
    assignment_counts = {'Assigned': 0, 'Unassigned': 0}
    age_buckets = {
        '0-30 days': 0,
        '31-90 days': 0,
        '91-180 days': 0,
        '181-365 days': 0,
        '1-2 years': 0,
        '2+ years': 0
    }
    activity_buckets = {
        'Last 7 days': 0,
        'Last 30 days': 0,
        'Last 90 days': 0,
        'Last 180 days': 0,
        'Last 365 days': 0,
        '1+ year ago': 0
    }

    # Commitment signal analysis
    committed_work = {
        'Has Sprint': 0,
        'Active State': 0,
        'Recent Activity (90d)': 0,
        'High Priority (P0/P1)': 0,
        'Assigned': 0,
        'Meets ANY criteria': set(),
        'Meets ALL criteria': set()
    }

    print(f"{'='*80}")
    print(f"DIAGNOSTIC REPORT: {project_name}")
    print(f"{'='*80}\n")

    # Analyze each item
    for item in items:
        item_id = item.get('System.Id')
        work_type = item.get('System.WorkItemType', 'Unknown')
        state = item.get('System.State', 'Unknown')
        created = item.get('System.CreatedDate')
        changed = item.get('System.ChangedDate')
        assigned_to = item.get('System.AssignedTo')
        iteration = item.get('System.IterationPath', '')
        priority = item.get('Microsoft.VSTS.Common.Priority')

        # Count by dimensions
        state_counts[state] += 1
        type_counts[work_type] += 1

        if priority is not None:
            priority_counts[f'P{priority}'] += 1
        else:
            priority_counts['No Priority'] += 1

        # Iteration assignment
        if iteration and ('Sprint' in iteration or 'Iteration' in iteration):
            iteration_counts['Has Sprint'] += 1
        else:
            iteration_counts['Backlog (No Sprint)'] += 1

        # Assignment
        if assigned_to:
            assignment_counts['Assigned'] += 1
        else:
            assignment_counts['Unassigned'] += 1

        # Age analysis
        if created:
            try:
                created_dt = datetime.fromisoformat(str(created).replace('Z', '+00:00'))
                days_old = (now - created_dt.astimezone()).total_seconds() / 86400

                if days_old <= 30:
                    age_buckets['0-30 days'] += 1
                elif days_old <= 90:
                    age_buckets['31-90 days'] += 1
                elif days_old <= 180:
                    age_buckets['91-180 days'] += 1
                elif days_old <= 365:
                    age_buckets['181-365 days'] += 1
                elif days_old <= 730:
                    age_buckets['1-2 years'] += 1
                else:
                    age_buckets['2+ years'] += 1
            except:
                pass

        # Activity analysis
        if changed:
            try:
                changed_dt = datetime.fromisoformat(str(changed).replace('Z', '+00:00'))
                days_since_change = (now - changed_dt.astimezone()).total_seconds() / 86400

                if days_since_change <= 7:
                    activity_buckets['Last 7 days'] += 1
                elif days_since_change <= 30:
                    activity_buckets['Last 30 days'] += 1
                elif days_since_change <= 90:
                    activity_buckets['Last 90 days'] += 1
                elif days_since_change <= 180:
                    activity_buckets['Last 180 days'] += 1
                elif days_since_change <= 365:
                    activity_buckets['Last 365 days'] += 1
                else:
                    activity_buckets['1+ year ago'] += 1
            except:
                pass

        # Commitment signal analysis
        has_sprint = bool(iteration and ('Sprint' in iteration or 'Iteration' in iteration))
        is_active_state = state in ('Active', 'In Progress', 'Committed', 'Resolved')
        is_recent = False
        if changed:
            try:
                changed_dt = datetime.fromisoformat(str(changed).replace('Z', '+00:00'))
                is_recent = (now - changed_dt.astimezone()).total_seconds() / 86400 <= 90
            except:
                pass
        is_high_priority = priority is not None and priority <= 1
        is_assigned = bool(assigned_to)

        if has_sprint:
            committed_work['Has Sprint'] += 1
        if is_active_state:
            committed_work['Active State'] += 1
        if is_recent:
            committed_work['Recent Activity (90d)'] += 1
        if is_high_priority:
            committed_work['High Priority (P0/P1)'] += 1
        if is_assigned:
            committed_work['Assigned'] += 1

        # Track items meeting criteria
        if any([has_sprint, is_active_state, is_recent, is_high_priority]):
            committed_work['Meets ANY criteria'].add(item_id)

        if all([has_sprint or is_active_state, is_assigned]):
            committed_work['Meets ALL criteria'].add(item_id)

    total = len(items)

    # Print Report
    print(f"📊 TOTAL WORK ITEMS: {total:,}\n")

    print(f"{'─'*80}")
    print("1. WORK ITEM TYPE DISTRIBUTION")
    print(f"{'─'*80}")
    for wtype, count in type_counts.most_common():
        pct = (count / total * 100)
        print(f"  {wtype:<25} {count:>6,} ({pct:>5.1f}%)")

    print(f"\n{'─'*80}")
    print("2. STATE DISTRIBUTION")
    print(f"{'─'*80}")
    for state, count in state_counts.most_common():
        pct = (count / total * 100)
        print(f"  {state:<25} {count:>6,} ({pct:>5.1f}%)")

    print(f"\n{'─'*80}")
    print("3. ITERATION/SPRINT ASSIGNMENT")
    print(f"{'─'*80}")
    for status, count in iteration_counts.items():
        pct = (count / total * 100)
        print(f"  {status:<25} {count:>6,} ({pct:>5.1f}%)")

    print(f"\n{'─'*80}")
    print("4. ASSIGNMENT STATUS")
    print(f"{'─'*80}")
    for status, count in assignment_counts.items():
        pct = (count / total * 100)
        print(f"  {status:<25} {count:>6,} ({pct:>5.1f}%)")

    print(f"\n{'─'*80}")
    print("5. PRIORITY DISTRIBUTION")
    print(f"{'─'*80}")
    for priority, count in sorted(priority_counts.items()):
        pct = (count / total * 100)
        print(f"  {priority:<25} {count:>6,} ({pct:>5.1f}%)")

    print(f"\n{'─'*80}")
    print("6. AGE DISTRIBUTION (Time Since Created)")
    print(f"{'─'*80}")
    for age_range in ['0-30 days', '31-90 days', '91-180 days', '181-365 days', '1-2 years', '2+ years']:
        count = age_buckets[age_range]
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {age_range:<25} {count:>6,} ({pct:>5.1f}%)")

    print(f"\n{'─'*80}")
    print("7. ACTIVITY DISTRIBUTION (Time Since Last Change)")
    print(f"{'─'*80}")
    for period in ['Last 7 days', 'Last 30 days', 'Last 90 days', 'Last 180 days', 'Last 365 days', '1+ year ago']:
        count = activity_buckets[period]
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {period:<25} {count:>6,} ({pct:>5.1f}%)")

    print(f"\n{'='*80}")
    print("🎯 COMMITMENT SIGNAL ANALYSIS")
    print(f"{'='*80}")
    print("\nIndividual Signals:")
    for signal, count in committed_work.items():
        if signal not in ['Meets ANY criteria', 'Meets ALL criteria']:
            pct = (count / total * 100) if total > 0 else 0
            print(f"  {signal:<30} {count:>6,} ({pct:>5.1f}%)")

    meets_any = len(committed_work['Meets ANY criteria'])
    meets_all = len(committed_work['Meets ALL criteria'])

    print("\nCombined Filters:")
    print(f"  {'Items meeting ANY criteria':<30} {meets_any:>6,} ({meets_any/total*100:>5.1f}%)")
    print(f"  {'Items meeting ALL criteria':<30} {meets_all:>6,} ({meets_all/total*100:>5.1f}%)")

    print(f"\n{'='*80}")
    print("💡 RECOMMENDATIONS")
    print(f"{'='*80}\n")

    backlog_pct = (iteration_counts['Backlog (No Sprint)'] / total * 100)
    stale_pct = (activity_buckets['1+ year ago'] / total * 100)

    if backlog_pct > 70:
        print(f"  ⚠️  {backlog_pct:.0f}% of items have NO sprint assignment (backlog noise)")
        print("      Recommend: Filter to items WITH iteration path\n")

    if stale_pct > 50:
        print(f"  ⚠️  {stale_pct:.0f}% of items haven't been touched in 1+ year (stale)")
        print("      Recommend: Filter to items changed in last 90-180 days\n")

    new_state_pct = (state_counts.get('New', 0) / total * 100)
    if new_state_pct > 60:
        print(f"  ⚠️  {new_state_pct:.0f}% of items in 'New' state (not started)")
        print("      Recommend: Filter to Active/In Progress/Committed states\n")

    print("  ✅ RECOMMENDED FILTER:")
    print("     Items meeting ANY of:")
    print("     - Has sprint/iteration assignment")
    print("     - State is Active/In Progress/Committed/Resolved")
    print("     - Changed in last 90 days")
    print("     - Priority P0 or P1")
    print(f"\n     This would reduce {total:,} → {meets_any:,} items ({meets_any/total*100:.1f}%)\n")

    reduction_pct = ((total - meets_any) / total * 100)
    print(f"  📉 Noise reduction: {reduction_pct:.0f}% ({total - meets_any:,} items filtered out)\n")


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    print("="*80)
    print("WORK ITEM DIAGNOSTIC TOOL")
    print("="*80)

    # Load discovered projects
    try:
        import json
        with open(".tmp/observatory/ado_structure.json", encoding='utf-8') as f:
            discovery_data = json.load(f)
        projects = discovery_data['projects']
        print(f"\nFound {len(projects)} projects from discovery")
    except FileNotFoundError:
        print("\n[ERROR] Project discovery file not found.")
        print("Run: python execution/discover_projects.py")
        exit(1)

    # Connect to ADO
    print("\nConnecting to Azure DevOps...")
    try:
        connection = get_ado_connection()
        wit_client = connection.clients.get_work_item_tracking_client()
        print("[SUCCESS] Connected to ADO\n")
    except Exception as e:
        print(f"[ERROR] Failed to connect to ADO: {e}")
        exit(1)

    # Analyze each project (or selected projects)
    for project in projects[:3]:  # Analyze first 3 projects (remove limit if you want all)
        try:
            analyze_project_work_items(wit_client, project['project_name'])
        except Exception as e:
            print(f"\n[ERROR] Failed to analyze {project['project_name']}: {e}\n")
            continue

    print("\n" + "="*80)
    print("DIAGNOSTIC COMPLETE")
    print("="*80)
    print("\nUse this analysis to determine optimal filters for:")
    print("  - Flow Dashboard (committed work only)")
    print("  - Ownership Dashboard (active items)")
    print("  - Quality/Risk Dashboards (already correctly scoped)")
