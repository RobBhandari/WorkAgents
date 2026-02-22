#!/usr/bin/env python3
"""
Import Observatory metrics from JSON history files to SQLite.

Reads all *_history.json files and imports them into a normalised SQLite
database at .tmp/observatory/observatory.db.  After importing raw metrics the
script computes 8-week rolling statistics (mean, std, slope) and writes them
to the rolling_stats table, which the anomaly detector then consumes.
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path(".tmp/observatory/observatory.db")
HISTORY_DIR = Path(".tmp/observatory")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def create_database(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes (idempotent)."""
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS metrics (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_date  TEXT    NOT NULL,
            dashboard    TEXT    NOT NULL,
            project_name TEXT    NOT NULL,
            metric_name  TEXT    NOT NULL,
            metric_value REAL,
            metric_unit  TEXT,
            created_at   TEXT    DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_metrics_date      ON metrics (metric_date);
        CREATE INDEX IF NOT EXISTS idx_metrics_dashboard ON metrics (dashboard);
        CREATE INDEX IF NOT EXISTS idx_metrics_project   ON metrics (project_name, metric_name);

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_metrics(
    cursor: sqlite3.Cursor,
    week_date: str,
    dashboard: str,
    project_name: str,
    metrics: list[tuple[str, float | None, str]],
) -> int:
    """Bulk-insert a list of (metric_name, value, unit) rows. Returns count inserted."""
    count = 0
    for metric_name, metric_value, metric_unit in metrics:
        if metric_value is not None:
            cursor.execute(
                "INSERT INTO metrics (metric_date, dashboard, project_name, metric_name, metric_value, metric_unit) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (week_date, dashboard, project_name, metric_name, metric_value, metric_unit),
            )
            count += 1
    return count


def _load_history(file_path: Path) -> list[dict]:
    """Load weeks list from a history JSON file. Returns [] if missing."""
    if not file_path.exists():
        print(f"  ⚠  Skipping: {file_path.name} not found")
        return []
    with open(file_path, encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    weeks: list[dict] = data.get("weeks", [])
    return weeks


# ---------------------------------------------------------------------------
# Per-dashboard importers
# ---------------------------------------------------------------------------


def import_quality_metrics(conn: sqlite3.Connection) -> int:
    """Import quality metrics (open bugs, bug age, MTTR)."""
    weeks = _load_history(HISTORY_DIR / "quality_history.json")
    cursor = conn.cursor()
    total = 0

    for week in weeks:
        week_date = week["week_date"]
        for project in week.get("projects", []):
            project_name = project["project_name"]
            bug_age = project.get("bug_age_distribution", {})
            mttr = project.get("mttr", {})
            test_time = project.get("test_execution_time", {})

            rows: list[tuple[str, float | None, str]] = [
                ("open_bugs", project.get("open_bugs_count"), "bugs"),
                ("median_bug_age", bug_age.get("median_age_days"), "days"),
                ("p85_bug_age", bug_age.get("p85_age_days"), "days"),
                ("mttr_mean", mttr.get("mttr_days"), "days"),
                ("mttr_median", mttr.get("median_mttr_days"), "days"),
                ("test_execution_median_min", test_time.get("median_minutes"), "minutes"),
            ]
            total += _insert_metrics(cursor, week_date, "quality", project_name, rows)

    conn.commit()
    print(f"  ✓ quality: {total} rows")
    return total


def import_deployment_metrics(conn: sqlite3.Connection) -> int:
    """Import deployment metrics (build success rate, frequency, duration, lead time)."""
    weeks = _load_history(HISTORY_DIR / "deployment_history.json")
    cursor = conn.cursor()
    total = 0

    for week in weeks:
        week_date = week["week_date"]
        for project in week.get("projects", []):
            project_name = project["project_name"]
            freq = project.get("deployment_frequency", {})
            bsr = project.get("build_success_rate", {})
            dur = project.get("build_duration", {})
            lt = project.get("lead_time_for_changes", {})

            rows: list[tuple[str, float | None, str]] = [
                ("deployments_per_week", freq.get("deployments_per_week"), "deploys"),
                ("build_success_rate_pct", bsr.get("success_rate_pct"), "pct"),
                ("build_duration_median_min", dur.get("median_minutes"), "minutes"),
                ("lead_time_median_hours", lt.get("median_hours"), "hours"),
                ("lead_time_p85_hours", lt.get("p85_hours"), "hours"),
            ]
            total += _insert_metrics(cursor, week_date, "deployment", project_name, rows)

    conn.commit()
    print(f"  ✓ deployment: {total} rows")
    return total


def import_flow_metrics(conn: sqlite3.Connection) -> int:
    """Import flow metrics (open count, throughput, lead time per work type)."""
    weeks = _load_history(HISTORY_DIR / "flow_history.json")
    cursor = conn.cursor()
    total = 0

    for week in weeks:
        week_date = week["week_date"]
        for project in week.get("projects", []):
            project_name = project["project_name"]
            wt = project.get("work_type_metrics", {})

            rows: list[tuple[str, float | None, str]] = []
            for work_type, wt_data in wt.items():
                # Normalise work type name for column-safe key (e.g. "User Story" → "user_story")
                wt_key = work_type.lower().replace(" ", "_")
                lt = wt_data.get("lead_time", {})
                tp = wt_data.get("throughput", {})
                rows += [
                    (f"{wt_key}_open_count", wt_data.get("open_count"), "items"),
                    (f"{wt_key}_closed_90d", wt_data.get("closed_count_90d"), "items"),
                    (f"{wt_key}_lead_time_p50", lt.get("p50"), "days"),
                    (f"{wt_key}_throughput_per_week", tp.get("per_week"), "items"),
                ]

            total += _insert_metrics(cursor, week_date, "flow", project_name, rows)

    conn.commit()
    print(f"  ✓ flow: {total} rows")
    return total


def import_ownership_metrics(conn: sqlite3.Connection) -> int:
    """Import ownership metrics (unassigned pct, load imbalance, dev active days)."""
    weeks = _load_history(HISTORY_DIR / "ownership_history.json")
    cursor = conn.cursor()
    total = 0

    for week in weeks:
        week_date = week["week_date"]
        for project in week.get("projects", []):
            project_name = project["project_name"]
            unassigned = project.get("unassigned", {})
            assign_dist = project.get("assignment_distribution", {})
            dev_days = project.get("developer_active_days", {})

            rows: list[tuple[str, float | None, str]] = [
                ("unassigned_pct", unassigned.get("unassigned_pct"), "pct"),
                ("unassigned_count", unassigned.get("unassigned_count"), "items"),
                ("load_imbalance_ratio", assign_dist.get("load_imbalance_ratio"), "ratio"),
                ("avg_active_days", dev_days.get("avg_active_days"), "days"),
                ("total_commits", dev_days.get("total_commits"), "commits"),
            ]
            total += _insert_metrics(cursor, week_date, "ownership", project_name, rows)

    conn.commit()
    print(f"  ✓ ownership: {total} rows")
    return total


def import_risk_metrics(conn: sqlite3.Connection) -> int:
    """Import risk metrics (code churn, knowledge distribution, module coupling)."""
    weeks = _load_history(HISTORY_DIR / "risk_history.json")
    cursor = conn.cursor()
    total = 0

    for week in weeks:
        week_date = week["week_date"]
        for project in week.get("projects", []):
            project_name = project["project_name"]
            churn = project.get("code_churn", {})
            knowledge = project.get("knowledge_distribution", {})
            coupling = project.get("module_coupling", {})

            rows: list[tuple[str, float | None, str]] = [
                ("total_commits", churn.get("total_commits"), "commits"),
                ("unique_files_touched", churn.get("unique_files_touched"), "files"),
                ("single_owner_pct", knowledge.get("single_owner_pct"), "pct"),
                ("total_coupled_pairs", coupling.get("total_coupled_pairs"), "pairs"),
            ]
            total += _insert_metrics(cursor, week_date, "risk", project_name, rows)

    conn.commit()
    print(f"  ✓ risk: {total} rows")
    return total


def import_collaboration_metrics(conn: sqlite3.Connection) -> int:
    """Import collaboration metrics (PR merge time, review iterations, PR size)."""
    weeks = _load_history(HISTORY_DIR / "collaboration_history.json")
    cursor = conn.cursor()
    total = 0

    for week in weeks:
        week_date = week["week_date"]
        for project in week.get("projects", []):
            project_name = project["project_name"]
            pr_merge = project.get("pr_merge_time", {})
            pr_review = project.get("pr_review_time", {})
            iterations = project.get("review_iteration_count", {})
            pr_size = project.get("pr_size", {})

            rows: list[tuple[str, float | None, str]] = [
                ("pr_merge_time_median_hours", pr_merge.get("median_hours"), "hours"),
                ("pr_review_time_median_hours", pr_review.get("median_hours"), "hours"),
                ("review_iteration_median", iterations.get("median_iterations"), "iterations"),
                ("pr_size_median_commits", pr_size.get("median_commits"), "commits"),
                ("total_prs_analyzed", project.get("total_prs_analyzed"), "prs"),
            ]
            total += _insert_metrics(cursor, week_date, "collaboration", project_name, rows)

    conn.commit()
    print(f"  ✓ collaboration: {total} rows")
    return total


def _load_armorcode_id_map() -> dict[str, str]:
    """Load ArmorCode ID map and invert it to {numeric_id: product_name}.

    Returns an empty dict if the file doesn't exist (e.g. first run).
    """
    id_map_path = Path("data/armorcode_id_map.json")
    if not id_map_path.exists():
        return {}
    with open(id_map_path, encoding="utf-8") as fh:
        name_to_id: dict[str, str] = json.load(fh)
    return {v: k for k, v in name_to_id.items()}


def import_security_metrics(conn: sqlite3.Connection) -> int:
    """Import security metrics (critical/high counts) per product."""
    weeks = _load_history(HISTORY_DIR / "security_history.json")
    cursor = conn.cursor()
    total = 0

    id_to_name = _load_armorcode_id_map()

    for week in weeks:
        week_date = week["week_date"]
        metrics = week.get("metrics", {})
        product_breakdown = metrics.get("product_breakdown", {})

        for product_id, counts in product_breakdown.items():
            product_name = id_to_name.get(str(product_id), f"Product {product_id}")
            rows: list[tuple[str, float | None, str]] = [
                ("critical_vulns", counts.get("critical"), "vulns"),
                ("high_vulns", counts.get("high"), "vulns"),
                ("total_vulnerabilities", counts.get("total"), "vulns"),
            ]
            total += _insert_metrics(cursor, week_date, "security", product_name, rows)

    conn.commit()
    print(f"  ✓ security: {total} rows")
    return total


# ---------------------------------------------------------------------------
# Rolling stats computation
# ---------------------------------------------------------------------------


def compute_rolling_stats(conn: sqlite3.Connection) -> int:
    """
    Compute 8-week rolling mean, std, trend slope for every
    (dashboard, project_name, metric_name) combination.

    Upserts results into rolling_stats table.
    Returns the number of stat rows written.
    """
    try:
        import numpy as np
    except ImportError:
        print("  ⚠  numpy not available — skipping rolling stats computation")
        return 0

    cursor = conn.cursor()

    # Fetch all distinct (dashboard, project_name, metric_name) series
    cursor.execute("SELECT DISTINCT dashboard, project_name, metric_name FROM metrics ORDER BY dashboard, project_name")
    series_keys = cursor.fetchall()

    count = 0
    now_iso = __import__("datetime").datetime.now().isoformat()

    for dashboard, project_name, metric_name in series_keys:
        # Fetch last 52 weeks ordered by date
        cursor.execute(
            "SELECT metric_date, metric_value FROM metrics "
            "WHERE dashboard=? AND project_name=? AND metric_name=? "
            "ORDER BY metric_date DESC LIMIT 52",
            (dashboard, project_name, metric_name),
        )
        rows = cursor.fetchall()
        if not rows:
            continue

        values = np.array([r[1] for r in rows if r[1] is not None], dtype=float)
        if len(values) < 2:
            continue

        # All-time stats
        rolling_mean = float(np.mean(values))
        rolling_std = float(np.std(values))

        # Trend slope: reverse to oldest-first so positive slope = increasing over time.
        # (values are newest-first from the DESC query; polyfit on DESC order gives inverted slope)
        values_asc = values[::-1]
        x_asc = np.arange(len(values_asc), dtype=float)
        if len(values_asc) >= 2:
            coeffs = np.polyfit(x_asc, values_asc, 1)
            trend_slope = float(coeffs[0])
        else:
            trend_slope = 0.0

        # 8-week average (most recent 8 — values[:8] since values are newest-first)
        last_8w_avg = float(np.mean(values[:8]))

        cursor.execute(
            "INSERT INTO rolling_stats (dashboard, project_name, metric_name, "
            "rolling_mean, rolling_std, trend_slope, last_8w_avg, last_updated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(dashboard, project_name, metric_name) DO UPDATE SET "
            "rolling_mean=excluded.rolling_mean, rolling_std=excluded.rolling_std, "
            "trend_slope=excluded.trend_slope, last_8w_avg=excluded.last_8w_avg, "
            "last_updated=excluded.last_updated",
            (dashboard, project_name, metric_name, rolling_mean, rolling_std, trend_slope, last_8w_avg, now_iso),
        )
        count += 1

    conn.commit()
    print(f"  ✓ rolling stats computed: {count} series")
    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def clear_existing_data(conn: sqlite3.Connection) -> None:
    """Truncate raw metrics table before re-import (avoids duplicates)."""
    conn.execute("DELETE FROM metrics")
    conn.commit()


def main() -> None:
    """Run the full import pipeline: raw metrics → rolling stats."""
    print("=" * 60)
    print("Observatory Metrics → SQLite")
    print("=" * 60)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    print("\nInitialising schema...")
    create_database(conn)

    print("\nClearing existing raw metrics...")
    clear_existing_data(conn)

    print("\nImporting raw metrics...")
    total = 0
    total += import_quality_metrics(conn)
    total += import_deployment_metrics(conn)
    total += import_flow_metrics(conn)
    total += import_ownership_metrics(conn)
    total += import_risk_metrics(conn)
    total += import_collaboration_metrics(conn)
    total += import_security_metrics(conn)

    print("\nComputing rolling statistics...")
    compute_rolling_stats(conn)

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT metric_date) FROM metrics")
    date_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT dashboard) FROM metrics")
    dash_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM rolling_stats")
    stats_count = cursor.fetchone()[0]

    conn.close()

    print()
    print("=" * 60)
    print("✓ Import complete")
    print(f"  Raw rows:       {total}")
    print(f"  Unique dates:   {date_count}")
    print(f"  Dashboards:     {dash_count}")
    print(f"  Rolling stats:  {stats_count}")
    print(f"  Database:       {DB_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
