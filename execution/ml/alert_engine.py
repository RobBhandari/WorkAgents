"""
Alert engine for Observatory dashboards.

Combines anomaly detection with threshold-based rules to produce a unified
alert list.  Alerts are persisted to the SQLite ``alerts`` table and can be
read back for dashboard rendering.

Usage::

    from execution.ml.alert_engine import AlertEngine

    engine = AlertEngine(db_path=Path(".tmp/observatory/observatory.db"))
    engine.run()                    # detect + persist alerts
    alerts = engine.load_alerts()   # list[Alert] for rendering
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from execution.core import get_logger
from execution.ml.anomaly_detector import AnomalyDetector, AnomalyResult

logger = get_logger(__name__)

DEFAULT_DB_PATH = Path(".tmp/observatory/observatory.db")


@dataclass
class ThresholdRule:
    """A hard-threshold rule for a specific metric."""

    dashboard: str
    metric_name: str
    threshold: float
    operator: str  # "below" | "above"
    severity: str  # "warn" | "critical"
    message_template: str


@dataclass
class Alert:
    """A single persisted alert for dashboard rendering."""

    dashboard: str
    project_name: str
    metric_name: str
    metric_date: str
    alert_type: str  # "anomaly" | "threshold"
    severity: str  # "warn" | "critical" | "medium" | "high"
    value: float | None
    expected: float | None
    message: str


# ---------------------------------------------------------------------------
# Built-in threshold rules
# ---------------------------------------------------------------------------

THRESHOLD_RULES: list[ThresholdRule] = [
    ThresholdRule(
        dashboard="deployment",
        metric_name="build_success_rate_pct",
        threshold=80.0,
        operator="below",
        severity="critical",
        message_template="{project} build success rate is {value:.1f}% (below 80% threshold)",
    ),
    ThresholdRule(
        dashboard="deployment",
        metric_name="deployments_per_week",
        threshold=1.0,
        operator="below",
        severity="warn",
        message_template="{project} has {value:.1f} deployments/week (below 1 threshold)",
    ),
    ThresholdRule(
        dashboard="quality",
        metric_name="open_bugs",
        threshold=500.0,
        operator="above",
        severity="warn",
        message_template="{project} has {value:.0f} open bugs (above 500 threshold)",
    ),
    ThresholdRule(
        dashboard="ownership",
        metric_name="unassigned_pct",
        threshold=60.0,
        operator="above",
        severity="warn",
        message_template="{project} unassigned work is {value:.1f}% (above 60% threshold)",
    ),
    ThresholdRule(
        dashboard="risk",
        metric_name="single_owner_pct",
        threshold=80.0,
        operator="above",
        severity="warn",
        message_template="{project} single-owner files at {value:.1f}% (above 80% threshold)",
    ),
    ThresholdRule(
        dashboard="security",
        metric_name="critical_vulns",
        threshold=0.0,
        operator="above",
        severity="critical",
        message_template="{project} has {value:.0f} critical vulnerabilities open (expected 0)",
    ),
    ThresholdRule(
        dashboard="exploitable",
        metric_name="critical_vulns",
        threshold=0.0,
        operator="above",
        severity="critical",
        message_template="{project} has {value:.0f} exploitable critical CISA KEV findings (expected 0)",
    ),
    ThresholdRule(
        dashboard="exploitable",
        metric_name="high_vulns",
        threshold=0.0,
        operator="above",
        severity="warn",
        message_template="{project} has {value:.0f} exploitable high CISA KEV findings open",
    ),
]


# ---------------------------------------------------------------------------
# AlertEngine
# ---------------------------------------------------------------------------


class AlertEngine:
    """
    Evaluate anomaly detection results and threshold rules, then persist
    qualifying alerts to the SQLite database.
    """

    def __init__(
        self,
        db_path: Path = DEFAULT_DB_PATH,
        zscore_threshold: float = 2.0,
    ) -> None:
        self.db_path = db_path
        self.zscore_threshold = zscore_threshold

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> int:
        """
        Run the full alert pipeline:
        1. Detect anomalies via AnomalyDetector
        2. Evaluate threshold rules
        3. Persist all qualifying alerts to the DB

        Returns:
            Total number of alerts written.
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"Analytics database not found: {self.db_path}")

        conn = sqlite3.connect(self.db_path)
        try:
            # Clear previous alerts to avoid accumulating stale rows
            conn.execute("DELETE FROM alerts")
            conn.commit()

            total = 0
            total += self._run_anomaly_alerts(conn)
            total += self._run_threshold_alerts(conn)

            logger.info("Alert engine complete", extra={"total_alerts": total})
            return total
        finally:
            conn.close()

    def load_alerts(self, limit: int = 50) -> list[Alert]:
        """
        Read the most recent alerts from the DB for dashboard rendering.

        Args:
            limit: Maximum number of alerts to return (ordered by severity then date).

        Returns:
            List of Alert dataclass instances.
        """
        if not self.db_path.exists():
            return []

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT dashboard, project_name, metric_name, metric_date, "
                "alert_type, severity, value, expected, message "
                "FROM alerts "
                "ORDER BY "
                "CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'warn' THEN 2 ELSE 3 END, "
                "metric_date DESC "
                "LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        return [
            Alert(
                dashboard=row[0],
                project_name=row[1],
                metric_name=row[2],
                metric_date=row[3],
                alert_type=row[4],
                severity=row[5],
                value=row[6],
                expected=row[7],
                message=row[8],
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_anomaly_alerts(self, conn: sqlite3.Connection) -> int:
        """Detect z-score anomalies and persist them as alerts."""
        detector = AnomalyDetector(db_path=self.db_path, threshold=self.zscore_threshold)
        try:
            anomalies: list[AnomalyResult] = detector.detect_all()
        except FileNotFoundError:
            return 0

        cursor = conn.cursor()
        count = 0

        for a in anomalies:
            direction_word = "spike" if a.direction == "above" else "drop"
            message = (
                f"{a.project_name} {a.metric_name}: {direction_word} detected "
                f"(value={a.value:.2f}, expected≈{a.expected:.2f}, z={a.z_score:+.1f})"
            )
            cursor.execute(
                "INSERT INTO alerts (dashboard, project_name, metric_name, metric_date, "
                "alert_type, severity, value, expected, message) "
                "VALUES (?, ?, ?, ?, 'anomaly', ?, ?, ?, ?)",
                (
                    a.dashboard,
                    a.project_name,
                    a.metric_name,
                    a.metric_date,
                    a.severity,
                    a.value,
                    a.expected,
                    message,
                ),
            )
            count += 1

        conn.commit()
        logger.info("Anomaly alerts written", extra={"count": count})
        return count

    def _run_threshold_alerts(self, conn: sqlite3.Connection) -> int:
        """Evaluate hard-threshold rules against latest metric values."""
        cursor = conn.cursor()
        count = 0

        for rule in THRESHOLD_RULES:
            cursor.execute(
                "SELECT project_name, metric_date, metric_value FROM metrics "
                "WHERE dashboard=? AND metric_name=? AND metric_value IS NOT NULL "
                "ORDER BY metric_date DESC",
                (rule.dashboard, rule.metric_name),
            )
            # Get one row per project (latest only)
            seen_projects: set[str] = set()
            for project_name, metric_date, value in cursor.fetchall():
                if project_name in seen_projects:
                    continue
                seen_projects.add(project_name)

                triggered = (rule.operator == "below" and value < rule.threshold) or (
                    rule.operator == "above" and value > rule.threshold
                )
                if not triggered:
                    continue

                message = rule.message_template.format(project=project_name, value=value)
                conn.execute(
                    "INSERT INTO alerts (dashboard, project_name, metric_name, metric_date, "
                    "alert_type, severity, value, expected, message) "
                    "VALUES (?, ?, ?, ?, 'threshold', ?, ?, ?, ?)",
                    (
                        rule.dashboard,
                        project_name,
                        rule.metric_name,
                        metric_date,
                        rule.severity,
                        value,
                        rule.threshold,
                        message,
                    ),
                )
                count += 1

        conn.commit()
        logger.info("Threshold alerts written", extra={"count": count})
        return count
