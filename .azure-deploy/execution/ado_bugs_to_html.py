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

        # Step 3: Generate HTML
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Azure DevOps Bug Report - {data['project']}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .header p {{
            opacity: 0.9;
            font-size: 1.1em;
        }}

        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px 40px;
            background: #f8f9fa;
        }}

        .stat-card {{
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            text-align: center;
            transition: transform 0.3s ease;
        }}

        .stat-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 12px rgba(0,0,0,0.15);
        }}

        .stat-card h3 {{
            color: #667eea;
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .stat-card p {{
            color: #6c757d;
            font-size: 0.95em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .controls {{
            padding: 30px 40px;
            background: white;
            border-bottom: 2px solid #f0f0f0;
        }}

        .search-box {{
            width: 100%;
            padding: 15px 20px;
            font-size: 16px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            transition: border-color 0.3s ease;
        }}

        .search-box:focus {{
            outline: none;
            border-color: #667eea;
        }}

        .table-container {{
            padding: 0 40px 40px 40px;
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
        }}

        thead {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            position: sticky;
            top: 0;
            z-index: 10;
        }}

        th {{
            padding: 15px;
            text-align: left;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
            transition: background 0.3s ease;
        }}

        th:hover {{
            background: rgba(255,255,255,0.1);
        }}

        th::after {{
            content: ' ↕';
            opacity: 0.5;
            font-size: 0.8em;
        }}

        td {{
            padding: 15px;
            border-bottom: 1px solid #f0f0f0;
        }}

        tr:hover {{
            background: #f8f9fa;
        }}

        .badge {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .badge-priority-1 {{
            background: #ff4444;
            color: white;
        }}

        .badge-priority-2 {{
            background: #ff8800;
            color: white;
        }}

        .badge-priority-3 {{
            background: #ffbb33;
            color: white;
        }}

        .badge-priority-4 {{
            background: #00C851;
            color: white;
        }}

        .badge-priority-na {{
            background: #9e9e9e;
            color: white;
        }}

        .badge-state-new {{
            background: #2196F3;
            color: white;
        }}

        .badge-state-active {{
            background: #ff9800;
            color: white;
        }}

        .badge-state-resolved {{
            background: #4CAF50;
            color: white;
        }}

        .bug-id {{
            color: #667eea;
            font-weight: 600;
            font-family: 'Courier New', monospace;
        }}

        .footer {{
            padding: 20px 40px;
            background: #f8f9fa;
            text-align: center;
            color: #6c757d;
            font-size: 0.9em;
        }}

        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 1.8em;
            }}

            .stats {{
                grid-template-columns: 1fr;
            }}

            .table-container {{
                padding: 0 20px 20px 20px;
            }}

            th, td {{
                padding: 10px;
                font-size: 0.9em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🐛 Azure DevOps Bug Report</h1>
            <p>{data['project']}</p>
            <p style="font-size: 0.9em; margin-top: 10px; opacity: 0.8;">Generated: {datetime.fromisoformat(data['queried_at'].replace('Z', '+00:00')).strftime('%B %d, %Y at %I:%M %p')}</p>
        </div>

        <div class="stats">
            <div class="stat-card">
                <h3>{data['bug_count']}</h3>
                <p>Total Bugs</p>
            </div>"""

        # Add state count cards
        for state, count in sorted(state_counts.items()):
            html += f"""
            <div class="stat-card">
                <h3>{count}</h3>
                <p>{state}</p>
            </div>"""

        html += """
        </div>

        <div class="controls">
            <input type="text" id="searchBox" class="search-box" placeholder="🔍 Search bugs by ID, title, state, or priority..." onkeyup="filterTable()">
        </div>

        <div class="table-container">
            <table id="bugTable">
                <thead>
                    <tr>
                        <th onclick="sortTable(0)">ID</th>
                        <th onclick="sortTable(1)">Priority</th>
                        <th onclick="sortTable(2)">State</th>
                        <th onclick="sortTable(3)">Title</th>
                    </tr>
                </thead>
                <tbody>"""

        # Add bug rows
        for bug in data["bugs"]:
            priority = bug.get("priority", "N/A")
            priority_class = f"badge-priority-{priority}" if priority != "N/A" else "badge-priority-na"
            state_class = f'badge-state-{bug["state"].lower()}'

            html += f"""
                    <tr>
                        <td><span class="bug-id">#{bug['id']}</span></td>
                        <td><span class="badge {priority_class}">{priority}</span></td>
                        <td><span class="badge {state_class}">{bug['state']}</span></td>
                        <td>{bug['title']}</td>
                    </tr>"""

        html += f"""
                </tbody>
            </table>
        </div>

        <div class="footer">
            <p>📊 Report generated from Azure DevOps | <strong>{data['organization']}</strong></p>
        </div>
    </div>

    <script>
        function filterTable() {{
            const input = document.getElementById('searchBox');
            const filter = input.value.toLowerCase();
            const table = document.getElementById('bugTable');
            const tr = table.getElementsByTagName('tr');

            for (let i = 1; i < tr.length; i++) {{
                const row = tr[i];
                const text = row.textContent || row.innerText;

                if (text.toLowerCase().indexOf(filter) > -1) {{
                    row.style.display = '';
                }} else {{
                    row.style.display = 'none';
                }}
            }}
        }}

        function sortTable(columnIndex) {{
            const table = document.getElementById('bugTable');
            const tbody = table.tBodies[0];
            const rows = Array.from(tbody.rows);

            const sortedRows = rows.sort((a, b) => {{
                const aValue = a.cells[columnIndex].textContent.trim();
                const bValue = b.cells[columnIndex].textContent.trim();

                // Try to parse as numbers
                const aNum = parseInt(aValue.replace(/[^0-9]/g, ''));
                const bNum = parseInt(bValue.replace(/[^0-9]/g, ''));

                if (!isNaN(aNum) && !isNaN(bNum)) {{
                    return aNum - bNum;
                }}

                return aValue.localeCompare(bValue);
            }});

            // Toggle sort direction
            if (table.dataset.lastSort === String(columnIndex)) {{
                sortedRows.reverse();
                table.dataset.lastSort = '';
            }} else {{
                table.dataset.lastSort = String(columnIndex);
            }}

            // Re-append sorted rows
            sortedRows.forEach(row => tbody.appendChild(row));
        }}
    </script>
</body>
</html>"""

        # Step 4: Write HTML file
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
        Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Convert ADO bug JSON to modern HTML report")

    parser.add_argument("input_file", type=str, help="Path to input JSON file")

    parser.add_argument(
        "--output-file",
        type=str,
        default=f'.tmp/ado_bugs_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html',
        help="Path to output HTML file (default: .tmp/ado_bugs_report_[timestamp].html)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    """
    Entry point when script is run from command line.
    """
    try:
        # Parse command-line arguments
        args = parse_arguments()

        # Ensure .tmp directory exists
        os.makedirs(".tmp", exist_ok=True)

        # Generate HTML report
        output_file = generate_html_report(json_file=args.input_file, output_file=args.output_file)

        print(f"\n{'='*60}")
        print("HTML Report Generated Successfully")
        print(f"{'='*60}")
        print(f"Output file: {output_file}")
        print("\nOpen this file in your web browser to view the interactive report.")
        print(f"{'='*60}\n")

        # Exit with success code
        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
