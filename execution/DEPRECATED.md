# Deprecated Scripts

The following scripts are **deprecated** and no longer maintained. They rely on the Azure DevOps SDK (`azure-devops==7.1.0b4`), which has been removed from the project in favor of the REST API v7.1.

## 🚫 Deprecated Files (SDK-Dependent)

### Utilities
- **`utils/calculate_kloc.py`** - KLOC calculation using SDK
- **`utils/ado_batch_utils.py`** - Contains deprecated `batch_fetch_work_items()` (SDK version)
  - ✅ **Use instead**: `batch_fetch_work_items_rest()` in the same file (REST API version)

### Risk Query Modules
- **`collectors/risk_queries/missing_tests.py`** - Query for work items missing tests
- **`collectors/risk_queries/stale_bugs.py`** - Query for stale bugs
- **`collectors/risk_queries/high_priority_bugs.py`** - Query for high-priority bugs
- **`collectors/risk_queries/blocked_bugs.py`** - Query for blocked bugs

### One-Time Scripts
- **`create_ado_dec1_baseline.py`** - December 1st baseline creation script
- **`ado_baseline.py`** - Baseline utilities
- **`ado_doe_tracker.py`** - DOE tracker script
- **`ado_query_bugs.py`** - Bug query utility

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

## Recommended Approach

Instead of using these deprecated scripts:
1. Use the REST API-based collectors for production metrics
2. Migrate any needed functionality to REST API v7.1
3. See `collectors/ado_rest_client.py` for REST API implementation patterns
