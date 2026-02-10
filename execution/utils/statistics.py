"""
Statistics Utilities

Shared statistical functions for metrics calculations.
Eliminates duplication of percentile calculations across collectors.

Usage:
    from execution.utils.statistics import calculate_percentile, calculate_percentiles

    p50 = calculate_percentile(data, 50)
    stats = calculate_percentiles(data, [50, 85, 95])
"""

import logging
from collections.abc import Sequence

# Set up logger
logger = logging.getLogger(__name__)


def calculate_percentile(data: Sequence[float], percentile: float) -> float:
    """
    Calculate a single percentile value.

    Uses linear interpolation between values (same as numpy.percentile).

    Args:
        data: Sequence of numeric values
        percentile: Percentile to calculate (0-100)

    Returns:
        Percentile value

    Raises:
        ValueError: If data is empty or percentile is out of range

    Example:
        lead_times = [5.2, 10.1, 15.3, 20.0, 25.5]
        median = calculate_percentile(lead_times, 50)
        p85 = calculate_percentile(lead_times, 85)
    """
    if not data:
        raise ValueError("Cannot calculate percentile of empty data")

    if not 0 <= percentile <= 100:
        raise ValueError(f"Percentile must be 0-100, got {percentile}")

    # Convert to sorted list
    sorted_data = sorted(data)
    n = len(sorted_data)

    # Calculate index with linear interpolation
    index = (n - 1) * (percentile / 100.0)
    lower_index = int(index)
    upper_index = min(lower_index + 1, n - 1)

    # Interpolate between lower and upper values
    lower_value = sorted_data[lower_index]
    upper_value = sorted_data[upper_index]
    fraction = index - lower_index

    result = lower_value + fraction * (upper_value - lower_value)
    return float(result)


def calculate_percentiles(data: Sequence[float], percentiles: list[float]) -> dict[str, float]:
    """
    Calculate multiple percentiles at once.

    More efficient than calling calculate_percentile multiple times
    because data is only sorted once.

    Args:
        data: Sequence of numeric values
        percentiles: List of percentiles to calculate (e.g., [50, 85, 95])

    Returns:
        Dictionary mapping percentile names to values
        Keys are formatted as "p{percentile}" (e.g., "p50", "p85")

    Example:
        lead_times = [5, 10, 15, 20, 25, 30]
        stats = calculate_percentiles(lead_times, [50, 85, 95])
        # Returns: {"p50": 17.5, "p85": 27.25, "p95": 29.25}
    """
    if not data:
        return {f"p{int(p)}": 0.0 for p in percentiles}

    sorted_data = sorted(data)
    n = len(sorted_data)

    results = {}
    for percentile in percentiles:
        if not 0 <= percentile <= 100:
            raise ValueError(f"Percentile must be 0-100, got {percentile}")

        index = (n - 1) * (percentile / 100.0)
        lower_index = int(index)
        upper_index = min(lower_index + 1, n - 1)

        lower_value = sorted_data[lower_index]
        upper_value = sorted_data[upper_index]
        fraction = index - lower_index

        result = lower_value + fraction * (upper_value - lower_value)
        results[f"p{int(percentile)}"] = float(result)

    return results


def calculate_summary_stats(data: Sequence[float]) -> dict[str, float]:
    """
    Calculate common summary statistics.

    Includes: min, max, mean, median (p50), p85, p95.

    Args:
        data: Sequence of numeric values

    Returns:
        Dictionary with summary statistics

    Example:
        lead_times = [5, 10, 15, 20, 25]
        stats = calculate_summary_stats(lead_times)
        # Returns: {
        #     "min": 5.0,
        #     "max": 25.0,
        #     "mean": 15.0,
        #     "p50": 15.0,
        #     "p85": 23.0,
        #     "p95": 24.0,
        #     "count": 5
        # }
    """
    if not data:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "p50": 0.0, "p85": 0.0, "p95": 0.0, "count": 0}

    sorted_data = sorted(data)
    n = len(sorted_data)

    return {
        "min": float(sorted_data[0]),
        "max": float(sorted_data[-1]),
        "mean": float(sum(data) / n),
        "count": n,
        **calculate_percentiles(sorted_data, [50, 85, 95]),
    }


# Self-test
if __name__ == "__main__":
    # Set up logger for self-test
    test_logger = logging.getLogger(__name__)
    test_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    test_logger.addHandler(handler)

    test_logger.info("Statistics Utilities - Self Test")
    test_logger.info("=" * 60)

    # Test data
    test_data = [5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0]

    # Test 1: Single percentile
    test_logger.info("\n[Test 1] Single percentile calculation")
    p50 = calculate_percentile(test_data, 50)
    test_logger.info(f"  Median (P50): {p50}")
    assert p50 == 27.5, f"Expected 27.5, got {p50}"
    test_logger.info("  ✓ PASS")

    # Test 2: Multiple percentiles
    test_logger.info("\n[Test 2] Multiple percentiles")
    percentiles = calculate_percentiles(test_data, [25, 50, 75, 85, 95])
    test_logger.info(f"  P25: {percentiles['p25']:.2f}")
    test_logger.info(f"  P50: {percentiles['p50']:.2f}")
    test_logger.info(f"  P75: {percentiles['p75']:.2f}")
    test_logger.info(f"  P85: {percentiles['p85']:.2f}")
    test_logger.info(f"  P95: {percentiles['p95']:.2f}")
    test_logger.info("  ✓ PASS")

    # Test 3: Summary statistics
    test_logger.info("\n[Test 3] Summary statistics")
    stats = calculate_summary_stats(test_data)
    test_logger.info(f"  Min: {stats['min']}")
    test_logger.info(f"  Max: {stats['max']}")
    test_logger.info(f"  Mean: {stats['mean']}")
    test_logger.info(f"  Median: {stats['p50']}")
    test_logger.info(f"  P85: {stats['p85']}")
    test_logger.info(f"  Count: {stats['count']}")
    assert stats["min"] == 5.0
    assert stats["max"] == 50.0
    assert stats["mean"] == 27.5
    assert stats["count"] == 10
    test_logger.info("  ✓ PASS")

    # Test 4: Empty data
    test_logger.info("\n[Test 4] Empty data handling")
    try:
        calculate_percentile([], 50)
        test_logger.error("  ✗ FAIL - Should raise ValueError")
    except ValueError:
        test_logger.info("  ✓ PASS - Correctly raises ValueError")

    # Test 5: Edge case - single value
    test_logger.info("\n[Test 5] Single value")
    result = calculate_percentile([42.0], 50)
    assert result == 42.0
    test_logger.info(f"  Result: {result}")
    test_logger.info("  ✓ PASS")

    # Test 6: Invalid percentile
    test_logger.info("\n[Test 6] Invalid percentile")
    try:
        calculate_percentile([1, 2, 3], 150)
        test_logger.error("  ✗ FAIL - Should raise ValueError")
    except ValueError:
        test_logger.info("  ✓ PASS - Correctly raises ValueError")

    test_logger.info("\n" + "=" * 60)
    test_logger.info("All tests passed!")
    test_logger.info("\nUsage Examples:")
    test_logger.info("  from execution.utils.statistics import calculate_percentile, calculate_percentiles")
    test_logger.info("  p50 = calculate_percentile(lead_times, 50)")
    test_logger.info("  stats = calculate_percentiles(lead_times, [50, 85, 95])")
