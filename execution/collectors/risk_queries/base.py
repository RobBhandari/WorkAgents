"""
Risk Metric Query Protocol

Defines the interface for all risk metric query classes.
This enables type checking and ensures consistent query structure.
"""

from typing import Protocol


class RiskMetricQuery(Protocol):
    """
    Protocol for risk metric queries.

    All risk query classes should implement this interface to ensure
    consistency across different query types.
    """

    def execute(self) -> dict:
        """
        Execute the query and return results.

        Returns:
            Dictionary with query results including work item IDs and metadata
        """
        ...

    def build_wiql(self) -> str:
        """
        Build the WIQL query string.

        Returns:
            WIQL query string ready for execution
        """
        ...
