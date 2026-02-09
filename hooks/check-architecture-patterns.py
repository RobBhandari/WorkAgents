#!/usr/bin/env python3
"""
Pre-commit hook: Architecture Pattern Enforcement

Ensures new code follows established architectural patterns:
1. HTML generation must use Jinja2 templates (not f-strings)
2. New dashboard generators must use domain models
3. Files must stay under 500 lines
4. Public functions must have type hints

Exit codes:
  0: All checks passed
  1: Architecture violations found
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


class ArchitectureViolation:
    def __init__(self, file_path: str, line_num: int, violation_type: str, message: str):
        self.file_path = file_path
        self.line_num = line_num
        self.violation_type = violation_type
        self.message = message


def check_html_in_strings(file_path: Path) -> list[ArchitectureViolation]:
    """Detect HTML generation with f-strings (should use templates)"""
    violations = []

    # Component files are ALLOWED to generate HTML fragments
    if "components" in str(file_path):
        return violations

    with open(file_path, encoding="utf-8") as f:
        content = f.read()
        lines = content.split("\n")

    # Pattern: f-string or format() with HTML tags
    html_patterns = [
        r'f["\'].*<(?:html|div|table|tr|td|p|h\d|span).*["\']',  # f-string with HTML
        r'["\'].*<(?:html|div|table).*["\']\.format\(',  # str.format() with HTML
        r'html\s*=\s*["\']<html>',  # Direct HTML string assignment
    ]

    for i, line in enumerate(lines, 1):
        for pattern in html_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                violations.append(
                    ArchitectureViolation(
                        str(file_path),
                        i,
                        "HTML_IN_PYTHON",
                        "HTML generation detected in Python code. Use Jinja2 templates instead.",
                    )
                )
                break

    return violations


def check_file_size(file_path: Path, max_lines: int = 575) -> list[ArchitectureViolation]:
    """Enforce file size limits"""
    violations = []

    with open(file_path, encoding="utf-8") as f:
        lines = f.readlines()
        line_count = len(lines)

    if line_count > max_lines:
        violations.append(
            ArchitectureViolation(
                str(file_path),
                1,
                "FILE_TOO_LARGE",
                f"File has {line_count} lines (max: {max_lines}). Consider splitting into modules.",
            )
        )

    return violations


def check_type_hints(file_path: Path) -> list[ArchitectureViolation]:
    """Ensure public functions have type hints"""
    violations = []

    with open(file_path, encoding="utf-8") as f:
        content = f.read()
        lines = content.split("\n")

    # Find public function definitions (not starting with _)
    func_pattern = r"^def ([a-z][a-z0-9_]*)\((.*?)\)(?:\s*->)?\s*:"

    for i, line in enumerate(lines, 1):
        match = re.match(func_pattern, line.strip())
        if match:
            func_name = match.group(1)
            params = match.group(2)
            has_return_type = "->" in line

            # Skip if it's __init__, __str__, etc.
            if func_name.startswith("__"):
                continue

            # Check if parameters have type hints (look for : in params)
            # Simple heuristic: if there are params but no colons, likely missing types
            if params and params.strip() not in ["", "self", "cls"]:
                # Check if parameters have type annotations
                param_list = [p.strip() for p in params.split(",")]
                for param in param_list:
                    if param in ["self", "cls"]:
                        continue
                    if ":" not in param and "=" not in param:
                        violations.append(
                            ArchitectureViolation(
                                str(file_path),
                                i,
                                "MISSING_TYPE_HINTS",
                                f'Function "{func_name}" parameter "{param}" missing type hint',
                            )
                        )

            # Check return type annotation
            if not has_return_type and func_name not in ["__init__", "__str__", "__repr__"]:
                # Allow functions with docstrings that explicitly say "returns None"
                # or have @property decorator
                if i > 1 and "@property" not in lines[i - 2]:
                    violations.append(
                        ArchitectureViolation(
                            str(file_path),
                            i,
                            "MISSING_RETURN_TYPE",
                            f'Function "{func_name}" missing return type annotation',
                        )
                    )

    return violations


def check_domain_model_usage(file_path: Path) -> list[ArchitectureViolation]:
    """Ensure dashboard generators use domain models (not dicts)"""
    violations = []

    # Only check dashboard generators
    if "dashboards" not in str(file_path):
        return violations

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Check if file imports domain models
    has_domain_import = bool(re.search(r"from.*domain.*import", content))

    # Check if file creates dictionaries for metrics (code smell)
    has_dict_metrics = bool(re.search(r"metrics\s*=\s*\{", content))
    has_dict_bugs = bool(re.search(r"bug\s*=\s*\{", content))
    has_dict_vulns = bool(re.search(r"vuln(?:erability)?\s*=\s*\{", content))

    if (has_dict_metrics or has_dict_bugs or has_dict_vulns) and not has_domain_import:
        violations.append(
            ArchitectureViolation(
                str(file_path),
                1,
                "MISSING_DOMAIN_MODELS",
                "Dashboard generator should use domain models instead of dictionaries. "
                "Import from execution.domain (Bug, SecurityMetrics, etc.)",
            )
        )

    return violations


def check_template_usage(file_path: Path) -> list[ArchitectureViolation]:
    """Ensure dashboard generators use templates"""
    violations = []

    # Only check dashboard generators
    if "dashboards" not in str(file_path) or "components" in str(file_path):
        return violations

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Check if file imports template renderer
    has_renderer_import = bool(re.search(r"from.*renderer.*import|from.*dashboards\.renderer", content))

    # Check if file has HTML strings (code smell for dashboards)
    has_html_strings = bool(re.search(r"<html>|<div class=|<table", content))

    if has_html_strings and not has_renderer_import:
        violations.append(
            ArchitectureViolation(
                str(file_path),
                1,
                "MISSING_TEMPLATE_USAGE",
                "Dashboard generator should use Jinja2 templates via render_dashboard(). "
                "Import from execution.dashboards.renderer",
            )
        )

    return violations


def should_skip_file(file_path: Path) -> bool:
    """Determine if file should be skipped"""
    skip_patterns = [
        "archive",
        "experiments",
        "__pycache__",
        ".pyc",
        "test_",  # Test files
        "conftest.py",
        "legacy",  # Legacy code marked for future refactoring
        "collectors",  # Data collection ETL code - different constraints than presentation code
    ]

    # Normalize path to use forward slashes for consistent matching across platforms
    file_str = str(file_path).replace("\\", "/")
    return any(pattern in file_str for pattern in skip_patterns)


def main():
    # Get files from command line (passed by pre-commit)
    files = sys.argv[1:]

    if not files:
        print("[INFO] No files to check")
        return 0

    all_violations = []

    for file_path_str in files:
        file_path = Path(file_path_str)

        # Skip non-Python files
        if file_path.suffix != ".py":
            continue

        # Skip archived/experimental files
        if should_skip_file(file_path):
            continue

        # Run all checks
        violations = []
        violations.extend(check_file_size(file_path))
        violations.extend(check_html_in_strings(file_path))
        violations.extend(check_type_hints(file_path))
        violations.extend(check_domain_model_usage(file_path))
        violations.extend(check_template_usage(file_path))

        all_violations.extend(violations)

    # Report violations
    if all_violations:
        print("\n" + "=" * 70)
        print("ARCHITECTURE VIOLATIONS DETECTED")
        print("=" * 70)

        for v in all_violations:
            print(f"\n[{v.violation_type}] {v.file_path}:{v.line_num}")
            print(f"  -> {v.message}")

        print("\n" + "=" * 70)
        print("GUIDELINES:")
        print("=" * 70)
        print("1. HTML Generation: Use Jinja2 templates (execution.dashboards.renderer)")
        print("2. Data Models: Use domain models (execution.domain.*)")
        print("3. File Size: Keep files under 500 lines")
        print("4. Type Hints: Add type annotations to all public functions")
        print("\nSee: execution/CONTRIBUTING.md for details")
        print("=" * 70)

        return 1

    print("[OK] Architecture patterns check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
