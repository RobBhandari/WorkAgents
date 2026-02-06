"""
Generate Aggregated 70% Reduction Target Dashboard

Creates a simple, on-demand dashboard showing progress toward 70% reduction targets
for both ArmorCode security vulnerabilities and Azure DevOps bugs.

Usage:
    python generate_target_dashboard.py
    python generate_target_dashboard.py --output-file custom_dashboard.html
"""

import os
import sys
import json
import argparse

# Import mobile-responsive framework
try:
    from execution.dashboard_framework import get_dashboard_framework
except ModuleNotFoundError:
    from dashboard_framework import get_dashboard_framework
import logging
from datetime import datetime
from dotenv import load_dotenv

# Azure DevOps SDK
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'.tmp/target_dashboard_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def load_baseline(file_path: str, system_name: str) -> dict:
    """Load baseline data from file"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{system_name} baseline not found: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        baseline = json.load(f)

    logger.info(f"Loaded {system_name} baseline: {file_path}")
    return baseline


def query_current_ado_bugs() -> int:
    """Query current bugs from quality_history.json (matches quality dashboard methodology)

    This uses the same calculation as the quality dashboard:
    - Excludes 'Closed' AND 'Removed' states
    - Filters out ArmorCode security bugs (to avoid double-counting with Security Dashboard)
    - Aggregates across all tracked projects
    """
    try:
        quality_history_file = '.tmp/observatory/quality_history.json'

        if not os.path.exists(quality_history_file):
            logger.warning(f"Quality history file not found: {quality_history_file}")
            logger.warning("Run: python execution/ado_quality_metrics.py")
            raise FileNotFoundError(f"Quality history not found: {quality_history_file}")

        with open(quality_history_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Get latest week's data
        if not data.get('weeks') or len(data['weeks']) == 0:
            raise ValueError("No weeks data found in quality_history.json")

        latest_week = data['weeks'][-1]

        # Sum open_bugs_count across all projects
        total_bugs = sum(p['open_bugs_count'] for p in latest_week['projects'])

        logger.info(f"Current ADO bugs (from quality_history.json): {total_bugs}")
        logger.info(f"  Week: {latest_week['week_date']}")
        logger.info(f"  Projects: {len(latest_week['projects'])}")

        return total_bugs

    except Exception as e:
        logger.error(f"Error reading quality history: {e}")
        raise


def query_current_armorcode_vulns() -> int:
    """Query current vulnerabilities from security_history.json (matches security dashboard methodology)

    This uses the same calculation as the security dashboard:
    - HIGH + CRITICAL severity vulnerabilities only
    - OPEN + CONFIRMED status
    - Aggregates across all tracked products
    """
    try:
        security_history_file = '.tmp/observatory/security_history.json'

        if not os.path.exists(security_history_file):
            logger.warning(f"Security history file not found: {security_history_file}")
            logger.warning("Run: python execution/armorcode_enhanced_metrics.py")
            raise FileNotFoundError(f"Security history not found: {security_history_file}")

        with open(security_history_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Get latest week's data
        if not data.get('weeks') or len(data['weeks']) == 0:
            raise ValueError("No weeks data found in security_history.json")

        latest_week = data['weeks'][-1]
        metrics = latest_week['metrics']

        # Get total HIGH + CRITICAL vulnerabilities
        total_vulns = metrics['current_total']

        logger.info(f"Current ArmorCode vulnerabilities (from security_history.json): {total_vulns}")
        logger.info(f"  Week: {latest_week['week_date']}")
        logger.info(f"  Critical: {metrics['severity_breakdown']['critical']}")
        logger.info(f"  High: {metrics['severity_breakdown']['high']}")

        return total_vulns

    except Exception as e:
        logger.error(f"Error reading security history: {e}")
        raise


def load_last_run_state() -> dict:
    """Load last run state for calculating net burn"""
    last_run_file = '.tmp/target_dashboard_last_run.json'

    if os.path.exists(last_run_file):
        with open(last_run_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    return None


def save_current_state(security_count: int, bugs_count: int):
    """Save current state as last run for next comparison"""
    last_run_file = '.tmp/target_dashboard_last_run.json'
    os.makedirs('.tmp', exist_ok=True)

    state = {
        'timestamp': datetime.now().isoformat(),
        'security_vulnerabilities': security_count,
        'bugs': bugs_count
    }

    with open(last_run_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)

    logger.info(f"Saved current state to {last_run_file}")


def calculate_metrics(baseline_count: int, target_count: int, current_count: int,
                     weeks_to_target: int) -> dict:
    """Calculate progress metrics for target dashboard

    Focuses on fixed baseline → target tracking:
    - Baseline (Dec 1, 2025): Starting point
    - Current: Where we are now
    - Target (June 30, 2026): End goal (70% reduction)
    """

    # Progress from baseline (can be negative if count increased)
    total_reduction_needed = baseline_count - target_count
    progress_from_baseline = baseline_count - current_count
    progress_pct = (progress_from_baseline / total_reduction_needed * 100) if total_reduction_needed > 0 else 0

    # Days/weeks remaining to target date
    target_date = datetime.strptime('2026-06-30', '%Y-%m-%d')
    today = datetime.now()
    days_remaining = (target_date - today).days
    weeks_remaining = days_remaining / 7

    # Remaining work to hit target
    remaining_to_target = current_count - target_count

    # Required weekly burn FROM CURRENT POSITION to hit target
    required_weekly_burn = remaining_to_target / weeks_remaining if weeks_remaining > 0 else 0

    # Status determination based on progress percentage
    if progress_pct >= 100:
        status = 'TARGET MET'
        status_color = '#10b981'  # Green
    elif progress_pct >= 70:
        status = 'ON TRACK'
        status_color = '#10b981'  # Green
    elif progress_pct >= 40:
        status = 'BEHIND SCHEDULE'
        status_color = '#f59e0b'  # Amber
    else:
        status = 'AT RISK'
        status_color = '#ef4444'  # Red

    return {
        'baseline_count': baseline_count,
        'current_count': current_count,
        'target_count': target_count,
        'progress_from_baseline': progress_from_baseline,
        'progress_pct': round(progress_pct, 1),
        'days_remaining': days_remaining,
        'weeks_remaining': round(weeks_remaining, 1),
        'required_weekly_burn': round(required_weekly_burn, 2),
        'status': status,
        'status_color': status_color,
        'remaining_to_target': remaining_to_target
    }


def generate_html(security_metrics: dict, bugs_metrics: dict) -> str:
    """Generate HTML dashboard"""

    now = datetime.now()

    # Get mobile-responsive framework
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start='#1e40af',
        header_gradient_end='#1e3a8a',
        include_table_scroll=True,
        include_expandable_rows=False,
        include_glossary=False
    )

    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>70% Reduction Target Dashboard - {now.strftime('%Y-%m-%d')}</title>
    {framework_css}
    <style>
        /* Dashboard-specific styles */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}

        @media (max-width: 1024px) {{
            .metrics-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

        @media (max-width: 768px) {{
            .metrics-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .metric-card {{
            background: var(--bg-secondary);
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px var(--shadow);
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
        }}

        .metric-unit {{
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-top: 4px;
        }}

        .progress-section {{
            margin-top: 20px;
            padding: 20px;
            background: var(--bg-tertiary);
            border-radius: 8px;
        }}

        .progress-row {{
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid var(--border-color);
        }}

        .refresh-btn {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.875rem;
            font-weight: 600;
            transition: all 0.2s ease;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
        }}

        .refresh-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }}

        .refresh-btn:active {{
            transform: translateY(0);
        }}

        .section {{
            background: var(--bg-secondary);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid var(--border-color);
        }}

        .section-title {{
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--text-primary);
        }}

        .status-badge {{
            display: inline-block;
            padding: 6px 16px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.875rem;
            color: white;
        }}

        .progress-section {{
            margin-top: 20px;
            padding: 20px;
            background: var(--bg-tertiary);
            border-radius: 8px;
        }}

        .progress-row {{
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid var(--border-color);
        }}

        .progress-row:last-child {{
            border-bottom: none;
        }}

        .progress-label {{
            color: var(--text-secondary);
            font-size: 0.875rem;
        }}

        .progress-value {{
            color: var(--text-primary);
            font-weight: 600;
        }}

        .footer {{
            text-align: center;
            padding: 20px;
            color: var(--text-secondary);
            font-size: 0.875rem;
            margin-top: 30px;
        }}

        @media (max-width: 768px) {{
            .metrics-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
    </style>
</head>
<body>
    <div class="theme-toggle" onclick="toggleTheme()">
        <span id="theme-icon">🌙</span>
        <span id="theme-label">Dark</span>
    </div>

    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🎯 70% Reduction Target Dashboard</h1>
            <div class="subtitle">On-Demand Target Tracking • Dec 1, 2025 → June 30, 2026</div>
            <div class="timestamp">Last Updated: {now.strftime('%B %d, %Y at %H:%M')}</div>
        </div>

        <!-- Security Vulnerabilities Section -->
        <div class="section">
            <div class="section-header">
                <div class="section-title">🔒 Security Vulnerabilities (ArmorCode)</div>
            </div>

            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Baseline</div>
                    <div class="metric-value">{security_metrics['baseline_count']}</div>
                    <div class="metric-unit">Dec 1, 2025</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Current</div>
                    <div class="metric-value">{security_metrics['current_count']}</div>
                    <div class="metric-unit">vulnerabilities</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Target</div>
                    <div class="metric-value">{security_metrics['target_count']}</div>
                    <div class="metric-unit">June 30, 2026</div>
                </div>
                <div class="metric-card" style="background: linear-gradient(135deg, {security_metrics['status_color']}E6 0%, {security_metrics['status_color']}B3 100%); border: 1px solid {security_metrics['status_color']}80; box-shadow: 0 2px 8px {security_metrics['status_color']}40;">
                    <div class="metric-label" style="color: white; opacity: 0.95;">Progress</div>
                    <div class="metric-value" style="color: white;">{security_metrics['progress_pct']}%</div>
                    <div class="metric-unit" style="color: white; opacity: 0.9;">toward goal</div>
                </div>
            </div>

            <div class="progress-section">
                <div class="progress-row">
                    <span class="progress-label">Progress from Baseline:</span>
                    <span class="progress-value">{security_metrics['progress_from_baseline']:+d} vulnerabilities</span>
                </div>
                <div class="progress-row">
                    <span class="progress-label">Remaining to Target:</span>
                    <span class="progress-value">{security_metrics['remaining_to_target']} vulnerabilities</span>
                </div>
                <div class="progress-row">
                    <span class="progress-label">Days Remaining:</span>
                    <span class="progress-value">{security_metrics['days_remaining']} days ({security_metrics['weeks_remaining']} weeks)</span>
                </div>
                <div class="progress-row">
                    <span class="progress-label">Required Weekly Burn (from now):</span>
                    <span class="progress-value">{security_metrics['required_weekly_burn']:.2f} vulnerabilities/week</span>
                </div>
            </div>
        </div>

        <!-- Bugs Section -->
        <div class="section">
            <div class="section-header">
                <div class="section-title">🐛 Bugs (Azure DevOps)</div>
            </div>

            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Baseline</div>
                    <div class="metric-value">{bugs_metrics['baseline_count']}</div>
                    <div class="metric-unit">Dec 1, 2025</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Current</div>
                    <div class="metric-value">{bugs_metrics['current_count']}</div>
                    <div class="metric-unit">bugs</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Target</div>
                    <div class="metric-value">{bugs_metrics['target_count']}</div>
                    <div class="metric-unit">June 30, 2026</div>
                </div>
                <div class="metric-card" style="background: linear-gradient(135deg, {bugs_metrics['status_color']}E6 0%, {bugs_metrics['status_color']}B3 100%); border: 1px solid {bugs_metrics['status_color']}80; box-shadow: 0 2px 8px {bugs_metrics['status_color']}40;">
                    <div class="metric-label" style="color: white; opacity: 0.95;">Progress</div>
                    <div class="metric-value" style="color: white;">{bugs_metrics['progress_pct']}%</div>
                    <div class="metric-unit" style="color: white; opacity: 0.9;">toward goal</div>
                </div>
            </div>

            <div class="progress-section">
                <div class="progress-row">
                    <span class="progress-label">Progress from Baseline:</span>
                    <span class="progress-value">{bugs_metrics['progress_from_baseline']:+d} bugs</span>
                </div>
                <div class="progress-row">
                    <span class="progress-label">Remaining to Target:</span>
                    <span class="progress-value">{bugs_metrics['remaining_to_target']} bugs</span>
                </div>
                <div class="progress-row">
                    <span class="progress-label">Days Remaining:</span>
                    <span class="progress-value">{bugs_metrics['days_remaining']} days ({bugs_metrics['weeks_remaining']} weeks)</span>
                </div>
                <div class="progress-row">
                    <span class="progress-label">Required Weekly Burn (from now):</span>
                    <span class="progress-value">{bugs_metrics['required_weekly_burn']:.2f} bugs/week</span>
                </div>
            </div>
        </div>

        <!-- Footer -->
        <div class="footer">
            <p>Director Observatory • 70% Reduction Target Tracking</p>
            <p style="margin-top: 8px;">Run <code>python execution/generate_target_dashboard.py</code> to update</p>
        </div>
    </div>

    {framework_js}
    <script>
        // Copy refresh command to clipboard
        function copyRefreshCommand() {{
            const command = 'python execution/generate_target_dashboard.py';

            navigator.clipboard.writeText(command).then(function() {{
                // Success feedback
                const btn = event.target;
                const originalText = btn.textContent;
                btn.textContent = '✓ Copied!';
                btn.style.background = 'linear-gradient(135deg, #10b981 0%, #059669 100%)';

                setTimeout(function() {{
                    btn.textContent = originalText;
                    btn.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
                }}, 2000);
            }}, function(err) {{
                // Fallback for older browsers
                alert('Copy this command to your terminal:\\n\\n' + command);
            }});
        }}

        // Load theme preference
        document.addEventListener('DOMContentLoaded', function() {{
            const savedTheme = localStorage.getItem('theme') || 'dark';
            document.documentElement.setAttribute('data-theme', savedTheme);

            const icon = document.getElementById('theme-icon');
            const label = document.getElementById('theme-label');

            if (savedTheme === 'dark') {{
                icon.textContent = '🌙';
                label.textContent = 'Dark';
            }} else {{
                icon.textContent = '☀️';
                label.textContent = 'Light';
            }}
        }});
    </script>
</body>
</html>
"""
    return html


def main():
    """Main execution"""
    try:
        parser = argparse.ArgumentParser(description='Generate 70% reduction target dashboard')
        parser.add_argument('--output-file', default='.tmp/observatory/dashboards/target_dashboard.html',
                          help='Output HTML file path')
        args = parser.parse_args()

        logger.info("Starting target dashboard generation")
        logger.info("="*70)

        # Load baselines
        security_baseline = load_baseline('data/armorcode_baseline.json', 'ArmorCode Security')
        bugs_baseline = load_baseline('data/baseline.json', 'ADO Bugs')

        # Query current state
        logger.info("Querying current state...")
        current_security = query_current_armorcode_vulns()
        current_bugs = query_current_ado_bugs()

        # Calculate metrics
        logger.info("Calculating metrics...")
        security_metrics = calculate_metrics(
            baseline_count=security_baseline['total_vulnerabilities'],
            target_count=security_baseline['target_vulnerabilities'],
            current_count=current_security,
            weeks_to_target=security_baseline['weeks_to_target']
        )

        bugs_metrics = calculate_metrics(
            baseline_count=bugs_baseline['open_count'],
            target_count=bugs_baseline['target_count'],
            current_count=current_bugs,
            weeks_to_target=bugs_baseline['weeks_to_target']
        )

        # Generate HTML
        logger.info("Generating HTML dashboard...")
        html = generate_html(security_metrics, bugs_metrics)

        # Save dashboard
        os.makedirs(os.path.dirname(args.output_file), exist_ok=True)
        with open(args.output_file, 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info("="*70)
        logger.info(f"Dashboard generated successfully!")
        logger.info(f"Output: {args.output_file}")
        logger.info("="*70)

        # Print summary
        print(f"\n{'='*70}")
        print(f"70% REDUCTION TARGET DASHBOARD")
        print(f"{'='*70}")
        print(f"\nSecurity Vulnerabilities:")
        print(f"  Current: {current_security} ({security_metrics['progress_pct']}% progress)")
        print(f"  Status: {security_metrics['status']}")
        print(f"\nBugs:")
        print(f"  Current: {current_bugs} ({bugs_metrics['progress_pct']}% progress)")
        print(f"  Status: {bugs_metrics['status']}")
        print(f"\nDashboard: {args.output_file}")
        print(f"{'='*70}\n")

        sys.exit(0)

    except Exception as e:
        logger.error(f"Failed to generate dashboard: {e}", exc_info=True)
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
