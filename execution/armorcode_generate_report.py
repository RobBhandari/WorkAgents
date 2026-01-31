"""
ArmorCode Report Generator - Create HTML Report from Weekly Query Results

Generates a visual HTML report showing progress towards vulnerability reduction goal.
"""

import os
import sys
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_html_report(data, output_file):
    """Generate HTML report from weekly query data."""

    baseline = data.get('baseline', {})
    current = data.get('current', {})
    progress = data.get('progress', {})

    # Extract key metrics
    baseline_total = progress.get('baseline_total', 0)
    current_total = progress.get('current_total', 0)
    change = progress.get('change', 0)
    change_percent = progress.get('change_percent', 0)
    reduction_goal_percent = progress.get('reduction_goal_percent', 70)
    target_remaining = progress.get('target_remaining', 0)
    progress_percent = progress.get('progress_towards_goal', 0)
    days_tracking = progress.get('days_tracking', 0)
    days_remaining = progress.get('days_remaining', 0)

    # Extract severity breakdown
    current_critical = current.get('summary', {}).get('total_critical', 0)
    current_high = current.get('summary', {}).get('total_high', 0)
    baseline_critical = baseline.get('summary', {}).get('total_critical', 0)
    baseline_high = baseline.get('summary', {}).get('total_high', 0)

    # Determine status
    if change > 0:
        status_color = "#28a745"  # Green
        status_text = "Improving"
        trend_icon = "↓"
    elif change < 0:
        status_color = "#dc3545"  # Red
        status_text = "Worsening"
        trend_icon = "↑"
    else:
        status_color = "#ffc107"  # Yellow
        status_text = "Stable"
        trend_icon = "→"

    # Progress bar color
    if progress_percent >= 100:
        progress_color = "#28a745"  # Green - goal achieved
    elif progress_percent >= 50:
        progress_color = "#17a2b8"  # Blue - on track
    else:
        progress_color = "#ffc107"  # Yellow - needs attention

    # Generate product rows
    baseline_by_product = baseline.get('by_product', {})
    current_by_product = current.get('by_product', {})

    product_rows = []
    for product_name in sorted(baseline_by_product.keys()):
        baseline_counts = baseline_by_product.get(product_name, {})
        current_counts = current_by_product.get(product_name, {})

        baseline_prod_total = baseline_counts.get('total', 0)
        current_prod_total = current_counts.get('total', 0)
        current_prod_critical = current_counts.get('CRITICAL', 0)
        current_prod_high = current_counts.get('HIGH', 0)
        prod_change = baseline_prod_total - current_prod_total
        prod_change_percent = (prod_change / baseline_prod_total * 100) if baseline_prod_total > 0 else 0

        if prod_change > 0:
            prod_trend = f'<span style="color: #28a745;">↓ {prod_change} ({prod_change_percent:+.0f}%)</span>'
        elif prod_change < 0:
            prod_trend = f'<span style="color: #dc3545;">↑ {abs(prod_change)} ({prod_change_percent:+.0f}%)</span>'
        else:
            prod_trend = '<span style="color: #6c757d;">→ 0 (0%)</span>'

        product_rows.append(f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #dee2e6;">{product_name}</td>
            <td style="padding: 12px; border-bottom: 1px solid #dee2e6; text-align: center;">{baseline_prod_total}</td>
            <td style="padding: 12px; border-bottom: 1px solid #dee2e6; text-align: center;">{current_prod_total}</td>
            <td style="padding: 12px; border-bottom: 1px solid #dee2e6; text-align: center;">{current_prod_critical}</td>
            <td style="padding: 12px; border-bottom: 1px solid #dee2e6; text-align: center;">{current_prod_high}</td>
            <td style="padding: 12px; border-bottom: 1px solid #dee2e6; text-align: center;">{prod_trend}</td>
        </tr>
        """)

    products_html = ''.join(product_rows)

    # Generate HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ArmorCode Security Report - {datetime.now().strftime('%Y-%m-%d')}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f8f9fa;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 10px;
                margin-bottom: 30px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            .header h1 {{
                margin: 0 0 10px 0;
                font-size: 32px;
            }}
            .header p {{
                margin: 5px 0;
                opacity: 0.9;
                font-size: 16px;
            }}
            .card {{
                background: white;
                border-radius: 8px;
                padding: 25px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .metric-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }}
            .metric {{
                text-align: center;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 8px;
            }}
            .metric-value {{
                font-size: 36px;
                font-weight: bold;
                margin: 10px 0;
            }}
            .metric-label {{
                color: #6c757d;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .progress-container {{
                background: #e9ecef;
                border-radius: 10px;
                height: 40px;
                margin: 20px 0;
                position: relative;
                overflow: hidden;
            }}
            .progress-bar {{
                background: {progress_color};
                height: 100%;
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: bold;
                transition: width 0.3s ease;
                width: {min(progress_percent, 100)}%;
            }}
            .progress-text {{
                position: absolute;
                width: 100%;
                text-align: center;
                line-height: 40px;
                font-weight: bold;
                color: #333;
                z-index: 1;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
            th {{
                background: #f8f9fa;
                padding: 15px;
                text-align: left;
                font-weight: 600;
                border-bottom: 2px solid #dee2e6;
            }}
            td {{
                padding: 12px;
                border-bottom: 1px solid #dee2e6;
            }}
            .status-badge {{
                display: inline-block;
                padding: 6px 12px;
                border-radius: 20px;
                font-weight: 600;
                font-size: 14px;
                background: {status_color};
                color: white;
            }}
            .footer {{
                text-align: center;
                color: #6c757d;
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #dee2e6;
                font-size: 14px;
            }}
            h2 {{
                color: #333;
                margin-top: 0;
                font-size: 24px;
            }}
            .summary-text {{
                font-size: 18px;
                margin: 15px 0;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🛡️ ArmorCode Security Report</h1>
            <p><strong>Report Date:</strong> {datetime.now().strftime('%B %d, %Y')}</p>
            <p><strong>Baseline Date:</strong> {baseline.get('baseline_date', 'N/A')}</p>
            <p><strong>Target Date:</strong> {baseline.get('target_date', 'N/A')}</p>
        </div>

        <div class="card">
            <h2>📊 Executive Summary</h2>
            <div class="summary-text">
                Status: <span class="status-badge">{trend_icon} {status_text}</span>
            </div>
            <div class="summary-text">
                <strong>{current_total}</strong> vulnerabilities currently open
                ({change:+d} from baseline of {baseline_total})
            </div>
            <div class="summary-text">
                <strong>Goal:</strong> Reduce by {reduction_goal_percent}% to {target_remaining} vulnerabilities
            </div>
        </div>

        <div class="card">
            <h2>🎯 Progress Towards Goal</h2>
            <div class="progress-container">
                <div class="progress-text">{progress_percent:.1f}% Complete</div>
                <div class="progress-bar"></div>
            </div>
            <div class="metric-grid">
                <div class="metric">
                    <div class="metric-label">Baseline</div>
                    <div class="metric-value">{baseline_total}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Current</div>
                    <div class="metric-value" style="color: {status_color};">{current_total}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Target</div>
                    <div class="metric-value">{target_remaining}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Remaining</div>
                    <div class="metric-value">{current_total - target_remaining}</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>⏱️ Timeline</h2>
            <div class="metric-grid">
                <div class="metric">
                    <div class="metric-label">Days Tracking</div>
                    <div class="metric-value">{days_tracking}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Days Remaining</div>
                    <div class="metric-value">{days_remaining}</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>📋 Product Breakdown</h2>
            <table>
                <thead>
                    <tr>
                        <th>Product</th>
                        <th style="text-align: center;">Baseline</th>
                        <th style="text-align: center;">Current</th>
                        <th style="text-align: center;">Critical</th>
                        <th style="text-align: center;">High</th>
                        <th style="text-align: center;">Change</th>
                    </tr>
                </thead>
                <tbody>
                    {products_html}
                </tbody>
            </table>
        </div>

        <div class="footer">
            <p>Generated by ArmorCode Security Tracking System</p>
            <p>Legal Products - HIGH + CRITICAL Vulnerabilities (OPEN + CONFIRMED)</p>
        </div>
    </body>
    </html>
    """

    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info(f"HTML report generated: {output_file}")
    return output_file


def main():
    """Main execution."""
    try:
        # Find most recent weekly query file
        import glob
        query_files = glob.glob('.tmp/armorcode_weekly_*.json')

        if not query_files:
            logger.error("No weekly query files found. Run armorcode_weekly_query.py first.")
            sys.exit(1)

        # Use most recent file
        latest_file = max(query_files, key=os.path.getctime)
        logger.info(f"Loading data from: {latest_file}")

        with open(latest_file, 'r') as f:
            data = json.load(f)

        # Generate report
        output_file = f'.tmp/armorcode_report_{datetime.now().strftime("%Y%m%d")}.html'
        generate_html_report(data, output_file)

        logger.info("="*70)
        logger.info(f"Report generated successfully: {output_file}")
        logger.info("="*70)

        return output_file

    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
