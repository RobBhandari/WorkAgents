"""
AI Tools Usage Tables Report Generator

Generates interactive HTML report for AI usage data with two modes:
1. Interactive Mode (default): HTML with IMPORT CSV button for browser-based file upload
2. CLI Mode: Direct processing with --file argument

Features:
- Filters for target team users
- Side-by-side Claude and Devin usage tables
- Heatmap styling (red/amber/green)
- Sortable columns and search functionality
- Mobile-responsive dashboard framework
- Client-side CSV processing (data never leaves your computer)

NOTE: data/ai_usage_data.csv is gitignored (contains sensitive employee data).

Usage:
    # Interactive mode (generates HTML with IMPORT button)
    python execution/reports/usage_tables_report.py
    python execution/reports/usage_tables_report.py --open

    # CLI mode (direct processing)
    python execution/reports/usage_tables_report.py --file data/ai_usage_data.csv
    python execution/reports/usage_tables_report.py --file mydata.xlsx --open
"""

import argparse
import logging
import os
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from execution.framework import get_dashboard_framework
from execution.reports.usage_tables.data_loader import read_excel_usage_data
from execution.reports.usage_tables.data_processor import (
    calculate_summary_stats,
    filter_team_users,
    prepare_claude_data,
    prepare_devin_data,
)
from execution.reports.usage_tables.interactive_uploader import (
    generate_data_processing_js,
    generate_file_upload_handler_js,
    generate_import_button_html,
    generate_import_button_styles,
    generate_papaparse_script_tag,
    generate_placeholder_html,
    generate_utility_functions_js,
)
from execution.reports.usage_tables.table_generator import generate_table_html

# Load environment variables
load_dotenv()

# Configurable team filter - update as needed for your organization
TEAM_FILTER = "TARGET_TEAM"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'.tmp/usage_tables_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def generate_html_report_with_data(claude_df, devin_df, output_file: str) -> str:
    """
    Generate HTML report with provided data.

    Args:
        claude_df: DataFrame with Claude usage data
        devin_df: DataFrame with Devin usage data
        output_file: Path to output HTML file

    Returns:
        str: Path to generated HTML file
    """
    logger.info("Generating HTML report with data")

    # Calculate statistics
    stats = calculate_summary_stats(claude_df, devin_df)

    # Generate tables
    claude_table_html = generate_table_html(
        claude_df, "claudeTable", "Claude Usage (Last 30 Days)", "Claude 30 day usage", "Claude Access"
    )
    devin_table_html = generate_table_html(
        devin_df, "devinTable", "Devin Usage (Last 30 Days)", "Devin_30d", "Devin Access"
    )

    # Get framework CSS/JS
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#667eea",
        header_gradient_end="#764ba2",
        include_table_scroll=True,
        include_expandable_rows=False,
        include_glossary=False,
    )

    # Generate report date
    report_date = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    # Build complete HTML
    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Tools Usage Report</title>
    {framework_css}
</head>
<body>
    <button class="theme-toggle" onclick="toggleTheme()" id="themeToggle">
        <span id="theme-icon">☀️</span>
        <span id="theme-label">Light Mode</span>
    </button>

    <div class="container">
        <div class="header">
            <h1>🤖 AI Tools Usage Report</h1>
            <p class="subtitle">Team Metrics</p>
            <p class="timestamp">Generated: {report_date}</p>
        </div>

        <div class="stats-card">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="value">{stats['total_users']}</div>
                    <div class="label">Total Team Users</div>
                </div>
                <div class="stat-card">
                    <div class="value">{stats['claude_active_users']}</div>
                    <div class="label">Claude Active Users</div>
                </div>
                <div class="stat-card">
                    <div class="value">{stats['devin_active_users']}</div>
                    <div class="label">Devin Active Users</div>
                </div>
                <div class="stat-card">
                    <div class="value">{int(stats['avg_claude_usage'])}</div>
                    <div class="label">Avg Claude Usage</div>
                </div>
                <div class="stat-card">
                    <div class="value">{int(stats['avg_devin_usage'])}</div>
                    <div class="label">Avg Devin Usage</div>
                </div>
            </div>
        </div>

        <div class="tables-container">
            {claude_table_html}
            {devin_table_html}
        </div>
    </div>

    {framework_js}
</body>
</html>"""

    # Write HTML file
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"HTML report created: {output_file}")

    # Also save as latest
    latest_file = Path(".tmp/observatory/dashboards/usage_tables_latest.html")
    try:
        latest_file.parent.mkdir(parents=True, exist_ok=True)
        with open(latest_file, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"Latest copy saved to: {latest_file}")
    except Exception as e:
        logger.warning(f"Failed to save latest copy: {e}")

    return str(output_path)


def generate_interactive_html(output_file: str) -> str:
    """
    Generate interactive HTML with CSV import capability.

    Args:
        output_file: Path to save the HTML file

    Returns:
        str: Path to generated HTML file
    """
    logger.info("Generating interactive HTML with import capability")

    # Get framework CSS/JS
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#667eea",
        header_gradient_end="#764ba2",
        include_table_scroll=True,
        include_expandable_rows=False,
        include_glossary=False,
    )

    # Generate report date
    report_date = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    # Build HTML with interactive components
    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Tools Usage Report - Import Data</title>
    {generate_papaparse_script_tag()}
    {framework_css}
    <style>
        {generate_import_button_styles()}
    </style>
</head>
<body>
    <button class="theme-toggle" onclick="toggleTheme()" id="themeToggle">
        <span id="theme-icon">☀️</span>
        <span id="theme-label">Light Mode</span>
    </button>

    {generate_import_button_html()}

    <div class="container">
        <div class="header">
            <h1>🤖 AI Tools Usage Report</h1>
            <p class="subtitle">Team Metrics</p>
            <p class="timestamp">Generated: {report_date}</p>
        </div>

        {generate_placeholder_html()}

        <div id="content" class="hidden">
            <div class="stats-card">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="value" id="total-users">0</div>
                        <div class="label">Total Team Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="value" id="claude-users">0</div>
                        <div class="label">Claude Active Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="value" id="devin-users">0</div>
                        <div class="label">Devin Active Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="value" id="avg-claude">0</div>
                        <div class="label">Avg Claude Usage</div>
                    </div>
                    <div class="stat-card">
                        <div class="value" id="avg-devin">0</div>
                        <div class="label">Avg Devin Usage</div>
                    </div>
                </div>
            </div>

            <div class="tables-container">
                <div class="table-card">
                    <h2>Claude Usage (Last 30 Days)</h2>
                    <div class="table-wrapper">
                        <table id="claudeTable" class="usage-table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Job Title</th>
                                    <th>Access</th>
                                    <th>Usage (30 days)</th>
                                </tr>
                            </thead>
                            <tbody id="claudeTableBody"></tbody>
                        </table>
                    </div>
                </div>

                <div class="table-card">
                    <h2>Devin Usage (Last 30 Days)</h2>
                    <div class="table-wrapper">
                        <table id="devinTable" class="usage-table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Job Title</th>
                                    <th>Access</th>
                                    <th>Usage (30 days)</th>
                                </tr>
                            </thead>
                            <tbody id="devinTableBody"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    {framework_js}
    <script>
        {generate_file_upload_handler_js(TEAM_FILTER)}
        {generate_data_processing_js(TEAM_FILTER)}
        {generate_utility_functions_js()}
    </script>
</body>
</html>"""

    # Write HTML file
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"Interactive HTML with import capability created: {output_file}")

    # Also save as latest
    latest_file = Path(".tmp/observatory/dashboards/usage_tables_latest.html")
    try:
        latest_file.parent.mkdir(parents=True, exist_ok=True)
        with open(latest_file, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"Latest copy saved to: {latest_file}")
    except Exception as e:
        logger.warning(f"Failed to save latest copy: {e}")

    return str(output_path)


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate AI Tools usage tables report from CSV/Excel file")

    parser.add_argument(
        "--file",
        type=str,
        required=False,
        help="Path to CSV or Excel file with AI usage data (optional - if not provided, generates interactive HTML with import button)",
    )

    parser.add_argument(
        "--output-file",
        type=str,
        default=f'.tmp/usage_tables_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html',
        help="Path to output HTML file (default: .tmp/usage_tables_[timestamp].html)",
    )

    parser.add_argument("--open", action="store_true", help="Open HTML report in browser after generation")

    return parser.parse_args()


def main():
    """Main entry point for the report generator."""
    try:
        # Parse command-line arguments
        args = parse_arguments()

        # Ensure .tmp directory exists
        os.makedirs(".tmp", exist_ok=True)

        # Check if file is provided
        if not args.file:
            # No file provided - generate interactive HTML with import button
            logger.info("No data file provided - generating interactive HTML with import capability")
            output_file = generate_interactive_html(args.output_file)

            print(f"\n{'='*70}")
            print("SUCCESS: Interactive AI Tools Usage Report Generated")
            print(f"{'='*70}")
            print(f"Output file: {output_file}")
            print("\nTo use this report:")
            print("  1. Open the HTML file in your web browser")
            print("  2. Click the 'IMPORT CSV' button in the top-right corner")
            print("  3. Select your AI usage data CSV file")
            print("  4. View the generated tables instantly")
            print("\nAll processing happens in your browser - data never leaves your computer!")
            print(f"{'='*70}\n")

            # Open in browser if requested
            if args.open:
                webbrowser.open(f"file://{os.path.abspath(output_file)}")
                logger.info("Opened report in browser")

            sys.exit(0)

        # CLI Mode: Process file directly
        logger.info(f"Using data file: {args.file}")

        # Pipeline: Load → Filter → Process → Generate
        df = read_excel_usage_data(args.file)
        team_df = filter_team_users(df, TEAM_FILTER)
        claude_df = prepare_claude_data(team_df)
        devin_df = prepare_devin_data(team_df)
        output_file = generate_html_report_with_data(claude_df, devin_df, args.output_file)

        # Print success message
        stats = calculate_summary_stats(claude_df, devin_df)
        print(f"\n{'='*70}")
        print("SUCCESS: AI Tools Usage Report Generated")
        print(f"{'='*70}")
        print(f"Output file: {output_file}")
        print("\nStatistics:")
        print(f"  • Total Team Users: {stats['total_users']}")
        print(f"  • Claude Active Users: {stats['claude_active_users']}")
        print(f"  • Devin Active Users: {stats['devin_active_users']}")
        print("\nOpen this file in your web browser to view the interactive report.")
        print(f"{'='*70}\n")

        # Open in browser if requested
        if args.open:
            webbrowser.open(f"file://{os.path.abspath(output_file)}")
            logger.info("Opened report in browser")

        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        logger.error(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
