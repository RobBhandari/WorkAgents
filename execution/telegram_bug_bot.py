"""
Telegram Bug Position Bot

Responds to Telegram commands to provide instant bug position reports.
Reuses the multi-project report logic for consistency.

Setup:
1. Install: pip install python-telegram-bot
2. Create bot with @BotFather on Telegram
3. Add TELEGRAM_BOT_TOKEN to .env file
4. Run: python telegram_bug_bot.py

Commands:
- /start - Welcome message and help
- /bugposition - Full multi-project bug position report
- /week - Current week number
- /project <name> - Details for specific project

Usage:
    python telegram_bug_bot.py
"""

import glob
import json
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

from execution.core import get_config

# Import telegram library
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes
except ImportError:
    print("ERROR: python-telegram-bot not installed")
    print("Please run: pip install python-telegram-bot")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'.tmp/telegram_bot_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Status emojis
STATUS_EMOJIS = {"GREEN": "🟢", "AMBER": "🟠", "RED": "🔴"}

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
        project_key = os.path.basename(file).replace("baseline_", "").replace(".json", "")
        project_keys.append(project_key)

    return project_keys


def load_project_data(project_key: str) -> dict:
    """
    Load baseline and latest weekly tracking for a project.

    Args:
        project_key: Project key

    Returns:
        dict: Combined project data with baseline and latest week
    """
    baseline_file = f".tmp/baseline_{project_key}.json"
    tracking_file = f".tmp/weekly_tracking_{project_key}.json"

    if not os.path.exists(baseline_file):
        raise FileNotFoundError(f"Baseline not found for project '{project_key}'")

    if not os.path.exists(tracking_file):
        raise FileNotFoundError(f"Weekly tracking not found for project '{project_key}'")

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


def format_bug_position_report(projects: list[dict]) -> str:
    """
    Format bug position report for Telegram (plain text with emojis).

    Args:
        projects: List of project data (already sorted)

    Returns:
        str: Formatted report for Telegram
    """
    # Sort projects by status
    projects = sort_projects_by_status(projects)

    if not projects:
        return "❌ No projects found. Please run baseline and tracker scripts first."

    # Calculate week number (should be same for all projects)
    week_number = projects[0]["week_number"]
    weeks_remaining = projects[0]["weeks_remaining"]
    target_date = projects[0]["baseline"]["target_date"]

    # Build report
    lines = []
    lines.append(f"🐛 <b>Bug Position Report - Week {week_number}</b>")
    lines.append(f"📅 {datetime.now().strftime('%B %d, %Y')}")
    lines.append("")

    # Group by status
    current_status = None
    for project in projects:
        week = project["latest_week"]
        baseline = project["baseline"]
        status = week["status"]

        # Add separator between status groups
        if current_status != status:
            if current_status is not None:
                lines.append("─" * 50)
            current_status = status

        # Project row
        status_emoji = STATUS_EMOJIS.get(status, "⚪")
        net_burn_indicator = "🔥" if week["net_burn"] > 0 else "❄️"

        lines.append(f"<b>{project['project_name']}</b>")
        lines.append(f"  {status_emoji} Status: {status}")
        lines.append(f"  📊 Current: {week['open']} | Expected: {week['expected']} | Delta: {week['delta']:+d}")
        lines.append(
            f"  {net_burn_indicator} Net burn: {week['net_burn']:+d} | Required: +{week['required_burn']:.2f}/week"
        )
        lines.append("")

    # Footer
    lines.append("═" * 50)
    lines.append(f"⏰ <b>{weeks_remaining} weeks</b> remaining until <b>{target_date}</b>")

    return "\n".join(lines)


def format_project_detail(project_data: dict) -> str:
    """
    Format detailed view for a single project.

    Args:
        project_data: Project data dictionary

    Returns:
        str: Formatted project details
    """
    week = project_data["latest_week"]
    baseline = project_data["baseline"]
    status_emoji = STATUS_EMOJIS.get(week["status"], "⚪")

    lines = []
    lines.append(f"📊 <b>{project_data['project_name']}</b>")
    lines.append("")
    lines.append(f"{status_emoji} <b>Status: {week['status']}</b>")
    lines.append("")
    lines.append(f"📈 <b>Current Week {week['week_number']}</b>")
    lines.append(f"  • Open bugs: {week['open']}")
    lines.append(f"  • Expected: {week['expected']}")
    lines.append(f"  • Delta: {week['delta']:+d}")
    lines.append("")
    lines.append("📉 <b>This Week's Activity</b>")
    lines.append(f"  • New bugs: {week['new']}")
    lines.append(f"  • Closed bugs: {week['closed']}")
    lines.append(f"  • Net burn: {week['net_burn']:+d}")
    lines.append(f"  • Required burn/week: +{week['required_burn']:.2f}")
    lines.append("")
    lines.append("🎯 <b>Baseline (Dec 2025)</b>")
    lines.append(f"  • Starting bugs: {baseline['open_count']}")
    lines.append(f"  • Target (Jun 2026): {baseline['target_count']}")
    lines.append(f"  • Target date: {baseline['target_date']}")
    lines.append("")
    lines.append(f"⏰ {project_data['weeks_remaining']} weeks remaining")

    return "\n".join(lines)


# Command Handlers


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /start command.
    """
    welcome_text = """
👋 <b>Welcome to Bug Position Bot!</b>

I can help you track bug status across all projects.

<b>Available Commands:</b>

/bugposition - Show full multi-project bug report
/week - Show current week number
/project &lt;name&gt; - Show details for a specific project
/projects - List all tracked projects
/help - Show this help message

<b>Quick Start:</b>
Try /bugposition to see the latest status!
"""
    await update.message.reply_text(welcome_text, parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /help command.
    """
    await start_command(update, context)


async def bugposition_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /bugposition command - show full multi-project report.
    """
    try:
        logger.info(f"Bug position request from user {update.effective_user.id}")

        # Load all projects
        projects = load_all_projects()

        if not projects:
            await update.message.reply_text(
                "❌ No projects found. Please run baseline and tracker scripts first.", parse_mode="HTML"
            )
            return

        # Format and send report
        report = format_bug_position_report(projects)
        await update.message.reply_text(report, parse_mode="HTML")

        logger.info(f"Sent bug position report with {len(projects)} projects")

    except Exception as e:
        logger.error(f"Error generating bug position report: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error generating report: {str(e)}", parse_mode="HTML")


async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /week command - show current week number.
    """
    try:
        projects = load_all_projects()

        if not projects:
            await update.message.reply_text("❌ No projects found.")
            return

        week_number = projects[0]["week_number"]
        weeks_remaining = projects[0]["weeks_remaining"]
        target_date = projects[0]["baseline"]["target_date"]

        await update.message.reply_text(
            f"📅 <b>Current Week: {week_number}</b>\n\n" f"⏰ {weeks_remaining} weeks remaining until {target_date}",
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error(f"Error getting week info: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def projects_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /projects command - list all tracked projects.
    """
    try:
        projects = load_all_projects()
        projects = sort_projects_by_status(projects)

        if not projects:
            await update.message.reply_text("❌ No projects found.")
            return

        lines = ["📋 <b>Tracked Projects:</b>\n"]

        for project in projects:
            status_emoji = STATUS_EMOJIS.get(project["latest_week"]["status"], "⚪")
            lines.append(f"{status_emoji} <code>{project['project_key']}</code> - {project['project_name']}")

        lines.append("\n💡 Use /project &lt;name&gt; for details")

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error listing projects: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def project_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /project <name> command - show details for specific project.
    """
    try:
        if not context.args:
            await update.message.reply_text(
                "❌ Please specify a project key.\n\n"
                "Usage: /project &lt;project_key&gt;\n"
                "Example: /project Access_Legal_Case_Management\n\n"
                "Use /projects to see available projects.",
                parse_mode="HTML",
            )
            return

        project_key = " ".join(context.args).replace(" ", "_")

        # Try to load the specific project
        try:
            project_data = load_project_data(project_key)
        except FileNotFoundError:
            await update.message.reply_text(
                f"❌ Project '{project_key}' not found.\n\n" f"Use /projects to see available projects.",
                parse_mode="HTML",
            )
            return

        # Format and send project details
        details = format_project_detail(project_data)
        await update.message.reply_text(details, parse_mode="HTML")

        logger.info(f"Sent project details for {project_key}")

    except Exception as e:
        logger.error(f"Error getting project details: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {str(e)}")


def main():
    """
    Main entry point - start the Telegram bot.
    """
    # Get bot token from environment
    bot_token = get_config().get("TELEGRAM_BOT_TOKEN")

    if not bot_token or bot_token == "your_telegram_bot_token_here":
        print("\n" + "=" * 60)
        print("ERROR: TELEGRAM_BOT_TOKEN not configured")
        print("=" * 60)
        print("\nPlease follow these steps:\n")
        print("1. Open Telegram and search for @BotFather")
        print("2. Send /newbot command")
        print("3. Follow prompts to create your bot")
        print("4. Copy the bot token")
        print("5. Add to .env file:")
        print("   TELEGRAM_BOT_TOKEN=your_token_here")
        print("\n" + "=" * 60)
        sys.exit(1)

    try:
        # Create application
        logger.info("Starting Telegram bot...")
        application = Application.builder().token(bot_token).build()

        # Register command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("bugposition", bugposition_command))
        application.add_handler(CommandHandler("week", week_command))
        application.add_handler(CommandHandler("projects", projects_command))
        application.add_handler(CommandHandler("project", project_command))

        logger.info("Bot started successfully! Press Ctrl+C to stop.")
        print("\n" + "=" * 60)
        print("Bug Position Bot is running!")
        print("=" * 60)
        print("\nGo to Telegram and send /start to your bot to begin.")
        print("Press Ctrl+C to stop the bot.\n")

        # Start the bot
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        print(f"\nERROR: Failed to start bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
