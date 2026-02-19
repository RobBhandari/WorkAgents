"""
Azure DevOps REST API Client

Provides direct REST API access to Azure DevOps, replacing the beta SDK.
Uses AsyncSecureHTTPClient for HTTP/2, connection pooling, and SSL enforcement.

This module replaces azure-devops==7.1.0b4 SDK with maintained REST API v7.1.

Usage:
    from execution.collectors.ado_rest_client import get_ado_rest_client

    # Get authenticated client
    client = get_ado_rest_client()

    # Query work items
    result = await client.query_by_wiql(project="MyProject", wiql_query="SELECT [System.Id] FROM WorkItems")

    # Get work items by IDs
    items = await client.get_work_items(ids=[1001, 1002], fields=["System.Title", "System.State"])

    # Get builds
    builds = await client.get_builds(project="MyProject", min_time="2026-01-01T00:00:00Z")

API Documentation:
    https://learn.microsoft.com/en-us/rest/api/azure/devops/?view=azure-devops-rest-7.1
"""

import asyncio
import base64
import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from execution.async_http_client import AsyncSecureHTTPClient
from execution.core import get_logger

# Import collector metrics tracker for performance monitoring
from execution.core.collector_metrics import get_current_tracker
from execution.secure_config import get_config
from execution.utils.error_handling import log_and_continue

logger = get_logger(__name__)


class AzureDevOpsRESTClient:
    """
    Azure DevOps REST API v7.1 client using direct HTTP calls.

    Replaces azure-devops SDK with AsyncSecureHTTPClient for better security and maintainability.

    Features:
    - Async HTTP/2 requests with connection pooling
    - Base64-encoded PAT authentication
    - Retry logic for rate limiting and server errors
    - Comprehensive error handling
    """

    API_VERSION = "7.1"

    def __init__(self, organization_url: str, pat: str):
        """
        Initialize Azure DevOps REST client.

        Args:
            organization_url: Azure DevOps organization URL (e.g., https://dev.azure.com/myorg)
            pat: Personal Access Token for authentication

        Raises:
            ValueError: If organization_url or pat is empty
        """
        if not organization_url or not pat:
            raise ValueError("organization_url and pat are required")

        self.organization_url = organization_url.rstrip("/")
        self.pat = pat
        self.auth_header = self._build_auth_header(pat)

    def _build_auth_header(self, pat: str) -> dict[str, str]:
        """
        Build Basic Authentication header from PAT.

        Azure DevOps uses Basic Auth with empty username and PAT as password.

        Args:
            pat: Personal Access Token

        Returns:
            Dictionary with Authorization header

        Example:
            {"Authorization": "Basic OjxiYXNlNjQtZW5jb2RlZC1wYXQ+"}
        """
        credentials = f":{pat}"  # Empty username, PAT as password
        b64_credentials = base64.b64encode(credentials.encode()).decode()  # nosec B108
        return {
            "Authorization": f"Basic {b64_credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _build_url(self, project: str | None, resource: str, **params: Any) -> str:
        """
        Build Azure DevOps REST API URL with query parameters.

        Args:
            project: Project name (None for organization-level APIs)
            resource: Resource path (e.g., "wit/wiql", "build/builds")
            **params: Query parameters (None values are filtered out)

        Returns:
            Complete API URL with query string

        Example:
            _build_url("MyProject", "wit/wiql", api_version="7.1")
            -> "https://dev.azure.com/org/MyProject/_apis/wit/wiql?api-version=7.1"
        """
        if project:
            url = f"{self.organization_url}/{project}/_apis/{resource}"
        else:
            url = f"{self.organization_url}/_apis/{resource}"

        # Filter out None values and build query string
        filtered_params = {k: v for k, v in params.items() if v is not None}
        if filtered_params:
            query_string = urlencode(filtered_params)
            url = f"{url}?{query_string}"

        return url

    async def _handle_api_call(self, method: str, url: str, max_retries: int = 3, **kwargs: Any) -> dict[str, Any]:
        """
        Execute API call with retry logic and error handling.

        Handles:
        - Rate limiting (429) with exponential backoff
        - Server errors (500, 502, 503) with retry
        - Network errors with retry
        - Authentication errors (401, 403) fail fast

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full API URL
            max_retries: Maximum retry attempts for transient errors
            **kwargs: Additional arguments for HTTP client

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: For non-retryable HTTP errors
            httpx.RequestError: For network errors after retries exhausted
        """
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                # Record API call for performance tracking
                tracker = get_current_tracker()
                if tracker:
                    tracker.record_api_call()

                async with AsyncSecureHTTPClient() as client:
                    # Merge auth headers with any provided headers
                    headers = {**self.auth_header, **kwargs.pop("headers", {})}

                    # Make HTTP request
                    if method.upper() == "GET":
                        response = await client.get(url, headers=headers, **kwargs)
                    elif method.upper() == "POST":
                        response = await client.post(url, headers=headers, **kwargs)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                    response.raise_for_status()
                    return response.json()  # type: ignore[no-any-return]

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code

                # Authentication/Authorization errors - fail fast
                if status_code in [401, 403]:
                    logger.error(f"Authentication failed (HTTP {status_code}): {e.response.text}")
                    raise

                # Rate limiting - retry with backoff
                if status_code == 429:
                    # Record rate limit hit for monitoring
                    if tracker:
                        tracker.record_rate_limit_hit()

                    retry_after = int(e.response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited, retrying after {retry_after}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_after)
                    last_error = e
                    continue

                # Server errors - retry with exponential backoff
                if status_code in [500, 502, 503]:
                    # Record retry for monitoring
                    if tracker:
                        tracker.record_retry()

                    backoff = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        f"Server error (HTTP {status_code}), retrying in {backoff}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(backoff)
                    last_error = e
                    continue

                # Other HTTP errors - fail fast
                logger.error(f"HTTP error {status_code}: {e.response.text}")
                raise

            except (httpx.TimeoutException, httpx.RequestError) as e:
                backoff = 2**attempt
                logger.warning(f"Network error, retrying in {backoff}s (attempt {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(backoff)
                last_error = e
                continue

        # All retries exhausted
        if last_error:
            log_and_continue(logger, last_error, {"url": url, "max_retries": max_retries}, "ADO API call")
            raise last_error

        raise RuntimeError("Unexpected: No error but retries exhausted")

    # ==============================
    # Work Item Tracking APIs
    # ==============================

    async def query_by_wiql(self, project: str, wiql_query: str) -> dict[str, Any]:
        """
        Execute WIQL (Work Item Query Language) query.

        REST Endpoint: POST {org}/{project}/_apis/wit/wiql?api-version=7.1

        Args:
            project: Project name
            wiql_query: WIQL query string (e.g., "SELECT [System.Id] FROM WorkItems WHERE [System.WorkItemType] = 'Bug'")

        Returns:
            Query result with workItems array:
            {
                "queryType": "flat",
                "queryResultType": "workItem",
                "workItems": [{"id": 1001, "url": "..."}]
            }

        Example:
            result = await client.query_by_wiql(
                project="MyProject",
                wiql_query="SELECT [System.Id] FROM WorkItems WHERE [System.State] = 'Active'"
            )
            work_item_ids = [item["id"] for item in result["workItems"]]
        """
        url = self._build_url(project, "wit/wiql", **{"api-version": self.API_VERSION})
        payload = {"query": wiql_query}
        return await self._handle_api_call("POST", url, json=payload)

    async def get_work_items(
        self, ids: list[int], fields: list[str] | None = None, as_of: str | None = None
    ) -> dict[str, Any]:
        """
        Get work items by IDs.

        REST Endpoint: GET {org}/_apis/wit/workitems?ids={ids}&fields={fields}&api-version=7.1

        Note: Azure DevOps supports up to 200 IDs per request. For larger batches, use batch utilities.

        Args:
            ids: List of work item IDs (max 200 per call)
            fields: Optional list of fields to retrieve (e.g., ["System.Title", "System.State"])
            as_of: Optional datetime for historical data (ISO 8601 format)

        Returns:
            Work items response:
            {
                "count": 2,
                "value": [
                    {"id": 1001, "fields": {"System.Title": "Bug title", "System.State": "Active"}},
                    {"id": 1002, "fields": {...}}
                ]
            }

        Example:
            items = await client.get_work_items(
                ids=[1001, 1002],
                fields=["System.Id", "System.Title", "System.State"]
            )
        """
        if len(ids) > 200:
            logger.warning(f"Requested {len(ids)} items, but API limit is 200. Use batch utilities for large requests.")

        ids_str = ",".join(str(id) for id in ids)
        fields_str = ",".join(fields) if fields else None

        url = self._build_url(
            None, "wit/workitems", ids=ids_str, fields=fields_str, asOf=as_of, **{"api-version": self.API_VERSION}
        )
        return await self._handle_api_call("GET", url)

    # ==============================
    # Build APIs
    # ==============================

    async def get_builds(
        self, project: str, min_time: str | None = None, max_per_definition: int | None = None
    ) -> dict[str, Any]:
        """
        Get builds for project.

        REST Endpoint: GET {org}/{project}/_apis/build/builds?minTime={min_time}&api-version=7.1

        Args:
            project: Project name
            min_time: Optional minimum finish time filter (ISO 8601 format)
            max_per_definition: Optional limit per definition

        Returns:
            Builds response:
            {
                "count": 10,
                "value": [
                    {
                        "id": 123,
                        "buildNumber": "20260210.1",
                        "status": "completed",
                        "result": "succeeded",
                        "startTime": "2026-02-10T10:00:00Z",
                        "finishTime": "2026-02-10T10:15:00Z",
                        "definition": {"id": 5, "name": "MyPipeline"}
                    }
                ]
            }

        Example:
            builds = await client.get_builds(
                project="MyProject",
                min_time="2026-01-01T00:00:00Z"
            )
        """
        url = self._build_url(
            project,
            "build/builds",
            minTime=min_time,
            maxPerDefinition=max_per_definition,
            **{"api-version": self.API_VERSION},
        )
        return await self._handle_api_call("GET", url)

    async def get_build_changes(self, project: str, build_id: int) -> dict[str, Any]:
        """
        Get changes (commits) for a build.

        REST Endpoint: GET {org}/{project}/_apis/build/builds/{buildId}/changes?api-version=7.1

        Args:
            project: Project name
            build_id: Build ID

        Returns:
            Changes response:
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

        Example:
            changes = await client.get_build_changes(project="MyProject", build_id=123)
        """
        url = self._build_url(project, f"build/builds/{build_id}/changes", **{"api-version": self.API_VERSION})
        return await self._handle_api_call("GET", url)

    # ==============================
    # Git APIs
    # ==============================

    async def get_repositories(self, project: str) -> dict[str, Any]:
        """
        Get repositories for project.

        REST Endpoint: GET {org}/{project}/_apis/git/repositories?api-version=7.1

        Args:
            project: Project name

        Returns:
            Repositories response:
            {
                "count": 5,
                "value": [{"id": "repo-guid", "name": "MyRepo", "url": "..."}]
            }
        """
        url = self._build_url(project, "git/repositories", **{"api-version": self.API_VERSION})
        return await self._handle_api_call("GET", url)

    async def get_pull_requests(
        self, project: str, repository_id: str, status: str | None = None, creator_id: str | None = None
    ) -> dict[str, Any]:
        """
        Get pull requests for repository.

        REST Endpoint: GET {org}/{project}/_apis/git/repositories/{repoId}/pullrequests?api-version=7.1

        Args:
            project: Project name
            repository_id: Repository ID or name
            status: Optional PR status filter ("active", "completed", "abandoned", "all")
            creator_id: Optional creator ID filter

        Returns:
            Pull requests response:
            {
                "count": 10,
                "value": [
                    {
                        "pullRequestId": 42,
                        "title": "Fix bug",
                        "creationDate": "2026-02-10T10:00:00Z",
                        "closedDate": "2026-02-10T11:00:00Z",
                        "createdBy": {"displayName": "John Doe"},
                        "repository": {"id": "repo-guid"}
                    }
                ]
            }
        """
        params = {"api-version": self.API_VERSION}
        if status:
            params["searchCriteria.status"] = status
        if creator_id:
            params["searchCriteria.creatorId"] = creator_id

        url = self._build_url(project, f"git/repositories/{repository_id}/pullrequests", **params)
        return await self._handle_api_call("GET", url)

    async def get_pull_request_threads(self, project: str, repository_id: str, pull_request_id: int) -> dict[str, Any]:
        """
        Get PR threads (comments).

        REST Endpoint: GET {org}/{project}/_apis/git/repositories/{repoId}/pullrequests/{prId}/threads?api-version=7.1

        Args:
            project: Project name
            repository_id: Repository ID or name
            pull_request_id: Pull request ID

        Returns:
            Threads response:
            {
                "count": 5,
                "value": [
                    {
                        "id": 1,
                        "publishedDate": "2026-02-10T10:30:00Z",
                        "comments": [{"content": "LGTM"}]
                    }
                ]
            }
        """
        url = self._build_url(
            project,
            f"git/repositories/{repository_id}/pullrequests/{pull_request_id}/threads",
            **{"api-version": self.API_VERSION},
        )
        return await self._handle_api_call("GET", url)

    async def get_pull_request_iterations(
        self, project: str, repository_id: str, pull_request_id: int
    ) -> dict[str, Any]:
        """
        Get PR iterations (pushes).

        REST Endpoint: GET {org}/{project}/_apis/git/repositories/{repoId}/pullrequests/{prId}/iterations?api-version=7.1

        Args:
            project: Project name
            repository_id: Repository ID or name
            pull_request_id: Pull request ID

        Returns:
            Iterations response:
            {
                "count": 3,
                "value": [
                    {"id": 1, "createdDate": "2026-02-10T10:00:00Z"}
                ]
            }
        """
        url = self._build_url(
            project,
            f"git/repositories/{repository_id}/pullrequests/{pull_request_id}/iterations",
            **{"api-version": self.API_VERSION},
        )
        return await self._handle_api_call("GET", url)

    async def get_pull_request_commits(self, project: str, repository_id: str, pull_request_id: int) -> dict[str, Any]:
        """
        Get PR commits.

        REST Endpoint: GET {org}/{project}/_apis/git/repositories/{repoId}/pullrequests/{prId}/commits?api-version=7.1

        Args:
            project: Project name
            repository_id: Repository ID or name
            pull_request_id: Pull request ID

        Returns:
            Commits response:
            {
                "count": 5,
                "value": [
                    {"commitId": "abc123", "comment": "Fix bug"}
                ]
            }
        """
        url = self._build_url(
            project,
            f"git/repositories/{repository_id}/pullrequests/{pull_request_id}/commits",
            **{"api-version": self.API_VERSION},
        )
        return await self._handle_api_call("GET", url)

    async def get_commits(
        self,
        project: str,
        repository_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
        top: int = 1000,
    ) -> dict[str, Any]:
        """
        Get commits for repository.

        REST Endpoint: GET {org}/{project}/_apis/git/repositories/{repoId}/commits?api-version=7.1

        Args:
            project: Project name
            repository_id: Repository ID or name
            from_date: Optional start date filter (ISO 8601)
            to_date: Optional end date filter (ISO 8601)
            top: Maximum commits to return (default 1000; ADO default is 100)

        Returns:
            Commits response:
            {
                "count": 100,
                "value": [
                    {
                        "commitId": "abc123",
                        "comment": "Fix bug",
                        "author": {"name": "John Doe", "date": "2026-02-10T10:00:00Z"}
                    }
                ]
            }
        """
        params: dict[str, Any] = {"api-version": self.API_VERSION, "$top": top}
        if from_date:
            params["searchCriteria.fromDate"] = from_date
        if to_date:
            params["searchCriteria.toDate"] = to_date

        url = self._build_url(project, f"git/repositories/{repository_id}/commits", **params)
        return await self._handle_api_call("GET", url)

    async def get_changes(self, project: str, repository_id: str, commit_id: str) -> dict[str, Any]:
        """
        Get changes (files) for a commit.

        REST Endpoint: GET {org}/{project}/_apis/git/repositories/{repoId}/commits/{commitId}/changes?api-version=7.1

        Args:
            project: Project name
            repository_id: Repository ID or name
            commit_id: Commit ID

        Returns:
            Changes response:
            {
                "changes": [
                    {"item": {"path": "/src/file.py"}, "changeType": "edit"}
                ]
            }
        """
        url = self._build_url(
            project,
            f"git/repositories/{repository_id}/commits/{commit_id}/changes",
            **{"api-version": self.API_VERSION},
        )
        return await self._handle_api_call("GET", url)

    # ==============================
    # Test APIs
    # ==============================

    async def get_test_runs(self, project: str, top: int = 50) -> dict[str, Any]:
        """
        Get test runs for project.

        REST Endpoint: GET {org}/{project}/_apis/test/runs?$top={top}&api-version=7.1

        Args:
            project: Project name
            top: Maximum number of runs to retrieve (default: 50)

        Returns:
            Test runs response:
            {
                "count": 50,
                "value": [
                    {
                        "id": 123,
                        "name": "My Test Run",
                        "startedDate": "2026-02-10T10:00:00Z",
                        "completedDate": "2026-02-10T10:15:00Z",
                        "totalTests": 100,
                        "passedTests": 95
                    }
                ]
            }
        """
        url = self._build_url(project, "test/runs", **{"$top": top, "api-version": self.API_VERSION})
        return await self._handle_api_call("GET", url)


def get_ado_rest_client() -> AzureDevOpsRESTClient:
    """
    Get Azure DevOps REST client with credentials from config.

    Loads credentials from environment variables via secure_config.

    Returns:
        AzureDevOpsRESTClient: Authenticated REST client

    Raises:
        ValueError: If ADO_ORGANIZATION_URL or ADO_PAT are not set

    Example:
        client = get_ado_rest_client()
        result = await client.query_by_wiql(project="MyProject", wiql_query="SELECT [System.Id] FROM WorkItems")
    """
    ado_config = get_config().get_ado_config()
    return AzureDevOpsRESTClient(organization_url=ado_config.organization_url, pat=ado_config.pat)
