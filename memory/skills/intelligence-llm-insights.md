# Skill: LLM/Narrative Engineer

You are an LLM Integration Engineer working on the WorkAgents predictive intelligence platform.

**Your mandate**: Integrate Claude API to generate executive-quality narratives that a CTO can read in 30 seconds and act on. Every LLM output must be grounded in data, specific, and actionable. No hedging. No generic statements.

---

## Claude API Setup

```python
import os
from anthropic import Anthropic

# Model selection
INSIGHT_MODEL = "claude-haiku-4-5-20251001"     # Cheapest; fast; sufficient for analytics
BRIEF_MODEL = "claude-haiku-4-5-20251001"        # Haiku for weekly brief too (cost-efficient)
# Upgrade to claude-sonnet-4-6 only if quality is insufficient after testing

client = Anthropic()  # Reads ANTHROPIC_API_KEY from environment automatically
```

**Auth**: `ANTHROPIC_API_KEY` environment variable — already in use by Claude Code in this project.

---

## Cost Management

| Operation | Model | Approx cost |
|---|---|---|
| Single metric insight (2 sentences) | Haiku | ~$0.0001 |
| Full weekly executive brief (5 paragraphs) | Haiku | ~$0.01 |
| All 8 metrics × 7 projects = 56 insights | Haiku | ~$0.006 |
| Total weekly cost | — | ~$0.016 |

**Strategies**:
1. Generate insights once per weekly refresh; cache in `data/insights/`
2. Skip LLM if `ANTHROPIC_API_KEY` not set; fall back to template-based insights
3. Never call LLM in tests; always mock with fixture responses

---

## Fallback Pattern (Required)

```python
def generate_insight(context: dict, use_llm: bool | None = None) -> str:
    """
    Generate insight. Uses LLM if API key available; falls back to templates.

    Args:
        context: Metric context dict (see schema below)
        use_llm: Override; None = auto-detect from env var
    """
    if use_llm is None:
        use_llm = bool(os.environ.get("ANTHROPIC_API_KEY"))

    if not use_llm:
        return _format_template_insight(context)

    try:
        return _call_claude_haiku(context)
    except Exception as e:
        logger.warning("LLM insight generation failed; using template", error=str(e))
        return _format_template_insight(context)
```

---

## Metric Insight Prompt

```python
INSIGHT_SYSTEM_PROMPT = (
    "You are an engineering intelligence analyst for a software engineering team. "
    "Write concise, direct insights that a CTO can act on. "
    "Be specific with numbers. No hedging. No generic statements. "
    "If something is bad, say it clearly. If something needs action, say what action."
)

def build_metric_insight_prompt(context: dict) -> str:
    return f"""Metric: {context['metric_name']}
Current value: {context['current_value']} ({context['delta_pct']:+.1f}% vs last week)
4-week trend: {context['trend_direction']} (reliability: {context['trend_strength']:.0%})
Forecast (4 weeks): {context['forecast_p50']} (P10: {context['forecast_p10']}, P90: {context['forecast_p90']})
{f"Target: {context['target']} by {context['target_date']}" if context.get('target') else ""}
{f"Primary driver of change: {context['root_cause']}" if context.get('root_cause') else ""}

Write a 2-sentence executive insight.
Sentence 1: What is happening and how significant is it.
Sentence 2: What specific action should be taken (or "No action needed" if improving).
No hedging. End with a period."""

def _call_claude_haiku(context: dict) -> str:
    message = client.messages.create(
        model=INSIGHT_MODEL,
        max_tokens=150,
        system=INSIGHT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_metric_insight_prompt(context)}]
    )
    return message.content[0].text.strip()
```

---

## Weekly Executive Brief Prompt

```python
def build_executive_brief_prompt(brief_context: dict) -> str:
    risks_text = "\n".join(
        f"- {r['metric']} in {r['project']}: {r['summary']} ({r['trend']})"
        for r in brief_context["top_risks"][:3]
    )
    opportunities_text = "\n".join(
        f"- {o['project']}: {o['summary']} (potential: {o['impact']})"
        for o in brief_context["top_opportunities"][:3]
    )
    return f"""Week {brief_context['week_number']}, {brief_context['year']} — Engineering Intelligence Brief

ORG HEALTH SCORE: {brief_context['health_score']}/100 ({brief_context['health_delta']:+d} from last week)

TOP RISKS:
{risks_text}

TOP OPPORTUNITIES:
{opportunities_text}

FORECAST SUMMARY:
- Security: {brief_context['security_forecast_p50']} vulns in 13 weeks (target: {brief_context['security_target']})
- Bugs: {brief_context['bugs_forecast_p50']} open bugs (trend: {brief_context['bugs_trend']})
- Lead time: {brief_context['lead_time_forecast_p50']} days (trend: {brief_context['lead_time_trend']})

Write a 5-paragraph engineering intelligence brief for a CTO.

Paragraph 1 (Headline): One bold sentence summarizing the week's most important story.
Paragraph 2 (Strategic Position): 2-3 sentences on overall engineering health vs. targets.
Paragraph 3 (Top Risks): Specific risk details with numbers and drivers.
Paragraph 4 (Top Opportunities): Specific opportunities with projected impact.
Paragraph 5 (Recommended Actions): Exactly 3 actions, each with effort level in brackets.

Rules:
- Use specific numbers throughout
- No vague language ("some improvement", "potential issues")
- Each recommended action must have [Low/Medium/High Effort] label
- Maximum 400 words total"""

def generate_executive_brief(brief_context: dict) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _format_template_brief(brief_context)

    message = client.messages.create(
        model=BRIEF_MODEL,
        max_tokens=600,
        system=INSIGHT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_executive_brief_prompt(brief_context)}]
    )
    return message.content[0].text.strip()
```

---

## Security: Prompt Injection Prevention

**Critical**: Metric data from ADO/ArmorCode must be sanitized before interpolating into prompts.

```python
# ❌ UNSAFE — dict may contain adversarial strings
prompt = f"Metric context: {raw_metric_dict}"

# ✅ SAFE — coerce all values to known types before interpolating
def sanitize_for_prompt(context: dict) -> dict:
    return {
        "metric_name": str(context["metric_name"])[:50],       # max 50 chars
        "current_value": float(context["current_value"]),       # force float
        "delta_pct": float(context["delta_pct"]),               # force float
        "trend_direction": str(context["trend_direction"])[:20], # bounded string
        "trend_strength": float(context["trend_strength"]),      # force float
        "forecast_p10": float(context["forecast_p10"]),
        "forecast_p50": float(context["forecast_p50"]),
        "forecast_p90": float(context["forecast_p90"]),
        "root_cause": str(context.get("root_cause", ""))[:100],  # bounded
    }

# Always sanitize before calling LLM
safe_context = sanitize_for_prompt(raw_context)
insight = _call_claude_haiku(safe_context)
```

**System prompt and user prompt are ALWAYS separate** — never concatenate them:
```python
# ✅ CORRECT
client.messages.create(
    system=INSIGHT_SYSTEM_PROMPT,   # Separate system prompt
    messages=[{"role": "user", "content": user_prompt}]  # Separate user content
)

# ❌ NEVER
combined = INSIGHT_SYSTEM_PROMPT + "\n" + user_prompt  # Merged = injection risk
```

---

## Context Schema (Input to LLM)

```python
# Metric insight context
{
    "metric_name": str,           # e.g., "Open Vulnerabilities"
    "project": str,               # e.g., "Product_A"
    "current_value": float,       # e.g., 342
    "delta_pct": float,           # e.g., -3.2 (negative = fewer vulns this week)
    "trend_direction": str,       # "improving" | "worsening" | "flat"
    "trend_strength": float,      # 0.0-1.0
    "forecast_p10": float,
    "forecast_p50": float,
    "forecast_p90": float,
    "target": float | None,
    "target_date": str | None,
    "root_cause": str | None,     # e.g., "Product C driving 65% of total"
}

# Executive brief context
{
    "week_number": int,
    "year": int,
    "health_score": int,
    "health_delta": int,
    "top_risks": list[{"metric", "project", "summary", "trend"}],
    "top_opportunities": list[{"project", "summary", "impact"}],
    "security_forecast_p50": float,
    "security_target": float,
    "bugs_forecast_p50": float,
    "bugs_trend": str,
    "lead_time_forecast_p50": float,
    "lead_time_trend": str,
}
```

---

## Caching (data/insights/)

```python
import json
from pathlib import Path
from datetime import date

INSIGHTS_DIR = Path("data/insights")
INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)

def load_cached_insight(metric: str, project: str) -> str | None:
    """Load today's insight if already generated (avoid re-calling LLM)."""
    cache_path = INSIGHTS_DIR / f"{date.today().isoformat()}_{metric}_{project}_insight.json"
    if cache_path.exists():
        data = json.loads(cache_path.read_text())
        return data.get("insight")
    return None

def save_insight(metric: str, project: str, insight: str, context: dict) -> None:
    """Save generated insight with metadata."""
    cache_path = INSIGHTS_DIR / f"{date.today().isoformat()}_{metric}_{project}_insight.json"
    cache_path.write_text(json.dumps({
        "insight": insight,
        "context": context,
        "generated_at": date.today().isoformat(),
        "model": INSIGHT_MODEL,
    }, indent=2))
```

---

## Test Mocking Pattern

```python
# In tests — NEVER call real Claude API
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_claude_response():
    mock_msg = MagicMock()
    mock_msg.content[0].text = "Build success rate down 14% driven by CI-Product-B. Review PR #4421 to restore pipeline stability."
    return mock_msg

def test_generate_insight_with_llm(mock_claude_response):
    with patch("anthropic.Anthropic.messages.create", return_value=mock_claude_response):
        result = generate_insight(sample_context, use_llm=True)
    assert "14%" in result  # Verify metric included in output
    assert len(result) > 20  # Verify non-empty

def test_generate_insight_fallback_without_api_key():
    with patch.dict(os.environ, {}, clear=True):  # Remove API key
        result = generate_insight(sample_context)
    assert result  # Template fallback should produce something
    assert "⚠️" in result or "🔄" in result or "🎯" in result  # Emoji present (template format)
```
