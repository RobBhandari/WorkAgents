#!/usr/bin/env python3
"""
KLOC Calculator for Azure DevOps Git Repositories

Calculates Kilo Lines of Code (KLOC) for each project by analyzing Git repositories.
Uses Azure DevOps Git API to fetch file contents and count lines of code.

Key Features:
- Counts only source code files (excludes config, docs, etc.)
- Filters out comments and blank lines where possible
- Caches results to avoid repeated API calls
- Integrates with existing project structure

Output: KLOC metrics per project stored in .tmp/observatory/kloc_data.json
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from execution.core import get_config

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from azure.devops.connection import Connection
from dotenv import load_dotenv
from msrest.authentication import BasicAuthentication

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

# Load environment variables
load_dotenv()

# Source code file extensions to analyze
SOURCE_CODE_EXTENSIONS = {
    # Programming languages
    ".py",
    ".java",
    ".cs",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".cc",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".scala",
    ".kt",
    ".swift",
    ".m",
    ".mm",
    ".sql",
    # Web
    ".html",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".vue",
    ".svelte",
    # Scripts
    ".sh",
    ".bash",
    ".ps1",
    ".bat",
    ".cmd",
}

# Files/directories to exclude from KLOC calculation
EXCLUDE_PATTERNS = {
    # Dependencies
    "node_modules",
    "vendor",
    "packages",
    ".venv",
    "venv",
    "env",
    # Build outputs
    "bin",
    "obj",
    "build",
    "dist",
    "out",
    "target",
    # IDE
    ".vs",
    ".vscode",
    ".idea",
    ".settings",
    # Version control
    ".git",
    ".svn",
    ".hg",
    # Test data
    "__pycache__",
    ".pytest_cache",
    "coverage",
}

# Non-code file extensions to skip
EXCLUDE_EXTENSIONS = {
    # Config
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    # Docs
    ".md",
    ".txt",
    ".rst",
    ".adoc",
    # Assets
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".webp",
    ".mp4",
    ".mp3",
    ".wav",
    ".mov",
    ".avi",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    # Compiled/Binary
    ".dll",
    ".exe",
    ".so",
    ".dylib",
    ".class",
    ".pyc",
    ".pyo",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    # Locks
    ".lock",
}


def get_ado_connection():
    """Create connection to Azure DevOps"""
    organization_url = get_config().get("ADO_ORGANIZATION_URL")
    pat = get_config().get_ado_config().pat

    if not organization_url or not pat:
        raise ValueError("ADO_ORGANIZATION_URL and ADO_PAT must be set in .env file")

    credentials = BasicAuthentication("", pat)
    connection = Connection(base_url=organization_url, creds=credentials)
    return connection


def should_analyze_file(file_path: str) -> bool:
    """
    Determine if a file should be included in KLOC calculation.

    Returns True if the file is source code that should be counted.
    """
    # Check if path contains excluded directories
    path_parts = Path(file_path).parts
    for part in path_parts:
        if part.lower() in EXCLUDE_PATTERNS:
            return False

    # Get file extension
    ext = Path(file_path).suffix.lower()

    # Skip if in exclude extensions
    if ext in EXCLUDE_EXTENSIONS:
        return False

    # Include if in source code extensions
    if ext in SOURCE_CODE_EXTENSIONS:
        return True

    return False


def count_lines_in_content(content: str, file_path: str) -> dict[str, int]:
    """
    Count lines in file content.

    Returns dict with:
    - total_lines: All lines including blank and comments
    - code_lines: Lines that are not blank or comments (best effort)
    - blank_lines: Empty or whitespace-only lines
    - comment_lines: Lines that appear to be comments (simple heuristic)
    """
    lines = content.split("\n")
    total_lines = len(lines)
    blank_lines = 0
    comment_lines = 0

    ext = Path(file_path).suffix.lower()

    # Comment patterns by language
    single_line_comment_chars = {
        ".py": "#",
        ".rb": "#",
        ".sh": "#",
        ".bash": "#",
        ".ps1": "#",
        ".yaml": "#",
        ".yml": "#",
        ".js": "//",
        ".ts": "//",
        ".jsx": "//",
        ".tsx": "//",
        ".java": "//",
        ".cs": "//",
        ".cpp": "//",
        ".c": "//",
        ".cc": "//",
        ".h": "//",
        ".hpp": "//",
        ".go": "//",
        ".rs": "//",
        ".php": "//",
        ".swift": "//",
        ".kt": "//",
        ".scala": "//",
        ".sql": "--",
        ".css": None,  # No single-line comments
        ".html": None,  # No single-line comments
    }

    comment_char = single_line_comment_chars.get(ext, "//")

    for line in lines:
        stripped = line.strip()

        # Count blank lines
        if not stripped:
            blank_lines += 1
            continue

        # Count comment lines (simple heuristic)
        if comment_char and stripped.startswith(comment_char):
            comment_lines += 1
            continue

        # Check for block comment starts (basic detection)
        if (
            stripped.startswith("/*")
            or stripped.startswith("<!--")
            or stripped.startswith('"""')
            or stripped.startswith("'''")
        ):
            comment_lines += 1
            continue

    code_lines = total_lines - blank_lines - comment_lines

    return {
        "total_lines": total_lines,
        "code_lines": max(0, code_lines),  # Ensure non-negative
        "blank_lines": blank_lines,
        "comment_lines": comment_lines,
    }


def get_repository_kloc(git_client, project_name: str, repo_name: str, repo_id: str) -> dict:
    """
    Calculate KLOC for a single repository.

    Returns dict with:
    - repo_name: Repository name
    - repo_id: Repository ID
    - total_kloc: Total lines / 1000
    - code_kloc: Code lines (excluding comments/blanks) / 1000
    - files_analyzed: Number of source files counted
    - file_breakdown: Dict of extension -> line counts
    """
    print(f"  Analyzing repository: {repo_name}")

    try:
        # Get repository items (files) - try common branch names
        # Try common default branch names in order of likelihood
        items = None
        branches_to_try = ["main", "master", "develop", "dev", "development", "trunk", "release"]

        for branch in branches_to_try:
            try:
                items = git_client.get_items(
                    repository_id=repo_id,
                    project=project_name,
                    scope_path="/",
                    recursion_level="Full",
                    version_descriptor={"version": branch, "version_type": "branch"},
                )
                print(f"    Using branch: {branch}")
                break
            except Exception:
                continue

        if items is None:
            print(f"    ⚠ Could not access any branch (tried: {', '.join(branches_to_try)})")
            return None

        total_lines = 0
        total_code_lines = 0
        total_blank_lines = 0
        total_comment_lines = 0
        files_analyzed = 0
        extension_breakdown = defaultdict(lambda: {"files": 0, "lines": 0, "code_lines": 0})

        # Analyze each file
        for item in items.value:
            # Skip directories
            if item.git_object_type != "blob":
                continue

            file_path = item.path

            # Check if we should analyze this file
            if not should_analyze_file(file_path):
                continue

            try:
                # Get file content
                file_content = git_client.get_item_content(
                    repository_id=repo_id,
                    project=project_name,
                    path=file_path,
                    version_descriptor={"version": items.value[0].commit_id, "version_type": "commit"},
                )

                # Decode content
                if isinstance(file_content, bytes):
                    try:
                        content = file_content.decode("utf-8")
                    except UnicodeDecodeError:
                        # Skip binary files
                        continue
                else:
                    content = file_content

                # Count lines
                line_counts = count_lines_in_content(content, file_path)

                total_lines += line_counts["total_lines"]
                total_code_lines += line_counts["code_lines"]
                total_blank_lines += line_counts["blank_lines"]
                total_comment_lines += line_counts["comment_lines"]
                files_analyzed += 1

                # Track by extension
                ext = Path(file_path).suffix.lower()
                extension_breakdown[ext]["files"] += 1
                extension_breakdown[ext]["lines"] += line_counts["total_lines"]
                extension_breakdown[ext]["code_lines"] += line_counts["code_lines"]

            except Exception:
                # Skip files we can't read
                continue

        print(f"    ✓ Analyzed {files_analyzed} files, {total_lines:,} total lines")

        return {
            "repo_name": repo_name,
            "repo_id": repo_id,
            "total_lines": total_lines,
            "total_kloc": round(total_lines / 1000, 2),
            "code_lines": total_code_lines,
            "code_kloc": round(total_code_lines / 1000, 2),
            "blank_lines": total_blank_lines,
            "comment_lines": total_comment_lines,
            "files_analyzed": files_analyzed,
            "extension_breakdown": dict(extension_breakdown),
            "analyzed_at": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"    ✗ Error analyzing repository: {e}")
        return None


def calculate_project_kloc(connection, project_config: dict) -> dict | None:
    """
    Calculate KLOC for all repositories in a project.

    Returns dict with aggregated KLOC metrics for the project.
    """
    project_name = project_config.get("ado_project_name") or project_config["project_name"]
    project_key = project_config["project_key"]

    print(f"\n[{project_key}] Calculating KLOC for project: {project_name}")

    try:
        git_client = connection.clients.get_git_client()

        # Get all repositories for this project
        repositories = git_client.get_repositories(project=project_name)

        if not repositories:
            print("  ⚠ No repositories found")
            return None

        print(f"  Found {len(repositories)} repositories")

        # Quick diagnostic: check if repos have any branches
        repos_with_branches = 0
        for repo in repositories:
            try:
                branches = git_client.get_branches(repository_id=repo.id, project=project_name)
                if branches:
                    repos_with_branches += 1
            except:
                pass

        if repos_with_branches == 0:
            print(f"  ⚠ Warning: None of the {len(repositories)} repositories have accessible branches")
            print("  This could mean repositories are empty or use TFVC instead of Git")

        # Calculate KLOC for each repository
        repo_metrics = []
        total_kloc = 0
        total_code_kloc = 0
        total_files = 0

        for repo in repositories:
            repo_kloc = get_repository_kloc(git_client, project_name, repo.name, repo.id)

            if repo_kloc:
                repo_metrics.append(repo_kloc)
                total_kloc += repo_kloc["total_kloc"]
                total_code_kloc += repo_kloc["code_kloc"]
                total_files += repo_kloc["files_analyzed"]

        if not repo_metrics:
            print("  ⚠ No KLOC data collected")
            return None

        result = {
            "project_key": project_key,
            "project_name": project_config["project_name"],
            "ado_project_name": project_name,
            "total_kloc": round(total_kloc, 2),
            "code_kloc": round(total_code_kloc, 2),
            "files_analyzed": total_files,
            "repository_count": len(repo_metrics),
            "repositories": repo_metrics,
            "collected_at": datetime.now().isoformat(),
        }

        print(f"  ✓ Total KLOC: {result['total_kloc']:.2f} ({result['code_kloc']:.2f} code)")

        return result

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None


def main():
    """Main execution function"""
    print("=" * 80)
    print("KLOC Calculator for Azure DevOps Projects")
    print("=" * 80)

    # Load project structure
    structure_file = ".tmp/observatory/ado_structure.json"
    if not os.path.exists(structure_file):
        print(f"\n[ERROR] Project structure file not found: {structure_file}")
        print("Run: python execution/discover_projects.py")
        return

    with open(structure_file, encoding="utf-8") as f:
        discovery_data = json.load(f)

    projects = discovery_data.get("projects", [])

    print(f"\nFound {len(projects)} projects to analyze")

    # Connect to Azure DevOps
    print("\nConnecting to Azure DevOps...")
    try:
        connection = get_ado_connection()
        print("✓ Connected successfully")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return

    # Calculate KLOC for each project
    kloc_results = []

    for project in projects:
        result = calculate_project_kloc(connection, project)
        if result:
            kloc_results.append(result)

    # Save results
    output_dir = Path(".tmp/observatory")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "kloc_data.json"

    output_data = {"calculated_at": datetime.now().isoformat(), "projects": kloc_results}

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    # Print summary
    print("\n" + "=" * 80)
    print("KLOC CALCULATION SUMMARY")
    print("=" * 80)
    print(f"\nProjects analyzed: {len(kloc_results)}/{len(projects)}")
    print("\nTotal Portfolio KLOC:")

    total_kloc = sum(p["total_kloc"] for p in kloc_results)
    total_code_kloc = sum(p["code_kloc"] for p in kloc_results)
    total_files = sum(p["files_analyzed"] for p in kloc_results)

    print(f"  Total Lines: {total_kloc:.2f} KLOC")
    print(f"  Code Lines:  {total_code_kloc:.2f} KLOC (excluding comments/blanks)")
    print(f"  Files:       {total_files:,}")

    print(f"\nResults saved to: {output_file}")

    # Print per-project summary
    print("\nPer-Project KLOC:")
    print(f"{'Project':<40} {'KLOC':>10} {'Code KLOC':>12} {'Files':>8}")
    print("-" * 75)

    for project in sorted(kloc_results, key=lambda x: x["total_kloc"], reverse=True):
        print(
            f"{project['project_name']:<40} {project['total_kloc']:>10.2f} {project['code_kloc']:>12.2f} {project['files_analyzed']:>8,}"
        )

    print("\n✓ KLOC calculation complete!")


if __name__ == "__main__":
    main()
