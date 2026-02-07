#!/usr/bin/env python3
"""
Analyze PRs to identify those created by Devin AI
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime


def load_risk_metrics():
    """Load risk metrics from history file"""
    risk_file = ".tmp/observatory/risk_history.json"

    if not os.path.exists(risk_file):
        print(f"[ERROR] Risk metrics file not found: {risk_file}")
        print("Run: py execution/ado_risk_metrics.py")
        return None

    with open(risk_file, encoding='utf-8') as f:
        return json.load(f)


def is_devin_pr(pr):
    """
    Check if a PR was created by Devin based on various signals.

    Devin might be identified by:
    - Author name containing "devin" (case-insensitive)
    - Branch name containing "devin"
    - PR title or description mentioning Devin
    - Email containing "devin"
    """
    indicators = []

    # Check author name
    author = pr.get('created_by', '').lower()
    if 'devin' in author:
        indicators.append(f"Author: {pr.get('created_by')}")

    # Check email
    email = pr.get('created_by_email', '').lower() if pr.get('created_by_email') else ''
    if email and 'devin' in email:
        indicators.append(f"Email: {email}")

    # Check branch name
    branch = pr.get('source_branch', '').lower() if pr.get('source_branch') else ''
    if branch and 'devin' in branch:
        indicators.append(f"Branch: {branch}")

    # Check title
    title = pr.get('title', '').lower()
    if 'devin' in title:
        indicators.append("Title mentions Devin")

    # Check description
    description = pr.get('description', '').lower() if pr.get('description') else ''
    if 'devin' in description:
        indicators.append("Description mentions Devin")

    return len(indicators) > 0, indicators


def analyze_devin_prs(risk_data):
    """Analyze all PRs to find Devin contributions"""

    if not risk_data or 'weeks' not in risk_data:
        print("[ERROR] Invalid risk data")
        return None, None

    # Get most recent week
    latest_week = risk_data['weeks'][-1]
    week_date = latest_week.get('week_date', 'Unknown')

    print(f"\nAnalyzing PRs from Week {latest_week.get('week_number')} ({week_date})")
    print("=" * 80)

    devin_prs = []
    all_prs = []
    project_stats = defaultdict(lambda: {'total': 0, 'devin': 0, 'devin_prs': []})
    author_stats = defaultdict(int)

    # Check if raw PR data exists
    has_raw_data = False

    # Collect all PRs from all projects
    for project in latest_week.get('projects', []):
        project_name = project['project_name']
        raw_prs = project.get('raw_prs', [])

        if not raw_prs:
            continue

        has_raw_data = True

        for pr in raw_prs:
            # Add project context to PR
            pr_with_context = {**pr, 'project': project_name}
            all_prs.append(pr_with_context)

            # Track authors
            author = pr.get('created_by', 'Unknown')
            author_stats[author] += 1

            # Check if this is a Devin PR
            is_devin, indicators = is_devin_pr(pr)

            project_stats[project_name]['total'] += 1

            if is_devin:
                project_stats[project_name]['devin'] += 1
                project_stats[project_name]['devin_prs'].append(pr['pr_id'])

                devin_prs.append({
                    'project': project_name,
                    'pr_id': pr['pr_id'],
                    'title': pr['title'],
                    'created_by': pr.get('created_by', 'Unknown'),
                    'created_date': pr.get('created_date'),
                    'commit_count': pr.get('commit_count', 0),
                    'indicators': indicators
                })

    if not has_raw_data:
        print("\n[INFO] No PR author data found in current metrics.")
        print("[INFO] Need to re-run metrics collection with enhanced author tracking.")
        print("\nRun this command to collect PR author data:")
        print("  py execution/ado_risk_metrics.py")
        return None, None

    # Print author statistics
    print(f"\nFound {len(all_prs)} total PRs from {len(author_stats)} unique authors")
    print("\nTop PR Contributors:")
    for author, count in sorted(author_stats.items(), key=lambda x: x[1], reverse=True)[:10]:
        is_devin = 'devin' in author.lower()
        marker = " [DEVIN]" if is_devin else ""
        print(f"  {author}{marker}: {count} PRs")

    # Print project statistics
    if project_stats:
        print("\nPRs by Project:")
        for project, stats in sorted(project_stats.items(), key=lambda x: x[1]['total'], reverse=True):
            devin_count = stats['devin']
            total = stats['total']
            pct = (devin_count / total * 100) if total > 0 else 0
            if devin_count > 0:
                print(f"  {project}: {devin_count}/{total} PRs by Devin ({pct:.1f}%)")
            else:
                print(f"  {project}: {total} PRs (none by Devin)")

    return devin_prs, all_prs


def generate_devin_report(devin_prs, all_prs, output_file=".tmp/observatory/devin_analysis.json"):
    """Generate a report of Devin's contributions"""

    if not all_prs:
        return

    total_prs = len(all_prs)
    devin_count = len(devin_prs)
    devin_percentage = (devin_count / total_prs * 100) if total_prs > 0 else 0

    report = {
        'analysis_date': datetime.now().isoformat(),
        'summary': {
            'total_prs': total_prs,
            'devin_prs': devin_count,
            'devin_percentage': round(devin_percentage, 1),
            'human_prs': total_prs - devin_count
        },
        'devin_prs': devin_prs
    }

    # Save report
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n[SAVED] Devin analysis report: {output_file}")

    # Print summary
    print("\n" + "=" * 80)
    print("DEVIN CONTRIBUTION ANALYSIS")
    print("=" * 80)
    print(f"Total PRs analyzed: {total_prs}")
    print(f"PRs created by Devin: {devin_count} ({devin_percentage:.1f}%)")
    print(f"PRs created by humans: {total_prs - devin_count} ({100-devin_percentage:.1f}%)")

    if devin_prs:
        print(f"\nDevin PRs (showing first 10 of {len(devin_prs)}):")
        for pr in devin_prs[:10]:
            print(f"\n  PR #{pr['pr_id']} - {pr['project']}")
            print(f"  Title: {pr['title']}")
            print(f"  Created by: {pr['created_by']}")
            print(f"  Date: {pr['created_date']}")
            print(f"  Commits: {pr['commit_count']}")
            print(f"  Indicators: {', '.join(pr['indicators'])}")


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    print("Devin PR Analysis Tool")
    print("=" * 80)

    # Load risk metrics
    risk_data = load_risk_metrics()

    if risk_data:
        devin_prs, all_prs = analyze_devin_prs(risk_data)

        if devin_prs is not None and all_prs is not None:
            generate_devin_report(devin_prs, all_prs)
        else:
            print("\n" + "=" * 80)
            print("NEXT STEPS:")
            print("=" * 80)
            print("1. Re-run metrics collection to capture author data:")
            print("   py execution/ado_risk_metrics.py")
            print("\n2. Run this script again to analyze Devin PRs:")
            print("   py execution/analyze_devin_prs.py")
