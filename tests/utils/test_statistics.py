#!/usr/bin/env python3
"""
Tests for statistics module

Tests percentile calculations and statistical aggregations.
Verifies accuracy against numpy/scipy implementations.
"""

import pytest

from execution.utils.statistics import (
    calculate_percentile,
    calculate_percentiles,
    calculate_summary_stats,
)


class TestCalculatePercentile:
    """Tests for calculate_percentile function."""

    def test_median_odd_count(self):
        """Test median calculation with odd number of values."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_percentile(data, 50)
        assert result == 3.0

    def test_median_even_count(self):
        """Test median calculation with even number of values (interpolation)."""
        data = [1.0, 2.0, 3.0, 4.0]
        result = calculate_percentile(data, 50)
        assert result == 2.5

    def test_p0_minimum(self):
        """Test that P0 returns minimum value."""
        data = [5.0, 10.0, 15.0, 20.0, 25.0]
        result = calculate_percentile(data, 0)
        assert result == 5.0

    def test_p100_maximum(self):
        """Test that P100 returns maximum value."""
        data = [5.0, 10.0, 15.0, 20.0, 25.0]
        result = calculate_percentile(data, 100)
        assert result == 25.0

    def test_p25_first_quartile(self):
        """Test P25 calculation (first quartile)."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_percentile(data, 25)
        assert result == 2.0

    def test_p75_third_quartile(self):
        """Test P75 calculation (third quartile)."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_percentile(data, 75)
        assert result == 4.0

    def test_p85_interpolation(self):
        """Test P85 calculation with linear interpolation."""
        data = [5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0]
        result = calculate_percentile(data, 85)
        # P85 with 10 values: index = (10-1) * 0.85 = 7.65
        # Between index 7 (40.0) and 8 (45.0), interpolate 0.65 * (45-40) = 43.25
        assert result == pytest.approx(43.25)

    def test_p95_high_percentile(self):
        """Test P95 calculation for high percentile."""
        data = [5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0]
        result = calculate_percentile(data, 95)
        # P95 with 10 values: index = (10-1) * 0.95 = 8.55
        # Between index 8 (45.0) and 9 (50.0), interpolate 0.55 * (50-45) = 47.75
        assert result == pytest.approx(47.75)

    def test_unsorted_data(self):
        """Test that function handles unsorted data correctly."""
        data = [25.0, 5.0, 15.0, 20.0, 10.0]
        result = calculate_percentile(data, 50)
        assert result == 15.0

    def test_single_value(self):
        """Test percentile of single value returns that value."""
        data = [42.0]
        result = calculate_percentile(data, 50)
        assert result == 42.0

    def test_two_values_median(self):
        """Test median of two values (average)."""
        data = [10.0, 20.0]
        result = calculate_percentile(data, 50)
        assert result == 15.0

    def test_identical_values(self):
        """Test percentile with all identical values."""
        data = [7.0, 7.0, 7.0, 7.0, 7.0]
        result = calculate_percentile(data, 50)
        assert result == 7.0

    def test_negative_values(self):
        """Test percentile with negative numbers."""
        data = [-5.0, -3.0, -1.0, 1.0, 3.0, 5.0]
        result = calculate_percentile(data, 50)
        assert result == 0.0

    def test_floating_point_precision(self):
        """Test floating point calculation precision."""
        data = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        result = calculate_percentile(data, 50)
        assert result == pytest.approx(0.55, rel=1e-9)

    def test_large_dataset(self):
        """Test percentile with large dataset."""
        data = list(range(1000))
        result = calculate_percentile(data, 50)
        # Median of 0-999 should be around 499.5
        assert result == pytest.approx(499.5, rel=1e-6)

    def test_empty_data_raises_error(self):
        """Test that empty data raises ValueError."""
        with pytest.raises(ValueError, match="Cannot calculate percentile of empty data"):
            calculate_percentile([], 50)

    def test_percentile_below_zero_raises_error(self):
        """Test that percentile < 0 raises ValueError."""
        with pytest.raises(ValueError, match="Percentile must be 0-100"):
            calculate_percentile([1.0, 2.0, 3.0], -10)

    def test_percentile_above_100_raises_error(self):
        """Test that percentile > 100 raises ValueError."""
        with pytest.raises(ValueError, match="Percentile must be 0-100"):
            calculate_percentile([1.0, 2.0, 3.0], 150)

    def test_percentile_exactly_zero(self):
        """Test that percentile = 0 is valid."""
        data = [1.0, 2.0, 3.0]
        result = calculate_percentile(data, 0)
        assert result == 1.0

    def test_percentile_exactly_100(self):
        """Test that percentile = 100 is valid."""
        data = [1.0, 2.0, 3.0]
        result = calculate_percentile(data, 100)
        assert result == 3.0


class TestCalculatePercentiles:
    """Tests for calculate_percentiles function (batch calculation)."""

    def test_multiple_percentiles(self):
        """Test calculating multiple percentiles at once."""
        data = [5.0, 10.0, 15.0, 20.0, 25.0]
        result = calculate_percentiles(data, [25, 50, 75])
        assert result == {"p25": 10.0, "p50": 15.0, "p75": 20.0}

    def test_standard_percentiles(self):
        """Test standard percentiles (p50, p85, p95)."""
        data = [5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0]
        result = calculate_percentiles(data, [50, 85, 95])
        assert result["p50"] == pytest.approx(27.5)
        assert result["p85"] == pytest.approx(43.25)
        assert result["p95"] == pytest.approx(47.75)

    def test_single_percentile_batch(self):
        """Test calculating single percentile using batch function."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_percentiles(data, [50])
        assert result == {"p50": 3.0}

    def test_all_quartiles(self):
        """Test calculating all quartiles (P0, P25, P50, P75, P100)."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_percentiles(data, [0, 25, 50, 75, 100])
        assert result["p0"] == 1.0
        assert result["p25"] == 2.0
        assert result["p50"] == 3.0
        assert result["p75"] == 4.0
        assert result["p100"] == 5.0

    def test_empty_data_returns_zeros(self):
        """Test that empty data returns zero values."""
        result = calculate_percentiles([], [50, 85, 95])
        assert result == {"p50": 0.0, "p85": 0.0, "p95": 0.0}

    def test_empty_percentiles_list(self):
        """Test with empty percentiles list."""
        data = [1.0, 2.0, 3.0]
        result = calculate_percentiles(data, [])
        assert result == {}

    def test_invalid_percentile_in_batch(self):
        """Test that invalid percentile in batch raises ValueError."""
        with pytest.raises(ValueError, match="Percentile must be 0-100"):
            calculate_percentiles([1.0, 2.0, 3.0], [50, 150])

    def test_percentile_key_format(self):
        """Test that result keys are formatted correctly (p50, p85, etc)."""
        data = [1.0, 2.0, 3.0]
        result = calculate_percentiles(data, [50, 85, 95])
        assert "p50" in result
        assert "p85" in result
        assert "p95" in result

    def test_consistency_with_single_calculation(self):
        """Test that batch results match individual calculations."""
        data = [5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0]
        batch_result = calculate_percentiles(data, [50, 85, 95])
        p50_single = calculate_percentile(data, 50)
        p85_single = calculate_percentile(data, 85)
        p95_single = calculate_percentile(data, 95)

        assert batch_result["p50"] == p50_single
        assert batch_result["p85"] == p85_single
        assert batch_result["p95"] == p95_single


class TestCalculateSummaryStats:
    """Tests for calculate_summary_stats function."""

    def test_complete_summary(self):
        """Test complete summary statistics calculation."""
        data = [5.0, 10.0, 15.0, 20.0, 25.0]
        result = calculate_summary_stats(data)

        assert result["min"] == 5.0
        assert result["max"] == 25.0
        assert result["mean"] == 15.0
        assert result["p50"] == 15.0
        # P85 with 5 values: index = (5-1) * 0.85 = 3.4
        # Between index 3 (20.0) and 4 (25.0), interpolate 0.4 * (25-20) = 22.0
        assert result["p85"] == 22.0
        # P95 with 5 values: index = (5-1) * 0.95 = 3.8
        # Between index 3 (20.0) and 4 (25.0), interpolate 0.8 * (25-20) = 24.0
        assert result["p95"] == 24.0
        assert result["count"] == 5

    def test_summary_all_keys_present(self):
        """Test that all expected keys are present in summary."""
        data = [1.0, 2.0, 3.0]
        result = calculate_summary_stats(data)

        expected_keys = {"min", "max", "mean", "p50", "p85", "p95", "count"}
        assert set(result.keys()) == expected_keys

    def test_empty_data_summary(self):
        """Test summary statistics for empty data."""
        result = calculate_summary_stats([])

        assert result["min"] == 0.0
        assert result["max"] == 0.0
        assert result["mean"] == 0.0
        assert result["p50"] == 0.0
        assert result["p85"] == 0.0
        assert result["p95"] == 0.0
        assert result["count"] == 0

    def test_single_value_summary(self):
        """Test summary statistics for single value."""
        result = calculate_summary_stats([42.0])

        assert result["min"] == 42.0
        assert result["max"] == 42.0
        assert result["mean"] == 42.0
        assert result["p50"] == 42.0
        assert result["p85"] == 42.0
        assert result["p95"] == 42.0
        assert result["count"] == 1

    def test_identical_values_summary(self):
        """Test summary statistics for identical values."""
        result = calculate_summary_stats([7.0, 7.0, 7.0, 7.0, 7.0])

        assert result["min"] == 7.0
        assert result["max"] == 7.0
        assert result["mean"] == 7.0
        assert result["p50"] == 7.0
        assert result["p85"] == 7.0
        assert result["p95"] == 7.0
        assert result["count"] == 5

    def test_mean_calculation(self):
        """Test that mean is calculated correctly."""
        data = [2.0, 4.0, 6.0, 8.0, 10.0]
        result = calculate_summary_stats(data)
        assert result["mean"] == 6.0

    def test_min_max_with_outliers(self):
        """Test min/max with outlier values."""
        data = [1.0, 10.0, 10.0, 10.0, 100.0]
        result = calculate_summary_stats(data)
        assert result["min"] == 1.0
        assert result["max"] == 100.0

    def test_negative_values_summary(self):
        """Test summary statistics with negative values."""
        data = [-10.0, -5.0, 0.0, 5.0, 10.0]
        result = calculate_summary_stats(data)
        assert result["min"] == -10.0
        assert result["max"] == 10.0
        assert result["mean"] == 0.0
        assert result["p50"] == 0.0

    def test_floating_point_mean(self):
        """Test mean with floating point precision."""
        data = [0.1, 0.2, 0.3, 0.4, 0.5]
        result = calculate_summary_stats(data)
        assert result["mean"] == pytest.approx(0.3, rel=1e-9)

    def test_large_dataset_summary(self):
        """Test summary statistics with large dataset."""
        data = list(range(1000))
        result = calculate_summary_stats(data)
        assert result["min"] == 0.0
        assert result["max"] == 999.0
        assert result["mean"] == pytest.approx(499.5, rel=1e-6)
        assert result["count"] == 1000


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_large_numbers(self):
        """Test percentile with very large numbers."""
        data = [1e10, 2e10, 3e10, 4e10, 5e10]
        result = calculate_percentile(data, 50)
        assert result == 3e10

    def test_very_small_numbers(self):
        """Test percentile with very small numbers."""
        data = [1e-10, 2e-10, 3e-10, 4e-10, 5e-10]
        result = calculate_percentile(data, 50)
        assert result == pytest.approx(3e-10, rel=1e-6)

    def test_mixed_magnitude_values(self):
        """Test percentile with values of different magnitudes."""
        data = [0.001, 10.0, 1000.0]
        result = calculate_percentile(data, 50)
        assert result == 10.0

    def test_duplicate_values(self):
        """Test percentile with many duplicate values."""
        data = [1.0, 1.0, 1.0, 2.0, 3.0, 3.0, 3.0]
        result = calculate_percentile(data, 50)
        assert result == 2.0

    def test_near_zero_percentile(self):
        """Test with very small percentile value."""
        data = list(range(100))
        result = calculate_percentile(data, 0.5)
        # P0.5 with 100 values: index = 99 * 0.005 = 0.495
        assert result == pytest.approx(0.495, rel=1e-6)

    def test_near_100_percentile(self):
        """Test with percentile very close to 100."""
        data = list(range(100))
        result = calculate_percentile(data, 99.5)
        # P99.5 with 100 values: index = 99 * 0.995 = 98.505
        assert result == pytest.approx(98.505, rel=1e-6)

    def test_integer_list_input(self):
        """Test that function works with integer input (converts to float)."""
        data = [1, 2, 3, 4, 5]
        result = calculate_percentile(data, 50)
        assert result == 3.0
        assert isinstance(result, float)

    def test_mixed_int_float_input(self):
        """Test with mixed integer and float values."""
        data = [1, 2.5, 3, 4.5, 5]
        result = calculate_percentile(data, 50)
        assert result == 3.0

    def test_tuple_input(self):
        """Test that function accepts tuple input (Sequence)."""
        data = (1.0, 2.0, 3.0, 4.0, 5.0)
        result = calculate_percentile(data, 50)
        assert result == 3.0

    def test_percentile_decimal_precision(self):
        """Test percentile with decimal precision in input."""
        data = [50.123, 85.456, 95.789]
        result = calculate_percentiles(data, [50, 85, 95])
        assert "p50" in result
        assert "p85" in result
        assert "p95" in result


class TestRealWorldScenarios:
    """Tests simulating real-world usage scenarios."""

    def test_lead_time_metrics(self):
        """Test percentiles for lead time data (days)."""
        lead_times = [0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0, 34.0]
        stats = calculate_summary_stats(lead_times)

        assert stats["p50"] < stats["p85"] < stats["p95"]
        assert stats["min"] == 0.5
        assert stats["max"] == 34.0
        assert stats["count"] == 9

    def test_deployment_frequency_metrics(self):
        """Test percentiles for deployment frequency (deploys per day)."""
        frequencies = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 10.0]
        result = calculate_percentiles(frequencies, [50, 85, 95])

        assert result["p50"] == 2.0
        assert result["p85"] > result["p50"]
        assert result["p95"] > result["p85"]

    def test_quality_score_distribution(self):
        """Test percentiles for quality scores (0-100)."""
        scores = [45.0, 60.0, 70.0, 75.0, 80.0, 85.0, 90.0, 95.0, 98.0, 100.0]
        stats = calculate_summary_stats(scores)

        assert stats["min"] == 45.0
        assert stats["max"] == 100.0
        assert 70 < stats["p50"] < 85
        assert stats["mean"] == pytest.approx(79.8, rel=1e-6)

    def test_response_time_percentiles(self):
        """Test percentiles for response times (milliseconds)."""
        response_times = [50, 100, 150, 200, 250, 300, 400, 500, 1000, 5000]
        result = calculate_percentiles(response_times, [50, 90, 95, 99])

        # P50 should be low (most requests fast)
        # P95/P99 should be higher (tail latency)
        assert result["p50"] < result["p90"] < result["p95"] < result["p99"]

    def test_zero_values_in_dataset(self):
        """Test handling of zero values in real data."""
        data = [0.0, 0.0, 1.0, 2.0, 3.0, 5.0, 10.0]
        result = calculate_summary_stats(data)

        assert result["min"] == 0.0
        assert result["mean"] == pytest.approx(3.0, rel=1e-6)
        assert result["p50"] == 2.0
