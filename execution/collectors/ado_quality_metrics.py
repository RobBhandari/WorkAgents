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

Migrated to Azure DevOps REST API v7.1 (replaces SDK).
"""

import asyncio
import json
import logging
import os
import statistics
import sys
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv

from execution.collectors.ado_rest_client import AzureDevOpsRESTClient, get_ado_rest_client
from execution.collectors.ado_rest_transformers import TestTransformer, WorkItemTransformer
from execution.collectors.security_bug_filter import filter_security_bugs
from execution.secure_config import get_config
from execution.security import WIQLValidator
from execution.utils.ado_batch_utils import batch_fetch_work_items_rest
from execution.utils.datetime_utils import calculate_age_days, calculate_lead_time_days, parse_ado_timestamp
from execution.utils.error_handling import log_and_continue, log_and_return_default
from execution.utils.statistics import calculate_percentile

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


def _build_area_filter_clause(area_path_filter: str | None) -> str:
    """
    Build WIQL area path filter clause.

    Args:
        area_path_filter: Optional area path filter (format: "EXCLUDE:path" or "INCLUDE:path")

    Returns:
        WIQL filter clause string
    """
    if not area_path_filter:
        return ""

    if area_path_filter.startswith("EXCLUDE:"):
        path = area_path_filter.replace("EXCLUDE:", "")
        # Validate area path to prevent injection
        safe_path = WIQLValidator.validate_area_path(path)
        print(f"      Excluding area path: {safe_path}")
        return f"AND [System.AreaPath] NOT UNDER '{safe_path}'"
    elif area_path_filter.startswith("INCLUDE:"):
        path = area_path_filter.replace("INCLUDE:", "")
        # Validate area path to prevent injection
        safe_path = WIQLValidator.validate_area_path(path)
        print(f"      Including only area path: {safe_path}")
        return f"AND [System.AreaPath] UNDER '{safe_path}'"

    return ""


async def _fetch_bug_details(rest_client: AzureDevOpsRESTClient, bug_ids: list[int], fields: list[str]) -> list[dict]:
    """
    Fetch full bug details using batch utility (REST API).

    Args:
        rest_client: Azure DevOps REST API client
        bug_ids: List of bug IDs to fetch
        fields: List of fields to retrieve

    Returns:
        List of bug field dictionaries

    Raises:
        Exception: If all batches fail
    """
    if not bug_ids:
        return []

    try:
        # Use REST batch fetching (concurrent)
        bugs_raw, failed_ids = await batch_fetch_work_items_rest(
            rest_client, item_ids=bug_ids, fields=fields, logger=logger
        )

        if failed_ids:
            logger.warning(f"Failed to fetch {len(failed_ids)} out of {len(bug_ids)} bugs")

        # Transform to SDK format
        bugs = WorkItemTransformer.transform_work_items_response({"value": bugs_raw})
        return bugs

    except Exception as e:
        logger.error(f"All bug fetches failed: {e}")
        raise


async def query_bugs_for_quality(
    rest_client: AzureDevOpsRESTClient, project_name: str, lookback_days: int = 90, area_path_filter: str | None = None
) -> dict:
    """
    Query bugs for quality metrics (REST API).

    Args:
        rest_client: Azure DevOps REST API client
        project_name: ADO project name
        lookback_days: How many days back to look for bugs
        area_path_filter: Optional area path filter (format: "EXCLUDE:path" or "INCLUDE:path")

    Returns:
        Dictionary with categorized bugs

    Raises:
        Exception: If query execution fails
    """
    lookback_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    print(f"    Querying bugs for {project_name}...")

    # Validate inputs to prevent WIQL injection
    safe_project = WIQLValidator.validate_project_name(project_name)
    safe_lookback_date = WIQLValidator.validate_date_iso8601(lookback_date)

    # Build area path filter clause (validates area paths internally)
    area_filter_clause = _build_area_filter_clause(area_path_filter)

    # Query 1: All bugs (for overall quality assessment)
    wiql_all_bugs_query = f"""SELECT [System.Id], [System.Title], [System.State], [System.CreatedDate],
               [System.WorkItemType], [Microsoft.VSTS.Common.Priority],
               [Microsoft.VSTS.Common.Severity], [System.Tags],
               [Microsoft.VSTS.Common.ClosedDate], [Microsoft.VSTS.Common.ResolvedDate]
        FROM WorkItems
        WHERE [System.TeamProject] = '{safe_project}'
          AND [System.WorkItemType] = 'Bug'
          AND [System.CreatedDate] >= '{safe_lookback_date}'
          {area_filter_clause}
        ORDER BY [System.CreatedDate] DESC
        """  # nosec B608 - Inputs validated by WIQLValidator

    # Query 2: Currently open bugs (for aging analysis)
    wiql_open_bugs_query = f"""SELECT [System.Id], [System.Title], [System.State], [System.CreatedDate],
               [System.WorkItemType], [Microsoft.VSTS.Common.Priority],
               [Microsoft.VSTS.Common.Severity], [System.Tags]
        FROM WorkItems
        WHERE [System.TeamProject] = '{safe_project}'
          AND [System.WorkItemType] = 'Bug'
          AND [System.State] <> 'Closed'
          AND [System.State] <> 'Removed'
          AND ([Microsoft.VSTS.Common.Triage] <> 'Rejected' OR [Microsoft.VSTS.Common.Triage] = '')
          {area_filter_clause}
        ORDER BY [System.CreatedDate] ASC
        """  # nosec B608 - Inputs validated by WIQLValidator

    # Execute queries CONCURRENTLY (REST API)
    all_bugs_response, open_bugs_response = await asyncio.gather(
        rest_client.query_by_wiql(project=safe_project, wiql_query=wiql_all_bugs_query),
        rest_client.query_by_wiql(project=safe_project, wiql_query=wiql_open_bugs_query),
    )

    # Transform responses to SDK format
    all_bugs_wiql = WorkItemTransformer.transform_wiql_response(all_bugs_response)
    open_bugs_wiql = WorkItemTransformer.transform_wiql_response(open_bugs_response)

    all_bugs_result = all_bugs_wiql.work_items
    open_bugs_result = open_bugs_wiql.work_items

    print(f"      Found {len(all_bugs_result) if all_bugs_result else 0} total bugs (last {lookback_days} days)")
    print(f"      Found {len(open_bugs_result) if open_bugs_result else 0} open bugs")

    # Fetch full bug details with batching CONCURRENTLY
    all_bugs = []
    open_bugs = []

    # Create tasks for concurrent fetching
    all_bug_task = None
    open_bug_task = None

    if all_bugs_result:
        all_bug_ids = [item.id for item in all_bugs_result]
        all_bug_task = _fetch_bug_details(
            rest_client,
            all_bug_ids,
            fields=[
                "System.Id",
                "System.Title",
                "System.State",
                "System.CreatedDate",
                "System.WorkItemType",
                "Microsoft.VSTS.Common.Priority",
                "Microsoft.VSTS.Common.Severity",
                "System.Tags",
                "Microsoft.VSTS.Common.ClosedDate",
                "Microsoft.VSTS.Common.ResolvedDate",
                "System.CreatedBy",
            ],
        )

    if open_bugs_result:
        open_bug_ids = [item.id for item in open_bugs_result]
        open_bug_task = _fetch_bug_details(
            rest_client,
            open_bug_ids,
            fields=[
                "System.Id",
                "System.Title",
                "System.State",
                "System.CreatedDate",
                "System.WorkItemType",
                "Microsoft.VSTS.Common.Priority",
                "Microsoft.VSTS.Common.Severity",
                "System.Tags",
                "System.CreatedBy",
            ],
        )

    # Execute fetches concurrently
    tasks = []
    if all_bug_task:
        tasks.append(all_bug_task)
    if open_bug_task:
        tasks.append(open_bug_task)

    if tasks:
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            result_idx = 0

            if all_bug_task:
                all_bugs_result = results[result_idx]  # type: ignore[assignment]
                if isinstance(all_bugs_result, Exception):
                    logger.warning(f"Error fetching all bugs: {all_bugs_result}")
                    all_bugs = []
                else:
                    all_bugs = all_bugs_result  # type: ignore[assignment]
                result_idx += 1

            if open_bug_task:
                open_bugs_result = results[result_idx]  # type: ignore[assignment]
                if isinstance(open_bugs_result, Exception):
                    logger.warning(f"Error fetching open bugs: {open_bugs_result}")
                    open_bugs = []
                else:
                    open_bugs = open_bugs_result  # type: ignore[assignment]

        except Exception as e:
            logger.error(f"Error fetching bugs: {e}")

    return {"all_bugs": all_bugs, "open_bugs": open_bugs}


# REMOVED: calculate_reopen_rate
# Reason: Proxy calculation using current state, not actual revision history.
# Cannot reliably distinguish true reopens from state corrections or data issues.
# Would require querying work item revision history for accurate tracking.


# REMOVED: calculate_escaped_defects
# Reason: Pure speculation based on keyword matching. No field tracks who actually found the bug.
# Cannot reliably distinguish customer-found bugs from internally-found production bugs.


def calculate_bug_age_distribution(open_bugs: list[dict]) -> dict:
    """
    Calculate bug age distribution: How long bugs have been open.

    Args:
        open_bugs: List of open bug field dictionaries

    Returns:
        Age distribution metrics dictionary

    Raises:
        ValueError: If date parsing fails for all bugs
    """
    now = datetime.now(UTC)  # Make timezone-aware to match Azure DevOps dates
    ages = []
    parse_errors = 0

    for bug in open_bugs:
        created = bug.get("System.CreatedDate")

        age = calculate_age_days(created, reference_time=now)
        if age is not None:
            ages.append(age)
        elif created:
            # Log parsing errors
            parse_errors += 1
            if parse_errors <= 3:
                logger.warning(f"Could not parse date for bug {bug.get('System.Id')}: {created}")
            continue

    if parse_errors > 0:
        logger.warning(f"Failed to parse {parse_errors} out of {len(open_bugs)} open bug dates")

    if not ages:
        return {
            "median_age_days": None,
            "p85_age_days": None,
            "p95_age_days": None,
            "sample_size": 0,
            "ages_distribution": {"0-7_days": 0, "8-30_days": 0, "31-90_days": 0, "90+_days": 0},
        }

    return {
        "median_age_days": round(calculate_percentile(ages, 50), 1),
        "p85_age_days": round(calculate_percentile(ages, 85), 1),
        "p95_age_days": round(calculate_percentile(ages, 95), 1),
        "sample_size": len(ages),
        "ages_distribution": {
            "0-7_days": sum(1 for age in ages if age <= 7),
            "8-30_days": sum(1 for age in ages if 7 < age <= 30),
            "31-90_days": sum(1 for age in ages if 30 < age <= 90),
            "90+_days": sum(1 for age in ages if age > 90),
        },
    }


# REMOVED: calculate_quality_debt_index
# Reason: Invented formula with arbitrary severity weights (Critical=5, High=3, etc.).
# No industry standard or business validation for this calculation.
# Weights and formula are speculation, not based on actual business impact.


def _parse_repair_times(all_bugs: list[dict]) -> list[float]:
    """
    Parse repair times from bug data.

    Args:
        all_bugs: List of bug field dictionaries

    Returns:
        List of repair times in days
    """
    repair_times = []

    for bug in all_bugs:
        created_date = bug.get("System.CreatedDate")
        closed_date = bug.get("Microsoft.VSTS.Common.ClosedDate")

        # Only calculate for bugs that have been closed
        repair_time = calculate_lead_time_days(created_date, closed_date)
        if repair_time is not None:
            repair_times.append(repair_time)

    return repair_times


def calculate_mttr(all_bugs: list[dict]) -> dict:
    """
    Calculate MTTR (Mean Time To Repair): Average time from bug creation to closure.

    Args:
        all_bugs: List of all bug field dictionaries

    Returns:
        MTTR metrics dictionary in days
    """
    repair_times = _parse_repair_times(all_bugs)

    if not repair_times:
        return {
            "mttr_days": None,
            "median_mttr_days": None,
            "p85_mttr_days": None,
            "p95_mttr_days": None,
            "sample_size": 0,
            "mttr_distribution": {"0-1_days": 0, "1-7_days": 0, "7-30_days": 0, "30+_days": 0},
        }

    mean_mttr = sum(repair_times) / len(repair_times)

    return {
        "mttr_days": round(mean_mttr, 1),
        "median_mttr_days": round(calculate_percentile(repair_times, 50), 1),
        "p85_mttr_days": round(calculate_percentile(repair_times, 85), 1),
        "p95_mttr_days": round(calculate_percentile(repair_times, 95), 1),
        "sample_size": len(repair_times),
        "mttr_distribution": {
            "0-1_days": sum(1 for t in repair_times if t <= 1),
            "1-7_days": sum(1 for t in repair_times if 1 < t <= 7),
            "7-30_days": sum(1 for t in repair_times if 7 < t <= 30),
            "30+_days": sum(1 for t in repair_times if t > 30),
        },
    }


# REMOVED: calculate_fix_quality
# Reason: Same proxy issue as reopen rate - checks current state, not actual reopening events.
# Cannot reliably track if bugs stayed fixed without revision history.


async def calculate_test_execution_time(rest_client: AzureDevOpsRESTClient, project_name: str) -> dict:
    """
    Calculate test execution time from recent test runs (REST API).

    HARD DATA: Actual test run completed_date - started_date.

    Args:
        rest_client: Azure DevOps REST API client
        project_name: ADO project name

    Returns:
        Test execution time metrics dictionary
    """
    default_result = {"sample_size": 0, "median_minutes": None, "p85_minutes": None, "p95_minutes": None}

    try:
        # Get recent test runs via REST API
        response = await rest_client.get_test_runs(project=project_name, top=50)

        # Transform to SDK format
        test_runs = TestTransformer.transform_test_runs_response(response)

        execution_times = []

        for run in test_runs:
            started_date_str = run.get("started_date")
            completed_date_str = run.get("completed_date")

            if started_date_str and completed_date_str:
                try:
                    started_date = parse_ado_timestamp(started_date_str)
                    completed_date = parse_ado_timestamp(completed_date_str)

                    if started_date and completed_date:
                        duration = completed_date - started_date
                        duration_minutes = duration.total_seconds() / 60

                        if duration_minutes > 0:
                            execution_times.append(duration_minutes)
                except (AttributeError, TypeError, ValueError) as e:
                    logger.debug(f"Could not parse test run duration: {e}")
                    continue

        if not execution_times:
            return default_result

        return {
            "sample_size": len(execution_times),
            "median_minutes": round(calculate_percentile(execution_times, 50), 1),
            "p85_minutes": round(calculate_percentile(execution_times, 85), 1),
            "p95_minutes": round(calculate_percentile(execution_times, 95), 1),
        }

    except Exception as e:
        log_and_return_default(
            logger,
            e,
            context={"project_name": project_name, "operation": "get_test_runs"},
            default_value=default_result,
            error_type="Test execution time calculation",
        )
        return default_result


def _print_metrics_summary(age_distribution: dict, mttr: dict, test_execution: dict) -> None:
    """
    Print metrics summary to console.

    Args:
        age_distribution: Bug age distribution metrics
        mttr: MTTR metrics
        test_execution: Test execution time metrics
    """
    print(f"    Median Bug Age: {age_distribution['median_age_days']} days")
    print(f"    MTTR: {mttr['mttr_days']} days (median: {mttr['median_mttr_days']})")
    print(f"    Test Execution Time: {test_execution['median_minutes']} minutes (median)")


async def collect_quality_metrics_for_project(rest_client: AzureDevOpsRESTClient, project: dict, config: dict) -> dict:
    """
    Collect all quality metrics for a single project (REST API).

    Args:
        rest_client: Azure DevOps REST API client
        project: Project metadata from discovery
        config: Configuration dict (thresholds, lookback days, etc.)

    Returns:
        Quality metrics dictionary for the project
    """
    project_name = project["project_name"]
    project_key = project["project_key"]

    # Get the actual ADO project name (may differ from display name)
    ado_project_name = project.get("ado_project_name", project_name)

    # Get area path filter if specified
    area_path_filter = project.get("area_path_filter")

    print(f"\n  Collecting quality metrics for: {project_name}")

    # Query bugs and get test execution time CONCURRENTLY
    bugs_task = query_bugs_for_quality(
        rest_client, ado_project_name, lookback_days=config.get("lookback_days", 90), area_path_filter=area_path_filter
    )
    test_exec_task = calculate_test_execution_time(rest_client, ado_project_name)

    # Execute concurrently
    bugs, test_execution = await asyncio.gather(bugs_task, test_exec_task)

    # Filter out ArmorCode security bugs to avoid double-counting
    bugs["all_bugs"], excluded_all = filter_security_bugs(bugs["all_bugs"])
    bugs["open_bugs"], excluded_open = filter_security_bugs(bugs["open_bugs"])

    if excluded_open > 0 or excluded_all > 0:
        print(
            f"    Excluded {excluded_open} open security bugs and {excluded_all} total security bugs from quality metrics"
        )

    # Calculate metrics - ONLY HARD DATA (synchronous calculations)
    age_distribution = calculate_bug_age_distribution(bugs["open_bugs"])
    mttr = calculate_mttr(bugs["all_bugs"])

    _print_metrics_summary(age_distribution, mttr, test_execution)

    return {
        "project_key": project_key,
        "project_name": project_name,
        "bug_age_distribution": age_distribution,
        "mttr": mttr,
        "test_execution_time": test_execution,
        "total_bugs_analyzed": len(bugs["all_bugs"]),
        "open_bugs_count": len(bugs["open_bugs"]),
        "excluded_security_bugs": {"total": excluded_all, "open": excluded_open},
        "collected_at": datetime.now().isoformat(),
    }


def save_quality_metrics(metrics: dict, output_file: str = ".tmp/observatory/quality_history.json") -> bool:
    """
    Save quality metrics to history file.

    Appends to existing history or creates new file.
    Validates data before saving to prevent persisting collection failures.

    Args:
        metrics: Weekly metrics dictionary
        output_file: Path to history file

    Returns:
        True if saved successfully, False otherwise
    """
    from execution.utils_atomic_json import atomic_json_save, load_json_with_recovery

    # Validate that we have actual data before saving
    projects = metrics.get("projects", [])

    if not projects:
        logger.warning("No project data to save - collection may have failed")
        return False

    # Check if this looks like a failed collection (all zeros)
    total_bugs = sum(p.get("total_bugs_analyzed", 0) for p in projects)
    total_open = sum(p.get("open_bugs_count", 0) for p in projects)

    if total_bugs == 0 and total_open == 0:
        logger.warning("All projects returned zero bugs - likely a collection failure")
        logger.warning("Not persisting this data to avoid corrupting trend history")
        return False

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Load existing history
    history = load_json_with_recovery(output_file, default_value={"weeks": []})

    # Add validation if structure check exists
    if not isinstance(history, dict) or "weeks" not in history:
        logger.warning("Existing history file has invalid structure - recreating")
        history = {"weeks": []}

    # Add new week entry
    history["weeks"].append(metrics)

    # Keep only last 52 weeks (12 months) for quarter/annual analysis
    history["weeks"] = history["weeks"][-52:]

    # Save updated history
    try:
        atomic_json_save(history, output_file)
        logger.info(f"Quality metrics saved to: {output_file}")
        logger.info(f"History now contains {len(history['weeks'])} week(s)")
        return True
    except OSError as e:
        logger.error(f"Failed to save Quality metrics: {e}")
        return False


class QualityCollector:
    """Quality metrics collector using BaseCollector infrastructure"""

    def __init__(self):
        from execution.collectors.base import BaseCollector

        class _BaseHelper(BaseCollector):
            async def collect(self, project, rest_client):
                pass

            def save_metrics(self, results):
                pass

        self._base = _BaseHelper(name="quality", lookback_days=90)
        self.config = self._base.config

    async def run(self) -> bool:
        from execution.core.collector_metrics import track_collector_performance

        with track_collector_performance("quality") as tracker:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            print("Director Observatory - Quality Metrics Collector (REST API)")
            print("=" * 60)

            discovery_data = self._base.load_discovery_data()
            projects = discovery_data.get("projects", [])
            tracker.project_count = len(projects)

            if not projects:
                return False

            rest_client = self._base.get_rest_client()

            print("\nCollecting quality metrics (concurrent execution)...")
            print("=" * 60)

            tasks = [collect_quality_metrics_for_project(rest_client, project, self.config) for project in projects]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            project_metrics: list[dict] = []
            for project, result in zip(projects, results, strict=True):
                if isinstance(result, Exception):
                    logger.error(f"Error collecting metrics for {project['project_name']}: {result}")
                else:
                    project_metrics.append(result)  # type: ignore[arg-type]

            week_metrics = {
                "week_date": datetime.now().strftime("%Y-%m-%d"),
                "week_number": datetime.now().isocalendar()[1],
                "projects": project_metrics,
                "config": self.config,
            }

            success = save_quality_metrics(week_metrics)
            tracker.success = success
            self._log_summary(project_metrics)
            return success

    def _log_summary(self, project_metrics: list[dict]) -> None:
        print("\n" + "=" * 60)
        print("Quality Metrics Collection Summary:")
        print(f"  Projects processed: {len(project_metrics)}")
        total_bugs = sum(p["total_bugs_analyzed"] for p in project_metrics)
        total_open = sum(p["open_bugs_count"] for p in project_metrics)
        total_excluded = sum(p["excluded_security_bugs"]["total"] for p in project_metrics)
        total_excluded_open = sum(p["excluded_security_bugs"]["open"] for p in project_metrics)
        print(f"  Total bugs analyzed: {total_bugs}")
        print(f"  Total open bugs: {total_open}")
        if total_excluded > 0:
            print(f"  Security bugs excluded: {total_excluded} total ({total_excluded_open} open)")
            print("    → Prevents double-counting with Security Dashboard")
        mttr_values = [p["mttr"]["mttr_days"] for p in project_metrics if p["mttr"]["mttr_days"] is not None]
        if mttr_values:
            avg_mttr = sum(mttr_values) / len(mttr_values)
            print(f"  Avg MTTR: {round(avg_mttr, 1)} days")
        print("\nQuality metrics collection complete (REST API + concurrent execution)!")
        print("  ✓ Only hard data - no speculation")
        print("  ✓ MTTR: Actual CreatedDate → ClosedDate")
        print("  ✓ Bug Age: Actual time open")
        print("  ✓ Security bugs filtered out (no double-counting)")
        print("  ✓ Rejected bugs excluded (Triage = 'Rejected')")
        print("  ✓ Concurrent collection for maximum speed")
        print("\nNext step: Generate quality dashboard")


async def main() -> None:
    collector = QualityCollector()
    await collector.run()


if __name__ == "__main__":
    asyncio.run(main())
