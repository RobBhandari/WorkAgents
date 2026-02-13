"""
Genericize product names in history files for public repository.

This script replaces real product names with generic placeholders (Product A, B, C, etc.)
in all history JSON files to prepare for public GitHub repository.

SECURITY NOTE:
- Product name mappings are loaded from .product_mapping_forward.json (not committed to git)
- In CI/CD, this file is created from GitHub Secrets
- Never commit the mapping file - it contains sensitive product information
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict


def load_forward_mapping() -> Dict[str, str]:
    """
    Load forward mapping (real name -> generic name) from file.

    Returns:
        Dictionary mapping real names to generic names

    Raises:
        FileNotFoundError: If mapping file doesn't exist
        ValueError: If mapping file is invalid
    """
    mapping_file = Path(".product_mapping_forward.json")

    if not mapping_file.exists():
        print(f"[ERROR] Forward mapping file not found: {mapping_file}")
        print("In CI/CD, this file should be created from PRODUCT_NAME_MAPPING_FORWARD secret")
        print("Locally, create it with: echo '$MAPPING_JSON' > .product_mapping_forward.json")
        sys.exit(1)

    try:
        with open(mapping_file, "r", encoding="utf-8") as f:
            mapping = json.load(f)

        if not isinstance(mapping, dict):
            raise ValueError("Mapping file must contain a JSON object")

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
    PRODUCT_MAPPING = load_forward_mapping()
except SystemExit:
    # Re-raise SystemExit to allow proper script termination
    raise
except Exception as e:
    print(f"[FATAL] Unexpected error loading forward mapping: {e}")
    sys.exit(1)


def genericize_value(value: Any, stats: Dict[str, int]) -> Any:
    """
    Recursively replace product names and sensitive data in any data structure.

    Args:
        value: Value to process (can be dict, list, str, or primitive)
        stats: Dictionary to track replacement counts

    Returns:
        Genericized value
    """
    if isinstance(value, dict):
        # Genericize both keys AND values
        genericized_dict = {}
        for k, v in value.items():
            # Genericize the key
            genericized_key = k
            for real_name, generic_name in sorted(
                PRODUCT_MAPPING.items(), key=lambda x: len(x[0]), reverse=True
            ):
                if real_name in genericized_key:
                    count = genericized_key.count(real_name)
                    stats[real_name] = stats.get(real_name, 0) + count
                    genericized_key = genericized_key.replace(real_name, generic_name)

            # Genericize the value recursively
            genericized_dict[genericized_key] = genericize_value(v, stats)
        return genericized_dict
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

        # Anonymize email addresses (replace @theaccessgroup.com with @company.com)
        if "@theaccessgroup.com" in genericized:
            # Extract name part before @ and create generic email
            import re
            email_pattern = r'([a-zA-Z0-9._%+-]+)@theaccessgroup\.com'
            matches = re.findall(email_pattern, genericized)
            for match in matches:
                original_email = f"{match}@theaccessgroup.com"
                # Convert email to name format (jac.martin -> Jac Martin)
                name_parts = match.split('.')
                generic_name = ' '.join(word.capitalize() for word in name_parts)
                genericized = genericized.replace(original_email, generic_name)
                stats["email_anonymized"] = stats.get("email_anonymized", 0) + 1

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
