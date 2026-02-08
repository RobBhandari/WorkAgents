"""
ArmorCode HTML Report Generator

Converts JSON vulnerability data to a styled HTML report with baseline comparison,
trend visualization, and detailed vulnerability listing.

Usage:
    python armorcode_report_to_html.py <query_json_file>
    python armorcode_report_to_html.py .tmp/armorcode_query_20260130_120000.json
    python armorcode_report_to_html.py <json_file> --output-file custom_report.html
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'.tmp/armorcode_html_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout),
    ],
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

    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    logger.info("Query data loaded successfully")
    return data


def load_tracking_history() -> list:
    """
    Load tracking history for trend visualization.

    Returns:
        list: Historical query data
    """
    tracking_file = ".tmp/armorcode_tracking.json"

    if not os.path.exists(tracking_file):
        logger.info("No tracking history found")
        return []

    with open(tracking_file, encoding="utf-8") as f:
        tracking = json.load(f)

    return tracking.get("queries", [])


def generate_html_report(data: dict, tracking_history: list) -> str:
    """
    Generate HTML report from query data.

    Args:
        data: Query data
        tracking_history: Historical tracking data

    Returns:
        str: HTML content
    """
    baseline = data["baseline"]
    target = data["target"]
    current = data["current"]
    comparison = data["comparison"]
    vulnerabilities = current["vulnerabilities"]

    # Count by severity
    critical_count = sum(1 for v in vulnerabilities if v.get("severity") == "CRITICAL")
    high_count = sum(1 for v in vulnerabilities if v.get("severity") == "HIGH")

    # Count by product
    product_counts = {}
    for v in vulnerabilities:
        product = v.get("product", "Unknown")
        product_counts[product] = product_counts.get(product, 0) + 1

    # Count by status
    status_counts = {}
    for v in vulnerabilities:
        status = v.get("status", "Unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    # Extract values for template
    baseline_date = baseline["date"]
    baseline_count = baseline["count"]
    target_date = target["date"]
    target_count = target["count"]
    target_reduction_pct = target["reduction_goal_pct"]
    current_count = current["count"]
    reduction_amount = comparison["reduction_amount"]
    reduction_pct = comparison["reduction_pct"]
    remaining_to_goal = comparison["remaining_to_goal"]
    progress_to_goal_pct = comparison["progress_to_goal_pct"]
    days_since_baseline = comparison["days_since_baseline"]
    days_to_target = comparison["days_to_target"]

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ArmorCode Vulnerability Tracking Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #f5f7fa;
            color: #2c3e50;
            padding: 20px;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        }}

        h1 {{
            font-size: 32px;
            color: #1a1a1a;
            margin-bottom: 10px;
            font-weight: 600;
        }}

        .timestamp {{
            color: #666;
            font-size: 14px;
            margin-bottom: 30px;
        }}

        /* Executive Summary */
        .executive-summary {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }}

        .summary-title {{
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 25px;
            text-align: center;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 25px;
            text-align: center;
        }}

        .summary-item {{
            background: rgba(255, 255, 255, 0.15);
            padding: 20px;
            border-radius: 8px;
            backdrop-filter: blur(10px);
        }}

        .summary-label {{
            font-size: 13px;
            opacity: 0.9;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .summary-value {{
            font-size: 36px;
            font-weight: 700;
            line-height: 1;
        }}

        .summary-unit {{
            font-size: 14px;
            opacity: 0.8;
            margin-top: 5px;
        }}

        .progress-section {{
            background: rgba(255, 255, 255, 0.15);
            padding: 20px;
            border-radius: 8px;
            backdrop-filter: blur(10px);
            margin-top: 20px;
        }}

        .progress-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        }}

        .progress-row:last-child {{
            border-bottom: none;
        }}

        .progress-label {{
            font-size: 14px;
            opacity: 0.9;
        }}

        .progress-value {{
            font-size: 18px;
            font-weight: 600;
        }}

        /* Statistics Cards */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin: 30px 0;
        }}

        .stat-card {{
            background: #fff;
            border: 2px solid #e1e8ed;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            transition: all 0.3s ease;
        }}

        .stat-card:hover {{
            border-color: #667eea;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
            transform: translateY(-2px);
        }}

        .stat-card.critical {{
            border-color: #ff4444;
            background: linear-gradient(135deg, #fff 0%, #fff5f5 100%);
        }}

        .stat-card.high {{
            border-color: #ff8800;
            background: linear-gradient(135deg, #fff 0%, #fff8f0 100%);
        }}

        .stat-label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }}

        .stat-value {{
            font-size: 36px;
            font-weight: 700;
            color: #2c3e50;
        }}

        .stat-card.critical .stat-value {{
            color: #ff4444;
        }}

        .stat-card.high .stat-value {{
            color: #ff8800;
        }}

        /* Trend Chart */
        .trend-section {{
            margin: 30px 0;
            padding: 30px;
            background: #f8f9fa;
            border-radius: 8px;
        }}

        .trend-title {{
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 20px;
            color: #2c3e50;
        }}

        .trend-table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
        }}

        .trend-table th {{
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            font-size: 14px;
        }}

        .trend-table td {{
            padding: 12px;
            border-bottom: 1px solid #e1e8ed;
            font-size: 14px;
        }}

        .trend-table tr:last-child td {{
            border-bottom: none;
        }}

        .trend-bar {{
            height: 20px;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 4px;
            margin: 5px 0;
        }}

        /* Vulnerabilities Table */
        .section-title {{
            font-size: 24px;
            font-weight: 600;
            margin: 40px 0 20px 0;
            color: #2c3e50;
        }}

        .table-controls {{
            margin-bottom: 20px;
            display: flex;
            gap: 15px;
        }}

        .search-input {{
            flex: 1;
            padding: 10px 15px;
            border: 2px solid #e1e8ed;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.3s;
        }}

        .search-input:focus {{
            outline: none;
            border-color: #667eea;
        }}

        .vulns-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }}

        .vulns-table th {{
            background: #2c3e50;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            cursor: pointer;
            user-select: none;
        }}

        .vulns-table th:hover {{
            background: #34495e;
        }}

        .vulns-table td {{
            padding: 15px;
            border-bottom: 1px solid #e1e8ed;
            font-size: 14px;
        }}

        .vulns-table tr:hover {{
            background: #f8f9fa;
        }}

        .severity-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .severity-critical {{
            background: #ff4444;
            color: white;
        }}

        .severity-high {{
            background: #ff8800;
            color: white;
        }}

        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            background: #e1e8ed;
            color: #2c3e50;
        }}

        .vuln-title {{
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 4px;
        }}

        .vuln-id {{
            font-size: 12px;
            color: #666;
        }}

        /* Footer */
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #e1e8ed;
            text-align: center;
            color: #666;
            font-size: 14px;
        }}

        /* Responsive */
        @media (max-width: 1200px) {{
            .summary-grid {{
                grid-template-columns: 1fr;
            }}
            .stats-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

        @media (max-width: 768px) {{
            .container {{
                padding: 20px;
            }}
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        /* Print styles */
        @media print {{
            body {{
                background: white;
            }}
            .container {{
                box-shadow: none;
            }}
            .search-input {{
                display: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>ArmorCode Vulnerability Tracking Report</h1>
        <div class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>

        <!-- Executive Summary -->
        <div class="executive-summary">
            <div class="summary-title">Vulnerability Reduction Progress</div>

            <div class="summary-grid">
                <div class="summary-item">
                    <div class="summary-label">Baseline ({baseline['date']})</div>
                    <div class="summary-value">{baseline['count']}</div>
                    <div class="summary-unit">vulnerabilities</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Target ({target['reduction_goal_pct']}% Reduction)</div>
                    <div class="summary-value">{target['count']}</div>
                    <div class="summary-unit">vulnerabilities</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Current</div>
                    <div class="summary-value">{current['count']}</div>
                    <div class="summary-unit">vulnerabilities</div>
                </div>
            </div>

            <div class="progress-section">
                <div class="progress-row">
                    <span class="progress-label">Vulnerabilities Reduced:</span>
                    <span class="progress-value">{comparison['reduction_amount']} ({comparison['reduction_pct']}%)</span>
                </div>
                <div class="progress-row">
                    <span class="progress-label">Remaining to Goal:</span>
                    <span class="progress-value">{comparison['remaining_to_goal']} vulnerabilities</span>
                </div>
                <div class="progress-row">
                    <span class="progress-label">Goal Progress:</span>
                    <span class="progress-value">{comparison['progress_to_goal_pct']}% of the way there</span>
                </div>
                <div class="progress-row">
                    <span class="progress-label">Days Since Baseline:</span>
                    <span class="progress-value">{comparison['days_since_baseline']} days</span>
                </div>
                <div class="progress-row">
                    <span class="progress-label">Days to Target:</span>
                    <span class="progress-value">{comparison['days_to_target']} days</span>
                </div>
            </div>
        </div>

        <!-- Statistics Cards -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total</div>
                <div class="stat-value">{current['count']}</div>
            </div>
            <div class="stat-card critical">
                <div class="stat-label">Critical</div>
                <div class="stat-value">{critical_count}</div>
            </div>
            <div class="stat-card high">
                <div class="stat-label">High</div>
                <div class="stat-value">{high_count}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Products</div>
                <div class="stat-value">{len(product_counts)}</div>
            </div>
        </div>"""

    # Add trend section if history available
    if tracking_history and len(tracking_history) > 1:
        html += """
        <!-- Trend Chart -->
        <div class="trend-section">
            <div class="trend-title">Vulnerability Trend Over Time</div>
            <table class="trend-table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Count</th>
                        <th>% of Baseline</th>
                        <th>Reduction</th>
                        <th>Trend</th>
                    </tr>
                </thead>
                <tbody>"""

        baseline_count = baseline["count"]
        for entry in tracking_history[-10:]:  # Show last 10 entries
            count = entry["count"]
            pct_of_baseline = (count / baseline_count * 100) if baseline_count > 0 else 0
            reduction_pct = entry.get("reduction_pct", 0)
            bar_width = int(pct_of_baseline)

            html += f"""
                    <tr>
                        <td>{entry['date']}</td>
                        <td>{count}</td>
                        <td>{pct_of_baseline:.1f}%</td>
                        <td>{reduction_pct:.1f}%</td>
                        <td><div class="trend-bar" style="width: {bar_width}%;"></div></td>
                    </tr>"""

        html += """
                </tbody>
            </table>
        </div>"""

    # Add vulnerabilities table
    html += f"""
        <!-- Vulnerabilities Table -->
        <h2 class="section-title">Current Vulnerabilities ({current['count']})</h2>

        <div class="table-controls">
            <input type="text" class="search-input" id="searchInput" placeholder="Search vulnerabilities..." onkeyup="filterTable()">
        </div>

        <table class="vulns-table" id="vulnsTable">
            <thead>
                <tr>
                    <th onclick="sortTable(0)">Severity ▼</th>
                    <th onclick="sortTable(1)">Product ▼</th>
                    <th onclick="sortTable(2)">Title ▼</th>
                    <th onclick="sortTable(3)">CVE/CWE ▼</th>
                    <th onclick="sortTable(4)">Status ▼</th>
                    <th onclick="sortTable(5)">First Seen ▼</th>
                </tr>
            </thead>
            <tbody>"""

    # Sort vulnerabilities: Critical first, then High
    sorted_vulns = sorted(vulnerabilities, key=lambda x: (x.get("severity") != "CRITICAL", x.get("severity") != "HIGH"))

    for vuln in sorted_vulns:
        severity = vuln.get("severity", "UNKNOWN")
        severity_class = severity.lower() if severity in ["CRITICAL", "HIGH"] else ""
        cve_cwe = ", ".join(filter(None, [vuln.get("cve"), vuln.get("cwe")]))

        html += f"""
                <tr>
                    <td><span class="severity-badge severity-{severity_class}">{severity}</span></td>
                    <td>{vuln.get('product', 'N/A')}</td>
                    <td>
                        <div class="vuln-title">{vuln.get('title', 'N/A')}</div>
                        <div class="vuln-id">{vuln.get('id', '')}</div>
                    </td>
                    <td>{cve_cwe or 'N/A'}</td>
                    <td><span class="status-badge">{vuln.get('status', 'Unknown')}</span></td>
                    <td>{vuln.get('first_seen', 'N/A')[:10] if vuln.get('first_seen') else 'N/A'}</td>
                </tr>"""

    # Close table and add JavaScript
    html += """
            </tbody>
        </table>

        <!-- Footer -->
        <div class="footer">
            <p>ArmorCode Vulnerability Tracking System | Generated from baseline: {baseline['date']}</p>
            <p>Target: {target['reduction_goal_pct']}% reduction by {target['date']}</p>
        </div>
    </div>

    <script>
        // Table search filter
        function filterTable() {{
            const input = document.getElementById('searchInput');
            const filter = input.value.toLowerCase();
            const table = document.getElementById('vulnsTable');
            const rows = table.getElementsByTagName('tr');

            for (let i = 1; i < rows.length; i++) {{
                const row = rows[i];
                const text = row.textContent || row.innerText;
                row.style.display = text.toLowerCase().includes(filter) ? '' : 'none';
            }}
        }}

        // Table sorting
        function sortTable(columnIndex) {{
            const table = document.getElementById('vulnsTable');
            const rows = Array.from(table.rows).slice(1);
            const isAscending = table.dataset.sortOrder !== 'asc';

            rows.sort((a, b) => {{
                const aText = a.cells[columnIndex].textContent.trim();
                const bText = b.cells[columnIndex].textContent.trim();
                return isAscending ? aText.localeCompare(bText) : bText.localeCompare(aText);
            }});

            rows.forEach(row => table.tBodies[0].appendChild(row));
            table.dataset.sortOrder = isAscending ? 'asc' : 'desc';
        }}
    </script>
</body>
</html>"""

    return html


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate HTML report from ArmorCode query JSON")

    parser.add_argument("json_file", type=str, help="Path to query JSON file")

    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Path to output HTML file (default: .tmp/armorcode_report_[timestamp].html)",
    )

    return parser.parse_args()


if __name__ == "__main__":
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
            output_file = f".tmp/armorcode_report_{timestamp}.html"

        # Save HTML
        os.makedirs(".tmp", exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"HTML report generated: {output_file}")
        print("\nHTML report generated successfully:")
        print(f"  {output_file}")
        print("\nOpen in browser to view the report.")

        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
