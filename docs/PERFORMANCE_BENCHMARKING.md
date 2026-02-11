# Performance Benchmarking Guide

## Overview

This guide documents the performance benchmarking suite for validating the Azure DevOps SDK → REST API v7.1 migration speedup claims.

**Claim:** *"3-50x faster performance with REST API v7.1 async implementation"*

## Quick Start

### 1. Run Quick Benchmark (Recommended for Testing)

Tests a subset of collectors (Quality, Flow, Deployment):

```bash
python execution/benchmark_collectors_enhanced.py --quick
```

**Duration:** ~5-10 minutes

### 2. Run Full Benchmark (All Collectors)

Tests all 6 ADO collectors + ArmorCode:

```bash
python execution/benchmark_collectors_enhanced.py --full
```

**Duration:** ~15-30 minutes

### 3. Generate Performance Report

After running the benchmark, generate documentation:

```bash
python execution/generate_performance_report.py
```

**Outputs:**
- `.tmp/observatory/performance_report.md` - Markdown report
- `.tmp/observatory/performance_report.html` - HTML report (open in browser)

## Benchmark Architecture

### Collectors Tested

| Collector | API Calls per Project | Expected Speedup |
|-----------|----------------------|------------------|
| **Quality** | 3 (WIQL + work items + tests) | 3-5x |
| **Flow** | 3 (WIQL + work items + aging) | 3-5x |
| **Deployment** | 7 (builds + changes + commits) | 10-20x |
| **Ownership** | 15 (repos + commits + PRs) | 20-50x |
| **Collaboration** | 12 (repos + PRs + threads) | 20-50x |
| **Risk** | 6 (security WIQL + work items) | 5-10x |
| **ArmorCode** | 1 per product | 5-10x |

### Metrics Tracked

1. **Execution Time** - Total duration for each collector
2. **API Call Count** - Number of REST API calls made
3. **Throughput** - API calls per second
4. **Memory Usage** - Peak memory consumption (MB)
5. **Success Rate** - Percentage of successful collections

### Execution Modes

#### Sequential Mode (Baseline)
Collectors run one after another:
```
Quality → Flow → Deployment → ... → Total Time
```

#### Concurrent Mode (Optimized)
Collectors run in parallel using `asyncio.gather()`:
```
Quality ┐
Flow    ├→ All run concurrently → Total Time (max of individual times)
Deploy  ┘
```

## Performance Analysis

### Expected Results

Based on the migration from SDK to REST API v7.1:

| Metric | Before (SDK) | After (REST API) | Improvement |
|--------|--------------|------------------|-------------|
| **Total Runtime** | 50-100 minutes | 5-20 minutes | **3-10x faster** |
| **API Throughput** | 2-5 calls/sec | 20-50 calls/sec | **10x faster** |
| **Concurrency** | ThreadPoolExecutor (10 workers) | Native asyncio (unlimited) | **True async** |
| **HTTP Protocol** | HTTP/1.1 | HTTP/2 (multiplexing) | **Connection reuse** |

### Speedup Factors by Collector Type

Different collectors benefit differently from async optimization:

- **Low API Call Collectors** (Quality, Flow): 3-5x speedup
  - Fewer API calls = less parallelization benefit
  - Still improved by HTTP/2 and connection pooling

- **Medium API Call Collectors** (Deployment, Risk): 5-10x speedup
  - Moderate parallelization gains
  - HTTP/2 multiplexing reduces latency

- **High API Call Collectors** (Ownership, Collaboration): 20-50x speedup
  - Maximum benefit from concurrent execution
  - Many independent API calls run in parallel

## Interpreting Results

### Successful Benchmark

```
SPEEDUP ANALYSIS
================================================================================
Sequential Total:    450.23s (7.50 min)
Concurrent Total:     68.45s (1.14 min)
Time Saved:          381.78s (6.36 min)
Speedup Factor:        6.58x

✓ CLAIM VALIDATED: Achieved 3x+ speedup target!
```

**Analysis:**
- ✅ Speedup factor: 6.58x (within 3-50x claim)
- ✅ Time saved: 6.36 minutes per run
- ✅ Claim validated

### Partial Success

```
SPEEDUP ANALYSIS
================================================================================
Sequential Total:    120.50s (2.01 min)
Concurrent Total:     55.25s (0.92 min)
Time Saved:           65.25s (1.09 min)
Speedup Factor:        2.18x

⚠ PARTIAL SUCCESS: 2-3x speedup (below 3x target)
```

**Analysis:**
- ⚠️ Speedup factor: 2.18x (below 3x target)
- Possible causes:
  - Network latency dominating (API calls too fast)
  - Limited test data (fewer projects/items)
  - Azure DevOps API rate limiting

### Failed Benchmark

```
✗ BELOW TARGET: <2x speedup (needs investigation)
```

**Troubleshooting:**
1. Check network connectivity to Azure DevOps
2. Verify API rate limits not being hit (HTTP 429)
3. Ensure sufficient test data exists
4. Review collector error logs

## Technical Implementation Details

### Migration Changes

#### Before (SDK with ThreadPoolExecutor)
```python
# OLD: SDK-based synchronous calls wrapped in thread pool
executor = ThreadPoolExecutor(max_workers=10)
futures = [executor.submit(collect_sync, project) for project in projects]
results = [f.result() for f in futures]
```

**Limitations:**
- Thread pool overhead
- GIL contention in Python
- HTTP/1.1 connection limits
- Limited to 10 concurrent operations

#### After (REST API with asyncio)
```python
# NEW: Native async REST API calls
tasks = [collect_async(project) for project in projects]
results = await asyncio.gather(*tasks)
```

**Benefits:**
- No thread pool overhead
- True concurrent I/O
- HTTP/2 multiplexing
- Unlimited concurrent operations

### HTTP/2 Multiplexing Benefits

The REST API client uses `httpx` with HTTP/2 support:

- **Single Connection:** Reused across all API calls
- **Multiplexing:** Multiple requests/responses in parallel
- **Header Compression:** Reduced bandwidth usage
- **Server Push:** (not used but available)

### Connection Pooling

`AsyncSecureHTTPClient` maintains a connection pool:

```python
limits = httpx.Limits(
    max_connections=100,      # Total connections
    max_keepalive_connections=20,  # Persistent connections
)
```

## Monitoring and Debugging

### Enable Debug Logging

Set environment variable before running:

```bash
export LOG_LEVEL=DEBUG
python execution/benchmark_collectors_enhanced.py --quick
```

### Memory Profiling

Memory usage is tracked automatically using `tracemalloc`:

```
Collector Memory Usage:
- ADO Quality: 45.23 MB
- ADO Flow: 38.67 MB
- ArmorCode: 12.34 MB
```

High memory usage (>100 MB) may indicate:
- Large work item result sets
- Inefficient data structures
- Memory leaks (check for unclosed connections)

### API Call Validation

The benchmark estimates API calls based on collector type. To verify actual calls:

1. Enable network debugging:
   ```bash
   export HTTPX_LOG_LEVEL=DEBUG
   ```

2. Count actual HTTP requests in logs:
   ```bash
   python execution/benchmark_collectors_enhanced.py --quick 2>&1 | grep "HTTP Request: POST" | wc -l
   ```

## Common Issues

### Issue: "Project discovery file not found"

**Error:**
```
FileNotFoundError: Project discovery file not found. Run: python execution/discover_projects.py
```

**Solution:**
```bash
python execution/discover_projects.py
```

This creates `.tmp/observatory/ado_structure.json` with project metadata.

### Issue: "Authentication failed (HTTP 401)"

**Error:**
```
Authentication failed (HTTP 401): Invalid credentials
```

**Solution:**
1. Verify `.env` file exists with:
   ```
   ADO_ORGANIZATION_URL=https://dev.azure.com/yourorg
   ADO_PAT=your_personal_access_token
   ```
2. Check PAT has required permissions:
   - Work Items: Read
   - Build: Read
   - Code: Read
   - Test: Read

### Issue: "Rate limited (HTTP 429)"

**Error:**
```
Rate limited, retrying after 60s
```

**Solution:**
- Azure DevOps has rate limits (200 requests per user per minute)
- Benchmark will automatically retry after cooldown
- Consider spreading benchmark runs over time

### Issue: Low speedup factor (<2x)

**Possible Causes:**
1. **Network latency:** API calls too fast, network becomes bottleneck
2. **Limited data:** Few projects/work items = less parallelization benefit
3. **API throttling:** Rate limits reducing throughput
4. **System resources:** CPU/memory constraints

**Solutions:**
1. Run on production-scale data (many projects)
2. Test on high-bandwidth network
3. Verify system has sufficient resources

## Best Practices

### 1. Baseline Before Changes

Always run benchmarks before making performance-related changes:

```bash
python execution/benchmark_collectors_enhanced.py --full > baseline.txt
```

### 2. Multiple Runs

Run benchmarks 3-5 times and average results to account for variance:

```bash
for i in {1..3}; do
    python execution/benchmark_collectors_enhanced.py --quick
    sleep 60  # Cool down between runs
done
```

### 3. Production-Like Data

Use production-scale data for accurate benchmarks:
- ≥10 projects
- ≥100 work items per project
- ≥50 builds per project

### 4. Stable Environment

Ensure consistent conditions:
- Same network connection
- No other heavy processes running
- Consistent time of day (avoid peak Azure usage hours)

## Continuous Integration

### Automated Benchmarking

Add to CI/CD pipeline to track performance over time:

```yaml
# .github/workflows/benchmark.yml
name: Performance Benchmark

on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday 2 AM

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run benchmark
        run: |
          python execution/benchmark_collectors_enhanced.py --quick
          python execution/generate_performance_report.py
      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: performance-report
          path: .tmp/observatory/performance_report.html
```

## Further Reading

- [Azure DevOps REST API Documentation](https://learn.microsoft.com/en-us/rest/api/azure/devops/?view=azure-devops-rest-7.1)
- [Python asyncio Documentation](https://docs.python.org/3/library/asyncio.html)
- [HTTP/2 Specification](https://http2.github.io/)
- [HTTPX Documentation](https://www.python-httpx.org/)

## Support

For issues or questions:
1. Check this documentation
2. Review benchmark error logs
3. Open GitHub issue with:
   - Benchmark output
   - System information
   - Error messages
