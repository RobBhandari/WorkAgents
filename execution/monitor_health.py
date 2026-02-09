#!/usr/bin/env python3
"""
Health Monitoring Script

Checks:
- Data freshness (metrics files not stale)
- Dashboard availability (HTML files exist and valid)
- Performance of monitoring checks themselves

Run this script periodically (via cron or scheduled task) to monitor system health.

Usage:
    python execution/monitor_health.py

Environment Variables:
    SLACK_WEBHOOK_URL: Slack webhook for alerts (optional)
    SENTRY_DSN: Sentry DSN for error tracking (optional)
"""

from pathlib import Path

from execution.core import (
    check_dashboard_availability,
    check_data_freshness,
    get_logger,
    send_slack_notification,
    setup_logging,
    setup_observability,
    track_performance,
)

logger = get_logger(__name__)


def check_metrics_freshness(max_age_hours: float = 25.0) -> tuple[int, int]:
    """
    Check freshness of all metric history files.

    Args:
        max_age_hours: Maximum age before considered stale

    Returns:
        Tuple of (fresh_count, stale_count)
    """
    observatory_dir = Path(".tmp/observatory")
    metric_files = [
        "quality_history.json",
        "security_history.json",
        "flow_history.json",
    ]

    fresh_count = 0
    stale_count = 0

    for filename in metric_files:
        file_path = observatory_dir / filename
        if file_path.exists():
            is_fresh, age = check_data_freshness(file_path, max_age_hours)
            if is_fresh:
                fresh_count += 1
            else:
                stale_count += 1
        else:
            logger.warning("Metric file not found", extra={"file": filename})
            stale_count += 1

    return fresh_count, stale_count


def check_all_dashboards() -> tuple[int, int]:
    """
    Check availability of all dashboard files.

    Returns:
        Tuple of (available_count, unavailable_count)
    """
    dashboard_dir = Path(".tmp/observatory/dashboards")
    dashboards = [
        "security.html",
        "executive_summary.html",
        "trends.html",
    ]

    available_count = 0
    unavailable_count = 0

    for filename in dashboards:
        file_path = dashboard_dir / filename
        if check_dashboard_availability(file_path):
            available_count += 1
        else:
            unavailable_count += 1

    return available_count, unavailable_count


def main() -> int:
    """
    Run health monitoring checks.

    Returns:
        Exit code (0 = healthy, 1 = issues detected)
    """
    # Setup logging and observability
    setup_logging(level="INFO", json_output=False)
    setup_observability(environment="production", enable_sentry=False, enable_slack=True)

    logger.info("=" * 60)
    logger.info("Health Monitoring Check - Starting")
    logger.info("=" * 60)

    issues_detected = 0

    # Check metrics freshness
    with track_performance("metrics_freshness_check", alert_threshold_ms=2000):
        fresh_count, stale_count = check_metrics_freshness(max_age_hours=25.0)

        logger.info(
            "Metrics freshness check complete",
            extra={
                "fresh_count": fresh_count,
                "stale_count": stale_count,
                "total_checked": fresh_count + stale_count,
            },
        )

        if stale_count > 0:
            issues_detected += stale_count
            logger.warning(f"{stale_count} stale metric files detected")

    # Check dashboard availability
    with track_performance("dashboard_availability_check", alert_threshold_ms=1000):
        available_count, unavailable_count = check_all_dashboards()

        logger.info(
            "Dashboard availability check complete",
            extra={
                "available_count": available_count,
                "unavailable_count": unavailable_count,
                "total_checked": available_count + unavailable_count,
            },
        )

        if unavailable_count > 0:
            issues_detected += unavailable_count
            logger.warning(f"{unavailable_count} dashboards unavailable")

    # Summary
    logger.info("=" * 60)
    if issues_detected == 0:
        logger.info("✅ Health Check PASSED - All systems operational")
        send_slack_notification(
            "Health check passed - All systems operational",
            severity="info",
            context={
                "fresh_metrics": fresh_count,
                "available_dashboards": available_count,
            },
        )
        return 0
    else:
        logger.error(
            f"❌ Health Check FAILED - {issues_detected} issues detected",
            extra={
                "stale_metrics": stale_count,
                "unavailable_dashboards": unavailable_count,
                "total_issues": issues_detected,
            },
        )
        send_slack_notification(
            f"Health check failed - {issues_detected} issues detected",
            severity="error",
            context={
                "stale_metrics": stale_count,
                "unavailable_dashboards": unavailable_count,
            },
        )
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        exit(exit_code)
    except Exception as e:
        logger.error("Health monitoring script failed", exc_info=True)
        send_slack_notification(
            "Health monitoring script crashed",
            severity="critical",
            context={"error": str(e)},
        )
        exit(2)
