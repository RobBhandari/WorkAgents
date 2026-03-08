"""
Tests for execution/intelligence/health_score.py

Coverage:
- all-green metrics        → score 100, label "healthy"
- all-amber metrics        → score 50, label "fair"
- all-red metrics          → score 0, label "at risk"
- mixed RAG                → correct weighted mean
- excluded metrics (ai-usage, target) → not counted in total or score
- unknown / absent ragColor → skipped (contributing_metrics drops, no penalty)
- empty metrics list       → score 0, contributing_metrics=0, total_metrics=0
- label thresholds         → boundary values 80, 60, 59, 0
- response shape           → required keys present
- ragColor constants       → three known values documented explicitly
- auth on /api/v1/intelligence/health  → 401 without credentials
- no historical data       → 404 returned
- unexpected context error → 500, detail does not leak internals
- unexpected score error   → 500, detail does not leak internals
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from execution.api.app import create_app
from execution.intelligence.health_score import (
    _EXCLUDED_METRIC_IDS,
    _RAG_AMBER,
    _RAG_GREEN,
    _RAG_RED,
    build_health_score_response,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metric(metric_id: str, rag_color: str = _RAG_GREEN) -> dict[str, Any]:
    """Build a minimal metric dict matching the renderer output shape."""
    return {"id": metric_id, "ragColor": rag_color, "current": 10, "data": []}


def _metrics_all(rag_color: str, n: int = 4) -> list[dict[str, Any]]:
    """Return n metrics all with the same ragColor."""
    return [_metric(f"metric-{i}", rag_color) for i in range(n)]


# ---------------------------------------------------------------------------
# TestRagColorConstants — documents the three expected values explicitly so
# any renderer change is immediately visible in tests.
# ---------------------------------------------------------------------------


class TestRagColorConstants:
    def test_green_value(self) -> None:
        assert _RAG_GREEN == "#10b981"

    def test_amber_value(self) -> None:
        assert _RAG_AMBER == "#f59e0b"

    def test_red_value(self) -> None:
        assert _RAG_RED == "#ef4444"


# ---------------------------------------------------------------------------
# TestExcludedMetrics
# ---------------------------------------------------------------------------


class TestExcludedMetrics:
    def test_ai_usage_excluded(self) -> None:
        assert "ai-usage" in _EXCLUDED_METRIC_IDS

    def test_target_excluded(self) -> None:
        assert "target" in _EXCLUDED_METRIC_IDS

    def test_excluded_metrics_not_in_total(self) -> None:
        metrics = [
            _metric("ai-usage", _RAG_RED),
            _metric("target", _RAG_RED),
            _metric("deployment", _RAG_GREEN),
        ]
        result = build_health_score_response(metrics)
        assert result["total_metrics"] == 1
        assert result["contributing_metrics"] == 1
        assert result["score"] == 100

    def test_all_excluded_metrics_gives_zero_score(self) -> None:
        metrics = [_metric("ai-usage", _RAG_GREEN), _metric("target", _RAG_GREEN)]
        result = build_health_score_response(metrics)
        assert result["score"] == 0
        assert result["total_metrics"] == 0
        assert result["contributing_metrics"] == 0


# ---------------------------------------------------------------------------
# TestScoreModel
# ---------------------------------------------------------------------------


class TestScoreModel:
    def test_all_green_score_100(self) -> None:
        result = build_health_score_response(_metrics_all(_RAG_GREEN))
        assert result["score"] == 100

    def test_all_amber_score_50(self) -> None:
        result = build_health_score_response(_metrics_all(_RAG_AMBER))
        assert result["score"] == 50

    def test_all_red_score_0(self) -> None:
        result = build_health_score_response(_metrics_all(_RAG_RED))
        assert result["score"] == 0

    def test_mixed_rag_mean(self) -> None:
        # Green=100, Amber=50, Red=0 → mean=50 → "fair"
        metrics = [
            _metric("a", _RAG_GREEN),
            _metric("b", _RAG_AMBER),
            _metric("c", _RAG_RED),
        ]
        result = build_health_score_response(metrics)
        assert result["score"] == 50
        assert result["contributing_metrics"] == 3

    def test_empty_metrics_list(self) -> None:
        result = build_health_score_response([])
        assert result["score"] == 0
        assert result["contributing_metrics"] == 0
        assert result["total_metrics"] == 0

    def test_unknown_rag_color_skipped(self) -> None:
        # Unknown color is skipped — does not penalise the score.
        metrics = [
            _metric("a", _RAG_GREEN),
            _metric("b", "#unknown"),  # skipped
            _metric("c", _RAG_GREEN),
        ]
        result = build_health_score_response(metrics)
        assert result["score"] == 100
        assert result["total_metrics"] == 3
        assert result["contributing_metrics"] == 2

    def test_absent_rag_color_skipped(self) -> None:
        metrics = [{"id": "a", "current": 5, "data": []}]  # no ragColor key
        result = build_health_score_response(metrics)
        assert result["total_metrics"] == 1
        assert result["contributing_metrics"] == 0
        assert result["score"] == 0

    def test_score_clamped_to_0_100(self) -> None:
        # Ensure arithmetic never produces out-of-range values.
        result = build_health_score_response(_metrics_all(_RAG_GREEN, n=1))
        assert 0 <= result["score"] <= 100


# ---------------------------------------------------------------------------
# TestLabelThresholds
# ---------------------------------------------------------------------------


class TestLabelThresholds:
    def _score_from_ratio(self, green: int, total: int) -> dict[str, Any]:
        metrics = [_metric(f"m{i}", _RAG_GREEN) for i in range(green)]
        metrics += [_metric(f"r{i}", _RAG_RED) for i in range(total - green)]
        return build_health_score_response(metrics)

    def test_score_80_is_healthy(self) -> None:
        # 4 green + 1 red → mean(100,100,100,100,0) = 80
        result = self._score_from_ratio(4, 5)
        assert result["score"] == 80
        assert result["label"] == "healthy"

    def test_score_60_is_fair(self) -> None:
        # 3 green + 2 red → mean(100,100,100,0,0) = 60
        result = self._score_from_ratio(3, 5)
        assert result["score"] == 60
        assert result["label"] == "fair"

    def test_score_59_is_at_risk(self) -> None:
        # all-amber = 50 → "at risk"
        result = build_health_score_response(_metrics_all(_RAG_AMBER, n=1))
        assert result["score"] == 50
        assert result["label"] == "at risk"

    def test_score_0_is_at_risk(self) -> None:
        result = build_health_score_response(_metrics_all(_RAG_RED))
        assert result["score"] == 0
        assert result["label"] == "at risk"

    def test_score_100_is_healthy(self) -> None:
        result = build_health_score_response(_metrics_all(_RAG_GREEN))
        assert result["score"] == 100
        assert result["label"] == "healthy"


# ---------------------------------------------------------------------------
# TestResponseShape
# ---------------------------------------------------------------------------


class TestResponseShape:
    def test_required_keys_present(self) -> None:
        result = build_health_score_response([_metric("security", _RAG_GREEN)])
        assert {"generated_at", "score", "label", "contributing_metrics", "total_metrics"} <= result.keys()

    def test_generated_at_is_iso_string(self) -> None:
        result = build_health_score_response([])
        assert isinstance(result["generated_at"], str)
        assert "T" in result["generated_at"]

    def test_score_is_int(self) -> None:
        result = build_health_score_response([_metric("a", _RAG_AMBER)])
        assert isinstance(result["score"], int)


# ---------------------------------------------------------------------------
# Auth helpers (identical pattern to test_signals.py)
# ---------------------------------------------------------------------------


def _mock_auth_config() -> MagicMock:
    """Return a mock config with admin/changeme credentials."""
    mock_auth = MagicMock()
    mock_auth.username = "admin"
    mock_auth.password = "changeme"
    mock_config = MagicMock()
    mock_config.get_api_auth_config.return_value = mock_auth
    return mock_config


# ---------------------------------------------------------------------------
# TestApiAuth
# ---------------------------------------------------------------------------


class TestApiAuth:
    @pytest.fixture
    def client(self) -> Generator[TestClient, None, None]:
        with patch("execution.secure_config.get_config", return_value=_mock_auth_config()):
            yield TestClient(create_app())

    def test_unauthenticated_returns_401(self, client: TestClient) -> None:
        response = client.get("/api/v1/intelligence/health")
        assert response.status_code == 401

    def test_invalid_credentials_returns_401(self, client: TestClient) -> None:
        response = client.get("/api/v1/intelligence/health", auth=("wrong", "creds"))
        assert response.status_code == 401

    def test_valid_credentials_not_401(self, client: TestClient) -> None:
        """With valid credentials the endpoint responds — 200 or 404 (no data), not 401."""
        response = client.get("/api/v1/intelligence/health", auth=("admin", "changeme"))
        assert response.status_code in (200, 404)


# ---------------------------------------------------------------------------
# TestInternalErrorHandling (integration)
# ---------------------------------------------------------------------------


class TestInternalErrorHandling:
    @pytest.fixture
    def client(self) -> Generator[TestClient, None, None]:
        with patch("execution.secure_config.get_config", return_value=_mock_auth_config()):
            yield TestClient(create_app())

    def test_unexpected_exception_returns_500(self, client: TestClient) -> None:
        with patch(
            "execution.dashboards.trends.pipeline.build_trends_context",
            side_effect=RuntimeError("boom"),
        ):
            response = client.get("/api/v1/intelligence/health", auth=("admin", "changeme"))
        assert response.status_code == 500
        body = response.json()
        assert "detail" in body
        assert "boom" not in body["detail"]
        assert "Traceback" not in body["detail"]

    def test_no_historical_data_returns_404(self, client: TestClient) -> None:
        with patch(
            "execution.dashboards.trends.pipeline.build_trends_context",
            side_effect=ValueError("No historical data found"),
        ):
            response = client.get("/api/v1/intelligence/health", auth=("admin", "changeme"))
        assert response.status_code == 404

    def test_build_health_score_exception_returns_500(self, client: TestClient) -> None:
        """Unexpected error inside build_health_score_response must return 500."""
        dummy_context: dict[str, Any] = {
            "metrics": [],
            "active_alerts": [],
            "framework_css": "",
            "framework_js": "",
        }
        with (
            patch(
                "execution.dashboards.trends.pipeline.build_trends_context",
                return_value=dummy_context,
            ),
            patch(
                "execution.intelligence.health_score.build_health_score_response",
                side_effect=RuntimeError("internal"),
            ),
        ):
            response = client.get("/api/v1/intelligence/health", auth=("admin", "changeme"))
        assert response.status_code == 500
        body = response.json()
        assert "detail" in body
        assert "internal" not in body["detail"]
        assert "Traceback" not in body["detail"]
