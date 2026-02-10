#!/usr/bin/env python3
"""
Add Data Collection Methodology sections to all dashboards
"""

import logging
import os
import re

logger = logging.getLogger(__name__)


def get_methodology_html(dashboard_type):
    """Get the methodology HTML for each dashboard type"""

    methodologies = {
        "flow": """
        <!-- Data Collection Methodology -->
        <div class="info-section" style="margin-top: 30px;">
            <h2>📊 Data Collection Methodology</h2>
            <p style="margin-bottom: 20px;">
                Flow metrics are collected from Azure DevOps Work Items to measure delivery speed and throughput.
            </p>

            <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px;">Metrics Definitions</h3>
            <ul style="line-height: 1.8; padding-left: 30px; margin-bottom: 20px;">
                <li><strong>Lead Time (P85):</strong> 85th percentile time from work item creation to closure. Measures overall delivery speed.</li>
                <li><strong>WIP (Work in Progress):</strong> Count of active work items not yet resolved or closed.</li>
                <li><strong>Throughput (Closed 90d):</strong> Total work items resolved/closed in the last 90 days.</li>
                <li><strong>Cycle Time:</strong> Time from "Active" to "Resolved" state (actual development time).</li>
            </ul>

            <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px;">Data Sources</h3>
            <ul style="line-height: 1.8; padding-left: 30px; margin-bottom: 20px;">
                <li><strong>Source:</strong> Azure DevOps Work Item Tracking API</li>
                <li><strong>Work Item Types:</strong> User Story, Bug, Task</li>
                <li><strong>Timeframe:</strong> Last 90 days for closed items, current snapshot for WIP</li>
                <li><strong>State Tracking:</strong> New → Active → Resolved → Closed</li>
            </ul>

            <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px;">Verification</h3>
            <ul style="line-height: 1.8; padding-left: 30px;">
                <li>Cross-reference counts with Azure DevOps Queries (e.g., "State = Active")</li>
                <li>Verify lead times by sampling individual work items' history</li>
                <li>Check date ranges in Azure DevOps Analytics for closed items</li>
            </ul>
        </div>""",
        "ownership": """
        <!-- Data Collection Methodology -->
        <div class="info-section" style="margin-top: 30px;">
            <h2>📊 Data Collection Methodology</h2>
            <p style="margin-bottom: 20px;">
                Ownership metrics track work assignment clarity by analyzing the "Assigned To" field in Azure DevOps.
            </p>

            <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px;">Metrics Definitions</h3>
            <ul style="line-height: 1.8; padding-left: 30px; margin-bottom: 20px;">
                <li><strong>Unassigned %:</strong> Percentage of active work items with no owner assigned.</li>
                <li><strong>Orphan Areas:</strong> Work areas or projects with high unassigned rates (>50%).</li>
                <li><strong>Total Items:</strong> All active work items (User Stories, Bugs, Tasks) across projects.</li>
            </ul>

            <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px;">Data Sources</h3>
            <ul style="line-height: 1.8; padding-left: 30px; margin-bottom: 20px;">
                <li><strong>Source:</strong> Azure DevOps Work Item Tracking API</li>
                <li><strong>Work Item Types:</strong> User Story, Bug, Task</li>
                <li><strong>States Included:</strong> New, Active (not Resolved/Closed)</li>
                <li><strong>Field Analyzed:</strong> "System.AssignedTo"</li>
            </ul>

            <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px;">Verification</h3>
            <ul style="line-height: 1.8; padding-left: 30px;">
                <li>Run Azure DevOps query: "State IN (New, Active) AND [Assigned To] = ''"</li>
                <li>Compare total counts with project-level work item queries</li>
                <li>Validate "orphan areas" by checking team/area path assignments</li>
            </ul>
        </div>""",
        "quality": """
        <!-- Data Collection Methodology -->
        <div class="info-section" style="margin-top: 30px;">
            <h2>📊 Data Collection Methodology</h2>
            <p style="margin-bottom: 20px;">
                Quality metrics track bug lifecycle, MTTR, and reopen rates to identify quality erosion patterns.
            </p>

            <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px;">Metrics Definitions</h3>
            <ul style="line-height: 1.8; padding-left: 30px; margin-bottom: 20px;">
                <li><strong>MTTR (Mean Time To Repair):</strong> Average days from bug creation to closure. Lower is better.</li>
                <li><strong>Reopen Rate:</strong> (Reopened Bugs / Total Closed Bugs) × 100. Indicates fix effectiveness.</li>
                <li><strong>Escaped Defects:</strong> Bugs found in production after release (P1/P2 severity).</li>
                <li><strong>Fix Quality:</strong> % of recently closed bugs that stayed fixed (not reopened).</li>
                <li><strong>Total Reopened:</strong> Count of bugs that moved from Resolved/Closed back to Active.</li>
                <li><strong>Open Bugs:</strong> Current count of bugs in New or Active state.</li>
            </ul>

            <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px;">Data Sources</h3>
            <ul style="line-height: 1.8; padding-left: 30px; margin-bottom: 20px;">
                <li><strong>Source:</strong> Azure DevOps Work Item Tracking API</li>
                <li><strong>Work Item Type:</strong> Bug only</li>
                <li><strong>Timeframe:</strong> Last 90 days for reopen analysis</li>
                <li><strong>MTTR Calculation:</strong> (ClosedDate - CreatedDate) averaged across closed bugs</li>
                <li><strong>Detection Method:</strong> State change history tracking (Resolved/Closed → Active)</li>
            </ul>

            <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px;">Verification</h3>
            <ul style="line-height: 1.8; padding-left: 30px;">
                <li>Cross-check reopen counts with Azure DevOps "State Change Date" field</li>
                <li>Validate MTTR by sampling individual bug lifespans (Created → Closed dates)</li>
                <li>Validate by sampling bug history for state transitions</li>
                <li>Compare total bug counts with Azure DevOps Analytics</li>
            </ul>
        </div>""",
        "security": """
        <!-- Data Collection Methodology -->
        <div class="info-section" style="margin-top: 30px;">
            <h2>📊 Data Collection Methodology</h2>
            <p style="margin-bottom: 20px;">
                Security metrics are aggregated from ArmorCode vulnerability management platform.
            </p>

            <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px;">Metrics Definitions</h3>
            <ul style="line-height: 1.8; padding-left: 30px; margin-bottom: 20px;">
                <li><strong>Critical Vulnerabilities:</strong> CVSS score 9.0-10.0 or Critical severity rating.</li>
                <li><strong>High Severity:</strong> CVSS score 7.0-8.9 or High severity rating.</li>
                <li><strong>Stale Criticals:</strong> Critical vulnerabilities open for >30 days.</li>
                <li><strong>Total Vulnerabilities:</strong> All open findings across all severity levels.</li>
            </ul>

            <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px;">Data Sources</h3>
            <ul style="line-height: 1.8; padding-left: 30px; margin-bottom: 20px;">
                <li><strong>Source:</strong> ArmorCode API (Vulnerability Management Platform)</li>
                <li><strong>Scanners:</strong> Aggregated from multiple security tools (SAST, DAST, SCA)</li>
                <li><strong>Products:</strong> All active products in ArmorCode</li>
                <li><strong>Status:</strong> Open vulnerabilities only (not Resolved/Closed)</li>
            </ul>

            <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px;">Verification</h3>
            <ul style="line-height: 1.8; padding-left: 30px;">
                <li>Log into ArmorCode and compare total vulnerability counts by severity</li>
                <li>Validate stale criticals with ArmorCode filters (Severity=Critical, Age>30 days)</li>
                <li>Cross-reference product-level counts with ArmorCode dashboards</li>
            </ul>
        </div>""",
        "risk": """
        <!-- Data Collection Methodology -->
        <div class="info-section" style="margin-top: 30px;">
            <h2>📊 Data Collection Methodology</h2>
            <p style="margin-bottom: 20px;">
                Risk metrics combine Git repository data and bug tracking to identify delivery and quality risks.
            </p>

            <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px;">Metrics Definitions</h3>
            <ul style="line-height: 1.8; padding-left: 30px; margin-bottom: 20px;">
                <li><strong>PR Size Distribution:</strong> Small (≤3 commits), Medium (4-10), Large (>10 commits).</li>
                <li><strong>Code Churn:</strong> Frequency of changes to files (identifies "hot paths").</li>
                <li><strong>Reopened Bugs:</strong> Bugs moved from Resolved/Closed back to Active state.</li>
                <li><strong>Projects at Risk:</strong> Projects with high reopen rates or large PR percentage.</li>
            </ul>

            <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px;">Data Sources</h3>
            <ul style="line-height: 1.8; padding-left: 30px; margin-bottom: 20px;">
                <li><strong>Git Metrics:</strong> Azure DevOps Git API (commits, pull requests)</li>
                <li><strong>Bug Tracking:</strong> Azure DevOps Work Item Tracking API</li>
                <li><strong>Timeframe:</strong> Last 90 days for all metrics</li>
                <li><strong>Scope:</strong> Top 5 active repositories per project</li>
                <li><strong>PR Limit:</strong> Up to 200 most recent completed PRs per repository</li>
            </ul>

            <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px;">Required Permissions</h3>
            <ul style="line-height: 1.8; padding-left: 30px; margin-bottom: 20px;">
                <li><strong>Azure DevOps PAT:</strong> Work Items (Read), Code (Read)</li>
                <li>Code (Read) permission is required for Git repository access</li>
            </ul>

            <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px;">Verification</h3>
            <ul style="line-height: 1.8; padding-left: 30px;">
                <li>Compare PR counts with Azure DevOps repo pull request history</li>
                <li>Validate commit counts using Git history in Azure DevOps</li>
                <li>Cross-check reopened bugs with Azure DevOps queries for state changes</li>
            </ul>
        </div>""",
    }

    return methodologies.get(dashboard_type, "")


def add_methodology_to_dashboard(html_file, dashboard_type):
    """Add methodology section to a dashboard HTML file"""

    if not os.path.exists(html_file):
        logger.info(f"File not found (skipping): {html_file}")
        return False

    with open(html_file, encoding="utf-8") as f:
        content = f.read()

    # Check if methodology already exists
    if "Data Collection Methodology" in content:
        logger.info(f"Methodology already exists (skipping): {os.path.basename(html_file)}")
        return False

    # Get methodology HTML
    methodology = get_methodology_html(dashboard_type)
    if not methodology:
        logger.error(f"No methodology template for type: {dashboard_type}")
        return False

    # Find insertion point (before closing </div> of container and before footer)
    # Try to insert before footer or last info section
    patterns = [
        (r'(<div class="footer">)', f"{methodology}\n\n\\1"),
        (r"(</div>\s*</div>\s*<script>)", f"{methodology}\n\\1"),
        (r"(</div>\s*<script>)", f"{methodology}\n\\1"),
    ]

    modified = False
    for pattern, replacement in patterns:
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content, count=1)
            modified = True
            break

    if not modified:
        logger.error(f"Could not find insertion point in {os.path.basename(html_file)}")
        return False

    # Save updated content
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Added methodology to {os.path.basename(html_file)}")
    return True


if __name__ == "__main__":
    import sys

    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    logger.info("Adding Data Collection Methodology to Dashboards")
    logger.info("=" * 60)

    dashboard_dir = ".tmp/observatory/dashboards"

    dashboards = {
        "flow_dashboard.html": "flow",
        "ownership_dashboard.html": "ownership",
        "quality_dashboard.html": "quality",
        "security_dashboard.html": "security",
        "risk_dashboard.html": "risk",
    }

    success_count = 0
    for filename, dashboard_type in dashboards.items():
        filepath = os.path.join(dashboard_dir, filename)
        logger.info(f"Processing: {filename}")
        if add_methodology_to_dashboard(filepath, dashboard_type):
            success_count += 1

    logger.info("=" * 60)
    logger.info(f"Complete: {success_count}/{len(dashboards)} dashboards updated")
    logger.info("Note: AI Contributions dashboard already has methodology.")
    logger.info("Note: Executive Summary doesn't need detailed methodology (it aggregates from others).")
