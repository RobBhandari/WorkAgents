"""
Interactive CSV Uploader Module

Provides client-side file upload and processing capabilities for usage reports.
Generates JavaScript and HTML components for browser-based CSV import with
PapaParse library integration.

All data processing happens client-side for maximum security - data never
leaves the user's browser.
"""

import html as html_module


def generate_import_button_html() -> str:
    """
    Generate HTML for the import button and file input.

    Returns:
        str: HTML string for import button and hidden file input
    """
    return """
    <button class="import-button" onclick="document.getElementById('file-input').click()">
        📥 IMPORT CSV
    </button>
    <input type="file" id="file-input" accept=".csv,.xlsx,.xls" onchange="handleFileUpload(event)">
"""


def generate_placeholder_html() -> str:
    """
    Generate HTML for the placeholder shown when no data is loaded.

    Returns:
        str: HTML string for placeholder content
    """
    return """
        <div id="placeholder" class="placeholder">
            <div class="placeholder-icon">📊</div>
            <h2>No Data Loaded</h2>
            <p>Click the <strong>IMPORT CSV</strong> button above to load your AI usage data.</p>
            <p style="font-size: 0.9rem; color: var(--text-secondary);">
                Supported formats: CSV, Excel (.xlsx, .xls)<br>
                All processing happens in your browser - data never leaves your computer.
            </p>
        </div>
"""


def generate_file_upload_handler_js(team_filter: str = "TARGET_TEAM") -> str:
    """
    Generate JavaScript for handling file uploads.

    Args:
        team_filter: Team name to filter data by (default: TARGET_TEAM)

    Returns:
        str: JavaScript code for file upload handling
    """
    # Escape team filter for safe JavaScript embedding
    escaped_team_filter = html_module.escape(team_filter)

    return """
        function handleFileUpload(event) {
            const file = event.target.files[0];
            if (!file) return;

            // Show loading state
            document.querySelector('.import-button').textContent = '⏳ Loading...';
            document.querySelector('.import-button').disabled = true;

            // Parse CSV
            Papa.parse(file, {
                header: true,
                skipEmptyLines: true,
                complete: function(results) {
                    processData(results.data);
                    document.querySelector('.import-button').textContent = '✅ Data Loaded';
                    setTimeout(() => {
                        document.querySelector('.import-button').textContent = '📥 IMPORT CSV';
                        document.querySelector('.import-button').disabled = false;
                    }, 2000);
                },
                error: function(error) {
                    alert('Error parsing CSV: ' + error.message);
                    document.querySelector('.import-button').textContent = '❌ Error';
                    setTimeout(() => {
                        document.querySelector('.import-button').textContent = '📥 IMPORT CSV';
                        document.querySelector('.import-button').disabled = false;
                    }, 2000);
                }
            });
        }
"""


def generate_data_processing_js(team_filter: str = "TARGET_TEAM") -> str:
    """
    Generate JavaScript for processing uploaded data.

    Args:
        team_filter: Team name to filter data by (default: TARGET_TEAM)

    Returns:
        str: JavaScript code for data processing logic
    """
    # Escape team filter for safe JavaScript embedding
    escaped_team_filter = html_module.escape(team_filter)

    return f"""
        function processData(data) {{
            // Filter for target team users
            const TEAM_FILTER = '{escaped_team_filter}';
            const lglData = data.filter(row =>
                row['Software Company'] && row['Software Company'].trim().toUpperCase() === TEAM_FILTER
            );

            if (lglData.length === 0) {{
                alert(`No ${{TEAM_FILTER}} users found in the data!`);
                return;
            }}

            // Find the correct column names (handle variations)
            const claudeAccessCol = Object.keys(lglData[0]).find(k =>
                k === 'Claude Access?' || k === 'Claude Access '
            ) || 'Claude Access?';

            const devinAccessCol = Object.keys(lglData[0]).find(k =>
                k === 'Devin Access?' || k === 'Devin Access '
            ) || 'Devin Access?';

            // Calculate statistics
            const claudeActiveUsers = lglData.filter(row => parseFloat(row['Claude 30 day usage'] || 0) > 0).length;
            const devinActiveUsers = lglData.filter(row => parseFloat(row['Devin_30d'] || 0) > 0).length;
            const avgClaudeUsage = lglData.reduce((sum, row) => sum + parseFloat(row['Claude 30 day usage'] || 0), 0) / lglData.length;
            const avgDevinUsage = lglData.reduce((sum, row) => sum + parseFloat(row['Devin_30d'] || 0), 0) / lglData.length;

            // Update stats
            document.getElementById('total-users').textContent = lglData.length;
            document.getElementById('claude-users').textContent = claudeActiveUsers;
            document.getElementById('devin-users').textContent = devinActiveUsers;
            document.getElementById('avg-claude').textContent = Math.round(avgClaudeUsage);
            document.getElementById('avg-devin').textContent = Math.round(avgDevinUsage);

            // Sort by usage descending
            const claudeData = [...lglData].sort((a, b) =>
                parseFloat(b['Claude 30 day usage'] || 0) - parseFloat(a['Claude 30 day usage'] || 0)
            );
            const devinData = [...lglData].sort((a, b) =>
                parseFloat(b['Devin_30d'] || 0) - parseFloat(a['Devin_30d'] || 0)
            );

            // Generate Claude table
            const claudeTableBody = document.getElementById('claudeTableBody');
            claudeTableBody.innerHTML = claudeData.map(row => {{
                const usage = parseFloat(row['Claude 30 day usage'] || 0);
                const {{ bgColor, textColor }} = getHeatmapColor(usage);
                const access = String(row[claudeAccessCol] || '').trim().toUpperCase();
                const accessBadge = ['YES', '1', '1.0'].includes(access)
                    ? '<span class="badge badge-success">Yes</span>'
                    : '<span class="badge badge-secondary">No</span>';

                return `
                    <tr>
                        <td>${{escapeHtml(row['Name'] || '')}}</td>
                        <td>${{escapeHtml(row['Job Title'] || '')}}</td>
                        <td>${{accessBadge}}</td>
                        <td class="heatmap-cell" style="background-color: ${{bgColor}}; color: ${{textColor}};" data-value="${{usage}}">
                            ${{Math.round(usage)}}
                        </td>
                    </tr>
                `;
            }}).join('');

            // Generate Devin table
            const devinTableBody = document.getElementById('devinTableBody');
            devinTableBody.innerHTML = devinData.map(row => {{
                const usage = parseFloat(row['Devin_30d'] || 0);
                const {{ bgColor, textColor }} = getHeatmapColor(usage);
                const access = String(row[devinAccessCol] || '').trim().toUpperCase();
                const accessBadge = ['YES', '1', '1.0'].includes(access)
                    ? '<span class="badge badge-success">Yes</span>'
                    : '<span class="badge badge-secondary">No</span>';

                return `
                    <tr>
                        <td>${{escapeHtml(row['Name'] || '')}}</td>
                        <td>${{escapeHtml(row['Job Title'] || '')}}</td>
                        <td>${{accessBadge}}</td>
                        <td class="heatmap-cell" style="background-color: ${{bgColor}}; color: ${{textColor}};" data-value="${{usage}}">
                            ${{Math.round(usage)}}
                        </td>
                    </tr>
                `;
            }}).join('');

            // Show content, hide placeholder
            document.getElementById('placeholder').classList.add('hidden');
            document.getElementById('content').classList.remove('hidden');
        }}
"""


def generate_utility_functions_js() -> str:
    """
    Generate utility JavaScript functions for heatmap colors and HTML escaping.

    Returns:
        str: JavaScript code for utility functions
    """
    return """
        function getHeatmapColor(usage) {
            if (usage >= 100) {
                return { bgColor: '#d1fae5', textColor: '#065f46' };
            } else if (usage >= 20) {
                return { bgColor: '#fef3c7', textColor: '#92400e' };
            } else {
                return { bgColor: '#fee2e2', textColor: '#991b1b' };
            }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
"""


def generate_import_button_styles() -> str:
    """
    Generate CSS styles for the import button.

    Returns:
        str: CSS string for import button styling
    """
    return """
        .import-button {
            position: fixed;
            top: 20px;
            right: 200px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: all 0.3s ease;
            z-index: 1000;
        }

        .import-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
        }

        .import-button:active {
            transform: translateY(0);
        }

        #file-input {
            display: none;
        }

        .placeholder {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-secondary);
        }

        .placeholder-icon {
            font-size: 64px;
            margin-bottom: 20px;
            opacity: 0.5;
        }

        .placeholder h2 {
            font-size: 1.5rem;
            margin-bottom: 10px;
            color: var(--text-primary);
        }

        .placeholder p {
            font-size: 1rem;
            margin-bottom: 20px;
        }

        .hidden {
            display: none !important;
        }
"""


def generate_papaparse_script_tag() -> str:
    """
    Generate script tag for PapaParse CSV parsing library.

    Returns:
        str: HTML script tag for PapaParse CDN
    """
    return '<script src="https://cdnjs.cloudflare.com/ajax/libs/PapaParse/5.4.1/papaparse.min.js"></script>'
