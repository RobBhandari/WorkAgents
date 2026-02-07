# Metrics Cleanup Summary - Removing Speculative Data

**Date:** 2026-02-02
**Reason:** Remove all speculative/assumptive calculations. Keep only verifiable hard data.
**Principle:** Better to have fewer accurate metrics than many unreliable ones.

---

## ❌ REMOVED METRICS (Speculative/Fiction)

### Quality Dashboard

#### 1. **Escaped Defects** - REMOVED
- **Why Speculative:** Keyword matching in tags/title ('production', 'prod', 'customer', 'live', 'escaped', 'release')
- **Problem:** No field tracks who actually found the bug
- **Risk:** "Live" bugs ≠ customer-found bugs. Could report 20% escaped when it's actually 2% or 80%.
- **To Fix Properly:** Requires custom field like "Found By" with values: Customer, QA, Developer, etc.

#### 2. **Reopen Rate** - REMOVED
- **Why Speculative:** Proxy - if bug has ClosedDate but current state ≠ Closed/Removed/Resolved, assumes "reopened"
- **Problem:** Doesn't check actual revision history
- **Risk:** Can't distinguish true reopens from state corrections or data issues
- **To Fix Properly:** Requires querying work item revision history to track state transitions

#### 3. **Fix Quality** - REMOVED
- **Why Speculative:** Same proxy as reopen rate - checks current state, not actual reopening events
- **Problem:** No tracking of actual "stayed fixed" vs "reopened"
- **To Fix Properly:** Same as reopen rate - requires revision history

#### 4. **Quality Debt Index** - REMOVED
- **Why Speculative:** Invented formula (age_days × severity_weight) with arbitrary weights (Critical=5, High=3, Medium=2, Low=1)
- **Problem:** Weights and formula have no industry standard or business validation
- **Risk:** Arbitrary scoring system presents invented metrics as factual measurements
- **To Fix Properly:** Requires business stakeholder agreement on actual impact weights, or use industry-standard debt calculation

---

### Flow Dashboard

#### 5. **Cycle Time** - REMOVED
- **Why Speculative:** Approximation - uses StateChangeDate OR CreatedDate as "first active" time
- **Problem:** StateChangeDate is not actual "first active" - could be any state change
- **Risk:** Presents approximate timing as accurate cycle time measurement
- **To Fix Properly:** Requires revision history to accurately track when work actually started (e.g., moved to "In Progress")

---

### Risk Dashboard

#### 6. **PR Size Classification** - REMOVED
- **Why Speculative:** Uses commit count as proxy for size (Small: ≤3, Medium: 4-10, Large: >10 commits)
- **Problem:**
  - Commits ≠ actual lines of code changed
  - Classification thresholds are arbitrary
  - Doesn't measure actual file changes or complexity
- **To Fix Properly:** Requires analyzing actual file diffs to count lines added/deleted

#### 7. **Reopened Bugs** - REMOVED
- **Why Speculative:** Assumes bugs with state='Active' AND recent StateChangeDate were "reopened"
- **Problem:** Doesn't verify if bug was previously closed - could be new bugs or routine state changes
- **To Fix Properly:** Same as reopen rate - requires revision history

---

## ✅ KEPT METRICS (Hard Data Only)

### Quality Dashboard - ACCURATE METRICS
| Metric | Data Source | Why It's Solid |
|--------|-------------|----------------|
| **MTTR** | CreatedDate → ClosedDate | Direct field calculation, no assumptions |
| **Bug Age Distribution** | CreatedDate → Now | Direct date math, no assumptions |
| **Open Bug Count** | State field filtering | Direct count of open items |

### Flow Dashboard - ACCURATE METRICS
| Metric | Data Source | Why It's Solid |
|--------|-------------|----------------|
| **Lead Time** | CreatedDate → ClosedDate | Direct field calculation |
| **WIP** | Count of open items | Direct count |
| **Aging Items** | CreatedDate → Now | Direct age calculation |

### Ownership Dashboard - ACCURATE METRICS
| Metric | Data Source | Why It's Solid |
|--------|-------------|----------------|
| **Unassigned %** | AssignedTo field null check | Direct field validation |
| **Assignment Distribution** | Count per assignee | Direct aggregation |
| **Work Type Segmentation** | WorkItemType field | Direct field grouping |
| **Orphan Areas** | Area + Assignment stats | Based on solid unassigned data (thresholds are arbitrary but underlying data is solid) |

### Risk Dashboard - ACCURATE METRICS
| Metric | Data Source | Why It's Solid |
|--------|-------------|----------------|
| **Code Churn** | File changes per commit | Actual commit data from Git |

---

## 📊 IMPACT SUMMARY

### Before Cleanup:
- **Quality Dashboard:** 6 metrics (4 speculative, 2 solid) - **67% unreliable**
- **Flow Dashboard:** 4 metrics (1 speculative, 3 solid) - **25% unreliable**
- **Risk Dashboard:** 3 metrics (2 speculative, 1 solid) - **67% unreliable**
- **Overall:** 13 metrics → **54% based on speculation**

### After Cleanup:
- **Quality Dashboard:** 2 metrics (100% solid)
- **Flow Dashboard:** 3 metrics (100% solid)
- **Ownership Dashboard:** 4 metrics (100% solid)
- **Risk Dashboard:** 1 metric (100% solid)
- **Overall:** 10 metrics → **100% verifiable hard data**

---

## 🎯 PRINCIPLE ESTABLISHED

**"Better 10 accurate metrics than 13 metrics where 7 are speculation."**

- No keyword guessing
- No proxy calculations
- No arbitrary formulas
- No invented indices
- Only direct field calculations and counts

---

## 🔧 NEXT STEPS

### To Restore Removed Metrics (Properly):
1. **For Reopen Rate / Fix Quality / Reopened Bugs:**
   - Query work item revision history
   - Track actual state transitions (Closed → Active)
   - Verify temporal sequence

2. **For Escaped Defects:**
   - Add custom field: "Found By" (Customer, QA, Developer, etc.)
   - Add custom field: "Environment Found" (Production, Staging, Dev, Test)
   - Require manual tagging at bug creation

3. **For Cycle Time:**
   - Query revision history to find actual "first active" transition
   - Track specific state: New → In Progress (or equivalent)

4. **For PR Size:**
   - Analyze actual Git diffs
   - Count lines added + deleted
   - Use industry-standard thresholds (e.g., Small: <200 LOC, Large: >400 LOC)

5. **For Quality Debt Index:**
   - Get business stakeholder agreement on severity impact
   - Use validated industry frameworks (e.g., SQALE)
   - Or simply don't create synthetic indices - report raw data instead

---

## 📝 FILES MODIFIED

### Data Collection Scripts:
- `execution/ado_quality_metrics.py` - Removed 4 functions, simplified collection
- `execution/ado_flow_metrics.py` - Removed 1 function
- `execution/ado_risk_metrics.py` - Removed 3 functions

### Dashboard Generators (TO BE UPDATED):
- `execution/generate_quality_dashboard.py` - Needs update
- `execution/generate_flow_dashboard.py` - Needs update
- `execution/generate_risk_dashboard.py` - Needs update

---

## ✅ VALIDATION

To verify metrics are solid, ask:
1. **Is this a direct field value?** (System.State, AssignedTo, CreatedDate, etc.)
2. **Is this simple date math?** (Date1 - Date2 = duration)
3. **Is this a direct count?** (Count of items matching criteria)
4. **Does it require no assumptions?**

If answer is YES to all → Keep it.
If answer is NO to any → Remove it or fix the data source.
