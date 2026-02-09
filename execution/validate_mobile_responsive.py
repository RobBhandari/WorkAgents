"""
Mobile Responsiveness Validation Script

Validates that all dashboard generators use the mobile-responsive framework
and have proper mobile support.

Usage:
    python execution/validate_mobile_responsive.py
"""

import os
from pathlib import Path


def check_dashboard_file(filepath):
    """
    Check if dashboard uses framework and has mobile support.

    Args:
        filepath: Path to dashboard generator file

    Returns:
        dict: Dictionary of checks and their pass/fail status
    """
    if not os.path.exists(filepath):
        return {
            "file_exists": False,
            "uses_framework": False,
            "has_table_wrapper": False,
            "viewport_meta": False,
        }

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    checks = {
        "file_exists": True,
        "uses_framework": "from execution.dashboard_framework import" in content
        or "import dashboard_framework" in content,
        "has_table_wrapper": ".table-wrapper" in content
        or '<div class="table-wrapper">' in content
        or 'class="table-wrapper"' in content,
        "viewport_meta": "width=device-width" in content,
    }

    return checks


def main():
    """Main validation function"""
    dashboard_files = [
        "execution/generate_quality_dashboard.py",
        "execution/generate_flow_dashboard.py",
        "execution/generate_ownership_dashboard.py",
        "execution/generate_risk_dashboard.py",
        "execution/generate_deployment_dashboard.py",
        "execution/generate_collaboration_dashboard.py",
        "execution/generate_security_dashboard.py",
        "execution/generate_target_dashboard.py",
        "execution/generate_trends_dashboard.py",
        "execution/generate_executive_summary.py",
        "execution/usage_tables_report.py",
    ]

    print("=" * 70)
    print("Mobile Responsiveness Validation Report")
    print("=" * 70)
    print()

    total_dashboards = len(dashboard_files)
    passed_dashboards = 0
    failed_dashboards = []

    for filepath in dashboard_files:
        checks = check_dashboard_file(filepath)
        all_passed = all(checks.values())

        if all_passed:
            status = "[PASS]"
            passed_dashboards += 1
        else:
            status = "[FAIL]"
            failed_dashboards.append(Path(filepath).name)

        print(f"{status} {Path(filepath).name}")

        if not all_passed:
            for check, passed in checks.items():
                if not passed:
                    print(f"   - Missing: {check}")
            print()

    print()
    print("=" * 70)
    print(f"Summary: {passed_dashboards}/{total_dashboards} dashboards passed validation")
    print("=" * 70)

    if failed_dashboards:
        print()
        print("Failed dashboards:")
        for dashboard in failed_dashboards:
            print(f"  - {dashboard}")

    return 0 if passed_dashboards == total_dashboards else 1


if __name__ == "__main__":
    exit(main())
