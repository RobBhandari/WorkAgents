#!/usr/bin/env python3
"""
ADO Delivery Risk Metrics Collector for Director Observatory

Collects delivery risk and change stability metrics at project level:
- PR Size Distribution: Small vs large changes
- Code Churn: Files changed frequently (hot paths)
- Change Risk: Large changes to core files
- Reopened Bugs: Bugs reopened after recent changes

Read-only operation - does not modify any existing data.
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

# Azure DevOps SDK
from azure.devops.connection import Connection

# Load environment variables
from dotenv import load_dotenv
from msrest.authentication import BasicAuthentication

from execution.core import get_config

load_dotenv()


def get_ado_connection():
    """Get ADO connection using credentials from .env"""
    organization_url = get_config().get("ADO_ORGANIZATION_URL")
    pat = get_config().get_ado_config().pat

    if not organization_url or not pat:
        raise ValueError("ADO_ORGANIZATION_URL and ADO_PAT must be set in .env file")

    credentials = BasicAuthentication("", pat)
    connection = Connection(base_url=organization_url, creds=credentials)
    return connection


def query_recent_commits(git_client, project_name: str, repo_id: str, days: int = 90) -> list[dict]:
    """
    Query recent commits to analyze code churn.

    Args:
        git_client: Git client
        project_name: ADO project name
        repo_id: Repository ID
        days: Lookback period in days

    Returns:
        List of commits with file changes
    """
    since_date = datetime.now() - timedelta(days=days)

    try:
        # Azure DevOps SDK expects parameters directly, not in search_criteria dict
        from azure.devops.v7_1.git.models import GitQueryCommitsCriteria

        search_criteria = GitQueryCommitsCriteria(from_date=since_date.isoformat())

        commits = git_client.get_commits(
            repository_id=repo_id,
            project=project_name,
            search_criteria=search_criteria,
            top=100,  # Limit to 100 most recent commits for performance
        )

        commit_data = []

        # Process ALL commits for author/date info, but only fetch file details for first 20 (performance optimization)
        for idx, commit in enumerate(commits):
            # Fetch file details only for first 20 commits (representative sample for hot paths)
            if idx < 20:
                try:
                    changes = git_client.get_changes(
                        commit_id=commit.commit_id, repository_id=repo_id, project=project_name
                    )

                    commit_data.append(
                        {
                            "commit_id": commit.commit_id,
                            "author": commit.author.name if commit.author else "Unknown",
                            "date": commit.author.date if commit.author else None,
                            "message": commit.comment,
                            "changes": len(changes.changes) if changes.changes else 0,
                            "files": (
                                [
                                    change["item"]["path"]
                                    for change in changes.changes
                                    if isinstance(change, dict)
                                    and "item" in change
                                    and change["item"]
                                    and "path" in change["item"]
                                ]
                                if changes.changes
                                else []
                            ),
                        }
                    )
                except Exception as e:
                    print(f"        [WARNING] Could not get changes for commit {commit.commit_id}: {e}")
                    # Still add commit with basic info
                    commit_data.append(
                        {
                            "commit_id": commit.commit_id,
                            "author": commit.author.name if commit.author else "Unknown",
                            "date": commit.author.date if commit.author else None,
                            "message": commit.comment,
                            "changes": 0,
                            "files": [],
                        }
                    )
            else:
                # For commits beyond first 20, only store basic info (no file details)
                commit_data.append(
                    {
                        "commit_id": commit.commit_id,
                        "author": commit.author.name if commit.author else "Unknown",
                        "date": commit.author.date if commit.author else None,
                        "message": commit.comment,
                        "changes": 0,
                        "files": [],
                    }
                )

        return commit_data

    except Exception as e:
        print(f"      [WARNING] Could not query commits: {e}")
        return []


def query_pull_requests(git_client, project_name: str, repo_id: str, days: int = 90) -> list[dict]:
    """
    Query recent pull requests to analyze PR size.

    Args:
        git_client: Git client
        project_name: ADO project name
        repo_id: Repository ID
        days: Lookback period in days

    Returns:
        List of PR data
    """
    try:
        # Azure DevOps SDK expects GitPullRequestSearchCriteria object
        from azure.devops.v7_1.git.models import GitPullRequestSearchCriteria

        # Use string value for status instead of enum (which doesn't exist in SDK)
        search_criteria = GitPullRequestSearchCriteria(status="completed")

        prs = git_client.get_pull_requests(
            repository_id=repo_id,
            project=project_name,
            search_criteria=search_criteria,
            # No top limit - fetch ALL PRs
        )

        pr_data = []
        cutoff_date = datetime.now(prs[0].creation_date.tzinfo if prs and prs[0].creation_date else None) - timedelta(
            days=days
        )

        for pr in prs:
            if pr.creation_date < cutoff_date:
                continue

            # Get PR commits to estimate size
            try:
                commits = git_client.get_pull_request_commits(
                    repository_id=repo_id, pull_request_id=pr.pull_request_id, project=project_name
                )
                commit_count = len(commits) if commits else 0
            except:
                commit_count = 0

            pr_data.append(
                {
                    "pr_id": pr.pull_request_id,
                    "title": pr.title,
                    "created_date": pr.creation_date.isoformat() if pr.creation_date else None,
                    "closed_date": pr.closed_date.isoformat() if pr.closed_date else None,
                    "commit_count": commit_count,
                    "status": pr.status,
                    "created_by": pr.created_by.display_name if pr.created_by else "Unknown",
                    "created_by_email": pr.created_by.unique_name if pr.created_by else None,
                    "source_branch": pr.source_ref_name if hasattr(pr, "source_ref_name") else None,
                    "description": pr.description if hasattr(pr, "description") else None,
                }
            )

        return pr_data

    except Exception as e:
        print(f"      [WARNING] Could not query PRs: {e}")
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
    file_change_counts = Counter()
    total_changes = 0

    for commit in commits:
        total_changes += commit["changes"]
        for file_path in commit["files"]:
            file_change_counts[file_path] += 1

    # Get top 20 most changed files (hot paths)
    hot_paths = [{"path": path, "change_count": count} for path, count in file_change_counts.most_common(20)]

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

    file_pair_counts = defaultdict(int)

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

    # Sort by co-change count
    coupled_pairs.sort(key=lambda x: x["co_change_count"], reverse=True)

    return {
        "total_coupled_pairs": len(coupled_pairs),
        "top_coupled_pairs": coupled_pairs[:20],  # Top 20
        "note": "Pairs that changed together 3+ times",
    }


def collect_risk_metrics_for_project(connection, project: dict, config: dict) -> dict:
    """
    Collect all risk metrics for a single project.

    Args:
        connection: ADO connection
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

    print(f"\n  Collecting risk metrics for: {project_name}")

    git_client = connection.clients.get_git_client()
    wit_client = connection.clients.get_work_item_tracking_client()

    # Get repositories
    try:
        repos = git_client.get_repositories(project=ado_project_name)
        print(f"    Found {len(repos)} repositories")
    except Exception as e:
        print(f"    [WARNING] Could not get repositories: {e}")
        repos = []

    # Aggregate metrics across all repos - ONLY HARD DATA
    all_commits = []

    for repo in repos:  # Analyze ALL repositories for complete data
        print(f"    Analyzing repo: {repo.name}")

        try:
            # Get commits for code churn analysis
            commits = query_recent_commits(git_client, ado_project_name, repo.id, days=config.get("lookback_days", 90))
            all_commits.extend(commits)
            print(f"      Found {len(commits)} commits")
        except Exception as e:
            print(f"      [WARNING] Failed to analyze repo {repo.name}: {e}")
            continue

    # Analyze code churn (HARD DATA ONLY)
    churn_analysis = analyze_code_churn(all_commits)
    knowledge_dist = calculate_knowledge_distribution(all_commits)
    module_coupling = calculate_module_coupling(all_commits)

    print(f"    Code churn: {churn_analysis['total_commits']} commits, {churn_analysis['unique_files_touched']} files")
    print(
        f"    Knowledge: {knowledge_dist['single_owner_count']} single-owner files ({knowledge_dist['single_owner_pct']}%)"
    )
    print(f"    Coupling: {module_coupling['total_coupled_pairs']} file pairs frequently changed together")

    return {
        "project_key": project_key,
        "project_name": project_name,
        "code_churn": churn_analysis,
        "knowledge_distribution": knowledge_dist,  # NEW
        "module_coupling": module_coupling,  # NEW
        "repository_count": len(repos),
        "collected_at": datetime.now().isoformat(),
    }


def save_risk_metrics(metrics: dict, output_file: str = ".tmp/observatory/risk_history.json"):
    """
    Save risk metrics to history file.

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
    total_commits = sum(p.get("code_churn", {}).get("total_commits", 0) for p in projects)
    total_files = sum(p.get("code_churn", {}).get("unique_files_touched", 0) for p in projects)
    total_repos = sum(p.get("repository_count", 0) for p in projects)

    if total_commits == 0 and total_files == 0 and total_repos == 0:
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
        print(f"\n[SAVED] Risk metrics saved to: {output_file}")
        print(f"        History now contains {len(history['weeks'])} week(s)")
        return True
    except Exception as e:
        print(f"\n[ERROR] Failed to save Risk metrics: {e}")
        return False


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    print("Director Observatory - Delivery Risk Metrics Collector\n")
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
    print("\nCollecting delivery risk metrics...")
    print("=" * 60)

    project_metrics = []
    for project in projects:
        try:
            metrics = collect_risk_metrics_for_project(connection, project, config)
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

    save_risk_metrics(week_metrics)

    # Summary
    print("\n" + "=" * 60)
    print("Delivery Risk Metrics Collection Summary:")
    print(f"  Projects processed: {len(project_metrics)}")

    total_commits = sum(p["code_churn"]["total_commits"] for p in project_metrics)
    total_files = sum(p["code_churn"]["unique_files_touched"] for p in project_metrics)

    print(f"  Total commits analyzed: {total_commits}")
    print(f"  Total unique files changed: {total_files}")

    print("\nDelivery risk metrics collection complete!")
    print("  ✓ Only hard data - no speculation")
    print("  ✓ Code churn: Actual file change counts from commits")
    print("\nNext step: Generate risk dashboard")
