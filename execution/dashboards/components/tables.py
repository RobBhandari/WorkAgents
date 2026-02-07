"""
Table components for dashboards

Provides reusable data table HTML generators.
"""

from typing import List, Optional


def data_table(
    headers: List[str],
    rows: List[List[str]],
    table_id: str = "dataTable",
    sortable: bool = False,
    wrap_in_div: bool = True
) -> str:
    """
    Generate a data table HTML component.

    Args:
        headers: List of column headers
        rows: List of row data (each row is a list matching headers length)
        table_id: HTML id attribute for the table
        sortable: Whether to enable column sorting (requires JS)
        wrap_in_div: Whether to wrap table in scrollable div

    Returns:
        HTML string for data table

    Example:
        headers = ["Product", "Bugs", "Status"]
        rows = [
            ["API", "5", "Good"],
            ["Web App", "12", "Attention"],
        ]
        html = data_table(headers, rows, sortable=True)
    """
    sortable_class = "sortable" if sortable else ""

    # Generate table headers
    headers_html = "".join(f"<th>{header}</th>" for header in headers)

    # Generate table rows
    rows_html = []
    for row in rows:
        cells_html = "".join(f"<td>{cell}</td>" for cell in row)
        rows_html.append(f"<tr>{cells_html}</tr>")

    table_html = f'''
    <table id="{table_id}" class="data-table {sortable_class}">
        <thead>
            <tr>{headers_html}</tr>
        </thead>
        <tbody>
            {"".join(rows_html)}
        </tbody>
    </table>
    '''

    if wrap_in_div:
        return f'<div class="table-wrapper">{table_html}</div>'
    else:
        return table_html


def expandable_row_table(
    headers: List[str],
    rows: List[dict]
) -> str:
    """
    Generate a table with expandable detail rows.

    Args:
        headers: List of column headers
        rows: List of row dictionaries with 'cells' and 'details' keys
              Each dict should have:
                - 'cells': List of cell values for main row
                - 'details': HTML string for detail content
                - 'id': Unique identifier for the row

    Returns:
        HTML string for expandable table

    Example:
        rows = [
            {
                'id': 'row1',
                'cells': ['API', '5', 'Good'],
                'details': '<p>Details about API...</p>'
            }
        ]
        html = expandable_row_table(['Product', 'Bugs', 'Status'], rows)
    """
    headers_html = "".join(f"<th>{header}</th>" for header in headers)

    rows_html: List[str] = []
    for row in rows:
        row_id = row.get('id', f"row_{len(rows_html)}")
        cells = row.get('cells', [])
        details = row.get('details', '')

        # Main data row (clickable)
        cells_html = "".join(f"<td>{cell}</td>" for cell in cells)
        rows_html.append(
            f'<tr class="data-row" onclick="toggleDetail(\'detail-{row_id}\', this)">'
            f'{cells_html}'
            f'</tr>'
        )

        # Detail row (hidden by default)
        rows_html.append(
            f'<tr id="detail-{row_id}" class="detail-row">'
            f'<td colspan="{len(headers)}">'
            f'<div class="detail-content">{details}</div>'
            f'</td>'
            f'</tr>'
        )

    return f'''
    <div class="table-wrapper">
        <table class="data-table expandable">
            <thead>
                <tr>{headers_html}</tr>
            </thead>
            <tbody>
                {"".join(rows_html)}
            </tbody>
        </table>
    </div>
    '''


def summary_table(data: List[dict]) -> str:
    """
    Generate a simple two-column summary table (label + value).

    Args:
        data: List of dicts with 'label' and 'value' keys

    Returns:
        HTML string for summary table

    Example:
        data = [
            {'label': 'Total Bugs', 'value': '42'},
            {'label': 'Open Bugs', 'value': '15'},
        ]
        html = summary_table(data)
    """
    rows_html = []
    for item in data:
        label = item.get('label', '')
        value = item.get('value', '')
        rows_html.append(
            f'<tr>'
            f'<td class="summary-label">{label}</td>'
            f'<td class="summary-value">{value}</td>'
            f'</tr>'
        )

    return f'''
    <table class="summary-table">
        <tbody>
            {"".join(rows_html)}
        </tbody>
    </table>
    '''
