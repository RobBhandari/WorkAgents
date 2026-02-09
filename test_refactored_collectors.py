#!/usr/bin/env python3
"""
Test Refactored Collectors

Quick verification that all refactored collectors work.
"""

import subprocess
import sys


def test_collector(script_path: str, name: str) -> bool:
    """Test a single collector"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            print(f"✓ {name} - PASS")
            return True
        else:
            print(f"✗ {name} - FAIL")
            print(f"  Error: {result.stderr[:200]}")
            return False

    except subprocess.TimeoutExpired:
        print(f"✗ {name} - TIMEOUT")
        return False
    except Exception as e:
        print(f"✗ {name} - ERROR: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("COLLECTOR REFACTORING - VERIFICATION TEST")
    print("="*60)

    collectors = [
        ("execution/utils/ado_batch_utils.py", "Batch Utils"),
        ("execution/utils/statistics.py", "Statistics Utils"),
        ("execution/collectors/ado_quality_metrics.py", "Quality Metrics"),
        ("execution/collectors/ado_risk_metrics.py", "Risk Metrics"),
        ("execution/collectors/ado_ownership_metrics.py", "Ownership Metrics"),
        ("execution/collectors/ado_collaboration_metrics.py", "Collaboration Metrics"),
        ("execution/collectors/ado_deployment_metrics.py", "Deployment Metrics"),
    ]

    results = []
    for script, name in collectors:
        results.append(test_collector(script, name))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(results)
    total = len(results)

    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nCollector refactoring complete and verified.")
        print("Ready to commit!")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("\nPlease review failures above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
