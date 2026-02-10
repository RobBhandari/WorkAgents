"""
HTML Table Generation for AI Usage Reports

This module provides functions to generate HTML tables with heatmap styling,
access badges, and sortable columns for AI usage data visualization.

Features:
- Heatmap color coding based on usage thresholds (red/amber/green)
- Access status badges (Yes/No)
- XSS-safe HTML escaping
- Sortable column headers
- Responsive table structure

Usage:
    from execution.reports.usage_tables.table_generator import generate_table_html

    html = generate_table_html(
        df=usage_dataframe,
        table_id="claudeTable",
        title="Claude Usage",
        usage_column="Claude 30 day usage",
        access_column="Claude Access"
    )
"""

import html as html_module
from dataclasses import dataclass
from enum import Enum
from typing import Any

import pandas as pd


class AccessBadgeType(Enum):
    """
    Enumeration for access badge types.

    Attributes:
        YES: User has access (green badge)
        NO: User does not have access (gray badge)
    """

    YES = "yes"
    NO = "no"


@dataclass(frozen=True)
class HeatmapColor:
    """
    Immutable dataclass representing heatmap color scheme.

    Attributes:
        background: Hex color for cell background
        text: Hex color for cell text
        intensity: String label for intensity level (low/medium/high)
    """

    background: str
    text: str
    intensity: str


@dataclass(frozen=True)
class TableRow:
    """
    Immutable dataclass representing a single table row's data.

    Attributes:
        name: User's name (will be HTML-escaped)
        job_title: User's job title (will be HTML-escaped)
        access: Access status value (Yes/No/0/1/etc.)
        usage: Numeric usage value for heatmap
    """

    name: str
    job_title: str
    access: Any
    usage: float


def get_usage_heatmap_color(usage: float) -> HeatmapColor:
    """
    Determine heatmap color based on usage value.

    Thresholds:
    - Low (RED): usage < 20
    - Medium (AMBER): 20 <= usage < 100
    - High (GREEN): usage >= 100

    Args:
        usage: Usage count value

    Returns:
        HeatmapColor: Immutable color scheme with background, text, and intensity

    Examples:
        >>> color = get_usage_heatmap_color(150)
        >>> color.background
        '#d1fae5'
        >>> color.intensity
        'high'
    """
    if usage >= 100:
        # High - Green
        return HeatmapColor(background="#d1fae5", text="#065f46", intensity="high")
    elif usage >= 20:
        # Medium - Amber
        return HeatmapColor(background="#fef3c7", text="#92400e", intensity="medium")
    else:
        # Low - Red
        return HeatmapColor(background="#fee2e2", text="#991b1b", intensity="low")


def parse_access_value(access_value: Any) -> AccessBadgeType:
    """
    Parse access value to badge type.

    Treats the following as YES: "YES", "1", "1.0" (case-insensitive)
    Treats all other values as NO: "NO", "0", "0.0", NaN, None, empty string

    Args:
        access_value: Raw access value from data (string, int, float, None)

    Returns:
        AccessBadgeType: YES or NO enum value

    Examples:
        >>> parse_access_value("YES")
        <AccessBadgeType.YES: 'yes'>
        >>> parse_access_value(1)
        <AccessBadgeType.YES: 'yes'>
        >>> parse_access_value("No")
        <AccessBadgeType.NO: 'no'>
        >>> parse_access_value(None)
        <AccessBadgeType.NO: 'no'>
    """
    access_str = str(access_value).strip().upper()
    if access_str in ["YES", "1", "1.0"]:
        return AccessBadgeType.YES
    else:
        return AccessBadgeType.NO


def generate_access_badge_html(badge_type: AccessBadgeType) -> str:
    """
    Generate HTML for access badge.

    Args:
        badge_type: Type of badge (YES or NO)

    Returns:
        str: HTML span element with appropriate styling

    Examples:
        >>> generate_access_badge_html(AccessBadgeType.YES)
        '<span class="badge badge-success">Yes</span>'
        >>> generate_access_badge_html(AccessBadgeType.NO)
        '<span class="badge badge-secondary">No</span>'
    """
    if badge_type == AccessBadgeType.YES:
        return '<span class="badge badge-success">Yes</span>'
    else:
        return '<span class="badge badge-secondary">No</span>'


def generate_heatmap_cell_html(usage: float, color: HeatmapColor) -> str:
    """
    Generate HTML for heatmap cell with usage value.

    Args:
        usage: Usage count to display
        color: HeatmapColor scheme for styling

    Returns:
        str: HTML td element with inline styles and data attribute

    Examples:
        >>> color = get_usage_heatmap_color(150)
        >>> html = generate_heatmap_cell_html(150, color)
        >>> 'background-color: #d1fae5' in html
        True
        >>> 'data-value="150"' in html
        True
    """
    return (
        f'<td class="heatmap-cell" '
        f'style="background-color: {color.background}; color: {color.text};" '
        f'data-value="{usage}">'
        f"{int(usage)}"
        f"</td>"
    )


def generate_table_row_html(row: TableRow) -> str:
    """
    Generate HTML for a complete table row.

    Args:
        row: TableRow dataclass with user data

    Returns:
        str: HTML tr element with all cells (name, job title, access badge, usage heatmap)

    Examples:
        >>> row = TableRow(name="John Doe", job_title="Engineer", access="YES", usage=125.0)
        >>> html = generate_table_row_html(row)
        >>> 'John Doe' in html
        True
        >>> 'badge-success' in html
        True
    """
    # Escape user-provided text to prevent XSS
    name_escaped = html_module.escape(row.name)
    job_title_escaped = html_module.escape(row.job_title)

    # Parse access value and generate badge
    badge_type = parse_access_value(row.access)
    access_badge = generate_access_badge_html(badge_type)

    # Get heatmap color and generate cell
    color = get_usage_heatmap_color(row.usage)
    usage_cell = generate_heatmap_cell_html(row.usage, color)

    return f"""
                        <tr>
                            <td>{name_escaped}</td>
                            <td>{job_title_escaped}</td>
                            <td>{access_badge}</td>
                            {usage_cell}
                        </tr>"""


def generate_table_html(df: pd.DataFrame, table_id: str, title: str, usage_column: str, access_column: str) -> str:
    """
    Generate complete HTML table with header and rows.

    Creates a sortable table with:
    - Sortable column headers (onclick handlers)
    - HTML-escaped user data
    - Access status badges
    - Heatmap-styled usage cells

    Args:
        df: DataFrame with user data (must contain: Name, Job Title, usage_column, access_column)
        table_id: Unique HTML ID for table element (used for sorting/filtering)
        title: Table title displayed in h2 header
        usage_column: Name of column containing usage counts
        access_column: Name of column containing access status

    Returns:
        str: Complete HTML structure (div.table-card > h2 + div.table-wrapper > table)

    Raises:
        KeyError: If required columns are missing from DataFrame

    Examples:
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     'Name': ['Alice', 'Bob'],
        ...     'Job Title': ['Engineer', 'Manager'],
        ...     'Claude Access': ['YES', 'NO'],
        ...     'Claude 30 day usage': [150, 10]
        ... })
        >>> html = generate_table_html(
        ...     df=df,
        ...     table_id='claudeTable',
        ...     title='Claude Usage',
        ...     usage_column='Claude 30 day usage',
        ...     access_column='Claude Access'
        ... )
        >>> 'Claude Usage' in html
        True
        >>> 'Alice' in html
        True
    """
    # Validate required columns exist
    required_cols = ["Name", "Job Title", usage_column, access_column]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise KeyError(f"Missing required columns: {missing_cols}")

    # Escape title to prevent XSS
    title_escaped = html_module.escape(title)

    # Start table HTML
    html = f"""
            <div class="table-card">
                <h2>{title_escaped}</h2>
                <div class="table-wrapper">
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
    for _, row_data in df.iterrows():
        row = TableRow(
            name=str(row_data["Name"]),
            job_title=str(row_data["Job Title"]),
            access=row_data[access_column],
            usage=float(row_data[usage_column]),
        )
        html += generate_table_row_html(row)

    # Close table HTML
    html += """
                        </tbody>
                    </table>
                </div>
            </div>"""

    return html
