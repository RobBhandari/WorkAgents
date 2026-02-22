"""
Tests for execution/ml/alert_engine.py

Verifies threshold rules, anomaly-based alerts, and DB persistence.
"""

import sqlite3
from pathlib import Path

import pytest

from execution.ml.alert_engine import THRESHOLD_RULES, Alert, AlertEngine

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Return path to a fully-schema'd test SQLite DB."""
    p = tmp_path / "test.db"
    conn = sqlite3.connect(p)
    _create_schema(conn)
    return p


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS metrics (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_date  TEXT    NOT NULL,
            dashboard    TEXT    NOT NULL,
            project_name TEXT    NOT NULL,
            metric_name  TEXT    NOT NULL,
            metric_value REAL,
            metric_unit  TEXT
        );
        CREATE TABLE IF NOT EXISTS rolling_stats (
            dashboard    TEXT NOT NULL,
            project_name TEXT NOT NULL,
            metric_name  TEXT NOT NULL,
            rolling_mean REAL,
            rolling_std  REAL,
            trend_slope  REAL,
            last_8w_avg  REAL,
            last_updated TEXT,
            PRIMARY KEY (dashboard, project_name, metric_name)
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            dashboard    TEXT NOT NULL,
            project_name TEXT NOT NULL,
            metric_name  TEXT NOT NULL,
            metric_date  TEXT NOT NULL,
            alert_type   TEXT NOT NULL,
            severity     TEXT NOT NULL,
            value        REAL,
            expected     REAL,
            message      TEXT,
            created_at   TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()


def _insert_metric(
    conn: sqlite3.Connection, dashboard: str, project: str, metric: str, value: float, date: str = "2026-02-17"
) -> None:
    conn.execute(
        "INSERT INTO metrics (metric_date, dashboard, project_name, metric_name, metric_value) "
        "VALUES (?, ?, ?, ?, ?)",
        (date, dashboard, project, metric, value),
    )
    conn.commit()


def _insert_stats(conn: sqlite3.Connection, dashboard: str, project: str, metric: str, mean: float, std: float) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO rolling_stats "
        "(dashboard, project_name, metric_name, rolling_mean, rolling_std, "
        "trend_slope, last_8w_avg, last_updated) "
        "VALUES (?, ?, ?, ?, ?, 0.0, ?, datetime('now'))",
        (dashboard, project, metric, mean, std, mean),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Tests: threshold rules
# ---------------------------------------------------------------------------


class TestThresholdRules:
    def test_all_rules_have_required_fields(self) -> None:
        for rule in THRESHOLD_RULES:
            assert rule.dashboard
            assert rule.metric_name
            assert rule.operator in ("below", "above")
            assert rule.severity in ("warn", "critical")
            assert "{project}" in rule.message_template or "{value}" in rule.message_template

    def test_low_build_success_rate_triggers_critical(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        _insert_metric(conn, "deployment", "Product A", "build_success_rate_pct", 70.0)
        conn.close()

        engine = AlertEngine(db_path=db_path)
        engine.run()
        alerts = engine.load_alerts()

        threshold_alerts = [
            a for a in alerts if a.alert_type == "threshold" and a.metric_name == "build_success_rate_pct"
        ]
        assert len(threshold_alerts) == 1
        assert threshold_alerts[0].severity == "critical"

    def test_build_success_rate_above_threshold_no_alert(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        _insert_metric(conn, "deployment", "Product A", "build_success_rate_pct", 95.0)
        conn.close()

        engine = AlertEngine(db_path=db_path)
        engine.run()
        alerts = engine.load_alerts()

        assert not any(a.metric_name == "build_success_rate_pct" for a in alerts)

    def test_critical_vulns_above_zero_triggers_alert(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        _insert_metric(conn, "security", "All Products", "critical_vulns", 5.0)
        conn.close()

        engine = AlertEngine(db_path=db_path)
        engine.run()
        alerts = engine.load_alerts()

        security_alerts = [a for a in alerts if a.metric_name == "critical_vulns"]
        assert len(security_alerts) == 1
        assert security_alerts[0].severity == "critical"

    def test_zero_critical_vulns_no_alert(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        _insert_metric(conn, "security", "All Products", "critical_vulns", 0.0)
        conn.close()

        engine = AlertEngine(db_path=db_path)
        engine.run()
        alerts = engine.load_alerts()

        assert not any(a.metric_name == "critical_vulns" for a in alerts)

    def test_unassigned_above_75_triggers_critical_not_warn(self, db_path: Path) -> None:
        """82% unassigned should fire critical (>75%), not a separate warn."""
        conn = sqlite3.connect(db_path)
        _insert_metric(conn, "ownership", "Product A", "unassigned_pct", 82.0)
        conn.close()

        engine = AlertEngine(db_path=db_path)
        engine.run()
        alerts = [a for a in engine.load_alerts() if a.metric_name == "unassigned_pct"]

        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    def test_unassigned_between_60_and_75_triggers_warn(self, db_path: Path) -> None:
        """65% unassigned should fire warn (>60% but <75%)."""
        conn = sqlite3.connect(db_path)
        _insert_metric(conn, "ownership", "Product A", "unassigned_pct", 65.0)
        conn.close()

        engine = AlertEngine(db_path=db_path)
        engine.run()
        alerts = [a for a in engine.load_alerts() if a.metric_name == "unassigned_pct"]

        assert len(alerts) == 1
        assert alerts[0].severity == "warn"

    def test_single_owner_above_90_triggers_critical_not_warn(self, db_path: Path) -> None:
        """98% single-owner should fire critical (>90%), not a separate warn."""
        conn = sqlite3.connect(db_path)
        _insert_metric(conn, "risk", "Product A", "single_owner_pct", 98.0)
        conn.close()

        engine = AlertEngine(db_path=db_path)
        engine.run()
        alerts = [a for a in engine.load_alerts() if a.metric_name == "single_owner_pct"]

        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    def test_single_owner_between_80_and_90_triggers_warn(self, db_path: Path) -> None:
        """85% single-owner should fire warn (>80% but <90%)."""
        conn = sqlite3.connect(db_path)
        _insert_metric(conn, "risk", "Product A", "single_owner_pct", 85.0)
        conn.close()

        engine = AlertEngine(db_path=db_path)
        engine.run()
        alerts = [a for a in engine.load_alerts() if a.metric_name == "single_owner_pct"]

        assert len(alerts) == 1
        assert alerts[0].severity == "warn"

    def test_only_latest_value_per_project_evaluated(self, db_path: Path) -> None:
        """Only the most-recent row for each project should be checked."""
        conn = sqlite3.connect(db_path)
        # Old row: below threshold (would trigger) — but newer row is fine
        _insert_metric(conn, "deployment", "Product A", "build_success_rate_pct", 50.0, "2026-01-01")
        _insert_metric(conn, "deployment", "Product A", "build_success_rate_pct", 92.0, "2026-02-17")
        conn.close()

        engine = AlertEngine(db_path=db_path)
        engine.run()
        alerts = engine.load_alerts()

        assert not any(a.metric_name == "build_success_rate_pct" for a in alerts)


# ---------------------------------------------------------------------------
# Tests: anomaly-based alerts
# ---------------------------------------------------------------------------


class TestAnomalyAlerts:
    def test_anomaly_alert_written_for_spike(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        for i in range(8):
            _insert_metric(conn, "quality", "Product A", "open_bugs", 100.0, f"2026-01-{i + 1:02d}")
        _insert_metric(conn, "quality", "Product A", "open_bugs", 200.0, "2026-02-17")
        _insert_stats(conn, "quality", "Product A", "open_bugs", mean=100.0, std=5.0)
        conn.close()

        engine = AlertEngine(db_path=db_path, zscore_threshold=2.0)
        engine.run()
        alerts = engine.load_alerts()

        anomaly_alerts = [a for a in alerts if a.alert_type == "anomaly"]
        assert len(anomaly_alerts) == 1
        assert anomaly_alerts[0].metric_name == "open_bugs"
        assert anomaly_alerts[0].value == 200.0

    def test_no_anomaly_alert_for_normal_value(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        _insert_metric(conn, "quality", "Product A", "open_bugs", 102.0, "2026-02-17")
        _insert_stats(conn, "quality", "Product A", "open_bugs", mean=100.0, std=5.0)
        conn.close()

        engine = AlertEngine(db_path=db_path, zscore_threshold=2.0)
        engine.run()
        alerts = engine.load_alerts()

        assert not any(a.alert_type == "anomaly" for a in alerts)


# ---------------------------------------------------------------------------
# Tests: persistence and loading
# ---------------------------------------------------------------------------


class TestAlertPersistence:
    def test_alerts_cleared_on_each_run(self, db_path: Path) -> None:
        """Running the engine twice should not accumulate duplicate alerts."""
        conn = sqlite3.connect(db_path)
        _insert_metric(conn, "deployment", "Product A", "build_success_rate_pct", 50.0)
        conn.close()

        engine = AlertEngine(db_path=db_path)
        engine.run()
        engine.run()  # second run
        alerts = engine.load_alerts()

        # Should still have only 1 alert — not 2
        threshold_alerts = [a for a in alerts if a.metric_name == "build_success_rate_pct"]
        assert len(threshold_alerts) == 1

    def test_load_alerts_returns_empty_when_no_db(self, tmp_path: Path) -> None:
        engine = AlertEngine(db_path=tmp_path / "missing.db")
        assert engine.load_alerts() == []

    def test_load_alerts_ordered_critical_first(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        _insert_metric(conn, "deployment", "Product A", "build_success_rate_pct", 50.0)  # critical
        _insert_metric(conn, "deployment", "Product A", "deployments_per_week", 0.5)  # warn
        conn.close()

        engine = AlertEngine(db_path=db_path)
        engine.run()
        alerts = engine.load_alerts()

        severities = [a.severity for a in alerts]
        assert severities[0] == "critical"

    def test_run_raises_when_db_missing(self, tmp_path: Path) -> None:
        engine = AlertEngine(db_path=tmp_path / "missing.db")
        with pytest.raises(FileNotFoundError):
            engine.run()

    def test_alert_message_contains_project_name(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        _insert_metric(conn, "deployment", "My Project", "build_success_rate_pct", 50.0)
        conn.close()

        engine = AlertEngine(db_path=db_path)
        engine.run()
        alerts = engine.load_alerts()

        threshold_alerts = [a for a in alerts if a.metric_name == "build_success_rate_pct"]
        assert len(threshold_alerts) == 1
        assert "My Project" in threshold_alerts[0].message

    def test_alert_dataclass_fields(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        _insert_metric(conn, "security", "All Products", "critical_vulns", 3.0)
        conn.close()

        engine = AlertEngine(db_path=db_path)
        engine.run()
        alerts = engine.load_alerts()

        assert len(alerts) > 0
        alert = alerts[0]
        assert isinstance(alert, Alert)
        assert alert.dashboard == "security"
        assert alert.project_name == "All Products"
        assert alert.metric_name == "critical_vulns"
        assert alert.value == 3.0
        assert alert.expected == 0.0  # threshold value
