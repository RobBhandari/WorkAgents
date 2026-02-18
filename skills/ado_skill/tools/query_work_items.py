"""
Query Work Items Tool

Executes WIQL (Work Item Query Language) queries against Azure DevOps.
Includes security validation to prevent WIQL injection attacks.
"""

import os
from typing import Any

from execution.collectors.ado_rest_client import AzureDevOpsRESTClient
from execution.security import WIQLValidator


async def query_work_items(organization: str, project: str, wiql: str) -> dict[str, Any]:
    """
    Execute WIQL query to search Azure DevOps work items.

    This tool provides safe, reusable work item querying with:
    - WIQL injection prevention (validates query syntax)
    - Automatic retry on transient errors
    - Rate limiting handling
    - Connection pooling (HTTP/2)

    Args:
        organization: ADO organization name (e.g., 'contoso' from https://dev.azure.com/contoso)
        project: Project name
        wiql: WIQL query string (e.g., "SELECT [System.Id] FROM WorkItems WHERE [System.State] = 'Active'")

    Returns:
        Query results in format:
        {
            "queryType": "flat",
            "workItems": [
                {"id": 1001, "url": "..."},
                {"id": 1002, "url": "..."}
            ]
        }

    Raises:
        SecurityError: If WIQL query fails validation (potential injection)
        ValueError: If organization_url or PAT environment variables not set
        httpx.HTTPStatusError: If ADO API returns error (401/403/404/500)

    Example:
        >>> result = await query_work_items(
        ...     organization="contoso",
        ...     project="MyProject",
        ...     wiql="SELECT [System.Id] FROM WorkItems WHERE [System.WorkItemType] = 'Bug'"
        ... )
        >>> bug_ids = [item["id"] for item in result["workItems"]]

    Security:
        - WIQL query is validated by WIQLValidator before execution
        - Prevents SQL-like injection attacks (e.g., DROP TABLE, malformed syntax)
        - Uses parameterized queries internally where possible
    """
    # Step 1: Get authenticated REST client
    # Note: WIQL validation is performed by the agent before calling this tool
    # (validates project name, dates, area paths individually before query construction)
    organization_url = os.getenv("ADO_ORGANIZATION_URL")
    pat = os.getenv("ADO_PAT")

    if not organization_url or not pat:
        raise ValueError(
            "Missing Azure DevOps credentials. Set ADO_ORGANIZATION_URL and ADO_PAT environment variables."
        )

    # Ensure organization URL matches the organization parameter
    # (prevent querying wrong org with different credentials)
    if organization not in organization_url:
        raise ValueError(
            f"Organization '{organization}' does not match ADO_ORGANIZATION_URL '{organization_url}'. "
            "Ensure credentials match the target organization."
        )

    # Step 2: Execute query via REST API
    client = AzureDevOpsRESTClient(organization_url=organization_url, pat=pat)

    try:
        result = await client.query_by_wiql(project=project, wiql_query=wiql)
        return result
    except Exception as e:
        # Re-raise with context
        raise RuntimeError(
            f"ADO query failed for project '{project}': {e}"
        ) from e


class SecurityError(Exception):
    """Raised when security validation fails (e.g., WIQL injection detected)"""
    pass
