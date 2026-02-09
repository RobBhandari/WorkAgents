"""
Microsoft Teams Bug Position Bot

Provides instant bug position reports via Microsoft Teams.
Queries Azure DevOps API directly for live data.

Setup:
1. Install: pip install botbuilder-core aiohttp azure-devops
2. Create Azure Bot Service
3. Configure bot credentials in .env
4. Deploy to Azure App Service with baseline files
5. Install bot in Teams

Commands:
- bugposition - Full multi-project bug position report
- week - Current week number
- projects - List all tracked projects
- project <name> - Details for specific project
- help - Show help message

Usage:
    python teams_bug_bot.py
"""

import glob
import json
import logging
import os
import sys
from datetime import datetime, timedelta

from aiohttp import web
from aiohttp.web import Request, Response

# Azure DevOps SDK
from azure.devops.connection import Connection
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity, ActivityTypes
from dotenv import load_dotenv
from msrest.authentication import BasicAuthentication

from execution.core import get_config

# Security utilities for input validation
from execution.security import ValidationError, WIQLValidator

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Status emojis
STATUS_EMOJIS = {"GREEN": "🟢", "AMBER": "🟠", "RED": "🔴"}

# Status sort order
STATUS_ORDER = {"GREEN": 0, "AMBER": 1, "RED": 2}

# Status thresholds
STATUS_AMBER_THRESHOLD = 1.10


def query_current_bugs(organization_url: str, project_name: str, pat: str) -> int:
    """Query current count of open bugs in ADO."""
    try:
        credentials = BasicAuthentication("", pat)
        connection = Connection(base_url=organization_url, creds=credentials)
        wit_client = connection.clients.get_work_item_tracking_client()

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
            work_type="Bug",
            state="Closed",
        )

        wiql_results = wit_client.query_by_wiql(
            wiql={"query": wiql_query}
        )  # nosec B608 - Input validated by WIQLValidator.build_safe_wiql()

        if not wiql_results.work_items:
            return 0

        return len(wiql_results.work_items)

    except ValidationError as e:
        logger.error(f"Invalid input for project '{project_name}': {e}")
        raise ValueError(f"Invalid project name: {e}")
    except Exception as e:
        logger.error(f"Error querying bugs for {project_name}: {e}")
        raise


def query_bugs_by_date_range(
    organization_url: str, project_name: str, pat: str, start_date: str, end_date: str, query_type: str
) -> int:
    """Query bugs created or closed within a date range."""
    try:
        credentials = BasicAuthentication("", pat)
        connection = Connection(base_url=organization_url, creds=credentials)
        wit_client = connection.clients.get_work_item_tracking_client()

        # Validate inputs to prevent WIQL injection
        safe_project = WIQLValidator.validate_project_name(project_name)
        safe_start_date = WIQLValidator.validate_date_iso8601(start_date)
        safe_end_date = WIQLValidator.validate_date_iso8601(end_date)

        if query_type == "created":
            wiql_query = WIQLValidator.build_safe_wiql(
                """SELECT [System.Id]
                FROM WorkItems
                WHERE [System.TeamProject] = '{project}'
                AND [System.WorkItemType] = '{work_type}'
                AND [System.CreatedDate] >= '{start_date}'
                AND [System.CreatedDate] < '{end_date}'""",
                project=safe_project,
                work_type="Bug",
                start_date=safe_start_date,
                end_date=safe_end_date,
            )
        elif query_type == "closed":
            wiql_query = WIQLValidator.build_safe_wiql(
                """SELECT [System.Id]
                FROM WorkItems
                WHERE [System.TeamProject] = '{project}'
                AND [System.WorkItemType] = '{work_type}'
                AND [System.State] = '{state}'
                AND [Microsoft.VSTS.Common.ClosedDate] >= '{start_date}'
                AND [Microsoft.VSTS.Common.ClosedDate] < '{end_date}'""",
                project=safe_project,
                work_type="Bug",
                state="Closed",
                start_date=safe_start_date,
                end_date=safe_end_date,
            )
        else:
            raise ValueError(f"Invalid query_type: {query_type}")

        wiql_results = wit_client.query_by_wiql(
            wiql={"query": wiql_query}
        )  # nosec B608 - Input validated by WIQLValidator.build_safe_wiql()

        if not wiql_results.work_items:
            return 0

        return len(wiql_results.work_items)

    except ValidationError as e:
        logger.error(f"Invalid input for project '{project_name}' or dates: {e}")
        raise ValueError(f"Invalid input: {e}")
    except Exception as e:
        logger.error(f"Error querying bugs by date for {project_name}: {e}")
        raise


def calculate_week_dates(baseline_date: str, week_number: int) -> tuple:
    """Calculate week start and end dates for a given week number."""
    baseline = datetime.strptime(baseline_date, "%Y-%m-%d")
    week_start = baseline + timedelta(weeks=week_number - 1)
    week_end = week_start + timedelta(weeks=1)
    return week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")


def calculate_current_week(baseline_date: str) -> int:
    """Calculate current week number based on baseline date."""
    baseline = datetime.strptime(baseline_date, "%Y-%m-%d")
    today = datetime.now()
    days_elapsed = (today - baseline).days
    return max(1, (days_elapsed // 7) + 1)


def determine_status(actual: int, expected: int) -> str:
    """Determine status based on actual vs expected values."""
    if actual <= expected:
        return "GREEN"
    elif actual <= expected * STATUS_AMBER_THRESHOLD:
        return "AMBER"
    else:
        return "RED"


def discover_projects() -> list[str]:
    """Discover all projects by finding baseline files."""
    baseline_files = glob.glob(".tmp/baseline_*.json")
    project_keys = []
    for file in baseline_files:
        project_key = os.path.basename(file).replace("baseline_", "").replace(".json", "")
        project_keys.append(project_key)
    logger.info(f"Discovered {len(project_keys)} projects")
    return project_keys


def load_baseline(project_key: str) -> dict:
    """Load baseline data from file."""
    baseline_file = f".tmp/baseline_{project_key}.json"

    if not os.path.exists(baseline_file):
        raise FileNotFoundError(f"Baseline not found for project '{project_key}'")

    with open(baseline_file, encoding="utf-8") as f:
        baseline = json.load(f)

    return baseline


def load_project_data(project_key: str, organization_url: str, pat: str) -> dict:
    """Load project data by querying ADO API."""
    # Load baseline from file
    baseline = load_baseline(project_key)
    project_name = baseline.get("project", project_key)

    # Calculate current week
    week_number = calculate_current_week(baseline["baseline_date"])
    week_start, week_end = calculate_week_dates(baseline["baseline_date"], week_number)

    # Query current open bugs
    current_open = query_current_bugs(organization_url, project_name, pat)

    # Query bugs created/closed this week
    new_bugs = query_bugs_by_date_range(organization_url, project_name, pat, week_start, week_end, "created")
    closed_bugs = query_bugs_by_date_range(organization_url, project_name, pat, week_start, week_end, "closed")

    # Calculate metrics
    net_burn = closed_bugs - new_bugs
    weeks_elapsed = week_number
    expected_reduction = baseline["required_weekly_burn"] * weeks_elapsed
    expected_open = max(baseline["target_count"], int(baseline["open_count"] - expected_reduction))
    delta = current_open - expected_open
    status = determine_status(current_open, expected_open)
    weeks_remaining = baseline["weeks_to_target"] - week_number
    dynamic_required_burn = (current_open - baseline["target_count"]) / weeks_remaining if weeks_remaining > 0 else 0

    latest_week = {
        "week_number": week_number,
        "open": current_open,
        "new": new_bugs,
        "closed": closed_bugs,
        "net_burn": net_burn,
        "expected": expected_open,
        "delta": delta,
        "status": status,
        "required_burn": round(dynamic_required_burn, 2),
    }

    return {
        "project_key": project_key,
        "project_name": project_name,
        "baseline": baseline,
        "latest_week": latest_week,
        "week_number": week_number,
        "weeks_remaining": weeks_remaining,
    }


def load_all_projects(project_keys: list[str] = None) -> list[dict]:
    """Load data for all projects."""
    organization_url = get_config().get("ADO_ORGANIZATION_URL")
    pat = get_config().get_ado_config().pat

    if not organization_url or not pat:
        raise RuntimeError("ADO_ORGANIZATION_URL and ADO_PAT must be configured")

    if project_keys is None:
        project_keys = discover_projects()

    projects = []
    for project_key in project_keys:
        try:
            project_data = load_project_data(project_key, organization_url, pat)
            projects.append(project_data)
        except Exception as e:
            logger.warning(f"Failed to load project '{project_key}': {e}")

    return projects


def sort_projects_by_status(projects: list[dict]) -> list[dict]:
    """Sort projects by RAG status (GREEN, AMBER, RED)."""

    def get_sort_key(project):
        status = project["latest_week"]["status"]
        return STATUS_ORDER.get(status, 99)

    return sorted(projects, key=get_sort_key)


def format_bug_position_report(projects: list[dict]) -> str:
    """Format bug position report for Teams."""
    projects = sort_projects_by_status(projects)

    if not projects:
        return "❌ No projects found. Please ensure baseline files are deployed."

    week_number = projects[0]["week_number"]
    weeks_remaining = projects[0]["weeks_remaining"]
    target_date = projects[0]["baseline"]["target_date"]

    lines = []
    lines.append(f"# 🐛 Bug Position Report - Week {week_number}\n")
    lines.append(f"📅 {datetime.now().strftime('%B %d, %Y')}\n")
    lines.append("---\n")

    current_status = None
    for project in projects:
        week = project["latest_week"]
        baseline = project["baseline"]
        status = week["status"]

        if current_status != status:
            if current_status is not None:
                lines.append("\n")
            current_status = status

        status_emoji = STATUS_EMOJIS.get(status, "⚪")
        net_burn_indicator = "🔥" if week["net_burn"] > 0 else "❄️"

        lines.append(f"**{project['project_name']}**  \n")
        lines.append(f"{status_emoji} Status: **{status}**  \n")
        lines.append(f"📊 Current: {week['open']} | Expected: {week['expected']} | Delta: {week['delta']:+d}  \n")
        lines.append(
            f"{net_burn_indicator} Net burn: {week['net_burn']:+d} | Required: +{week['required_burn']:.2f}/week\n"
        )

    lines.append("\n---\n")
    lines.append(f"⏰ **{weeks_remaining} weeks** remaining until **{target_date}**")

    return "\n".join(lines)


def format_project_detail(project_data: dict) -> str:
    """Format detailed view for a single project."""
    week = project_data["latest_week"]
    baseline = project_data["baseline"]
    status_emoji = STATUS_EMOJIS.get(week["status"], "⚪")

    lines = []
    lines.append(f"# 📊 {project_data['project_name']}\n")
    lines.append(f"{status_emoji} **Status: {week['status']}**\n")
    lines.append("---\n")
    lines.append(f"**📈 Current Week {week['week_number']}**  \n")
    lines.append(f"• Open bugs: {week['open']}  \n")
    lines.append(f"• Expected: {week['expected']}  \n")
    lines.append(f"• Delta: {week['delta']:+d}\n")
    lines.append("\n**📉 This Week's Activity**  \n")
    lines.append(f"• New bugs: {week['new']}  \n")
    lines.append(f"• Closed bugs: {week['closed']}  \n")
    lines.append(f"• Net burn: {week['net_burn']:+d}  \n")
    lines.append(f"• Required burn/week: +{week['required_burn']:.2f}\n")
    lines.append("\n**🎯 Baseline**  \n")
    lines.append(f"• Starting bugs: {baseline['open_count']}  \n")
    lines.append(f"• Target: {baseline['target_count']}  \n")
    lines.append(f"• Target date: {baseline['target_date']}\n")
    lines.append(f"\n⏰ {project_data['weeks_remaining']} weeks remaining")

    return "\n".join(lines)


class BugPositionBot:
    """Teams bot that provides bug position reports."""

    async def on_turn(self, turn_context: TurnContext):
        """Handle incoming activity."""
        if turn_context.activity.type == ActivityTypes.message:
            text = turn_context.activity.text.strip().lower()

            try:
                if text in ["help", "start"]:
                    await self.send_help(turn_context)
                elif text == "bugposition":
                    await self.send_bug_position(turn_context)
                elif text == "week":
                    await self.send_week_info(turn_context)
                elif text == "projects":
                    await self.send_projects_list(turn_context)
                elif text.startswith("project "):
                    project_key = text[8:].strip().replace(" ", "_")
                    await self.send_project_detail(turn_context, project_key)
                else:
                    await turn_context.send_activity(
                        "I didn't understand that command. Type **help** to see available commands."
                    )
            except Exception as e:
                logger.error(f"Error processing command: {e}", exc_info=True)
                await turn_context.send_activity(f"❌ Error: {str(e)}")

    async def send_help(self, turn_context: TurnContext):
        """Send help message."""
        help_text = """
# 👋 Bug Position Bot

I can help you track bug status across all projects.

**Available Commands:**

• **bugposition** - Show full multi-project bug report
• **week** - Show current week number
• **projects** - List all tracked projects
• **project <name>** - Show details for a specific project
• **help** - Show this help message

**Quick Start:**
Try **bugposition** to see the latest status!
"""
        await turn_context.send_activity(help_text)

    async def send_bug_position(self, turn_context: TurnContext):
        """Send bug position report."""
        logger.info(f"Bug position request from user {turn_context.activity.from_property.id}")
        projects = load_all_projects()

        if not projects:
            await turn_context.send_activity("❌ No projects found. Please ensure baseline files are deployed.")
            return

        report = format_bug_position_report(projects)
        await turn_context.send_activity(report)
        logger.info(f"Sent bug position report with {len(projects)} projects")

    async def send_week_info(self, turn_context: TurnContext):
        """Send current week information."""
        projects = load_all_projects()

        if not projects:
            await turn_context.send_activity("❌ No projects found.")
            return

        week_number = projects[0]["week_number"]
        weeks_remaining = projects[0]["weeks_remaining"]
        target_date = projects[0]["baseline"]["target_date"]

        await turn_context.send_activity(
            f"📅 **Current Week: {week_number}**\n\n" f"⏰ {weeks_remaining} weeks remaining until {target_date}"
        )

    async def send_projects_list(self, turn_context: TurnContext):
        """Send list of all tracked projects."""
        projects = load_all_projects()
        projects = sort_projects_by_status(projects)

        if not projects:
            await turn_context.send_activity("❌ No projects found.")
            return

        lines = ["# 📋 Tracked Projects\n"]

        for project in projects:
            status_emoji = STATUS_EMOJIS.get(project["latest_week"]["status"], "⚪")
            lines.append(f"{status_emoji} **{project['project_name']}** (`{project['project_key']}`)")

        lines.append("\n💡 Use **project <name>** for details")

        await turn_context.send_activity("\n".join(lines))

    async def send_project_detail(self, turn_context: TurnContext, project_key: str):
        """Send details for a specific project."""
        organization_url = get_config().get("ADO_ORGANIZATION_URL")
        pat = get_config().get_ado_config().pat

        try:
            project_data = load_project_data(project_key, organization_url, pat)
        except FileNotFoundError:
            await turn_context.send_activity(
                f"❌ Project '{project_key}' not found.\n\n" f"Use **projects** to see available projects."
            )
            return

        details = format_project_detail(project_data)
        await turn_context.send_activity(details)
        logger.info(f"Sent project details for {project_key}")


# Initialize bot
bot = BugPositionBot()

# Bot Framework Adapter Settings
APP_ID = get_config().get("MICROSOFT_APP_ID")
APP_PASSWORD = get_config().get("MICROSOFT_APP_PASSWORD")
SETTINGS = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
ADAPTER = BotFrameworkAdapter(SETTINGS)


# Error handler
async def on_error(context: TurnContext, error: Exception):
    """Handle errors."""
    logger.error(f"Error: {error}", exc_info=True)
    await context.send_activity("Sorry, an error occurred processing your request.")


ADAPTER.on_turn_error = on_error


# Web server routes
async def messages(req: Request) -> Response:
    """Handle incoming messages from Teams."""
    if req.headers.get("Content-Type", "").startswith("application/json"):
        body = await req.json()
    else:
        return Response(status=415)

    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    try:
        response = await ADAPTER.process_activity(activity, auth_header, bot.on_turn)
        if response:
            return Response(body=json.dumps(response.body), status=response.status)
        return Response(status=200)
    except Exception as e:
        logger.error(f"Error processing activity: {e}", exc_info=True)
        return Response(status=500)


async def health(req: Request) -> Response:
    """Health check endpoint."""
    return Response(text="OK", status=200)


# Create web app
app = web.Application()
app.router.add_post("/api/messages", messages)
app.router.add_get("/health", health)
app.router.add_get("/", health)


if __name__ == "__main__":
    """Start the web server."""
    try:
        # Validate configuration
        if not APP_ID or APP_ID == "your_microsoft_app_id_here":
            logger.warning("MICROSOFT_APP_ID not configured - bot will run in development mode")

        if not APP_PASSWORD or APP_PASSWORD == "your_microsoft_app_password_here":
            logger.warning("MICROSOFT_APP_PASSWORD not configured - bot will run in development mode")

        # Default port for Teams bots (can be overridden via Azure App Service configuration)
        PORT = 3978

        logger.info(f"Starting Teams Bot on port {PORT}")
        print("=" * 60)
        print(f"Teams Bug Position Bot is running on port {PORT}!")
        print("=" * 60)
        print("\nBot endpoint: http://localhost:3978/api/messages")
        print("Health check: http://localhost:3978/health")
        print("\nPress Ctrl+C to stop the bot.\n")

        web.run_app(
            app, host="0.0.0.0", port=PORT
        )  # nosec B104 - Required for Azure App Service containerized deployment

    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        print(f"\nERROR: Failed to start bot: {e}")
        sys.exit(1)
