"""Trends calculation logic for Executive Trends Dashboard

Extracts and calculates trends from historical Observatory data:
- Target progress tracking with burn rate analysis
- Week-over-week changes for all metrics
- Trend indicators (↑↓→) and RAG colors
- Statistical aggregations (median, weighted averages)
"""

from datetime import datetime
from statistics import median


class TrendsCalculator:
    """Calculate trends and metrics for the Executive Trends Dashboard"""

    def __init__(self, baselines: dict | None = None):
        """Initialize calculator with baseline data

        Args:
            baselines: Dict with 'bugs' and 'security' baseline values
        """
        self.baselines = baselines or {}

    def calculate_target_progress(self, quality_weeks: list[dict], security_weeks: list[dict]) -> dict | None:
        """Calculate overall target progress (70% reduction goal)

        Args:
            quality_weeks: List of weekly quality data
            security_weeks: List of weekly security data

        Returns:
            Dict with progress metrics and forecast, or None if insufficient data
        """
        if not quality_weeks or not security_weeks:
            return None

        # Get current counts from latest data
        latest_quality = quality_weeks[-1]
        current_bugs = sum(p.get("open_bugs_count", 0) for p in latest_quality.get("projects", []))

        latest_security = security_weeks[-1]
        current_vulns = latest_security.get("metrics", {}).get("current_total", 0)

        # Calculate progress
        baseline_bugs = self.baselines.get("bugs", 0)
        baseline_vulns = self.baselines.get("security", 0)

        target_bugs = round(baseline_bugs * 0.3)  # 70% reduction = 30% remaining
        target_vulns = round(baseline_vulns * 0.3)

        # Progress calculation
        bugs_progress = (
            ((baseline_bugs - current_bugs) / (baseline_bugs - target_bugs) * 100) if baseline_bugs > target_bugs else 0
        )
        vulns_progress = (
            ((baseline_vulns - current_vulns) / (baseline_vulns - target_vulns) * 100)
            if baseline_vulns > target_vulns
            else 0
        )

        # Overall progress (average)
        overall_progress = (bugs_progress + vulns_progress) / 2

        # Weeks to target (June 30, 2026)
        target_date = datetime.strptime("2026-06-30", "%Y-%m-%d")
        today = datetime.now()
        weeks_remaining = max(0, (target_date - today).days / 7)

        # Burn rate analysis (4-week average) - SEPARATE for bugs and vulns
        if len(quality_weeks) >= 5 and len(security_weeks) >= 5:
            # Bugs 4 weeks ago
            bugs_4wk_ago = sum(p.get("open_bugs_count", 0) for p in quality_weeks[-5].get("projects", []))
            bugs_burned_4wk = bugs_4wk_ago - current_bugs
            actual_bugs_burn_rate = bugs_burned_4wk / 4

            # Vulns 4 weeks ago
            vulns_4wk_ago = security_weeks[-5].get("metrics", {}).get("current_total", 0)
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
            trajectory = "On Track"
            trajectory_color = "#10b981"
        elif overall_progress >= 40:
            trajectory = "Behind"
            trajectory_color = "#f59e0b"
        else:
            trajectory = "Behind"
            trajectory_color = "#ef4444"

        # Forecast message - check if BOTH are going backwards
        bugs_going_backwards = actual_bugs_burn_rate <= 0
        vulns_going_backwards = actual_vulns_burn_rate <= 0

        if bugs_going_backwards and vulns_going_backwards:
            forecast_msg = "⚠ Both bugs and vulnerabilities are increasing. Need to turn around immediately."
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
                forecast_msg = "On track: Current pace will reach target by June 30."
            else:
                forecast_msg = f"At current pace ({actual_bugs_burn_rate:.1f} bugs/wk, {actual_vulns_burn_rate:.1f} vulns/wk), reaching {int(avg_pct)}% of target by June 30."

        # Extract trend data for sparkline
        progress_trend = []

        for i in range(len(quality_weeks)):
            week_bugs = sum(p.get("open_bugs_count", 0) for p in quality_weeks[i].get("projects", []))

            if i < len(security_weeks):
                week_vulns = security_weeks[i].get("metrics", {}).get("current_total", 0)

                # Calculate progress for this week
                week_bugs_progress = (
                    ((baseline_bugs - week_bugs) / (baseline_bugs - target_bugs) * 100)
                    if baseline_bugs > target_bugs
                    else 0
                )
                week_vulns_progress = (
                    ((baseline_vulns - week_vulns) / (baseline_vulns - target_vulns) * 100)
                    if baseline_vulns > target_vulns
                    else 0
                )
                week_progress = (week_bugs_progress + week_vulns_progress) / 2
                progress_trend.append(round(week_progress, 1))

        return {
            "current": round(overall_progress, 1),
            "previous": progress_trend[-2] if len(progress_trend) > 1 else round(overall_progress, 1),
            "trend_data": progress_trend,
            "unit": "% progress",
            "forecast": {
                "trajectory": trajectory,
                "trajectory_color": trajectory_color,
                "weeks_to_target": round(weeks_remaining, 1),
                "required_bugs_burn": round(required_bugs_burn_rate, 2),
                "required_vulns_burn": round(required_vulns_burn_rate, 2),
                "actual_bugs_burn": round(actual_bugs_burn_rate, 2),
                "actual_vulns_burn": round(actual_vulns_burn_rate, 2),
                "forecast_msg": forecast_msg,
            },
        }

    def extract_quality_trends(self, weeks: list[dict]) -> dict | None:
        """Extract bug and MTTR trends from quality data

        Args:
            weeks: List of weekly quality data

        Returns:
            Dict with bugs and mttr trends, or None if no data
        """
        if not weeks:
            return None

        total_bugs_trend = []
        mttr_trend = []

        for week in weeks:
            # Sum open bugs across all projects
            total_bugs = sum(p.get("open_bugs_count", 0) for p in week.get("projects", []))
            total_bugs_trend.append(total_bugs)

            # Average MTTR across projects
            mttr_values = [
                p.get("mttr", {}).get("mttr_days")
                for p in week.get("projects", [])
                if p.get("mttr", {}).get("mttr_days") is not None
            ]
            avg_mttr = sum(mttr_values) / len(mttr_values) if mttr_values else 0
            mttr_trend.append(round(avg_mttr, 1))

        return {
            "bugs": {
                "current": total_bugs_trend[-1] if total_bugs_trend else 0,
                "previous": total_bugs_trend[-2] if len(total_bugs_trend) > 1 else 0,
                "trend_data": total_bugs_trend,
                "unit": "bugs",
            },
            "mttr": {
                "current": mttr_trend[-1] if mttr_trend else 0,
                "previous": mttr_trend[-2] if len(mttr_trend) > 1 else 0,
                "trend_data": mttr_trend,
                "unit": "days",
            },
        }

    def extract_security_trends(self, weeks: list[dict]) -> dict | None:
        """Extract security vulnerability trends

        Args:
            weeks: List of weekly security data

        Returns:
            Dict with vulnerability trends, or None if no data
        """
        if not weeks:
            return None

        vuln_trend = []

        for week in weeks:
            metrics = week.get("metrics", {})
            total = metrics.get("current_total", 0)
            vuln_trend.append(total)

        return {
            "vulnerabilities": {
                "current": vuln_trend[-1] if vuln_trend else 0,
                "previous": vuln_trend[-2] if len(vuln_trend) > 1 else 0,
                "trend_data": vuln_trend,
                "unit": "vulns",
            }
        }

    def extract_flow_trends(self, weeks: list[dict]) -> dict | None:
        """Extract flow trends (lead time)

        Uses median across all work types with operational metrics when cleanup is detected.
        Matches executive summary calculation for consistency.

        Args:
            weeks: List of weekly flow data

        Returns:
            Dict with lead time trends, or None if no data
        """
        if not weeks:
            return None

        lead_time_trend = []

        for week in weeks:
            projects = week.get("projects", [])

            # Collect lead times across all work types (matches exec summary logic)
            lead_times = []
            for proj in projects:
                # Check if project has work_type_metrics
                if "work_type_metrics" in proj:
                    # Aggregate across ALL work types
                    for work_type, metrics in proj.get("work_type_metrics", {}).items():
                        dual_metrics = metrics.get("dual_metrics", {})
                        has_cleanup = dual_metrics.get("indicators", {}).get("is_cleanup_effort", False)

                        if has_cleanup:
                            # Use operational metrics for accurate performance view
                            operational = dual_metrics.get("operational", {})
                            op_p85 = operational.get("p85")
                            if op_p85:
                                lead_times.append(op_p85)
                        else:
                            # Use standard lead time
                            lead_time = metrics.get("lead_time", {})
                            if lead_time.get("p85"):
                                lead_times.append(lead_time["p85"])
                else:
                    # Legacy data format
                    if proj.get("lead_time", {}).get("p85"):
                        lead_times.append(proj["lead_time"]["p85"])

            # Use median (not mean) to handle outliers
            avg_lead_time = median(lead_times) if lead_times else 0
            lead_time_trend.append(round(avg_lead_time, 1))

        return {
            "lead_time": {
                "current": lead_time_trend[-1] if lead_time_trend else 0,
                "previous": lead_time_trend[-2] if len(lead_time_trend) > 1 else 0,
                "trend_data": lead_time_trend,
                "unit": "days",
            }
        }

    def extract_deployment_trends(self, weeks: list[dict]) -> dict | None:
        """Extract deployment trends (build success rate)

        Uses weighted average (total successful / total builds) for accuracy.
        Matches executive summary calculation for consistency.

        Args:
            weeks: List of weekly deployment data

        Returns:
            Dict with build success trends, or None if no data
        """
        if not weeks:
            return None

        build_success_trend = []

        for week in weeks:
            projects = week.get("projects", [])

            # Weighted average: total successful builds / total builds (matches exec summary)
            total_builds = sum(p.get("build_success_rate", {}).get("total_builds", 0) for p in projects)
            total_successful = sum(p.get("build_success_rate", {}).get("succeeded", 0) for p in projects)
            weighted_success_rate = (total_successful / total_builds * 100) if total_builds > 0 else 0
            build_success_trend.append(round(weighted_success_rate, 1))

        return {
            "build_success": {
                "current": build_success_trend[-1] if build_success_trend else 0,
                "previous": build_success_trend[-2] if len(build_success_trend) > 1 else 0,
                "trend_data": build_success_trend,
                "unit": "%",
            }
        }

    def extract_collaboration_trends(self, weeks: list[dict]) -> dict | None:
        """Extract collaboration trends (PR merge time)

        Uses median of project medians for robustness to outliers.
        Matches executive summary calculation for consistency.

        Args:
            weeks: List of weekly collaboration data

        Returns:
            Dict with PR merge time trends, or None if no data
        """
        if not weeks:
            return None

        pr_merge_trend = []

        for week in weeks:
            projects = week.get("projects", [])

            # Median PR merge time across projects (robust to outliers)
            merge_times = [
                p.get("pr_merge_time", {}).get("median_hours")
                for p in projects
                if p.get("pr_merge_time", {}).get("median_hours") is not None
            ]
            avg_merge_time = median(merge_times) if merge_times else 0
            pr_merge_trend.append(round(avg_merge_time, 1))

        return {
            "pr_merge_time": {
                "current": pr_merge_trend[-1] if pr_merge_trend else 0,
                "previous": pr_merge_trend[-2] if len(pr_merge_trend) > 1 else 0,
                "trend_data": pr_merge_trend,
                "unit": "hours",
            }
        }

    def extract_ownership_trends(self, weeks: list[dict]) -> dict | None:
        """Extract ownership trends (unassigned work percentage)

        Args:
            weeks: List of weekly ownership data

        Returns:
            Dict with unassigned work trends, or None if no data
        """
        if not weeks:
            return None

        unassigned_trend = []

        for week in weeks:
            projects = week.get("projects", [])

            # Weighted average: total unassigned / total items (consistent with Ownership Dashboard)
            total_items = sum(p.get("unassigned", {}).get("total_items", 0) for p in projects)
            total_unassigned = sum(p.get("unassigned", {}).get("unassigned_count", 0) for p in projects)
            weighted_unassigned = (total_unassigned / total_items * 100) if total_items > 0 else 0
            unassigned_trend.append(round(weighted_unassigned, 1))

        return {
            "work_unassigned": {
                "current": unassigned_trend[-1] if unassigned_trend else 0,
                "previous": unassigned_trend[-2] if len(unassigned_trend) > 1 else 0,
                "trend_data": unassigned_trend,
                "unit": "%",
            }
        }

    def extract_risk_trends(self, weeks: list[dict]) -> dict | None:
        """Extract risk trends (commit activity)

        Tracks commit activity over time as indicator of delivery risk.
        Matches executive summary calculation for consistency.

        Args:
            weeks: List of weekly risk data

        Returns:
            Dict with commit trends, or None if no data
        """
        if not weeks:
            return None

        commits_trend = []

        for week in weeks:
            projects = week.get("projects", [])

            # Total commits across all projects
            total_commits = sum(p.get("code_churn", {}).get("total_commits", 0) for p in projects)
            commits_trend.append(total_commits)

        return {
            "total_commits": {
                "current": commits_trend[-1] if commits_trend else 0,
                "previous": commits_trend[-2] if len(commits_trend) > 1 else 0,
                "trend_data": commits_trend,
                "unit": "commits",
            }
        }

    @staticmethod
    def get_trend_indicator(current: float, previous: float, good_direction: str = "down") -> tuple[str, str, float]:
        """Get trend indicator (↑↓→) and CSS class

        Args:
            current: Current metric value
            previous: Previous metric value
            good_direction: "down", "up", or "stable" - which direction is good

        Returns:
            Tuple of (arrow, css_class, change)
        """
        change = current - previous

        if abs(change) < 0.5:
            return ("→", "trend-stable", change)

        is_increasing = change > 0

        if good_direction == "down":
            if is_increasing:
                return ("↑", "trend-up", change)  # Red (bad)
            else:
                return ("↓", "trend-down", change)  # Green (good)
        else:  # good_direction == 'up'
            if is_increasing:
                return ("↑", "trend-down", change)  # Green (good)
            else:
                return ("↓", "trend-up", change)  # Red (bad)

    @staticmethod
    def get_rag_color(value: float | int | str | None, metric_type: str) -> str:
        """Determine RAG color based on metric value and type

        Args:
            value: Metric value
            metric_type: Type of metric (e.g., "lead_time", "bugs", "success_rate")

        Returns:
            Hex color code for RAG status
        """
        if value == "N/A" or value is None:
            return "#94a3b8"  # Gray for N/A

        try:
            if metric_type == "lead_time":
                # Lower is better: <30 days green, 30-60 amber, >60 red
                val = float(value)
                if val < 30:
                    return "#10b981"  # Green
                elif val < 60:
                    return "#f59e0b"  # Amber
                else:
                    return "#ef4444"  # Red

            elif metric_type == "mttr":
                # Lower is better: <7 days green, 7-14 days amber, >14 days red
                val = float(value)
                if val < 7:
                    return "#10b981"
                elif val < 14:
                    return "#f59e0b"
                else:
                    return "#ef4444"

            elif metric_type == "total_vulns":
                # Lower is better: <150 green, 150-250 amber, >250 red
                val = int(value)
                if val < 150:
                    return "#10b981"
                elif val < 250:
                    return "#f59e0b"
                else:
                    return "#ef4444"

            elif metric_type == "bugs":
                # Lower is better: <100 green, 100-200 amber, >200 red
                val = int(value)
                if val < 100:
                    return "#10b981"
                elif val < 200:
                    return "#f59e0b"
                else:
                    return "#ef4444"

            elif metric_type == "success_rate":
                # Higher is better: >90% green, 70-90% amber, <70% red
                val = float(value)
                if val >= 90:
                    return "#10b981"
                elif val >= 70:
                    return "#f59e0b"
                else:
                    return "#ef4444"

            elif metric_type == "merge_time":
                # Lower is better: <4h green, 4-24h amber, >24h red
                val = float(value)
                if val < 4:
                    return "#10b981"
                elif val < 24:
                    return "#f59e0b"
                else:
                    return "#ef4444"

            elif metric_type == "unassigned":
                # Lower is better: <20% green, 20-40% amber, >40% red
                val = float(value)
                if val < 20:
                    return "#10b981"
                elif val < 40:
                    return "#f59e0b"
                else:
                    return "#ef4444"

            elif metric_type == "target_progress":
                # Higher is better: >=70% green, 40-70% amber, <40% red
                val = float(value)
                if val >= 70:
                    return "#10b981"
                elif val >= 40:
                    return "#f59e0b"
                else:
                    return "#ef4444"

            elif metric_type == "commits":
                # Neutral metric - no RAG thresholds
                return "#6366f1"  # Purple

            return "#6366f1"  # Default purple
        except (ValueError, TypeError):
            return "#94a3b8"  # Gray for invalid values
