"""
Genericize product names in history files for public repository.

This script replaces real product names with generic placeholders (Product A, B, C, etc.)
in all history JSON files to prepare for public GitHub repository.

SECURITY NOTE:
- Product name mappings are loaded from .product_mapping_forward.json (not committed to git)
- In CI/CD, this file is created from GitHub Secrets
- Never commit the mapping file - it contains sensitive product information

SHARED COMPONENTS:
- Uses execution.utils.product_name_translator for translation logic (DRY principle)
- Ensures consistency with de_genericize_history_files.py
"""

import sys
from pathlib import Path

from execution.utils.product_name_translator import (
    load_mapping_file,
    translate_history_file,
)

# Load forward mapping at module level
try:
    PRODUCT_MAPPING = load_mapping_file(
        Path(".product_mapping_forward.json"), direction="forward"
    )
except SystemExit:
    # Re-raise SystemExit to allow proper script termination
    raise
except Exception as e:
    print(f"[FATAL] Unexpected error loading forward mapping: {e}")
    sys.exit(1)


def genericize_history_file(file_path: Path) -> dict[str, int]:
    """
    Genericize a single history file.

    Args:
        file_path: Path to history JSON file

    Returns:
        Dictionary of replacement statistics
    """
    print(f"Processing {file_path.name}...")

    # Use shared translator (no fail_on_unmapped for forward direction)
    stats = translate_history_file(
        file_path, PRODUCT_MAPPING, direction="forward", fail_on_unmapped=False
    )

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
    total_stats: dict[str, int] = {}
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
    print("\nReplacements made:")

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
