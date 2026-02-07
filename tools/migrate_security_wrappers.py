#!/usr/bin/env python3
"""
Automated Security Wrapper Migration Tool

Migrates Python files from direct os.getenv() and requests usage
to secure wrappers (secure_config and http_client).

Usage:
    python tools/migrate_security_wrappers.py execution/ado_quality_metrics.py
    python tools/migrate_security_wrappers.py execution/ado_*.py --dry-run
    python tools/migrate_security_wrappers.py --all --dry-run

Examples:
    # Dry run on single file
    python tools/migrate_security_wrappers.py execution/file.py --dry-run

    # Migrate single file
    python tools/migrate_security_wrappers.py execution/file.py

    # Migrate all files
    python tools/migrate_security_wrappers.py --all
"""

import re
import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Dict
from dataclasses import dataclass


@dataclass
class Migration:
    """Represents a single migration change"""
    line_num: int
    old_code: str
    new_code: str
    change_type: str  # 'os.getenv', 'requests.get', 'requests.post', etc.


@dataclass
class MigrationResult:
    """Results of migrating a file"""
    file_path: Path
    original_content: str
    migrated_content: str
    migrations: List[Migration]
    needs_imports: Dict[str, List[str]]  # module -> [imports]


class SecurityWrapperMigrator:
    """Migrates code to use security wrappers"""

    # Environment variable mappings
    ENV_VAR_MAPPINGS = {
        'ADO_PAT': 'get_config().get_ado_config().pat',
        'ADO_ORG': 'get_config().get_ado_config().organization',
        'ADO_PROJECT': 'get_config().get_ado_config().project',
        'ARMORCODE_API_KEY': 'get_config().get_armorcode_config().api_key',
        'ARMORCODE_BASE_URL': 'get_config().get_armorcode_config().base_url',
        'GRAPH_CLIENT_ID': 'get_config().get_graph_config().client_id',
        'GRAPH_CLIENT_SECRET': 'get_config().get_graph_config().client_secret',
        'GRAPH_TENANT_ID': 'get_config().get_graph_config().tenant_id',
    }

    def migrate_file(self, file_path: Path, dry_run: bool = False) -> MigrationResult:
        """Migrate a single file"""
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Migrating: {file_path}")

        # Read original content
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        # Track changes
        migrations = []
        migrated_content = original_content
        needs_imports = {}

        # Step 1: Migrate os.getenv() calls
        migrated_content, env_migrations = self._migrate_os_getenv(migrated_content)
        migrations.extend(env_migrations)
        if env_migrations:
            needs_imports['secure_config'] = ['get_config']

        # Step 2: Migrate requests imports and usage
        migrated_content, req_migrations = self._migrate_requests(migrated_content)
        migrations.extend(req_migrations)
        if req_migrations:
            # Determine which http_client functions are needed
            http_funcs = set()
            if 'requests.get(' in original_content or 'requests.get (' in original_content:
                http_funcs.add('get')
            if 'requests.post(' in original_content or 'requests.post (' in original_content:
                http_funcs.add('post')
            if 'requests.put(' in original_content:
                http_funcs.add('put')
            if 'requests.delete(' in original_content:
                http_funcs.add('delete')
            if http_funcs:
                needs_imports['http_client'] = sorted(http_funcs)

        # Step 3: Add necessary imports
        if needs_imports:
            migrated_content = self._add_imports(migrated_content, needs_imports)

        # Step 4: Remove unused imports
        migrated_content = self._remove_unused_imports(migrated_content, original_content)

        return MigrationResult(
            file_path=file_path,
            original_content=original_content,
            migrated_content=migrated_content,
            migrations=migrations,
            needs_imports=needs_imports
        )

    def _migrate_os_getenv(self, content: str) -> Tuple[str, List[Migration]]:
        """Migrate os.getenv() calls to secure_config"""
        migrations = []

        # Pattern: os.getenv('VAR_NAME') or os.getenv("VAR_NAME")
        # Also handles: os.getenv('VAR_NAME', 'default')
        pattern = r'os\.getenv\([\'"]([A-Z_]+)[\'"](?:,\s*[\'"][^\'"]*[\'"])?\)'

        def replace_getenv(match):
            var_name = match.group(1)
            old_code = match.group(0)

            # Check if we have a mapping for this variable
            if var_name in self.ENV_VAR_MAPPINGS:
                new_code = self.ENV_VAR_MAPPINGS[var_name]
            else:
                # Generic fallback
                new_code = f'get_config().get("{var_name}")'

            migrations.append(Migration(
                line_num=0,  # Will be calculated later if needed
                old_code=old_code,
                new_code=new_code,
                change_type='os.getenv'
            ))

            return new_code

        migrated = re.sub(pattern, replace_getenv, content)
        return migrated, migrations

    def _migrate_requests(self, content: str) -> Tuple[str, List[Migration]]:
        """Migrate requests library to http_client"""
        migrations = []

        # Replace requests.get() -> get()
        # Replace requests.post() -> post()
        # etc.

        replacements = {
            'requests.get(': 'get(',
            'requests.post(': 'post(',
            'requests.put(': 'put(',
            'requests.delete(': 'delete(',
        }

        migrated = content
        for old, new in replacements.items():
            if old in migrated:
                count = migrated.count(old)
                migrated = migrated.replace(old, new)
                if count > 0:
                    migrations.append(Migration(
                        line_num=0,
                        old_code=old,
                        new_code=new,
                        change_type='requests'
                    ))

        return migrated, migrations

    def _add_imports(self, content: str, needs_imports: Dict[str, List[str]]) -> str:
        """Add necessary imports at the top of the file"""
        lines = content.split('\n')

        # Find insertion point (after docstring, before first import)
        insert_index = 0
        in_docstring = False
        docstring_char = None

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Handle docstrings
            if not in_docstring:
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    docstring_char = stripped[:3]
                    if stripped.count(docstring_char) == 1:  # Opening only
                        in_docstring = True
                    elif stripped.count(docstring_char) >= 2:  # Complete docstring on one line
                        insert_index = i + 1
                    continue
            else:
                if docstring_char in line:
                    in_docstring = False
                    insert_index = i + 1
                continue

            # Skip comments and blank lines at the top
            if stripped.startswith('#') or not stripped:
                insert_index = i + 1
                continue

            # Found first non-docstring, non-comment line
            if stripped.startswith('import ') or stripped.startswith('from '):
                insert_index = i
                break
            else:
                # No imports yet, insert before first statement
                insert_index = i
                break

        # Build import statements
        import_lines = []

        if 'secure_config' in needs_imports:
            import_lines.append('from execution.core import get_config')

        if 'http_client' in needs_imports:
            funcs = ', '.join(needs_imports['http_client'])
            import_lines.append(f'from execution.core import {funcs}')

        # Check if imports already exist
        existing_imports = '\n'.join(lines)
        new_import_lines = []
        for imp in import_lines:
            if imp not in existing_imports:
                new_import_lines.append(imp)

        if new_import_lines:
            # Insert imports
            lines.insert(insert_index, '\n'.join(new_import_lines))

        return '\n'.join(lines)

    def _remove_unused_imports(self, migrated: str, original: str) -> str:
        """Remove import statements that are no longer needed"""
        lines = migrated.split('\n')
        new_lines = []

        for line in lines:
            stripped = line.strip()

            # Check if this is an import we should remove
            should_remove = False

            # Remove 'import requests' if no longer used
            if stripped == 'import requests':
                if 'requests.' not in migrated or migrated.count('requests.') == migrated.count('# import requests'):
                    should_remove = True
                    print(f"  - Removing unused: {stripped}")

            # Remove 'import os' if only used for getenv
            if stripped == 'import os':
                # Check if os is used for anything other than getenv
                os_usage = re.findall(r'\bos\.\w+', migrated)
                if all('os.getenv' in usage or 'os.path' in usage or 'os.makedirs' in usage for usage in os_usage):
                    # Only used for common patterns, might still be needed
                    pass

            if not should_remove:
                new_lines.append(line)

        return '\n'.join(new_lines)

    def save_migration(self, result: MigrationResult, dry_run: bool = False):
        """Save migrated file and create backup"""
        if dry_run:
            print(f"\n[DRY RUN] Would save to: {result.file_path}")
            return

        # Create backup
        backup_path = result.file_path.with_suffix('.py.backup')
        if not backup_path.exists():
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(result.original_content)
            print(f"  [OK] Backup created: {backup_path}")

        # Save migrated file
        with open(result.file_path, 'w', encoding='utf-8') as f:
            f.write(result.migrated_content)
        print(f"  [OK] Migrated: {result.file_path}")

    def print_summary(self, result: MigrationResult):
        """Print migration summary"""
        if not result.migrations:
            print("  -> No changes needed")
            return

        print(f"  -> {len(result.migrations)} changes:")

        # Group by change type
        by_type = {}
        for m in result.migrations:
            by_type.setdefault(m.change_type, []).append(m)

        for change_type, changes in by_type.items():
            print(f"    - {len(changes)}x {change_type}")

        if result.needs_imports:
            print(f"  -> Added imports:")
            for module, funcs in result.needs_imports.items():
                print(f"    - from execution.core import {', '.join(funcs)}")


def find_files_to_migrate(pattern: str = None) -> List[Path]:
    """Find Python files that need migration"""
    execution_dir = Path('execution')

    if pattern:
        files = list(execution_dir.glob(pattern))
    else:
        files = list(execution_dir.glob('*.py'))

    # Exclude certain directories
    exclude_dirs = ['archive', 'experiments', '__pycache__']
    files = [f for f in files if not any(excl in str(f) for excl in exclude_dirs)]

    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description='Migrate code to use security wrappers')
    parser.add_argument('files', nargs='*', help='Files to migrate (or patterns like ado_*.py)')
    parser.add_argument('--all', action='store_true', help='Migrate all files in execution/')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without modifying files')
    parser.add_argument('--collectors', action='store_true', help='Migrate all collector files')

    args = parser.parse_args()

    # Determine files to migrate
    if args.all:
        files = find_files_to_migrate()
    elif args.collectors:
        files = find_files_to_migrate('ado_*.py') + find_files_to_migrate('armorcode_*.py')
    elif args.files:
        files = []
        for pattern in args.files:
            if '*' in pattern:
                files.extend(find_files_to_migrate(pattern))
            else:
                files.append(Path(pattern))
    else:
        parser.print_help()
        return 1

    if not files:
        print("No files found to migrate")
        return 1

    print(f"{'='*70}")
    print(f"Security Wrapper Migration Tool")
    print(f"{'='*70}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE MIGRATION'}")
    print(f"Files to migrate: {len(files)}")
    print()

    # Migrate each file
    migrator = SecurityWrapperMigrator()
    results = []

    for file_path in files:
        if not file_path.exists():
            print(f"\n[!] Skipping (not found): {file_path}")
            continue

        try:
            result = migrator.migrate_file(file_path, dry_run=args.dry_run)
            results.append(result)
            migrator.print_summary(result)

            if not args.dry_run and result.migrations:
                migrator.save_migration(result, dry_run=args.dry_run)

        except Exception as e:
            print(f"\n[X] Error migrating {file_path}: {e}")
            import traceback
            traceback.print_exc()

    # Print final summary
    print(f"\n{'='*70}")
    print(f"Migration Summary")
    print(f"{'='*70}")

    total_changes = sum(len(r.migrations) for r in results)
    files_changed = sum(1 for r in results if r.migrations)

    print(f"Files processed: {len(results)}")
    print(f"Files changed: {files_changed}")
    print(f"Total changes: {total_changes}")

    if args.dry_run:
        print(f"\n[DRY RUN] No files were modified")
        print(f"Run without --dry-run to apply changes")
    else:
        print(f"\n[OK] Migration complete!")
        print(f"Backups created with .py.backup extension")

    return 0


if __name__ == '__main__':
    sys.exit(main())
