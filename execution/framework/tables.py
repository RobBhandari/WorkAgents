"""
Table Styles and Collapsible Components

Provides mobile-optimized table styles with horizontal scrolling,
expandable rows, and glossary collapsible sections.
"""


def get_table_styles():
    """
    Returns mobile-optimized table styles with horizontal scroll support.

    Includes:
    - Scrollable table wrapper with touch optimization
    - Custom scrollbar styles
    - Fade gradient indicator for scrollable content
    - Touch-friendly row interactions
    - Column sizing and text overflow handling

    Returns:
        String of table CSS
    """
    return """
    /* Table Wrapper with Horizontal Scroll */
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

    /* Fade Gradient Indicator */
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

    /* Table Base Styles */
    table {
        width: 100%;
        border-collapse: collapse;
        min-width: 600px; /* Force scroll on mobile */
    }

    @media (min-width: 768px) {
        table { min-width: 100%; }
    }

    /* Table Header */
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

    /* Table Data Cells */
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

    /* Touch-Friendly Row Interaction */
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

    /* Column Min-Widths */
    th:nth-child(1), td:nth-child(1) { min-width: 120px; }
    th:nth-child(2), td:nth-child(2) { min-width: 150px; }

    /* Text Overflow Handling */
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


def get_collapsible_styles():
    """
    Returns expandable row and glossary collapsible section styles.

    Includes:
    - Glossary toggle section
    - Expandable table rows with animations
    - Touch-friendly toggle interactions
    - Smooth expand/collapse animations

    Returns:
        String of collapsible component CSS
    """
    return """
    /* Glossary Collapsible Section */
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

    /* Expandable Table Rows */
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
