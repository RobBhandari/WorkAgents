"""
Send Multi-Project DOE Report Email

Sends weekly DOE bug tracking report for multiple projects via Gmail SMTP.
Formats the report as a table sorted by RAG status.

Usage:
    python send_multi_project_report.py
    python send_multi_project_report.py --recipient alternate@email.com
    python send_multi_project_report.py --dry-run
    python send_multi_project_report.py --projects ALCM ProjectB ProjectC
"""

import argparse
import glob
import json
import logging
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'.tmp/send_multi_project_report_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Default recipient
DEFAULT_RECIPIENT = "robin.bhandari@theaccessgroup.com"

# Status colors for HTML (softer, gradient-friendly tones)
STATUS_COLORS = {"GREEN": "#10b981", "AMBER": "#f59e0b", "RED": "#f87171"}

# Status sort order
STATUS_ORDER = {"GREEN": 0, "AMBER": 1, "RED": 2}


def discover_projects() -> list[str]:
    """
    Discover all projects by finding baseline files.

    Returns:
        list: List of project keys
    """
    baseline_files = glob.glob(".tmp/baseline_*.json")
    project_keys = []

    for file in baseline_files:
        # Extract project key from filename: baseline_<project_key>.json
        project_key = os.path.basename(file).replace("baseline_", "").replace(".json", "")
        project_keys.append(project_key)

    logger.info(f"Discovered {len(project_keys)} projects: {', '.join(project_keys)}")
    return project_keys


def load_project_data(project_key: str) -> dict:
    """
    Load baseline and latest weekly tracking for a project.

    Args:
        project_key: Project key

    Returns:
        dict: Combined project data with baseline and latest week

    Raises:
        FileNotFoundError: If baseline or tracking file doesn't exist
    """
    baseline_file = f".tmp/baseline_{project_key}.json"
    tracking_file = f".tmp/weekly_tracking_{project_key}.json"

    if not os.path.exists(baseline_file):
        raise FileNotFoundError(f"Baseline not found for project '{project_key}': {baseline_file}")

    if not os.path.exists(tracking_file):
        raise FileNotFoundError(f"Weekly tracking not found for project '{project_key}': {tracking_file}")

    logger.info(f"Loading data for project '{project_key}'")

    with open(baseline_file, encoding="utf-8") as f:
        baseline = json.load(f)

    with open(tracking_file, encoding="utf-8") as f:
        tracking = json.load(f)

    weeks = tracking.get("weeks", [])
    if not weeks:
        raise ValueError(f"No weekly data found for project '{project_key}'")

    latest_week = weeks[-1]

    return {
        "project_key": project_key,
        "project_name": baseline.get("project", project_key),
        "baseline": baseline,
        "latest_week": latest_week,
        "week_number": latest_week["week_number"],
        "weeks_remaining": baseline["weeks_to_target"] - latest_week["week_number"],
    }


def load_all_projects(project_keys: list[str] = None) -> list[dict]:
    """
    Load data for all projects.

    Args:
        project_keys: Optional list of specific project keys to load

    Returns:
        list: List of project data dictionaries
    """
    if project_keys is None:
        project_keys = discover_projects()

    projects = []
    for project_key in project_keys:
        try:
            project_data = load_project_data(project_key)
            projects.append(project_data)
        except Exception as e:
            logger.warning(f"Failed to load project '{project_key}': {e}")

    return projects


def sort_projects_by_status(projects: list[dict]) -> list[dict]:
    """
    Sort projects by RAG status (GREEN, AMBER, RED).

    Args:
        projects: List of project data

    Returns:
        list: Sorted list of projects
    """

    def get_sort_key(project):
        status = project["latest_week"]["status"]
        return STATUS_ORDER.get(status, 99)

    return sorted(projects, key=get_sort_key)


def format_email_body_text(projects: list[dict]) -> str:
    """
    Format email body as plain text table.

    Args:
        projects: List of project data (already sorted)

    Returns:
        str: Plain text email body
    """
    # Sort projects by status
    projects = sort_projects_by_status(projects)

    # Calculate week number (should be same for all projects)
    week_number = projects[0]["week_number"] if projects else 0

    body = f"""Bug Position Report - Week {week_number}
Generated: {datetime.now().strftime('%B %d, %Y')}

"""

    # Table header
    body += f"{'Project':<20} {'Status':<8} {'Dec 2025':<9} {'Target':<11} {'Current':<8} {'Expected':<9} {'Net Burn':<9} {'Required':<9}\n"
    body += f"{'':20} {'':8} {'':9} {'Jun 2026':<11} {'Bugs':<8} {'Bugs':<9} {'This Week':<9} {'Burn/Week':<9}\n"
    body += "─" * 100 + "\n"

    # Table rows
    for project in projects:
        week = project["latest_week"]
        baseline = project["baseline"]

        # Status indicator (using text for plain email)
        status_map = {"GREEN": "[G]", "AMBER": "[A]", "RED": "[R]"}
        status_text = status_map.get(week["status"], "[?]")

        body += f"{project['project_name']:<20} {status_text:<8} {baseline['open_count']:<9} {baseline['target_count']:<7} {week['open']:<8} {week['expected']:<9} {week['net_burn']:+9} {week['required_burn']:+9.2f}\n"

    body += "─" * 100 + "\n"
    body += f"\nWeeks remaining until target date: {project['weeks_remaining']} ({baseline['target_date']})\n"

    return body


def format_email_body_html(projects: list[dict]) -> str:
    """
    Format email body as HTML table with colored status rectangles.

    Args:
        projects: List of project data (already sorted)

    Returns:
        str: HTML email body
    """
    # Sort projects by status
    projects = sort_projects_by_status(projects)

    # Calculate week number (should be same for all projects)
    week_number = projects[0]["week_number"] if projects else 0
    weeks_remaining = projects[0]["weeks_remaining"] if projects else 0
    target_date = projects[0]["baseline"]["target_date"] if projects else ""

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif; background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%);">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 0; padding: 15px;">
        <tr>
            <td align="center">
                <table role="presentation" width="1050" cellspacing="0" cellpadding="0" border="0" style="background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden;">

                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #1e40af 0%, #1e3a8a 100%); padding: 20px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 26px; font-weight: 700; letter-spacing: -0.5px; text-shadow: 0 2px 8px rgba(0,0,0,0.2);">Bug Position Report</h1>
                            <p style="margin: 6px 0 0 0; color: rgba(255,255,255,0.95); font-size: 15px; font-weight: 500;">Week {week_number} • {datetime.now().strftime('%B %d, %Y')}</p>
                        </td>
                    </tr>

                    <!-- Table -->
                    <tr>
                        <td style="padding: 20px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse: collapse; border-radius: 8px; overflow: hidden;">

                                <!-- Table Header -->
                                <thead>
                                <tr style="background-color: #1e40af;">
                                    <th style="padding: 14px 10px; text-align: left; font-size: 11px; font-weight: 700; color: #ffffff; text-transform: uppercase; letter-spacing: 1px; border-right: 1px solid rgba(255,255,255,0.2); border-bottom: 3px solid #1e3a8a;">PROJECT</th>
                                    <th style="padding: 14px 10px; text-align: center; font-size: 11px; font-weight: 700; color: #ffffff; text-transform: uppercase; letter-spacing: 1px; border-right: 1px solid rgba(255,255,255,0.2); border-bottom: 3px solid #1e3a8a; width: 60px;">STATUS</th>
                                    <th style="padding: 14px 10px; text-align: right; font-size: 11px; font-weight: 700; color: #ffffff; text-transform: uppercase; letter-spacing: 1px; border-right: 1px solid rgba(255,255,255,0.2); border-bottom: 3px solid #1e3a8a;">DEC 2025</th>
                                    <th style="padding: 14px 10px; text-align: right; font-size: 11px; font-weight: 700; color: #ffffff; text-transform: uppercase; letter-spacing: 1px; border-right: 1px solid rgba(255,255,255,0.2); border-bottom: 3px solid #1e3a8a;">TARGET<br/>JUN 2026</th>
                                    <th style="padding: 14px 10px; text-align: right; font-size: 11px; font-weight: 700; color: #ffffff; text-transform: uppercase; letter-spacing: 1px; border-right: 1px solid rgba(255,255,255,0.2); border-bottom: 3px solid #1e3a8a;">CURRENT<br/>BUGS</th>
                                    <th style="padding: 14px 10px; text-align: right; font-size: 11px; font-weight: 700; color: #ffffff; text-transform: uppercase; letter-spacing: 1px; border-right: 1px solid rgba(255,255,255,0.2); border-bottom: 3px solid #1e3a8a;">EXPECTED<br/>BUGS</th>
                                    <th style="padding: 14px 10px; text-align: right; font-size: 11px; font-weight: 700; color: #ffffff; text-transform: uppercase; letter-spacing: 1px; border-right: 1px solid rgba(255,255,255,0.2); border-bottom: 3px solid #1e3a8a;">NET BURN<br/>THIS WEEK</th>
                                    <th style="padding: 14px 10px; text-align: right; font-size: 11px; font-weight: 700; color: #ffffff; text-transform: uppercase; letter-spacing: 1px; border-bottom: 3px solid #1e3a8a;">REQUIRED<br/>BURN/WEEK</th>
                                </tr>
                                </thead>
                                <tbody>

"""

    # Table rows
    for i, project in enumerate(projects):
        week = project["latest_week"]
        baseline = project["baseline"]
        status = week["status"]
        status_color = STATUS_COLORS[status]

        # Determine if next project has same status (add stronger separator between different statuses)
        next_same_status = i < len(projects) - 1 and projects[i + 1]["latest_week"]["status"] == status
        status_border = "" if next_same_status else "border-bottom: 4px solid rgba(0,0,0,0.15);"

        # Alternate row colors with soft gradients
        row_bg = (
            "linear-gradient(to right, #ffffff 0%, #fafbfc 100%)"
            if i % 2 == 0
            else "linear-gradient(to right, #f8f9fa 0%, #f1f3f5 100%)"
        )

        # Net burn color with softer tones (only positive is green, zero or negative is red)
        net_burn_color = "#10b981" if week["net_burn"] > 0 else "#f87171"
        net_burn_bg = (
            "linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(16, 185, 129, 0.12) 100%)"
            if week["net_burn"] > 0
            else "linear-gradient(135deg, rgba(248, 113, 113, 0.08) 0%, rgba(248, 113, 113, 0.12) 100%)"
        )

        # Add extra padding for last row of each status group
        row_padding = "14px 10px 20px 10px" if not next_same_status else "14px 10px"

        html += f"""
                                <tr style="background: {row_bg};">
                                    <td style="padding: {row_padding}; font-size: 14px; color: #374151; font-weight: 600; border-bottom: 1px solid #e5e7eb; border-right: 1px solid #e5e7eb;">{project['project_name']}</td>
                                    <td style="padding: 0; text-align: center; background-color: {status_color}; {status_border} border-right: 1px solid #e5e7eb; width: 60px;">
                                    </td>
                                    <td style="padding: {row_padding}; text-align: right; font-size: 14px; color: #6b7280; border-bottom: 1px solid #e5e7eb; border-right: 1px solid #e5e7eb;">{baseline['open_count']}</td>
                                    <td style="padding: {row_padding}; text-align: right; font-size: 14px; color: #6b7280; border-bottom: 1px solid #e5e7eb; border-right: 1px solid #e5e7eb;">{baseline['target_count']}</td>
                                    <td style="padding: {row_padding}; text-align: right; font-size: 16px; font-weight: 700; color: #1f2937; border-bottom: 1px solid #e5e7eb; border-right: 1px solid #e5e7eb;">{week['open']}</td>
                                    <td style="padding: {row_padding}; text-align: right; font-size: 14px; color: #6b7280; border-bottom: 1px solid #e5e7eb; border-right: 1px solid #e5e7eb;">{week['expected']}</td>
                                    <td style="padding: {row_padding}; text-align: right; font-size: 15px; font-weight: 700; color: {net_burn_color}; background: {net_burn_bg}; border-bottom: 1px solid #e5e7eb; border-right: 1px solid #e5e7eb;">{week['net_burn']:+d}</td>
                                    <td style="padding: {row_padding}; text-align: right; font-size: 14px; font-weight: 600; color: #1f2937; border-bottom: 1px solid #e5e7eb;">+{week['required_burn']:.2f}</td>
                                </tr>
"""

    html += f"""
                                </tbody>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 18px 20px; text-align: center; background: linear-gradient(to right, #f8f9fa 0%, #e9ecef 100%); border-top: 1px solid #dee2e6;">
                            <p style="margin: 0; color: #495057; font-size: 15px; font-weight: 600;">
                                <strong style="color: #212529;">{weeks_remaining} weeks</strong> remaining until target date: <strong style="color: #212529;">{target_date}</strong>
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    return html


def send_email(recipient: str, subject: str, body_text: str, body_html: str, dry_run: bool = False) -> bool:
    """
    Send email via Gmail SMTP.

    Args:
        recipient: Email recipient address
        subject: Email subject
        body_text: Plain text email body
        body_html: HTML email body
        dry_run: If True, don't actually send email

    Returns:
        bool: True if successful, False otherwise
    """
    # Load SMTP configuration from environment
    sender_email = os.getenv("EMAIL_ADDRESS")
    sender_password = os.getenv("EMAIL_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))

    # Validate configuration
    if not sender_email or sender_email == "your_email@gmail.com":
        raise ValueError("EMAIL_ADDRESS not configured in .env file.\n" "Please set your Gmail address")

    if not sender_password or sender_password == "your_app_password_here":
        raise ValueError("EMAIL_PASSWORD not configured in .env file.\n" "Please create a Gmail App Password")

    if dry_run:
        logger.info("DRY RUN - Email not sent")
        print("\n" + "=" * 80)
        print("DRY RUN - Email Preview")
        print("=" * 80)
        print(f"From: {sender_email}")
        print(f"To: {recipient}")
        print(f"Subject: {subject}")
        print("=" * 80)
        print(body_text)
        print("=" * 80)
        return True

    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Bug Position Report <{sender_email}>"
        msg["To"] = recipient

        # Attach both plain text and HTML versions
        part1 = MIMEText(body_text, "plain")
        part2 = MIMEText(body_html, "html")
        msg.attach(part1)
        msg.attach(part2)

        # Connect to SMTP server and send email
        logger.info(f"Connecting to SMTP server: {smtp_server}:{smtp_port}")
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        logger.info(f"Email sent successfully to {recipient}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}", exc_info=True)
        raise RuntimeError(f"Email send failed: {e}") from e


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Send multi-project DOE bug tracking report via email")

    parser.add_argument("--recipient", help=f"Email recipient (default: {DEFAULT_RECIPIENT})")

    parser.add_argument("--dry-run", action="store_true", help="Print email without sending")

    parser.add_argument(
        "--projects", nargs="+", help="Specific project keys to include (default: all discovered projects)"
    )

    return parser.parse_args()


if __name__ == "__main__":
    """
    Entry point when script is run from command line.
    """
    try:
        # Fix encoding for Windows console
        import io

        if sys.stdout.encoding != "utf-8":
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

        # Parse command-line arguments
        args = parse_arguments()

        # Determine recipient
        recipient = args.recipient if args.recipient else DEFAULT_RECIPIENT

        # Load project data
        projects = load_all_projects(args.projects)

        if not projects:
            raise ValueError("No projects found. Please run baseline and tracker for at least one project.")

        logger.info(f"Loaded {len(projects)} projects")

        # Get week number from first project
        week_number = projects[0]["week_number"]

        # Format email
        subject = f"Bug Position Report - Week {week_number}"
        body_text = format_email_body_text(projects)
        body_html = format_email_body_html(projects)

        # Send email
        send_email(recipient=recipient, subject=subject, body_text=body_text, body_html=body_html, dry_run=args.dry_run)

        if not args.dry_run:
            print(f"\n✓ Multi-project report sent successfully to {recipient}")

        # Exit with success code
        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
