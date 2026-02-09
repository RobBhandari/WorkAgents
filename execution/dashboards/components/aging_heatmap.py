"""
Aging Heatmap Component

Generates HTML heatmap showing vulnerability age distribution by severity.

Usage:
    from execution.dashboards.components.aging_heatmap import generate_aging_heatmap

    vulnerabilities = [...]  # List of VulnerabilityDetail objects
    heatmap_html = generate_aging_heatmap(vulnerabilities)
"""


def generate_aging_heatmap(vulnerabilities: list) -> str:
    """
    Generate HTML for aging heatmap visualization.

    Shows vulnerability counts by age bucket (0-7, 8-14, 15-30, 31-90, 90+ days)
    and severity (Critical, High).

    Args:
        vulnerabilities: List of vulnerability objects with 'severity' and 'age_days' attributes

    Returns:
        HTML string for heatmap

    Example:
        vulns = [Vulnerability(severity='CRITICAL', age_days=15), ...]
        html = generate_aging_heatmap(vulns)
    """
    if not vulnerabilities:
        return '<div class="no-data">No vulnerability details available</div>'

    # Define age buckets
    age_buckets = [
        {"label": "0-7", "min": 0, "max": 7},
        {"label": "8-14", "min": 8, "max": 14},
        {"label": "15-30", "min": 15, "max": 30},
        {"label": "31-90", "min": 31, "max": 90},
        {"label": "90+", "min": 91, "max": 999999},
    ]

    # Initialize counts
    heatmap_data = {
        "CRITICAL": {bucket["label"]: 0 for bucket in age_buckets},
        "HIGH": {bucket["label"]: 0 for bucket in age_buckets},
    }

    # Count vulnerabilities by severity and age bucket
    for vuln in vulnerabilities:
        severity = vuln.severity if hasattr(vuln, "severity") else vuln.get("severity", "")
        age_days = vuln.age_days if hasattr(vuln, "age_days") else vuln.get("age_days", 0)

        if severity not in ["CRITICAL", "HIGH"]:
            continue

        for bucket in age_buckets:
            if bucket["min"] <= age_days <= bucket["max"]:
                heatmap_data[severity][bucket["label"]] += 1
                break

    # Calculate max value for color intensity scaling
    max_count = 0
    for severity_data in heatmap_data.values():
        max_count = max(max_count, max(severity_data.values()))

    # Generate heatmap HTML
    html_parts = []
    html_parts.append('<div class="detail-content">')
    html_parts.append('<div class="heatmap-container">')
    html_parts.append('<div class="heatmap-header">')
    html_parts.append("<h4>Finding Age Distribution</h4>")
    html_parts.append('<p class="heatmap-subtitle">Vulnerability count by age and severity</p>')
    html_parts.append("</div>")

    # Heatmap grid
    html_parts.append('<div class="heatmap-grid">')
    html_parts.append('<div class="heatmap-corner"></div>')

    # Age bucket headers
    for bucket in age_buckets:
        html_parts.append(
            f'<div class="heatmap-col-header">{bucket["label"]}<span class="days-label">DAYS</span></div>'
        )

    # Critical row
    html_parts.append('<div class="heatmap-row-header critical-header">Critical</div>')
    for bucket in age_buckets:
        count = heatmap_data["CRITICAL"][bucket["label"]]
        intensity = (count / max_count) if max_count > 0 else 0
        html_parts.append(_generate_heatmap_cell(count, intensity, "critical"))

    # High row
    html_parts.append('<div class="heatmap-row-header high-header">High</div>')
    for bucket in age_buckets:
        count = heatmap_data["HIGH"][bucket["label"]]
        intensity = (count / max_count) if max_count > 0 else 0
        html_parts.append(_generate_heatmap_cell(count, intensity, "high"))

    html_parts.append("</div>")  # heatmap-grid
    html_parts.append("</div>")  # heatmap-container
    html_parts.append("</div>")  # detail-content

    return "".join(html_parts)


def _generate_heatmap_cell(count: int, intensity: float, severity_type: str) -> str:
    """
    Generate a single heatmap cell with appropriate styling.

    Args:
        count: Number of vulnerabilities in this cell
        intensity: Color intensity (0.0 to 1.0)
        severity_type: 'critical' or 'high'

    Returns:
        HTML string for cell
    """
    if count == 0:
        # Empty cell - subtle gray
        return (
            '<div class="heatmap-cell empty" '
            'style="background: rgba(148, 163, 184, 0.1); color: var(--text-secondary);"></div>'
        )

    # Determine background color based on severity and intensity
    if severity_type == "critical":
        # Red color scale for critical
        if intensity < 0.3:
            bg_color = f"rgba(239, 68, 68, {0.3 + intensity * 0.3})"
        elif intensity < 0.7:
            bg_color = f"rgba(239, 68, 68, {0.6 + intensity * 0.2})"
        else:
            bg_color = f"rgba(220, 38, 38, {0.8 + intensity * 0.2})"
    else:
        # Orange/amber scale for high
        if intensity < 0.3:
            bg_color = f"rgba(251, 146, 60, {0.3 + intensity * 0.3})"
        elif intensity < 0.7:
            bg_color = f"rgba(249, 115, 22, {0.6 + intensity * 0.2})"
        else:
            bg_color = f"rgba(234, 88, 12, {0.8 + intensity * 0.2})"

    # Text color - white for high intensity, darker for low
    text_color = "#ffffff" if intensity > 0.5 else "var(--text-primary)"

    return f'<div class="heatmap-cell" style="background: {bg_color}; color: {text_color};">{count}</div>'


def get_aging_heatmap_styles() -> str:
    """
    Get CSS styles for aging heatmap.

    Returns:
        CSS string to include in <style> tag
    """
    return """
        /* Aging Heatmap Styles */
        .heatmap-container {
            margin: 20px 0;
            padding: 20px;
            background: var(--bg-secondary);
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .heatmap-header h4 {
            margin: 0 0 8px 0;
            font-size: 1.1rem;
            color: var(--text-primary);
        }

        .heatmap-subtitle {
            margin: 0 0 16px 0;
            font-size: 0.9rem;
            color: var(--text-secondary);
        }

        .heatmap-grid {
            display: grid;
            grid-template-columns: 100px repeat(5, 1fr);
            gap: 8px;
            align-items: center;
        }

        @media (max-width: 768px) {
            .heatmap-grid {
                grid-template-columns: 80px repeat(5, 1fr);
                gap: 4px;
                font-size: 0.85rem;
            }
        }

        .heatmap-corner {
            background: transparent;
        }

        .heatmap-col-header {
            text-align: center;
            font-weight: 600;
            font-size: 0.9rem;
            color: var(--text-secondary);
            padding: 8px 4px;
        }

        .days-label {
            display: block;
            font-size: 0.65rem;
            font-weight: 400;
            opacity: 0.7;
            margin-top: 2px;
        }

        .heatmap-row-header {
            font-weight: 600;
            font-size: 0.95rem;
            padding: 12px 8px;
            text-align: right;
            border-radius: 4px;
        }

        .critical-header {
            color: #ef4444;
            background: rgba(239, 68, 68, 0.1);
        }

        .high-header {
            color: #f59e0b;
            background: rgba(245, 158, 11, 0.1);
        }

        .heatmap-cell {
            padding: 16px 8px;
            text-align: center;
            font-weight: 700;
            font-size: 1.1rem;
            border-radius: 6px;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            cursor: default;
        }

        .heatmap-cell:not(.empty):hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 10;
        }

        .heatmap-cell.empty {
            font-size: 0.8rem;
        }

        .no-data {
            padding: 40px;
            text-align: center;
            color: var(--text-secondary);
            font-style: italic;
        }
    """


# Self-test
if __name__ == "__main__":
    print("Aging Heatmap Component - Self Test")
    print("=" * 60)

    # Mock vulnerability data
    class MockVuln:
        def __init__(self, severity: str, age_days: int):
            self.severity = severity
            self.age_days = age_days

    test_vulns = [
        MockVuln("CRITICAL", 5),
        MockVuln("CRITICAL", 12),
        MockVuln("CRITICAL", 25),
        MockVuln("CRITICAL", 95),
        MockVuln("HIGH", 3),
        MockVuln("HIGH", 15),
        MockVuln("HIGH", 45),
        MockVuln("HIGH", 120),
    ]

    heatmap_html = generate_aging_heatmap(test_vulns)
    print(f"Generated heatmap HTML: {len(heatmap_html)} characters")

    styles = get_aging_heatmap_styles()
    print(f"Generated heatmap styles: {len(styles)} characters")

    # Write test HTML
    test_file = ".tmp/test_heatmap.html"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Heatmap Test</title>
    <style>
        :root {{
            --bg-primary: #f9fafb;
            --bg-secondary: #ffffff;
            --text-primary: #1f2937;
            --text-secondary: #6b7280;
        }}
        body {{ font-family: sans-serif; padding: 20px; background: var(--bg-primary); }}
        {styles}
    </style>
</head>
<body>
    <h1>Aging Heatmap Component Test</h1>
    {heatmap_html}
</body>
</html>""")

    print(f"\n[SUCCESS] Test HTML written to: {test_file}")
    print("Open in browser to view heatmap")
