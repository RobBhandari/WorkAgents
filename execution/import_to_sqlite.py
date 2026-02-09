#!/usr/bin/env python3
"""
Import Observatory metrics from JSON to SQLite database

Reads all JSON history files and imports them into a normalized SQLite database
for trend analysis and cross-metric queries.
"""

import json
import os
import sqlite3

# Database path
DB_PATH = ".tmp/observatory/observatory.db"


def create_database():
    """Create SQLite database with schema"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create metrics table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_date DATE NOT NULL,
            dashboard VARCHAR(50) NOT NULL,
            project_name VARCHAR(100),
            metric_name VARCHAR(100) NOT NULL,
            metric_value REAL,
            metric_unit VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes for fast queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_date ON metrics(metric_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_dashboard ON metrics(dashboard)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name)")

    # Create target progress table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS target_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date DATE NOT NULL,
            category VARCHAR(50) NOT NULL,
            baseline_count INTEGER,
            current_count INTEGER,
            target_count INTEGER,
            progress_pct REAL,
            required_weekly_burn REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_target_date ON target_progress(snapshot_date)")

    conn.commit()
    conn.close()
    print(f"✓ Database created: {DB_PATH}")


def import_quality_metrics(conn):
    """Import quality metrics from quality_history.json"""
    file_path = ".tmp/observatory/quality_history.json"
    if not os.path.exists(file_path):
        print(f"⚠ Skipping: {file_path} not found")
        return 0

    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    cursor = conn.cursor()
    count = 0

    for week in data.get("weeks", []):
        week_date = week["week_date"]

        for project in week.get("projects", []):
            project_name = project["project_name"]

            # Import bug age distribution metrics
            bug_age = project.get("bug_age_distribution", {})
            metrics_to_import = [
                ("open_bugs", project.get("open_bugs_count", 0), "bugs"),
                ("median_bug_age", bug_age.get("median_age_days"), "days"),
                ("p85_bug_age", bug_age.get("p85_age_days"), "days"),
                ("mttr", project.get("mttr", {}).get("mttr_days"), "days"),
                ("median_mttr", project.get("mttr", {}).get("median_mttr_days"), "days"),
            ]

            for metric_name, metric_value, metric_unit in metrics_to_import:
                if metric_value is not None:
                    cursor.execute(
                        """
                        INSERT INTO metrics (metric_date, dashboard, project_name, metric_name, metric_value, metric_unit)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (week_date, "quality", project_name, metric_name, metric_value, metric_unit),
                    )
                    count += 1

    conn.commit()
    print(f"✓ Imported {count} quality metrics")
    return count


def import_security_metrics(conn):
    """Import security metrics from security_history.json"""
    file_path = ".tmp/observatory/security_history.json"
    if not os.path.exists(file_path):
        print(f"⚠ Skipping: {file_path} not found")
        return 0

    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    cursor = conn.cursor()
    count = 0

    for week in data.get("weeks", []):
        week_date = week["week_date"]
        metrics = week.get("metrics", {})

        # Import aggregate security metrics
        metrics_to_import = [
            ("total_vulnerabilities", metrics.get("current_total"), "vulns"),
            ("critical_vulns", metrics.get("severity_breakdown", {}).get("critical"), "vulns"),
            ("high_vulns", metrics.get("severity_breakdown", {}).get("high"), "vulns"),
            ("stale_criticals", metrics.get("stale_criticals"), "vulns"),
        ]

        for metric_name, metric_value, metric_unit in metrics_to_import:
            if metric_value is not None:
                cursor.execute(
                    """
                    INSERT INTO metrics (metric_date, dashboard, project_name, metric_name, metric_value, metric_unit)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (week_date, "security", "All Products", metric_name, metric_value, metric_unit),
                )
                count += 1

    conn.commit()
    print(f"✓ Imported {count} security metrics")
    return count


def import_flow_metrics(conn):
    """Import flow metrics from flow_history.json"""
    file_path = ".tmp/observatory/flow_history.json"
    if not os.path.exists(file_path):
        print(f"⚠ Skipping: {file_path} not found")
        return 0

    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    cursor = conn.cursor()
    count = 0

    for week in data.get("weeks", []):
        week_date = week["week_date"]

        for project in week.get("projects", []):
            project_name = project["project_name"]

            metrics_to_import = [
                ("lead_time_p85", project.get("lead_time", {}).get("p85_days"), "days"),
                ("cycle_time_p85", project.get("cycle_time", {}).get("p85_days"), "days"),
                ("wip_count", project.get("wip_count"), "items"),
                ("throughput", project.get("throughput"), "items"),
            ]

            for metric_name, metric_value, metric_unit in metrics_to_import:
                if metric_value is not None:
                    cursor.execute(
                        """
                        INSERT INTO metrics (metric_date, dashboard, project_name, metric_name, metric_value, metric_unit)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (week_date, "flow", project_name, metric_name, metric_value, metric_unit),
                    )
                    count += 1

    conn.commit()
    print(f"✓ Imported {count} flow metrics")
    return count


def import_other_dashboards(conn):
    """Import metrics from other dashboard history files"""
    dashboard_files = {
        "deployment": ".tmp/observatory/deployment_history.json",
        "collaboration": ".tmp/observatory/collaboration_history.json",
        "ownership": ".tmp/observatory/ownership_history.json",
        "risk": ".tmp/observatory/risk_history.json",
    }

    total_count = 0

    for dashboard_name, file_path in dashboard_files.items():
        if not os.path.exists(file_path):
            print(f"⚠ Skipping: {file_path} not found")
            continue

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            cursor = conn.cursor()
            count = 0

            for week in data.get("weeks", []):
                week_date = week["week_date"]

                # Import aggregate metrics if available
                if "aggregate" in week:
                    for metric_name, metric_value in week["aggregate"].items():
                        if isinstance(metric_value, (int, float)):
                            cursor.execute(
                                """
                                INSERT INTO metrics (metric_date, dashboard, project_name, metric_name, metric_value, metric_unit)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """,
                                (week_date, dashboard_name, "All Projects", metric_name, metric_value, ""),
                            )
                            count += 1

            conn.commit()
            total_count += count
            print(f"✓ Imported {count} {dashboard_name} metrics")

        except Exception as e:
            print(f"⚠ Error importing {dashboard_name}: {e}")

    return total_count


def clear_existing_data(conn):
    """Clear existing metrics data to avoid duplicates"""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM metrics")
    cursor.execute("DELETE FROM target_progress")
    conn.commit()
    print("✓ Cleared existing data")


def main():
    """Main import process"""
    print("=" * 70)
    print("Observatory Metrics Import to SQLite")
    print("=" * 70)

    # Create database
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    create_database()

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    # Clear existing data
    clear_existing_data(conn)

    # Import from each dashboard
    print("\nImporting metrics...")
    total = 0
    total += import_quality_metrics(conn)
    total += import_security_metrics(conn)
    total += import_flow_metrics(conn)
    total += import_other_dashboards(conn)

    # Get statistics
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT metric_date) FROM metrics")
    date_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT dashboard) FROM metrics")
    dashboard_count = cursor.fetchone()[0]

    conn.close()

    print("\n" + "=" * 70)
    print("✓ Import complete!")
    print(f"  Total metrics imported: {total}")
    print(f"  Unique dates: {date_count}")
    print(f"  Dashboards: {dashboard_count}")
    print(f"  Database: {DB_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    main()
