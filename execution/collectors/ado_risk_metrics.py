#!/usr/bin/env python3
"""
ADO Delivery Risk Metrics Collector for Director Observatory

Collects delivery risk and change stability metrics at project level:
- PR Size Distribution: Small vs large changes
- Code Churn: Files changed frequently (hot paths)
- Change Risk: Large changes to core files
- Reopened Bugs: Bugs reopened after recent changes

Read-only operation - does not modify any existing data.

Migrated to Azure DevOps REST API v7.1 (replaces SDK).
"""

import asyncio
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

# Load environment variables
from dotenv import load_dotenv

from execution.collectors.ado_rest_client import AzureDevOpsRESTClient, get_ado_rest_client
from execution.collectors.ado_rest_transformers import GitTransformer
from execution.core.collector_metrics import track_collector_performance
from execution.core.logging_config import get_logger
from execution.domain.constants import flow_metrics, sampling_config
from execution.secure_config import get_config
from execution.utils.error_handling import log_and_continue, log_and_return_default

load_dotenv()

# Configure logging
logger = get_logger(__name__)


def _extract_file_paths_from_changes(changes: dict) -> list[str]:
    """
    Extract file paths from Git changes REST response.

    Args:
        changes: Git changes response dict from REST API

    Returns:
        List of file paths that were changed
    """
    if not changes or "changes" not in changes:
        return []

    file_paths = []
    for change in changes.get("changes", []):
        # REST API format: change["item"]["path"]
        if "item" in change and change["item"] and "path" in change["item"]:
            file_paths.append(change["item"]["path"])

    return file_paths


def _build_commit_data(commit: dict, changes: int = 0, files: list[str] | None = None) -> dict:
    """
    Build commit data dictionary from commit dict (REST format).

    Args:
        commit: Git commit dict from REST API (transformed by GitTransformer)
        changes: Number of file changes (default 0)
        files: List of changed file paths (default empty list)

    Returns:
        Commit data dictionary with standardized structure
    """
    if files is None:
        files = []

    return {
        "commit_id": commit.get("commit_id"),
        "author": commit.get("author_name", "Unknown"),
        "date": commit.get("author_date"),
        "message": commit.get("comment"),
        "changes": changes,
        "files": files,
    }


async def _fetch_commit_changes(
    rest_client: AzureDevOpsRESTClient, commit_id: str, repo_id: str, project_name: str
) -> tuple[int, list[str]]:
    """
    Fetch file changes for a single commit with error handling.

    Args:
        rest_client: Azure DevOps REST API client
        commit_id: Commit ID
        repo_id: Repository ID
        project_name: Project name

    Returns:
        Tuple of (change_count, file_paths)
        Returns (0, []) on any error
    """
    try:
        # Get changes via REST API
        changes = await rest_client.get_changes(project=project_name, repository_id=repo_id, commit_id=commit_id)

        change_count = len(changes.get("changes", [])) if changes else 0
        file_paths = _extract_file_paths_from_changes(changes)

        return change_count, file_paths

    except Exception as e:
        logger.warning(
            "API error getting changes for commit",
            extra={
                "commit_id": commit_id[:8] if len(commit_id) >= 8 else commit_id,
                "repo_id": repo_id,
                "error": str(e),
            },
        )
        return 0, []


async def query_recent_commits(
    rest_client: AzureDevOpsRESTClient, project_name: str, repo_id: str, days: int = flow_metrics.LOOKBACK_DAYS
) -> list[dict]:
    """
    Query recent commits to analyze code churn.

    Args:
        rest_client: Azure DevOps REST API client
        project_name: ADO project name
        repo_id: Repository ID
        days: Lookback period in days

    Returns:
        List of commits with file changes
    """
    since_date = datetime.now() - timedelta(days=days)

    try:
        # Query commits via REST API
        response = await rest_client.get_commits(
            project=project_name, repository_id=repo_id, from_date=since_date.isoformat() + "Z"
        )

        # Transform to simplified format
        commits = GitTransformer.transform_commits_response(response)

        # Limit to 100 most recent commits for performance
        commits = commits[:100]

        # Fetch file changes concurrently for sample commits (PARALLEL EXECUTION)
        sample_limit = min(sampling_config.COMMIT_DETAIL_LIMIT, len(commits))

        # Create tasks for commits that need file details
        change_tasks = [
            _fetch_commit_changes(rest_client, commits[idx]["commit_id"], repo_id, project_name)
            for idx in range(sample_limit)
        ]

        # Execute change fetches concurrently
        change_results = await asyncio.gather(*change_tasks, return_exceptions=True)

        commit_data = []

        # Process commits with file details from concurrent results
        for idx in range(len(commits)):
            commit = commits[idx]
            if idx < sample_limit:
                # Use result from concurrent fetch
                result = change_results[idx]
                if isinstance(result, Exception):
                    changes, files = 0, []
                else:
                    changes, files = result  # type: ignore[misc]
                commit_data.append(_build_commit_data(commit, changes, files))
            else:
                # For commits beyond limit, only store basic info (no file details)
                commit_data.append(_build_commit_data(commit))

        return commit_data

    except Exception as e:
        logger.warning(
            "API error querying commits",
            extra={"project": project_name, "repo_id": repo_id, "days": days, "error": str(e)},
        )
        return []


async def query_pull_requests(
    rest_client: AzureDevOpsRESTClient, project_name: str, repo_id: str, days: int = flow_metrics.LOOKBACK_DAYS
) -> list[dict]:
    """
    Query recent pull requests to analyze PR size.

    Args:
        rest_client: Azure DevOps REST API client
        project_name: ADO project name
        repo_id: Repository ID
        days: Lookback period in days

    Returns:
        List of PR data
    """
    try:
        # Query completed PRs via REST API
        response = await rest_client.get_pull_requests(project=project_name, repository_id=repo_id, status="completed")

        # Transform to simplified format
        prs = GitTransformer.transform_pull_requests_response(response)

        # Filter by date
        cutoff_date = datetime.now(datetime.now().astimezone().tzinfo) - timedelta(days=days)

        filtered_prs = []
        for pr in prs:
            created_date_str = pr.get("creation_date")
            if created_date_str:
                try:
                    created_date = datetime.fromisoformat(created_date_str.replace("Z", "+00:00"))
                    if created_date < cutoff_date:
                        continue
                except ValueError:
                    continue

            filtered_prs.append(pr)

        # Get commit counts concurrently for all PRs (PARALLEL EXECUTION)
        async def get_pr_commit_count(pr: dict) -> tuple[dict, int]:
            try:
                response = await rest_client.get_pull_request_commits(
                    project=project_name, repository_id=repo_id, pull_request_id=pr["pull_request_id"]
                )
                commit_count = len(response.get("value", []))
                return pr, commit_count
            except Exception as e:
                logger.debug(
                    "Could not get PR commits (PR may be old/deleted)",
                    extra={"pr_id": pr.get("pull_request_id"), "repo_id": repo_id, "error": str(e)},
                )
                return pr, 0

        commit_count_tasks = [get_pr_commit_count(pr) for pr in filtered_prs]
        commit_count_results = await asyncio.gather(*commit_count_tasks, return_exceptions=True)

        # Build PR data with commit counts
        pr_data = []
        for result in commit_count_results:
            if isinstance(result, Exception):
                continue

            pr, commit_count = result  # type: ignore[misc]
            pr_data.append(
                {
                    "pr_id": pr.get("pull_request_id"),
                    "title": pr.get("title"),
                    "created_date": pr.get("creation_date"),
                    "closed_date": pr.get("closed_date"),
                    "commit_count": commit_count,
                    "status": "completed",
                    "created_by": pr.get("created_by", "Unknown"),
                    "created_by_email": None,  # Not in REST transform
                    "source_branch": None,  # Not in REST transform
                    "description": None,  # Not in REST transform
                }
            )

        return pr_data

    except Exception as e:
        logger.warning(
            "API error querying PRs",
            extra={"project": project_name, "repo_id": repo_id, "days": days, "error": str(e)},
        )
        return []


# REMOVED: query_reopened_bugs
# Reason: Assumes bugs with state='Active' and recent StateChangeDate were "reopened".
# Doesn't verify if bug was previously closed - could be new bugs or state changes.
# Would require revision history to accurately track reopens.


def analyze_code_churn(commits: list[dict]) -> dict:
    """
    Analyze code churn from commits.

    Args:
        commits: List of commit data

    Returns:
        Churn analysis
    """
    file_change_counts: Counter[str] = Counter()
    total_changes = 0

    for commit in commits:
        total_changes += commit["changes"]
        for file_path in commit["files"]:
            file_change_counts[file_path] += 1

    # Get top N most changed files (hot paths)
    hot_paths = [
        {"path": path, "change_count": count}
        for path, count in file_change_counts.most_common(sampling_config.HOT_PATHS_LIMIT)
    ]

    return {
        "total_commits": len(commits),
        "total_file_changes": total_changes,
        "unique_files_touched": len(file_change_counts),
        "hot_paths": hot_paths,
        "avg_changes_per_commit": total_changes / len(commits) if commits else 0,
    }


# REMOVED: analyze_pr_sizes
# Reason: Uses commit count as proxy for PR size, not actual lines of code or file changes.
# Classification thresholds (<=3, 4-10, >10) are arbitrary.
# Would need to analyze actual file diffs to measure real PR size.


def calculate_knowledge_distribution(commits: list[dict]) -> dict:
    """
    Calculate knowledge distribution - bus factor / key person risk.

    HARD DATA: Files touched by only N unique developers.

    Args:
        commits: List of commit data

    Returns:
        Knowledge distribution metrics
    """

    file_contributors = defaultdict(set)  # file -> set of authors

    for commit in commits:
        author = commit.get("author", "Unknown")
        files = commit.get("files", [])

        for file_path in files:
            file_contributors[file_path].add(author)

    # Count files by contributor count
    single_owner_files = []
    two_owner_files = []
    multi_owner_files = []

    for file_path, contributors in file_contributors.items():
        contributor_count = len(contributors)

        if contributor_count == 1:
            single_owner_files.append({"path": file_path, "owner": list(contributors)[0]})
        elif contributor_count == 2:
            two_owner_files.append({"path": file_path, "contributors": list(contributors)})
        else:
            multi_owner_files.append({"path": file_path, "contributor_count": contributor_count})

    total_files = len(file_contributors)
    single_owner_pct = (len(single_owner_files) / total_files * 100) if total_files > 0 else 0

    return {
        "total_files_analyzed": total_files,
        "single_owner_count": len(single_owner_files),
        "two_owner_count": len(two_owner_files),
        "multi_owner_count": len(multi_owner_files),
        "single_owner_pct": round(single_owner_pct, 1),
        "single_owner_files": single_owner_files[:20],  # Top 20 for reference
    }


def calculate_module_coupling(commits: list[dict]) -> dict:
    """
    Calculate module coupling - files that change together.

    HARD DATA: Co-change patterns from commit history.

    Args:
        commits: List of commit data

    Returns:
        Module coupling metrics
    """
    from itertools import combinations

    file_pair_counts: defaultdict[tuple[str, str], int] = defaultdict(int)

    for commit in commits:
        files = commit.get("files", [])

        # For each commit with multiple files, count file pair co-changes
        if len(files) > 1:
            for file1, file2 in combinations(sorted(files), 2):
                # Sort to ensure consistent pairing
                pair = (file1, file2) if file1 < file2 else (file2, file1)
                file_pair_counts[pair] += 1

    # Find top coupled pairs
    coupled_pairs = [
        {"file1": pair[0], "file2": pair[1], "co_change_count": count}
        for pair, count in file_pair_counts.items()
        if count >= 3  # Only pairs that changed together 3+ times
    ]

    # Sort by co-change count (count is already int from defaultdict)
    coupled_pairs.sort(key=lambda x: x["co_change_count"], reverse=True)  # type: ignore[arg-type, return-value]

    return {
        "total_coupled_pairs": len(coupled_pairs),
        "top_coupled_pairs": coupled_pairs[:20],  # Top 20
        "note": "Pairs that changed together 3+ times",
    }


async def collect_risk_metrics_for_project(rest_client: AzureDevOpsRESTClient, project: dict, config: dict) -> dict:
    """
    Collect all risk metrics for a single project.

    Args:
        rest_client: Azure DevOps REST API client
        project: Project metadata from discovery
        config: Configuration dict

    Returns:
        Risk metrics dictionary for the project
    """
    project_name = project["project_name"]
    project_key = project["project_key"]

    # Get the actual ADO project name (may differ from display name)
    # Note: Risk metrics are at repository level, not work item level
    # Area path filters don't apply to Git repositories
    ado_project_name = project.get("ado_project_name", project_name)

    logger.info(f"Collecting risk metrics for: {project_name}", extra={"project_name": project_name})
    print(f"\n  Collecting risk metrics for: {project_name}")

    # Get repositories via REST API
    try:
        repos_response = await rest_client.get_repositories(project=ado_project_name)
        repos = GitTransformer.transform_repositories_response(repos_response)
        logger.info(f"Found {len(repos)} repositories", extra={"project_name": project_name, "repo_count": len(repos)})
        print(f"    Found {len(repos)} repositories")
    except Exception as e:
        logger.warning("API error getting repositories", extra={"project": ado_project_name, "error": str(e)})
        print(f"    [WARNING] Could not get repositories: {e}")
        repos = []

    # Query commits concurrently for all repos (PARALLEL EXECUTION)
    commit_tasks = [
        query_recent_commits(rest_client, ado_project_name, repo["id"], days=config.get("lookback_days", 90))
        for repo in repos
    ]

    commit_results = await asyncio.gather(*commit_tasks, return_exceptions=True)

    # Aggregate metrics across all repos - ONLY HARD DATA
    all_commits: list[dict] = []

    for repo, result in zip(repos, commit_results, strict=True):
        logger.debug(f"Analyzing repo: {repo['name']}", extra={"repo_name": repo["name"], "project": project_name})
        print(f"    Analyzing repo: {repo['name']}")

        if isinstance(result, Exception):
            logger.warning(
                "API error analyzing repo",
                extra={"repo_name": repo["name"], "project": project_name, "error": str(result)},
            )
            print(f"      [WARNING] Failed to analyze repo {repo['name']}: {result}")
            continue

        commits: list[dict] = result  # type: ignore[assignment]
        all_commits.extend(commits)  # type: ignore[arg-type]
        logger.debug(f"Found {len(commits)} commits", extra={"repo_name": repo["name"], "commit_count": len(commits)})  # type: ignore[arg-type]
        print(f"      Found {len(commits)} commits")  # type: ignore[arg-type]

    # Analyze code churn (HARD DATA ONLY)
    churn_analysis = analyze_code_churn(all_commits)
    knowledge_dist = calculate_knowledge_distribution(all_commits)
    module_coupling = calculate_module_coupling(all_commits)

    logger.info(
        "Risk metrics collected",
        extra={
            "project": project_name,
            "commits": churn_analysis["total_commits"],
            "files_touched": churn_analysis["unique_files_touched"],
            "single_owner_files": knowledge_dist["single_owner_count"],
            "coupled_pairs": module_coupling["total_coupled_pairs"],
        },
    )
    print(f"    Code churn: {churn_analysis['total_commits']} commits, {churn_analysis['unique_files_touched']} files")
    print(
        f"    Knowledge: {knowledge_dist['single_owner_count']} single-owner files ({knowledge_dist['single_owner_pct']}%)"
    )
    print(f"    Coupling: {module_coupling['total_coupled_pairs']} file pairs frequently changed together")

    return {
        "project_key": project_key,
        "project_name": project_name,
        "code_churn": churn_analysis,
        "knowledge_distribution": knowledge_dist,
        "module_coupling": module_coupling,
        "repository_count": len(repos),
        "collected_at": datetime.now().isoformat(),
    }


def save_risk_metrics(metrics: dict, output_file: str = ".tmp/observatory/risk_history.json") -> bool:
    """
    Save risk metrics to history file.

    Appends to existing history or creates new file.
    Validates data before saving to prevent persisting collection failures.
    """
    from execution.utils_atomic_json import atomic_json_save, load_json_with_recovery

    # Validate that we have actual data before saving
    projects = metrics.get("projects", [])

    if not projects:
        logger.warning("No project data to save - collection may have failed")
        print("\n[SKIPPED] No project data to save - collection may have failed")
        return False

    # Check if this looks like a failed collection (all zeros)
    total_commits = sum(p.get("code_churn", {}).get("total_commits", 0) for p in projects)
    total_files = sum(p.get("code_churn", {}).get("unique_files_touched", 0) for p in projects)
    total_repos = sum(p.get("repository_count", 0) for p in projects)

    if total_commits == 0 and total_files == 0 and total_repos == 0:
        logger.warning(
            "All projects returned zero risk data - likely a collection failure",
            extra={
                "project_count": len(projects),
                "total_commits": total_commits,
                "total_files": total_files,
                "total_repos": total_repos,
            },
        )
        print("\n[SKIPPED] All projects returned zero risk data - likely a collection failure")
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
        logger.info("Risk metrics saved", extra={"file": output_file, "week_count": len(history["weeks"])})
        print(f"\n[SAVED] Risk metrics saved to: {output_file}")
        print(f"        History now contains {len(history['weeks'])} week(s)")
        return True
    except (OSError, PermissionError) as e:
        print(f"\n[ERROR] Failed to save Risk metrics: {e}")
        return bool(
            log_and_return_default(
                logger,
                e,
                context={"file": output_file},
                default_value=False,
                error_type="File system error saving risk metrics",
            )
        )


class RiskCollector:
    """Risk metrics collector using BaseCollector infrastructure"""

    def __init__(self):
        from execution.collectors.base import BaseCollector

        class _BaseHelper(BaseCollector):
            async def collect(self, project, rest_client):
                pass

            def save_metrics(self, results):
                pass

        self._base = _BaseHelper(name="risk", lookback_days=90)
        self.config = self._base.config

    async def run(self) -> bool:
        with track_collector_performance("risk") as tracker:
            print("Director Observatory - Delivery Risk Metrics Collector (REST API)")
            print("=" * 60)

            discovery_data = self._base.load_discovery_data()
            projects = discovery_data.get("projects", [])
            tracker.project_count = len(projects)

            if not projects:
                return False

            rest_client = self._base.get_rest_client()

            print("\nCollecting delivery risk metrics (concurrent execution)...")
            print("=" * 60)

            tasks = [collect_risk_metrics_for_project(rest_client, project, self.config) for project in projects]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            project_metrics: list[dict] = []
            for project, result in zip(projects, results, strict=True):
                if isinstance(result, Exception):
                    logger.error(
                        "Error collecting metrics",
                        extra={"project": project.get("project_name", "Unknown"), "error": str(result)},
                    )
                    print(f"  [ERROR] Failed to collect metrics for {project.get('project_name', 'Unknown')}: {result}")
                else:
                    project_metrics.append(result)  # type: ignore[arg-type]

            week_metrics = {
                "week_date": datetime.now().strftime("%Y-%m-%d"),
                "week_number": datetime.now().isocalendar()[1],
                "projects": project_metrics,
                "config": self.config,
            }

            success = save_risk_metrics(week_metrics)
            tracker.success = success
            self._log_summary(project_metrics)
            return success

    def _log_summary(self, project_metrics: list[dict]) -> None:
        print("\n" + "=" * 60)
        print("Delivery Risk Metrics Collection Summary:")
        print(f"  Projects processed: {len(project_metrics)}")
        total_commits = sum(p["code_churn"]["total_commits"] for p in project_metrics)
        total_files = sum(p["code_churn"]["unique_files_touched"] for p in project_metrics)
        print(f"  Total commits analyzed: {total_commits}")
        print(f"  Total unique files changed: {total_files}")
        print("\nDelivery risk metrics collection complete (REST API + concurrent execution)!")
        print("  ✓ Only hard data - no speculation")
        print("  ✓ Code churn: Actual file change counts from commits")
        print("  ✓ Concurrent collection for maximum speed")
        print("\nNext step: Generate risk dashboard")


async def main() -> None:
    collector = RiskCollector()
    await collector.run()


if __name__ == "__main__":
    asyncio.run(main())
