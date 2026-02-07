# Archived Scripts

This directory contains historical versions of scripts that have been superseded by newer implementations.

## Purpose

These files are kept for **reference only**. DO NOT USE in production.

- **Version files** (`*_v2.py`, `*_v3.py`) - Intermediate versions during API evolution
- **Old implementations** (`*_old.py`) - Previous implementations before refactoring
- **Deprecated scripts** - Files scheduled for removal

## Why Archive Instead of Delete?

1. **Historical Reference**: Sometimes useful to understand why changes were made
2. **Pattern Mining**: May contain useful patterns or approaches
3. **Rollback Safety**: If new implementation has issues, can temporarily revert
4. **Documentation**: Explains evolution of the codebase

## Maintenance Policy

**DO NOT**:
- ❌ Import from archived files
- ❌ Fix bugs in archived files
- ❌ Update archived files to work with new APIs
- ❌ Add new archived files without documenting reason

**DO**:
- ✅ Document why each file was archived (in this README)
- ✅ Delete files older than 12 months with no reference value
- ✅ Extract useful patterns to production code before archiving

## Archived Files

### ArmorCode Baselines

**armorcode_baseline_v2.py**
- **Archived**: 2026-02-07
- **Reason**: Intermediate version during GraphQL API migration
- **Superseded by**: `armorcode_baseline.py` (current)
- **Notes**: Used REST API with different pagination approach

**armorcode_baseline_v3.py**
- **Archived**: 2026-02-07
- **Reason**: Experimental GraphQL implementation
- **Superseded by**: `armorcode_baseline_graphql.py` (current)
- **Notes**: Alternative schema exploration

### Report Generation

**armorcode_generate_report_old.py**
- **Archived**: 2026-02-07
- **Reason**: Monolithic report generator before template refactoring
- **Superseded by**: `dashboards/security.py`
- **Notes**: Contains HTML string building patterns (avoid in new code)

---

## Git History Note

All version history is preserved in git. Use `git log` and `git diff` to see changes over time.

```bash
# See history of current file
git log -- execution/armorcode_baseline.py

# Compare archived vs current
git diff execution/archive/armorcode_baseline_v2.py execution/armorcode_baseline.py
```

---

**Last Updated**: 2026-02-07
