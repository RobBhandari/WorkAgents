"""
Get Test Runs Tool

Fetches test run history for Azure DevOps projects.
"""

import os
from typing import Any

from execution.collectors.ado_rest_client import AzureDevOpsRESTClient


async def get_test_runs(
    organization: str,
    project: str,
    top: int = 50
) -> dict[str, Any]:
    """
    Get test run history for a project.

    Args:
        organization: ADO organization name
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
                },
                ...
            ]
        }

    Raises:
        ValueError: If credentials not set
        httpx.HTTPStatusError: If ADO API returns error

    Example:
        >>> result = await get_test_runs(
        ...     organization="contoso",
        ...     project="MyProject",
        ...     top=100
        ... )
        >>> pass_rates = [r["passedTests"] / r["totalTests"] for r in result["value"]]
    """
    organization_url = os.getenv("ADO_ORGANIZATION_URL")
    pat = os.getenv("ADO_PAT")

    if not organization_url or not pat:
        raise ValueError("Missing ADO credentials (ADO_ORGANIZATION_URL, ADO_PAT)")

    if organization not in organization_url:
        raise ValueError(f"Organization mismatch: '{organization}' not in '{organization_url}'")

    client = AzureDevOpsRESTClient(organization_url=organization_url, pat=pat)

    try:
        result = await client.get_test_runs(project=project, top=top)
        return result
    except Exception as e:
        raise RuntimeError(f"Failed to fetch test runs for project '{project}': {e}") from e
