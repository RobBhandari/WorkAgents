"""
Cross-metric anomaly detector for Observatory dashboards.

Reads pre-computed rolling_stats from the SQLite database and flags the
most-recent data point for each (dashboard, project, metric) series when its
z-score exceeds a configurable threshold.

Usage::

    from execution.ml.anomaly_detector import AnomalyDetector

    detector = AnomalyDetector(db_path=Path(".tmp/observatory/observatory.db"))
    anomalies = detector.detect_all()   # list[AnomalyResult]
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from execution.core import get_logger

logger = get_logger(__name__)

DEFAULT_DB_PATH = Path(".tmp/observatory/observatory.db")
DEFAULT_ZSCORE_THRESHOLD = 2.0


@dataclass
class AnomalyResult:
    """A single flagged data point."""

    dashboard: str
    project_name: str
    metric_name: str
    metric_date: str
    value: float
    expected: float  # rolling mean
    z_score: float
    direction: str  # "above" | "below"
    severity: str  # "high" (|z|>3) | "medium" (|z|>2)


class AnomalyDetector:
    """
    Detect anomalous data points across all Observatory metrics.

    Algorithm: for each series (dashboard, project, metric) compare the most
    recent value against the rolling_stats computed by import_to_sqlite.
    Flag values whose z-score exceeds *threshold*.
    """

    def __init__(
        self,
        db_path: Path = DEFAULT_DB_PATH,
        threshold: float = DEFAULT_ZSCORE_THRESHOLD,
    ) -> None:
        self.db_path = db_path
        self.threshold = threshold

    def detect_all(self) -> list[AnomalyResult]:
        """
        Run anomaly detection across every metric series.

        Returns:
            List of AnomalyResult, sorted by severity (high first) then z-score.

        Raises:
            FileNotFoundError: If the SQLite database does not exist.
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"Analytics database not found: {self.db_path}")

        conn = sqlite3.connect(self.db_path)
        try:
            return self._run_detection(conn)
        finally:
            conn.close()

    def detect_for_dashboard(self, dashboard: str) -> list[AnomalyResult]:
        """Run anomaly detection for a single dashboard only."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Analytics database not found: {self.db_path}")

        conn = sqlite3.connect(self.db_path)
        try:
            return [r for r in self._run_detection(conn) if r.dashboard == dashboard]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_detection(self, conn: sqlite3.Connection) -> list[AnomalyResult]:
        cursor = conn.cursor()

        # Fetch rolling stats for all series
        cursor.execute(
            "SELECT dashboard, project_name, metric_name, rolling_mean, rolling_std "
            "FROM rolling_stats "
            "WHERE rolling_std > 0"
        )
        stats_rows = cursor.fetchall()

        if not stats_rows:
            logger.warning("No rolling stats found in database — run import first")
            return []

        results: list[AnomalyResult] = []

        for dashboard, project_name, metric_name, rolling_mean, rolling_std in stats_rows:
            latest = self._fetch_latest_value(cursor, dashboard, project_name, metric_name)
            if latest is None:
                continue

            metric_date, value = latest
            z_score = (value - rolling_mean) / rolling_std

            if abs(z_score) < self.threshold:
                continue

            severity = "high" if abs(z_score) > 3.0 else "medium"
            direction = "above" if z_score > 0 else "below"

            results.append(
                AnomalyResult(
                    dashboard=dashboard,
                    project_name=project_name,
                    metric_name=metric_name,
                    metric_date=metric_date,
                    value=value,
                    expected=rolling_mean,
                    z_score=round(z_score, 2),
                    direction=direction,
                    severity=severity,
                )
            )

        logger.info(
            "Anomaly detection complete",
            extra={"total_anomalies": len(results), "threshold": self.threshold},
        )

        # Sort: high severity first, then by absolute z-score descending
        return sorted(results, key=lambda r: (r.severity != "high", -abs(r.z_score)))

    def _fetch_latest_value(
        self,
        cursor: sqlite3.Cursor,
        dashboard: str,
        project_name: str,
        metric_name: str,
    ) -> tuple[str, float] | None:
        """Return (metric_date, value) for the most recent row in this series."""
        cursor.execute(
            "SELECT metric_date, metric_value FROM metrics "
            "WHERE dashboard=? AND project_name=? AND metric_name=? "
            "AND metric_value IS NOT NULL "
            "ORDER BY metric_date DESC LIMIT 1",
            (dashboard, project_name, metric_name),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return str(row[0]), float(row[1])
