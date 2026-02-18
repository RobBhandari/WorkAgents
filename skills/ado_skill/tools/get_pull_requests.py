"""
Get Pull Requests Tool

Fetches PR history for Azure DevOps Git repositories.
"""

import os
from typing import Any

from execution.collectors.ado_rest_client import AzureDevOpsRESTClient


async def get_pull_requests(
    organization: str,
    project: str,
    repository_id: str,
    status: str | None = None
) -> dict[str, Any]:
    """
    Get pull request history for a repository.

    Args:
        organization: ADO organization name
        project: Project name
        repository_id: Repository ID or name
        status: Optional PR status filter ("active", "completed", "abandoned", "all")

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
                },
                ...
            ]
        }

    Raises:
        ValueError: If credentials not set
        httpx.HTTPStatusError: If ADO API returns error

    Example:
        >>> result = await get_pull_requests(
        ...     organization="contoso",
        ...     project="MyProject",
        ...     repository_id="my-repo",
        ...     status="completed"
        ... )
        >>> pr_count = result["count"]
    """
    organization_url = os.getenv("ADO_ORGANIZATION_URL")
    pat = os.getenv("ADO_PAT")

    if not organization_url or not pat:
        raise ValueError("Missing ADO credentials (ADO_ORGANIZATION_URL, ADO_PAT)")

    if organization not in organization_url:
        raise ValueError(f"Organization mismatch: '{organization}' not in '{organization_url}'")

    client = AzureDevOpsRESTClient(organization_url=organization_url, pat=pat)

    try:
        result = await client.get_pull_requests(
            project=project,
            repository_id=repository_id,
            status=status
        )
        return result
    except Exception as e:
        raise RuntimeError(f"Failed to fetch PRs for repository '{repository_id}': {e}") from e
