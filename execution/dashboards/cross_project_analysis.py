"""
Cross-Project Performance Dashboard - Enabled by Async REST API

Leverages 3-10x performance improvements to enable fast cross-project analysis:
- Side-by-side comparison of all projects
- Identify best/worst performers
- Distribution analysis for key metrics
- Outlier detection

Usage:
    from execution.dashboards.cross_project_analysis import generate_cross_project_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/cross_project.html')
    generate_cross_project_dashboard(output_path)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from execution.core import get_logger
from execution.dashboards.renderer import render_dashboard
from execution.framework import get_dashboard_framework

logger = get_logger(__name__)


class CrossProjectAnalyzer:
    """
    Cross-project performance analysis.

    Compares metrics across all projects to identify patterns,
    outliers, and improvement opportunities.
    """

    def __init__(self) -> None:
        """Initialize analyzer."""
        self.quality_file = Path(".tmp/observatory/quality_history.json")
        self.security_file = Path(".tmp/observatory/security_history.json")
        self.deployment_file = Path(".tmp/observatory/deployment_history.json")

    def generate(self, output_path: Path | None = None) -> str:
        """
        Generate cross-project dashboard HTML.

        Args:
            output_path: Optional path to write HTML file

        Returns:
            Generated HTML string
        """
        logger.info("Generating cross-project analysis dashboard")

        # Step 1: Load latest week data for all projects
        project_data = self._load_latest_project_data()

        # Step 2: Calculate rankings and distributions
        rankings = self._calculate_rankings(project_data)

        # Step 3: Identify outliers
        outliers = self._identify_outliers(project_data)

        # Step 4: Build dashboard context
        context = self._build_context(project_data, rankings, outliers)

        # Step 5: Render dashboard
        html = render_dashboard("dashboards/cross_project_dashboard.html", context)

        # Write to file if specified
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html, encoding="utf-8")
            logger.info("Cross-project dashboard written", extra={"path": str(output_path)})

        return html

    def _load_latest_project_data(self) -> dict[str, dict[str, Any]]:
        """Load latest week data for all projects"""
        logger.info("Loading latest project data")

        projects: dict[str, dict[str, Any]] = {}

        # Load quality data
        if self.quality_file.exists():
            with open(self.quality_file, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("weeks"):
                latest_week = data["weeks"][-1]
                for proj in latest_week.get("projects", []):
                    project_key = proj.get("project_key", "Unknown")
                    if project_key not in projects:
                        projects[project_key] = {"project_key": project_key, "project_name": proj.get("project_name")}

                    projects[project_key]["open_bugs"] = proj.get("open_bugs_count", 0)
                    projects[project_key]["priority_1_bugs"] = proj.get("priority_1_count", 0)
                    projects[project_key]["priority_2_bugs"] = proj.get("priority_2_count", 0)

        # Load deployment data
        if self.deployment_file.exists():
            with open(self.deployment_file, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("weeks"):
                latest_week = data["weeks"][-1]
                for proj in latest_week.get("projects", []):
                    project_key = proj.get("project_key", "Unknown")
                    if project_key in projects:
                        freq = proj.get("deployment_frequency", {})
                        projects[project_key]["deployments_per_week"] = freq.get("per_week", 0)
                        projects[project_key]["success_rate"] = proj.get("success_rate", 0)

        logger.info("Project data loaded", extra={"project_count": len(projects)})
        return projects

    def _calculate_rankings(self, project_data: dict[str, dict[str, Any]]) -> dict:
        """Calculate project rankings for key metrics"""
        logger.info("Calculating project rankings")

        # Sort projects by open bugs (ascending = better)
        projects_list = list(project_data.values())
        by_bugs = sorted(projects_list, key=lambda p: p.get("open_bugs", 0))
        by_deployments = sorted(projects_list, key=lambda p: p.get("deployments_per_week", 0), reverse=True)
        by_success_rate = sorted(projects_list, key=lambda p: p.get("success_rate", 0), reverse=True)

        return {
            "best_quality": by_bugs[:3] if len(by_bugs) >= 3 else by_bugs,
            "worst_quality": list(reversed(by_bugs[-3:])) if len(by_bugs) >= 3 else list(reversed(by_bugs)),
            "best_deployment": by_deployments[:3] if len(by_deployments) >= 3 else by_deployments,
            "best_reliability": by_success_rate[:3] if len(by_success_rate) >= 3 else by_success_rate,
        }

    def _identify_outliers(self, project_data: dict[str, dict[str, Any]]) -> dict:
        """Identify statistical outliers"""
        logger.info("Identifying outliers")

        projects_list = list(project_data.values())
        if not projects_list:
            return {}

        # Calculate mean and std dev for open bugs
        bug_counts = [p.get("open_bugs", 0) for p in projects_list]
        if not bug_counts:
            return {}

        import statistics

        mean_bugs = statistics.mean(bug_counts)
        std_bugs = statistics.stdev(bug_counts) if len(bug_counts) > 1 else 0

        outliers = []
        for project in projects_list:
            bugs = project.get("open_bugs", 0)
            if std_bugs > 0:
                z_score = (bugs - mean_bugs) / std_bugs
                if abs(z_score) > 2.0:  # More than 2 standard deviations
                    outliers.append(
                        {
                            "project_key": project["project_key"],
                            "project_name": project.get("project_name", "Unknown"),
                            "open_bugs": bugs,
                            "z_score": round(z_score, 2),
                            "severity": "high" if abs(z_score) > 3.0 else "medium",
                        }
                    )

        logger.info("Outliers identified", extra={"outlier_count": len(outliers)})
        return {"bug_count_outliers": outliers, "mean_bugs": round(mean_bugs, 1), "std_dev": round(std_bugs, 1)}

    def _build_context(self, project_data: dict[str, dict[str, Any]], rankings: dict, outliers: dict) -> dict[str, Any]:
        """Build template context"""
        # Get framework
        framework_css, framework_js = get_dashboard_framework(
            header_gradient_start="#06b6d4", header_gradient_end="#0891b2", include_table_scroll=True
        )

        # Convert project data to list for table
        projects_list = sorted(project_data.values(), key=lambda p: p.get("open_bugs", 0))

        return {
            "framework_css": framework_css,
            "framework_js": framework_js,
            "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "project_count": len(project_data),
            "projects": projects_list,
            "rankings": rankings,
            "outliers": outliers,
        }


def generate_cross_project_dashboard(output_path: Path | None = None) -> str:
    """
    Generate cross-project performance dashboard.

    Args:
        output_path: Optional output path (defaults to .tmp/observatory/dashboards/cross_project.html)

    Returns:
        Generated HTML string
    """
    if output_path is None:
        output_path = Path(".tmp/observatory/dashboards/cross_project.html")

    analyzer = CrossProjectAnalyzer()
    return analyzer.generate(output_path)


# Self-test
if __name__ == "__main__":
    logger.info("Cross-Project Dashboard Generator - Self Test")

    try:
        output_path = Path(".tmp/observatory/dashboards/cross_project.html")
        html = generate_cross_project_dashboard(output_path)

        logger.info(
            "Cross-project dashboard generated successfully",
            extra={"output": str(output_path), "html_size": len(html)},
        )

    except Exception as e:
        logger.error("Failed to generate cross-project dashboard", exc_info=True)
        exit(1)
