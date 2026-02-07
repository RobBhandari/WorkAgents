"""
ArmorCode Email Delivery - Send HTML Report via Email

Sends the generated HTML report to configured recipients.
"""

from execution.core import get_config
import os
import sys
import logging
import smtplib
import glob
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def send_email(html_file, recipients):
    """Send HTML report via email."""

    # Get email configuration
    config = get_config()
    email_address = config.get("EMAIL_ADDRESS")
    email_password = config.get("EMAIL_PASSWORD")
    smtp_server = config.get("SMTP_SERVER")
    smtp_port = int(config.get("SMTP_PORT", "587"))

    if not email_address or not email_password:
        raise ValueError("EMAIL_ADDRESS and EMAIL_PASSWORD must be set in .env")

    # Read HTML content
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'ArmorCode Security Report - {datetime.now().strftime("%B %d, %Y")}'
    msg['From'] = f'ArmorCode Report <{email_address}>'
    msg['To'] = ', '.join(recipients) if isinstance(recipients, list) else recipients

    # Attach HTML content
    html_part = MIMEText(html_content, 'html')
    msg.attach(html_part)

    # Send email
    logger.info(f"Sending email to: {msg['To']}")
    logger.info(f"Using SMTP server: {smtp_server}:{smtp_port}")

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.send_message(msg)

        logger.info("Email sent successfully!")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise


def main():
    """Main execution."""
    try:
        # Get recipients from environment
        recipients_str = get_config().get("ARMORCODE_EMAIL_RECIPIENTS")
        if not recipients_str:
            logger.error("ARMORCODE_EMAIL_RECIPIENTS not set in .env")
            sys.exit(1)

        recipients = [r.strip() for r in recipients_str.split(',') if r.strip()]

        # Find most recent report file
        report_files = glob.glob('.tmp/armorcode_report_*.html')

        if not report_files:
            logger.error("No report files found. Run armorcode_generate_report.py first.")
            sys.exit(1)

        # Use most recent file
        latest_report = max(report_files, key=os.path.getctime)
        logger.info(f"Using report: {latest_report}")

        # Send email
        send_email(latest_report, recipients)

        logger.info("="*70)
        logger.info("Email delivery complete!")
        logger.info("="*70)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
