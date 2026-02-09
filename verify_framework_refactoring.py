"""
Verification Script for Framework Refactoring

Tests that all dashboards still generate correctly after refactoring
execution/dashboard_framework.py into execution/framework/ package.
"""

import sys
from pathlib import Path


def test_framework_import():
    """Test that the new framework can be imported"""
    try:
        from execution.framework import get_dashboard_framework

        print("[PASS] New framework import successful: execution.framework")
        return True
    except ImportError as e:
        print(f"[FAIL] Failed to import new framework: {e}")
        return False


def test_old_framework_import():
    """Test that the old deprecated module still works"""
    try:
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from execution.dashboard_framework import get_dashboard_framework

            # Check that deprecation warning was issued
            if len(w) > 0 and issubclass(w[0].category, DeprecationWarning):
                print("[PASS] Old framework import works (with deprecation warning)")
                return True
            else:
                print("[WARN] Old framework import works but no deprecation warning issued")
                return True
    except ImportError as e:
        print(f"[FAIL] Failed to import old framework: {e}")
        return False


def test_framework_output():
    """Test that framework generates valid CSS and JavaScript"""
    try:
        from execution.framework import get_dashboard_framework

        css, js = get_dashboard_framework()

        # Basic validation
        assert isinstance(css, str) and len(css) > 0, "CSS is empty"
        assert isinstance(js, str) and len(js) > 0, "JavaScript is empty"
        assert "<style>" in css and "</style>" in css, "CSS missing tags"
        assert "<script>" in js and "</script>" in js, "JavaScript missing tags"
        assert ":root {" in css, "CSS missing theme variables"
        assert "function toggleTheme()" in js, "JavaScript missing theme toggle"

        print(f"[PASS] Framework generates valid output ({len(css)} chars CSS, {len(js)} chars JS)")
        return True
    except Exception as e:
        print(f"[FAIL] Framework output test failed: {e}")
        return False


def test_custom_colors():
    """Test framework with custom colors"""
    try:
        from execution.framework import get_dashboard_framework

        css, _ = get_dashboard_framework(header_gradient_start="#8b5cf6", header_gradient_end="#7c3aed")

        assert "--header-gradient-start: #8b5cf6" in css
        assert "--header-gradient-end: #7c3aed" in css

        print("[PASS] Custom colors work correctly")
        return True
    except Exception as e:
        print(f"[FAIL] Custom colors test failed: {e}")
        return False


def test_feature_flags():
    """Test framework with different feature flags"""
    try:
        from execution.framework import get_dashboard_framework

        # Full features
        _, js_full = get_dashboard_framework(
            include_table_scroll=True, include_expandable_rows=True, include_glossary=True
        )

        # Minimal features
        _, js_min = get_dashboard_framework(
            include_table_scroll=False, include_expandable_rows=False, include_glossary=False
        )

        assert "function toggleGlossary()" in js_full
        assert "function toggleGlossary()" not in js_min
        assert len(js_full) > len(js_min)

        print("[PASS] Feature flags work correctly")
        return True
    except Exception as e:
        print(f"[FAIL] Feature flags test failed: {e}")
        return False


def test_backward_compatibility():
    """Test that old and new APIs produce identical output"""
    try:
        import warnings

        from execution.framework import get_dashboard_framework as new_func

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from execution.dashboard_framework import get_dashboard_framework as old_func

        # Test with same parameters
        css_new, js_new = new_func(
            header_gradient_start="#667eea",
            header_gradient_end="#764ba2",
            include_table_scroll=True,
            include_expandable_rows=False,
            include_glossary=True,
        )

        css_old, js_old = old_func(
            header_gradient_start="#667eea",
            header_gradient_end="#764ba2",
            include_table_scroll=True,
            include_expandable_rows=False,
            include_glossary=True,
        )

        # Output should be identical
        assert css_new == css_old, "CSS output differs between old and new"
        assert js_new == js_old, "JavaScript output differs between old and new"

        print("[PASS] Backward compatibility maintained (identical output)")
        return True
    except Exception as e:
        print(f"[FAIL] Backward compatibility test failed: {e}")
        return False


def test_dashboard_imports():
    """Test that dashboard files can still import the framework"""
    dashboards = [
        "ai",
        "collaboration",
        "deployment",
        "executive",
        "flow",
        "ownership",
        "quality",
        "risk",
        "security",
        "targets",
        "trends",
    ]

    print("\nTesting dashboard imports:")
    success_count = 0

    for dashboard in dashboards:
        try:
            module_name = f"execution.dashboards.{dashboard}"
            __import__(module_name)
            print(f"  [PASS] {dashboard}")
            success_count += 1
        except ImportError as e:
            print(f"  [FAIL] {dashboard}: {e}")

    total = len(dashboards)
    if success_count == total:
        print(f"[PASS] All {total} dashboards import successfully")
        return True
    else:
        print(f"[WARN] {success_count}/{total} dashboards import successfully")
        return success_count == total


def main():
    """Run all verification tests"""
    print("=" * 70)
    print("Framework Refactoring Verification")
    print("=" * 70)
    print()

    tests = [
        test_framework_import,
        test_old_framework_import,
        test_framework_output,
        test_custom_colors,
        test_feature_flags,
        test_backward_compatibility,
        test_dashboard_imports,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"[FAIL] Test {test.__name__} crashed: {e}")
            results.append(False)
        print()

    print("=" * 70)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"[PASS] ALL TESTS PASSED ({passed}/{total})")
        print("=" * 70)
        return 0
    else:
        print(f"[FAIL] SOME TESTS FAILED ({passed}/{total} passed)")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
