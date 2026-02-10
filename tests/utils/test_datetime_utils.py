#!/usr/bin/env python3
"""
Tests for datetime_utils module

Tests datetime parsing and calculation functions used across collectors.
"""

from datetime import UTC, datetime, timezone

import pytest

from execution.utils.datetime_utils import (
    calculate_age_days,
    calculate_lead_time_days,
    parse_ado_timestamp,
    parse_iso_timestamp,
)


class TestParseAdoTimestamp:
    """Tests for parse_ado_timestamp function."""

    def test_valid_timestamp_with_z_suffix(self):
        """Test parsing valid ADO timestamp with Z suffix."""
        result = parse_ado_timestamp("2026-02-10T10:00:00Z")
        assert result == datetime(2026, 2, 10, 10, 0, 0, tzinfo=UTC)

    def test_valid_timestamp_with_microseconds(self):
        """Test parsing timestamp with microseconds."""
        result = parse_ado_timestamp("2026-02-10T10:00:00.123456Z")
        assert result == datetime(2026, 2, 10, 10, 0, 0, 123456, tzinfo=UTC)

    def test_valid_timestamp_without_z_suffix(self):
        """Test parsing timestamp with explicit UTC offset."""
        result = parse_ado_timestamp("2026-02-10T10:00:00+00:00")
        assert result == datetime(2026, 2, 10, 10, 0, 0, tzinfo=UTC)

    def test_none_input(self):
        """Test that None input returns None."""
        result = parse_ado_timestamp(None)
        assert result is None

    def test_empty_string(self):
        """Test that empty string returns None."""
        result = parse_ado_timestamp("")
        assert result is None

    def test_invalid_format(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            parse_ado_timestamp("not-a-timestamp")

    def test_invalid_type(self):
        """Test that non-string input raises ValueError."""
        with pytest.raises(ValueError, match="Timestamp must be a string"):
            parse_ado_timestamp(12345)  # type: ignore

    def test_date_only_timestamp(self):
        """Test that date-only format is valid."""
        result = parse_ado_timestamp("2026-02-10")
        assert result == datetime(2026, 2, 10, 0, 0, 0)


class TestCalculateLeadTimeDays:
    """Tests for calculate_lead_time_days function."""

    def test_valid_lead_time_whole_days(self):
        """Test calculating lead time for whole days."""
        created = "2026-02-01T10:00:00Z"
        closed = "2026-02-10T10:00:00Z"
        result = calculate_lead_time_days(created, closed)
        assert result == 9.0

    def test_valid_lead_time_fractional_days(self):
        """Test calculating fractional lead time (half day)."""
        created = "2026-02-10T10:00:00Z"
        closed = "2026-02-10T22:00:00Z"
        result = calculate_lead_time_days(created, closed)
        assert result == 0.5

    def test_valid_lead_time_with_microseconds(self):
        """Test lead time calculation with microsecond precision."""
        created = "2026-02-10T10:00:00.000000Z"
        closed = "2026-02-11T10:00:00.000000Z"
        result = calculate_lead_time_days(created, closed)
        assert result == 1.0

    def test_same_timestamp(self):
        """Test lead time of zero when created and closed are same."""
        timestamp = "2026-02-10T10:00:00Z"
        result = calculate_lead_time_days(timestamp, timestamp)
        assert result == 0.0

    def test_none_created(self):
        """Test that None created timestamp returns None."""
        result = calculate_lead_time_days(None, "2026-02-10T10:00:00Z")
        assert result is None

    def test_none_closed(self):
        """Test that None closed timestamp returns None."""
        result = calculate_lead_time_days("2026-02-10T10:00:00Z", None)
        assert result is None

    def test_both_none(self):
        """Test that both None returns None."""
        result = calculate_lead_time_days(None, None)
        assert result is None

    def test_negative_lead_time(self):
        """Test that negative lead time (closed before created) returns None."""
        created = "2026-02-10T10:00:00Z"
        closed = "2026-02-01T10:00:00Z"  # Earlier than created
        result = calculate_lead_time_days(created, closed)
        assert result is None

    def test_invalid_created_format(self):
        """Test that invalid created format returns None."""
        result = calculate_lead_time_days("invalid", "2026-02-10T10:00:00Z")
        assert result is None

    def test_invalid_closed_format(self):
        """Test that invalid closed format returns None."""
        result = calculate_lead_time_days("2026-02-10T10:00:00Z", "invalid")
        assert result is None

    def test_very_long_lead_time(self):
        """Test calculating lead time spanning years."""
        created = "2020-01-01T00:00:00Z"
        closed = "2026-02-10T00:00:00Z"
        result = calculate_lead_time_days(created, closed)
        # 6 years + 1 month + 9 days (accounting for leap years)
        assert result is not None
        assert result > 2200  # Approximately 6 years


class TestCalculateAgeDays:
    """Tests for calculate_age_days function."""

    def test_age_with_explicit_reference(self):
        """Test calculating age with explicit reference time."""
        created = "2026-02-01T10:00:00Z"
        reference = datetime(2026, 2, 10, 10, 0, 0, tzinfo=UTC)
        result = calculate_age_days(created, reference_time=reference)
        assert result == 9.0

    def test_age_fractional_days(self):
        """Test calculating fractional age (12 hours = 0.5 days)."""
        created = "2026-02-10T10:00:00Z"
        reference = datetime(2026, 2, 10, 22, 0, 0, tzinfo=UTC)
        result = calculate_age_days(created, reference_time=reference)
        assert result == 0.5

    def test_age_same_time(self):
        """Test age of zero when created and reference are same."""
        created = "2026-02-10T10:00:00Z"
        reference = datetime(2026, 2, 10, 10, 0, 0, tzinfo=UTC)
        result = calculate_age_days(created, reference_time=reference)
        assert result == 0.0

    def test_none_created(self):
        """Test that None created timestamp returns None."""
        result = calculate_age_days(None)
        assert result is None

    def test_negative_age(self):
        """Test that negative age (created in future) returns None."""
        created = "2026-02-10T10:00:00Z"
        reference = datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC)  # Earlier
        result = calculate_age_days(created, reference_time=reference)
        assert result is None

    def test_invalid_created_format(self):
        """Test that invalid format returns None."""
        result = calculate_age_days("invalid-timestamp")
        assert result is None

    def test_age_with_naive_reference_time(self):
        """Test that naive reference time is treated as UTC."""
        created = "2026-02-01T10:00:00Z"
        reference = datetime(2026, 2, 10, 10, 0, 0)  # Naive datetime
        result = calculate_age_days(created, reference_time=reference)
        assert result == 9.0

    def test_age_default_reference_time(self):
        """Test calculating age with default reference time (now)."""
        # Create timestamp from 1 day ago using timedelta
        from datetime import timedelta

        one_day_ago = datetime.now(UTC) - timedelta(days=1)
        created = one_day_ago.strftime("%Y-%m-%dT%H:%M:%SZ")

        result = calculate_age_days(created)
        assert result is not None
        # Should be approximately 1 day (allow some tolerance for test execution time)
        assert 0.99 < result < 1.01


class TestParseIsoTimestamp:
    """Tests for parse_iso_timestamp function (generic ISO parser)."""

    def test_iso_with_z_suffix(self):
        """Test parsing ISO timestamp with Z suffix."""
        result = parse_iso_timestamp("2026-02-10T10:00:00Z")
        assert result == datetime(2026, 2, 10, 10, 0, 0, tzinfo=UTC)

    def test_iso_with_explicit_utc(self):
        """Test parsing ISO timestamp with explicit UTC offset."""
        result = parse_iso_timestamp("2026-02-10T10:00:00+00:00")
        assert result == datetime(2026, 2, 10, 10, 0, 0, tzinfo=UTC)

    def test_iso_with_timezone_offset(self):
        """Test parsing ISO timestamp with non-UTC timezone."""
        result = parse_iso_timestamp("2026-02-10T10:00:00-05:00")
        assert result is not None
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 10

    def test_iso_date_only(self):
        """Test parsing date-only ISO format."""
        result = parse_iso_timestamp("2026-02-10")
        assert result == datetime(2026, 2, 10, 0, 0, 0)

    def test_iso_naive_datetime(self):
        """Test parsing naive datetime (no timezone)."""
        result = parse_iso_timestamp("2026-02-10T10:00:00")
        assert result == datetime(2026, 2, 10, 10, 0, 0)
        assert result.tzinfo is None

    def test_none_input(self):
        """Test that None input returns None."""
        result = parse_iso_timestamp(None)
        assert result is None

    def test_empty_string(self):
        """Test that empty string returns None."""
        result = parse_iso_timestamp("")
        assert result is None

    def test_invalid_format(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid ISO timestamp format"):
            parse_iso_timestamp("not-a-timestamp")

    def test_invalid_type(self):
        """Test that non-string input raises ValueError."""
        with pytest.raises(ValueError, match="Timestamp must be a string"):
            parse_iso_timestamp(12345)  # type: ignore


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_leap_year_timestamp(self):
        """Test parsing leap year date (Feb 29)."""
        result = parse_ado_timestamp("2024-02-29T10:00:00Z")
        assert result == datetime(2024, 2, 29, 10, 0, 0, tzinfo=UTC)

    def test_year_boundary_lead_time(self):
        """Test lead time calculation across year boundary."""
        created = "2025-12-31T23:00:00Z"
        closed = "2026-01-01T01:00:00Z"
        result = calculate_lead_time_days(created, closed)
        assert result is not None
        # 2 hours = 2/24 = 0.0833... days
        assert 0.08 < result < 0.09

    def test_dst_boundary(self):
        """Test timestamps around DST boundary (UTC should be unaffected)."""
        # March DST change (UTC timestamps should be stable)
        created = "2026-03-08T01:00:00Z"
        closed = "2026-03-08T03:00:00Z"
        result = calculate_lead_time_days(created, closed)
        assert result is not None
        # 2 hours = 2/24 = 0.0833... days
        assert 0.08 < result < 0.09

    def test_very_old_timestamp(self):
        """Test parsing very old timestamp (year 2000)."""
        result = parse_ado_timestamp("2000-01-01T00:00:00Z")
        assert result == datetime(2000, 1, 1, 0, 0, 0, tzinfo=UTC)

    def test_future_timestamp(self):
        """Test parsing future timestamp (year 2099)."""
        result = parse_ado_timestamp("2099-12-31T23:59:59Z")
        assert result == datetime(2099, 12, 31, 23, 59, 59, tzinfo=UTC)
