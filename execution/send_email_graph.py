"""
Microsoft Graph API Email Sending Script

Sends emails from Office365/Microsoft 365 accounts using Microsoft Graph API
with OAuth 2.0 authentication (modern auth, no password required).
"""

import os
import sys
import argparse
import logging
import json
import base64
from datetime import datetime
from typing import List, Optional
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'.tmp/email_graph_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Microsoft Graph API endpoints
GRAPH_API_ENDPOINT = 'https://graph.microsoft.com/v1.0'
TOKEN_ENDPOINT = 'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'


def get_access_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    """
    Get OAuth 2.0 access token for Microsoft Graph API using client credentials flow.

    Args:
        tenant_id: Azure AD tenant ID
        client_id: Application (client) ID
        client_secret: Client secret value

    Returns:
        str: Access token

    Raises:
        RuntimeError: If authentication fails
    """
    logger.info("Requesting access token from Microsoft Graph API...")

    token_url = TOKEN_ENDPOINT.format(tenant_id=tenant_id)

    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'https://graph.microsoft.com/.default',
        'grant_type': 'client_credentials'
    }

    try:
        response = requests.post(token_url, data=data, timeout=30)
        response.raise_for_status()

        token_data = response.json()
        access_token = token_data.get('access_token')

        if not access_token:
            raise RuntimeError("No access token in response")

        logger.info("Successfully obtained access token")
        return access_token

    except requests.exceptions.HTTPError as e:
        error_details = e.response.json() if e.response else {}
        raise RuntimeError(
            f"Failed to get access token: {e}\n"
            f"Error details: {error_details}\n"
            f"Make sure:\n"
            f"1. Tenant ID, Client ID, and Client Secret are correct in .env\n"
            f"2. App has 'Mail.Send' permission in Azure AD\n"
            f"3. Admin consent has been granted"
        ) from e
    except Exception as e:
        raise RuntimeError(f"Authentication error: {e}") from e


def send_email_graph(
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
    access_token: str,
    attachments: Optional[List[str]] = None,
    html: bool = False,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None
) -> bool:
    """
    Send an email via Microsoft Graph API.

    Args:
        from_email: Sender email address
        to_email: Recipient email address
        subject: Email subject
        body: Email body content
        access_token: OAuth 2.0 access token
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

    # Build email message
    message = {
        'message': {
            'subject': subject,
            'body': {
                'contentType': 'HTML' if html else 'Text',
                'content': body
            },
            'toRecipients': [
                {'emailAddress': {'address': to_email}}
            ]
        },
        'saveToSentItems': 'true'
    }

    # Add CC recipients
    if cc:
        message['message']['ccRecipients'] = [
            {'emailAddress': {'address': addr}} for addr in cc
        ]

    # Add BCC recipients
    if bcc:
        message['message']['bccRecipients'] = [
            {'emailAddress': {'address': addr}} for addr in bcc
        ]

    # Add attachments
    if attachments:
        message['message']['attachments'] = []
        for file_path in attachments:
            if not os.path.exists(file_path):
                logger.warning(f"Attachment not found: {file_path}")
                continue

            logger.info(f"Attaching file: {file_path}")

            # Check file size (4MB limit for inline attachments)
            file_size = os.path.getsize(file_path)
            if file_size > 4 * 1024 * 1024:  # 4MB
                logger.warning(f"File {file_path} is larger than 4MB, skipping (use upload session for large files)")
                continue

            with open(file_path, 'rb') as f:
                file_content = f.read()
                file_base64 = base64.b64encode(file_content).decode('utf-8')

            message['message']['attachments'].append({
                '@odata.type': '#microsoft.graph.fileAttachment',
                'name': os.path.basename(file_path),
                'contentType': 'application/octet-stream',
                'contentBytes': file_base64
            })

    # Send email via Graph API
    send_url = f'{GRAPH_API_ENDPOINT}/users/{from_email}/sendMail'

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Sending email via Graph API (attempt {attempt + 1})...")

            response = requests.post(
                send_url,
                headers=headers,
                json=message,
                timeout=60
            )

            response.raise_for_status()

            logger.info("Email sent successfully via Graph API!")
            return True

        except requests.exceptions.HTTPError as e:
            error_details = e.response.json() if e.response else {}
            error_code = error_details.get('error', {}).get('code', '')

            # Handle throttling
            if e.response.status_code == 429 or error_code == 'TooManyRequests':
                if attempt < max_retries - 1:
                    retry_after = int(e.response.headers.get('Retry-After', 5))
                    logger.warning(f"Rate limited. Retrying after {retry_after} seconds...")
                    import time
                    time.sleep(retry_after)
                    continue

            raise RuntimeError(
                f"Failed to send email: HTTP {e.response.status_code}\n"
                f"Error details: {error_details}\n"
                f"Make sure the sender email address ({from_email}) is valid and accessible"
            ) from e

        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Failed to send email after {max_retries} attempts: {e}") from e
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying...")

    return False


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Send an email via Microsoft Graph API'
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

        # Get Azure AD credentials
        tenant_id = os.getenv('AZURE_TENANT_ID')
        client_id = os.getenv('AZURE_CLIENT_ID')
        client_secret = os.getenv('AZURE_CLIENT_SECRET')
        from_email = args.from_email or os.getenv('EMAIL_ADDRESS')

        if not all([tenant_id, client_id, client_secret]):
            raise RuntimeError(
                "Azure AD credentials not configured in .env file.\n"
                "Required: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET\n\n"
                "See directives/send_email_graph.md for setup instructions."
            )

        if not from_email:
            raise RuntimeError(
                "Sender email not specified. Set EMAIL_ADDRESS in .env or use --from-email"
            )

        # Get body content
        if args.body:
            body = args.body
        elif args.body_file:
            with open(args.body_file, 'r', encoding='utf-8') as f:
                body = f.read()
        else:
            raise ValueError("Either --body or --body-file must be provided")

        # Get access token
        access_token = get_access_token(tenant_id, client_id, client_secret)

        # Send email
        success = send_email_graph(
            from_email=from_email,
            to_email=args.to_email,
            subject=args.subject,
            body=body,
            access_token=access_token,
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
