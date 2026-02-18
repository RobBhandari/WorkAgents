"""
Tests for get_work_items_by_ids tool

Ensures batching limits, field filtering, and error handling.
"""

import os
import pytest
from unittest.mock import AsyncMock, patch

from skills.ado_skill.tools.get_work_items_by_ids import get_work_items_by_ids


@pytest.mark.asyncio
async def test_get_work_items_rejects_large_batches():
    """Test that >200 IDs are rejected (API limit)"""

    # Setup
    os.environ["ADO_ORGANIZATION_URL"] = "https://dev.azure.com/contoso"
    os.environ["ADO_PAT"] = "test-pat"

    # Try to fetch 201 items (over limit)
    large_batch = list(range(1, 202))  # 201 IDs

    with pytest.raises(ValueError, match="API limit is 200 per call"):
        await get_work_items_by_ids(
            organization="contoso",
            ids=large_batch
        )


@pytest.mark.asyncio
async def test_get_work_items_handles_empty_list():
    """Test that empty ID list returns empty result"""

    # Setup
    os.environ["ADO_ORGANIZATION_URL"] = "https://dev.azure.com/contoso"
    os.environ["ADO_PAT"] = "test-pat"

    # Execute
    result = await get_work_items_by_ids(
        organization="contoso",
        ids=[]
    )

    # Verify
    assert result == {"count": 0, "value": []}


@pytest.mark.asyncio
async def test_get_work_items_with_field_filtering():
    """Test that field filtering is passed to API"""

    # Setup
    os.environ["ADO_ORGANIZATION_URL"] = "https://dev.azure.com/contoso"
    os.environ["ADO_PAT"] = "test-pat"

    mock_result = {
        "count": 2,
        "value": [
            {"id": 1001, "fields": {"System.Title": "Bug 1"}},
            {"id": 1002, "fields": {"System.Title": "Bug 2"}}
        ]
    }

    with patch("skills.ado_skill.tools.get_work_items_by_ids.AzureDevOpsRESTClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.get_work_items = AsyncMock(return_value=mock_result)

        # Execute with specific fields
        result = await get_work_items_by_ids(
            organization="contoso",
            ids=[1001, 1002],
            fields=["System.Id", "System.Title"]
        )

        # Verify
        assert result == mock_result
        mock_client.get_work_items.assert_called_once_with(
            ids=[1001, 1002],
            fields=["System.Id", "System.Title"]
        )


@pytest.mark.asyncio
async def test_get_work_items_success():
    """Test successful work item fetch"""

    # Setup
    os.environ["ADO_ORGANIZATION_URL"] = "https://dev.azure.com/contoso"
    os.environ["ADO_PAT"] = "test-pat"

    mock_result = {
        "count": 3,
        "value": [
            {
                "id": 1001,
                "fields": {
                    "System.Title": "Bug in login",
                    "System.State": "Active",
                    "System.AssignedTo": {"displayName": "John Doe"}
                }
            },
            {
                "id": 1002,
                "fields": {
                    "System.Title": "Feature request",
                    "System.State": "New"
                }
            },
            {
                "id": 1003,
                "fields": {
                    "System.Title": "Fix typo",
                    "System.State": "Closed"
                }
            }
        ]
    }

    with patch("skills.ado_skill.tools.get_work_items_by_ids.AzureDevOpsRESTClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.get_work_items = AsyncMock(return_value=mock_result)

        # Execute
        result = await get_work_items_by_ids(
            organization="contoso",
            ids=[1001, 1002, 1003]
        )

        # Verify
        assert result["count"] == 3
        assert len(result["value"]) == 3
        assert result["value"][0]["fields"]["System.Title"] == "Bug in login"
