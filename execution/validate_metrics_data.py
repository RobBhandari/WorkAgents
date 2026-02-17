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


def validate_history_file(file_path: str, required_fields: list | None = None) -> tuple:
    """
    Validate a single history file.

    Returns: (is_valid, error_message)
    """
    if not os.path.exists(file_path):
        return False, "File does not exist"

    try:
        # Check file is not empty
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return False, "File is empty (0 bytes)"

        # Check valid JSON
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        # Check has weeks structure
        if "weeks" not in data:
            return False, "Missing 'weeks' key in data structure"

        weeks = data["weeks"]
        if not isinstance(weeks, list):
            return False, "'weeks' is not a list"

        if len(weeks) == 0:
            return False, "No weeks data found (empty weeks array)"

        # Check required fields if specified
        if required_fields:
            latest_week = weeks[-1]
            missing_fields = [field for field in required_fields if field not in latest_week]
            if missing_fields:
                return False, f"Missing required fields: {missing_fields}"

        return True, f"Valid ({len(weeks)} weeks, {file_size:,} bytes)"

    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except UnicodeDecodeError as e:
        return False, f"Unicode decode error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def main():
    """Validate all metrics history files"""
    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    print("=" * 70)
    print("Metrics Data Validation")
    print("=" * 70)

    data_dir = Path(".tmp/observatory")

    # Required history files
    required_files = {
        "quality_history.json": ["projects", "week_date"],
        "security_history.json": ["week_date"],
        "flow_history.json": ["projects", "week_date"],
        "deployment_history.json": ["projects", "week_date"],
        "collaboration_history.json": ["projects", "week_date"],
        "ownership_history.json": ["projects", "week_date"],
        "risk_history.json": ["projects", "week_date"],
    }

    all_valid = True
    validation_results = []

    for filename, required_fields in required_files.items():
        file_path = data_dir / filename
        is_valid, message = validate_history_file(str(file_path), required_fields)

        status_icon = "✓" if is_valid else "✗"
        status_text = "VALID" if is_valid else "INVALID"

        print(f"{status_icon} {filename:30s} {status_text:8s} - {message}")

        validation_results.append({"file": filename, "valid": is_valid, "message": message})

        if not is_valid:
            all_valid = False

    print("=" * 70)

    if all_valid:
        print("✓ All metrics history files are valid!")
        print(f"✓ Total files validated: {len(required_files)}")
        return 0
    else:
        invalid_count = sum(1 for r in validation_results if not r["valid"])
        print(f"✗ Validation failed! {invalid_count}/{len(required_files)} files are invalid.")
        print("\nInvalid files:")
        for result in validation_results:
            if not result["valid"]:
                print(f"  - {result['file']}: {result['message']}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
