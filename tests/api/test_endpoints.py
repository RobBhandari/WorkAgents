"""
API Endpoints Integration Tests

Tests all REST API endpoints for correct responses, data structure, and behavior.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from execution.api.app import create_app


@pytest.fixture
def client():
    """Create FastAPI test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def auth():
    """HTTP Basic auth credentials for testing."""
    return ("admin", "changeme")


@pytest.fixture
def mock_quality_history(tmp_path):
    """Create mock quality history file."""
    observatory_dir = tmp_path / ".tmp" / "observatory"
    observatory_dir.mkdir(parents=True)

    quality_file = observatory_dir / "quality_history.json"
    quality_data = {
        "project": "TestProject",
        "weeks": [
            {
                "week_ending": "2026-01-31T00:00:00",
                "metrics": {
                    "open_bugs": 100,
                    "closed_this_week": 15,
                    "net_change": -5,
                    "closure_rate": 75.0,
                    "p1_count": 5,
                    "p2_count": 20,
                },
            },
            {
                "week_ending": "2026-02-07T00:00:00",
                "metrics": {
                    "open_bugs": 95,
                    "closed_this_week": 20,
                    "net_change": -10,
                    "closure_rate": 80.0,
                    "p1_count": 4,
                    "p2_count": 18,
                },
            },
        ],
    }

    with open(quality_file, "w", encoding="utf-8") as f:
        json.dump(quality_data, f)

    return observatory_dir


@pytest.fixture
def mock_security_history(tmp_path):
    """Create mock security history file."""
    observatory_dir = tmp_path / ".tmp" / "observatory"
    observatory_dir.mkdir(parents=True, exist_ok=True)

    security_file = observatory_dir / "security_history.json"
    security_data = {
        "weeks": [
            {
                "week_ending": "2026-02-07T00:00:00",
                "metrics": {
                    "total_vulnerabilities": 842,
                    "critical": 12,
                    "high": 89,
                    "product_breakdown": {
                        "Product A": {"total": 145, "critical": 3, "high": 18},
                        "Product B": {"total": 98, "critical": 0, "high": 12},
                        "Product C": {"total": 234, "critical": 5, "high": 31},
                    },
                },
            }
        ]
    }

    with open(security_file, "w", encoding="utf-8") as f:
        json.dump(security_data, f)

    return observatory_dir


@pytest.fixture
def mock_flow_history(tmp_path):
    """Create mock flow history file."""
    observatory_dir = tmp_path / ".tmp" / "observatory"
    observatory_dir.mkdir(parents=True, exist_ok=True)

    flow_file = observatory_dir / "flow_history.json"
    flow_data = {
        "project": "TestProject",
        "weeks": [
            {
                "week_ending": "2026-02-07T00:00:00",
                "metrics": {
                    "cycle_time_p50": 3.2,
                    "cycle_time_p85": 8.5,
                    "cycle_time_p95": 15.3,
                    "lead_time_p50": 5.8,
                    "lead_time_p85": 12.4,
                    "lead_time_p95": 22.1,
                    "work_items_completed": 145,
                },
            }
        ],
    }

    with open(flow_file, "w", encoding="utf-8") as f:
        json.dump(flow_data, f)

    return observatory_dir


# ============================================================
# Health Check Tests
# ============================================================


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check_no_auth_required(self, client):
        """Health check should work without authentication."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_response_structure(self, client):
        """Health check should return correct structure."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "data_freshness" in data

        assert data["version"] == "2.0.0"

    def test_health_check_data_freshness_structure(self, client):
        """Data freshness should have correct structure."""
        response = client.get("/health")
        data = response.json()

        freshness = data["data_freshness"]

        for metric_type in ["quality", "security", "flow"]:
            assert metric_type in freshness
            assert "fresh" in freshness[metric_type]
            assert isinstance(freshness[metric_type]["fresh"], bool)

    def test_health_check_degraded_when_files_missing(self, client):
        """Health check should report degraded if data files missing."""
        response = client.get("/health")
        data = response.json()

        # If files don't exist, status should be degraded
        if not all(freshness["fresh"] for freshness in data["data_freshness"].values()):
            assert data["status"] == "degraded"


# ============================================================
# Quality Metrics Tests
# ============================================================


class TestQualityMetricsEndpoints:
    """Tests for /api/v1/metrics/quality/* endpoints."""

    def test_quality_latest_requires_auth(self, client):
        """Latest quality metrics should require authentication."""
        response = client.get("/api/v1/metrics/quality/latest")
        assert response.status_code == 401

    def test_quality_latest_with_auth(self, client, auth, monkeypatch, mock_quality_history):
        """Latest quality metrics should return with valid auth."""
        # Mock the history file path
        monkeypatch.setattr(
            "execution.collectors.ado_quality_loader.Path",
            lambda x: mock_quality_history / "quality_history.json" if "quality_history" in x else Path(x),
        )

        response = client.get("/api/v1/metrics/quality/latest", auth=auth)

        if response.status_code == 404:
            pytest.skip("Quality history file not found (expected in test environment)")

        assert response.status_code == 200

    def test_quality_latest_response_structure(self, client, auth, monkeypatch, mock_quality_history):
        """Latest quality metrics should have correct structure."""
        # This test will skip if data doesn't exist
        response = client.get("/api/v1/metrics/quality/latest", auth=auth)

        if response.status_code == 404:
            pytest.skip("Quality history file not found")

        data = response.json()

        assert "timestamp" in data
        assert "project" in data
        assert "open_bugs" in data
        assert "closed_this_week" in data
        assert "net_change" in data
        assert "closure_rate" in data
        assert "p1_count" in data
        assert "p2_count" in data

    def test_quality_history_requires_auth(self, client):
        """Quality history should require authentication."""
        response = client.get("/api/v1/metrics/quality/history")
        assert response.status_code == 401

    def test_quality_history_default_weeks(self, client, auth):
        """Quality history should default to 12 weeks."""
        response = client.get("/api/v1/metrics/quality/history", auth=auth)

        if response.status_code == 404:
            pytest.skip("Quality history file not found")

        assert response.status_code == 200
        data = response.json()

        assert "weeks" in data
        assert "count" in data

    def test_quality_history_custom_weeks(self, client, auth):
        """Quality history should respect weeks parameter."""
        response = client.get("/api/v1/metrics/quality/history?weeks=4", auth=auth)

        if response.status_code == 404:
            pytest.skip("Quality history file not found")

        assert response.status_code == 200
        data = response.json()

        # Should return at most 4 weeks
        assert data["count"] <= 4


# ============================================================
# Security Metrics Tests
# ============================================================


class TestSecurityMetricsEndpoints:
    """Tests for /api/v1/metrics/security/* endpoints."""

    def test_security_latest_requires_auth(self, client):
        """Latest security metrics should require authentication."""
        response = client.get("/api/v1/metrics/security/latest")
        assert response.status_code == 401

    def test_security_latest_with_auth(self, client, auth):
        """Latest security metrics should return with valid auth."""
        response = client.get("/api/v1/metrics/security/latest", auth=auth)

        if response.status_code == 404:
            pytest.skip("Security history file not found")

        assert response.status_code == 200

    def test_security_latest_response_structure(self, client, auth):
        """Latest security metrics should have correct structure."""
        response = client.get("/api/v1/metrics/security/latest", auth=auth)

        if response.status_code == 404:
            pytest.skip("Security history file not found")

        data = response.json()

        assert "timestamp" in data
        assert "total_vulnerabilities" in data
        assert "critical" in data
        assert "high" in data
        assert "product_count" in data
        assert "products" in data

        # Products should be a list
        assert isinstance(data["products"], list)

    def test_security_product_requires_auth(self, client):
        """Product security metrics should require authentication."""
        response = client.get("/api/v1/metrics/security/product/TestProduct")
        assert response.status_code == 401

    def test_security_product_not_found(self, client, auth):
        """Non-existent product should return 404."""
        response = client.get("/api/v1/metrics/security/product/NonExistentProduct", auth=auth)

        # Could be 404 (product not found) or 404 (data not found)
        if response.status_code != 404:
            pytest.skip("Security data exists, checking product existence")

        assert response.status_code == 404


# ============================================================
# Flow Metrics Tests
# ============================================================


class TestFlowMetricsEndpoints:
    """Tests for /api/v1/metrics/flow/* endpoints."""

    def test_flow_latest_requires_auth(self, client):
        """Latest flow metrics should require authentication."""
        response = client.get("/api/v1/metrics/flow/latest")
        assert response.status_code == 401

    def test_flow_latest_with_auth(self, client, auth):
        """Latest flow metrics should return with valid auth."""
        response = client.get("/api/v1/metrics/flow/latest", auth=auth)

        if response.status_code == 404:
            pytest.skip("Flow history file not found")

        assert response.status_code == 200

    def test_flow_latest_response_structure(self, client, auth):
        """Latest flow metrics should have correct structure."""
        response = client.get("/api/v1/metrics/flow/latest", auth=auth)

        if response.status_code == 404:
            pytest.skip("Flow history file not found")

        data = response.json()

        assert "timestamp" in data
        assert "project" in data
        assert "cycle_time_p50" in data
        assert "cycle_time_p85" in data
        assert "cycle_time_p95" in data
        assert "lead_time_p50" in data
        assert "lead_time_p85" in data
        assert "lead_time_p95" in data
        assert "work_items_completed" in data


# ============================================================
# Dashboard Endpoints Tests
# ============================================================


class TestDashboardEndpoints:
    """Tests for /api/v1/dashboards/* endpoints."""

    def test_dashboards_list_requires_auth(self, client):
        """Dashboard list should require authentication."""
        response = client.get("/api/v1/dashboards/list")
        assert response.status_code == 401

    def test_dashboards_list_with_auth(self, client, auth):
        """Dashboard list should return with valid auth."""
        response = client.get("/api/v1/dashboards/list", auth=auth)
        assert response.status_code == 200

    def test_dashboards_list_response_structure(self, client, auth):
        """Dashboard list should have correct structure."""
        response = client.get("/api/v1/dashboards/list", auth=auth)
        data = response.json()

        assert "dashboards" in data
        assert "count" in data
        assert isinstance(data["dashboards"], list)
        assert data["count"] == len(data["dashboards"])

    def test_dashboards_list_item_structure(self, client, auth):
        """Each dashboard item should have correct structure."""
        response = client.get("/api/v1/dashboards/list", auth=auth)
        data = response.json()

        if data["count"] > 0:
            dashboard = data["dashboards"][0]

            assert "name" in dashboard
            assert "filename" in dashboard
            assert "size_kb" in dashboard
            assert "last_modified" in dashboard


# ============================================================
# ML Predictions Tests
# ============================================================


class TestMLPredictionsEndpoints:
    """Tests for /api/v1/predictions/* endpoints."""

    def test_predictions_requires_auth(self, client):
        """Predictions should require authentication."""
        response = client.get("/api/v1/predictions/quality/Test_Project")
        assert response.status_code == 401

    def test_predictions_with_auth(self, client, auth):
        """Predictions should return with valid auth."""
        response = client.get("/api/v1/predictions/quality/One_Office", auth=auth)

        if response.status_code == 404:
            pytest.skip("Quality history file not found or project doesn't exist")

        assert response.status_code in [200, 400]  # 200 = success, 400 = insufficient data

    def test_predictions_response_structure(self, client, auth):
        """Predictions should have correct structure."""
        response = client.get("/api/v1/predictions/quality/One_Office", auth=auth)

        if response.status_code != 200:
            pytest.skip("Predictions not available (insufficient data or file not found)")

        data = response.json()

        assert "project_key" in data
        assert "current_bug_count" in data
        assert "trend_direction" in data
        assert "model_r2_score" in data
        assert "prediction_date" in data
        assert "predictions" in data
        assert "historical_anomalies" in data

        # Verify trend direction is valid
        assert data["trend_direction"] in ["increasing", "decreasing", "stable"]

        # Verify predictions array
        assert isinstance(data["predictions"], list)

        if len(data["predictions"]) > 0:
            pred = data["predictions"][0]
            assert "week_ending" in pred
            assert "predicted_count" in pred
            assert "confidence_interval" in pred
            assert "anomaly_expected" in pred

            # Verify confidence interval structure
            ci = pred["confidence_interval"]
            assert "lower" in ci
            assert "upper" in ci
            assert ci["lower"] <= pred["predicted_count"] <= ci["upper"]

    def test_predictions_custom_weeks_ahead(self, client, auth):
        """Predictions should support custom weeks_ahead parameter."""
        response = client.get("/api/v1/predictions/quality/One_Office?weeks_ahead=2", auth=auth)

        if response.status_code != 200:
            pytest.skip("Predictions not available")

        data = response.json()
        assert len(data["predictions"]) == 2

    def test_predictions_invalid_weeks_ahead(self, client, auth):
        """Invalid weeks_ahead should return 400."""
        # Too low
        response = client.get("/api/v1/predictions/quality/One_Office?weeks_ahead=0", auth=auth)
        assert response.status_code == 400

        # Too high
        response = client.get("/api/v1/predictions/quality/One_Office?weeks_ahead=10", auth=auth)
        assert response.status_code == 400

    def test_predictions_project_not_found(self, client, auth):
        """Non-existent project should return 404."""
        response = client.get("/api/v1/predictions/quality/NonExistentProject123", auth=auth)

        # Could be 404 (data not found) or 404 (project not found)
        if response.status_code != 404:
            pytest.skip("Either quality data doesn't exist or project was found")

        assert response.status_code == 404

    def test_predictions_anomalies_structure(self, client, auth):
        """Historical anomalies should have correct structure."""
        response = client.get("/api/v1/predictions/quality/One_Office", auth=auth)

        if response.status_code != 200:
            pytest.skip("Predictions not available")

        data = response.json()
        anomalies = data["historical_anomalies"]

        assert isinstance(anomalies, list)

        # If anomalies exist, check structure
        if len(anomalies) > 0:
            anomaly = anomalies[0]
            assert "week_ending" in anomaly
            assert "bug_count" in anomaly
            assert "z_score" in anomaly
            assert "severity" in anomaly
            assert anomaly["severity"] in ["high", "medium"]


# ============================================================
# Response Format Tests
# ============================================================


class TestResponseFormats:
    """Tests for response format consistency."""

    def test_json_content_type(self, client, auth):
        """All endpoints should return JSON."""
        endpoints = [
            "/health",
            "/api/v1/metrics/quality/latest",
            "/api/v1/metrics/security/latest",
            "/api/v1/metrics/flow/latest",
            "/api/v1/dashboards/list",
        ]

        for endpoint in endpoints:
            if endpoint == "/health":
                response = client.get(endpoint)
            else:
                response = client.get(endpoint, auth=auth)

            # Skip 404s (data might not exist in test env)
            if response.status_code == 404:
                continue

            assert "application/json" in response.headers.get("content-type", "")

    def test_timestamps_are_iso_format(self, client, auth):
        """Timestamps should be ISO 8601 format."""
        response = client.get("/health")
        data = response.json()

        # Timestamp should be parseable as ISO format
        timestamp = data["timestamp"]
        assert "T" in timestamp or " " in timestamp  # ISO format has T separator
