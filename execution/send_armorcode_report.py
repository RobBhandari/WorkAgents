"""
ArmorCode Report Email Sender

Sends the ArmorCode vulnerability tracking HTML report via email
using Microsoft Graph API.

Usage:
    python send_armorcode_report.py <html_file>
    python send_armorcode_report.py .tmp/armorcode_report_20260130.html
    python send_armorcode_report.py <html_file> --json-summary <json_file>
    python send_armorcode_report.py <html_file> --recipients email1@company.com,email2@company.com
"""

from execution.core import get_config
import os
import sys
import argparse
import logging
import json
import base64
from datetime import datetime
from dotenv import load_dotenv
from http_client import get, post, put, delete, patch

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'.tmp/send_armorcode_report_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def load_summary_data(json_file: str = None) -> dict:
    """
    Load summary data from JSON file.

    Args:
        json_file: Path to JSON file (optional)

    Returns:
        dict: Summary data or empty dict
    """
    if not json_file:
        logger.info("No JSON summary file specified")
        return {}

    if not os.path.exists(json_file):
        logger.warning(f"JSON file not found: {json_file}")
        return {}

    logger.info(f"Loading summary data from {json_file}")

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data


def send_email_graph(tenant_id: str, client_id: str, client_secret: str,
                     sender_email: str, recipients: list, subject: str,
                     body: str, html_file: str) -> bool:
    """
    Send email with HTML attachment using Microsoft Graph API.

    Args:
        tenant_id: Azure AD tenant ID
        client_id: Azure AD app client ID
        client_secret: Azure AD app client secret
        sender_email: Sender email address
        recipients: List of recipient email addresses
        subject: Email subject
        body: Email body text
        html_file: Path to HTML attachment

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        import requests

        logger.info("Authenticating with Microsoft Graph API")

        # Step 1: Get access token
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        token_data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'https://graph.microsoft.com/.default'
        }

        token_response = post(token_url, data=token_data, timeout=30)
        token_response.raise_for_status()
        access_token = token_response.json()['access_token']

        logger.info("Successfully authenticated with Graph API")

        # Step 2: Read HTML file
        with open(html_file, 'rb') as f:
            html_content = f.read()

        # Encode HTML file as base64
        html_b64 = base64.b64encode(html_content).decode('utf-8')
        html_filename = os.path.basename(html_file)

        logger.info(f"Prepared attachment: {html_filename} ({len(html_content)} bytes)")

        # Step 3: Build email message
        to_recipients = [{"emailAddress": {"address": email}} for email in recipients]

        message = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": body
                },
                "toRecipients": to_recipients,
                "attachments": [
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": html_filename,
                        "contentType": "text/html",
                        "contentBytes": html_b64
                    }
                ]
            },
            "saveToSentItems": "true"
        }

        # Step 4: Send email
        send_url = f"https://graph.microsoft.com/v1.0/users/{sender_email}/sendMail"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        logger.info(f"Sending email to {len(recipients)} recipient(s)")

        send_response = post(send_url, headers=headers, json=message, timeout=30)
        send_response.raise_for_status()

        logger.info("Email sent successfully")
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request failed: {e}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response: {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"Error sending email: {e}", exc_info=True)
        return False


def build_email_body(summary_data: dict) -> str:
    """
    Build email body text from summary data.

    Args:
        summary_data: Summary data from JSON

    Returns:
        str: Email body text
    """
    if not summary_data:
        return """ArmorCode Vulnerability Tracking Report

Please see the attached HTML report for details.

This is an automated report from the ArmorCode Vulnerability Tracking System."""

    baseline = summary_data.get('baseline', {})
    target = summary_data.get('target', {})
    current = summary_data.get('current', {})
    comparison = summary_data.get('comparison', {})

    body = f"""ArmorCode Vulnerability Tracking Report
Report Date: {datetime.now().strftime('%Y-%m-%d')}

Summary:
- Baseline ({baseline.get('date', 'N/A')}): {baseline.get('count', 'N/A')} vulnerabilities
- Target ({target.get('reduction_goal_pct', 'N/A')}% reduction): {target.get('count', 'N/A')} vulnerabilities
- Current: {current.get('count', 'N/A')} vulnerabilities

Progress:
- Reduction: {comparison.get('reduction_amount', 'N/A')} vulnerabilities ({comparison.get('reduction_pct', 'N/A')}%)
- Progress to goal: {comparison.get('progress_to_goal_pct', 'N/A')}%
- Remaining: {comparison.get('remaining_to_goal', 'N/A')} vulnerabilities

Timeline:
- Days since baseline: {comparison.get('days_since_baseline', 'N/A')}
- Days to target: {comparison.get('days_to_target', 'N/A')}

See attached HTML report for full details including vulnerability listing and trend analysis.

---
This is an automated report from the ArmorCode Vulnerability Tracking System."""

    return body


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Send ArmorCode HTML report via email'
    )

    parser.add_argument(
        'html_file',
        type=str,
        help='Path to HTML report file'
    )

    parser.add_argument(
        '--json-summary',
        type=str,
        default=None,
        help='Path to JSON summary file (optional, for email body)'
    )

    parser.add_argument(
        '--recipients',
        type=str,
        default=None,
        help='Comma-separated list of recipient email addresses (overrides .env)'
    )

    parser.add_argument(
        '--subject',
        type=str,
        default=None,
        help='Email subject (default: auto-generated from summary)'
    )

    return parser.parse_args()


if __name__ == '__main__':
    """Entry point when script is run from command line."""
    try:
        args = parse_arguments()

        # Validate HTML file exists
        if not os.path.exists(args.html_file):
            raise FileNotFoundError(f"HTML file not found: {args.html_file}")

        # Load summary data
        summary_data = load_summary_data(args.json_summary)

        # Load configuration from environment
        tenant_id = get_config().get("AZURE_TENANT_ID")
        client_id = get_config().get("AZURE_CLIENT_ID")
        client_secret = get_config().get("AZURE_CLIENT_SECRET")
        sender_email = get_config().get("EMAIL_ADDRESS")

        # Get recipients
        if args.recipients:
            recipients_str = args.recipients
        else:
            recipients_str = get_config().get("ARMORCODE_EMAIL_RECIPIENTS")

        if not recipients_str:
            raise RuntimeError(
                "No recipients specified.\n"
                "Use --recipients flag or set ARMORCODE_EMAIL_RECIPIENTS in .env file"
            )

        recipients = [email.strip() for email in recipients_str.split(',') if email.strip()]

        # Validate configuration
        if not all([tenant_id, client_id, client_secret]):
            raise RuntimeError(
                "Microsoft Graph API credentials not configured in .env file.\n"
                "Required: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET"
            )

        if not sender_email:
            raise RuntimeError("EMAIL_ADDRESS not configured in .env file")

        # Build email subject
        if args.subject:
            subject = args.subject
        elif summary_data:
            current_count = summary_data.get('current', {}).get('count', 'N/A')
            progress_pct = summary_data.get('comparison', {}).get('progress_to_goal_pct', 'N/A')
            subject = f"ArmorCode Vulnerability Report - {datetime.now().strftime('%Y-%m-%d')} - {current_count} vulns ({progress_pct}% to goal)"
        else:
            subject = f"ArmorCode Vulnerability Report - {datetime.now().strftime('%Y-%m-%d')}"

        # Build email body
        body = build_email_body(summary_data)

        # Send email
        logger.info("=" * 70)
        logger.info("Sending ArmorCode Report")
        logger.info("=" * 70)
        logger.info(f"To: {', '.join(recipients)}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Attachment: {args.html_file}")
        logger.info("=" * 70)

        success = send_email_graph(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            sender_email=sender_email,
            recipients=recipients,
            subject=subject,
            body=body,
            html_file=args.html_file
        )

        if success:
            print(f"\nEmail sent successfully!")
            print(f"Recipients: {', '.join(recipients)}")
            print(f"Subject: {subject}")
            sys.exit(0)
        else:
            print(f"\nFailed to send email. Check logs for details.")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
