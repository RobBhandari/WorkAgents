"""
API Error and Auth Path Tests

Covers uncovered lines in execution/api/app.py:
- Lines 76, 81: startup/shutdown event handlers
- Lines 105-107: ConfigurationError in verify_credentials
- Line 159: health check with missing data files
- Lines 203-205: quality metrics unexpected exception
- Lines 293-295: security metrics unexpected exception
- Lines 319-323: product security metrics success path
- Lines 369-375: flow metrics error paths
- Lines 407-417: predictions success logging
- Lines 497-515: executive trends error paths
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

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


# ============================================================
# Startup / Shutdown Events (lines 76, 81)
# ============================================================


class TestLifecycleEvents:
    """Test startup and shutdown event handlers fire without error."""

    def test_startup_event_fires(self):
        """App startup event should log without error."""
        app = create_app()
        with TestClient(app):
            pass  # startup fires on enter, shutdown on exit


# ============================================================
# Auth ConfigurationError (lines 105-107)
# ============================================================


class TestAuthConfigError:
    """Test that misconfigured auth returns 500."""

    def test_missing_auth_config_returns_500(self, client):
        """When get_config() raises ConfigurationError, return 500."""
        from execution.secure_config import ConfigurationError

        with patch(
            "execution.secure_config.get_config",
            side_effect=ConfigurationError("API_USERNAME not set"),
        ):
            response = client.get("/api/v1/metrics/quality/latest", auth=("admin", "changeme"))
            assert response.status_code == 500
            assert "not configured" in response.json()["detail"]


# ============================================================
# Health Check - missing data files (line 159)
# ============================================================


class TestHealthCheckDataFreshness:
    """Test health endpoint with missing data files."""

    def test_health_missing_data_files_reports_degraded(self, client):
        """Health check should report degraded when data files are missing."""
        # Use a non-existent observatory dir so all file_path.exists() → False
        with patch(
            "execution.api.app.Path",
            side_effect=lambda p: Path("nonexistent_dir_abc123") if "observatory" in p else Path(p),
        ):
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            for name in ("quality", "security", "flow"):
                assert data["data_freshness"][name]["error"] == "File not found"


# ============================================================
# Quality Metrics - unexpected exception (lines 203-205)
# ============================================================


class TestQualityMetricsErrors:
    """Test quality metrics error paths."""

    def test_quality_latest_unexpected_error_returns_500(self, client, auth):
        """Unexpected exception in quality loader returns 500."""
        with patch(
            "execution.collectors.ado_quality_loader.ADOQualityLoader.load_latest_metrics",
            side_effect=RuntimeError("disk I/O error"),
        ):
            response = client.get("/api/v1/metrics/quality/latest", auth=auth)
            assert response.status_code == 500
            assert "Failed to load metrics" in response.json()["detail"]


# ============================================================
# Security Metrics - unexpected exception (lines 293-295)
# ============================================================


class TestSecurityMetricsErrors:
    """Test security metrics error paths."""

    def test_security_latest_unexpected_error_returns_500(self, client, auth):
        """Unexpected exception in security loader returns 500."""
        with patch(
            "execution.collectors.armorcode_loader.ArmorCodeLoader.load_latest_metrics",
            side_effect=RuntimeError("connection reset"),
        ):
            response = client.get("/api/v1/metrics/security/latest", auth=auth)
            assert response.status_code == 500
            assert "Failed to load metrics" in response.json()["detail"]


# ============================================================
# Product Security Metrics (lines 319-323)
# ============================================================


class TestProductSecurityMetrics:
    """Test product security metrics success and error paths."""

    def test_product_security_success(self, client, auth):
        """Product security endpoint returns metrics for a known product."""
        mock_metrics = MagicMock()
        mock_metrics.timestamp.isoformat.return_value = "2026-03-15T00:00:00"
        mock_metrics.total_vulnerabilities = 42
        mock_metrics.critical = 5
        mock_metrics.high = 10

        with patch(
            "execution.collectors.armorcode_loader.ArmorCodeLoader.load_latest_metrics",
            return_value={"TestProduct": mock_metrics},
        ):
            response = client.get("/api/v1/metrics/security/product/TestProduct", auth=auth)
            assert response.status_code == 200
            data = response.json()
            assert data["product"] == "TestProduct"
            assert data["critical"] == 5


# ============================================================
# Flow Metrics - error paths (lines 369-375)
# ============================================================


class TestFlowMetricsErrors:
    """Test flow metrics error paths."""

    def test_flow_latest_file_not_found_returns_404(self, client, auth):
        """Missing flow data returns 404."""
        with patch(
            "execution.collectors.ado_flow_loader.ADOFlowLoader.load_latest_metrics",
            side_effect=FileNotFoundError("flow_metrics_latest.json not found"),
        ):
            response = client.get("/api/v1/metrics/flow/latest", auth=auth)
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_flow_latest_unexpected_error_returns_500(self, client, auth):
        """Unexpected exception in flow loader returns 500."""
        with patch(
            "execution.collectors.ado_flow_loader.ADOFlowLoader.load_latest_metrics",
            side_effect=RuntimeError("unexpected"),
        ):
            response = client.get("/api/v1/metrics/flow/latest", auth=auth)
            assert response.status_code == 500
            assert "Failed to load metrics" in response.json()["detail"]


# ============================================================
# Predictions - success + error paths (lines 407-417)
# ============================================================


class TestPredictionEndpoint:
    """Test quality predictions endpoint."""

    def test_predictions_success(self, client, auth):
        """Successful prediction returns 200 with expected fields."""
        mock_pred = MagicMock()
        mock_pred.week_offset = 1
        mock_pred.predicted_count = 15
        mock_pred.lower_bound = 10
        mock_pred.upper_bound = 20
        mock_pred.is_anomaly_expected = False

        mock_analysis = MagicMock()
        mock_analysis.project_key = "TestProject"
        mock_analysis.current_count = 12
        mock_analysis.trend_direction = "stable"
        mock_analysis.model_r2_score = 0.85
        mock_analysis.prediction_date = "2026-03-15"
        mock_analysis.predictions = [mock_pred]
        mock_analysis.anomalies_detected = 0

        with patch(
            "execution.ml.TrendPredictor.predict_trends",
            return_value=mock_analysis,
        ):
            response = client.get("/api/v1/predictions/quality/TestProject?weeks_ahead=2", auth=auth)
            assert response.status_code == 200
            data = response.json()
            assert data["project_key"] == "TestProject"
            assert data["trend_direction"] == "stable"

    def test_predictions_invalid_weeks_ahead(self, client, auth):
        """weeks_ahead out of range returns 400."""
        response = client.get("/api/v1/predictions/quality/TestProject?weeks_ahead=10", auth=auth)
        assert response.status_code == 400

    def test_predictions_project_not_found(self, client, auth):
        """ValueError with 'No data found' returns 404."""
        with patch(
            "execution.ml.TrendPredictor.predict_trends",
            side_effect=ValueError("No data found for project FakeProject"),
        ):
            response = client.get("/api/v1/predictions/quality/FakeProject", auth=auth)
            assert response.status_code == 404

    def test_predictions_insufficient_data(self, client, auth):
        """ValueError with 'Insufficient data' returns 400."""
        with patch(
            "execution.ml.TrendPredictor.predict_trends",
            side_effect=ValueError("Insufficient data for prediction"),
        ):
            response = client.get("/api/v1/predictions/quality/TestProject", auth=auth)
            assert response.status_code == 400


# ============================================================
# Executive Trends - error paths (lines 497-515)
# ============================================================


class TestExecutiveTrendsErrors:
    """Test executive trends endpoint error paths."""

    def test_executive_trends_no_data_returns_404(self, client, auth):
        """ValueError from pipeline returns 404."""
        with patch(
            "execution.dashboards.trends.pipeline.build_trends_context",
            side_effect=ValueError("No history files found"),
        ):
            response = client.get("/api/v1/dashboards/executive-trends", auth=auth)
            assert response.status_code == 404
            assert "No historical data" in response.json()["detail"]

    def test_executive_trends_unexpected_error_returns_500(self, client, auth):
        """Unexpected exception from pipeline returns 500."""
        with patch(
            "execution.dashboards.trends.pipeline.build_trends_context",
            side_effect=RuntimeError("corrupted JSON"),
        ):
            response = client.get("/api/v1/dashboards/executive-trends", auth=auth)
            assert response.status_code == 500
            assert "Failed to load" in response.json()["detail"]

    def test_executive_trends_success(self, client, auth):
        """Successful trends endpoint returns metrics, alerts, timestamp."""
        mock_context = {
            "metrics": [{"id": "m1", "title": "Test", "current": 5}],
            "active_alerts": [],
            "timestamp": "2026-03-15T00:00:00",
        }
        with patch(
            "execution.dashboards.trends.pipeline.build_trends_context",
            return_value=mock_context,
        ):
            response = client.get("/api/v1/dashboards/executive-trends", auth=auth)
            assert response.status_code == 200
            data = response.json()
            assert "metrics" in data
            assert "alerts" in data
            assert "timestamp" in data
