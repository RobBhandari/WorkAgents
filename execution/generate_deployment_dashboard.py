#!/usr/bin/env python3
"""
Deployment Dashboard Generator

Creates a self-contained HTML dashboard for DORA deployment metrics.
Shows deployment frequency, build success rate, build duration, and lead time for changes.

HARD DATA ONLY - No arbitrary thresholds or status classifications.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Import mobile-responsive framework
try:
    from execution.dashboard_framework import get_dashboard_framework
except ModuleNotFoundError:
    from dashboard_framework import get_dashboard_framework

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


def load_deployment_data():
    """Load deployment metrics history from JSON file."""
    history_file = Path(".tmp/observatory/deployment_history.json")

    if not history_file.exists():
        print(f"[ERROR] Deployment history file not found: {history_file}")
        print("Run: python execution/ado_deployment_metrics.py")
        sys.exit(1)

    with open(history_file, encoding="utf-8") as f:
        data = json.load(f)

    return data


def generate_deployment_dashboard():
    """Generate the deployment dashboard HTML."""

    print("Generating Deployment Dashboard...")

    # Load data
    data = load_deployment_data()

    if not data.get("weeks"):
        print("[ERROR] No deployment data found in history")
        sys.exit(1)

    # Get latest week data
    latest_week = data["weeks"][-1]
    projects = latest_week.get("projects", [])

    print(f"  Found {len(projects)} projects with deployment data")

    # Generate project rows HTML
    project_rows_html = ""

    for project in sorted(
        projects, key=lambda p: p.get("deployment_frequency", {}).get("deployments_per_week", 0), reverse=True
    ):
        proj_name = project["project_name"]

        # Deployment Frequency
        deploy_freq = project.get("deployment_frequency", {})
        deploys_per_week = deploy_freq.get("deployments_per_week", 0)
        total_successful = deploy_freq.get("total_successful_builds", 0)

        # Build Success Rate
        success_rate = project.get("build_success_rate", {})
        success_pct = success_rate.get("success_rate_pct", 0)
        total_builds = success_rate.get("total_builds", 0)
        succeeded = success_rate.get("succeeded", 0)
        failed = success_rate.get("failed", 0)

        # Build Duration
        duration = project.get("build_duration", {})
        median_duration = duration.get("median_minutes", 0) or 0
        p85_duration = duration.get("p85_minutes", 0) or 0

        # Lead Time for Changes
        lead_time = project.get("lead_time_for_changes", {})
        median_lead_time = lead_time.get("median_hours", 0) or 0
        p85_lead_time = lead_time.get("p85_hours", 0) or 0

        # Format values
        deploys_display = f"{deploys_per_week:.1f}/week"
        success_display = f"{success_pct:.1f}%"
        success_detail = f"{succeeded}/{total_builds} builds"
        duration_display = f"{median_duration:.1f}m"
        duration_detail = f"P85: {p85_duration:.1f}m"
        lead_time_display = f"{median_lead_time:.1f}h"
        lead_time_detail = f"P85: {p85_lead_time:.1f}h"

        # Determine status based on build success rate and deployment activity
        if success_pct >= 90 and deploys_per_week >= 1:
            status_display = "✓ Good"
            status_class = "status-good"
            status_tooltip = f"Good: {success_pct:.1f}% success rate, {deploys_per_week:.1f} deploys/week"
        elif success_pct >= 70 and deploys_per_week >= 0.5:
            status_display = "⚠ Caution"
            status_class = "status-caution"
            status_tooltip = f"Caution: {success_pct:.1f}% success rate, {deploys_per_week:.1f} deploys/week"
        elif total_builds == 0 or deploys_per_week == 0:
            status_display = "○ Inactive"
            status_class = "status-inactive"
            status_tooltip = "Inactive: No deployments in 90 days"
        else:
            status_display = "● Action Needed"
            status_class = "status-action"
            status_tooltip = f"Action Needed: {success_pct:.1f}% success rate, {deploys_per_week:.1f} deploys/week"

        project_rows_html += f"""
        <tr>
            <td><strong>{proj_name}</strong></td>
            <td title="{total_successful} successful builds">{deploys_display}</td>
            <td title="{success_detail}">{success_display}</td>
            <td title="{duration_detail}">{duration_display}</td>
            <td title="{lead_time_detail}">{lead_time_display}</td>
            <td title="{status_tooltip}" class="{status_class}">{status_display}</td>
        </tr>
        """

    # Calculate totals
    total_builds_all = sum(p["build_success_rate"]["total_builds"] for p in projects)
    total_successful_all = sum(p["deployment_frequency"]["total_successful_builds"] for p in projects)
    overall_success_rate = (total_successful_all / total_builds_all * 100) if total_builds_all > 0 else 0

    # Get collection date
    collection_date = latest_week.get("week_date", "Unknown")

    # Get mobile-responsive framework
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#667eea",
        header_gradient_end="#764ba2",
        include_table_scroll=True,
        include_expandable_rows=False,
        include_glossary=True,
    )

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Deployment Dashboard - DORA Metrics</title>
    {framework_css}
    <style>
        /* Dashboard-specific styles */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .metric-card {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 12px var(--shadow);
            border-left: 4px solid #667eea;
        }}

        .metric-label {{
            color: var(--text-secondary);
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
        }}

        .metric-value {{
            color: var(--text-primary);
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 4px;
        }}

        .metric-detail {{
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}

        .table-card {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 12px var(--shadow);
            margin-bottom: 20px;
        }}

        h2 {{
            color: var(--text-primary);
            font-size: 1.3rem;
            margin-bottom: 16px;
        }}

        .status-good {{
            color: #10b981;
            font-weight: 600;
        }}

        .status-caution {{
            color: #f59e0b;
            font-weight: 600;
        }}

        .status-action {{
            color: #ef4444;
            font-weight: 600;
        }}

        .status-inactive {{
            color: var(--text-secondary);
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="theme-toggle" onclick="toggleTheme()" title="Toggle dark/light mode">
        <span id="theme-icon">🌙</span>
        <span id="theme-label">Dark</span>
    </div>

    <div class="container">
        <div class="header">
            <h1>Deployment Dashboard</h1>
            <div class="subtitle">DORA Metrics - Deployment Performance</div>
            <div class="timestamp">Data collected: {collection_date} • Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Total Builds (90 days)</div>
                <div class="metric-value">{total_builds_all:,}</div>
                <div class="metric-detail">{total_successful_all:,} successful</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Overall Success Rate</div>
                <div class="metric-value">{overall_success_rate:.1f}%</div>
                <div class="metric-detail">Across all projects</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Projects Tracked</div>
                <div class="metric-value">{len(projects)}</div>
                <div class="metric-detail">With deployment data</div>
            </div>
        </div>

        <div class="table-card">
            <h2>Deployment Metrics by Project</h2>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Project</th>
                            <th>Deployment Frequency</th>
                            <th>Build Success Rate</th>
                            <th>Build Duration (Median)</th>
                            <th>Lead Time (Median)</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {project_rows_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Glossary -->
        <div class="glossary">
            <div class="glossary-header" onclick="toggleGlossary()">
                <h3>📖 What These Metrics Mean</h3>
                <span class="glossary-toggle" id="glossary-toggle">▼</span>
            </div>
            <div class="glossary-content" id="glossary-content">
                <div class="glossary-item">
                    <div class="glossary-term">Status Indicator</div>
                    <div class="glossary-definition">
                        Overall health of the deployment pipeline based on success rate and activity:<br><br>
                        <span style="color: #10b981;">✓ <strong>Good</strong></span>: ≥90% success rate + ≥1 deploy/week<br>
                        <span style="color: #f59e0b;">⚠ <strong>Caution</strong></span>: ≥70% success rate + ≥0.5 deploys/week<br>
                        <span style="color: #ef4444;">● <strong>Action Needed</strong></span>: Low success rate or infrequent deployments<br>
                        <span style="color: #94a3b8;">○ <strong>Inactive</strong></span>: No deployments in the last 90 days
                    </div>
                </div>

                <div class="glossary-item">
                    <div class="glossary-term">DORA Metrics</div>
                    <div class="glossary-definition">
                        DevOps Research and Assessment (DORA) metrics are industry-standard measures of software delivery performance.
                        These metrics help teams understand their deployment velocity, stability, and efficiency.
                        Research shows that high-performing teams excel across all four DORA metrics.
                    </div>
                </div>

                <div class="glossary-item">
                    <div class="glossary-term">Deployment Frequency</div>
                    <div class="glossary-definition">
                        How often code is successfully deployed to production. Measured as deployments per week.
                        <strong>Higher is better</strong> - more frequent deployments indicate better agility and faster delivery of value to customers.
                        <br><br>
                        Elite performers: Multiple deployments per day<br>
                        High performers: Daily to weekly deployments<br>
                        Medium performers: Weekly to monthly deployments
                    </div>
                </div>

                <div class="glossary-item">
                    <div class="glossary-term">Build Success Rate</div>
                    <div class="glossary-definition">
                        Percentage of builds that complete successfully without failures.
                        <strong>Higher is better</strong> - indicates code quality, test coverage, and build stability.
                        <br><br>
                        A high success rate (>90%) suggests robust testing and quality gates.
                        Low success rates can indicate flaky tests, infrastructure issues, or code quality problems.
                    </div>
                </div>

                <div class="glossary-item">
                    <div class="glossary-term">Build Duration (Median)</div>
                    <div class="glossary-definition">
                        The median time it takes to complete a build, measured in minutes.
                        <strong>Lower is better</strong> - faster builds mean quicker feedback for developers.
                        <br><br>
                        We show both median (typical time) and P85 (85th percentile) to account for variability.
                        Long build times can slow down development velocity and delay feedback on code changes.
                    </div>
                </div>

                <div class="glossary-item">
                    <div class="glossary-term">Lead Time for Changes</div>
                    <div class="glossary-definition">
                        The time from when code is committed to when it's successfully deployed to production, measured in hours.
                        <strong>Lower is better</strong> - shorter lead times mean faster response to customer needs and market changes.
                        <br><br>
                        Elite performers: Less than 1 hour<br>
                        High performers: 1 day to 1 week<br>
                        Medium performers: 1 week to 1 month
                        <br><br>
                        This metric combines build time, test time, approval processes, and deployment time.
                    </div>
                </div>

                <div class="glossary-item">
                    <div class="glossary-term">P85 (85th Percentile)</div>
                    <div class="glossary-definition">
                        A statistical measure showing the value below which 85% of observations fall.
                        This helps filter out extreme outliers while capturing realistic upper bounds.
                        <br><br>
                        For example, if P85 build duration is 15 minutes, it means 85% of builds complete in 15 minutes or less.
                    </div>
                </div>

                <h3 style="margin-top: 30px; color: #667eea;">📊 Data Collection Details</h3>

                <div class="glossary-item">
                    <div class="glossary-term">Time Period</div>
                    <div class="glossary-definition">
                        <strong>90-day lookback period</strong> for all deployment metrics.
                        This provides enough data for meaningful statistics while remaining relevant to current performance.
                    </div>
                </div>

                <div class="glossary-item">
                    <div class="glossary-term">Build Criteria</div>
                    <div class="glossary-definition">
                        Only completed builds (succeeded or failed) are counted.
                        Canceled or in-progress builds are excluded from metrics.
                        Deployment frequency counts only successful builds.
                    </div>
                </div>

                <div class="glossary-item">
                    <div class="glossary-term">Why These Metrics Matter</div>
                    <div class="glossary-definition">
                        DORA metrics correlate strongly with organizational performance and business outcomes.
                        Teams that excel in these metrics deliver more value, respond faster to incidents,
                        and have higher job satisfaction. These are <strong>leading indicators</strong> of overall engineering effectiveness.
                    </div>
                </div>
            </div>
        </div>

        <div class="footer">
            <p>Director Observatory • Read-Only Metrics • No Enforcement</p>
            <p style="margin-top: 10px;">Data source: Azure DevOps • Updated: {collection_date}</p>
        </div>
    </div>

    {framework_js}

</body>
</html>"""

    # Save HTML
    output_dir = Path(".tmp/observatory/dashboards")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "deployment_dashboard.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[SUCCESS] Deployment dashboard generated: {output_file}")
    return str(output_file)


if __name__ == "__main__":
    print("=" * 60)
    print("Deployment Dashboard Generator")
    print("=" * 60)

    try:
        output_path = generate_deployment_dashboard()
        print("\nDashboard ready!")
        print(f"Open: {output_path}")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Failed to generate dashboard: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
