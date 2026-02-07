"""
Tests for security domain models

Tests Vulnerability and SecurityMetrics classes.
"""

import pytest
from datetime import datetime
from execution.domain.security import Vulnerability, SecurityMetrics


class TestVulnerability:
    """Tests for Vulnerability domain model"""

    def test_vulnerability_creation(self, sample_vulnerability):
        """Test creating a Vulnerability instance"""
        assert sample_vulnerability.id == "VUL-2026-0123"
        assert sample_vulnerability.severity == "CRITICAL"
        assert sample_vulnerability.status == "Open"
        assert sample_vulnerability.product == "API Gateway"

    def test_is_critical(self, sample_vulnerability):
        """Test is_critical property"""
        assert sample_vulnerability.is_critical is True

    def test_is_high(self, sample_vulnerability):
        """Test is_high property"""
        # This is CRITICAL, not HIGH
        assert sample_vulnerability.is_high is False

    def test_is_critical_or_high_critical(self, sample_vulnerability):
        """Test is_critical_or_high for CRITICAL vuln"""
        assert sample_vulnerability.is_critical_or_high is True

    def test_is_critical_or_high_high(self):
        """Test is_critical_or_high for HIGH vuln"""
        vuln = Vulnerability(
            id="VUL-123", title="XSS vulnerability", severity="HIGH", status="Open", product="Web App", age_days=10
        )
        assert vuln.is_critical_or_high is True

    def test_is_critical_or_high_medium(self):
        """Test is_critical_or_high for MEDIUM vuln"""
        vuln = Vulnerability(
            id="VUL-123", title="Info disclosure", severity="MEDIUM", status="Open", product="API", age_days=5
        )
        assert vuln.is_critical_or_high is False

    def test_severity_score(self, sample_vulnerability):
        """Test severity_score calculation"""
        assert sample_vulnerability.severity_score() == 4  # CRITICAL


class TestSecurityMetrics:
    """Tests for SecurityMetrics domain model"""

    def test_security_metrics_creation(self, sample_security_metrics):
        """Test creating SecurityMetrics instance"""
        metrics = sample_security_metrics
        assert metrics.project == "API Gateway"
        assert metrics.total_vulnerabilities == 42
        assert metrics.critical == 3
        assert metrics.high == 12

    def test_critical_high_count(self, sample_security_metrics):
        """Test critical_high_count calculation"""
        # 3 critical + 12 high = 15
        assert sample_security_metrics.critical_high_count == 15

    def test_has_critical(self, sample_security_metrics):
        """Test has_critical when critical > 0"""
        assert sample_security_metrics.has_critical is True

    def test_reduction_progress(self, sample_security_metrics):
        """Test reduction_progress calculation"""
        # Baseline: 100, Target: 30, Current: 15 (critical+high)
        # Progress: (100-15)/(100-30) = 85/70 = 121.4% (but clamped to 100)
        progress = sample_security_metrics.reduction_progress()
        assert progress == 100.0  # Clamped to 100

    def test_is_on_track(self, sample_security_metrics):
        """Test is_on_track when below target"""
        # Current critical+high = 15, target = 30
        assert sample_security_metrics.is_on_track() is True

    def test_str_representation(self, sample_security_metrics):
        """Test string representation"""
        str_repr = str(sample_security_metrics)
        assert "API Gateway" in str_repr
        assert "total=42" in str_repr
