#!/usr/bin/env python3
"""
One-time migration: convert ArmorCode history files from product-name keys to product-ID keys.

Processes:
  .tmp/observatory/security_history.json
  .tmp/observatory/exploitable_history.json

Each week's `product_breakdown` currently has product names (or generic names) as keys:
  {"Access Diversity": {"critical": 0, ...}}   ← real name
  {"Product G": {"critical": 0, ...}}          ← generic name (if not yet de-genericized)

After migration, keys are product IDs:
  {"12345": {"critical": 0, ...}}

Requires:
  - data/armorcode_id_map.json     (real_name → product_id, from ARMORCODE_ID_MAP secret)
  - .product_mapping.json          (generic_name → real_name, from PRODUCT_NAME_MAPPING secret)
                                   Only needed if history files contain generic names.

Usage (local):
  # 1. Create data/armorcode_id_map.json:
  python scripts/fetch_armorcode_id_map.py
  # 2. Run migration:
  python scripts/migrate_armorcode_history_to_ids.py

Usage (CI):
  Both files are written from secrets before this script runs.
"""

import json
import sys
from pathlib import Path

HISTORY_FILES = [
    Path(".tmp/observatory/security_history.json"),
    Path(".tmp/observatory/exploitable_history.json"),
]

ID_MAP_PATH = Path("data/armorcode_id_map.json")
PRODUCT_MAPPING_PATH = Path(".product_mapping.json")


def load_id_map() -> dict[str, str]:
    """Load real_name → product_id mapping."""
    if not ID_MAP_PATH.exists():
        print(f"ERROR: {ID_MAP_PATH} not found.")
        print("   Run: python scripts/fetch_armorcode_id_map.py")
        sys.exit(1)
    result: dict[str, str] = json.loads(ID_MAP_PATH.read_text(encoding="utf-8"))
    return result


def load_generic_to_real() -> dict[str, str]:
    """Load generic_name → real_name mapping (optional, for genericized files)."""
    if not PRODUCT_MAPPING_PATH.exists():
        return {}
    result: dict[str, str] = json.loads(PRODUCT_MAPPING_PATH.read_text(encoding="utf-8"))
    return result


def build_name_to_id(id_map: dict[str, str], generic_to_real: dict[str, str]) -> dict[str, str]:
    """Build composite mapping: any_name → product_id.

    Covers both real names ("Access Diversity" → "12345") and
    generic names ("Product G" → "12345") via the composed mapping.
    """
    name_to_id: dict[str, str] = {}
    # Real names directly
    for real_name, product_id in id_map.items():
        name_to_id[real_name] = product_id
    # Generic names via composition: generic → real → id
    for generic_name, real_name in generic_to_real.items():
        if real_name in id_map:
            name_to_id[generic_name] = id_map[real_name]
    return name_to_id


def migrate_file(path: Path, name_to_id: dict[str, str]) -> tuple[int, int]:
    """Migrate a single history file. Returns (weeks_migrated, keys_converted)."""
    if not path.exists():
        print(f"⚠️  Skipping {path.name} — file not found")
        return 0, 0

    data = json.loads(path.read_text(encoding="utf-8"))
    weeks = data.get("weeks", [])

    weeks_migrated = 0
    keys_converted = 0

    for week in weeks:
        breakdown = week.get("metrics", {}).get("product_breakdown", {})
        if not breakdown:
            continue

        new_breakdown: dict = {}
        week_converted = 0
        week_unchanged = 0

        for key, value in breakdown.items():
            if key in name_to_id:
                new_breakdown[name_to_id[key]] = value
                week_converted += 1
            else:
                # Already an ID, or unknown name — keep as-is
                new_breakdown[key] = value
                week_unchanged += 1

        week["metrics"]["product_breakdown"] = new_breakdown
        keys_converted += week_converted
        if week_converted > 0:
            weeks_migrated += 1

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return weeks_migrated, keys_converted


def main() -> None:
    print("ArmorCode History Migration: Product Names -> Product IDs")
    print("=" * 60)

    id_map = load_id_map()
    generic_to_real = load_generic_to_real()
    name_to_id = build_name_to_id(id_map, generic_to_real)

    print(f"Loaded {len(id_map)} products from {ID_MAP_PATH}")
    if generic_to_real:
        print(f"Loaded {len(generic_to_real)} generic->real mappings from {PRODUCT_MAPPING_PATH}")
    else:
        print(f"INFO: {PRODUCT_MAPPING_PATH} not found - assuming history files use real names")

    print()

    total_keys = 0
    for path in HISTORY_FILES:
        weeks_migrated, keys_converted = migrate_file(path, name_to_id)
        if path.exists():
            print(f"OK {path.name}: {weeks_migrated} weeks updated, {keys_converted} keys converted")
        total_keys += keys_converted

    print()
    print(f"Migration complete: {total_keys} total keys converted to product IDs")
    print()
    print("Next steps:")
    print("  git diff .tmp/observatory/  (verify changes look correct)")
    print("  git add .tmp/observatory/security_history.json .tmp/observatory/exploitable_history.json")
    print("  git commit -m 'chore: migrate ArmorCode history product_breakdown keys to product IDs'")


if __name__ == "__main__":
    main()
