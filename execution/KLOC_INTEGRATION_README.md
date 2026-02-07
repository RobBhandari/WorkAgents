# KLOC Integration for Quality Dashboard

## Overview

KLOC (Kilo Lines of Code) metrics have been successfully integrated into the Quality Dashboard to provide **defect density** measurements - a key industry-standard quality metric.

## What Was Added

### 1. KLOC Calculator (`calculate_kloc.py`)

A new script that:
- Connects to Azure DevOps Git repositories
- Analyzes source code files across all project repositories
- Counts lines of code (total and code-only, excluding comments/blanks)
- Supports all major programming languages (.py, .js, .cs, .java, .ts, .cpp, etc.)
- Excludes non-code files (config, docs, dependencies, build outputs)
- Caches results in `.tmp/observatory/kloc_data.json`

**Usage:**
```bash
python execution\calculate_kloc.py
```

### 2. Quality Metrics Integration

Enhanced `ado_quality_metrics.py` to:
- Load KLOC data from cache
- Calculate **defect density** (bugs per KLOC)
- Include KLOC metrics in quality history
- Track both total KLOC and code KLOC

**Defect Density Formula:**
```
Defect Density = Total Bugs / Code KLOC
```

### 3. Quality Dashboard Updates

Enhanced `generate_quality_dashboard.py` with:

#### New Summary Cards:
- **Total KLOC**: Portfolio-wide code size
- **Defect Density**: Average bugs per KLOC
- **Projects with KLOC**: Coverage indicator

#### New Table Columns:
- **KLOC**: Code size per project
- **Defect Density**: Color-coded quality indicator
  - 🟢 Green: < 1.0 bugs/KLOC (Excellent)
  - 🟠 Amber: 1.0 - 3.0 bugs/KLOC (Good)
  - 🔴 Red: > 3.0 bugs/KLOC (Needs Improvement)

#### Enhanced Project Drill-Down:
When clicking on a project, you'll see:
- Code KLOC vs Total KLOC
- Number of files analyzed
- Repository count
- Defect density breakdown (total and open bugs)

#### Updated Glossary:
- Explains what KLOC measures
- Defines defect density
- Provides industry benchmarks
- Explains why defect density matters

## Workflow

### Complete Integration Test

Run the test script to verify everything works:

```bash
execution\test_kloc_integration.bat
```

This will:
1. Calculate KLOC from your Git repositories
2. Collect quality metrics with defect density
3. Generate the Quality Dashboard with KLOC display

### Manual Step-by-Step

If you prefer to run steps individually:

```bash
# Step 1: Calculate KLOC
python execution\calculate_kloc.py

# Step 2: Collect quality metrics (includes KLOC)
python execution\ado_quality_metrics.py

# Step 3: Generate dashboard
python execution\generate_quality_dashboard.py

# Step 4: Open dashboard
start .tmp\observatory\dashboards\quality_dashboard.html
```

## Data Files

### Input
- `.tmp/observatory/ado_structure.json` - Project definitions
- Azure DevOps Git repositories (accessed via API)

### Output
- `.tmp/observatory/kloc_data.json` - KLOC metrics cache
- `.tmp/observatory/quality_history.json` - Quality metrics with KLOC
- `.tmp/observatory/dashboards/quality_dashboard.html` - Dashboard

## KLOC Calculation Details

### What's Counted
- Source code files only (.py, .js, .cs, .java, .ts, .cpp, .go, .rb, etc.)
- Code lines (excluding comments and blank lines where possible)
- All files across all repositories in a project

### What's Excluded
- Dependencies (node_modules, vendor, packages, venv)
- Build outputs (bin, obj, build, dist, target)
- IDE files (.vs, .vscode, .idea)
- Version control (.git, .svn)
- Config files (.json, .yaml, .xml, .toml)
- Documentation (.md, .txt, .rst)
- Assets (images, videos, binaries)

### Language Support

Single-line comment detection for:
- Python, Ruby, Shell: `#`
- JavaScript, TypeScript, Java, C#, C/C++, Go, Rust, PHP, Swift: `//`
- SQL: `--`

Block comment detection:
- C-style: `/* */`
- HTML: `<!-- -->`
- Python docstrings: `"""` or `'''`

## Defect Density Benchmarks

Based on industry standards:

| Defect Density | Quality Level | Typical For |
|---------------|---------------|-------------|
| < 0.5 bugs/KLOC | Exceptional | Safety-critical systems, financial software |
| 0.5 - 1.0 bugs/KLOC | Excellent | Well-tested enterprise applications |
| 1.0 - 2.0 bugs/KLOC | Good | Standard commercial software |
| 2.0 - 3.0 bugs/KLOC | Acceptable | Rapid development projects |
| > 3.0 bugs/KLOC | Needs Improvement | Technical debt, insufficient testing |

**Important Notes:**
- Defect density is a relative metric - use it to compare projects within your organization
- Context matters: A complex legacy system may naturally have higher defect density
- Trend over time is more important than absolute values
- Should be used alongside other quality metrics (MTTR, bug age, etc.)

## Why Defect Density Matters

### Problem Without KLOC
- Project A: 100 bugs - seems like a lot
- Project B: 50 bugs - seems better

### Reality With KLOC
- Project A: 100 bugs, 500 KLOC = **0.2 bugs/KLOC** (excellent!)
- Project B: 50 bugs, 10 KLOC = **5.0 bugs/KLOC** (needs work!)

Defect density normalizes bug counts by codebase size, allowing fair comparison across projects of different sizes.

## Troubleshooting

### KLOC calculation returns 0 or fails
- **Issue**: No repositories found or unable to access branch
- **Solution**:
  - Verify Azure DevOps PAT has Git read permissions
  - Check that projects have Git repositories
  - Ensure repositories have a 'main' or 'master' branch

### KLOC data not showing in dashboard
- **Issue**: KLOC data not loaded during quality metrics collection
- **Solution**:
  - Run `calculate_kloc.py` first to create the cache
  - Verify `.tmp/observatory/kloc_data.json` exists
  - Re-run `ado_quality_metrics.py`

### Defect density seems wrong
- **Issue**: Very high or very low values
- **Check**:
  - KLOC file extensions - are the right files being counted?
  - Bug filters - are all bugs being included?
  - Use code_kloc (not total_kloc) for accurate measurement

## Maintenance

### When to Recalculate KLOC
- After significant code additions or deletions
- When onboarding new projects
- Monthly or quarterly for trend tracking
- Before executive reporting

### Refresh Frequency
- **KLOC**: Weekly or monthly (code size changes gradually)
- **Quality Metrics**: Weekly (bug counts change frequently)
- **Dashboard**: Weekly (automated via refresh script)

## Integration with Other Dashboards

The KLOC calculation is modular and can be integrated into:
- **Flow Dashboard**: Code churn (KLOC added/modified)
- **Ownership Dashboard**: KLOC per assignee or team
- **Risk Dashboard**: Code complexity vs KLOC

## Next Steps

To integrate KLOC into automated weekly reporting:

1. Add KLOC calculation to your refresh script:
```bash
# Add to refresh_all_dashboards.bat or .py
python execution/calculate_kloc.py
```

2. Schedule KLOC recalculation monthly (since code size changes slowly)

3. Track defect density trends over time to measure quality improvements

## Support

For issues or questions:
1. Check output logs from `calculate_kloc.py`
2. Verify `.tmp/observatory/kloc_data.json` structure
3. Review Azure DevOps Git API permissions

---

**Generated**: 2026-02-03
**Integration Status**: ✓ Complete
**Compatibility**: Works with existing Director Observatory infrastructure
