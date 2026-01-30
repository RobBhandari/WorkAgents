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

import os
import sys
import argparse
import logging
import json
import smtplib
import subprocess
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'.tmp/send_doe_report_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Default recipient
DEFAULT_RECIPIENT = "robin.bhandari@theaccessgroup.com"

# Status colors for HTML
STATUS_COLORS = {
    'GREEN': '#28a745',
    'AMBER': '#ffc107',
    'RED': '#dc3545'
}


def load_latest_report() -> dict:
    """
    Load the latest DOE report from weekly tracking.

    Returns:
        dict: Latest week's report data

    Raises:
        FileNotFoundError: If tracking file doesn't exist
        ValueError: If tracking data is invalid
    """
    tracking_file = '.tmp/weekly_tracking.json'

    if not os.path.exists(tracking_file):
        raise FileNotFoundError(
            f"Weekly tracking not found: {tracking_file}\n"
            f"Please run: python execution/ado_doe_tracker.py"
        )

    logger.info(f"Loading weekly tracking from {tracking_file}")

    with open(tracking_file, 'r', encoding='utf-8') as f:
        tracking = json.load(f)

    weeks = tracking.get('weeks', [])
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
    baseline_file = '.tmp/baseline.json'

    if not os.path.exists(baseline_file):
        raise FileNotFoundError(
            f"Baseline not found: {baseline_file}\n"
            f"Please run: python execution/ado_baseline.py"
        )

    logger.info(f"Loading baseline from {baseline_file}")

    with open(baseline_file, 'r', encoding='utf-8') as f:
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
    status_emoji = '🟢' if report['status'] == 'GREEN' else ('🟠' if report['status'] == 'AMBER' else '🔴')
    weeks_remaining = baseline['weeks_to_target'] - report['week_number']
    delta_text = f"({abs(report['delta'])} bugs {'behind' if report['delta'] > 0 else 'ahead'} schedule)"

    required_burn = report.get('required_burn', baseline['required_weekly_burn'])

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
    Format email body as HTML with color coding.

    Args:
        report: Weekly report data
        baseline: Baseline data

    Returns:
        str: HTML email body
    """
    status = report['status']
    status_color = STATUS_COLORS[status]
    status_emoji = '🟢' if status == 'GREEN' else ('🟠' if status == 'AMBER' else '🔴')
    weeks_remaining = baseline['weeks_to_target'] - report['week_number']
    net_burn_color = '#28a745' if report['net_burn'] > 0 else '#dc3545'
    delta_text = f"{abs(report['delta'])} bugs {'behind' if report['delta'] > 0 else 'ahead'} schedule"
    required_burn = report.get('required_burn', baseline['required_weekly_burn'])

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #ffffff;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 0; padding: 0;">
        <tr>
            <td align="center" style="margin: 0; padding: 0;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="background-color: #ffffff; margin: 0; padding: 0;">

                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 600;">Bug Position - ALCM</h1>
                            <p style="margin: 6px 0 0 0; color: #ffffff; font-size: 14px; opacity: 0.95;">Week {report['week_number']} Report</p>
                        </td>
                    </tr>

                    <!-- Status Banner -->
                    <tr>
                        <td style="padding: 20px 25px 15px 25px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {status_color}; border-radius: 6px;">
                                <tr>
                                    <td style="padding: 20px; text-align: center;">
                                        <div style="color: #000000; font-size: 18px; font-weight: 600;">{status}</div>
                                        <div style="color: #000000; font-size: 14px; margin-top: 5px;">{delta_text}</div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Metrics Grid -->
                    <tr>
                        <td style="padding: 15px 25px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td width="48%" valign="top" style="background-color: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 3px solid #667eea;">
                                        <div style="font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;">BASELINE</div>
                                        <div style="font-size: 28px; font-weight: 700; color: #1a1a1a;">{baseline['open_count']}</div>
                                        <div style="font-size: 12px; color: #666; margin-top: 3px;">Week 0 starting point</div>
                                    </td>
                                    <td width="4%"></td>
                                    <td width="48%" valign="top" style="background-color: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 3px solid #667eea;">
                                        <div style="font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;">TARGET (30%)</div>
                                        <div style="font-size: 28px; font-weight: 700; color: #1a1a1a;">{baseline['target_count']}</div>
                                        <div style="font-size: 12px; color: #666; margin-top: 3px;">by {baseline['target_date']}</div>
                                    </td>
                                </tr>
                                <tr><td colspan="3" height="15"></td></tr>
                                <tr>
                                    <td width="48%" valign="top" style="background-color: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 3px solid #667eea;">
                                        <div style="font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;">EXPECTED NOW</div>
                                        <div style="font-size: 28px; font-weight: 700; color: #1a1a1a;">{report['expected']}</div>
                                        <div style="font-size: 12px; color: #666; margin-top: 3px;">projected for week {report['week_number']}</div>
                                    </td>
                                    <td width="4%"></td>
                                    <td width="48%" valign="top" style="background-color: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 3px solid {status_color};">
                                        <div style="font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;">ACTUAL</div>
                                        <div style="font-size: 28px; font-weight: 700; color: #1a1a1a;">{report['open']}</div>
                                        <div style="font-size: 12px; color: #666; margin-top: 3px;">current open bugs</div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Weekly Activity -->
                    <tr>
                        <td style="padding: 15px 25px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f8f9fa; border-radius: 6px;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <div style="font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 15px; font-weight: 600;">THIS WEEK'S ACTIVITY</div>

                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="10" border="0">
                                            <tr style="border-bottom: 1px solid #e0e0e0;">
                                                <td style="font-size: 14px; color: #666;">Closed</td>
                                                <td align="right" style="font-size: 18px; font-weight: 600; color: #1a1a1a;">{report['closed']}</td>
                                            </tr>
                                            <tr style="border-bottom: 1px solid #e0e0e0;">
                                                <td style="font-size: 14px; color: #666;">Created</td>
                                                <td align="right" style="font-size: 18px; font-weight: 600; color: #1a1a1a;">{report['new']}</td>
                                            </tr>
                                            <tr style="border-bottom: 1px solid #e0e0e0;">
                                                <td style="font-size: 14px; color: #666;">Net Burn</td>
                                                <td align="right" style="font-size: 18px; font-weight: 600; color: {net_burn_color};">{report['net_burn']:+d}</td>
                                            </tr>
                                            <tr>
                                                <td style="font-size: 14px; color: #666;">Required Burn</td>
                                                <td align="right" style="font-size: 18px; font-weight: 600; color: #1a1a1a;">+{required_burn:.2f}</td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Timeline -->
                    <tr>
                        <td style="padding: 15px 25px 30px 25px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f8f9fa; border-radius: 6px;">
                                <tr>
                                    <td style="padding: 15px 20px; text-align: center; font-size: 14px; color: #666;">
                                        <strong style="color: #1a1a1a; font-size: 16px;">{weeks_remaining}</strong> weeks remaining until <strong style="color: #1a1a1a; font-size: 16px;">{baseline['target_date']}</strong>
                                    </td>
                                </tr>
                            </table>
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
    sender_email = os.getenv('EMAIL_ADDRESS')
    sender_password = os.getenv('EMAIL_PASSWORD')
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))

    # Validate configuration
    if not sender_email or sender_email == 'your_email@gmail.com':
        raise ValueError(
            "EMAIL_ADDRESS not configured in .env file.\n"
            "Please set your Gmail address"
        )

    if not sender_password or sender_password == 'your_app_password_here':
        raise ValueError(
            "EMAIL_PASSWORD not configured in .env file.\n"
            "Please create a Gmail App Password"
        )

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
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"Bug Position - ALCM <{sender_email}>"
        msg['To'] = recipient

        # Attach both plain text and HTML versions
        part1 = MIMEText(body_text, 'plain')
        part2 = MIMEText(body_html, 'html')
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
        result = subprocess.run(
            ['schtasks', '/query', '/tn', task_name],
            capture_output=True,
            text=True,
            timeout=5
        )

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

    # Create the scheduled task
    try:
        result = subprocess.run([
            'schtasks', '/create',
            '/tn', task_name,
            '/tr', f'cmd.exe /c "{batch_file}" >> "{log_file}" 2>&1',
            '/sc', 'weekly',
            '/d', 'FRI',
            '/st', '07:00',
            '/f'
        ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            logger.info(f"✓ Scheduled task created successfully!")
            print(f"\n{'='*60}")
            print(f"✓ AUTO-SCHEDULED: Weekly email every Friday at 7:00 AM")
            print(f"{'='*60}")
            print(f"Task name: {task_name}")
            print(f"Schedule: Every Friday at 7:00 AM")
            print(f"Logs: {log_file}")
            print(f"\nTo view: taskschd.msc")
            print(f"To test now: schtasks /run /tn \"{task_name}\"")
            print(f"To remove: schtasks /delete /tn \"{task_name}\" /f")
            print(f"{'='*60}\n")
            return True
        else:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            if "access is denied" in error_msg.lower():
                logger.warning("Admin rights required to create scheduled task")
                print(f"\n{'='*60}")
                print(f"⚠ AUTO-SCHEDULE REQUIRES ADMIN RIGHTS")
                print(f"{'='*60}")
                print(f"To enable Friday 7am automated emails, run as Administrator:")
                print(f"  cd {script_dir}")
                print(f"  schedule_doe_report.bat")
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
    parser = argparse.ArgumentParser(
        description='Send DOE bug tracking report via email'
    )

    parser.add_argument(
        '--recipient',
        help=f'Email recipient (default: {DEFAULT_RECIPIENT})'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print email without sending'
    )

    parser.add_argument(
        '--report-file',
        help='Load report from custom file (default: use latest from weekly tracking)'
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

        # Determine recipient
        recipient = args.recipient if args.recipient else DEFAULT_RECIPIENT

        # Load baseline data
        baseline = load_baseline()

        # Load report data
        if args.report_file:
            logger.info(f"Loading report from {args.report_file}")
            with open(args.report_file, 'r', encoding='utf-8') as f:
                report = json.load(f)
        else:
            report = load_latest_report()

        # Format email
        subject = f"Bug Position - ALCM - Week {report['week_number']}"
        body_text = format_email_body_text(report, baseline)
        body_html = format_email_body_html(report, baseline)

        # Send email
        send_email(
            recipient=recipient,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            dry_run=args.dry_run
        )

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
