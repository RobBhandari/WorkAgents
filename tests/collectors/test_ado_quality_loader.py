"""
Tests for ADO Quality Metrics Loader

Tests cover:
- Loading latest metrics from history file
- Handling both new format (projects array) and old format
- File not found error handling
- Invalid JSON handling
- Missing/malformed data handling
- Date parsing edge cases
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from execution.collectors.ado_quality_loader import ADOQualityLoader
from execution.domain.quality import QualityMetrics


@pytest.fixture
def quality_history_new_format():
    """Sample quality history in new format (projects array)"""
    return {
        "project": "Engineering",
        "weeks": [
            {
                "week_date": "2026-01-31",
                "projects": [
                    {
                        "name": "Project A",
                        "open_bugs_count": 25,
                        "total_bugs_analyzed": 5,
                    },
                    {
                        "name": "Project B",
                        "open_bugs_count": 30,
                        "total_bugs_analyzed": 8,
                    },
                ],
            },
            {
                "week_date": "2026-02-07",
                "projects": [
                    {
                        "name": "Project A",
                        "open_bugs_count": 20,
                        "total_bugs_analyzed": 7,
                    },
                    {
                        "name": "Project B",
                        "open_bugs_count": 28,
                        "total_bugs_analyzed": 6,
                    },
                ],
            },
        ],
    }


@pytest.fixture
def quality_history_old_format():
    """Sample quality history in old format (direct metrics)"""
    return {
        "project": "Legacy Project",
        "weeks": [
            {
                "week_ending": "2026-01-31",
                "metrics": {
                    "open_bugs": 45,
                    "closed_this_week": 8,
                    "created_this_week": 5,
                    "net_change": -3,
                    "p1_count": 2,
                    "p2_count": 7,
                },
            },
            {
                "week_date": "2026-02-07",
                "metrics": {
                    "open_bugs": 42,
                    "closed_this_week": 10,
                    "created_this_week": 7,
                    "net_change": -3,
                    "p1_count": 1,
                    "p2_count": 6,
                },
            },
        ],
    }


@pytest.fixture
def temp_history_file(tmp_path):
    """Create a temporary history file path"""
    return tmp_path / "quality_history.json"


class TestADOQualityLoaderInit:
    """Test ADOQualityLoader initialization"""

    def test_default_history_file_path(self):
        """Test default history file path is set correctly"""
        loader = ADOQualityLoader()
        assert loader.history_file == Path(".tmp/observatory/quality_history.json")

    def test_custom_history_file_path(self, temp_history_file):
        """Test custom history file path is accepted"""
        loader = ADOQualityLoader(history_file=temp_history_file)
        assert loader.history_file == temp_history_file


class TestLoadLatestMetricsNewFormat:
    """Test loading metrics in new format (projects array)"""

    def test_load_latest_week_new_format(self, temp_history_file, quality_history_new_format):
        """Test loading latest week with new format"""
        # Write test data
        temp_history_file.write_text(json.dumps(quality_history_new_format))

        loader = ADOQualityLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should aggregate from latest week (2026-02-07)
        assert isinstance(metrics, QualityMetrics)
        assert metrics.project == "Engineering"
        assert metrics.open_bugs == 48  # 20 + 28
        assert metrics.closed_this_week == 13  # 7 + 6
        assert metrics.created_this_week == 0  # Not available in new format
        assert metrics.net_change == 0  # Not available in new format
        assert metrics.p1_count == 0  # Not available in new format
        assert metrics.p2_count == 0  # Not available in new format

    def test_timestamp_parsing_new_format(self, temp_history_file, quality_history_new_format):
        """Test timestamp is parsed correctly from week_date"""
        temp_history_file.write_text(json.dumps(quality_history_new_format))

        loader = ADOQualityLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        assert metrics.timestamp == datetime.fromisoformat("2026-02-07")

    def test_aggregation_with_empty_projects(self, temp_history_file):
        """Test aggregation when projects have no bug data"""
        history = {
            "project": "Test",
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "projects": [
                        {"name": "Empty Project 1"},
                        {"name": "Empty Project 2"},
                    ],
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOQualityLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should default to 0 for missing metrics
        assert metrics.open_bugs == 0
        assert metrics.closed_this_week == 0


class TestLoadLatestMetricsOldFormat:
    """Test loading metrics in old format (direct metrics)"""

    def test_load_latest_week_old_format(self, temp_history_file, quality_history_old_format):
        """Test loading latest week with old format"""
        temp_history_file.write_text(json.dumps(quality_history_old_format))

        loader = ADOQualityLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should use latest week (2026-02-07)
        assert isinstance(metrics, QualityMetrics)
        assert metrics.project == "Legacy Project"
        assert metrics.open_bugs == 42
        assert metrics.closed_this_week == 10
        assert metrics.created_this_week == 7
        assert metrics.net_change == -3
        assert metrics.p1_count == 1
        assert metrics.p2_count == 6

    def test_timestamp_fallback_to_week_ending(self, temp_history_file):
        """Test timestamp parsing falls back to week_ending if week_date not present"""
        history = {
            "project": "Test",
            "weeks": [
                {
                    "week_ending": "2026-01-31",
                    "metrics": {
                        "open_bugs": 30,
                        "closed_this_week": 5,
                        "created_this_week": 3,
                        "net_change": -2,
                    },
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOQualityLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        assert metrics.timestamp == datetime.fromisoformat("2026-01-31")

    def test_missing_optional_fields_old_format(self, temp_history_file):
        """Test loading with missing optional fields in old format"""
        history = {
            "project": "Minimal",
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "metrics": {
                        "open_bugs": 15,
                        # Missing other fields
                    },
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOQualityLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should default to 0 for missing fields
        assert metrics.open_bugs == 15
        assert metrics.closed_this_week == 0
        assert metrics.created_this_week == 0
        assert metrics.net_change == 0
        assert metrics.p1_count == 0
        assert metrics.p2_count == 0


class TestErrorHandling:
    """Test error handling for various failure scenarios"""

    def test_file_not_found(self, temp_history_file):
        """Test FileNotFoundError when history file doesn't exist"""
        # Don't create the file
        loader = ADOQualityLoader(history_file=temp_history_file)

        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load_latest_metrics()

        assert "Quality history not found" in str(exc_info.value)
        assert str(temp_history_file) in str(exc_info.value)

    def test_invalid_json(self, temp_history_file):
        """Test ValueError when JSON is malformed"""
        temp_history_file.write_text("{ invalid json }")

        loader = ADOQualityLoader(history_file=temp_history_file)

        with pytest.raises(ValueError) as exc_info:
            loader.load_latest_metrics()

        assert "Invalid JSON in history file" in str(exc_info.value)

    def test_missing_weeks_data(self, temp_history_file):
        """Test ValueError when weeks data is missing"""
        history = {"project": "Test"}  # No weeks
        temp_history_file.write_text(json.dumps(history))

        loader = ADOQualityLoader(history_file=temp_history_file)

        with pytest.raises(ValueError) as exc_info:
            loader.load_latest_metrics()

        assert "No weeks data in history file" in str(exc_info.value)

    def test_empty_weeks_array(self, temp_history_file):
        """Test ValueError when weeks array is empty"""
        history = {"project": "Test", "weeks": []}
        temp_history_file.write_text(json.dumps(history))

        loader = ADOQualityLoader(history_file=temp_history_file)

        with pytest.raises(ValueError) as exc_info:
            loader.load_latest_metrics()

        assert "No weeks data in history file" in str(exc_info.value)

    def test_missing_week_date_field(self, temp_history_file):
        """Test handling when both week_date and week_ending are missing"""
        history = {
            "project": "Test",
            "weeks": [
                {
                    # No week_date or week_ending
                    "metrics": {"open_bugs": 10, "closed_this_week": 2, "created_this_week": 1, "net_change": -1}
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOQualityLoader(history_file=temp_history_file)

        # When both date fields are None, fromisoformat raises TypeError
        with pytest.raises(TypeError):
            loader.load_latest_metrics()

    def test_invalid_date_format(self, temp_history_file):
        """Test ValueError when date format is invalid"""
        history = {
            "project": "Test",
            "weeks": [
                {
                    "week_date": "not-a-date",
                    "metrics": {"open_bugs": 10, "closed_this_week": 2, "created_this_week": 1, "net_change": -1},
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOQualityLoader(history_file=temp_history_file)

        with pytest.raises(ValueError):
            loader.load_latest_metrics()


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_single_week_data(self, temp_history_file):
        """Test loading when only one week of data exists"""
        history = {
            "project": "Single",
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "metrics": {"open_bugs": 20, "closed_this_week": 3, "created_this_week": 2, "net_change": -1},
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOQualityLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        assert metrics.open_bugs == 20

    def test_multiple_weeks_uses_latest(self, temp_history_file, quality_history_old_format):
        """Test that the loader uses the last week in the array"""
        temp_history_file.write_text(json.dumps(quality_history_old_format))

        loader = ADOQualityLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should use second week (index -1)
        assert metrics.timestamp == datetime.fromisoformat("2026-02-07")
        assert metrics.open_bugs == 42  # From second week

    def test_zero_bugs(self, temp_history_file):
        """Test handling when bug counts are zero"""
        history = {
            "project": "Perfect",
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "metrics": {
                        "open_bugs": 0,
                        "closed_this_week": 0,
                        "created_this_week": 0,
                        "net_change": 0,
                        "p1_count": 0,
                        "p2_count": 0,
                    },
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOQualityLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        assert metrics.open_bugs == 0
        assert metrics.closed_this_week == 0
        assert metrics.closure_rate is None  # Division by zero handling

    def test_large_bug_counts(self, temp_history_file):
        """Test handling large bug counts"""
        history = {
            "project": "Large",
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "metrics": {
                        "open_bugs": 10000,
                        "closed_this_week": 500,
                        "created_this_week": 300,
                        "net_change": -200,
                    },
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOQualityLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        assert metrics.open_bugs == 10000
        assert metrics.closed_this_week == 500


class TestLogging:
    """Test logging behavior"""

    @patch("execution.collectors.ado_quality_loader.logger")
    def test_logs_on_successful_load(self, mock_logger, temp_history_file, quality_history_new_format):
        """Test that successful loads are logged"""
        temp_history_file.write_text(json.dumps(quality_history_new_format))

        loader = ADOQualityLoader(history_file=temp_history_file)
        loader.load_latest_metrics()

        # Should log successful load
        mock_logger.info.assert_called()

    @patch("execution.collectors.ado_quality_loader.logger")
    def test_logs_on_file_not_found(self, mock_logger, temp_history_file):
        """Test that file not found errors are logged"""
        loader = ADOQualityLoader(history_file=temp_history_file)

        with pytest.raises(FileNotFoundError):
            loader.load_latest_metrics()

        # Should log error
        mock_logger.error.assert_called()

    @patch("execution.collectors.ado_quality_loader.logger")
    def test_logs_on_invalid_json(self, mock_logger, temp_history_file):
        """Test that invalid JSON errors are logged"""
        temp_history_file.write_text("{ invalid }")

        loader = ADOQualityLoader(history_file=temp_history_file)

        with pytest.raises(ValueError):
            loader.load_latest_metrics()

        # Should log error with exc_info
        mock_logger.error.assert_called()
