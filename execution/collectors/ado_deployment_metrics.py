#!/usr/bin/env python3
"""
ADO Deployment Metrics Collector for Director Observatory

Collects DORA and deployment metrics at project level:
- Deployment Frequency: Count of successful builds (by pipeline)
- Build Success Rate: Succeeded vs failed builds
- Build Duration: Actual build time in minutes
- Lead Time for Changes: Commit timestamp to build completion

HARD DATA ONLY - No assumptions, no thresholds, no classifications.
Read-only operation - does not modify any existing data.

Migrated to Azure DevOps REST API v7.1 (replaces SDK).
"""

import asyncio
import json
import logging
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from typing import cast

# Load environment variables
from dotenv import load_dotenv

from execution.collectors.ado_rest_client import AzureDevOpsRESTClient, get_ado_rest_client
from execution.collectors.ado_rest_transformers import BuildTransformer, GitTransformer
from execution.core.collector_metrics import track_collector_performance
from execution.secure_config import get_config
from execution.utils.datetime_utils import parse_ado_timestamp
from execution.utils.error_handling import log_and_continue, log_and_raise, log_and_return_default
from execution.utils.statistics import calculate_percentile

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


async def query_builds(rest_client: AzureDevOpsRESTClient, project_name: str, days: int = 90) -> list[dict]:
    """
    Query recent builds from Azure Pipelines (REST API).

    Args:
        rest_client: Azure DevOps REST API client
        project_name: ADO project name
        days: Lookback period in days

    Returns:
        List of build data with timestamps and status
    """
    lookback_date = datetime.now() - timedelta(days=days)
    min_time_iso = lookback_date.isoformat() + "Z"

    try:
        # REST API call
        response = await rest_client.get_builds(project=project_name, min_time=min_time_iso)

        # Transform to SDK-compatible format
        builds = BuildTransformer.transform_builds_response(response)

        build_data = []
        for build in builds:
            # Calculate duration if both timestamps exist
            duration_minutes = None
            start_time = build.get("start_time")
            finish_time = build.get("finish_time")

            if start_time and finish_time:
                start_dt = parse_ado_timestamp(start_time)
                finish_dt = parse_ado_timestamp(finish_time)
                if start_dt and finish_dt:
                    delta = finish_dt - start_dt
                    duration_minutes = delta.total_seconds() / 60

            build_data.append(
                {
                    "build_id": build.get("id"),
                    "build_number": build.get("build_number"),
                    "definition_id": build.get("definition", {}).get("id"),
                    "definition_name": build.get("definition", {}).get("name", "Unknown"),
                    "status": build.get("status"),
                    "result": build.get("result"),
                    "start_time": start_time,
                    "finish_time": finish_time,
                    "duration_minutes": round(duration_minutes, 2) if duration_minutes else None,
                    "source_branch": build.get("source_branch"),
                    "source_version": build.get("source_version"),
                    "requested_for": build.get("requested_for", "Unknown"),
                }
            )

        return build_data

    except Exception as e:
        logger.warning(f"Error querying builds for {project_name}: {e}")
        print(f"      [WARNING] Could not query builds: {e}")
        return []


def calculate_deployment_frequency(builds: list[dict], lookback_days: int = 90) -> dict:
    """
    Calculate deployment frequency - count of successful builds.

    HARD DATA: Just counts, no thresholds, no classifications.

    Args:
        builds: List of build data
        lookback_days: Period to analyze

    Returns:
        Deployment frequency metrics
    """
    # Filter to completed successful builds
    successful_builds = [b for b in builds if b["result"] == "succeeded"]

    # Count by pipeline
    by_pipeline: defaultdict[str, int] = defaultdict(int)
    for build in successful_builds:
        pipeline = build["definition_name"]
        by_pipeline[pipeline] += 1

    # Calculate rate
    total_successful = len(successful_builds)
    weeks = lookback_days / 7
    deployments_per_week = total_successful / weeks if weeks > 0 else 0

    return {
        "total_successful_builds": total_successful,
        "lookback_days": lookback_days,
        "deployments_per_week": round(deployments_per_week, 2),
        "by_pipeline": dict(by_pipeline),
        "pipeline_count": len(by_pipeline),
    }


def calculate_build_success_rate(builds: list[dict]) -> dict:
    """
    Calculate build success rate - succeeded vs failed/canceled.

    HARD DATA: Azure DevOps provides build.result status.
    No assumptions about what "success" means - ADO defines it.

    Args:
        builds: List of build data

    Returns:
        Build success rate metrics
    """
    # Count by result
    by_result: defaultdict[str, int] = defaultdict(int)
    by_pipeline: defaultdict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))

    for build in builds:
        result = build["result"]
        pipeline = build["definition_name"]

        by_result[result] += 1
        by_pipeline[pipeline][result] += 1

    total = len(builds)
    succeeded = by_result.get("succeeded", 0)
    failed = by_result.get("failed", 0)
    canceled = by_result.get("canceled", 0)
    partial = by_result.get("partiallySucceeded", 0)

    success_rate = (succeeded / total * 100) if total > 0 else 0

    return {
        "total_builds": total,
        "succeeded": succeeded,
        "failed": failed,
        "canceled": canceled,
        "partially_succeeded": partial,
        "success_rate_pct": round(success_rate, 1),
        "by_result": dict(by_result),
        "by_pipeline": {pipeline: dict(results) for pipeline, results in by_pipeline.items()},
    }


def calculate_build_duration(builds: list[dict]) -> dict:
    """
    Calculate build duration statistics.

    HARD DATA: finish_time - start_time from Azure DevOps.

    Args:
        builds: List of build data

    Returns:
        Build duration metrics
    """
    # Get builds with duration data
    builds_with_duration = [b for b in builds if b["duration_minutes"] is not None]

    if not builds_with_duration:
        return {
            "sample_size": 0,
            "median_minutes": None,
            "p85_minutes": None,
            "p95_minutes": None,
            "min_minutes": None,
            "max_minutes": None,
        }

    durations = [b["duration_minutes"] for b in builds_with_duration]

    # By pipeline
    by_pipeline = defaultdict(list)
    for build in builds_with_duration:
        by_pipeline[build["definition_name"]].append(build["duration_minutes"])

    pipeline_stats = {}
    for pipeline, pipeline_durations in by_pipeline.items():
        if pipeline_durations:
            pipeline_stats[pipeline] = {
                "count": len(pipeline_durations),
                "median_minutes": round(statistics.median(pipeline_durations), 1),
            }

    return {
        "sample_size": len(durations),
        "median_minutes": round(statistics.median(durations), 1),
        "p85_minutes": round(calculate_percentile(durations, 85), 1),
        "p95_minutes": round(calculate_percentile(durations, 95), 1),
        "min_minutes": round(min(durations), 1),
        "max_minutes": round(max(durations), 1),
        "by_pipeline": pipeline_stats,
    }


async def _get_commit_timestamp_from_build(
    rest_client: AzureDevOpsRESTClient, project_name: str, build: dict
) -> datetime | None:
    """
    Extract the latest commit timestamp from a build's changes (REST API).

    Args:
        rest_client: Azure DevOps REST API client
        project_name: ADO project name
        build: Build data dictionary

    Returns:
        Commit timestamp if found, None otherwise
    """
    try:
        if not build["finish_time"] or not build["source_version"]:
            return None

        # Get build changes (commits) via REST API
        response = await rest_client.get_build_changes(project=project_name, build_id=build["build_id"])

        # Transform response
        changes = BuildTransformer.transform_build_changes_response(response)

        if not changes:
            return None

        # Get the latest commit timestamp (changes are typically ordered with latest first)
        latest_change = changes[0]
        timestamp_str = latest_change.get("timestamp")

        if not timestamp_str:
            return None

        # Parse timestamp
        return parse_ado_timestamp(timestamp_str)

    except Exception as e:
        logger.debug(f"Error getting changes for build {build.get('build_id', 'unknown')}: {e}")
        return None


def _calculate_single_build_lead_time(commit_time: datetime, build: dict) -> float | None:
    """
    Calculate lead time in hours for a single build.

    Args:
        commit_time: Commit timestamp
        build: Build data dictionary with finish_time

    Returns:
        Lead time in hours if positive, None otherwise
    """
    try:
        build_finish_time = parse_ado_timestamp(build.get("finish_time"))
        if build_finish_time is None:
            return None

        # Make timezone-aware if needed
        if commit_time.tzinfo is None and build_finish_time.tzinfo is not None:
            commit_time = commit_time.replace(tzinfo=build_finish_time.tzinfo)

        lead_time_delta = build_finish_time - commit_time
        lead_time_hours = lead_time_delta.total_seconds() / 3600

        # Only count positive lead times (build after commit)
        if lead_time_hours > 0:
            return lead_time_hours

        return None

    except (ValueError, KeyError, AttributeError) as e:
        logger.debug(f"Error calculating lead time for build {build.get('build_id', 'unknown')}: {e}")
        return None


async def calculate_lead_time_for_changes(
    rest_client: AzureDevOpsRESTClient, project_name: str, builds: list[dict]
) -> dict:
    """
    Calculate lead time for changes - commit timestamp to build completion (REST API).

    HARD DATA: Commit timestamp → Build finish_time.
    Only counts builds where we can link to commits.
    Uses concurrent API calls for maximum performance.

    Args:
        rest_client: Azure DevOps REST API client
        project_name: ADO project name
        builds: List of build data

    Returns:
        Lead time metrics
    """
    lead_times = []

    # Sample recent successful builds (limit to 50 for performance)
    successful_builds = [b for b in builds if b["result"] == "succeeded"][:50]

    # Get commit timestamps concurrently for all builds
    commit_time_tasks = [
        _get_commit_timestamp_from_build(rest_client, project_name, build) for build in successful_builds
    ]
    commit_times = await asyncio.gather(*commit_time_tasks)

    # Calculate lead times
    for build, commit_time in zip(successful_builds, commit_times, strict=True):
        if not commit_time:
            continue

        lead_time_hours = _calculate_single_build_lead_time(commit_time, build)
        if lead_time_hours is not None:
            lead_times.append(lead_time_hours)

    if not lead_times:
        return {"sample_size": 0, "median_hours": None, "p85_hours": None, "p95_hours": None}

    return {
        "sample_size": len(lead_times),
        "median_hours": round(statistics.median(lead_times), 1),
        "p85_hours": round(calculate_percentile(lead_times, 85), 1),
        "p95_hours": round(calculate_percentile(lead_times, 95), 1),
    }


async def collect_deployment_metrics_for_project(
    rest_client: AzureDevOpsRESTClient, project: dict, config: dict
) -> dict:
    """
    Collect all deployment metrics for a single project (REST API).

    Args:
        rest_client: Azure DevOps REST API client
        project: Project metadata from discovery
        config: Configuration dict

    Returns:
        Deployment metrics dictionary for the project
    """
    project_name = project["project_name"]
    project_key = project["project_key"]

    # Get the actual ADO project name
    ado_project_name = project.get("ado_project_name", project_name)

    print(f"\n  Collecting deployment metrics for: {project_name}")

    # Query builds via REST API
    try:
        builds = await query_builds(rest_client, ado_project_name, days=config.get("lookback_days", 90))
        print(f"    Found {len(builds)} builds in last {config.get('lookback_days', 90)} days")
    except Exception as e:
        logger.error(f"Error querying builds for {project_name}: {e}")
        print(f"    [ERROR] Failed to query builds: {e}")
        builds = []
        builds = log_and_return_default(
            logger,
            e,
            context={"project_name": project_name, "ado_project_name": ado_project_name},
            default_value=[],
            error_type="Build query data handling",
        )
        print(f"    [ERROR] Failed to query builds: {e}")

    if not builds:
        print("    [WARNING] No builds found - skipping deployment metrics")
        return {
            "project_key": project_key,
            "project_name": project_name,
            "deployment_frequency": {"total_successful_builds": 0},
            "build_success_rate": {"total_builds": 0},
            "build_duration": {"sample_size": 0},
            "lead_time_for_changes": {"sample_size": 0},
            "collected_at": datetime.now().isoformat(),
        }

    # Calculate metrics - ALL HARD DATA
    deployment_frequency = calculate_deployment_frequency(builds, config.get("lookback_days", 90))
    build_success_rate = calculate_build_success_rate(builds)
    build_duration = calculate_build_duration(builds)
    lead_time = await calculate_lead_time_for_changes(rest_client, ado_project_name, builds)

    print(f"    Deployment Frequency: {deployment_frequency['deployments_per_week']:.1f} per week")
    print(f"    Build Success Rate: {build_success_rate['success_rate_pct']:.1f}%")
    print(f"    Median Build Duration: {build_duration['median_minutes']} min")
    print(f"    Median Lead Time: {lead_time['median_hours']} hours")

    return {
        "project_key": project_key,
        "project_name": project_name,
        "deployment_frequency": deployment_frequency,
        "build_success_rate": build_success_rate,
        "build_duration": build_duration,
        "lead_time_for_changes": lead_time,
        "collected_at": datetime.now().isoformat(),
    }


def save_deployment_metrics(metrics: dict, output_file: str = ".tmp/observatory/deployment_history.json") -> bool:
    """
    Save deployment metrics to history file.

    Appends to existing history or creates new file.
    Validates data before saving to prevent persisting collection failures.
    """
    from execution.utils_atomic_json import atomic_json_save, load_json_with_recovery

    # Validate that we have actual data before saving
    projects = metrics.get("projects", [])

    if not projects:
        print("\n[SKIPPED] No project data to save - collection may have failed")
        return False

    # Check if this looks like a failed collection (all zeros)
    total_builds = sum(p.get("build_success_rate", {}).get("total_builds", 0) for p in projects)
    total_successful = sum(p.get("deployment_frequency", {}).get("total_successful_builds", 0) for p in projects)

    if total_builds == 0 and total_successful == 0:
        print("\n[SKIPPED] All projects returned zero deployment data - likely a collection failure")
        print("          Not persisting this data to avoid corrupting trend history")
        return False

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Load existing history
    history = load_json_with_recovery(output_file, default_value={"weeks": []})

    # Add validation if structure check exists
    if not isinstance(history, dict) or "weeks" not in history:
        print("\n[WARNING] Existing history file has invalid structure - recreating")
        history = {"weeks": []}

    # Add new week entry
    history["weeks"].append(metrics)

    # Keep only last 52 weeks (12 months) for quarter/annual analysis
    history["weeks"] = history["weeks"][-52:]

    # Save updated history
    try:
        atomic_json_save(history, output_file)
        print(f"\n[SAVED] Deployment metrics saved to: {output_file}")
        print(f"        History now contains {len(history['weeks'])} week(s)")
        return True
    except OSError as e:
        logger.error(f"File I/O error saving deployment metrics to {output_file}: {e}")
        print(f"\n[ERROR] Failed to save Deployment metrics: {e}")
        return False
    except (TypeError, ValueError) as e:
        log_and_return_default(
            logger,
            e,
            context={"output_file": output_file, "weeks_count": len(history.get("weeks", []))},
            default_value=False,
            error_type="JSON serialization",
        )
        print(f"\n[ERROR] Failed to save Deployment metrics: {e}")
        return False


async def main() -> None:
    """Main async function for deployment metrics collection"""
    with track_collector_performance("deployment") as tracker:
        # Set UTF-8 encoding for Windows console
        if sys.platform == "win32":
            import codecs

            sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
            sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(".tmp/observatory/deployment_metrics.log"), logging.StreamHandler()],
        )

    print("Director Observatory - Deployment Metrics Collector (REST API)\n")
    print("=" * 60)

    # Configuration
    config = {"lookback_days": 90}

    # Load discovered projects
    try:
        with open(".tmp/observatory/ado_structure.json", encoding="utf-8") as f:
            discovery_data = json.load(f)
        projects = discovery_data["projects"]
        print(f"Loaded {len(projects)} projects from discovery")
    except FileNotFoundError:
        print("[ERROR] Project discovery file not found.")
        print("Run: python execution/discover_projects.py")
        exit(1)

    # Connect to ADO REST API
    print("\nConnecting to Azure DevOps REST API...")
    try:
        rest_client = get_ado_rest_client()
        print("[SUCCESS] Connected to ADO REST API")
    except Exception as e:
        logger.error(f"Error connecting to ADO: {e}")
        print(f"[ERROR] Failed to connect to ADO: {e}")
        exit(1)

    # Collect metrics for all projects CONCURRENTLY
    print("\nCollecting deployment metrics (concurrent execution)...")
    print("=" * 60)

    # Create tasks for all projects (concurrent collection)
    tasks = [collect_deployment_metrics_for_project(rest_client, project, config) for project in projects]

    # Execute all collections concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter successful results
    project_metrics: list[dict] = []
    for project, result in zip(projects, results, strict=True):
        if isinstance(result, Exception):
            logger.error(f"Error collecting metrics for {project['project_name']}: {result}")
            print(f"  [ERROR] Failed to collect metrics for {project['project_name']}: {result}")
        else:
            project_metrics.append(result)  # type: ignore[arg-type]

    # Save results
    week_metrics = {
        "week_date": datetime.now().strftime("%Y-%m-%d"),
        "week_number": datetime.now().isocalendar()[1],
        "projects": project_metrics,
        "config": config,
    }

    save_deployment_metrics(week_metrics)

    # Summary
    print("\n" + "=" * 60)
    print("Deployment Metrics Collection Summary:")
    print(f"  Projects processed: {len(project_metrics)}")

    total_builds = sum(p["build_success_rate"]["total_builds"] for p in project_metrics)
    total_successful = sum(p["deployment_frequency"]["total_successful_builds"] for p in project_metrics)

    print(f"  Total builds analyzed: {total_builds}")
    print(f"  Total successful builds: {total_successful}")

    print("\nDeployment metrics collection complete (REST API + concurrent execution)!")
    print("  ✓ Only hard data - no assumptions")
    print("  ✓ Deployment Frequency: Actual build counts")
    print("  ✓ Build Success Rate: ADO-provided status")
    print("  ✓ Build Duration: Actual finish_time - start_time")
    print("  ✓ Lead Time: Actual commit → build timestamps (concurrent API calls)")
    print("  ✓ Concurrent collection for maximum speed")
    print("\nNext step: Generate deployment dashboard")


if __name__ == "__main__":
    asyncio.run(main())
