"""
Integration Tests for usage_tables_report.py

Tests the end-to-end workflow of the usage tables report generator,
including CLI argument parsing, data pipeline, and HTML generation.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from execution.reports.usage_tables_report import (
    TEAM_FILTER,
    generate_html_report_with_data,
    generate_interactive_html,
    main,
    parse_arguments,
)


@pytest.fixture
def sample_team_data():
    """Sample team-filtered data for testing."""
    return pd.DataFrame(
        {
            "Name": ["Alice Smith", "Bob Jones", "Charlie Brown"],
            "Job Title": ["Engineer", "Manager", "Analyst"],
            "Software Company": ["TARGET_TEAM", "TARGET_TEAM", "TARGET_TEAM"],
            "Claude Access": ["Yes", "No", "Yes"],
            "Claude 30 day usage": [150, 10, 75],
            "Devin Access": ["Yes", "Yes", "No"],
            "Devin_30d": [200, 50, 5],
        }
    )


@pytest.fixture
def sample_claude_data():
    """Sample Claude usage data."""
    return pd.DataFrame(
        {
            "Name": ["Alice Smith", "Charlie Brown", "Bob Jones"],
            "Job Title": ["Engineer", "Analyst", "Manager"],
            "Claude Access": ["Yes", "Yes", "No"],
            "Claude 30 day usage": [150, 75, 10],
        }
    )


@pytest.fixture
def sample_devin_data():
    """Sample Devin usage data."""
    return pd.DataFrame(
        {
            "Name": ["Alice Smith", "Bob Jones", "Charlie Brown"],
            "Job Title": ["Engineer", "Manager", "Analyst"],
            "Devin Access": ["Yes", "Yes", "No"],
            "Devin_30d": [200, 50, 5],
        }
    )


class TestArgumentParsing:
    """Test CLI argument parsing."""

    def test_parse_arguments_no_file(self):
        """Test parsing with no file argument (interactive mode)."""
        with patch("sys.argv", ["usage_tables_report.py"]):
            args = parse_arguments()
            assert args.file is None
            assert args.open is False
            assert ".tmp/usage_tables_" in args.output_file

    def test_parse_arguments_with_file(self):
        """Test parsing with file argument (CLI mode)."""
        with patch("sys.argv", ["usage_tables_report.py", "--file", "data.csv"]):
            args = parse_arguments()
            assert args.file == "data.csv"
            assert args.open is False

    def test_parse_arguments_with_open_flag(self):
        """Test parsing with --open flag."""
        with patch("sys.argv", ["usage_tables_report.py", "--open"]):
            args = parse_arguments()
            assert args.open is True

    def test_parse_arguments_custom_output(self):
        """Test parsing with custom output file."""
        with patch("sys.argv", ["usage_tables_report.py", "--output-file", "custom.html"]):
            args = parse_arguments()
            assert args.output_file == "custom.html"


class TestHtmlReportGeneration:
    """Test HTML report generation with data."""

    def test_generate_html_report_with_data(self, sample_claude_data, sample_devin_data, tmp_path):
        """Test generating HTML report with provided data."""
        output_file = tmp_path / "test_report.html"

        result_path = generate_html_report_with_data(sample_claude_data, sample_devin_data, str(output_file))

        # Verify file was created
        assert Path(result_path).exists()

        # Read and validate HTML content
        with open(result_path, encoding="utf-8") as f:
            html = f.read()

        # Verify key elements
        assert "<!DOCTYPE html>" in html
        assert "AI Tools Usage Report" in html
        assert "Alice Smith" in html
        assert "Bob Jones" in html
        assert "Charlie Brown" in html
        assert "Claude Usage (Last 30 Days)" in html
        assert "Devin Usage (Last 30 Days)" in html
        assert "Total Team Users" in html

        # Verify statistics
        assert "3" in html  # Total users
        assert "2" in html  # Claude active users
        assert "2" in html  # Devin active users

    def test_generate_html_includes_framework(self, sample_claude_data, sample_devin_data, tmp_path):
        """Test that generated HTML includes dashboard framework CSS/JS."""
        output_file = tmp_path / "test_framework.html"

        result_path = generate_html_report_with_data(sample_claude_data, sample_devin_data, str(output_file))

        with open(result_path, encoding="utf-8") as f:
            html = f.read()

        # Verify framework components
        assert "theme-toggle" in html
        assert "toggleTheme()" in html
        assert "data-theme=" in html

    def test_generate_html_creates_parent_directory(self, sample_claude_data, sample_devin_data, tmp_path):
        """Test that parent directory is created if it doesn't exist."""
        output_file = tmp_path / "nested" / "dir" / "report.html"

        result_path = generate_html_report_with_data(sample_claude_data, sample_devin_data, str(output_file))

        assert Path(result_path).exists()
        assert Path(result_path).parent.exists()


class TestInteractiveHtmlGeneration:
    """Test interactive HTML generation with CSV import capability."""

    def test_generate_interactive_html(self, tmp_path):
        """Test generating interactive HTML with import button."""
        output_file = tmp_path / "test_interactive.html"

        result_path = generate_interactive_html(str(output_file))

        # Verify file was created
        assert Path(result_path).exists()

        # Read and validate HTML content
        with open(result_path, encoding="utf-8") as f:
            html = f.read()

        # Verify interactive components
        assert "<!DOCTYPE html>" in html
        assert "IMPORT CSV" in html
        assert "file-input" in html
        assert "handleFileUpload" in html
        assert "processData" in html
        assert "PapaParse" in html
        assert "placeholder" in html
        assert "No Data Loaded" in html

    def test_generate_interactive_html_includes_team_filter(self, tmp_path):
        """Test that team filter is embedded in JavaScript."""
        output_file = tmp_path / "test_filter.html"

        result_path = generate_interactive_html(str(output_file))

        with open(result_path, encoding="utf-8") as f:
            html = f.read()

        # Verify team filter is in JS
        assert TEAM_FILTER in html

    def test_generate_interactive_html_includes_utility_functions(self, tmp_path):
        """Test that utility functions are included."""
        output_file = tmp_path / "test_utils.html"

        result_path = generate_interactive_html(str(output_file))

        with open(result_path, encoding="utf-8") as f:
            html = f.read()

        # Verify utility functions
        assert "getHeatmapColor" in html
        assert "escapeHtml" in html


class TestEndToEndWorkflow:
    """Test end-to-end CLI workflow."""

    @patch("execution.reports.usage_tables_report.read_excel_usage_data")
    @patch("execution.reports.usage_tables_report.webbrowser.open")
    @patch("sys.argv", ["usage_tables_report.py", "--file", "test.csv"])
    def test_main_cli_mode_success(self, mock_browser, mock_read_excel, sample_team_data, tmp_path, capsys):
        """Test main function in CLI mode with successful execution."""
        # Setup mocks
        mock_read_excel.return_value = sample_team_data

        # Patch output file to tmp_path
        output_file = tmp_path / "test_output.html"
        with patch("execution.reports.usage_tables_report.parse_arguments") as mock_parse:
            mock_args = Mock()
            mock_args.file = "test.csv"
            mock_args.output_file = str(output_file)
            mock_args.open = False
            mock_parse.return_value = mock_args

            # Run main
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Verify successful exit
            assert exc_info.value.code == 0

            # Verify output
            captured = capsys.readouterr()
            assert "SUCCESS: AI Tools Usage Report Generated" in captured.out
            assert "Total Team Users: 3" in captured.out
            assert "Claude Active Users: 3" in captured.out

            # Verify HTML was generated
            assert output_file.exists()

    @patch("execution.reports.usage_tables_report.webbrowser.open")
    @patch("sys.argv", ["usage_tables_report.py"])
    def test_main_interactive_mode_success(self, mock_browser, tmp_path, capsys):
        """Test main function in interactive mode."""
        # Patch output file to tmp_path
        output_file = tmp_path / "test_interactive.html"
        with patch("execution.reports.usage_tables_report.parse_arguments") as mock_parse:
            mock_args = Mock()
            mock_args.file = None
            mock_args.output_file = str(output_file)
            mock_args.open = False
            mock_parse.return_value = mock_args

            # Run main
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Verify successful exit
            assert exc_info.value.code == 0

            # Verify output
            captured = capsys.readouterr()
            assert "SUCCESS: Interactive AI Tools Usage Report Generated" in captured.out
            assert "IMPORT CSV" in captured.out

            # Verify HTML was generated
            assert output_file.exists()

    @patch("execution.reports.usage_tables_report.read_excel_usage_data")
    @patch("sys.argv", ["usage_tables_report.py", "--file", "test.csv"])
    def test_main_file_not_found_error(self, mock_read_excel, capsys):
        """Test main function with file not found error."""
        # Setup mock to raise FileNotFoundError
        mock_read_excel.side_effect = FileNotFoundError("File not found: test.csv")

        with patch("execution.reports.usage_tables_report.parse_arguments") as mock_parse:
            mock_args = Mock()
            mock_args.file = "test.csv"
            mock_args.output_file = ".tmp/test.html"
            mock_args.open = False
            mock_parse.return_value = mock_args

            # Run main
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Verify error exit
            assert exc_info.value.code == 1

            # Verify error message
            captured = capsys.readouterr()
            assert "ERROR:" in captured.err

    @patch("execution.reports.usage_tables_report.read_excel_usage_data")
    @patch("execution.reports.usage_tables_report.webbrowser.open")
    @patch("sys.argv", ["usage_tables_report.py", "--file", "test.csv", "--open"])
    def test_main_opens_browser_when_requested(self, mock_browser, mock_read_excel, sample_team_data, tmp_path):
        """Test that browser opens when --open flag is used."""
        # Setup mocks
        mock_read_excel.return_value = sample_team_data

        output_file = tmp_path / "test_browser.html"
        with patch("execution.reports.usage_tables_report.parse_arguments") as mock_parse:
            mock_args = Mock()
            mock_args.file = "test.csv"
            mock_args.output_file = str(output_file)
            mock_args.open = True
            mock_parse.return_value = mock_args

            # Run main
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Verify browser was opened
            mock_browser.assert_called_once()
            assert exc_info.value.code == 0


class TestPipelineIntegration:
    """Test the complete data pipeline integration."""

    @patch("execution.reports.usage_tables_report.read_excel_usage_data")
    def test_pipeline_load_filter_process_generate(self, mock_read_excel, tmp_path):
        """Test complete pipeline: Load → Filter → Process → Generate."""
        # Setup data with multiple teams
        full_data = pd.DataFrame(
            {
                "Name": ["Alice", "Bob", "Charlie", "Diana"],
                "Job Title": ["Engineer", "Manager", "Analyst", "Director"],
                "Software Company": ["TARGET_TEAM", "TARGET_TEAM", "OTHER_TEAM", "TARGET_TEAM"],
                "Claude Access": ["Yes", "No", "Yes", "Yes"],
                "Claude 30 day usage": [150, 10, 200, 100],
                "Devin Access": ["Yes", "Yes", "No", "Yes"],
                "Devin_30d": [200, 50, 100, 75],
            }
        )
        mock_read_excel.return_value = full_data

        output_file = tmp_path / "test_pipeline.html"
        with patch("execution.reports.usage_tables_report.parse_arguments") as mock_parse:
            mock_args = Mock()
            mock_args.file = "test.csv"
            mock_args.output_file = str(output_file)
            mock_args.open = False
            mock_parse.return_value = mock_args

            # Run main
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 0

            # Read generated HTML
            with open(output_file, encoding="utf-8") as f:
                html = f.read()

            # Verify only TARGET_TEAM users are included
            assert "Alice" in html
            assert "Bob" in html
            assert "Diana" in html
            assert "Charlie" not in html  # Different team

            # Verify sorting (Claude usage descending: Alice 150, Diana 100, Bob 10)
            # Verify sorting (Devin usage descending: Alice 200, Diana 75, Bob 50)
            assert html.index("Alice") < html.index("Diana")
