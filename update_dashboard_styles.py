"""
Update all dashboard templates with refined minimalist CSS.

This script replaces the old aggressive CSS overrides with the refined,
subtle minimalist styling from the Executive Trends dashboard (index_MINIMALIST.html).
"""

from pathlib import Path

# Refined minimalist CSS (extracted from index_MINIMALIST.html)
# NOTE: This is a simplified version that applies to all dashboards
# Dashboard-specific styles (tables, cards, etc.) will use framework defaults
REFINED_CSS = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">

<style>
/* ═══════════════════════════════════════════════════════════════
   MODERN MINIMALIST - Refined Dashboard Styling
   Design Direction: Clean, Refined, Professional
   Inspiration: Stripe, Linear, Modern SaaS dashboards
   ═══════════════════════════════════════════════════════════════ */

:root {
    --color-slate-50: #f8fafc;
    --color-slate-100: #f1f5f9;
    --color-slate-200: #e2e8f0;
    --color-slate-300: #cbd5e1;
    --color-slate-400: #94a3b8;
    --color-slate-500: #64748b;
    --color-slate-600: #475569;
    --color-slate-700: #334155;
    --color-slate-800: #1e293b;
    --color-slate-900: #0f172a;

    --color-blue-400: #60a5fa;
    --color-blue-500: #3b82f6;
    --color-blue-600: #2563eb;

    --color-emerald-500: #10b981;
    --color-amber-500: #f59e0b;
    --color-red-500: #ef4444;

    --header-gradient-start: var(--color-slate-900) !important;
    --header-gradient-end: var(--color-slate-900) !important;
}

/* Refined typography - Inter with OpenType features */
body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    background: var(--color-slate-900) !important;
    color: #ffffff !important;
    font-feature-settings: 'cv02', 'cv03', 'cv04', 'cv11';
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

/* Sophisticated header */
body .header,
.container .header,
div.header {
    background: var(--color-slate-900) !important;
    border: none !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 64px 32px !important;
}

.header h1 {
    font-weight: 600 !important;
    letter-spacing: -0.02em !important;
    color: #ffffff !important;
    text-transform: none !important;
    font-size: 2.5rem !important;
}

.header p,
.header .subtitle {
    color: var(--color-slate-400) !important;
    font-weight: 400 !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
}

/* Summary Cards - Refined with subtle borders */
.summary-card,
.card {
    background: var(--color-slate-900) !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-radius: 8px !important;
    padding: 24px !important;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06) !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

.summary-card:hover,
.card:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.3) !important;
    border-color: rgba(59, 130, 246, 0.3) !important;
}

/* Tables - Refined styling */
table {
    border-collapse: collapse !important;
}

th {
    background: var(--color-slate-800) !important;
    color: var(--color-slate-400) !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    padding: 14px 16px !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06) !important;
}

tbody tr {
    border-bottom: 1px solid rgba(255, 255, 255, 0.06) !important;
    transition: background-color 0.2s ease !important;
}

tbody tr:hover {
    background: rgba(255, 255, 255, 0.02) !important;
}

td {
    padding: 12px 16px !important;
    color: #ffffff !important;
}

/* Chevron indicators for expandable rows */
tbody tr.data-row td:first-child {
    position: relative !important;
    padding-left: 30px !important;
}

tbody tr.data-row td:first-child::before {
    content: '▶';
    position: absolute;
    left: 12px;
    font-size: 0.7rem;
    color: var(--color-slate-400);
    transition: transform 0.3s ease;
}

tbody tr.data-row.expanded td:first-child::before {
    transform: rotate(90deg);
}

/* Status badges - Refined colors */
.status-good { color: var(--color-emerald-500) !important; }
.status-caution { color: var(--color-amber-500) !important; }
.status-action { color: var(--color-red-500) !important; }
.status-inactive { color: var(--color-slate-500) !important; }

/* Detail rows - Refined styling */
.detail-row {
    display: none;
}

.detail-row.show {
    display: table-row;
}

.detail-content {
    background: var(--color-slate-800) !important;
    padding: 24px !important;
    border-left: 2px solid rgba(59, 130, 246, 0.3) !important;
}

.detail-section {
    margin-bottom: 20px;
}

.detail-section h3,
.detail-section h4 {
    color: #ffffff !important;
    margin-bottom: 12px;
}

.detail-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
}

.detail-metric {
    background: var(--color-slate-900) !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-radius: 8px !important;
    padding: 16px !important;
    color: var(--color-slate-300) !important;
}

.detail-metric-label {
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    color: var(--color-slate-400) !important;
    margin-bottom: 8px !important;
    letter-spacing: 0.05em !important;
}

.detail-metric-value {
    font-size: 1.5rem !important;
    font-weight: 600 !important;
    color: #ffffff !important;
}

/* ═══════════════════════════════════════════════════════════════
   LIGHT THEME SUPPORT - Complete styling for light mode
   ═══════════════════════════════════════════════════════════════ */

[data-theme="light"] body {
    background: #ffffff !important;
    color: var(--color-slate-900) !important;
}

[data-theme="light"] .header {
    background: #ffffff !important;
    border-bottom-color: var(--color-slate-200) !important;
}

[data-theme="light"] .header h1 {
    color: var(--color-slate-900) !important;
}

[data-theme="light"] .header p,
[data-theme="light"] .header .subtitle {
    color: var(--color-slate-600) !important;
}

[data-theme="light"] .summary-card,
[data-theme="light"] .card {
    background: #ffffff !important;
    border-color: var(--color-slate-200) !important;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px 0 rgba(0, 0, 0, 0.03) !important;
}

[data-theme="light"] .summary-card:hover,
[data-theme="light"] .card:hover {
    border-color: var(--color-blue-400) !important;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.05) !important;
}

[data-theme="light"] th {
    background: var(--color-slate-100) !important;
    color: var(--color-slate-700) !important;
    border-bottom-color: var(--color-slate-200) !important;
}

[data-theme="light"] tbody tr {
    border-bottom-color: var(--color-slate-200) !important;
}

[data-theme="light"] tbody tr:hover {
    background: var(--color-slate-50) !important;
}

[data-theme="light"] td {
    color: var(--color-slate-900) !important;
}

/* Detail rows - Light Mode */
[data-theme="light"] .detail-content {
    background: var(--color-slate-100) !important;
}

[data-theme="light"] .detail-metric {
    background: #ffffff !important;
    border-color: var(--color-slate-200) !important;
}

[data-theme="light"] .detail-metric-value {
    color: var(--color-slate-900) !important;
}

/* Chevron - Light Mode */
[data-theme="light"] tbody tr.data-row td:first-child::before {
    color: var(--color-slate-600) !important;
}

/* Footer - Light Mode */
[data-theme="light"] .footer p {
    color: var(--color-slate-600) !important;
}
</style>
"""


def update_dashboard_template(template_path: Path) -> bool:
    """
    Update a single dashboard template with refined CSS.

    Args:
        template_path: Path to template file

    Returns:
        True if updated, False if skipped
    """
    content = template_path.read_text(encoding="utf-8")

    # Check if template has extra_css block
    if "{% block extra_css %}" not in content:
        print(f"SKIP  Skipping {template_path.name} (no extra_css block)")
        return False

    # Find the extra_css block boundaries
    start_marker = "{% block extra_css %}"
    end_marker = "{% endblock %}"

    start_idx = content.find(start_marker)
    if start_idx == -1:
        print(f"SKIP  Skipping {template_path.name} (no extra_css block)")
        return False

    # Find the corresponding endblock (could be first one after extra_css)
    search_start = start_idx + len(start_marker)
    end_idx = content.find(end_marker, search_start)

    if end_idx == -1:
        print(f"ERROR Error in {template_path.name} (no matching endblock)")
        return False

    # Reconstruct the template with new CSS
    before_css = content[:start_idx + len(start_marker)]
    after_css = content[end_idx:]

    new_content = before_css + "\n" + REFINED_CSS + "\n" + after_css

    # Write updated template
    template_path.write_text(new_content, encoding="utf-8")
    print(f"OK Updated {template_path.name}")
    return True


def main():
    """Update all dashboard templates."""
    templates_dir = Path("templates/dashboards")

    if not templates_dir.exists():
        print(f"ERROR Templates directory not found: {templates_dir}")
        return

    # Find all dashboard templates (excluding base)
    templates = list(templates_dir.glob("*_dashboard.html"))
    templates = [t for t in templates if t.name != "base_dashboard.html"]

    print(f"Found {len(templates)} dashboard templates to update\n")

    updated_count = 0
    for template_path in sorted(templates):
        if update_dashboard_template(template_path):
            updated_count += 1

    print(f"\nDone Updated {updated_count}/{len(templates)} dashboard templates")


if __name__ == "__main__":
    main()
