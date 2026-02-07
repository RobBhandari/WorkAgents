"""
Azure DevOps DOE Tracker

Calculates weekly metrics, burn-down math, and status indicators for the DOE Operating Charter.
Tracks progress toward the 30% bug reduction target.

Usage:
    python ado_doe_tracker.py
    python ado_doe_tracker.py --week-number 5
    python ado_doe_tracker.py --output-format json
    python ado_doe_tracker.py --output-file custom_report.json
"""

import os
import sys
import argparse
import logging
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Azure DevOps SDK
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication

# Security utilities for input validation
from security_utils import WIQLValidator, ValidationError

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'.tmp/ado_doe_tracker_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Status thresholds
STATUS_AMBER_THRESHOLD = 1.10  # Actual <= Expected × 1.10
STATUS_EMOJIS = {
    'GREEN': '🟢',
    'AMBER': '🟠',
    'RED': '🔴'
}


def load_baseline(project_key: str = None) -> dict:
    """
    Load baseline data from file.

    Args:
        project_key: Project key for multi-project tracking (if None, uses legacy baseline.json)

    Returns:
        dict: Baseline data

    Raises:
        FileNotFoundError: If baseline file doesn't exist
        ValueError: If baseline data is invalid
    """
    if project_key:
        baseline_file = f'.tmp/baseline_{project_key}.json'
    else:
        baseline_file = '.tmp/baseline.json'

    if not os.path.exists(baseline_file):
        raise FileNotFoundError(
            f"Baseline not found: {baseline_file}\n"
            f"Please run: python execution/ado_baseline.py" +
            (f" --project-key {project_key}" if project_key else "")
        )

    logger.info(f"Loading baseline from {baseline_file}")

    with open(baseline_file, 'r', encoding='utf-8') as f:
        baseline = json.load(f)

    # Validate baseline
    required_fields = ['baseline_date', 'open_count', 'target_count', 'required_weekly_burn', 'weeks_to_target']
    for field in required_fields:
        if field not in baseline:
            raise ValueError(f"Invalid baseline: missing field '{field}'")

    logger.info(f"Baseline loaded: {baseline['open_count']} bugs on {baseline['baseline_date']}")
    return baseline


def load_weekly_tracking(project_key: str = None) -> dict:
    """
    Load historical weekly tracking data.

    Args:
        project_key: Project key for multi-project tracking (if None, uses legacy weekly_tracking.json)

    Returns:
        dict: Weekly tracking data (or empty structure if file doesn't exist)
    """
    if project_key:
        tracking_file = f'.tmp/weekly_tracking_{project_key}.json'
    else:
        tracking_file = '.tmp/weekly_tracking.json'

    if not os.path.exists(tracking_file):
        logger.info("No previous weekly tracking data found, starting fresh")
        return {"weeks": []}

    logger.info(f"Loading weekly tracking from {tracking_file}")

    with open(tracking_file, 'r', encoding='utf-8') as f:
        tracking = json.load(f)

    logger.info(f"Loaded {len(tracking.get('weeks', []))} previous weeks")
    return tracking


def save_weekly_tracking(tracking: dict, project_key: str = None):
    """
    Save weekly tracking data to file.

    Args:
        tracking: Weekly tracking data
        project_key: Project key for multi-project tracking (if None, uses legacy weekly_tracking.json)
    """
    if project_key:
        tracking_file = f'.tmp/weekly_tracking_{project_key}.json'
    else:
        tracking_file = '.tmp/weekly_tracking.json'

    os.makedirs('.tmp', exist_ok=True)

    with open(tracking_file, 'w', encoding='utf-8') as f:
        json.dump(tracking, f, indent=2, ensure_ascii=False)

    logger.info(f"Weekly tracking saved to {tracking_file}")


def query_current_bugs(organization_url: str, project_name: str, pat: str) -> int:
    """
    Query current count of open bugs in ADO.

    Args:
        organization_url: ADO organization URL
        project_name: Project name in ADO
        pat: Personal Access Token

    Returns:
        int: Count of currently open bugs
    """
    try:
        # Step 1: Authenticate with ADO
        credentials = BasicAuthentication('', pat)
        connection = Connection(base_url=organization_url, creds=credentials)
        wit_client = connection.clients.get_work_item_tracking_client()
        logger.info("Successfully connected to Azure DevOps")

        # Step 2: Query for currently open bugs
        # Validate input to prevent WIQL injection
        safe_project = WIQLValidator.validate_project_name(project_name)

        wiql_query = WIQLValidator.build_safe_wiql(
            """SELECT [System.Id]
            FROM WorkItems
            WHERE [System.TeamProject] = '{project}'
            AND [System.WorkItemType] = '{work_type}'
            AND [System.State] <> '{state}'
            ORDER BY [System.Id] ASC""",
            project=safe_project,
            work_type='Bug',
            state='Closed'
        )

        logger.info("Querying current open bugs...")
        wiql_results = wit_client.query_by_wiql(wiql={'query': wiql_query})

        if not wiql_results.work_items:
            logger.info("No open bugs found")
            return 0

        bug_count = len(wiql_results.work_items)
        logger.info(f"Found {bug_count} currently open bugs")
        return bug_count

    except Exception as e:
        logger.error(f"Error querying bugs: {e}", exc_info=True)
        raise RuntimeError(f"Failed to query current bugs: {e}") from e


def query_bugs_by_date_range(organization_url: str, project_name: str, pat: str,
                              start_date: str, end_date: str, query_type: str) -> int:
    """
    Query bugs created or closed within a date range.

    Args:
        organization_url: ADO organization URL
        project_name: Project name in ADO
        pat: Personal Access Token
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        query_type: 'created' or 'closed'

    Returns:
        int: Count of bugs matching criteria
    """
    try:
        credentials = BasicAuthentication('', pat)
        connection = Connection(base_url=organization_url, creds=credentials)
        wit_client = connection.clients.get_work_item_tracking_client()

        if query_type == 'created':
            # Query bugs created in date range
            wiql_query = f"""
            SELECT [System.Id]
            FROM WorkItems
            WHERE [System.TeamProject] = '{project_name}'
            AND [System.WorkItemType] = 'Bug'
            AND [System.CreatedDate] >= '{start_date}'
            AND [System.CreatedDate] < '{end_date}'
            """
        elif query_type == 'closed':
            # Query bugs closed in date range
            wiql_query = f"""
            SELECT [System.Id]
            FROM WorkItems
            WHERE [System.TeamProject] = '{project_name}'
            AND [System.WorkItemType] = 'Bug'
            AND [System.State] = 'Closed'
            AND [Microsoft.VSTS.Common.ClosedDate] >= '{start_date}'
            AND [Microsoft.VSTS.Common.ClosedDate] < '{end_date}'
            """
        else:
            raise ValueError(f"Invalid query_type: {query_type}")

        logger.info(f"Querying bugs {query_type} between {start_date} and {end_date}...")
        wiql_results = wit_client.query_by_wiql(wiql={'query': wiql_query})

        if not wiql_results.work_items:
            return 0

        return len(wiql_results.work_items)

    except Exception as e:
        logger.error(f"Error querying bugs by date: {e}", exc_info=True)
        raise RuntimeError(f"Failed to query bugs by date: {e}") from e


def calculate_week_dates(baseline_date: str, week_number: int) -> tuple[str, str]:
    """
    Calculate week start and end dates for a given week number.

    Args:
        baseline_date: Baseline date (YYYY-MM-DD)
        week_number: Week number (1, 2, 3, ...)

    Returns:
        tuple: (week_start_date, week_end_date) as YYYY-MM-DD strings
    """
    baseline = datetime.strptime(baseline_date, "%Y-%m-%d")
    week_start = baseline + timedelta(weeks=week_number - 1)
    week_end = week_start + timedelta(weeks=1)

    return week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")


def calculate_current_week(baseline_date: str) -> int:
    """
    Calculate current week number based on baseline date.

    Args:
        baseline_date: Baseline date (YYYY-MM-DD)

    Returns:
        int: Current week number (1, 2, 3, ...)
    """
    baseline = datetime.strptime(baseline_date, "%Y-%m-%d")
    today = datetime.now()
    days_elapsed = (today - baseline).days
    week_number = max(1, (days_elapsed // 7) + 1)

    return week_number


def determine_status(actual: int, expected: int) -> str:
    """
    Determine status based on actual vs expected values.

    Args:
        actual: Actual open bug count
        expected: Expected open bug count

    Returns:
        str: Status ('GREEN', 'AMBER', or 'RED')
    """
    if actual <= expected:
        return 'GREEN'
    elif actual <= expected * STATUS_AMBER_THRESHOLD:
        return 'AMBER'
    else:
        return 'RED'


def calculate_doe_metrics(organization_url: str, project_name: str, pat: str,
                          week_number: int = None, project_key: str = None) -> dict:
    """
    Calculate DOE metrics for the current or specified week.

    Args:
        organization_url: ADO organization URL
        project_name: Project name in ADO
        pat: Personal Access Token
        week_number: Override week number (default: auto-calculate)
        project_key: Project key for multi-project tracking

    Returns:
        dict: DOE metrics report
    """
    # Load baseline
    baseline = load_baseline(project_key)

    # Load previous tracking data
    tracking = load_weekly_tracking(project_key)
    previous_weeks = tracking.get('weeks', [])

    # Determine week number
    if week_number is None:
        week_number = calculate_current_week(baseline['baseline_date'])
    logger.info(f"Calculating metrics for Week {week_number}")

    # Calculate week dates
    week_start, week_end = calculate_week_dates(baseline['baseline_date'], week_number)
    logger.info(f"Week {week_number}: {week_start} to {week_end}")

    # Query current open bugs
    current_open = query_current_bugs(organization_url, project_name, pat)

    # Get previous week's open count (for new/closed calculation)
    previous_open = baseline['open_count'] if len(previous_weeks) == 0 else previous_weeks[-1]['open']

    # Query bugs created this week
    new_bugs = query_bugs_by_date_range(organization_url, project_name, pat, week_start, week_end, 'created')

    # Query bugs closed this week
    closed_bugs = query_bugs_by_date_range(organization_url, project_name, pat, week_start, week_end, 'closed')

    # Calculate net burn
    net_burn = closed_bugs - new_bugs

    # Calculate expected open count
    weeks_elapsed = week_number
    expected_reduction = baseline['required_weekly_burn'] * weeks_elapsed
    expected_open = max(baseline['target_count'], int(baseline['open_count'] - expected_reduction))

    # Calculate delta
    delta = current_open - expected_open

    # Determine status
    status = determine_status(current_open, expected_open)

    # Calculate weeks remaining
    weeks_remaining = baseline['weeks_to_target'] - week_number

    # Calculate dynamic required burn (what's needed NOW to hit target from current position)
    dynamic_required_burn = (current_open - baseline['target_count']) / weeks_remaining if weeks_remaining > 0 else 0

    # Build metrics report
    report = {
        'week_number': week_number,
        'week_start': week_start,
        'week_end': week_end,
        'project': {
            'name': project_name,
            'key': project_key if project_key else project_name.replace(' ', '_').replace('-', '_')
        },
        'baseline': {
            'date': baseline['baseline_date'],
            'count': baseline['open_count'],
            'target': baseline['target_count'],
            'required_burn': baseline['required_weekly_burn']
        },
        'current': {
            'open': current_open,
            'new': new_bugs,
            'closed': closed_bugs,
            'net_burn': net_burn,
            'required_burn': round(dynamic_required_burn, 2)
        },
        'expected': {
            'open': expected_open,
            'delta': delta
        },
        'status': {
            'indicator': status,
            'emoji': STATUS_EMOJIS[status]
        },
        'timeline': {
            'weeks_elapsed': week_number,
            'weeks_remaining': weeks_remaining,
            'target_date': baseline['target_date']
        },
        'calculated_at': datetime.now().isoformat()
    }

    # Save this week's data to tracking
    week_data = {
        'week_number': week_number,
        'week_date': week_end,
        'open': current_open,
        'new': new_bugs,
        'closed': closed_bugs,
        'net_burn': net_burn,
        'expected': expected_open,
        'status': status,
        'delta': delta,
        'required_burn': round(dynamic_required_burn, 2)
    }

    # Update tracking data (replace if week already exists, otherwise append)
    updated = False
    for i, week in enumerate(previous_weeks):
        if week['week_number'] == week_number:
            previous_weeks[i] = week_data
            updated = True
            break

    if not updated:
        previous_weeks.append(week_data)

    tracking['weeks'] = previous_weeks
    save_weekly_tracking(tracking, project_key)

    logger.info(f"Week {week_number} metrics calculated successfully")
    return report


def format_report_text(report: dict) -> str:
    """
    Format report as human-readable text.

    Args:
        report: DOE metrics report

    Returns:
        str: Formatted text report
    """
    status_emoji = report['status']['emoji']
    status_name = report['status']['indicator']

    output = []
    output.append("=" * 60)
    output.append(f"DOE Bug Tracker - Week {report['week_number']}")
    output.append("=" * 60)
    output.append("")
    output.append("Weekly Summary")
    output.append("=" * 60)
    output.append(f"Starting (Week 0):     {report['baseline']['count']}")
    output.append(f"Target (30%):          {report['baseline']['target']}")
    output.append(f"Expected this week:    {report['expected']['open']}")
    output.append(f"Actual:                {report['current']['open']} {status_emoji}")
    output.append("")
    output.append(f"New: {report['current']['new']} | Closed: {report['current']['closed']} | Net burn: {report['current']['net_burn']:+d}")
    output.append(f"Required burn: +{report['current']['required_burn']:.2f}")
    output.append("")
    output.append(f"Status: {status_name} ({status_emoji})")
    output.append(f"Weeks remaining: {report['timeline']['weeks_remaining']}")
    output.append(f"Target date: {report['timeline']['target_date']}")
    output.append("")
    output.append("=" * 60)

    return "\n".join(output)


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Calculate DOE metrics and track progress toward bug reduction target'
    )

    parser.add_argument(
        '--week-number',
        type=int,
        help='Override week number (default: auto-calculate from baseline date)'
    )

    parser.add_argument(
        '--output-format',
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)'
    )

    parser.add_argument(
        '--output-file',
        help='Save report to file (in addition to console output)'
    )

    parser.add_argument(
        '--project',
        type=str,
        help='ADO project name (overrides ADO_PROJECT_NAME from .env)'
    )

    parser.add_argument(
        '--project-key',
        type=str,
        help='Project key for multi-project tracking (defaults to sanitized project name)'
    )

    return parser.parse_args()


if __name__ == '__main__':
    """
    Entry point when script is run from command line.
    """
    try:
        # Fix encoding for Windows console
        import io
        if sys.stdout.encoding != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

        # Parse command-line arguments
        args = parse_arguments()

        # Load configuration from environment
        organization_url = os.getenv('ADO_ORGANIZATION_URL')
        project_name = args.project if args.project else os.getenv('ADO_PROJECT_NAME')
        pat = os.getenv('ADO_PAT')

        # Validate environment variables
        if not organization_url or organization_url == 'your_ado_org_url_here':
            raise RuntimeError(
                "ADO_ORGANIZATION_URL not configured in .env file.\n"
                "Please set your Azure DevOps organization URL"
            )

        if not project_name or project_name == 'your_project_name_here':
            raise RuntimeError(
                "ADO_PROJECT_NAME not configured in .env file (or provide --project).\n"
                "Please set your Azure DevOps project name"
            )

        if not pat or pat == 'your_personal_access_token_here':
            raise RuntimeError(
                "ADO_PAT not configured in .env file.\n"
                "Please create a Personal Access Token"
            )

        # Calculate DOE metrics
        # Use project_key from args, or derive from project_name
        project_key = args.project_key
        if project_key is None and project_name:
            project_key = project_name.replace(' ', '_').replace('-', '_')

        report = calculate_doe_metrics(
            organization_url=organization_url,
            project_name=project_name,
            pat=pat,
            week_number=args.week_number,
            project_key=project_key
        )

        # Output report
        if args.output_format == 'json':
            output = json.dumps(report, indent=2)
        else:
            output = format_report_text(report)

        print(output)

        # Save to file if requested
        if args.output_file:
            with open(args.output_file, 'w', encoding='utf-8') as f:
                f.write(output)
            logger.info(f"Report saved to {args.output_file}")

        # Exit with success code
        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
