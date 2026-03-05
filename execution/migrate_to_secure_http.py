"""
Automated Migration Script: Migrate to Secure HTTP Client

Migrates files from using requests.get/post/etc to using the secure http_client wrapper.

This script:
1. Finds all files using requests.get(), requests.post(), etc.
2. Adds import for secure http_client functions
3. Replaces requests.METHOD( with METHOD(
4. Preserves all other code unchanged

Usage:
    python execution/migrate_to_secure_http.py --dry-run  # Preview changes
    python execution/migrate_to_secure_http.py            # Apply changes
"""

import argparse
import re
import sys
from pathlib import Path


def _get_skip_reason(file_path: Path, content: str) -> str | None:
    """Return a skip reason string if the file should not be migrated, else None."""
    if file_path.name == "http_client.py":
        return "SKIP (http_client.py itself)"
    if file_path.name == "migrate_to_secure_http.py":
        return "SKIP (migration script)"
    if not re.search(r"requests\.(get|post|put|delete|patch)\(", content):
        return "SKIP (no requests calls)"
    if "from http_client import" in content or "from .http_client import" in content:
        return "SKIP (already migrated)"
    return None


def _inject_import(content: str) -> tuple[str, bool]:
    """Insert the http_client import after the last existing import line. Returns (new_content, modified)."""
    if "import requests" not in content:
        return content, False
    import_pattern = re.compile(r"^(from .+ import .+|import .+)$", re.MULTILINE)
    imports = list(import_pattern.finditer(content))
    if not imports:
        return content, False
    last_import_end = imports[-1].end()
    new_import = "\nfrom http_client import get, post, put, delete, patch"
    return content[:last_import_end] + new_import + content[last_import_end:], True


def migrate_file(file_path: Path, dry_run: bool = False) -> tuple[bool, str]:
    """
    Migrate a single file to use secure HTTP client.

    Args:
        file_path: Path to file to migrate
        dry_run: If True, only show what would be changed

    Returns:
        tuple: (was_modified, status_message)
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        skip_reason = _get_skip_reason(file_path, content)
        if skip_reason:
            return False, skip_reason

        original_content = content
        modified = False

        content, import_added = _inject_import(content)
        if import_added:
            modified = True

        # Replace requests.METHOD( with METHOD(
        replacements = [
            (r"\brequests\.get\(", "get("),
            (r"\brequests\.post\(", "post("),
            (r"\brequests\.put\(", "put("),
            (r"\brequests\.delete\(", "delete("),
            (r"\brequests\.patch\(", "patch("),
        ]
        for pattern, replacement in replacements:
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                modified = True

        if modified and content != original_content:
            if not dry_run:
                file_path.write_text(content, encoding="utf-8")
            return True, "MIGRATED"
        return False, "SKIP (no changes needed)"

    except Exception as e:
        return False, f"ERROR: {e}"


def main():
    """Main migration function."""
    parser = argparse.ArgumentParser(description="Migrate files to use secure HTTP client")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without modifying files")
    args = parser.parse_args()

    execution_dir = Path(__file__).parent
    py_files = list(execution_dir.glob("*.py"))

    print("Secure HTTP Client Migration")
    print("=" * 60)
    if args.dry_run:
        print("DRY RUN MODE - No files will be modified")
        print("=" * 60)

    migrated_count = 0
    skipped_count = 0
    error_count = 0

    for py_file in sorted(py_files):
        was_modified, status = migrate_file(py_file, dry_run=args.dry_run)

        if was_modified:
            print(f"[{status}] {py_file.name}")
            migrated_count += 1
        elif status.startswith("ERROR"):
            print(f"[{status}] {py_file.name}")
            error_count += 1
        else:
            # Only show skipped files in verbose mode
            if args.dry_run:
                print(f"[{status}] {py_file.name}")
            skipped_count += 1

    print("=" * 60)
    print("Summary:")
    print(f"  Migrated: {migrated_count} files")
    print(f"  Skipped:  {skipped_count} files")
    print(f"  Errors:   {error_count} files")

    if args.dry_run:
        print("\nRun without --dry-run to apply changes")
    else:
        print("\nMigration complete!")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
