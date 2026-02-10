"""
Tests for data_processor module.

Tests data filtering, calculation, and transformation logic for AI usage data.
"""

import pandas as pd
import pytest

from execution.reports.usage_tables.data_processor import (
    calculate_summary_stats,
    filter_by_access_status,
    filter_by_usage_threshold,
    filter_team_users,
    get_usage_intensity_distribution,
    normalize_access_column_value,
    prepare_claude_data,
    prepare_devin_data,
)


@pytest.fixture
def sample_usage_data():
    """Sample AI usage data for testing."""
    return pd.DataFrame(
        {
            "Name": ["Alice Smith", "Bob Jones", "Charlie Davis", "Diana Prince", "Eve Adams"],
            "Job Title": ["Engineer", "Manager", "Analyst", "Director", "Engineer"],
            "Software Company": ["TARGET_TEAM", "TARGET_TEAM", "OTHER_TEAM", "TARGET_TEAM", "TARGET_TEAM"],
            "Claude Access": ["YES", "NO", "YES", "1", "0"],
            "Claude 30 day usage": [150.0, 0.0, 75.0, 25.0, 5.0],
            "Devin Access": ["YES", "YES", "NO", "1.0", "NO"],
            "Devin_30d": [200.0, 10.0, 0.0, 120.0, 15.0],
        }
    )


@pytest.fixture
def sample_claude_prepared():
    """Expected Claude data after preparation (sorted by usage)."""
    return pd.DataFrame(
        {
            "Name": ["Alice Smith", "Diana Prince", "Eve Adams", "Bob Jones"],
            "Job Title": ["Engineer", "Director", "Engineer", "Manager"],
            "Claude Access": ["YES", "1", "0", "NO"],
            "Claude 30 day usage": [150.0, 25.0, 5.0, 0.0],
        }
    ).reset_index(drop=True)


@pytest.fixture
def sample_devin_prepared():
    """Expected Devin data after preparation (sorted by usage)."""
    return pd.DataFrame(
        {
            "Name": ["Alice Smith", "Diana Prince", "Eve Adams", "Bob Jones"],
            "Job Title": ["Engineer", "Director", "Engineer", "Manager"],
            "Devin Access": ["YES", "1.0", "NO", "YES"],
            "Devin_30d": [200.0, 120.0, 15.0, 10.0],
        }
    ).reset_index(drop=True)


class TestFilterTeamUsers:
    """Tests for filter_team_users function."""

    def test_filter_target_team(self, sample_usage_data):
        """Test filtering for target team returns correct users."""
        result = filter_team_users(sample_usage_data, "TARGET_TEAM")

        assert len(result) == 4
        assert set(result["Name"]) == {"Alice Smith", "Bob Jones", "Diana Prince", "Eve Adams"}

    def test_filter_case_insensitive(self, sample_usage_data):
        """Test that team filtering is case-insensitive."""
        result_upper = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result_lower = filter_team_users(sample_usage_data, "target_team")
        result_mixed = filter_team_users(sample_usage_data, "TaRgEt_TeAm")

        assert len(result_upper) == len(result_lower) == len(result_mixed) == 4

    def test_filter_other_team(self, sample_usage_data):
        """Test filtering for other team returns correct users."""
        result = filter_team_users(sample_usage_data, "OTHER_TEAM")

        assert len(result) == 1
        assert result["Name"].iloc[0] == "Charlie Davis"

    def test_filter_nonexistent_team(self, sample_usage_data):
        """Test that filtering for nonexistent team raises ValueError."""
        with pytest.raises(ValueError, match="No NONEXISTENT users found"):
            filter_team_users(sample_usage_data, "NONEXISTENT")

    def test_filter_empty_dataframe(self):
        """Test filtering an empty DataFrame raises ValueError."""
        empty_df = pd.DataFrame(columns=["Name", "Software Company"])

        with pytest.raises(ValueError):
            filter_team_users(empty_df, "TARGET_TEAM")


class TestPrepareClaudeData:
    """Tests for prepare_claude_data function."""

    def test_prepare_claude_basic(self, sample_usage_data, sample_claude_prepared):
        """Test preparing Claude data returns correct columns and order."""
        filtered_data = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = prepare_claude_data(filtered_data)

        pd.testing.assert_frame_equal(result, sample_claude_prepared)

    def test_prepare_claude_sorted_descending(self, sample_usage_data):
        """Test that Claude data is sorted by usage in descending order."""
        filtered_data = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = prepare_claude_data(filtered_data)

        usage_values = result["Claude 30 day usage"].tolist()
        assert usage_values == sorted(usage_values, reverse=True)

    def test_prepare_claude_index_reset(self, sample_usage_data):
        """Test that index is reset after sorting."""
        filtered_data = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = prepare_claude_data(filtered_data)

        assert result.index.tolist() == list(range(len(result)))

    def test_prepare_claude_columns(self, sample_usage_data):
        """Test that only required columns are included."""
        filtered_data = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = prepare_claude_data(filtered_data)

        expected_columns = ["Name", "Job Title", "Claude Access", "Claude 30 day usage"]
        assert result.columns.tolist() == expected_columns


class TestPrepareDevinData:
    """Tests for prepare_devin_data function."""

    def test_prepare_devin_basic(self, sample_usage_data, sample_devin_prepared):
        """Test preparing Devin data returns correct columns and order."""
        filtered_data = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = prepare_devin_data(filtered_data)

        pd.testing.assert_frame_equal(result, sample_devin_prepared)

    def test_prepare_devin_sorted_descending(self, sample_usage_data):
        """Test that Devin data is sorted by usage in descending order."""
        filtered_data = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = prepare_devin_data(filtered_data)

        usage_values = result["Devin_30d"].tolist()
        assert usage_values == sorted(usage_values, reverse=True)

    def test_prepare_devin_index_reset(self, sample_usage_data):
        """Test that index is reset after sorting."""
        filtered_data = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = prepare_devin_data(filtered_data)

        assert result.index.tolist() == list(range(len(result)))

    def test_prepare_devin_columns(self, sample_usage_data):
        """Test that only required columns are included."""
        filtered_data = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = prepare_devin_data(filtered_data)

        expected_columns = ["Name", "Job Title", "Devin Access", "Devin_30d"]
        assert result.columns.tolist() == expected_columns


class TestCalculateSummaryStats:
    """Tests for calculate_summary_stats function."""

    def test_summary_stats_basic(self, sample_usage_data):
        """Test calculating summary statistics."""
        filtered_data = filter_team_users(sample_usage_data, "TARGET_TEAM")
        claude_df = prepare_claude_data(filtered_data)
        devin_df = prepare_devin_data(filtered_data)

        result = calculate_summary_stats(claude_df, devin_df)

        assert result["total_users"] == 4
        assert result["claude_active_users"] == 3  # Alice, Diana, Eve (usage > 0)
        assert result["devin_active_users"] == 4  # All have usage > 0
        assert result["avg_claude_usage"] == pytest.approx(45.0)  # (150 + 25 + 5 + 0) / 4
        assert result["avg_devin_usage"] == pytest.approx(86.25)  # (200 + 120 + 15 + 10) / 4

    def test_summary_stats_all_zero_usage(self):
        """Test summary stats with all zero usage."""
        df = pd.DataFrame(
            {
                "Name": ["User1", "User2"],
                "Job Title": ["Engineer", "Manager"],
                "Claude Access": ["YES", "YES"],
                "Claude 30 day usage": [0.0, 0.0],
                "Devin Access": ["YES", "YES"],
                "Devin_30d": [0.0, 0.0],
            }
        )

        result = calculate_summary_stats(df, df)

        assert result["total_users"] == 2
        assert result["claude_active_users"] == 0
        assert result["devin_active_users"] == 0
        assert result["avg_claude_usage"] == 0.0
        assert result["avg_devin_usage"] == 0.0

    def test_summary_stats_single_user(self):
        """Test summary stats with single user."""
        df = pd.DataFrame(
            {
                "Name": ["Solo User"],
                "Job Title": ["Engineer"],
                "Claude Access": ["YES"],
                "Claude 30 day usage": [100.0],
                "Devin Access": ["YES"],
                "Devin_30d": [50.0],
            }
        )

        result = calculate_summary_stats(df, df)

        assert result["total_users"] == 1
        assert result["claude_active_users"] == 1
        assert result["devin_active_users"] == 1
        assert result["avg_claude_usage"] == 100.0
        assert result["avg_devin_usage"] == 50.0


class TestNormalizeAccessColumnValue:
    """Tests for normalize_access_column_value function."""

    def test_normalize_yes_values(self):
        """Test that various 'yes' formats normalize to 'Yes'."""
        assert normalize_access_column_value("YES") == "Yes"
        assert normalize_access_column_value("yes") == "Yes"
        assert normalize_access_column_value("Yes") == "Yes"
        assert normalize_access_column_value("1") == "Yes"
        assert normalize_access_column_value("1.0") == "Yes"
        assert normalize_access_column_value(1) == "Yes"
        assert normalize_access_column_value(1.0) == "Yes"

    def test_normalize_no_values(self):
        """Test that various 'no' formats normalize to 'No'."""
        assert normalize_access_column_value("NO") == "No"
        assert normalize_access_column_value("no") == "No"
        assert normalize_access_column_value("No") == "No"
        assert normalize_access_column_value("0") == "No"
        assert normalize_access_column_value("0.0") == "No"
        assert normalize_access_column_value(0) == "No"
        assert normalize_access_column_value(0.0) == "No"

    def test_normalize_missing_values(self):
        """Test that missing values normalize to 'No'."""
        assert normalize_access_column_value(None) == "No"
        assert normalize_access_column_value("") == "No"
        assert normalize_access_column_value("   ") == "No"
        assert normalize_access_column_value(pd.NA) == "No"

    def test_normalize_unexpected_values(self):
        """Test that unexpected values normalize to 'No'."""
        assert normalize_access_column_value("MAYBE") == "No"
        assert normalize_access_column_value("2") == "No"
        assert normalize_access_column_value("NaN") == "No"


class TestFilterByAccessStatus:
    """Tests for filter_by_access_status function."""

    def test_filter_with_access(self, sample_usage_data):
        """Test filtering users with access."""
        filtered_team = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = filter_by_access_status(filtered_team, "Claude Access", has_access=True)

        assert len(result) == 2
        assert set(result["Name"]) == {"Alice Smith", "Diana Prince"}

    def test_filter_without_access(self, sample_usage_data):
        """Test filtering users without access."""
        filtered_team = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = filter_by_access_status(filtered_team, "Claude Access", has_access=False)

        assert len(result) == 2
        assert set(result["Name"]) == {"Bob Jones", "Eve Adams"}

    def test_filter_devin_access(self, sample_usage_data):
        """Test filtering Devin access."""
        filtered_team = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = filter_by_access_status(filtered_team, "Devin Access", has_access=True)

        assert len(result) == 3
        assert set(result["Name"]) == {"Alice Smith", "Bob Jones", "Diana Prince"}


class TestFilterByUsageThreshold:
    """Tests for filter_by_usage_threshold function."""

    def test_filter_high_usage(self, sample_usage_data):
        """Test filtering users with high usage (>= 100)."""
        filtered_team = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = filter_by_usage_threshold(filtered_team, "Claude 30 day usage", min_usage=100.0)

        assert len(result) == 1
        assert result["Name"].iloc[0] == "Alice Smith"

    def test_filter_medium_usage(self, sample_usage_data):
        """Test filtering users with medium usage (20-100)."""
        filtered_team = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = filter_by_usage_threshold(filtered_team, "Claude 30 day usage", min_usage=20.0, max_usage=100.0)

        assert len(result) == 1
        assert result["Name"].iloc[0] == "Diana Prince"

    def test_filter_low_usage(self, sample_usage_data):
        """Test filtering users with low usage (< 20)."""
        filtered_team = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = filter_by_usage_threshold(filtered_team, "Claude 30 day usage", min_usage=0.0, max_usage=20.0)

        assert len(result) == 2
        assert set(result["Name"]) == {"Bob Jones", "Eve Adams"}

    def test_filter_zero_usage(self, sample_usage_data):
        """Test filtering users with zero usage."""
        filtered_team = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = filter_by_usage_threshold(filtered_team, "Claude 30 day usage", min_usage=0.0, max_usage=0.1)

        assert len(result) == 1
        assert result["Name"].iloc[0] == "Bob Jones"

    def test_filter_devin_usage(self, sample_usage_data):
        """Test filtering Devin usage."""
        filtered_team = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = filter_by_usage_threshold(filtered_team, "Devin_30d", min_usage=100.0)

        assert len(result) == 2
        assert set(result["Name"]) == {"Alice Smith", "Diana Prince"}


class TestGetUsageIntensityDistribution:
    """Tests for get_usage_intensity_distribution function."""

    def test_distribution_claude(self, sample_usage_data):
        """Test calculating usage intensity distribution for Claude."""
        filtered_team = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = get_usage_intensity_distribution(filtered_team, "Claude 30 day usage")

        assert result["low"] == 2  # Bob (0), Eve (5)
        assert result["medium"] == 1  # Diana (25)
        assert result["high"] == 1  # Alice (150)

    def test_distribution_devin(self, sample_usage_data):
        """Test calculating usage intensity distribution for Devin."""
        filtered_team = filter_team_users(sample_usage_data, "TARGET_TEAM")
        result = get_usage_intensity_distribution(filtered_team, "Devin_30d")

        assert result["low"] == 2  # Bob (10), Eve (15)
        assert result["medium"] == 0
        assert result["high"] == 2  # Alice (200), Diana (120)

    def test_distribution_all_low(self):
        """Test distribution with all low usage."""
        df = pd.DataFrame(
            {
                "Name": ["User1", "User2", "User3"],
                "Usage": [0.0, 5.0, 19.0],
            }
        )

        result = get_usage_intensity_distribution(df, "Usage")

        assert result["low"] == 3
        assert result["medium"] == 0
        assert result["high"] == 0

    def test_distribution_all_high(self):
        """Test distribution with all high usage."""
        df = pd.DataFrame(
            {
                "Name": ["User1", "User2", "User3"],
                "Usage": [100.0, 150.0, 200.0],
            }
        )

        result = get_usage_intensity_distribution(df, "Usage")

        assert result["low"] == 0
        assert result["medium"] == 0
        assert result["high"] == 3

    def test_distribution_boundary_values(self):
        """Test distribution with boundary values."""
        df = pd.DataFrame(
            {
                "Name": ["User1", "User2", "User3", "User4"],
                "Usage": [19.9, 20.0, 99.9, 100.0],
            }
        )

        result = get_usage_intensity_distribution(df, "Usage")

        assert result["low"] == 1  # 19.9
        assert result["medium"] == 2  # 20.0, 99.9
        assert result["high"] == 1  # 100.0
