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
        assert route_intent("what is the build success rate?", {}) == "deployment_compare"

    def test_ownership_keywords(self) -> None:
        assert route_intent("who owns these modules", {}) == "ownership_query"

    def test_ownership_keyword_single_owner(self) -> None:
        assert route_intent("which files have a single owner?", {}) == "ownership_query"

    def test_best_product_keywords(self) -> None:
        assert route_intent("which metric is improving fastest", {}) == "best_product"

    def test_best_product_keyword_healthiest(self) -> None:
        assert route_intent("what is going well in the portfolio", {}) == "best_product"

    def test_security_keywords(self) -> None:
        assert route_intent("which product has the worst security posture", {}) == "security_query"

    def test_security_keyword_exploitable(self) -> None:
        assert route_intent("how many exploitable vulnerabilities are there", {}) == "security_query"

    def test_worst_metric_keywords(self) -> None:
        assert route_intent("which metric is failing", {}) == "worst_metric"

    def test_trend_keywords(self) -> None:
        assert route_intent("is it getting worse?", {}) == "trend_drill"

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
