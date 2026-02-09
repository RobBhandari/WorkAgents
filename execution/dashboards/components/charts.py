"""
Chart components for dashboards

Provides reusable chart HTML generators (sparklines, trends).
"""


def sparkline(values: list[float], width: int = 100, height: int = 30, color: str = "currentColor") -> str:
    """
    Generate an inline SVG sparkline chart.

    Args:
        values: List of numeric values to plot
        width: SVG width in pixels
        height: SVG height in pixels
        color: Line color (CSS color value or 'currentColor')

    Returns:
        HTML string with inline SVG sparkline

    Example:
        svg = sparkline([10, 15, 12, 18, 20], width=150, height=40)
    """
    if not values or len(values) < 2:
        return ""

    # Normalize values to fit in SVG
    min_val = min(values)
    max_val = max(values)
    value_range = max_val - min_val if max_val != min_val else 1

    # Generate points for polyline
    points = []
    for i, val in enumerate(values):
        x = (i / (len(values) - 1)) * width
        y = height - ((val - min_val) / value_range * height)
        points.append(f"{x:.2f},{y:.2f}")

    polyline = " ".join(points)

    return f"""
    <svg class="sparkline" width="{width}" height="{height}"
         viewBox="0 0 {width} {height}"
         xmlns="http://www.w3.org/2000/svg">
        <polyline points="{polyline}"
                  fill="none"
                  stroke="{color}"
                  stroke-width="1.5"/>
    </svg>
    """


def trend_indicator(change: float, show_value: bool = True) -> str:
    """
    Generate a trend indicator (arrow + value).

    Args:
        change: Numeric change value (positive = up, negative = down)
        show_value: Whether to show the numeric value

    Returns:
        HTML string for trend indicator

    Example:
        # Shows: ↓ -5
        indicator = trend_indicator(-5)

        # Shows: ↑
        indicator = trend_indicator(10, show_value=False)
    """
    if change > 0:
        arrow = "↑"
        css_class = "trend-up"
    elif change < 0:
        arrow = "↓"
        css_class = "trend-down"
    else:
        arrow = "→"
        css_class = "trend-neutral"

    value_text = f" {change:+.0f}" if show_value else ""

    return f'<span class="trend-indicator {css_class}">{arrow}{value_text}</span>'


def percentage_bar(percentage: float, label: str = "", show_value: bool = True) -> str:
    """
    Generate a horizontal percentage bar.

    Args:
        percentage: Percentage value (0-100)
        label: Optional label text
        show_value: Whether to show the percentage value

    Returns:
        HTML string for percentage bar

    Example:
        bar = percentage_bar(65.5, label="Progress to Target")
        # Shows a 65.5% filled bar with label
    """
    # Clamp percentage to 0-100
    pct = max(0, min(100, percentage))

    # Determine color based on percentage
    if pct >= 75:
        color_class = "progress-good"
    elif pct >= 50:
        color_class = "progress-ok"
    elif pct >= 25:
        color_class = "progress-warning"
    else:
        color_class = "progress-critical"

    label_html = f'<span class="progress-label">{label}</span>' if label else ""
    value_html = f'<span class="progress-value">{pct:.1f}%</span>' if show_value else ""

    return f"""
    <div class="progress-container">
        {label_html}
        <div class="progress-bar">
            <div class="progress-fill {color_class}" style="width: {pct}%"></div>
        </div>
        {value_html}
    </div>
    """


def mini_chart(values: list[float], labels: list[str] | None = None, chart_type: str = "bar") -> str:
    """
    Generate a mini chart (bar or line) using SVG.

    Args:
        values: List of numeric values
        labels: Optional list of labels (same length as values)
        chart_type: 'bar' or 'line'

    Returns:
        HTML string with SVG chart

    Example:
        chart = mini_chart([10, 15, 8, 20], chart_type='bar')
    """
    if not values:
        return ""

    width = 200
    height = 100
    padding = 10

    # Normalize values
    max_val = max(values) if values else 1
    bar_width = (width - padding * 2) / len(values)

    if chart_type == "bar":
        # Generate bars
        bars = []
        for i, val in enumerate(values):
            bar_height = (val / max_val) * (height - padding * 2)
            x = padding + i * bar_width + bar_width * 0.1
            y = height - padding - bar_height
            bar_width_actual = bar_width * 0.8

            bars.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" '
                f'width="{bar_width_actual:.2f}" height="{bar_height:.2f}" '
                f'fill="currentColor" opacity="0.8"/>'
            )

        content = "\n".join(bars)

    else:  # line chart
        # Generate polyline
        points = []
        for i, val in enumerate(values):
            x = padding + i * bar_width + bar_width / 2
            y = height - padding - (val / max_val) * (height - padding * 2)
            points.append(f"{x:.2f},{y:.2f}")

        polyline = " ".join(points)
        content = f'<polyline points="{polyline}" fill="none" stroke="currentColor" stroke-width="2"/>'

    return f"""
    <svg class="mini-chart" width="{width}" height="{height}"
         viewBox="0 0 {width} {height}"
         xmlns="http://www.w3.org/2000/svg">
        {content}
    </svg>
    """
