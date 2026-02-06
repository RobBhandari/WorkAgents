#!/usr/bin/env python3
"""
ADO Quality Metrics Collector for Director Observatory

Collects quality and defect metrics at project level:
- Reopen Rate: % of bugs that are reopened after being closed
- Escaped Defect Rate: % of bugs found in production (vs test/dev)
- Bug Age Distribution: How long bugs stay open
- Quality Debt Index: Weighted score based on age, severity, reopen count
- Fix Quality: % of bugs that stay fixed (no reopen within 30 days)

Read-only operation - does not modify any existing data.
"""

import os
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import statistics

# Azure DevOps SDK
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from azure.devops.v7_1.work_item_tracking import Wiql

# Load environment variables
from dotenv import load_dotenv
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


def query_bugs_for_quality(wit_client, project_name: str, lookback_days: int = 90, area_path_filter: str = None) -> Dict:
    """
    Query bugs for quality metrics.

    Args:
        wit_client: Work Item Tracking client
        project_name: ADO project name
        lookback_days: How many days back to look for bugs
        area_path_filter: Optional area path filter (format: "EXCLUDE:path" or "INCLUDE:path")

    Returns:
        Dictionary with categorized bugs
    """
    lookback_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

    print(f"    Querying bugs for {project_name}...")

    # Build area path filter clause
    area_filter_clause = ""
    if area_path_filter:
        if area_path_filter.startswith("EXCLUDE:"):
            path = area_path_filter.replace("EXCLUDE:", "")
            area_filter_clause = f"AND [System.AreaPath] NOT UNDER '{path}'"
            print(f"      Excluding area path: {path}")
        elif area_path_filter.startswith("INCLUDE:"):
            path = area_path_filter.replace("INCLUDE:", "")
            area_filter_clause = f"AND [System.AreaPath] UNDER '{path}'"
            print(f"      Including only area path: {path}")

    # Query 1: All bugs (for overall quality assessment)
    wiql_all_bugs = Wiql(
        query=f"""
        SELECT [System.Id], [System.Title], [System.State], [System.CreatedDate],
               [System.WorkItemType], [Microsoft.VSTS.Common.Priority],
               [Microsoft.VSTS.Common.Severity], [System.Tags],
               [Microsoft.VSTS.Common.ClosedDate], [Microsoft.VSTS.Common.ResolvedDate]
        FROM WorkItems
        WHERE [System.TeamProject] = '{project_name}'
          AND [System.WorkItemType] = 'Bug'
          AND [System.CreatedDate] >= '{lookback_date}'
          {area_filter_clause}
        ORDER BY [System.CreatedDate] DESC
        """
    )

    # Query 2: Currently open bugs (for aging analysis)
    wiql_open_bugs = Wiql(
        query=f"""
        SELECT [System.Id], [System.Title], [System.State], [System.CreatedDate],
               [System.WorkItemType], [Microsoft.VSTS.Common.Priority],
               [Microsoft.VSTS.Common.Severity], [System.Tags]
        FROM WorkItems
        WHERE [System.TeamProject] = '{project_name}'
          AND [System.WorkItemType] = 'Bug'
          AND [System.State] <> 'Closed'
          AND [System.State] <> 'Removed'
          AND ([Microsoft.VSTS.Common.Triage] <> 'Rejected' OR [Microsoft.VSTS.Common.Triage] = '')
          {area_filter_clause}
        ORDER BY [System.CreatedDate] ASC
        """
    )

    try:
        # Execute queries
        all_bugs_result = wit_client.query_by_wiql(wiql_all_bugs).work_items
        open_bugs_result = wit_client.query_by_wiql(wiql_open_bugs).work_items

        print(f"      Found {len(all_bugs_result) if all_bugs_result else 0} total bugs (last {lookback_days} days)")
        print(f"      Found {len(open_bugs_result) if open_bugs_result else 0} open bugs")

        # Fetch full bug details with batching (200 per batch)
        all_bugs = []
        if all_bugs_result and len(all_bugs_result) > 0:
            all_bug_ids = [item.id for item in all_bugs_result]  # Fetch ALL bugs for accurate metrics
            try:
                for i in range(0, len(all_bug_ids), 200):
                    batch_ids = all_bug_ids[i:i+200]
                    batch_bugs = wit_client.get_work_items(
                        ids=batch_ids,
                        fields=['System.Id', 'System.Title', 'System.State', 'System.CreatedDate',
                                'System.WorkItemType', 'Microsoft.VSTS.Common.Priority',
                                'Microsoft.VSTS.Common.Severity', 'System.Tags',
                                'Microsoft.VSTS.Common.ClosedDate', 'Microsoft.VSTS.Common.ResolvedDate',
                                'System.CreatedBy']
                        # Note: Cannot use expand='Relations' with fields parameter
                    )
                    all_bugs.extend([item.fields for item in batch_bugs])
            except Exception as e:
                print(f"      [WARNING] Error fetching all bugs: {e}")

        open_bugs = []
        if open_bugs_result and len(open_bugs_result) > 0:
            open_bug_ids = [item.id for item in open_bugs_result]  # Fetch ALL open bugs for accurate metrics
            try:
                for i in range(0, len(open_bug_ids), 200):
                    batch_ids = open_bug_ids[i:i+200]
                    batch_bugs = wit_client.get_work_items(
                        ids=batch_ids,
                        fields=['System.Id', 'System.Title', 'System.State', 'System.CreatedDate',
                                'System.WorkItemType', 'Microsoft.VSTS.Common.Priority',
                                'Microsoft.VSTS.Common.Severity', 'System.Tags', 'System.CreatedBy']
                    )
                    open_bugs.extend([item.fields for item in batch_bugs])
            except Exception as e:
                print(f"      [WARNING] Error fetching open bugs: {e}")

        return {
            "all_bugs": all_bugs,
            "open_bugs": open_bugs
        }

    except Exception as e:
        print(f"      [ERROR] Failed to query bugs: {e}")
        return {
            "all_bugs": [],
            "open_bugs": []
        }


# REMOVED: calculate_reopen_rate
# Reason: Proxy calculation using current state, not actual revision history.
# Cannot reliably distinguish true reopens from state corrections or data issues.
# Would require querying work item revision history for accurate tracking.


# REMOVED: calculate_escaped_defects
# Reason: Pure speculation based on keyword matching. No field tracks who actually found the bug.
# Cannot reliably distinguish customer-found bugs from internally-found production bugs.


def filter_security_bugs(bugs: List[Dict]) -> tuple:
    """
    Filter out security bugs created by ArmorCode to avoid double-counting.

    These bugs are already tracked in the Security Dashboard, so we exclude them
    from quality metrics to prevent inflating bug counts.

    Excludes bugs if:
    - Created by ArmorCode (creator name contains 'armorcode')
    - Tagged with ArmorCode (tags contain 'armorcode')

    Returns:
        tuple: (filtered_bugs, excluded_count)
    """
    filtered = []
    excluded = 0

    for bug in bugs:
        created_by = bug.get('System.CreatedBy', {})
        tags = bug.get('System.Tags', '')

        # Extract creator name
        if isinstance(created_by, dict):
            creator_name = created_by.get('displayName', '').lower()
        else:
            creator_name = str(created_by).lower()

        # Extract tags (handle as string, typically semicolon-separated)
        tags_str = str(tags).lower() if tags else ''

        # Exclude bugs created by ArmorCode OR tagged with armorcode
        if 'armorcode' in creator_name or 'armorcode' in tags_str:
            excluded += 1
        else:
            filtered.append(bug)

    return filtered, excluded


def calculate_bug_age_distribution(open_bugs: List[Dict]) -> Dict:
    """
    Calculate bug age distribution: How long bugs have been open.

    Returns age distribution metrics
    """
    from datetime import timezone
    now = datetime.now(timezone.utc)  # Make timezone-aware to match Azure DevOps dates
    ages = []
    parse_errors = 0

    for bug in open_bugs:
        created = bug.get('System.CreatedDate')

        if created:
            try:
                created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                age_days = (now - created_dt).total_seconds() / 86400
                ages.append(age_days)
            except Exception as e:
                parse_errors += 1
                # Log first few errors to help debug
                if parse_errors <= 3:
                    print(f"      [WARNING] Could not parse date for bug {bug.get('System.Id')}: {created} - {e}")
                continue

    if parse_errors > 0:
        print(f"      [WARNING] Failed to parse {parse_errors} out of {len(open_bugs)} open bug dates")

    if not ages:
        return {
            "median_age_days": None,
            "p85_age_days": None,
            "p95_age_days": None,
            "sample_size": 0,
            "ages_distribution": {
                "0-7_days": 0,
                "8-30_days": 0,
                "31-90_days": 0,
                "90+_days": 0
            }
        }

    sorted_ages = sorted(ages)

    return {
        "median_age_days": round(sorted_ages[len(sorted_ages) // 2], 1) if ages else None,
        "p85_age_days": round(sorted_ages[int(len(sorted_ages) * 0.85)], 1) if ages else None,
        "p95_age_days": round(sorted_ages[int(len(sorted_ages) * 0.95)], 1) if ages else None,
        "sample_size": len(ages),
        "ages_distribution": {
            "0-7_days": sum(1 for age in ages if age <= 7),
            "8-30_days": sum(1 for age in ages if 7 < age <= 30),
            "31-90_days": sum(1 for age in ages if 30 < age <= 90),
            "90+_days": sum(1 for age in ages if age > 90)
        }
    }


# REMOVED: calculate_quality_debt_index
# Reason: Invented formula with arbitrary severity weights (Critical=5, High=3, etc.).
# No industry standard or business validation for this calculation.
# Weights and formula are speculation, not based on actual business impact.


def calculate_mttr(all_bugs: List[Dict]) -> Dict:
    """
    Calculate MTTR (Mean Time To Repair): Average time from bug creation to closure.

    Returns MTTR metrics in days
    """
    repair_times = []

    for bug in all_bugs:
        created_date = bug.get('System.CreatedDate')
        closed_date = bug.get('Microsoft.VSTS.Common.ClosedDate')

        # Only calculate for bugs that have been closed
        if created_date and closed_date:
            try:
                created_dt = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
                closed_dt = datetime.fromisoformat(closed_date.replace('Z', '+00:00'))

                # Calculate repair time in days
                repair_time_days = (closed_dt - created_dt).total_seconds() / 86400

                # Filter out negative values (data quality issue)
                if repair_time_days >= 0:
                    repair_times.append(repair_time_days)
            except Exception as e:
                continue

    if not repair_times:
        return {
            "mttr_days": None,
            "median_mttr_days": None,
            "p85_mttr_days": None,
            "p95_mttr_days": None,
            "sample_size": 0,
            "mttr_distribution": {
                "0-1_days": 0,
                "1-7_days": 0,
                "7-30_days": 0,
                "30+_days": 0
            }
        }

    sorted_times = sorted(repair_times)
    mean_mttr = sum(repair_times) / len(repair_times)

    return {
        "mttr_days": round(mean_mttr, 1),
        "median_mttr_days": round(sorted_times[len(sorted_times) // 2], 1),
        "p85_mttr_days": round(sorted_times[int(len(sorted_times) * 0.85)], 1),
        "p95_mttr_days": round(sorted_times[int(len(sorted_times) * 0.95)], 1),
        "sample_size": len(repair_times),
        "mttr_distribution": {
            "0-1_days": sum(1 for t in repair_times if t <= 1),
            "1-7_days": sum(1 for t in repair_times if 1 < t <= 7),
            "7-30_days": sum(1 for t in repair_times if 7 < t <= 30),
            "30+_days": sum(1 for t in repair_times if t > 30)
        }
    }


# REMOVED: calculate_fix_quality
# Reason: Same proxy issue as reopen rate - checks current state, not actual reopening events.
# Cannot reliably track if bugs stayed fixed without revision history.


def calculate_test_execution_time(test_client, project_name: str) -> Dict:
    """
    Calculate test execution time from recent test runs.

    HARD DATA: Actual test run completed_date - started_date.

    Args:
        test_client: Test client
        project_name: ADO project name

    Returns:
        Test execution time metrics
    """
    try:
        # Get recent test runs
        test_runs = test_client.get_test_runs(project=project_name, top=50)

        execution_times = []

        for run in test_runs:
            if run.started_date and run.completed_date:
                try:
                    duration = run.completed_date - run.started_date
                    duration_minutes = duration.total_seconds() / 60

                    if duration_minutes > 0:
                        execution_times.append(duration_minutes)
                except Exception:
                    continue

        if not execution_times:
            return {
                'sample_size': 0,
                'median_minutes': None,
                'p85_minutes': None,
                'p95_minutes': None
            }

        sorted_times = sorted(execution_times)
        n = len(sorted_times)

        def percentile(data, p):
            index = int(n * p / 100)
            return data[min(index, n - 1)]

        return {
            'sample_size': n,
            'median_minutes': round(statistics.median(execution_times), 1),
            'p85_minutes': round(percentile(sorted_times, 85), 1),
            'p95_minutes': round(percentile(sorted_times, 95), 1)
        }

    except Exception as e:
        print(f"      [WARNING] Could not calculate test execution time: {e}")
        return {
            'sample_size': 0,
            'median_minutes': None,
            'p85_minutes': None,
            'p95_minutes': None
        }


def collect_quality_metrics_for_project(connection, project: Dict, config: Dict) -> Dict:
    """
    Collect all quality metrics for a single project.

    Args:
        connection: ADO connection
        project: Project metadata from discovery
        config: Configuration dict (thresholds, lookback days, etc.)

    Returns:
        Quality metrics dictionary for the project
    """
    project_name = project['project_name']
    project_key = project['project_key']

    # Get the actual ADO project name (may differ from display name)
    ado_project_name = project.get('ado_project_name', project_name)

    # Get area path filter if specified
    area_path_filter = project.get('area_path_filter')

    print(f"\n  Collecting quality metrics for: {project_name}")

    wit_client = connection.clients.get_work_item_tracking_client()
    test_client = connection.clients.get_test_client()

    # Query bugs
    bugs = query_bugs_for_quality(
        wit_client,
        ado_project_name,
        lookback_days=config.get('lookback_days', 90),
        area_path_filter=area_path_filter
    )

    # Filter out ArmorCode security bugs to avoid double-counting
    bugs['all_bugs'], excluded_all = filter_security_bugs(bugs['all_bugs'])
    bugs['open_bugs'], excluded_open = filter_security_bugs(bugs['open_bugs'])

    if excluded_open > 0 or excluded_all > 0:
        print(f"    Excluded {excluded_open} open security bugs and {excluded_all} total security bugs from quality metrics")

    # Calculate metrics - ONLY HARD DATA
    age_distribution = calculate_bug_age_distribution(bugs['open_bugs'])
    mttr = calculate_mttr(bugs['all_bugs'])
    test_execution = calculate_test_execution_time(test_client, ado_project_name)

    print(f"    Median Bug Age: {age_distribution['median_age_days']} days")
    print(f"    MTTR: {mttr['mttr_days']} days (median: {mttr['median_mttr_days']})")
    print(f"    Test Execution Time: {test_execution['median_minutes']} minutes (median)")

    return {
        "project_key": project_key,
        "project_name": project_name,
        "bug_age_distribution": age_distribution,
        "mttr": mttr,
        "test_execution_time": test_execution,  # NEW
        "total_bugs_analyzed": len(bugs['all_bugs']),
        "open_bugs_count": len(bugs['open_bugs']),
        "excluded_security_bugs": {
            "total": excluded_all,
            "open": excluded_open
        },
        "collected_at": datetime.now().isoformat()
    }


def save_quality_metrics(metrics: Dict, output_file: str = ".tmp/observatory/quality_history.json"):
    """
    Save quality metrics to history file.

    Appends to existing history or creates new file.
    Validates data before saving to prevent persisting collection failures.
    """
    # Validate that we have actual data before saving
    projects = metrics.get('projects', [])

    if not projects:
        print("\n[SKIPPED] No project data to save - collection may have failed")
        return False

    # Check if this looks like a failed collection (all zeros)
    total_bugs = sum(p.get('total_bugs_analyzed', 0) for p in projects)
    total_open = sum(p.get('open_bugs_count', 0) for p in projects)

    if total_bugs == 0 and total_open == 0:
        print("\n[SKIPPED] All projects returned zero bugs - likely a collection failure")
        print("          Not persisting this data to avoid corrupting trend history")
        return False

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Load existing history
    history = {"weeks": []}
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            history = json.load(f)

    # Add new week entry
    history['weeks'].append(metrics)

    # Keep only last 52 weeks (12 months) for quarter/annual analysis
    history['weeks'] = history['weeks'][-52:]

    # Save updated history
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    print(f"\n[SAVED] Quality metrics saved to: {output_file}")
    print(f"        History now contains {len(history['weeks'])} week(s)")
    return True


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    print("Director Observatory - Quality Metrics Collector\n")
    print("=" * 60)

    # Configuration
    config = {
        "lookback_days": 90,  # How many days back to look for bugs
    }

    # Load discovered projects
    try:
        with open(".tmp/observatory/ado_structure.json", 'r', encoding='utf-8') as f:
            discovery_data = json.load(f)
        projects = discovery_data['projects']
        print(f"Loaded {len(projects)} projects from discovery")
    except FileNotFoundError:
        print("[ERROR] Project discovery file not found.")
        print("Run: python execution/discover_projects.py")
        exit(1)

    # Connect to ADO
    print("\nConnecting to Azure DevOps...")
    try:
        connection = get_ado_connection()
        print("[SUCCESS] Connected to ADO")
    except Exception as e:
        print(f"[ERROR] Failed to connect to ADO: {e}")
        exit(1)

    # Collect metrics for all projects
    print("\nCollecting quality metrics...")
    print("=" * 60)

    project_metrics = []
    for project in projects:
        try:
            metrics = collect_quality_metrics_for_project(connection, project, config)
            project_metrics.append(metrics)
        except Exception as e:
            print(f"  [ERROR] Failed to collect metrics for {project['project_name']}: {e}")
            continue

    # Save results
    week_metrics = {
        "week_date": datetime.now().strftime('%Y-%m-%d'),
        "week_number": datetime.now().isocalendar()[1],  # ISO week number
        "projects": project_metrics,
        "config": config
    }

    save_quality_metrics(week_metrics)

    # Summary
    print("\n" + "=" * 60)
    print("Quality Metrics Collection Summary:")
    print(f"  Projects processed: {len(project_metrics)}")

    total_bugs = sum(p['total_bugs_analyzed'] for p in project_metrics)
    total_open = sum(p['open_bugs_count'] for p in project_metrics)
    total_excluded = sum(p['excluded_security_bugs']['total'] for p in project_metrics)
    total_excluded_open = sum(p['excluded_security_bugs']['open'] for p in project_metrics)

    print(f"  Total bugs analyzed: {total_bugs}")
    print(f"  Total open bugs: {total_open}")

    if total_excluded > 0:
        print(f"  Security bugs excluded: {total_excluded} total ({total_excluded_open} open)")
        print(f"    → Prevents double-counting with Security Dashboard")

    # Calculate average MTTR
    mttr_values = [p['mttr']['mttr_days'] for p in project_metrics if p['mttr']['mttr_days'] is not None]
    if mttr_values:
        avg_mttr = sum(mttr_values) / len(mttr_values)
        print(f"  Avg MTTR: {round(avg_mttr, 1)} days")

    print("\nQuality metrics collection complete!")
    print("  ✓ Only hard data - no speculation")
    print("  ✓ MTTR: Actual CreatedDate → ClosedDate")
    print("  ✓ Bug Age: Actual time open")
    print("  ✓ Security bugs filtered out (no double-counting)")
    print("  ✓ Rejected bugs excluded (Triage = 'Rejected')")
    print("\nNext step: Generate quality dashboard")
