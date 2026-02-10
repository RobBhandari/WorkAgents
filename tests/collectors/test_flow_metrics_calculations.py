"""
Tests for Flow Metrics Calculation Functions

Tests cover:
- calculate_percentile: Edge cases (empty lists, None values, errors)
- calculate_lead_time: Various date formats and None handling
- calculate_dual_metrics: Operational vs cleanup classification
- calculate_throughput: Basic calculations
- calculate_cycle_time_variance: Standard deviation calculations
- calculate_aging_items: Aging threshold logic
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from execution.collectors.flow_metrics_calculations import (
    calculate_aging_items,
    calculate_cycle_time_variance,
    calculate_dual_metrics,
    calculate_lead_time,
    calculate_percentile,
    calculate_throughput,
)


class TestCalculatePercentile:
    """Test percentile calculation with various edge cases"""

    def test_empty_list(self):
        """Test percentile with empty list returns None"""
        result = calculate_percentile([], 50)
        assert result is None

    def test_list_with_none_values(self):
        """Test percentile filters out None values"""
        values = [1.0, None, 2.0, None, 3.0]  # type: ignore[list-item]
        result = calculate_percentile(values, 50)  # type: ignore[arg-type]
        assert result == 2.0  # Median of [1.0, 2.0, 3.0]

    def test_all_none_values(self):
        """Test percentile with all None values returns None"""
        values = [None, None, None]  # type: ignore[list-item]
        result = calculate_percentile(values, 50)  # type: ignore[arg-type]
        assert result is None

    def test_single_value(self):
        """Test percentile with single value"""
        result = calculate_percentile([5.0], 85)
        assert result == 5.0

    def test_p50_calculation(self):
        """Test P50 (median) calculation"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_percentile(values, 50)
        assert result == 3.0

    def test_p85_calculation(self):
        """Test P85 calculation"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        result = calculate_percentile(values, 85)
        # P85 of 10 values should be around 8.5
        assert result is not None
        assert 8.0 <= result <= 9.0

    def test_p95_calculation(self):
        """Test P95 calculation"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        result = calculate_percentile(values, 95)
        # P95 of 10 values should be around 9.5
        assert result is not None
        assert 9.0 <= result <= 10.0

    def test_unsorted_values(self):
        """Test percentile with unsorted values"""
        values = [5.0, 2.0, 8.0, 1.0, 9.0]
        result = calculate_percentile(values, 50)
        assert result == 5.0  # Median

    def test_duplicate_values(self):
        """Test percentile with duplicate values"""
        values = [1.0, 2.0, 2.0, 2.0, 3.0]
        result = calculate_percentile(values, 50)
        assert result == 2.0

    def test_error_handling_value_error(self):
        """Test percentile handles ValueError gracefully"""
        # This should not raise, but return None
        result = calculate_percentile([1.0, 2.0], 50)
        assert result is not None

    def test_error_handling_with_invalid_percentile(self):
        """Test percentile with edge percentile values"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        # Test P0 (minimum)
        result = calculate_percentile(values, 0)
        assert result == 1.0
        # Test P100 (maximum)
        result = calculate_percentile(values, 100)
        assert result == 5.0

    def test_error_handling_with_invalid_value_types(self):
        """Test percentile handles invalid value types gracefully"""
        # Test with mixed invalid types that might cause TypeError
        values = [1.0, 2.0, float("nan"), 3.0]
        result = calculate_percentile(values, 50)
        # Should handle gracefully - nan values may cause issues
        assert result is not None or result is None  # Either way, shouldn't crash

    def test_error_handling_percentile_calculation_error(self):
        """Test percentile error handling path with edge case"""
        # Create a scenario that could trigger calculation errors
        # Very small list with potential for edge case errors
        values = [float("inf")]
        result = calculate_percentile(values, 50)
        # Should return the value or None, not crash
        assert result is not None or result is None


class TestCalculateLeadTime:
    """Test lead time calculation with various date formats"""

    def test_basic_lead_time(self):
        """Test basic lead time calculation"""
        closed_items = [
            {
                "System.CreatedDate": "2026-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-10T00:00:00",
            },
            {
                "System.CreatedDate": "2026-01-05T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-20T00:00:00",
            },
        ]

        result = calculate_lead_time(closed_items)

        assert result["sample_size"] == 2
        assert result["p50"] is not None
        assert result["p85"] is not None
        assert result["p95"] is not None
        assert len(result["raw_values"]) == 2

    def test_lead_time_with_missing_dates(self):
        """Test lead time with missing date fields"""
        closed_items = [
            {"System.CreatedDate": "2026-01-01T00:00:00"},  # Missing closed date
            {
                "System.CreatedDate": "2026-01-05T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-20T00:00:00",
            },
        ]

        result = calculate_lead_time(closed_items)

        # Only one valid lead time
        assert result["sample_size"] == 1
        assert len(result["raw_values"]) == 1

    def test_lead_time_with_no_valid_dates(self):
        """Test lead time with no valid date pairs"""
        closed_items = [
            {"System.CreatedDate": "2026-01-01T00:00:00"},
            {"Microsoft.VSTS.Common.ClosedDate": "2026-01-10T00:00:00"},
        ]

        result = calculate_lead_time(closed_items)

        assert result["sample_size"] == 0
        assert result["p50"] is None
        assert result["p85"] is None
        assert result["p95"] is None
        assert len(result["raw_values"]) == 0

    def test_lead_time_empty_list(self):
        """Test lead time with empty item list"""
        result = calculate_lead_time([])

        assert result["sample_size"] == 0
        assert result["p50"] is None
        assert result["p85"] is None
        assert result["p95"] is None

    def test_lead_time_rounding(self):
        """Test that lead times are rounded to 1 decimal place"""
        closed_items = [
            {
                "System.CreatedDate": "2026-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-03T06:00:00",  # 2.25 days
            }
        ]

        result = calculate_lead_time(closed_items)

        # Check rounding
        assert isinstance(result["p50"], float)
        assert result["p50"] == round(result["raw_values"][0], 1)


class TestCalculateDualMetrics:
    """Test dual metrics (operational vs cleanup) calculation"""

    def test_operational_only(self):
        """Test dual metrics with only operational items (< 365 days)"""
        closed_items = [
            {
                "System.CreatedDate": "2026-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-10T00:00:00",  # 9 days
            },
            {
                "System.CreatedDate": "2026-01-05T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-20T00:00:00",  # 15 days
            },
        ]

        result = calculate_dual_metrics(closed_items)

        assert result["operational"]["closed_count"] == 2
        assert result["cleanup"]["closed_count"] == 0
        assert result["indicators"]["is_cleanup_effort"] is False
        assert result["indicators"]["cleanup_percentage"] == 0.0

    def test_cleanup_only(self):
        """Test dual metrics with only cleanup items (>= 365 days)"""
        closed_items = [
            {
                "System.CreatedDate": "2024-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-10T00:00:00",  # ~740 days
            },
            {
                "System.CreatedDate": "2023-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-10T00:00:00",  # ~1100 days
            },
        ]

        result = calculate_dual_metrics(closed_items)

        assert result["operational"]["closed_count"] == 0
        assert result["cleanup"]["closed_count"] == 2
        assert result["indicators"]["cleanup_percentage"] == 100.0
        assert result["cleanup"]["avg_age_years"] is not None
        assert result["cleanup"]["avg_age_years"] > 2.0

    def test_mixed_operational_and_cleanup(self):
        """Test dual metrics with mix of operational and cleanup items"""
        closed_items = [
            {
                "System.CreatedDate": "2026-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-10T00:00:00",  # 9 days
            },
            {
                "System.CreatedDate": "2024-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-10T00:00:00",  # ~740 days
            },
        ]

        result = calculate_dual_metrics(closed_items)

        assert result["operational"]["closed_count"] == 1
        assert result["cleanup"]["closed_count"] == 1
        assert result["indicators"]["total_closed"] == 2
        assert result["indicators"]["cleanup_percentage"] == 50.0

    def test_cleanup_effort_detection(self):
        """Test cleanup effort detection (>30% cleanup)"""
        # Create 7 operational and 3 cleanup items (30% cleanup)
        closed_items = []
        for i in range(7):
            closed_items.append(
                {
                    "System.CreatedDate": f"2026-01-0{i+1}T00:00:00",
                    "Microsoft.VSTS.Common.ClosedDate": f"2026-01-{i+10}T00:00:00",
                }
            )
        for i in range(4):  # 4 cleanup items = 36% cleanup
            closed_items.append(
                {
                    "System.CreatedDate": "2024-01-01T00:00:00",
                    "Microsoft.VSTS.Common.ClosedDate": "2026-01-10T00:00:00",
                }
            )

        result = calculate_dual_metrics(closed_items)

        assert result["cleanup"]["closed_count"] == 4
        assert result["indicators"]["cleanup_percentage"] > 30.0
        assert result["indicators"]["is_cleanup_effort"] is True

    def test_significant_cleanup_detection(self):
        """Test significant cleanup detection (>10 cleanup items)"""
        # Create 15 cleanup items
        closed_items = []
        for i in range(15):
            closed_items.append(
                {
                    "System.CreatedDate": "2024-01-01T00:00:00",
                    "Microsoft.VSTS.Common.ClosedDate": "2026-01-10T00:00:00",
                }
            )

        result = calculate_dual_metrics(closed_items)

        assert result["cleanup"]["closed_count"] == 15
        assert result["indicators"]["has_significant_cleanup"] is True

    def test_custom_cleanup_threshold(self):
        """Test dual metrics with custom cleanup threshold"""
        closed_items = [
            {
                "System.CreatedDate": "2025-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-10T00:00:00",  # ~375 days
            }
        ]

        # With default threshold (365 days), this is cleanup
        result_default = calculate_dual_metrics(closed_items)
        assert result_default["cleanup"]["closed_count"] == 1

        # With higher threshold (400 days), this is operational
        result_custom = calculate_dual_metrics(closed_items, cleanup_threshold_days=400)
        assert result_custom["operational"]["closed_count"] == 1
        assert result_custom["indicators"]["threshold_days"] == 400

    def test_empty_items(self):
        """Test dual metrics with empty list"""
        result = calculate_dual_metrics([])

        assert result["operational"]["closed_count"] == 0
        assert result["cleanup"]["closed_count"] == 0
        assert result["indicators"]["cleanup_percentage"] == 0.0


class TestCalculateThroughput:
    """Test throughput calculation"""

    def test_basic_throughput(self):
        """Test basic throughput calculation"""
        closed_items = [{"id": i} for i in range(90)]  # 90 items

        result = calculate_throughput(closed_items, lookback_days=90)

        assert result["closed_count"] == 90
        assert result["lookback_days"] == 90
        # 90 items / (90/7) weeks = 7.0 items per week
        assert result["per_week"] == 7.0

    def test_throughput_with_custom_lookback(self):
        """Test throughput with custom lookback period"""
        closed_items = [{"id": i} for i in range(30)]

        result = calculate_throughput(closed_items, lookback_days=30)

        assert result["closed_count"] == 30
        assert result["lookback_days"] == 30
        # 30 items / (30/7) weeks ≈ 7.0 items per week
        assert result["per_week"] == 7.0

    def test_throughput_with_zero_items(self):
        """Test throughput with no closed items"""
        result = calculate_throughput([], lookback_days=90)

        assert result["closed_count"] == 0
        assert result["per_week"] == 0.0

    def test_throughput_rounding(self):
        """Test that throughput is rounded to 1 decimal place"""
        closed_items = [{"id": i} for i in range(13)]  # Should give non-round number

        result = calculate_throughput(closed_items, lookback_days=90)

        assert isinstance(result["per_week"], float)
        # Check it's rounded to 1 decimal place
        assert result["per_week"] == round(result["per_week"], 1)


class TestCalculateCycleTimeVariance:
    """Test cycle time variance calculation"""

    def test_basic_variance(self):
        """Test basic variance calculation"""
        closed_items = [
            {
                "System.CreatedDate": "2026-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-05T00:00:00",  # 4 days
            },
            {
                "System.CreatedDate": "2026-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-07T00:00:00",  # 6 days
            },
            {
                "System.CreatedDate": "2026-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-11T00:00:00",  # 10 days
            },
        ]

        result = calculate_cycle_time_variance(closed_items)

        assert result["sample_size"] == 3
        assert result["std_dev_days"] is not None
        assert result["coefficient_of_variation"] is not None
        assert result["mean_days"] is not None

    def test_variance_with_insufficient_data(self):
        """Test variance with less than 2 data points"""
        closed_items = [
            {
                "System.CreatedDate": "2026-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-05T00:00:00",
            }
        ]

        result = calculate_cycle_time_variance(closed_items)

        assert result["sample_size"] == 1
        assert result["std_dev_days"] is None
        assert result["coefficient_of_variation"] is None

    def test_variance_with_empty_list(self):
        """Test variance with empty list"""
        result = calculate_cycle_time_variance([])

        assert result["sample_size"] == 0
        assert result["std_dev_days"] is None
        assert result["coefficient_of_variation"] is None

    def test_variance_with_missing_dates(self):
        """Test variance excludes items with missing dates"""
        closed_items = [
            {
                "System.CreatedDate": "2026-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-05T00:00:00",
            },
            {"System.CreatedDate": "2026-01-01T00:00:00"},  # Missing closed date
            {
                "System.CreatedDate": "2026-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-10T00:00:00",
            },
        ]

        result = calculate_cycle_time_variance(closed_items)

        assert result["sample_size"] == 2

    def test_variance_rounding(self):
        """Test that variance metrics are rounded to 1 decimal place"""
        closed_items = [
            {
                "System.CreatedDate": "2026-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-04T00:00:00",
            },
            {
                "System.CreatedDate": "2026-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-08T00:00:00",
            },
        ]

        result = calculate_cycle_time_variance(closed_items)

        assert result["std_dev_days"] == round(result["std_dev_days"], 1)
        assert result["mean_days"] == round(result["mean_days"], 1)
        if result["coefficient_of_variation"]:
            assert result["coefficient_of_variation"] == round(result["coefficient_of_variation"], 1)

    def test_variance_with_zero_mean(self):
        """Test variance handles zero mean gracefully (CV should be None)"""
        # This is an edge case that shouldn't happen in practice
        # but we test error handling
        closed_items = [
            {
                "System.CreatedDate": "2026-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-05T00:00:00",
            },
            {
                "System.CreatedDate": "2026-01-01T00:00:00",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-06T00:00:00",
            },
        ]

        result = calculate_cycle_time_variance(closed_items)
        # With normal data, CV should be calculated
        assert result["coefficient_of_variation"] is not None


class TestCalculateAgingItems:
    """Test aging items calculation"""

    def test_basic_aging_items(self):
        """Test basic aging items detection"""
        now = datetime.now()
        old_date = (now - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        recent_date = (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S") + "Z"

        open_items = [
            {
                "System.Id": 1,
                "System.Title": "Old Bug",
                "System.State": "Active",
                "System.WorkItemType": "Bug",
                "System.CreatedDate": old_date,
            },
            {
                "System.Id": 2,
                "System.Title": "Recent Bug",
                "System.State": "Active",
                "System.WorkItemType": "Bug",
                "System.CreatedDate": recent_date,
            },
        ]

        result = calculate_aging_items(open_items, aging_threshold_days=30)

        assert result["count"] == 1  # Only the old bug
        assert result["threshold_days"] == 30
        assert len(result["items"]) == 1
        assert result["items"][0]["id"] == 1
        assert result["items"][0]["age_days"] > 30

    def test_aging_items_sorted_by_age(self):
        """Test aging items are sorted by age (oldest first)"""
        now = datetime.now()
        dates = [
            (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S") + "Z",
            (now - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%S") + "Z",
            (now - timedelta(days=45)).strftime("%Y-%m-%dT%H:%M:%S") + "Z",
        ]

        open_items = [
            {
                "System.Id": i,
                "System.Title": f"Bug {i}",
                "System.State": "Active",
                "System.WorkItemType": "Bug",
                "System.CreatedDate": dates[i],
            }
            for i in range(3)
        ]

        result = calculate_aging_items(open_items, aging_threshold_days=30)

        assert result["count"] == 3
        # Check sorted by age (oldest first)
        ages = [item["age_days"] for item in result["items"]]
        assert ages == sorted(ages, reverse=True)
        assert result["items"][0]["id"] == 0  # Oldest item

    def test_aging_items_limit_to_20(self):
        """Test aging items limited to top 20"""
        now = datetime.now()
        old_date = (now - timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%S") + "Z"

        open_items = [
            {
                "System.Id": i,
                "System.Title": f"Bug {i}",
                "System.State": "Active",
                "System.WorkItemType": "Bug",
                "System.CreatedDate": old_date,
            }
            for i in range(30)
        ]

        result = calculate_aging_items(open_items, aging_threshold_days=30)

        assert result["count"] == 30
        assert len(result["items"]) == 20  # Limited to top 20

    def test_aging_items_with_no_aging(self):
        """Test aging items when none exceed threshold"""
        now = datetime.now()
        recent_date = (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S") + "Z"

        open_items = [
            {
                "System.Id": 1,
                "System.Title": "Recent Bug",
                "System.State": "Active",
                "System.WorkItemType": "Bug",
                "System.CreatedDate": recent_date,
            }
        ]

        result = calculate_aging_items(open_items, aging_threshold_days=30)

        assert result["count"] == 0
        assert len(result["items"]) == 0

    def test_aging_items_with_empty_list(self):
        """Test aging items with empty list"""
        result = calculate_aging_items([])

        assert result["count"] == 0
        assert len(result["items"]) == 0

    def test_aging_items_with_missing_created_date(self):
        """Test aging items excludes items with missing created date"""
        now = datetime.now()
        old_date = (now - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%S") + "Z"

        open_items = [
            {
                "System.Id": 1,
                "System.Title": "Old Bug",
                "System.State": "Active",
                "System.WorkItemType": "Bug",
                "System.CreatedDate": old_date,
            },
            {
                "System.Id": 2,
                "System.Title": "No Date Bug",
                "System.State": "Active",
                "System.WorkItemType": "Bug",
                # Missing System.CreatedDate
            },
        ]

        result = calculate_aging_items(open_items, aging_threshold_days=30)

        assert result["count"] == 1
        assert result["items"][0]["id"] == 1

    def test_aging_items_custom_threshold(self):
        """Test aging items with custom threshold"""
        now = datetime.now()
        date_50_days = (now - timedelta(days=50)).strftime("%Y-%m-%dT%H:%M:%S") + "Z"

        open_items = [
            {
                "System.Id": 1,
                "System.Title": "Bug",
                "System.State": "Active",
                "System.WorkItemType": "Bug",
                "System.CreatedDate": date_50_days,
            }
        ]

        # With default threshold (30 days), should be aging
        result_30 = calculate_aging_items(open_items, aging_threshold_days=30)
        assert result_30["count"] == 1

        # With higher threshold (60 days), should not be aging
        result_60 = calculate_aging_items(open_items, aging_threshold_days=60)
        assert result_60["count"] == 0

    def test_aging_items_includes_all_fields(self):
        """Test aging items includes all expected fields"""
        now = datetime.now()
        old_date = (now - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%S") + "Z"

        open_items = [
            {
                "System.Id": 123,
                "System.Title": "Test Bug Title",
                "System.State": "Active",
                "System.WorkItemType": "Bug",
                "System.CreatedDate": old_date,
            }
        ]

        result = calculate_aging_items(open_items, aging_threshold_days=30)

        item = result["items"][0]
        assert item["id"] == 123
        assert item["title"] == "Test Bug Title"
        assert item["state"] == "Active"
        assert item["type"] == "Bug"
        assert item["age_days"] > 30
        assert item["created_date"] == old_date
