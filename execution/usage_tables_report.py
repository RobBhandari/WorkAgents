"""
LGL AI Tools Usage Tables Report Generator

Reads the git-tracked CSV file from data/ai_usage_data.csv, filters for LGL users,
and generates a modern, interactive HTML report with two side-by-side tables showing
Claude and Devin usage with heatmap styling.

Update data/ai_usage_data.csv weekly with the latest usage data.

Usage:
    python execution/usage_tables_report.py
    python execution/usage_tables_report.py --output-file report.html
    python execution/usage_tables_report.py --open
"""

import os
import sys
import argparse
import logging
import html as html_module
from datetime import datetime
from typing import Tuple
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'.tmp/usage_tables_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def read_excel_usage_data(file_path: str) -> pd.DataFrame:
    """
    Read Excel or CSV file and validate required columns exist.

    Args:
        file_path: Path to Excel/CSV file containing usage data

    Returns:
        pd.DataFrame: Cleaned DataFrame with usage data

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If required columns are missing
    """
    logger.info(f"Reading file: {file_path}")

    # Validate file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        # Detect file type and read accordingly
        file_ext = Path(file_path).suffix.lower()

        if file_ext == '.csv':
            df = pd.read_csv(file_path)
            logger.info(f"Successfully read CSV file with {len(df)} rows")
        elif file_ext in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path, engine='openpyxl')
            logger.info(f"Successfully read Excel file with {len(df)} rows")
        else:
            raise ValueError(f"Unsupported file type: {file_ext}. Please use .csv, .xlsx, or .xls")

        logger.info(f"Available columns: {list(df.columns)}")

    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        raise ValueError(f"Error reading file: {e}") from e

    # Validate required columns (check for variations)
    required_columns = {
        'Name': 'Name',
        'Software Company': 'Software Company',
        'Claude Access': None,  # Will find the right variant
        'Claude 30 day usage': 'Claude 30 day usage',
        'Devin_30d': 'Devin_30d'
    }

    # Find Claude Access column (with or without space before ?)
    claude_access_col = None
    for col in df.columns:
        if col in ['Claude Access?', 'Claude Access ?']:
            claude_access_col = col
            break

    if not claude_access_col:
        raise ValueError(
            f"Missing 'Claude Access?' or 'Claude Access ?' column\n"
            f"Available columns: {list(df.columns)}"
        )

    # Find Devin Access column (with or without space before ?)
    devin_access_col = None
    for col in df.columns:
        if col in ['Devin Access?', 'Devin Access ?']:
            devin_access_col = col
            break

    if not devin_access_col:
        raise ValueError(
            f"Missing 'Devin Access?' or 'Devin Access ?' column\n"
            f"Available columns: {list(df.columns)}"
        )

    # Verify other required columns exist
    missing = []
    for req_col in ['Name', 'Software Company', 'Claude 30 day usage', 'Devin_30d']:
        if req_col not in df.columns:
            missing.append(req_col)

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}\n"
            f"Available columns: {list(df.columns)}"
        )

    # Standardize the access column names
    df = df.rename(columns={
        claude_access_col: 'Claude Access',
        devin_access_col: 'Devin Access'
    })
    logger.info(f"Using column '{claude_access_col}' for Claude Access")
    logger.info(f"Using column '{devin_access_col}' for Devin Access")

    # Clean data
    # Strip whitespace from string columns
    for col in ['Name', 'Software Company', 'Claude Access', 'Devin Access']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Handle missing usage values (treat as 0)
    df['Claude 30 day usage'] = pd.to_numeric(df['Claude 30 day usage'], errors='coerce').fillna(0)
    df['Devin_30d'] = pd.to_numeric(df['Devin_30d'], errors='coerce').fillna(0)

    logger.info(f"Data cleaned successfully")
    return df


def filter_lgl_users(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter DataFrame for Software Company = 'LGL'.

    Args:
        df: DataFrame with usage data

    Returns:
        pd.DataFrame: Filtered DataFrame containing only LGL users

    Raises:
        ValueError: If no LGL users found
    """
    logger.info("Filtering for Software Company = 'LGL'")

    # Filter for LGL (case-insensitive)
    filtered_df = df[df['Software Company'].str.upper() == 'LGL'].copy()

    if len(filtered_df) == 0:
        raise ValueError("No LGL users found in dataset")

    logger.info(f"Found {len(filtered_df)} LGL users out of {len(df)} total users")
    return filtered_df


def prepare_claude_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare Claude usage table data.

    Args:
        df: Filtered DataFrame with LGL users

    Returns:
        pd.DataFrame: DataFrame sorted by Claude usage (descending)
    """
    # Select relevant columns
    claude_df = df[['Name', 'Job Title', 'Claude Access', 'Claude 30 day usage']].copy()

    # Sort by usage (descending)
    claude_df = claude_df.sort_values('Claude 30 day usage', ascending=False)

    # Reset index
    claude_df = claude_df.reset_index(drop=True)

    logger.info(f"Prepared Claude table with {len(claude_df)} users")
    logger.info(f"Claude usage range: {claude_df['Claude 30 day usage'].min():.0f} - {claude_df['Claude 30 day usage'].max():.0f}")

    return claude_df


def prepare_devin_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare Devin usage table data.

    Args:
        df: Filtered DataFrame with LGL users

    Returns:
        pd.DataFrame: DataFrame sorted by Devin usage (descending)
    """
    # Select relevant columns
    devin_df = df[['Name', 'Job Title', 'Devin Access', 'Devin_30d']].copy()

    # Sort by usage (descending)
    devin_df = devin_df.sort_values('Devin_30d', ascending=False)

    # Reset index
    devin_df = devin_df.reset_index(drop=True)

    logger.info(f"Prepared Devin table with {len(devin_df)} users")
    logger.info(f"Devin usage range: {devin_df['Devin_30d'].min():.0f} - {devin_df['Devin_30d'].max():.0f}")

    return devin_df


def get_usage_heatmap_color(usage: float) -> Tuple[str, str, str]:
    """
    Determine heatmap color based on usage value.

    Thresholds (per user requirement):
    - Low (RED): usage < 20
    - Medium (AMBER): 20 <= usage < 100
    - High (GREEN): usage >= 100

    Args:
        usage: Usage count value

    Returns:
        Tuple of (background_color, text_color, intensity_class)
    """
    if usage >= 100:
        # High - Green
        return '#d1fae5', '#065f46', 'high'
    elif usage >= 20:
        # Medium - Amber
        return '#fef3c7', '#92400e', 'medium'
    else:
        # Low - Red
        return '#fee2e2', '#991b1b', 'low'


def generate_table_html(df: pd.DataFrame, table_id: str, title: str, usage_column: str, access_column: str) -> str:
    """
    Generate HTML for a single usage table.

    Args:
        df: DataFrame with table data
        table_id: HTML ID for the table
        title: Table title
        usage_column: Name of the usage column
        access_column: Name of the access column

    Returns:
        str: HTML string for the table section
    """
    html = f"""
            <div class="table-card">
                <h2>{html_module.escape(title)}</h2>
                <table id="{table_id}" class="usage-table">
                    <thead>
                        <tr>
                            <th onclick="sortTable('{table_id}', 0)">Name</th>
                            <th onclick="sortTable('{table_id}', 1)">Job Title</th>
                            <th onclick="sortTable('{table_id}', 2)">Access</th>
                            <th onclick="sortTable('{table_id}', 3)">Usage (30 days)</th>
                        </tr>
                    </thead>
                    <tbody>"""

    # Generate rows
    for _, row in df.iterrows():
        name = html_module.escape(str(row['Name']))
        job_title = html_module.escape(str(row['Job Title']))
        access = str(row[access_column]).strip()
        usage = float(row[usage_column])

        # Get heatmap color
        bg_color, text_color, intensity = get_usage_heatmap_color(usage)

        # Access badge (handle both text and numeric values)
        # Treat NaN, empty, or 0 as "No"
        if access.upper() in ['YES', '1', '1.0']:
            access_badge = '<span class="badge badge-success">Yes</span>'
        elif access.upper() in ['NO', '0', '0.0', 'NAN', 'NONE', '']:
            access_badge = '<span class="badge badge-secondary">No</span>'
        else:
            access_badge = '<span class="badge badge-secondary">No</span>'

        html += f"""
                        <tr>
                            <td>{name}</td>
                            <td>{job_title}</td>
                            <td>{access_badge}</td>
                            <td class="heatmap-cell"
                                style="background-color: {bg_color}; color: {text_color};"
                                data-value="{usage}">
                                {int(usage)}
                            </td>
                        </tr>"""

    html += """
                    </tbody>
                </table>
            </div>"""

    return html


def generate_html_report(claude_df: pd.DataFrame, devin_df: pd.DataFrame, output_file: str) -> str:
    """
    Generate complete HTML report with both tables.

    Args:
        claude_df: DataFrame with Claude usage data
        devin_df: DataFrame with Devin usage data
        output_file: Path to output HTML file

    Returns:
        str: Path to generated HTML file
    """
    logger.info("Generating HTML report")

    # Calculate statistics
    total_users = len(claude_df)
    claude_users = len(claude_df[claude_df['Claude 30 day usage'] > 0])
    devin_users = len(devin_df[devin_df['Devin_30d'] > 0])
    avg_claude_usage = claude_df['Claude 30 day usage'].mean()
    avg_devin_usage = devin_df['Devin_30d'].mean()

    # Generate report date
    report_date = datetime.now().strftime('%B %d, %Y at %I:%M %p')

    # Generate Claude table HTML
    claude_table_html = generate_table_html(
        claude_df,
        'claudeTable',
        'Claude Usage (Last 30 Days)',
        'Claude 30 day usage',
        'Claude Access'
    )

    # Generate Devin table HTML
    devin_table_html = generate_table_html(
        devin_df,
        'devinTable',
        'Devin Usage (Last 30 Days)',
        'Devin_30d',
        'Devin Access'
    )

    # Complete HTML document
    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LGL AI Tools Usage Report</title>
    <style>
        :root {{
            --bg-primary: #f9fafb;
            --bg-secondary: #ffffff;
            --bg-tertiary: #f9fafb;
            --text-primary: #1f2937;
            --text-secondary: #6b7280;
            --border-color: #e5e7eb;
            --shadow: rgba(0,0,0,0.1);
        }}

        [data-theme="dark"] {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-tertiary: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #cbd5e1;
            --border-color: #475569;
            --shadow: rgba(0,0,0,0.3);
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-primary);
            padding: 20px;
            color: var(--text-primary);
            transition: background-color 0.3s ease, color 0.3s ease;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px var(--shadow);
        }}

        .header h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .header .subtitle {{
            font-size: 1.1rem;
            opacity: 0.9;
        }}

        .header .timestamp {{
            font-size: 0.9rem;
            opacity: 0.8;
            margin-top: 10px;
        }}

        .theme-toggle {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 8px 16px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 4px 12px var(--shadow);
            z-index: 1000;
            transition: all 0.3s ease;
        }}

        .theme-toggle:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 16px var(--shadow);
        }}

        #theme-icon {{
            font-size: 1.2rem;
        }}

        #theme-label {{
            font-size: 0.9rem;
            color: var(--text-primary);
            font-weight: 600;
        }}

        .stats-card {{
            background: var(--bg-secondary);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}

        .stat-card {{
            background: var(--bg-tertiary);
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid #667eea;
        }}

        .stat-card .value {{
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 8px;
            font-variant-numeric: tabular-nums;
        }}

        .stat-card .label {{
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            font-weight: 600;
        }}

        .legend-card {{
            background: var(--bg-secondary);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .legend-card h3 {{
            font-size: 1.25rem;
            margin-bottom: 16px;
            color: var(--text-primary);
        }}

        .legend-content {{
            display: flex;
            align-items: center;
            gap: 20px;
            flex-wrap: wrap;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.9rem;
        }}

        .legend-box {{
            width: 20px;
            height: 20px;
            border-radius: 4px;
            display: inline-block;
        }}

        .legend-green {{
            background-color: #d1fae5;
            border: 2px solid #065f46;
        }}

        .legend-amber {{
            background-color: #fef3c7;
            border: 2px solid #92400e;
        }}

        .legend-red {{
            background-color: #fee2e2;
            border: 2px solid #991b1b;
        }}

        .search-card {{
            background: var(--bg-secondary);
            padding: 20px 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .search-box {{
            width: 100%;
            padding: 14px 20px;
            font-size: 1rem;
            border: 2px solid var(--border-color);
            border-radius: 8px;
            transition: all 0.3s ease;
            background: var(--bg-primary);
            color: var(--text-primary);
        }}

        .search-box:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}

        .tables-container {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }}

        @media (max-width: 1200px) {{
            .tables-container {{
                grid-template-columns: 1fr;
            }}
        }}

        .table-card {{
            background: var(--bg-secondary);
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .table-card h2 {{
            font-size: 1.5rem;
            margin-bottom: 20px;
            color: var(--text-primary);
        }}

        .usage-table {{
            width: 100%;
            border-collapse: collapse;
        }}

        .usage-table thead {{
            background: var(--bg-tertiary);
        }}

        .usage-table th {{
            padding: 14px 16px;
            text-align: left;
            font-weight: 600;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            border-bottom: 2px solid var(--border-color);
            cursor: pointer;
            user-select: none;
        }}

        .usage-table th:hover {{
            background: var(--bg-secondary);
        }}

        .usage-table th:nth-child(3), .usage-table th:nth-child(4) {{
            text-align: center;
        }}

        .usage-table td {{
            padding: 14px 16px;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-primary);
        }}

        .usage-table td:nth-child(3), .usage-table td:nth-child(4) {{
            text-align: center;
        }}

        .usage-table tbody tr:hover {{
            background: var(--bg-tertiary);
        }}

        .heatmap-cell {{
            font-weight: 700;
            border-radius: 4px;
        }}

        .badge {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 600;
        }}

        .badge-success {{
            background-color: #10b981;
            color: white;
        }}

        .badge-secondary {{
            background-color: #6b7280;
            color: white;
        }}

        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 1.8rem;
            }}

            .stats-grid {{
                grid-template-columns: 1fr;
            }}

            .tables-container {{
                grid-template-columns: 1fr;
            }}

            .usage-table th,
            .usage-table td {{
                padding: 10px 12px;
                font-size: 0.85rem;
            }}
        }}
    </style>
</head>
<body>
    <button class="theme-toggle" onclick="toggleTheme()" id="themeToggle">
        <span id="theme-icon">☀️</span>
        <span id="theme-label">Light Mode</span>
    </button>

    <div class="container">
        <div class="header">
            <h1>🤖 LGL AI Tools Usage Report</h1>
            <p class="subtitle">Software Company: LGL</p>
            <p class="timestamp">Generated: {report_date}</p>
        </div>

        <div class="stats-card">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="value">{total_users}</div>
                    <div class="label">Total LGL Users</div>
                </div>
                <div class="stat-card">
                    <div class="value">{claude_users}</div>
                    <div class="label">Claude Active Users</div>
                </div>
                <div class="stat-card">
                    <div class="value">{devin_users}</div>
                    <div class="label">Devin Active Users</div>
                </div>
                <div class="stat-card">
                    <div class="value">{avg_claude_usage:.0f}</div>
                    <div class="label">Avg Claude Usage</div>
                </div>
                <div class="stat-card">
                    <div class="value">{avg_devin_usage:.0f}</div>
                    <div class="label">Avg Devin Usage</div>
                </div>
            </div>
        </div>

        <div class="legend-card">
            <h3>📊 Usage Intensity Legend</h3>
            <div class="legend-content">
                <div class="legend-item">
                    <span class="legend-box legend-green"></span>
                    <strong>High (≥100 uses)</strong>
                </div>
                <div class="legend-item">
                    <span class="legend-box legend-amber"></span>
                    <strong>Medium (20-99 uses)</strong>
                </div>
                <div class="legend-item">
                    <span class="legend-box legend-red"></span>
                    <strong>Low (&lt;20 uses)</strong>
                </div>
            </div>
        </div>

        <div class="search-card">
            <input type="text"
                   id="globalSearch"
                   class="search-box"
                   placeholder="🔍 Search by name across both tables..."
                   onkeyup="filterAllTables()">
        </div>

        <div class="tables-container">
{claude_table_html}
{devin_table_html}
        </div>
    </div>

    <script>
        function filterAllTables() {{
            const input = document.getElementById('globalSearch');
            const filter = input.value.toLowerCase();

            // Filter both tables
            const tables = ['claudeTable', 'devinTable'];

            tables.forEach(tableId => {{
                const table = document.getElementById(tableId);
                const rows = table.getElementsByTagName('tr');

                for (let i = 1; i < rows.length; i++) {{
                    const nameCell = rows[i].cells[0];
                    if (nameCell) {{
                        const name = nameCell.textContent.toLowerCase();
                        if (name.includes(filter)) {{
                            rows[i].style.display = '';
                        }} else {{
                            rows[i].style.display = 'none';
                        }}
                    }}
                }}
            }});
        }}

        function sortTable(tableId, columnIndex) {{
            const table = document.getElementById(tableId);
            const tbody = table.tBodies[0];
            const rows = Array.from(tbody.rows);

            const isNumeric = columnIndex === 3;  // Usage column (now at index 3)

            rows.sort((a, b) => {{
                let aValue, bValue;

                if (isNumeric) {{
                    aValue = parseFloat(a.cells[columnIndex].getAttribute('data-value') || 0);
                    bValue = parseFloat(b.cells[columnIndex].getAttribute('data-value') || 0);
                    return bValue - aValue;  // Descending
                }} else {{
                    aValue = a.cells[columnIndex].textContent.trim();
                    bValue = b.cells[columnIndex].textContent.trim();
                    return aValue.localeCompare(bValue);
                }}
            }});

            // Toggle direction on repeated clicks
            if (table.dataset.lastSort === String(columnIndex)) {{
                rows.reverse();
                table.dataset.lastSort = '';
            }} else {{
                table.dataset.lastSort = String(columnIndex);
            }}

            rows.forEach(row => tbody.appendChild(row));
        }}

        // Theme toggle functionality
        function toggleTheme() {{
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);

            updateThemeButton(newTheme);
        }}

        function updateThemeButton(theme) {{
            const icon = document.getElementById('theme-icon');
            const label = document.getElementById('theme-label');

            if (theme === 'dark') {{
                icon.textContent = '☀️';
                label.textContent = 'Light Mode';
            }} else {{
                icon.textContent = '🌙';
                label.textContent = 'Dark Mode';
            }}
        }}

        // Set dark mode as default on page load
        (function() {{
            const html = document.documentElement;
            const savedTheme = localStorage.getItem('theme');

            // If no saved preference, default to dark mode
            const theme = savedTheme || 'dark';

            html.setAttribute('data-theme', theme);
            updateThemeButton(theme);
        }})();
    </script>
</body>
</html>"""

    # Write HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info(f"HTML report created successfully: {output_file}")

    # Also save a copy as "latest" in dashboards directory for trends dashboard linking
    latest_file = Path('.tmp/observatory/dashboards/usage_tables_latest.html')
    try:
        # Ensure dashboards directory exists
        latest_file.parent.mkdir(parents=True, exist_ok=True)
        with open(latest_file, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info(f"Latest copy saved to: {latest_file}")
    except Exception as e:
        logger.warning(f"Failed to save latest copy: {e}")

    return output_file


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Generate LGL AI Tools usage tables report from hardcoded CSV file'
    )

    parser.add_argument(
        '--output-file',
        type=str,
        default=f'.tmp/usage_tables_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html',
        help='Path to output HTML file (default: .tmp/usage_tables_[timestamp].html)'
    )

    parser.add_argument(
        '--open',
        action='store_true',
        help='Open HTML report in browser after generation'
    )

    return parser.parse_args()


if __name__ == '__main__':
    """
    Entry point when script is run from command line.
    """
    try:
        # Parse command-line arguments
        args = parse_arguments()

        # Ensure .tmp directory exists
        os.makedirs('.tmp', exist_ok=True)

        # Use git-tracked CSV file in data directory
        file_path = "data/ai_usage_data.csv"
        logger.info(f"Using git-tracked CSV file: {file_path}")

        # Step 1: Read Excel file
        df = read_excel_usage_data(file_path)

        # Step 2: Filter for LGL users
        lgl_df = filter_lgl_users(df)

        # Step 3: Prepare Claude data
        claude_df = prepare_claude_data(lgl_df)

        # Step 4: Prepare Devin data
        devin_df = prepare_devin_data(lgl_df)

        # Step 5: Generate HTML report
        output_file = generate_html_report(
            claude_df=claude_df,
            devin_df=devin_df,
            output_file=args.output_file
        )

        print(f"\n{'='*70}")
        print(f"SUCCESS: LGL AI Tools Usage Report Generated")
        print(f"{'='*70}")
        print(f"Output file: {output_file}")
        print(f"\nStatistics:")
        print(f"  • Total LGL Users: {len(lgl_df)}")
        print(f"  • Claude Active Users: {len(claude_df[claude_df['Claude 30 day usage'] > 0])}")
        print(f"  • Devin Active Users: {len(devin_df[devin_df['Devin_30d'] > 0])}")
        print(f"\nOpen this file in your web browser to view the interactive report.")
        print(f"{'='*70}\n")

        # Open in browser if requested
        if args.open:
            import webbrowser
            webbrowser.open(f'file://{os.path.abspath(output_file)}')
            logger.info("Opened report in browser")

        # Exit with success code
        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
