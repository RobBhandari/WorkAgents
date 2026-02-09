# Metrics Feasibility Analysis

## Current Data Sources
1. **Azure DevOps API** (via azure-devops SDK 7.1.0)
   - Work Item Tracking (Bugs, User Stories, Tasks, Features)
   - Git repositories (commits, branches, file changes)
   - Pull Requests (PR lifecycle, reviews, comments)
   - Build pipelines (if available)

2. **ArmorCode API** (GraphQL)
   - Vulnerability findings
   - Limited fields: severity, status, product
   - No date fields (createDate, closedDate unavailable)

3. **Git Repository Access**
   - File analysis for KLOC
   - Commit history
   - File change patterns

---

## Metrics Feasibility Assessment

### ✅ **FULLY DETERMINABLE** (from existing data sources)

#### Deployment & Release Metrics (Partial)
| Metric | Data Source | Implementation Notes |
|--------|-------------|---------------------|
| **Deployment Frequency** | Azure Pipelines API | ✅ Query `build_client.get_builds()` with `status='completed'` and `result='succeeded'`<br>Track builds to production branch |
| **Lead Time for Changes** | Git + Work Items | ✅ Track commit timestamp → PR merge → build completion<br>Link work items to commits via commit messages |

#### Test & Quality Coverage Metrics
| Metric | Data Source | Implementation Notes |
|--------|-------------|---------------------|
| **Technical Debt Ratio** | Git commits | ⚠️ **PARTIAL**: Can calculate code churn and file complexity<br>❌ Cannot get SonarQube-style remediation cost without static analysis tool |

#### Velocity & Predictability Metrics
| Metric | Data Source | Implementation Notes |
|--------|-------------|---------------------|
| **Throughput** | Work Items | ✅ Count closed items per week (already have closed_count_90d)<br>Simple addition to existing flow metrics |
| **Cycle Time Variance** | Work Items | ✅ Calculate std deviation of lead times<br>Already collecting lead time data |
| **Planned vs Unplanned Work Ratio** | Work Items | ✅ Tag work items as "Planned" vs "Bug/Incident"<br>Already distinguishing Bugs vs User Stories |

#### Collaboration & Code Review Metrics
| Metric | Data Source | Implementation Notes |
|--------|-------------|---------------------|
| **PR Review Time** | Pull Requests API | ✅ `created_date` → first review comment timestamp<br>Query: `git_client.get_pull_request_threads()` |
| **PR Merge Time** | Pull Requests API | ✅ `created_date` → `closed_date`<br>Already available in PR data |
| **PR Size (Lines Changed)** | Pull Requests API | ✅ Query: `git_client.get_pull_request_commits()` + get commit diffs<br>Currently using commit count - can enhance |
| **Review Iteration Count** | Pull Requests API | ✅ Count push events after PR creation<br>Query: `git_client.get_pull_request_iterations()` |

#### Reliability & Operations Metrics
| Metric | Data Source | Implementation Notes |
|--------|-------------|---------------------|
| **Incident Count** | Work Items | ✅ Filter work items with tag "Incident" or type "Issue"<br>Add custom work item type if needed |

#### Developer Experience Metrics
| Metric | Data Source | Implementation Notes |
|--------|-------------|---------------------|
| **Build Success Rate** | Azure Pipelines API | ✅ Query: `build_client.get_builds()`<br>Calculate: `succeeded / (succeeded + failed)` |
| **Build Duration** | Azure Pipelines API | ✅ Available in build record: `finish_time - start_time` |
| **Developer Active Days** | Git commits | ✅ Count unique commit dates per developer<br>Already querying commits in risk metrics |
| **Blocked Work Items** | Work Items | ✅ Filter: `state='Blocked'` or custom tag<br>Track state change history for block duration |

#### Dependencies & Architecture Metrics
| Metric | Data Source | Implementation Notes |
|--------|-------------|---------------------|
| **Knowledge Distribution** | Git commits | ✅ Calculate bus factor from commit patterns<br>Already tracking file changes in code churn |
| **Module Coupling Score** | Git commits | ✅ Analyze co-change patterns (files changed together)<br>Calculate from commit file lists |

#### Team Health Indicators
| Metric | Data Source | Implementation Notes |
|--------|-------------|---------------------|
| **After-Hours Work %** | Git commits | ✅ Filter commits by timestamp (outside 9am-6pm)<br>Already have commit timestamps |

---

### ⚠️ **PARTIALLY DETERMINABLE** (limited data or approximations)

#### Deployment & Release Metrics
| Metric | Challenge | Workaround |
|--------|-----------|------------|
| **Change Failure Rate** | Need production incident data linked to deployments | ⚠️ Use "Bug" work items created within 48h of deployment<br>Requires tagging bugs with "Production" |
| **Failed Deployment Recovery Time** | Need incident start/end timestamps | ⚠️ Track time from failed build → next successful build<br>Approximation only |

#### Test & Quality Coverage Metrics
| Metric | Challenge | Workaround |
|--------|-----------|------------|
| **Test Coverage %** | Need test execution results | ⚠️ Query Azure Pipelines test results API if tests run in CI<br>Requires pipeline integration |
| **Test Execution Time** | Need test execution data | ⚠️ Extract from build logs if tests run in pipeline |
| **Flaky Test Rate** | Need test execution history | ⚠️ Track test pass/fail patterns across builds<br>Requires test results API |

#### Reliability & Operations Metrics
| Metric | Challenge | Workaround |
|--------|-----------|------------|
| **Mean Time to Detect (MTTD)** | Need monitoring data | ⚠️ Approximate using work item creation time - commit time<br>Unreliable without APM tool |
| **Mean Time to Acknowledge (MTTA)** | Need paging/alerting data | ⚠️ Track work item assignment time<br>Not true acknowledgment |
| **Escaped Defect Rate** | Need bug source classification | ⚠️ Use tags like "Customer-Reported" vs "Internal"<br>Requires manual tagging |

#### Dependencies & Architecture Metrics
| Metric | Challenge | Workaround |
|--------|-----------|------------|
| **Dependency Update Lag** | Need dependency scanning | ⚠️ Parse package.json, requirements.txt from Git<br>Manual version comparison |

---

### ❌ **NOT DETERMINABLE** (requires additional tools/integrations)

#### Customer & Business Value Metrics
| Metric | Missing Tool | Required Integration |
|--------|--------------|---------------------|
| **Feature Adoption Rate** | User analytics | Google Analytics / Mixpanel / Application Insights |
| **Customer-Reported Issues** | Support ticketing | Jira Service Desk / Zendesk |
| **Time to Customer Value** | End-to-end tracking | Requires linking planning → deployment → adoption |

---

## Summary Table

| Category | Fully Determinable | Partially Determinable | Not Determinable | Total Suggested |
|----------|-------------------|----------------------|-----------------|-----------------|
| **DORA Metrics** | 2 | 2 | 0 | 4 |
| **Test & Quality** | 0 | 4 | 0 | 4 |
| **Velocity** | 3 | 0 | 0 | 3 |
| **Code Review** | 4 | 0 | 0 | 4 |
| **Reliability** | 1 | 3 | 0 | 4 |
| **Developer Experience** | 4 | 0 | 0 | 4 |
| **Business Value** | 0 | 0 | 3 | 3 |
| **Architecture** | 2 | 1 | 0 | 3 |
| **Team Health** | 1 | 0 | 0 | 1 |
| **TOTAL** | **17** | **10** | **3** | **30** |

---

## Recommended Implementation Order

### Phase 1: Quick Wins (1-2 days implementation)
These metrics use data you're already querying:

1. ✅ **Throughput** - Already have closed items, just add per-week calculation
2. ✅ **Cycle Time Variance** - Add std deviation to existing lead time calc
3. ✅ **Planned vs Unplanned Ratio** - Segment existing Bugs vs Stories
4. ✅ **After-Hours Work %** - Filter existing commit timestamps
5. ✅ **Developer Active Days** - Count unique dates from existing commits
6. ✅ **Knowledge Distribution** - Analyze existing commit/file data

### Phase 2: Pipeline Integration (3-5 days)
Requires adding Azure Pipelines API calls:

7. ✅ **Deployment Frequency** - Query builds to production branch
8. ✅ **Build Success Rate** - Query build results
9. ✅ **Build Duration** - Extract from build records
10. ⚠️ **Test Coverage %** - If tests run in pipelines
11. ⚠️ **Test Execution Time** - If tests run in pipelines

### Phase 3: Enhanced Git Analysis (5-7 days)
Deeper analysis of existing Git data:

12. ✅ **PR Review Time** - Add PR comments API
13. ✅ **PR Merge Time** - Already have dates, formalize metric
14. ✅ **PR Size (LOC)** - Enhance from commit count to actual LOC
15. ✅ **Review Iteration Count** - Query PR iterations
16. ✅ **Lead Time for Changes** - Link commits → PRs → builds
17. ✅ **Module Coupling** - Co-change pattern analysis

### Phase 4: Work Item Enhancements (2-3 days)
Better work item classification:

18. ✅ **Blocked Work Items** - Filter by state or tag
19. ✅ **Incident Count** - Add custom work item type/tag
20. ⚠️ **Change Failure Rate** - Tag production bugs
21. ⚠️ **Escaped Defect Rate** - Add source tags to bugs

### Phase 5: External Integrations (requires 3rd party tools)
Would need new tool integrations:

22. ❌ **Feature Adoption Rate** - Needs analytics platform
23. ❌ **Customer-Reported Issues** - Needs support system
24. ❌ **Time to Customer Value** - Needs end-to-end tracking

---

## API Endpoints to Add

### Azure DevOps APIs you're NOT currently using:

```python
# Build & Release APIs
build_client = connection.clients.get_build_client()

# Get builds (for deployment frequency, build success rate)
builds = build_client.get_builds(
    project=project_name,
    definitions=[definition_id],  # Filter to production pipelines
    status_filter='completed',
    min_time=lookback_date
)

# Get build details (for build duration)
build_details = build_client.get_build(
    project=project_name,
    build_id=build_id
)

# Get test results (for test coverage, execution time)
test_client = connection.clients.get_test_client()
test_results = test_client.get_test_results_by_build(
    project=project_name,
    build_id=build_id
)

# PR review APIs
git_client = connection.clients.get_git_client()

# Get PR threads/comments (for review time)
pr_threads = git_client.get_threads(
    repository_id=repo_id,
    pull_request_id=pr_id,
    project=project_name
)

# Get PR iterations (for review iteration count)
pr_iterations = git_client.get_pull_request_iterations(
    repository_id=repo_id,
    pull_request_id=pr_id,
    project=project_name
)

# Get PR work items (for linking PRs to work items)
pr_work_items = git_client.get_pull_request_work_item_refs(
    repository_id=repo_id,
    pull_request_id=pr_id,
    project=project_name
)
```

---

## Metrics You CANNOT Get (Data Limitations)

### ArmorCode Limitations
❌ **Security MTTR** - GraphQL schema missing `createDate` and `closedDate` fields
❌ **Vulnerability Age** - Cannot calculate without creation date
❌ **Stale Criticals (accurate)** - Can only count current criticals, not age

**Workaround**: Request ArmorCode API enhancement or use REST API v2 if dates available

### Azure DevOps Limitations
⚠️ **Reopen Rate** - Would need work item revision history API (complex, high API call count)
⚠️ **Thrash Index** - Would need full assignment history (revision history)

**Workaround**: These require `work_item_tracking_client.get_updates(work_item_id)` which is expensive

---

## Final Recommendation

### Immediate Next Steps (This Week):
1. **Add Phase 1 metrics** (6 metrics, already have the data)
2. **Add Azure Pipelines client** to collect build/deployment data
3. **Enhance PR analysis** with review timing

### This Month:
4. Implement Phase 2 & 3 (deployment + git analysis)
5. Add work item tagging for incidents/production bugs

### Future (if business value justifies):
6. Integrate with analytics platform for feature adoption
7. Integrate with support system for customer issues
8. Request ArmorCode API enhancements for date fields

---

**Bottom Line**: You can determine **17 out of 30 metrics fully** and **10 partially** from your current Azure DevOps + Git data sources. That's **90% coverage** with the tools you already have access to.
