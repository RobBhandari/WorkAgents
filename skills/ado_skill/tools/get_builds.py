"""
Get Builds Tool

Fetches build history for Azure DevOps projects.
"""

import os
from typing import Any

from execution.collectors.ado_rest_client import AzureDevOpsRESTClient


async def get_builds(
    organization: str,
    project: str,
    min_time: str | None = None,
    max_per_definition: int | None = None
) -> dict[str, Any]:
    """
    Get build history for a project.

    Args:
        organization: ADO organization name
        project: Project name
        min_time: Optional minimum finish time filter (ISO 8601 format, e.g., '2026-01-01T00:00:00Z')
        max_per_definition: Optional limit per pipeline definition

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
                },
                ...
            ]
        }

    Raises:
        ValueError: If credentials not set
        httpx.HTTPStatusError: If ADO API returns error

    Example:
        >>> result = await get_builds(
        ...     organization="contoso",
        ...     project="MyProject",
        ...     min_time="2026-01-01T00:00:00Z"
        ... )
        >>> succeeded = [b for b in result["value"] if b["result"] == "succeeded"]
    """
    organization_url = os.getenv("ADO_ORGANIZATION_URL")
    pat = os.getenv("ADO_PAT")

    if not organization_url or not pat:
        raise ValueError("Missing ADO credentials (ADO_ORGANIZATION_URL, ADO_PAT)")

    if organization not in organization_url:
        raise ValueError(f"Organization mismatch: '{organization}' not in '{organization_url}'")

    client = AzureDevOpsRESTClient(organization_url=organization_url, pat=pat)

    try:
        result = await client.get_builds(
            project=project,
            min_time=min_time,
            max_per_definition=max_per_definition
        )
        return result
    except Exception as e:
        raise RuntimeError(f"Failed to fetch builds for project '{project}': {e}") from e
