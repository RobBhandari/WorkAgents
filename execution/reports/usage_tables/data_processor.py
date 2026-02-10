"""
Data Processing Module for AI Usage Tables Report

This module contains all data filtering, calculation, and transformation logic
for processing AI usage data from CSV/Excel files.

Functions:
    - filter_team_users: Filter DataFrame by team/company
    - prepare_claude_data: Extract and sort Claude usage data
    - prepare_devin_data: Extract and sort Devin usage data
    - calculate_summary_stats: Calculate aggregate statistics
    - normalize_access_column_value: Normalize access values to Yes/No
    - filter_by_access_status: Filter users by access status
    - filter_by_usage_threshold: Filter users by usage range
    - get_usage_intensity_distribution: Calculate usage distribution
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def filter_team_users(df: pd.DataFrame, team_filter: str) -> pd.DataFrame:
    """
    Filter DataFrame for target team (Software Company column).

    Args:
        df: DataFrame with usage data
        team_filter: Team/company name to filter for

    Returns:
        pd.DataFrame: Filtered DataFrame containing only target team users

    Raises:
        ValueError: If no target team users found
    """
    logger.info(f"Filtering for Software Company = '{team_filter}'")

    # Filter for team (case-insensitive)
    filtered_df = df[df["Software Company"].str.upper() == team_filter.upper()].copy()

    if len(filtered_df) == 0:
        raise ValueError(f"No {team_filter} users found in dataset")

    logger.info(f"Found {len(filtered_df)} {team_filter} users out of {len(df)} total users")
    return filtered_df


def prepare_claude_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare Claude usage table data.

    Extracts relevant columns, sorts by usage, and resets index.

    Args:
        df: Filtered DataFrame with target team users

    Returns:
        pd.DataFrame: DataFrame sorted by Claude usage (descending)
    """
    # Select relevant columns
    claude_df = df[["Name", "Job Title", "Claude Access", "Claude 30 day usage"]].copy()

    # Sort by usage (descending)
    claude_df = claude_df.sort_values("Claude 30 day usage", ascending=False)

    # Reset index
    claude_df = claude_df.reset_index(drop=True)

    logger.info(f"Prepared Claude table with {len(claude_df)} users")
    logger.info(
        f"Claude usage range: {claude_df['Claude 30 day usage'].min():.0f} - {claude_df['Claude 30 day usage'].max():.0f}"
    )

    return claude_df


def prepare_devin_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare Devin usage table data.

    Extracts relevant columns, sorts by usage, and resets index.

    Args:
        df: Filtered DataFrame with target team users

    Returns:
        pd.DataFrame: DataFrame sorted by Devin usage (descending)
    """
    # Select relevant columns
    devin_df = df[["Name", "Job Title", "Devin Access", "Devin_30d"]].copy()

    # Sort by usage (descending)
    devin_df = devin_df.sort_values("Devin_30d", ascending=False)

    # Reset index
    devin_df = devin_df.reset_index(drop=True)

    logger.info(f"Prepared Devin table with {len(devin_df)} users")
    logger.info(f"Devin usage range: {devin_df['Devin_30d'].min():.0f} - {devin_df['Devin_30d'].max():.0f}")

    return devin_df


def calculate_summary_stats(claude_df: pd.DataFrame, devin_df: pd.DataFrame) -> dict:
    """
    Calculate summary statistics for both Claude and Devin usage.

    Args:
        claude_df: DataFrame with Claude usage data
        devin_df: DataFrame with Devin usage data

    Returns:
        dict: Summary statistics including:
            - total_users: Total number of users
            - claude_active_users: Users with Claude usage > 0
            - devin_active_users: Users with Devin usage > 0
            - avg_claude_usage: Average Claude usage across all users
            - avg_devin_usage: Average Devin usage across all users
    """
    total_users = len(claude_df)
    claude_active_users = len(claude_df[claude_df["Claude 30 day usage"] > 0])
    devin_active_users = len(devin_df[devin_df["Devin_30d"] > 0])
    avg_claude_usage = claude_df["Claude 30 day usage"].mean()
    avg_devin_usage = devin_df["Devin_30d"].mean()

    logger.info(
        f"Summary stats calculated: {total_users} total users, {claude_active_users} Claude users, {devin_active_users} Devin users"
    )

    return {
        "total_users": total_users,
        "claude_active_users": claude_active_users,
        "devin_active_users": devin_active_users,
        "avg_claude_usage": avg_claude_usage,
        "avg_devin_usage": avg_devin_usage,
    }


def normalize_access_column_value(access_value: str | int | float | None) -> str:
    """
    Normalize access column values to 'Yes' or 'No'.

    Handles various input formats including text, numeric, and missing values.

    Args:
        access_value: Raw access value from DataFrame (str, int, float, or None)

    Returns:
        str: 'Yes' or 'No'
    """
    # Check for missing values first (handles pd.NA, None, NaN)
    try:
        if pd.isna(access_value):
            return "No"
    except (ValueError, TypeError):
        # pd.NA can raise TypeError on boolean evaluation
        return "No"

    # Handle empty strings
    if not access_value or (isinstance(access_value, str) and not access_value.strip()):
        return "No"

    access_str = str(access_value).strip().upper()

    # Treat 'YES', '1', '1.0' as Yes
    if access_str in ["YES", "1", "1.0"]:
        return "Yes"

    # Everything else is No (including 'NO', '0', '0.0', 'NAN', 'NONE', '')
    return "No"


def filter_by_access_status(df: pd.DataFrame, access_column: str, has_access: bool = True) -> pd.DataFrame:
    """
    Filter DataFrame by access status.

    Args:
        df: DataFrame with usage data
        access_column: Name of the access column (e.g., 'Claude Access', 'Devin Access')
        has_access: If True, return users with access; if False, return users without access

    Returns:
        pd.DataFrame: Filtered DataFrame
    """
    df_copy = df.copy()
    df_copy["normalized_access"] = df_copy[access_column].apply(normalize_access_column_value)

    if has_access:
        filtered = df_copy[df_copy["normalized_access"] == "Yes"]
    else:
        filtered = df_copy[df_copy["normalized_access"] == "No"]

    return filtered.drop(columns=["normalized_access"])


def filter_by_usage_threshold(
    df: pd.DataFrame, usage_column: str, min_usage: float = 0.0, max_usage: float = float("inf")
) -> pd.DataFrame:
    """
    Filter DataFrame by usage value range.

    Args:
        df: DataFrame with usage data
        usage_column: Name of the usage column (e.g., 'Claude 30 day usage', 'Devin_30d')
        min_usage: Minimum usage threshold (inclusive)
        max_usage: Maximum usage threshold (exclusive)

    Returns:
        pd.DataFrame: Filtered DataFrame
    """
    filtered = df[(df[usage_column] >= min_usage) & (df[usage_column] < max_usage)].copy()

    logger.info(f"Filtered {len(filtered)} users with {usage_column} in range [{min_usage}, {max_usage})")
    return filtered


def get_usage_intensity_distribution(df: pd.DataFrame, usage_column: str) -> dict:
    """
    Calculate distribution of users across usage intensity levels.

    Uses the same thresholds as get_usage_heatmap_color:
    - Low: < 20 uses
    - Medium: 20-99 uses
    - High: >= 100 uses

    Args:
        df: DataFrame with usage data
        usage_column: Name of the usage column

    Returns:
        dict: Distribution with keys 'low', 'medium', 'high' containing user counts
    """
    low_count = len(df[df[usage_column] < 20])
    medium_count = len(df[(df[usage_column] >= 20) & (df[usage_column] < 100)])
    high_count = len(df[df[usage_column] >= 100])

    return {
        "low": low_count,
        "medium": medium_count,
        "high": high_count,
    }
