"""
Table components for dashboards

Provides reusable data table HTML generators using secure Jinja2 templates.
"""

from execution.template_engine import render_template


def data_table(
    headers: list[str],
    rows: list[list[str]],
    table_id: str = "dataTable",
    sortable: bool = False,
    wrap_in_div: bool = True,
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

    Example::

        headers = ["Product", "Bugs", "Status"]
        rows = [
            ["API", "5", "Good"],
            ["Web App", "12", "Attention"],
        ]
        html = data_table(headers, rows, sortable=True)
    """
    sortable_class = "sortable" if sortable else ""

    return render_template(
        "components/data_table.html",
        headers=headers,
        rows=rows,
        table_id=table_id,
        sortable_class=sortable_class,
        wrap_in_div=wrap_in_div,
    )


def expandable_row_table(headers: list[str], rows: list[dict]) -> str:
    """
    Generate a table with expandable detail rows.

    Args:
        headers: List of column headers
        rows: List of row dictionaries with 'cells' and 'details' keys.
            Each dict should have:

            - 'cells': List of cell values for main row
            - 'details': HTML string for detail content
            - 'id': Unique identifier for the row

    Returns:
        HTML string for expandable table

    Example::

        rows = [
            {
                'id': 'row1',
                'cells': ['API', '5', 'Good'],
                'details': '<p>Details about API...</p>'
            }
        ]
        html = expandable_row_table(['Product', 'Bugs', 'Status'], rows)
    """
    # Add default IDs if missing
    for i, row in enumerate(rows):
        if "id" not in row:
            row["id"] = f"row_{i}"

    return render_template("components/expandable_row_table.html", headers=headers, rows=rows)


def summary_table(data: list[dict]) -> str:
    """
    Generate a simple two-column summary table (label + value).

    Args:
        data: List of dicts with 'label' and 'value' keys

    Returns:
        HTML string for summary table

    Example::

        data = [
            {'label': 'Total Bugs', 'value': '42'},
            {'label': 'Open Bugs', 'value': '15'},
        ]
        html = summary_table(data)
    """
    return render_template("components/summary_table.html", data=data)
