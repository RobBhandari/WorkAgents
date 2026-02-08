#!/usr/bin/env python3
"""
Pre-commit hook to detect security wrapper violations

Checks for:
1. Direct os.getenv() calls -> should use secure_config.get_config()
2. Direct requests imports -> should use http_client
3. HTML string building -> should use Jinja2 templates

Returns exit code 1 if violations found (warning only, non-blocking)
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

# Files to exclude from checks
EXCLUDE_PATTERNS = [
    "secure_config.py",
    "http_client.py",
    "security_utils.py",
    "__init__.py",
    "check-security-wrappers.py",
]

# Directories to exclude
EXCLUDE_DIRS = [
    "experiments",
    "archive",
    ".venv",
    "tests",
    "__pycache__",
]


class SecurityWrapperChecker:
    """Checks for security wrapper violations in Python files"""

    def __init__(self):
        self.violations = []

    def check_file(self, file_path: str) -> list[tuple[int, str]]:
        """Check a single file for violations

        Returns:
            List of (line_number, violation_message) tuples
        """
        path = Path(file_path)

        # Skip excluded files
        if path.name in EXCLUDE_PATTERNS:
            return []

        # Skip excluded directories
        if any(excluded in path.parts for excluded in EXCLUDE_DIRS):
            return []

        violations = []

        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
        except (UnicodeDecodeError, FileNotFoundError):
            return []

        for line_num, line in enumerate(lines, 1):
            # Check for os.getenv() usage
            if "os.getenv" in line or "os.environ.get" in line:
                violations.append(
                    (
                        line_num,
                        "[X] Direct os.getenv() usage detected\n"
                        "   -> Use: from secure_config import get_config; config = get_config()\n"
                        f"   -> Line: {line.strip()}",
                    )
                )

            # Check for direct requests import
            if re.match(r"^\s*import requests\s*$", line) or re.match(r"^\s*from requests import", line):
                violations.append(
                    (
                        line_num,
                        "[X] Direct requests import detected\n"
                        "   -> Use: from http_client import get, post, put, delete, patch\n"
                        f"   -> Line: {line.strip()}",
                    )
                )

            # Check for potential HTML string building (warning only)
            if re.search(r'f["\'].*<(div|html|body|table|tr|td)', line):
                violations.append(
                    (
                        line_num,
                        "[!]  HTML string building detected (consider Jinja2 templates)\n"
                        "   -> Consider: Using templates/ directory with Jinja2\n"
                        f"   -> Line: {line.strip()[:80]}...",
                    )
                )

        return violations

    def check_files(self, file_paths: list[str]) -> bool:
        """Check multiple files for violations

        Returns:
            True if violations found, False otherwise
        """
        has_violations = False

        for file_path in file_paths:
            if not file_path.endswith(".py"):
                continue

            violations = self.check_file(file_path)

            if violations:
                has_violations = True
                print(f"\n[FILE] {file_path}")
                for line_num, message in violations:
                    print(f"   Line {line_num}: {message}")

        return has_violations


def main():
    """Main entry point for pre-commit hook"""

    # Get files to check from command line args
    files_to_check = sys.argv[1:] if len(sys.argv) > 1 else []

    if not files_to_check:
        print("[INFO] No files to check")
        return 0

    checker = SecurityWrapperChecker()
    has_violations = checker.check_files(files_to_check)

    if has_violations:
        print("\n" + "=" * 80)
        print("[WARNING] SECURITY WRAPPER VIOLATIONS DETECTED")
        print("=" * 80)
        print("\n[DOCS] For guidelines, see: execution/CONTRIBUTING.md")
        print("\n[INFO] This is a warning only (non-blocking).")
        print("       Please fix violations to maintain code quality.\n")
        return 0  # Return 0 (non-blocking) for now

    return 0


if __name__ == "__main__":
    sys.exit(main())
