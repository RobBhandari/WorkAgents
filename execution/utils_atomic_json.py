#!/usr/bin/env python3
"""
Utility functions for atomic JSON file operations.

Prevents corruption by ensuring files are never left in a half-written state.
"""

import json
import os
import shutil
import tempfile
from typing import Any


def atomic_json_save(data: dict, output_file: str) -> bool:
    """
    Save JSON data to file using atomic write operations.

    This prevents corruption even if the write is interrupted by:
    1. Writing to a temporary file first
    2. Validating the JSON is correct
    3. Atomically moving the temp file to the final location

    Args:
        data: Dictionary to save as JSON
        output_file: Target file path

    Returns:
        True if save succeeded, False otherwise
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Create temp file in same directory (for atomic move)
    temp_fd, temp_path = tempfile.mkstemp(suffix=".json", dir=os.path.dirname(output_file), text=True)

    try:
        # Write to temp file with UTF-8 encoding
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Verify the temp file is valid JSON before moving
        with open(temp_path, encoding="utf-8") as f:
            json.load(f)  # This will raise JSONDecodeError if invalid

        # Atomic move (rename is atomic on most filesystems)
        shutil.move(temp_path, output_file)
        return True

    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e


def load_json_with_recovery(file_path: str, default_value: dict[Any, Any] | None = None) -> dict[Any, Any]:
    """
    Load JSON file with automatic recovery from corruption.

    If the file is corrupted or invalid, returns default_value instead
    of crashing.

    Args:
        file_path: Path to JSON file
        default_value: Value to return if file is invalid (defaults to {})

    Returns:
        Loaded JSON data or default_value
    """
    if default_value is None:
        default_value = {}

    if not os.path.exists(file_path):
        return default_value

    try:
        with open(file_path, encoding="utf-8") as f:
            data: dict[Any, Any] = json.load(f)
        return data

    except json.JSONDecodeError as e:
        print(f"\n[WARNING] JSON file is corrupted ({e}) - using default value")
        return default_value

    except UnicodeDecodeError as e:
        print(f"\n[WARNING] JSON file has encoding issues ({e}) - using default value")
        return default_value

    except Exception as e:
        print(f"\n[WARNING] Failed to load JSON file ({e}) - using default value")
        return default_value
