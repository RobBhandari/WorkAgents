"""
Theme Variables and Color Palette

Provides CSS custom properties for light/dark themes and color systems.
Includes RAG (Red/Amber/Green) status colors and spacing scale.
"""


def get_theme_variables(primary_color="#667eea", secondary_color="#764ba2"):
    """
    Returns CSS custom properties for light/dark themes.

    Args:
        primary_color: Primary brand color (used for header gradient start)
        secondary_color: Secondary brand color (used for header gradient end)

    Returns:
        String of CSS custom properties with :root and [data-theme="dark"] selectors
    """
    return f"""
    :root {{
        /* Background Colors */
        --bg-primary: #f9fafb;
        --bg-secondary: #ffffff;
        --bg-tertiary: #f9fafb;

        /* Text Colors */
        --text-primary: #1f2937;
        --text-secondary: #6b7280;

        /* Border and Shadow */
        --border-color: #e5e7eb;
        --shadow: rgba(0,0,0,0.1);

        /* Brand Colors */
        --header-gradient-start: {primary_color};
        --header-gradient-end: {secondary_color};

        /* RAG Status Colors */
        --color-rag-green: #10b981;
        --color-rag-amber: #f59e0b;
        --color-rag-red: #ef4444;

        /* Spacing Scale */
        --spacing-xs: 8px;
        --spacing-sm: 12px;
        --spacing-md: 16px;
        --spacing-lg: 24px;
        --spacing-xl: 32px;
    }}

    [data-theme="dark"] {{
        /* Dark Mode Background Colors */
        --bg-primary: #0f172a;
        --bg-secondary: #1e293b;
        --bg-tertiary: #334155;

        /* Dark Mode Text Colors */
        --text-primary: #f1f5f9;
        --text-secondary: #cbd5e1;

        /* Dark Mode Border and Shadow */
        --border-color: #475569;
        --shadow: rgba(0,0,0,0.3);
    }}
    """


def get_color_palette_docs():
    """
    Returns documentation for the color palette and theme system.
    Used for reference and auto-generated documentation.
    """
    return {
        "backgrounds": {
            "primary": "Main page background",
            "secondary": "Card and panel backgrounds",
            "tertiary": "Nested content and subtle highlights",
        },
        "text": {"primary": "Main text color (headings, body)", "secondary": "Secondary text (captions, labels)"},
        "rag_colors": {
            "green": "#10b981 - Success, healthy, on-track",
            "amber": "#f59e0b - Warning, caution, needs attention",
            "red": "#ef4444 - Error, critical, action required",
        },
        "spacing_scale": {
            "xs": "8px - Tight spacing (icon gaps, inline elements)",
            "sm": "12px - Small spacing (list items, small cards)",
            "md": "16px - Medium spacing (card padding, section gaps)",
            "lg": "24px - Large spacing (section margins)",
            "xl": "32px - Extra large spacing (major sections)",
        },
    }
