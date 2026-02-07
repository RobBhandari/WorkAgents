#!/usr/bin/env python3
"""
Generate AI Contributions Dashboard for Director Observatory
Shows Devin AI vs Human PR contributions
"""

import json
import os
import sys


def load_devin_analysis():
    """Load Devin analysis from JSON file"""
    analysis_file = ".tmp/observatory/devin_analysis.json"

    if not os.path.exists(analysis_file):
        print(f"[ERROR] Devin analysis file not found: {analysis_file}")
        print("Run: py execution/analyze_devin_prs.py")
        return None

    with open(analysis_file, encoding="utf-8") as f:
        return json.load(f)


def load_risk_metrics():
    """Load risk metrics for author stats"""
    risk_file = ".tmp/observatory/risk_history.json"

    if not os.path.exists(risk_file):
        return None

    with open(risk_file, encoding="utf-8") as f:
        return json.load(f)


def get_author_stats(risk_data):
    """Calculate author contribution statistics"""
    from collections import defaultdict

    if not risk_data or "weeks" not in risk_data:
        return {}

    latest_week = risk_data["weeks"][-1]
    author_stats = defaultdict(int)

    for project in latest_week.get("projects", []):
        raw_prs = project.get("raw_prs", [])
        for pr in raw_prs:
            author = pr.get("created_by", "Unknown")
            author_stats[author] += 1

    return dict(author_stats)


def get_project_stats(risk_data):
    """Calculate per-project Devin contribution stats"""
    from collections import defaultdict

    if not risk_data or "weeks" not in risk_data:
        return {}

    latest_week = risk_data["weeks"][-1]
    project_stats = defaultdict(lambda: {"total": 0, "devin": 0})

    for project in latest_week.get("projects", []):
        project_name = project["project_name"]
        raw_prs = project.get("raw_prs", [])

        for pr in raw_prs:
            project_stats[project_name]["total"] += 1
            author = pr.get("created_by", "").lower()
            if "devin" in author:
                project_stats[project_name]["devin"] += 1

    return dict(project_stats)


def generate_dashboard_html(analysis, author_stats, project_stats):
    """Generate the AI contributions dashboard HTML"""

    summary = analysis["summary"]
    total_prs = summary["total_prs"]
    devin_prs = summary["devin_prs"]
    human_prs = summary["human_prs"]
    devin_pct = summary["devin_percentage"]

    # Top 10 authors for chart
    top_authors = sorted(author_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    author_labels = [f'"{author}"' for author, _ in top_authors]
    author_counts = [count for _, count in top_authors]

    # Project stats for chart
    project_items = []
    for project, stats in sorted(project_stats.items(), key=lambda x: x[1]["total"], reverse=True):
        if stats["total"] > 0:
            project_items.append(
                {
                    "name": project,
                    "total": stats["total"],
                    "devin": stats["devin"],
                    "human": stats["total"] - stats["devin"],
                    "devin_pct": round(stats["devin"] / stats["total"] * 100, 1),
                }
            )

    # Recent Devin PRs table rows
    recent_prs_html = ""
    for pr in analysis.get("devin_prs", [])[:15]:  # Show 15 most recent
        recent_prs_html += f"""
            <tr>
                <td>#{pr['pr_id']}</td>
                <td>{pr['project']}</td>
                <td style="max-width: 400px; white-space: normal;">{pr['title']}</td>
                <td>{pr['created_by']}</td>
                <td>{pr['commit_count']}</td>
                <td>{pr['created_date'][:10] if pr.get('created_date') else 'N/A'}</td>
            </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Contributions - Director Observatory</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        :root {{
            --bg-primary: #f9fafb;
            --bg-secondary: #ffffff;
            --bg-card: rgba(255, 255, 255, 0.05);
            --text-primary: #1f2937;
            --text-secondary: #6b7280;
            --text-tertiary: #94a3b8;
            --border-color: rgba(255, 255, 255, 0.1);
            --shadow: rgba(0,0,0,0.1);
            --ai-color: #8b5cf6;
            --human-color: #3b82f6;
        }}

        [data-theme="dark"] {{
            --bg-primary: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            --bg-secondary: #1e293b;
            --bg-card: rgba(255, 255, 255, 0.05);
            --text-primary: #f1f5f9;
            --text-secondary: #cbd5e1;
            --text-tertiary: #94a3b8;
            --border-color: rgba(255, 255, 255, 0.1);
            --shadow: rgba(0,0,0,0.3);
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-primary);
            padding: 40px 20px;
            color: var(--text-primary);
            min-height: 100vh;
        }}

        [data-theme="light"] body {{
            background: linear-gradient(135deg, #f9fafb 0%, #e5e7eb 100%);
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        .header {{
            text-align: center;
            margin-bottom: 50px;
        }}

        .header h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 16px;
            background: linear-gradient(135deg, var(--ai-color) 0%, var(--human-color) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .header .subtitle {{
            font-size: 1.1rem;
            color: var(--text-secondary);
        }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}

        .metric-card {{
            background: var(--bg-card);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            border-left: 4px solid var(--ai-color);
        }}

        [data-theme="light"] .metric-card {{
            background: white;
            box-shadow: 0 2px 8px var(--shadow);
        }}

        .metric-card h3 {{
            font-size: 0.9rem;
            color: var(--text-tertiary);
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .metric-card .value {{
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 8px;
        }}

        .metric-card .label {{
            font-size: 0.95rem;
            color: var(--text-secondary);
        }}

        .chart-section {{
            background: var(--bg-card);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 32px;
            margin-bottom: 30px;
        }}

        [data-theme="light"] .chart-section {{
            background: white;
            box-shadow: 0 2px 8px var(--shadow);
        }}

        .chart-section h2 {{
            font-size: 1.5rem;
            margin-bottom: 24px;
            color: var(--text-primary);
        }}

        .chart-container {{
            position: relative;
            height: 400px;
        }}

        .table-container {{
            background: var(--bg-card);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 32px;
            overflow-x: auto;
        }}

        [data-theme="light"] .table-container {{
            background: white;
            box-shadow: 0 2px 8px var(--shadow);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th {{
            text-align: left;
            padding: 12px;
            border-bottom: 2px solid var(--border-color);
            color: var(--text-tertiary);
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        td {{
            padding: 12px;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-secondary);
        }}

        tr:hover {{
            background: rgba(255, 255, 255, 0.03);
        }}

        [data-theme="light"] tr:hover {{
            background: rgba(0, 0, 0, 0.02);
        }}

        .theme-toggle {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--bg-card);
            backdrop-filter: blur(10px);
            border: 2px solid var(--border-color);
            border-radius: 50px;
            padding: 8px 16px;
            cursor: pointer;
            font-size: 1.1rem;
            z-index: 1000;
        }}

        .back-link {{
            display: inline-block;
            margin-bottom: 30px;
            color: var(--ai-color);
            text-decoration: none;
            font-weight: 600;
        }}

        .back-link:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="theme-toggle" onclick="toggleTheme()" title="Toggle dark/light mode">
        <span id="theme-icon">🌙</span>
    </div>

    <div class="container">
        <a href="index.html" class="back-link">← Back to Observatory</a>

        <div class="header">
            <h1>🤖 AI Contributions Dashboard</h1>
            <div class="subtitle">Tracking Devin AI vs Human Development Contributions</div>
        </div>

        <!-- Summary Metrics -->
        <div class="metrics-grid">
            <div class="metric-card" style="border-left-color: var(--ai-color);">
                <h3>Devin AI PRs</h3>
                <div class="value">{devin_prs}</div>
                <div class="label">{devin_pct:.1f}% of total</div>
            </div>

            <div class="metric-card" style="border-left-color: var(--human-color);">
                <h3>Human PRs</h3>
                <div class="value">{human_prs}</div>
                <div class="label">{100-devin_pct:.1f}% of total</div>
            </div>

            <div class="metric-card" style="border-left-color: #10b981;">
                <h3>Total PRs</h3>
                <div class="value">{total_prs}</div>
                <div class="label">Last 90 days</div>
            </div>

            <div class="metric-card" style="border-left-color: #f59e0b;">
                <h3>Contributors</h3>
                <div class="value">{len(author_stats)}</div>
                <div class="label">Unique authors</div>
            </div>
        </div>

        <!-- Devin vs Human Chart -->
        <div class="chart-section">
            <h2>AI vs Human Contributions</h2>
            <div class="chart-container">
                <canvas id="aiVsHumanChart"></canvas>
            </div>
        </div>

        <!-- Top Contributors Chart -->
        <div class="chart-section">
            <h2>Top Contributors</h2>
            <div class="chart-container">
                <canvas id="contributorsChart"></canvas>
            </div>
        </div>

        <!-- Project Breakdown Chart -->
        <div class="chart-section">
            <h2>Devin Contributions by Project</h2>
            <div class="chart-container">
                <canvas id="projectsChart"></canvas>
            </div>
        </div>

        <!-- Recent Devin PRs Table -->
        <div class="table-container">
            <h2 style="margin-bottom: 20px;">Recent Devin PRs</h2>
            <table>
                <thead>
                    <tr>
                        <th>PR ID</th>
                        <th>Project</th>
                        <th>Title</th>
                        <th>Author</th>
                        <th>Commits</th>
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody>
                    {recent_prs_html}
                </tbody>
            </table>
        </div>

        <!-- Data Collection Methodology -->
        <div class="chart-section" style="margin-top: 30px;">
            <h2>📊 Data Collection Methodology</h2>
            <p style="color: var(--text-secondary); line-height: 1.8; margin-bottom: 20px;">
                This dashboard analyzes pull request authorship to identify AI-generated vs human-generated contributions.
                The statistics shown are based on the following data collection approach:
            </p>

            <h3 style="font-size: 1.1rem; margin-top: 25px; margin-bottom: 12px; color: var(--text-primary);">
                Detection Criteria
            </h3>
            <p style="color: var(--text-secondary); line-height: 1.8; margin-bottom: 15px;">
                A pull request is classified as "Devin AI" if <strong>any</strong> of the following indicators are present:
            </p>
            <ul style="color: var(--text-secondary); line-height: 1.8; padding-left: 30px; margin-bottom: 20px;">
                <li><strong>Author name</strong> contains "devin" (case-insensitive)
                    <br><em style="font-size: 0.9rem; color: var(--text-tertiary);">Example: "Devin Azure DevOps Integration", "Devin AI"</em>
                </li>
                <li><strong>Author email</strong> contains "devin"
                    <br><em style="font-size: 0.9rem; color: var(--text-tertiary);">Example: "devin.azuredevopsintegration@theaccessgroup.com"</em>
                </li>
                <li><strong>Branch name</strong> contains "devin"
                    <br><em style="font-size: 0.9rem; color: var(--text-tertiary);">Example: "refs/heads/devin/1766033274-add-feeearner-email-update-departmentid"</em>
                </li>
                <li><strong>PR title or description</strong> explicitly mentions "Devin"</li>
            </ul>

            <h3 style="font-size: 1.1rem; margin-top: 25px; margin-bottom: 12px; color: var(--text-primary);">
                Data Sources
            </h3>
            <ul style="color: var(--text-secondary); line-height: 1.8; padding-left: 30px; margin-bottom: 20px;">
                <li><strong>Source:</strong> Azure DevOps Git API</li>
                <li><strong>Timeframe:</strong> Last 90 days of completed pull requests</li>
                <li><strong>Scope:</strong> All active projects across the organization</li>
                <li><strong>Limit:</strong> Up to 200 most recent PRs per repository (top 5 repos per project)</li>
            </ul>

            <h3 style="font-size: 1.1rem; margin-top: 25px; margin-bottom: 12px; color: var(--text-primary);">
                Known Limitations
            </h3>
            <ul style="color: var(--text-secondary); line-height: 1.8; padding-left: 30px; margin-bottom: 20px;">
                <li>PRs where Devin initiated work but a human created the PR may be misclassified as "Human"</li>
                <li>Custom Devin configurations with different naming patterns may not be detected</li>
                <li>Historical PRs beyond 90 days are not included in current analysis</li>
                <li>PRs in archived or disabled repositories are excluded</li>
            </ul>

            <h3 style="font-size: 1.1rem; margin-top: 25px; margin-bottom: 12px; color: var(--text-primary);">
                Verification Steps
            </h3>
            <p style="color: var(--text-secondary); line-height: 1.8; margin-bottom: 15px;">
                To verify these statistics with your teams:
            </p>
            <ul style="color: var(--text-secondary); line-height: 1.8; padding-left: 30px; margin-bottom: 20px;">
                <li>Cross-reference PR counts with Azure DevOps PR history for specific projects</li>
                <li>Check individual PR authors in Azure DevOps to confirm Devin identification</li>
                <li>Review the "Recent Devin PRs" table above for sample data validation</li>
                <li>Examine branch naming patterns in your repositories for Devin conventions</li>
            </ul>

            <div style="background: rgba(139, 92, 246, 0.1); border-left: 4px solid #8b5cf6; padding: 15px; border-radius: 6px; margin-top: 20px;">
                <strong style="color: var(--text-primary);">📝 Note for Team Review:</strong>
                <p style="margin-top: 8px; margin-bottom: 0; color: var(--text-secondary); line-height: 1.6;">
                    These statistics are automatically collected from Azure DevOps. Please review with your teams to ensure
                    the Devin detection criteria align with your organization's Devin usage patterns. If you use custom
                    Devin configurations or naming conventions, the detection rules may need adjustment.
                </p>
            </div>
        </div>
    </div>

    <script>
        // Theme Toggle
        function toggleTheme() {{
            const html = document.documentElement;
            const current = html.getAttribute('data-theme');
            const newTheme = current === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(newTheme);
            updateCharts();
        }}

        function updateThemeIcon(theme) {{
            const icon = document.getElementById('theme-icon');
            icon.textContent = theme === 'dark' ? '🌙' : '☀️';
        }}

        // Load theme
        const savedTheme = localStorage.getItem('theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
        updateThemeIcon(savedTheme);

        // Chart colors
        function getChartColors() {{
            const theme = document.documentElement.getAttribute('data-theme');
            return {{
                text: theme === 'dark' ? '#cbd5e1' : '#6b7280',
                grid: theme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                ai: '#8b5cf6',
                human: '#3b82f6'
            }};
        }}

        // AI vs Human Pie Chart
        const aiVsHumanCtx = document.getElementById('aiVsHumanChart').getContext('2d');
        let aiVsHumanChart = new Chart(aiVsHumanCtx, {{
            type: 'doughnut',
            data: {{
                labels: ['Devin AI', 'Human'],
                datasets: [{{
                    data: [{devin_prs}, {human_prs}],
                    backgroundColor: ['#8b5cf6', '#3b82f6'],
                    borderWidth: 2,
                    borderColor: 'rgba(255, 255, 255, 0.1)'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        labels: {{
                            color: getChartColors().text,
                            font: {{ size: 14 }}
                        }}
                    }}
                }}
            }}
        }});

        // Top Contributors Bar Chart
        const contributorsCtx = document.getElementById('contributorsChart').getContext('2d');
        let contributorsChart = new Chart(contributorsCtx, {{
            type: 'bar',
            data: {{
                labels: [{', '.join(author_labels)}],
                datasets: [{{
                    label: 'PRs',
                    data: [{', '.join(map(str, author_counts))}],
                    backgroundColor: '#8b5cf6',
                    borderColor: '#8b5cf6',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{ color: getChartColors().text }},
                        grid: {{ color: getChartColors().grid }}
                    }},
                    x: {{
                        ticks: {{
                            color: getChartColors().text,
                            autoSkip: false,
                            maxRotation: 45,
                            minRotation: 45
                        }},
                        grid: {{ display: false }}
                    }}
                }},
                plugins: {{
                    legend: {{ display: false }}
                }}
            }}
        }});

        // Projects Chart
        const projectsCtx = document.getElementById('projectsChart').getContext('2d');
        const projectNames = {json.dumps([p['name'] for p in project_items])};
        const projectDevin = {json.dumps([p['devin'] for p in project_items])};
        const projectHuman = {json.dumps([p['human'] for p in project_items])};

        let projectsChart = new Chart(projectsCtx, {{
            type: 'bar',
            data: {{
                labels: projectNames,
                datasets: [
                    {{
                        label: 'Devin AI',
                        data: projectDevin,
                        backgroundColor: '#8b5cf6'
                    }},
                    {{
                        label: 'Human',
                        data: projectHuman,
                        backgroundColor: '#3b82f6'
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        stacked: true,
                        ticks: {{ color: getChartColors().text }},
                        grid: {{ color: getChartColors().grid }}
                    }},
                    x: {{
                        stacked: true,
                        ticks: {{
                            color: getChartColors().text,
                            autoSkip: false,
                            maxRotation: 45,
                            minRotation: 45
                        }},
                        grid: {{ display: false }}
                    }}
                }},
                plugins: {{
                    legend: {{
                        labels: {{
                            color: getChartColors().text,
                            font: {{ size: 14 }}
                        }}
                    }}
                }}
            }}
        }});

        // Update charts on theme change
        function updateCharts() {{
            const colors = getChartColors();

            [aiVsHumanChart, contributorsChart, projectsChart].forEach(chart => {{
                if (chart.options.plugins?.legend) {{
                    chart.options.plugins.legend.labels.color = colors.text;
                }}
                if (chart.options.scales?.y) {{
                    chart.options.scales.y.ticks.color = colors.text;
                    chart.options.scales.y.grid.color = colors.grid;
                }}
                if (chart.options.scales?.x) {{
                    chart.options.scales.x.ticks.color = colors.text;
                }}
                chart.update();
            }});
        }}
    </script>
</body>
</html>
"""

    return html


def save_dashboard(html, output_file=".tmp/observatory/dashboards/ai_contributions.html"):
    """Save the dashboard HTML"""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print("\n[SUCCESS] AI Contributions Dashboard generated!")
    print(f"  Location: {output_file}")
    print(f"  Size: {len(html):,} bytes")
    print(f"\nOpen in browser: start {output_file}")


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    print("AI Contributions Dashboard Generator")
    print("=" * 60)

    # Load data
    analysis = load_devin_analysis()
    if not analysis:
        exit(1)

    risk_data = load_risk_metrics()
    author_stats = get_author_stats(risk_data) if risk_data else {}
    project_stats = get_project_stats(risk_data) if risk_data else {}

    # Generate dashboard
    html = generate_dashboard_html(analysis, author_stats, project_stats)
    save_dashboard(html)

    print("\nFeatures:")
    print("  ✓ AI vs Human contribution pie chart")
    print("  ✓ Top contributors bar chart")
    print("  ✓ Project-level breakdown")
    print("  ✓ Recent Devin PRs table")
    print("  ✓ Dark/light theme toggle")
