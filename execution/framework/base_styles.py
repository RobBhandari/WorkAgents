"""
Base Styles and Typography

Provides mobile-first base styles, CSS reset, and responsive typography scale.
Forms the foundation for all dashboard styling.
"""


def get_base_styles():
    """
    Returns mobile-first base styles with progressive enhancement.

    Includes:
    - CSS reset (box-sizing, margin, padding)
    - Body and font styles
    - Responsive typography scale (mobile → tablet → desktop)
    - Accessibility-friendly line heights

    Returns:
        String of base CSS styles
    """
    return """
    /* CSS Reset */
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }

    /* Body and Font Styles */
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
        background: var(--bg-primary);
        padding: 12px;
        color: var(--text-primary);
        transition: background-color 0.3s ease, color 0.3s ease;
        line-height: 1.6;
    }

    /* Progressive Enhancement for Larger Screens */
    @media (min-width: 480px) {
        body { padding: 16px; }
    }

    @media (min-width: 768px) {
        body { padding: 20px; }
    }

    /* Responsive Typography Scale */
    h1 {
        font-size: 1.5rem;
        line-height: 1.2;
        margin-bottom: 8px;
    }

    h2 {
        font-size: 1.2rem;
        line-height: 1.3;
        margin-bottom: 8px;
    }

    h3 {
        font-size: 1rem;
        line-height: 1.4;
        margin-bottom: 8px;
    }

    /* Tablet Typography */
    @media (min-width: 768px) {
        h1 { font-size: 2rem; }
        h2 { font-size: 1.5rem; }
        h3 { font-size: 1.25rem; }
    }

    /* Desktop Typography */
    @media (min-width: 1024px) {
        h1 { font-size: 2.5rem; }
        h2 { font-size: 1.75rem; }
    }

    /* Paragraph Styles */
    p {
        margin-bottom: 12px;
    }

    /* Container */
    .container {
        max-width: 1400px;
        margin: 0 auto;
        width: 100%;
    }
    """


def get_reset_docs():
    """
    Returns documentation for the CSS reset and base styles.
    """
    return {
        "reset": "Removes browser defaults for consistent cross-browser styling",
        "mobile_first": "Base styles target mobile (320px+), progressively enhance for larger screens",
        "breakpoints": {
            "mobile": "320px - 479px (default)",
            "phablet": "480px - 767px",
            "tablet": "768px - 1023px",
            "desktop": "1024px+",
        },
        "typography_scale": {
            "h1": "1.5rem mobile → 2rem tablet → 2.5rem desktop",
            "h2": "1.2rem mobile → 1.5rem tablet → 1.75rem desktop",
            "h3": "1rem mobile → 1.25rem tablet",
        },
    }
