#!/usr/bin/env python3
"""
Flow Metrics Calculation Functions

Pure calculation functions for flow metrics (lead time, throughput, aging, etc.)
These functions operate on work item data and return metric dictionaries.
"""

import statistics
from datetime import datetime

from execution.domain.constants import cleanup_indicators, flow_metrics
from execution.utils.datetime_utils import calculate_age_days, calculate_lead_time_days


def calculate_percentile(values: list[float], percentile: int) -> float | None:
    """Calculate percentile from list of values."""
    if not values:
        return None

    # Remove None values
    values = [v for v in values if v is not None]
    if not values:
        return None

    # Use statistics.quantiles for percentile calculation
    try:
        # quantiles returns n-1 cut points for n quantiles
        # For P85, we want the value at 85% position
        sorted_values = sorted(values)
        index = (percentile / 100) * (len(sorted_values) - 1)
        lower_index = int(index)
        upper_index = min(lower_index + 1, len(sorted_values) - 1)
        weight = index - lower_index
        return sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight
    except Exception as e:
        print(f"    [WARNING] Error calculating P{percentile}: {e}")
        return None


def calculate_lead_time(closed_items: list[dict]) -> dict:
    """
    Calculate lead time: Created Date → Closed Date

    Returns percentiles (P50, P85, P95) in days
    """
    lead_times = []

    for item in closed_items:
        created = item.get("System.CreatedDate")
        closed = item.get("Microsoft.VSTS.Common.ClosedDate")

        lead_time = calculate_lead_time_days(created, closed)
        if lead_time is not None:
            lead_times.append(lead_time)

    p50 = calculate_percentile(lead_times, flow_metrics.P50_PERCENTILE)
    p85 = calculate_percentile(lead_times, flow_metrics.P85_PERCENTILE)
    p95 = calculate_percentile(lead_times, flow_metrics.P95_PERCENTILE)

    return {
        "p50": round(p50, 1) if p50 is not None else None,
        "p85": round(p85, 1) if p85 is not None else None,
        "p95": round(p95, 1) if p95 is not None else None,
        "sample_size": len(lead_times),
        "raw_values": lead_times[:10],  # Keep first 10 for debugging
    }


def calculate_dual_metrics(
    closed_items: list[dict], cleanup_threshold_days: int = flow_metrics.CLEANUP_THRESHOLD_DAYS
) -> dict:
    """
    Calculate separate metrics for operational work vs cleanup work.

    Operational: Items closed within 365 days (current/recent work)
    Cleanup: Items closed after >365 days (backlog grooming/historical cleanup)

    This separation prevents cleanup initiatives from distorting operational performance metrics.

    Args:
        closed_items: List of closed work items
        cleanup_threshold_days: Lead time threshold to classify as cleanup (default: 365 days)

    Returns:
        Dict with operational_metrics, cleanup_metrics, and cleanup_indicators
    """
    operational_items = []
    cleanup_items = []
    operational_lead_times = []
    cleanup_lead_times = []

    for item in closed_items:
        created = item.get("System.CreatedDate")
        closed = item.get("Microsoft.VSTS.Common.ClosedDate")

        lead_time = calculate_lead_time_days(created, closed)
        if lead_time is not None:
            if lead_time < cleanup_threshold_days:
                # Operational work - closed within threshold
                operational_items.append(item)
                operational_lead_times.append(lead_time)
            else:
                # Cleanup work - very old items closed
                cleanup_items.append(item)
                cleanup_lead_times.append(lead_time)

    # Calculate operational metrics
    op_p50 = calculate_percentile(operational_lead_times, flow_metrics.P50_PERCENTILE)
    op_p85 = calculate_percentile(operational_lead_times, flow_metrics.P85_PERCENTILE)
    op_p95 = calculate_percentile(operational_lead_times, flow_metrics.P95_PERCENTILE)

    operational_metrics = {
        "p50": round(op_p50, 1) if op_p50 is not None else None,
        "p85": round(op_p85, 1) if op_p85 is not None else None,
        "p95": round(op_p95, 1) if op_p95 is not None else None,
        "closed_count": len(operational_items),
        "sample_size": len(operational_lead_times),
    }

    # Calculate cleanup metrics
    cl_p50 = calculate_percentile(cleanup_lead_times, flow_metrics.P50_PERCENTILE)
    cl_p85 = calculate_percentile(cleanup_lead_times, flow_metrics.P85_PERCENTILE)
    cl_p95 = calculate_percentile(cleanup_lead_times, flow_metrics.P95_PERCENTILE)

    cleanup_metrics = {
        "p50": round(cl_p50, 1) if cl_p50 is not None else None,
        "p85": round(cl_p85, 1) if cl_p85 is not None else None,
        "p95": round(cl_p95, 1) if cl_p95 is not None else None,
        "closed_count": len(cleanup_items),
        "sample_size": len(cleanup_lead_times),
        "avg_age_years": (
            round(sum(cleanup_lead_times) / len(cleanup_lead_times) / 365, 1) if cleanup_lead_times else None
        ),
    }

    # Cleanup indicators - detect if metrics are being distorted
    total_closed = len(operational_items) + len(cleanup_items)
    cleanup_percentage = (len(cleanup_items) / total_closed * 100) if total_closed > 0 else 0

    is_cleanup_effort = cleanup_percentage > cleanup_indicators.CLEANUP_PERCENTAGE_THRESHOLD
    has_significant_cleanup = len(cleanup_items) > cleanup_indicators.SIGNIFICANT_CLEANUP_COUNT

    return {
        "operational": operational_metrics,
        "cleanup": cleanup_metrics,
        "indicators": {
            "cleanup_percentage": round(cleanup_percentage, 1),
            "is_cleanup_effort": is_cleanup_effort,
            "has_significant_cleanup": has_significant_cleanup,
            "total_closed": total_closed,
            "threshold_days": cleanup_threshold_days,
        },
    }


def calculate_throughput(closed_items: list[dict], lookback_days: int = 90) -> dict:
    """
    Calculate throughput - closed items per week.

    HARD DATA: Just count of closed items over time period.

    Args:
        closed_items: List of closed work items
        lookback_days: Period analyzed

    Returns:
        Throughput metrics
    """
    closed_count = len(closed_items)
    weeks = lookback_days / 7
    per_week = closed_count / weeks if weeks > 0 else 0

    return {"closed_count": closed_count, "lookback_days": lookback_days, "per_week": round(per_week, 1)}


def calculate_cycle_time_variance(closed_items: list[dict]) -> dict:
    """
    Calculate cycle time variance - standard deviation of lead times.

    HARD DATA: Statistical measure of lead time predictability.

    Args:
        closed_items: List of closed work items

    Returns:
        Variance metrics
    """
    lead_times = []

    for item in closed_items:
        created = item.get("System.CreatedDate")
        closed = item.get("Microsoft.VSTS.Common.ClosedDate")

        lead_time = calculate_lead_time_days(created, closed)
        if lead_time is not None:
            lead_times.append(lead_time)

    if len(lead_times) < 2:  # Need at least 2 points for std dev
        return {"sample_size": len(lead_times), "std_dev_days": None, "coefficient_of_variation": None}

    std_dev = statistics.stdev(lead_times)
    mean = statistics.mean(lead_times)
    cv = (std_dev / mean * 100) if mean > 0 else None

    return {
        "sample_size": len(lead_times),
        "std_dev_days": round(std_dev, 1),
        "coefficient_of_variation": round(cv, 1) if cv else None,
        "mean_days": round(mean, 1),
    }


def calculate_aging_items(
    open_items: list[dict], aging_threshold_days: int = flow_metrics.AGING_THRESHOLD_DAYS
) -> dict:
    """
    Calculate aging items: Items open > threshold days

    Returns count and list of aging items with details
    """
    now = datetime.now()
    aging_items = []

    for item in open_items:
        created = item.get("System.CreatedDate")

        age_days = calculate_age_days(created, reference_time=now)
        if age_days is not None and age_days > aging_threshold_days:
            aging_items.append(
                {
                    "id": item.get("System.Id"),
                    "title": item.get("System.Title"),
                    "state": item.get("System.State"),
                    "type": item.get("System.WorkItemType"),
                    "age_days": round(age_days, 1),
                    "created_date": created,
                }
            )

    # Sort by age (oldest first)
    aging_items.sort(key=lambda x: x["age_days"], reverse=True)

    return {
        "count": len(aging_items),
        "threshold_days": aging_threshold_days,
        "items": aging_items[:20],  # Top 20 oldest
    }
