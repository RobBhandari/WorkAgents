#!/usr/bin/env python3
"""
Test API Access for New Metrics
Checks what data is available from Azure DevOps for implementing new metrics
"""

import os
import sys
from datetime import datetime, timedelta

from azure.devops.connection import Connection
from dotenv import load_dotenv
from msrest.authentication import BasicAuthentication

load_dotenv()

def get_ado_connection():
    """Get ADO connection"""
    organization_url = os.getenv('ADO_ORGANIZATION_URL')
    pat = os.getenv('ADO_PAT')

    if not organization_url or not pat:
        raise ValueError("ADO_ORGANIZATION_URL and ADO_PAT must be set in .env")

    credentials = BasicAuthentication('', pat)
    connection = Connection(base_url=organization_url, creds=credentials)
    return connection

def test_build_api_access(connection, project_name):
    """Test if we can access Azure Pipelines build data"""
    print("\n" + "="*60)
    print("Testing Azure Pipelines / Build API Access")
    print("="*60)

    try:
        build_client = connection.clients.get_build_client()
        print("✓ Build client initialized")

        # Try to get build definitions (pipelines)
        try:
            definitions = build_client.get_definitions(project=project_name)
            print(f"✓ Found {len(definitions)} build definitions/pipelines")

            if definitions:
                print("\n  Available Pipelines:")
                for defn in definitions[:5]:  # Show first 5
                    print(f"    - {defn.name} (ID: {defn.id})")
                if len(definitions) > 5:
                    print(f"    ... and {len(definitions) - 5} more")
            else:
                print("  ⚠️  No build definitions found in this project")
                return False

        except Exception as e:
            print(f"✗ Cannot access build definitions: {e}")
            return False

        # Try to get recent builds
        try:
            lookback = datetime.now() - timedelta(days=30)
            builds = build_client.get_builds(
                project=project_name,
                min_time=lookback,
                top=5
            )
            print(f"✓ Found {len(builds)} builds in last 30 days")

            if builds:
                print("\n  Recent Builds:")
                for build in builds[:3]:
                    status = build.status or "Unknown"
                    result = build.result or "N/A"
                    duration = ""
                    if build.start_time and build.finish_time:
                        delta = build.finish_time - build.start_time
                        duration = f" ({delta.total_seconds()/60:.1f} min)"
                    print(f"    - {build.definition.name}: {result}{duration}")

            return True

        except Exception as e:
            print(f"✗ Cannot access builds: {e}")
            return False

    except Exception as e:
        print(f"✗ Build API not accessible: {e}")
        return False

def test_test_api_access(connection, project_name):
    """Test if we can access test results data"""
    print("\n" + "="*60)
    print("Testing Test Results API Access")
    print("="*60)

    try:
        test_client = connection.clients.get_test_client()
        print("✓ Test client initialized")

        # This will fail gracefully if no test runs exist
        try:
            test_runs = test_client.get_test_runs(project=project_name, top=5)
            if test_runs:
                print(f"✓ Found {len(test_runs)} recent test runs")
                return True
            else:
                print("  ⚠️  No test runs found (tests may not be configured)")
                return False
        except Exception as e:
            print(f"  ⚠️  Test runs not accessible: {e}")
            return False

    except Exception as e:
        print(f"✗ Test API not accessible: {e}")
        return False

def test_pr_advanced_access(connection, project_name):
    """Test if we can access PR threads, iterations, work items"""
    print("\n" + "="*60)
    print("Testing Advanced PR API Access")
    print("="*60)

    try:
        git_client = connection.clients.get_git_client()
        print("✓ Git client initialized")

        # Get first repo
        repos = git_client.get_repositories(project=project_name)
        if not repos:
            print("  ⚠️  No repositories found")
            return False

        repo = repos[0]
        print(f"  Testing with repo: {repo.name}")

        # Get a recent PR
        from azure.devops.v7_1.git.models import GitPullRequestSearchCriteria
        search_criteria = GitPullRequestSearchCriteria(status='completed')
        prs = git_client.get_pull_requests(
            repository_id=repo.id,
            project=project_name,
            search_criteria=search_criteria,
            top=1
        )

        if not prs:
            print("  ⚠️  No PRs found to test with")
            return False

        pr = prs[0]
        print(f"  Testing with PR #{pr.pull_request_id}: {pr.title[:50]}")

        # Test PR threads (for review comments)
        try:
            threads = git_client.get_threads(
                repository_id=repo.id,
                pull_request_id=pr.pull_request_id,
                project=project_name
            )
            print(f"  ✓ Can access PR threads/comments ({len(threads)} threads)")
        except Exception as e:
            print(f"  ✗ Cannot access PR threads: {e}")
            return False

        # Test PR iterations (for review cycles)
        try:
            iterations = git_client.get_pull_request_iterations(
                repository_id=repo.id,
                pull_request_id=pr.pull_request_id,
                project=project_name
            )
            print(f"  ✓ Can access PR iterations ({len(iterations)} iterations)")
        except Exception as e:
            print(f"  ✗ Cannot access PR iterations: {e}")
            return False

        # Test PR work items (for linking PRs to work)
        try:
            work_items = git_client.get_pull_request_work_item_refs(
                repository_id=repo.id,
                pull_request_id=pr.pull_request_id,
                project=project_name
            )
            print(f"  ✓ Can access PR work items ({len(work_items)} linked)")
        except Exception as e:
            print(f"  ✗ Cannot access PR work items: {e}")
            return False

        return True

    except Exception as e:
        print(f"✗ Advanced PR API not accessible: {e}")
        return False

def main():
    print("="*60)
    print("API Access Test for New Metrics Implementation")
    print("="*60)

    try:
        connection = get_ado_connection()
        print("✓ Connected to Azure DevOps")

        # Load a project to test with
        import json
        try:
            with open(".tmp/observatory/ado_structure.json", encoding='utf-8') as f:
                discovery_data = json.load(f)
            projects = discovery_data['projects']
            if not projects:
                print("✗ No projects found in discovery data")
                return 1

            # Use first project for testing
            test_project = projects[0]
            project_name = test_project.get('ado_project_name', test_project['project_name'])
            print(f"\nTesting with project: {project_name}")

        except FileNotFoundError:
            print("✗ Run discover_projects.py first")
            return 1

        # Run tests
        results = {}
        results['build_api'] = test_build_api_access(connection, project_name)
        results['test_api'] = test_test_api_access(connection, project_name)
        results['pr_advanced_api'] = test_pr_advanced_access(connection, project_name)

        # Summary
        print("\n" + "="*60)
        print("ACCESS SUMMARY")
        print("="*60)

        print("\nWhat You CAN Build:")
        if results['build_api']:
            print("  ✓ Deployment Dashboard (DORA metrics)")
            print("    - Deployment Frequency")
            print("    - Build Success Rate")
            print("    - Build Duration")
            print("    - Lead Time for Changes")
        else:
            print("  ✗ Deployment Dashboard - NO BUILD DATA AVAILABLE")

        if results['pr_advanced_api']:
            print("\n  ✓ Enhanced PR Metrics")
            print("    - PR Review Time")
            print("    - PR Merge Time")
            print("    - Review Iteration Count")
            print("    - PR → Work Item linking")
        else:
            print("\n  ✗ Enhanced PR Metrics - LIMITED PR DATA")

        if results['test_api']:
            print("\n  ✓ Test Quality Metrics")
            print("    - Test Coverage %")
            print("    - Test Execution Time")
            print("    - Flaky Test Rate")
        else:
            print("\n  ⚠️  Test Quality Metrics - NO TEST DATA")
            print("      (Only available if tests run in Azure Pipelines)")

        print("\n  ✓ Quick Win Metrics (Git/Work Items)")
        print("    - Throughput")
        print("    - Cycle Time Variance")
        print("    - Planned vs Unplanned Ratio")
        print("    - After-Hours Work %")
        print("    - Developer Active Days")
        print("    - Knowledge Distribution")
        print("    - Module Coupling")

        # Recommendations
        print("\n" + "="*60)
        print("RECOMMENDATIONS")
        print("="*60)

        if not results['build_api']:
            print("\n⚠️  No Azure Pipelines Data Found")
            print("   This could mean:")
            print("   1. No pipelines are configured in this project")
            print("   2. Your PAT doesn't have Build (Read) permissions")
            print("   3. Builds are in a different project")
            print("\n   To enable Deployment Dashboard:")
            print("   - Check PAT permissions at: https://dev.azure.com/[org]/_usersSettings/tokens")
            print("   - Ensure 'Build (Read)' scope is enabled")
        else:
            print("\n✓ You have everything needed for Deployment Dashboard!")

        if not results['test_api']:
            print("\n⚠️  No Test Runs Found")
            print("   Test metrics require automated tests running in Azure Pipelines")
            print("   You can still implement all other metrics")

        print("\n" + "="*60)
        successful = sum(1 for v in results.values() if v)
        print(f"APIs Available: {successful}/3")
        print("="*60)

        return 0

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    sys.exit(main())
