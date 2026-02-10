"""
Azure DevOps REST API Response Transformers

Converts REST API JSON responses to SDK-compatible formats.
Ensures backward compatibility during SDK → REST migration.

The Azure DevOps SDK wraps responses in custom object types. When migrating
to direct REST API calls, we need to transform raw JSON responses to match
the structure expected by existing collector code.

Usage:
    from execution.collectors.ado_rest_transformers import WorkItemTransformer

    # REST API returns:
    rest_response = {"count": 2, "value": [{"id": 1001, "fields": {...}}]}

    # Transform to SDK format:
    work_items = WorkItemTransformer.transform_work_items_response(rest_response)
    # Result: [{"System.Id": 1001, ...}]
"""

from datetime import datetime
from typing import Any


class WorkItemReference:
    """
    Mock SDK WorkItemReference object.

    The SDK's WIQL query returns WorkItemReference objects with an 'id' attribute.
    This class replicates that interface for REST API responses.
    """

    def __init__(self, id: int, url: str | None = None):
        """
        Initialize work item reference.

        Args:
            id: Work item ID
            url: Optional work item URL
        """
        self.id = id
        self.url = url


class WiqlResult:
    """
    Mock SDK WIQL query result object.

    The SDK's wit_client.query_by_wiql() returns an object with a 'work_items' attribute.
    This class replicates that interface for REST API responses.
    """

    def __init__(self, work_items: list[WorkItemReference]):
        """
        Initialize WIQL result.

        Args:
            work_items: List of WorkItemReference objects
        """
        self.work_items = work_items


class WorkItemTransformer:
    """
    Transform work item REST responses to SDK-compatible format.

    Handles:
    - WIQL query results
    - Work items batch fetch results
    - Field normalization
    """

    @staticmethod
    def transform_wiql_response(rest_response: dict[str, Any]) -> WiqlResult:
        """
        Transform WIQL query REST response to SDK format.

        REST Response:
        {
            "queryType": "flat",
            "queryResultType": "workItem",
            "workItems": [
                {"id": 1001, "url": "..."},
                {"id": 1002, "url": "..."}
            ]
        }

        SDK Format (what collector code expects):
        WiqlResult object with work_items attribute:
            result.work_items = [
                WorkItemReference(id=1001),
                WorkItemReference(id=1002)
            ]

        Args:
            rest_response: Raw REST API response dict

        Returns:
            WiqlResult object with work_items list

        Example:
            result = await client.query_by_wiql(project="...", wiql_query="...")
            wiql_result = WorkItemTransformer.transform_wiql_response(result)
            ids = [item.id for item in wiql_result.work_items]
        """
        work_items = [
            WorkItemReference(id=item["id"], url=item.get("url")) for item in rest_response.get("workItems", [])
        ]
        return WiqlResult(work_items=work_items)

    @staticmethod
    def transform_work_items_response(rest_response: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Transform work items REST response to SDK format.

        REST Response:
        {
            "count": 2,
            "value": [
                {
                    "id": 1001,
                    "fields": {
                        "System.Title": "Bug title",
                        "System.State": "Active"
                    }
                },
                {
                    "id": 1002,
                    "fields": {...}
                }
            ]
        }

        SDK Format (what collector code expects):
        [
            {
                "System.Id": 1001,
                "System.Title": "Bug title",
                "System.State": "Active"
            },
            {
                "System.Id": 1002,
                ...
            }
        ]

        The SDK merges the 'id' into the 'fields' dict as 'System.Id'.
        This transformation replicates that behavior.

        Args:
            rest_response: Raw REST API response dict

        Returns:
            List of work item field dictionaries

        Example:
            response = await client.get_work_items(ids=[1001, 1002])
            items = WorkItemTransformer.transform_work_items_response(response)
            for item in items:
                print(item["System.Title"], item["System.State"])
        """
        items = []
        for item in rest_response.get("value", []):
            # Merge id into fields dictionary
            fields = item.get("fields", {}).copy()
            fields["System.Id"] = item.get("id")

            # Add other top-level properties if needed
            if "rev" in item:
                fields["System.Rev"] = item["rev"]
            if "url" in item:
                fields["url"] = item["url"]

            items.append(fields)
        return items


class BuildTransformer:
    """
    Transform build REST responses to SDK-compatible format.

    Handles:
    - Build query results
    - Build changes (commits)
    - Definition details
    """

    @staticmethod
    def transform_builds_response(rest_response: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Transform builds REST response to simplified dict format.

        REST API returns comprehensive build details. Extract fields that collectors need.

        REST Response:
        {
            "count": 10,
            "value": [
                {
                    "id": 123,
                    "buildNumber": "20260210.1",
                    "definition": {"id": 5, "name": "MyPipeline"},
                    "status": "completed",
                    "result": "succeeded",
                    "startTime": "2026-02-10T10:00:00Z",
                    "finishTime": "2026-02-10T10:15:00Z",
                    "sourceBranch": "refs/heads/main",
                    "sourceVersion": "abc123",
                    "requestedFor": {"displayName": "John Doe"}
                }
            ]
        }

        SDK Format (simplified for collectors):
        [
            {
                "id": 123,
                "build_number": "20260210.1",
                "definition": {"id": 5, "name": "MyPipeline"},
                "status": "completed",
                "result": "succeeded",
                "start_time": "2026-02-10T10:00:00Z",
                "finish_time": "2026-02-10T10:15:00Z",
                "source_branch": "refs/heads/main",
                "source_version": "abc123",
                "requested_for": "John Doe"
            }
        ]

        Args:
            rest_response: Raw REST API response dict

        Returns:
            List of build dictionaries with normalized field names

        Example:
            response = await client.get_builds(project="...", min_time="...")
            builds = BuildTransformer.transform_builds_response(response)
            for build in builds:
                print(build["build_number"], build["status"], build["result"])
        """
        builds = []
        for build in rest_response.get("value", []):
            builds.append(
                {
                    "id": build.get("id"),
                    "build_number": build.get("buildNumber"),
                    "definition": {
                        "id": build.get("definition", {}).get("id"),
                        "name": build.get("definition", {}).get("name"),
                    },
                    "status": build.get("status"),
                    "result": build.get("result"),
                    "start_time": build.get("startTime"),
                    "finish_time": build.get("finishTime"),
                    "source_branch": build.get("sourceBranch"),
                    "source_version": build.get("sourceVersion"),
                    "requested_for": build.get("requestedFor", {}).get("displayName"),
                }
            )
        return builds

    @staticmethod
    def transform_build_changes_response(rest_response: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Transform build changes (commits) REST response.

        REST Response:
        {
            "count": 3,
            "value": [
                {
                    "id": "abc123",
                    "message": "Fix bug",
                    "timestamp": "2026-02-10T09:00:00Z",
                    "author": {"displayName": "John Doe"}
                }
            ]
        }

        SDK Format:
        [
            {
                "id": "abc123",
                "message": "Fix bug",
                "timestamp": "2026-02-10T09:00:00Z",
                "author": "John Doe"
            }
        ]

        Args:
            rest_response: Raw REST API response dict

        Returns:
            List of change dictionaries

        Example:
            response = await client.get_build_changes(project="...", build_id=123)
            changes = BuildTransformer.transform_build_changes_response(response)
        """
        changes = []
        for change in rest_response.get("value", []):
            changes.append(
                {
                    "id": change.get("id"),
                    "message": change.get("message"),
                    "timestamp": change.get("timestamp"),
                    "author": change.get("author", {}).get("displayName"),
                }
            )
        return changes


class GitTransformer:
    """
    Transform Git REST responses to SDK-compatible format.

    Handles:
    - Pull requests
    - PR threads (comments)
    - PR iterations (pushes)
    - Commits
    - Changes (files modified)
    """

    @staticmethod
    def transform_pull_requests_response(rest_response: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Transform pull requests REST response to simplified format.

        REST Response:
        {
            "count": 10,
            "value": [
                {
                    "pullRequestId": 42,
                    "title": "Fix bug",
                    "creationDate": "2026-02-10T10:00:00Z",
                    "closedDate": "2026-02-10T11:00:00Z",
                    "createdBy": {"displayName": "John Doe"},
                    "repository": {"id": "repo-guid", "name": "MyRepo"}
                }
            ]
        }

        SDK Format (simplified):
        [
            {
                "pull_request_id": 42,
                "title": "Fix bug",
                "creation_date": "2026-02-10T10:00:00Z",
                "closed_date": "2026-02-10T11:00:00Z",
                "created_by": "John Doe",
                "repository_id": "repo-guid"
            }
        ]

        Args:
            rest_response: Raw REST API response dict

        Returns:
            List of PR dictionaries with normalized field names

        Example:
            response = await client.get_pull_requests(project="...", repository_id="...", status="completed")
            prs = GitTransformer.transform_pull_requests_response(response)
        """
        prs = []
        for pr in rest_response.get("value", []):
            prs.append(
                {
                    "pull_request_id": pr.get("pullRequestId"),
                    "title": pr.get("title"),
                    "creation_date": pr.get("creationDate"),
                    "closed_date": pr.get("closedDate"),
                    "created_by": pr.get("createdBy", {}).get("displayName"),
                    "repository_id": pr.get("repository", {}).get("id"),
                    "repository_name": pr.get("repository", {}).get("name"),
                }
            )
        return prs

    @staticmethod
    def transform_threads_response(rest_response: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Transform PR threads (comments) REST response.

        REST Response:
        {
            "count": 5,
            "value": [
                {
                    "id": 1,
                    "publishedDate": "2026-02-10T10:30:00Z",
                    "comments": [
                        {"content": "LGTM", "publishedDate": "2026-02-10T10:30:00Z"}
                    ]
                }
            ]
        }

        SDK Format:
        [
            {
                "id": 1,
                "published_date": "2026-02-10T10:30:00Z",
                "comments": [...]
            }
        ]

        Args:
            rest_response: Raw REST API response dict

        Returns:
            List of thread dictionaries

        Example:
            response = await client.get_pull_request_threads(project="...", repository_id="...", pull_request_id=42)
            threads = GitTransformer.transform_threads_response(response)
        """
        threads = []
        for thread in rest_response.get("value", []):
            threads.append(
                {
                    "id": thread.get("id"),
                    "published_date": thread.get("publishedDate"),
                    "comments": thread.get("comments", []),
                }
            )
        return threads

    @staticmethod
    def transform_commits_response(rest_response: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Transform commits REST response.

        REST Response:
        {
            "count": 100,
            "value": [
                {
                    "commitId": "abc123",
                    "comment": "Fix bug",
                    "author": {
                        "name": "John Doe",
                        "email": "john@example.com",
                        "date": "2026-02-10T10:00:00Z"
                    }
                }
            ]
        }

        SDK Format:
        [
            {
                "commit_id": "abc123",
                "comment": "Fix bug",
                "author_name": "John Doe",
                "author_date": "2026-02-10T10:00:00Z"
            }
        ]

        Args:
            rest_response: Raw REST API response dict

        Returns:
            List of commit dictionaries

        Example:
            response = await client.get_commits(project="...", repository_id="...", from_date="...")
            commits = GitTransformer.transform_commits_response(response)
        """
        commits = []
        for commit in rest_response.get("value", []):
            commits.append(
                {
                    "commit_id": commit.get("commitId"),
                    "comment": commit.get("comment"),
                    "author_name": commit.get("author", {}).get("name"),
                    "author_email": commit.get("author", {}).get("email"),
                    "author_date": commit.get("author", {}).get("date"),
                }
            )
        return commits


class TestTransformer:
    """
    Transform test REST responses to SDK-compatible format.

    Handles:
    - Test runs
    - Test results
    """

    @staticmethod
    def transform_test_runs_response(rest_response: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Transform test runs REST response.

        REST Response:
        {
            "count": 50,
            "value": [
                {
                    "id": 123,
                    "name": "My Test Run",
                    "startedDate": "2026-02-10T10:00:00Z",
                    "completedDate": "2026-02-10T10:15:00Z",
                    "totalTests": 100,
                    "passedTests": 95,
                    "failedTests": 5
                }
            ]
        }

        SDK Format:
        [
            {
                "id": 123,
                "name": "My Test Run",
                "started_date": "2026-02-10T10:00:00Z",
                "completed_date": "2026-02-10T10:15:00Z",
                "total_tests": 100,
                "passed_tests": 95,
                "failed_tests": 5
            }
        ]

        Args:
            rest_response: Raw REST API response dict

        Returns:
            List of test run dictionaries

        Example:
            response = await client.get_test_runs(project="...", top=50)
            test_runs = TestTransformer.transform_test_runs_response(response)
            for run in test_runs:
                duration = parse_datetime(run["completed_date"]) - parse_datetime(run["started_date"])
        """
        runs = []
        for run in rest_response.get("value", []):
            runs.append(
                {
                    "id": run.get("id"),
                    "name": run.get("name"),
                    "started_date": run.get("startedDate"),
                    "completed_date": run.get("completedDate"),
                    "total_tests": run.get("totalTests"),
                    "passed_tests": run.get("passedTests"),
                    "failed_tests": run.get("failedTests"),
                }
            )
        return runs
