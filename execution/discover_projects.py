#!/usr/bin/env python3
"""
Project Discovery Utility for Observatory

Discovers ADO projects from existing baseline files.
Does not modify any existing files - read-only operation.
"""

import glob
import json
import os
from datetime import datetime
from typing import Any


def discover_projects(baseline_dir: str = "data") -> list[dict]:
    """
    Discover projects from baseline files.

    Args:
        baseline_dir: Directory containing baseline_*.json files (default: data)

    Returns:
        List of project dictionaries with metadata
    """
    projects: list[dict] = []
    baseline_pattern = os.path.join(baseline_dir, "baseline_*.json")
    baseline_files = glob.glob(baseline_pattern)

    if not baseline_files:
        print(f"[WARNING]  No baseline files found matching: {baseline_pattern}")
        return projects

    print(f"[Discovery] Found {len(baseline_files)} baseline files")

    for baseline_file in sorted(baseline_files):
        try:
            with open(baseline_file, encoding="utf-8") as f:
                baseline_data = json.load(f)

            # Extract project key from filename
            # baseline_Access_Legal_Case_Management.json -> Access_Legal_Case_Management
            filename = os.path.basename(baseline_file)
            project_key = filename.replace("baseline_", "").replace(".json", "")

            # Build project metadata
            project = {
                "project_key": project_key,
                "project_name": baseline_data.get("project", project_key.replace("_", " ")),
                "organization": baseline_data.get("organization", ""),
                "baseline_file": baseline_file,
                "baseline_date": baseline_data.get("baseline_date"),
                "baseline_count": baseline_data.get("open_count", 0),
                "discovered_at": datetime.now().isoformat(),
            }

            projects.append(project)
            print(
                f"  ✓ {project['project_name']}: {project['baseline_count']} bugs (baseline: {project['baseline_date']})"
            )

        except Exception as e:
            print(f"  ✗ Error reading {baseline_file}: {e}")
            continue

    return projects


def save_discovery_results(projects: list[dict], output_file: str = ".tmp/observatory/ado_structure.json"):
    """
    Save discovered projects to JSON file.

    Args:
        projects: List of project dictionaries
        output_file: Path to output JSON file
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    discovery_data = {"discovered_at": datetime.now().isoformat(), "project_count": len(projects), "projects": projects}

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(discovery_data, f, indent=2, ensure_ascii=False)

    print(f"\n[SAVED] Saved discovery results to: {output_file}")
    return discovery_data


def load_discovered_projects(discovery_file: str = ".tmp/observatory/ado_structure.json") -> list[dict]:
    """
    Load previously discovered projects.

    Args:
        discovery_file: Path to discovery JSON file

    Returns:
        List of project dictionaries
    """
    if not os.path.exists(discovery_file):
        return []

    with open(discovery_file, encoding="utf-8") as f:
        discovery_data = json.load(f)

    projects: list[dict[Any, Any]] = discovery_data.get("projects", [])
    return projects


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    import sys

    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    print("Director Observatory - Project Discovery\n")
    print("=" * 60)

    # Discover projects from baseline files
    projects = discover_projects()

    if not projects:
        print("\nWARNING: No projects discovered. Make sure baseline files exist in .tmp/")
        exit(1)

    # Save results
    discovery_data = save_discovery_results(projects)

    # Summary
    print("\n" + "=" * 60)
    print("Discovery Summary:")
    print(f"   Projects found: {len(projects)}")
    print(f"   Organizations: {len({p['organization'] for p in projects})}")
    print(f"   Total baseline bugs: {sum(p['baseline_count'] for p in projects)}")

    print("\nProject discovery complete!")
    print("\nNext step: Run flow metrics collector to gather engineering metrics.")
