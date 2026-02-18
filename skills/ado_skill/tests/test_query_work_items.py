"""
Tests for query_work_items tool

Ensures WIQL injection prevention, authentication, and API error handling.
"""

import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from skills.ado_skill.tools.query_work_items import query_work_items, SecurityError


@pytest.mark.asyncio
async def test_query_work_items_validates_wiql():
    """Test that WIQL injection attempts are blocked"""

    # Set required env vars (mock credentials)
    os.environ["ADO_ORGANIZATION_URL"] = "https://dev.azure.com/contoso"
    os.environ["ADO_PAT"] = "test-pat"

    # Attempt SQL injection-style attack
    malicious_wiql = "[System.Id] = 1; DROP TABLE WorkItems--"

    with pytest.raises(SecurityError, match="WIQL validation failed"):
        await query_work_items(
            organization="contoso",
            project="TestProject",
            wiql=malicious_wiql
        )


@pytest.mark.asyncio
async def test_query_work_items_requires_credentials():
    """Test that missing credentials raises clear error"""

    # Clear env vars
    if "ADO_ORGANIZATION_URL" in os.environ:
        del os.environ["ADO_ORGANIZATION_URL"]
    if "ADO_PAT" in os.environ:
        del os.environ["ADO_PAT"]

    with pytest.raises(ValueError, match="Missing Azure DevOps credentials"):
        await query_work_items(
            organization="contoso",
            project="TestProject",
            wiql="SELECT [System.Id] FROM WorkItems"
        )


@pytest.mark.asyncio
async def test_query_work_items_validates_organization_match():
    """Test that organization must match credentials"""

    # Set credentials for 'contoso' org
    os.environ["ADO_ORGANIZATION_URL"] = "https://dev.azure.com/contoso"
    os.environ["ADO_PAT"] = "test-pat"

    # Try to query different org (potential credential leak)
    with pytest.raises(ValueError, match="Organization.*does not match"):
        await query_work_items(
            organization="different-org",  # Wrong org!
            project="TestProject",
            wiql="SELECT [System.Id] FROM WorkItems"
        )


@pytest.mark.asyncio
async def test_query_work_items_success():
    """Test successful WIQL query"""

    # Setup
    os.environ["ADO_ORGANIZATION_URL"] = "https://dev.azure.com/contoso"
    os.environ["ADO_PAT"] = "test-pat"

    # Mock the REST client
    mock_result = {
        "queryType": "flat",
        "workItems": [
            {"id": 1001, "url": "https://..."},
            {"id": 1002, "url": "https://..."}
        ]
    }

    with patch("skills.ado_skill.tools.query_work_items.AzureDevOpsRESTClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.query_by_wiql = AsyncMock(return_value=mock_result)

        # Execute
        result = await query_work_items(
            organization="contoso",
            project="TestProject",
            wiql="SELECT [System.Id] FROM WorkItems WHERE [System.State] = 'Active'"
        )

        # Verify
        assert result == mock_result
        assert len(result["workItems"]) == 2
        mock_client.query_by_wiql.assert_called_once_with(
            project="TestProject",
            wiql_query="SELECT [System.Id] FROM WorkItems WHERE [System.State] = 'Active'"
        )


@pytest.mark.asyncio
async def test_query_work_items_handles_api_error():
    """Test that API errors are wrapped with context"""

    # Setup
    os.environ["ADO_ORGANIZATION_URL"] = "https://dev.azure.com/contoso"
    os.environ["ADO_PAT"] = "test-pat"

    # Mock API failure
    with patch("skills.ado_skill.tools.query_work_items.AzureDevOpsRESTClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.query_by_wiql = AsyncMock(side_effect=Exception("API Error: 429 Too Many Requests"))

        # Execute and verify error wrapping
        with pytest.raises(RuntimeError, match="ADO query failed for project 'TestProject'"):
            await query_work_items(
                organization="contoso",
                project="TestProject",
                wiql="SELECT [System.Id] FROM WorkItems"
            )


@pytest.mark.asyncio
async def test_query_work_items_empty_result():
    """Test handling of empty query results"""

    # Setup
    os.environ["ADO_ORGANIZATION_URL"] = "https://dev.azure.com/contoso"
    os.environ["ADO_PAT"] = "test-pat"

    # Mock empty result
    mock_result = {
        "queryType": "flat",
        "workItems": []
    }

    with patch("skills.ado_skill.tools.query_work_items.AzureDevOpsRESTClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.query_by_wiql = AsyncMock(return_value=mock_result)

        # Execute
        result = await query_work_items(
            organization="contoso",
            project="TestProject",
            wiql="SELECT [System.Id] FROM WorkItems WHERE 1 = 0"  # Always false
        )

        # Verify
        assert result["workItems"] == []
