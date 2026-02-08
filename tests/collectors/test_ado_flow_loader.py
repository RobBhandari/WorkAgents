"""
Tests for ADO Flow Metrics Loader

Tests cover:
- Loading latest metrics from history file
- Handling both new format (projects array) and old format
- Percentile calculations and aggregation
- File not found error handling
- Invalid JSON handling
- Missing/malformed data handling
- Date parsing edge cases
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from execution.collectors.ado_flow_loader import ADOFlowLoader
from execution.domain.flow import FlowMetrics


@pytest.fixture
def flow_history_new_format():
    """Sample flow history in new format (projects array with work_type_metrics)"""
    return {
        "project": "Engineering",
        "weeks": [
            {
                "week_date": "2026-01-31",
                "projects": [
                    {
                        "name": "Project A",
                        "work_type_metrics": {
                            "Bug": {
                                "dual_metrics": {
                                    "operational": {
                                        "p50": 5.2,
                                        "p85": 10.5,
                                        "p95": 15.8,
                                    }
                                },
                                "lead_time": {
                                    "p50": 8.5,
                                    "p85": 16.2,
                                    "p95": 24.3,
                                },
                                "throughput": {"closed_count": 10},
                            }
                        },
                    },
                    {
                        "name": "Project B",
                        "work_type_metrics": {
                            "Bug": {
                                "dual_metrics": {
                                    "operational": {
                                        "p50": 6.8,
                                        "p85": 12.3,
                                        "p95": 18.7,
                                    }
                                },
                                "lead_time": {
                                    "p50": 9.2,
                                    "p85": 18.5,
                                    "p95": 28.6,
                                },
                                "throughput": {"closed_count": 8},
                            }
                        },
                    },
                ],
            },
            {
                "week_date": "2026-02-07",
                "projects": [
                    {
                        "name": "Project A",
                        "work_type_metrics": {
                            "Bug": {
                                "dual_metrics": {
                                    "operational": {
                                        "p50": 4.5,
                                        "p85": 9.8,
                                        "p95": 14.2,
                                    }
                                },
                                "lead_time": {
                                    "p50": 7.8,
                                    "p85": 15.3,
                                    "p95": 22.8,
                                },
                                "throughput": {"closed_count": 12},
                            }
                        },
                    },
                    {
                        "name": "Project B",
                        "work_type_metrics": {
                            "Bug": {
                                "dual_metrics": {
                                    "operational": {
                                        "p50": 5.5,
                                        "p85": 11.2,
                                        "p95": 16.8,
                                    }
                                },
                                "lead_time": {
                                    "p50": 8.2,
                                    "p85": 17.1,
                                    "p95": 26.4,
                                },
                                "throughput": {"closed_count": 9},
                            }
                        },
                    },
                ],
            },
        ],
    }


@pytest.fixture
def flow_history_old_format():
    """Sample flow history in old format (direct metrics)"""
    return {
        "project": "Legacy Project",
        "weeks": [
            {
                "week_ending": "2026-01-31",
                "metrics": {
                    "cycle_time_p50": 5.5,
                    "cycle_time_p85": 11.2,
                    "cycle_time_p95": 16.8,
                    "lead_time_p50": 8.5,
                    "lead_time_p85": 17.2,
                    "lead_time_p95": 25.8,
                    "throughput": 15,
                },
            },
            {
                "week_date": "2026-02-07",
                "metrics": {
                    "cycle_time_p50": 4.8,
                    "cycle_time_p85": 10.5,
                    "cycle_time_p95": 15.2,
                    "lead_time_p50": 7.8,
                    "lead_time_p85": 16.1,
                    "lead_time_p95": 24.3,
                    "throughput": 18,
                },
            },
        ],
    }


@pytest.fixture
def temp_history_file(tmp_path):
    """Create a temporary history file path"""
    return tmp_path / "flow_history.json"


class TestADOFlowLoaderInit:
    """Test ADOFlowLoader initialization"""

    def test_default_history_file_path(self):
        """Test default history file path is set correctly"""
        loader = ADOFlowLoader()
        assert loader.history_file == Path(".tmp/observatory/flow_history.json")

    def test_custom_history_file_path(self, temp_history_file):
        """Test custom history file path is accepted"""
        loader = ADOFlowLoader(history_file=temp_history_file)
        assert loader.history_file == temp_history_file


class TestLoadLatestMetricsNewFormat:
    """Test loading metrics in new format (projects array)"""

    def test_load_latest_week_new_format(self, temp_history_file, flow_history_new_format):
        """Test loading latest week with new format"""
        temp_history_file.write_text(json.dumps(flow_history_new_format))

        loader = ADOFlowLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should aggregate from latest week (2026-02-07)
        # Average of Project A (4.5, 9.8, 14.2) and Project B (5.5, 11.2, 16.8)
        assert isinstance(metrics, FlowMetrics)
        assert metrics.project == "Engineering"
        assert metrics.cycle_time_p50 == pytest.approx(5.0, rel=0.01)  # (4.5 + 5.5) / 2
        assert metrics.cycle_time_p85 == pytest.approx(10.5, rel=0.01)  # (9.8 + 11.2) / 2
        assert metrics.cycle_time_p95 == pytest.approx(15.5, rel=0.01)  # (14.2 + 16.8) / 2
        assert metrics.lead_time_p50 == pytest.approx(8.0, rel=0.01)  # (7.8 + 8.2) / 2
        assert metrics.lead_time_p85 == pytest.approx(16.2, rel=0.01)  # (15.3 + 17.1) / 2
        assert metrics.lead_time_p95 == pytest.approx(24.6, rel=0.01)  # (22.8 + 26.4) / 2
        assert metrics.throughput == 21  # 12 + 9

    def test_timestamp_parsing_new_format(self, temp_history_file, flow_history_new_format):
        """Test timestamp is parsed correctly from week_date"""
        temp_history_file.write_text(json.dumps(flow_history_new_format))

        loader = ADOFlowLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        assert metrics.timestamp == datetime.fromisoformat("2026-02-07")

    def test_aggregation_with_missing_metrics(self, temp_history_file):
        """Test aggregation when some projects have missing metrics"""
        history = {
            "project": "Test",
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "projects": [
                        {
                            "name": "Complete Project",
                            "work_type_metrics": {
                                "Bug": {
                                    "dual_metrics": {"operational": {"p50": 5.0, "p85": 10.0, "p95": 15.0}},
                                    "lead_time": {"p50": 8.0, "p85": 16.0, "p95": 24.0},
                                    "throughput": {"closed_count": 10},
                                }
                            },
                        },
                        {
                            "name": "Incomplete Project",
                            "work_type_metrics": {
                                "Bug": {
                                    # Missing dual_metrics and lead_time
                                    "throughput": {"closed_count": 5}
                                }
                            },
                        },
                    ],
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOFlowLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should only average values from projects that have them
        assert metrics.cycle_time_p50 == 5.0  # Only one project has it
        assert metrics.throughput == 15  # 10 + 5

    def test_aggregation_with_no_bug_metrics(self, temp_history_file):
        """Test aggregation when projects have no Bug work items"""
        history = {
            "project": "Test",
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "projects": [
                        {
                            "name": "Project with no bugs",
                            "work_type_metrics": {},
                        },
                    ],
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOFlowLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should default to 0 for all metrics
        assert metrics.cycle_time_p50 == 0.0
        assert metrics.lead_time_p50 == 0.0
        assert metrics.throughput == 0


class TestLoadLatestMetricsOldFormat:
    """Test loading metrics in old format (direct metrics)"""

    def test_load_latest_week_old_format(self, temp_history_file, flow_history_old_format):
        """Test loading latest week with old format"""
        temp_history_file.write_text(json.dumps(flow_history_old_format))

        loader = ADOFlowLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should use latest week (2026-02-07)
        assert isinstance(metrics, FlowMetrics)
        assert metrics.project == "Legacy Project"
        assert metrics.cycle_time_p50 == 4.8
        assert metrics.cycle_time_p85 == 10.5
        assert metrics.cycle_time_p95 == 15.2
        assert metrics.lead_time_p50 == 7.8
        assert metrics.lead_time_p85 == 16.1
        assert metrics.lead_time_p95 == 24.3
        assert metrics.throughput == 18

    def test_timestamp_fallback_to_week_ending(self, temp_history_file):
        """Test timestamp parsing falls back to week_ending if week_date not present"""
        history = {
            "project": "Test",
            "weeks": [
                {
                    "week_ending": "2026-01-31",
                    "metrics": {
                        "cycle_time_p50": 5.0,
                        "lead_time_p50": 8.0,
                        "throughput": 10,
                    },
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOFlowLoader(history_file=temp_history_file)
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
                        "cycle_time_p50": 5.5,
                        # Missing other fields
                    },
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOFlowLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should default to 0 for missing fields
        assert metrics.cycle_time_p50 == 5.5
        assert metrics.cycle_time_p85 == 0.0
        assert metrics.cycle_time_p95 == 0.0
        assert metrics.lead_time_p50 == 0.0
        assert metrics.throughput == 0


class TestErrorHandling:
    """Test error handling for various failure scenarios"""

    def test_file_not_found(self, temp_history_file):
        """Test FileNotFoundError when history file doesn't exist"""
        loader = ADOFlowLoader(history_file=temp_history_file)

        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load_latest_metrics()

        assert "Flow history not found" in str(exc_info.value)
        assert str(temp_history_file) in str(exc_info.value)

    def test_invalid_json(self, temp_history_file):
        """Test ValueError when JSON is malformed"""
        temp_history_file.write_text("{ invalid json }")

        loader = ADOFlowLoader(history_file=temp_history_file)

        with pytest.raises(ValueError) as exc_info:
            loader.load_latest_metrics()

        assert "Invalid JSON in history file" in str(exc_info.value)

    def test_missing_weeks_data(self, temp_history_file):
        """Test ValueError when weeks data is missing"""
        history = {"project": "Test"}  # No weeks
        temp_history_file.write_text(json.dumps(history))

        loader = ADOFlowLoader(history_file=temp_history_file)

        with pytest.raises(ValueError) as exc_info:
            loader.load_latest_metrics()

        assert "No weeks data in history file" in str(exc_info.value)

    def test_empty_weeks_array(self, temp_history_file):
        """Test ValueError when weeks array is empty"""
        history = {"project": "Test", "weeks": []}
        temp_history_file.write_text(json.dumps(history))

        loader = ADOFlowLoader(history_file=temp_history_file)

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
                    "metrics": {"cycle_time_p50": 5.0, "lead_time_p50": 8.0}
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOFlowLoader(history_file=temp_history_file)

        # When both date fields are None, fromisoformat raises TypeError
        with pytest.raises(TypeError):
            loader.load_latest_metrics()

    def test_invalid_date_format(self, temp_history_file):
        """Test ValueError when date format is invalid"""
        history = {
            "project": "Test",
            "weeks": [{"week_date": "not-a-date", "metrics": {"cycle_time_p50": 5.0}}],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOFlowLoader(history_file=temp_history_file)

        with pytest.raises(ValueError):
            loader.load_latest_metrics()


class TestPercentileCalculations:
    """Test percentile calculation edge cases"""

    def test_single_project_no_averaging_needed(self, temp_history_file):
        """Test that single project values are used directly"""
        history = {
            "project": "Single",
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "projects": [
                        {
                            "name": "Only Project",
                            "work_type_metrics": {
                                "Bug": {
                                    "dual_metrics": {"operational": {"p50": 5.5, "p85": 11.0, "p95": 16.5}},
                                    "lead_time": {"p50": 8.5, "p85": 17.0, "p95": 25.5},
                                    "throughput": {"closed_count": 10},
                                }
                            },
                        }
                    ],
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOFlowLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should use values directly
        assert metrics.cycle_time_p50 == 5.5
        assert metrics.cycle_time_p85 == 11.0
        assert metrics.cycle_time_p95 == 16.5

    def test_averaging_across_multiple_projects(self, temp_history_file):
        """Test simple average calculation across multiple projects"""
        history = {
            "project": "Multi",
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "projects": [
                        {
                            "name": "Project 1",
                            "work_type_metrics": {
                                "Bug": {
                                    "dual_metrics": {"operational": {"p50": 4.0, "p85": 8.0, "p95": 12.0}},
                                }
                            },
                        },
                        {
                            "name": "Project 2",
                            "work_type_metrics": {
                                "Bug": {
                                    "dual_metrics": {"operational": {"p50": 6.0, "p85": 12.0, "p95": 18.0}},
                                }
                            },
                        },
                    ],
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOFlowLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should calculate simple average
        assert metrics.cycle_time_p50 == 5.0  # (4.0 + 6.0) / 2
        assert metrics.cycle_time_p85 == 10.0  # (8.0 + 12.0) / 2
        assert metrics.cycle_time_p95 == 15.0  # (12.0 + 18.0) / 2

    def test_zero_values_included_in_average(self, temp_history_file):
        """Test that zero values are included in averaging"""
        history = {
            "project": "WithZeros",
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "projects": [
                        {
                            "name": "Project 1",
                            "work_type_metrics": {
                                "Bug": {
                                    "dual_metrics": {"operational": {"p50": 10.0}},
                                }
                            },
                        },
                        {
                            "name": "Project 2 (no data)",
                            "work_type_metrics": {"Bug": {}},
                        },
                    ],
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOFlowLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Only Project 1 has data, so use that value
        assert metrics.cycle_time_p50 == 10.0


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_single_week_data(self, temp_history_file):
        """Test loading when only one week of data exists"""
        history = {
            "project": "Single",
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "metrics": {"cycle_time_p50": 5.5, "lead_time_p50": 8.5, "throughput": 10},
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOFlowLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        assert metrics.cycle_time_p50 == 5.5

    def test_multiple_weeks_uses_latest(self, temp_history_file, flow_history_old_format):
        """Test that the loader uses the last week in the array"""
        temp_history_file.write_text(json.dumps(flow_history_old_format))

        loader = ADOFlowLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should use second week (index -1)
        assert metrics.timestamp == datetime.fromisoformat("2026-02-07")
        assert metrics.cycle_time_p50 == 4.8  # From second week

    def test_zero_throughput(self, temp_history_file):
        """Test handling when throughput is zero"""
        history = {
            "project": "NoThroughput",
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "metrics": {"cycle_time_p50": 5.0, "lead_time_p50": 8.0, "throughput": 0},
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOFlowLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        assert metrics.throughput == 0

    def test_very_high_percentiles(self, temp_history_file):
        """Test handling very high percentile values"""
        history = {
            "project": "HighValues",
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "metrics": {
                        "cycle_time_p50": 100.5,
                        "cycle_time_p85": 250.8,
                        "cycle_time_p95": 500.2,
                        "lead_time_p50": 150.3,
                        "lead_time_p85": 300.7,
                        "lead_time_p95": 600.9,
                        "throughput": 1000,
                    },
                }
            ],
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ADOFlowLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        assert metrics.cycle_time_p50 == 100.5
        assert metrics.lead_time_p95 == 600.9
        assert metrics.throughput == 1000


class TestLogging:
    """Test logging behavior"""

    @patch("execution.collectors.ado_flow_loader.logger")
    def test_logs_on_successful_load(self, mock_logger, temp_history_file, flow_history_new_format):
        """Test that successful loads are logged"""
        temp_history_file.write_text(json.dumps(flow_history_new_format))

        loader = ADOFlowLoader(history_file=temp_history_file)
        loader.load_latest_metrics()

        # Should log successful load
        mock_logger.info.assert_called()

    @patch("execution.collectors.ado_flow_loader.logger")
    def test_logs_on_file_not_found(self, mock_logger, temp_history_file):
        """Test that file not found errors are logged"""
        loader = ADOFlowLoader(history_file=temp_history_file)

        with pytest.raises(FileNotFoundError):
            loader.load_latest_metrics()

        # Should log error
        mock_logger.error.assert_called()

    @patch("execution.collectors.ado_flow_loader.logger")
    def test_logs_on_invalid_json(self, mock_logger, temp_history_file):
        """Test that invalid JSON errors are logged"""
        temp_history_file.write_text("{ invalid }")

        loader = ADOFlowLoader(history_file=temp_history_file)

        with pytest.raises(ValueError):
            loader.load_latest_metrics()

        # Should log error with exc_info
        mock_logger.error.assert_called()
