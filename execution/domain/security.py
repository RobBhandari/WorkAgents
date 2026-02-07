"""
Security domain models - Vulnerabilities and security metrics

Represents security vulnerabilities and metrics for tracking:
    - Vulnerability counts by severity
    - 70% reduction target progress
    - Critical/High vulnerability trends
    - Product-level security posture
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from .metrics import MetricSnapshot


@dataclass
class Vulnerability:
    """
    Represents a security vulnerability from ArmorCode.

    Attributes:
        id: Vulnerability ID
        title: Vulnerability title/description
        severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW)
        status: Current status (Open, In Progress, Closed, etc.)
        product: Product/service name
        age_days: Days since first discovered
        cve_id: Optional CVE identifier

    Example:
        vuln = Vulnerability(
            id="VUL-2026-0123",
            title="SQL Injection in auth endpoint",
            severity="CRITICAL",
            status="Open",
            product="API Gateway",
            age_days=5,
            cve_id="CVE-2026-1234"
        )

        if vuln.is_critical_or_high:
            print(f"HIGH SEVERITY: {vuln.title}")

        if vuln.is_aging:
            print(f"Vulnerability has been open for {vuln.age_days} days")
    """
    id: str
    title: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    status: str
    product: str
    age_days: int
    cve_id: Optional[str] = None

    @property
    def is_critical(self) -> bool:
        """Check if vulnerability is CRITICAL severity"""
        return self.severity == 'CRITICAL'

    @property
    def is_high(self) -> bool:
        """Check if vulnerability is HIGH severity"""
        return self.severity == 'HIGH'

    @property
    def is_critical_or_high(self) -> bool:
        """
        Check if vulnerability is CRITICAL or HIGH severity.

        This is the threshold for the 70% reduction target.

        Returns:
            True if severity is CRITICAL or HIGH
        """
        return self.severity in ('CRITICAL', 'HIGH')

    @property
    def is_open(self) -> bool:
        """Check if vulnerability is currently open"""
        closed_statuses = {'Closed', 'Resolved', 'Fixed', 'Accepted Risk'}
        return self.status not in closed_statuses

    @property
    def is_aging(self, threshold_days: int = 14) -> bool:
        """
        Check if vulnerability has been open longer than threshold.

        Args:
            threshold_days: Age threshold in days (default: 14)

        Returns:
            True if open and older than threshold
        """
        return self.is_open and self.age_days > threshold_days

    def severity_score(self) -> int:
        """
        Get numeric severity score for sorting/prioritization.

        Returns:
            4 for CRITICAL, 3 for HIGH, 2 for MEDIUM, 1 for LOW
        """
        severity_map = {
            'CRITICAL': 4,
            'HIGH': 3,
            'MEDIUM': 2,
            'LOW': 1
        }
        return severity_map.get(self.severity, 0)


@dataclass(kw_only=True)
class SecurityMetrics(MetricSnapshot):
    """
    Security metrics for a product at a point in time.

    Tracks vulnerability counts by severity and progress toward reduction targets.

    Attributes:
        timestamp: When metrics were captured
        project: Product/service name
        total_vulnerabilities: Total count of all open vulnerabilities
        critical: Count of CRITICAL vulnerabilities
        high: Count of HIGH vulnerabilities
        medium: Count of MEDIUM vulnerabilities
        low: Count of LOW vulnerabilities
        baseline: Optional baseline count for tracking 70% reduction
        target: Optional target count (30% of baseline)

    Example:
        metrics = SecurityMetrics(
            timestamp=datetime.now(),
            project="API Gateway",
            total_vulnerabilities=42,
            critical=3,
            high=12,
            medium=20,
            low=7,
            baseline=100,
            target=30
        )

        print(f"Critical/High: {metrics.critical_high_count}")
        print(f"Progress to target: {metrics.reduction_progress()}%")

        if metrics.has_critical:
            print("CRITICAL vulnerabilities need immediate attention!")
    """
    total_vulnerabilities: int
    critical: int
    high: int
    medium: int = 0
    low: int = 0
    baseline: Optional[int] = None  # For 70% reduction tracking
    target: Optional[int] = None    # 30% of baseline

    @property
    def critical_high_count(self) -> int:
        """
        Get combined count of CRITICAL and HIGH vulnerabilities.

        This is the key metric for the 70% reduction target.

        Returns:
            Sum of critical and high severity vulnerabilities
        """
        return self.critical + self.high

    @property
    def has_critical(self) -> bool:
        """Check if there are any CRITICAL vulnerabilities"""
        return self.critical > 0

    @property
    def has_high(self) -> bool:
        """Check if there are any HIGH vulnerabilities"""
        return self.high > 0

    def reduction_progress(self) -> Optional[float]:
        """
        Calculate progress toward 70% reduction target.

        Formula: (baseline - current) / (baseline - target) * 100

        Returns:
            Percentage progress (0-100+), or None if baseline not set

        Example:
            Baseline: 100, Target: 30 (70% reduction), Current: 55
            Progress: (100-55)/(100-30) = 45/70 = 64.3%
        """
        if self.baseline is None or self.target is None:
            return None

        if self.baseline <= self.target:
            return 100.0  # Already at or below target

        current = self.critical_high_count
        reduction_needed = self.baseline - self.target
        reduction_achieved = self.baseline - current

        progress = (reduction_achieved / reduction_needed) * 100
        return min(max(progress, 0), 100)  # Clamp to 0-100

    def is_on_track(self) -> Optional[bool]:
        """
        Check if on track to meet 70% reduction target.

        Simplified check: Are we at or below target?

        Returns:
            True if at or below target, False if above, None if no target set
        """
        if self.target is None:
            return None

        return self.critical_high_count <= self.target

    def __str__(self) -> str:
        """String representation for logging/debugging"""
        return (
            f"SecurityMetrics(product={self.project}, "
            f"total={self.total_vulnerabilities}, "
            f"critical={self.critical}, high={self.high})"
        )
