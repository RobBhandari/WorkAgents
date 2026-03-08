"""
Tests for execution/intelligence/product_risk.py

Coverage:
- severity point values (critical=3, warn=1, medium=1)
- multi-severity aggregation
- sort order (score desc, then alpha)
- zero-score exclusion
- missing/empty project_name skipped
- domain deduplication and sorting
- total_alerts counts valid only
- empty input
- response shape
- API auth, 404, 500 error handling
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from execution.api.app import create_app
from execution.intelligence.product_risk import build_product_risk_response

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _alert(
    project_name: str = "Alpha",
    severity: str = "critical",
    dashboard: str = "security",
) -> dict[str, Any]:
    return {"project_name": project_name, "severity": severity, "dashboard": dashboard}


def _mock_auth_config() -> MagicMock:
    mock_auth = MagicMock()
    mock_auth.username = "admin"
    mock_auth.password = "changeme"
    mock_config = MagicMock()
    mock_config.get_api_auth_config.return_value = mock_auth
    return mock_config


# ---------------------------------------------------------------------------
# TestSeverityScoring
# ---------------------------------------------------------------------------


class TestSeverityScoring:
    def test_critical_scores_3_points(self) -> None:
        result = build_product_risk_response([_alert(severity="critical")])
        assert result["products"][0]["score"] == 3

    def test_warn_scores_1_point(self) -> None:
        result = build_product_risk_response([_alert(severity="warn")])
        assert result["products"][0]["score"] == 1

    def test_medium_scores_1_point(self) -> None:
        result = build_product_risk_response([_alert(severity="medium")])
        assert result["products"][0]["score"] == 1

    def test_mixed_severity_aggregation(self) -> None:
        alerts = [
            _alert(severity="critical"),
            _alert(severity="warn"),
            _alert(severity="warn"),
            _alert(severity="medium"),
        ]
        result = build_product_risk_response(alerts)
        # 3 + 1 + 1 + 1 = 6
        assert result["products"][0]["score"] == 6
        assert result["products"][0]["critical"] == 1
        assert result["products"][0]["warn"] == 2
        assert result["products"][0]["medium"] == 1


# ---------------------------------------------------------------------------
# TestSorting
# ---------------------------------------------------------------------------


class TestSorting:
    def test_multiple_products_sorted_by_score_desc(self) -> None:
        alerts = [
            _alert(project_name="Low", severity="warn"),
            _alert(project_name="High", severity="critical"),
        ]
        result = build_product_risk_response(alerts)
        assert result["products"][0]["product"] == "High"
        assert result["products"][1]["product"] == "Low"

    def test_tie_breaking_alphabetical(self) -> None:
        alerts = [
            _alert(project_name="Zebra", severity="warn"),
            _alert(project_name="Alpha", severity="warn"),
        ]
        result = build_product_risk_response(alerts)
        assert result["products"][0]["product"] == "Alpha"
        assert result["products"][1]["product"] == "Zebra"


# ---------------------------------------------------------------------------
# TestFiltering
# ---------------------------------------------------------------------------


class TestFiltering:
    def test_zero_score_products_excluded(self) -> None:
        alerts = [_alert(severity="unknown_severity")]
        result = build_product_risk_response(alerts)
        assert result["products"] == []

    def test_missing_project_name_skipped(self) -> None:
        alerts: list[dict[str, Any]] = [
            {"project_name": "", "severity": "critical", "dashboard": "sec"},
            {"project_name": None, "severity": "critical", "dashboard": "sec"},
            {"severity": "critical", "dashboard": "sec"},
        ]
        result = build_product_risk_response(alerts)
        assert result["products"] == []
        assert result["total_alerts"] == 0

    def test_total_alerts_counts_valid_only(self) -> None:
        alerts = [
            _alert(project_name="A"),
            _alert(project_name=""),  # skipped
            _alert(project_name="B"),
        ]
        result = build_product_risk_response(alerts)
        assert result["total_alerts"] == 2


# ---------------------------------------------------------------------------
# TestDomains
# ---------------------------------------------------------------------------


class TestDomains:
    def test_domains_deduplicated_and_sorted(self) -> None:
        alerts = [
            _alert(dashboard="security"),
            _alert(dashboard="quality"),
            _alert(dashboard="security"),  # duplicate
        ]
        result = build_product_risk_response(alerts)
        assert result["products"][0]["domains"] == ["quality", "security"]


# ---------------------------------------------------------------------------
# TestResponseShape
# ---------------------------------------------------------------------------


class TestInputContract:
    def test_non_dict_items_in_alerts_skipped(self) -> None:
        """Alerts that are None or non-dict raise AttributeError — input contract is list[dict]."""
        # The function contract requires list[dict]. Non-dict items will raise AttributeError.
        # This test documents the assumption; the route handler's except Exception catches it.
        with pytest.raises((AttributeError, TypeError)):
            build_product_risk_response([None, "bad"])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# TestResponseShape
# ---------------------------------------------------------------------------


class TestResponseShape:
    def test_empty_alerts_returns_empty_products(self) -> None:
        result = build_product_risk_response([])
        assert result["products"] == []
        assert result["total_alerts"] == 0

    def test_response_has_required_fields(self) -> None:
        result = build_product_risk_response([_alert()])
        assert {"generated_at", "total_alerts", "products"} <= result.keys()
        assert isinstance(result["generated_at"], str)
        assert "T" in result["generated_at"]


# ---------------------------------------------------------------------------
# TestApiAuth
# ---------------------------------------------------------------------------


class TestApiAuth:
    @pytest.fixture
    def client(self) -> Generator[TestClient, None, None]:
        with patch("execution.secure_config.get_config", return_value=_mock_auth_config()):
            yield TestClient(create_app())

    def test_api_401_no_credentials(self, client: TestClient) -> None:
        response = client.get("/api/v1/intelligence/product-risk")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# TestApiErrorHandling
# ---------------------------------------------------------------------------


class TestApiErrorHandling:
    @pytest.fixture
    def client(self) -> Generator[TestClient, None, None]:
        with patch("execution.secure_config.get_config", return_value=_mock_auth_config()):
            yield TestClient(create_app())

    def test_api_404_no_history(self, client: TestClient) -> None:
        with patch(
            "execution.dashboards.trends.pipeline.build_trends_context",
            side_effect=ValueError("No data"),
        ):
            response = client.get("/api/v1/intelligence/product-risk", auth=("admin", "changeme"))
        assert response.status_code == 404

    def test_api_500_context_exception(self, client: TestClient) -> None:
        with patch(
            "execution.dashboards.trends.pipeline.build_trends_context",
            side_effect=RuntimeError("boom"),
        ):
            response = client.get("/api/v1/intelligence/product-risk", auth=("admin", "changeme"))
        assert response.status_code == 500
        assert "boom" not in response.json()["detail"]

    def test_api_500_response_builder_exception(self, client: TestClient) -> None:
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
                "execution.intelligence.product_risk.build_product_risk_response",
                side_effect=RuntimeError("internal"),
            ),
        ):
            response = client.get("/api/v1/intelligence/product-risk", auth=("admin", "changeme"))
        assert response.status_code == 500
        assert "internal" not in response.json()["detail"]
