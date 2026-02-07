"""
Microsoft Teams Bug Position Bot

Provides instant bug position reports via Microsoft Teams.
Reuses the multi-project report logic for consistency.

Setup:
1. Install: pip install botbuilder-core aiohttp
2. Create Azure Bot Service
3. Configure bot credentials in .env
4. Deploy to Azure App Service
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

import os
import sys
import json
import glob
import logging
from datetime import datetime
from typing import List
from aiohttp import web
from aiohttp.web import Request, Response
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity, ActivityTypes, Attachment, CardAction, HeroCard
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'.tmp/teams_bot_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Status emojis
STATUS_EMOJIS = {
    'GREEN': '🟢',
    'AMBER': '🟠',
    'RED': '🔴'
}

# Status sort order
STATUS_ORDER = {
    'GREEN': 0,
    'AMBER': 1,
    'RED': 2
}


def discover_projects() -> List[str]:
    """Discover all projects by finding baseline files."""
    baseline_files = glob.glob('.tmp/baseline_*.json')
    project_keys = []
    for file in baseline_files:
        project_key = os.path.basename(file).replace('baseline_', '').replace('.json', '')
        project_keys.append(project_key)
    return project_keys


def load_project_data(project_key: str) -> dict:
    """Load baseline and latest weekly tracking for a project."""
    baseline_file = f'.tmp/baseline_{project_key}.json'
    tracking_file = f'.tmp/weekly_tracking_{project_key}.json'

    if not os.path.exists(baseline_file):
        raise FileNotFoundError(f"Baseline not found for project '{project_key}'")

    if not os.path.exists(tracking_file):
        raise FileNotFoundError(f"Weekly tracking not found for project '{project_key}'")

    with open(baseline_file, 'r', encoding='utf-8') as f:
        baseline = json.load(f)

    with open(tracking_file, 'r', encoding='utf-8') as f:
        tracking = json.load(f)

    weeks = tracking.get('weeks', [])
    if not weeks:
        raise ValueError(f"No weekly data found for project '{project_key}'")

    latest_week = weeks[-1]

    return {
        'project_key': project_key,
        'project_name': baseline.get('project', project_key),
        'baseline': baseline,
        'latest_week': latest_week,
        'week_number': latest_week['week_number'],
        'weeks_remaining': baseline['weeks_to_target'] - latest_week['week_number']
    }


def load_all_projects(project_keys: List[str] = None) -> List[dict]:
    """Load data for all projects."""
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


def sort_projects_by_status(projects: List[dict]) -> List[dict]:
    """Sort projects by RAG status (GREEN, AMBER, RED)."""
    def get_sort_key(project):
        status = project['latest_week']['status']
        return STATUS_ORDER.get(status, 99)
    return sorted(projects, key=get_sort_key)


def format_bug_position_report(projects: List[dict]) -> str:
    """Format bug position report for Teams."""
    projects = sort_projects_by_status(projects)

    if not projects:
        return "❌ No projects found. Please run baseline and tracker scripts first."

    week_number = projects[0]['week_number']
    weeks_remaining = projects[0]['weeks_remaining']
    target_date = projects[0]['baseline']['target_date']

    lines = []
    lines.append(f"# 🐛 Bug Position Report - Week {week_number}\n")
    lines.append(f"📅 {datetime.now().strftime('%B %d, %Y')}\n")
    lines.append("---\n")

    current_status = None
    for project in projects:
        week = project['latest_week']
        baseline = project['baseline']
        status = week['status']

        if current_status != status:
            if current_status is not None:
                lines.append("\n")
            current_status = status

        status_emoji = STATUS_EMOJIS.get(status, '⚪')
        net_burn_indicator = "🔥" if week['net_burn'] > 0 else "❄️"

        lines.append(f"**{project['project_name']}**  \n")
        lines.append(f"{status_emoji} Status: **{status}**  \n")
        lines.append(f"📊 Current: {week['open']} | Expected: {week['expected']} | Delta: {week['delta']:+d}  \n")
        lines.append(f"{net_burn_indicator} Net burn: {week['net_burn']:+d} | Required: +{week['required_burn']:.2f}/week\n")

    lines.append("\n---\n")
    lines.append(f"⏰ **{weeks_remaining} weeks** remaining until **{target_date}**")

    return "\n".join(lines)


def format_project_detail(project_data: dict) -> str:
    """Format detailed view for a single project."""
    week = project_data['latest_week']
    baseline = project_data['baseline']
    status_emoji = STATUS_EMOJIS.get(week['status'], '⚪')

    lines = []
    lines.append(f"# 📊 {project_data['project_name']}\n")
    lines.append(f"{status_emoji} **Status: {week['status']}**\n")
    lines.append("---\n")
    lines.append(f"**📈 Current Week {week['week_number']}**  \n")
    lines.append(f"• Open bugs: {week['open']}  \n")
    lines.append(f"• Expected: {week['expected']}  \n")
    lines.append(f"• Delta: {week['delta']:+d}\n")
    lines.append(f"\n**📉 This Week's Activity**  \n")
    lines.append(f"• New bugs: {week['new']}  \n")
    lines.append(f"• Closed bugs: {week['closed']}  \n")
    lines.append(f"• Net burn: {week['net_burn']:+d}  \n")
    lines.append(f"• Required burn/week: +{week['required_burn']:.2f}\n")
    lines.append(f"\n**🎯 Baseline (Dec 2025)**  \n")
    lines.append(f"• Starting bugs: {baseline['open_count']}  \n")
    lines.append(f"• Target (Jun 2026): {baseline['target_count']}  \n")
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
                if text in ['help', 'start']:
                    await self.send_help(turn_context)
                elif text == 'bugposition':
                    await self.send_bug_position(turn_context)
                elif text == 'week':
                    await self.send_week_info(turn_context)
                elif text == 'projects':
                    await self.send_projects_list(turn_context)
                elif text.startswith('project '):
                    project_key = text[8:].strip().replace(' ', '_')
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
            await turn_context.send_activity("❌ No projects found. Please run baseline and tracker scripts first.")
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

        week_number = projects[0]['week_number']
        weeks_remaining = projects[0]['weeks_remaining']
        target_date = projects[0]['baseline']['target_date']

        await turn_context.send_activity(
            f"📅 **Current Week: {week_number}**\n\n"
            f"⏰ {weeks_remaining} weeks remaining until {target_date}"
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
            status_emoji = STATUS_EMOJIS.get(project['latest_week']['status'], '⚪')
            lines.append(f"{status_emoji} **{project['project_name']}** (`{project['project_key']}`)")

        lines.append("\n💡 Use **project <name>** for details")

        await turn_context.send_activity("\n".join(lines))

    async def send_project_detail(self, turn_context: TurnContext, project_key: str):
        """Send details for a specific project."""
        try:
            project_data = load_project_data(project_key)
        except FileNotFoundError:
            await turn_context.send_activity(
                f"❌ Project '{project_key}' not found.\n\n"
                f"Use **projects** to see available projects."
            )
            return

        details = format_project_detail(project_data)
        await turn_context.send_activity(details)
        logger.info(f"Sent project details for {project_key}")


# Initialize bot
bot = BugPositionBot()

# Bot Framework Adapter Settings
APP_ID = os.getenv('MICROSOFT_APP_ID', '')
APP_PASSWORD = os.getenv('MICROSOFT_APP_PASSWORD', '')
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
    if req.headers.get("Content-Type") == "application/json":
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
        if not APP_ID or APP_ID == 'your_microsoft_app_id_here':
            logger.warning("MICROSOFT_APP_ID not configured - bot will run in development mode")

        if not APP_PASSWORD or APP_PASSWORD == 'your_microsoft_app_password_here':
            logger.warning("MICROSOFT_APP_PASSWORD not configured - bot will run in development mode")

        PORT = int(os.getenv('PORT', 3978))

        logger.info(f"Starting Teams Bot on port {PORT}")
        print("=" * 60)
        print(f"Teams Bug Position Bot is running on port {PORT}!")
        print("=" * 60)
        print("\nBot endpoint: http://localhost:3978/api/messages")
        print("Health check: http://localhost:3978/health")
        print("\nPress Ctrl+C to stop the bot.\n")

        web.run_app(app, host='0.0.0.0', port=PORT)

    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        print(f"\nERROR: Failed to start bot: {e}")
        sys.exit(1)
