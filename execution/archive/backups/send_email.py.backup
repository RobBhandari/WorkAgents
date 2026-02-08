"""
Email Sending Script

Sends emails via SMTP with optional HTML content and attachments.
Supports Gmail, Outlook, and other SMTP servers.
"""

import os
import sys
import argparse
import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'.tmp/email_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# SMTP Configuration
SMTP_SERVERS = {
    'gmail': ('smtp.gmail.com', 587),
    'outlook': ('smtp.office365.com', 587),
    'office365': ('smtp.office365.com', 587),
}


def send_email(
    to_email: str,
    subject: str,
    body: str,
    from_email: Optional[str] = None,
    from_password: Optional[str] = None,
    smtp_server: Optional[str] = None,
    smtp_port: Optional[int] = None,
    attachments: Optional[List[str]] = None,
    html: bool = False,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None
) -> bool:
    """
    Send an email via SMTP.

    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body content
        from_email: Sender email (default: from .env)
        from_password: Email password (default: from .env)
        smtp_server: SMTP server address (default: from .env or auto-detect)
        smtp_port: SMTP port (default: 587)
        attachments: List of file paths to attach
        html: Whether body is HTML (default: False)
        cc: List of CC recipients
        bcc: List of BCC recipients

    Returns:
        bool: True if email sent successfully

    Raises:
        RuntimeError: If email sending fails
    """
    logger.info(f"Preparing to send email to {to_email}")

    # Get email credentials from environment or parameters
    from_email = from_email or os.getenv('EMAIL_ADDRESS')
    from_password = from_password or os.getenv('EMAIL_PASSWORD')

    if not from_email or not from_password:
        raise RuntimeError(
            "Email credentials not configured.\n"
            "Set EMAIL_ADDRESS and EMAIL_PASSWORD in .env file or pass as arguments.\n"
            "For Gmail, use an App Password: https://myaccount.google.com/apppasswords"
        )

    # Auto-detect SMTP server if not provided
    if not smtp_server:
        smtp_server = os.getenv('SMTP_SERVER')
        if not smtp_server:
            # Try to detect from email domain
            domain = from_email.split('@')[1].lower()
            if 'gmail' in domain:
                smtp_server, smtp_port = SMTP_SERVERS['gmail']
            elif 'outlook' in domain or 'office365' in domain or 'hotmail' in domain:
                smtp_server, smtp_port = SMTP_SERVERS['outlook']
            else:
                raise RuntimeError(
                    f"Could not auto-detect SMTP server for {domain}.\n"
                    "Please set SMTP_SERVER and SMTP_PORT in .env"
                )
            logger.info(f"Auto-detected SMTP: {smtp_server}:{smtp_port}")

    smtp_port = smtp_port or int(os.getenv('SMTP_PORT', '587'))

    # Create message
    msg = MIMEMultipart('alternative')
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')

    if cc:
        msg['Cc'] = ', '.join(cc)

    # Attach body
    if html:
        msg.attach(MIMEText(body, 'html'))
    else:
        msg.attach(MIMEText(body, 'plain'))

    # Attach files
    if attachments:
        for file_path in attachments:
            if not os.path.exists(file_path):
                logger.warning(f"Attachment not found: {file_path}")
                continue

            logger.info(f"Attaching file: {file_path}")
            with open(file_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {os.path.basename(file_path)}'
                )
                msg.attach(part)

    # Build recipient list
    recipients = [to_email]
    if cc:
        recipients.extend(cc)
    if bcc:
        recipients.extend(bcc)

    # Send email
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Connecting to SMTP server: {smtp_server}:{smtp_port} (attempt {attempt + 1})")

            with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()

                logger.info("Authenticating...")
                server.login(from_email, from_password)

                logger.info(f"Sending email to {len(recipients)} recipient(s)...")
                server.send_message(msg)

                logger.info("Email sent successfully!")
                return True

        except smtplib.SMTPAuthenticationError as e:
            raise RuntimeError(
                f"SMTP Authentication failed: {e}\n"
                "For Gmail: Use an App Password (https://myaccount.google.com/apppasswords)\n"
                "For Outlook: Ensure 'SMTP AUTH' is enabled in your account settings"
            ) from e

        except smtplib.SMTPException as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Failed to send email after {max_retries} attempts: {e}") from e
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying...")

        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Unexpected error sending email: {e}") from e
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying...")

    return False


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Send an email via SMTP'
    )

    parser.add_argument(
        'to_email',
        type=str,
        help='Recipient email address'
    )

    parser.add_argument(
        '--subject',
        type=str,
        required=True,
        help='Email subject'
    )

    parser.add_argument(
        '--body',
        type=str,
        help='Email body text (or use --body-file)'
    )

    parser.add_argument(
        '--body-file',
        type=str,
        help='Path to file containing email body'
    )

    parser.add_argument(
        '--html',
        action='store_true',
        help='Body is HTML format'
    )

    parser.add_argument(
        '--attachments',
        type=str,
        nargs='+',
        help='Files to attach'
    )

    parser.add_argument(
        '--from-email',
        type=str,
        help='Sender email (default: from .env EMAIL_ADDRESS)'
    )

    parser.add_argument(
        '--cc',
        type=str,
        nargs='+',
        help='CC recipients'
    )

    parser.add_argument(
        '--bcc',
        type=str,
        nargs='+',
        help='BCC recipients'
    )

    return parser.parse_args()


if __name__ == '__main__':
    """Entry point when script is run from command line."""
    try:
        # Parse arguments
        args = parse_arguments()

        # Ensure .tmp directory exists
        os.makedirs('.tmp', exist_ok=True)

        # Get body content
        if args.body:
            body = args.body
        elif args.body_file:
            with open(args.body_file, 'r', encoding='utf-8') as f:
                body = f.read()
        else:
            raise ValueError("Either --body or --body-file must be provided")

        # Send email
        success = send_email(
            to_email=args.to_email,
            subject=args.subject,
            body=body,
            from_email=args.from_email,
            attachments=args.attachments,
            html=args.html,
            cc=args.cc,
            bcc=args.bcc
        )

        if success:
            print(f"\nSuccess! Email sent to {args.to_email}")
            sys.exit(0)
        else:
            print(f"\nFailed to send email to {args.to_email}", file=sys.stderr)
            sys.exit(1)

    except RuntimeError as e:
        logger.error(f"Script failed: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        sys.exit(1)
