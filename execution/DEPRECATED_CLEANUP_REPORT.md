# Deprecated Scripts Cleanup Report

**Date**: 2026-02-11
**Analysis**: Comprehensive review of 10 deprecated SDK-dependent scripts
**Status**: Documentation phase complete - Migration roadmap defined

---

## Executive Summary

After removing Azure DevOps SDK (`azure-devops==7.1.0b4`) from production, **5 critical files remain SDK-dependent**:

- ✅ **6 production collectors** - Already migrated to REST API v7.1
- ⚠️ **5 critical files** - Still use SDK, need immediate migration (Phase 1)
- ❓ **4 standalone scripts** - DOE initiative, migration deferred (Phase 2)

---

## Critical Findings

### 🚨 Production Code Breakage Risk

**Files that will cause `ImportError` at runtime:**

1. **`execution/collectors/risk_queries/blocked_bugs.py`**
   - Used by: `risk_collector.py` (line 21)
   - SDK dependency: `from azure.devops.v7_1.work_item_tracking import Wiql`
   - Impact: Risk metrics collection will fail

2. **`execution/collectors/risk_queries/high_priority_bugs.py`**
   - Used by: `risk_collector.py` (line 22)
   - SDK dependency: `from azure.devops.v7_1.work_item_tracking import Wiql`
   - Impact: Risk metrics collection will fail

3. **`execution/collectors/risk_queries/missing_tests.py`**
   - Used by: `risk_collector.py` (line 23)
   - SDK dependency: `from azure.devops.v7_1.work_item_tracking import Wiql`
   - Impact: Risk metrics collection will fail

4. **`execution/collectors/risk_queries/stale_bugs.py`**
   - Used by: `risk_collector.py` (line 24)
   - SDK dependency: `from azure.devops.v7_1.work_item_tracking import Wiql`
   - Impact: Risk metrics collection will fail

5. **`execution/utils/calculate_kloc.py`**
   - Used by: Quality Dashboard for defect density calculations
   - Documentation: `execution/KLOC_INTEGRATION_README.md`
   - SDK dependency: `from azure.devops.connection import Connection`
   - Impact: KLOC calculations and defect density metrics will fail

---

## Analysis Details

### ✅ Already Migrated (Production)

These collectors were successfully migrated to REST API v7.1:
- `collectors/ado_quality_metrics.py`
- `collectors/ado_flow_metrics.py`
- `collectors/ado_deployment_metrics.py`
- `collectors/ado_ownership_metrics.py`
- `collectors/ado_collaboration_metrics.py`
- `collectors/ado_risk_metrics.py`

**Status**: ✅ Production-ready, running in GitHub Actions

---

### ⚠️ Phase 1: Critical Production Fixes (IMMEDIATE)

#### 1. Risk Queries Module (4 files)

**Location**: `execution/collectors/risk_queries/`

**Files**:
- `blocked_bugs.py` (51 lines)
- `high_priority_bugs.py` (similar structure)
- `missing_tests.py` (similar structure)
- `stale_bugs.py` (similar structure)

**Current Implementation**:
```python
from azure.devops.v7_1.work_item_tracking import Wiql
from execution.utils.ado_batch_utils import batch_fetch_work_items  # SDK version
```

**Migration Pattern** (Use REST API):
```python
from execution.collectors.ado_rest_client import AzureDevOpsRESTClient

# Replace Wiql() with REST API POST
response = await client.post(
    f"{org}/{project}/_apis/wit/wiql?api-version=7.1",
    json={"query": wiql_query}
)

# Replace batch_fetch_work_items() with batch_fetch_work_items_rest()
from execution.utils.ado_batch_utils import batch_fetch_work_items_rest
items, failed = await batch_fetch_work_items_rest(client, item_ids, fields)
```

**Reference Implementation**: `collectors/ado_quality_metrics.py` (lines 200-250)

**Estimated Effort**: 2-3 hours per file (8-12 hours total)

---

#### 2. KLOC Calculator

**Location**: `execution/utils/calculate_kloc.py`

**Current Implementation**:
```python
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication

connection = Connection(base_url=org_url, creds=BasicAuthentication('', pat))
git_client = connection.clients.get_git_client()
```

**Migration Pattern** (Use REST API):
```python
from execution.collectors.ado_rest_client import get_ado_rest_client

client = get_ado_rest_client()

# Get repositories
repos_response = await client.get(
    f"{org}/{project}/_apis/git/repositories?api-version=7.1"
)

# Get file tree
items_response = await client.get(
    f"{org}/{project}/_apis/git/repositories/{repo_id}/items"
    f"?recursionLevel=Full&api-version=7.1"
)

# Get file content
content_response = await client.get(
    f"{org}/{project}/_apis/git/repositories/{repo_id}/items"
    f"?path={file_path}&api-version=7.1"
)
```

**Reference Implementation**: `collectors/ado_rest_client.py` (Git API methods)

**Estimated Effort**: 3-4 hours

---

### ❓ Phase 2: Standalone Scripts (Deferred)

#### DOE Initiative Tracking Scripts

**Files**:
1. `execution/ado_baseline.py` (Week 0 baseline - Jan 1, 2026)
2. `execution/ado_doe_tracker.py` (Weekly tracking - 30% bug reduction)
3. `execution/create_ado_dec1_baseline.py` (Dec 1, 2025 baseline)
4. `execution/ado_query_bugs.py` (Basic bug query utility)

**Related Files** (Support DOE workflow):
- `execution/send_doe_report.py` (Email report sender)
- `execution/ado_bugs_to_html.py` (HTML report generator)
- `execution/run_weekly_doe_report.bat` (Batch orchestrator)

**Last Activity**: January-February 2026 (recent commits)

**Status**: Uncertain if DOE (Department of Excellence?) initiative is still active

**Decision Required**:
- **If active**: Migrate to REST API v7.1 (estimated 6-8 hours for all 4 scripts)
- **If inactive**: Remove from codebase (clean up 7 files)
- **If uncertain**: Keep as-is in DEPRECATED.md (current approach)

---

## File Categorization Summary

| Category | Count | Status | Action |
|----------|-------|--------|--------|
| Production collectors (migrated) | 6 | ✅ Complete | None |
| Risk queries (production import) | 4 | ⚠️ Broken | **MIGRATE** |
| KLOC calculator (production usage) | 1 | ⚠️ Broken | **MIGRATE** |
| DOE tracking scripts | 4 | ❓ Uncertain | **DEFER** |
| DOE support scripts | 3 | ❓ Uncertain | **DEFER** |
| **TOTAL** | **18** | | |

---

## Migration Testing Strategy

### For Each Migrated File:

1. **Unit Tests**: Update existing tests to use REST API mocks
   - Example: `tests/collectors/risk_queries/test_blocked_bugs.py`
   - Replace SDK client mocks with REST response mocks

2. **Integration Tests**: Verify REST API responses match SDK behavior
   - Compare JSON output format
   - Validate error handling

3. **Quality Gates**: All 6 checks must pass before commit
   - Black formatting
   - Ruff linting
   - MyPy type checking
   - Pytest unit tests
   - Bandit security scan
   - Sphinx documentation build

---

## Next Steps

### Immediate Actions:

1. ✅ **DONE**: Update `execution/DEPRECATED.md` with critical production warnings
2. ✅ **DONE**: Create migration roadmap document (this file)
3. ⏳ **PENDING**: Migrate `risk_queries/` modules (4 files) to REST API v7.1
4. ⏳ **PENDING**: Migrate `calculate_kloc.py` to REST API v7.1
5. ⏳ **PENDING**: Update tests for migrated modules
6. ⏳ **PENDING**: Run all 6 quality gates before commit

### Future Actions (When DOE Status Confirmed):

- If DOE active: Migrate 4 DOE tracking scripts
- If DOE inactive: Remove 7 DOE-related files
- If DOE uncertain: Leave in DEPRECATED.md as-is

---

## References

- **Migration Guide**: `docs/MIGRATION_GUIDE_SDK_TO_REST.md`
- **REST Client**: `execution/collectors/ado_rest_client.py`
- **Example Migration**: `execution/collectors/ado_quality_metrics.py`
- **DEPRECATED List**: `execution/DEPRECATED.md`
- **KLOC Documentation**: `execution/KLOC_INTEGRATION_README.md`

---

## Success Criteria

Migration is complete when:
- ✅ No production code imports SDK-dependent modules
- ✅ All 6 quality gates pass
- ✅ Integration tests verify REST API equivalence
- ✅ Documentation updated to reflect REST API patterns
- ✅ `execution/DEPRECATED.md` updated or removed

---

**Generated**: 2026-02-11
**Next Review**: After Phase 1 migration complete
