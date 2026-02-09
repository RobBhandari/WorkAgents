"""
Tests for TrendPredictor - Bug Trend Prediction and Anomaly Detection

Tests linear regression predictions and z-score anomaly detection.
"""

import json
import sys
from pathlib import Path

import pytest

from execution.ml import TrendPredictor


@pytest.fixture
def mock_quality_history_ml(tmp_path):
    """Create mock quality history for ML testing with realistic trend."""
    observatory_dir = tmp_path / ".tmp" / "observatory"
    observatory_dir.mkdir(parents=True)

    quality_file = observatory_dir / "quality_history.json"

    # Create 10 weeks of data with slight upward trend + some noise
    quality_data = {
        "weeks": [
            {
                "week_date": f"2026-01-{i:02d}",
                "week_number": i,
                "projects": [
                    {
                        "project_key": "Test_Project",
                        "project_name": "Test Project",
                        "open_bugs_count": 100 + (i * 2) + ((-1) ** i * 5),  # Trend + noise
                        "total_bugs_analyzed": 50,
                    },
                    {
                        "project_key": "Another_Project",
                        "project_name": "Another Project",
                        "open_bugs_count": 50,
                        "total_bugs_analyzed": 25,
                    },
                ],
            }
            for i in range(1, 11)
        ]
    }

    with open(quality_file, "w", encoding="utf-8") as f:
        json.dump(quality_data, f)

    return quality_file


@pytest.fixture
def mock_quality_history_with_anomaly(tmp_path):
    """Create mock quality history with a clear anomaly spike."""
    observatory_dir = tmp_path / ".tmp" / "observatory"
    observatory_dir.mkdir(parents=True)

    quality_file = observatory_dir / "quality_history.json"

    # Week 6 has a spike (anomaly)
    bug_counts = [100, 105, 103, 108, 107, 200, 110, 112, 115, 113]

    quality_data = {
        "weeks": [
            {
                "week_date": f"2026-01-{i:02d}",
                "week_number": i,
                "projects": [
                    {
                        "project_key": "Spike_Project",
                        "project_name": "Spike Project",
                        "open_bugs_count": bug_counts[i - 1],
                        "total_bugs_analyzed": 50,
                    }
                ],
            }
            for i in range(1, 11)
        ]
    }

    with open(quality_file, "w", encoding="utf-8") as f:
        json.dump(quality_data, f)

    return quality_file


class TestTrendPredictor:
    """Test suite for TrendPredictor."""

    def test_initialization(self, tmp_path):
        """Test predictor initializes with custom path."""
        custom_path = tmp_path / "custom_history.json"
        predictor = TrendPredictor(history_file=custom_path)

        assert predictor.history_file == custom_path
        assert predictor.model is not None

    def test_initialization_default_path(self):
        """Test predictor uses default path."""
        predictor = TrendPredictor()

        assert predictor.history_file == Path(".tmp/observatory/quality_history.json")

    def test_predict_trends_success(self, mock_quality_history_ml, monkeypatch):
        """Test successful trend prediction."""

        # Monkeypatch to use test file
        def mock_init(self, history_file=None):
            self.history_file = mock_quality_history_ml
            from sklearn.linear_model import LinearRegression

            self.model = LinearRegression()

        monkeypatch.setattr(TrendPredictor, "__init__", mock_init)

        predictor = TrendPredictor()
        analysis = predictor.predict_trends("Test_Project", weeks_ahead=4)

        # Verify structure
        assert analysis.project_key == "Test_Project"
        assert analysis.current_count > 0
        assert analysis.trend_direction in ["increasing", "decreasing", "stable"]
        assert len(analysis.predictions) == 4
        assert analysis.model_r2_score >= 0.0  # R² can be negative for bad fit
        assert analysis.prediction_date is not None

        # Verify prediction structure
        for pred in analysis.predictions:
            assert pred.week_ending is not None
            assert pred.predicted_count >= 0
            assert len(pred.confidence_interval) == 2
            assert pred.confidence_interval[0] <= pred.predicted_count <= pred.confidence_interval[1]
            assert isinstance(pred.is_anomaly_expected, bool)

    def test_predict_trends_with_anomaly_detection(self, mock_quality_history_with_anomaly, monkeypatch):
        """Test anomaly detection in historical data."""

        # Monkeypatch to use test file
        def mock_init(self, history_file=None):
            self.history_file = mock_quality_history_with_anomaly
            from sklearn.linear_model import LinearRegression

            self.model = LinearRegression()

        monkeypatch.setattr(TrendPredictor, "__init__", mock_init)

        predictor = TrendPredictor()
        analysis = predictor.predict_trends("Spike_Project", weeks_ahead=4)

        # Should detect the spike in week 6 (200 bugs vs ~110 average)
        assert len(analysis.anomalies_detected) > 0

        # Verify anomaly structure
        for anomaly in analysis.anomalies_detected:
            assert "week_ending" in anomaly
            assert "bug_count" in anomaly
            assert "z_score" in anomaly
            assert "severity" in anomaly
            assert anomaly["severity"] in ["high", "medium"]
            assert abs(anomaly["z_score"]) > 2.0  # Must exceed threshold

    def test_predict_trends_insufficient_data(self, tmp_path, monkeypatch):
        """Test error when insufficient data (< 3 weeks)."""
        # Create minimal history
        observatory_dir = tmp_path / ".tmp" / "observatory"
        observatory_dir.mkdir(parents=True)
        quality_file = observatory_dir / "quality_history.json"

        quality_data = {
            "weeks": [
                {
                    "week_date": "2026-01-01",
                    "week_number": 1,
                    "projects": [{"project_key": "Minimal_Project", "open_bugs_count": 50}],
                }
            ]
        }

        with open(quality_file, "w", encoding="utf-8") as f:
            json.dump(quality_data, f)

        def mock_init(self, history_file=None):
            self.history_file = quality_file
            from sklearn.linear_model import LinearRegression

            self.model = LinearRegression()

        monkeypatch.setattr(TrendPredictor, "__init__", mock_init)

        predictor = TrendPredictor()

        with pytest.raises(ValueError, match="Insufficient data"):
            predictor.predict_trends("Minimal_Project", weeks_ahead=4)

    def test_predict_trends_project_not_found(self, mock_quality_history_ml, monkeypatch):
        """Test error when project doesn't exist."""

        def mock_init(self, history_file=None):
            self.history_file = mock_quality_history_ml
            from sklearn.linear_model import LinearRegression

            self.model = LinearRegression()

        monkeypatch.setattr(TrendPredictor, "__init__", mock_init)

        predictor = TrendPredictor()

        with pytest.raises(ValueError, match="No data found for project"):
            predictor.predict_trends("NonExistent_Project", weeks_ahead=4)

    def test_predict_trends_file_not_found(self, tmp_path):
        """Test error when history file doesn't exist."""
        nonexistent_file = tmp_path / "nonexistent.json"
        predictor = TrendPredictor(history_file=nonexistent_file)

        with pytest.raises(FileNotFoundError):
            predictor.predict_trends("Any_Project", weeks_ahead=4)

    def test_trend_direction_increasing(self, tmp_path, monkeypatch):
        """Test increasing trend detection."""
        observatory_dir = tmp_path / ".tmp" / "observatory"
        observatory_dir.mkdir(parents=True)
        quality_file = observatory_dir / "quality_history.json"

        # Clear increasing trend
        quality_data = {
            "weeks": [
                {
                    "week_date": f"2026-01-{i:02d}",
                    "week_number": i,
                    "projects": [{"project_key": "Increasing_Project", "open_bugs_count": 50 + (i * 10)}],
                }
                for i in range(1, 8)
            ]
        }

        with open(quality_file, "w", encoding="utf-8") as f:
            json.dump(quality_data, f)

        def mock_init(self, history_file=None):
            self.history_file = quality_file
            from sklearn.linear_model import LinearRegression

            self.model = LinearRegression()

        monkeypatch.setattr(TrendPredictor, "__init__", mock_init)

        predictor = TrendPredictor()
        analysis = predictor.predict_trends("Increasing_Project", weeks_ahead=2)

        assert analysis.trend_direction == "increasing"

    def test_trend_direction_decreasing(self, tmp_path, monkeypatch):
        """Test decreasing trend detection."""
        observatory_dir = tmp_path / ".tmp" / "observatory"
        observatory_dir.mkdir(parents=True)
        quality_file = observatory_dir / "quality_history.json"

        # Clear decreasing trend
        quality_data = {
            "weeks": [
                {
                    "week_date": f"2026-01-{i:02d}",
                    "week_number": i,
                    "projects": [{"project_key": "Decreasing_Project", "open_bugs_count": 200 - (i * 10)}],
                }
                for i in range(1, 8)
            ]
        }

        with open(quality_file, "w", encoding="utf-8") as f:
            json.dump(quality_data, f)

        def mock_init(self, history_file=None):
            self.history_file = quality_file
            from sklearn.linear_model import LinearRegression

            self.model = LinearRegression()

        monkeypatch.setattr(TrendPredictor, "__init__", mock_init)

        predictor = TrendPredictor()
        analysis = predictor.predict_trends("Decreasing_Project", weeks_ahead=2)

        assert analysis.trend_direction == "decreasing"

    def test_trend_direction_stable(self, tmp_path, monkeypatch):
        """Test stable trend detection."""
        observatory_dir = tmp_path / ".tmp" / "observatory"
        observatory_dir.mkdir(parents=True)
        quality_file = observatory_dir / "quality_history.json"

        # Stable with minor noise
        quality_data = {
            "weeks": [
                {
                    "week_date": f"2026-01-{i:02d}",
                    "week_number": i,
                    "projects": [{"project_key": "Stable_Project", "open_bugs_count": 100 + ((-1) ** i * 2)}],
                }
                for i in range(1, 8)
            ]
        }

        with open(quality_file, "w", encoding="utf-8") as f:
            json.dump(quality_data, f)

        def mock_init(self, history_file=None):
            self.history_file = quality_file
            from sklearn.linear_model import LinearRegression

            self.model = LinearRegression()

        monkeypatch.setattr(TrendPredictor, "__init__", mock_init)

        predictor = TrendPredictor()
        analysis = predictor.predict_trends("Stable_Project", weeks_ahead=2)

        assert analysis.trend_direction == "stable"

    def test_predictions_are_non_negative(self, mock_quality_history_ml, monkeypatch):
        """Test that predictions never return negative bug counts."""

        def mock_init(self, history_file=None):
            self.history_file = mock_quality_history_ml
            from sklearn.linear_model import LinearRegression

            self.model = LinearRegression()

        monkeypatch.setattr(TrendPredictor, "__init__", mock_init)

        predictor = TrendPredictor()
        analysis = predictor.predict_trends("Test_Project", weeks_ahead=4)

        for pred in analysis.predictions:
            assert pred.predicted_count >= 0
            assert pred.confidence_interval[0] >= 0  # Lower bound also non-negative
