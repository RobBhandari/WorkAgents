"""
Responsive Utilities and Accessibility

Provides utility classes for badges, status indicators, accessibility features,
print styles, and touch device optimizations.
"""


def get_utility_styles():
    """
    Returns utility styles including badges, accessibility, and print styles.

    Includes:
    - Status badges with RAG colors
    - Badge components for labels
    - Accessibility (focus-visible, reduced motion)
    - Print optimization styles
    - Touch device tap highlight prevention

    Returns:
        String of utility CSS
    """
    return """
    /* Status Badges */
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

    /* Badge Components */
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

    /* Accessibility: Focus Visible */
    *:focus-visible {
        outline: 3px solid #667eea;
        outline-offset: 2px;
    }

    /* Reduced Motion Support */
    @media (prefers-reduced-motion: reduce) {
        * {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }
    }

    /* Print Styles */
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

    /* Touch Device Optimizations */
    @media (hover: none) and (pointer: coarse) {
        * {
            -webkit-tap-highlight-color: transparent;
        }
        button, a, th, .data-row {
            -webkit-tap-highlight-color: rgba(102, 126, 234, 0.2);
        }
    }
    """


def get_responsive_breakpoints():
    """
    Returns documentation for responsive breakpoint system.

    Provides comprehensive documentation for the mobile-first responsive
    breakpoint strategy including specific pixel ranges, media queries,
    and usage patterns.

    Returns:
        Dictionary containing responsive breakpoint documentation including:
        - Breakpoint ranges and media queries
        - Mobile-first strategy principles
        - Touch optimization guidelines

    Example:
        >>> docs = get_responsive_breakpoints()
        >>> print(docs['breakpoints']['tablet']['query'])
        '@media (min-width: 768px)'
    """
    return {
        "breakpoints": {
            "mobile": {
                "range": "320px - 479px",
                "description": "Default baseline, 1-column layouts",
                "usage": "No media query needed (mobile-first)",
            },
            "phablet": {
                "range": "480px - 767px",
                "query": "@media (min-width: 480px)",
                "description": "Large phones, 2-column grids start",
                "usage": "Progressive enhancement from mobile",
            },
            "tablet": {
                "range": "768px - 1023px",
                "query": "@media (min-width: 768px)",
                "description": "Tablets, 3-column grids, larger typography",
                "usage": "Most significant layout changes",
            },
            "desktop": {
                "range": "1024px+",
                "query": "@media (min-width: 1024px)",
                "description": "Desktop screens, maximum spacing and type size",
                "usage": "Final polish for large screens",
            },
        },
        "mobile_first_strategy": {
            "principle": "Start with mobile styles (320px), progressively enhance for larger screens",
            "benefits": [
                "Faster mobile load times (no need to override desktop styles)",
                "Simpler CSS (add features instead of removing them)",
                "Better accessibility (keyboard and touch-friendly by default)",
            ],
            "example": """
                /* Mobile-first example */
                .grid { grid-template-columns: 1fr; }  /* Default: 1 column */
                @media (min-width: 480px) { .grid { grid-template-columns: repeat(2, 1fr); } }
                @media (min-width: 768px) { .grid { grid-template-columns: repeat(3, 1fr); } }
            """,
        },
        "touch_optimization": {
            "min_tap_target": "44x44px (Apple, Android guidelines)",
            "hover_detection": "@media (hover: hover) - only apply hover on mouse devices",
            "coarse_pointer": "@media (pointer: coarse) - touch-specific interactions",
        },
    }


def get_accessibility_guidelines():
    """
    Returns documentation for accessibility features.

    Provides comprehensive documentation for accessibility features including
    focus indicators, reduced motion support, color contrast, and touch targets.

    Returns:
        Dictionary containing accessibility guidelines including:
        - Focus indicators for keyboard navigation
        - Reduced motion preferences
        - Color contrast ratios (WCAG compliance)
        - Touch target minimum sizes
        - Screen reader support

    Example:
        >>> docs = get_accessibility_guidelines()
        >>> print(docs['touch_targets']['minimum_size'])
        '44x44px for all interactive elements'
    """
    return {
        "focus_indicators": {
            "implementation": "*:focus-visible { outline: 3px solid #667eea; outline-offset: 2px; }",
            "rationale": "Clear, high-contrast focus indicators for keyboard navigation",
        },
        "reduced_motion": {
            "implementation": "@media (prefers-reduced-motion: reduce)",
            "rationale": "Respects user's OS-level motion preferences, disables animations",
        },
        "color_contrast": {
            "text_primary": "4.5:1 minimum contrast ratio (WCAG AA)",
            "text_secondary": "Used for non-essential text (captions, labels)",
            "rag_colors": "Sufficiently different for colorblind users",
        },
        "touch_targets": {
            "minimum_size": "44x44px for all interactive elements",
            "implementation": "min-height: 44px on buttons, th, interactive rows",
        },
        "screen_reader_support": {
            "semantic_html": "Use proper HTML5 elements (<header>, <nav>, <main>, etc.)",
            "aria_labels": "Add aria-label where text content isn't sufficient",
            "skip_links": "Consider adding skip-to-content links for long pages",
        },
    }
