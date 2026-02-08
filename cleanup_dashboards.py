#!/usr/bin/env python3
"""
Clean up old/deprecated dashboard files from .tmp/observatory/dashboards/
"""

import os
from pathlib import Path

# Files to remove (old/deprecated)
OLD_FILES = [
    'executive_summary.html',
    'trends_dashboard.html',
    'ai_contributions.html',
    'security_dashboard.html',  # Old name, now uses security.html
]

# ML Prototypes (decide whether to keep or remove)
PROTOTYPE_FILES = [
    'correlation_prototype.html',
    'forecast_prototype.html',
    'health_scorecard_prototype.html',
    'trends_prototype.html',
]

def cleanup_dashboards():
    """Remove old dashboard files"""

    dashboard_dir = Path('.tmp/observatory/dashboards')

    if not dashboard_dir.exists():
        print(f"[ERROR] Directory not found: {dashboard_dir}")
        return

    print("Cleaning up dashboard files...\n")

    # Remove old files
    print("Removing deprecated files:")
    for filename in OLD_FILES:
        file_path = dashboard_dir / filename
        if file_path.exists():
            file_path.unlink()
            print(f"  [OK] Deleted: {filename}")
        else:
            print(f"  [SKIP]  Not found: {filename}")

    # Show prototypes but don't delete (user decision)
    print("\nML Prototypes (not linked from dashboards):")
    for filename in PROTOTYPE_FILES:
        file_path = dashboard_dir / filename
        if file_path.exists():
            size_kb = file_path.stat().st_size / 1024
            print(f"  [?] {filename} ({size_kb:.1f} KB)")

    print("\n" + "="*60)
    print("Cleanup complete!")
    print("\nTo remove ML prototypes, delete them manually or run:")
    print("  rm .tmp/observatory/dashboards/*_prototype.html")
    print("="*60)


if __name__ == "__main__":
    cleanup_dashboards()
