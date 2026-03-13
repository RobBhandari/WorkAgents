"""
Ask EI — Conversational Query Layer.

Intent router + module composer for natural-language queries about engineering health.
Uses LLM classification (Claude Haiku, lazy import) with keyword fallback when API key absent.

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
    # Order matters — more specific intents first
    "product_query": [
        "status of",
        "how is",
        "tell me about",
        "what's happening with",
        "what is happening with",
        "posture for",
        "health of",
        "how are",
    ],
    "worst_product": [
        "worst performing product",
        "worst product",
        "bottom of the portfolio",
        "most problems",
        "underperforming product",
        "lowest performing",
    ],
    "attention_areas": [
        "need most attention",
        "most attention",
        "where to focus",
        "where should we focus",
        "most critical",
        "needs focus",
        "which areas",
        "which products need",
        "need to prioritise",
        "need to prioritize",
    ],
    "security_query": [
        "security",
        "vulnerabilit",
        "exploitable",
        "security posture",
        "worst security",
        "secure",
    ],
    "ownership_query": ["owner", "single owner", "knowledge", "who owns", "inactive", "bus factor"],
    "deployment_compare": ["deploy", "build success", "success rate", "pipeline", "release frequency"],
    "risk_explanation": [
        "risk score",
        "risk high",
        "risk low",
        "risk so high",
        "what's driving",
        "driving the risk",
        "high score",
    ],
    "trend_drill": ["getting worse", "trend over", "improving over", "declining", "deteriorat"],
    "portfolio_summary": [
        "worry about",
        "this sprint",
        "what's wrong",
        "overview",
        "should i",
        "concerned",
        "what to focus",
        "priority",
        "worst",
        "biggest problem",
    ],
    "best_product": ["improving fastest", "healthiest", "going well", "best performing"],
    "worst_metric": ["which metric", "which area", "what is failing", "most at risk"],
}

_FALLBACK_INTENT = "portfolio_summary"

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
Classify the user query into exactly one of these intent keys:

- product_query: questions about a specific named product (e.g. "status of Fusion", "how is Proclaim doing", "tell me about Product A")
- worst_product: questions about the worst or lowest-performing product overall and why
- attention_areas: questions about which products or areas need the most attention, where to focus, most critical issues
- security_query: questions about security posture, vulnerabilities, exploitable issues, which product is most/least secure
- ownership_query: questions about code ownership, single owners, bus factor, knowledge concentration
- deployment_compare: questions about deployments, build success, pipelines, release frequency
- risk_explanation: questions about risk scores, what is driving risk, why risk is high/low
- trend_drill: questions about trends over time, deteriorating/improving metrics, rate of change
- portfolio_summary: general health questions, what to worry about, overview, priorities, sprint concerns
- best_product: which product/metric is performing best, healthiest, improving fastest
- worst_metric: which metric/area is worst, most at risk, failing

Respond with ONLY the intent key — no explanation, no punctuation."""

_VALID_INTENTS = frozenset(_INTENT_MAP.keys())


def _route_intent_llm(query: str) -> str | None:
    """LLM-based intent classification via Claude Haiku. Returns None on any failure."""
    try:
        from anthropic import Anthropic  # lazy import — only needed when API key present

        client = Anthropic()
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            system=_LLM_INTENT_SYSTEM,
            messages=[{"role": "user", "content": query}],
        )
        raw = message.content[0].text.strip().lower() if message.content else ""
        if raw in _VALID_INTENTS:
            return raw
        logger.warning("LLM returned unknown intent %r — falling back to keywords", raw)
        return None
    except Exception as exc:
        logger.debug("LLM intent routing failed (%s) — using keyword fallback", exc)
        return None


def route_intent(query: str, context: dict[str, Any]) -> str:
    """Determine intent from query string.

    Tries LLM classification first (Claude Haiku); falls back to keyword matching
    if API key is absent or the call fails.

    Args:
        query: Raw natural-language query from the user.
        context: Optional context dict (unused in routing but kept for signature parity).

    Returns:
        Intent key string.
    """
    intent = _route_intent_llm(query)
    if intent:
        return intent
    return _route_intent_keywords(query) or _FALLBACK_INTENT


def compose_response(
    intent: str,
    context: dict[str, Any],
    trends_context: dict[str, Any],
    product_risk: dict[str, Any] | None = None,
    alerts: list[dict[str, Any]] | None = None,
    query: str = "",
) -> dict[str, Any]:
    """Build the full query response dict from intent + live trends data.

    Args:
        intent: Matched intent key.
        context: Caller-supplied context (echoed back).
        trends_context: Output of build_trends_context().
        product_risk: Optional output of build_product_risk_response() for per-product data.

    Returns:
        Fully-formed response dict (see module docstring for schema).
    """
    metrics: list[dict[str, Any]] = trends_context.get("metrics", [])
    raw_alerts: list[dict[str, Any]] = alerts or []
    products: list[dict[str, Any]] = (product_risk or {}).get("products", [])

    # Segment metrics by RAG colour for reuse across intents
    red_metrics = [m for m in metrics if m.get("ragColor") == _RAG_RED]
    amber_metrics = [m for m in metrics if m.get("ragColor") == _RAG_AMBER]
    green_metrics = [m for m in metrics if m.get("ragColor") == _RAG_GREEN]

    narrative: str
    signal_pills: list[dict[str, Any]] = []
    evidence_cards: list[dict[str, Any]] = []
    suggested_followups: list[str] = []
    source_modules: list[str] = ["pipeline", "query_engine"]

    # ------------------------------------------------------------------
    if intent == "product_query":
        source_modules.append("product_risk")
        matched = _extract_product(query, products)

        if matched:
            pname = matched["product"]
            p_alerts = _alerts_for_product(pname, raw_alerts)
            score = matched["score"]
            critical = matched["critical"]
            warn = matched.get("warn", 0)
            domains = matched.get("domains", [])

            rag = "red" if critical > 0 else ("amber" if warn > 0 else "green")
            narrative = (
                f"{pname} has a risk score of {score} "
                f"({critical} critical, {warn} warning alert(s)) — status: {rag}. "
            )
            if domains:
                narrative += f"Active problem areas: {', '.join(domains)}. "
            reasons = _format_alert_reasons(p_alerts)
            if reasons:
                narrative += f"Key issues: {reasons}"
            else:
                narrative += "No detailed alert messages available for this product."

            evidence_cards = [
                {
                    "label": a.get("metric_name", a.get("dashboard", "")),
                    "value": a.get("severity", "").upper(),
                    "delta": a.get("dashboard", ""),
                    "rag": "red" if a.get("severity") == "critical" else "amber",
                }
                for a in p_alerts[:4]
            ]
            signal_pills = [
                {
                    "type": "threshold_breach",
                    "metric_id": f"{pname.lower().replace(' ', '_')}_{a.get('dashboard', '')}",
                    "severity": a.get("severity", "warn"),
                    "label": a.get("metric_name", a.get("dashboard", "")),
                }
                for a in p_alerts[:3]
            ]
        else:
            # Product name not found — give a ranked list instead
            narrative = "I couldn't find a product matching your query in the current data. "
            if products:
                names = ", ".join(p["product"] for p in products)
                narrative += f"Known products with active alerts: {names}."
            evidence_cards = []
            signal_pills = []

        suggested_followups = [
            "What's the overall portfolio risk?",
            "Which product needs the most attention?",
            "What are the security posture details?",
        ]

    # ------------------------------------------------------------------
    elif intent == "worst_product":
        source_modules.append("product_risk")
        # Sort by score desc for this intent (products list is alphabetical after the fix)
        ranked = sorted(products, key=lambda p: (-int(p["score"]), str(p["product"])))

        if ranked:
            worst = ranked[0]
            pname = worst["product"]
            p_alerts = _alerts_for_product(pname, raw_alerts)
            reasons = _format_alert_reasons(p_alerts)

            narrative = (
                f"The worst performing product is {pname} with a risk score of {worst['score']} "
                f"({worst['critical']} critical, {worst.get('warn', 0)} warning alert(s)). "
            )
            if worst.get("domains"):
                narrative += f"Problems span: {', '.join(worst['domains'])}. "
            if reasons:
                narrative += f"Why: {reasons}"
            else:
                narrative += "No detailed alert breakdown available."

            if len(ranked) > 1:
                second = ranked[1]
                narrative += f" The next most at-risk is {second['product']} " f"(score: {second['score']})."

            evidence_cards = [
                {
                    "label": p["product"],
                    "value": str(p["score"]),
                    "delta": f"{p['critical']}× critical",
                    "rag": "red" if p["critical"] > 0 else "amber",
                }
                for p in ranked[:4]
            ]
            signal_pills = [
                {
                    "type": "threshold_breach",
                    "metric_id": f"product_{worst['product'].lower().replace(' ', '_')}",
                    "severity": "critical",
                    "label": f"{worst['product']} — highest risk",
                }
            ]
        else:
            narrative = "No products with active alerts found. The portfolio appears healthy."
            evidence_cards = []
            signal_pills = []

        suggested_followups = [
            f"Tell me more about {ranked[0]['product']}" if ranked else "What should I focus on this sprint?",
            "Which areas need the most attention?",
            "What's the security posture across the portfolio?",
        ]

    # ------------------------------------------------------------------
    elif intent == "attention_areas":
        source_modules.append("product_risk")
        ranked = sorted(products, key=lambda p: (-int(p["score"]), str(p["product"])))
        top = ranked[:3]

        if top:
            parts: list[str] = []
            for p in top:
                p_alerts = _alerts_for_product(p["product"], raw_alerts)
                reasons = _format_alert_reasons(p_alerts, limit=2)
                line = (
                    f"{p['product']} (score {p['score']}, {p['critical']}× critical"
                    + (f": {reasons}" if reasons else "")
                    + ")"
                )
                parts.append(line)

            narrative = f"The {len(top)} product(s) needing the most attention right now: " + "; ".join(parts) + ". "

            # Portfolio metric summary
            n_red = len(red_metrics)
            n_amber = len(amber_metrics)
            if n_red or n_amber:
                narrative += (
                    f"Across all metrics, {n_red} are red and {n_amber} are amber. "
                    "Focus efforts on the products above first."
                )
        else:
            narrative = (
                "No products with active alerts detected. "
                f"Portfolio metrics: {len(red_metrics)} red, {len(amber_metrics)} amber, {len(green_metrics)} green."
            )

        evidence_cards = [
            {
                "label": p["product"],
                "value": str(p["score"]),
                "delta": f"{p['critical']}× critical, {p.get('warn', 0)}× warn",
                "rag": "red" if p["critical"] > 0 else "amber",
            }
            for p in top
        ]
        signal_pills = [
            {
                "type": "threshold_breach",
                "metric_id": f"attention_{p['product'].lower().replace(' ', '_')}",
                "severity": "critical" if p["critical"] > 0 else "warning",
                "label": f"{p['product']} needs attention",
            }
            for p in top
        ]
        suggested_followups = [
            f"Tell me about {top[0]['product']}" if top else "What's the overall portfolio status?",
            "What's the worst performing product and why?",
            "What should I do about the security posture?",
        ]

    # ------------------------------------------------------------------
    elif intent == "risk_explanation":
        source_modules.append("risk_scorer")
        risk_metric = next((m for m in metrics if "risk" in m.get("id", "").lower()), None)
        if risk_metric:
            narrative = (
                f"The risk score is currently {_fmt_value(risk_metric.get('current'))} "
                f"({_rag_label(risk_metric.get('ragColor', ''))}), "
                f"up {_fmt_delta(risk_metric.get('change'))} from the prior period. "
            )
        else:
            narrative = "No risk metric found in current data. "

        if red_metrics:
            top = red_metrics[:3]
            names = ", ".join(m.get("title", m.get("id", "")) for m in top)
            narrative += f"Key contributors in the red zone include: {names}. "
        else:
            narrative += "No metrics are currently in the red zone. "

        narrative += "Review the evidence cards below for detailed figures."

        evidence_cards = [
            {
                "label": m.get("title", m.get("id", "")),
                "value": _fmt_value(m.get("current")),
                "delta": _fmt_delta(m.get("change")),
                "rag": _rag_label(m.get("ragColor", "")),
            }
            for m in red_metrics[:4]
        ]

        signal_pills = [
            {
                "type": "threshold_breach",
                "metric_id": m.get("id", ""),
                "severity": "critical",
                "label": f"{m.get('title', m.get('id', ''))} is red",
            }
            for m in red_metrics[:3]
        ]

        suggested_followups = [
            "What's the deployment trend over the last 5 weeks?",
            "Which product has the highest risk score?",
            "What's improving in the portfolio?",
        ]

    # ------------------------------------------------------------------
    elif intent == "portfolio_summary":
        source_modules.append("signals")
        n_red = len(red_metrics)
        n_amber = len(amber_metrics)
        n_green = len(green_metrics)

        if n_red:
            top_concern = red_metrics[0].get("title", red_metrics[0].get("id", "unknown"))
            narrative = (
                f"The portfolio has {n_red} red metric(s) and {n_amber} amber metric(s) "
                f"requiring attention. The top concern is {top_concern} "
                f"(current: {_fmt_value(red_metrics[0].get('current'))}, "
                f"change: {_fmt_delta(red_metrics[0].get('change'))}). "
            )
        else:
            narrative = (
                f"The portfolio looks relatively healthy with {n_amber} amber metric(s) "
                f"and {n_green} green metric(s). "
            )

        # Augment with per-product risk ranking if available
        if products:
            top_product = products[0]
            narrative += (
                f"The highest-risk product is {top_product['product']} "
                f"(score: {top_product['score']}, "
                f"{top_product['critical']} critical alert(s)). "
            )

        if n_green:
            green_names = ", ".join(m.get("title", m.get("id", "")) for m in green_metrics[:2])
            narrative += f"Positives this sprint: {green_names}."

        evidence_cards = [
            {
                "label": m.get("title", m.get("id", "")),
                "value": _fmt_value(m.get("current")),
                "delta": _fmt_delta(m.get("change")),
                "rag": _rag_label(m.get("ragColor", "")),
            }
            for m in (red_metrics + amber_metrics)[:4]
        ]

        signal_pills = [
            {
                "type": "threshold_breach",
                "metric_id": m.get("id", ""),
                "severity": "critical" if m.get("ragColor") == _RAG_RED else "warning",
                "label": f"{m.get('title', m.get('id', ''))} needs attention",
            }
            for m in (red_metrics + amber_metrics)[:3]
        ]

        suggested_followups = [
            "Why is the risk score high?",
            "What's driving the deployment issues?",
            "Which product is improving fastest?",
        ]

    # ------------------------------------------------------------------
    elif intent == "trend_drill":
        source_modules.append("change_point_detector")
        improving = [m for m in metrics if (m.get("change") or 0) < 0 and m.get("ragColor") == _RAG_GREEN]
        worsening = [m for m in metrics if (m.get("change") or 0) > 0 and m.get("ragColor") == _RAG_RED]

        if worsening:
            names = ", ".join(m.get("title", m.get("id", "")) for m in worsening[:2])
            narrative = f"The metrics showing the most deterioration are: {names}. "
        else:
            narrative = "No strongly worsening trends detected in the current data. "

        if improving:
            imp_names = ", ".join(m.get("title", m.get("id", "")) for m in improving[:2])
            narrative += f"Metrics that are improving: {imp_names}. "

        narrative += "Use the evidence cards to review week-on-week changes."

        evidence_cards = [
            {
                "label": m.get("title", m.get("id", "")),
                "value": _fmt_value(m.get("current")),
                "delta": _fmt_delta(m.get("change")),
                "rag": _rag_label(m.get("ragColor", "")),
            }
            for m in metrics[:4]
        ]

        signal_pills = [
            {
                "type": "sustained_deterioration",
                "metric_id": m.get("id", ""),
                "severity": "warning",
                "label": f"{m.get('title', m.get('id', ''))} deteriorating",
            }
            for m in worsening[:3]
        ]

        suggested_followups = [
            "Why is risk high?",
            "What's happening with deployment build rates?",
            "What should I worry about this sprint?",
        ]

    # ------------------------------------------------------------------
    elif intent == "deployment_compare":
        source_modules.append("deployment_collector")
        deploy_metric = next(
            (m for m in metrics if "deployment" in m.get("id", "").lower() or "build" in m.get("id", "").lower()),
            None,
        )

        if deploy_metric:
            current = _fmt_value(deploy_metric.get("current"))
            delta = _fmt_delta(deploy_metric.get("change"))
            rag = _rag_label(deploy_metric.get("ragColor", ""))
            narrative = (
                f"Build/deployment success rate is currently {current} " f"({delta} vs prior period) — status: {rag}. "
            )
            if deploy_metric.get("ragColor") == _RAG_RED:
                narrative += "This is below the acceptable threshold and needs immediate investigation. "
            else:
                narrative += "Deployment health is within acceptable bounds. "
            narrative += "Review pipeline trends in the evidence cards."
        else:
            narrative = (
                "No deployment metric found in the current dashboard. "
                "Ensure the deployment collector is running and producing history data."
            )

        evidence_cards = (
            [
                {
                    "label": deploy_metric.get("title", "Deployment"),
                    "value": _fmt_value(deploy_metric.get("current")),
                    "delta": _fmt_delta(deploy_metric.get("change")),
                    "rag": _rag_label(deploy_metric.get("ragColor", "")),
                }
            ]
            if deploy_metric
            else []
        )
        # Pad with other metrics
        for m in metrics:
            if deploy_metric and m.get("id") == deploy_metric.get("id"):
                continue
            if len(evidence_cards) >= 4:
                break
            evidence_cards.append(
                {
                    "label": m.get("title", m.get("id", "")),
                    "value": _fmt_value(m.get("current")),
                    "delta": _fmt_delta(m.get("change")),
                    "rag": _rag_label(m.get("ragColor", "")),
                }
            )

        signal_pills = (
            [
                {
                    "type": "threshold_breach",
                    "metric_id": deploy_metric.get("id", "deployment"),
                    "severity": "critical" if deploy_metric.get("ragColor") == _RAG_RED else "info",
                    "label": "Build success rate below threshold",
                }
            ]
            if deploy_metric
            else []
        )

        suggested_followups = [
            "What's the overall portfolio status?",
            "Which product has the worst risk score?",
            "Is deployment trend improving or declining?",
        ]

    # ------------------------------------------------------------------
    elif intent == "ownership_query":
        source_modules.append("ownership_collector")
        ownership_metric = next(
            (m for m in metrics if "ownership" in m.get("id", "").lower()),
            None,
        )

        if ownership_metric:
            narrative = (
                f"Ownership health is {_rag_label(ownership_metric.get('ragColor', 'neutral'))} "
                f"with a current score of {_fmt_value(ownership_metric.get('current'))} "
                f"({_fmt_delta(ownership_metric.get('change'))} vs prior week). "
                "Single-owner files represent a knowledge concentration risk. "
                "Review the ownership history to identify at-risk modules."
            )
        else:
            narrative = (
                "No ownership metric found in the current dashboard. "
                "Ensure the ownership collector has run and produced history data. "
                "Single-owner files present a bus-factor risk if the owner is unavailable."
            )

        evidence_cards = (
            [
                {
                    "label": ownership_metric.get("title", "Ownership"),
                    "value": _fmt_value(ownership_metric.get("current")),
                    "delta": _fmt_delta(ownership_metric.get("change")),
                    "rag": _rag_label(ownership_metric.get("ragColor", "")),
                }
            ]
            if ownership_metric
            else []
        )
        for m in red_metrics[:3]:
            if ownership_metric and m.get("id") == ownership_metric.get("id"):
                continue
            if len(evidence_cards) >= 4:
                break
            evidence_cards.append(
                {
                    "label": m.get("title", m.get("id", "")),
                    "value": _fmt_value(m.get("current")),
                    "delta": _fmt_delta(m.get("change")),
                    "rag": "red",
                }
            )

        signal_pills = (
            [
                {
                    "type": "threshold_breach",
                    "metric_id": ownership_metric.get("id", "ownership"),
                    "severity": "warning",
                    "label": "Knowledge concentration risk",
                }
            ]
            if ownership_metric
            else []
        )

        suggested_followups = [
            "Which metrics are in the red zone?",
            "What's the overall portfolio health?",
            "Is deployment stability improving?",
        ]

    # ------------------------------------------------------------------
    elif intent == "security_query":
        source_modules.append("risk_scorer")
        sec_metric = next(
            (m for m in metrics if any(k in m.get("id", "").lower() for k in ("security", "exploitable", "vuln"))),
            None,
        )

        # If a specific product is named in the query, scope to that product
        named_product = _extract_product(query, products)

        # Use per-product ranking if available
        sec_products = [p for p in products if "security" in p.get("domains", [])]
        if not sec_products:
            sec_products = products  # fall back to all-domain ranking

        if named_product:
            pname = named_product["product"]
            p_alerts = _alerts_for_product(pname, raw_alerts)
            sec_alerts = [
                a
                for a in p_alerts
                if "security" in a.get("dashboard", "").lower()
                or "vuln" in a.get("metric_name", "").lower()
                or "security" in a.get("metric_name", "").lower()
            ]
            reasons = _format_alert_reasons(sec_alerts or p_alerts)
            rag = "red" if named_product["critical"] > 0 else ("amber" if named_product.get("warn", 0) > 0 else "green")
            narrative = (
                f"Security posture for {pname}: risk score {named_product['score']}, "
                f"{named_product['critical']} critical alert(s) — status {rag}. "
            )
            if reasons:
                narrative += f"Key issues: {reasons}"
            else:
                narrative += "No security-specific alerts found for this product."
            evidence_cards = [
                {
                    "label": a.get("metric_name", a.get("dashboard", "")),
                    "value": a.get("severity", "").upper(),
                    "delta": a.get("dashboard", ""),
                    "rag": "red" if a.get("severity") == "critical" else "amber",
                }
                for a in (sec_alerts or p_alerts)[:4]
            ]
            signal_pills = [
                {
                    "type": "threshold_breach",
                    "metric_id": f"security_{pname.lower().replace(' ', '_')}",
                    "severity": "critical" if named_product["critical"] > 0 else "warning",
                    "label": f"{pname} security — {rag}",
                }
            ]
            suggested_followups = [
                f"What's the overall status of {pname}?",
                "Which product has the worst security posture?",
                "What should we prioritise this sprint?",
            ]
        elif sec_products:
            worst_product = sec_products[0]
            best_product_item = sec_products[-1] if len(sec_products) > 1 else None
            narrative = (
                f"The product with the highest security risk is {worst_product['product']} "
                f"(risk score: {worst_product['score']}, "
                f"{worst_product['critical']} critical alert(s)). "
            )
            if best_product_item:
                narrative += (
                    f"{best_product_item['product']} is the strongest performer "
                    f"with a score of {best_product_item['score']}. "
                )
            if sec_metric:
                rag = _rag_label(sec_metric.get("ragColor", ""))
                narrative += f"Portfolio-level security is {rag} at {_fmt_value(sec_metric.get('current'))}."

            evidence_cards = [
                {
                    "label": p["product"],
                    "value": f"Score {p['score']}",
                    "delta": f"{p['critical']}× critical",
                    "rag": "red" if p["critical"] > 0 else "amber",
                }
                for p in sec_products[:3]
            ]
            if sec_metric and len(evidence_cards) < 4:
                evidence_cards.append(
                    {
                        "label": sec_metric.get("title", "Security"),
                        "value": _fmt_value(sec_metric.get("current")),
                        "delta": _fmt_delta(sec_metric.get("change")),
                        "rag": _rag_label(sec_metric.get("ragColor", "")),
                    }
                )
            signal_pills = [
                {
                    "type": "threshold_breach",
                    "metric_id": f"security_{p['product'].lower().replace(' ', '_')}",
                    "severity": "critical" if p["critical"] > 0 else "warning",
                    "label": f"{p['product']} security at risk",
                }
                for p in sec_products[:3]
            ]
            suggested_followups = [
                "What's the overall portfolio risk?",
                "Is the security trend improving?",
                "What should I prioritise this sprint?",
            ]
        elif sec_metric:
            rag = _rag_label(sec_metric.get("ragColor", ""))
            narrative = (
                f"Security posture is currently {rag} — "
                f"{sec_metric.get('title', 'Security')} at {_fmt_value(sec_metric.get('current'))} "
                f"({_fmt_delta(sec_metric.get('change'))} vs prior period). "
            )
            if sec_metric.get("ragColor") == _RAG_GREEN:
                narrative += "The portfolio is tracking toward its security target."
            elif sec_metric.get("ragColor") == _RAG_RED:
                narrative += "Exploitable vulnerabilities need immediate attention."
            else:
                narrative += "Some progress is being made but the target has not yet been reached."
            evidence_cards = [
                {
                    "label": sec_metric.get("title", "Security"),
                    "value": _fmt_value(sec_metric.get("current")),
                    "delta": _fmt_delta(sec_metric.get("change")),
                    "rag": _rag_label(sec_metric.get("ragColor", "")),
                }
            ]
            signal_pills = []
            suggested_followups = [
                "What's the overall portfolio risk?",
                "Is the security trend improving?",
                "What should I prioritise this sprint?",
            ]
        else:
            narrative = (
                "No security data found in the current dashboard. "
                "Ensure the security collector has run and produced history data."
            )
            evidence_cards = []
            signal_pills = []
            suggested_followups = [
                "What's the overall portfolio risk?",
                "What should I prioritise this sprint?",
            ]

    # ------------------------------------------------------------------
    elif intent == "worst_metric":
        source_modules.append("signals")
        if red_metrics:
            worst = red_metrics[0]
            narrative = (
                f"The metric in worst health is {worst.get('title', worst.get('id', 'unknown'))} "
                f"at {_fmt_value(worst.get('current'))} ({_fmt_delta(worst.get('change'))} vs prior period) — currently red. "
            )
            if len(red_metrics) > 1:
                others = ", ".join(m.get("title", m.get("id", "")) for m in red_metrics[1:3])
                narrative += f"Other red metrics: {others}. "
            narrative += "Focus remediation effort here first."
        elif amber_metrics:
            worst = amber_metrics[0]
            narrative = (
                f"No metrics are currently in the red zone. "
                f"The most at-risk metric is {worst.get('title', worst.get('id', 'unknown'))} "
                f"at {_fmt_value(worst.get('current'))} ({_fmt_delta(worst.get('change'))}) — amber. "
                "Monitor closely."
            )
        else:
            narrative = "All metrics are currently in the green zone. The portfolio is in good health."

        evidence_cards = [
            {
                "label": m.get("title", m.get("id", "")),
                "value": _fmt_value(m.get("current")),
                "delta": _fmt_delta(m.get("change")),
                "rag": _rag_label(m.get("ragColor", "")),
            }
            for m in (red_metrics + amber_metrics)[:4]
        ]

        signal_pills = [
            {
                "type": "threshold_breach",
                "metric_id": m.get("id", ""),
                "severity": "critical",
                "label": f"{m.get('title', m.get('id', ''))} is red",
            }
            for m in red_metrics[:2]
        ]

        suggested_followups = [
            "Why is risk high?",
            "What's the deployment status?",
            "What should I focus on this sprint?",
        ]

    # ------------------------------------------------------------------
    elif intent == "best_product":
        source_modules.append("signals")
        if green_metrics:
            best = green_metrics[0]
            narrative = (
                f"The metric showing the strongest health is {best.get('title', best.get('id', 'unknown'))} "
                f"with a current value of {_fmt_value(best.get('current'))} "
                f"({_fmt_delta(best.get('change'))} vs prior period). "
            )
            if len(green_metrics) > 1:
                rest = ", ".join(m.get("title", m.get("id", "")) for m in green_metrics[1:3])
                narrative += f"Other green metrics include: {rest}. "
            narrative += "These represent the portfolio's strongest engineering signals."
        else:
            narrative = (
                "No metrics are currently in the green zone. "
                "The portfolio is under pressure — focus on reducing red and amber metrics first."
            )

        evidence_cards = [
            {
                "label": m.get("title", m.get("id", "")),
                "value": _fmt_value(m.get("current")),
                "delta": _fmt_delta(m.get("change")),
                "rag": _rag_label(m.get("ragColor", "")),
            }
            for m in green_metrics[:4]
        ]

        signal_pills = [
            {
                "type": "recovery_trend",
                "metric_id": m.get("id", ""),
                "severity": "info",
                "label": f"{m.get('title', m.get('id', ''))} is healthy",
            }
            for m in green_metrics[:3]
        ]

        suggested_followups = [
            "What needs the most attention right now?",
            "What's the risk explanation for red metrics?",
            "How is deployment performing?",
        ]

    # ------------------------------------------------------------------
    else:
        # Unexpected intent — return a safe fallback
        narrative = (
            "Unable to determine a specific answer for that query. "
            "The portfolio currently has "
            f"{len(red_metrics)} red and {len(amber_metrics)} amber metrics. "
            "Try asking about risk, deployment, trends, or ownership."
        )
        evidence_cards = [
            {
                "label": m.get("title", m.get("id", "")),
                "value": _fmt_value(m.get("current")),
                "delta": _fmt_delta(m.get("change")),
                "rag": _rag_label(m.get("ragColor", "")),
            }
            for m in metrics[:4]
        ]
        signal_pills = []
        suggested_followups = [
            "What should I worry about this sprint?",
            "Why is risk high?",
            "How is deployment performing?",
        ]

    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "intent": intent,
        "narrative": narrative.strip(),
        "signal_pills": signal_pills,
        "evidence_cards": evidence_cards,
        "suggested_followups": suggested_followups,
        "source_modules": source_modules,
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
    response = compose_response(intent, context, trends_context, product_risk, alerts, query)
    response["query"] = query
    return response
