"""
De-genericize product names in history files (reverse translation).

This script replaces generic placeholders (Product A, B, C, etc.) with real product names
to prepare fresh data for Azure deployment with real names visible.

This is the REVERSE of genericize_history_files.py.

SECURITY NOTE:
- Product name mappings are loaded from .product_mapping.json (not committed to git)
- In CI/CD, this file is created from GitHub Secrets
- Never commit the mapping file - it contains sensitive product information
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Load reverse mapping from file (created from GitHub Secret in CI/CD)
def load_reverse_mapping() -> Dict[str, str]:
    """
    Load reverse mapping from .product_mapping.json file.

    Returns:
        Dictionary mapping generic names to real names

    Raises:
        FileNotFoundError: If mapping file doesn't exist
        ValueError: If mapping file is invalid
    """
    mapping_file = Path(".product_mapping.json")

    if not mapping_file.exists():
        print(f"[ERROR] Mapping file not found: {mapping_file}")
        print("In CI/CD, this file should be created from PRODUCT_NAME_MAPPING secret")
        print("Locally, create it with: echo '$MAPPING_JSON' > .product_mapping.json")
        sys.exit(1)

    try:
        with open(mapping_file, "r", encoding="utf-8") as f:
            mapping = json.load(f)

        if not isinstance(mapping, dict):
            raise ValueError("Mapping file must contain a JSON object")

        # Validate structure (keys should be "Product X", values should be non-empty strings)
        for key, value in mapping.items():
            if not key.startswith("Product "):
                print(f"[WARN] Unexpected key in mapping: {key}")
            if not isinstance(value, str) or not value:
                raise ValueError(f"Invalid mapping value for key: {key}")

        print(f"[OK] Loaded {len(mapping)} product mappings from {mapping_file}")
        return mapping

    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in mapping file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Failed to load mapping file: {e}")
        sys.exit(1)


# Load mapping at module level
try:
    REVERSE_MAPPING = load_reverse_mapping()
except SystemExit:
    # Re-raise SystemExit to allow proper script termination
    raise
except Exception as e:
    print(f"[FATAL] Unexpected error loading reverse mapping: {e}")
    sys.exit(1)


def de_genericize_value(value: Any, stats: Dict[str, int]) -> Any:
    """
    Recursively replace generic product names with real names.

    Args:
        value: Value to process (can be dict, list, str, or primitive)
        stats: Dictionary to track replacement counts

    Returns:
        De-genericized value
    """
    if isinstance(value, dict):
        # De-genericize both keys AND values
        de_genericized_dict = {}
        for k, v in value.items():
            # De-genericize the key
            de_genericized_key = k
            for generic_name, real_name in sorted(
                REVERSE_MAPPING.items(), key=lambda x: len(x[0]), reverse=True
            ):
                if generic_name in de_genericized_key:
                    de_genericized_key = de_genericized_key.replace(generic_name, real_name)
                    stats[generic_name] = stats.get(generic_name, 0) + 1

            # De-genericize the value recursively
            de_genericized_dict[de_genericized_key] = de_genericize_value(v, stats)
        return de_genericized_dict
    elif isinstance(value, list):
        return [de_genericize_value(item, stats) for item in value]
    elif isinstance(value, str):
        de_genericized = value
        # Replace generic names with real names
        # Order from most specific to least specific
        for generic_name, real_name in sorted(
            REVERSE_MAPPING.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if generic_name in de_genericized:
                de_genericized = de_genericized.replace(generic_name, real_name)
                stats[generic_name] = stats.get(generic_name, 0) + 1
        return de_genericized
    else:
        return value


def de_genericize_history_file(file_path: Path) -> bool:
    """
    De-genericize a single history JSON file.

    Args:
        file_path: Path to history file

    Returns:
        True if successful, False otherwise
    """
    try:
        # Load JSON
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Track replacements
        stats: Dict[str, int] = {}

        # De-genericize all values
        de_genericized_data = de_genericize_value(data, stats)

        # Save back
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(de_genericized_data, f, indent=2, ensure_ascii=False)

        # Report
        total_replacements = sum(stats.values())
        if total_replacements > 0:
            print(f"[OK] {file_path.name}: {total_replacements} de-genericizations")
            for generic, count in sorted(stats.items()):
                print(f"   {generic} -> {REVERSE_MAPPING[generic]}: {count}x")
        else:
            print(f"[INFO]  {file_path.name}: No generic names found (already real names)")

        return True

    except Exception as e:
        print(f"[ERROR] Error processing {file_path.name}: {e}")
        return False


def main():
    """De-genericize all history files in .tmp/observatory/."""
    print("De-Genericizing History Files (Generic -> Real Names)")
    print("=" * 70)

    history_dir = Path(".tmp/observatory")

    if not history_dir.exists():
        print(f"[ERROR] Directory not found: {history_dir}")
        sys.exit(1)

    # Find all history JSON files
    history_files = list(history_dir.glob("*_history.json"))

    if not history_files:
        print(f"[WARN]  No history files found in {history_dir}")
        sys.exit(0)

    print(f"Found {len(history_files)} history files to de-genericize\n")

    success_count = 0
    for file_path in sorted(history_files):
        if de_genericize_history_file(file_path):
            success_count += 1

    print("\n" + "=" * 70)
    print(f"[OK] De-genericization complete: {success_count}/{len(history_files)} files processed")
    print("[LOCK] History files now contain REAL product names for Azure deployment")
    print("[NOTE] These will be genericized again before committing to git")


if __name__ == "__main__":
    main()
