"""
Product name translation utilities for genericizing/de-genericizing history files.

This module provides a single source of truth for translating product names
between real names and generic placeholders (Product A, B, C, etc.).

SECURITY NOTE:
- Product name mappings are loaded from external JSON files (not committed to git)
- In CI/CD, these files are created from GitHub Secrets
- Never commit mapping files - they contain sensitive product information

DRY PRINCIPLE:
- Both genericize_history_files.py and de_genericize_history_files.py use this module
- Ensures consistency between forward and reverse translations
- Reduces duplication and potential bugs
"""

import json
import re
import sys
from pathlib import Path
from typing import Any


def translate_value(
    value: Any,
    mapping: dict[str, str],
    stats: dict[str, int],
    direction: str = "forward",
    fail_on_unmapped: bool = False,
) -> Any:
    """
    Recursively translate product names in any data structure.

    This function processes dictionaries, lists, and strings, replacing all
    occurrences of product names according to the provided mapping.

    IMPORTANT: Processes BOTH dictionary keys AND values to ensure complete
    translation. This is critical for data structures like security_history.json
    where product names appear as keys in nested dictionaries.

    Args:
        value: Value to process (can be dict, list, str, or primitive)
        mapping: Dictionary mapping source names to target names
        stats: Dictionary to track replacement counts
        direction: "forward" (real->generic) or "reverse" (generic->real)
        fail_on_unmapped: If True, fail loudly when generic products found but not in mapping

    Returns:
        Translated value

    Raises:
        ValueError: If fail_on_unmapped=True and unmapped generic products found
    """
    if isinstance(value, dict):
        # Translate both keys AND values
        translated_dict = {}
        for k, v in value.items():
            # Translate the key using word boundaries to avoid partial matches
            translated_key = k
            for source_name, target_name in sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True):
                pat = re.compile(r"\b" + re.escape(source_name) + r"\b")
                matches = pat.findall(translated_key)
                if matches:
                    stats[source_name] = stats.get(source_name, 0) + len(matches)
                    translated_key = pat.sub(target_name, translated_key)

            # Check for unmapped generic products in keys
            if fail_on_unmapped and direction == "reverse":
                _check_unmapped_generics(translated_key, mapping, "dictionary key")

            # Translate the value recursively
            translated_dict[translated_key] = translate_value(v, mapping, stats, direction, fail_on_unmapped)
        return translated_dict

    elif isinstance(value, list):
        return [translate_value(item, mapping, stats, direction, fail_on_unmapped) for item in value]

    elif isinstance(value, str):
        # Replace product names using word boundaries to avoid partial matches in titles
        translated = value
        for source_name, target_name in sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True):
            pat = re.compile(r"\b" + re.escape(source_name) + r"\b")
            matches = pat.findall(translated)
            if matches:
                stats[source_name] = stats.get(source_name, 0) + len(matches)
                translated = pat.sub(target_name, translated)

        # Check for unmapped generic products in string values
        if fail_on_unmapped and direction == "reverse":
            _check_unmapped_generics(translated, mapping, "string value")

        # Email anonymization (only for forward/genericization)
        if direction == "forward" and "@theaccessgroup.com" in translated:
            translated = _anonymize_emails(translated, stats)

        return translated
    else:
        return value


def _check_unmapped_generics(text: str, mapping: dict[str, str], context: str) -> None:
    """
    Check if text contains unmapped generic product names and fail loudly.

    Args:
        text: Text to check
        mapping: Mapping dictionary (generic -> real names)
        context: Description of where this text came from (for error message)

    Raises:
        ValueError: If unmapped generic products found
    """
    # Check for "Product X" pattern where X is A-Z (word boundaries prevent
    # false positives like "Product Sign off" matching "Product S")
    pattern = r"\bProduct [A-Z]\b"
    matches = re.findall(pattern, text)

    if matches:
        unmapped = [m for m in matches if m not in mapping]
        if unmapped:
            unique_unmapped = sorted(set(unmapped))
            raise ValueError(
                f"❌ UNMAPPED GENERIC PRODUCTS FOUND in {context}:\n"
                f"   Found: {', '.join(unique_unmapped)}\n"
                f"   These generic product names are not in the mapping file.\n"
                f"   This usually means:\n"
                f"   1. The mapping file is incomplete\n"
                f"   2. New products were added but mapping wasn't updated\n"
                f"   3. The mapping file wasn't loaded correctly\n"
                f"   Current mapping has {len(mapping)} products: {', '.join(sorted(mapping.keys()))}"
            )


def _anonymize_emails(text: str, stats: dict[str, int]) -> str:
    """
    Anonymize email addresses (replace @theaccessgroup.com with name format).

    Args:
        text: Text containing potential email addresses
        stats: Dictionary to track anonymization counts

    Returns:
        Text with emails anonymized
    """
    email_pattern = r"([a-zA-Z0-9._%+-]+)@theaccessgroup\.com"
    matches = re.findall(email_pattern, text)

    anonymized = text
    for match in matches:
        original_email = f"{match}@theaccessgroup.com"
        # Convert email to name format (jac.martin -> Jac Martin)
        name_parts = match.split(".")
        generic_name = " ".join(word.capitalize() for word in name_parts)
        anonymized = anonymized.replace(original_email, generic_name)
        stats["email_anonymized"] = stats.get("email_anonymized", 0) + 1

    return anonymized


def translate_history_file(
    file_path: Path,
    mapping: dict[str, str],
    direction: str = "forward",
    fail_on_unmapped: bool = False,
) -> dict[str, int]:
    """
    Translate product names in a single history JSON file.

    Args:
        file_path: Path to history JSON file
        mapping: Dictionary mapping source names to target names
        direction: "forward" (real->generic) or "reverse" (generic->real)
        fail_on_unmapped: If True, fail loudly when unmapped generic products found

    Returns:
        Dictionary of replacement statistics

    Raises:
        ValueError: If fail_on_unmapped=True and unmapped generic products found
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    # Load JSON
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    # Track replacements
    stats: dict[str, int] = {}

    # Translate all values
    translated_data = translate_value(data, mapping, stats, direction, fail_on_unmapped)

    # Save back
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(translated_data, f, indent=2, ensure_ascii=False)

    return stats


def load_mapping_file(file_path: Path, direction: str = "forward") -> dict[str, str]:
    """
    Load product name mapping from JSON file.

    Args:
        file_path: Path to mapping JSON file
        direction: "forward" (real->generic) or "reverse" (generic->real)

    Returns:
        Dictionary mapping source names to target names

    Raises:
        SystemExit: If mapping file is missing or invalid
    """
    if not file_path.exists():
        print(f"[ERROR] Mapping file not found: {file_path}")
        print("In CI/CD, this file should be created from GitHub Secrets")
        print(f"Locally, create it with: echo '$MAPPING_JSON' > {file_path}")
        sys.exit(1)

    try:
        with open(file_path, encoding="utf-8") as f:
            mapping = json.load(f)

        if not isinstance(mapping, dict):
            raise ValueError("Mapping file must contain a JSON object")

        # Validate structure based on direction
        if direction == "reverse":
            # Reverse mapping: keys should be "Product X", values should be non-empty strings
            for key, value in mapping.items():
                if not key.startswith("Product "):
                    # This is a warning, not an error (for keys like "Build Product A Searches")
                    print(f"[WARN] Unexpected key in mapping: {key}")
                if not isinstance(value, str) or not value:
                    raise ValueError(f"Invalid mapping value for key: {key}")

        print(f"[OK] Loaded {len(mapping)} product mappings from {file_path}")
        return mapping

    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in mapping file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Failed to load mapping file: {e}")
        sys.exit(1)
