"""
Security Detail Page Generator

Generates standalone HTML pages for individual products with full vulnerability details.

Features:
- Full vulnerability list
- Aging heatmap
- Search/filter functionality
- Excel export
- Dark mode toggle

Usage:
    from execution.dashboards.security_detail_page import generate_product_detail_page

    vulnerabilities = [...]  # List of VulnerabilityDetail objects
    html = generate_product_detail_page('Product Name', '12345', vulnerabilities)
"""

from datetime import datetime

try:
    from ..dashboards.components.aging_heatmap import generate_aging_heatmap
except ImportError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from dashboards.components.aging_heatmap import generate_aging_heatmap  # type: ignore[no-redef]


def generate_product_detail_page(
    product_name: str, product_id: str, vulnerabilities: list, query_date: str | None = None
) -> str:
    """
    Generate standalone HTML page with vulnerability details for a product.

    Args:
        product_name: Name of the product
        product_id: ArmorCode product ID
        vulnerabilities: List of VulnerabilityDetail objects
        query_date: Date of query (defaults to today)

    Returns:
        Complete HTML page as string

    Example:
        html = generate_product_detail_page('MyApp', '123', vulns, '2026-02-08')
        with open('myapp_details.html', 'w') as f:
            f.write(html)
    """
    if query_date is None:
        query_date = datetime.now().strftime("%Y-%m-%d")

    total_vulns = len(vulnerabilities)
    critical_count = sum(1 for v in vulnerabilities if v.severity == "CRITICAL")
    high_count = sum(1 for v in vulnerabilities if v.severity == "HIGH")
    open_count = sum(1 for v in vulnerabilities if v.status == "OPEN")
    confirmed_count = sum(1 for v in vulnerabilities if v.status == "CONFIRMED")

    # Sort vulnerabilities by severity (Critical first) then by age (oldest first)
    sorted_vulns = sorted(vulnerabilities, key=lambda v: (0 if v.severity == "CRITICAL" else 1, -v.age_days))

    # Generate aging heatmap
    heatmap_html = generate_aging_heatmap(vulnerabilities)

    # Generate vulnerability rows
    vuln_rows = _generate_vulnerability_rows(sorted_vulns)

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{product_name} - Vulnerabilities Report</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
    <style>
        {_get_detail_page_styles()}
    </style>
</head>
<body>
    <!-- Theme Toggle -->
    <div class="theme-toggle" onclick="toggleTheme()" title="Toggle dark/light mode">
        <span id="theme-icon">🌙</span>
        <span id="theme-label">Dark</span>
    </div>

    <!-- Header -->
    <div class="header">
        <div class="header-content">
            <h1>{product_name}</h1>
            <p class="subtitle">Security Vulnerability Report - {query_date}</p>
            <div class="header-stats">
                <div class="stat">
                    <span class="stat-label">Total Findings:</span>
                    <span class="stat-value">{total_vulns}</span>
                </div>
                <div class="stat critical">
                    <span class="stat-label">Critical:</span>
                    <span class="stat-value">{critical_count}</span>
                </div>
                <div class="stat high">
                    <span class="stat-label">High:</span>
                    <span class="stat-value">{high_count}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Open:</span>
                    <span class="stat-value">{open_count}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Confirmed:</span>
                    <span class="stat-value">{confirmed_count}</span>
                </div>
            </div>
        </div>
    </div>

    <!-- Aging Heatmap -->
    {heatmap_html}

    <!-- Controls -->
    <div class="controls">
        <input type="text" id="searchInput" placeholder="Search vulnerabilities..." onkeyup="filterTable()">
        <div class="filter-buttons">
            <button class="filter-btn active" onclick="filterBySeverity('ALL')">All ({total_vulns})</button>
            <button class="filter-btn critical" onclick="filterBySeverity('CRITICAL')">Critical ({critical_count})</button>
            <button class="filter-btn high" onclick="filterBySeverity('HIGH')">High ({high_count})</button>
        </div>
        <button class="export-btn" onclick="exportToExcel()">📊 Export to Excel</button>
    </div>

    <!-- Vulnerability Table -->
    <div class="table-container">
        <table id="vulnTable">
            <thead>
                <tr>
                    <th onclick="sortTable(0)">Severity ▾</th>
                    <th onclick="sortTable(1)">Status ▾</th>
                    <th onclick="sortTable(2)">Age (Days) ▾</th>
                    <th onclick="sortTable(3)">Title ▾</th>
                    <th onclick="sortTable(4)">Description ▾</th>
                    <th>ID</th>
                </tr>
            </thead>
            <tbody>
{vuln_rows}
            </tbody>
        </table>
    </div>

    <div class="footer">
        <p>Generated by Engineering Metrics Platform | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        <p class="product-id">Product ID: {product_id}</p>
    </div>

    <script>
        {_get_detail_page_javascript()}
    </script>
</body>
</html>"""


def _generate_vulnerability_rows(vulnerabilities: list) -> str:
    """Generate HTML table rows for vulnerabilities"""
    rows = []
    for vuln in vulnerabilities:
        severity_class = "critical" if vuln.severity == "CRITICAL" else "high"
        status_class = "open" if vuln.status == "OPEN" else "confirmed"

        # Truncate long descriptions
        desc = vuln.description[:200] + "..." if len(vuln.description) > 200 else vuln.description
        title = vuln.title[:100] + "..." if len(vuln.title) > 100 else vuln.title

        rows.append(f"""
                <tr>
                    <td class="severity {severity_class}">{vuln.severity}</td>
                    <td class="status {status_class}">{vuln.status}</td>
                    <td class="age">{vuln.age_days}</td>
                    <td class="title">{_escape_html(title)}</td>
                    <td class="description">{_escape_html(desc)}</td>
                    <td class="id">{vuln.id[:8]}...</td>
                </tr>""")

    return "".join(rows)


def _escape_html(text: str) -> str:
    """Escape HTML special characters"""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _get_detail_page_styles() -> str:
    """Get CSS styles for detail page"""
    from ..dashboards.components.aging_heatmap import get_aging_heatmap_styles

    base_styles = """
        :root {
            --bg-primary: #f9fafb;
            --bg-secondary: #ffffff;
            --bg-tertiary: #f3f4f6;
            --text-primary: #1f2937;
            --text-secondary: #6b7280;
            --border-color: #e5e7eb;
            --hover-bg: #f8f9fa;
            --header-bg: #2c3e50;
            --header-text: #ffffff;
            --shadow: rgba(0,0,0,0.1);
        }

        [data-theme="dark"] {
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-tertiary: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #cbd5e1;
            --border-color: #475569;
            --hover-bg: #334155;
            --header-bg: #1e293b;
            --header-text: #f1f5f9;
            --shadow: rgba(0,0,0,0.3);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            transition: background-color 0.3s ease, color 0.3s ease;
            padding: 20px;
            max-width: 1600px;
            margin: 0 auto;
        }

        /* Theme Toggle */
        .theme-toggle {
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
        }

        .theme-toggle:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 16px var(--shadow);
        }

        /* Header */
        .header {
            background: var(--header-bg);
            color: var(--header-text);
            padding: 30px;
            margin-bottom: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 12px var(--shadow);
        }

        .header h1 {
            font-size: 2rem;
            margin-bottom: 8px;
        }

        .subtitle {
            font-size: 1rem;
            opacity: 0.9;
            margin-bottom: 20px;
        }

        .header-stats {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }

        .stat {
            display: flex;
            gap: 8px;
            align-items: center;
            padding: 8px 12px;
            background: rgba(255,255,255,0.1);
            border-radius: 6px;
        }

        .stat.critical {
            background: rgba(239, 68, 68, 0.2);
        }

        .stat.high {
            background: rgba(245, 158, 11, 0.2);
        }

        .stat-label {
            font-size: 0.9rem;
            opacity: 0.9;
        }

        .stat-value {
            font-size: 1.2rem;
            font-weight: 700;
        }

        /* Controls */
        .controls {
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
            margin-bottom: 20px;
            align-items: center;
        }

        #searchInput {
            flex: 1;
            min-width: 250px;
            padding: 12px 16px;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            background: var(--bg-secondary);
            color: var(--text-primary);
            font-size: 1rem;
        }

        .filter-buttons {
            display: flex;
            gap: 8px;
        }

        .filter-btn, .export-btn {
            padding: 10px 16px;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            background: var(--bg-secondary);
            color: var(--text-primary);
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 600;
            transition: all 0.2s ease;
        }

        .filter-btn:hover, .export-btn:hover {
            background: var(--hover-bg);
            transform: translateY(-1px);
        }

        .filter-btn.active {
            background: #3b82f6;
            color: white;
            border-color: #3b82f6;
        }

        .filter-btn.critical {
            border-color: #ef4444;
        }

        .filter-btn.critical.active {
            background: #ef4444;
        }

        .filter-btn.high {
            border-color: #f59e0b;
        }

        .filter-btn.high.active {
            background: #f59e0b;
        }

        /* Table */
        .table-container {
            background: var(--bg-secondary);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px var(--shadow);
            margin-bottom: 20px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        thead {
            background: var(--bg-tertiary);
        }

        th {
            padding: 16px;
            text-align: left;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
        }

        th:hover {
            background: var(--hover-bg);
        }

        tbody tr {
            border-bottom: 1px solid var(--border-color);
            transition: background 0.15s ease;
        }

        tbody tr:hover {
            background: var(--hover-bg);
        }

        td {
            padding: 12px 16px;
        }

        .severity {
            font-weight: 700;
            padding: 4px 8px;
            border-radius: 4px;
            display: inline-block;
            font-size: 0.85rem;
        }

        .severity.critical {
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
        }

        .severity.high {
            background: rgba(245, 158, 11, 0.2);
            color: #f59e0b;
        }

        .status {
            font-size: 0.85rem;
        }

        .status.open {
            color: #ef4444;
        }

        .status.confirmed {
            color: #f59e0b;
        }

        .age {
            font-weight: 600;
            color: var(--text-secondary);
        }

        .title {
            font-weight: 500;
        }

        .description {
            color: var(--text-secondary);
            font-size: 0.9rem;
        }

        .id {
            font-family: monospace;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }

        /* Footer */
        .footer {
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-top: 40px;
        }

        .product-id {
            margin-top: 8px;
            font-family: monospace;
        }
    """

    return base_styles + "\n\n" + get_aging_heatmap_styles()


def _get_detail_page_javascript() -> str:
    """Get JavaScript for detail page interactivity"""
    return """
        // Theme toggle
        function toggleTheme() {
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', newTheme);

            const icon = document.getElementById('theme-icon');
            const label = document.getElementById('theme-label');
            if (newTheme === 'dark') {
                icon.textContent = '🌙';
                label.textContent = 'Dark';
            } else {
                icon.textContent = '☀️';
                label.textContent = 'Light';
            }
        }

        // Search filter
        function filterTable() {
            const searchInput = document.getElementById('searchInput');
            const filter = searchInput.value.toLowerCase();
            const table = document.getElementById('vulnTable');
            const rows = table.getElementsByTagName('tr');

            for (let i = 1; i < rows.length; i++) {
                const row = rows[i];
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(filter) ? '' : 'none';
            }
        }

        // Severity filter
        let currentFilter = 'ALL';
        function filterBySeverity(severity) {
            currentFilter = severity;
            const table = document.getElementById('vulnTable');
            const rows = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');

            // Update button states
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            // Filter rows
            for (let row of rows) {
                const severityCell = row.cells[0].textContent;
                if (severity === 'ALL' || severityCell === severity) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            }
        }

        // Table sorting
        function sortTable(columnIndex) {
            const table = document.getElementById('vulnTable');
            const tbody = table.getElementsByTagName('tbody')[0];
            const rows = Array.from(tbody.getElementsByTagName('tr'));

            rows.sort((a, b) => {
                let aVal = a.cells[columnIndex].textContent;
                let bVal = b.cells[columnIndex].textContent;

                // Numeric sort for age column
                if (columnIndex === 2) {
                    return parseInt(bVal) - parseInt(aVal);
                }

                // String sort
                return aVal.localeCompare(bVal);
            });

            // Re-append sorted rows
            rows.forEach(row => tbody.appendChild(row));
        }

        // Excel export
        function exportToExcel() {
            const table = document.getElementById('vulnTable');
            const wb = XLSX.utils.table_to_book(table, {sheet: "Vulnerabilities"});
            const filename = `vulnerabilities_${new Date().toISOString().split('T')[0]}.xlsx`;
            XLSX.writeFile(wb, filename);
        }
    """


# Self-test
if __name__ == "__main__":
    print("Security Detail Page Generator - Self Test")
    print("=" * 60)

    # Mock vulnerability class
    class MockVuln:
        def __init__(self, severity: str, status: str, age_days: int, title: str, description: str, vuln_id: str):
            self.severity = severity
            self.status = status
            self.age_days = age_days
            self.title = title
            self.description = description
            self.id = vuln_id

    test_vulns = [
        MockVuln("CRITICAL", "OPEN", 45, "SQL Injection in login form", "A critical SQL injection vulnerability", "abc123"),
        MockVuln("HIGH", "CONFIRMED", 12, "XSS vulnerability", "Cross-site scripting issue found", "def456"),
        MockVuln("CRITICAL", "OPEN", 90, "Remote code execution", "RCE vulnerability in upload handler", "ghi789"),
    ]

    html = generate_product_detail_page("Test Product", "12345", test_vulns)
    print(f"Generated {len(html)} characters of HTML")

    output_file = ".tmp/test_security_detail.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n[SUCCESS] Test detail page written to: {output_file}")
    print("Open in browser to view")
