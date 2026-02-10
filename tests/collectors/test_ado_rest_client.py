"""
Unit Tests for Azure DevOps REST Client

Tests the AzureDevOpsRESTClient class that replaces the beta SDK.

Test Coverage:
- Authentication header building
- URL construction
- Work Item Tracking APIs
- Build APIs
- Git APIs
- Test APIs
- Error handling (401, 404, 429, 500, timeout)
- Retry logic
"""

import base64
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from execution.collectors.ado_rest_client import AzureDevOpsRESTClient, get_ado_rest_client


class TestClientInitialization:
    """Test client initialization and configuration"""

    def test_init_with_valid_credentials(self):
        """Test client initializes correctly with valid credentials"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/test-org", pat="test-pat-token-123")

        assert client.organization_url == "https://dev.azure.com/test-org"
        assert client.pat == "test-pat-token-123"
        assert "Authorization" in client.auth_header

    def test_init_strips_trailing_slash_from_url(self):
        """Test that trailing slash is removed from organization URL"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/test-org/", pat="test-pat")

        assert client.organization_url == "https://dev.azure.com/test-org"

    def test_init_with_empty_url_raises_error(self):
        """Test that empty organization URL raises ValueError"""
        with pytest.raises(ValueError, match="organization_url and pat are required"):
            AzureDevOpsRESTClient(organization_url="", pat="test-pat")

    def test_init_with_empty_pat_raises_error(self):
        """Test that empty PAT raises ValueError"""
        with pytest.raises(ValueError, match="organization_url and pat are required"):
            AzureDevOpsRESTClient(organization_url="https://dev.azure.com/org", pat="")


class TestAuthHeader:
    """Test authentication header building"""

    def test_build_auth_header_format(self):
        """Test that auth header is correctly formatted"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/org", pat="my-secret-pat")

        assert "Authorization" in client.auth_header
        assert client.auth_header["Authorization"].startswith("Basic ")
        assert "Content-Type" in client.auth_header
        assert client.auth_header["Content-Type"] == "application/json"

    def test_build_auth_header_base64_encoding(self):
        """Test that PAT is correctly base64 encoded"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/org", pat="test-pat-123")

        # Decode the base64 auth header
        encoded = client.auth_header["Authorization"].replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode()

        # Azure DevOps uses empty username and PAT as password
        assert decoded == ":test-pat-123"


class TestURLBuilding:
    """Test URL construction"""

    def test_build_url_with_project(self):
        """Test URL building for project-level API"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/myorg", pat="pat")

        url = client._build_url(project="MyProject", resource="wit/wiql", **{"api-version": "7.1"})

        assert url == "https://dev.azure.com/myorg/MyProject/_apis/wit/wiql?api-version=7.1"

    def test_build_url_without_project(self):
        """Test URL building for organization-level API"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/myorg", pat="pat")

        url = client._build_url(project=None, resource="wit/workitems", ids="1001,1002", **{"api-version": "7.1"})

        assert url == "https://dev.azure.com/myorg/_apis/wit/workitems?ids=1001%2C1002&api-version=7.1"

    def test_build_url_filters_none_params(self):
        """Test that None parameters are excluded from query string"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/myorg", pat="pat")

        url = client._build_url(project="MyProject", resource="build/builds", minTime=None, **{"api-version": "7.1"})

        assert url == "https://dev.azure.com/myorg/MyProject/_apis/build/builds?api-version=7.1"
        assert "minTime" not in url


class TestWorkItemTrackingAPIs:
    """Test Work Item Tracking API methods"""

    @pytest.mark.asyncio
    async def test_query_by_wiql_success(self):
        """Test successful WIQL query"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/org", pat="pat")

        # Mock HTTP response
        mock_response = Mock()
        mock_response.json = Mock(
            return_value={"queryType": "flat", "workItems": [{"id": 1001, "url": "..."}, {"id": 1002, "url": "..."}]}
        )
        mock_response.raise_for_status = Mock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with patch("execution.collectors.ado_rest_client.AsyncSecureHTTPClient", return_value=mock_http_client):
            result = await client.query_by_wiql(project="TestProject", wiql_query="SELECT [System.Id] FROM WorkItems")

        assert "workItems" in result
        assert len(result["workItems"]) == 2
        assert result["workItems"][0]["id"] == 1001

    @pytest.mark.asyncio
    async def test_get_work_items_success(self):
        """Test successful work items fetch"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/org", pat="pat")

        # Mock HTTP response
        mock_response = Mock()
        mock_response.json = Mock(
            return_value={
                "count": 2,
                "value": [
                    {"id": 1001, "fields": {"System.Title": "Bug 1", "System.State": "Active"}},
                    {"id": 1002, "fields": {"System.Title": "Bug 2", "System.State": "Closed"}},
                ],
            }
        )
        mock_response.raise_for_status = Mock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with patch("execution.collectors.ado_rest_client.AsyncSecureHTTPClient", return_value=mock_http_client):
            result = await client.get_work_items(ids=[1001, 1002], fields=["System.Id", "System.Title"])

        assert result["count"] == 2
        assert len(result["value"]) == 2
        assert result["value"][0]["id"] == 1001

    @pytest.mark.asyncio
    async def test_get_work_items_warns_on_large_batch(self):
        """Test warning is logged when requesting >200 items"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/org", pat="pat")

        # Mock HTTP response
        mock_response = Mock()
        mock_response.json = Mock(return_value={"count": 0, "value": []})
        mock_response.raise_for_status = Mock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with patch("execution.collectors.ado_rest_client.AsyncSecureHTTPClient", return_value=mock_http_client):
            with patch("execution.collectors.ado_rest_client.logger") as mock_logger:
                # Request 201 items (over limit)
                await client.get_work_items(ids=list(range(1, 202)))

                # Verify warning was logged
                mock_logger.warning.assert_called_once()
                assert "200" in mock_logger.warning.call_args[0][0]


class TestBuildAPIs:
    """Test Build API methods"""

    @pytest.mark.asyncio
    async def test_get_builds_success(self):
        """Test successful builds fetch"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/org", pat="pat")

        # Mock HTTP response
        mock_response = Mock()
        mock_response.json = Mock(
            return_value={
                "count": 1,
                "value": [
                    {
                        "id": 123,
                        "buildNumber": "20260210.1",
                        "status": "completed",
                        "result": "succeeded",
                        "startTime": "2026-02-10T10:00:00Z",
                        "finishTime": "2026-02-10T10:15:00Z",
                    }
                ],
            }
        )
        mock_response.raise_for_status = Mock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with patch("execution.collectors.ado_rest_client.AsyncSecureHTTPClient", return_value=mock_http_client):
            result = await client.get_builds(project="TestProject", min_time="2026-01-01T00:00:00Z")

        assert result["count"] == 1
        assert result["value"][0]["id"] == 123

    @pytest.mark.asyncio
    async def test_get_build_changes_success(self):
        """Test successful build changes fetch"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/org", pat="pat")

        # Mock HTTP response
        mock_response = Mock()
        mock_response.json = Mock(
            return_value={
                "count": 2,
                "value": [
                    {"id": "abc123", "message": "Fix bug", "timestamp": "2026-02-10T09:00:00Z"},
                    {"id": "def456", "message": "Add feature", "timestamp": "2026-02-10T08:00:00Z"},
                ],
            }
        )
        mock_response.raise_for_status = Mock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with patch("execution.collectors.ado_rest_client.AsyncSecureHTTPClient", return_value=mock_http_client):
            result = await client.get_build_changes(project="TestProject", build_id=123)

        assert result["count"] == 2
        assert result["value"][0]["id"] == "abc123"


class TestGitAPIs:
    """Test Git API methods"""

    @pytest.mark.asyncio
    async def test_get_repositories_success(self):
        """Test successful repositories fetch"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/org", pat="pat")

        # Mock HTTP response
        mock_response = Mock()
        mock_response.json = Mock(return_value={"count": 2, "value": [{"id": "repo1", "name": "MyRepo"}]})
        mock_response.raise_for_status = Mock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with patch("execution.collectors.ado_rest_client.AsyncSecureHTTPClient", return_value=mock_http_client):
            result = await client.get_repositories(project="TestProject")

        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_get_pull_requests_success(self):
        """Test successful pull requests fetch"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/org", pat="pat")

        # Mock HTTP response
        mock_response = Mock()
        mock_response.json = Mock(
            return_value={
                "count": 1,
                "value": [
                    {
                        "pullRequestId": 42,
                        "title": "Fix bug",
                        "creationDate": "2026-02-10T10:00:00Z",
                        "closedDate": "2026-02-10T11:00:00Z",
                    }
                ],
            }
        )
        mock_response.raise_for_status = Mock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with patch("execution.collectors.ado_rest_client.AsyncSecureHTTPClient", return_value=mock_http_client):
            result = await client.get_pull_requests(project="TestProject", repository_id="repo1", status="completed")

        assert result["count"] == 1
        assert result["value"][0]["pullRequestId"] == 42


class TestTestAPIs:
    """Test Test API methods"""

    @pytest.mark.asyncio
    async def test_get_test_runs_success(self):
        """Test successful test runs fetch"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/org", pat="pat")

        # Mock HTTP response
        mock_response = Mock()
        mock_response.json = Mock(
            return_value={
                "count": 1,
                "value": [
                    {
                        "id": 123,
                        "name": "My Test Run",
                        "startedDate": "2026-02-10T10:00:00Z",
                        "completedDate": "2026-02-10T10:15:00Z",
                    }
                ],
            }
        )
        mock_response.raise_for_status = Mock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with patch("execution.collectors.ado_rest_client.AsyncSecureHTTPClient", return_value=mock_http_client):
            result = await client.get_test_runs(project="TestProject", top=50)

        assert result["count"] == 1
        assert result["value"][0]["id"] == 123


class TestErrorHandling:
    """Test error handling and retry logic"""

    @pytest.mark.asyncio
    async def test_authentication_error_fails_fast(self):
        """Test that 401 authentication errors fail immediately without retry"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/org", pat="invalid-pat")

        # Mock 401 response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError("401 Unauthorized", request=Mock(), response=mock_response)
        )

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with patch("execution.collectors.ado_rest_client.AsyncSecureHTTPClient", return_value=mock_http_client):
            with pytest.raises(httpx.HTTPStatusError):
                await client.query_by_wiql(project="TestProject", wiql_query="SELECT [System.Id] FROM WorkItems")

            # Verify only 1 attempt (no retries for auth errors)
            assert mock_http_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_rate_limit_retries_with_backoff(self):
        """Test that 429 rate limit errors trigger retry with backoff"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/org", pat="pat")

        # Mock 429 response with Retry-After header
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "1"}  # 1 second
        mock_response_429.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError("429 Too Many Requests", request=Mock(), response=mock_response_429)
        )

        # Mock successful response on retry
        mock_response_success = Mock()
        mock_response_success.json = Mock(return_value={"workItems": []})
        mock_response_success.raise_for_status = Mock()

        mock_http_client = AsyncMock()
        # First call: 429, second call: success
        mock_http_client.post = AsyncMock(side_effect=[mock_response_429, mock_response_success])
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with patch("execution.collectors.ado_rest_client.AsyncSecureHTTPClient", return_value=mock_http_client):
            with patch("asyncio.sleep") as mock_sleep:  # Mock sleep to avoid delays in tests
                result = await client.query_by_wiql(
                    project="TestProject", wiql_query="SELECT [System.Id] FROM WorkItems"
                )

                # Verify retry occurred
                assert mock_http_client.post.call_count == 2
                # Verify sleep was called with Retry-After value
                mock_sleep.assert_called_with(1)

    @pytest.mark.asyncio
    async def test_server_error_retries_with_exponential_backoff(self):
        """Test that 500 server errors trigger retry with exponential backoff"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/org", pat="pat")

        # Mock 500 response
        mock_response_500 = Mock()
        mock_response_500.status_code = 500
        mock_response_500.text = "Internal Server Error"
        mock_response_500.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError("500 Internal Server Error", request=Mock(), response=mock_response_500)
        )

        # Mock successful response on retry
        mock_response_success = Mock()
        mock_response_success.json = Mock(return_value={"workItems": []})
        mock_response_success.raise_for_status = Mock()

        mock_http_client = AsyncMock()
        # First call: 500, second call: success
        mock_http_client.post = AsyncMock(side_effect=[mock_response_500, mock_response_success])
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with patch("execution.collectors.ado_rest_client.AsyncSecureHTTPClient", return_value=mock_http_client):
            with patch("asyncio.sleep") as mock_sleep:
                result = await client.query_by_wiql(
                    project="TestProject", wiql_query="SELECT [System.Id] FROM WorkItems"
                )

                # Verify retry occurred
                assert mock_http_client.post.call_count == 2
                # Verify exponential backoff (2^0 = 1 second for first retry)
                mock_sleep.assert_called_with(1)

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises_error(self):
        """Test that all retries exhausted raises final error"""
        client = AzureDevOpsRESTClient(organization_url="https://dev.azure.com/org", pat="pat")

        # Mock 500 response that never succeeds
        mock_response_500 = Mock()
        mock_response_500.status_code = 500
        mock_response_500.text = "Internal Server Error"
        mock_response_500.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError("500 Internal Server Error", request=Mock(), response=mock_response_500)
        )

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response_500)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with patch("execution.collectors.ado_rest_client.AsyncSecureHTTPClient", return_value=mock_http_client):
            with patch("asyncio.sleep"):  # Mock sleep to avoid delays
                with pytest.raises(httpx.HTTPStatusError):
                    await client.query_by_wiql(project="TestProject", wiql_query="SELECT [System.Id] FROM WorkItems")

                # Verify max retries (3 attempts total)
                assert mock_http_client.post.call_count == 3


class TestFactoryFunction:
    """Test get_ado_rest_client() factory function"""

    @patch("execution.collectors.ado_rest_client.get_config")
    def test_get_ado_rest_client_loads_from_config(self, mock_get_config):
        """Test that factory function loads credentials from config"""
        # Mock config
        mock_config = Mock()
        mock_ado_config = Mock()
        mock_ado_config.organization_url = "https://dev.azure.com/my-org"
        mock_ado_config.pat = "my-secret-pat"
        mock_config.get_ado_config = Mock(return_value=mock_ado_config)
        mock_get_config.return_value = mock_config

        # Call factory function
        client = get_ado_rest_client()

        # Verify client was created with config values
        assert client.organization_url == "https://dev.azure.com/my-org"
        assert client.pat == "my-secret-pat"
        mock_config.get_ado_config.assert_called_once()
