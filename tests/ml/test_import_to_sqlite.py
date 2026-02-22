"""
Tests for execution/import_to_sqlite.py

Verifies that each importer correctly extracts scalar metrics from the JSON
history structures, writes them to SQLite, and that rolling stats are computed.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from execution.import_to_sqlite import (
    clear_existing_data,
    compute_rolling_stats,
    create_database,
    import_collaboration_metrics,
    import_deployment_metrics,
    import_flow_metrics,
    import_ownership_metrics,
    import_quality_metrics,
    import_risk_metrics,
    import_security_metrics,
)

# ---------------------------------------------------------------------------
# Fixtures: minimal one-week history stubs
# ---------------------------------------------------------------------------


def _week(week_date: str, projects: list[dict]) -> dict:
    return {"week_date": week_date, "week_number": 1, "projects": projects}


@pytest.fixture
def quality_history_file(tmp_path: Path) -> Path:
    data = {
        "weeks": [
            _week(
                "2026-02-17",
                [
                    {
                        "project_key": "Product_A",
                        "project_name": "Product A",
                        "open_bugs_count": 183,
                        "total_bugs_analyzed": 45,
                        "bug_age_distribution": {"median_age_days": 426.5, "p85_age_days": 596.1},
                        "mttr": {"mttr_days": 22.1, "median_mttr_days": 13.8},
                        "test_execution_time": {"median_minutes": None},
                        "collected_at": "2026-02-17T23:34:06.000000",
                    }
                ],
            )
        ]
    }
    p = tmp_path / "quality_history.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def deployment_history_file(tmp_path: Path) -> Path:
    data = {
        "weeks": [
            _week(
                "2026-02-18",
                [
                    {
                        "project_key": "Product_A",
                        "project_name": "Product A",
                        "deployment_frequency": {"deployments_per_week": 28.16},
                        "build_success_rate": {"success_rate_pct": 62.4},
                        "build_duration": {"median_minutes": 17.7},
                        "lead_time_for_changes": {"median_hours": 0.2, "p85_hours": 511.1},
                        "collected_at": "2026-02-18T01:36:11.000000",
                    }
                ],
            )
        ]
    }
    p = tmp_path / "deployment_history.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def flow_history_file(tmp_path: Path) -> Path:
    data = {
        "weeks": [
            _week(
                "2026-02-18",
                [
                    {
                        "project_key": "Product_A",
                        "project_name": "Product A",
                        "work_type_metrics": {
                            "Bug": {
                                "open_count": 183,
                                "closed_count_90d": 76,
                                "lead_time": {"p50": 167.2},
                                "throughput": {"per_week": 5.9},
                            },
                            "User Story": {
                                "open_count": 904,
                                "closed_count_90d": 238,
                                "lead_time": {"p50": 1.1},
                                "throughput": {"per_week": 18.3},
                            },
                        },
                        "collected_at": "2026-02-18T00:00:00.000000",
                    }
                ],
            )
        ]
    }
    p = tmp_path / "flow_history.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def ownership_history_file(tmp_path: Path) -> Path:
    data = {
        "weeks": [
            _week(
                "2026-02-18",
                [
                    {
                        "project_key": "Product_A",
                        "project_name": "Product A",
                        "unassigned": {"unassigned_count": 680, "unassigned_pct": 44.0},
                        "assignment_distribution": {"load_imbalance_ratio": 680.0},
                        "developer_active_days": {"avg_active_days": 6.1, "total_commits": 1066},
                        "collected_at": "2026-02-18T00:00:00.000000",
                    }
                ],
            )
        ]
    }
    p = tmp_path / "ownership_history.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def risk_history_file(tmp_path: Path) -> Path:
    data = {
        "weeks": [
            _week(
                "2026-02-17",
                [
                    {
                        "project_key": "Product_A",
                        "project_name": "Product A",
                        "code_churn": {"total_commits": 1066, "unique_files_touched": 671},
                        "knowledge_distribution": {"single_owner_pct": 65.9},
                        "module_coupling": {"total_coupled_pairs": 28313},
                        "collected_at": "2026-02-17T00:00:00.000000",
                    }
                ],
            )
        ]
    }
    p = tmp_path / "risk_history.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def collaboration_history_file(tmp_path: Path) -> Path:
    data = {
        "weeks": [
            _week(
                "2026-02-17",
                [
                    {
                        "project_key": "Product_A",
                        "project_name": "Product A",
                        "pr_merge_time": {"median_hours": 0.6},
                        "pr_review_time": {"median_hours": None},
                        "review_iteration_count": {"median_iterations": 1.0},
                        "pr_size": {"median_commits": 2.0},
                        "total_prs_analyzed": 456,
                        "collected_at": "2026-02-17T00:00:00.000000",
                    }
                ],
            )
        ]
    }
    p = tmp_path / "collaboration_history.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def security_history_file(tmp_path: Path) -> Path:
    data = {
        "weeks": [
            {
                "week_date": "2026-02-17",
                "week_number": 1,
                "metrics": {
                    "current_total": 259,
                    "severity_breakdown": {"critical": 10, "high": 249},
                    "product_breakdown": {
                        "101": {"critical": 10, "high": 50, "total": 60},
                        "102": {"critical": 0, "high": 199, "total": 199},
                    },
                },
            }
        ]
    }
    p = tmp_path / "security_history.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    """In-memory-equivalent: a temp-file SQLite DB, pre-schema'd."""
    conn = sqlite3.connect(tmp_path / "test.db")
    create_database(conn)
    return conn


# ---------------------------------------------------------------------------
# Helpers to point importers at tmp_path
# ---------------------------------------------------------------------------


def _patch_history_dir(monkeypatch, tmp_path: Path) -> None:
    """Redirect HISTORY_DIR in the module under test to tmp_path."""
    import execution.import_to_sqlite as mod

    monkeypatch.setattr(mod, "HISTORY_DIR", tmp_path)


# ---------------------------------------------------------------------------
# Tests: quality importer
# ---------------------------------------------------------------------------


class TestImportQualityMetrics:
    def test_imports_open_bugs(self, db, tmp_path, monkeypatch, quality_history_file):
        _patch_history_dir(monkeypatch, tmp_path)
        count = import_quality_metrics(db)
        assert count > 0

        cursor = db.cursor()
        cursor.execute("SELECT metric_value FROM metrics WHERE metric_name='open_bugs' AND project_name='Product A'")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 183

    def test_imports_median_bug_age(self, db, tmp_path, monkeypatch, quality_history_file):
        _patch_history_dir(monkeypatch, tmp_path)
        import_quality_metrics(db)

        cursor = db.cursor()
        cursor.execute(
            "SELECT metric_value FROM metrics WHERE metric_name='median_bug_age' AND project_name='Product A'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == pytest.approx(426.5)

    def test_skips_null_values(self, db, tmp_path, monkeypatch, quality_history_file):
        """test_execution_time has median_minutes=None — should not insert a row."""
        _patch_history_dir(monkeypatch, tmp_path)
        import_quality_metrics(db)

        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM metrics WHERE metric_name='test_execution_median_min'")
        assert cursor.fetchone()[0] == 0

    def test_missing_file_returns_zero(self, db, tmp_path, monkeypatch):
        _patch_history_dir(monkeypatch, tmp_path)  # no quality file in tmp_path
        count = import_quality_metrics(db)
        assert count == 0


# ---------------------------------------------------------------------------
# Tests: deployment importer
# ---------------------------------------------------------------------------


class TestImportDeploymentMetrics:
    def test_imports_build_success_rate(self, db, tmp_path, monkeypatch, deployment_history_file):
        _patch_history_dir(monkeypatch, tmp_path)
        count = import_deployment_metrics(db)
        assert count > 0

        cursor = db.cursor()
        cursor.execute(
            "SELECT metric_value FROM metrics "
            "WHERE metric_name='build_success_rate_pct' AND project_name='Product A'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == pytest.approx(62.4)

    def test_imports_deployments_per_week(self, db, tmp_path, monkeypatch, deployment_history_file):
        _patch_history_dir(monkeypatch, tmp_path)
        import_deployment_metrics(db)

        cursor = db.cursor()
        cursor.execute(
            "SELECT metric_value FROM metrics " "WHERE metric_name='deployments_per_week' AND project_name='Product A'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == pytest.approx(28.16)


# ---------------------------------------------------------------------------
# Tests: flow importer
# ---------------------------------------------------------------------------


class TestImportFlowMetrics:
    def test_imports_bug_open_count(self, db, tmp_path, monkeypatch, flow_history_file):
        _patch_history_dir(monkeypatch, tmp_path)
        count = import_flow_metrics(db)
        assert count > 0

        cursor = db.cursor()
        cursor.execute(
            "SELECT metric_value FROM metrics " "WHERE metric_name='bug_open_count' AND project_name='Product A'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 183

    def test_imports_user_story_throughput(self, db, tmp_path, monkeypatch, flow_history_file):
        _patch_history_dir(monkeypatch, tmp_path)
        import_flow_metrics(db)

        cursor = db.cursor()
        cursor.execute(
            "SELECT metric_value FROM metrics "
            "WHERE metric_name='user_story_throughput_per_week' AND project_name='Product A'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == pytest.approx(18.3)

    def test_work_type_key_normalisation(self, db, tmp_path, monkeypatch, flow_history_file):
        """'User Story' must be stored as 'user_story_*', not 'User Story_*'."""
        _patch_history_dir(monkeypatch, tmp_path)
        import_flow_metrics(db)

        cursor = db.cursor()
        cursor.execute("SELECT DISTINCT metric_name FROM metrics WHERE dashboard='flow'")
        names = {row[0] for row in cursor.fetchall()}
        assert any("user_story" in n for n in names), "Expected normalised key 'user_story_*'"
        assert not any("User Story" in n for n in names), "Space-containing key should not exist"


# ---------------------------------------------------------------------------
# Tests: ownership importer
# ---------------------------------------------------------------------------


class TestImportOwnershipMetrics:
    def test_imports_unassigned_pct(self, db, tmp_path, monkeypatch, ownership_history_file):
        _patch_history_dir(monkeypatch, tmp_path)
        import_ownership_metrics(db)

        cursor = db.cursor()
        cursor.execute(
            "SELECT metric_value FROM metrics " "WHERE metric_name='unassigned_pct' AND project_name='Product A'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == pytest.approx(44.0)


# ---------------------------------------------------------------------------
# Tests: risk importer
# ---------------------------------------------------------------------------


class TestImportRiskMetrics:
    def test_imports_single_owner_pct(self, db, tmp_path, monkeypatch, risk_history_file):
        _patch_history_dir(monkeypatch, tmp_path)
        import_risk_metrics(db)

        cursor = db.cursor()
        cursor.execute(
            "SELECT metric_value FROM metrics " "WHERE metric_name='single_owner_pct' AND project_name='Product A'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == pytest.approx(65.9)


# ---------------------------------------------------------------------------
# Tests: collaboration importer
# ---------------------------------------------------------------------------


class TestImportCollaborationMetrics:
    def test_imports_pr_merge_time(self, db, tmp_path, monkeypatch, collaboration_history_file):
        _patch_history_dir(monkeypatch, tmp_path)
        import_collaboration_metrics(db)

        cursor = db.cursor()
        cursor.execute(
            "SELECT metric_value FROM metrics "
            "WHERE metric_name='pr_merge_time_median_hours' AND project_name='Product A'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == pytest.approx(0.6)

    def test_skips_null_pr_review_time(self, db, tmp_path, monkeypatch, collaboration_history_file):
        _patch_history_dir(monkeypatch, tmp_path)
        import_collaboration_metrics(db)

        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM metrics WHERE metric_name='pr_review_time_median_hours'")
        assert cursor.fetchone()[0] == 0


# ---------------------------------------------------------------------------
# Tests: security importer
# ---------------------------------------------------------------------------


class TestImportSecurityMetrics:
    def test_imports_per_product_rows(self, db, tmp_path, monkeypatch, security_history_file):
        """Security metrics are imported per product, not as 'All Products' aggregate."""
        _patch_history_dir(monkeypatch, tmp_path)
        count = import_security_metrics(db)
        assert count > 0

        cursor = db.cursor()
        cursor.execute("SELECT DISTINCT project_name FROM metrics WHERE dashboard='security'")
        projects = {row[0] for row in cursor.fetchall()}
        assert "All Products" not in projects
        assert len(projects) == 2  # two products in fixture

    def test_imports_critical_vulns_per_product(self, db, tmp_path, monkeypatch, security_history_file):
        """Critical vuln count is stored per product."""
        _patch_history_dir(monkeypatch, tmp_path)
        import_security_metrics(db)

        cursor = db.cursor()
        cursor.execute(
            "SELECT SUM(metric_value) FROM metrics " "WHERE metric_name='critical_vulns' AND dashboard='security'"
        )
        total = cursor.fetchone()[0]
        assert total == 10  # 10 + 0 from fixture


# ---------------------------------------------------------------------------
# Tests: rolling stats computation
# ---------------------------------------------------------------------------


class TestComputeRollingStats:
    def _seed_metrics(self, conn: sqlite3.Connection, values: list[float]) -> None:
        """Insert a synthetic time series into the metrics table."""
        cursor = conn.cursor()
        for i, v in enumerate(values):
            cursor.execute(
                "INSERT INTO metrics (metric_date, dashboard, project_name, metric_name, metric_value, metric_unit) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (f"2026-01-{i + 1:02d}", "quality", "Test Project", "open_bugs", v, "bugs"),
            )
        conn.commit()

    def test_computes_mean_and_std(self, db):
        values = [100.0, 110.0, 90.0, 105.0, 95.0, 108.0, 102.0, 98.0]
        self._seed_metrics(db, values)
        compute_rolling_stats(db)

        cursor = db.cursor()
        cursor.execute(
            "SELECT rolling_mean, rolling_std FROM rolling_stats "
            "WHERE dashboard='quality' AND project_name='Test Project' AND metric_name='open_bugs'"
        )
        row = cursor.fetchone()
        assert row is not None
        mean, std = row
        assert mean == pytest.approx(sum(values) / len(values), rel=0.01)
        assert std > 0

    def test_computes_trend_slope(self, db):
        """Increasing sequence → positive slope."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
        self._seed_metrics(db, values)
        compute_rolling_stats(db)

        cursor = db.cursor()
        cursor.execute(
            "SELECT trend_slope FROM rolling_stats "
            "WHERE dashboard='quality' AND project_name='Test Project' AND metric_name='open_bugs'"
        )
        slope = cursor.fetchone()[0]
        assert slope > 0

    def test_skips_single_value_series(self, db):
        self._seed_metrics(db, [42.0])
        count = compute_rolling_stats(db)
        # Single-value series has std=0, no rolling stats row expected
        assert count == 0

    def test_clear_existing_data_truncates_metrics(self, db):
        self._seed_metrics(db, [1.0, 2.0, 3.0])
        clear_existing_data(db)

        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 0
