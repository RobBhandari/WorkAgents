"""
Organization Structure Report Generator

Reads an Excel file and generates a modern HTML report showing
manager-employee relationships, grouped by manager.
"""

import argparse
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'.tmp/org_report_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Modern HTML template
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}

        h1 {{
            color: #2d3748;
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 10px;
        }}

        .subtitle {{
            color: #718096;
            font-size: 1.1rem;
        }}

        .stats {{
            display: flex;
            gap: 20px;
            margin-top: 20px;
            flex-wrap: wrap;
        }}

        .stat {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 25px;
            border-radius: 12px;
            font-weight: 600;
        }}

        .stat-number {{
            font-size: 2rem;
            display: block;
        }}

        .stat-label {{
            font-size: 0.9rem;
            opacity: 0.9;
        }}

        .manager-card {{
            background: white;
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 24px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .manager-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 30px rgba(0,0,0,0.12);
        }}

        .manager-header {{
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 2px solid #e2e8f0;
        }}

        .manager-icon {{
            width: 60px;
            height: 60px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.8rem;
            margin-right: 20px;
            color: white;
        }}

        .manager-info {{
            flex: 1;
        }}

        .manager-name {{
            font-size: 1.5rem;
            font-weight: 700;
            color: #2d3748;
            margin-bottom: 5px;
        }}

        .employee-count {{
            color: #718096;
            font-size: 0.95rem;
        }}

        .employees {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 15px;
        }}

        .employee {{
            background: #f7fafc;
            padding: 15px 20px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            transition: background 0.2s;
        }}

        .employee:hover {{
            background: #edf2f7;
        }}

        .employee-icon {{
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.1rem;
            margin-right: 12px;
            flex-shrink: 0;
        }}

        .employee-name {{
            color: #2d3748;
            font-weight: 500;
            font-size: 0.95rem;
        }}

        .no-manager {{
            background: linear-gradient(135deg, #fc8181 0%, #f56565 100%);
        }}

        footer {{
            text-align: center;
            color: white;
            margin-top: 40px;
            opacity: 0.9;
        }}

        @media (max-width: 768px) {{
            h1 {{
                font-size: 2rem;
            }}

            .employees {{
                grid-template-columns: 1fr;
            }}

            .stats {{
                flex-direction: column;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{title}</h1>
            <p class="subtitle">Organization structure report generated on {date}</p>
            <div class="stats">
                <div class="stat">
                    <span class="stat-number">{total_managers}</span>
                    <span class="stat-label">Managers</span>
                </div>
                <div class="stat">
                    <span class="stat-number">{total_employees}</span>
                    <span class="stat-label">Total Employees</span>
                </div>
            </div>
        </header>

        {manager_sections}

        <footer>
            <p>Generated by Agentic Organization Structure Report</p>
        </footer>
    </div>
</body>
</html>
"""

MANAGER_SECTION_TEMPLATE = """
        <div class="manager-card">
            <div class="manager-header">
                <div class="manager-icon {no_manager_class}">
                    {icon}
                </div>
                <div class="manager-info">
                    <div class="manager-name">{manager_name}</div>
                    <div class="employee-count">{employee_count} direct report{plural}</div>
                </div>
            </div>
            <div class="employees">
                {employees}
            </div>
        </div>
"""

EMPLOYEE_TEMPLATE = """
                <div class="employee">
                    <div class="employee-icon">👤</div>
                    <div class="employee-name">{name}</div>
                </div>
"""


def read_excel_file(file_path: str, name_column: str, manager_column: str) -> pd.DataFrame:
    """
    Read Excel file and extract relevant columns.

    Args:
        file_path: Path to Excel file
        name_column: Name of the column containing employee names
        manager_column: Name of the column containing manager names

    Returns:
        DataFrame with name and manager columns

    Raises:
        RuntimeError: If file cannot be read or columns don't exist
    """
    logger.info(f"Reading Excel file: {file_path}")

    try:
        # Try reading the file
        if file_path.endswith(".xlsx"):
            df = pd.read_excel(file_path, engine="openpyxl")
        elif file_path.endswith(".xls"):
            df = pd.read_excel(file_path, engine="xlrd")
        else:
            df = pd.read_excel(file_path)

        logger.info(f"Successfully read {len(df)} rows")
        logger.info(f"Columns found: {list(df.columns)}")

        # Check if required columns exist
        if name_column not in df.columns:
            raise RuntimeError(
                f"Column '{name_column}' not found in Excel file.\n" f"Available columns: {list(df.columns)}"
            )

        if manager_column not in df.columns:
            raise RuntimeError(
                f"Column '{manager_column}' not found in Excel file.\n" f"Available columns: {list(df.columns)}"
            )

        # Extract relevant columns
        df = df[[name_column, manager_column]].copy()

        # Clean up data
        df[name_column] = df[name_column].astype(str).str.strip()
        df[manager_column] = df[manager_column].astype(str).str.strip()

        # Remove rows where name is NaN or 'nan'
        df = df[df[name_column].notna()]
        df = df[df[name_column] != "nan"]
        df = df[df[name_column] != ""]

        logger.info(f"Cleaned data: {len(df)} valid rows")

        return df

    except FileNotFoundError:
        raise RuntimeError(f"File not found: {file_path}")
    except Exception as e:
        raise RuntimeError(f"Error reading Excel file: {e}") from e


def group_by_manager(df: pd.DataFrame, name_column: str, manager_column: str) -> dict[str, list[str]]:
    """
    Group employees by their manager.

    Args:
        df: DataFrame with employee data
        name_column: Name column
        manager_column: Manager column

    Returns:
        Dictionary mapping manager names to list of employee names
    """
    logger.info("Grouping employees by manager...")

    manager_groups = defaultdict(list)

    for _, row in df.iterrows():
        name = row[name_column]
        manager = row[manager_column]

        # Handle missing managers
        if pd.isna(manager) or manager == "nan" or manager == "":
            manager = "No Manager Assigned"

        manager_groups[manager].append(name)

    # Sort employees within each manager group
    for manager in manager_groups:
        manager_groups[manager].sort()

    logger.info(f"Found {len(manager_groups)} unique managers")

    return dict(manager_groups)


def generate_html(manager_groups: dict[str, list[str]], title: str = "Organization Structure") -> str:
    """
    Generate HTML report from manager-employee groups.

    Args:
        manager_groups: Dictionary mapping managers to employees
        title: Report title

    Returns:
        HTML string
    """
    logger.info("Generating HTML report...")

    # Calculate stats
    total_managers = len(manager_groups)
    total_employees = sum(len(employees) for employees in manager_groups.values())

    # Sort managers alphabetically, but put "No Manager Assigned" at the end
    sorted_managers = sorted(manager_groups.keys())
    if "No Manager Assigned" in sorted_managers:
        sorted_managers.remove("No Manager Assigned")
        sorted_managers.append("No Manager Assigned")

    # Generate manager sections
    manager_sections = []
    for manager in sorted_managers:
        employees = manager_groups[manager]
        employee_count = len(employees)

        # Generate employee HTML
        employees_html = "\n".join([EMPLOYEE_TEMPLATE.format(name=name) for name in employees])

        # Determine icon and style
        if manager == "No Manager Assigned":
            icon = "⚠️"
            no_manager_class = "no-manager"
        else:
            icon = "👔"
            no_manager_class = ""

        # Generate manager section
        manager_section = MANAGER_SECTION_TEMPLATE.format(
            manager_name=manager,
            employee_count=employee_count,
            plural="s" if employee_count != 1 else "",
            employees=employees_html,
            icon=icon,
            no_manager_class=no_manager_class,
        )

        manager_sections.append(manager_section)

    # Generate final HTML
    html = HTML_TEMPLATE.format(
        title=title,
        date=datetime.now().strftime("%B %d, %Y at %I:%M %p"),
        total_managers=total_managers,
        total_employees=total_employees,
        manager_sections="\n".join(manager_sections),
    )

    logger.info("HTML generation complete")

    return html


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate organization structure HTML report from Excel")

    parser.add_argument("file_path", type=str, help="Path to Excel file")

    parser.add_argument(
        "--name-column", type=str, default="Name", help='Name of column containing employee names (default: "Name")'
    )

    parser.add_argument(
        "--manager-column",
        type=str,
        default="Reports To",
        help='Name of column containing manager names (default: "Reports To")',
    )

    parser.add_argument(
        "--output", type=str, default=None, help="Output HTML file path (default: .tmp/org_report_[timestamp].html)"
    )

    parser.add_argument(
        "--title", type=str, default="Organization Structure", help='Report title (default: "Organization Structure")'
    )

    parser.add_argument("--open", action="store_true", help="Open the HTML file in browser after generation")

    return parser.parse_args()


if __name__ == "__main__":
    """Entry point when script is run from command line."""
    try:
        # Parse arguments
        args = parse_arguments()

        # Ensure .tmp directory exists
        os.makedirs(".tmp", exist_ok=True)

        # Read Excel file
        df = read_excel_file(args.file_path, args.name_column, args.manager_column)

        # Group by manager
        manager_groups = group_by_manager(df, args.name_column, args.manager_column)

        # Generate HTML
        html = generate_html(manager_groups, args.title)

        # Determine output file
        if args.output:
            output_file = args.output
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f".tmp/org_report_{timestamp}.html"

        # Save HTML
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"Report saved to: {output_file}")
        print("\n✅ Success! HTML report generated:")
        print(f"   📄 {os.path.abspath(output_file)}")

        # Open in browser if requested
        if args.open:
            import webbrowser

            webbrowser.open(f"file://{os.path.abspath(output_file)}")
            print("   🌐 Opened in browser")

        sys.exit(0)

    except RuntimeError as e:
        logger.error(f"Script failed: {e}")
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
