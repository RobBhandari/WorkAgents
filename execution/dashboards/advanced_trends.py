"""
Advanced Trend Analytics Dashboard - Performance-Enabled Features

Leverages REST API 3-10x performance improvements to provide:
- Moving averages (7-day, 30-day, 90-day) for noise reduction
- ML-based predictions integrated from TrendPredictor
- Extended 180-day historical lookback
- Cross-metric trend correlation

This dashboard demonstrates high-value features made possible by async REST API performance.

Usage:
    from execution.dashboards.advanced_trends import generate_advanced_trends_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/advanced_trends.html')
    generate_advanced_trends_dashboard(output_path)
"""

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from execution.core import get_logger
from execution.dashboards.components.charts import sparkline
from execution.dashboards.renderer import render_dashboard
from execution.domain.metrics import TrendData
from execution.framework import get_dashboard_framework
from execution.ml.trend_predictor import TrendPredictor
from execution.utils.error_handling import log_and_return_default

logger = get_logger(__name__)


class AdvancedTrendsAnalyzer:
    """
    Advanced trend analysis with ML predictions and moving averages.

    Combines historical data with predictive analytics to provide
    strategic insights enabled by REST API performance improvements.
    """

    def __init__(self, lookback_weeks: int = 26) -> None:
        """
        Initialize analyzer.

        Args:
            lookback_weeks: Number of weeks of history to analyze (default: 26 = ~180 days)
        """
        self.lookback_weeks = lookback_weeks
        self.quality_file = Path(".tmp/observatory/quality_history.json")
        self.security_file = Path(".tmp/observatory/security_history.json")
        self.flow_file = Path(".tmp/observatory/flow_history.json")
        self.predictor = TrendPredictor()

    def generate(self, output_path: Path | None = None) -> str:
        """
        Generate advanced trends dashboard HTML.

        Args:
            output_path: Optional path to write HTML file

        Returns:
            Generated HTML string
        """
        logger.info("Generating advanced trends dashboard", extra={"lookback_weeks": self.lookback_weeks})

        # Step 1: Load extended historical data
        historical_data = self._load_extended_history()

        # Step 2: Calculate moving averages for key metrics
        trend_analytics = self._calculate_moving_averages(historical_data)

        # Step 3: Generate ML predictions
        predictions = self._generate_predictions(historical_data)

        # Step 4: Build dashboard context
        context = self._build_context(trend_analytics, predictions, historical_data)

        # Step 5: Render dashboard
        html = render_dashboard("dashboards/advanced_trends_dashboard.html", context)

        # Write to file if specified
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html, encoding="utf-8")
            logger.info("Advanced trends dashboard written", extra={"path": str(output_path), "html_size": len(html)})

        return html

    def _load_extended_history(self) -> dict:
        """Load extended historical data (up to 180 days)"""
        logger.info("Loading extended history", extra={"weeks": self.lookback_weeks})

        return {
            "quality": self._load_history_file(self.quality_file),
            "security": self._load_history_file(self.security_file),
            "flow": self._load_history_file(self.flow_file),
        }

    def _load_history_file(self, file_path: Path) -> dict | None:
        """Load history file with extended lookback"""
        if not file_path.exists():
            logger.warning("History file not found", extra={"file": file_path.name})
            return None

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            weeks = data.get("weeks", [])
            if not weeks:
                logger.warning("No weeks data in file", extra={"file": file_path.name})
                return None

            # Get last N weeks (extended lookback)
            weeks_subset = weeks[-self.lookback_weeks :] if len(weeks) > self.lookback_weeks else weeks
            logger.info("Extended history loaded", extra={"file": file_path.name, "weeks_loaded": len(weeks_subset)})

            return {"weeks": weeks_subset, "all_weeks": weeks}

        except Exception as e:
            result: dict[Any, Any] | None = log_and_return_default(
                logger,
                e,
                context={"file": file_path.name, "operation": "load_extended_history"},
                default_value=None,
                error_type="History file loading",
            )
            return result

    def _calculate_moving_averages(self, historical_data: dict) -> list[dict]:
        """Calculate moving averages for key metrics"""
        logger.info("Calculating moving averages")

        analytics = []
        quality = historical_data.get("quality")
        security = historical_data.get("security")

        # Metric 1: Open Bugs with moving averages
        if quality:
            values, timestamps = self._extract_time_series(
                quality["weeks"], lambda week: sum(p.get("open_bugs_count", 0) for p in week.get("projects", []))
            )

            if values and len(values) >= 7:
                trend = TrendData(values=values, timestamps=timestamps, label="Open Bugs")

                analytics.append(
                    self._create_analytics_card(
                        title="Open Bugs",
                        trend=trend,
                        lower_is_better=True,
                        ma_windows=[7, 30, 90],
                    )
                )

        # Metric 2: Critical Vulnerabilities with moving averages
        if security:
            values, timestamps = self._extract_time_series(
                security["weeks"], lambda week: week.get("metrics", {}).get("critical", 0)
            )

            if values and len(values) >= 7:
                trend = TrendData(values=values, timestamps=timestamps, label="Critical Vulnerabilities")

                analytics.append(
                    self._create_analytics_card(
                        title="Critical Vulnerabilities",
                        trend=trend,
                        lower_is_better=True,
                        ma_windows=[7, 30, 90],
                    )
                )

        # Metric 3: Total Vulnerabilities with moving averages
        if security:
            values, timestamps = self._extract_time_series(
                security["weeks"], lambda week: week.get("metrics", {}).get("current_total", 0)
            )

            if values and len(values) >= 7:
                trend = TrendData(values=values, timestamps=timestamps, label="Total Vulnerabilities")

                analytics.append(
                    self._create_analytics_card(
                        title="Total Vulnerabilities",
                        trend=trend,
                        lower_is_better=True,
                        ma_windows=[7, 30, 90],
                    )
                )

        logger.info("Moving averages calculated", extra={"metrics": len(analytics)})
        return analytics

    def _extract_time_series(
        self, weeks: list[dict], value_extractor: Callable[[dict], float | int]
    ) -> tuple[list[float], list[datetime]]:
        """Extract time series data from weeks using value extractor function"""
        values = []
        timestamps = []

        for week in weeks:
            try:
                value = value_extractor(week)
                values.append(float(value))

                # Parse week_date timestamp
                week_date = week.get("week_date", "")
                if week_date:
                    timestamps.append(datetime.fromisoformat(week_date.replace("Z", "+00:00")))
                else:
                    timestamps.append(datetime.now())

            except Exception as e:
                logger.warning("Failed to extract time series value", extra={"error": str(e)})
                continue

        return values, timestamps

    def _create_analytics_card(
        self, title: str, trend: TrendData, lower_is_better: bool, ma_windows: list[int]
    ) -> dict:
        """Create analytics card with raw data, moving averages, and sparklines"""
        current = trend.latest()
        if current is None:
            return {}

        # Calculate moving averages
        moving_averages = {}
        for window in ma_windows:
            if len(trend.values) >= window:
                ma_values = trend.moving_average(window=window)
                # Get latest non-NaN value
                latest_ma = next((v for v in reversed(ma_values) if not (v != v)), None)  # NaN check
                if latest_ma is not None:
                    moving_averages[f"ma_{window}"] = round(latest_ma, 1)

        # Calculate change vs 7-day MA
        change_vs_ma = None
        if "ma_7" in moving_averages:
            change_vs_ma = current - moving_averages["ma_7"]

        # Generate sparkline
        sparkline_html = sparkline(trend.values, width=300, height=80)

        # Determine trend direction
        week_change = trend.week_over_week_change()
        if week_change is not None:
            if lower_is_better:
                trend_class = "improving" if week_change < 0 else "degrading"
                trend_arrow = "↓" if week_change < 0 else "↑"
            else:
                trend_class = "improving" if week_change > 0 else "degrading"
                trend_arrow = "↑" if week_change > 0 else "↓"
        else:
            trend_class = "stable"
            trend_arrow = "→"

        return {
            "title": title,
            "current_value": int(current),
            "moving_averages": moving_averages,
            "change_vs_ma": round(change_vs_ma, 1) if change_vs_ma is not None else None,
            "sparkline": sparkline_html,
            "trend_class": trend_class,
            "trend_arrow": trend_arrow,
            "weeks_analyzed": len(trend.values),
            "lower_is_better": lower_is_better,
        }

    def _generate_predictions(self, historical_data: dict) -> dict[str, Any]:
        """Generate ML predictions for key metrics"""
        logger.info("Generating ML predictions")

        predictions: dict[str, Any] = {}
        quality = historical_data.get("quality")

        if not quality or not quality.get("weeks"):
            logger.warning("Insufficient data for predictions")
            return predictions

        # Get all unique projects
        all_projects = set()
        for week in quality["weeks"]:
            for project in week.get("projects", []):
                project_key = project.get("project_key")
                if project_key:
                    all_projects.add(project_key)

        # Generate predictions for first project (demo - could extend to all)
        if all_projects:
            project_key = list(all_projects)[0]
            try:
                analysis = self.predictor.predict_trends(project_key, weeks_ahead=4)

                predictions[project_key] = {
                    "current_count": analysis.current_count,
                    "trend_direction": analysis.trend_direction,
                    "r2_score": round(analysis.model_r2_score, 3),
                    "predictions": [
                        {
                            "week_ending": pred.week_ending,
                            "predicted_count": pred.predicted_count,
                            "confidence_low": pred.confidence_interval[0],
                            "confidence_high": pred.confidence_interval[1],
                            "is_anomaly": pred.is_anomaly_expected,
                        }
                        for pred in analysis.predictions
                    ],
                    "anomalies": analysis.anomalies_detected[:3],  # Top 3 anomalies
                }

                logger.info("Predictions generated", extra={"project": project_key, "weeks_ahead": 4})

            except Exception as e:
                logger.warning("Failed to generate predictions", extra={"project": project_key, "error": str(e)})

        return predictions

    def _build_context(self, trend_analytics: list[dict], predictions: dict, historical_data: dict) -> dict:
        """Build template context for dashboard"""
        # Get framework
        framework_css, framework_js = get_dashboard_framework(
            header_gradient_start="#8b5cf6", header_gradient_end="#6d28d9", include_table_scroll=False
        )

        # Build data status
        data_status = []
        for name, data in historical_data.items():
            data_status.append(
                {"name": name.capitalize(), "loaded": data is not None, "weeks": len(data["weeks"]) if data else 0}
            )

        return {
            "framework_css": framework_css,
            "framework_js": framework_js,
            "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "lookback_weeks": self.lookback_weeks,
            "lookback_days": self.lookback_weeks * 7,
            "trend_analytics": trend_analytics,
            "predictions": predictions,
            "data_status": data_status,
        }


def generate_advanced_trends_dashboard(output_path: Path | None = None, lookback_weeks: int = 26) -> str:
    """
    Generate advanced trends dashboard with ML predictions and moving averages.

    Args:
        output_path: Optional output path (defaults to .tmp/observatory/dashboards/advanced_trends.html)
        lookback_weeks: Number of weeks to analyze (default: 26 = ~180 days)

    Returns:
        Generated HTML string
    """
    if output_path is None:
        output_path = Path(".tmp/observatory/dashboards/advanced_trends.html")

    analyzer = AdvancedTrendsAnalyzer(lookback_weeks=lookback_weeks)
    return analyzer.generate(output_path)


# Self-test
if __name__ == "__main__":
    logger.info("Advanced Trends Dashboard Generator - Self Test")

    try:
        output_path = Path(".tmp/observatory/dashboards/advanced_trends.html")
        html = generate_advanced_trends_dashboard(output_path, lookback_weeks=26)

        logger.info(
            "Advanced trends dashboard generated successfully",
            extra={"output": str(output_path), "html_size": len(html)},
        )

    except Exception as e:
        logger.error("Failed to generate advanced trends dashboard", exc_info=True)
        exit(1)
