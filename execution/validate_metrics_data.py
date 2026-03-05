#!/usr/bin/env python3
"""
Validate metrics history files before dashboard generation.

Checks that all required history files exist, are valid JSON,
and have the expected structure with at least one week of data.
"""

import json
import os
import sys
from pathlib import Path


def _check_file_readable(file_path: str) -> tuple:
    """Check file exists and is non-empty. Returns (file_size, error_message)."""
    if not os.path.exists(file_path):
        return None, "File does not exist"
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        return None, "File is empty (0 bytes)"
    return file_size, None


def _check_weeks_structure(data: dict) -> tuple:
    """Validate the weeks key and structure. Returns (weeks, error_message)."""
    if "weeks" not in data:
        return None, "Missing 'weeks' key in data structure"
    weeks = data["weeks"]
    if not isinstance(weeks, list):
        return None, "'weeks' is not a list"
    if len(weeks) == 0:
        return None, "No weeks data found (empty weeks array)"
    return weeks, None


def _check_required_fields(weeks: list, required_fields: list) -> tuple:
    """Validate required fields in the latest week. Returns (ok, error_message)."""
    latest_week = weeks[-1]
    missing_fields = [field for field in required_fields if field not in latest_week]
    if missing_fields:
        return False, f"Missing required fields: {missing_fields}"
    return True, None


def validate_history_file(file_path: str, required_fields: list | None = None) -> tuple:
    """
    Validate a single history file.

    Returns: (is_valid, error_message)
    """
    file_size, err = _check_file_readable(file_path)
    if err:
        return False, err

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except UnicodeDecodeError as e:
        return False, f"Unicode decode error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"

    weeks, err = _check_weeks_structure(data)
    if err:
        return False, err

    if required_fields:
        ok, err = _check_required_fields(weeks, required_fields)
        if not ok:
            return False, err

    return True, f"Valid ({len(weeks)} weeks, {file_size:,} bytes)"


def _setup_utf8_console() -> None:
    """Configure UTF-8 console output on Windows."""
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


def _run_validations(required_files: dict, data_dir: Path) -> list:
    """Validate each file and return list of result dicts."""
    validation_results = []
    for filename, required_fields in required_files.items():
        file_path = data_dir / filename
        is_valid, message = validate_history_file(str(file_path), required_fields)
        status_icon = "✓" if is_valid else "✗"
        status_text = "VALID" if is_valid else "INVALID"
        print(f"{status_icon} {filename:30s} {status_text:8s} - {message}")
        validation_results.append({"file": filename, "valid": is_valid, "message": message})
    return validation_results


def _print_summary(validation_results: list, total_count: int) -> int:
    """Print validation summary and return exit code."""
    print("=" * 70)
    all_valid = all(r["valid"] for r in validation_results)
    if all_valid:
        print("✓ All metrics history files are valid!")
        print(f"✓ Total files validated: {total_count}")
        return 0
    invalid_count = sum(1 for r in validation_results if not r["valid"])
    print(f"✗ Validation failed! {invalid_count}/{total_count} files are invalid.")
    print("\nInvalid files:")
    for result in validation_results:
        if not result["valid"]:
            print(f"  - {result['file']}: {result['message']}")
    return 1


def main():
    """Validate all metrics history files"""
    _setup_utf8_console()

    print("=" * 70)
    print("Metrics Data Validation")
    print("=" * 70)

    data_dir = Path(".tmp/observatory")

    required_files = {
        "quality_history.json": ["projects", "week_date"],
        "security_history.json": ["week_date"],
        "flow_history.json": ["projects", "week_date"],
        "deployment_history.json": ["projects", "week_date"],
        "collaboration_history.json": ["projects", "week_date"],
        "ownership_history.json": ["projects", "week_date"],
        "risk_history.json": ["projects", "week_date"],
    }

    validation_results = _run_validations(required_files, data_dir)
    return _print_summary(validation_results, len(required_files))


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
