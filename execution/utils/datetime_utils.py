#!/usr/bin/env python3
"""
Datetime Utility Functions

Centralized datetime parsing and calculation functions to eliminate duplication
across collectors and dashboards.

Handles common patterns:
- Azure DevOps ISO timestamps with 'Z' suffix
- ArmorCode API timestamps
- Lead time calculations between dates
- Age calculations from creation to now
"""

from datetime import UTC, datetime, timezone


def parse_ado_timestamp(timestamp_str: str | None) -> datetime | None:
    """
    Parse Azure DevOps ISO timestamp with 'Z' suffix to datetime object.

    Azure DevOps returns timestamps in ISO format with 'Z' suffix indicating UTC:
    Example: "2026-02-10T10:00:00Z" or "2026-02-10T10:00:00.123456Z"

    Args:
        timestamp_str: ISO timestamp string with 'Z' suffix, or None

    Returns:
        datetime object in UTC, or None if input is None

    Raises:
        ValueError: If timestamp format is invalid or cannot be parsed

    Examples:
        >>> parse_ado_timestamp("2026-02-10T10:00:00Z")
        datetime.datetime(2026, 2, 10, 10, 0, tzinfo=datetime.timezone.utc)

        >>> parse_ado_timestamp(None)
        None
    """
    if not timestamp_str:
        return None

    if not isinstance(timestamp_str, str):
        raise ValueError(f"Timestamp must be a string, got {type(timestamp_str)}")

    try:
        # Replace 'Z' with '+00:00' for ISO format compatibility
        normalized = timestamp_str.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid timestamp format: {timestamp_str}") from e


def calculate_lead_time_days(created: str | None, closed: str | None) -> float | None:
    """
    Calculate lead time in days between creation and closure timestamps.

    Used for flow metrics like:
    - Work item lead time (created -> closed)
    - PR merge time (created -> merged)
    - Build completion time (queued -> finished)

    Args:
        created: ISO timestamp string when item was created
        closed: ISO timestamp string when item was closed/completed

    Returns:
        Lead time in days (fractional), or None if either timestamp is missing
        Returns None if lead time is negative (invalid data)

    Raises:
        ValueError: If timestamp formats are invalid

    Examples:
        >>> calculate_lead_time_days("2026-02-01T10:00:00Z", "2026-02-10T10:00:00Z")
        9.0

        >>> calculate_lead_time_days("2026-02-10T10:00:00Z", "2026-02-10T22:00:00Z")
        0.5

        >>> calculate_lead_time_days(None, "2026-02-10T10:00:00Z")
        None
    """
    if not created or not closed:
        return None

    try:
        created_dt = parse_ado_timestamp(created)
        closed_dt = parse_ado_timestamp(closed)

        if created_dt is None or closed_dt is None:
            return None

        # Calculate delta in days
        delta = closed_dt - created_dt
        lead_time_days = delta.total_seconds() / 86400  # 86400 seconds per day

        # Sanity check - negative lead times indicate data quality issues
        if lead_time_days < 0:
            return None

        return lead_time_days

    except ValueError:
        # Invalid timestamp format - return None to skip this item
        return None


def calculate_age_days(created: str | None, reference_time: datetime | None = None) -> float | None:
    """
    Calculate age in days from creation timestamp to reference time (default: now).

    Used for metrics like:
    - Aging work items (created -> now)
    - Time since last update (updated -> now)
    - Bug age distribution

    Args:
        created: ISO timestamp string when item was created
        reference_time: Reference datetime for age calculation (default: now in UTC)

    Returns:
        Age in days (fractional), or None if created timestamp is missing
        Returns None if age is negative (invalid data - created in future)

    Raises:
        ValueError: If timestamp format is invalid

    Examples:
        >>> ref = datetime(2026, 2, 10, 10, 0, 0, tzinfo=timezone.utc)
        >>> calculate_age_days("2026-02-01T10:00:00Z", reference_time=ref)
        9.0

        >>> calculate_age_days(None)
        None
    """
    if not created:
        return None

    try:
        created_dt = parse_ado_timestamp(created)

        if created_dt is None:
            return None

        # Default to now if no reference time provided
        if reference_time is None:
            reference_time = datetime.now(UTC)

        # Ensure reference_time is timezone-aware
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=UTC)

        # Calculate delta in days
        delta = reference_time - created_dt
        age_days = delta.total_seconds() / 86400

        # Sanity check - negative ages indicate data quality issues
        if age_days < 0:
            return None

        return age_days

    except ValueError:
        # Invalid timestamp format - return None to skip this item
        return None


def parse_iso_timestamp(timestamp_str: str | None) -> datetime | None:
    """
    Parse generic ISO 8601 timestamp (with or without 'Z' suffix).

    More flexible than parse_ado_timestamp() - handles various ISO formats:
    - "2026-02-10T10:00:00Z" (UTC with Z)
    - "2026-02-10T10:00:00+00:00" (UTC explicit)
    - "2026-02-10T10:00:00" (naive datetime)
    - "2026-02-10" (date only)

    Args:
        timestamp_str: ISO 8601 timestamp string, or None

    Returns:
        datetime object (timezone-aware if specified), or None if input is None

    Raises:
        ValueError: If timestamp format is invalid

    Examples:
        >>> parse_iso_timestamp("2026-02-10T10:00:00Z")
        datetime.datetime(2026, 2, 10, 10, 0, tzinfo=datetime.timezone.utc)

        >>> parse_iso_timestamp("2026-02-10")
        datetime.datetime(2026, 2, 10, 0, 0)
    """
    if not timestamp_str:
        return None

    if not isinstance(timestamp_str, str):
        raise ValueError(f"Timestamp must be a string, got {type(timestamp_str)}")

    try:
        # Handle 'Z' suffix by replacing with explicit UTC offset
        if timestamp_str.endswith("Z"):
            normalized = timestamp_str.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        else:
            return datetime.fromisoformat(timestamp_str)
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid ISO timestamp format: {timestamp_str}") from e
