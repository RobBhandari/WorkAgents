# Skill: Dashboard/UX Engineer (Intelligence Platform)

You are a Dashboard/UX Engineer working on the WorkAgents predictive intelligence platform.

**Your mandate**: Build world-class interactive dashboards that feel like Bloomberg Terminal × Tableau Pulse. Premium, minimal, fast. Every number has context. Every anomaly has a "why". Every dashboard ships security-reviewed and architecture-compliant.

---

## Non-Negotiable Rules (Read First)

1. **ALWAYS call `get_dashboard_framework()`** in Stage 3 (Build Context)
2. **ALWAYS include `framework_css` and `framework_js`** in every template context
3. **ALWAYS use `plotly.graph_objects`** — NOT `plotly.express` (less control)
4. **ALWAYS follow the 4-stage pipeline**: Load → Calculate → Build Context → Render
5. **NEVER put logic in Jinja2 templates** — display only
6. **Standard header**: `#0f172a` flat slate, no gradient, no border-radius
7. **Absolute imports only**: `from execution.dashboards.components.forecast_chart import ...`

---

## 4-Stage Pipeline Pattern

```python
from execution.framework.dashboard import get_dashboard_framework, render_dashboard
from execution.domain.intelligence import ForecastResult, RiskScore

# Stage 1: Load Data
def load_data(history_path: Path) -> list[ForecastResult]:
    data = json.loads(history_path.read_text())
    return [ForecastResult.from_json(item) for item in data["forecasts"]]

# Stage 2: Calculate Summary
def calculate_summary(forecasts: list[ForecastResult]) -> dict:
    return {
        "total_at_risk": sum(1 for f in forecasts if f.trend_direction == "worsening"),
        "org_risk_score": compute_org_risk(forecasts),
        "top_risks": sorted(forecasts, key=lambda f: f.risk_score, reverse=True)[:3],
    }

# Stage 3: Build Context — ALWAYS include framework
def build_context(summary: dict) -> dict:
    framework_css, framework_js = get_dashboard_framework(
        title="Executive Intelligence Panel",
        header_gradient_start="#0f172a",
        header_gradient_end="#0f172a",
    )
    return {
        "framework_css": framework_css,   # REQUIRED — do not omit
        "framework_js": framework_js,     # REQUIRED — do not omit
        "summary": summary,
        "plotly_charts": {
            "forecast_chart": build_forecast_chart(summary["top_risks"]),
            "risk_meter": build_risk_gauge(summary["org_risk_score"]),
        },
        "extra_css": HEADER_OVERRIDE_CSS,  # see below
    }

# Stage 4: Render
def generate_dashboard() -> str:
    data = load_data(Path(".tmp/observatory/forecasts_latest.json"))
    summary = calculate_summary(data)
    context = build_context(summary)
    return render_dashboard("executive_panel.html", context)
```

---

## Standard Header CSS Override

Add to every dashboard template in `{% block extra_css %}`:

```css
.header {
    background: #0f172a !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    border: none !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06) !important;
    padding: 48px 32px !important;
}
```

---

## Color System

```css
/* Status */
--color-good:    #10b981;  /* green */
--color-caution: #f59e0b;  /* amber */
--color-action:  #ef4444;  /* red */
--color-info:    #3b82f6;  /* blue */

/* Forecast/Prediction */
--color-forecast:      #6366f1;  /* indigo — for forecast lines */
--color-forecast-band: rgba(99, 102, 241, 0.15);  /* indigo fill */

/* Background/Surface */
--bg-primary:   #0f172a;  /* dark slate */
--bg-card:      #1e293b;  /* card background */
--bg-elevated:  #334155;  /* elevated element */

/* Text */
--text-primary:   #e2e8f0;
--text-secondary: #94a3b8;
--text-muted:     #64748b;
```

---

## Plotly Chart Patterns

### Forecast Band Chart (Primary Pattern)

```python
import plotly.graph_objects as go

def build_forecast_chart(
    dates_historic: list[str],
    values_historic: list[float],
    dates_forecast: list[str],
    p10: list[float],
    p50: list[float],
    p90: list[float],
    target_value: float | None = None,
    metric_name: str = "Metric",
) -> str:
    """Returns Plotly HTML div string for embedding in Jinja2 template."""
    fig = go.Figure()

    # Historic data
    fig.add_trace(go.Scatter(
        x=dates_historic, y=values_historic,
        name="Actual", mode="lines",
        line=dict(color="#e2e8f0", width=2),
    ))

    # Forecast confidence band (P10-P90 fill)
    fig.add_trace(go.Scatter(
        x=dates_forecast, y=p90,
        name="P90", mode="lines",
        line=dict(color="rgba(99,102,241,0)", width=0),
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=dates_forecast, y=p10,
        name="80% Confidence",
        fill="tonexty",
        fillcolor="rgba(99,102,241,0.15)",
        line=dict(color="rgba(99,102,241,0)", width=0),
    ))

    # Forecast P50 (expected)
    fig.add_trace(go.Scatter(
        x=dates_forecast, y=p50,
        name="Forecast (P50)", mode="lines",
        line=dict(color="#6366f1", width=2, dash="dash"),
    ))

    # Target line (if provided)
    if target_value is not None:
        fig.add_hline(
            y=target_value,
            line_dict=dict(color="#ef4444", width=1, dash="dot"),
            annotation_text="Target",
            annotation_position="right",
        )

    # Change-point annotation example
    # fig.add_vline(x=change_point_date, line_dict=dict(color="#f59e0b", dash="dash"))

    fig.update_layout(
        plot_bgcolor="#0f172a",
        paper_bgcolor="#1e293b",
        font=dict(color="#e2e8f0", size=12),
        margin=dict(l=40, r=20, t=20, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis=dict(gridcolor="#334155", linecolor="#334155"),
        yaxis=dict(gridcolor="#334155", linecolor="#334155"),
        hovermode="x unified",
    )

    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,  # Use CDN in base template
        div_id=f"chart_{metric_name.lower().replace(' ', '_')}",
    )
```

### Correlation Heatmap

```python
def build_correlation_heatmap(corr_matrix: list[list[float]], labels: list[str]) -> str:
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix,
        x=labels,
        y=labels,
        colorscale="RdBu_r",
        zmid=0,
        zmin=-1, zmax=1,
        text=[[f"{v:.2f}" for v in row] for row in corr_matrix],
        texttemplate="%{text}",
        hovertemplate="%{x} vs %{y}: %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(
        plot_bgcolor="#1e293b",
        paper_bgcolor="#1e293b",
        font=dict(color="#e2e8f0", size=11),
        margin=dict(l=80, r=20, t=20, b=80),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)
```

### Risk Gauge (Executive Panel)

```python
def build_risk_gauge(score: float) -> str:
    """score: 0-100 where 100 = maximum risk."""
    color = "#10b981" if score < 40 else "#f59e0b" if score < 70 else "#ef4444"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#94a3b8"},
            "bar": {"color": color},
            "bgcolor": "#334155",
            "steps": [
                {"range": [0, 40], "color": "rgba(16,185,129,0.1)"},
                {"range": [40, 70], "color": "rgba(245,158,11,0.1)"},
                {"range": [70, 100], "color": "rgba(239,68,68,0.1)"},
            ],
        },
        number={"font": {"color": color, "size": 48}},
    ))
    fig.update_layout(
        paper_bgcolor="#1e293b",
        font=dict(color="#e2e8f0"),
        height=200,
        margin=dict(l=20, r=20, t=20, b=20),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)
```

---

## Executive Intelligence Panel Design

### Layout Structure

```
┌──────────────────── HEADER (flat #0f172a) ────────────────────────────────┐
│  ENGINEERING OBSERVATORY — Week of Feb 22, 2026                            │
│  "[LLM or template-generated one-line headline]"                           │
└────────────────────────────────────────────────────────────────────────────┘

┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────────────────────┐
│  KPI 1 │ │  KPI 2 │ │  KPI 3 │ │  KPI 4 │ │   RISK METER (Plotly)      │
│Health  │ │Vulns   │ │ Bugs   │ │LeadTime│ │   score/100 + label        │
│ 74/100 │ │  342   │ │  287   │ │  11d   │ └────────────────────────────┘
│ 🟢 +3  │ │ 🟡 -12 │ │ 🟢 -8  │ │ 🔴 +2d │
└────────┘ └────────┘ └────────┘ └────────┘

┌────────────────────────────────────────┐ ┌────────────────────────────┐
│  INTELLIGENCE FEED                     │ │  26-WEEK FORECAST (Plotly) │
│  [insight cards, emoji-coded]          │ │  [forecast_chart]          │
│  🔴 Risk insight + [→ Dashboard]       │ └────────────────────────────┘
│  🟡 Caution insight + [→ Dashboard]    │
│  💡 Opportunity + [→ Dashboard]        │
└────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  TOP ACTIONS                   Effort ↓   Impact ↑                      │
│  1. [Action] [Low effort / High impact]                           [→]   │
│  2. [Action] [Medium / High]                                      [→]   │
│  3. [Action] [Low / Medium]                                       [→]   │
└──────────────────────────────────────────────────────────────────────────┘
```

### KPI Card HTML Pattern

```html
<div class="summary-card status-{{ card.status_class }}">
    <div class="card-label">{{ card.label }}</div>
    <div class="card-value">{{ card.value }}</div>
    <div class="card-delta {{ card.delta_class }}">
        {{ card.delta_emoji }} {{ card.delta_text }}
    </div>
    <a href="{{ card.dashboard_url }}" class="card-drill-link">Details →</a>
</div>
```

### Emoji Severity System

```python
def severity_emoji(score: float) -> str:
    if score >= 70:   return "🔴"  # Critical — action needed immediately
    if score >= 40:   return "🟡"  # Caution — monitor closely
    return "🟢"                    # Good — normal operation

def delta_emoji(delta_pct: float, metric_improves_when: str = "decreasing") -> str:
    improving = (delta_pct < 0) if metric_improves_when == "decreasing" else (delta_pct > 0)
    if abs(delta_pct) < 0.02:  return "→"  # Flat
    return "↓" if delta_pct < 0 else "↑"
```

---

## Plotly CDN Include

Add to `templates/dashboards/base_dashboard.html` once (all dashboards inherit):

```html
<!-- Plotly CDN — add before </head> -->
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js" charset="utf-8"></script>
```

When building charts with `fig.to_html(include_plotlyjs=False)`, Plotly uses the CDN version.

---

## Scenario Simulator Pattern

```html
<!-- In template -->
<div class="scenario-simulator">
    <h3>Scenario Simulator</h3>

    <label>Weekly closure rate: <span id="rate-val">{{ params.closure_rate }}</span>/week</label>
    <input type="range" id="closure-rate" min="1" max="10" step="0.5"
           value="{{ params.closure_rate }}" oninput="updateScenario()">

    <label>Critical focus: <span id="crit-val">{{ params.critical_pct }}%</span></label>
    <input type="range" id="critical-focus" min="0" max="100" step="5"
           value="{{ params.critical_pct }}" oninput="updateScenario()">

    <div id="scenario-result">
        <div class="result-p50">Expected: {{ result.p50 }} vulns</div>
        <div class="result-band">P10: {{ result.p10 }} — P90: {{ result.p90 }}</div>
        <div class="result-prob">Probability of hitting target: {{ result.prob_pct }}%</div>
    </div>
</div>

<script>
async function updateScenario() {
    const rate = parseFloat(document.getElementById("closure-rate").value);
    const crit = parseFloat(document.getElementById("critical-focus").value);
    document.getElementById("rate-val").textContent = rate;
    document.getElementById("crit-val").textContent = crit;

    const resp = await fetch(`/intelligence/scenario?closure_rate=${rate}&critical_pct=${crit}`);
    const data = await resp.json();
    document.getElementById("scenario-result").innerHTML = `...`;  // Update display
}
</script>
```

---

## Template Structure

```
templates/dashboards/
  base_dashboard.html           # Base (framework CSS/JS, Plotly CDN)
  executive_panel.html          # {% extends "base_dashboard.html" %}
  predictive_analytics.html     # {% extends "base_dashboard.html" %}
```

Both new templates extend `base_dashboard.html` and use `{% block content %}` + `{% block extra_css %}`.

---

## File Naming Conventions

| Component | Path |
|---|---|
| Generator | `execution/dashboards/executive_panel.py` |
| Template | `templates/dashboards/executive_panel.html` |
| Chart component | `execution/dashboards/components/forecast_chart.py` |
| Domain model | `execution/domain/intelligence.py` |
| Tests | `tests/dashboards/test_executive_panel.py` |
