"""
Shared Azure DevOps Connection Module

Provides centralized ADO connection management for all metrics collectors.
Eliminates duplicate connection code across multiple files.

Functions:
    get_ado_connection() -> Connection
        Create and return an authenticated ADO connection using credentials from secure_config.

    get_wit_client(connection=None) -> WorkItemTrackingClient
        Get Work Item Tracking client. Convenience wrapper for the most common use case.

Usage:
    from execution.collectors.ado_connection import get_ado_connection, get_wit_client

    # Option 1: Get connection and create client
    connection = get_ado_connection()
    wit_client = connection.clients.get_work_item_tracking_client()

    # Option 2: Use convenience function
    wit_client = get_wit_client()
"""

from azure.devops.connection import Connection
from azure.devops.v7_1.work_item_tracking import WorkItemTrackingClient
from msrest.authentication import BasicAuthentication

from execution.secure_config import get_config


def get_ado_connection() -> Connection:
    """
    Get ADO connection using credentials from secure_config.

    Returns:
        Connection: Authenticated Azure DevOps connection object

    Raises:
        ValueError: If ADO_ORGANIZATION_URL or ADO_PAT are not set

    Example:
        connection = get_ado_connection()
        wit_client = connection.clients.get_work_item_tracking_client()
    """
    ado_config = get_config().get_ado_config()
    organization_url = ado_config.organization_url
    pat = ado_config.pat

    if not organization_url or not pat:
        raise ValueError("ADO_ORGANIZATION_URL and ADO_PAT must be set in .env file")

    credentials = BasicAuthentication("", pat)
    connection = Connection(base_url=organization_url, creds=credentials)
    return connection


def get_wit_client(connection: Connection | None = None) -> WorkItemTrackingClient:
    """
    Get Work Item Tracking client.

    Convenience function that provides a WIT client without requiring
    the caller to know the connection details.

    Args:
        connection: Optional existing ADO connection. If None, creates a new connection.

    Returns:
        WorkItemTrackingClient: Work Item Tracking client for querying ADO work items

    Example:
        # Simple usage - automatically creates connection
        wit_client = get_wit_client()

        # Reuse existing connection
        connection = get_ado_connection()
        wit_client = get_wit_client(connection)
    """
    if connection is None:
        connection = get_ado_connection()

    return connection.clients.get_work_item_tracking_client()
