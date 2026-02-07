#!/usr/bin/env python3
"""
Diagnostic script to understand the structure of Git changes from Azure DevOps API
"""

import os
import sys
from datetime import datetime, timedelta

from azure.devops.connection import Connection
from azure.devops.v7_1.git.models import GitQueryCommitsCriteria
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

def diagnose_change_structure():
    """Diagnose the structure of change objects"""

    # Connect to ADO
    connection = get_ado_connection()
    git_client = connection.clients.get_git_client()

    # Get first project with repositories
    core_client = connection.clients.get_core_client()
    projects = core_client.get_projects()

    found_commits = False
    for project in projects[:10]:  # Check first 10 projects
        if found_commits:
            break

        print(f"\n{'='*60}")
        print(f"Project: {project.name}")
        print(f"{'='*60}")

        try:
            repos = git_client.get_repositories(project=project.name)
            print(f"Found {len(repos)} repositories")

            if not repos:
                continue

            # Try first few repos until we find one with commits
            for repo in repos[:5]:
                print(f"\nAnalyzing repo: {repo.name}")

                since_date = datetime.now() - timedelta(days=90)  # Last 90 days
                search_criteria = GitQueryCommitsCriteria(from_date=since_date.isoformat())

                commits = git_client.get_commits(
                    repository_id=repo.id,
                    project=project.name,
                    search_criteria=search_criteria
                )

                if not commits:
                    print("  No commits found in this repo")
                    continue

                found_commits = True

                # Get first commit
                commit = commits[0]
                print(f"\nFirst commit: {commit.commit_id[:8]}")
                print(f"  Message: {commit.comment[:50] if commit.comment else 'N/A'}...")

                # Get changes for this commit
                changes = git_client.get_changes(
                    commit_id=commit.commit_id,
                    repository_id=repo.id,
                    project=project.name
                )

                print(f"\nChanges object type: {type(changes)}")
                print(f"Changes attributes: {dir(changes)}")

                if hasattr(changes, 'changes') and changes.changes:
                    print(f"\nNumber of changes: {len(changes.changes)}")

                    # Examine first change
                    if len(changes.changes) > 0:
                        change = changes.changes[0]
                        print("\nFirst change object:")
                        print(f"  Type: {type(change)}")
                        if isinstance(change, dict):
                            print(f"  Keys: {list(change.keys())}")
                            print(f"  Full content: {change}")
                        else:
                            print(f"  Attributes: {[attr for attr in dir(change) if not attr.startswith('_')]}")

                        # Check for common path-related attributes
                        print("\n  Checking path attributes:")
                        print(f"    hasattr(change, 'item'): {hasattr(change, 'item')}")
                        if hasattr(change, 'item'):
                            print(f"    change.item type: {type(change.item)}")
                            if change.item:
                                print(f"    change.item attributes: {[attr for attr in dir(change.item) if not attr.startswith('_')]}")
                                print(f"    hasattr(change.item, 'path'): {hasattr(change.item, 'path')}")
                                if hasattr(change.item, 'path'):
                                    print(f"    change.item.path: {change.item.path}")

                        print(f"\n    hasattr(change, 'path'): {hasattr(change, 'path')}")
                        if hasattr(change, 'path'):
                            print(f"    change.path: {change.path}")

                        print(f"\n    hasattr(change, 'source_server_item'): {hasattr(change, 'source_server_item')}")
                        if hasattr(change, 'source_server_item'):
                            print(f"    change.source_server_item: {change.source_server_item}")

                        # Try to print the object as dict
                        print("\n  Trying to access as dict:")
                        try:
                            print(f"    change.__dict__: {change.__dict__ if hasattr(change, '__dict__') else 'N/A'}")
                        except:
                            print("    Cannot access __dict__")

                        # Print first 3 changes
                        print("\nFirst 3 changes (attempting path extraction):")
                        for i, chg in enumerate(changes.changes[:3]):
                            print(f"\n  Change {i+1}:")
                            # Try different ways to get path
                            path = None
                            try:
                                if hasattr(chg, 'item') and chg.item and hasattr(chg.item, 'path'):
                                    path = chg.item.path
                                    print(f"    Path (via item.path): {path}")
                            except Exception as e:
                                print(f"    Error accessing item.path: {e}")

                            # Return after first successful project analysis
                            if i == 2:
                                return

                # Break out of repo loop if we found commits
                break

        except Exception as e:
            print(f"  Error analyzing project: {e}")
            import traceback
            traceback.print_exc()
            continue

if __name__ == "__main__":
    diagnose_change_structure()
