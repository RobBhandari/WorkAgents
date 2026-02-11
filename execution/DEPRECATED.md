# Deprecated Scripts

The following scripts are **deprecated** and no longer maintained. They rely on the Azure DevOps SDK (`azure-devops==7.1.0b4`), which has been removed from the project in favor of the REST API v7.1.

---

## 🗑️ Removed (Dead Code - 2026-02-11)

The following SDK-dependent files were **NOT used in production** and have been removed:

### Risk Query Modules (Dead Code - Replaced by ado_risk_metrics.py)
- ~~`collectors/risk_queries/missing_tests.py`~~ ❌ REMOVED
- ~~`collectors/risk_queries/stale_bugs.py`~~ ❌ REMOVED
- ~~`collectors/risk_queries/high_priority_bugs.py`~~ ❌ REMOVED
- ~~`collectors/risk_queries/blocked_bugs.py`~~ ❌ REMOVED
- ~~`collectors/risk_collector.py`~~ ❌ REMOVED (orchestrator for above modules)

**Reason**: Dead code left from incomplete migration. Production uses `collectors/ado_risk_metrics.py` (REST API v7.1) instead.

### KLOC Calculator (Incomplete Feature - Never Deployed)
- ~~`utils/calculate_kloc.py`~~ ❌ REMOVED
- ~~`KLOC_INTEGRATION_README.md`~~ ❌ REMOVED
- ~~`test_kloc_integration.bat`~~ ❌ REMOVED

**Reason**: Incomplete feature that was documented but never integrated into production GitHub Actions workflow or dashboards.

### Test Files
- ~~`tests/collectors/test_risk_collector.py`~~ ❌ REMOVED
- ~~`tests/collectors/risk_queries/`~~ ❌ REMOVED (directory)

---

## 📋 Remaining Deprecated Scripts

### DOE Initiative Tracking Scripts (Status Uncertain)
- **`create_ado_dec1_baseline.py`** - December 1st baseline creation script
- **`ado_baseline.py`** - Week 0 baseline utilities (Jan 1, 2026)
- **`ado_doe_tracker.py`** - Weekly DOE progress tracking (30% bug reduction target)
- **`ado_query_bugs.py`** - Basic bug query utility

**Status**: Uncertain if DOE (Department of Excellence) initiative is still active
**Usage**: Referenced by `send_doe_report.py`, `ado_bugs_to_html.py`, `run_weekly_doe_report.bat`
**Last Activity**: January-February 2026
**Action**: Keep as-is until initiative status confirmed

**To Use These Scripts** (Requires Manual SDK Installation):
```bash
# Install SDK manually (not in requirements.txt)
pip install azure-devops==7.1.0b4

# Run DOE tracking script
python execution/ado_doe_tracker.py
```

### Utility Functions (Partially Deprecated)
- **`utils/ado_batch_utils.py`** - Contains deprecated `batch_fetch_work_items()` (SDK version)
  - **Status**: File is NOT deprecated, only one function is deprecated
  - ✅ **Use instead**: `batch_fetch_work_items_rest()` in the same file (REST API version)
  - **Note**: All production collectors use the REST version

---

## ✅ Production Collectors (REST API v7.1)

These collectors are **actively maintained** and run in production (GitHub Actions):
- ✅ `collectors/ado_quality_metrics.py`
- ✅ `collectors/ado_flow_metrics.py`
- ✅ `collectors/ado_deployment_metrics.py`
- ✅ `collectors/ado_ownership_metrics.py`
- ✅ `collectors/ado_collaboration_metrics.py`
- ✅ `collectors/ado_risk_metrics.py` ← **This replaced risk_collector.py**
- ✅ `armorcode_enhanced_metrics.py` (Security metrics)

**Workflow**: `.github/workflows/refresh-dashboards.yml`

---

## Migration Notes

**Date**: 2026-02-10
**Reason**: Removed Azure DevOps SDK (`azure-devops==7.1.0b4`) due to:
- Security vulnerability (H-1 severity)
- Beta/unmaintained package
- 10+ transitive dependencies
- Replaced with direct REST API v7.1 calls (3-50x faster with async/await)

**Impact**: Legacy scripts will fail with `ModuleNotFoundError: No module named 'azure.devops'` if executed locally.

---

## Cleanup Summary (2026-02-11)

**Removed**: 11 files (dead code)
- 5 risk query modules (replaced by `ado_risk_metrics.py`)
- 3 KLOC feature files (incomplete, never deployed)
- 3 test files

**Remaining**: 4 DOE tracking scripts (status uncertain)

**Production**: 7 REST API collectors (all migrated, all working)

---

## Migration Reference

For migrating remaining scripts to REST API v7.1:
- **Migration Guide**: `docs/MIGRATION_GUIDE_SDK_TO_REST.md`
- **REST Client**: `execution/collectors/ado_rest_client.py`
- **Example Migration**: `execution/collectors/ado_quality_metrics.py`
