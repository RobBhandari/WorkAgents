# Exploration Scripts

This directory contains experimental and one-off scripts used for:
- **API exploration** (`explore_*.py`) - Testing API endpoints, understanding responses
- **Data analysis** (`analyze_*.py`) - One-time data investigations
- **Prototyping** (`experiment_*.py`) - Proof-of-concepts and experiments
- **Diagnostics** (`diagnose_*.py`) - Debugging and troubleshooting scripts
- **Introspection** (`introspect_*.py`) - Schema and structure discovery

## Important Notes

⚠️ **These are NOT pytest tests!**

Despite some files being named `test_*.py`, these are **exploration scripts**, not unit/integration tests.

For real tests, see `tests/` directory in the project root.

## Usage

These scripts are typically run manually for investigation purposes:

```bash
# Example: Explore ArmorCode API
python execution/experiments/explore_armorcode_api.py

# Example: Analyze work type breakdown
python execution/experiments/analyze_work_type_breakdown.py
```

## Maintenance

Scripts in this directory are:
- **Not maintained** as production code
- **Not covered** by automated tests
- **Not guaranteed** to work with current APIs
- **Historical reference** only

If you find a useful pattern here, consider:
1. Extracting it to proper production code in `execution/`
2. Adding proper tests in `tests/`
3. Documenting it in `execution/CONTRIBUTING.md`

## Cleanup Policy

Scripts older than 6 months with no recent usage should be deleted or documented in this README for reference.

---

**Last Updated**: 2026-02-07
