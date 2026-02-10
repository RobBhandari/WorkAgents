"""
Unit Tests for Azure DevOps REST API Transformers

Tests response transformation from REST JSON to SDK-compatible formats.

Test Coverage:
- WorkItemTransformer (WIQL results, work items)
- BuildTransformer (builds, build changes)
- GitTransformer (PRs, threads, commits)
- TestTransformer (test runs)
"""

import pytest

from execution.collectors.ado_rest_transformers import (
    BuildTransformer,
    GitTransformer,
    TestTransformer,
    WiqlResult,
    WorkItemReference,
    WorkItemTransformer,
)


class TestWorkItemTransformer:
    """Test WorkItemTransformer"""

    def test_transform_wiql_response(self):
        """Test WIQL response transformation"""
        rest_response = {
            "queryType": "flat",
            "queryResultType": "workItem",
            "workItems": [{"id": 1001, "url": "https://..."}, {"id": 1002, "url": "https://..."}],
        }

        result = WorkItemTransformer.transform_wiql_response(rest_response)

        assert isinstance(result, WiqlResult)
        assert len(result.work_items) == 2
        assert result.work_items[0].id == 1001
        assert result.work_items[1].id == 1002

    def test_transform_wiql_response_empty(self):
        """Test WIQL response with no results"""
        rest_response = {"queryType": "flat", "workItems": []}

        result = WorkItemTransformer.transform_wiql_response(rest_response)

        assert len(result.work_items) == 0

    def test_transform_work_items_response(self):
        """Test work items response transformation"""
        rest_response = {
            "count": 2,
            "value": [
                {"id": 1001, "rev": 5, "fields": {"System.Title": "Bug 1", "System.State": "Active"}},
                {"id": 1002, "rev": 3, "fields": {"System.Title": "Bug 2", "System.State": "Closed"}},
            ],
        }

        items = WorkItemTransformer.transform_work_items_response(rest_response)

        assert len(items) == 2
        # Verify System.Id is merged from top-level id
        assert items[0]["System.Id"] == 1001
        assert items[0]["System.Title"] == "Bug 1"
        assert items[0]["System.Rev"] == 5
        assert items[1]["System.Id"] == 1002

    def test_transform_work_items_response_empty(self):
        """Test empty work items response"""
        rest_response = {"count": 0, "value": []}

        items = WorkItemTransformer.transform_work_items_response(rest_response)

        assert len(items) == 0


class TestBuildTransformer:
    """Test BuildTransformer"""

    def test_transform_builds_response(self):
        """Test builds response transformation"""
        rest_response = {
            "count": 1,
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
                    "requestedFor": {"displayName": "John Doe"},
                }
            ],
        }

        builds = BuildTransformer.transform_builds_response(rest_response)

        assert len(builds) == 1
        assert builds[0]["id"] == 123
        assert builds[0]["build_number"] == "20260210.1"
        assert builds[0]["definition"]["name"] == "MyPipeline"
        assert builds[0]["status"] == "completed"
        assert builds[0]["result"] == "succeeded"
        assert builds[0]["requested_for"] == "John Doe"

    def test_transform_build_changes_response(self):
        """Test build changes response transformation"""
        rest_response = {
            "count": 2,
            "value": [
                {
                    "id": "abc123",
                    "message": "Fix bug",
                    "timestamp": "2026-02-10T09:00:00Z",
                    "author": {"displayName": "John Doe"},
                },
                {
                    "id": "def456",
                    "message": "Add feature",
                    "timestamp": "2026-02-10T08:00:00Z",
                    "author": {"displayName": "Jane Smith"},
                },
            ],
        }

        changes = BuildTransformer.transform_build_changes_response(rest_response)

        assert len(changes) == 2
        assert changes[0]["id"] == "abc123"
        assert changes[0]["message"] == "Fix bug"
        assert changes[0]["author"] == "John Doe"


class TestGitTransformer:
    """Test GitTransformer"""

    def test_transform_pull_requests_response(self):
        """Test pull requests response transformation"""
        rest_response = {
            "count": 1,
            "value": [
                {
                    "pullRequestId": 42,
                    "title": "Fix bug",
                    "creationDate": "2026-02-10T10:00:00Z",
                    "closedDate": "2026-02-10T11:00:00Z",
                    "createdBy": {"displayName": "John Doe"},
                    "repository": {"id": "repo-guid", "name": "MyRepo"},
                }
            ],
        }

        prs = GitTransformer.transform_pull_requests_response(rest_response)

        assert len(prs) == 1
        assert prs[0]["pull_request_id"] == 42
        assert prs[0]["title"] == "Fix bug"
        assert prs[0]["created_by"] == "John Doe"
        assert prs[0]["repository_id"] == "repo-guid"

    def test_transform_threads_response(self):
        """Test PR threads response transformation"""
        rest_response = {
            "count": 2,
            "value": [
                {"id": 1, "publishedDate": "2026-02-10T10:30:00Z", "comments": [{"content": "LGTM"}]},
                {"id": 2, "publishedDate": "2026-02-10T10:45:00Z", "comments": [{"content": "Fix typo"}]},
            ],
        }

        threads = GitTransformer.transform_threads_response(rest_response)

        assert len(threads) == 2
        assert threads[0]["id"] == 1
        assert threads[0]["published_date"] == "2026-02-10T10:30:00Z"
        assert len(threads[0]["comments"]) == 1

    def test_transform_commits_response(self):
        """Test commits response transformation"""
        rest_response = {
            "count": 2,
            "value": [
                {
                    "commitId": "abc123",
                    "comment": "Fix bug",
                    "author": {"name": "John Doe", "email": "john@example.com", "date": "2026-02-10T10:00:00Z"},
                },
                {
                    "commitId": "def456",
                    "comment": "Add feature",
                    "author": {"name": "Jane Smith", "email": "jane@example.com", "date": "2026-02-10T09:00:00Z"},
                },
            ],
        }

        commits = GitTransformer.transform_commits_response(rest_response)

        assert len(commits) == 2
        assert commits[0]["commit_id"] == "abc123"
        assert commits[0]["comment"] == "Fix bug"
        assert commits[0]["author_name"] == "John Doe"
        assert commits[0]["author_email"] == "john@example.com"


class TestTestTransformer:
    """Test TestTransformer"""

    def test_transform_test_runs_response(self):
        """Test test runs response transformation"""
        rest_response = {
            "count": 1,
            "value": [
                {
                    "id": 123,
                    "name": "My Test Run",
                    "startedDate": "2026-02-10T10:00:00Z",
                    "completedDate": "2026-02-10T10:15:00Z",
                    "totalTests": 100,
                    "passedTests": 95,
                    "failedTests": 5,
                }
            ],
        }

        runs = TestTransformer.transform_test_runs_response(rest_response)

        assert len(runs) == 1
        assert runs[0]["id"] == 123
        assert runs[0]["name"] == "My Test Run"
        assert runs[0]["total_tests"] == 100
        assert runs[0]["passed_tests"] == 95
        assert runs[0]["failed_tests"] == 5
