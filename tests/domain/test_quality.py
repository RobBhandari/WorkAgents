"""
Tests for quality domain models

Tests Bug and QualityMetrics classes.
"""

import pytest
from datetime import datetime
from execution.domain.quality import Bug, QualityMetrics


class TestBug:
    """Tests for Bug domain model"""

    def test_bug_creation(self, sample_bug):
        """Test creating a Bug instance"""
        assert sample_bug.id == 12345
        assert sample_bug.title == "Sample bug for testing"
        assert sample_bug.state == "Active"
        assert sample_bug.priority == 1
        assert sample_bug.age_days == 23

    def test_bug_is_open(self, sample_bug):
        """Test is_open property for active bug"""
        assert sample_bug.is_open is True

    def test_bug_is_closed(self, sample_closed_bug):
        """Test is_open property for closed bug"""
        assert sample_closed_bug.is_open is False

    def test_bug_is_high_priority(self, sample_bug):
        """Test is_high_priority for P1 bug"""
        assert sample_bug.is_high_priority is True

    def test_bug_not_high_priority(self, sample_closed_bug):
        """Test is_high_priority for P2 bug"""
        # P2 is still high priority
        assert sample_closed_bug.is_high_priority is True

    def test_bug_is_aging_default_threshold(self, sample_bug):
        """Test is_aging with default 30-day threshold"""
        # Bug is 23 days old, not aging yet
        assert sample_bug.is_aging() is False

    def test_bug_is_aging_custom_threshold(self, sample_bug):
        """Test is_aging with custom threshold"""
        # Bug is 23 days old, should be aging with 20-day threshold
        assert sample_bug.is_aging(threshold_days=20) is True

    def test_closed_bug_not_aging(self, sample_closed_bug):
        """Test that closed bugs are not considered aging"""
        assert sample_closed_bug.is_aging() is False


class TestQualityMetrics:
    """Tests for QualityMetrics domain model"""

    def test_quality_metrics_creation(self, sample_quality_metrics):
        """Test creating QualityMetrics instance"""
        metrics = sample_quality_metrics
        assert metrics.project == "Test Project"
        assert metrics.open_bugs == 50
        assert metrics.closed_this_week == 10
        assert metrics.created_this_week == 5
        assert metrics.net_change == -5

    def test_is_improving_positive(self, sample_quality_metrics):
        """Test is_improving when net_change is negative"""
        assert sample_quality_metrics.is_improving is True

    def test_is_improving_negative(self, sample_timestamp):
        """Test is_improving when net_change is positive"""
        metrics = QualityMetrics(
            timestamp=sample_timestamp,
            project="Test",
            open_bugs=55,
            closed_this_week=5,
            created_this_week=10,
            net_change=5,
        )
        assert metrics.is_improving is False

    def test_has_critical_bugs(self, sample_quality_metrics):
        """Test has_critical_bugs when P1 count > 0"""
        assert sample_quality_metrics.has_critical_bugs is True

    def test_no_critical_bugs(self, sample_timestamp):
        """Test has_critical_bugs when P1 count is 0"""
        metrics = QualityMetrics(
            timestamp=sample_timestamp,
            project="Test",
            open_bugs=10,
            closed_this_week=5,
            created_this_week=3,
            net_change=-2,
            p1_count=0,
        )
        assert metrics.has_critical_bugs is False

    def test_high_priority_count(self, sample_quality_metrics):
        """Test high_priority_count calculation"""
        # P1=2, P2=8, total=10
        assert sample_quality_metrics.high_priority_count == 10

    def test_closure_rate(self, sample_quality_metrics):
        """Test closure_rate calculation"""
        # 10 closed / 50 open = 20%
        assert sample_quality_metrics.closure_rate == 20.0

    def test_closure_rate_no_bugs(self, sample_timestamp):
        """Test closure_rate when no bugs"""
        metrics = QualityMetrics(
            timestamp=sample_timestamp,
            project="Test",
            open_bugs=0,
            closed_this_week=0,
            created_this_week=0,
            net_change=0,
        )
        assert metrics.closure_rate is None

    def test_str_representation(self, sample_quality_metrics):
        """Test string representation"""
        str_repr = str(sample_quality_metrics)
        assert "Test Project" in str_repr
        assert "open=50" in str_repr
        assert "net_change=-5" in str_repr
