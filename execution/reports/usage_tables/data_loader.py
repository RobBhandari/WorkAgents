"""
Data Loading Module for AI Tools Usage Tables Report

This module handles reading and validating CSV/Excel files containing AI usage data.
Supports both .csv and .xlsx/.xls formats with robust column name validation.

Functions:
    read_excel_usage_data: Read and validate Excel or CSV file
    validate_required_columns: Validate presence of required columns
    find_column_variant: Find column name variants (e.g., with/without trailing space)
    clean_dataframe: Clean and normalize DataFrame values
"""

import logging
import os
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def find_column_variant(df: pd.DataFrame, column_variants: list[str]) -> str | None:
    """
    Find a column that matches one of the provided variants.

    Args:
        df: DataFrame to search in
        column_variants: List of possible column name variations

    Returns:
        str: First matching column name, or None if not found
    """
    for col in df.columns:
        col_str = str(col)
        if col_str in column_variants:
            return col_str
    return None


def validate_required_columns(df: pd.DataFrame) -> tuple[str, str]:
    """
    Validate that required columns exist in the DataFrame.

    Handles column name variations (e.g., "Claude Access?" vs "Claude Access ?").

    Args:
        df: DataFrame to validate

    Returns:
        tuple[str, str]: (claude_access_column, devin_access_column)

    Raises:
        ValueError: If required columns are missing
    """
    # Find Claude Access column (with or without space before ?)
    claude_access_col = find_column_variant(df, ["Claude Access?", "Claude Access ?"])
    if not claude_access_col:
        raise ValueError(
            f"Missing 'Claude Access?' or 'Claude Access ?' column\n" f"Available columns: {list(df.columns)}"
        )

    # Find Devin Access column (with or without space before ?)
    devin_access_col = find_column_variant(df, ["Devin Access?", "Devin Access ?"])
    if not devin_access_col:
        raise ValueError(
            f"Missing 'Devin Access?' or 'Devin Access ?' column\n" f"Available columns: {list(df.columns)}"
        )

    # Verify other required columns exist
    required_columns = ["Name", "Software Company", "Claude 30 day usage", "Devin_30d"]
    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        raise ValueError(f"Missing required columns: {missing}\n" f"Available columns: {list(df.columns)}")

    logger.info(f"Using column '{claude_access_col}' for Claude Access")
    logger.info(f"Using column '{devin_access_col}' for Devin Access")

    return claude_access_col, devin_access_col


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and normalize DataFrame values.

    Operations:
    - Strip whitespace from string columns
    - Convert usage columns to numeric, treating missing values as 0
    - Handle NaN values in text fields

    Args:
        df: DataFrame to clean

    Returns:
        pd.DataFrame: Cleaned DataFrame
    """
    # Strip whitespace from string columns
    for col in ["Name", "Software Company", "Claude Access", "Devin Access"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Handle missing usage values (treat as 0)
    df["Claude 30 day usage"] = pd.to_numeric(df["Claude 30 day usage"], errors="coerce").fillna(0)
    df["Devin_30d"] = pd.to_numeric(df["Devin_30d"], errors="coerce").fillna(0)

    logger.info("Data cleaned successfully")
    return df


def read_excel_usage_data(file_path: str) -> pd.DataFrame:
    """
    Read Excel or CSV file and validate required columns exist.

    Supported formats: .csv, .xlsx, .xls
    Handles column name variations (e.g., trailing spaces in column names).

    Args:
        file_path: Path to Excel/CSV file containing usage data

    Returns:
        pd.DataFrame: Cleaned DataFrame with usage data and standardized column names

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If required columns are missing or file format is unsupported
    """
    logger.info(f"Reading file: {file_path}")

    # Validate file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        # Detect file type and read accordingly
        file_ext = Path(file_path).suffix.lower()

        if file_ext == ".csv":
            df = pd.read_csv(file_path)
            logger.info(f"Successfully read CSV file with {len(df)} rows")
        elif file_ext in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path, engine="openpyxl")
            logger.info(f"Successfully read Excel file with {len(df)} rows")
        else:
            raise ValueError(f"Unsupported file type: {file_ext}. Please use .csv, .xlsx, or .xls")

        logger.info(f"Available columns: {list(df.columns)}")

    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        raise ValueError(f"Error reading file: {e}") from e

    # Validate required columns and get standardized names
    claude_access_col, devin_access_col = validate_required_columns(df)

    # Standardize the access column names
    df = df.rename(
        columns={
            claude_access_col: "Claude Access",
            devin_access_col: "Devin Access",
        }
    )

    # Clean data
    df = clean_dataframe(df)

    return df
