"""
Azure DevOps DOE Baseline Creator

Creates an immutable Week 0 baseline snapshot of bugs open on January 1, 2026.
This baseline is used to track progress toward the 30% reduction target by June 30, 2026.

Usage:
    python ado_baseline.py
    python ado_baseline.py --force  # Overwrite existing baseline (use with caution)
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

# Azure DevOps SDK
from azure.devops.connection import Connection
from dotenv import load_dotenv
from msrest.authentication import BasicAuthentication

# Security utilities for input validation
from security_utils import WIQLValidator

from execution.core import get_config

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'.tmp/ado_baseline_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Constants
BASELINE_DATE = "2026-01-01"
TARGET_DATE = "2026-06-30"
TARGET_PERCENTAGE = 0.30


def calculate_weeks_between(start_date_str: str, end_date_str: str) -> int:
    """Calculate number of weeks between two dates."""
    start = datetime.strptime(start_date_str, "%Y-%m-%d")
    end = datetime.strptime(end_date_str, "%Y-%m-%d")
    days = (end - start).days
    return days // 7


def create_baseline(
    organization_url: str, project_name: str, pat: str, force: bool = False, project_key: str = None
) -> dict:
    """
    Create baseline snapshot of bugs open on January 1, 2026.

    Args:
        organization_url: ADO organization URL
        project_name: Project name in ADO
        pat: Personal Access Token
        force: If True, overwrite existing baseline
        project_key: Optional key for multi-project tracking (defaults to sanitized project_name)

    Returns:
        dict: Baseline data

    Raises:
        ValueError: If baseline already exists and force=False
        RuntimeError: If baseline creation fails
    """
    # Use project_key for filename, or sanitize project_name
    if project_key is None:
        project_key = project_name.replace(" ", "_").replace("-", "_")

    baseline_file = f".tmp/baseline_{project_key}.json"

    # Check if baseline already exists
    if os.path.exists(baseline_file) and not force:
        logger.error(f"Baseline already exists at {baseline_file}")
        raise ValueError(
            f"Baseline already exists and is immutable.\n"
            f"File: {baseline_file}\n"
            f"Use --force to overwrite (NOT RECOMMENDED)"
        )

    logger.info(f"Creating baseline for bugs open on {BASELINE_DATE}")

    try:
        # Step 1: Authenticate with ADO
        credentials = BasicAuthentication("", pat)
        connection = Connection(base_url=organization_url, creds=credentials)
        wit_client = connection.clients.get_work_item_tracking_client()
        logger.info("Successfully connected to Azure DevOps")

        # Step 2: Build WIQL query for bugs open on baseline date
        # Bugs open on 2026-01-01 means:
        # - Created BEFORE 2026-01-01 (not on that day, as we want bugs at start of day)
        # - AND (Currently not closed OR closed ON/AFTER 2026-01-01)

        # Validate inputs to prevent WIQL injection
        safe_project = WIQLValidator.validate_project_name(project_name)
        safe_baseline_date = WIQLValidator.validate_date_iso8601(BASELINE_DATE)

        wiql_query = WIQLValidator.build_safe_wiql(
            """SELECT [System.Id], [System.Title], [System.State], [Microsoft.VSTS.Common.Priority]
            FROM WorkItems
            WHERE [System.TeamProject] = '{project}'
            AND [System.WorkItemType] = '{work_type}'
            AND [System.CreatedDate] < '{baseline_date}'
            AND (
                [System.State] <> '{closed_state}'
                OR [Microsoft.VSTS.Common.ClosedDate] >= '{baseline_date}'
            )
            ORDER BY [System.Id] ASC""",
            project=safe_project,
            work_type="Bug",
            baseline_date=safe_baseline_date,
            closed_state="Closed",
        )

        # Step 3: Execute WIQL query
        logger.info(f"Executing WIQL query for bugs open on {BASELINE_DATE}...")
        wiql_results = wit_client.query_by_wiql(wiql={"query": wiql_query})  # nosec B608 - Input validated by WIQLValidator.build_safe_wiql()

        if not wiql_results.work_items:
            logger.warning("No bugs found for baseline date")
            baseline_count = 0
            bugs = []
        else:
            work_item_ids = [item.id for item in wiql_results.work_items]
            logger.info(f"Found {len(work_item_ids)} bugs open on {BASELINE_DATE}")

            # Step 4: Fetch full work item details in batches
            logger.info("Fetching bug details...")
            bugs = []
            batch_size = 200

            for i in range(0, len(work_item_ids), batch_size):
                batch_ids = work_item_ids[i : i + batch_size]
                logger.info(
                    f"Fetching batch {i//batch_size + 1}/{(len(work_item_ids) + batch_size - 1)//batch_size} ({len(batch_ids)} items)..."
                )

                work_items = wit_client.get_work_items(
                    ids=batch_ids,
                    fields=[
                        "System.Id",
                        "System.Title",
                        "System.State",
                        "Microsoft.VSTS.Common.Priority",
                        "System.CreatedDate",
                    ],
                )

                for item in work_items:
                    bug_data = {
                        "id": item.id,
                        "title": item.fields.get("System.Title", "N/A"),
                        "state": item.fields.get("System.State", "N/A"),
                        "priority": item.fields.get("Microsoft.VSTS.Common.Priority", "N/A"),
                        "created_date": str(item.fields.get("System.CreatedDate", "")),
                    }
                    bugs.append(bug_data)

            baseline_count = len(bugs)

        # Step 5: Calculate baseline metrics
        target_count = int(baseline_count * TARGET_PERCENTAGE)
        weeks_to_target = calculate_weeks_between(BASELINE_DATE, TARGET_DATE)
        required_weekly_burn = (baseline_count - target_count) / weeks_to_target if weeks_to_target > 0 else 0

        # Step 6: Create baseline data structure
        baseline = {
            "baseline_date": BASELINE_DATE,
            "baseline_week": 0,
            "open_count": baseline_count,
            "target_count": target_count,
            "target_date": TARGET_DATE,
            "target_percentage": TARGET_PERCENTAGE,
            "weeks_to_target": weeks_to_target,
            "required_weekly_burn": round(required_weekly_burn, 2),
            "immutable": True,
            "created_at": datetime.now().isoformat(),
            "project": project_name,
            "project_key": project_key,
            "organization": organization_url,
            "bugs": bugs,
        }

        # Step 7: Save baseline to file
        os.makedirs(".tmp", exist_ok=True)
        with open(baseline_file, "w", encoding="utf-8") as f:
            json.dump(baseline, f, indent=2, ensure_ascii=False)

        logger.info(f"Baseline created successfully: {baseline_file}")
        return baseline

    except Exception as e:
        logger.error(f"Error creating baseline: {e}", exc_info=True)
        raise RuntimeError(f"Failed to create baseline: {e}") from e


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Create immutable DOE baseline snapshot for January 1, 2026")

    parser.add_argument("--force", action="store_true", help="Force overwrite of existing baseline (NOT RECOMMENDED)")

    parser.add_argument("--project", type=str, help="ADO project name (overrides ADO_PROJECT_NAME from .env)")

    parser.add_argument(
        "--project-key", type=str, help="Project key for multi-project tracking (defaults to sanitized project name)"
    )

    return parser.parse_args()


if __name__ == "__main__":
    """
    Entry point when script is run from command line.
    """
    try:
        # Parse command-line arguments
        args = parse_arguments()

        # Load configuration from environment
        organization_url = get_config().get("ADO_ORGANIZATION_URL")
        project_name = args.project if args.project else get_config().get("ADO_PROJECT_NAME")
        pat = get_config().get_ado_config().pat

        # Validate environment variables
        if not organization_url or organization_url == "your_ado_org_url_here":
            raise RuntimeError(
                "ADO_ORGANIZATION_URL not configured in .env file.\n" "Please set your Azure DevOps organization URL"
            )

        if not project_name or project_name == "your_project_name_here":
            raise RuntimeError(
                "ADO_PROJECT_NAME not configured in .env file (or provide --project).\n"
                "Please set your Azure DevOps project name"
            )

        if not pat or pat == "your_personal_access_token_here":
            raise RuntimeError("ADO_PAT not configured in .env file.\n" "Please create a Personal Access Token")

        # Create baseline
        baseline = create_baseline(
            organization_url=organization_url,
            project_name=project_name,
            pat=pat,
            force=args.force,
            project_key=args.project_key,
        )

        # Print summary
        print(f"\n{'='*60}")
        print("DOE Baseline Created")
        print(f"{'='*60}")
        print(f"Baseline Date: {baseline['baseline_date']}")
        print(f"Open Bugs on {baseline['baseline_date']}: {baseline['open_count']}")
        print(f"Target (30%): {baseline['target_count']}")
        print(f"Target Date: {baseline['target_date']}")
        print(f"Weeks to Target: {baseline['weeks_to_target']}")
        print(f"Required Weekly Burn: +{baseline['required_weekly_burn']:.2f}")
        print("\nBaseline saved to: .tmp/baseline.json")
        print(f"{'='*60}\n")

        # Exit with success code
        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
