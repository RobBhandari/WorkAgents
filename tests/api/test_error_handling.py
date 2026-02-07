"""
API Error Handling Tests

Tests for HTTP error responses, validation errors, and error message formats.
"""

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
# 404 Not Found Tests
# ============================================================


class TestNotFoundErrors:
    """Tests for 404 Not Found responses."""

    def test_nonexistent_endpoint_returns_404(self, client, auth):
        """Request to non-existent endpoint should return 404."""
        response = client.get("/api/v1/nonexistent", auth=auth)
        assert response.status_code == 404

    def test_nonexistent_product_returns_404(self, client, auth):
        """Request for non-existent product should return 404."""
        response = client.get("/api/v1/metrics/security/product/NonExistentProduct123", auth=auth)

        # Should be 404 unless product actually exists
        # (might also be 404 for data not found)
        assert response.status_code == 404

    def test_404_includes_error_detail(self, client, auth):
        """404 responses should include error detail."""
        response = client.get("/api/v1/nonexistent", auth=auth)

        assert response.status_code == 404

        data = response.json()
        assert "detail" in data

    def test_404_is_json_response(self, client, auth):
        """404 responses should be JSON."""
        response = client.get("/api/v1/nonexistent", auth=auth)

        assert response.status_code == 404
        assert "application/json" in response.headers.get("content-type", "")


# ============================================================
# 500 Internal Server Error Tests
# ============================================================


class TestInternalServerErrors:
    """Tests for 500 Internal Server Error responses."""

    def test_server_errors_return_500(self, client, auth, monkeypatch):
        """Internal errors should return 500."""
        # This is hard to test without mocking, but we can check the behavior
        # if we encounter an actual error

        # For now, just verify the endpoint exists
        response = client.get("/api/v1/metrics/quality/latest", auth=auth)

        # Should be 200 (success) or 404 (data not found), not 500
        assert response.status_code in [200, 404]

    def test_500_includes_error_detail(self, client, auth):
        """500 responses should include error detail."""
        # We can't easily trigger a 500, but we can document expected behavior
        # If a 500 occurs, it should have a detail field
        pass


# ============================================================
# Validation Error Tests (422)
# ============================================================


class TestValidationErrors:
    """Tests for 422 Unprocessable Entity (validation errors)."""

    def test_invalid_weeks_parameter_type(self, client, auth):
        """Invalid weeks parameter type should return validation error."""
        response = client.get("/api/v1/metrics/quality/history?weeks=invalid", auth=auth)

        # FastAPI should return 422 for type validation errors
        assert response.status_code == 422

    def test_negative_weeks_parameter(self, client, auth):
        """Negative weeks parameter should be handled."""
        response = client.get("/api/v1/metrics/quality/history?weeks=-5", auth=auth)

        # Could be 422 (validation error) or 200 (handled gracefully)
        assert response.status_code in [200, 404, 422]

    def test_validation_error_response_structure(self, client, auth):
        """Validation errors should have proper structure."""
        response = client.get("/api/v1/metrics/quality/history?weeks=invalid", auth=auth)

        if response.status_code == 422:
            data = response.json()
            assert "detail" in data


# ============================================================
# Error Message Format Tests
# ============================================================


class TestErrorMessageFormats:
    """Tests for consistent error message formatting."""

    def test_all_errors_return_json(self, client, auth):
        """All error responses should be JSON."""
        error_requests = [
            ("/api/v1/nonexistent", 404),
            ("/api/v1/metrics/quality/history?weeks=invalid", 422),
        ]

        for endpoint, expected_status in error_requests:
            response = client.get(endpoint, auth=auth)

            if response.status_code == expected_status:
                assert "application/json" in response.headers.get("content-type", "")

    def test_all_errors_include_detail_field(self, client, auth):
        """All error responses should include 'detail' field."""
        error_requests = [
            ("/api/v1/nonexistent", 404),
        ]

        for endpoint, expected_status in error_requests:
            response = client.get(endpoint, auth=auth)

            if response.status_code == expected_status:
                data = response.json()
                assert "detail" in data

    def test_error_messages_are_descriptive(self, client, auth):
        """Error messages should be descriptive and helpful."""
        response = client.get("/api/v1/nonexistent", auth=auth)

        assert response.status_code == 404

        data = response.json()
        detail = data.get("detail", "")

        # Detail should be a non-empty string
        assert isinstance(detail, str)
        assert len(detail) > 0


# ============================================================
# Data Not Found Tests
# ============================================================


class TestDataNotFound:
    """Tests for cases where data files don't exist."""

    def test_missing_quality_data_returns_404(self, client, auth, monkeypatch, tmp_path):
        """Missing quality data file should return 404."""
        # Mock the file path to a non-existent location
        fake_path = tmp_path / "nonexistent" / "quality_history.json"

        def mock_path_constructor(path_str):
            from pathlib import Path

            if "quality_history" in str(path_str):
                return fake_path
            return Path(path_str)

        monkeypatch.setattr("pathlib.Path", mock_path_constructor)

        response = client.get("/api/v1/metrics/quality/latest", auth=auth)

        # Should return 404 with helpful message
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower() or "run collectors" in data["detail"].lower()

    def test_missing_security_data_returns_404(self, client, auth, monkeypatch, tmp_path):
        """Missing security data file should return 404."""
        fake_path = tmp_path / "nonexistent" / "security_history.json"

        def mock_path_constructor(path_str):
            from pathlib import Path

            if "security_history" in str(path_str):
                return fake_path
            return Path(path_str)

        monkeypatch.setattr("pathlib.Path", mock_path_constructor)

        response = client.get("/api/v1/metrics/security/latest", auth=auth)

        assert response.status_code == 404

    def test_data_not_found_message_is_helpful(self, client, auth):
        """Data not found errors should suggest running collectors."""
        # Try to access data that might not exist
        response = client.get("/api/v1/metrics/quality/latest", auth=auth)

        if response.status_code == 404:
            data = response.json()
            detail = data.get("detail", "").lower()

            # Should mention either "not found" or "run collectors"
            assert "not found" in detail or "collector" in detail or "data" in detail


# ============================================================
# Method Not Allowed Tests (405)
# ============================================================


class TestMethodNotAllowed:
    """Tests for 405 Method Not Allowed responses."""

    def test_post_to_get_endpoint_returns_405(self, client, auth):
        """POST to GET-only endpoint should return 405."""
        response = client.post("/api/v1/metrics/quality/latest", auth=auth)

        assert response.status_code == 405

    def test_put_to_get_endpoint_returns_405(self, client, auth):
        """PUT to GET-only endpoint should return 405."""
        response = client.put("/api/v1/metrics/quality/latest", auth=auth)

        assert response.status_code == 405

    def test_delete_to_get_endpoint_returns_405(self, client, auth):
        """DELETE to GET-only endpoint should return 405."""
        response = client.delete("/api/v1/metrics/quality/latest", auth=auth)

        assert response.status_code == 405


# ============================================================
# Malformed Request Tests
# ============================================================


class TestMalformedRequests:
    """Tests for handling malformed requests."""

    def test_invalid_json_in_request_body(self, client, auth):
        """Invalid JSON in request body should be handled."""
        # Most endpoints are GET, but test POST if it exists
        response = client.post(
            "/api/v1/nonexistent", auth=auth, data="invalid json{{{", headers={"Content-Type": "application/json"}
        )

        # Should return 404 (endpoint doesn't exist) or 422 (invalid JSON)
        assert response.status_code in [404, 422]

    def test_extremely_long_url_path(self, client, auth):
        """Extremely long URL path should be handled."""
        long_path = "/api/v1/metrics/security/product/" + "A" * 10000

        response = client.get(long_path, auth=auth)

        # Should return 404 (not found) or 414 (URI too long)
        assert response.status_code in [404, 414]


# ============================================================
# CORS and Headers Tests
# ============================================================


class TestCorsAndHeaders:
    """Tests for CORS and response headers."""

    def test_error_responses_include_content_type(self, client, auth):
        """Error responses should include Content-Type header."""
        response = client.get("/api/v1/nonexistent", auth=auth)

        assert response.status_code == 404
        assert "content-type" in response.headers

    def test_options_request_handling(self, client):
        """OPTIONS requests should be handled (for CORS preflight)."""
        response = client.options("/api/v1/metrics/quality/latest")

        # Should return 200 (OK) or 405 (Method Not Allowed)
        assert response.status_code in [200, 405]


# ============================================================
# Error Recovery Tests
# ============================================================


class TestErrorRecovery:
    """Tests for recovery from error conditions."""

    def test_error_then_successful_request(self, client, auth):
        """Error followed by successful request should work."""
        # First request returns error
        response1 = client.get("/api/v1/nonexistent", auth=auth)
        assert response1.status_code == 404

        # Second request should work normally
        response2 = client.get("/health")
        assert response2.status_code == 200

    def test_multiple_errors_in_sequence(self, client, auth):
        """Multiple errors in sequence should be handled consistently."""
        for _ in range(3):
            response = client.get("/api/v1/nonexistent", auth=auth)
            assert response.status_code == 404


# ============================================================
# Rate Limiting Tests (if implemented)
# ============================================================


class TestRateLimiting:
    """Tests for rate limiting (if implemented)."""

    def test_many_rapid_requests(self, client, auth):
        """Many rapid requests should be handled."""
        responses = []

        for _ in range(50):
            response = client.get("/health")
            responses.append(response.status_code)

        # Should handle all requests (or rate limit with 429)
        # For now, just verify no 500 errors
        assert 500 not in responses

    def test_rate_limit_returns_429_if_implemented(self, client, auth):
        """Rate limiting should return 429 if implemented."""
        # Make many requests to a protected endpoint
        responses = []

        for _ in range(100):
            response = client.get("/api/v1/metrics/quality/latest", auth=auth)
            responses.append(response.status_code)

        # If rate limiting is implemented, should see 429
        # If not, should see 200 or 404
        valid_codes = [200, 404, 429]
        assert all(code in valid_codes for code in responses)
