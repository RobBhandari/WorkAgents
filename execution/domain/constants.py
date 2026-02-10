#!/usr/bin/env python3
"""
Application Constants

Centralized configuration constants for metrics, API calls, and thresholds.
Provides type-safe, immutable configuration values used across collectors and dashboards.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FlowMetricsConfig:
    """Flow metrics calculation constants"""

    CLEANUP_THRESHOLD_DAYS: int = 365
    """Lead time threshold to classify work as cleanup (items open >365 days)"""

    AGING_THRESHOLD_DAYS: int = 30
    """Age threshold for identifying aging work items (open >30 days)"""

    LOOKBACK_DAYS: int = 90
    """Default lookback period for historical metrics"""

    P50_PERCENTILE: int = 50
    """50th percentile (median)"""

    P85_PERCENTILE: int = 85
    """85th percentile (common SLA target)"""

    P95_PERCENTILE: int = 95
    """95th percentile (tail latency)"""


@dataclass(frozen=True)
class APIConfig:
    """API call configuration constants"""

    ARMORCODE_PAGE_SIZE: int = 100
    """ArmorCode GraphQL API page size"""

    ARMORCODE_MAX_PAGES: int = 100
    """Maximum pages to fetch from ArmorCode API (safety limit)"""

    ARMORCODE_TIMEOUT_SECONDS: int = 60
    """Timeout for ArmorCode API calls"""

    DEFAULT_TIMEOUT_SECONDS: int = 30
    """Default HTTP timeout for API calls"""

    LONG_TIMEOUT_SECONDS: int = 120
    """Extended timeout for long-running operations"""


@dataclass(frozen=True)
class QualityThresholds:
    """Quality metrics thresholds"""

    HIGH_PRIORITY_BUG_THRESHOLD: int = 10
    """Threshold for high-priority bug count alerts"""

    STALE_BUG_DAYS: int = 90
    """Days after which a bug is considered stale"""

    FIX_QUALITY_WINDOW_DAYS: int = 30
    """Window for measuring if bugs stay fixed (no reopen within 30 days)"""


@dataclass(frozen=True)
class SamplingConfig:
    """Sampling and pagination constants"""

    PR_SAMPLE_SIZE: int = 10
    """Pull request sample size for statistical validity"""

    COMMIT_DETAIL_LIMIT: int = 20
    """Number of commits to fetch detailed file changes for"""

    TOP_ITEMS_LIMIT: int = 20
    """Standard limit for top N items in reports"""

    HOT_PATHS_LIMIT: int = 20
    """Number of hot paths (frequently changed files) to track"""


@dataclass(frozen=True)
class CleanupIndicators:
    """Cleanup effort detection thresholds"""

    CLEANUP_PERCENTAGE_THRESHOLD: float = 30.0
    """Percentage of closures that triggers cleanup effort indicator (>30%)"""

    SIGNIFICANT_CLEANUP_COUNT: int = 10
    """Minimum count of old items to flag as significant cleanup effort"""


@dataclass(frozen=True)
class HistoryRetention:
    """Data retention constants"""

    WEEKS_TO_RETAIN: int = 52
    """Number of weeks to retain in history (12 months for quarterly/annual analysis)"""


# Singleton instances for easy import
flow_metrics = FlowMetricsConfig()
api_config = APIConfig()
quality_thresholds = QualityThresholds()
sampling_config = SamplingConfig()
cleanup_indicators = CleanupIndicators()
history_retention = HistoryRetention()
