"""
Tests for execution/ml/anomaly_detector.py

Verifies z-score based anomaly detection across Observatory metrics.
"""

import sqlite3
from pathlib import Path

import pytest

from execution.ml.anomaly_detector import AnomalyDetector, AnomalyResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Return path to a pre-populated test SQLite DB."""
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
    """)
    conn.commit()


def _seed(
    conn: sqlite3.Connection,
    values: list[float],
    dashboard: str = "quality",
    project: str = "Product A",
    metric: str = "open_bugs",
) -> None:
    """Insert a synthetic time series."""
    for i, v in enumerate(values):
        conn.execute(
            "INSERT INTO metrics (metric_date, dashboard, project_name, metric_name, metric_value) "
            "VALUES (?, ?, ?, ?, ?)",
            (f"2026-01-{i + 1:02d}", dashboard, project, metric, v),
        )
    conn.commit()


def _seed_stats(
    conn: sqlite3.Connection,
    mean: float,
    std: float,
    dashboard: str = "quality",
    project: str = "Product A",
    metric: str = "open_bugs",
) -> None:
    """Insert a rolling_stats row directly."""
    conn.execute(
        "INSERT OR REPLACE INTO rolling_stats "
        "(dashboard, project_name, metric_name, rolling_mean, rolling_std, trend_slope, last_8w_avg, last_updated) "
        "VALUES (?, ?, ?, ?, ?, 0.0, ?, datetime('now'))",
        (dashboard, project, metric, mean, std, mean),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAnomalyDetector:
    def test_raises_when_db_missing(self, tmp_path: Path) -> None:
        detector = AnomalyDetector(db_path=tmp_path / "nonexistent.db")
        with pytest.raises(FileNotFoundError):
            detector.detect_all()

    def test_returns_empty_when_no_stats(self, db_path: Path) -> None:
        detector = AnomalyDetector(db_path=db_path)
        # No rolling_stats seeded → empty result
        results = detector.detect_all()
        assert results == []

    def test_detects_spike_above_threshold(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        # Normal values: mean≈100, std≈5; latest value = 125 (z≈5 → anomaly)
        _seed(conn, [100, 102, 98, 101, 99, 103, 97, 100, 125])
        _seed_stats(conn, mean=100.0, std=5.0)
        conn.close()

        detector = AnomalyDetector(db_path=db_path, threshold=2.0)
        results = detector.detect_all()

        assert len(results) == 1
        result = results[0]
        assert result.dashboard == "quality"
        assert result.project_name == "Product A"
        assert result.metric_name == "open_bugs"
        assert result.value == 125
        assert result.direction == "above"
        assert result.z_score > 2.0

    def test_detects_drop_below_threshold(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        _seed(conn, [100, 102, 98, 101, 99, 103, 97, 100, 60])
        _seed_stats(conn, mean=100.0, std=5.0)
        conn.close()

        detector = AnomalyDetector(db_path=db_path, threshold=2.0)
        results = detector.detect_all()

        assert len(results) == 1
        assert results[0].direction == "below"
        assert results[0].z_score < -2.0

    def test_no_anomaly_for_normal_value(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        _seed(conn, [100.0, 102.0, 98.0, 101.0, 99.0, 103.0, 97.0, 100.0, 102.0])  # last value well within range
        _seed_stats(conn, mean=100.0, std=5.0)
        conn.close()

        detector = AnomalyDetector(db_path=db_path, threshold=2.0)
        results = detector.detect_all()
        assert results == []

    def test_severity_high_for_extreme_zscore(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        _seed(conn, [100.0] * 8 + [200.0])  # z = (200-100)/5 = 20 → high
        _seed_stats(conn, mean=100.0, std=5.0)
        conn.close()

        detector = AnomalyDetector(db_path=db_path, threshold=2.0)
        results = detector.detect_all()

        assert len(results) == 1
        assert results[0].severity == "high"

    def test_severity_medium_for_moderate_zscore(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        _seed(conn, [100.0] * 8 + [112.0])  # z = (112-100)/5 = 2.4 → medium
        _seed_stats(conn, mean=100.0, std=5.0)
        conn.close()

        detector = AnomalyDetector(db_path=db_path, threshold=2.0)
        results = detector.detect_all()

        assert len(results) == 1
        assert results[0].severity == "medium"

    def test_results_sorted_high_first(self, db_path: Path) -> None:
        """High-severity anomalies must appear before medium ones."""
        conn = sqlite3.connect(db_path)
        # Two metrics: one extreme (high), one moderate (medium)
        _seed(conn, [100.0] * 8 + [200.0], metric="open_bugs")
        _seed_stats(conn, mean=100.0, std=5.0, metric="open_bugs")

        _seed(conn, [100.0] * 8 + [112.0], metric="build_success_rate_pct")
        _seed_stats(conn, mean=100.0, std=5.0, metric="build_success_rate_pct")
        conn.close()

        detector = AnomalyDetector(db_path=db_path, threshold=2.0)
        results = detector.detect_all()

        assert len(results) == 2
        assert results[0].severity == "high"
        assert results[1].severity == "medium"

    def test_detect_for_dashboard_filters_correctly(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        _seed(conn, [100.0] * 8 + [200.0], dashboard="quality", metric="open_bugs")
        _seed_stats(conn, mean=100.0, std=5.0, dashboard="quality", metric="open_bugs")

        _seed(conn, [10.0] * 8 + [50.0], dashboard="deployment", metric="deployments_per_week")
        _seed_stats(conn, mean=10.0, std=2.0, dashboard="deployment", metric="deployments_per_week")
        conn.close()

        detector = AnomalyDetector(db_path=db_path, threshold=2.0)
        results = detector.detect_for_dashboard("quality")

        assert all(r.dashboard == "quality" for r in results)
        assert not any(r.dashboard == "deployment" for r in results)

    def test_ignores_series_with_zero_std(self, db_path: Path) -> None:
        """Zero std means no variance — detector should skip the series."""
        conn = sqlite3.connect(db_path)
        _seed(conn, [100] * 9)
        # std=0 in rolling_stats → WHERE rolling_std > 0 excludes it
        _seed_stats(conn, mean=100.0, std=0.0)
        conn.close()

        detector = AnomalyDetector(db_path=db_path, threshold=2.0)
        results = detector.detect_all()
        assert results == []
