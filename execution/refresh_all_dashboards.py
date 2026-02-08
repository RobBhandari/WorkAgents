#!/usr/bin/env python3
"""
Refresh all Observatory dashboards
Runs all metrics collectors and dashboard generators in sequence
"""

import subprocess
import sys
from datetime import datetime


def run_script(script_path, description):
    """Run a Python script and return success status"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"{'='*60}")

    try:
        result = subprocess.run([sys.executable, script_path], capture_output=False, text=True, check=False)

        if result.returncode == 0:
            print(f"[OK] {description} - SUCCESS")
            return True
        else:
            print(f"[FAIL] {description} - FAILED (exit code: {result.returncode})")
            return False
    except Exception as e:
        print(f"[ERROR] {description} - ERROR: {e}")
        return False


def main():
    print("=" * 60)
    print("Director Observatory - Dashboard Refresh")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = {}

    # Phase 1: Collect Metrics (ASYNC - 3-5x faster!)
    print("\n" + "=" * 60)
    print("PHASE 1: COLLECTING METRICS (ASYNC)")
    print("=" * 60)

    # Run async collector orchestrator (runs all collectors concurrently)
    print("\nRunning async metrics collection...")
    print("Expected duration: 30-90 seconds (vs 3-7 minutes sequential)")
    print()

    result = subprocess.run(
        [sys.executable, "execution/collect_all_metrics.py"],
        capture_output=False,
        text=True,
        check=False
    )

    if result.returncode == 0:
        print("\n[OK] Async metrics collection - SUCCESS")
        results["Metrics Collection (Async)"] = True
    else:
        print("\n[WARN] Async metrics collection had some failures")
        results["Metrics Collection (Async)"] = False

    # Legacy sequential collectors (commented out - fallback if needed)
    # collectors = [
    #     ("execution/ado_quality_metrics.py", "Quality Metrics"),
    #     ("execution/ado_flow_metrics.py", "Flow Metrics"),
    #     ("execution/ado_ownership_metrics.py", "Ownership Metrics"),
    #     ("execution/ado_risk_metrics.py", "Risk Metrics"),
    #     ("execution/ado_deployment_metrics.py", "Deployment Metrics (DORA)"),
    #     ("execution/ado_collaboration_metrics.py", "Collaboration Metrics (PR Analysis)"),
    #     ("execution/armorcode_enhanced_metrics.py", "Security Metrics (ArmorCode)"),
    # ]
    # for script, name in collectors:
    #     results[name] = run_script(script, name)

    # Phase 2: Generate Dashboards
    print("\n" + "=" * 60)
    print("PHASE 2: GENERATING DASHBOARDS")
    print("=" * 60)

    generators = [
        ("execution/generate_quality_dashboard.py", "Quality Dashboard"),
        ("execution/generate_flow_dashboard.py", "Flow Dashboard"),
        ("execution/generate_ownership_dashboard.py", "Ownership Dashboard"),
        ("execution/generate_risk_dashboard.py", "Risk Dashboard"),
        ("execution/generate_deployment_dashboard.py", "Deployment Dashboard"),
        ("execution/generate_collaboration_dashboard.py", "Collaboration Dashboard"),
        ("execution/archive/generate_security_dashboard_original.py", "Security Dashboard (with drill-down)"),
        ("execution/archive/generate_trends_dashboard_original.py", "Executive Trends (index.html)"),
    ]

    for script, name in generators:
        results[name] = run_script(script, name)

    # Summary
    print("\n" + "=" * 60)
    print("REFRESH SUMMARY")
    print("=" * 60)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    successful = sum(1 for v in results.values() if v)
    failed = len(results) - successful

    print(f"Total tasks: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print()

    if failed > 0:
        print("Failed tasks:")
        for task, success in results.items():
            if not success:
                print(f"  [X] {task}")
    else:
        print("[OK] All dashboards refreshed successfully!")

    print("\nDashboards location: .tmp/observatory/dashboards/")
    print("Open index: start .tmp/observatory/dashboards/index.html")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
