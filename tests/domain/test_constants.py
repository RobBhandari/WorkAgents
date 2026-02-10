#!/usr/bin/env python3
"""
Tests for Application Constants Module

Verifies immutability, type correctness, and importability of constants.
"""

import pytest

from execution.domain.constants import (
    APIConfig,
    CleanupIndicators,
    FlowMetricsConfig,
    HistoryRetention,
    QualityThresholds,
    SamplingConfig,
    api_config,
    cleanup_indicators,
    flow_metrics,
    history_retention,
    quality_thresholds,
    sampling_config,
)


class TestFlowMetricsConfig:
    """Test FlowMetricsConfig constants"""

    def test_cleanup_threshold_days(self):
        """Test cleanup threshold is 365 days"""
        assert FlowMetricsConfig.CLEANUP_THRESHOLD_DAYS == 365
        assert isinstance(FlowMetricsConfig.CLEANUP_THRESHOLD_DAYS, int)

    def test_aging_threshold_days(self):
        """Test aging threshold is 30 days"""
        assert FlowMetricsConfig.AGING_THRESHOLD_DAYS == 30
        assert isinstance(FlowMetricsConfig.AGING_THRESHOLD_DAYS, int)

    def test_lookback_days(self):
        """Test lookback period is 90 days"""
        assert FlowMetricsConfig.LOOKBACK_DAYS == 90
        assert isinstance(FlowMetricsConfig.LOOKBACK_DAYS, int)

    def test_percentiles(self):
        """Test percentile values are correct"""
        assert FlowMetricsConfig.P50_PERCENTILE == 50
        assert FlowMetricsConfig.P85_PERCENTILE == 85
        assert FlowMetricsConfig.P95_PERCENTILE == 95

    def test_immutability(self):
        """Test that FlowMetricsConfig instances are immutable"""
        config = FlowMetricsConfig()
        with pytest.raises(AttributeError):
            config.CLEANUP_THRESHOLD_DAYS = 999  # type: ignore

    def test_singleton_instance(self):
        """Test singleton instance is available"""
        assert flow_metrics.CLEANUP_THRESHOLD_DAYS == 365
        assert flow_metrics.P85_PERCENTILE == 85


class TestAPIConfig:
    """Test APIConfig constants"""

    def test_armorcode_page_size(self):
        """Test ArmorCode page size is 100"""
        assert APIConfig.ARMORCODE_PAGE_SIZE == 100
        assert isinstance(APIConfig.ARMORCODE_PAGE_SIZE, int)

    def test_armorcode_max_pages(self):
        """Test ArmorCode max pages is 100"""
        assert APIConfig.ARMORCODE_MAX_PAGES == 100
        assert isinstance(APIConfig.ARMORCODE_MAX_PAGES, int)

    def test_armorcode_timeout(self):
        """Test ArmorCode timeout is 60 seconds"""
        assert APIConfig.ARMORCODE_TIMEOUT_SECONDS == 60
        assert isinstance(APIConfig.ARMORCODE_TIMEOUT_SECONDS, int)

    def test_default_timeout(self):
        """Test default timeout is 30 seconds"""
        assert APIConfig.DEFAULT_TIMEOUT_SECONDS == 30
        assert isinstance(APIConfig.DEFAULT_TIMEOUT_SECONDS, int)

    def test_long_timeout(self):
        """Test long timeout is 120 seconds"""
        assert APIConfig.LONG_TIMEOUT_SECONDS == 120
        assert isinstance(APIConfig.LONG_TIMEOUT_SECONDS, int)

    def test_immutability(self):
        """Test that APIConfig instances are immutable"""
        config = APIConfig()
        with pytest.raises(AttributeError):
            config.ARMORCODE_PAGE_SIZE = 999  # type: ignore

    def test_singleton_instance(self):
        """Test singleton instance is available"""
        assert api_config.ARMORCODE_PAGE_SIZE == 100
        assert api_config.DEFAULT_TIMEOUT_SECONDS == 30


class TestQualityThresholds:
    """Test QualityThresholds constants"""

    def test_high_priority_bug_threshold(self):
        """Test high priority bug threshold is 10"""
        assert QualityThresholds.HIGH_PRIORITY_BUG_THRESHOLD == 10
        assert isinstance(QualityThresholds.HIGH_PRIORITY_BUG_THRESHOLD, int)

    def test_stale_bug_days(self):
        """Test stale bug threshold is 90 days"""
        assert QualityThresholds.STALE_BUG_DAYS == 90
        assert isinstance(QualityThresholds.STALE_BUG_DAYS, int)

    def test_fix_quality_window_days(self):
        """Test fix quality window is 30 days"""
        assert QualityThresholds.FIX_QUALITY_WINDOW_DAYS == 30
        assert isinstance(QualityThresholds.FIX_QUALITY_WINDOW_DAYS, int)

    def test_immutability(self):
        """Test that QualityThresholds instances are immutable"""
        config = QualityThresholds()
        with pytest.raises(AttributeError):
            config.STALE_BUG_DAYS = 999  # type: ignore

    def test_singleton_instance(self):
        """Test singleton instance is available"""
        assert quality_thresholds.STALE_BUG_DAYS == 90
        assert quality_thresholds.FIX_QUALITY_WINDOW_DAYS == 30


class TestSamplingConfig:
    """Test SamplingConfig constants"""

    def test_pr_sample_size(self):
        """Test PR sample size is 10"""
        assert SamplingConfig.PR_SAMPLE_SIZE == 10
        assert isinstance(SamplingConfig.PR_SAMPLE_SIZE, int)

    def test_commit_detail_limit(self):
        """Test commit detail limit is 20"""
        assert SamplingConfig.COMMIT_DETAIL_LIMIT == 20
        assert isinstance(SamplingConfig.COMMIT_DETAIL_LIMIT, int)

    def test_top_items_limit(self):
        """Test top items limit is 20"""
        assert SamplingConfig.TOP_ITEMS_LIMIT == 20
        assert isinstance(SamplingConfig.TOP_ITEMS_LIMIT, int)

    def test_hot_paths_limit(self):
        """Test hot paths limit is 20"""
        assert SamplingConfig.HOT_PATHS_LIMIT == 20
        assert isinstance(SamplingConfig.HOT_PATHS_LIMIT, int)

    def test_immutability(self):
        """Test that SamplingConfig instances are immutable"""
        config = SamplingConfig()
        with pytest.raises(AttributeError):
            config.PR_SAMPLE_SIZE = 999  # type: ignore

    def test_singleton_instance(self):
        """Test singleton instance is available"""
        assert sampling_config.PR_SAMPLE_SIZE == 10
        assert sampling_config.TOP_ITEMS_LIMIT == 20


class TestCleanupIndicators:
    """Test CleanupIndicators constants"""

    def test_cleanup_percentage_threshold(self):
        """Test cleanup percentage threshold is 30%"""
        assert CleanupIndicators.CLEANUP_PERCENTAGE_THRESHOLD == 30.0
        assert isinstance(CleanupIndicators.CLEANUP_PERCENTAGE_THRESHOLD, float)

    def test_significant_cleanup_count(self):
        """Test significant cleanup count is 10"""
        assert CleanupIndicators.SIGNIFICANT_CLEANUP_COUNT == 10
        assert isinstance(CleanupIndicators.SIGNIFICANT_CLEANUP_COUNT, int)

    def test_immutability(self):
        """Test that CleanupIndicators instances are immutable"""
        config = CleanupIndicators()
        with pytest.raises(AttributeError):
            config.CLEANUP_PERCENTAGE_THRESHOLD = 999.0  # type: ignore

    def test_singleton_instance(self):
        """Test singleton instance is available"""
        assert cleanup_indicators.CLEANUP_PERCENTAGE_THRESHOLD == 30.0
        assert cleanup_indicators.SIGNIFICANT_CLEANUP_COUNT == 10


class TestHistoryRetention:
    """Test HistoryRetention constants"""

    def test_weeks_to_retain(self):
        """Test weeks to retain is 52 (12 months)"""
        assert HistoryRetention.WEEKS_TO_RETAIN == 52
        assert isinstance(HistoryRetention.WEEKS_TO_RETAIN, int)

    def test_immutability(self):
        """Test that HistoryRetention instances are immutable"""
        config = HistoryRetention()
        with pytest.raises(AttributeError):
            config.WEEKS_TO_RETAIN = 999  # type: ignore

    def test_singleton_instance(self):
        """Test singleton instance is available"""
        assert history_retention.WEEKS_TO_RETAIN == 52


class TestConstantsImportability:
    """Test that constants can be imported and used"""

    def test_import_all_classes(self):
        """Test that all constant classes can be imported"""
        assert FlowMetricsConfig is not None
        assert APIConfig is not None
        assert QualityThresholds is not None
        assert SamplingConfig is not None
        assert CleanupIndicators is not None
        assert HistoryRetention is not None

    def test_import_all_singletons(self):
        """Test that all singleton instances can be imported"""
        assert flow_metrics is not None
        assert api_config is not None
        assert quality_thresholds is not None
        assert sampling_config is not None
        assert cleanup_indicators is not None
        assert history_retention is not None

    def test_singleton_instances_are_correct_type(self):
        """Test that singleton instances are correct type"""
        assert isinstance(flow_metrics, FlowMetricsConfig)
        assert isinstance(api_config, APIConfig)
        assert isinstance(quality_thresholds, QualityThresholds)
        assert isinstance(sampling_config, SamplingConfig)
        assert isinstance(cleanup_indicators, CleanupIndicators)
        assert isinstance(history_retention, HistoryRetention)


class TestConstantsUsagePatterns:
    """Test common usage patterns for constants"""

    def test_class_level_access(self):
        """Test accessing constants via class"""
        assert FlowMetricsConfig.CLEANUP_THRESHOLD_DAYS == 365
        assert APIConfig.ARMORCODE_PAGE_SIZE == 100

    def test_instance_level_access(self):
        """Test accessing constants via instance"""
        config = FlowMetricsConfig()
        assert config.CLEANUP_THRESHOLD_DAYS == 365
        assert config.P85_PERCENTILE == 85

    def test_singleton_access(self):
        """Test accessing constants via singleton"""
        assert flow_metrics.CLEANUP_THRESHOLD_DAYS == 365
        assert api_config.ARMORCODE_PAGE_SIZE == 100

    def test_use_in_function_defaults(self):
        """Test using constants as function default values"""

        def sample_function(
            threshold: int = flow_metrics.CLEANUP_THRESHOLD_DAYS,
            page_size: int = api_config.ARMORCODE_PAGE_SIZE,
        ) -> dict:
            return {"threshold": threshold, "page_size": page_size}

        result = sample_function()
        assert result["threshold"] == 365
        assert result["page_size"] == 100
