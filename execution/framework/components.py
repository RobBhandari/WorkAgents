"""
UI Component Styles

Provides reusable component styles for cards, headers, metrics, and theme toggle.
All components are mobile-responsive with progressive enhancement.
"""


def get_layout_components():
    """
    Returns mobile-responsive layout component styles.

    Includes:
    - Header with gradient background
    - Card containers
    - Section spacing

    Returns:
        String of layout component CSS
    """
    return """
    /* Header Component */
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

    /* Card Component */
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

    /* Section Component */
    .section {
        margin-bottom: 24px;
    }

    @media (min-width: 768px) {
        .section { margin-bottom: 30px; }
    }
    """


def get_metric_components():
    """
    Returns responsive metric card and summary grid styles.

    Includes:
    - Responsive grid layout (1 col mobile → 2 col phablet → 3+ col desktop)
    - Metric cards with labels, values, and units
    - RAG status colored cards

    Returns:
        String of metric component CSS
    """
    return """
    /* Summary Grid */
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

    /* Summary Card */
    .summary-card {
        background: var(--bg-tertiary);
        padding: 16px;
        border-radius: 8px;
        border-left: 4px solid var(--border-color);
        transition: background-color 0.3s ease;
    }

    /* Metric Label */
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

    /* Metric Value */
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

    /* Metric Unit */
    .metric-unit {
        font-size: 0.8rem;
        color: var(--text-secondary);
        margin-top: 4px;
    }

    @media (min-width: 768px) {
        .metric-unit { font-size: 0.875rem; }
    }

    /* RAG Status Colors */
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


def get_theme_toggle_styles():
    """
    Returns touch-friendly theme toggle button styles.

    Includes:
    - Fixed position button
    - Icon and label layout
    - Touch-optimized interactions
    - Responsive sizing

    Returns:
        String of theme toggle CSS
    """
    return """
    /* Theme Toggle Button */
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

    /* Touch-Friendly Interaction */
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

    /* Prevent Tap Highlight */
    .theme-toggle {
        -webkit-tap-highlight-color: transparent;
    }
    """
