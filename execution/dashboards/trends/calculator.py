"""Trends calculation logic for Executive Trends Dashboard

Extracts and calculates trends from historical Observatory data:
- Target progress tracking with burn rate analysis
- Week-over-week changes for all metrics
- Trend indicators (↑↓→) and RAG colors
- Statistical aggregations (median, weighted averages)
"""

from datetime import datetime
from statistics import median
from typing import Any

# ---------------------------------------------------------------------------
# RAG color constants
# ---------------------------------------------------------------------------
_GREEN = "#10b981"
_AMBER = "#f59e0b"
_RED = "#ef4444"
_PURPLE = "#6366f1"
_GRAY = "#94a3b8"

# ---------------------------------------------------------------------------
# RAG threshold lookup table
#
# Each entry: (cast_fn, [(threshold, color), ...], fallback_color)
#
# For "lower is better" metrics the thresholds are upper bounds checked in
# ascending order; the first threshold whose value is LESS THAN the limit
# wins.  A sentinel entry of (None, fallback) at the end catches the
# remainder.
#
# For "higher is better" metrics the thresholds are lower bounds checked in
# descending order; the first threshold whose value is GREATER THAN OR EQUAL
# TO the limit wins.
#
# The optional 4th element "higher" marks metrics where larger values are
# better (checked with >=).  Absence means "lower is better" (checked with <).
# ---------------------------------------------------------------------------
_RAG_THRESHOLDS: dict[str, tuple[Any, list[tuple[float, str]], str] | tuple[Any, list[tuple[float, str]], str, str]] = {
    # lower is better
    "lead_time": (float, [(30, _GREEN), (60, _AMBER)], _RED),
    "mttr": (float, [(7, _GREEN), (14, _AMBER)], _RED),
    "total_vulns": (int, [(150, _GREEN), (250, _AMBER)], _RED),
    "bugs": (int, [(100, _GREEN), (200, _AMBER)], _RED),
    "merge_time": (float, [(4, _GREEN), (24, _AMBER)], _RED),
    "unassigned": (float, [(20, _GREEN), (40, _AMBER)], _RED),
    # higher is better
    "success_rate": (float, [(90, _GREEN), (70, _AMBER)], _RED, "higher"),
    "target_progress": (float, [(70, _GREEN), (40, _AMBER)], _RED, "higher"),
    # neutral
    "commits": (int, [], _PURPLE),
}


def _apply_rag_thresholds(
    cast_fn: Any,
    thresholds: list[tuple[float, str]],
    fallback: str,
    raw_value: Any,
    higher_is_better: bool,
) -> str:
    """Apply threshold list to a raw value and return the matching color."""
    val = cast_fn(raw_value)
    for limit, color in thresholds:
        if higher_is_better:
            if val >= limit:
                return color
        else:
            if val < limit:
                return color
    return fallback


def _compute_progress_pct(current: int, baseline: int, target: int) -> float:
    """Compute progress percentage toward target for a single metric.

    Returns 0 when the denominator would be zero (baseline already at or below target).
    """
    if baseline <= target:
        return 0.0
    return (baseline - current) / (baseline - target) * 100


def _collect_project_lead_times(proj: dict) -> list[float]:
    """Extract lead-time values from a single project dict.

    Handles both the new work_type_metrics format and the legacy lead_time format.
    Returns a (possibly empty) list of p85 values.
    """
    lead_times: list[float] = []
    if "work_type_metrics" in proj:
        for _wt, metrics in proj.get("work_type_metrics", {}).items():
            dual = metrics.get("dual_metrics", {})
            has_cleanup = dual.get("indicators", {}).get("is_cleanup_effort", False)
            if has_cleanup:
                op_p85 = dual.get("operational", {}).get("p85")
                if op_p85:
                    lead_times.append(op_p85)
            else:
                p85 = metrics.get("lead_time", {}).get("p85")
                if p85:
                    lead_times.append(p85)
    else:
        p85 = proj.get("lead_time", {}).get("p85")
        if p85:
            lead_times.append(p85)
    return lead_times


class TrendsCalculator:
    """Calculate trends and metrics for the Executive Trends Dashboard"""

    def __init__(self, baselines: dict | None = None):
        """Initialize calculator with baseline data

        Args:
            baselines: Dict with 'bugs' and 'security' baseline values
        """
        self.baselines = baselines or {}

    # ------------------------------------------------------------------
    # Private helpers for calculate_target_progress
    # ------------------------------------------------------------------

    @staticmethod
    def _get_week_vulns(security_week: dict) -> int:
        """Extract vuln count from a single security week, preferring code_cloud bucket."""
        bb = security_week.get("metrics", {}).get("bucket_breakdown", {})
        cc = bb.get("code_cloud", {}).get("total", None)
        return cc if cc is not None else security_week.get("metrics", {}).get("current_total", 0)

    @staticmethod
    def _compute_burn_rates(
        quality_weeks: list[dict],
        security_weeks: list[dict],
        current_bugs: int,
        current_vulns: int,
    ) -> tuple[float, float]:
        """Compute 4-week burn rates for bugs and vulns. Returns (bugs_rate, vulns_rate)."""
        if len(quality_weeks) >= 5 and len(security_weeks) >= 5:
            bugs_4wk_ago = sum(p.get("open_bugs_count", 0) for p in quality_weeks[-5].get("projects", []))
            actual_bugs_burn_rate = (bugs_4wk_ago - current_bugs) / 4

            vulns_4wk_ago = TrendsCalculator._get_week_vulns(security_weeks[-5])
            actual_vulns_burn_rate = (vulns_4wk_ago - current_vulns) / 4
        else:
            actual_bugs_burn_rate = 0.0
            actual_vulns_burn_rate = 0.0
        return actual_bugs_burn_rate, actual_vulns_burn_rate

    @staticmethod
    def _build_trajectory(overall_progress: float) -> tuple[str, str]:
        """Return (trajectory_label, trajectory_color) for a given progress %."""
        if overall_progress >= 70:
            return "On Track", _GREEN
        elif overall_progress >= 40:
            return "Behind", _AMBER
        return "Behind", _RED

    @staticmethod
    def _build_forecast_msg(
        actual_bugs_burn: float,
        actual_vulns_burn: float,
        required_bugs_burn: float,
        required_vulns_burn: float,
    ) -> str:
        """Build human-readable forecast message from burn-rate data."""
        bugs_going_backwards = actual_bugs_burn <= 0
        vulns_going_backwards = actual_vulns_burn <= 0

        if bugs_going_backwards and vulns_going_backwards:
            return "⚠ Both bugs and vulnerabilities are increasing. Need to turn around immediately."
        if bugs_going_backwards:
            return (
                f"⚠ Bugs are increasing at {abs(actual_bugs_burn):.1f}/wk. "
                f"Vulnerabilities decreasing at {actual_vulns_burn:.1f}/wk."
            )
        if vulns_going_backwards:
            return (
                f"⚠ Vulnerabilities are increasing at {abs(actual_vulns_burn):.1f}/wk. "
                f"Bugs decreasing at {actual_bugs_burn:.1f}/wk."
            )

        # Both positive — show pace status
        bugs_pct = (actual_bugs_burn / required_bugs_burn * 100) if required_bugs_burn > 0 else 0
        vulns_pct = (actual_vulns_burn / required_vulns_burn * 100) if required_vulns_burn > 0 else 0
        avg_pct = (bugs_pct + vulns_pct) / 2

        if avg_pct >= 100:
            return "On track: Current pace will reach target by June 30."
        return (
            f"At current pace ({actual_bugs_burn:.1f} bugs/wk, {actual_vulns_burn:.1f} vulns/wk), "
            f"reaching {int(avg_pct)}% of target by June 30."
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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

        # Current counts from latest data
        latest_quality = quality_weeks[-1]
        current_bugs = sum(p.get("open_bugs_count", 0) for p in latest_quality.get("projects", []))
        current_vulns = self._get_week_vulns(security_weeks[-1])

        # Baselines and targets (70% reduction = 30% remaining)
        baseline_bugs = self.baselines.get("bugs", 0)
        baseline_vulns = self.baselines.get("security", 0)
        target_bugs = round(baseline_bugs * 0.3)
        target_vulns = round(baseline_vulns * 0.3)

        # Progress percentages
        bugs_progress = _compute_progress_pct(current_bugs, baseline_bugs, target_bugs)
        vulns_progress = _compute_progress_pct(current_vulns, baseline_vulns, target_vulns)
        overall_progress = (bugs_progress + vulns_progress) / 2

        # Time remaining
        target_date = datetime.strptime("2026-06-30", "%Y-%m-%d")
        weeks_remaining = max(0, (target_date - datetime.now()).days / 7)

        # Burn rates
        actual_bugs_burn, actual_vulns_burn = self._compute_burn_rates(
            quality_weeks, security_weeks, current_bugs, current_vulns
        )

        # Required burn rates
        required_bugs_burn = (current_bugs - target_bugs) / weeks_remaining if weeks_remaining > 0 else 0
        required_vulns_burn = (current_vulns - target_vulns) / weeks_remaining if weeks_remaining > 0 else 0

        # Trajectory and forecast
        trajectory, trajectory_color = self._build_trajectory(overall_progress)
        forecast_msg = self._build_forecast_msg(
            actual_bugs_burn, actual_vulns_burn, required_bugs_burn, required_vulns_burn
        )

        # Sparkline trend data
        progress_trend = self._build_progress_trend(
            quality_weeks, security_weeks, baseline_bugs, baseline_vulns, target_bugs, target_vulns
        )

        # Use previous only if it was also computed with bucket_breakdown (code_cloud) data
        prev_has_cc = (
            len(security_weeks) >= 2
            and security_weeks[-2].get("metrics", {}).get("bucket_breakdown", {}).get("code_cloud") is not None
        )
        previous_progress = (
            progress_trend[-2] if (len(progress_trend) > 1 and prev_has_cc) else round(overall_progress, 1)
        )

        return {
            "current": round(overall_progress, 1),
            "previous": previous_progress,
            "trend_data": progress_trend,
            "unit": "% progress",
            "forecast": {
                "trajectory": trajectory,
                "trajectory_color": trajectory_color,
                "weeks_to_target": round(weeks_remaining, 1),
                "required_bugs_burn": round(required_bugs_burn, 2),
                "required_vulns_burn": round(required_vulns_burn, 2),
                "actual_bugs_burn": round(actual_bugs_burn, 2),
                "actual_vulns_burn": round(actual_vulns_burn, 2),
                "forecast_msg": forecast_msg,
            },
        }

    def _build_progress_trend(
        self,
        quality_weeks: list[dict],
        security_weeks: list[dict],
        baseline_bugs: int,
        baseline_vulns: int,
        target_bugs: int,
        target_vulns: int,
    ) -> list[float]:
        """Build per-week progress percentages for sparkline rendering."""
        progress_trend = []
        for i in range(len(quality_weeks)):
            if i >= len(security_weeks):
                continue
            week_bugs = sum(p.get("open_bugs_count", 0) for p in quality_weeks[i].get("projects", []))
            week_vulns = self._get_week_vulns(security_weeks[i])
            week_bugs_progress = _compute_progress_pct(week_bugs, baseline_bugs, target_bugs)
            week_vulns_progress = _compute_progress_pct(week_vulns, baseline_vulns, target_vulns)
            progress_trend.append(round((week_bugs_progress + week_vulns_progress) / 2, 1))
        return progress_trend

    @staticmethod
    def _extract_week_mttr(projects: list[dict]) -> float:
        """Return the average MTTR (days) across projects for one week, or 0 if none."""
        mttr_values = [
            p.get("mttr", {}).get("mttr_days") for p in projects if p.get("mttr", {}).get("mttr_days") is not None
        ]
        return round(sum(mttr_values) / len(mttr_values), 1) if mttr_values else 0

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
            projects = week.get("projects", [])
            total_bugs_trend.append(sum(p.get("open_bugs_count", 0) for p in projects))
            mttr_trend.append(self._extract_week_mttr(projects))

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
            lead_times: list[float] = []
            for proj in projects:
                lead_times.extend(_collect_project_lead_times(proj))

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

    def extract_security_code_cloud_trends(self, weeks: list[dict]) -> dict | None:
        """Extract Code+Cloud vulnerability trends from bucket_breakdown in history.

        Reads bucket_breakdown.code_cloud.total from each week.
        Missing key (historical weeks before split deploy) → 0; no raise.

        Args:
            weeks: List of weekly security data

        Returns:
            Dict with code_cloud vulnerability trends, or None if no data
        """
        if not weeks:
            return None

        cc_trend = [
            w.get("metrics", {}).get("bucket_breakdown", {}).get("code_cloud", {}).get("total", 0) for w in weeks
        ]
        return {
            "vulnerabilities": {
                "current": cc_trend[-1],
                "previous": cc_trend[-2] if len(cc_trend) > 1 else 0,
                "trend_data": cc_trend,
                "unit": "vulns",
            }
        }

    def extract_security_infra_trends(self, weeks: list[dict]) -> dict | None:
        """Extract Infrastructure vulnerability trends from bucket_breakdown in history.

        Reads bucket_breakdown.infrastructure.total from each week.
        Missing key (historical weeks before split deploy) → 0; no raise.

        Args:
            weeks: List of weekly security data

        Returns:
            Dict with infrastructure vulnerability trends, or None if no data
        """
        if not weeks:
            return None

        infra_trend = [
            w.get("metrics", {}).get("bucket_breakdown", {}).get("infrastructure", {}).get("total", 0) for w in weeks
        ]
        return {
            "vulnerabilities": {
                "current": infra_trend[-1],
                "previous": infra_trend[-2] if len(infra_trend) > 1 else 0,
                "trend_data": infra_trend,
                "unit": "vulns",
            }
        }

    def extract_exploitable_trends(self, weeks: list[dict]) -> dict | None:
        """Extract exploitable vulnerability trends from exploitable_history.json weeks."""
        if not weeks:
            return None
        total_trend: list[int] = []
        critical_list: list[int] = []
        high_list: list[int] = []
        for week in weeks:
            sb = week.get("metrics", {}).get("severity_breakdown", {})
            total_trend.append(sb.get("total", 0))
            critical_list.append(sb.get("critical", 0))
            high_list.append(sb.get("high", 0))
        return {
            "exploitable": {
                "current": total_trend[-1] if total_trend else 0,
                "previous": total_trend[-2] if len(total_trend) > 1 else 0,
                "current_critical": critical_list[-1] if critical_list else 0,
                "current_high": high_list[-1] if high_list else 0,
                "trend_data": total_trend,
                "unit": "vulns",
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
            return _GRAY

        config = _RAG_THRESHOLDS.get(metric_type)
        if config is None:
            return _PURPLE

        cast_fn, thresholds, fallback = config[0], config[1], config[2]
        higher_is_better = len(config) == 4 and config[3] == "higher"

        try:
            return _apply_rag_thresholds(cast_fn, thresholds, fallback, value, higher_is_better)
        except (ValueError, TypeError):
            return _GRAY
