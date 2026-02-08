"""
Google Calendar Birthday Retrieval Script

Retrieves birthday events from Google Calendar for a specified time period.
Handles OAuth authentication and filters events by birthday keywords.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'.tmp/calendar_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Google Calendar API scope
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Birthday keywords to search for
BIRTHDAY_KEYWORDS = ["birthday", "bday", "b-day", "birth day", "cumpleaños", "anniversaire"]


def get_calendar_service():
    """
    Authenticate and return Google Calendar service.

    Returns:
        Calendar service object

    Raises:
        RuntimeError: If authentication fails
    """
    creds = None
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    token_path = os.getenv("GOOGLE_TOKEN_PATH", "token.json")

    # Check if credentials.json exists
    if not os.path.exists(credentials_path):
        raise RuntimeError(
            f"Google OAuth credentials not found at: {credentials_path}\n"
            "Please follow these steps:\n"
            "1. Go to https://console.cloud.google.com/\n"
            "2. Create a project or select existing one\n"
            "3. Enable Google Calendar API\n"
            "4. Create OAuth 2.0 credentials (Desktop app)\n"
            "5. Download credentials and save as 'credentials.json'"
        )

    # Load existing token if available
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired token...")
            creds.refresh(Request())
        else:
            logger.info("Starting OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for next run
        with open(token_path, "w") as token:
            token.write(creds.to_json())
        logger.info(f"Token saved to {token_path}")

    try:
        service = build("calendar", "v3", credentials=creds)
        logger.info("Successfully authenticated with Google Calendar API")
        return service
    except Exception as e:
        raise RuntimeError(f"Failed to build Calendar service: {e}") from e


def is_birthday_event(event: dict[str, Any]) -> bool:
    """
    Check if an event is a birthday based on keywords and properties.

    Args:
        event: Calendar event dictionary

    Returns:
        bool: True if event is a birthday
    """
    summary = event.get("summary", "").lower()

    # Check if summary contains birthday keywords
    for keyword in BIRTHDAY_KEYWORDS:
        if keyword in summary:
            return True

    # Check if event type is birthday
    if event.get("eventType") == "birthday":
        return True

    # Check if it's a yearly recurring event with birthday-like name
    recurrence = event.get("recurrence", [])
    if recurrence:
        for rule in recurrence:
            if "FREQ=YEARLY" in rule.upper():
                # If it's yearly and has a person's name pattern, likely a birthday
                if summary and not summary.startswith("holiday"):
                    return True

    return False


def get_birthdays(service, year: int = None, month: int = None, calendar_id: str = "primary") -> list[dict[str, Any]]:
    """
    Retrieve birthday events from Google Calendar for specified month.

    Args:
        service: Google Calendar service object
        year: Year to search (default: current year)
        month: Month to search (default: current month)
        calendar_id: Calendar ID to search (default: 'primary')

    Returns:
        List of birthday events with details

    Raises:
        RuntimeError: If API call fails
    """
    now = datetime.now()
    year = year or now.year
    month = month or now.month

    # Calculate time range for the month
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    time_min = start_date.isoformat() + "Z"
    time_max = end_date.isoformat() + "Z"

    logger.info(f"Searching for birthdays in {start_date.strftime('%B %Y')}")

    try:
        # Call the Calendar API
        events_result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=500,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        logger.info(f"Retrieved {len(events)} total events")

        # Filter for birthdays
        birthdays = []
        for event in events:
            if is_birthday_event(event):
                start = event["start"].get("dateTime", event["start"].get("date"))

                # Parse the date
                if "T" in start:
                    event_date = datetime.fromisoformat(start.replace("Z", "+00:00"))
                else:
                    event_date = datetime.fromisoformat(start)

                # Calculate days until
                days_until = (event_date.date() - now.date()).days

                birthdays.append(
                    {
                        "summary": event.get("summary", "Untitled"),
                        "date": event_date.strftime("%Y-%m-%d"),
                        "day_of_week": event_date.strftime("%A"),
                        "days_until": days_until,
                        "has_passed": days_until < 0,
                        "description": event.get("description", ""),
                    }
                )

        logger.info(f"Found {len(birthdays)} birthdays")
        return birthdays

    except HttpError as e:
        raise RuntimeError(f"Google Calendar API error: {e}") from e


def format_birthdays_table(birthdays: list[dict[str, Any]], month_name: str) -> str:
    """
    Format birthdays as a text table.

    Args:
        birthdays: List of birthday events
        month_name: Name of the month

    Returns:
        Formatted string table
    """
    if not birthdays:
        return f"\n📅 No birthdays found in {month_name}\n"

    output = [f"\n🎂 Birthdays in {month_name}\n"]
    output.append("=" * 80)

    for birthday in birthdays:
        name = birthday["summary"].replace("'s Birthday", "").replace("'s birthday", "").strip()
        date = birthday["date"]
        day = birthday["day_of_week"]
        days_until = birthday["days_until"]

        if days_until < 0:
            timing = f"(was {abs(days_until)} days ago)"
        elif days_until == 0:
            timing = "🎉 TODAY! 🎉"
        elif days_until == 1:
            timing = "⭐ TOMORROW!"
        else:
            timing = f"(in {days_until} days)"

        output.append(f"\n👤 {name}")
        output.append(f"   📅 {date} ({day}) {timing}")

    output.append("\n" + "=" * 80 + "\n")
    return "\n".join(output)


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Retrieve birthday events from Google Calendar")

    parser.add_argument("--month", type=int, default=None, help="Month number (1-12, default: current month)")

    parser.add_argument("--year", type=int, default=None, help="Year (default: current year)")

    parser.add_argument("--calendar-id", type=str, default="primary", help="Calendar ID to search (default: primary)")

    parser.add_argument(
        "--output", type=str, default=None, help="Output JSON file path (default: display to console only)"
    )

    parser.add_argument(
        "--format", type=str, choices=["table", "json"], default="table", help="Output format (default: table)"
    )

    return parser.parse_args()


if __name__ == "__main__":
    """Entry point when script is run from command line."""
    try:
        # Parse arguments
        args = parse_arguments()

        # Ensure .tmp directory exists
        os.makedirs(".tmp", exist_ok=True)

        # Get authenticated service
        logger.info("Authenticating with Google Calendar...")
        service = get_calendar_service()

        # Get birthdays
        birthdays = get_birthdays(service, year=args.year, month=args.month, calendar_id=args.calendar_id)

        # Determine month name for display
        now = datetime.now()
        year = args.year or now.year
        month = args.month or now.month
        month_name = datetime(year, month, 1).strftime("%B %Y")

        # Sort by date
        birthdays.sort(key=lambda x: x["date"])

        # Output results
        if args.format == "json" or args.output:
            result = {"month": month_name, "count": len(birthdays), "birthdays": birthdays}

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                logger.info(f"Results saved to {args.output}")
                print(f"\n✅ Results saved to: {args.output}")
            else:
                print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            # Display as table
            print(format_birthdays_table(birthdays, month_name))

        sys.exit(0)

    except RuntimeError as e:
        logger.error(f"Script failed: {e}")
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
