"""
Tests for data_loader module

Tests CSV/Excel reading, column validation, and data cleaning functionality.
"""

import io
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pandas as pd
import pytest

from execution.reports.usage_tables.data_loader import (
    clean_dataframe,
    find_column_variant,
    read_excel_usage_data,
    validate_required_columns,
)


@pytest.fixture
def sample_csv_data() -> str:
    """Sample CSV data with all required columns."""
    return """Name,Job Title,Software Company,Claude Access?,Claude 30 day usage,Devin Access?,Devin_30d
John Doe,Engineer,TARGET_TEAM,Yes,150,Yes,75
Jane Smith,Manager,TARGET_TEAM,No,25,Yes,120
Bob Johnson,Developer,OTHER_TEAM,Yes,0,No,0"""


@pytest.fixture
def sample_csv_data_with_spaces() -> str:
    """Sample CSV data with spaces in column names."""
    return """Name,Job Title,Software Company,Claude Access ?,Claude 30 day usage,Devin Access ?,Devin_30d
John Doe,Engineer,TARGET_TEAM,Yes,150,Yes,75
Jane Smith,Manager,TARGET_TEAM,No,25,Yes,120"""


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Sample DataFrame for testing."""
    return pd.DataFrame(
        {
            "Name": ["John Doe", "Jane Smith", "Bob Johnson"],
            "Job Title": ["Engineer", "Manager", "Developer"],
            "Software Company": ["TARGET_TEAM", "TARGET_TEAM", "OTHER_TEAM"],
            "Claude Access?": ["Yes", "No", "Yes"],
            "Claude 30 day usage": [150, 25, 0],
            "Devin Access?": ["Yes", "Yes", "No"],
            "Devin_30d": [75, 120, 0],
        }
    )


@pytest.fixture
def sample_dataframe_with_missing_values() -> pd.DataFrame:
    """Sample DataFrame with missing/invalid values."""
    return pd.DataFrame(
        {
            "Name": ["  John Doe  ", "Jane Smith", "Bob Johnson"],
            "Job Title": ["Engineer", "Manager", "Developer"],
            "Software Company": ["  TARGET_TEAM  ", "TARGET_TEAM", "OTHER_TEAM"],
            "Claude Access": ["Yes", "No", "Yes"],
            "Claude 30 day usage": [150, None, "invalid"],
            "Devin Access": ["Yes", "Yes", "No"],
            "Devin_30d": [75, None, "invalid"],
        }
    )


class TestFindColumnVariant:
    """Tests for find_column_variant function."""

    def test_find_exact_match(self, sample_dataframe):
        """Test finding exact column match."""
        result = find_column_variant(sample_dataframe, ["Claude Access?"])
        assert result == "Claude Access?"

    def test_find_variant_with_space(self):
        """Test finding column with space variant."""
        df = pd.DataFrame({"Claude Access ?": [1, 2, 3]})
        result = find_column_variant(df, ["Claude Access?", "Claude Access ?"])
        assert result == "Claude Access ?"

    def test_no_match_found(self, sample_dataframe):
        """Test when no matching column is found."""
        result = find_column_variant(sample_dataframe, ["Nonexistent Column"])
        assert result is None

    def test_returns_first_match(self):
        """Test that first matching variant is returned."""
        df = pd.DataFrame({"Claude Access?": [1, 2, 3], "Claude Access ?": [4, 5, 6]})
        result = find_column_variant(df, ["Claude Access?", "Claude Access ?"])
        assert result == "Claude Access?"


class TestValidateRequiredColumns:
    """Tests for validate_required_columns function."""

    def test_valid_columns(self, sample_dataframe):
        """Test validation with all required columns present."""
        claude_col, devin_col = validate_required_columns(sample_dataframe)
        assert claude_col == "Claude Access?"
        assert devin_col == "Devin Access?"

    def test_valid_columns_with_spaces(self):
        """Test validation with column names containing trailing spaces."""
        df = pd.DataFrame(
            {
                "Name": ["John"],
                "Job Title": ["Engineer"],
                "Software Company": ["TARGET_TEAM"],
                "Claude Access ?": ["Yes"],
                "Claude 30 day usage": [150],
                "Devin Access ?": ["Yes"],
                "Devin_30d": [75],
            }
        )
        claude_col, devin_col = validate_required_columns(df)
        assert claude_col == "Claude Access ?"
        assert devin_col == "Devin Access ?"

    def test_missing_claude_access_column(self):
        """Test error when Claude Access column is missing."""
        df = pd.DataFrame(
            {
                "Name": ["John"],
                "Job Title": ["Engineer"],
                "Software Company": ["TARGET_TEAM"],
                "Claude 30 day usage": [150],
                "Devin Access?": ["Yes"],
                "Devin_30d": [75],
            }
        )
        with pytest.raises(ValueError, match="Missing 'Claude Access.*' column"):
            validate_required_columns(df)

    def test_missing_devin_access_column(self):
        """Test error when Devin Access column is missing."""
        df = pd.DataFrame(
            {
                "Name": ["John"],
                "Job Title": ["Engineer"],
                "Software Company": ["TARGET_TEAM"],
                "Claude Access?": ["Yes"],
                "Claude 30 day usage": [150],
                "Devin_30d": [75],
            }
        )
        with pytest.raises(ValueError, match="Missing 'Devin Access.*' column"):
            validate_required_columns(df)

    def test_missing_standard_column(self):
        """Test error when standard required column is missing."""
        df = pd.DataFrame(
            {
                "Name": ["John"],
                "Job Title": ["Engineer"],
                "Software Company": ["TARGET_TEAM"],
                "Claude Access?": ["Yes"],
                "Devin Access?": ["Yes"],
                "Devin_30d": [75],
            }
        )
        with pytest.raises(ValueError, match="Missing required columns"):
            validate_required_columns(df)


class TestCleanDataframe:
    """Tests for clean_dataframe function."""

    def test_strip_whitespace(self, sample_dataframe_with_missing_values):
        """Test whitespace stripping from text columns."""
        cleaned = clean_dataframe(sample_dataframe_with_missing_values)
        assert cleaned["Name"].iloc[0] == "John Doe"
        assert cleaned["Software Company"].iloc[0] == "TARGET_TEAM"

    def test_convert_usage_to_numeric(self, sample_dataframe_with_missing_values):
        """Test conversion of usage columns to numeric."""
        cleaned = clean_dataframe(sample_dataframe_with_missing_values)
        assert pd.api.types.is_numeric_dtype(cleaned["Claude 30 day usage"])
        assert pd.api.types.is_numeric_dtype(cleaned["Devin_30d"])

    def test_fill_missing_usage_with_zero(self, sample_dataframe_with_missing_values):
        """Test that missing usage values are filled with 0."""
        cleaned = clean_dataframe(sample_dataframe_with_missing_values)
        # None values should become 0
        assert cleaned["Claude 30 day usage"].iloc[1] == 0.0
        assert cleaned["Devin_30d"].iloc[1] == 0.0

    def test_invalid_usage_becomes_zero(self, sample_dataframe_with_missing_values):
        """Test that invalid numeric values become 0."""
        cleaned = clean_dataframe(sample_dataframe_with_missing_values)
        # "invalid" string should be coerced to NaN then filled with 0
        assert cleaned["Claude 30 day usage"].iloc[2] == 0.0
        assert cleaned["Devin_30d"].iloc[2] == 0.0


class TestReadExcelUsageData:
    """Tests for read_excel_usage_data function."""

    def test_read_csv_file(self, sample_csv_data):
        """Test reading a CSV file."""
        mock_file_path = "data/test.csv"
        # Create DataFrame BEFORE patching to avoid using mocked read_csv
        df = pd.read_csv(io.StringIO(sample_csv_data))

        with patch("execution.reports.usage_tables.data_loader.os.path.exists", return_value=True):
            with patch("execution.reports.usage_tables.data_loader.pd.read_csv", return_value=df) as mock_read_csv:
                result = read_excel_usage_data(mock_file_path)

                mock_read_csv.assert_called_once_with(mock_file_path)
                assert len(result) == 3
                assert "Claude Access" in result.columns
                assert "Devin Access" in result.columns

    def test_read_excel_file(self, sample_dataframe):
        """Test reading an Excel file."""
        mock_file_path = "data/test.xlsx"

        with patch("execution.reports.usage_tables.data_loader.os.path.exists", return_value=True):
            with patch("execution.reports.usage_tables.data_loader.pd.read_excel") as mock_read_excel:
                mock_read_excel.return_value = sample_dataframe

                result = read_excel_usage_data(mock_file_path)

                mock_read_excel.assert_called_once_with(mock_file_path, engine="openpyxl")
                assert len(result) == 3
                assert "Claude Access" in result.columns
                assert "Devin Access" in result.columns

    def test_file_not_found(self):
        """Test error when file doesn't exist."""
        mock_file_path = "data/nonexistent.csv"

        with patch("execution.reports.usage_tables.data_loader.os.path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="File not found"):
                read_excel_usage_data(mock_file_path)

    def test_unsupported_file_type(self):
        """Test error with unsupported file type."""
        mock_file_path = "data/test.txt"

        with patch("os.path.exists", return_value=True):
            with patch("pandas.read_csv") as mock_read_csv:
                # Simulate reading attempt
                mock_read_csv.side_effect = ValueError("Unsupported file type")

                with pytest.raises(ValueError, match="Error reading file"):
                    read_excel_usage_data(mock_file_path)

    def test_column_standardization(self, sample_csv_data_with_spaces):
        """Test that column names with spaces are standardized."""
        mock_file_path = "data/test.csv"
        # Create DataFrame BEFORE patching
        df = pd.read_csv(io.StringIO(sample_csv_data_with_spaces))

        with patch("execution.reports.usage_tables.data_loader.os.path.exists", return_value=True):
            with patch("execution.reports.usage_tables.data_loader.pd.read_csv", return_value=df):
                result = read_excel_usage_data(mock_file_path)

                # Standardized column names should exist
                assert "Claude Access" in result.columns
                assert "Devin Access" in result.columns
                # Original columns with spaces should be removed
                assert "Claude Access ?" not in result.columns
                assert "Devin Access ?" not in result.columns

    def test_data_cleaning_applied(self, sample_csv_data):
        """Test that data cleaning is applied during reading."""
        mock_file_path = "data/test.csv"
        # Create DataFrame BEFORE patching
        df = pd.read_csv(io.StringIO(sample_csv_data))

        with patch("execution.reports.usage_tables.data_loader.os.path.exists", return_value=True):
            with patch("execution.reports.usage_tables.data_loader.pd.read_csv", return_value=df):
                result = read_excel_usage_data(mock_file_path)

                # Check that usage columns are numeric
                assert pd.api.types.is_numeric_dtype(result["Claude 30 day usage"])
                assert pd.api.types.is_numeric_dtype(result["Devin_30d"])

    def test_missing_required_columns_raises_error(self):
        """Test error when required columns are missing."""
        mock_file_path = "data/test.csv"
        incomplete_df = pd.DataFrame(
            {
                "Name": ["John"],
                "Job Title": ["Engineer"],
            }
        )

        with patch("execution.reports.usage_tables.data_loader.os.path.exists", return_value=True):
            with patch("execution.reports.usage_tables.data_loader.pd.read_csv", return_value=incomplete_df):
                with pytest.raises(ValueError, match="Missing"):
                    read_excel_usage_data(mock_file_path)

    def test_read_xls_file(self, sample_dataframe):
        """Test reading an .xls (old Excel) file."""
        mock_file_path = "data/test.xls"

        with patch("execution.reports.usage_tables.data_loader.os.path.exists", return_value=True):
            with patch("execution.reports.usage_tables.data_loader.pd.read_excel") as mock_read_excel:
                mock_read_excel.return_value = sample_dataframe

                result = read_excel_usage_data(mock_file_path)

                mock_read_excel.assert_called_once_with(mock_file_path, engine="openpyxl")
                assert len(result) == 3

    def test_encoding_issues_handled(self):
        """Test that encoding issues are handled gracefully."""
        mock_file_path = "data/test.csv"

        with patch("execution.reports.usage_tables.data_loader.os.path.exists", return_value=True):
            with patch("execution.reports.usage_tables.data_loader.pd.read_csv") as mock_read_csv:
                mock_read_csv.side_effect = UnicodeDecodeError("utf-8", b"", 0, 1, "invalid")

                with pytest.raises(ValueError, match="Error reading file"):
                    read_excel_usage_data(mock_file_path)
