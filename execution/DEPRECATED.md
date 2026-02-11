# Deprecated Scripts

The following scripts are **deprecated** and no longer maintained. They rely on the Azure DevOps SDK (`azure-devops==7.1.0b4`), which has been removed from the project in favor of the REST API v7.1.

---

## 🚨 CRITICAL: Production-Impacting SDK Dependencies (HIGH PRIORITY MIGRATION)

**WARNING**: These modules are **actively imported by production code** and will fail at runtime.

### Risk Query Modules (Used by `risk_collector.py`)
- **`collectors/risk_queries/missing_tests.py`** ⚠️ **PRODUCTION IMPORT**
- **`collectors/risk_queries/stale_bugs.py`** ⚠️ **PRODUCTION IMPORT**
- **`collectors/risk_queries/high_priority_bugs.py`** ⚠️ **PRODUCTION IMPORT**
- **`collectors/risk_queries/blocked_bugs.py`** ⚠️ **PRODUCTION IMPORT**

**Impact**: Imported by `collectors/risk_collector.py` (lines 20-24)
**Issue**: Uses `azure.devops.v7_1.work_item_tracking` SDK (removed from requirements.txt)
**Result**: `ImportError` at runtime when risk_collector is used
**Action Required**: Migrate to REST API v7.1 using patterns from `collectors/ado_rest_client.py`

### Utilities
- **`utils/calculate_kloc.py`** ⚠️ **PRODUCTION USAGE**
  - **Impact**: Used for defect density calculations in Quality Dashboard
  - **Documentation**: `execution/KLOC_INTEGRATION_README.md`
  - **Issue**: Uses `azure.devops.connection` SDK (removed from requirements.txt)
  - **Action Required**: Migrate to REST API v7.1 Git API endpoints

- **`utils/ado_batch_utils.py`** - Contains deprecated `batch_fetch_work_items()` (SDK version)
  - **Status**: File is NOT deprecated, only one function is deprecated
  - ✅ **Use instead**: `batch_fetch_work_items_rest()` in the same file (REST API version)
  - **Note**: Risk queries migration will automatically fix this dependency

---

## 📋 Standalone Scripts (Lower Priority)

### DOE Initiative Tracking Scripts
- **`create_ado_dec1_baseline.py`** - December 1st baseline creation script
- **`ado_baseline.py`** - Week 0 baseline utilities (Jan 1, 2026)
- **`ado_doe_tracker.py`** - Weekly DOE progress tracking (30% bug reduction target)
- **`ado_query_bugs.py`** - Basic bug query utility

**Status**: Uncertain if DOE initiative is still active
**Usage**: Referenced by `send_doe_report.py`, `ado_bugs_to_html.py`, `run_weekly_doe_report.bat`
**Last Activity**: January-February 2026
**Action**: Keep as-is until initiative status confirmed

---

## ✅ Production Collectors (REST API v7.1)

These collectors are **actively maintained** and run in production (GitHub Actions):
- ✅ `collectors/ado_quality_metrics.py`
- ✅ `collectors/ado_flow_metrics.py`
- ✅ `collectors/ado_deployment_metrics.py`
- ✅ `collectors/ado_ownership_metrics.py`
- ✅ `collectors/ado_collaboration_metrics.py`
- ✅ `collectors/ado_risk_metrics.py`

## Migration Notes

**Date**: 2026-02-10
**Reason**: Removed Azure DevOps SDK (`azure-devops==7.1.0b4`) due to:
- Security vulnerability (H-1 severity)
- Beta/unmaintained package
- 10+ transitive dependencies
- Replaced with direct REST API v7.1 calls (3-50x faster with async/await)

**Impact**: Legacy scripts will fail with `ModuleNotFoundError: No module named 'azure.devops'` if executed locally.

**To Use Legacy Scripts** (Not Recommended):
```bash
# Install SDK manually (not in requirements.txt)
pip install azure-devops==7.1.0b4

# Run legacy script
python execution/ado_query_bugs.py
```

## Migration Priority Roadmap

### Phase 1: Critical Production Fixes (IMMEDIATE)
**Objective**: Fix broken production imports

1. **Migrate `collectors/risk_queries/` modules (4 files)**
   - Pattern: Use `ado_rest_client.py` for WIQL queries via REST API
   - Replace `azure.devops.v7_1.work_item_tracking.Wiql` with REST API POST to `{org}/{project}/_apis/wit/wiql?api-version=7.1`
   - Reference: See `collectors/ado_quality_metrics.py` (already migrated)
   - Files:
     - `blocked_bugs.py`
     - `high_priority_bugs.py`
     - `missing_tests.py`
     - `stale_bugs.py`

2. **Migrate `utils/calculate_kloc.py`**
   - Pattern: Use REST API Git endpoints via `AzureDevOpsRESTClient`
   - Replace `azure.devops.connection.Connection` with REST API
   - Reference: See `collectors/ado_rest_client.py` for Git API patterns
   - Endpoints needed:
     - GET `{org}/{project}/_apis/git/repositories?api-version=7.1`
     - GET `{org}/{project}/_apis/git/repositories/{repositoryId}/items?recursionLevel=Full&api-version=7.1`

### Phase 2: Standalone Scripts (As Needed)
**Objective**: Migrate DOE tracking scripts if initiative is confirmed active

- `ado_baseline.py`
- `ado_doe_tracker.py`
- `create_ado_dec1_baseline.py`
- `ado_query_bugs.py`

**Status**: Deferred until DOE initiative status confirmed

---

## Recommended Approach

Instead of using these deprecated scripts:
1. **PRIORITY**: Migrate risk queries and KLOC calculator (see Phase 1 above)
2. Use the REST API-based collectors for production metrics (already completed for 6 collectors)
3. Migrate any needed functionality to REST API v7.1
4. See `collectors/ado_rest_client.py` for REST API implementation patterns
5. See `docs/MIGRATION_GUIDE_SDK_TO_REST.md` for detailed migration guide
