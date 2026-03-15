"""
Intent handler functions for Ask EI query engine.

Each handler takes a standardised IntentContext and returns an IntentResult.
Extracted from compose_response() to reduce cyclomatic complexity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------


@dataclass
class IntentContext:
    """All data an intent handler needs to build a response."""

    intent: str
    query: str
    metrics: list[dict[str, Any]]
    products: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    red_metrics: list[dict[str, Any]]
    amber_metrics: list[dict[str, Any]]
    green_metrics: list[dict[str, Any]]


@dataclass
class IntentResult:
    """Structured output from an intent handler."""

    narrative: str
    evidence_cards: list[dict[str, Any]] = field(default_factory=list)
    signal_pills: list[dict[str, Any]] = field(default_factory=list)
    suggested_followups: list[str] = field(default_factory=list)
    source_modules: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers (imported from query_engine to avoid duplication)
# ---------------------------------------------------------------------------

# RAG colour constants
_RAG_RED = "#ef4444"
_RAG_AMBER = "#f59e0b"
_RAG_GREEN = "#10b981"


def _rag_label(color: str) -> str:
    return {_RAG_RED: "red", _RAG_AMBER: "amber", _RAG_GREEN: "green"}.get(color, "neutral")


def _fmt_value(v: Any) -> str:
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)


def _fmt_delta(change: Any) -> str:
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
    lowered = query.lower()
    sorted_products = sorted(products, key=lambda p: len(str(p.get("product", ""))), reverse=True)
    for p in sorted_products:
        name = str(p.get("product", ""))
        if name and name.lower() in lowered:
            return p
    return None


def _alerts_for_product(product_name: str, alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    name_lower = product_name.lower()
    return [a for a in alerts if str(a.get("project_name", "")).lower() == name_lower]


def _format_alert_reasons(alerts: list[dict[str, Any]], limit: int = 4) -> str:
    seen: list[str] = []
    for a in alerts[:limit]:
        msg = a.get("message") or a.get("root_cause_hint") or ""
        if msg and msg not in seen:
            seen.append(msg)
    if not seen:
        return ""
    return " ".join(f"• {m}" for m in seen)


def _metric_card(m: dict[str, Any]) -> dict[str, Any]:
    """Build a standard evidence card dict from a metric."""
    return {
        "label": m.get("title", m.get("id", "")),
        "value": _fmt_value(m.get("current")),
        "delta": _fmt_delta(m.get("change")),
        "rag": _rag_label(m.get("ragColor", "")),
    }


def _product_card(p: dict[str, Any], delta_fmt: str | None = None) -> dict[str, Any]:
    """Build a standard evidence card dict from a product."""
    return {
        "label": p["product"],
        "value": str(p["score"]),
        "delta": delta_fmt or f"{p['critical']}× critical",
        "rag": "red" if p["critical"] > 0 else ("amber" if p.get("warn", 0) > 0 else "green"),
    }


def _alert_cards(alerts: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    """Build evidence cards from raw alert dicts."""
    cards: list[dict[str, Any]] = []
    for a in alerts[:limit]:
        label = a.get("metric_name", a.get("dashboard", ""))
        if "_" in label:
            label = label.replace("_", " ").title()
        cards.append(
            {
                "label": label,
                "value": a.get("severity", "warning").title(),
                "delta": a.get("dashboard", ""),
                "rag": "red" if a.get("severity") == "critical" else "amber",
            }
        )
    return cards


def _pad_evidence(
    lead_cards: list[dict[str, Any]],
    ctx: IntentContext,
    exclude_id: str | None = None,
    max_cards: int = 4,
) -> list[dict[str, Any]]:
    """Pad evidence cards with actionable metrics up to max_cards."""
    cards = list(lead_cards)
    for m in ctx.red_metrics + ctx.amber_metrics + ctx.green_metrics:
        if exclude_id and m.get("id") == exclude_id:
            continue
        if len(cards) >= max_cards:
            break
        cards.append(_metric_card(m))
    return cards


def _append_bullet_reasons(narrative: str, reasons: str) -> str:
    """Append formatted bullet reasons to a narrative, or a 'no details' note."""
    if reasons:
        bullet_lines = [r.strip() for r in reasons.split("•") if r.strip()]
        return narrative + "\n\nKey issues:\n" + "\n".join(f"  • {b}" for b in bullet_lines)
    return narrative + "\n\nNo detailed alert messages available for this product."


def _rag_commentary(rag: str, change_num: float = 0.0) -> str:
    """Return directional commentary for a RAG status."""
    if rag == "red":
        return "This metric needs attention — it is below the acceptable threshold."
    if rag == "amber":
        return "This metric is in the warning zone — monitor closely."
    if rag == "green":
        return "This metric is healthy and still improving." if change_num < 0 else "This metric is healthy."
    return ""


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------


def _product_query_matched(matched: dict[str, Any], ctx: IntentContext) -> IntentResult:
    """Product query when a specific product was found."""
    pname = matched["product"]
    p_alerts = _alerts_for_product(pname, ctx.alerts)
    critical, warn = matched["critical"], matched.get("warn", 0)
    domains = matched.get("domains", [])
    rag = "red" if critical > 0 else ("amber" if warn > 0 else "green")

    narrative = f"{pname} — risk score {matched['score']} ({critical} critical, {warn} warning) — {rag}."
    if domains:
        narrative += f"\nProblem areas: {', '.join(domains)}"
    narrative = _append_bullet_reasons(narrative, _format_alert_reasons(p_alerts))

    evidence_cards: list[dict[str, Any]] = [
        {"label": pname, "value": str(matched["score"]), "delta": f"{critical}× critical, {warn}× warn", "rag": rag}
    ]
    evidence_cards.extend(_alert_cards(p_alerts))

    return IntentResult(
        narrative=narrative,
        source_modules=["product_risk"],
        evidence_cards=evidence_cards,
        signal_pills=[
            {
                "type": "threshold_breach",
                "metric_id": f"{pname.lower().replace(' ', '_')}_{a.get('dashboard', '')}",
                "severity": a.get("severity", "warn"),
                "label": a.get("metric_name", a.get("dashboard", "")),
            }
            for a in p_alerts[:3]
        ],
        suggested_followups=[
            "What's the overall portfolio risk?",
            "Which product needs the most attention?",
            "What are the security posture details?",
        ],
    )


def handle_product_query(ctx: IntentContext) -> IntentResult:
    matched = _extract_product(ctx.query, ctx.products)
    if matched:
        return _product_query_matched(matched, ctx)

    narrative = "I couldn't find a product matching your query in the current data. "
    if ctx.products:
        names = ", ".join(p["product"] for p in ctx.products)
        narrative += f"Known products with active alerts: {names}."
    return IntentResult(
        narrative=narrative,
        source_modules=["product_risk"],
        suggested_followups=[
            "What's the overall portfolio risk?",
            "Which product needs the most attention?",
            "What are the security posture details?",
        ],
    )


def handle_worst_product(ctx: IntentContext) -> IntentResult:
    result = IntentResult(narrative="", source_modules=["product_risk"])
    ranked = sorted(ctx.products, key=lambda p: (-int(p["score"]), str(p["product"])))

    if ranked:
        worst = ranked[0]
        pname = worst["product"]
        p_alerts = _alerts_for_product(pname, ctx.alerts)
        reasons = _format_alert_reasons(p_alerts)

        result.narrative = (
            f"The worst performing product is {pname} — "
            f"risk score {worst['score']} "
            f"({worst['critical']} critical, {worst.get('warn', 0)} warning)."
        )
        if worst.get("domains"):
            result.narrative += f"\nProblem areas: {', '.join(worst['domains'])}"
        if reasons:
            bullet_lines = [r.strip() for r in reasons.split("•") if r.strip()]
            result.narrative += "\n\nKey issues:\n" + "\n".join(f"  • {b}" for b in bullet_lines)
        if len(ranked) > 1:
            second = ranked[1]
            result.narrative += f"\n\nNext most at-risk: {second['product']} (score {second['score']})."

        result.evidence_cards = [_product_card(p) for p in ranked[:4]]
        result.signal_pills = [
            {
                "type": "threshold_breach",
                "metric_id": f"product_{worst['product'].lower().replace(' ', '_')}",
                "severity": "critical",
                "label": f"{worst['product']} — highest risk",
            }
        ]
    else:
        result.narrative = "No products with active alerts found. The portfolio appears healthy."

    result.suggested_followups = [
        f"Tell me more about {ranked[0]['product']}" if ranked else "Where should I focus next?",
        "Which areas need the most attention?",
        "What's the security posture across the portfolio?",
    ]
    return result


def _attention_product_summary(idx: int, p: dict[str, Any], alerts: list[dict[str, Any]]) -> str:
    """Build a numbered summary line for one product in the attention list."""
    reasons = _format_alert_reasons(_alerts_for_product(p["product"], alerts), limit=2)
    header = f"{idx}. {p['product']} — score {p['score']}, {p['critical']}× critical"
    if reasons:
        bullet_lines = [r.strip() for r in reasons.split("•") if r.strip()]
        header += "\n" + "\n".join(f"   • {b}" for b in bullet_lines)
    return header


def handle_attention_areas(ctx: IntentContext) -> IntentResult:
    ranked = sorted(ctx.products, key=lambda p: (-int(p["score"]), str(p["product"])))
    top = ranked[:3]

    if top:
        parts = [_attention_product_summary(i, p, ctx.alerts) for i, p in enumerate(top, 1)]
        narrative = f"{len(top)} product(s) need attention:\n\n" + "\n\n".join(parts)
        n_red, n_amber = len(ctx.red_metrics), len(ctx.amber_metrics)
        if n_red or n_amber:
            narrative += f"\n\nAcross all metrics: {n_red} red, {n_amber} amber. Focus on the products above first."
    else:
        narrative = (
            "No products with active alerts detected. "
            f"Portfolio metrics: {len(ctx.red_metrics)} red, {len(ctx.amber_metrics)} amber, "
            f"{len(ctx.green_metrics)} green."
        )

    return IntentResult(
        narrative=narrative,
        source_modules=["product_risk"],
        evidence_cards=[
            {
                "label": p["product"],
                "value": str(p["score"]),
                "delta": f"{p['critical']}× critical, {p.get('warn', 0)}× warn",
                "rag": "red" if p["critical"] > 0 else "amber",
            }
            for p in top
        ],
        signal_pills=[
            {
                "type": "threshold_breach",
                "metric_id": f"attention_{p['product'].lower().replace(' ', '_')}",
                "severity": "critical" if p["critical"] > 0 else "warning",
                "label": f"{p['product']} needs attention",
            }
            for p in top
        ],
        suggested_followups=[
            f"Tell me about {top[0]['product']}" if top else "What's the overall portfolio status?",
            "What's the worst performing product and why?",
            "What should I do about the security posture?",
        ],
    )


def handle_risk_explanation(ctx: IntentContext) -> IntentResult:
    result = IntentResult(narrative="", source_modules=["risk_scorer"])
    risk_metric = next((m for m in ctx.metrics if "risk" in m.get("id", "").lower()), None)

    if risk_metric:
        result.narrative = (
            f"Risk score: {_fmt_value(risk_metric.get('current'))} "
            f"({_rag_label(risk_metric.get('ragColor', ''))}) — "
            f"{_fmt_delta(risk_metric.get('change'))} from prior period."
        )
    else:
        result.narrative = "No risk metric found in current data."

    if ctx.red_metrics:
        top = ctx.red_metrics[:3]
        result.narrative += "\n\nRed zone contributors:"
        for m in top:
            title = m.get("title", m.get("id", ""))
            result.narrative += f"\n  • {title} — {_fmt_value(m.get('current'))} ({_fmt_delta(m.get('change'))})"
    else:
        result.narrative += "\n\nNo metrics are currently in the red zone."

    result.evidence_cards = [_metric_card(m) for m in ctx.red_metrics[:4]]
    result.signal_pills = [
        {
            "type": "threshold_breach",
            "metric_id": m.get("id", ""),
            "severity": "critical",
            "label": f"{m.get('title', m.get('id', ''))} is red",
        }
        for m in ctx.red_metrics[:3]
    ]
    result.suggested_followups = [
        "What's the deployment trend over the last 5 weeks?",
        "Which product has the highest risk?",
        "What's improving fastest?",
    ]
    return result


def handle_portfolio_summary(ctx: IntentContext) -> IntentResult:
    result = IntentResult(narrative="", source_modules=["signals"])
    n_red = len(ctx.red_metrics)
    n_amber = len(ctx.amber_metrics)
    n_green = len(ctx.green_metrics)

    if n_red:
        top_concern = ctx.red_metrics[0].get("title", ctx.red_metrics[0].get("id", "unknown"))
        result.narrative = (
            f"Portfolio health: {n_red} red, {n_amber} amber, {n_green} green metric(s).\n\n"
            f"Top concern: {top_concern} "
            f"(current: {_fmt_value(ctx.red_metrics[0].get('current'))}, "
            f"change: {_fmt_delta(ctx.red_metrics[0].get('change'))})"
        )
    else:
        result.narrative = f"The portfolio looks relatively healthy — {n_amber} amber, {n_green} green metric(s)."

    if ctx.products:
        sorted_products = sorted(ctx.products, key=lambda p: (-int(p["score"]), str(p["product"])))
        top_product = sorted_products[0]
        result.narrative += (
            f"\n\nHighest-risk product: {top_product['product']} "
            f"(score {top_product['score']}, "
            f"{top_product['critical']} critical)"
        )

    if n_green:
        green_names = ", ".join(m.get("title", m.get("id", "")) for m in ctx.green_metrics[:2])
        result.narrative += f"\n\nPositives this sprint: {green_names}."

    result.evidence_cards = [_metric_card(m) for m in (ctx.red_metrics + ctx.amber_metrics)[:4]]
    result.signal_pills = [
        {
            "type": "threshold_breach",
            "metric_id": m.get("id", ""),
            "severity": "critical" if m.get("ragColor") == _RAG_RED else "warning",
            "label": f"{m.get('title', m.get('id', ''))} needs attention",
        }
        for m in (ctx.red_metrics + ctx.amber_metrics)[:3]
    ]
    result.suggested_followups = [
        "Why is the risk score high?",
        "What's driving the deployment issues?",
        "Which product is improving fastest?",
    ]
    return result


def handle_trend_drill(ctx: IntentContext) -> IntentResult:
    result = IntentResult(narrative="", source_modules=["change_point_detector"])
    improving = [m for m in ctx.metrics if (m.get("change") or 0) < 0 and m.get("ragColor") == _RAG_GREEN]
    worsening = [m for m in ctx.metrics if (m.get("change") or 0) > 0 and m.get("ragColor") == _RAG_RED]

    if worsening:
        names = ", ".join(m.get("title", m.get("id", "")) for m in worsening[:2])
        result.narrative = f"The metrics showing the most deterioration are: {names}. "
    else:
        result.narrative = "No strongly worsening trends detected in the current data. "

    if improving:
        imp_names = ", ".join(m.get("title", m.get("id", "")) for m in improving[:2])
        result.narrative += f"Metrics that are improving: {imp_names}. "

    result.narrative += "Use the evidence cards to review week-on-week changes."

    trend_relevant = (worsening + improving)[:4] or ctx.metrics[:4]
    result.evidence_cards = [_metric_card(m) for m in trend_relevant]
    result.signal_pills = [
        {
            "type": "sustained_deterioration",
            "metric_id": m.get("id", ""),
            "severity": "warning",
            "label": f"{m.get('title', m.get('id', ''))} deteriorating",
        }
        for m in worsening[:3]
    ]
    result.suggested_followups = [
        "Why is risk high?",
        "What's happening with deployment build rates?",
        "What should I worry about this sprint?",
    ]
    return result


def handle_deployment_compare(ctx: IntentContext) -> IntentResult:
    deploy_metric = next(
        (m for m in ctx.metrics if "deployment" in m.get("id", "").lower() or "build" in m.get("id", "").lower()),
        None,
    )

    if deploy_metric:
        current = _fmt_value(deploy_metric.get("current"))
        delta = _fmt_delta(deploy_metric.get("change"))
        rag = _rag_label(deploy_metric.get("ragColor", ""))
        health_note = (
            "This is below the acceptable threshold and needs immediate investigation. "
            if deploy_metric.get("ragColor") == _RAG_RED
            else "Deployment health is within acceptable bounds. "
        )
        narrative = (
            f"Build/deployment success rate is currently {current} ({delta} vs prior period) — status: {rag}. "
            + health_note
            + "Review pipeline trends in the evidence cards."
        )
        evidence_cards = _pad_evidence([_metric_card(deploy_metric)], ctx, exclude_id=deploy_metric.get("id"))
        signal_pills = [
            {
                "type": "threshold_breach",
                "metric_id": deploy_metric.get("id", "deployment"),
                "severity": "critical" if deploy_metric.get("ragColor") == _RAG_RED else "info",
                "label": "Build success rate below threshold",
            }
        ]
    else:
        narrative = (
            "No deployment metric found in the current dashboard. "
            "Ensure the deployment collector is running and producing history data."
        )
        evidence_cards = _pad_evidence([], ctx)
        signal_pills = []

    return IntentResult(
        narrative=narrative,
        source_modules=["deployment_collector"],
        evidence_cards=evidence_cards,
        signal_pills=signal_pills,
        suggested_followups=[
            "What's the overall portfolio status?",
            "Which product has the worst risk?",
            "Is deployment trend improving or declining?",
        ],
    )


def handle_ownership_query(ctx: IntentContext) -> IntentResult:
    result = IntentResult(narrative="", source_modules=["ownership_collector"])
    ownership_metric = next(
        (m for m in ctx.metrics if "ownership" in m.get("id", "").lower()),
        None,
    )

    if ownership_metric:
        result.narrative = (
            f"Ownership health is {_rag_label(ownership_metric.get('ragColor', 'neutral'))} "
            f"with a current score of {_fmt_value(ownership_metric.get('current'))} "
            f"({_fmt_delta(ownership_metric.get('change'))} vs prior week). "
            "Single-owner files represent a knowledge concentration risk. "
            "Review the ownership history to identify at-risk modules."
        )
    else:
        result.narrative = (
            "No ownership metric found in the current dashboard. "
            "Ensure the ownership collector has run and produced history data. "
            "Single-owner files present a bus-factor risk if the owner is unavailable."
        )

    evidence_cards: list[dict[str, Any]] = []
    if ownership_metric:
        evidence_cards.append(_metric_card(ownership_metric))
    for m in ctx.red_metrics[:3]:
        if ownership_metric and m.get("id") == ownership_metric.get("id"):
            continue
        if len(evidence_cards) >= 4:
            break
        evidence_cards.append({**_metric_card(m), "rag": "red"})
    result.evidence_cards = evidence_cards

    result.signal_pills = (
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
    result.suggested_followups = [
        "Which metrics are in the red zone?",
        "What's the overall portfolio health?",
        "Is deployment stability improving?",
    ]
    return result


def _security_named_product(
    named_product: dict[str, Any],
    ctx: IntentContext,
) -> IntentResult:
    """Security response scoped to a specific named product."""
    pname = named_product["product"]
    p_alerts = _alerts_for_product(pname, ctx.alerts)
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
        f"{named_product['critical']} critical — {rag}."
    )
    if reasons:
        bullet_lines = [r.strip() for r in reasons.split("•") if r.strip()]
        narrative += "\n\nKey issues:\n" + "\n".join(f"  • {b}" for b in bullet_lines)
    else:
        narrative += "\n\nNo security-specific alerts found for this product."

    evidence_cards: list[dict[str, Any]] = [
        {
            "label": pname,
            "value": str(named_product["score"]),
            "delta": f"{named_product['critical']}× critical",
            "rag": rag,
        }
    ]
    evidence_cards.extend(_alert_cards(sec_alerts or p_alerts))

    return IntentResult(
        narrative=narrative,
        source_modules=["risk_scorer"],
        evidence_cards=evidence_cards,
        signal_pills=[
            {
                "type": "threshold_breach",
                "metric_id": f"security_{pname.lower().replace(' ', '_')}",
                "severity": "critical" if named_product["critical"] > 0 else "warning",
                "label": f"{pname} security — {rag}",
            }
        ],
        suggested_followups=[
            f"What's the overall status of {pname}?",
            "Which product has the worst security posture?",
            "What should we prioritise this sprint?",
        ],
    )


def _security_product_ranking(
    sec_products: list[dict[str, Any]],
    sec_metric: dict[str, Any] | None,
) -> IntentResult:
    """Security response with per-product ranking."""
    result = IntentResult(narrative="", source_modules=["risk_scorer"])
    worst_product = sec_products[0]
    best_product_item = sec_products[-1] if len(sec_products) > 1 else None
    result.narrative = (
        f"The product with the highest security risk is {worst_product['product']} "
        f"(risk score: {worst_product['score']}, "
        f"{worst_product['critical']} critical alert(s)). "
    )
    if best_product_item:
        result.narrative += (
            f"{best_product_item['product']} is the strongest performer "
            f"with a score of {best_product_item['score']}. "
        )
    if sec_metric:
        rag = _rag_label(sec_metric.get("ragColor", ""))
        result.narrative += f"Portfolio-level security is {rag} at {_fmt_value(sec_metric.get('current'))}."

    result.evidence_cards = [
        {
            "label": p["product"],
            "value": f"Score {p['score']}",
            "delta": f"{p['critical']}× critical",
            "rag": "red" if p["critical"] > 0 else "amber",
        }
        for p in sec_products[:3]
    ]
    if sec_metric and len(result.evidence_cards) < 4:
        result.evidence_cards.append(_metric_card(sec_metric))
    result.signal_pills = [
        {
            "type": "threshold_breach",
            "metric_id": f"security_{p['product'].lower().replace(' ', '_')}",
            "severity": "critical" if p["critical"] > 0 else "warning",
            "label": f"{p['product']} security at risk",
        }
        for p in sec_products[:3]
    ]
    result.suggested_followups = [
        "What's the overall portfolio risk?",
        "Is the security trend improving?",
        "What should I prioritise next?",
    ]
    return result


def _security_metric_only(sec_metric: dict[str, Any]) -> IntentResult:
    """Security response with only a portfolio-level metric (no per-product data)."""
    result = IntentResult(narrative="", source_modules=["risk_scorer"])
    rag = _rag_label(sec_metric.get("ragColor", ""))
    result.narrative = (
        f"Security posture is currently {rag} — "
        f"{sec_metric.get('title', 'Security')} at {_fmt_value(sec_metric.get('current'))} "
        f"({_fmt_delta(sec_metric.get('change'))} vs prior period). "
    )
    if sec_metric.get("ragColor") == _RAG_GREEN:
        result.narrative += "The portfolio is tracking toward its security target."
    elif sec_metric.get("ragColor") == _RAG_RED:
        result.narrative += "Exploitable vulnerabilities need immediate attention."
    else:
        result.narrative += "Some progress is being made but the target has not yet been reached."
    result.evidence_cards = [_metric_card(sec_metric)]
    result.suggested_followups = [
        "What's the overall portfolio risk?",
        "Is the security trend improving?",
        "What should I prioritise next?",
    ]
    return result


def handle_security_query(ctx: IntentContext) -> IntentResult:
    sec_metric = next(
        (m for m in ctx.metrics if any(k in m.get("id", "").lower() for k in ("security", "exploitable", "vuln"))),
        None,
    )

    named_product = _extract_product(ctx.query, ctx.products)
    sec_products = [p for p in ctx.products if "security" in p.get("domains", [])]
    if not sec_products:
        sec_products = ctx.products

    if named_product:
        return _security_named_product(named_product, ctx)
    if sec_products:
        return _security_product_ranking(sec_products, sec_metric)
    if sec_metric:
        return _security_metric_only(sec_metric)

    return IntentResult(
        narrative=(
            "No security data found in the current dashboard. "
            "Ensure the security collector has run and produced history data."
        ),
        source_modules=["risk_scorer"],
        suggested_followups=[
            "What's the overall portfolio risk?",
            "What should I prioritise next?",
        ],
    )


def handle_worst_metric(ctx: IntentContext) -> IntentResult:
    result = IntentResult(narrative="", source_modules=["signals"])

    if ctx.red_metrics:
        worst = ctx.red_metrics[0]
        result.narrative = (
            f"The metric in worst health is {worst.get('title', worst.get('id', 'unknown'))} "
            f"at {_fmt_value(worst.get('current'))} ({_fmt_delta(worst.get('change'))} vs prior period) — currently red. "
        )
        if len(ctx.red_metrics) > 1:
            others = ", ".join(m.get("title", m.get("id", "")) for m in ctx.red_metrics[1:3])
            result.narrative += f"Other red metrics: {others}. "
        result.narrative += "Focus remediation effort here first."
    elif ctx.amber_metrics:
        worst = ctx.amber_metrics[0]
        result.narrative = (
            f"No metrics are currently in the red zone. "
            f"The most at-risk metric is {worst.get('title', worst.get('id', 'unknown'))} "
            f"at {_fmt_value(worst.get('current'))} ({_fmt_delta(worst.get('change'))}) — amber. "
            "Monitor closely."
        )
    else:
        result.narrative = "All metrics are currently in the green zone. The portfolio is in good health."

    result.evidence_cards = [_metric_card(m) for m in (ctx.red_metrics + ctx.amber_metrics)[:4]]
    result.signal_pills = [
        {
            "type": "threshold_breach",
            "metric_id": m.get("id", ""),
            "severity": "critical",
            "label": f"{m.get('title', m.get('id', ''))} is red",
        }
        for m in ctx.red_metrics[:2]
    ]
    result.suggested_followups = [
        "Why is risk high?",
        "What's the deployment status?",
        "Where should I focus next?",
    ]
    return result


_BEST_PRODUCT_FOLLOWUPS = [
    "What needs the most attention right now?",
    "Which product has the worst risk?",
    "How is deployment performing?",
]


def _best_product_ranked(ranked: list[dict[str, Any]], ctx: IntentContext) -> IntentResult:
    """Best product response when product data is available."""
    best = ranked[0]
    narrative = (
        f"The best performing product is {best['product']} with the lowest risk score "
        f"of {best['score']} ({best.get('critical', 0)} critical, "
        f"{best.get('warn', 0)} warning alert(s)). "
    )
    if len(ranked) > 1:
        narrative += f"Next best is {ranked[1]['product']} (score: {ranked[1]['score']}). "
    if ctx.green_metrics:
        green_names = ", ".join(m.get("title", m.get("id", "")) for m in ctx.green_metrics[:2])
        narrative += f"Healthy metrics across the portfolio: {green_names}."

    return IntentResult(
        narrative=narrative,
        source_modules=["product_risk"],
        evidence_cards=[
            {
                "label": p["product"],
                "value": str(p["score"]),
                "delta": f"{p.get('critical', 0)}× critical",
                "rag": (
                    "green"
                    if p["critical"] == 0 and p.get("warn", 0) == 0
                    else ("amber" if p["critical"] == 0 else "red")
                ),
            }
            for p in ranked[:4]
        ],
        signal_pills=[
            {
                "type": "recovery_trend",
                "metric_id": f"product_{ranked[0]['product'].lower().replace(' ', '_')}",
                "severity": "info",
                "label": f"{ranked[0]['product']} — lowest risk",
            }
        ],
        suggested_followups=_BEST_PRODUCT_FOLLOWUPS,
    )


def _best_product_fallback(ctx: IntentContext) -> IntentResult:
    """Best product response when no product data is available."""
    if ctx.green_metrics:
        best_m = ctx.green_metrics[0]
        narrative = (
            f"No per-product data available. The healthiest metric is "
            f"{best_m.get('title', best_m.get('id', 'unknown'))} at "
            f"{_fmt_value(best_m.get('current'))} "
            f"({_fmt_delta(best_m.get('change'))} vs prior period)."
        )
    else:
        narrative = (
            "No products or green metrics found. "
            "The portfolio is under pressure — focus on reducing red and amber metrics."
        )
    return IntentResult(
        narrative=narrative,
        source_modules=["product_risk"],
        evidence_cards=[_metric_card(m) for m in ctx.green_metrics[:4]],
        suggested_followups=_BEST_PRODUCT_FOLLOWUPS,
    )


def handle_best_product(ctx: IntentContext) -> IntentResult:
    ranked = sorted(ctx.products, key=lambda p: (int(p["score"]), str(p["product"])))
    if ranked:
        return _best_product_ranked(ranked, ctx)
    return _best_product_fallback(ctx)


_SECTION_GUIDE: list[tuple[list[str], str, str]] = [
    (
        ["anomaly river"],
        "Anomaly River",
        "The Anomaly River is a time-based heatmap showing anomaly intensity across metric domains (security, deployment, flow, quality, etc.) over recent weeks. Brighter/warmer colours indicate stronger anomalies — periods where metrics deviated significantly from their normal range. Click any domain row to drill into that metric's history.",
    ),
    (
        ["system shape", "radar chart", "spider chart", "health radar"],
        "System Shape Radar",
        "The System Shape radar chart shows engineering health across all metric domains simultaneously. Each axis is a domain — the further the plot extends outward, the healthier that domain. An ideal shape is a large, balanced polygon. A lopsided shape reveals which domains are lagging.",
    ),
    (
        ["movement layer", "movement panel"],
        "Movement Layer",
        "The Movement Layer shows week-over-week changes for every metric. It highlights which metrics moved significantly (up or down) since the last data collection, helping you spot sudden shifts that need investigation.",
    ),
    (
        ["narrative layer", "narrative panel"],
        "Narrative Layer",
        "The Narrative Layer provides a text summary of the current engineering health state, combining signals from the health score, active alerts, and collision detection to tell a coherent story about what's happening.",
    ),
    (
        ["alert layer", "risk signals panel"],
        "Alert Layer / Active Risk Signals",
        "The Alert Layer shows all currently firing alerts across the portfolio. Alerts are grouped by severity (critical, warning). When multiple domains deteriorate simultaneously a cross-domain collision escalation banner appears, signalling a systemic issue.",
    ),
    (
        ["metric grid", "metric cards", "metric overview"],
        "Metric Overview Grid",
        "The Metric Overview grid displays all tracked metrics as cards. Each card shows the current value, week-over-week change, a sparkline trend line, and RAG (Red/Amber/Green) status. Click any card to open the investigation drawer for deeper analysis.",
    ),
    (
        ["product risk panel", "product risk breakdown", "risk breakdown", "risk panel"],
        "Product Risk Panel",
        "The Product Risk Panel ranks products by risk score. Scores are calculated from alert severity: critical alerts score 3 points, warnings and medium alerts score 1 each. Higher scores mean more active problems across that product's domains.",
    ),
    (
        ["health score card", "health score panel", "health score"],
        "Health Score",
        "The Health Score (0–100) is a weighted composite of all metric domains. It factors in how many metrics are green vs red/amber, the severity of active alerts, and trend direction. Above 70 is generally healthy, 40–70 needs attention, below 40 is critical.",
    ),
    (
        ["collision banner", "escalation banner", "collision"],
        "Collision Escalation",
        "The Collision Escalation banner appears when multiple metric domains deteriorate at the same time, suggesting a systemic issue rather than an isolated problem. High-confidence collisions warrant immediate investigation.",
    ),
    (
        ["sparkline"],
        "Sparklines",
        "Sparklines are the small inline trend charts on each metric card. They show the metric's value over the last several weeks so you can see the direction of travel at a glance without opening the detail view.",
    ),
    (
        ["investigation drawer"],
        "Metric Investigation Drawer",
        "The Investigation Drawer opens when you click a metric card or an Anomaly River row. It provides a deep dive into that metric's history, change points, and contributing factors.",
    ),
    (
        [
            "score calculated",
            "how is the score",
            "how are scores",
            "how does the score",
            "how does scoring",
            "risk calculated",
            "methodology",
            "how does this work",
            "how does it work",
        ],
        "Risk Score Methodology",
        "Product risk scores are calculated from active alerts:\n\n  • Critical alerts = 3 points each\n  • Warning/medium alerts = 1 point each\n\nHigher scores mean more active problems across that product's domains (security, deployment, quality, flow, ownership).\n\nRAG status thresholds:\n  • Red: any critical alerts present\n  • Amber: warnings only, no criticals\n  • Green: no active alerts",
    ),
]

_GENERIC_VISUAL_EXPLANATION = (
    "The Engineering Command Centre has these main sections: "
    "Health Score (overall 0–100 composite), "
    "Alert Layer (active risk signals), "
    "System Shape radar (domain health), "
    "Movement Layer (week-over-week changes), "
    "Narrative Layer (text summary), "
    "Anomaly River (time-heatmap of anomalies), "
    "Metric Overview grid (all metric cards with sparklines), "
    "and the Product Risk Panel (per-product risk ranking). "
    "Ask about any specific section for more detail."
)


def _match_section(query: str) -> tuple[str, str]:
    """Match a query to a dashboard section. Returns (section_name, explanation)."""
    lowered = query.lower()
    for keywords, section_name, explanation in _SECTION_GUIDE:
        if any(kw in lowered for kw in keywords):
            return section_name, explanation
    return "dashboard", _GENERIC_VISUAL_EXPLANATION


def _visual_evidence_cards(section: str, ctx: IntentContext) -> list[dict[str, Any]]:
    """Pick evidence cards appropriate for the matched dashboard section."""
    if section == "Product Risk Panel" and ctx.products:
        ranked = sorted(ctx.products, key=lambda p: (-int(p["score"]), str(p["product"])))
        return [_product_card(p) for p in ranked[:3]]
    if section in ("Health Score", "Alert Layer / Active Risk Signals"):
        return [_metric_card(m) for m in (ctx.red_metrics + ctx.amber_metrics)[:3]]
    return [_metric_card(m) for m in (ctx.red_metrics + ctx.amber_metrics + ctx.green_metrics)[:3]]


def handle_visual_explanation(ctx: IntentContext) -> IntentResult:
    section, narrative = _match_section(ctx.query)
    return IntentResult(
        narrative=narrative,
        source_modules=["dashboard"],
        evidence_cards=_visual_evidence_cards(section, ctx),
        signal_pills=(
            [
                {
                    "type": "info",
                    "metric_id": f"visual_{section.lower().replace(' ', '_')}",
                    "severity": "info",
                    "label": f"Explaining: {section}",
                }
            ]
            if section
            else []
        ),
        suggested_followups=[
            "What does the anomaly river show?",
            "How do I read the system shape radar?",
            "What's the overall portfolio health?",
        ],
    )


_METRIC_HINTS: list[tuple[list[str], str]] = [
    (["lead time", "cycle time"], "flow"),
    (["merge time", "pr merge", "pull request merge"], "collaboration"),
    (["open bugs", "bug count", "bugs", "number of bugs", "how many bugs"], "bugs"),
    (["unassigned", "work unassigned"], "ownership"),
    (["total commits", "commit count", "commit volume"], "risk"),
    (["reduction target", "70% target", "70 percent"], "target"),
    (["ai usage", "ai tracker", "copilot"], "ai-usage"),
    (["infrastructure vuln", "infra vuln"], "security-infra"),
    (["code and cloud", "code & cloud"], "security"),
    (["build success rate", "build success"], "deployment"),
    (["exploitable"], "exploitable"),
]

_METRIC_DETAIL_FOLLOWUPS = [
    "What's the overall portfolio health?",
    "Which metric is most at risk?",
    "How has this changed over time?",
]


def _resolve_metric(query: str, metrics: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Resolve a metric from query text using keyword hints then title/id fallback."""
    lowered = query.lower()
    for hint_keywords, metric_id in _METRIC_HINTS:
        if any(kw in lowered for kw in hint_keywords):
            return next((m for m in metrics if m.get("id") == metric_id), None)

    for m in metrics:
        mid = m.get("id", "").lower()
        mtitle = m.get("title", "").lower()
        if mid in lowered or mtitle in lowered:
            return m
    return None


def _metric_detail_found(matched: dict[str, Any], ctx: IntentContext) -> IntentResult:
    """Build response for a successfully resolved metric."""
    title = matched.get("title", matched.get("id", "unknown"))
    current = _fmt_value(matched.get("current"))
    delta = _fmt_delta(matched.get("change"))
    rag = _rag_label(matched.get("ragColor", ""))
    desc = matched.get("description", "")

    change_val = matched.get("change")
    try:
        change_num = float(change_val) if change_val is not None else 0.0
    except (TypeError, ValueError):
        change_num = 0.0

    narrative = f"{title} is currently at {current} ({delta} vs last week) — status: {rag}. "
    if desc:
        narrative += f"{desc} "
    narrative += _rag_commentary(rag, change_num)

    return IntentResult(
        narrative=narrative,
        source_modules=["pipeline"],
        evidence_cards=_pad_evidence([_metric_card(matched)], ctx, exclude_id=matched.get("id")),
        signal_pills=[
            {
                "type": "threshold_breach" if rag == "red" else "info",
                "metric_id": matched.get("id", ""),
                "severity": "critical" if rag == "red" else ("warning" if rag == "amber" else "info"),
                "label": f"{title}: {current} ({rag})",
            }
        ],
        suggested_followups=_METRIC_DETAIL_FOLLOWUPS,
    )


def _metric_detail_not_found(ctx: IntentContext) -> IntentResult:
    """Build response when the requested metric could not be identified."""
    metric_names = ", ".join(m.get("title", m.get("id", "")) for m in ctx.metrics[:8])
    return IntentResult(
        narrative=(
            "I couldn't identify which specific metric you're asking about. "
            f"Available metrics include: {metric_names}. "
            "Try asking by name, e.g. 'What's the current lead time?' or "
            "'How are bugs looking?'"
        ),
        source_modules=["pipeline"],
        evidence_cards=[_metric_card(m) for m in (ctx.red_metrics + ctx.amber_metrics + ctx.green_metrics)[:4]],
        suggested_followups=_METRIC_DETAIL_FOLLOWUPS,
    )


def handle_metric_detail(ctx: IntentContext) -> IntentResult:
    matched = _resolve_metric(ctx.query, ctx.metrics)
    if matched:
        return _metric_detail_found(matched, ctx)
    return _metric_detail_not_found(ctx)


def handle_unknown(ctx: IntentContext) -> IntentResult:
    metric_names = ", ".join(m.get("title", m.get("id", "")) for m in ctx.metrics[:8])
    return IntentResult(
        narrative=(
            "I'm not sure how to answer that specific question. "
            "I can help with: portfolio health overview, risk explanations, "
            "security posture, deployment/build status, ownership & bus factor, "
            "trend analysis, product comparisons, or details on specific metrics. "
            f"Available metrics: {metric_names}. "
            "Try one of the suggestions below."
        ),
        evidence_cards=[_metric_card(m) for m in (ctx.red_metrics + ctx.amber_metrics + ctx.green_metrics)[:4]],
        signal_pills=[],
        suggested_followups=[
            "What should I worry about this sprint?",
            "Which product has the highest risk?",
            "What's the current build success rate?",
            "How does the anomaly river work?",
        ],
    )


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

INTENT_HANDLERS: dict[str, Any] = {
    "product_query": handle_product_query,
    "worst_product": handle_worst_product,
    "attention_areas": handle_attention_areas,
    "risk_explanation": handle_risk_explanation,
    "portfolio_summary": handle_portfolio_summary,
    "trend_drill": handle_trend_drill,
    "deployment_compare": handle_deployment_compare,
    "ownership_query": handle_ownership_query,
    "security_query": handle_security_query,
    "worst_metric": handle_worst_metric,
    "best_product": handle_best_product,
    "visual_explanation": handle_visual_explanation,
    "metric_detail": handle_metric_detail,
}
