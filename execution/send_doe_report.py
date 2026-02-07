"""
Send DOE Report Email

Sends weekly DOE bug tracking report via Gmail SMTP.
Formats the report with status indicators and sends to configured recipients.

Usage:
    python send_doe_report.py
    python send_doe_report.py --recipient alternate@email.com
    python send_doe_report.py --dry-run
    python send_doe_report.py --report-file custom_report.json
"""

import argparse
import json
import logging
import os
import smtplib
import subprocess
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape
from security_utils import PathValidator, ValidationError

from execution.core import get_config

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'.tmp/send_doe_report_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Default recipient
DEFAULT_RECIPIENT = "robin.bhandari@theaccessgroup.com"

# Status colors for HTML
STATUS_COLORS = {"GREEN": "#28a745", "AMBER": "#ffc107", "RED": "#dc3545"}


def load_latest_report() -> dict:
    """
    Load the latest DOE report from weekly tracking.

    Returns:
        dict: Latest week's report data

    Raises:
        FileNotFoundError: If tracking file doesn't exist
        ValueError: If tracking data is invalid
    """
    tracking_file = ".tmp/weekly_tracking.json"

    if not os.path.exists(tracking_file):
        raise FileNotFoundError(
            f"Weekly tracking not found: {tracking_file}\n" f"Please run: python execution/ado_doe_tracker.py"
        )

    logger.info(f"Loading weekly tracking from {tracking_file}")

    with open(tracking_file, encoding="utf-8") as f:
        tracking = json.load(f)

    weeks = tracking.get("weeks", [])
    if not weeks:
        raise ValueError("No weekly data found in tracking file")

    # Get the most recent week
    latest_week = weeks[-1]
    logger.info(f"Loaded Week {latest_week['week_number']} data")

    return latest_week


def load_baseline() -> dict:
    """
    Load baseline data from file.

    Returns:
        dict: Baseline data

    Raises:
        FileNotFoundError: If baseline file doesn't exist
    """
    baseline_file = ".tmp/baseline.json"

    if not os.path.exists(baseline_file):
        raise FileNotFoundError(
            f"Baseline not found: {baseline_file}\n" f"Please run: python execution/ado_baseline.py"
        )

    logger.info(f"Loading baseline from {baseline_file}")

    with open(baseline_file, encoding="utf-8") as f:
        baseline = json.load(f)

    return baseline


def format_email_body_text(report: dict, baseline: dict) -> str:
    """
    Format email body as plain text.

    Args:
        report: Weekly report data
        baseline: Baseline data

    Returns:
        str: Plain text email body
    """
    status_emoji = "🟢" if report["status"] == "GREEN" else ("🟠" if report["status"] == "AMBER" else "🔴")
    weeks_remaining = baseline["weeks_to_target"] - report["week_number"]
    delta_text = f"({abs(report['delta'])} bugs {'behind' if report['delta'] > 0 else 'ahead'} schedule)"

    required_burn = report.get("required_burn", baseline["required_weekly_burn"])

    body = f"""Week {report['week_number']} Bug Position - ALCM

📊 Status: {report['status']} {status_emoji} {delta_text}

Baseline: {baseline['open_count']} bugs → Target: {baseline['target_count']} bugs (30%)
Current: {report['open']} open bugs
Expected: {report['expected']} bugs
This week: Closed {report['closed']}, Created {report['new']}, Net burn: {report['net_burn']:+d}
Required: +{required_burn:.2f} per week
Time left: {weeks_remaining} weeks until {baseline['target_date']}
"""

    return body


def format_email_body_html(report: dict, baseline: dict) -> str:
    """
    Format email body as HTML with color coding using Jinja2 templates.

    Args:
        report: Weekly report data
        baseline: Baseline data

    Returns:
        str: HTML email body

    Raises:
        RuntimeError: If template rendering fails
    """
    logger.info("Generating email HTML with Jinja2")

    try:
        # Calculate derived values
        status = report["status"]
        status_color = STATUS_COLORS[status]
        weeks_remaining = baseline["weeks_to_target"] - report["week_number"]
        net_burn_color = "#28a745" if report["net_burn"] > 0 else "#dc3545"
        delta_text = f"{abs(report['delta'])} bugs {'behind' if report['delta'] > 0 else 'ahead'} schedule"
        required_burn = report.get("required_burn", baseline["required_weekly_burn"])

        # Setup Jinja2 environment with auto-escaping (XSS prevention)
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
        env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"]),  # CRITICAL: Auto-escape for XSS prevention
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Prepare template context
        context = {
            "report": report,
            "baseline": baseline,
            "status": status,
            "status_color": status_color,
            "weeks_remaining": weeks_remaining,
            "net_burn_color": net_burn_color,
            "delta_text": delta_text,
            "required_burn": required_burn,
        }

        # Render template (Jinja2 auto-escapes all variables)
        template = env.get_template("bug_position_email.html")
        html = template.render(**context)

        logger.info("Email HTML generated successfully with Jinja2")
        return html

    except Exception as e:
        logger.error(f"Error generating email HTML: {e}", exc_info=True)
        raise RuntimeError(f"Failed to generate email HTML: {e}") from e


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
    sender_email = get_config().get("EMAIL_ADDRESS")
    sender_password = get_config().get("EMAIL_PASSWORD")
    smtp_server = get_config().get("SMTP_SERVER")
    smtp_port = int(get_config().get("SMTP_PORT"))

    # Validate configuration
    if not sender_email or sender_email == "your_email@gmail.com":
        raise ValueError("EMAIL_ADDRESS not configured in .env file.\n" "Please set your Gmail address")

    if not sender_password or sender_password == "your_app_password_here":
        raise ValueError("EMAIL_PASSWORD not configured in .env file.\n" "Please create a Gmail App Password")

    if dry_run:
        logger.info("DRY RUN - Email not sent")
        print("\n" + "=" * 60)
        print("DRY RUN - Email Preview")
        print("=" * 60)
        print(f"From: {sender_email}")
        print(f"To: {recipient}")
        print(f"Subject: {subject}")
        print("=" * 60)
        print(body_text)
        print("=" * 60)
        return True

    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Bug Position - ALCM <{sender_email}>"
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


def check_and_create_scheduled_task() -> bool:
    """
    Check if scheduled task exists, create it if not.

    Returns:
        bool: True if task exists or was created, False if creation failed
    """
    task_name = "DOE_Weekly_Bug_Report"

    # Check if task already exists
    try:
        result = subprocess.run(["schtasks", "/query", "/tn", task_name], capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            logger.info(f"Scheduled task '{task_name}' already exists")
            return True

    except Exception as e:
        logger.warning(f"Could not query scheduled task: {e}")

    # Task doesn't exist, try to create it
    logger.info("Scheduled task not found, attempting to create...")

    # Get the absolute path to run_weekly_doe_report.bat
    script_dir = os.path.dirname(os.path.abspath(__file__))
    batch_file = os.path.join(script_dir, "run_weekly_doe_report.bat")
    log_file = os.path.join(os.path.dirname(script_dir), ".tmp", "scheduled_doe_report.log")

    # SECURITY: Validate file paths to prevent command injection
    try:
        # Validate batch file path (must be in script directory)
        safe_batch_file = PathValidator.validate_safe_path(script_dir, batch_file)

        # Validate log file path (must be in .tmp directory)
        tmp_dir = os.path.join(os.path.dirname(script_dir), ".tmp")
        os.makedirs(tmp_dir, exist_ok=True)  # Ensure .tmp exists
        safe_log_file = PathValidator.validate_safe_path(tmp_dir, log_file)

        logger.info(f"Validated batch file: {safe_batch_file}")
        logger.info(f"Validated log file: {safe_log_file}")

    except ValidationError as e:
        logger.error(f"Path validation failed: {e}")
        print(f"\n[SECURITY ERROR] Invalid file paths detected: {e}")
        return False

    # Create the scheduled task
    # SECURITY: Execute batch file directly (no cmd.exe wrapper to prevent injection)
    # Note: The batch file itself should handle logging to {safe_log_file}
    try:
        result = subprocess.run(
            [
                "schtasks",
                "/create",
                "/tn",
                task_name,
                "/tr",
                safe_batch_file,  # SECURE: Direct execution, no cmd.exe wrapper
                "/sc",
                "weekly",
                "/d",
                "FRI",
                "/st",
                "07:00",
                "/f",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )  # CRITICAL: shell=False

        if result.returncode == 0:
            logger.info("[OK] Scheduled task created successfully!")
            print(f"\n{'='*60}")
            print("[OK] AUTO-SCHEDULED: Weekly email every Friday at 7:00 AM")
            print(f"{'='*60}")
            print(f"Task name: {task_name}")
            print("Schedule: Every Friday at 7:00 AM")
            print(f"Batch file: {safe_batch_file}")
            print(f"Logs: {safe_log_file}")
            print("\nTo view: taskschd.msc")
            print(f'To test now: schtasks /run /tn "{task_name}"')
            print(f'To remove: schtasks /delete /tn "{task_name}" /f')
            print(f"{'='*60}\n")
            return True
        else:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            if "access is denied" in error_msg.lower():
                logger.warning("Admin rights required to create scheduled task")
                print(f"\n{'='*60}")
                print("⚠ AUTO-SCHEDULE REQUIRES ADMIN RIGHTS")
                print(f"{'='*60}")
                print("To enable Friday 7am automated emails, run as Administrator:")
                print(f"  cd {script_dir}")
                print("  schedule_doe_report.bat")
                print(f"{'='*60}\n")
            else:
                logger.warning(f"Failed to create scheduled task: {error_msg}")
            return False

    except Exception as e:
        logger.warning(f"Could not create scheduled task: {e}")
        return False


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Send DOE bug tracking report via email")

    parser.add_argument("--recipient", help=f"Email recipient (default: {DEFAULT_RECIPIENT})")

    parser.add_argument("--dry-run", action="store_true", help="Print email without sending")

    parser.add_argument("--report-file", help="Load report from custom file (default: use latest from weekly tracking)")

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

        # Load baseline data
        baseline = load_baseline()

        # Load report data
        if args.report_file:
            logger.info(f"Loading report from {args.report_file}")
            with open(args.report_file, encoding="utf-8") as f:
                report = json.load(f)
        else:
            report = load_latest_report()

        # Format email
        subject = f"Bug Position - ALCM - Week {report['week_number']}"
        body_text = format_email_body_text(report, baseline)
        body_html = format_email_body_html(report, baseline)

        # Send email
        send_email(recipient=recipient, subject=subject, body_text=body_text, body_html=body_html, dry_run=args.dry_run)

        if not args.dry_run:
            print(f"\n✓ DOE report sent successfully to {recipient}")

            # Auto-schedule weekly emails on first successful send
            check_and_create_scheduled_task()

        # Exit with success code
        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
