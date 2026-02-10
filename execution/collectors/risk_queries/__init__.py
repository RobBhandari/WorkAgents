"""
Risk Queries Package

Query classes for collecting risk-related metrics from Azure DevOps.
Follows Command pattern with execute() methods for query execution.

Classes:
    HighPriorityBugsQuery: Query for high-priority bugs (Priority 1 & 2)
    StaleBugsQuery: Query for stale/aging bugs (open >N days)
    BlockedBugsQuery: Query for bugs in blocked state
    MissingTestsQuery: Query for work items without test coverage

Usage:
    from execution.collectors.risk_queries import (
        HighPriorityBugsQuery,
        StaleBugsQuery,
        BlockedBugsQuery,
        MissingTestsQuery,
    )

    query = BlockedBugsQuery(ado_client)
    results = query.execute(project_name="MyProject")
"""

from execution.collectors.risk_queries.blocked_bugs import BlockedBugsQuery
from execution.collectors.risk_queries.high_priority_bugs import HighPriorityBugsQuery
from execution.collectors.risk_queries.missing_tests import MissingTestsQuery
from execution.collectors.risk_queries.stale_bugs import StaleBugsQuery

__all__ = ["HighPriorityBugsQuery", "StaleBugsQuery", "BlockedBugsQuery", "MissingTestsQuery"]
