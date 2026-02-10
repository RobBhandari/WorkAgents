"""
Dashboard JavaScript Functions

Provides interactive functionality for dashboards including theme toggling,
table scroll detection, expandable rows, and glossary toggles.
"""


def get_theme_toggle_script():
    """
    Returns theme toggle JavaScript for light/dark mode switching.

    Features:
    - Toggles between light and dark themes
    - Persists theme preference to localStorage
    - Updates icon and label dynamically
    - Initializes from saved preference or defaults to dark

    Returns:
        String of JavaScript code
    """
    return """
    function toggleTheme() {
        const html = document.documentElement;
        const currentTheme = html.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateThemeIcon(newTheme);
    }

    function updateThemeIcon(theme) {
        const icon = document.getElementById('theme-icon');
        const label = document.getElementById('theme-label');
        if (theme === 'dark') {
            icon.textContent = '☀️';
            if (label) label.textContent = 'Light Mode';
        } else {
            icon.textContent = '🌙';
            if (label) label.textContent = 'Dark Mode';
        }
    }

    document.addEventListener('DOMContentLoaded', function() {
        const savedTheme = localStorage.getItem('theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
        updateThemeIcon(savedTheme);
    });
    """


def get_glossary_toggle_script():
    """
    Returns glossary toggle JavaScript for expanding/collapsing glossary section.

    Features:
    - Toggles glossary content visibility
    - Animates expand/collapse
    - Rotates toggle icon

    Returns:
        String of JavaScript code
    """
    return """
    function toggleGlossary() {
        const content = document.getElementById('glossary-content');
        const toggle = document.getElementById('glossary-toggle');
        content.classList.toggle('expanded');
        toggle.classList.toggle('expanded');
    }
    """


def get_table_scroll_script():
    """
    Returns table scroll detection JavaScript for fade gradient indicator.

    Features:
    - Detects when table is scrolled to the end
    - Shows/hides fade gradient indicator
    - Handles window resize events
    - Touch-optimized scrolling

    Returns:
        String of JavaScript code
    """
    return """
    document.querySelectorAll('.table-wrapper').forEach(wrapper => {
        function checkScroll() {
            const isScrolledEnd = wrapper.scrollWidth - wrapper.scrollLeft <= wrapper.clientWidth + 1;
            if (isScrolledEnd) {
                wrapper.classList.add('scrolled-end');
            } else {
                wrapper.classList.remove('scrolled-end');
            }
        }

        wrapper.addEventListener('scroll', checkScroll);
        window.addEventListener('resize', checkScroll);
        checkScroll(); // Initial check
    });
    """


def get_expandable_row_script():
    """
    Returns expandable table row JavaScript for detail row toggling.

    Features:
    - Toggles detail row visibility
    - Adds/removes expanded class for icon rotation
    - Smooth show/hide animations

    Returns:
        String of JavaScript code
    """
    return """
    function toggleDetail(detailId, rowElement) {
        const detailRow = document.getElementById(detailId);
        const isExpanded = detailRow.classList.contains('show');

        if (isExpanded) {
            detailRow.classList.remove('show');
            rowElement.classList.remove('expanded');
        } else {
            detailRow.classList.add('show');
            rowElement.classList.add('expanded');
        }
    }
    """


def get_dashboard_javascript(include_table_scroll=True, include_expandable_rows=False, include_glossary=False):
    """
    Returns complete JavaScript bundle based on feature flags.

    Args:
        include_table_scroll: Include table scroll detection script
        include_expandable_rows: Include expandable row functionality
        include_glossary: Include glossary toggle functionality

    Returns:
        String of JavaScript code wrapped in <script> tags
    """
    js_parts = [get_theme_toggle_script()]  # Always include theme toggle

    if include_table_scroll:
        js_parts.append(get_table_scroll_script())
    if include_expandable_rows:
        js_parts.append(get_expandable_row_script())
    if include_glossary:
        js_parts.append(get_glossary_toggle_script())

    javascript = f"""
    <script>
    {chr(10).join(js_parts)}
    </script>
    """

    return javascript


def get_javascript_docs():
    """
    Returns documentation for JavaScript features.

    Provides comprehensive documentation for all interactive dashboard features
    including theme toggling, glossary, table scrolling, and expandable rows.

    Returns:
        Dictionary containing JavaScript feature documentation including:
        - Feature descriptions
        - Required HTML structure
        - Function signatures
        - Behavior details

    Example:
        >>> docs = get_javascript_docs()
        >>> print(docs['theme_toggle']['description'])
        'Light/dark mode switcher with localStorage persistence'
    """
    return {
        "theme_toggle": {
            "description": "Light/dark mode switcher with localStorage persistence",
            "functions": ["toggleTheme()", "updateThemeIcon(theme)"],
            "html_requirements": [
                '<div class="theme-toggle" onclick="toggleTheme()">',
                '  <span id="theme-icon">🌙</span>',
                '  <span id="theme-label">Dark Mode</span>',
                "</div>",
            ],
            "persistence": "Saves preference to localStorage.getItem('theme')",
            "default": "Dark mode",
        },
        "glossary_toggle": {
            "description": "Expandable/collapsible glossary section",
            "functions": ["toggleGlossary()"],
            "html_requirements": [
                '<div class="glossary">',
                '  <div class="glossary-header" onclick="toggleGlossary()">',
                '    <span id="glossary-toggle">▼</span>',
                "  </div>",
                '  <div id="glossary-content" class="glossary-content">',
                "    <!-- glossary items -->",
                "  </div>",
                "</div>",
            ],
        },
        "table_scroll": {
            "description": "Detects table scroll position and shows fade gradient",
            "functions": ["Automatic - runs on DOMContentLoaded"],
            "html_requirements": ['<div class="table-wrapper">', "  <table><!-- table content --></table>", "</div>"],
            "behavior": "Adds 'scrolled-end' class when scrolled to the end",
        },
        "expandable_rows": {
            "description": "Toggle detail rows in tables",
            "functions": ["toggleDetail(detailId, rowElement)"],
            "html_requirements": [
                '<tr class="data-row" onclick="toggleDetail(\'detail-1\', this)">',
                "  <td>Row data</td>",
                "</tr>",
                '<tr id="detail-1" class="detail-row">',
                '  <td colspan="100%">',
                '    <div class="detail-content">Detail content</div>',
                "  </td>",
                "</tr>",
            ],
        },
    }
