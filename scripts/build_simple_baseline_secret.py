#!/usr/bin/env python3
"""
Build simplified BASELINE_ADO_PROJECTS GitHub Secret.

Only includes what's actually needed:
- Project names (for discovery)
- Optional: area_path_filter (for projects with special filtering)
- Optional: ado_project_name (when ADO name differs from display name)

NO baseline counts, targets, dates, or other unused metadata.
"""

import json
import sys
from pathlib import Path


def build_simple_secret() -> dict:
    """Build simplified secret with just project names and filters."""

    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    projects = [
        {
            "name": "Access Legal Case Management",
            "area_path_filter": "EXCLUDE:Access Legal Case Management\\OneOffice and Financial Director",
        },
        {
            "name": "One Office",
            "ado_project_name": "Access Legal Case Management",  # Shared project
            "area_path_filter": "INCLUDE:Access Legal Case Management\\OneOffice and Financial Director",
        },
        {"name": "Access LawFusion"},
        {"name": "Learning Content Legal"},
        {"name": "Access LegalBricks"},
        {"name": "Access Legal Compliance"},
        {"name": "Access Legal InCase"},
        {"name": "Access Legal Proclaim"},
    ]

    secret = {"projects": projects}

    print("Building Simplified BASELINE_ADO_PROJECTS Secret\n")
    print("=" * 60)
    for p in projects:
        print(f"✓ {p['name']}")
        if "area_path_filter" in p:
            print(f"  ├─ Filter: {p['area_path_filter']}")
        if "ado_project_name" in p:
            print(f"  └─ ADO Project: {p['ado_project_name']}")

    print(f"\n{'='*60}")
    print(f"✅ Built secret with {len(projects)} projects")
    print(f"{'='*60}\n")

    # Save
    output_json = json.dumps(secret, ensure_ascii=False, separators=(",", ":"))
    output_file = Path(".tmp/baseline_secret_simple.json")
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output_json)

    print(f"📝 Saved to: {output_file}")
    print(f"📏 Size: {len(output_json):,} characters\n")

    return secret


if __name__ == "__main__":
    build_simple_secret()
