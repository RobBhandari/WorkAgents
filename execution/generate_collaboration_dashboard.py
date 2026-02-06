#!/usr/bin/env python3
"""
Collaboration Dashboard Generator

Creates a self-contained HTML dashboard for code review and PR metrics.
Shows PR review time, merge time, iteration count, and PR size.

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
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def calculate_composite_status(merge_time, iterations, pr_size):
    """
    Calculate composite collaboration status based on HARD DATA metrics only.
    Returns tuple: (status_html, tooltip_text, priority)

    Priority is used for sorting: 0 = Action Needed (Red), 1 = Caution (Amber), 2 = Good (Green)

    Status determination:
    - Good: All metrics meet target thresholds
    - Caution: One or more metrics need attention but not critical
    - Action Needed: Multiple metrics miss targets or any critical threshold exceeded

    Thresholds:
    - Merge Time: Good < 24h, Caution 24-72h, Poor > 72h
    - Iterations: Good <= 2, Caution 3-5, Poor > 5
    - PR Size: Good <= 5 commits, Caution 6-10 commits, Poor > 10 commits
    """
    issues = []
    metric_details = []

    # Check Merge Time (hours)
    if merge_time is not None and merge_time > 0:
        if merge_time > 72:
            issues.append('poor')
            metric_details.append(f"Merge time {merge_time:.1f}h (poor - target <24h)")
        elif merge_time > 24:
            issues.append('caution')
            metric_details.append(f"Merge time {merge_time:.1f}h (caution - target <24h)")
        else:
            metric_details.append(f"Merge time {merge_time:.1f}h (good)")

    # Check Iterations
    if iterations is not None and iterations > 0:
        if iterations > 5:
            issues.append('poor')
            metric_details.append(f"{iterations:.1f} iterations (poor - target ≤2)")
        elif iterations > 2:
            issues.append('caution')
            metric_details.append(f"{iterations:.1f} iterations (caution - target ≤2)")
        else:
            metric_details.append(f"{iterations:.1f} iterations (good)")

    # Check PR Size
    if pr_size is not None and pr_size > 0:
        if pr_size > 10:
            issues.append('poor')
            metric_details.append(f"{pr_size:.1f} commits (poor - target ≤5)")
        elif pr_size > 5:
            issues.append('caution')
            metric_details.append(f"{pr_size:.1f} commits (caution - target ≤5)")
        else:
            metric_details.append(f"{pr_size:.1f} commits (good)")

    # Build tooltip text
    tooltip = "\n".join(metric_details) if metric_details else "No data available"

    # Determine overall status
    if 'poor' in issues and len([i for i in issues if i == 'poor']) >= 2:
        # Two or more metrics poor = Action Needed
        status_html = '<span style="color: #ef4444;">● Action Needed</span>'
        priority = 0
    elif 'poor' in issues:
        # One poor metric = Caution
        status_html = '<span style="color: #f59e0b;">⚠ Caution</span>'
        priority = 1
    elif 'caution' in issues:
        # Some caution metrics = Caution
        status_html = '<span style="color: #f59e0b;">⚠ Caution</span>'
        priority = 1
    elif metric_details:
        # All metrics meet targets = Good
        status_html = '<span style="color: #10b981;">✓ Good</span>'
        priority = 2
    else:
        # No data
        status_html = '<span style="color: #94a3b8;">○ No Data</span>'
        priority = 3

    return status_html, tooltip, priority


def load_collaboration_data():
    """Load collaboration metrics history from JSON file."""
    history_file = Path(".tmp/observatory/collaboration_history.json")

    if not history_file.exists():
        print(f"[ERROR] Collaboration history file not found: {history_file}")
        print("Run: python execution/ado_collaboration_metrics.py")
        sys.exit(1)

    with open(history_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data


def generate_collaboration_dashboard():
    """Generate the collaboration dashboard HTML."""

    print("Generating Collaboration Dashboard...")

    # Load data
    data = load_collaboration_data()

    if not data.get('weeks'):
        print("[ERROR] No collaboration data found in history")
        sys.exit(1)

    # Get latest week data
    latest_week = data['weeks'][-1]
    projects = latest_week.get('projects', [])

    print(f"  Found {len(projects)} projects with collaboration data")

    # Generate project rows HTML with status sorting
    projects_with_status = []

    for project in projects:
        proj_name = project['project_name']

        # PR Merge Time
        merge_time = project.get('pr_merge_time', {})
        median_merge = merge_time.get('median_hours', 0) or 0
        p85_merge = merge_time.get('p85_hours', 0) or 0
        merge_sample = merge_time.get('sample_size', 0)

        # Review Iteration Count
        iterations = project.get('review_iteration_count', {})
        median_iterations = iterations.get('median_iterations', 0) or 0
        max_iterations = iterations.get('max_iterations', 0) or 0

        # PR Size
        pr_size = project.get('pr_size', {})
        median_commits = pr_size.get('median_commits', 0) or 0
        p85_commits = pr_size.get('p85_commits', 0) or 0

        # Total PRs
        total_prs = project.get('total_prs_analyzed', 0)

        # Format values
        merge_display = f"{median_merge:.1f}h" if median_merge else "N/A"
        merge_detail = f"P85: {p85_merge:.1f}h, {merge_sample} PRs" if merge_sample else "No data"

        iterations_display = f"{median_iterations:.1f}" if median_iterations else "N/A"
        iterations_detail = f"Max: {max_iterations}" if max_iterations else "No data"

        size_display = f"{median_commits:.1f}" if median_commits else "N/A"
        size_detail = f"P85: {p85_commits:.1f} commits" if p85_commits else "No data"

        # Calculate status
        status_html, status_tooltip, status_priority = calculate_composite_status(
            merge_time=median_merge if median_merge else None,
            iterations=median_iterations if median_iterations else None,
            pr_size=median_commits if median_commits else None
        )

        projects_with_status.append({
            'proj_name': proj_name,
            'total_prs': total_prs,
            'merge_display': merge_display,
            'merge_detail': merge_detail,
            'iterations_display': iterations_display,
            'iterations_detail': iterations_detail,
            'size_display': size_display,
            'size_detail': size_detail,
            'status_html': status_html,
            'status_tooltip': status_tooltip,
            'status_priority': status_priority
        })

    # Sort by status priority (Red->Amber->Green), then by total PRs
    projects_with_status.sort(key=lambda x: (x['status_priority'], -x['total_prs']))

    # Generate HTML rows
    project_rows_html = ""
    for proj_data in projects_with_status:
        project_rows_html += f"""
        <tr>
            <td><strong>{proj_data['proj_name']}</strong></td>
            <td>{proj_data['total_prs']}</td>
            <td title="{proj_data['merge_detail']}">{proj_data['merge_display']}</td>
            <td title="{proj_data['iterations_detail']}">{proj_data['iterations_display']}</td>
            <td title="{proj_data['size_detail']}">{proj_data['size_display']}</td>
            <td title="{proj_data['status_tooltip']}">{proj_data['status_html']}</td>
        </tr>
        """

    # Calculate totals
    total_prs_all = sum(p.get('total_prs_analyzed', 0) for p in projects)
    projects_with_prs = sum(1 for p in projects if p.get('total_prs_analyzed', 0) > 0)

    # Get collection date
    collection_date = latest_week.get('week_date', 'Unknown')

    # Get mobile-responsive framework
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start='#f093fb',
        header_gradient_end='#f5576c',
        include_table_scroll=True,
        include_expandable_rows=False,
        include_glossary=True
    )

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Collaboration Dashboard - PR Metrics</title>
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
            border-left: 4px solid #fb7185;
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

        /* Sortable column styling */
        th.sortable {{
            cursor: pointer;
            user-select: none;
        }}

        th.sortable:hover {{
            background: var(--bg-primary);
        }}

        th.sortable::after {{
            content: ' ↕';
            color: var(--text-secondary);
            font-size: 0.7em;
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
            <h1>Collaboration Dashboard</h1>
            <div class="subtitle">Code Review & PR Metrics - Team Collaboration</div>
            <div class="timestamp">Data collected: {collection_date} • Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Total PRs (90 days)</div>
                <div class="metric-value">{total_prs_all:,}</div>
                <div class="metric-detail">Across all projects</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Projects with PRs</div>
                <div class="metric-value">{projects_with_prs}</div>
                <div class="metric-detail">Active code review</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Avg PRs per Project</div>
                <div class="metric-value">{total_prs_all // projects_with_prs if projects_with_prs > 0 else 0}</div>
                <div class="metric-detail">Review activity</div>
            </div>
        </div>

        <div class="table-card">
            <h2>PR Metrics by Project</h2>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Project</th>
                            <th>Total PRs</th>
                            <th>Merge Time (Median)</th>
                            <th>Iterations (Median)</th>
                            <th>Size (Median Commits)</th>
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
                    <div class="glossary-term">Code Review Metrics</div>
                    <div class="glossary-definition">
                        Code review metrics measure the efficiency and effectiveness of your team's collaboration process.
                        Fast, thorough reviews help maintain code quality while keeping development velocity high.
                        These metrics help identify bottlenecks in the review process and opportunities for improvement.
                    </div>
                </div>

                <div class="glossary-item">
                    <div class="glossary-term">PR Merge Time (Median)</div>
                    <div class="glossary-definition">
                        The total time from when a pull request is created to when it's merged into the main branch, measured in hours.
                        <strong>Lower is better</strong> - faster merges mean quicker delivery and less time for merge conflicts to develop.
                        <br><br>
                        This metric includes review time, iteration time, and any approval/CI delays.
                        Long merge times can indicate complex changes, multiple review rounds, or process bottlenecks.
                    </div>
                </div>

                <div class="glossary-item">
                    <div class="glossary-term">Review Iteration Count (Median)</div>
                    <div class="glossary-definition">
                        The number of review cycles (comments, changes, re-review) before a PR is merged.
                        <strong>Fewer iterations can indicate</strong> clear requirements, good PR descriptions, and aligned expectations.
                        <br><br>
                        However, some iteration is healthy - it means thorough review.
                        Very high iteration counts might suggest unclear requirements, large PR scope,
                        or misaligned expectations between author and reviewers.
                    </div>
                </div>

                <div class="glossary-item">
                    <div class="glossary-term">PR Size (Median Commits)</div>
                    <div class="glossary-definition">
                        The number of commits in a pull request. Used as a proxy for PR complexity and reviewability.
                        <strong>Smaller PRs are generally easier to review</strong> and have faster review cycles.
                        <br><br>
                        Small PRs (1-5 commits) are easier to review thoroughly and merge quickly.
                        Large PRs (>10 commits) may indicate features that could be broken down,
                        or complex refactorings that need extra review attention.
                        <br><br>
                        Note: Commit count is an imperfect proxy - what matters most is the amount of code change and conceptual complexity.
                    </div>
                </div>

                <div class="glossary-item">
                    <div class="glossary-term">Overall Status</div>
                    <div class="glossary-definition">
                        The status indicator for each project is calculated by evaluating collaboration metrics together.
                        <br><br>
                        <strong>Status Determination:</strong>
                        <ul style="margin: 10px 0; padding-left: 20px;">
                            <li><strong style="color: #10b981;">✓ Good:</strong> All metrics meet target thresholds</li>
                            <li><strong style="color: #f59e0b;">⚠ Caution:</strong> One metric needs attention</li>
                            <li><strong style="color: #ef4444;">● Action Needed:</strong> Multiple metrics miss targets</li>
                        </ul>
                        <br>
                        <strong>Thresholds Used:</strong>
                        <ul style="margin: 10px 0; padding-left: 20px;">
                            <li><strong>Merge Time:</strong> Good &lt; 24h | Caution 24-72h | Poor &gt; 72h</li>
                            <li><strong>Iterations:</strong> Good ≤ 2 | Caution 3-5 | Poor &gt; 5</li>
                            <li><strong>PR Size:</strong> Good ≤ 5 commits | Caution 6-10 | Poor &gt; 10 commits</li>
                        </ul>
                        <br>
                        <em>Note: These thresholds are guidelines based on common industry practices. Hover over the status to see specific metric values for each project.</em>
                    </div>
                </div>

                <div class="glossary-item">
                    <div class="glossary-term">Median vs P85</div>
                    <div class="glossary-definition">
                        <strong>Median (P50):</strong> The middle value - half of PRs are faster, half are slower.
                        This represents the typical experience.
                        <br><br>
                        <strong>P85 (85th Percentile):</strong> 85% of PRs complete within this time.
                        This shows realistic upper bounds while filtering out extreme outliers.
                        <br><br>
                        Together, these give you both typical and worst-case scenarios for planning.
                    </div>
                </div>

                <h3 style="margin-top: 30px; color: #f5576c;">📊 Data Collection Details</h3>

                <div class="glossary-item">
                    <div class="glossary-term">Time Period</div>
                    <div class="glossary-definition">
                        <strong>90-day lookback period</strong> for all PR metrics.
                        This provides sufficient data for statistical significance while remaining relevant to current team practices.
                    </div>
                </div>

                <div class="glossary-item">
                    <div class="glossary-term">PR Criteria</div>
                    <div class="glossary-definition">
                        Only completed (merged or abandoned) pull requests are analyzed.
                        Draft PRs and PRs still in progress are excluded.
                        Review time is measured from PR creation to first substantive review comment.
                    </div>
                </div>

                <div class="glossary-item">
                    <div class="glossary-term">Sample Size</div>
                    <div class="glossary-definition">
                        Each metric shows its sample size in the tooltip.
                        Larger sample sizes (>30 PRs) provide more statistically reliable metrics.
                        Smaller samples may show higher variability and should be interpreted with care.
                    </div>
                </div>

                <div class="glossary-item">
                    <div class="glossary-term">Why These Metrics Matter</div>
                    <div class="glossary-definition">
                        Fast, effective code reviews improve both code quality and developer productivity.
                        Long review delays frustrate developers, increase context-switching costs,
                        and slow down feature delivery. These metrics help teams identify and address
                        collaboration bottlenecks while maintaining quality standards.
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

    output_file = output_dir / "collaboration_dashboard.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"[SUCCESS] Collaboration dashboard generated: {output_file}")
    return str(output_file)


if __name__ == "__main__":
    print("=" * 60)
    print("Collaboration Dashboard Generator")
    print("=" * 60)

    try:
        output_path = generate_collaboration_dashboard()
        print("\nDashboard ready!")
        print(f"Open: {output_path}")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Failed to generate dashboard: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
