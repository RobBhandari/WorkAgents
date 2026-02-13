"""
De-genericize product names in history files (reverse translation).

This script replaces generic placeholders (Product A, B, C, etc.) with real product names
to prepare fresh data for Azure deployment with real names visible.

This is the REVERSE of genericize_history_files.py.

SECURITY NOTE:
- Product name mappings are loaded from .product_mapping.json (not committed to git)
- In CI/CD, this file is created from GitHub Secrets
- Never commit the mapping file - it contains sensitive product information

SHARED COMPONENTS:
- Uses execution.utils.product_name_translator for translation logic (DRY principle)
- Ensures consistency with genericize_history_files.py
"""

import sys
from pathlib import Path
from typing import Dict

# Import shared translation utilities
from execution.utils.product_name_translator import (
    load_mapping_file,
    translate_history_file,
)


# Load reverse mapping from file (created from GitHub Secret in CI/CD)
try:
    REVERSE_MAPPING = load_mapping_file(
        Path(".product_mapping.json"), direction="reverse"
    )
except SystemExit:
    # Re-raise SystemExit to allow proper script termination
    raise
except Exception as e:
    print(f"[FATAL] Unexpected error loading reverse mapping: {e}")
    sys.exit(1)


def de_genericize_history_file(file_path: Path) -> bool:
    """
    De-genericize a single history JSON file.

    Args:
        file_path: Path to history file

    Returns:
        True if successful, False otherwise
    """
    try:
        # Use shared translator with FAIL-LOUD validation
        stats = translate_history_file(
            file_path,
            REVERSE_MAPPING,
            direction="reverse",
            fail_on_unmapped=True,  # Fail loudly if unmapped generic products found
        )

        # Report
        total_replacements = sum(stats.values())
        if total_replacements > 0:
            print(f"[OK] {file_path.name}: {total_replacements} de-genericizations")
            for generic, count in sorted(stats.items()):
                print(f"   {generic} -> {REVERSE_MAPPING[generic]}: {count}x")
        else:
            print(
                f"[INFO]  {file_path.name}: No generic names found (already real names)"
            )

        return True

    except ValueError as e:
        # Fail-loud validation error (unmapped generic products)
        print(f"[ERROR] {file_path.name}: {e}")
        return False
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
