"""
Bug Trend Predictor - Linear Regression for Quality Metrics

Simple ML model for:
- Predicting next 4 weeks of bug counts
- Detecting anomalous spikes in bug trends
- Providing confidence intervals

Uses scikit-learn LinearRegression with rolling windows.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

import numpy as np
from sklearn.linear_model import LinearRegression

from execution.core import get_logger

logger = get_logger(__name__)


@dataclass
class BugPrediction:
    """Single week bug count prediction."""
    week_ending: str
    predicted_count: int
    confidence_interval: Tuple[int, int]  # (lower, upper)
    is_anomaly_expected: bool


@dataclass
class TrendAnalysis:
    """Complete trend analysis with predictions and anomalies."""
    project_key: str
    current_count: int
    trend_direction: str  # "increasing", "decreasing", "stable"
    predictions: List[BugPrediction]
    anomalies_detected: List[dict]  # Historical anomalies
    model_r2_score: float
    prediction_date: str


class TrendPredictor:
    """Predict bug trends using linear regression."""

    def __init__(self, history_file: Path | None = None):
        """
        Initialize predictor.

        Args:
            history_file: Path to quality history JSON (default: .tmp/observatory/quality_history.json)
        """
        self.history_file = history_file or Path(".tmp/observatory/quality_history.json")
        self.model = LinearRegression()

    def predict_trends(self, project_key: str, weeks_ahead: int = 4) -> TrendAnalysis:
        """
        Predict bug trends for a specific project.

        Args:
            project_key: Project identifier (e.g., "One_Office")
            weeks_ahead: Number of weeks to predict (default: 4)

        Returns:
            TrendAnalysis with predictions and anomaly detection

        Raises:
            FileNotFoundError: If history file doesn't exist
            ValueError: If insufficient data for prediction
        """
        logger.info("Starting trend prediction", extra={"project": project_key, "weeks_ahead": weeks_ahead})

        # Load historical data
        historical_data = self._load_project_history(project_key)

        if len(historical_data) < 3:
            raise ValueError(f"Insufficient data for prediction: need at least 3 weeks, got {len(historical_data)}")

        # Extract time series
        weeks = np.array([i for i in range(len(historical_data))])
        bug_counts = np.array([d["open_bugs"] for d in historical_data])

        # Train linear regression model
        X = weeks.reshape(-1, 1)
        y = bug_counts
        self.model.fit(X, y)
        r2_score = self.model.score(X, y)

        logger.info("Model trained", extra={"r2_score": r2_score, "samples": len(historical_data)})

        # Detect anomalies in historical data
        anomalies = self._detect_anomalies(historical_data, bug_counts)

        # Make predictions
        future_weeks = np.array([len(weeks) + i for i in range(1, weeks_ahead + 1)])
        predictions = self._make_predictions(future_weeks, historical_data[-1]["week_ending"], bug_counts)

        # Determine trend direction
        trend_slope = self.model.coef_[0]
        if trend_slope > 2:
            trend_direction = "increasing"
        elif trend_slope < -2:
            trend_direction = "decreasing"
        else:
            trend_direction = "stable"

        logger.info(
            "Trend analysis complete",
            extra={
                "trend_direction": trend_direction,
                "slope": trend_slope,
                "anomalies_found": len(anomalies)
            }
        )

        return TrendAnalysis(
            project_key=project_key,
            current_count=int(bug_counts[-1]),
            trend_direction=trend_direction,
            predictions=predictions,
            anomalies_detected=anomalies,
            model_r2_score=r2_score,
            prediction_date=datetime.now().isoformat()
        )

    def _load_project_history(self, project_key: str) -> List[dict]:
        """
        Load historical bug counts for a project.

        Returns:
            List of {week_ending, open_bugs} dicts, sorted by date
        """
        if not self.history_file.exists():
            logger.error("History file not found", extra={"file_path": str(self.history_file)})
            raise FileNotFoundError(f"Quality history not found: {self.history_file}")

        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            history = []
            for week in data.get("weeks", []):
                for project in week.get("projects", []):
                    if project.get("project_key") == project_key:
                        history.append({
                            "week_ending": week["week_date"],
                            "open_bugs": project["open_bugs_count"]
                        })
                        break

            if not history:
                raise ValueError(f"No data found for project: {project_key}")

            logger.info("Loaded project history", extra={"project": project_key, "weeks": len(history)})
            return history

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in history file", exc_info=True)
            raise ValueError(f"Invalid JSON: {e}")

    def _detect_anomalies(self, historical_data: List[dict], bug_counts: np.ndarray) -> List[dict]:
        """
        Detect anomalies using z-score method.

        An anomaly is a week where bug count is >2 standard deviations from mean.

        Returns:
            List of anomaly dicts with week_ending, count, and z_score
        """
        mean = np.mean(bug_counts)
        std = np.std(bug_counts)

        if std == 0:
            return []  # No variance, no anomalies

        anomalies = []
        for i, count in enumerate(bug_counts):
            z_score = (count - mean) / std
            if abs(z_score) > 2.0:  # 2 standard deviations
                anomalies.append({
                    "week_ending": historical_data[i]["week_ending"],
                    "bug_count": int(count),
                    "z_score": float(z_score),
                    "severity": "high" if abs(z_score) > 3.0 else "medium"
                })

        logger.info(
            "Anomaly detection complete",
            extra={"anomalies_found": len(anomalies), "mean": mean, "std": std}
        )

        return anomalies

    def _make_predictions(
        self,
        future_weeks: np.ndarray,
        last_week_ending: str,
        historical_counts: np.ndarray
    ) -> List[BugPrediction]:
        """
        Make predictions for future weeks with confidence intervals.

        Confidence interval = prediction ± 1.96 * std_dev (95% CI)
        """
        X_future = future_weeks.reshape(-1, 1)
        predictions = self.model.predict(X_future)

        # Calculate prediction uncertainty based on historical variance
        residuals = historical_counts - self.model.predict(np.arange(len(historical_counts)).reshape(-1, 1))
        std_dev = np.std(residuals)
        margin = 1.96 * std_dev  # 95% confidence interval

        # Calculate mean and check for anomaly likelihood
        mean_count = np.mean(historical_counts)

        results = []
        last_date = datetime.strptime(last_week_ending, "%Y-%m-%d")

        for i, pred in enumerate(predictions):
            week_date = last_date + timedelta(weeks=i + 1)
            predicted_count = max(0, int(pred))  # Can't have negative bugs

            lower_bound = max(0, int(pred - margin))
            upper_bound = int(pred + margin)

            # Flag as potential anomaly if prediction is >2 std from historical mean
            is_anomaly = abs(pred - mean_count) > (2 * std_dev)

            results.append(BugPrediction(
                week_ending=week_date.strftime("%Y-%m-%d"),
                predicted_count=predicted_count,
                confidence_interval=(lower_bound, upper_bound),
                is_anomaly_expected=bool(is_anomaly)  # Convert numpy bool to Python bool
            ))

        return results


# Self-test
if __name__ == "__main__":
    from execution.core import setup_logging

    setup_logging(level="INFO", json_output=False)

    logger.info("Trend Predictor - Self Test")
    logger.info("=" * 60)

    try:
        predictor = TrendPredictor()
        logger.info("Predictor initialized", extra={"history_file": str(predictor.history_file)})

        # Load history to find a project
        with open(predictor.history_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if data.get("weeks") and data["weeks"][0].get("projects"):
            project_key = data["weeks"][0]["projects"][0]["project_key"]
            logger.info("Testing with project", extra={"project_key": project_key})

            # Make predictions
            analysis = predictor.predict_trends(project_key, weeks_ahead=4)

            logger.info(
                "Analysis complete",
                extra={
                    "project": analysis.project_key,
                    "current_bugs": analysis.current_count,
                    "trend": analysis.trend_direction,
                    "r2_score": analysis.model_r2_score,
                    "predictions": len(analysis.predictions),
                    "anomalies": len(analysis.anomalies_detected)
                }
            )

            logger.info("Predictions:")
            for pred in analysis.predictions:
                logger.info(
                    f"  {pred.week_ending}: {pred.predicted_count} bugs "
                    f"(CI: {pred.confidence_interval[0]}-{pred.confidence_interval[1]})"
                    + (" ⚠️ ANOMALY" if pred.is_anomaly_expected else "")
                )

            if analysis.anomalies_detected:
                logger.info("Historical anomalies detected:")
                for anomaly in analysis.anomalies_detected:
                    logger.info(
                        f"  {anomaly['week_ending']}: {anomaly['bug_count']} bugs "
                        f"(z-score: {anomaly['z_score']:.2f}, severity: {anomaly['severity']})"
                    )

            logger.info("=" * 60)
            logger.info("✅ Self-test PASSED")
        else:
            logger.warning("No project data found in history file")

    except Exception as e:
        logger.error("❌ Self-test FAILED", exc_info=True)
        exit(1)
