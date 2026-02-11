"""
Collector Health Dashboard Generator

Generates monitoring dashboard for collector pipeline health.
Tracks execution time, API usage, rate limiting, and failures.

Usage:
    from execution.dashboards.collector_health import generate_collector_health_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/collector_health.html')
    generate_collector_health_dashboard(output_path)
"""

import json
from datetime import datetime
from pathlib import Path

from execution.core import get_logger
from execution.dashboards.renderer import render_dashboard
from execution.domain.collector_health import CollectorHealthSummary, from_json
from execution.framework import get_dashboard_framework

logger = get_logger(__name__)


def generate_collector_health_dashboard(output_path: Path | None = None) -> str:
    """
    Generate collector health monitoring dashboard HTML.

    This is the main entry point for generating the collector health dashboard.
    It loads performance data, processes it, and renders the HTML template.

    Args:
        output_path: Optional path to write HTML file

    Returns:
        Generated HTML string

    Raises:
        FileNotFoundError: If collector_performance_history.json doesn't exist

    Example:
        from pathlib import Path
        html = generate_collector_health_dashboard(
            Path('.tmp/observatory/dashboards/collector_health.html')
        )
        logger.info("Dashboard generated", extra={"html_size": len(html)})
    """
    logger.info("Generating collector health dashboard")

    # Step 1: Load data
    logger.info("Loading collector performance data")
    metrics_list, collection_date = _load_collector_performance_data()
    logger.info("Collector performance data loaded", extra={"collector_count": len(metrics_list)})

    # Step 2: Calculate summary statistics
    logger.info("Calculating summary metrics")
    summary_stats = _calculate_summary(metrics_list)

    # Step 3: Prepare template context
    logger.info("Preparing dashboard components")
    context = _build_context(metrics_list, summary_stats, collection_date)

    # Step 4: Render template
    logger.info("Rendering HTML template")
    html = render_dashboard("dashboards/collector_health_dashboard.html", context)

    # Write to file if specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info("Dashboard written to file", extra={"path": str(output_path)})

    logger.info("Collector health dashboard generated", extra={"html_size": len(html)})
    return html


def _load_collector_performance_data() -> tuple[list, str]:
    """
    Load collector performance metrics from history file.

    Returns:
        Tuple of (metrics_list, collection_date)

    Raises:
        FileNotFoundError: If collector_performance_history.json doesn't exist
    """
    history_file = Path(".tmp/observatory/collector_performance_history.json")

    if not history_file.exists():
        raise FileNotFoundError(
            f"Collector performance history file not found: {history_file}\n"
            "Run: python execution/collectors/ado_quality_metrics.py"
        )

    with history_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not data.get("weeks") or len(data["weeks"]) == 0:
        raise ValueError("No collector performance data found in history file")

    # Get latest week's data
    latest_week = data["weeks"][-1]
    collectors = latest_week.get("collectors", [])
    collection_date = latest_week.get("week_date", "Unknown")

    # Convert to domain models
    metrics_list = [from_json(collector) for collector in collectors]

    return metrics_list, collection_date


def _calculate_summary(metrics_list: list) -> dict:
    """
    Calculate aggregated summary statistics.

    Args:
        metrics_list: List of CollectorPerformanceMetrics instances

    Returns:
        Dictionary with summary statistics
    """
    if not metrics_list:
        return {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "success_rate_pct": 0.0,
            "avg_execution_time_ms": 0.0,
            "total_api_calls": 0,
            "total_rate_limit_hits": 0,
            "slowest_collector": None,
            "slowest_collector_time_ms": None,
        }

    total_runs = len(metrics_list)
    successful_runs = sum(1 for m in metrics_list if m.success)
    failed_runs = total_runs - successful_runs

    avg_execution_time_ms = sum(m.execution_time_ms for m in metrics_list) / total_runs
    total_api_calls = sum(m.api_call_count for m in metrics_list)
    total_rate_limit_hits = sum(m.rate_limit_hits for m in metrics_list)

    slowest = max(metrics_list, key=lambda m: m.execution_time_ms)

    # Create summary using domain model
    summary = CollectorHealthSummary(
        total_runs=total_runs,
        successful_runs=successful_runs,
        failed_runs=failed_runs,
        avg_execution_time_ms=avg_execution_time_ms,
        total_api_calls=total_api_calls,
        total_rate_limit_hits=total_rate_limit_hits,
        slowest_collector=slowest.collector_name,
        slowest_collector_time_ms=slowest.execution_time_ms,
    )

    return {
        "total_runs": total_runs,
        "successful_runs": successful_runs,
        "failed_runs": failed_runs,
        "success_rate_pct": summary.success_rate_pct,
        "failure_rate_pct": summary.failure_rate_pct,
        "avg_execution_time_ms": avg_execution_time_ms,
        "avg_execution_time_sec": avg_execution_time_ms / 1000,
        "total_api_calls": total_api_calls,
        "total_rate_limit_hits": total_rate_limit_hits,
        "slowest_collector": slowest.collector_name,
        "slowest_collector_time_ms": slowest.execution_time_ms,
        "slowest_collector_time_sec": slowest.execution_time_ms / 1000,
        "overall_status": summary.overall_status,
        "overall_status_class": "good" if summary.overall_status == "Good" else "action",
    }


def _build_context(metrics_list: list, summary: dict, collection_date: str) -> dict:
    """
    Build template context with HTML components.

    Args:
        metrics_list: List of CollectorPerformanceMetrics instances
        summary: Summary statistics dictionary
        collection_date: Date of data collection

    Returns:
        Dictionary with template variables
    """
    # CRITICAL: Get framework CSS/JS
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#667eea",  # Standard purple-blue
        header_gradient_end="#764ba2",  # Standard purple
        include_table_scroll=False,
        include_expandable_rows=False,
        include_glossary=True,
    )

    # Build summary cards
    summary_cards = [
        {
            "title": "Total Runs",
            "value": summary["total_runs"],
            "unit": "collectors",
            "status": "info",
            "trend": f"{summary['successful_runs']} successful",
        },
        {
            "title": "Success Rate",
            "value": f"{summary['success_rate_pct']:.1f}%",
            "status": "good" if summary["success_rate_pct"] >= 90 else "action",
            "trend": f"{summary['failed_runs']} failed" if summary["failed_runs"] > 0 else "No failures",
        },
        {
            "title": "Avg Execution Time",
            "value": f"{summary['avg_execution_time_sec']:.1f}",
            "unit": "seconds",
            "status": "good" if summary["avg_execution_time_ms"] < 60000 else "caution",
            "trend": f"Slowest: {summary['slowest_collector_time_sec']:.1f}s",
        },
        {
            "title": "Total API Calls",
            "value": summary["total_api_calls"],
            "unit": "requests",
            "status": "info",
            "trend": f"~{summary['total_api_calls'] // summary['total_runs']} per collector",
        },
        {
            "title": "Rate Limit Hits",
            "value": summary["total_rate_limit_hits"],
            "status": "good" if summary["total_rate_limit_hits"] == 0 else "action",
            "trend": "No rate limits" if summary["total_rate_limit_hits"] == 0 else "⚠️ Throttled",
        },
    ]

    # Build collector table rows (sorted by execution time, slowest first)
    collector_rows = []
    for metric in sorted(metrics_list, key=lambda m: m.execution_time_ms, reverse=True):
        collector_rows.append(
            {
                "collector_name": metric.collector_name.capitalize(),
                "execution_time": f"{metric.execution_time_seconds:.1f}s",
                "status": metric.status,
                "status_class": metric.status_class,
                "project_count": metric.project_count,
                "api_calls": metric.api_call_count,
                "rate_limits": metric.rate_limit_hits,
                "retries": metric.retry_count,
                "error_message": metric.error_message or "—",
                "success_icon": "✓" if metric.success else "✗",
            }
        )

    return {
        "framework_css": framework_css,  # REQUIRED by base_dashboard.html
        "framework_js": framework_js,  # REQUIRED by base_dashboard.html
        "collection_date": collection_date,
        "summary_cards": summary_cards,
        "overall_status": summary["overall_status"],
        "overall_status_class": summary["overall_status_class"],
        "collector_rows": collector_rows,
        "slowest_collector": summary["slowest_collector"].capitalize(),
        "slowest_time": f"{summary['slowest_collector_time_sec']:.1f}s",
        "total_collectors": summary["total_runs"],
    }


def main() -> None:
    """
    Main entry point when run as a script.

    Generates collector health dashboard and saves to default location.
    """
    output_path = Path(".tmp/observatory/dashboards/collector_health.html")
    try:
        html = generate_collector_health_dashboard(output_path)
        print("\n[SUCCESS] Collector health dashboard generated successfully")
        print(f"  Output: {output_path}")
        print(f"  Size: {len(html):,} bytes")
        print(f"\nOpen in browser: file://{output_path.resolve()}")
    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        print("\nTo generate metrics, run a collector first:")
        print("  python execution/collectors/ado_quality_metrics.py")
    except Exception as e:
        logger.error("Failed to generate collector health dashboard", exc_info=True)
        print(f"\n[ERROR] Error generating dashboard: {e}")
        raise


if __name__ == "__main__":
    main()
