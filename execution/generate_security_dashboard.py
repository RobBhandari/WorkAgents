#!/usr/bin/env python3
"""
Security Dashboard Generator

Creates a table-based HTML dashboard for security vulnerabilities with expandable drill-down.
Shows product-level metrics with individual vulnerability details.
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set UTF-8 encoding for Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def load_armorcode_data():
    """Load ArmorCode weekly data"""
    weekly_file = '.tmp/armorcode_weekly_20260131.json'  # Use most recent

    # Try to find the most recent weekly file
    import glob
    weekly_files = glob.glob('.tmp/armorcode_weekly_*.json')
    if weekly_files:
        weekly_file = max(weekly_files)  # Get most recent

    print(f"Loading ArmorCode data from: {weekly_file}")

    with open(weekly_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def get_product_ids_graphql(api_key, base_url, product_names):
    """Get product IDs for specified product names via GraphQL"""
    import requests

    graphql_url = f"{base_url.rstrip('/')}/api/graphql"
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    all_products = []

    # Fetch all pages of products
    for page in range(1, 10):
        query = f"""
        {{
          products(page: {page}, size: 100) {{
            products {{
              id
              name
            }}
            pageInfo {{
              hasNext
            }}
          }}
        }}
        """

        try:
            response = requests.post(graphql_url, headers=headers, json={'query': query}, timeout=60)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'products' in data['data']:
                    result = data['data']['products']
                    products = result.get('products', [])
                    all_products.extend(products)

                    if not result.get('pageInfo', {}).get('hasNext', False):
                        break
        except Exception as e:
            print(f"[WARNING] Error fetching products: {e}")
            break

    # Map product names to IDs
    product_map = {p['name']: p['id'] for p in all_products}
    product_data = []
    for name in product_names:
        if name in product_map:
            product_data.append({'name': name, 'id': product_map[name]})

    return product_data


def query_vulnerabilities_from_armorcode(product_names):
    """Query individual vulnerability details from ArmorCode GraphQL API"""
    try:
        import requests

        api_key = os.getenv('ARMORCODE_API_KEY')
        base_url = os.getenv('ARMORCODE_BASE_URL', 'https://app.armorcode.com')

        if not api_key:
            print("[WARNING] No ARMORCODE_API_KEY found - cannot fetch individual vulnerability details")
            return []

        # Get product IDs first
        print("Fetching product IDs from ArmorCode...")
        products = get_product_ids_graphql(api_key, base_url, product_names)
        print(f"Found {len(products)} products with IDs")

        graphql_url = f"{base_url.rstrip('/')}/api/graphql"
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        all_vulnerabilities = []

        # Query findings for each product
        for product in products:
            product_id = product['id']
            product_name = product['name']

            print(f"Querying findings for: {product_name}")

            page = 1
            has_next = True

            while has_next:
                # GraphQL query with proper filters
                query = f"""
                {{
                  findings(
                    page: {page}
                    size: 100
                    findingFilter: {{
                      product: [{product_id}]
                      severity: [High, Critical]
                      status: ["OPEN", "CONFIRMED"]
                    }}
                  ) {{
                    findings {{
                      id
                      title
                      description
                      severity
                      status
                      createdAt
                    }}
                    pageInfo {{
                      hasNext
                      totalElements
                    }}
                  }}
                }}
                """

                try:
                    response = requests.post(graphql_url, headers=headers, json={'query': query}, timeout=60)

                    if response.status_code == 200:
                        data = response.json()

                        if 'errors' in data:
                            print(f"  GraphQL error: {data['errors']}")
                            break

                        if 'data' in data and 'findings' in data['data']:
                            findings_data = data['data']['findings']
                            page_findings = findings_data.get('findings', [])
                            page_info = findings_data.get('pageInfo', {})

                            # Format findings
                            for vuln in page_findings:
                                # Calculate age
                                created_at = vuln.get('createdAt')
                                age_days = 0
                                if created_at:
                                    try:
                                        from dateutil import parser
                                        created_dt = parser.parse(str(created_at))
                                        age_days = (datetime.now() - created_dt.replace(tzinfo=None)).days
                                    except Exception as e:
                                        # Silently default to 0 if date parsing fails
                                        pass

                                severity_raw = vuln.get('severity', 'UNKNOWN')

                                vuln_data = {
                                    "id": vuln.get('id'),
                                    "title": vuln.get('title') or 'Unknown',
                                    "description": vuln.get('description', 'No description available'),
                                    "severity": severity_raw.upper() if severity_raw else 'UNKNOWN',
                                    "product": product_name,
                                    "age_days": age_days,
                                    "status": vuln.get('status', 'OPEN')
                                }
                                all_vulnerabilities.append(vuln_data)

                            has_next = page_info.get('hasNext', False)
                            page += 1
                        else:
                            break
                    else:
                        print(f"  [WARNING] API returned status {response.status_code}")
                        break

                except Exception as e:
                    print(f"  [WARNING] Error querying findings: {e}")
                    break

        print(f"Retrieved {len(all_vulnerabilities)} total vulnerabilities")
        return all_vulnerabilities

    except Exception as e:
        print(f"[WARNING] Failed to query ArmorCode API: {e}")
        return []


def calculate_status_indicator(current_count):
    """
    Calculate status color based on vulnerability count
    Returns tuple: (status_text, color, priority)
    Priority is used for sorting: 0 = Action Needed (Red), 1 = Caution (Amber), 2 = Good (Green)
    """
    if current_count == 0:
        return '✓ Good', '#10b981', 2  # Green
    elif current_count <= 50:
        return '⚠ Caution', '#f59e0b', 1  # Amber
    else:
        return '● Action Needed', '#ef4444', 0  # Red


def generate_vulnerability_detail_page(product_name, product_id, product_vulns, query_date):
    """Generate a standalone HTML page with vulnerability details for a product"""

    total_vulns = len(product_vulns)
    critical_count = sum(1 for v in product_vulns if v['severity'] == 'CRITICAL')
    high_count = sum(1 for v in product_vulns if v['severity'] == 'HIGH')
    open_count = sum(1 for v in product_vulns if v['status'] == 'OPEN')
    confirmed_count = sum(1 for v in product_vulns if v['status'] == 'CONFIRMED')

    # Sort vulnerabilities by severity (Critical first) then by age (oldest first)
    sorted_vulns = sorted(product_vulns, key=lambda v: (
        0 if v['severity'] == 'CRITICAL' else 1,
        -v['age_days']
    ))

    html = f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{product_name} - Vulnerabilities Report</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
    <style>
        :root {{
            --bg-primary: #f9fafb;
            --bg-secondary: #ffffff;
            --bg-filter: #ecf0f1;
            --text-primary: #1f2937;
            --text-secondary: #6b7280;
            --border-color: #e5e7eb;
            --hover-bg: #f8f9fa;
            --header-bg: #2c3e50;
            --header-text: #ffffff;
        }}

        [data-theme="dark"] {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-filter: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #cbd5e1;
            --border-color: #475569;
            --hover-bg: #334155;
            --header-bg: #1e293b;
            --header-text: #f1f5f9;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            transition: background-color 0.3s ease, color 0.3s ease;
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
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            z-index: 1000;
            transition: all 0.3s ease;
        }}

        .theme-toggle:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0,0,0,0.15);
        }}

        #theme-icon {{
            font-size: 1.2rem;
        }}

        #theme-label {{
            font-size: 0.9rem;
            color: var(--text-primary);
            font-weight: 600;
        }}

        .header {{
            background: var(--header-bg);
            color: var(--header-text);
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 24px;
        }}

        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}

        .summary-card {{
            background: var(--bg-secondary);
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border: 1px solid var(--border-color);
        }}

        .summary-card h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            color: var(--text-secondary);
            text-transform: uppercase;
        }}

        .summary-card .value {{
            font-size: 32px;
            font-weight: bold;
            color: var(--text-primary);
        }}

        .critical {{ color: #e74c3c; }}
        .high {{ color: #e67e22; }}

        .container {{
            background: var(--bg-secondary);
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
            border: 1px solid var(--border-color);
        }}

        .filters {{
            padding: 15px;
            background-color: var(--bg-filter);
            border-bottom: 1px solid var(--border-color);
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
        }}

        .filters input, .filters select {{
            padding: 8px 12px;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            font-size: 14px;
            background: var(--bg-secondary);
            color: var(--text-primary);
        }}

        .export-btn {{
            padding: 8px 16px;
            background-color: #27ae60;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 14px;
            cursor: pointer;
            font-weight: 600;
            transition: background-color 0.2s;
        }}

        .export-btn:hover {{
            background-color: #229954;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        thead {{
            background-color: var(--header-bg);
            color: var(--header-text);
            position: sticky;
            top: 0;
        }}

        th {{
            padding: 12px;
            text-align: left;
            font-weight: 600;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        td {{
            padding: 12px;
            border-bottom: 1px solid var(--border-color);
            font-size: 14px;
            color: var(--text-primary);
        }}

        tbody tr:hover {{
            background-color: var(--hover-bg);
        }}

        .severity-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .severity-critical {{
            background-color: #e74c3c;
            color: white;
        }}

        .severity-high {{
            background-color: #e67e22;
            color: white;
        }}

        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }}

        .status-confirmed {{
            background-color: #3498db;
            color: white;
        }}

        .status-open {{
            background-color: #95a5a6;
            color: white;
        }}

        .title-cell {{
            max-width: 300px;
        }}

        .description-cell {{
            max-width: 400px;
            font-size: 13px;
            color: var(--text-secondary);
        }}

        .truncate {{
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .age-cell {{
            color: #e67e22;
            font-weight: 600;
        }}

        @media (max-width: 768px) {{
            .summary {{
                grid-template-columns: 1fr;
            }}

            table {{
                font-size: 12px;
            }}

            th, td {{
                padding: 8px;
            }}
        }}
    </style>
</head>
<body>
    <div class="theme-toggle" onclick="toggleTheme()" title="Toggle dark/light mode">
        <span id="theme-icon">🌙</span>
        <span id="theme-label">Dark</span>
    </div>

    <div class="header">
        <h1>{product_name} - Security Vulnerabilities</h1>
        <p>Product ID: {product_id} | Query Date: {query_date}</p>
    </div>

    <div class="summary">
        <div class="summary-card">
            <h3>Total Vulnerabilities</h3>
            <div class="value">{total_vulns}</div>
        </div>
        <div class="summary-card">
            <h3>Critical</h3>
            <div class="value critical">{critical_count}</div>
        </div>
        <div class="summary-card">
            <h3>High</h3>
            <div class="value high">{high_count}</div>
        </div>
        <div class="summary-card">
            <h3>Open Issues</h3>
            <div class="value">{open_count}</div>
        </div>
        <div class="summary-card">
            <h3>Confirmed</h3>
            <div class="value">{confirmed_count}</div>
        </div>
    </div>

    <div class="container">
        <div class="filters">
            <input type="text" id="searchInput" placeholder="Search vulnerabilities..." style="width: 300px;">
            <select id="severityFilter">
                <option value="">All Severities</option>
                <option value="CRITICAL">Critical</option>
                <option value="HIGH">High</option>
            </select>
            <select id="statusFilter">
                <option value="">All Statuses</option>
                <option value="OPEN">Open</option>
                <option value="CONFIRMED">Confirmed</option>
            </select>
            <button class="export-btn" onclick="exportToExcel()">📊 Export to Excel</button>
        </div>

        <table id="vulnTable">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Title</th>
                    <th>Severity</th>
                    <th>Status</th>
                    <th>Age (Days)</th>
                    <th>Description</th>
                </tr>
            </thead>
            <tbody>
'''

    # Add vulnerability rows
    for vuln in sorted_vulns:
        severity_class = 'severity-critical' if vuln['severity'] == 'CRITICAL' else 'severity-high'
        status_class = 'status-confirmed' if vuln['status'] == 'CONFIRMED' else 'status-open'

        # Escape HTML in strings
        title = vuln['title'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        description = vuln['description'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        html += f'''
                <tr data-severity="{vuln['severity']}" data-status="{vuln['status']}">
                    <td>{vuln['id']}</td>
                    <td class="title-cell">{title}</td>
                    <td><span class="severity-badge {severity_class}">{vuln['severity'].title()}</span></td>
                    <td><span class="status-badge {status_class}">{vuln['status'].title()}</span></td>
                    <td class="age-cell">{vuln['age_days']}</td>
                    <td class="description-cell truncate">{description}</td>
                </tr>
'''

    html += '''
            </tbody>
        </table>
    </div>

    <script>
        // Filter functionality
        const searchInput = document.getElementById('searchInput');
        const severityFilter = document.getElementById('severityFilter');
        const statusFilter = document.getElementById('statusFilter');
        const table = document.getElementById('vulnTable');
        const rows = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');

        function filterTable() {
            const searchTerm = searchInput.value.toLowerCase();
            const severityValue = severityFilter.value;
            const statusValue = statusFilter.value;

            for (let row of rows) {
                const text = row.textContent.toLowerCase();
                const severity = row.getAttribute('data-severity');
                const status = row.getAttribute('data-status');

                const matchesSearch = searchTerm === '' || text.includes(searchTerm);
                const matchesSeverity = severityValue === '' || severity === severityValue;
                const matchesStatus = statusValue === '' || status === statusValue;

                if (matchesSearch && matchesSeverity && matchesStatus) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            }
        }

        searchInput.addEventListener('input', filterTable);
        severityFilter.addEventListener('change', filterTable);
        statusFilter.addEventListener('change', filterTable);

        // Make truncated cells expandable on click
        document.querySelectorAll('.truncate').forEach(cell => {
            cell.style.cursor = 'pointer';
            cell.addEventListener('click', function() {
                this.classList.toggle('truncate');
            });
        });

        // Export to Excel functionality
        function exportToExcel() {
            // Get visible rows only
            const visibleRows = Array.from(rows).filter(row => row.style.display !== 'none');

            // Prepare data for Excel
            const data = [
                ['ID', 'Title', 'Severity', 'Status', 'Age (Days)', 'Description']
            ];

            visibleRows.forEach(row => {
                const cells = row.getElementsByTagName('td');
                const rowData = [
                    cells[0].textContent.trim(),  // ID
                    cells[1].textContent.trim(),  // Title
                    cells[2].textContent.trim(),  // Severity
                    cells[3].textContent.trim(),  // Status
                    cells[4].textContent.trim(),  // Age
                    cells[5].textContent.trim()   // Description
                ];
                data.push(rowData);
            });

            // Create workbook and worksheet
            const wb = XLSX.utils.book_new();
            const ws = XLSX.utils.aoa_to_sheet(data);

            // Set column widths
            ws['!cols'] = [
                {wch: 15},  // ID
                {wch: 40},  // Title
                {wch: 12},  // Severity
                {wch: 12},  // Status
                {wch: 12},  // Age
                {wch: 60}   // Description
            ];

            // Add worksheet to workbook
            XLSX.utils.book_append_sheet(wb, ws, 'Vulnerabilities');

            // Generate filename with timestamp
            const timestamp = new Date().toISOString().split('T')[0];
            const filename = `''' + product_name.replace(' ', '_') + '''_vulnerabilities_${timestamp}.xlsx`;

            // Save file
            XLSX.writeFile(wb, filename);
        }

        // Theme toggle functions
        function toggleTheme() {{
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);

            updateThemeIcon(newTheme);
        }}

        function updateThemeIcon(theme) {{
            const icon = document.getElementById('theme-icon');
            const label = document.getElementById('theme-label');

            if (theme === 'dark') {{
                icon.textContent = '🌙';
                label.textContent = 'Dark';
            }} else {{
                icon.textContent = '☀️';
                label.textContent = 'Light';
            }}
        }}

        // Load theme preference on page load
        document.addEventListener('DOMContentLoaded', function() {{
            const savedTheme = localStorage.getItem('theme') || 'dark';
            document.documentElement.setAttribute('data-theme', savedTheme);
            updateThemeIcon(savedTheme);
        }});
    </script>
</body>
</html>
'''

    return html


def generate_aging_heatmap(product_vulns):
    """Generate HTML for aging heatmap visualization"""
    if not product_vulns:
        return '<div class="no-data">No vulnerability details available</div>'

    # Define age buckets
    age_buckets = [
        {'label': '0-7', 'min': 0, 'max': 7},
        {'label': '8-14', 'min': 8, 'max': 14},
        {'label': '15-30', 'min': 15, 'max': 30},
        {'label': '31-90', 'min': 31, 'max': 90},
        {'label': '90+', 'min': 91, 'max': 999999}
    ]

    # Initialize counts
    heatmap_data = {
        'CRITICAL': {bucket['label']: 0 for bucket in age_buckets},
        'HIGH': {bucket['label']: 0 for bucket in age_buckets}
    }

    # Count vulnerabilities by severity and age bucket
    for vuln in product_vulns:
        severity = vuln['severity']
        age_days = vuln['age_days']

        if severity not in ['CRITICAL', 'HIGH']:
            continue

        for bucket in age_buckets:
            if bucket['min'] <= age_days <= bucket['max']:
                heatmap_data[severity][bucket['label']] += 1
                break

    # Calculate max value for color intensity scaling
    max_count = 0
    for severity_data in heatmap_data.values():
        max_count = max(max_count, max(severity_data.values()))

    # Generate heatmap HTML
    html = '<div class="detail-content">'
    html += '<div class="heatmap-container">'
    html += '<div class="heatmap-header">'
    html += '<h4>Finding Age Distribution</h4>'
    html += '<p class="heatmap-subtitle">Vulnerability count by age and severity</p>'
    html += '</div>'

    # Age bucket headers
    html += '<div class="heatmap-grid">'
    html += '<div class="heatmap-corner"></div>'
    for bucket in age_buckets:
        html += f'<div class="heatmap-col-header">{bucket["label"]}<span class="days-label">DAYS</span></div>'

    # Critical row
    html += '<div class="heatmap-row-header critical-header">Critical</div>'
    for bucket in age_buckets:
        count = heatmap_data['CRITICAL'][bucket['label']]
        intensity = (count / max_count) if max_count > 0 else 0
        html += generate_heatmap_cell(count, intensity, 'critical')

    # High row
    html += '<div class="heatmap-row-header high-header">High</div>'
    for bucket in age_buckets:
        count = heatmap_data['HIGH'][bucket['label']]
        intensity = (count / max_count) if max_count > 0 else 0
        html += generate_heatmap_cell(count, intensity, 'high')

    html += '</div>'  # heatmap-grid
    html += '</div>'  # heatmap-container
    html += '</div>'  # detail-content
    return html


def generate_heatmap_cell(count, intensity, severity_type):
    """Generate a single heatmap cell with appropriate styling"""
    if count == 0:
        # Empty cell - subtle gray
        cell_class = 'heatmap-cell empty'
        bg_color = 'rgba(148, 163, 184, 0.1)'
        text_color = 'var(--text-secondary)'
        display_value = ''
    else:
        cell_class = 'heatmap-cell'

        if severity_type == 'critical':
            # Red color scale for critical
            if intensity < 0.3:
                bg_color = f'rgba(239, 68, 68, {0.3 + intensity * 0.3})'
            elif intensity < 0.7:
                bg_color = f'rgba(239, 68, 68, {0.6 + intensity * 0.2})'
            else:
                bg_color = f'rgba(220, 38, 38, {0.8 + intensity * 0.2})'
        else:
            # Orange/amber scale for high
            if intensity < 0.3:
                bg_color = f'rgba(251, 146, 60, {0.3 + intensity * 0.3})'
            elif intensity < 0.7:
                bg_color = f'rgba(249, 115, 22, {0.6 + intensity * 0.2})'
            else:
                bg_color = f'rgba(234, 88, 12, {0.8 + intensity * 0.2})'

        text_color = 'white' if intensity > 0.5 else 'var(--text-primary)'
        display_value = str(count)

    return f'''
    <div class="{cell_class}"
         style="background: {bg_color}; color: {text_color};"
         data-count="{count}"
         title="{count} vulnerabilities">
        <span class="cell-value">{display_value}</span>
    </div>
    '''


def generate_html(armorcode_data, vulnerabilities):
    """Generate self-contained HTML dashboard"""

    # Extract current data
    current_data = armorcode_data.get('current', {})
    by_product = current_data.get('by_product', {})

    # Group vulnerabilities by product
    vulns_by_product = {}
    for vuln in vulnerabilities:
        product = vuln['product']
        if product not in vulns_by_product:
            vulns_by_product[product] = []
        vulns_by_product[product].append(vuln)

    # Calculate totals from live API data
    total_critical = sum(1 for v in vulnerabilities if v['severity'] == 'CRITICAL')
    total_high = sum(1 for v in vulnerabilities if v['severity'] == 'HIGH')
    total_vulns = len(vulnerabilities)

    # Overall status
    if total_critical == 0 and total_high <= 10:
        status_color = "#10b981"
        status_text = "HEALTHY"
    elif total_critical <= 5:
        status_color = "#f59e0b"
        status_text = "CAUTION"
    else:
        status_color = "#ef4444"
        status_text = "ACTION NEEDED"

    html = f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Security Dashboard - {datetime.now().strftime('%Y-%m-%d')}</title>
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
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
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

        .executive-summary {{
            background: var(--bg-secondary);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .status-badge {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.9rem;
            background: {status_color};
            color: white;
            margin-bottom: 20px;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin-top: 16px;
        }}

        .summary-card {{
            background: var(--bg-tertiary);
            padding: 16px;
            border-radius: 8px;
            border-left: 4px solid #ef4444;
        }}

        .summary-card .label {{
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }}

        .summary-card .value {{
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--text-primary);
            font-variant-numeric: tabular-nums;
        }}

        .summary-card .explanation {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-top: 6px;
        }}

        .card {{
            background: var(--bg-secondary);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .card h2 {{
            font-size: 1.5rem;
            margin-bottom: 20px;
            color: var(--text-primary);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}

        thead {{
            background: var(--bg-tertiary);
        }}

        th {{
            padding: 14px 16px;
            text-align: left;
            font-weight: 600;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            border-bottom: 2px solid var(--border-color);
        }}

        th:nth-child(2), th:nth-child(3), th:nth-child(4), th:nth-child(5), th:nth-child(6) {{
            text-align: center;
        }}

        .view-btn {{
            display: inline-block;
            padding: 6px 16px;
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.2s ease;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .view-btn:hover {{
            background: linear-gradient(135deg, #2980b9, #21618c);
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }}

        .view-btn:active {{
            transform: translateY(0);
        }}

        tbody tr.data-row {{
            cursor: pointer;
            transition: background-color 0.15s ease;
        }}

        tbody tr.data-row:hover {{
            background: var(--bg-tertiary);
        }}

        tbody tr.data-row td:first-child {{
            position: relative;
            padding-left: 40px;
        }}

        tbody tr.data-row td:first-child::before {{
            content: '▶';
            position: absolute;
            left: 16px;
            transition: transform 0.2s ease;
            color: var(--text-secondary);
            font-size: 0.7em;
        }}

        tbody tr.data-row.expanded td:first-child::before {{
            transform: rotate(90deg);
        }}

        tbody tr.data-row td {{
            padding: 14px 16px;
            border-bottom: 1px solid var(--border-color);
            font-variant-numeric: tabular-nums;
        }}

        tbody tr.data-row td:nth-child(2),
        tbody tr.data-row td:nth-child(3),
        tbody tr.data-row td:nth-child(4),
        tbody tr.data-row td:nth-child(5),
        tbody tr.data-row td:nth-child(6) {{
            text-align: center;
        }}

        tbody tr.detail-row {{
            display: none;
            background: var(--bg-tertiary);
        }}

        tbody tr.detail-row.show {{
            display: table-row;
        }}

        tbody tr.detail-row td {{
            padding: 0;
            border-bottom: 2px solid var(--border-color);
        }}

        .detail-content {{
            padding: 24px;
            animation: slideDown 0.3s ease;
        }}

        @keyframes slideDown {{
            from {{
                opacity: 0;
                transform: translateY(-10px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        .detail-section {{
            margin-bottom: 20px;
        }}

        .detail-section h4 {{
            font-size: 1rem;
            margin-bottom: 12px;
            color: var(--text-primary);
        }}

        .vuln-list {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}

        .vuln-item {{
            background: var(--bg-secondary);
            padding: 16px;
            border-radius: 8px;
            border-left: 3px solid #ef4444;
        }}

        .vuln-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}

        .vuln-severity {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 700;
            color: white;
            letter-spacing: 0.05em;
        }}

        .vuln-age {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-weight: 600;
        }}

        .vuln-title {{
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 8px;
        }}

        .vuln-description {{
            font-size: 0.9rem;
            color: var(--text-secondary);
            line-height: 1.5;
        }}

        .no-data {{
            color: var(--text-secondary);
            font-style: italic;
            padding: 20px;
            text-align: center;
        }}

        /* Heatmap Styles */
        .heatmap-container {{
            padding: 16px 24px;
        }}

        .heatmap-header {{
            margin-bottom: 14px;
        }}

        .heatmap-header h4 {{
            font-size: 1.05rem;
            margin-bottom: 3px;
            color: var(--text-primary);
            font-weight: 600;
        }}

        .heatmap-subtitle {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin: 0;
        }}

        .heatmap-grid {{
            display: grid;
            grid-template-columns: 80px repeat(5, 1fr);
            gap: 10px;
            align-items: stretch;
        }}

        .heatmap-corner {{
            grid-column: 1;
            grid-row: 1;
        }}

        .heatmap-col-header {{
            font-size: 0.8rem;
            font-weight: 700;
            text-align: center;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 0 0 6px 0;
            display: flex;
            flex-direction: column;
            gap: 1px;
            align-items: center;
            justify-content: flex-end;
        }}

        .days-label {{
            font-size: 0.65rem;
            font-weight: 500;
            opacity: 0.6;
        }}

        .heatmap-row-header {{
            font-size: 0.9rem;
            font-weight: 600;
            text-align: right;
            padding-right: 14px;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            justify-content: flex-end;
        }}

        .critical-header {{
            color: #ef4444;
        }}

        .high-header {{
            color: #f59e0b;
        }}

        .heatmap-cell {{
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 6px;
            font-size: 1.1rem;
            font-weight: 700;
            transition: all 0.15s ease;
            cursor: pointer;
            position: relative;
            height: 40px;
            border: 1px solid transparent;
        }}

        .heatmap-cell:not(.empty):hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px var(--shadow);
            border-color: rgba(255, 255, 255, 0.2);
            z-index: 10;
        }}

        .heatmap-cell.empty {{
            background: rgba(148, 163, 184, 0.05) !important;
            border: 1px dashed rgba(148, 163, 184, 0.2);
            cursor: default;
        }}

        .heatmap-cell.empty:hover {{
            transform: none;
            box-shadow: none;
        }}

        .cell-value {{
            font-variant-numeric: tabular-nums;
            text-shadow: 0 1px 1px rgba(0, 0, 0, 0.1);
        }}

        .heatmap-cell[data-count]:not([data-count="0"])::after {{
            content: attr(title);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%) translateY(-6px);
            background: rgba(0, 0, 0, 0.9);
            color: white;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 500;
            white-space: nowrap;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.15s ease, transform 0.15s ease;
            z-index: 100;
        }}

        .heatmap-cell[data-count]:not([data-count="0"]):hover::after {{
            opacity: 1;
            transform: translateX(-50%) translateY(-2px);
        }}

        @media (max-width: 768px) {{
            .heatmap-grid {{
                grid-template-columns: 70px repeat(5, 1fr);
                gap: 8px;
            }}

            .heatmap-cell {{
                height: 36px;
                font-size: 1rem;
            }}

            .heatmap-col-header {{
                font-size: 0.75rem;
            }}

            .heatmap-row-header {{
                font-size: 0.85rem;
                padding-right: 10px;
            }}
        }}

        .footer {{
            text-align: center;
            padding: 20px;
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}

        @media print {{
            body {{
                background: var(--bg-secondary);
            }}
            .card, .executive-summary {{
                box-shadow: none;
                border: 1px solid var(--border-color);
            }}
        }}
    </style>
</head>
<body>
    <div class="theme-toggle" onclick="toggleTheme()" title="Toggle dark/light mode">
        <span id="theme-icon">🌙</span>
        <span id="theme-label">Dark</span>
    </div>

    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>Security Dashboard</h1>
            <div class="subtitle">Vulnerability Tracking & Remediation</div>
            <div class="timestamp">Generated {datetime.now().strftime('%B %d, %Y at %H:%M')}</div>
        </div>

        <!-- Executive Summary -->
        <div class="executive-summary">
            <div class="status-badge">{status_text}</div>
            <h2 style="margin-bottom: 10px;">Executive Summary</h2>
            <p style="color: var(--text-secondary); margin-bottom: 16px; font-size: 0.95rem;">
                Security vulnerability metrics from ArmorCode. Tracking open HIGH and CRITICAL vulnerabilities across all products.
            </p>

            <div class="summary-grid">
                <div class="summary-card">
                    <div class="label">Total Vulnerabilities</div>
                    <div class="value">{total_vulns:,}</div>
                    <div class="explanation">All open HIGH + CRITICAL</div>
                </div>

                <div class="summary-card" style="border-left-color: #dc2626;">
                    <div class="label">Critical</div>
                    <div class="value">{total_critical:,}</div>
                    <div class="explanation">Immediate attention required</div>
                </div>

                <div class="summary-card" style="border-left-color: #f59e0b;">
                    <div class="label">High Severity</div>
                    <div class="value">{total_high:,}</div>
                    <div class="explanation">Address urgently</div>
                </div>
            </div>
        </div>

        <!-- Product Vulnerability Table -->
        <div class="card">
            <h2>Vulnerabilities by Product</h2>
            <table>
                <thead>
                    <tr>
                        <th>Product</th>
                        <th>Current</th>
                        <th>Critical</th>
                        <th>High</th>
                        <th>View</th>
                        <th title="Good: 0 vulns | Caution: 1-50 vulns | Action Needed: >50 vulns">Status</th>
                    </tr>
                </thead>
                <tbody>
'''

    # Generate product rows
    # First, prepare products with their status for sorting
    products_with_status = []
    for product_name, counts in by_product.items():
        baseline_total = counts.get('total', 0)

        # Skip if no vulnerabilities in baseline
        if baseline_total == 0:
            continue

        # Get vulnerabilities for this product - try exact match first, then partial match
        product_vulns = vulns_by_product.get(product_name, [])

        # If no exact match, try to find partial matches
        if not product_vulns:
            for api_product_name, vulns in vulns_by_product.items():
                # Check if product names are similar (case-insensitive, partial match)
                if api_product_name.lower() in product_name.lower() or product_name.lower() in api_product_name.lower():
                    product_vulns = vulns
                    break

        # Calculate actual counts from live API data
        critical = sum(1 for v in product_vulns if v['severity'] == 'CRITICAL')
        high = sum(1 for v in product_vulns if v['severity'] == 'HIGH')
        current = len(product_vulns)

        # Calculate status
        status_text, status_color, status_priority = calculate_status_indicator(current)

        drilldown_html = generate_aging_heatmap(product_vulns)

        products_with_status.append({
            'product_name': product_name,
            'current': current,
            'critical': critical,
            'high': high,
            'status_text': status_text,
            'status_color': status_color,
            'status_priority': status_priority,
            'drilldown_html': drilldown_html,
            'product_vulns': product_vulns
        })

    # Sort by status priority (Red->Amber->Green), then by total count descending
    products_with_status.sort(key=lambda x: (x['status_priority'], -x['current']))

    # Now render the sorted products
    for idx, prod_data in enumerate(products_with_status):
        product_name = prod_data['product_name']
        current = prod_data['current']
        critical = prod_data['critical']
        high = prod_data['high']
        status_text = prod_data['status_text']
        status_color = prod_data['status_color']
        drilldown_html = prod_data['drilldown_html']

        # Generate safe filename for this product
        product_filename = f"vuln_detail_{idx}_{product_name.replace(' ', '_').replace('/', '_')}.html"

        # Store product data with filename for later generation
        prod_data['filename'] = product_filename
        prod_data['product_vulns'] = vulns_by_product.get(product_name, [])

        html += f'''
                    <tr class="data-row" onclick="toggleDetail('sec-detail-{idx}', this)">
                        <td><strong>{product_name}</strong></td>
                        <td>{current}</td>
                        <td>{critical}</td>
                        <td>{high}</td>
                        <td><a href="{product_filename}" target="_blank" class="view-btn" onclick="event.stopPropagation();">View</a></td>
                        <td><span style="color: {status_color};">{status_text}</span></td>
                    </tr>
                    <tr class="detail-row" id="sec-detail-{idx}">
                        <td colspan="6">
                            {drilldown_html}
                        </td>
                    </tr>
'''

    html += f'''
                </tbody>
            </table>
        </div>

        <!-- Footer -->
        <div class="footer">
            <p>Director Observatory • Security Vulnerability Tracking</p>
            <p style="margin-top: 10px;">Data source: ArmorCode • Click any product row to see vulnerability details</p>
        </div>
    </div>

    <script>
        // Expandable row toggle function
        function toggleDetail(detailId, rowElement) {{
            const detailRow = document.getElementById(detailId);
            const isExpanded = detailRow.classList.contains('show');

            if (isExpanded) {{
                detailRow.classList.remove('show');
                rowElement.classList.remove('expanded');
            }} else {{
                detailRow.classList.add('show');
                rowElement.classList.add('expanded');
            }}
        }}

        function toggleTheme() {{
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);

            updateThemeIcon(newTheme);
        }}

        function updateThemeIcon(theme) {{
            const icon = document.getElementById('theme-icon');
            const label = document.getElementById('theme-label');

            if (theme === 'dark') {{
                icon.textContent = '🌙';
                label.textContent = 'Dark';
            }} else {{
                icon.textContent = '☀️';
                label.textContent = 'Light';
            }}
        }}

        // Load theme preference on page load
        document.addEventListener('DOMContentLoaded', function() {{
            const savedTheme = localStorage.getItem('theme') || 'dark';
            document.documentElement.setAttribute('data-theme', savedTheme);
            updateThemeIcon(savedTheme);
        }});
    </script>
</body>
</html>
'''
    return html, products_with_status


def main():
    print("Security Dashboard Generator\n")
    print("=" * 60)

    # Load ArmorCode data
    try:
        armorcode_data = load_armorcode_data()
        print(f"Loaded ArmorCode data")
    except FileNotFoundError:
        print("[ERROR] No ArmorCode weekly data found.")
        print("Run: python execution/armorcode_query_vulns.py")
        return

    # Get product names from weekly data
    current_data = armorcode_data.get('current', {})
    by_product = current_data.get('by_product', {})
    product_names = [name for name, counts in by_product.items() if counts.get('total', 0) > 0]

    print(f"\nProducts to query: {len(product_names)}")

    # Query individual vulnerabilities using GraphQL
    print("\nQuerying individual vulnerability details via GraphQL...")
    vulnerabilities = query_vulnerabilities_from_armorcode(product_names)
    print(f"Retrieved {len(vulnerabilities)} vulnerability details")

    # Generate HTML
    print("\nGenerating dashboard...")
    html, products_with_status = generate_html(armorcode_data, vulnerabilities)

    # Save main dashboard to file
    output_dir = '.tmp/observatory/dashboards'
    output_file = os.path.join(output_dir, 'security_dashboard.html')
    os.makedirs(output_dir, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    # Generate individual vulnerability detail pages for each product
    print(f"\nGenerating individual vulnerability detail pages...")
    query_date = datetime.now().strftime('%Y-%m-%d')

    # Get product IDs from ArmorCode API for the detail pages
    print("Fetching product IDs for detail pages...")
    api_key = os.getenv('ARMORCODE_API_KEY')
    base_url = os.getenv('ARMORCODE_BASE_URL', 'https://app.armorcode.com')

    # Get all product IDs
    product_id_map = {}
    if api_key:
        product_data = get_product_ids_graphql(api_key, base_url, [p['product_name'] for p in products_with_status])
        product_id_map = {p['name']: p['id'] for p in product_data}

    for product_info in products_with_status:
        product_name = product_info['product_name']
        product_vulns = product_info.get('product_vulns', [])
        product_filename = product_info['filename']

        # Get product ID, or use a default if not found
        product_id = product_id_map.get(product_name, 'Unknown')

        # Generate the vulnerability detail page
        detail_html = generate_vulnerability_detail_page(
            product_name,
            product_id,
            product_vulns,
            query_date
        )

        # Save the detail page
        detail_file_path = os.path.join(output_dir, product_filename)
        with open(detail_file_path, 'w', encoding='utf-8') as f:
            f.write(detail_html)

        print(f"  Generated: {product_filename} ({len(product_vulns)} vulnerabilities)")

    print(f"\n[SUCCESS] Dashboard generated!")
    print(f"  Main Dashboard: {output_file}")
    print(f"  Detail Pages: {len(products_with_status)} files")
    print(f"  Size: {len(html):,} bytes")
    print(f"\nOpen in browser: start {output_file}")
    print("\nFeatures:")
    print("  ✓ Table-based layout (no charts)")
    print("  ✓ Expandable rows for vulnerability details")
    print("  ✓ Product | Current | Critical | High | View | Status")
    print("  ✓ View button opens detailed vulnerability page in new tab")
    print("  ✓ Detail pages include search, filters, and Excel export")
    print("  ✓ Dark mode support with toggle (default: dark)")
    print("  ✓ Sorted by Critical first, then High, by age")
    print("  ✓ Self-contained (works offline)")


if __name__ == "__main__":
    main()
