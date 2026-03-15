"""
Tests for execution.intelligence.query_engine — Ask EI conversational layer.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from execution.intelligence.query_engine import (
    build_query_response,
    compose_response,
    route_intent,
)

MOCK_TRENDS: dict = {
    "metrics": [
        {
            "id": "risk",
            "title": "Risk Score",
            "current": 74,
            "change": 16,
            "ragColor": "#ef4444",
            "data": [58, 60, 65, 70, 74],
        },
        {
            "id": "deployment",
            "title": "Build Success Rate",
            "current": 61,
            "change": -27,
            "ragColor": "#ef4444",
            "data": [88, 86, 80, 73, 61],
        },
        {
            "id": "quality",
            "title": "Bug Escape Rate",
            "current": 3.8,
            "change": 1.7,
            "ragColor": "#f59e0b",
            "data": [2.1, 2.3, 2.8, 3.4, 3.8],
        },
        {
            "id": "flow",
            "title": "Lead Time",
            "current": 18,
            "change": 0,
            "ragColor": "#f59e0b",
            "data": [16, 18, 17, 19, 18],
        },
        {
            "id": "security",
            "title": "Exploitable Vulns",
            "current": 3,
            "change": -5,
            "ragColor": "#10b981",
            "data": [8, 7, 6, 5, 3],
        },
    ],
    "alerts": [],
    "timestamp": "2026-03-10T00:00:00",
}


# ---------------------------------------------------------------------------
# TestRouteIntent
# ---------------------------------------------------------------------------


class TestRouteIntent:
    def test_risk_keywords(self) -> None:
        assert route_intent("why is risk high", {}) == "risk_explanation"

    def test_risk_keyword_driving(self) -> None:
        assert route_intent("what's driving the score up", {}) == "risk_explanation"

    def test_portfolio_keywords(self) -> None:
        assert route_intent("what should I worry about", {}) == "portfolio_summary"

    def test_portfolio_keyword_overview(self) -> None:
        assert route_intent("give me an overview of the portfolio", {}) == "portfolio_summary"

    def test_deploy_keywords(self) -> None:
        assert route_intent("deployment is failing", {}) == "deployment_compare"

    def test_deploy_keyword_build(self) -> None:
        # "build success rate" matches metric_detail (more specific) before deployment_compare
        assert route_intent("show me the build success rate", {}) == "metric_detail"

    def test_ownership_keywords(self) -> None:
        assert route_intent("who owns these modules", {}) == "ownership_query"

    def test_ownership_keyword_single_owner(self) -> None:
        assert route_intent("which files have a single owner?", {}) == "ownership_query"

    def test_best_product_keywords(self) -> None:
        assert route_intent("which metric is improving fastest", {}) == "best_product"

    def test_best_product_keyword_healthiest(self) -> None:
        assert route_intent("what is going well right now", {}) == "best_product"

    def test_security_keywords(self) -> None:
        assert route_intent("which product has the worst security posture", {}) == "security_query"

    def test_security_keyword_exploitable(self) -> None:
        assert route_intent("how many exploitable vulnerabilities are there", {}) == "security_query"

    def test_worst_metric_keywords(self) -> None:
        assert route_intent("which metric is failing", {}) == "worst_metric"

    def test_trend_keywords(self) -> None:
        assert route_intent("is it getting worse?", {}) == "trend_drill"

    # --- New: visual_explanation intent ---
    def test_visual_anomaly_river(self) -> None:
        assert route_intent("what does the anomaly river show?", {}) == "visual_explanation"

    def test_visual_system_shape(self) -> None:
        assert route_intent("explain the system shape radar", {}) == "visual_explanation"

    def test_visual_showing_me(self) -> None:
        assert route_intent("what is the product risk breakdown showing me on this page?", {}) == "visual_explanation"

    def test_visual_what_is_the(self) -> None:
        assert route_intent("what is the movement layer?", {}) == "visual_explanation"

    def test_visual_sparkline(self) -> None:
        assert route_intent("what do the sparklines mean?", {}) == "visual_explanation"

    def test_visual_how_to_read(self) -> None:
        assert route_intent("how do i read this chart?", {}) == "visual_explanation"

    def test_visual_this_section(self) -> None:
        assert route_intent("what does this section do?", {}) == "visual_explanation"

    # --- New: metric_detail intent ---
    def test_metric_detail_lead_time(self) -> None:
        assert route_intent("what's the lead time right now?", {}) == "metric_detail"

    def test_metric_detail_bugs(self) -> None:
        assert route_intent("how many bugs are open?", {}) == "metric_detail"

    def test_metric_detail_build_success(self) -> None:
        assert route_intent("what's the build success rate?", {}) == "metric_detail"

    def test_metric_detail_reduction_target(self) -> None:
        assert route_intent("where are we on the 70% target?", {}) == "metric_detail"

    def test_metric_detail_ai_usage(self) -> None:
        assert route_intent("show me ai usage stats", {}) == "metric_detail"

    def test_metric_detail_unassigned(self) -> None:
        assert route_intent("what's the unassigned work percentage?", {}) == "metric_detail"

    # --- Expanded keyword coverage for existing intents ---
    def test_risk_bare_keyword(self) -> None:
        assert route_intent("what is the risk situation?", {}) == "risk_explanation"

    def test_risk_red_metrics(self) -> None:
        assert route_intent("what's the risk explanation for red metrics?", {}) == "risk_explanation"

    def test_risk_why_red(self) -> None:
        assert route_intent("why are there so many red metrics?", {}) == "risk_explanation"

    def test_portfolio_tldr(self) -> None:
        assert route_intent("give me the tldr", {}) == "portfolio_summary"

    def test_portfolio_catch_me_up(self) -> None:
        assert route_intent("catch me up on the portfolio", {}) == "portfolio_summary"

    def test_portfolio_how_are_we(self) -> None:
        assert route_intent("how are we doing overall?", {}) == "portfolio_summary"  # matches "overall"

    def test_portfolio_executive_summary(self) -> None:
        assert route_intent("executive summary please", {}) == "portfolio_summary"

    def test_trend_over_time(self) -> None:
        assert route_intent("how have metrics changed over time?", {}) == "trend_drill"

    def test_trend_getting_better(self) -> None:
        assert route_intent("are things getting better?", {}) == "trend_drill"

    def test_trend_past_weeks(self) -> None:
        assert route_intent("show me the past few weeks", {}) == "trend_drill"

    def test_trend_compared_to_last(self) -> None:
        assert route_intent("how does this compare to last week?", {}) == "trend_drill"

    def test_attention_urgent(self) -> None:
        assert route_intent("anything urgent I should know about?", {}) == "attention_areas"

    def test_attention_where_to_start(self) -> None:
        assert route_intent("where should I start today?", {}) == "attention_areas"

    def test_security_vuln(self) -> None:
        assert route_intent("what's the vuln count?", {}) == "security_query"

    def test_security_cve(self) -> None:
        assert route_intent("any new CVEs this week?", {}) == "security_query"

    def test_deployment_cicd(self) -> None:
        assert route_intent("how's the CI/CD pipeline?", {}) == "deployment_compare"

    def test_deployment_shipping(self) -> None:
        assert route_intent("how often are we shipping?", {}) == "deployment_compare"

    def test_ownership_bus_factor(self) -> None:
        assert route_intent("what's our bus factor risk?", {}) == "ownership_query"

    def test_ownership_tribal_knowledge(self) -> None:
        assert route_intent("is there tribal knowledge risk?", {}) == "ownership_query"

    def test_best_good_news(self) -> None:
        assert route_intent("any good news this sprint?", {}) == "best_product"

    def test_best_bright_spot(self) -> None:
        assert route_intent("what's the bright spot?", {}) == "best_product"

    def test_worst_product_riskiest(self) -> None:
        assert route_intent("which is the riskiest product?", {}) == "worst_product"

    def test_worst_metric_failing(self) -> None:
        assert route_intent("what's failing right now?", {}) == "worst_metric"

    def test_fallback_unknown_query(self) -> None:
        assert route_intent("xyz abc 123", {}) == "portfolio_summary"

    def test_fallback_empty_query(self) -> None:
        assert route_intent("", {}) == "portfolio_summary"


# ---------------------------------------------------------------------------
# TestComposeResponse
# ---------------------------------------------------------------------------


class TestComposeResponse:
    """Tests for compose_response() using MOCK_TRENDS."""

    _REQUIRED_KEYS = {
        "generated_at",
        "intent",
        "narrative",
        "signal_pills",
        "evidence_cards",
        "suggested_followups",
        "source_modules",
        "context",
    }

    def _call(self, intent: str) -> dict:
        return compose_response(intent, {}, MOCK_TRENDS)

    def test_returns_required_keys(self) -> None:
        result = self._call("portfolio_summary")
        assert self._REQUIRED_KEYS.issubset(result.keys())

    def test_narrative_is_non_empty_string(self) -> None:
        for intent in [
            "risk_explanation",
            "portfolio_summary",
            "trend_drill",
            "deployment_compare",
            "ownership_query",
            "best_product",
        ]:
            result = self._call(intent)
            assert isinstance(result["narrative"], str)
            assert len(result["narrative"]) > 0, f"Empty narrative for intent: {intent}"

    def test_evidence_cards_have_correct_shape(self) -> None:
        result = self._call("risk_explanation")
        for card in result["evidence_cards"]:
            assert "label" in card
            assert "value" in card
            assert "delta" in card
            assert card["rag"] in ("red", "amber", "green", "neutral")

    def test_signal_pills_have_correct_shape(self) -> None:
        result = self._call("portfolio_summary")
        for pill in result["signal_pills"]:
            assert "type" in pill
            assert "metric_id" in pill
            assert "severity" in pill
            assert "label" in pill

    def test_suggested_followups_are_strings(self) -> None:
        result = self._call("risk_explanation")
        assert isinstance(result["suggested_followups"], list)
        for followup in result["suggested_followups"]:
            assert isinstance(followup, str)

    def test_source_modules_is_list_of_strings(self) -> None:
        result = self._call("trend_drill")
        assert isinstance(result["source_modules"], list)
        for mod in result["source_modules"]:
            assert isinstance(mod, str)

    def test_context_is_echoed(self) -> None:
        ctx = {"product": "Product_A"}
        result = compose_response("portfolio_summary", ctx, MOCK_TRENDS)
        assert result["context"] == ctx

    def test_intent_is_echoed(self) -> None:
        result = self._call("deployment_compare")
        assert result["intent"] == "deployment_compare"

    def test_risk_intent_finds_red_metrics(self) -> None:
        result = self._call("risk_explanation")
        # Risk score and deployment are both red in MOCK_TRENDS
        assert len(result["evidence_cards"]) >= 1
        assert result["evidence_cards"][0]["rag"] == "red"

    def test_best_product_finds_green_metrics(self) -> None:
        result = self._call("best_product")
        # security is green in MOCK_TRENDS
        assert any("Exploitable" in c["label"] or c["rag"] == "green" for c in result["evidence_cards"])

    def test_deployment_intent_finds_deployment_metric(self) -> None:
        result = self._call("deployment_compare")
        assert "Build Success Rate" in result["narrative"] or "deployment" in result["narrative"].lower()

    def test_handles_empty_metrics(self) -> None:
        empty_trends = {"metrics": [], "alerts": [], "timestamp": "2026-03-10T00:00:00"}
        result = compose_response("portfolio_summary", {}, empty_trends)
        assert isinstance(result["narrative"], str)
        assert len(result["narrative"]) > 0

    def test_evidence_cards_max_four(self) -> None:
        result = self._call("portfolio_summary")
        assert len(result["evidence_cards"]) <= 4

    def test_signal_pills_max_three(self) -> None:
        result = self._call("risk_explanation")
        assert len(result["signal_pills"]) <= 3

    # --- New: visual_explanation compose tests ---
    def test_visual_explanation_anomaly_river(self) -> None:
        result = compose_response("visual_explanation", {}, MOCK_TRENDS, query="what does the anomaly river show?")
        assert "Anomaly River" in result["narrative"]
        assert "heatmap" in result["narrative"].lower()

    def test_visual_explanation_radar(self) -> None:
        result = compose_response("visual_explanation", {}, MOCK_TRENDS, query="explain the system shape radar")
        assert "radar" in result["narrative"].lower()

    def test_visual_explanation_generic(self) -> None:
        result = compose_response("visual_explanation", {}, MOCK_TRENDS, query="what am I looking at?")
        assert "Health Score" in result["narrative"]
        assert "Anomaly River" in result["narrative"]

    def test_visual_explanation_product_risk_panel(self) -> None:
        result = compose_response(
            "visual_explanation",
            {},
            MOCK_TRENDS,
            query="what is the product risk breakdown showing me?",
        )
        assert "Product Risk" in result["narrative"]

    # --- New: metric_detail compose tests ---
    def test_metric_detail_finds_deployment(self) -> None:
        result = compose_response("metric_detail", {}, MOCK_TRENDS, query="what's the build success rate?")
        assert "Build Success Rate" in result["narrative"] or "61" in result["narrative"]
        assert result["evidence_cards"][0]["label"] == "Build Success Rate"

    def test_metric_detail_finds_flow(self) -> None:
        result = compose_response("metric_detail", {}, MOCK_TRENDS, query="what's the lead time?")
        assert "Lead Time" in result["narrative"]

    def test_metric_detail_not_found(self) -> None:
        result = compose_response("metric_detail", {}, MOCK_TRENDS, query="what's the nonexistent metric?")
        assert "couldn't identify" in result["narrative"].lower()

    # --- New: unknown fallback is honest ---
    def test_unknown_fallback_is_honest(self) -> None:
        result = compose_response("unknown_intent_xyz", {}, MOCK_TRENDS, query="zzzz")
        assert "not sure" in result["narrative"].lower()
        assert "suggested_followups" in result
        assert len(result["suggested_followups"]) > 0


# ---------------------------------------------------------------------------
# TestBuildQueryResponse
# ---------------------------------------------------------------------------


class TestBuildQueryResponse:
    """Tests for build_query_response() — full end-to-end with mocked pipeline."""

    @patch("execution.intelligence.query_engine.build_trends_context", return_value=MOCK_TRENDS)
    def test_end_to_end_risk_query(self, _mock: object) -> None:
        result = build_query_response("why is risk so high?")
        assert result["intent"] == "risk_explanation"
        assert "query" in result
        assert result["query"] == "why is risk so high?"

    @patch("execution.intelligence.query_engine.build_trends_context", return_value=MOCK_TRENDS)
    def test_end_to_end_portfolio_query(self, _mock: object) -> None:
        result = build_query_response("give me an overview")
        assert result["intent"] == "portfolio_summary"
        assert isinstance(result["narrative"], str)

    @patch("execution.intelligence.query_engine.build_trends_context", return_value=MOCK_TRENDS)
    def test_context_is_echoed_back(self, _mock: object) -> None:
        ctx = {"product": "Product_A", "sprint": "2026-W10"}
        result = build_query_response("what should I worry about", ctx)
        assert result["context"] == ctx

    @patch(
        "execution.intelligence.query_engine.build_trends_context",
        return_value={"metrics": [], "alerts": [], "timestamp": "2026-03-10T00:00:00"},
    )
    def test_handles_empty_metrics_gracefully(self, _mock: object) -> None:
        result = build_query_response("what's happening")
        assert isinstance(result, dict)
        assert "narrative" in result
        assert len(result["narrative"]) > 0

    @patch("execution.intelligence.query_engine.build_trends_context", return_value=MOCK_TRENDS)
    def test_response_contains_all_required_keys(self, _mock: object) -> None:
        result = build_query_response("overview")
        required = {
            "generated_at",
            "query",
            "intent",
            "narrative",
            "signal_pills",
            "evidence_cards",
            "suggested_followups",
            "source_modules",
            "context",
        }
        assert required.issubset(result.keys())

    @patch("execution.intelligence.query_engine.build_trends_context", return_value=MOCK_TRENDS)
    def test_none_context_defaults_to_empty_dict(self, _mock: object) -> None:
        result = build_query_response("overview", None)
        assert result["context"] == {}

    @patch("execution.intelligence.query_engine.build_trends_context", return_value=MOCK_TRENDS)
    def test_generated_at_is_iso_string(self, _mock: object) -> None:
        result = build_query_response("risk explanation")
        # Should parse without error
        from datetime import datetime

        datetime.fromisoformat(result["generated_at"])
