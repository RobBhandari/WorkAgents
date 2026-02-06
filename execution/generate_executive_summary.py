#!/usr/bin/env python3
"""
Generate Executive Summary Dashboard for Director Observatory

A one-page director-grade health brief that answers:
- Are we shipping faster or slower?
- Where is quality eroding?
- Where are we accumulating invisible risk?
- Which teams/services need attention — and why?
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from statistics import median


def get_most_recent_week_with_data(weeks, data_check_fn):
    """Get the most recent week that has actual data"""
    if not weeks:
        return None

    # Iterate backwards to find the most recent week with data
    for week in reversed(weeks):
        if data_check_fn(week):
            return week

    # If no week has data, return the last week anyway
    return weeks[-1] if weeks else None


def calculate_target_progress():
    """Calculate 70% reduction target progress (average of bugs and vulnerabilities progress)"""
    # Load baselines
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
            baselines['bugs'] = data.get('open_count', 0)

    # Get current counts from latest data
    quality_file = Path('.tmp/observatory/quality_history.json')
    security_file = Path('.tmp/observatory/security_history.json')

    if not quality_file.exists() or not security_file.exists():
        return None

    try:
        with open(quality_file, 'r', encoding='utf-8') as f:
            quality_data = json.load(f)
        with open(security_file, 'r', encoding='utf-8') as f:
            security_data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, Exception) as e:
        print(f"⚠️ Error loading target progress baseline data: {e}")
        return None

    if not quality_data.get('weeks') or not security_data.get('weeks'):
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

    target_bugs = round(baseline_bugs * 0.3)  # 70% reduction = 30% remaining
    target_vulns = round(baseline_vulns * 0.3)

    # Progress calculation
    bugs_progress = ((baseline_bugs - current_bugs) / (baseline_bugs - target_bugs) * 100) if baseline_bugs > target_bugs else 0
    vulns_progress = ((baseline_vulns - current_vulns) / (baseline_vulns - target_vulns) * 100) if baseline_vulns > target_vulns else 0

    # Overall progress (average)
    overall_progress = (bugs_progress + vulns_progress) / 2

    return {
        'progress': round(overall_progress, 1),
        'baseline_bugs': baseline_bugs,
        'current_bugs': current_bugs,
        'target_bugs': target_bugs,
        'baseline_vulns': baseline_vulns,
        'current_vulns': current_vulns,
        'target_vulns': target_vulns,
        'bugs_progress': round(bugs_progress, 1),
        'vulns_progress': round(vulns_progress, 1)
    }


def load_history_file_safe(file_path: Path, file_label: str = None):
    """Load a history JSON file with error handling"""
    label = file_label or file_path.name

    if not file_path.exists():
        print(f"  ⚠️ {label}: File not found")
        return None

    try:
        # Check file size
        file_size = file_path.stat().st_size
        if file_size == 0:
            print(f"  ⚠️ {label}: File is empty")
            return None

        # Load and parse JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Validate structure
        if not isinstance(data, dict):
            print(f"  ⚠️ {label}: Invalid data structure (not a dictionary)")
            return None

        if 'weeks' not in data:
            print(f"  ⚠️ {label}: Missing 'weeks' key")
            return None

        weeks = data.get('weeks', [])
        if not weeks:
            print(f"  ⚠️ {label}: No weeks data found")
            return None

        print(f"  ✓ {label}: Loaded successfully ({len(weeks)} weeks, {file_size:,} bytes)")
        return data

    except json.JSONDecodeError as e:
        print(f"  ✗ {label}: JSON decode error - {e}")
        return None
    except UnicodeDecodeError as e:
        print(f"  ✗ {label}: Unicode decode error - {e}")
        return None
    except Exception as e:
        print(f"  ✗ {label}: Unexpected error - {e}")
        return None


def load_dashboard_data():
    """Load metrics from all dashboard data files"""
    data_dir = Path(".tmp/observatory")

    print("\nLoading historical data...")

    # Load flow metrics - use most recent week with actual flow data
    flow_file = data_dir / "flow_history.json"
    flow_data = None
    flow_history = load_history_file_safe(flow_file, "Flow metrics")
    if flow_history:
        weeks = flow_history.get('weeks', [])
        # Check if week has WIP or lead time data
        flow_data = get_most_recent_week_with_data(
            weeks,
            lambda w: any(p.get('wip_count') or p.get('lead_time', {}).get('p85')
                         for p in w.get('projects', []))
        )

    # Load ownership metrics
    ownership_file = data_dir / "ownership_history.json"
    ownership_data = None
    ownership_history = load_history_file_safe(ownership_file, "Ownership metrics")
    if ownership_history:
        weeks = ownership_history.get('weeks', [])
        ownership_data = weeks[-1] if weeks else None

    # Load quality metrics
    quality_file = data_dir / "quality_history.json"
    quality_data = None
    quality_history = load_history_file_safe(quality_file, "Quality metrics")
    if quality_history:
        weeks = quality_history.get('weeks', [])
        quality_data = weeks[-1] if weeks else None

    # Load security metrics
    security_file = data_dir / "security_history.json"
    security_data = None
    security_history = load_history_file_safe(security_file, "Security metrics")
    if security_history:
        weeks = security_history.get('weeks', [])
        security_data = weeks[-1] if weeks else None

    # Load risk metrics
    risk_file = data_dir / "risk_history.json"
    risk_data = None
    risk_history = load_history_file_safe(risk_file, "Risk metrics")
    if risk_history:
        weeks = risk_history.get('weeks', [])
        risk_data = weeks[-1] if weeks else None

    # Load deployment metrics
    deployment_file = data_dir / "deployment_history.json"
    deployment_data = None
    deployment_history = load_history_file_safe(deployment_file, "Deployment metrics")
    if deployment_history:
        weeks = deployment_history.get('weeks', [])
        deployment_data = weeks[-1] if weeks else None

    # Load collaboration metrics
    collaboration_file = data_dir / "collaboration_history.json"
    collaboration_data = None
    collaboration_history = load_history_file_safe(collaboration_file, "Collaboration metrics")
    if collaboration_history:
        weeks = collaboration_history.get('weeks', [])
        collaboration_data = weeks[-1] if weeks else None

    return {
        'flow': flow_data,
        'ownership': ownership_data,
        'quality': quality_data,
        'security': security_data,
        'risk': risk_data,
        'deployment': deployment_data,
        'collaboration': collaboration_data
    }


def calculate_flow_summary(flow_data):
    """
    Calculate flow metrics summary from project data.

    Uses operational metrics when cleanup work is detected to provide
    accurate operational performance view.
    """
    if not flow_data or 'projects' not in flow_data:
        return None

    projects = flow_data['projects']
    lead_times = []
    wip_total = 0
    cleanup_detected_count = 0

    for proj in projects:
        # Check if project has work_type_metrics (new data format)
        if 'work_type_metrics' in proj:
            # Aggregate across all work types
            for work_type, metrics in proj.get('work_type_metrics', {}).items():
                dual_metrics = metrics.get('dual_metrics', {})
                has_cleanup = dual_metrics.get('indicators', {}).get('is_cleanup_effort', False)

                if has_cleanup:
                    cleanup_detected_count += 1
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

                wip_total += metrics.get('open_count', 0)
        else:
            # Legacy data format
            if proj.get('lead_time', {}).get('p85'):
                lead_times.append(proj['lead_time']['p85'])
            wip_total += proj.get('wip_count', 0)

    avg_lead_time = median(lead_times) if lead_times else 0

    return {
        'avg_lead_time_p85': avg_lead_time,
        'total_wip': wip_total,
        'projects_count': len(projects),
        'cleanup_detected_count': cleanup_detected_count
    }


def calculate_quality_summary(quality_data):
    """Calculate quality metrics summary from project data"""
    if not quality_data or 'projects' not in quality_data:
        return None

    projects = quality_data['projects']
    total_bugs_analyzed = 0
    total_open_bugs = 0
    mttr_values = []

    for proj in projects:
        total_bugs_analyzed += proj.get('total_bugs_analyzed', 0)
        total_open_bugs += proj.get('open_bugs_count', 0)

        # Collect MTTR values for averaging
        mttr = proj.get('mttr', {}).get('mttr_days')
        if mttr is not None:
            mttr_values.append(mttr)

    avg_mttr = (sum(mttr_values) / len(mttr_values)) if mttr_values else None

    return {
        'avg_mttr': avg_mttr,
        'total_bugs_analyzed': total_bugs_analyzed,
        'total_open_bugs': total_open_bugs,
        'projects_count': len(projects)
    }


def calculate_ownership_summary(ownership_data):
    """Calculate ownership metrics summary from project data"""
    if not ownership_data or 'projects' not in ownership_data:
        return None

    projects = ownership_data['projects']
    total_unassigned = 0
    total_items = 0

    for proj in projects:
        unassigned = proj.get('unassigned', {})
        total_unassigned += unassigned.get('unassigned_count', 0)
        total_items += unassigned.get('total_items', 0)

    unassigned_pct = (total_unassigned / total_items * 100) if total_items > 0 else 0

    return {
        'unassigned_pct': unassigned_pct,
        'total_unassigned': total_unassigned,
        'projects_count': len(projects)
    }


def calculate_risk_summary(risk_data):
    """Calculate risk metrics summary from project data (Git activity)"""
    if not risk_data or 'projects' not in risk_data:
        return None

    projects = risk_data['projects']
    total_commits = 0
    total_files_changed = 0

    for proj in projects:
        code_churn = proj.get('code_churn', {})
        total_commits += code_churn.get('total_commits', 0)
        total_files_changed += code_churn.get('unique_files_touched', 0)

    return {
        'total_commits': total_commits,
        'files_changed': total_files_changed,
        'active_projects': len(projects)
    }


def calculate_deployment_summary(deployment_data):
    """Calculate deployment metrics summary from project data"""
    if not deployment_data or 'projects' not in deployment_data:
        return None

    projects = deployment_data['projects']
    total_builds = 0
    total_successful = 0
    deploy_frequencies = []

    for proj in projects:
        # Build success rate
        success_rate = proj.get('build_success_rate', {})
        total_builds += success_rate.get('total_builds', 0)
        total_successful += success_rate.get('succeeded', 0)

        # Deployment frequency
        deploy_freq = proj.get('deployment_frequency', {})
        deploys_per_week = deploy_freq.get('deployments_per_week', 0)
        if deploys_per_week:
            deploy_frequencies.append(deploys_per_week)

    overall_success_rate = (total_successful / total_builds * 100) if total_builds > 0 else 0
    avg_deploy_freq = median(deploy_frequencies) if deploy_frequencies else 0

    return {
        'success_rate': overall_success_rate,
        'total_builds': total_builds,
        'avg_deploy_frequency': avg_deploy_freq,
        'projects_count': len(projects)
    }


def calculate_collaboration_summary(collaboration_data):
    """Calculate collaboration metrics summary from project data"""
    if not collaboration_data or 'projects' not in collaboration_data:
        return None

    projects = collaboration_data['projects']
    total_prs = 0
    merge_times = []

    for proj in projects:
        total_prs += proj.get('total_prs_analyzed', 0)

        # PR merge time
        merge_time = proj.get('pr_merge_time', {})
        median_merge = merge_time.get('median_hours')
        if median_merge:
            merge_times.append(median_merge)

    avg_merge_time = median(merge_times) if merge_times else 0

    return {
        'total_prs': total_prs,
        'avg_merge_time': avg_merge_time,
        'projects_count': len(projects)
    }


def get_attention_items(metrics):
    """Identify teams/services that need attention"""
    items = []

    # Flow issues
    if metrics['flow']:
        flow_summary = calculate_flow_summary(metrics['flow'])
        if flow_summary and flow_summary['avg_lead_time_p85'] > 100:
            items.append(f"Lead time at {flow_summary['avg_lead_time_p85']:.0f} days (target: <60 days)")

    # Security issues
    if metrics['security'] and 'metrics' in metrics['security']:
        sec = metrics['security']['metrics']
        critical = sec.get('severity_breakdown', {}).get('critical', 0)
        high = sec.get('severity_breakdown', {}).get('high', 0)
        if critical > 0:
            items.append(f"{critical} critical vulnerabilities open")
        if high > 5:
            items.append(f"{high} high-severity vulnerabilities open")

    # Quality issues
    if metrics['quality']:
        quality_summary = calculate_quality_summary(metrics['quality'])
        if quality_summary and quality_summary['avg_mttr'] and quality_summary['avg_mttr'] > 14:
            items.append(f"MTTR at {quality_summary['avg_mttr']:.1f} days (target: <7 days)")

    # Ownership issues
    if metrics['ownership']:
        ownership_summary = calculate_ownership_summary(metrics['ownership'])
        if ownership_summary and ownership_summary['unassigned_pct'] > 20:
            items.append(f"{ownership_summary['unassigned_pct']:.1f}% of work unassigned")

    return items


def determine_overall_status(metrics):
    """Determine overall health status"""
    attention_items = get_attention_items(metrics)

    critical_count = sum(1 for item in attention_items if 'critical' in item.lower())

    if critical_count > 0 or len(attention_items) >= 3:
        return "ACTION NEEDED", "#ef4444"
    elif len(attention_items) > 0:
        return "CAUTION", "#f59e0b"
    else:
        return "HEALTHY", "#10b981"


def generate_html(metrics):
    """Generate executive summary HTML"""

    # Calculate target progress (70% reduction goal)
    target_progress = calculate_target_progress()

    # Calculate summaries
    flow_summary = calculate_flow_summary(metrics['flow']) if metrics['flow'] else None
    quality_summary = calculate_quality_summary(metrics['quality']) if metrics['quality'] else None
    ownership_summary = calculate_ownership_summary(metrics['ownership']) if metrics['ownership'] else None
    risk_summary = calculate_risk_summary(metrics['risk']) if metrics['risk'] else None
    deployment_summary = calculate_deployment_summary(metrics['deployment']) if metrics['deployment'] else None
    collaboration_summary = calculate_collaboration_summary(metrics['collaboration']) if metrics['collaboration'] else None
    security_metrics = metrics['security'].get('metrics') if metrics['security'] else None

    # Determine status
    status_text, status_color = determine_overall_status(metrics)
    attention_items = get_attention_items(metrics)

    # Get week info
    week_date = metrics['flow']['week_date'] if metrics['flow'] else datetime.now().strftime('%Y-%m-%d')
    week_number = metrics['flow']['week_number'] if metrics['flow'] else 'Current'

    # Format metrics for display with RAG colors
    def get_rag_color(value, metric_type):
        """Determine RAG color based on metric value and type"""
        if value == "N/A":
            return "#94a3b8"  # Gray for N/A

        if metric_type == "lead_time":
            # Lower is better: <30 days green, 30-60 amber, >60 red
            val = float(value)
            if val < 30: return "#10b981"  # Green
            elif val < 60: return "#f59e0b"  # Amber
            else: return "#ef4444"  # Red

        elif metric_type == "mttr":
            # Lower is better: <7 days green, 7-14 days amber, >14 days red
            val = float(value.replace(' days', ''))
            if val < 7: return "#10b981"
            elif val < 14: return "#f59e0b"
            else: return "#ef4444"

        elif metric_type == "critical_vulns":
            # Lower is better: 0 green, 1-3 amber, >3 red
            val = int(value)
            if val == 0: return "#10b981"
            elif val <= 3: return "#f59e0b"
            else: return "#ef4444"

        elif metric_type == "success_rate":
            # Higher is better: >90% green, 70-90% amber, <70% red
            val = float(value.replace('%', ''))
            if val >= 90: return "#10b981"
            elif val >= 70: return "#f59e0b"
            else: return "#ef4444"

        elif metric_type == "merge_time":
            # Lower is better: <4h green, 4-24h amber, >24h red
            val = float(value.replace('h', ''))
            if val < 4: return "#10b981"
            elif val < 24: return "#f59e0b"
            else: return "#ef4444"

        elif metric_type == "unassigned":
            # Lower is better: <20% green, 20-40% amber, >40% red
            val = float(value.replace('%', ''))
            if val < 20: return "#10b981"
            elif val < 40: return "#f59e0b"
            else: return "#ef4444"

        elif metric_type == "attention":
            # Lower is better: 0 green, 1-2 amber, >2 red
            val = int(value)
            if val == 0: return "#10b981"
            elif val <= 2: return "#f59e0b"
            else: return "#ef4444"

        elif metric_type == "target_progress":
            # Higher is better: >=70% green, 40-70% amber, <40% red
            val = float(value.replace('%', ''))
            if val >= 70: return "#10b981"
            elif val >= 40: return "#f59e0b"
            else: return "#ef4444"

        elif metric_type == "total_vulns":
            # Lower is better: <150 green, 150-250 amber, >250 red
            val = int(value)
            if val < 150: return "#10b981"
            elif val < 250: return "#f59e0b"
            else: return "#ef4444"

        return "#6366f1"  # Default purple

    def get_rag_tooltip(metric_type):
        """Get tooltip explaining RAG thresholds for each metric"""
        tooltips = {
            "lead_time": "RAG Rating:\n🟢 Good: < 30 days\n🟡 Caution: 30-60 days\n🔴 Action Needed: > 60 days",
            "mttr": "RAG Rating:\n🟢 Good: < 7 days\n🟡 Caution: 7-14 days\n🔴 Action Needed: > 14 days",
            "critical_vulns": "RAG Rating:\n🟢 Good: 0 vulns\n🟡 Caution: 1-3 vulns\n🔴 Action Needed: > 3 vulns",
            "success_rate": "RAG Rating:\n🟢 Good: ≥ 90%\n🟡 Caution: 70-90%\n🔴 Action Needed: < 70%",
            "merge_time": "RAG Rating:\n🟢 Good: < 4 hours\n🟡 Caution: 4-24 hours\n🔴 Action Needed: > 24 hours",
            "unassigned": "RAG Rating:\n🟢 Good: < 20%\n🟡 Caution: 20-40%\n🔴 Action Needed: > 40%",
            "attention": "RAG Rating:\n🟢 Good: 0 items\n🟡 Caution: 1-2 items\n🔴 Action Needed: > 2 items"
        }
        return tooltips.get(metric_type, "")

    # Target progress display
    target_display = f"{target_progress['progress']}%" if target_progress else "N/A"
    target_color = get_rag_color(target_display, "target_progress")

    lead_time_display = f"{flow_summary['avg_lead_time_p85']:.0f}" if flow_summary else "N/A"
    lead_time_color = get_rag_color(lead_time_display, "lead_time")

    mttr_display = f"{quality_summary['avg_mttr']:.1f} days" if quality_summary and quality_summary['avg_mttr'] else "N/A"
    mttr_color = get_rag_color(mttr_display, "mttr")

    total_vulns_display = str(security_metrics['current_total']) if security_metrics else "N/A"
    total_vulns_color = get_rag_color(total_vulns_display, "total_vulns")

    success_rate_display = f"{deployment_summary['success_rate']:.1f}%" if deployment_summary else "N/A"
    success_rate_color = get_rag_color(success_rate_display, "success_rate")

    merge_time_display = f"{collaboration_summary['avg_merge_time']:.1f}h" if collaboration_summary else "N/A"
    merge_time_color = get_rag_color(merge_time_display, "merge_time")

    unassigned_display = f"{ownership_summary['unassigned_pct']:.1f}%" if ownership_summary else "N/A"
    unassigned_color = get_rag_color(unassigned_display, "unassigned")

    attention_count = len(attention_items)
    attention_color = get_rag_color(str(attention_count), "attention")

    html = f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Executive Summary - Director Observatory</title>
    <style>
        :root {{
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
            max-width: 1400px;
            margin: 0 auto;
        }}

        .theme-toggle {{
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
            background: var(--bg-card);
            border: 2px solid var(--border-color);
            border-radius: 50px;
            padding: 10px 20px;
            cursor: pointer;
            font-size: 1.2rem;
            box-shadow: 0 4px 12px var(--shadow);
            transition: all 0.3s ease;
        }}

        .theme-toggle:hover {{
            transform: translateY(-2px);
        }}

        .header {{
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            color: white;
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}

        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
        }}

        .header p {{
            opacity: 0.9;
            font-size: 1.1rem;
        }}

        .status-banner {{
            background: var(--bg-card);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            border-left: 5px solid {status_color};
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .status-banner h2 {{
            color: {status_color};
            font-size: 2rem;
            margin-bottom: 15px;
        }}

        .metric-pairs-container {{
            display: flex;
            flex-direction: column;
            gap: 24px;
            margin-bottom: 30px;
        }}

        .metric-pair {{
            display: grid;
            grid-template-columns: 1fr 350px;
            gap: 20px;
            align-items: stretch;
            cursor: move;
            transition: opacity 0.2s ease, transform 0.2s ease;
        }}

        .metric-pair.dragging {{
            opacity: 0.5;
            transform: scale(0.98);
        }}

        .metric-pair.drag-over {{
            border-top: 3px solid #667eea;
            margin-top: 3px;
        }}

        @media (max-width: 1024px) {{
            .metric-pair {{
                grid-template-columns: 1fr;
            }}
        }}

        .question-card {{
            background: var(--bg-card);
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 12px var(--shadow);
            border-left: 4px solid #6366f1;
        }}

        .question-card-header {{
            display: flex;
            align-items: baseline;
            gap: 20px;
            margin-bottom: 20px;
        }}

        .question-card h3 {{
            color: var(--text-primary);
            font-size: 1.2rem;
            margin: 0;
            font-weight: 700;
            flex-shrink: 0;
            white-space: nowrap;
            line-height: 1.5;
            width: 280px;
        }}

        .header-description {{
            color: var(--text-secondary);
            font-size: 1.15rem;
            line-height: 1.5;
            margin: 0;
            flex: 1;
            padding-top: 1px;
            text-align: left;
        }}

        .metric {{
            font-size: 2.5rem;
            font-weight: bold;
            margin-bottom: 10px;
            line-height: 1;
            height: 3rem;
            display: flex;
            align-items: baseline;
        }}

        .metric-label {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}

        .rag-legend {{
            font-size: 0.7rem;
            color: var(--text-secondary);
            margin: 10px 0;
            padding: 6px 10px;
            background: rgba(0,0,0,0.2);
            border-radius: 6px;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
        }}

        [data-theme="light"] .rag-legend {{
            background: rgba(0,0,0,0.05);
        }}

        .rag-legend-item {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            white-space: nowrap;
        }}

        .rag-dot {{
            width: 6px;
            height: 6px;
            border-radius: 50%;
            flex-shrink: 0;
        }}


        .detail-card {{
            background: var(--bg-card);
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 12px var(--shadow);
            transition: all 0.3s ease;
            text-decoration: none;
            color: inherit;
            display: block;
            cursor: pointer;
            border: 2px solid var(--border-color);
            position: relative;
            overflow: hidden;
        }}

        .detail-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transform: scaleX(0);
            transition: transform 0.3s ease;
        }}

        .detail-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 8px 20px var(--shadow);
            border-color: #667eea;
        }}

        .detail-card:hover::before {{
            transform: scaleX(1);
        }}

        .detail-card h4 {{
            color: var(--text-primary);
            margin-bottom: 12px;
            font-size: 1rem;
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 600;
        }}

        .dashboard-icon {{
            font-size: 1.5rem;
            opacity: 0.8;
        }}

        .metric-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
        }}

        .metric-row:last-child {{
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }}

        .metric-row span {{
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}

        .metric-row strong {{
            color: var(--text-primary);
            font-size: 0.95rem;
        }}

        @media print {{
            .theme-toggle {{
                display: none;
            }}
            body {{
                background: white;
                color: black;
            }}
        }}
    </style>
</head>
<body>
    <button class="theme-toggle" onclick="toggleTheme()">🌓</button>

    <div class="container">
        <div class="header">
            <h1>Executive Summary</h1>
            <p>Director Observatory - Week {week_number} ({week_date})</p>
        </div>

        <div class="status-banner">
            <h2>Overall Status: {status_text}</h2>
            <p style="font-size: 1.1rem;">Engineering health assessment across 7 key dimensions: flow, quality, security, deployment, collaboration, ownership, and risk.</p>
        </div>

        <div class="metric-pairs-container" id="cards-container">
            <!-- Pair 0: 70% Reduction Target -->
            <div class="metric-pair" draggable="true" data-card-id="target">
                <div class="question-card">
                    <div class="question-card-header">
                        <h3>70% Reduction Target</h3>
                        <div class="header-description">
                            Track progress toward 70% reduction goals for security vulnerabilities and bugs. Combined progress from Dec 1, 2025 baseline through June 30, 2026.
                        </div>
                    </div>
                    <div class="metric" style="color: {target_color};">{target_display}</div>
                    <div class="metric-label">Overall Progress to Target</div>
                    <div class="rag-legend">
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #10b981;"></span> Good: &ge;70%</div>
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #f59e0b;"></span> Caution: 40-70%</div>
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #ef4444;"></span> Action: &lt;40%</div>
                    </div>
                </div>
                <a href="target_dashboard.html" class="detail-card">
                    <h4><span class="dashboard-icon">🎯</span> Target Dashboard</h4>
                    <div class="metric-row">
                        <span>Overall Progress</span>
                        <strong>{target_display}</strong>
                    </div>
                    <div class="metric-row">
                        <span>Bugs Progress</span>
                        <strong>{target_progress['bugs_progress'] if target_progress else 'N/A'}% ({target_progress['current_bugs'] if target_progress else 'N/A'}/{target_progress['target_bugs'] if target_progress else 'N/A'} target)</strong>
                    </div>
                    <div class="metric-row">
                        <span>Vulns Progress</span>
                        <strong>{target_progress['vulns_progress'] if target_progress else 'N/A'}% ({target_progress['current_vulns'] if target_progress else 'N/A'}/{target_progress['target_vulns'] if target_progress else 'N/A'} target)</strong>
                    </div>
                </a>
            </div>

            <!-- Pair 1: AI Usage Tracker -->
            <div class="metric-pair" draggable="true" data-card-id="ai-usage">
                <div class="question-card">
                    <div class="question-card-header">
                        <h3>AI Usage Tracker</h3>
                        <div class="header-description">
                            Monitor Claude and Devin usage across LGL team members. Track adoption and activity patterns.
                        </div>
                    </div>
                    <div class="metric" style="color: #6366f1;">LGL Team</div>
                    <div class="metric-label">AI Tools Adoption Report</div>
                    <div class="rag-legend">
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #6366f1;"></span> Click to view usage report</div>
                    </div>
                </div>
                <a href="javascript:void(0);" onclick="openUsageTracker()" class="detail-card">
                    <h4><span class="dashboard-icon">🤖</span> Launch Usage Report</h4>
                    <div class="metric-row">
                        <span>Report Type</span>
                        <strong>Claude & Devin Usage</strong>
                    </div>
                    <div class="metric-row">
                        <span>Filters</span>
                        <strong>LGL Team Members</strong>
                    </div>
                    <div class="metric-row">
                        <span>Features</span>
                        <strong>Search, Sort, Heatmaps</strong>
                    </div>
                </a>
            </div>

            <!-- Pair 2: Flow -->
            <div class="metric-pair" draggable="true" data-card-id="flow">
                <div class="question-card">
                    <div class="question-card-header">
                        <h3>Flow & Throughput</h3>
                        <div class="header-description">
                            Measure delivery speed, work in progress, and throughput across teams. See bottlenecks before they become problems.
                        </div>
                    </div>
                    <div class="metric" style="color: {lead_time_color};">{lead_time_display}</div>
                    <div class="metric-label">Average Lead Time (days, P85)</div>
                    <div class="rag-legend">
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #10b981;"></span> Good: &lt;30d</div>
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #f59e0b;"></span> Caution: 30-60d</div>
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #ef4444;"></span> Action: &gt;60d</div>
                    </div>
                </div>
                <a href="flow_dashboard.html" class="detail-card">
                    <h4><span class="dashboard-icon">🔄</span> Flow Dashboard</h4>
                    <div class="metric-row">
                        <span>Lead Time (P85)</span>
                        <strong>{lead_time_display} days</strong>
                    </div>
                    <div class="metric-row">
                        <span>Total WIP</span>
                        <strong>{flow_summary['total_wip'] if flow_summary else 'N/A'}</strong>
                    </div>
                    <div class="metric-row">
                        <span>Projects</span>
                        <strong>{flow_summary['projects_count'] if flow_summary else 'N/A'}</strong>
                    </div>
                </a>
            </div>

            <!-- Pair 3: Quality -->
            <div class="metric-pair" draggable="true" data-card-id="quality">
                <div class="question-card">
                    <div class="question-card-header">
                        <h3>Quality & Fix Effectiveness</h3>
                        <div class="header-description">
                            Track bug resolution speed and open bug trends. Measure how quickly issues are fixed across teams.
                        </div>
                    </div>
                    <div class="metric" style="color: {mttr_color};">{mttr_display}</div>
                    <div class="metric-label">MTTR (Mean Time To Repair)</div>
                    <div class="rag-legend">
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #10b981;"></span> Good: &lt;7d</div>
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #f59e0b;"></span> Caution: 7-14d</div>
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #ef4444;"></span> Action: &gt;14d</div>
                    </div>
                </div>
                <a href="quality_dashboard.html" class="detail-card">
                    <h4><span class="dashboard-icon">✓</span> Quality Dashboard</h4>
                    <div class="metric-row">
                        <span>MTTR</span>
                        <strong>{mttr_display}</strong>
                    </div>
                    <div class="metric-row">
                        <span>Open Bugs</span>
                        <strong>{quality_summary['total_open_bugs'] if quality_summary else 'N/A'}</strong>
                    </div>
                    <div class="metric-row">
                        <span>Projects</span>
                        <strong>{quality_summary['projects_count'] if quality_summary else 'N/A'}</strong>
                    </div>
                </a>
            </div>

            <!-- Pair 4: Security -->
            <div class="metric-pair" draggable="true" data-card-id="security">
                <div class="question-card">
                    <div class="question-card-header">
                        <h3>Security & Vulnerabilities</h3>
                        <div class="header-description">
                            Track vulnerability trends and security debt. Translate scanner noise into engineering action.
                        </div>
                    </div>
                    <div class="metric" style="color: {total_vulns_color};">{total_vulns_display}</div>
                    <div class="metric-label">Total Vulnerabilities</div>
                    <div class="rag-legend">
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #10b981;"></span> Good: &lt;150</div>
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #f59e0b;"></span> Caution: 150-250</div>
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #ef4444;"></span> Action: &gt;250</div>
                    </div>
                </div>
                <a href="security_dashboard.html" class="detail-card">
                    <h4><span class="dashboard-icon">🔒</span> Security Dashboard</h4>
                    <div class="metric-row">
                        <span>Critical Vulns</span>
                        <strong>{security_metrics['severity_breakdown']['critical'] if security_metrics else 'N/A'}</strong>
                    </div>
                    <div class="metric-row">
                        <span>High Vulns</span>
                        <strong>{security_metrics['severity_breakdown']['high'] if security_metrics else 'N/A'}</strong>
                    </div>
                    <div class="metric-row">
                        <span>Total Vulns</span>
                        <strong>{security_metrics['current_total'] if security_metrics else 'N/A'}</strong>
                    </div>
                </a>
            </div>

            <!-- Pair 5: Deployment -->
            <div class="metric-pair" draggable="true" data-card-id="deployment">
                <div class="question-card">
                    <div class="question-card-header">
                        <h3>Deployment & DORA</h3>
                        <div class="header-description">
                            Track deployment frequency, build success rates, and lead time for changes. Measure DevOps performance.
                        </div>
                    </div>
                    <div class="metric" style="color: {success_rate_color};">{success_rate_display}</div>
                    <div class="metric-label">Build Success Rate</div>
                    <div class="rag-legend">
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #10b981;"></span> Good: &ge;90%</div>
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #f59e0b;"></span> Caution: 70-90%</div>
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #ef4444;"></span> Action: &lt;70%</div>
                    </div>
                </div>
                <a href="deployment_dashboard.html" class="detail-card">
                    <h4><span class="dashboard-icon">🚀</span> Deployment Dashboard</h4>
                    <div class="metric-row">
                        <span>Build Success Rate</span>
                        <strong>{success_rate_display}</strong>
                    </div>
                    <div class="metric-row">
                        <span>Total Builds (90d)</span>
                        <strong>{deployment_summary['total_builds'] if deployment_summary else 'N/A'}</strong>
                    </div>
                    <div class="metric-row">
                        <span>Projects</span>
                        <strong>{deployment_summary['projects_count'] if deployment_summary else 'N/A'}</strong>
                    </div>
                </a>
            </div>

            <!-- Pair 6: Collaboration -->
            <div class="metric-pair" draggable="true" data-card-id="collaboration">
                <div class="question-card">
                    <div class="question-card-header">
                        <h3>Collaboration & PRs</h3>
                        <div class="header-description">
                            Monitor code review efficiency, PR merge times, and review iterations. Optimize team collaboration.
                        </div>
                    </div>
                    <div class="metric" style="color: {merge_time_color};">{merge_time_display}</div>
                    <div class="metric-label">Avg PR Merge Time</div>
                    <div class="rag-legend">
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #10b981;"></span> Good: &lt;4h</div>
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #f59e0b;"></span> Caution: 4-24h</div>
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #ef4444;"></span> Action: &gt;24h</div>
                    </div>
                </div>
                <a href="collaboration_dashboard.html" class="detail-card">
                    <h4><span class="dashboard-icon">👥</span> Collaboration Dashboard</h4>
                    <div class="metric-row">
                        <span>Avg PR Merge Time</span>
                        <strong>{merge_time_display}</strong>
                    </div>
                    <div class="metric-row">
                        <span>Total PRs (90d)</span>
                        <strong>{collaboration_summary['total_prs'] if collaboration_summary else 'N/A'}</strong>
                    </div>
                    <div class="metric-row">
                        <span>Projects</span>
                        <strong>{collaboration_summary['projects_count'] if collaboration_summary else 'N/A'}</strong>
                    </div>
                </a>
            </div>

            <!-- Pair 7: Ownership -->
            <div class="metric-pair" draggable="true" data-card-id="ownership">
                <div class="question-card">
                    <div class="question-card-header">
                        <h3>Ownership & Distribution</h3>
                        <div class="header-description">
                            Track work assignment clarity and orphan areas. Identify ownership gaps early.
                        </div>
                    </div>
                    <div class="metric" style="color: {unassigned_color};">{unassigned_display}</div>
                    <div class="metric-label">Work Unassigned</div>
                    <div class="rag-legend">
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #10b981;"></span> Good: &lt;20%</div>
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #f59e0b;"></span> Caution: 20-40%</div>
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #ef4444;"></span> Action: &gt;40%</div>
                    </div>
                </div>
                <a href="ownership_dashboard.html" class="detail-card">
                    <h4><span class="dashboard-icon">👤</span> Ownership Dashboard</h4>
                    <div class="metric-row">
                        <span>Unassigned %</span>
                        <strong>{unassigned_display}</strong>
                    </div>
                    <div class="metric-row">
                        <span>Unassigned Items</span>
                        <strong>{ownership_summary['total_unassigned'] if ownership_summary else 'N/A'}</strong>
                    </div>
                    <div class="metric-row">
                        <span>Projects</span>
                        <strong>{ownership_summary['projects_count'] if ownership_summary else 'N/A'}</strong>
                    </div>
                </a>
            </div>

            <!-- Pair 8: Delivery Risk (Git Activity) -->
            <div class="metric-pair" draggable="true" data-card-id="risk">
                <div class="question-card">
                    <div class="question-card-header">
                        <h3>Delivery Risk & Stability</h3>
                        <div class="header-description">
                            Track code change activity and commit patterns. Understand delivery risk through Git metrics.
                        </div>
                    </div>
                    <div class="metric" style="color: #6366f1;">{risk_summary['total_commits'] if risk_summary else 'N/A'}</div>
                    <div class="metric-label">Total Commits (90d)</div>
                    <div class="rag-legend">
                        <div class="rag-legend-item"><span class="rag-dot" style="background: #6366f1;"></span> Git Activity Metrics</div>
                    </div>
                </div>
                <a href="risk_dashboard.html" class="detail-card">
                    <h4><span class="dashboard-icon">📊</span> Risk Dashboard</h4>
                    <div class="metric-row">
                        <span>Total Commits</span>
                        <strong>{risk_summary['total_commits'] if risk_summary else 'N/A'}</strong>
                    </div>
                    <div class="metric-row">
                        <span>Files Changed</span>
                        <strong>{risk_summary['files_changed'] if risk_summary else 'N/A'}</strong>
                    </div>
                    <div class="metric-row">
                        <span>Active Projects</span>
                        <strong>{risk_summary['active_projects'] if risk_summary else 'N/A'}</strong>
                    </div>
                </a>
            </div>
        </div>
    </div>

    <script>
        // Theme toggle
        function toggleTheme() {{
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        }}

        // Load saved theme
        const savedTheme = localStorage.getItem('theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);

        // Drag and Drop functionality
        let draggedElement = null;

        function initDragAndDrop() {{
            const cards = document.querySelectorAll('.metric-pair');

            cards.forEach(card => {{
                card.addEventListener('dragstart', handleDragStart);
                card.addEventListener('dragover', handleDragOver);
                card.addEventListener('drop', handleDrop);
                card.addEventListener('dragend', handleDragEnd);
                card.addEventListener('dragleave', handleDragLeave);
            }});

            // Load saved order
            loadCardOrder();
        }}

        function handleDragStart(e) {{
            draggedElement = this;
            this.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/html', this.innerHTML);
        }}

        function handleDragOver(e) {{
            if (e.preventDefault) {{
                e.preventDefault();
            }}
            e.dataTransfer.dropEffect = 'move';

            if (this !== draggedElement) {{
                this.classList.add('drag-over');
            }}
            return false;
        }}

        function handleDragLeave(e) {{
            this.classList.remove('drag-over');
        }}

        function handleDrop(e) {{
            if (e.stopPropagation) {{
                e.stopPropagation();
            }}

            this.classList.remove('drag-over');

            if (draggedElement !== this) {{
                const container = document.getElementById('cards-container');
                const allCards = [...container.children];
                const draggedIndex = allCards.indexOf(draggedElement);
                const targetIndex = allCards.indexOf(this);

                if (draggedIndex < targetIndex) {{
                    container.insertBefore(draggedElement, this.nextSibling);
                }} else {{
                    container.insertBefore(draggedElement, this);
                }}

                saveCardOrder();
            }}

            return false;
        }}

        function handleDragEnd(e) {{
            this.classList.remove('dragging');

            const cards = document.querySelectorAll('.metric-pair');
            cards.forEach(card => {{
                card.classList.remove('drag-over');
            }});
        }}

        function saveCardOrder() {{
            const container = document.getElementById('cards-container');
            const cards = [...container.children];
            const order = cards.map(card => card.getAttribute('data-card-id'));
            localStorage.setItem('cardOrder', JSON.stringify(order));
        }}

        function loadCardOrder() {{
            const savedOrder = localStorage.getItem('cardOrder');
            if (!savedOrder) return;

            try {{
                const order = JSON.parse(savedOrder);
                const container = document.getElementById('cards-container');
                const cards = [...container.children];

                // Reorder cards based on saved order
                order.forEach((cardId, index) => {{
                    const card = cards.find(c => c.getAttribute('data-card-id') === cardId);
                    if (card) {{
                        container.appendChild(card);
                    }}
                }});
            }} catch (e) {{
                console.error('Failed to load card order:', e);
            }}
        }}

        // Initialize drag and drop when page loads
        document.addEventListener('DOMContentLoaded', initDragAndDrop);

        // Open AI Usage Tracker
        function openUsageTracker() {{
            // Try to open the latest usage report
            // Path is relative to executive_summary.html location
            const reportPath = '../usage_tables_latest.html';

            // Open in new tab
            window.open(reportPath, '_blank');

            // Show info message
            setTimeout(() => {{
                if (!confirm('Usage report opened in new tab.\\n\\nTo refresh with latest data, run:\\npython execution/usage_tables_report.py\\n\\nView report now?')) {{
                    return;
                }}
            }}, 500);
        }}
    </script>
</body>
</html>'''

    return html


def main():
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    print("\nExecutive Summary Generator")
    print("=" * 60)

    print("\nLoading metrics from all dashboards...")
    metrics = load_dashboard_data()

    if not any(metrics.values()):
        print("[ERROR] No dashboard data found. Run individual dashboard generators first.")
        exit(1)

    print("  + Flow metrics loaded" if metrics['flow'] else "  ! Flow metrics not found")
    print("  + Ownership metrics loaded" if metrics['ownership'] else "  ! Ownership metrics not found")
    print("  + Quality metrics loaded" if metrics['quality'] else "  ! Quality metrics not found")
    print("  + Security metrics loaded" if metrics['security'] else "  ! Security metrics not found")
    print("  + Risk metrics loaded" if metrics['risk'] else "  ! Risk metrics not found")

    # Generate HTML
    print("\nGenerating executive summary...")
    html = generate_html(metrics)

    # Write to file (separate file, not landing page)
    output_dir = Path(".tmp/observatory/dashboards")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "executive_summary.html"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n[SUCCESS] Executive summary generated!")
    print(f"  Location: {output_file}")
    print(f"  Size: {len(html):,} bytes")
    print(f"\nOpen in browser: start {output_file}")

    print("\nFeatures:")
    print("  + Director-grade one-page health brief")
    print("  + Answers 7 key questions across all dimensions")
    print("  + Dashboard drill-through summaries")
    print("  + Items needing attention")
    print("  + Dark/light theme toggle")
    print("  + Print-friendly CSS")


if __name__ == '__main__':
    main()
