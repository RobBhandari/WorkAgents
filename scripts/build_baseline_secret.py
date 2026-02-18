#!/usr/bin/env python3
"""
Build BASELINE_ADO_PROJECTS GitHub Secret from local baseline files.

This script reads all baseline_*.json files from .tmp/ and generates
the JSON structure needed for the BASELINE_ADO_PROJECTS GitHub Secret.
"""

import json
import sys
from pathlib import Path


def build_baseline_secret(baseline_dir: Path = Path(".tmp")) -> dict:
    """
    Build BASELINE_ADO_PROJECTS secret structure from local baseline files.

    Args:
        baseline_dir: Directory containing baseline_*.json files

    Returns:
        Dictionary in the format expected by GitHub Secret
    """
    # Exclude the output file itself
    baseline_files = sorted([f for f in baseline_dir.glob("baseline_*.json") if f.name != "baseline_secret.json"])

    if not baseline_files:
        print(f"❌ No baseline files found in {baseline_dir}")
        sys.exit(1)

    projects = []

    for baseline_path in baseline_files:
        # Read baseline data
        with open(baseline_path, encoding="utf-8") as f:
            baseline_data = json.load(f)

        # Extract filename (e.g., "baseline_Project_A.json")
        baseline_filename = baseline_path.name

        # Strip out bug list for security - only keep metadata
        # Note: weeks_to_target and required_weekly_burn are calculated at runtime
        minimal_baseline = {
            "baseline_date": baseline_data.get("baseline_date"),
            "baseline_week": baseline_data.get("baseline_week", 0),
            "open_count": baseline_data.get("open_count", 0),
            "target_count": baseline_data.get("target_count", 0),
            "target_date": baseline_data.get("target_date"),
            "target_percentage": baseline_data.get("target_percentage", 0.3),
            "immutable": baseline_data.get("immutable", True),
            "created_at": baseline_data.get("created_at"),
            "project": baseline_data.get("project"),
            "organization": baseline_data.get("organization"),
            "note": baseline_data.get("note", ""),
            "bugs": [],  # Empty - query bugs live from ADO API
        }

        # Add optional fields if present
        if "area_path_filter" in baseline_data:
            minimal_baseline["area_path_filter"] = baseline_data["area_path_filter"]
        if "ado_project_name" in baseline_data:
            minimal_baseline["ado_project_name"] = baseline_data["ado_project_name"]

        # Build project entry
        project_entry = {"baseline_file": baseline_filename, "baseline_data": minimal_baseline}

        projects.append(project_entry)

        print(f"✓ Added: {baseline_filename} (metadata only, bugs stripped)")

    secret_structure = {"projects": projects}

    return secret_structure


def main():
    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    print("Building BASELINE_ADO_PROJECTS GitHub Secret\n")
    print("=" * 60)

    # Build secret structure
    secret_data = build_baseline_secret()

    print(f"\n{'='*60}")
    print(f"✅ Built secret with {len(secret_data['projects'])} projects")
    print(f"{'='*60}\n")

    # Output JSON (compact for GitHub Secrets)
    output_json = json.dumps(secret_data, ensure_ascii=False, separators=(",", ":"))

    # Save to file
    output_file = Path(".tmp/baseline_secret.json")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output_json)

    print(f"📝 Saved to: {output_file}")
    print(f"📏 Size: {len(output_json):,} characters\n")

    print("Next steps:")
    print("  1. Copy the JSON from .tmp/baseline_secret.json")
    print("  2. Go to: https://github.com/RobBhandari/WorkAgents/settings/secrets/actions")
    print("  3. Edit BASELINE_ADO_PROJECTS secret")
    print("  4. Paste the JSON content")
    print("  5. Save")
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
