"""
Ask EI — Conversational Query Layer.

Intent router + module composer for natural-language queries about engineering health.
Uses Gemini Flash for intent classification and narrative generation (free tier).
Falls back to keyword routing and template narratives when API key absent.

Public entry point: build_query_response(query, context) -> dict
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from execution.dashboards.trends.pipeline import build_trends_context

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent map: intent key -> keywords (any match wins)
# ---------------------------------------------------------------------------

_INTENT_MAP: dict[str, list[str]] = {
    # ---------------------------------------------------------------
    # Order matters — more specific intents checked first.
    # Keywords are substring-matched (case-insensitive).
    # ---------------------------------------------------------------
    #
    # 1. Product-specific (narrow phrases that imply a named product)
    "product_query": [
        "status of",
        "how is",
        "tell me about",
        "tell me more about",
        "more about product",
        "details on product",
        "what about product",
        "drill into product",
        "what's happening with",
        "what is happening with",
        "posture for",
        "health of",
        "details for",
        "drill into",
        "deep dive on",
        "alerts for",
        "issues with",
        "problems with",
    ],
    #
    # 2. Visual / dashboard-element explanations
    "visual_explanation": [
        # Named sections
        "anomaly river",
        "system shape",
        "radar chart",
        "spider chart",
        "sparkline",
        "heatmap",
        "heat map",
        "movement layer",
        "movement panel",
        "narrative layer",
        "narrative panel",
        "alert layer",
        "risk signals panel",
        "metric grid",
        "metric cards",
        "metric overview",
        "health score card",
        "health score panel",
        "health radar",
        "product risk panel",
        "product risk breakdown",
        "risk breakdown",
        "collision banner",
        "escalation banner",
        "investigation drawer",
        # Generic "explain this UI" phrases
        "what does the",
        "what do the",
        "showing me",
        "on this page",
        "on the page",
        "on the screen",
        "on screen",
        "explain the chart",
        "explain the radar",
        "explain the river",
        "explain the panel",
        "explain the section",
        "explain the dashboard",
        "explain the grid",
        "explain the heatmap",
        "explain the score",
        "how is the score",
        "how are scores",
        "how is risk calculated",
        "how does the score work",
        "how does scoring work",
        "score calculated",
        "calculated the score",
        "methodology",
        "how does this work",
        "how does it work",
        "how to read",
        "how do i read",
        "what am i looking at",
        "what's this chart",
        "what's this section",
        "this visualization",
        "this section",
        "this panel",
        "this chart",
        "this graph",
        "this diagram",
    ],
    #
    # 3. Specific metric by name (before broad intents steal keywords)
    "metric_detail": [
        "lead time",
        "cycle time",
        "merge time",
        "pr merge time",
        "pull request merge",
        "open bugs",
        "bug count",
        "how many bugs",
        "number of bugs",
        "work unassigned",
        "unassigned work",
        "unassigned percentage",
        "total commits",
        "commit count",
        "commit volume",
        "reduction target",
        "70% target",
        "70 percent",
        "ai usage",
        "ai tracker",
        "copilot usage",
        "infrastructure vuln",
        "infra vuln",
        "code and cloud",
        "code & cloud",
        "build success rate",
        "current value of",
        "what's the current",
    ],
    #
    # 4. Worst product
    "worst_product": [
        "worst performing product",
        "worst product",
        "bottom of the portfolio",
        "most problems",
        "underperforming product",
        "lowest performing",
        "weakest product",
        "struggling product",
        "most troubled product",
        "highest risk product",
        "riskiest product",
        "which product is worst",
        "which product is failing",
        "which product has the most",
        "which product should i worry",
        "worst performing",
        "poorest performing",
        "worst in the portfolio",
        "bottom performer",
        "which product is the worst",
        "product performing worst",
        "lagging product",
        "most at-risk product",
        "which product has the highest risk",
        "which product has the worst risk",
        "product with the highest risk",
        "product with the worst risk",
    ],
    #
    # 5. Attention areas
    "attention_areas": [
        "need most attention",
        "most attention",
        "where to focus",
        "where should we focus",
        "where should i focus",
        "most critical",
        "needs focus",
        "which areas",
        "which products need",
        "need to prioritise",
        "need to prioritize",
        "urgent",
        "action needed",
        "immediate attention",
        "top priorities",
        "what's urgent",
        "what needs fixing",
        "what needs work",
        "where to start",
        "where should i start",
        "what do i tackle",
        "what to tackle",
        "what should i address",
        "should i prioritise",
        "should i prioritize",
        "should i focus",
        "what to focus on",
        "what requires action",
        "needs intervention",
        "fire to put out",
    ],
    #
    # 6. Security
    "security_query": [
        "security",
        "vulnerabilit",
        "exploitable",
        "security posture",
        "worst security",
        "secure",
        "insecure",
        "vuln count",
        "vuln",
        "cve",
        "patch",
        "remediat",
        "attack surface",
        "exposure",
        "most vulnerable",
        "least secure",
        "appsec",
        "application security",
        "code scan",
        "cloud scan",
        "infra scan",
        "sast",
        "dast",
        "pen test",
        "penetration",
        "critical risk",
        "high risk",
    ],
    #
    # 7. Ownership / knowledge
    "ownership_query": [
        "owner",
        "single owner",
        "knowledge",
        "who owns",
        "inactive",
        "bus factor",
        "code ownership",
        "knowledge concentration",
        "expertise",
        "contributor",
        "abandoned",
        "orphaned",
        "unmaintained",
        "who maintains",
        "who is responsible",
        "single point of failure",
        "key person risk",
        "tribal knowledge",
    ],
    #
    # 8. Deployment / build / pipeline
    "deployment_compare": [
        "deploy",
        "build success",
        "success rate",
        "pipeline",
        "release frequency",
        "release cadence",
        "ci/cd",
        "cicd",
        "build fail",
        "build failure",
        "deployment frequency",
        "deployment trend",
        "pipeline health",
        "pipeline status",
        "release",
        "shipping",
        "ship rate",
        "build rate",
        "build status",
        "builds",
        "continuous integration",
        "continuous delivery",
        "deployment stability",
        "deployment success",
        "how often do we deploy",
        "how often do we release",
        "how often do we ship",
    ],
    #
    # 9. Risk explanation
    "risk_explanation": [
        "risk score",
        "risk high",
        "risk low",
        "risk so high",
        "what's driving",
        "driving the risk",
        "high score",
        "risk level",
        "risk situation",
        "red zone",
        "red metrics",
        "why red",
        "why is it red",
        "what's red",
        "what is red",
        "risk factor",
        "risk contributor",
        "contributing to risk",
        "causes of risk",
        "danger",
        "at risk",
        "explain the red",
        "why are there red",
        "why so many red",
        "what caused the red",
        "what are these risks",
        "what are the risks",
    ],
    #
    # 10. Trend / time-series
    "trend_drill": [
        "getting worse",
        "trend over",
        "improving over",
        "declining",
        "deteriorat",
        "trajectory",
        "over time",
        "week over week",
        "week-over-week",
        "week on week",
        "historical",
        "history of",
        "trending",
        "trend for",
        "rate of change",
        "direction",
        "momentum",
        "velocity",
        "going up",
        "going down",
        "increasing",
        "decreasing",
        "changed since",
        "compare to last",
        "compared to last",
        "vs last week",
        "from last week",
        "over the last",
        "past few weeks",
        "last 5 weeks",
        "last five weeks",
        "how has",
        "getting better",
    ],
    #
    # 11. Best product / positive signals (before portfolio_summary to avoid "good news" conflict)
    "best_product": [
        "improving fastest",
        "what's improving",
        "what is improving",
        "healthiest",
        "going well",
        "best performing",
        "good news",
        "positive",
        "strongest",
        "winning",
        "success story",
        "bright spot",
        "what's going right",
        "what's working",
        "performing well",
        "best metric",
        "greenest",
        "most improved",
        "best progress",
        "celebrate",
        "proud of",
        "highlight",
        "shout out",
        "best product",
        "best in the portfolio",
        "top performer",
        "top performing product",
    ],
    #
    # 12. Worst metric
    "worst_metric": [
        "which metric",
        "which area",
        "what is failing",
        "most at risk",
        "worst metric",
        "worst area",
        "biggest concern metric",
        "most broken",
        "weakest metric",
        "weakest area",
        "what metric is worst",
        "failing metric",
        "lowest metric",
        "bottom metric",
        "what's failing",
    ],
    #
    # 13. Portfolio summary (broadest — checked last among real intents)
    "portfolio_summary": [
        "worry about",
        "this sprint",
        "what's wrong",
        "overview",
        "should i",
        "concerned",
        "what to focus",
        "summary",
        "overall",
        "how are we doing",
        "how's everything",
        "general health",
        "portfolio",
        "big picture",
        "state of things",
        "give me a summary",
        "brief me",
        "sitrep",
        "situation report",
        "catch me up",
        "what do i need to know",
        "anything wrong",
        "how's the portfolio",
        "how is the portfolio",
        "what should i know",
        "quick update",
        "status update",
        "engineering health",
        "what's the status",
        "how's it looking",
        "good or bad",
        "are we ok",
        "are we okay",
        "how are things",
        "high level",
        "executive summary",
        "tldr",
        "tl;dr",
    ],
}

_FALLBACK_INTENT = "portfolio_summary"

_last_routing_source: str = "fallback"

# RAG colour constants
_RAG_RED = "#ef4444"
_RAG_AMBER = "#f59e0b"
_RAG_GREEN = "#10b981"


def _rag_label(color: str) -> str:
    """Map hex colour to RAG string."""
    return {_RAG_RED: "red", _RAG_AMBER: "amber", _RAG_GREEN: "green"}.get(color, "neutral")


def _fmt_value(v: Any) -> str:
    """Format a metric current value as a short string."""
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)


def _fmt_delta(change: Any) -> str:
    """Format a change value with sign."""
    try:
        n = float(change)
    except (TypeError, ValueError):
        return "—"
    if n > 0:
        return f"+{n:.1f}"
    if n < 0:
        return f"{n:.1f}"
    return "±0"


def _extract_product(query: str, products: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find a product whose name appears in the query string (case-insensitive).

    Tries longest name first so "Product A Extra" beats "Product A".
    Returns the matching product dict, or None if no match.
    """
    lowered = query.lower()
    sorted_products = sorted(products, key=lambda p: len(str(p.get("product", ""))), reverse=True)
    for p in sorted_products:
        name = str(p.get("product", ""))
        if name and name.lower() in lowered:
            return p
    return None


def _alerts_for_product(product_name: str, alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return alerts where project_name matches product_name (case-insensitive)."""
    name_lower = product_name.lower()
    return [a for a in alerts if str(a.get("project_name", "")).lower() == name_lower]


def _format_alert_reasons(alerts: list[dict[str, Any]], limit: int = 4) -> str:
    """Build a human-readable bullet list of alert reasons from alert messages."""
    seen: list[str] = []
    for a in alerts[:limit]:
        msg = a.get("message") or a.get("root_cause_hint") or ""
        if msg and msg not in seen:
            seen.append(msg)
    if not seen:
        return ""
    return " ".join(f"• {m}" for m in seen)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _route_intent_keywords(query: str) -> str | None:
    """Keyword-based fallback intent routing. Returns None if no keyword matches."""
    lowered = query.lower()
    for intent, keywords in _INTENT_MAP.items():
        for kw in keywords:
            if kw in lowered:
                return intent
    return None


_LLM_INTENT_SYSTEM = """\
You are an intent classifier for an engineering intelligence dashboard.
Classify the user query into exactly one of these intent keys.

INTENT DEFINITIONS (with disambiguation):

- product_query: questions about a SPECIFIC NAMED product (e.g. "status of Product A", "how is Product B doing", "tell me about Product C"). Must mention a product by name.
- visual_explanation: questions about what a dashboard section or chart shows (e.g. "what does the anomaly river show?", "explain the radar chart", "what am I looking at?")
- metric_detail: questions about a specific metric's current value (e.g. "what's the lead time?", "how are bugs looking?", "current build success rate?")
- worst_product: questions about which PRODUCT is worst, lowest-performing, most troubled, riskiest. Even if "portfolio" appears in the query, if the user is asking about the worst PRODUCT, use this intent. Examples: "worst performing product", "worst product in the portfolio", "which product is failing", "bottom of the portfolio"
- best_product: which PRODUCT is performing best, healthiest, improving fastest, good news. Examples: "best performing product", "which product is doing well", "any success stories"
- attention_areas: questions about where to focus effort, what needs the most attention, top priorities, what to tackle first
- security_query: questions about security posture, vulnerabilities, exploitable issues, which product is most/least secure
- ownership_query: questions about code ownership, single owners, bus factor, knowledge concentration
- deployment_compare: questions about deployments, build success, pipelines, release frequency, CI/CD
- risk_explanation: questions about risk SCORES specifically — what is driving the risk score, why risk is high/low. NOT general "what's wrong" questions.
- trend_drill: questions about changes OVER TIME, deteriorating/improving trends, week-over-week comparisons, historical data
- worst_metric: which METRIC or AREA (not product) is worst, most at risk, failing. Use when the question is about metrics, not products.
- portfolio_summary: ONLY for genuinely broad overview questions — "how are we doing", "give me a summary", "catch me up", "sitrep". Do NOT use this for questions that ask about worst/best/specific things.

CRITICAL RULES:
- "worst product" / "worst performing product" → worst_product (NEVER portfolio_summary)
- "best product" / "best performing product" → best_product (NEVER portfolio_summary)
- "which product" + superlative → worst_product or best_product depending on direction
- "what should I focus on" / "where to focus" → attention_areas (NOT portfolio_summary)
- The word "portfolio" does NOT automatically mean portfolio_summary — check the actual question

Respond with ONLY the intent key — no explanation, no punctuation."""

_VALID_INTENTS = frozenset(_INTENT_MAP.keys())


def _get_gemini_client() -> Any | None:
    """Lazy-initialise Gemini client. Returns None if unavailable."""
    try:
        import os

        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return None
        from google import genai  # lazy import — new SDK

        return genai.Client(api_key=api_key)
    except Exception as exc:
        logger.debug("Gemini init failed (%s)", exc)
        return None


_GEMINI_MODEL = "gemini-2.5-flash"


def _route_intent_llm(query: str) -> str | None:
    """LLM-based intent classification via Gemini Flash. Returns None on any failure."""
    try:
        client = _get_gemini_client()
        if client is None:
            return None
        valid_list = ", ".join(sorted(_VALID_INTENTS))
        response = client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=f"{_LLM_INTENT_SYSTEM}\n\nValid keys: {valid_list}\n\nUser query: {query}",
            config={"max_output_tokens": 256, "temperature": 0.0},
        )
        raw = response.text.strip().lower().strip("`\"' ") if response.text else ""
        if raw in _VALID_INTENTS:
            return raw
        logger.warning("LLM returned unknown intent %r — falling back to keywords", raw)
        return None
    except Exception as exc:
        logger.debug("LLM intent routing failed (%s) — using keyword fallback", exc)
        return None


def _generate_narrative_llm(
    query: str,
    intent: str,
    template_narrative: str,
    data_summary: str,
) -> str | None:
    """Use Gemini Flash to generate a conversational narrative from data context.

    Returns None on any failure (caller falls back to template narrative).
    """
    try:
        client = _get_gemini_client()
        if client is None:
            return None

        # Only ask Gemini for a short conversational summary (1-2 sentences).
        # The structured detail (bullets, numbered lists) comes from the template.
        prompt = (
            "You are the AI assistant for an Engineering Intelligence dashboard. "
            "A user asked a question about their engineering health metrics. "
            "Write a SHORT conversational summary (1-2 sentences max) that directly "
            "answers the user's question using the data provided. "
            "Do not invent numbers. Do not use markdown. "
            "Do not start with 'Based on the data' or similar preamble. "
            "Do not list individual issues or bullet points — just the headline answer. "
            "IMPORTANT: If the data provided does not contain the specific information "
            "the user asked about (e.g. they asked for a list of items but you only "
            "have aggregate counts), acknowledge this honestly — say what you CAN "
            "show and what you cannot. Never present unrelated data as if it answers "
            "the question.\n\n"
            f"User question: {query}\n"
            f"Classified intent: {intent}\n"
            f"Data summary:\n{data_summary}"
        )

        response = client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=prompt,
            config={"max_output_tokens": 256, "temperature": 0.3},
        )
        text = response.text.strip() if response.text else ""
        if len(text) > 20:  # sanity check — must be a real answer
            return text
        return None
    except Exception as exc:
        logger.debug("Gemini narrative generation failed (%s) — using template", exc)
        return None


def _match_metric_card(m: dict[str, Any], lowered: str, seen_ids: set[str]) -> dict[str, Any] | None:
    """Return an evidence card if the metric is mentioned in the narrative."""
    mid = m.get("id", "")
    title = m.get("title", "")
    mentioned = (title and title.lower() in lowered) or (mid and mid.lower() in lowered)
    if not mentioned or mid in seen_ids:
        return None
    seen_ids.add(mid)
    return {
        "label": title or mid,
        "value": _fmt_value(m.get("current")),
        "delta": _fmt_delta(m.get("change")),
        "rag": _rag_label(m.get("ragColor", "")),
    }


def _match_product_card(p: dict[str, Any], lowered: str, seen_ids: set[str]) -> dict[str, Any] | None:
    """Return an evidence card if the product is mentioned in the narrative."""
    pname = str(p.get("product", ""))
    if not pname or pname.lower() not in lowered or pname in seen_ids:
        return None
    seen_ids.add(pname)
    rag = "red" if p.get("critical", 0) > 0 else ("amber" if p.get("warn", 0) > 0 else "green")
    return {
        "label": pname,
        "value": str(p.get("score", "")),
        "delta": f"{p.get('critical', 0)}× critical",
        "rag": rag,
    }


_PRODUCT_INTENTS = {"worst_product", "best_product", "product_query", "attention_areas"}


def _select_relevant_cards(
    narrative: str,
    metrics: list[dict[str, Any]],
    products: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    max_cards: int = 3,
    intent: str = "",
) -> list[dict[str, Any]] | None:
    """Pick evidence cards that match entities mentioned in the LLM narrative."""
    lowered = narrative.lower()
    seen_ids: set[str] = set()

    metric_cards = [c for m in metrics if (c := _match_metric_card(m, lowered, seen_ids))]
    product_cards = [c for p in products if (c := _match_product_card(p, lowered, seen_ids))]

    if intent in _PRODUCT_INTENTS:
        cards = product_cards + metric_cards
    else:
        cards = metric_cards + product_cards

    return cards[:max_cards] or None


def _build_data_summary(
    metrics: list[dict[str, Any]],
    products: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
) -> str:
    """Build a compact text summary of current data for the LLM prompt."""
    lines: list[str] = []

    lines.append("=== Metrics ===")
    for m in metrics:
        title = m.get("title", m.get("id", "unknown"))
        current = _fmt_value(m.get("current"))
        delta = _fmt_delta(m.get("change"))
        rag = _rag_label(m.get("ragColor", ""))
        lines.append(f"- {title}: {current} ({delta} vs last week) [{rag}]")

    if products:
        lines.append("\n=== Product Risk (sorted by score desc) ===")
        for p in sorted(products, key=lambda x: -int(x.get("score", 0)))[:6]:
            lines.append(
                f"- {p['product']}: score {p['score']}, "
                f"{p.get('critical', 0)} critical, "
                f"{p.get('warn', 0)} warning, "
                f"domains: {', '.join(p.get('domains', []))}"
            )

    if alerts:
        lines.append(f"\n=== Active Alerts ({len(alerts)} total) ===")
        for a in alerts[:8]:
            lines.append(
                f"- [{a.get('severity', '?')}] {a.get('project_name', '?')} / "
                f"{a.get('dashboard', '?')}: {a.get('message', a.get('metric_name', ''))}"
            )

    return "\n".join(lines)


def route_intent(query: str, context: dict[str, Any]) -> str:
    """Determine intent from query string.

    Strategy: keywords first for specific intents, LLM as tiebreaker/fallback.
    Keyword matches on specific intents are high-confidence — the LLM can
    misclassify when broad terms (e.g. "portfolio") appear alongside specific
    phrases (e.g. "worst performing product").

    Args:
        query: Raw natural-language query from the user.
        context: Optional context dict (unused in routing but kept for signature parity).

    Returns:
        Intent key string.
    """
    global _last_routing_source
    keyword_intent = _route_intent_keywords(query)

    # High-confidence keyword match on a specific (non-fallback) intent — trust it.
    if keyword_intent and keyword_intent != _FALLBACK_INTENT:
        _last_routing_source = "keyword"
        return keyword_intent

    # Keywords matched nothing or only the broad fallback — let the LLM decide.
    llm_intent = _route_intent_llm(query)
    if llm_intent:
        _last_routing_source = "llm"
        return llm_intent

    # LLM unavailable or failed — use keyword result or ultimate fallback.
    _last_routing_source = "keyword" if keyword_intent else "fallback"
    return keyword_intent or _FALLBACK_INTENT


def compose_response(
    intent: str,
    context: dict[str, Any],
    trends_context: dict[str, Any],
    product_risk: dict[str, Any] | None = None,
    alerts: list[dict[str, Any]] | None = None,
    query: str = "",
) -> dict[str, Any]:
    """Build the full query response dict from intent + live trends data.

    Dispatches to intent-specific handler functions in intent_handlers.py.

    Args:
        intent: Matched intent key.
        context: Caller-supplied context (echoed back).
        trends_context: Output of build_trends_context().
        product_risk: Optional output of build_product_risk_response() for per-product data.

    Returns:
        Fully-formed response dict (see module docstring for schema).
    """
    from execution.intelligence.intent_handlers import (
        INTENT_HANDLERS,
        IntentContext,
        handle_unknown,
    )

    metrics: list[dict[str, Any]] = trends_context.get("metrics", [])
    raw_alerts: list[dict[str, Any]] = alerts or []
    products: list[dict[str, Any]] = (product_risk or {}).get("products", [])

    ctx = IntentContext(
        intent=intent,
        query=query,
        metrics=metrics,
        products=products,
        alerts=raw_alerts,
        red_metrics=[m for m in metrics if m.get("ragColor") == _RAG_RED],
        amber_metrics=[m for m in metrics if m.get("ragColor") == _RAG_AMBER],
        green_metrics=[m for m in metrics if m.get("ragColor") == _RAG_GREEN],
    )

    handler = INTENT_HANDLERS.get(intent, handle_unknown)
    ir = handler(ctx)

    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "intent": intent,
        "narrative": ir.narrative.strip(),
        "signal_pills": ir.signal_pills,
        "evidence_cards": ir.evidence_cards,
        "suggested_followups": ir.suggested_followups,
        "source_modules": ["pipeline", "query_engine"] + ir.source_modules,
        "context": context,
    }


def build_query_response(
    query: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a complete conversational query response.

    Loads live trends data, routes intent, and composes a structured response.

    Args:
        query: Natural-language question from the user.
        context: Optional caller-supplied context dict (e.g. product filter).

    Returns:
        Response dict conforming to the Ask EI schema.
    """
    if context is None:
        context = {}

    from pathlib import Path

    from execution.intelligence.product_risk import build_product_risk_response

    trends_context = build_trends_context(history_dir=Path(".tmp/observatory"))
    alerts: list[dict[str, Any]] = trends_context.get("active_alerts", [])
    product_risk = build_product_risk_response(alerts)
    intent = route_intent(query, context)
    products: list[dict[str, Any]] = (product_risk or {}).get("products", [])
    response = compose_response(intent, context, trends_context, product_risk, alerts, query)
    response["query"] = query
    response["routing_source"] = _last_routing_source

    # When the query fell through to the portfolio_summary fallback (not a
    # direct keyword match), prefix the narrative with an honest acknowledgment
    # so the user knows their specific question wasn't directly answered.
    if intent == _FALLBACK_INTENT and _last_routing_source == "fallback":
        response["narrative"] = (
            "I don't have the specific data to answer that question directly, "
            "but here's the closest context I can provide.\n\n" + response["narrative"]
        )

    response = _enhance_response(response, query, intent, trends_context, products, alerts)
    return response


def _reselect_cards(
    response: dict[str, Any],
    narrative: str,
    metrics: list[dict[str, Any]],
    products: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    intent: str,
) -> None:
    """Re-select evidence cards to match updated narrative content."""
    cards = _select_relevant_cards(narrative, metrics, products, alerts, intent=intent)
    if cards:
        response["evidence_cards"] = cards


def _enhance_response(
    response: dict[str, Any],
    query: str,
    intent: str,
    trends_context: dict[str, Any],
    products: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply KB or LLM enhancement to the base response."""
    from execution.intelligence.knowledge_base import log_qa, lookup_knowledge

    metrics = trends_context.get("metrics", [])

    # 1. Check knowledge base first (instant, no API call)
    kb_answer = lookup_knowledge(query)
    if kb_answer:
        response["narrative"] = kb_answer
        response["source_modules"] = response.get("source_modules", []) + ["knowledge_base"]
        _reselect_cards(response, kb_answer, metrics, products, alerts, intent)
        return response

    # 2. Try LLM-enhanced summary
    data_summary = _build_data_summary(metrics, products, alerts)
    template_narrative = response["narrative"]
    llm_summary = _generate_narrative_llm(query, intent, template_narrative, data_summary)
    if llm_summary:
        detail_parts = template_narrative.split("\n\n", 1)
        structured_detail = detail_parts[1] if len(detail_parts) > 1 else ""
        response["narrative"] = llm_summary.rstrip() + "\n\n" + structured_detail if structured_detail else llm_summary
        response["source_modules"] = response.get("source_modules", []) + ["gemini_flash"]
        _reselect_cards(response, response["narrative"], metrics, products, alerts, intent)
        log_qa(query, intent, response["narrative"], source="gemini")
    else:
        log_qa(query, intent, response["narrative"], source="template")

    return response
