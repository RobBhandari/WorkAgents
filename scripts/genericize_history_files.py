"""
Genericize product names in history files for public repository.

This script replaces real product names with generic placeholders (Product A, B, C, etc.)
in all history JSON files to prepare for public GitHub repository.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

# Product name mapping (real name -> generic name)
# IMPORTANT: Ordered from most specific to least specific to avoid partial matches
PRODUCT_MAPPING = {
    # Fix partially-genericized names (from previous runs)
    "Access Legal Product D": "Product D",
    "Access Legal Product F": "Product F",
    "Access Legal Product L": "Product L",
    "Access Product D": "Product D",
    "Access Product F": "Product F",
    "Access Product L": "Product L",
    "Legal Product D": "Product D",
    "Legal Product F": "Product F",
    "Legal Product L": "Product L",

    # Product D variants (do these BEFORE "Proclaim" alone)
    "Access Legal Proclaim": "Product D",
    "Access Proclaim": "Product D",
    "Legal Proclaim": "Product D",
    "Proclaim Portals - Eclipse": "Product N",
    "Proclaim": "Product D",

    # Product F variants (do these BEFORE "inCase" alone)
    "Access Legal InCase": "Product F",
    "Access Legal inCase": "Product F",
    "Access InCase": "Product F",
    "Access inCase": "Product F",
    "Legal InCase": "Product F",
    "Legal inCase": "Product F",
    "inCase": "Product F",

    # Product L variants (do these BEFORE "Legal Bricks" alone)
    "Access LegalBricks": "Product L",
    "Access Legal Bricks": "Product L",
    "LegalBricks": "Product L",
    "Legal Bricks": "Product L",

    # Other products (specific to general)
    "Access Legal Case Management": "Product A",
    "One Office & Financial Director": "Product B",
    "One Office": "Product B",
    "Access LawFusion": "Product C",
    "LawFusion": "Product C",
    "Law Fusion": "Product C",
    "Access Legal Compliance": "Product E",
    "Access Diversity": "Product G",
    "Access Legal AI Services": "Product H",
    "Access Legal Framework": "Product I",
    "Access MyCalendars": "Product J",
    "Eclipse": "Product K",
    "Legal Workspace": "Product M",
    "Learning Content Legal": "Product O",
}


def genericize_value(value: Any, stats: Dict[str, int]) -> Any:
    """
    Recursively replace product names in any data structure.

    Args:
        value: Value to process (can be dict, list, str, or primitive)
        stats: Dictionary to track replacement counts

    Returns:
        Genericized value
    """
    if isinstance(value, dict):
        return {k: genericize_value(v, stats) for k, v in value.items()}
    elif isinstance(value, list):
        return [genericize_value(item, stats) for item in value]
    elif isinstance(value, str):
        # Replace product names (longest first to avoid partial matches)
        genericized = value
        for real_name, generic_name in sorted(
            PRODUCT_MAPPING.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if real_name in genericized:
                count = genericized.count(real_name)
                stats[real_name] = stats.get(real_name, 0) + count
                genericized = genericized.replace(real_name, generic_name)
        return genericized
    else:
        return value


def genericize_history_file(file_path: Path) -> Dict[str, int]:
    """
    Genericize a single history file.

    Args:
        file_path: Path to history JSON file

    Returns:
        Dictionary of replacement statistics
    """
    print(f"Processing {file_path.name}...")

    # Load file
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Track replacements
    stats = {}

    # Genericize all values
    genericized_data = genericize_value(data, stats)

    # Save back
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(genericized_data, f, indent=2, ensure_ascii=False)

    return stats


def main():
    """Main entry point."""
    history_dir = Path(".tmp/observatory")

    if not history_dir.exists():
        print(f"❌ Error: {history_dir} does not exist")
        sys.exit(1)

    # Find all history files
    history_files = list(history_dir.glob("*_history.json"))

    if not history_files:
        print(f"❌ Error: No history files found in {history_dir}")
        sys.exit(1)

    print(f"Found {len(history_files)} history files to process\n")

    # Process each file
    total_stats = {}
    for file_path in sorted(history_files):
        stats = genericize_history_file(file_path)

        # Merge stats
        for product, count in stats.items():
            total_stats[product] = total_stats.get(product, 0) + count

    # Report results
    print(f"\n{'='*70}")
    print("✅ GENERICIZATION COMPLETE")
    print(f"{'='*70}")
    print(f"Files processed: {len(history_files)}")
    print(f"\nReplacements made:")

    if total_stats:
        for product, count in sorted(total_stats.items(), key=lambda x: x[1], reverse=True):
            generic_name = PRODUCT_MAPPING[product]
            print(f"  • '{product}' → '{generic_name}' ({count} occurrences)")
    else:
        print("  • No product names found (files may already be genericized)")

    print(f"\n{'='*70}")
    print("Next steps:")
    print("  1. Review the changes: git diff .tmp/observatory/")
    print("  2. Commit the changes: git add .tmp/observatory/*_history.json")
    print("  3. Push to public repo: git commit -m 'feat: Genericize product names for public repo'")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
