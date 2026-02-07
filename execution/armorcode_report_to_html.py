"""
ArmorCode HTML Report Generator

Converts JSON vulnerability data to a styled HTML report with baseline comparison,
trend visualization, and detailed vulnerability listing.

Usage:
    python armorcode_report_to_html.py <query_json_file>
    python armorcode_report_to_html.py .tmp/armorcode_query_20260130_120000.json
    python armorcode_report_to_html.py <json_file> --output-file custom_report.html
"""

import os
import sys
import argparse
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'.tmp/armorcode_html_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def load_query_data(json_file: str) -> dict:
    """
    Load query data from JSON file.

    Args:
        json_file: Path to JSON file

    Returns:
        dict: Query data

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If JSON is invalid
    """
    if not os.path.exists(json_file):
        raise FileNotFoundError(f"Query file not found: {json_file}")

    logger.info(f"Loading query data from {json_file}")

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    logger.info("Query data loaded successfully")
    return data


def load_tracking_history() -> list:
    """
    Load tracking history for trend visualization.

    Returns:
        list: Historical query data
    """
    tracking_file = '.tmp/armorcode_tracking.json'

    if not os.path.exists(tracking_file):
        logger.info("No tracking history found")
        return []

    with open(tracking_file, 'r', encoding='utf-8') as f:
        tracking = json.load(f)

    return tracking.get('queries', [])


def generate_html_report(data: dict, tracking_history: list) -> str:
    """
    Generate HTML report from query data using Jinja2 templates.

    Args:
        data: Query data
        tracking_history: Historical tracking data

    Returns:
        str: HTML content

    Raises:
        RuntimeError: If template rendering fails
    """
    logger.info("Generating HTML report with Jinja2")

    try:
        # Extract data sections
        baseline = data['baseline']
        target = data['target']
        current = data['current']
        comparison = data['comparison']
        vulnerabilities = current['vulnerabilities']

        # Count by severity
        critical_count = sum(1 for v in vulnerabilities if v.get('severity') == 'CRITICAL')
        high_count = sum(1 for v in vulnerabilities if v.get('severity') == 'HIGH')

        # Count by product
        product_counts = {}
        for v in vulnerabilities:
            product = v.get('product', 'Unknown')
            product_counts[product] = product_counts.get(product, 0) + 1

        # Sort vulnerabilities: Critical first, then High
        sorted_vulns = sorted(
            vulnerabilities,
            key=lambda x: (x.get('severity') != 'CRITICAL', x.get('severity') != 'HIGH')
        )

        # Setup Jinja2 environment with auto-escaping (XSS prevention)
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
        env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml']),  # CRITICAL: Auto-escape for XSS prevention
            trim_blocks=True,
            lstrip_blocks=True
        )

        # Prepare template context
        generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        context = {
            'baseline': baseline,
            'target': target,
            'current': current,
            'comparison': comparison,
            'critical_count': critical_count,
            'high_count': high_count,
            'product_count': len(product_counts),
            'tracking_history': tracking_history,
            'sorted_vulns': sorted_vulns,
            'generated_at': generated_at
        }

        # Render template (Jinja2 auto-escapes all variables)
        template = env.get_template('armorcode_report.html')
        html = template.render(**context)

        logger.info("HTML report generated successfully with Jinja2")
        return html

    except Exception as e:
        logger.error(f"Error generating HTML report: {e}", exc_info=True)
        raise RuntimeError(f"Failed to generate HTML report: {e}") from e


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Generate HTML report from ArmorCode query JSON'
    )

    parser.add_argument(
        'json_file',
        type=str,
        help='Path to query JSON file'
    )

    parser.add_argument(
        '--output-file',
        type=str,
        default=None,
        help='Path to output HTML file (default: .tmp/armorcode_report_[timestamp].html)'
    )

    return parser.parse_args()


if __name__ == '__main__':
    """Entry point when script is run from command line."""
    try:
        args = parse_arguments()

        # Load query data
        data = load_query_data(args.json_file)

        # Load tracking history
        tracking_history = load_tracking_history()

        # Generate HTML
        html = generate_html_report(data, tracking_history)

        # Determine output file
        if args.output_file:
            output_file = args.output_file
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f'.tmp/armorcode_report_{timestamp}.html'

        # Save HTML
        os.makedirs('.tmp', exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info(f"HTML report generated: {output_file}")
        print(f"\nHTML report generated successfully:")
        print(f"  {output_file}")
        print(f"\nOpen in browser to view the report.")

        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
