"""
Target Dashboard Generator - Refactored

Generates 70% reduction target tracking dashboard using:
    - Jinja2 templates (XSS-safe)
    - Direct API queries for current metrics (no stale history files)
    - Clean separation of data loading and presentation
    - Reusable metric calculation functions

This replaces the original 633-line generate_target_dashboard.py with a
clean, maintainable implementation that queries APIs directly.

Usage:
    from execution.dashboards.targets import generate_targets_dashboard
    from pathlib import Path
    import asyncio

    output_path = Path('.tmp/observatory/dashboards/target_dashboard.html')
    html = asyncio.run(generate_targets_dashboard(output_path))
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from execution.collectors.ado_rest_client import AzureDevOpsRESTClient, get_ado_rest_client
from execution.collectors.ado_rest_transformers import WorkItemTransformer
from execution.collectors.armorcode_vulnerability_loader import ArmorCodeVulnerabilityLoader
from execution.collectors.security_bug_filter import filter_security_bugs
from execution.core import get_logger
from execution.dashboards.renderer import render_dashboard
from execution.framework import get_dashboard_framework
from execution.secure_config import get_config
from execution.security import WIQLValidator
from execution.utils.error_handling import log_and_raise

logger = get_logger(__name__)


async def generate_targets_dashboard(output_path: Path | None = None) -> str:
    """
    Generate 70% reduction target tracking dashboard HTML.

    This is the main entry point for generating the targets dashboard.
    It loads baseline data, queries current state from APIs, calculates progress,
    and renders the HTML template.

    Args:
        output_path: Optional path to write HTML file

    Returns:
        Generated HTML string

    Raises:
        FileNotFoundError: If baseline files don't exist

    Example:
        from pathlib import Path
        import asyncio
        html = asyncio.run(generate_targets_dashboard(
            Path('.tmp/observatory/dashboards/target_dashboard.html')
        ))
        logger.info("Dashboard generated", extra={"html_size": len(html)})
    """
    logger.info("Generating 70% reduction target dashboard")

    # Step 1: Load baseline data
    logger.info("Loading baseline data")
    baselines = _load_baselines()

    # Step 2: Query current state from APIs
    logger.info("Querying current metrics from APIs")
    current_state = await _query_current_state(baselines)

    # Step 3: Calculate summary metrics
    logger.info("Calculating progress metrics")
    summary_stats = _calculate_summary(baselines, current_state)

    # Step 4: Prepare template context
    logger.info("Preparing dashboard components")
    context = _build_context(summary_stats)

    # Step 5: Render template
    logger.info("Rendering HTML template")
    html = render_dashboard("dashboards/targets_dashboard.html", context)

    # Write to file if specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info("Dashboard written to file", extra={"path": str(output_path)})

    # Print summary to console
    _print_summary(summary_stats)

    logger.info("Target dashboard generated", extra={"html_size": len(html)})
    return html


def _load_baselines() -> dict[str, dict]:
    """
    Load baseline data from JSON files.

    Returns:
        Dictionary with baseline data for security and bugs

    Raises:
        FileNotFoundError: If baseline files don't exist
    """
    security_baseline_path = Path("data/armorcode_baseline.json")
    bugs_baseline_path = Path("data/baseline.json")

    if not security_baseline_path.exists():
        raise FileNotFoundError(f"Security baseline not found: {security_baseline_path}")

    if not bugs_baseline_path.exists():
        raise FileNotFoundError(f"Bugs baseline not found: {bugs_baseline_path}")

    with open(security_baseline_path, encoding="utf-8") as f:
        security_baseline = json.load(f)

    with open(bugs_baseline_path, encoding="utf-8") as f:
        bugs_baseline = json.load(f)

    logger.info(f"Loaded security baseline: {security_baseline_path}")
    logger.info(f"Loaded bugs baseline: {bugs_baseline_path}")

    return {"security": security_baseline, "bugs": bugs_baseline}


def _load_discovery_data() -> dict:
    """
    Load project discovery data from ADO structure file.

    Returns:
        Dictionary with project list

    Raises:
        FileNotFoundError: If discovery file doesn't exist
    """
    discovery_path = Path(".tmp/observatory/ado_structure.json")

    if not discovery_path.exists():
        raise FileNotFoundError(
            f"Discovery file not found: {discovery_path}\n" "Run: python execution/discover_projects.py"
        )

    with open(discovery_path, encoding="utf-8") as f:
        discovery_data = json.load(f)

    projects = discovery_data.get("projects", [])
    logger.info(f"Loaded {len(projects)} projects from discovery")

    discovery_data_typed: dict[Any, Any] = discovery_data
    return discovery_data_typed


async def _query_current_state(baselines: dict[str, dict]) -> dict[str, int]:
    """
    Query current vulnerability and bug counts from APIs.

    Args:
        baselines: Baseline data containing product lists

    Returns:
        Dictionary with current counts for security and bugs

    Raises:
        FileNotFoundError: If required config files don't exist
    """
    # Query security vulnerabilities and bugs concurrently
    security_task = _query_current_armorcode_vulns()
    bugs_task = _query_current_ado_bugs()

    security_count, bugs_count = await asyncio.gather(security_task, bugs_task)

    return {"security": security_count, "bugs": bugs_count}


async def _query_current_armorcode_vulns() -> int:
    """
    Query current HIGH + CRITICAL vulnerabilities from ArmorCode API.

    Uses the AQL count endpoint — 2 API calls total regardless of product count.
    Filters to Production environment, consistent with security_enhanced.py.

    Returns:
        Current Critical + High vulnerability count (Production only)

    Raises:
        RuntimeError: If ARMORCODE_HIERARCHY env var is not configured
    """
    hierarchy = get_config().get_optional_env("ARMORCODE_HIERARCHY")
    if not hierarchy:
        raise RuntimeError(
            "ARMORCODE_HIERARCHY env var not set. Add it as a GitHub secret and to your local .env file."
        )

    logger.info("Querying ArmorCode API for Critical + High vulnerabilities (Production, 2 API calls)")

    loader = ArmorCodeVulnerabilityLoader()
    critical_counts = loader.count_by_severity_aql("Critical", hierarchy)
    high_counts = loader.count_by_severity_aql("High", hierarchy)

    total_critical = sum(critical_counts.values())
    total_high = sum(high_counts.values())
    total_vulns = total_critical + total_high

    logger.info(f"Current ArmorCode vulnerabilities (Production): {total_vulns}")
    logger.info(f"  Critical: {total_critical}")
    logger.info(f"  High: {total_high}")

    return total_vulns


async def _query_current_ado_bugs() -> int:
    """
    Query current open bugs from ADO API across all projects.

    Returns:
        Current bug count (excluding security bugs)

    Raises:
        Exception: If API query fails
    """
    logger.info("Querying ADO API for open bugs across all projects")

    # Load discovery data to get project list
    discovery_data = _load_discovery_data()
    projects = discovery_data.get("projects", [])

    if not projects:
        logger.warning("No projects found in discovery data")
        return 0

    # Get REST client
    rest_client = get_ado_rest_client()

    # Query bugs for each project concurrently
    tasks = [_query_bugs_for_project(rest_client, project) for project in projects]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Sum up bug counts
    total_bugs = 0
    for project, result in zip(projects, results, strict=False):
        if isinstance(result, Exception):
            logger.error(f"Error querying bugs for {project['project_name']}: {result}")
        elif isinstance(result, int):
            total_bugs += result

    logger.info(f"Current ADO bugs (all projects): {total_bugs}")
    logger.info(f"  Projects queried: {len(projects)}")

    return total_bugs


async def _query_bugs_for_project(rest_client: AzureDevOpsRESTClient, project: dict) -> int:
    """
    Query open bugs for a single project.

    Args:
        rest_client: Azure DevOps REST client
        project: Project metadata dictionary

    Returns:
        Open bug count for this project (excluding security bugs)
    """
    project_name = project["project_name"]
    ado_project_name = project.get("ado_project_name", project_name)
    area_path_filter = project.get("area_path_filter")

    logger.info(f"  Querying bugs for: {project_name}")

    # Validate project name
    safe_project = WIQLValidator.validate_project_name(ado_project_name)

    # Build area path filter clause
    area_filter_clause = ""
    if area_path_filter:
        if area_path_filter.startswith("EXCLUDE:"):
            path = area_path_filter.replace("EXCLUDE:", "")
            safe_path = WIQLValidator.validate_area_path(path)
            area_filter_clause = f"AND [System.AreaPath] NOT UNDER '{safe_path}'"
        elif area_path_filter.startswith("INCLUDE:"):
            path = area_path_filter.replace("INCLUDE:", "")
            safe_path = WIQLValidator.validate_area_path(path)
            area_filter_clause = f"AND [System.AreaPath] UNDER '{safe_path}'"

    # WIQL query for open bugs
    wiql_query = f"""SELECT [System.Id]
        FROM WorkItems
        WHERE [System.TeamProject] = '{safe_project}'
          AND [System.WorkItemType] = 'Bug'
          AND [System.State] <> 'Closed'
          AND [System.State] <> 'Removed'
          AND ([Microsoft.VSTS.Common.Triage] <> 'Rejected' OR [Microsoft.VSTS.Common.Triage] = '')
          {area_filter_clause}
        ORDER BY [System.CreatedDate] DESC
        """  # nosec B608 - Inputs validated by WIQLValidator

    try:
        # Execute query
        response = await rest_client.query_by_wiql(project=safe_project, wiql_query=wiql_query)

        # Transform response
        wiql_result = WorkItemTransformer.transform_wiql_response(response)
        work_items = wiql_result.work_items

        if not work_items:
            logger.info(f"    {project_name}: 0 open bugs")
            return 0

        # Get bug IDs
        bug_ids = [item.id for item in work_items]

        # Fetch bug details to filter security bugs
        from execution.utils.ado_batch_utils import batch_fetch_work_items_rest

        bugs_raw, failed_ids = await batch_fetch_work_items_rest(
            rest_client,
            item_ids=bug_ids,
            fields=["System.Id", "System.Tags", "System.Title"],
            logger=logger,
        )

        bugs = WorkItemTransformer.transform_work_items_response({"value": bugs_raw})

        # Filter out security bugs (to avoid double-counting)
        filtered_bugs, excluded_count = filter_security_bugs(bugs)

        bug_count = len(filtered_bugs)
        logger.info(f"    {project_name}: {bug_count} open bugs (excluded {excluded_count} security bugs)")

        return bug_count

    except Exception as e:
        logger.error(f"    Error querying bugs for {project_name}: {e}")
        return 0


def _calculate_summary(baselines: dict[str, dict], current_state: dict[str, int]) -> dict[str, dict]:
    """
    Calculate progress metrics for both security and bugs.

    Args:
        baselines: Baseline data dictionary
        current_state: Current counts dictionary

    Returns:
        Dictionary with calculated metrics for both security and bugs
    """
    # Calculate security metrics
    security_metrics = _calculate_metrics(
        baseline_count=baselines["security"]["total_vulnerabilities"],
        target_count=baselines["security"]["target_vulnerabilities"],
        current_count=current_state["security"],
        weeks_to_target=baselines["security"]["weeks_to_target"],
    )

    # Calculate bugs metrics
    bugs_metrics = _calculate_metrics(
        baseline_count=baselines["bugs"]["open_count"],
        target_count=baselines["bugs"]["target_count"],
        current_count=current_state["bugs"],
        weeks_to_target=baselines["bugs"]["weeks_to_target"],
    )

    return {"security": security_metrics, "bugs": bugs_metrics}


def _calculate_metrics(
    baseline_count: int, target_count: int, current_count: int, weeks_to_target: int
) -> dict[str, int | float | str]:
    """
    Calculate progress metrics for target tracking.

    Focuses on fixed baseline → target tracking:
    - Baseline (Dec 1, 2025): Starting point
    - Current: Where we are now
    - Target (June 30, 2026): End goal (70% reduction)

    Args:
        baseline_count: Starting count from baseline
        target_count: Target count (70% reduction)
        current_count: Current count
        weeks_to_target: Weeks from baseline to target date

    Returns:
        Dictionary with calculated metrics including progress percentage,
        remaining days, and required weekly burn rate
    """
    # Progress from baseline (can be negative if count increased)
    total_reduction_needed = baseline_count - target_count
    progress_from_baseline = baseline_count - current_count
    progress_pct = (progress_from_baseline / total_reduction_needed * 100) if total_reduction_needed > 0 else 0

    # Days/weeks remaining to target date
    target_date = datetime.strptime("2026-06-30", "%Y-%m-%d")
    today = datetime.now()
    days_remaining = (target_date - today).days
    weeks_remaining = days_remaining / 7

    # Remaining work to hit target
    remaining_to_target = current_count - target_count

    # Required weekly burn FROM CURRENT POSITION to hit target
    required_weekly_burn = remaining_to_target / weeks_remaining if weeks_remaining > 0 else 0

    # Status determination based on progress percentage
    if progress_pct >= 100:
        status = "TARGET MET"
        status_color = "#10b981"  # Green
    elif progress_pct >= 70:
        status = "ON TRACK"
        status_color = "#10b981"  # Green
    elif progress_pct >= 40:
        status = "BEHIND SCHEDULE"
        status_color = "#f59e0b"  # Amber
    else:
        status = "AT RISK"
        status_color = "#ef4444"  # Red

    return {
        "baseline_count": baseline_count,
        "current_count": current_count,
        "target_count": target_count,
        "progress_from_baseline": progress_from_baseline,
        "progress_pct": round(progress_pct, 1),
        "days_remaining": days_remaining,
        "weeks_remaining": round(weeks_remaining, 1),
        "required_weekly_burn": round(required_weekly_burn, 2),
        "status": status,
        "status_color": status_color,
        "remaining_to_target": remaining_to_target,
    }


def _build_context(summary_stats: dict[str, dict]) -> dict[str, str | dict | bool]:
    """
    Build template context with all dashboard data.

    Args:
        summary_stats: Calculated summary statistics

    Returns:
        Dictionary for template rendering
    """
    # Get dashboard framework (CSS/JS)
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#1e40af",
        header_gradient_end="#1e3a8a",
        include_table_scroll=False,
        include_expandable_rows=False,
        include_glossary=False,
    )

    # Build context with security and bugs metrics
    context = {
        "framework_css": framework_css,
        "framework_js": framework_js,
        "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "security": summary_stats["security"],
        "bugs": summary_stats["bugs"],
        "show_glossary": False,
    }

    return context


def _print_summary(summary_stats: dict[str, dict]) -> None:
    """
    Print summary statistics to console.

    Args:
        summary_stats: Summary statistics dictionary
    """
    security = summary_stats["security"]
    bugs = summary_stats["bugs"]

    logger.info("70% Reduction Target Dashboard Summary")
    logger.info(
        "Security vulnerabilities",
        extra={
            "current": security["current_count"],
            "progress_pct": security["progress_pct"],
            "status": security["status"],
        },
    )
    logger.info(
        "Bugs", extra={"current": bugs["current_count"], "progress_pct": bugs["progress_pct"], "status": bugs["status"]}
    )


# Main execution for testing
if __name__ == "__main__":
    logger.info("Target Dashboard Generator - Self Test")

    try:
        output_path = Path(".tmp/observatory/dashboards/target_dashboard.html")
        html = asyncio.run(generate_targets_dashboard(output_path))

        logger.info(
            "Target dashboard generated successfully", extra={"output": str(output_path), "html_size": len(html)}
        )

        # Verify output
        if output_path.exists():
            file_size = output_path.stat().st_size
            logger.info("Output file verified", extra={"file_size": file_size})
        else:
            logger.warning("Output file not created")

    except FileNotFoundError as e:
        logger.error("Target data file not found", extra={"error": str(e)})
        logger.info("Check baseline files exist: data/armorcode_baseline.json, data/baseline.json")

    except Exception as e:
        log_and_raise(
            logger,
            e,
            context={"output_path": str(output_path), "operation": "dashboard_generation"},
            error_type="Target dashboard generation",
        )
