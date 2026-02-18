"""
Get Work Items By IDs Tool

Fetches full work item details by IDs.
Supports batching for large ID lists.
"""

import os
from typing import Any

from execution.collectors.ado_rest_client import AzureDevOpsRESTClient


async def get_work_items_by_ids(
    organization: str,
    ids: list[int],
    fields: list[str] | None = None
) -> dict[str, Any]:
    """
    Fetch full work item details by IDs.

    This tool provides efficient work item fetching with:
    - Batching support (up to 200 IDs per call)
    - Field filtering (fetch only needed fields)
    - Connection pooling (HTTP/2)
    - Automatic retry on transient errors

    Args:
        organization: ADO organization name
        ids: List of work item IDs (max 200 per call)
        fields: Optional list of fields to retrieve (e.g., ["System.Title", "System.State"])
                If omitted, returns all fields (slower but complete)

    Returns:
        Work items response:
        {
            "count": 2,
            "value": [
                {
                    "id": 1001,
                    "fields": {
                        "System.Title": "Bug title",
                        "System.State": "Active",
                        "System.AssignedTo": {"displayName": "John Doe"}
                    }
                },
                ...
            ]
        }

    Raises:
        ValueError: If more than 200 IDs requested (API limit)
        ValueError: If organization_url or PAT environment variables not set
        httpx.HTTPStatusError: If ADO API returns error

    Example:
        >>> result = await get_work_items_by_ids(
        ...     organization="contoso",
        ...     ids=[1001, 1002, 1003],
        ...     fields=["System.Id", "System.Title", "System.State"]
        ... )
        >>> for item in result["value"]:
        ...     print(f"{item['id']}: {item['fields']['System.Title']}")

    Performance Notes:
        - Requesting all fields is slower (more data transfer)
        - Specify only needed fields for better performance
        - For >200 IDs, call this tool multiple times with batched IDs
    """
    # Validate batch size
    if len(ids) > 200:
        raise ValueError(
            f"Requested {len(ids)} items, but API limit is 200 per call. "
            "Call this tool multiple times with batched IDs."
        )

    if len(ids) == 0:
        return {"count": 0, "value": []}

    # Get authenticated REST client
    organization_url = os.getenv("ADO_ORGANIZATION_URL")
    pat = os.getenv("ADO_PAT")

    if not organization_url or not pat:
        raise ValueError(
            "Missing Azure DevOps credentials. Set ADO_ORGANIZATION_URL and ADO_PAT environment variables."
        )

    if organization not in organization_url:
        raise ValueError(
            f"Organization '{organization}' does not match ADO_ORGANIZATION_URL '{organization_url}'."
        )

    # Execute API call
    client = AzureDevOpsRESTClient(organization_url=organization_url, pat=pat)

    try:
        result = await client.get_work_items(ids=ids, fields=fields)
        return result
    except Exception as e:
        raise RuntimeError(
            f"Failed to fetch work items {ids[:5]}{'...' if len(ids) > 5 else ''}: {e}"
        ) from e
