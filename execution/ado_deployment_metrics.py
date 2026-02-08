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
"""

import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta

# Azure DevOps SDK
from azure.devops.connection import Connection

# Load environment variables
from dotenv import load_dotenv
from msrest.authentication import BasicAuthentication

from execution.secure_config import get_config

load_dotenv()


def get_ado_connection():
    """Get ADO connection using credentials from .env"""
    ado_config = get_config().get_ado_config()
    organization_url = ado_config.organization_url
    pat = ado_config.pat

    if not organization_url or not pat:
        raise ValueError("ADO_ORGANIZATION_URL and ADO_PAT must be set in .env file")

    credentials = BasicAuthentication("", pat)
    connection = Connection(base_url=organization_url, creds=credentials)
    return connection


def query_builds(build_client, project_name: str, days: int = 90) -> list[dict]:
    """
    Query recent builds from Azure Pipelines.

    Args:
        build_client: Build client
        project_name: ADO project name
        days: Lookback period in days

    Returns:
        List of build data with timestamps and status
    """
    lookback_date = datetime.now() - timedelta(days=days)

    try:
        builds = build_client.get_builds(project=project_name, min_time=lookback_date)

        build_data = []
        for build in builds:
            # Calculate duration if both timestamps exist
            duration_minutes = None
            if build.start_time and build.finish_time:
                delta = build.finish_time - build.start_time
                duration_minutes = delta.total_seconds() / 60

            build_data.append(
                {
                    "build_id": build.id,
                    "build_number": build.build_number,
                    "definition_id": build.definition.id if build.definition else None,
                    "definition_name": build.definition.name if build.definition else "Unknown",
                    "status": build.status,
                    "result": build.result,
                    "start_time": build.start_time.isoformat() if build.start_time else None,
                    "finish_time": build.finish_time.isoformat() if build.finish_time else None,
                    "duration_minutes": round(duration_minutes, 2) if duration_minutes else None,
                    "source_branch": build.source_branch if hasattr(build, "source_branch") else None,
                    "source_version": build.source_version if hasattr(build, "source_version") else None,
                    "requested_for": build.requested_for.display_name if build.requested_for else "Unknown",
                }
            )

        return build_data

    except Exception as e:
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
    by_pipeline = defaultdict(int)
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
    by_result = defaultdict(int)
    by_pipeline = defaultdict(lambda: defaultdict(int))

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

    # Calculate percentiles
    sorted_durations = sorted(durations)
    n = len(sorted_durations)

    def percentile(data, p):
        index = int(n * p / 100)
        return data[min(index, n - 1)]

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
        "sample_size": n,
        "median_minutes": round(statistics.median(durations), 1),
        "p85_minutes": round(percentile(sorted_durations, 85), 1),
        "p95_minutes": round(percentile(sorted_durations, 95), 1),
        "min_minutes": round(min(durations), 1),
        "max_minutes": round(max(durations), 1),
        "by_pipeline": pipeline_stats,
    }


def calculate_lead_time_for_changes(build_client, git_client, project_name: str, builds: list[dict]) -> dict:
    """
    Calculate lead time for changes - commit timestamp to build completion.

    HARD DATA: Commit timestamp → Build finish_time.
    Only counts builds where we can link to commits.

    Args:
        build_client: Build client
        git_client: Git client
        project_name: ADO project name
        builds: List of build data

    Returns:
        Lead time metrics
    """
    lead_times = []

    # Sample recent successful builds (limit to 50 for performance)
    successful_builds = [b for b in builds if b["result"] == "succeeded"][:50]

    for build in successful_builds:
        try:
            if not build["finish_time"] or not build["source_version"]:
                continue

            # Get build changes (commits)
            changes = build_client.get_build_changes(project=project_name, build_id=build["build_id"])

            if not changes:
                continue

            # Get the latest commit timestamp
            # Changes are typically ordered with latest first
            latest_change = changes[0]
            if not hasattr(latest_change, "timestamp") or not latest_change.timestamp:
                continue

            # Calculate lead time
            commit_time = latest_change.timestamp
            build_finish_time = datetime.fromisoformat(build["finish_time"].replace("Z", "+00:00"))

            # Make timezone-aware if needed
            if commit_time.tzinfo is None and build_finish_time.tzinfo is not None:
                commit_time = commit_time.replace(tzinfo=build_finish_time.tzinfo)

            lead_time_delta = build_finish_time - commit_time
            lead_time_hours = lead_time_delta.total_seconds() / 3600

            # Only count positive lead times (build after commit)
            if lead_time_hours > 0:
                lead_times.append(lead_time_hours)

        except Exception:
            # Skip builds where we can't calculate lead time
            continue

    if not lead_times:
        return {"sample_size": 0, "median_hours": None, "p85_hours": None, "p95_hours": None}

    # Calculate percentiles
    sorted_lead_times = sorted(lead_times)
    n = len(sorted_lead_times)

    def percentile(data, p):
        index = int(n * p / 100)
        return data[min(index, n - 1)]

    return {
        "sample_size": n,
        "median_hours": round(statistics.median(lead_times), 1),
        "p85_hours": round(percentile(sorted_lead_times, 85), 1),
        "p95_hours": round(percentile(sorted_lead_times, 95), 1),
    }


def collect_deployment_metrics_for_project(connection, project: dict, config: dict) -> dict:
    """
    Collect all deployment metrics for a single project.

    Args:
        connection: ADO connection
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

    build_client = connection.clients.get_build_client()
    git_client = connection.clients.get_git_client()

    # Query builds
    try:
        builds = query_builds(build_client, ado_project_name, days=config.get("lookback_days", 90))
        print(f"    Found {len(builds)} builds in last {config.get('lookback_days', 90)} days")
    except Exception as e:
        print(f"    [ERROR] Failed to query builds: {e}")
        builds = []

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
    lead_time = calculate_lead_time_for_changes(build_client, git_client, ado_project_name, builds)

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


def save_deployment_metrics(metrics: dict, output_file: str = ".tmp/observatory/deployment_history.json"):
    """
    Save deployment metrics to history file.

    Appends to existing history or creates new file.
    Validates data before saving to prevent persisting collection failures.
    """
    from utils_atomic_json import atomic_json_save, load_json_with_recovery

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
    except Exception as e:
        print(f"\n[ERROR] Failed to save Deployment metrics: {e}")
        return False


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    print("Director Observatory - Deployment Metrics Collector\n")
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

    # Connect to ADO
    print("\nConnecting to Azure DevOps...")
    try:
        connection = get_ado_connection()
        print("[SUCCESS] Connected to ADO")
    except Exception as e:
        print(f"[ERROR] Failed to connect to ADO: {e}")
        exit(1)

    # Collect metrics for all projects
    print("\nCollecting deployment metrics...")
    print("=" * 60)

    project_metrics = []
    for project in projects:
        try:
            metrics = collect_deployment_metrics_for_project(connection, project, config)
            project_metrics.append(metrics)
        except Exception as e:
            print(f"  [ERROR] Failed to collect metrics for {project['project_name']}: {e}")
            continue

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

    print("\nDeployment metrics collection complete!")
    print("  ✓ Only hard data - no assumptions")
    print("  ✓ Deployment Frequency: Actual build counts")
    print("  ✓ Build Success Rate: ADO-provided status")
    print("  ✓ Build Duration: Actual finish_time - start_time")
    print("  ✓ Lead Time: Actual commit → build timestamps")
    print("\nNext step: Generate deployment dashboard")
