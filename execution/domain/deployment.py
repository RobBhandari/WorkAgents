"""
Deployment domain models - DORA metrics and deployment data

Represents deployment metrics for tracking:
    - Deployment frequency (deploys/week)
    - Build success rate (%)
    - Build duration (median, P85)
    - Lead time for changes (median, P85)
"""

from dataclasses import dataclass


@dataclass
class DeploymentFrequency:
    """
    Deployment frequency metrics.

    Attributes:
        total_successful_builds: Count of successful builds in lookback period
        deployments_per_week: Average deployments per week
        lookback_days: Number of days analyzed (typically 90)
        pipeline_count: Number of pipelines with deployments
    """

    total_successful_builds: int
    deployments_per_week: float
    lookback_days: int
    pipeline_count: int

    @property
    def is_active(self) -> bool:
        """
        Check if project has recent deployments.

        Returns:
            True if deployments_per_week > 0, False otherwise

        Example:
            >>> freq = DeploymentFrequency(total_successful_builds=10, deployments_per_week=2.5, lookback_days=90, pipeline_count=1)
            >>> freq.is_active
            True
        """
        return self.deployments_per_week > 0

    @property
    def is_frequent(self) -> bool:
        """
        Check if deployment frequency is high (≥1 per week).

        Returns:
            True if deployments_per_week >= 1.0, False otherwise

        Example:
            >>> freq = DeploymentFrequency(total_successful_builds=15, deployments_per_week=1.5, lookback_days=90, pipeline_count=1)
            >>> freq.is_frequent
            True
        """
        return self.deployments_per_week >= 1.0


@dataclass
class BuildSuccessRate:
    """
    Build success rate metrics.

    Attributes:
        total_builds: Total completed builds
        succeeded: Successfully completed builds
        failed: Failed builds
        success_rate_pct: Success rate percentage
    """

    total_builds: int
    succeeded: int
    failed: int
    success_rate_pct: float

    @property
    def is_stable(self) -> bool:
        """
        Check if build success rate is stable (≥90%).

        Returns:
            True if success_rate_pct >= 90.0, False otherwise

        Example:
            >>> rate = BuildSuccessRate(total_builds=100, succeeded=95, failed=5, success_rate_pct=95.0)
            >>> rate.is_stable
            True
        """
        return self.success_rate_pct >= 90.0

    @property
    def is_acceptable(self) -> bool:
        """
        Check if build success rate is acceptable (≥70%).

        Returns:
            True if success_rate_pct >= 70.0, False otherwise

        Example:
            >>> rate = BuildSuccessRate(total_builds=100, succeeded=75, failed=25, success_rate_pct=75.0)
            >>> rate.is_acceptable
            True
        """
        return self.success_rate_pct >= 70.0


@dataclass
class BuildDuration:
    """
    Build duration metrics.

    Attributes:
        median_minutes: Median build duration in minutes
        p85_minutes: 85th percentile duration in minutes
    """

    median_minutes: float
    p85_minutes: float

    @property
    def is_fast(self) -> bool:
        """
        Check if median build is fast (≤10 minutes).

        Returns:
            True if median_minutes <= 10.0, False otherwise

        Example:
            >>> duration = BuildDuration(median_minutes=8.5, p85_minutes=12.0)
            >>> duration.is_fast
            True
        """
        return self.median_minutes <= 10.0


@dataclass
class LeadTimeForChanges:
    """
    Lead time for changes metrics (commit to deploy).

    Attributes:
        median_hours: Median lead time in hours
        p85_hours: 85th percentile lead time in hours
    """

    median_hours: float
    p85_hours: float

    @property
    def is_elite(self) -> bool:
        """
        Check if lead time is elite (<1 hour).

        Returns:
            True if median_hours < 1.0, False otherwise

        Example:
            >>> lead_time = LeadTimeForChanges(median_hours=0.5, p85_hours=1.2)
            >>> lead_time.is_elite
            True
        """
        return self.median_hours < 1.0

    @property
    def is_high(self) -> bool:
        """
        Check if lead time is high (1 day to 1 week).

        Returns:
            True if median_hours is between 24.0 and 168.0, False otherwise

        Example:
            >>> lead_time = LeadTimeForChanges(median_hours=48.0, p85_hours=72.0)
            >>> lead_time.is_high
            True
        """
        return 24.0 <= self.median_hours <= 168.0


@dataclass
class DeploymentMetrics:
    """
    Complete deployment metrics for a single project.

    Represents all DORA metrics and deployment health indicators
    for a project over a lookback period (typically 90 days).

    Attributes:
        project_name: Project name
        deployment_frequency: Deployment frequency data
        build_success_rate: Build success data
        build_duration: Build duration data
        lead_time_for_changes: Lead time data

    Example:
        metrics = DeploymentMetrics(
            project_name="API Gateway",
            deployment_frequency=DeploymentFrequency(
                total_successful_builds=45,
                deployments_per_week=3.5,
                lookback_days=90,
                pipeline_count=2
            ),
            build_success_rate=BuildSuccessRate(
                total_builds=50,
                succeeded=45,
                failed=5,
                success_rate_pct=90.0
            ),
            build_duration=BuildDuration(
                median_minutes=8.5,
                p85_minutes=12.3
            ),
            lead_time_for_changes=LeadTimeForChanges(
                median_hours=2.5,
                p85_hours=6.0
            )
        )

        if metrics.is_healthy:
            print(f"{metrics.project_name} is healthy!")
    """

    project_name: str
    deployment_frequency: DeploymentFrequency
    build_success_rate: BuildSuccessRate
    build_duration: BuildDuration
    lead_time_for_changes: LeadTimeForChanges

    @property
    def is_healthy(self) -> bool:
        """
        Check if deployment pipeline is healthy.

        Healthy = ≥90% success rate + ≥1 deploy/week

        Returns:
            True if deployment pipeline is healthy, False otherwise

        Example:
            >>> metrics = DeploymentMetrics(...)  # With 95% success, 3 deploys/week
            >>> metrics.is_healthy
            True
        """
        return self.build_success_rate.is_stable and self.deployment_frequency.is_frequent

    @property
    def needs_attention(self) -> bool:
        """
        Check if deployment pipeline needs attention.

        Needs attention = low success rate or infrequent deployments

        Returns:
            True if pipeline needs attention, False otherwise

        Example:
            >>> metrics = DeploymentMetrics(...)  # With 75% success, 0.5 deploys/week
            >>> metrics.needs_attention
            True
        """
        return not self.is_healthy and self.deployment_frequency.is_active

    @property
    def is_inactive(self) -> bool:
        """
        Check if project has no recent deployments.

        Returns:
            True if project has no deployments, False otherwise

        Example:
            >>> metrics = DeploymentMetrics(...)  # With 0 deploys/week
            >>> metrics.is_inactive
            True
        """
        return not self.deployment_frequency.is_active

    @property
    def status(self) -> str:
        """
        Get deployment status label.

        Returns:
            Status string: "Good", "Caution", "Action Needed", or "Inactive"
        """
        if self.is_inactive:
            return "Inactive"
        elif self.is_healthy:
            return "Good"
        elif self.build_success_rate.is_acceptable and self.deployment_frequency.deployments_per_week >= 0.5:
            return "Caution"
        else:
            return "Action Needed"

    @property
    def status_class(self) -> str:
        """
        Get CSS class for status.

        Returns:
            CSS class string for styling
        """
        status_map: dict[str, str] = {
            "Good": "good",
            "Caution": "caution",
            "Action Needed": "action",
            "Inactive": "inactive",
        }
        return status_map.get(self.status, "inactive")


def from_json(project_data: dict) -> DeploymentMetrics:
    """
    Create DeploymentMetrics from JSON data structure.

    Args:
        project_data: Project data dictionary from deployment_history.json

    Returns:
        DeploymentMetrics instance

    Example:
        with open('deployment_history.json') as f:
            data = json.load(f)
            latest_week = data['weeks'][-1]

            for project_data in latest_week['projects']:
                metrics = from_json(project_data)
                print(f"{metrics.project_name}: {metrics.status}")
    """
    # Extract deployment frequency
    deploy_freq_data = project_data.get("deployment_frequency", {})
    deployment_frequency = DeploymentFrequency(
        total_successful_builds=deploy_freq_data.get("total_successful_builds", 0),
        deployments_per_week=deploy_freq_data.get("deployments_per_week", 0.0),
        lookback_days=deploy_freq_data.get("lookback_days", 90),
        pipeline_count=deploy_freq_data.get("pipeline_count", 0),
    )

    # Extract build success rate
    success_rate_data = project_data.get("build_success_rate", {})
    build_success_rate = BuildSuccessRate(
        total_builds=success_rate_data.get("total_builds", 0),
        succeeded=success_rate_data.get("succeeded", 0),
        failed=success_rate_data.get("failed", 0),
        success_rate_pct=success_rate_data.get("success_rate_pct", 0.0),
    )

    # Extract build duration
    duration_data = project_data.get("build_duration", {})
    build_duration = BuildDuration(
        median_minutes=duration_data.get("median_minutes") or 0.0, p85_minutes=duration_data.get("p85_minutes") or 0.0
    )

    # Extract lead time
    lead_time_data = project_data.get("lead_time_for_changes", {})
    lead_time_for_changes = LeadTimeForChanges(
        median_hours=lead_time_data.get("median_hours") or 0.0, p85_hours=lead_time_data.get("p85_hours") or 0.0
    )

    return DeploymentMetrics(
        project_name=project_data["project_name"],
        deployment_frequency=deployment_frequency,
        build_success_rate=build_success_rate,
        build_duration=build_duration,
        lead_time_for_changes=lead_time_for_changes,
    )
