"""
Security domain models - Vulnerabilities and security metrics

Represents security vulnerabilities and metrics for tracking:
    - Vulnerability counts by severity
    - 70% reduction target progress
    - Critical/High vulnerability trends
    - Product-level security posture
"""

from dataclasses import dataclass

from .metrics import MetricSnapshot

# Source tool → bucket mapping for security dashboard grouping
SOURCE_BUCKET_MAP: dict[str, str] = {
    "Mend": "CODE",
    "SonarQube": "CODE",
    "Custom-Pentest": "CODE",
    "Prisma Cloud Twistlock": "CLOUD",
    "Prisma Cloud Redlock": "CLOUD",
    "Prisma Cloud Compute": "CLOUD",
    "Cortex XDR": "INFRASTRUCTURE",
    "Tenable Infrastructure": "INFRASTRUCTURE",
    "Tenable Vulnerability Management": "INFRASTRUCTURE",
    "AppCheck": "INFRASTRUCTURE",
    "BitSight": "INFRASTRUCTURE",
}
BUCKET_ORDER: list[str] = ["CODE", "CLOUD", "INFRASTRUCTURE", "Other"]


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
    cve_id: str | None = None

    @property
    def is_critical(self) -> bool:
        """
        Check if vulnerability is CRITICAL severity.

        Returns:
            True if severity is CRITICAL, False otherwise

        Example:
            >>> vuln = Vulnerability(id="V1", title="SQL Injection", severity="CRITICAL", status="Open", product="API", age_days=5)
            >>> vuln.is_critical
            True
        """
        return self.severity == "CRITICAL"

    @property
    def is_high(self) -> bool:
        """
        Check if vulnerability is HIGH severity.

        Returns:
            True if severity is HIGH, False otherwise

        Example:
            >>> vuln = Vulnerability(id="V2", title="XSS", severity="HIGH", status="Open", product="Web", age_days=10)
            >>> vuln.is_high
            True
        """
        return self.severity == "HIGH"

    @property
    def is_critical_or_high(self) -> bool:
        """
        Check if vulnerability is CRITICAL or HIGH severity.

        This is the threshold for the 70% reduction target.

        Returns:
            True if severity is CRITICAL or HIGH
        """
        return self.severity in ("CRITICAL", "HIGH")

    @property
    def is_open(self) -> bool:
        """
        Check if vulnerability is currently open.

        Returns:
            True if status is not in closed/resolved states, False otherwise

        Example:
            >>> vuln = Vulnerability(id="V1", title="XSS", severity="HIGH", status="Open", product="Web", age_days=10)
            >>> vuln.is_open
            True
        """
        closed_statuses = {"Closed", "Resolved", "Fixed", "Accepted Risk"}
        return self.status not in closed_statuses

    def is_aging(self, threshold_days: int = 14) -> bool:
        """
        Check if vulnerability has been open longer than threshold.

        Args:
            threshold_days: Age threshold in days (default: 14)

        Returns:
            True if open and older than threshold, False otherwise

        Example:
            >>> vuln = Vulnerability(id="V1", title="XSS", severity="HIGH", status="Open", product="Web", age_days=20)
            >>> vuln.is_aging(14)
            True
        """
        return self.is_open and self.age_days > threshold_days

    def severity_score(self) -> int:
        """
        Get numeric severity score for sorting/prioritization.

        Returns:
            4 for CRITICAL, 3 for HIGH, 2 for MEDIUM, 1 for LOW, 0 for unknown

        Example:
            >>> vuln = Vulnerability(id="V1", title="XSS", severity="CRITICAL", status="Open", product="Web", age_days=5)
            >>> vuln.severity_score()
            4
        """
        severity_map = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
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
    baseline: int | None = None  # For 70% reduction tracking
    target: int | None = None  # 30% of baseline

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
        """
        Check if there are any CRITICAL vulnerabilities.

        Returns:
            True if critical count > 0, False otherwise

        Example:
            >>> metrics = SecurityMetrics(timestamp=datetime.now(), project="API", total_vulnerabilities=10, critical=2, high=5)
            >>> metrics.has_critical
            True
        """
        return self.critical > 0

    @property
    def has_high(self) -> bool:
        """
        Check if there are any HIGH vulnerabilities.

        Returns:
            True if high count > 0, False otherwise

        Example:
            >>> metrics = SecurityMetrics(timestamp=datetime.now(), project="API", total_vulnerabilities=10, critical=0, high=5)
            >>> metrics.has_high
            True
        """
        return self.high > 0

    def reduction_progress(self) -> float | None:
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

        current: int = self.critical_high_count
        reduction_needed: int = self.baseline - self.target
        reduction_achieved: int = self.baseline - current

        progress: float = (reduction_achieved / reduction_needed) * 100
        return min(max(progress, 0), 100)  # Clamp to 0-100

    def is_on_track(self) -> bool | None:
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
        """
        String representation for logging/debugging.

        Returns:
            Formatted string with product, total, critical, and high counts

        Example:
            >>> metrics = SecurityMetrics(timestamp=datetime.now(), project="API", total_vulnerabilities=42, critical=3, high=12)
            >>> str(metrics)
            'SecurityMetrics(product=API, total=42, critical=3, high=12)'
        """
        return (
            f"SecurityMetrics(product={self.project}, "
            f"total={self.total_vulnerabilities}, "
            f"critical={self.critical}, high={self.high})"
        )
