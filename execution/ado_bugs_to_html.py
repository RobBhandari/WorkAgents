"""
Azure DevOps Bugs to HTML Report

Converts JSON bug query results to a modern, interactive HTML report.

Usage:
    python ado_bugs_to_html.py input.json
    python ado_bugs_to_html.py input.json --output-file report.html
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'.tmp/ado_html_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def generate_html_report(json_file: str, output_file: str) -> str:
    """
    Generate a modern HTML report from JSON bug data.

    Args:
        json_file: Path to input JSON file
        output_file: Path to output HTML file

    Returns:
        str: Path to generated HTML file

    Raises:
        ValueError: If input validation fails
        RuntimeError: If report generation fails
    """
    logger.info(f"Generating HTML report from {json_file}")

    try:
        # Step 1: Read JSON file
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)

        # Step 2: Calculate statistics
        state_counts = {}
        priority_counts = {}
        for bug in data["bugs"]:
            state = bug["state"]
            priority = bug.get("priority", "N/A")
            state_counts[state] = state_counts.get(state, 0) + 1
            priority_counts[str(priority)] = priority_counts.get(str(priority), 0) + 1

        logger.info(f"Processing {data['bug_count']} bugs")

        # Step 3: Setup Jinja2 environment with auto-escaping
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
        env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"]),  # CRITICAL: Auto-escape for XSS prevention
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Step 4: Prepare template context
        generated_at = datetime.fromisoformat(data["queried_at"].replace("Z", "+00:00")).strftime(
            "%B %d, %Y at %I:%M %p"
        )

        context = {
            "project_name": data["project"],
            "bug_count": data["bug_count"],
            "state_counts": state_counts,
            "priority_counts": priority_counts,
            "bugs": data["bugs"],
            "organization": data["organization"],
            "generated_at": generated_at,
        }

        # Step 5: Render template (Jinja2 auto-escapes all variables)
        template = env.get_template("ado_bugs_report.html")
        html = template.render(**context)

        # Step 6: Write HTML file
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"HTML report created successfully: {output_file}")
        return output_file

    except FileNotFoundError as e:
        logger.error(f"Input file not found: {e}")
        raise ValueError(f"Input file not found: {json_file}") from e
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON file: {e}")
        raise ValueError(f"Invalid JSON format in {json_file}") from e
    except Exception as e:
        logger.error(f"Error generating HTML report: {e}", exc_info=True)
        raise RuntimeError(f"Failed to generate HTML report: {e}") from e


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Convert Azure DevOps bugs JSON to HTML report")
    parser.add_argument("json_file", type=str, help="Path to input JSON file (from ado_query_bugs.py)")
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Path to output HTML file (default: .tmp/ado_bugs_report_TIMESTAMP.html)",
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()

    # Determine output file
    if args.output_file:
        output_file = args.output_file
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f".tmp/ado_bugs_report_{timestamp}.html"

    # Ensure .tmp directory exists
    os.makedirs(".tmp", exist_ok=True)

    # Generate report
    try:
        result = generate_html_report(args.json_file, output_file)
        print("\n[OK] HTML report generated successfully!")
        print(f"  Location: {result}")
        print("\nOpen the file in your browser to view the report.")
    except (ValueError, RuntimeError) as e:
        print(f"\n[FAIL] Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
