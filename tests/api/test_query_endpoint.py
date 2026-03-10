"""
API endpoint tests for POST /api/v1/intelligence/query (Ask EI).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from execution.api.app import create_app

_MOCK_RESPONSE: dict = {
    "generated_at": "2026-03-10T00:00:00+00:00",
    "query": "test query",
    "intent": "portfolio_summary",
    "narrative": "The portfolio has 2 red metrics requiring attention.",
    "signal_pills": [
        {"type": "threshold_breach", "metric_id": "risk", "severity": "critical", "label": "Risk Score is red"}
    ],
    "evidence_cards": [{"label": "Risk Score", "value": "74", "delta": "+16.0", "rag": "red"}],
    "suggested_followups": ["Why is the risk score high?", "What's the deployment trend?"],
    "source_modules": ["pipeline", "query_engine", "signals"],
    "context": {},
}


@pytest.fixture
def client() -> TestClient:
    """Create FastAPI test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def auth() -> tuple[str, str]:
    """HTTP Basic auth credentials for testing."""
    return ("admin", "changeme")


class TestQueryEndpoint:
    """Tests for POST /api/v1/intelligence/query."""

    def test_query_requires_auth(self, client: TestClient) -> None:
        """Endpoint must return 401 without credentials."""
        response = client.post(
            "/api/v1/intelligence/query",
            json={"query": "what should I worry about"},
        )
        assert response.status_code == 401

    def test_query_with_valid_question(
        self, client: TestClient, auth: tuple[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Valid authenticated request returns 200."""
        monkeypatch.setattr(
            "execution.intelligence.query_engine.build_query_response",
            lambda query, context=None: _MOCK_RESPONSE,
        )
        response = client.post(
            "/api/v1/intelligence/query",
            json={"query": "what should I worry about"},
            auth=auth,
        )
        assert response.status_code == 200

    def test_query_response_structure(
        self, client: TestClient, auth: tuple[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Response must contain all required schema keys."""
        monkeypatch.setattr(
            "execution.intelligence.query_engine.build_query_response",
            lambda query, context=None: _MOCK_RESPONSE,
        )
        response = client.post(
            "/api/v1/intelligence/query",
            json={"query": "overview"},
            auth=auth,
        )
        assert response.status_code == 200
        data = response.json()
        required_keys = {
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
        assert required_keys.issubset(data.keys())

    def test_query_with_context(
        self, client: TestClient, auth: tuple[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Context field is accepted and forwarded to the engine."""
        captured: dict = {}

        def fake_build(query: str, context: dict | None = None) -> dict:
            captured["query"] = query
            captured["context"] = context
            return {**_MOCK_RESPONSE, "context": context or {}}

        monkeypatch.setattr(
            "execution.intelligence.query_engine.build_query_response",
            fake_build,
        )
        payload = {"query": "what's wrong", "context": {"product": "Product_A"}}
        response = client.post("/api/v1/intelligence/query", json=payload, auth=auth)
        assert response.status_code == 200
        assert captured["context"] == {"product": "Product_A"}

    def test_unknown_query_returns_fallback_not_500(
        self, client: TestClient, auth: tuple[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unrecognised query should return 200 with fallback intent, not 500."""
        monkeypatch.setattr(
            "execution.intelligence.query_engine.build_query_response",
            lambda query, context=None: {**_MOCK_RESPONSE, "intent": "portfolio_summary"},
        )
        response = client.post(
            "/api/v1/intelligence/query",
            json={"query": "zzz unknown gibberish"},
            auth=auth,
        )
        assert response.status_code == 200
        assert response.json()["intent"] == "portfolio_summary"

    def test_missing_query_field_returns_422(self, client: TestClient, auth: tuple[str, str]) -> None:
        """Request body without 'query' field should return 422 Unprocessable Entity."""
        response = client.post(
            "/api/v1/intelligence/query",
            json={"context": {"product": "x"}},
            auth=auth,
        )
        assert response.status_code == 422

    def test_engine_value_error_returns_404(
        self, client: TestClient, auth: tuple[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ValueError from engine propagates as 404."""

        def raise_value_error(query: str, context: dict | None = None) -> dict:
            raise ValueError("No historical data found.")

        monkeypatch.setattr(
            "execution.intelligence.query_engine.build_query_response",
            raise_value_error,
        )
        response = client.post(
            "/api/v1/intelligence/query",
            json={"query": "overview"},
            auth=auth,
        )
        assert response.status_code == 404

    def test_engine_unexpected_error_returns_500(
        self, client: TestClient, auth: tuple[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unexpected engine error propagates as 500."""

        def raise_runtime_error(query: str, context: dict | None = None) -> dict:
            raise RuntimeError("Unexpected failure")

        monkeypatch.setattr(
            "execution.intelligence.query_engine.build_query_response",
            raise_runtime_error,
        )
        response = client.post(
            "/api/v1/intelligence/query",
            json={"query": "overview"},
            auth=auth,
        )
        assert response.status_code == 500
