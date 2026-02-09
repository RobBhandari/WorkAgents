"""
De-genericize product names in history files (reverse translation).

This script replaces generic placeholders (Product A, B, C, etc.) with real product names
to prepare fresh data for Azure deployment with real names visible.

This is the REVERSE of genericize_history_files.py.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

# Reverse mapping (generic name -> real name)
# This is the OPPOSITE of the genericization mapping
REVERSE_MAPPING = {
    "Product A": "Access Legal Case Management",
    "Product B": "One Office & Financial Director",
    "Product C": "Access LawFusion",
    "Product D": "Access Legal Proclaim",
    "Product E": "Access Legal Compliance",
    "Product F": "Access Legal InCase",
    "Product G": "Access Diversity",
    "Product H": "Access Legal AI Services",
    "Product I": "Access Legal Framework",
    "Product J": "Access MyCalendars",
    "Product K": "Eclipse",
    "Product L": "Access LegalBricks",
    "Product M": "Legal Workspace",
    "Product N": "Proclaim Portals - Eclipse",
    "Product O": "Learning Content Legal",
}


def degener icize_value(value: Any, stats: Dict[str, int]) -> Any:
    """
    Recursively replace generic product names with real names.

    Args:
        value: Value to process (can be dict, list, str, or primitive)
        stats: Dictionary to track replacement counts

    Returns:
        De-genericized value
    """
    if isinstance(value, dict):
        return {k: degener icize_value(v, stats) for k, v in value.items()}
    elif isinstance(value, list):
        return [degener icize_value(item, stats) for item in value]
    elif isinstance(value, str):
        degener icized = value
        # Replace generic names with real names
        # Order from most specific to least specific
        for generic_name, real_name in sorted(
            REVERSE_MAPPING.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if generic_name in degener icized:
                degener icized = degener icized.replace(generic_name, real_name)
                stats[generic_name] = stats.get(generic_name, 0) + 1
        return degener icized
    else:
        return value


def degener icize_history_file(file_path: Path) -> bool:
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
        degener icized_data = degener icize_value(data, stats)

        # Save back
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(degener icized_data, f, indent=2, ensure_ascii=False)

        # Report
        total_replacements = sum(stats.values())
        if total_replacements > 0:
            print(f"✅ {file_path.name}: {total_replacements} de-genericizations")
            for generic, count in sorted(stats.items()):
                print(f"   {generic} → {REVERSE_MAPPING[generic]}: {count}x")
        else:
            print(f"ℹ️  {file_path.name}: No generic names found (already real names)")

        return True

    except Exception as e:
        print(f"❌ Error processing {file_path.name}: {e}")
        return False


def main():
    """De-genericize all history files in .tmp/observatory/."""
    print("🔓 De-Genericizing History Files (Generic → Real Names)")
    print("=" * 70)

    history_dir = Path(".tmp/observatory")

    if not history_dir.exists():
        print(f"❌ Directory not found: {history_dir}")
        sys.exit(1)

    # Find all history JSON files
    history_files = list(history_dir.glob("*_history.json"))

    if not history_files:
        print(f"⚠️  No history files found in {history_dir}")
        sys.exit(0)

    print(f"Found {len(history_files)} history files to de-genericize\n")

    success_count = 0
    for file_path in sorted(history_files):
        if degener icize_history_file(file_path):
            success_count += 1

    print("\n" + "=" * 70)
    print(f"✅ De-genericization complete: {success_count}/{len(history_files)} files processed")
    print("🔒 History files now contain REAL product names for Azure deployment")
    print("📝 These will be genericized again before committing to git")


if __name__ == "__main__":
    main()
