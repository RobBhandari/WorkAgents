#!/usr/bin/env python3
"""
Generate Executive Trends Dashboard from Observatory history files

Reads historical JSON data and creates a trends dashboard showing:
- Forecast banner with target progress and burn rate analysis
- 8 key metrics with 12-week sparklines
- Week-over-week changes
- Trend indicators (↑↓→)
- View selector (4/12/24 weeks)
"""

import os
import json
import sys
from datetime import datetime
from pathlib import Path
from statistics import median

# Import mobile-responsive framework
try:
    from execution.dashboard_framework import get_dashboard_framework
except ModuleNotFoundError:
    from dashboard_framework import get_dashboard_framework

def load_history_file(file_path):
    """Load a history JSON file with error handling"""
    filename = os.path.basename(file_path)

    if not os.path.exists(file_path):
        print(f"  ⚠️ {filename}: File not found")
        return None

    try:
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            print(f"  ⚠️ {filename}: File is empty")
            return None

        # Load and parse JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Validate structure
        if not isinstance(data, dict):
            print(f"  ⚠️ {filename}: Invalid data structure (not a dictionary)")
            return None

        if 'weeks' not in data:
            print(f"  ⚠️ {filename}: Missing 'weeks' key")
            return None

        weeks = data.get('weeks', [])
        if not weeks:
            print(f"  ⚠️ {filename}: No weeks data found")
            return None

        print(f"  ✓ {filename}: Loaded successfully ({len(weeks)} weeks, {file_size:,} bytes)")
        return data

    except json.JSONDecodeError as e:
        print(f"  ✗ {filename}: JSON decode error - {e}")
        return None
    except UnicodeDecodeError as e:
        print(f"  ✗ {filename}: Unicode decode error - {e}")
        return None
    except Exception as e:
        print(f"  ✗ {filename}: Unexpected error - {e}")
        return None


def load_baseline_data():
    """Load baseline data for target calculations"""
    baselines = {}

    # Load ArmorCode baseline
    armorcode_file = 'data/armorcode_baseline.json'
    if os.path.exists(armorcode_file):
        with open(armorcode_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            baselines['security'] = data.get('total_vulnerabilities', 0)

    # Load ADO bugs baseline
    ado_file = 'data/baseline.json'
    if os.path.exists(ado_file):
        with open(ado_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            baselines['bugs'] = data.get('open_count', 0)  # Field is 'open_count' not 'total_bugs'

    return baselines


def calculate_target_progress():
    """Calculate overall target progress (70% reduction goal)"""
    baselines = load_baseline_data()

    # Get current counts from latest data
    quality_data = load_history_file('.tmp/observatory/quality_history.json')
    security_data = load_history_file('.tmp/observatory/security_history.json')

    if not quality_data or not security_data:
        return None

    # Current bugs (latest week)
    latest_quality = quality_data['weeks'][-1]
    current_bugs = sum(p.get('open_bugs_count', 0) for p in latest_quality.get('projects', []))

    # Current security vulns (latest week)
    latest_security = security_data['weeks'][-1]
    current_vulns = latest_security.get('metrics', {}).get('current_total', 0)

    # Calculate progress
    baseline_bugs = baselines.get('bugs', 0)
    baseline_vulns = baselines.get('security', 0)

    target_bugs = round(baseline_bugs * 0.3)  # 70% reduction = 30% remaining (round to match target dashboard)
    target_vulns = round(baseline_vulns * 0.3)

    # Progress calculation
    bugs_progress = ((baseline_bugs - current_bugs) / (baseline_bugs - target_bugs) * 100) if baseline_bugs > target_bugs else 0
    vulns_progress = ((baseline_vulns - current_vulns) / (baseline_vulns - target_vulns) * 100) if baseline_vulns > target_vulns else 0

    # Overall progress (average)
    overall_progress = (bugs_progress + vulns_progress) / 2

    # Weeks to target (June 30, 2026)
    target_date = datetime.strptime('2026-06-30', '%Y-%m-%d')
    today = datetime.now()
    weeks_remaining = max(0, (target_date - today).days / 7)

    # Burn rate analysis (4-week average) - SEPARATE for bugs and vulns
    if len(quality_data['weeks']) >= 5 and len(security_data['weeks']) >= 5:
        # Bugs 4 weeks ago
        bugs_4wk_ago = sum(p.get('open_bugs_count', 0) for p in quality_data['weeks'][-5].get('projects', []))
        bugs_burned_4wk = bugs_4wk_ago - current_bugs
        actual_bugs_burn_rate = bugs_burned_4wk / 4

        # Vulns 4 weeks ago
        vulns_4wk_ago = security_data['weeks'][-5].get('metrics', {}).get('current_total', 0)
        vulns_burned_4wk = vulns_4wk_ago - current_vulns
        actual_vulns_burn_rate = vulns_burned_4wk / 4
    else:
        actual_bugs_burn_rate = 0
        actual_vulns_burn_rate = 0

    # Required burn rates to hit target - SEPARATE for bugs and vulns
    remaining_bugs = current_bugs - target_bugs
    remaining_vulns = current_vulns - target_vulns
    required_bugs_burn_rate = remaining_bugs / weeks_remaining if weeks_remaining > 0 else 0
    required_vulns_burn_rate = remaining_vulns / weeks_remaining if weeks_remaining > 0 else 0

    # Trajectory
    if overall_progress >= 70:
        trajectory = 'On Track'
        trajectory_color = '#10b981'
    elif overall_progress >= 40:
        trajectory = 'Behind'
        trajectory_color = '#f59e0b'
    else:
        trajectory = 'Behind'
        trajectory_color = '#ef4444'

    # Forecast message - check if BOTH are going backwards
    bugs_going_backwards = actual_bugs_burn_rate <= 0
    vulns_going_backwards = actual_vulns_burn_rate <= 0

    if bugs_going_backwards and vulns_going_backwards:
        forecast_msg = f"⚠ Both bugs and vulnerabilities are increasing. Need to turn around immediately."
    elif bugs_going_backwards:
        forecast_msg = f"⚠ Bugs are increasing at {abs(actual_bugs_burn_rate):.1f}/wk. Vulnerabilities decreasing at {actual_vulns_burn_rate:.1f}/wk."
    elif vulns_going_backwards:
        forecast_msg = f"⚠ Vulnerabilities are increasing at {abs(actual_vulns_burn_rate):.1f}/wk. Bugs decreasing at {actual_bugs_burn_rate:.1f}/wk."
    else:
        # Both positive - show status
        bugs_pct = (actual_bugs_burn_rate / required_bugs_burn_rate * 100) if required_bugs_burn_rate > 0 else 0
        vulns_pct = (actual_vulns_burn_rate / required_vulns_burn_rate * 100) if required_vulns_burn_rate > 0 else 0
        avg_pct = (bugs_pct + vulns_pct) / 2

        if avg_pct >= 100:
            forecast_msg = f"On track: Current pace will reach target by June 30."
        else:
            forecast_msg = f"At current pace ({actual_bugs_burn_rate:.1f} bugs/wk, {actual_vulns_burn_rate:.1f} vulns/wk), reaching {int(avg_pct)}% of target by June 30."

    # Extract trend data for sparkline
    bugs_trend = []
    vulns_trend = []
    progress_trend = []

    for i in range(len(quality_data['weeks'])):
        week_bugs = sum(p.get('open_bugs_count', 0) for p in quality_data['weeks'][i].get('projects', []))
        bugs_trend.append(week_bugs)

        if i < len(security_data['weeks']):
            week_vulns = security_data['weeks'][i].get('metrics', {}).get('current_total', 0)
            vulns_trend.append(week_vulns)

            # Calculate progress for this week
            week_bugs_progress = ((baseline_bugs - week_bugs) / (baseline_bugs - target_bugs) * 100) if baseline_bugs > target_bugs else 0
            week_vulns_progress = ((baseline_vulns - week_vulns) / (baseline_vulns - target_vulns) * 100) if baseline_vulns > target_vulns else 0
            week_progress = (week_bugs_progress + week_vulns_progress) / 2
            progress_trend.append(round(week_progress, 1))

    return {
        'current': round(overall_progress, 1),
        'previous': progress_trend[-2] if len(progress_trend) > 1 else round(overall_progress, 1),
        'trend_data': progress_trend,
        'unit': '% progress',
        'forecast': {
            'trajectory': trajectory,
            'trajectory_color': trajectory_color,
            'weeks_to_target': round(weeks_remaining, 1),
            'required_bugs_burn': round(required_bugs_burn_rate, 2),
            'required_vulns_burn': round(required_vulns_burn_rate, 2),
            'actual_bugs_burn': round(actual_bugs_burn_rate, 2),
            'actual_vulns_burn': round(actual_vulns_burn_rate, 2),
            'forecast_msg': forecast_msg
        }
    }


def extract_trends_from_quality():
    """Extract bug and MTTR trends from quality_history.json"""
    data = load_history_file('.tmp/observatory/quality_history.json')
    if not data or not data.get('weeks'):
        return None

    weeks = data['weeks']
    total_bugs_trend = []
    mttr_trend = []

    for week in weeks:
        # Sum open bugs across all projects
        total_bugs = sum(p.get('open_bugs_count', 0) for p in week.get('projects', []))
        total_bugs_trend.append(total_bugs)

        # Average MTTR across projects
        mttr_values = [p.get('mttr', {}).get('mttr_days') for p in week.get('projects', [])
                      if p.get('mttr', {}).get('mttr_days') is not None]
        avg_mttr = sum(mttr_values) / len(mttr_values) if mttr_values else 0
        mttr_trend.append(round(avg_mttr, 1))

    return {
        'bugs': {
            'current': total_bugs_trend[-1] if total_bugs_trend else 0,
            'previous': total_bugs_trend[-2] if len(total_bugs_trend) > 1 else 0,
            'trend_data': total_bugs_trend,
            'unit': 'bugs'
        },
        'mttr': {
            'current': mttr_trend[-1] if mttr_trend else 0,
            'previous': mttr_trend[-2] if len(mttr_trend) > 1 else 0,
            'trend_data': mttr_trend,
            'unit': 'days'
        }
    }


def extract_trends_from_security():
    """Extract security trends from security_history.json"""
    data = load_history_file('.tmp/observatory/security_history.json')
    if not data or not data.get('weeks'):
        return None

    weeks = data['weeks']
    vuln_trend = []

    for week in weeks:
        metrics = week.get('metrics', {})
        total = metrics.get('current_total', 0)
        vuln_trend.append(total)

    return {
        'vulnerabilities': {
            'current': vuln_trend[-1] if vuln_trend else 0,
            'previous': vuln_trend[-2] if len(vuln_trend) > 1 else 0,
            'trend_data': vuln_trend,
            'unit': 'vulns'
        }
    }


def extract_trends_from_flow():
    """Extract flow trends from flow_history.json

    Uses median across all work types with operational metrics when cleanup is detected.
    Matches executive summary calculation for consistency.
    """
    data = load_history_file('.tmp/observatory/flow_history.json')
    if not data or not data.get('weeks'):
        return None

    weeks = data['weeks']
    lead_time_trend = []

    for week in weeks:
        projects = week.get('projects', [])

        # Collect lead times across all work types (matches exec summary logic)
        lead_times = []
        for proj in projects:
            # Check if project has work_type_metrics
            if 'work_type_metrics' in proj:
                # Aggregate across ALL work types
                for work_type, metrics in proj.get('work_type_metrics', {}).items():
                    dual_metrics = metrics.get('dual_metrics', {})
                    has_cleanup = dual_metrics.get('indicators', {}).get('is_cleanup_effort', False)

                    if has_cleanup:
                        # Use operational metrics for accurate performance view
                        operational = dual_metrics.get('operational', {})
                        op_p85 = operational.get('p85')
                        if op_p85:
                            lead_times.append(op_p85)
                    else:
                        # Use standard lead time
                        lead_time = metrics.get('lead_time', {})
                        if lead_time.get('p85'):
                            lead_times.append(lead_time['p85'])
            else:
                # Legacy data format
                if proj.get('lead_time', {}).get('p85'):
                    lead_times.append(proj['lead_time']['p85'])

        # Use median (not mean) to handle outliers
        avg_lead_time = median(lead_times) if lead_times else 0
        lead_time_trend.append(round(avg_lead_time, 1))

    return {
        'lead_time': {
            'current': lead_time_trend[-1] if lead_time_trend else 0,
            'previous': lead_time_trend[-2] if len(lead_time_trend) > 1 else 0,
            'trend_data': lead_time_trend,
            'unit': 'days'
        }
    }


def extract_trends_from_deployment():
    """Extract deployment trends from deployment_history.json

    Uses weighted average (total successful / total builds) for accuracy.
    Matches executive summary calculation for consistency.
    """
    data = load_history_file('.tmp/observatory/deployment_history.json')
    if not data or not data.get('weeks'):
        return None

    weeks = data['weeks']
    build_success_trend = []

    for week in weeks:
        projects = week.get('projects', [])

        # Weighted average: total successful builds / total builds (matches exec summary)
        total_builds = sum(p.get('build_success_rate', {}).get('total_builds', 0) for p in projects)
        total_successful = sum(p.get('build_success_rate', {}).get('succeeded', 0) for p in projects)
        weighted_success_rate = (total_successful / total_builds * 100) if total_builds > 0 else 0
        build_success_trend.append(round(weighted_success_rate, 1))

    return {
        'build_success': {
            'current': build_success_trend[-1] if build_success_trend else 0,
            'previous': build_success_trend[-2] if len(build_success_trend) > 1 else 0,
            'trend_data': build_success_trend,
            'unit': '%'
        }
    }


def extract_trends_from_collaboration():
    """Extract collaboration trends from collaboration_history.json

    Uses median of project medians for robustness to outliers.
    Matches executive summary calculation for consistency.
    """
    data = load_history_file('.tmp/observatory/collaboration_history.json')
    if not data or not data.get('weeks'):
        return None

    weeks = data['weeks']
    pr_merge_trend = []

    for week in weeks:
        projects = week.get('projects', [])

        # Median PR merge time across projects (robust to outliers)
        merge_times = [p.get('pr_merge_time', {}).get('median_hours') for p in projects
                      if p.get('pr_merge_time', {}).get('median_hours') is not None]
        avg_merge_time = median(merge_times) if merge_times else 0
        pr_merge_trend.append(round(avg_merge_time, 1))

    return {
        'pr_merge_time': {
            'current': pr_merge_trend[-1] if pr_merge_trend else 0,
            'previous': pr_merge_trend[-2] if len(pr_merge_trend) > 1 else 0,
            'trend_data': pr_merge_trend,
            'unit': 'hours'
        }
    }


def extract_trends_from_ownership():
    """Extract ownership trends from ownership_history.json"""
    data = load_history_file('.tmp/observatory/ownership_history.json')
    if not data or not data.get('weeks'):
        return None

    weeks = data['weeks']
    unassigned_trend = []

    for week in weeks:
        projects = week.get('projects', [])

        # Weighted average: total unassigned / total items (consistent with Ownership Dashboard)
        total_items = sum(p.get('unassigned', {}).get('total_items', 0) for p in projects)
        total_unassigned = sum(p.get('unassigned', {}).get('unassigned_count', 0) for p in projects)
        weighted_unassigned = (total_unassigned / total_items * 100) if total_items > 0 else 0
        unassigned_trend.append(round(weighted_unassigned, 1))

    return {
        'work_unassigned': {
            'current': unassigned_trend[-1] if unassigned_trend else 0,
            'previous': unassigned_trend[-2] if len(unassigned_trend) > 1 else 0,
            'trend_data': unassigned_trend,
            'unit': '%'
        }
    }


def extract_trends_from_risk():
    """Extract risk trends from risk_history.json

    Tracks commit activity over time as indicator of delivery risk.
    Matches executive summary calculation for consistency.
    """
    data = load_history_file('.tmp/observatory/risk_history.json')
    if not data or not data.get('weeks'):
        return None

    weeks = data['weeks']
    commits_trend = []

    for week in weeks:
        projects = week.get('projects', [])

        # Total commits across all projects
        total_commits = sum(p.get('code_churn', {}).get('total_commits', 0) for p in projects)
        commits_trend.append(total_commits)

    return {
        'total_commits': {
            'current': commits_trend[-1] if commits_trend else 0,
            'previous': commits_trend[-2] if len(commits_trend) > 1 else 0,
            'trend_data': commits_trend,
            'unit': 'commits'
        }
    }


def get_trend_indicator(current, previous, good_direction='down'):
    """Get trend indicator (↑↓→) and color"""
    change = current - previous

    if abs(change) < 0.5:
        return ('→', 'trend-stable', change)

    is_increasing = change > 0

    if good_direction == 'down':
        if is_increasing:
            return ('↑', 'trend-up', change)  # Red (bad)
        else:
            return ('↓', 'trend-down', change)  # Green (good)
    else:  # good_direction == 'up'
        if is_increasing:
            return ('↑', 'trend-down', change)  # Green (good)
        else:
            return ('↓', 'trend-up', change)  # Red (bad)


def get_rag_color(value, metric_type):
    """Determine RAG color based on metric value and type"""
    if value == "N/A" or value is None:
        return "#94a3b8"  # Gray for N/A

    try:
        if metric_type == "lead_time":
            # Lower is better: <30 days green, 30-60 amber, >60 red
            val = float(value)
            if val < 30: return "#10b981"  # Green
            elif val < 60: return "#f59e0b"  # Amber
            else: return "#ef4444"  # Red

        elif metric_type == "mttr":
            # Lower is better: <7 days green, 7-14 days amber, >14 days red
            val = float(value)
            if val < 7: return "#10b981"
            elif val < 14: return "#f59e0b"
            else: return "#ef4444"

        elif metric_type == "total_vulns":
            # Lower is better: <150 green, 150-250 amber, >250 red
            val = int(value)
            if val < 150: return "#10b981"
            elif val < 250: return "#f59e0b"
            else: return "#ef4444"

        elif metric_type == "bugs":
            # Lower is better: <100 green, 100-200 amber, >200 red
            val = int(value)
            if val < 100: return "#10b981"
            elif val < 200: return "#f59e0b"
            else: return "#ef4444"

        elif metric_type == "success_rate":
            # Higher is better: >90% green, 70-90% amber, <70% red
            val = float(value)
            if val >= 90: return "#10b981"
            elif val >= 70: return "#f59e0b"
            else: return "#ef4444"

        elif metric_type == "merge_time":
            # Lower is better: <4h green, 4-24h amber, >24h red
            val = float(value)
            if val < 4: return "#10b981"
            elif val < 24: return "#f59e0b"
            else: return "#ef4444"

        elif metric_type == "unassigned":
            # Lower is better: <20% green, 20-40% amber, >40% red
            val = float(value)
            if val < 20: return "#10b981"
            elif val < 40: return "#f59e0b"
            else: return "#ef4444"

        elif metric_type == "target_progress":
            # Higher is better: >=70% green, 40-70% amber, <40% red
            val = float(value)
            if val >= 70: return "#10b981"
            elif val >= 40: return "#f59e0b"
            else: return "#ef4444"

        elif metric_type == "commits":
            # Neutral metric - no RAG thresholds
            return "#6366f1"  # Purple

        return "#6366f1"  # Default purple
    except (ValueError, TypeError):
        return "#94a3b8"  # Gray for invalid values


def generate_html(all_trends, target_progress):
    """Generate HTML dashboard"""
    now = datetime.now()

    # Build metrics data for JavaScript
    metrics_js = []

    # 1. Target Progress
    if target_progress:
        arrow, css_class, change = get_trend_indicator(target_progress['current'], target_progress['previous'], 'up')
        rag_color = get_rag_color(target_progress['current'], 'target_progress')
        metrics_js.append({
            'id': 'target',
            'icon': '🎯',
            'title': '70% Reduction Target',
            'description': 'Track progress toward 70% reduction goals for security vulnerabilities and bugs. Combined progress from Dec 1, 2025 baseline through June 30, 2026.',
            'current': target_progress['current'],
            'unit': target_progress['unit'],
            'change': round(change, 1),
            'changeLabel': 'vs last week',
            'data': target_progress['trend_data'],
            'arrow': arrow,
            'cssClass': css_class,
            'ragColor': rag_color,
            'dashboardUrl': 'target_dashboard.html'
        })

    # 2. AI Usage Tracker (Static launcher - no trend data)
    metrics_js.append({
        'id': 'ai-usage',
        'icon': '🤖',
        'title': 'AI Usage Tracker',
        'description': 'Monitor Claude and Devin usage across LGL team members. Track adoption and activity patterns.',
        'current': '',
        'unit': '',
        'change': '',
        'changeLabel': '',
        'data': [],  # Empty array - no sparkline needed for launcher
        'arrow': '',
        'cssClass': 'trend-stable',
        'ragColor': '#6366f1',
        'dashboardUrl': 'usage_tables_latest.html'
    })

    # 3. Security Vulnerabilities
    security = all_trends.get('security', {})
    if security:
        vulns = security.get('vulnerabilities', {})
        arrow, css_class, change = get_trend_indicator(vulns['current'], vulns['previous'], 'down')
        rag_color = get_rag_color(vulns['current'], 'total_vulns')
        metrics_js.append({
            'id': 'security',
            'icon': '🔒',
            'title': 'Security Vulnerabilities',
            'description': 'Track vulnerability trends and security debt. Translate scanner noise into engineering action.',
            'current': vulns['current'],
            'unit': vulns['unit'],
            'change': change,
            'changeLabel': 'vs last week',
            'data': vulns['trend_data'],
            'arrow': arrow,
            'cssClass': css_class,
            'ragColor': rag_color,
            'dashboardUrl': 'security_dashboard.html'
        })

    # 4. Open Bugs
    quality = all_trends.get('quality', {})
    if quality:
        bugs = quality.get('bugs', {})
        arrow, css_class, change = get_trend_indicator(bugs['current'], bugs['previous'], 'down')
        rag_color = get_rag_color(bugs['current'], 'bugs')
        metrics_js.append({
            'id': 'bugs',
            'icon': '🐛',
            'title': 'Open Bugs',
            'description': 'Track bug resolution speed and open bug trends. Measure how quickly issues are fixed across teams.',
            'current': bugs['current'],
            'unit': bugs['unit'],
            'change': change,
            'changeLabel': 'vs last week',
            'data': bugs['trend_data'],
            'arrow': arrow,
            'cssClass': css_class,
            'ragColor': rag_color,
            'dashboardUrl': 'quality_dashboard.html'
        })

    # 5. Lead Time
    flow = all_trends.get('flow', {})
    if flow:
        lead_time = flow.get('lead_time', {})
        arrow, css_class, change = get_trend_indicator(lead_time['current'], lead_time['previous'], 'down')
        rag_color = get_rag_color(lead_time['current'], 'lead_time')
        metrics_js.append({
            'id': 'flow',
            'icon': '🔄',
            'title': 'Lead Time (P85)',
            'description': 'Measure delivery speed, work in progress, and throughput across teams. See bottlenecks before they become problems.',
            'current': lead_time['current'],
            'unit': lead_time['unit'],
            'change': round(change, 1),
            'changeLabel': 'vs last week',
            'data': lead_time['trend_data'],
            'arrow': arrow,
            'cssClass': css_class,
            'ragColor': rag_color,
            'dashboardUrl': 'flow_dashboard.html'
        })

    # 6. Build Success Rate
    deployment = all_trends.get('deployment', {})
    if deployment:
        build_success = deployment.get('build_success', {})
        arrow, css_class, change = get_trend_indicator(build_success['current'], build_success['previous'], 'up')
        rag_color = get_rag_color(build_success['current'], 'success_rate')
        metrics_js.append({
            'id': 'deployment',
            'icon': '🚀',
            'title': 'Build Success Rate',
            'description': 'Track deployment frequency, build success rates, and lead time for changes. Measure DevOps performance.',
            'current': build_success['current'],
            'unit': build_success['unit'],
            'change': round(change, 1),
            'changeLabel': 'vs last week',
            'data': build_success['trend_data'],
            'arrow': arrow,
            'cssClass': css_class,
            'ragColor': rag_color,
            'dashboardUrl': 'deployment_dashboard.html'
        })

    # 7. PR Merge Time
    collaboration = all_trends.get('collaboration', {})
    if collaboration:
        pr_merge = collaboration.get('pr_merge_time', {})
        arrow, css_class, change = get_trend_indicator(pr_merge['current'], pr_merge['previous'], 'down')
        rag_color = get_rag_color(pr_merge['current'], 'merge_time')
        metrics_js.append({
            'id': 'collaboration',
            'icon': '🤝',
            'title': 'PR Merge Time',
            'description': 'Monitor code review efficiency, PR merge times, and review iterations. Optimize team collaboration.',
            'current': pr_merge['current'],
            'unit': pr_merge['unit'],
            'change': round(change, 1),
            'changeLabel': 'vs last week',
            'data': pr_merge['trend_data'],
            'arrow': arrow,
            'cssClass': css_class,
            'ragColor': rag_color,
            'dashboardUrl': 'collaboration_dashboard.html'
        })

    # 8. Work Unassigned
    ownership = all_trends.get('ownership', {})
    if ownership:
        unassigned = ownership.get('work_unassigned', {})
        arrow, css_class, change = get_trend_indicator(unassigned['current'], unassigned['previous'], 'down')
        rag_color = get_rag_color(unassigned['current'], 'unassigned')
        metrics_js.append({
            'id': 'ownership',
            'icon': '👤',
            'title': 'Work Unassigned',
            'description': 'Track work assignment clarity and orphan areas. Identify ownership gaps early.',
            'current': unassigned['current'],
            'unit': unassigned['unit'],
            'change': round(change, 1),
            'changeLabel': 'vs last week',
            'data': unassigned['trend_data'],
            'arrow': arrow,
            'cssClass': css_class,
            'ragColor': rag_color,
            'dashboardUrl': 'ownership_dashboard.html'
        })

    # 9. Total Commits (Risk)
    risk = all_trends.get('risk', {})
    if risk:
        commits = risk.get('total_commits', {})
        arrow, css_class, change = get_trend_indicator(commits['current'], commits['previous'], 'stable')
        rag_color = get_rag_color(commits['current'], 'commits')
        metrics_js.append({
            'id': 'risk',
            'icon': '📊',
            'title': 'Total Commits',
            'description': 'Track code change activity and commit patterns. Understand delivery risk through Git metrics.',
            'current': commits['current'],
            'unit': commits['unit'],
            'change': change,
            'changeLabel': 'vs last week',
            'data': commits['trend_data'],
            'arrow': arrow,
            'cssClass': css_class,
            'ragColor': rag_color,
            'dashboardUrl': 'risk_dashboard.html'
        })

    metrics_json = json.dumps(metrics_js, indent=4)

    # Get mobile-responsive framework
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start='#667eea',
        header_gradient_end='#764ba2',
        include_table_scroll=True,
        include_expandable_rows=False,
        include_glossary=False
    )

    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Executive Trends - Director Observatory</title>
    {framework_css}
    <style>
        /* Dashboard-specific styles */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}

        @media (max-width: 1024px) {{
            .metrics-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .metric-card {{
            background: var(--bg-secondary);
            padding: 24px;
            border-radius: 12px;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .forecast-banner {{
            --bg-primary: #f9fafb;
            --bg-secondary: #ffffff;
            --bg-card: #ffffff;
            --text-primary: #1f2937;
            --text-secondary: #6b7280;
            --border-color: #e5e7eb;
            --shadow: rgba(0,0,0,0.1);
        }}

        [data-theme="dark"] {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #1e293b;
            --text-primary: #f1f5f9;
            --text-secondary: #cbd5e1;
            --border-color: #475569;
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
            padding: 20px;
            color: var(--text-primary);
            transition: all 0.3s ease;
        }}

        .container {{
            max-width: 1600px;
            margin: 0 auto;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}

        .header h1 {{
            font-size: 2rem;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .header p {{
            opacity: 0.9;
            font-size: 1rem;
        }}

        .theme-toggle {{
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
            background: var(--bg-secondary);
            border: 2px solid var(--border-color);
            border-radius: 50px;
            padding: 10px 20px;
            cursor: pointer;
            font-size: 1.2rem;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .view-selector {{
            display: flex;
            gap: 10px;
            margin-bottom: 25px;
            align-items: center;
        }}

        .view-label {{
            font-weight: 600;
            color: var(--text-primary);
        }}

        .view-btn {{
            background: var(--bg-card);
            border: 2px solid var(--border-color);
            border-radius: 8px;
            padding: 8px 20px;
            cursor: pointer;
            font-size: 0.9rem;
            color: var(--text-primary);
            transition: all 0.2s ease;
        }}

        .view-btn:hover {{
            border-color: #667eea;
        }}

        .view-btn.active {{
            background: #667eea;
            border-color: #667eea;
            color: white;
            font-weight: 600;
        }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}

        @media (max-width: 1400px) {{
            .metrics-grid {{
                grid-template-columns: repeat(3, 1fr);
            }}
        }}

        @media (max-width: 1024px) {{
            .metrics-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

        @media (max-width: 640px) {{
            .metrics-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .metric-card-link {{
            display: block;
            text-decoration: none;
            color: inherit;
            height: 100%;
        }}

        .metric-card {{
            background: var(--bg-card);
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 12px var(--shadow);
            border-left: 4px solid #667eea;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            cursor: pointer;
            height: 100%;
        }}

        .metric-card:hover {{
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 20px 40px rgba(102, 126, 234, 0.25);
            border-left-color: #764ba2;
            border-left-width: 6px;
        }}

        .metric-card:active {{
            transform: translateY(-4px) scale(1.01);
        }}

        .metric-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}

        .metric-title {{
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .metric-icon {{
            font-size: 1.2rem;
        }}

        .trend-indicator {{
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            gap: 5px;
        }}

        .trend-up {{ color: #ef4444; }}
        .trend-down {{ color: #10b981; }}
        .trend-stable {{ color: #f59e0b; }}

        .metric-description {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-bottom: 12px;
            line-height: 1.4;
            opacity: 0.9;
        }}

        .metric-value {{
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 8px;
        }}

        .metric-change {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 15px;
        }}

        .sparkline-container {{
            height: 60px;
            margin-top: 15px;
            position: relative;
        }}

        .sparkline {{
            width: 100%;
            height: 100%;
        }}

        .sparkline-tooltip {{
            position: absolute;
            background: var(--bg-secondary);
            border: 2px solid #667eea;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-primary);
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s ease;
            white-space: nowrap;
            z-index: 100;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .sparkline-tooltip.visible {{
            opacity: 1;
        }}

        .timestamp {{
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.9rem;
            margin-top: 30px;
        }}
    </style>
</head>
<body>
    <button class="theme-toggle" onclick="toggleTheme()">🌓</button>

    <div class="container">
        <div class="header">
            <h1>Executive Trends Dashboard</h1>
            <p>Engineering Health Metrics</p>
        </div>

        <!-- View Selector -->
        <div class="view-selector">
            <span class="view-label">View:</span>
            <button class="view-btn" onclick="changeView(4)">1 Month</button>
            <button class="view-btn active" onclick="changeView(12)">3 Months</button>
            <button class="view-btn" onclick="changeView(24)">6 Months</button>
        </div>

        <div class="metrics-grid" id="metrics-container">
            <!-- Metrics will be dynamically generated here -->
        </div>

        <div class="timestamp">
            Generated: {now.strftime('%B %d, %Y at %H:%M')} • Data from Observatory history files
        </div>
    </div>

    {framework_js}
    <script>
        const trendsData = {metrics_json};
        let currentView = 12; // Default to 12 weeks

        function changeView(weeks) {{
            currentView = weeks;

            // Update button states
            document.querySelectorAll('.view-btn').forEach(btn => {{
                btn.classList.remove('active');
            }});
            event.target.classList.add('active');

            // Re-render metrics with new view
            renderMetrics();
        }}

        function generateSparkline(data, containerId, unit) {{
            const container = document.getElementById(containerId);
            if (!container) {{
                console.warn('Container not found:', containerId);
                return;
            }}

            // Slice data based on current view
            const viewData = data.slice(-currentView);

            // Validate data
            if (!viewData || viewData.length === 0) {{
                console.warn('No data for sparkline:', containerId);
                return;
            }}

            const width = container.offsetWidth;
            const height = 60;

            // Check if container has width
            if (width === 0) {{
                console.warn('Container has no width:', containerId);
                return;
            }}

            const max = Math.max(...viewData);
            const min = Math.min(...viewData);
            const range = max - min || 1;

            // Validate calculated values
            if (!isFinite(max) || !isFinite(min) || !isFinite(range)) {{
                console.error('Invalid data values for sparkline:', containerId, {{ max, min, range, viewData }});
                return;
            }}

            // Create tooltip
            const tooltip = document.createElement('div');
            tooltip.className = 'sparkline-tooltip';
            container.appendChild(tooltip);

            const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svg.setAttribute('width', width);
            svg.setAttribute('height', height);
            svg.setAttribute('class', 'sparkline');

            const points = viewData.map((value, index) => {{
                const x = viewData.length > 1 ? (index / (viewData.length - 1)) * width : width / 2;
                const y = height - ((value - min) / range) * (height - 10) - 5;
                return `${{x}},${{y}}`;
            }}).join(' ');

            // Gradient background
            const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            const gradient = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
            gradient.setAttribute('id', `gradient-${{containerId}}`);
            gradient.setAttribute('x1', '0%');
            gradient.setAttribute('y1', '0%');
            gradient.setAttribute('x2', '0%');
            gradient.setAttribute('y2', '100%');

            const stop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
            stop1.setAttribute('offset', '0%');
            stop1.setAttribute('style', 'stop-color:rgba(102,126,234,0.3);stop-opacity:1');

            const stop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
            stop2.setAttribute('offset', '100%');
            stop2.setAttribute('style', 'stop-color:rgba(102,126,234,0);stop-opacity:1');

            gradient.appendChild(stop1);
            gradient.appendChild(stop2);
            defs.appendChild(gradient);
            svg.appendChild(defs);

            // Area
            const area = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
            area.setAttribute('points', `0,${{height}} ${{points}} ${{width}},${{height}}`);
            area.setAttribute('fill', `url(#gradient-${{containerId}})`);
            svg.appendChild(area);

            // Line
            const polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
            polyline.setAttribute('points', points);
            polyline.setAttribute('fill', 'none');
            polyline.setAttribute('stroke', '#667eea');
            polyline.setAttribute('stroke-width', '2');
            svg.appendChild(polyline);

            // Dots with hover tooltips
            viewData.forEach((value, index) => {{
                const x = (index / (viewData.length - 1)) * width;
                const y = height - ((value - min) / range) * (height - 10) - 5;

                // Create invisible larger hit area for easier targeting
                const hitArea = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                hitArea.setAttribute('cx', x);
                hitArea.setAttribute('cy', y);
                hitArea.setAttribute('r', '12');
                hitArea.setAttribute('fill', 'transparent');
                hitArea.style.cursor = 'pointer';

                // Create visible circle
                const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                circle.setAttribute('cx', x);
                circle.setAttribute('cy', y);
                circle.setAttribute('r', '4');
                circle.setAttribute('fill', '#667eea');
                circle.style.transition = 'r 0.2s ease';
                circle.style.pointerEvents = 'none'; // Let hit area handle events

                // Hover effects on hit area
                hitArea.addEventListener('mouseenter', (e) => {{
                    circle.setAttribute('r', '6');
                    tooltip.textContent = `${{value}} ${{unit}}`;
                    tooltip.classList.add('visible');

                    // Position tooltip
                    const containerRect = container.getBoundingClientRect();
                    const circleRect = circle.getBoundingClientRect();
                    tooltip.style.left = (circleRect.left - containerRect.left + circleRect.width / 2 - tooltip.offsetWidth / 2) + 'px';
                    tooltip.style.top = (circleRect.top - containerRect.top - tooltip.offsetHeight - 8) + 'px';
                }});

                hitArea.addEventListener('mouseleave', () => {{
                    circle.setAttribute('r', '4');
                    tooltip.classList.remove('visible');
                }});

                svg.appendChild(hitArea);
                svg.appendChild(circle);
            }});

            container.appendChild(svg);
        }}

        function renderMetrics() {{
            const container = document.getElementById('metrics-container');
            container.innerHTML = '';

            trendsData.forEach(metric => {{
                const containerId = `sparkline-${{metric.id}}`;

                // Create clickable link wrapper
                const link = document.createElement('a');
                link.href = metric.dashboardUrl;
                link.className = 'metric-card-link';

                const card = document.createElement('div');
                card.className = 'metric-card';
                card.innerHTML = `
                    <div class="metric-header">
                        <div class="metric-title">
                            <span class="metric-icon">${{metric.icon}}</span>
                            ${{metric.title}}
                        </div>
                        <div class="trend-indicator ${{metric.cssClass}}">
                            ${{metric.arrow}}
                        </div>
                    </div>
                    <div class="metric-description">${{metric.description}}</div>
                    <div class="metric-value" style="color: ${{metric.ragColor}};">${{metric.current}} <span style="font-size: 1rem; font-weight: normal; color: var(--text-secondary);">${{metric.unit}}</span></div>
                    <div class="metric-change">
                        ${{metric.change > 0 ? '+' : ''}}${{metric.change}} ${{metric.changeLabel}}
                    </div>
                    <div class="sparkline-container" id="${{containerId}}"></div>
                `;

                link.appendChild(card);
                container.appendChild(link);

                // Generate sparkline after DOM is updated
                setTimeout(() => generateSparkline(metric.data, containerId, metric.unit), 0);
            }});
        }}

        // Initialize
        renderMetrics();
    </script>
</body>
</html>
"""

    return html


def main():
    """Main dashboard generation"""
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    print("=" * 70)
    print("Executive Trends Dashboard Generator")
    print("=" * 70)

    # Extract trends from all dashboards
    all_trends = {}

    print("\nLoading historical data...")

    # Calculate target progress
    target_progress = calculate_target_progress()
    if target_progress:
        print(f"✓ Target progress: {target_progress['current']}% (Forecast: {target_progress['forecast']['trajectory']})")

    quality = extract_trends_from_quality()
    if quality:
        all_trends['quality'] = quality
        print(f"✓ Quality metrics: {len(quality['bugs']['trend_data'])} weeks")

    security = extract_trends_from_security()
    if security:
        all_trends['security'] = security
        print(f"✓ Security metrics: {len(security['vulnerabilities']['trend_data'])} weeks")

    flow = extract_trends_from_flow()
    if flow:
        all_trends['flow'] = flow
        print(f"✓ Flow metrics: {len(flow['lead_time']['trend_data'])} weeks")

    deployment = extract_trends_from_deployment()
    if deployment:
        all_trends['deployment'] = deployment
        print(f"✓ Deployment metrics: {len(deployment['build_success']['trend_data'])} weeks")

    collaboration = extract_trends_from_collaboration()
    if collaboration:
        all_trends['collaboration'] = collaboration
        print(f"✓ Collaboration metrics: {len(collaboration['pr_merge_time']['trend_data'])} weeks")

    ownership = extract_trends_from_ownership()
    if ownership:
        all_trends['ownership'] = ownership
        print(f"✓ Ownership metrics: {len(ownership['work_unassigned']['trend_data'])} weeks")

    risk = extract_trends_from_risk()
    if risk:
        all_trends['risk'] = risk
        print(f"✓ Risk metrics: {len(risk['total_commits']['trend_data'])} weeks")

    if not all_trends:
        print("⚠ No historical data found")
        sys.exit(1)

    # Generate HTML
    print("\nGenerating dashboard...")
    html = generate_html(all_trends, target_progress)

    # Save to file (as index.html - this is the landing page)
    output_file = '.tmp/observatory/dashboards/index.html'
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✓ Dashboard generated: {output_file}")
    print(f"✓ Total metrics: {len(all_trends) + (1 if target_progress else 0)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
