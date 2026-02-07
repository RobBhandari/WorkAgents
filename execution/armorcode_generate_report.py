"""
ArmorCode Report Generator - Create HTML Report from Weekly Query Results

Generates a clean table-based HTML report for email delivery.
"""

import json
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_status_indicator(baseline_count, current_count):
    """Get status color bar based on progress."""
    if current_count == 0 or baseline_count == 0:
        color = "#28a745"  # Green
    else:
        change_percent = (current_count - baseline_count) / baseline_count * 100
        if change_percent <= -10:
            color = "#28a745"  # Green
        elif change_percent <= 10:
            color = "#ffc107"  # Amber
        else:
            color = "#dc3545"  # Red

    # Use a table cell with background color for better email compatibility
    return f'<table cellpadding="0" cellspacing="0" style="margin: 0 auto;"><tr><td style="width: 10px; height: 40px; background: {color}; border-radius: 3px;"></td></tr></table>'


def generate_html_report(data, output_file):
    """Generate HTML report from weekly query data."""

    baseline = data.get("baseline", {})
    current = data.get("current", {})
    progress = data.get("progress", {})

    # Extract key metrics
    baseline_total = progress.get("baseline_total", 0)
    current_total = progress.get("current_total", 0)
    change = progress.get("change", 0)
    change_percent = progress.get("change_percent", 0)
    reduction_goal_percent = progress.get("reduction_goal_percent", 70)
    target_remaining = progress.get("target_remaining", 0)
    progress_percent = progress.get("progress_towards_goal", 0)
    days_tracking = progress.get("days_tracking", 0)
    days_remaining = progress.get("days_remaining", 0)

    # Extract severity breakdown
    current_critical = current.get("summary", {}).get("total_critical", 0)
    current_high = current.get("summary", {}).get("total_high", 0)

    # Generate product rows
    baseline_by_product = baseline.get("by_product", {})
    current_by_product = current.get("by_product", {})

    product_rows = []
    for product_name in sorted(baseline_by_product.keys()):
        baseline_counts = baseline_by_product.get(product_name, {})
        current_counts = current_by_product.get(product_name, {})

        baseline_prod_total = baseline_counts.get("total", 0)
        current_prod_total = current_counts.get("total", 0)
        current_prod_critical = current_counts.get("CRITICAL", 0)
        current_prod_high = current_counts.get("HIGH", 0)
        prod_change = baseline_prod_total - current_prod_total

        # Status indicator
        status_bar = get_status_indicator(baseline_prod_total, current_prod_total)

        # Change formatting
        if prod_change > 0:
            change_display = f'<span style="color: #28a745; font-weight: 600;">+{prod_change}</span>'
        elif prod_change < 0:
            change_display = f'<span style="color: #dc3545; font-weight: 600;">{prod_change}</span>'
        else:
            change_display = '<span style="color: #6c757d;">+0</span>'

        product_rows.append(f"""
        <tr>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef; font-weight: 500;">{product_name}</td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef; text-align: center;">{status_bar}</td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef; text-align: center;">{baseline_prod_total}</td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef; text-align: center; font-weight: 600;">{current_prod_total}</td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef; text-align: center;">{current_prod_critical}</td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef; text-align: center;">{current_prod_high}</td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef; text-align: center;">{change_display}</td>
        </tr>
        """)

    products_html = "".join(product_rows)

    # Overall status
    if change > 0:
        overall_status = "↑ Increased"
        status_color = "#dc3545"
    elif change < 0:
        overall_status = "↓ Decreased"
        status_color = "#28a745"
    else:
        overall_status = "→ Stable"
        status_color = "#ffc107"

    # Generate HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ArmorCode Security Report - {datetime.now().strftime('%B %d, %Y')}</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">

        <!-- Main Container -->
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 1000px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

            <!-- Header -->
            <tr>
                <td style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); padding: 30px; color: white;">
                    <h1 style="margin: 0 0 10px 0; font-size: 28px; font-weight: 600;">ArmorCode Security Report</h1>
                    <p style="margin: 0; font-size: 16px; opacity: 0.9;">{datetime.now().strftime('%B %d, %Y')}</p>
                </td>
            </tr>

            <!-- Summary Metrics -->
            <tr>
                <td style="padding: 30px 30px 20px 30px;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td width="20%" style="padding: 15px; background: #f8f9fa; border-radius: 6px; text-align: center;">
                                <div style="font-size: 12px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Baseline</div>
                                <div style="font-size: 28px; font-weight: 700; color: #333;">{baseline_total}</div>
                            </td>
                            <td width="3%"></td>
                            <td width="20%" style="padding: 15px; background: #f8f9fa; border-radius: 6px; text-align: center;">
                                <div style="font-size: 12px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Current</div>
                                <div style="font-size: 28px; font-weight: 700; color: {status_color};">{current_total}</div>
                            </td>
                            <td width="3%"></td>
                            <td width="20%" style="padding: 15px; background: #f8f9fa; border-radius: 6px; text-align: center;">
                                <div style="font-size: 12px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Target</div>
                                <div style="font-size: 28px; font-weight: 700; color: #333;">{target_remaining}</div>
                            </td>
                            <td width="3%"></td>
                            <td width="31%" style="padding: 15px; background: #f8f9fa; border-radius: 6px; text-align: center;">
                                <div style="font-size: 12px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Progress</div>
                                <div style="font-size: 28px; font-weight: 700; color: #333;">{progress_percent:.1f}%</div>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>

            <!-- Goal Info -->
            <tr>
                <td style="padding: 10px 30px 20px 30px;">
                    <div style="background: #e7f3ff; border-left: 4px solid #2a5298; padding: 12px 16px; border-radius: 4px;">
                        <strong>Goal:</strong> Reduce by {reduction_goal_percent}% to {target_remaining} vulnerabilities by {baseline.get('target_date', 'June 30, 2026')}
                        <span style="color: #6c757d; margin-left: 10px;">({days_remaining} days remaining)</span>
                    </div>
                </td>
            </tr>

            <!-- Product Breakdown Table -->
            <tr>
                <td style="padding: 0 30px 30px 30px;">
                    <h2 style="font-size: 18px; font-weight: 600; margin: 0 0 15px 0; color: #333;">Product Breakdown</h2>

                    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse; background: white; border: 1px solid #dee2e6; border-radius: 6px; overflow: hidden;">
                        <thead>
                            <tr style="background: #1e3c72; color: white;">
                                <th style="padding: 14px 16px; text-align: left; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Product</th>
                                <th style="padding: 14px 16px; text-align: center; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Status</th>
                                <th style="padding: 14px 16px; text-align: center; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Baseline</th>
                                <th style="padding: 14px 16px; text-align: center; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Current</th>
                                <th style="padding: 14px 16px; text-align: center; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Critical</th>
                                <th style="padding: 14px 16px; text-align: center; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">High</th>
                                <th style="padding: 14px 16px; text-align: center; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Net Change</th>
                            </tr>
                        </thead>
                        <tbody>
                            {products_html}
                        </tbody>
                    </table>
                </td>
            </tr>

            <!-- Footer -->
            <tr>
                <td style="padding: 20px 30px; background: #f8f9fa; border-top: 1px solid #dee2e6; text-align: center; font-size: 12px; color: #6c757d;">
                    <p style="margin: 0;">Generated by ArmorCode Weekly Report Automation</p>
                    <p style="margin: 5px 0 0 0;">Tracking Period: {baseline.get('baseline_date', 'Dec 1, 2025')} - {baseline.get('target_date', 'June 30, 2026')}</p>
                </td>
            </tr>
        </table>

    </body>
    </html>
    """

    # Write to file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"HTML report generated: {output_file}")


def main():
    """Main execution function."""

    # Find the most recent weekly query file
    tmp_dir = ".tmp"
    files = [f for f in os.listdir(tmp_dir) if f.startswith("armorcode_weekly_") and f.endswith(".json")]

    if not files:
        logger.error("No weekly query files found in .tmp directory")
        sys.exit(1)

    # Sort by date in filename and get most recent
    files.sort(reverse=True)
    latest_file = os.path.join(tmp_dir, files[0])

    logger.info(f"Loading data from: {latest_file}")

    # Load data
    with open(latest_file) as f:
        data = json.load(f)

    # Generate output filename
    date_str = datetime.now().strftime("%Y%m%d")
    output_file = os.path.join(tmp_dir, f"armorcode_report_{date_str}.html")

    # Generate report
    generate_html_report(data, output_file)

    logger.info("=" * 70)
    logger.info(f"Report generated successfully: {output_file}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
