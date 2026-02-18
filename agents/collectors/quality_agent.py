"""
Quality Collector Agent

Autonomous agent that collects quality metrics using the ADO skill.
Replaces the monolithic ado_quality_metrics.py collector with a thin agent wrapper.
"""

import asyncio
from datetime import datetime

from skills.ado_skill.tools.get_test_runs import get_test_runs
from skills.ado_skill.tools.get_work_items_by_ids import get_work_items_by_ids
from skills.ado_skill.tools.query_work_items import query_work_items

from agents.base_agent import BaseAgent
from execution.collectors.security_bug_filter import filter_security_bugs
from execution.utils.datetime_utils import calculate_age_days, calculate_lead_time_days
from execution.utils.statistics import calculate_percentile


class QualityAgent(BaseAgent):
    """
    Autonomous quality metrics collector using ADO skill.

    Collects:
    - Bug age distribution
    - Mean Time To Repair (MTTR)
    - Test execution time

    Uses ADO skill tools instead of direct REST client calls.
    """

    def __init__(self, config: dict | None = None):
        """
        Initialize quality agent.

        Args:
            config: Optional configuration (lookback_days, etc.)
        """
        super().__init__(name="quality", config=config or {"lookback_days": 90})

    async def collect(self, project: dict) -> dict:
        """
        Collect quality metrics for a single project.

        Args:
            project: Project metadata from discovery

        Returns:
            Quality metrics dictionary
        """
        project_name = project["project_name"]
        project_key = project["project_key"]
        ado_project_name = project.get("ado_project_name", project_name)
        area_path_filter = project.get("area_path_filter")

        print(f"\n  Collecting quality metrics for: {project_name}")

        # Get organization name
        organization = self.get_ado_organization()
        lookback_days = self.config.get("lookback_days", 90)

        # Step 1: Query bugs and test execution time CONCURRENTLY
        bugs_task = self._query_bugs(organization, ado_project_name, lookback_days, area_path_filter)
        test_exec_task = self._get_test_execution_time(organization, ado_project_name)

        bugs, test_execution = await asyncio.gather(bugs_task, test_exec_task)

        # Step 2: Filter out security bugs (avoid double-counting with security dashboard)
        bugs["all_bugs"], excluded_all = filter_security_bugs(bugs["all_bugs"])
        bugs["open_bugs"], excluded_open = filter_security_bugs(bugs["open_bugs"])

        if excluded_open > 0 or excluded_all > 0:
            print(
                f"    Excluded {excluded_open} open security bugs and {excluded_all} total "
                f"security bugs from quality metrics"
            )

        # Step 3: Calculate metrics
        age_distribution = self._calculate_bug_age_distribution(bugs["open_bugs"])
        mttr = self._calculate_mttr(bugs["all_bugs"])

        print(f"    Median Bug Age: {age_distribution['median_age_days']} days")
        print(f"    MTTR: {mttr['mttr_days']} days (median: {mttr['median_mttr_days']})")
        print(f"    Test Execution Time: {test_execution['median_minutes']} minutes")

        return {
            "project_key": project_key,
            "project_name": project_name,
            "bug_age_distribution": age_distribution,
            "mttr": mttr,
            "test_execution_time": test_execution,
            "total_bugs_analyzed": len(bugs["all_bugs"]),
            "open_bugs_count": len(bugs["open_bugs"]),
            "excluded_security_bugs": {"total": excluded_all, "open": excluded_open},
            "collected_at": datetime.now().isoformat(),
        }

    async def _query_bugs(
        self, organization: str, project: str, lookback_days: int, area_path_filter: str | None
    ) -> dict:
        """
        Query bugs using ADO skill.

        Args:
            organization: ADO organization name
            project: Project name
            lookback_days: Days to look back
            area_path_filter: Optional area path filter

        Returns:
            Dict with all_bugs and open_bugs lists
        """
        from datetime import timedelta

        from execution.security import WIQLValidator

        lookback_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        safe_project = WIQLValidator.validate_project_name(project)
        safe_lookback_date = WIQLValidator.validate_date_iso8601(lookback_date)

        # Build area filter clause
        area_filter_clause = ""
        if area_path_filter:
            if area_path_filter.startswith("EXCLUDE:"):
                path = area_path_filter.replace("EXCLUDE:", "")
                safe_path = WIQLValidator.validate_area_path(path)
                area_filter_clause = f"AND [System.AreaPath] NOT UNDER '{safe_path}'"
            elif area_path_filter.startswith("INCLUDE:"):
                path = area_path_filter.replace("INCLUDE:", "")
                safe_path = WIQLValidator.validate_area_path(path)
                area_filter_clause = f"AND [System.AreaPath] UNDER '{safe_path}'"

        # Query 1: All bugs
        wiql_all_bugs = f"""
            SELECT [System.Id], [System.Title], [System.State], [System.CreatedDate],
                   [System.WorkItemType], [Microsoft.VSTS.Common.Priority],
                   [Microsoft.VSTS.Common.Severity], [System.Tags],
                   [Microsoft.VSTS.Common.ClosedDate], [Microsoft.VSTS.Common.ResolvedDate]
            FROM WorkItems
            WHERE [System.TeamProject] = '{safe_project}'
              AND [System.WorkItemType] = 'Bug'
              AND [System.CreatedDate] >= '{safe_lookback_date}'
              {area_filter_clause}
            ORDER BY [System.CreatedDate] DESC
        """

        # Query 2: Open bugs
        wiql_open_bugs = f"""
            SELECT [System.Id], [System.Title], [System.State], [System.CreatedDate],
                   [System.WorkItemType], [Microsoft.VSTS.Common.Priority],
                   [Microsoft.VSTS.Common.Severity], [System.Tags]
            FROM WorkItems
            WHERE [System.TeamProject] = '{safe_project}'
              AND [System.WorkItemType] = 'Bug'
              AND [System.State] <> 'Closed'
              AND [System.State] <> 'Removed'
              AND ([Microsoft.VSTS.Common.Triage] <> 'Rejected' OR [Microsoft.VSTS.Common.Triage] = '')
              {area_filter_clause}
            ORDER BY [System.CreatedDate] ASC
        """

        # Execute queries concurrently using ADO skill
        all_bugs_result, open_bugs_result = await asyncio.gather(
            query_work_items(organization, project, wiql_all_bugs),
            query_work_items(organization, project, wiql_open_bugs),
        )

        # Extract IDs
        all_bug_ids = [item["id"] for item in all_bugs_result.get("workItems", [])]
        open_bug_ids = [item["id"] for item in open_bugs_result.get("workItems", [])]

        print(f"      Found {len(all_bug_ids)} total bugs (last {lookback_days} days)")
        print(f"      Found {len(open_bug_ids)} open bugs")

        # Fetch full bug details concurrently
        all_bugs_task = self._fetch_bug_details(organization, all_bug_ids, include_closed=True)
        open_bugs_task = self._fetch_bug_details(organization, open_bug_ids, include_closed=False)

        all_bugs, open_bugs = await asyncio.gather(all_bugs_task, open_bugs_task)

        return {"all_bugs": all_bugs, "open_bugs": open_bugs}

    async def _fetch_bug_details(
        self, organization: str, bug_ids: list[int], include_closed: bool = True
    ) -> list[dict]:
        """
        Fetch full bug details using ADO skill (batched).

        Args:
            organization: ADO organization name
            bug_ids: List of bug IDs
            include_closed: Whether to include closed date fields

        Returns:
            List of bug field dictionaries
        """
        if not bug_ids:
            return []

        fields = [
            "System.Id",
            "System.Title",
            "System.State",
            "System.CreatedDate",
            "System.WorkItemType",
            "Microsoft.VSTS.Common.Priority",
            "Microsoft.VSTS.Common.Severity",
            "System.Tags",
            "System.CreatedBy",
        ]

        if include_closed:
            fields.extend(
                [
                    "Microsoft.VSTS.Common.ClosedDate",
                    "Microsoft.VSTS.Common.ResolvedDate",
                ]
            )

        # Batch into chunks of 200 (API limit)
        bugs = []
        for i in range(0, len(bug_ids), 200):
            batch = bug_ids[i : i + 200]
            result = await get_work_items_by_ids(organization, batch, fields)
            bugs.extend([item["fields"] for item in result.get("value", [])])

        return bugs

    async def _get_test_execution_time(self, organization: str, project: str) -> dict:
        """
        Get test execution time using ADO skill.

        Args:
            organization: ADO organization name
            project: Project name

        Returns:
            Test execution time metrics
        """
        try:
            result = await get_test_runs(organization, project, top=50)
            test_runs = result.get("value", [])

            execution_times = []
            for run in test_runs:
                started = run.get("startedDate")
                completed = run.get("completedDate")

                if started and completed:
                    from execution.utils.datetime_utils import parse_ado_timestamp

                    started_dt = parse_ado_timestamp(started)
                    completed_dt = parse_ado_timestamp(completed)

                    if started_dt and completed_dt:
                        duration = completed_dt - started_dt
                        duration_minutes = duration.total_seconds() / 60
                        if duration_minutes > 0:
                            execution_times.append(duration_minutes)

            if not execution_times:
                return {"sample_size": 0, "median_minutes": None, "p85_minutes": None, "p95_minutes": None}

            return {
                "sample_size": len(execution_times),
                "median_minutes": round(calculate_percentile(execution_times, 50), 1),
                "p85_minutes": round(calculate_percentile(execution_times, 85), 1),
                "p95_minutes": round(calculate_percentile(execution_times, 95), 1),
            }

        except Exception as e:
            print(f"      Warning: Could not get test execution time: {e}")
            return {"sample_size": 0, "median_minutes": None, "p85_minutes": None, "p95_minutes": None}

    def _calculate_bug_age_distribution(self, open_bugs: list[dict]) -> dict:
        """Calculate bug age distribution."""
        from datetime import UTC

        now = datetime.now(UTC)
        ages = []

        for bug in open_bugs:
            created = bug.get("System.CreatedDate")
            age = calculate_age_days(created, reference_time=now)
            if age is not None:
                ages.append(age)

        if not ages:
            return {
                "median_age_days": None,
                "p85_age_days": None,
                "p95_age_days": None,
                "sample_size": 0,
                "ages_distribution": {"0-7_days": 0, "8-30_days": 0, "31-90_days": 0, "90+_days": 0},
            }

        return {
            "median_age_days": round(calculate_percentile(ages, 50), 1),
            "p85_age_days": round(calculate_percentile(ages, 85), 1),
            "p95_age_days": round(calculate_percentile(ages, 95), 1),
            "sample_size": len(ages),
            "ages_distribution": {
                "0-7_days": sum(1 for age in ages if age <= 7),
                "8-30_days": sum(1 for age in ages if 7 < age <= 30),
                "31-90_days": sum(1 for age in ages if 30 < age <= 90),
                "90+_days": sum(1 for age in ages if age > 90),
            },
        }

    def _calculate_mttr(self, all_bugs: list[dict]) -> dict:
        """Calculate Mean Time To Repair."""
        repair_times = []

        for bug in all_bugs:
            created_date = bug.get("System.CreatedDate")
            closed_date = bug.get("Microsoft.VSTS.Common.ClosedDate")

            repair_time = calculate_lead_time_days(created_date, closed_date)
            if repair_time is not None:
                repair_times.append(repair_time)

        if not repair_times:
            return {
                "mttr_days": None,
                "median_mttr_days": None,
                "p85_mttr_days": None,
                "p95_mttr_days": None,
                "sample_size": 0,
                "mttr_distribution": {"0-1_days": 0, "1-7_days": 0, "7-30_days": 0, "30+_days": 0},
            }

        mean_mttr = sum(repair_times) / len(repair_times)

        return {
            "mttr_days": round(mean_mttr, 1),
            "median_mttr_days": round(calculate_percentile(repair_times, 50), 1),
            "p85_mttr_days": round(calculate_percentile(repair_times, 85), 1),
            "p95_mttr_days": round(calculate_percentile(repair_times, 95), 1),
            "sample_size": len(repair_times),
            "mttr_distribution": {
                "0-1_days": sum(1 for t in repair_times if t <= 1),
                "1-7_days": sum(1 for t in repair_times if 1 < t <= 7),
                "7-30_days": sum(1 for t in repair_times if 7 < t <= 30),
                "30+_days": sum(1 for t in repair_times if t > 30),
            },
        }

    def save_metrics(self, metrics: list[dict]) -> bool:
        """
        Save quality metrics to history file.

        Args:
            metrics: List of project metrics

        Returns:
            True if saved successfully
        """
        from pathlib import Path

        from execution.utils_atomic_json import atomic_json_save, load_json_with_recovery

        output_file = ".tmp/observatory/quality_history.json"

        # Validate data
        if not metrics:
            print("Warning: No project data to save")
            return False

        total_bugs = sum(m.get("total_bugs_analyzed", 0) for m in metrics)
        total_open = sum(m.get("open_bugs_count", 0) for m in metrics)

        if total_bugs == 0 and total_open == 0:
            print("Warning: All projects returned zero bugs - likely collection failure")
            return False

        # Create output directory
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        # Load existing history
        history = load_json_with_recovery(output_file, default_value={"weeks": []})

        if not isinstance(history, dict) or "weeks" not in history:
            history = {"weeks": []}

        # Add new week entry
        week_metrics = {
            "week_date": datetime.now().strftime("%Y-%m-%d"),
            "week_number": datetime.now().isocalendar()[1],
            "projects": metrics,
            "config": self.config,
        }

        history["weeks"].append(week_metrics)

        # Keep only last 52 weeks
        history["weeks"] = history["weeks"][-52:]

        # Save
        try:
            atomic_json_save(history, output_file)
            print(f"\n✅ Quality metrics saved to: {output_file}")
            print(f"   History now contains {len(history['weeks'])} week(s)")
            return True
        except OSError as e:
            print(f"\n❌ Failed to save metrics: {e}")
            return False
