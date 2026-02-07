"""
Mobile-Responsive Dashboard Framework

Provides shared CSS and JavaScript for all Observatory dashboards.
Extracts 2,000+ lines of common code into reusable components.

Usage:
    from execution.dashboard_framework import get_dashboard_framework

    css, javascript = get_dashboard_framework(
        header_gradient_start='#8b5cf6',
        header_gradient_end='#7c3aed',
        include_table_scroll=True,
        include_expandable_rows=True,
        include_glossary=True
    )

    html = f'''
    <head>
        {css}
        <style>/* Dashboard-specific CSS */</style>
    </head>
    <body>
        <!-- content -->
        {javascript}
        <script>/* Dashboard-specific JS */</script>
    </body>
    '''
"""


def get_theme_variables():
    """Returns CSS custom properties for light/dark themes"""
    return """
    :root {
        --bg-primary: #f9fafb;
        --bg-secondary: #ffffff;
        --bg-tertiary: #f9fafb;
        --text-primary: #1f2937;
        --text-secondary: #6b7280;
        --border-color: #e5e7eb;
        --shadow: rgba(0,0,0,0.1);

        /* RAG Colors */
        --color-rag-green: #10b981;
        --color-rag-amber: #f59e0b;
        --color-rag-red: #ef4444;

        /* Spacing Scale */
        --spacing-xs: 8px;
        --spacing-sm: 12px;
        --spacing-md: 16px;
        --spacing-lg: 24px;
        --spacing-xl: 32px;
    }

    [data-theme="dark"] {
        --bg-primary: #0f172a;
        --bg-secondary: #1e293b;
        --bg-tertiary: #334155;
        --text-primary: #f1f5f9;
        --text-secondary: #cbd5e1;
        --border-color: #475569;
        --shadow: rgba(0,0,0,0.3);
    }
    """


def get_base_styles():
    """Returns mobile-first base styles"""
    return """
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }

    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
        background: var(--bg-primary);
        padding: 12px;
        color: var(--text-primary);
        transition: background-color 0.3s ease, color 0.3s ease;
        line-height: 1.6;
    }

    /* Progressive enhancement for larger screens */
    @media (min-width: 480px) {
        body { padding: 16px; }
    }

    @media (min-width: 768px) {
        body { padding: 20px; }
    }

    /* Typography scale */
    h1 { font-size: 1.5rem; line-height: 1.2; margin-bottom: 8px; }
    h2 { font-size: 1.2rem; line-height: 1.3; margin-bottom: 8px; }
    h3 { font-size: 1rem; line-height: 1.4; margin-bottom: 8px; }

    @media (min-width: 768px) {
        h1 { font-size: 2rem; }
        h2 { font-size: 1.5rem; }
        h3 { font-size: 1.25rem; }
    }

    @media (min-width: 1024px) {
        h1 { font-size: 2.5rem; }
        h2 { font-size: 1.75rem; }
    }

    p {
        margin-bottom: 12px;
    }
    """


def get_layout_components():
    """Returns mobile-responsive layout components"""
    return """
    .container {
        max-width: 1400px;
        margin: 0 auto;
        width: 100%;
    }

    .header {
        background: linear-gradient(135deg, var(--header-gradient-start) 0%, var(--header-gradient-end) 100%);
        color: white;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px var(--shadow);
    }

    @media (min-width: 480px) {
        .header { padding: 24px; border-radius: 10px; }
    }

    @media (min-width: 768px) {
        .header { padding: 32px; border-radius: 12px; margin-bottom: 30px; }
    }

    @media (min-width: 1024px) {
        .header { padding: 40px; }
    }

    .header h1 {
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 8px;
    }

    @media (min-width: 768px) {
        .header h1 { font-size: 2rem; }
    }

    @media (min-width: 1024px) {
        .header h1 { font-size: 2.5rem; }
    }

    .header .subtitle,
    .header p {
        font-size: 0.9rem;
        opacity: 0.9;
        margin-bottom: 4px;
    }

    @media (min-width: 768px) {
        .header .subtitle,
        .header p { font-size: 1rem; }
    }

    .card {
        background: var(--bg-secondary);
        padding: 16px;
        border-radius: 8px;
        margin-bottom: 16px;
        box-shadow: 0 2px 8px var(--shadow);
        transition: background-color 0.3s ease;
    }

    @media (min-width: 480px) {
        .card { padding: 20px; border-radius: 10px; }
    }

    @media (min-width: 768px) {
        .card { padding: 24px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 12px var(--shadow); }
    }

    @media (min-width: 1024px) {
        .card { padding: 30px; }
    }

    .section {
        margin-bottom: 24px;
    }

    @media (min-width: 768px) {
        .section { margin-bottom: 30px; }
    }
    """


def get_table_styles():
    """Returns mobile-optimized table styles with horizontal scroll"""
    return """
    .table-wrapper {
        position: relative;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: thin;
        scrollbar-color: var(--border-color) transparent;
        margin-top: 16px;
    }

    .table-wrapper::-webkit-scrollbar {
        height: 8px;
    }

    .table-wrapper::-webkit-scrollbar-track {
        background: var(--bg-primary);
        border-radius: 4px;
    }

    .table-wrapper::-webkit-scrollbar-thumb {
        background: var(--border-color);
        border-radius: 4px;
    }

    .table-wrapper::after {
        content: '';
        position: absolute;
        top: 0;
        right: 0;
        bottom: 0;
        width: 30px;
        background: linear-gradient(to left, var(--bg-secondary), transparent);
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.3s ease;
    }

    .table-wrapper:not(.scrolled-end)::after {
        opacity: 1;
    }

    table {
        width: 100%;
        border-collapse: collapse;
        min-width: 600px; /* Force scroll on mobile */
    }

    @media (min-width: 768px) {
        table { min-width: 100%; }
    }

    thead {
        background: var(--bg-tertiary);
    }

    th {
        padding: 12px 10px;
        text-align: left;
        font-weight: 600;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--text-secondary);
        border-bottom: 2px solid var(--border-color);
        min-height: 44px;
    }

    @media (min-width: 768px) {
        th { padding: 14px 16px; font-size: 0.85rem; }
    }

    td {
        padding: 10px;
        border-bottom: 1px solid var(--border-color);
        font-variant-numeric: tabular-nums;
        color: var(--text-primary);
        font-size: 0.85rem;
    }

    @media (min-width: 768px) {
        td { padding: 12px 16px; font-size: 0.9rem; }
    }

    /* Touch-friendly row interaction */
    @media (hover: hover) and (pointer: fine) {
        tbody tr:hover {
            background: var(--bg-tertiary);
        }
    }

    @media (hover: none) and (pointer: coarse) {
        tbody tr:active {
            background: var(--bg-tertiary);
        }
    }

    /* Column min-widths */
    th:nth-child(1), td:nth-child(1) { min-width: 120px; }
    th:nth-child(2), td:nth-child(2) { min-width: 150px; }

    /* Text overflow handling */
    td {
        word-break: break-word;
        max-width: 300px;
    }

    td.truncate {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    """


def get_theme_toggle_styles():
    """Returns touch-friendly theme toggle"""
    return """
    .theme-toggle {
        position: fixed;
        top: 16px;
        right: 16px;
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 10px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        box-shadow: 0 4px 12px var(--shadow);
        z-index: 1000;
        transition: all 0.3s ease;
        min-width: 44px;
        min-height: 44px;
    }

    @media (min-width: 768px) {
        .theme-toggle {
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 24px;
        }
    }

    #theme-icon {
        font-size: 1.4rem;
    }

    #theme-label {
        display: none;
        font-size: 0.9rem;
        color: var(--text-primary);
        font-weight: 600;
    }

    @media (min-width: 768px) {
        #theme-label { display: block; }
    }

    /* Touch-friendly interaction */
    @media (hover: hover) and (pointer: fine) {
        .theme-toggle:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 16px var(--shadow);
        }
    }

    @media (hover: none) and (pointer: coarse) {
        .theme-toggle:active {
            transform: scale(0.95);
        }
    }

    /* Prevent tap highlight */
    .theme-toggle {
        -webkit-tap-highlight-color: transparent;
    }
    """


def get_metric_components():
    """Returns responsive metric card system"""
    return """
    .summary-grid {
        display: grid;
        grid-template-columns: 1fr;
        gap: 12px;
        margin-top: 16px;
    }

    @media (min-width: 480px) {
        .summary-grid {
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
        }
    }

    @media (min-width: 768px) {
        .summary-grid {
            grid-template-columns: repeat(3, 1fr);
        }
    }

    @media (min-width: 1024px) {
        .summary-grid {
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        }
    }

    .summary-card {
        background: var(--bg-tertiary);
        padding: 16px;
        border-radius: 8px;
        border-left: 4px solid var(--border-color);
        transition: background-color 0.3s ease;
    }

    .metric-label {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--text-secondary);
        margin-bottom: 8px;
        line-height: 1.2;
    }

    @media (min-width: 768px) {
        .metric-label { font-size: 0.75rem; }
    }

    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: var(--text-primary);
        font-variant-numeric: tabular-nums;
        line-height: 1;
    }

    @media (min-width: 768px) {
        .metric-value { font-size: 2rem; }
    }

    .metric-unit {
        font-size: 0.8rem;
        color: var(--text-secondary);
        margin-top: 4px;
    }

    @media (min-width: 768px) {
        .metric-unit { font-size: 0.875rem; }
    }

    /* RAG colored cards */
    .rag-green {
        background: rgba(16, 185, 129, 0.05);
        border-left-color: var(--color-rag-green);
    }

    .rag-amber {
        background: rgba(245, 158, 11, 0.05);
        border-left-color: var(--color-rag-amber);
    }

    .rag-red {
        background: rgba(239, 68, 68, 0.05);
        border-left-color: var(--color-rag-red);
    }
    """


def get_collapsible_styles():
    """Returns expandable row and glossary patterns"""
    return """
    /* Glossary collapsible section */
    .glossary {
        background: var(--bg-tertiary);
        padding: 0;
        border-radius: 8px;
        margin-top: 20px;
        overflow: hidden;
    }

    @media (min-width: 768px) {
        .glossary { border-radius: 12px; margin-top: 30px; }
    }

    .glossary-header {
        padding: 16px 20px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: space-between;
        user-select: none;
        transition: background-color 0.2s ease;
        min-height: 44px;
    }

    @media (min-width: 768px) {
        .glossary-header { padding: 20px 30px; }
    }

    @media (hover: hover) and (pointer: fine) {
        .glossary-header:hover {
            background: rgba(255, 255, 255, 0.05);
        }
        [data-theme="light"] .glossary-header:hover {
            background: rgba(0, 0, 0, 0.03);
        }
    }

    .glossary-toggle {
        font-size: 1.5rem;
        color: var(--text-secondary);
        transition: transform 0.3s ease;
    }

    .glossary-toggle.expanded {
        transform: rotate(180deg);
    }

    .glossary-content {
        max-height: 0;
        overflow: hidden;
        transition: max-height 0.4s ease;
        padding: 0 20px;
    }

    @media (min-width: 768px) {
        .glossary-content { padding: 0 30px; }
    }

    .glossary-content.expanded {
        max-height: 5000px;
        padding: 0 20px 20px 20px;
    }

    @media (min-width: 768px) {
        .glossary-content.expanded { padding: 0 30px 30px 30px; }
    }

    .glossary-item {
        margin-bottom: 12px;
    }

    .glossary-term {
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 4px;
        font-size: 0.9rem;
    }

    @media (min-width: 768px) {
        .glossary-term { font-size: 1rem; }
    }

    .glossary-definition {
        font-size: 0.85rem;
        color: var(--text-secondary);
        line-height: 1.5;
    }

    @media (min-width: 768px) {
        .glossary-definition { font-size: 0.9rem; }
    }

    /* Expandable table rows */
    tbody tr.data-row {
        cursor: pointer;
        transition: background-color 0.2s ease;
    }

    tbody tr.data-row td:first-child {
        position: relative;
        padding-left: 30px;
    }

    tbody tr.data-row td:first-child::before {
        content: '▶';
        position: absolute;
        left: 12px;
        font-size: 0.7rem;
        color: var(--text-secondary);
        transition: transform 0.3s ease;
    }

    tbody tr.data-row.expanded td:first-child::before {
        transform: rotate(90deg);
    }

    tr.detail-row {
        display: none;
    }

    tr.detail-row.show {
        display: table-row;
    }

    .detail-content {
        padding: 16px;
        background: var(--bg-tertiary);
        animation: slideDown 0.3s ease;
    }

    @media (min-width: 768px) {
        .detail-content { padding: 20px; }
    }

    @keyframes slideDown {
        from {
            opacity: 0;
            max-height: 0;
        }
        to {
            opacity: 1;
            max-height: 1000px;
        }
    }
    """


def get_utility_styles():
    """Returns badges, utilities, and print styles"""
    return """
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 6px 12px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
        margin-bottom: 12px;
    }

    @media (min-width: 768px) {
        .status-badge { padding: 8px 16px; font-size: 0.9rem; }
    }

    .status-good { color: var(--color-rag-green); }
    .status-caution { color: var(--color-rag-amber); }
    .status-action { color: var(--color-rag-red); }
    .status-inactive { color: var(--text-secondary); }

    /* Badge components (usage tables, etc.) */
    .badge {
        display: inline-block;
        padding: 5px 12px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    .badge-success {
        background-color: #10b981;
        color: white;
    }

    .badge-secondary {
        background-color: #6b7280;
        color: white;
    }

    /* Accessibility */
    *:focus-visible {
        outline: 3px solid #667eea;
        outline-offset: 2px;
    }

    /* Reduced motion support */
    @media (prefers-reduced-motion: reduce) {
        * {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }
    }

    /* Print styles */
    @media print {
        body {
            background: white;
            padding: 0;
        }
        .card {
            box-shadow: none;
            border: 1px solid #e5e7eb;
            page-break-inside: avoid;
        }
        .theme-toggle {
            display: none;
        }
        .glossary-content {
            max-height: none !important;
        }
    }

    /* Touch device optimizations */
    @media (hover: none) and (pointer: coarse) {
        * {
            -webkit-tap-highlight-color: transparent;
        }
        button, a, th, .data-row {
            -webkit-tap-highlight-color: rgba(102, 126, 234, 0.2);
        }
    }
    """


def get_theme_toggle_script():
    """Returns theme toggle JavaScript (identical across all dashboards)"""
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
    """Returns glossary toggle JavaScript"""
    return """
    function toggleGlossary() {
        const content = document.getElementById('glossary-content');
        const toggle = document.getElementById('glossary-toggle');
        content.classList.toggle('expanded');
        toggle.classList.toggle('expanded');
    }
    """


def get_table_scroll_script():
    """Returns table scroll detection JavaScript"""
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
    """Returns expandable table row JavaScript"""
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


def get_dashboard_framework(
    header_gradient_start="#667eea",
    header_gradient_end="#764ba2",
    include_table_scroll=True,
    include_expandable_rows=False,
    include_glossary=True,
):
    """
    Returns complete mobile-responsive CSS + JavaScript framework.

    Args:
        header_gradient_start: Start color for header gradient
        header_gradient_end: End color for header gradient
        include_table_scroll: Include table scroll detection script
        include_expandable_rows: Include expandable row functionality
        include_glossary: Include glossary toggle functionality

    Returns:
        Tuple of (css_string, javascript_string)
    """
    # CSS
    css = f"""
    <style>
    {get_theme_variables()}

    /* Header gradient customization */
    :root {{
        --header-gradient-start: {header_gradient_start};
        --header-gradient-end: {header_gradient_end};
    }}

    {get_base_styles()}
    {get_layout_components()}
    {get_table_styles()}
    {get_theme_toggle_styles()}
    {get_metric_components()}
    {get_collapsible_styles()}
    {get_utility_styles()}
    </style>
    """

    # JavaScript
    js_parts = [get_theme_toggle_script()]
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

    return css, javascript
