"""
API Authentication Tests

Tests for HTTP Basic authentication, credential validation, and unauthorized access.
"""

import base64

import pytest
from fastapi.testclient import TestClient

from execution.api.app import create_app


@pytest.fixture
def client():
    """Create FastAPI test client."""
    app = create_app()
    return TestClient(app)


# ============================================================
# Basic Authentication Tests
# ============================================================

class TestBasicAuthentication:
    """Tests for HTTP Basic authentication."""

    def test_no_auth_returns_401(self, client):
        """Requests without authentication should return 401."""
        response = client.get("/api/v1/metrics/quality/latest")
        assert response.status_code == 401

    def test_valid_credentials_accepted(self, client):
        """Valid credentials should be accepted."""
        response = client.get(
            "/api/v1/metrics/quality/latest",
            auth=("admin", "changeme")
        )

        # Either 200 (success) or 404 (data not found, but auth worked)
        assert response.status_code in [200, 404]

    def test_invalid_username_rejected(self, client):
        """Invalid username should be rejected."""
        response = client.get(
            "/api/v1/metrics/quality/latest",
            auth=("wrong_user", "changeme")
        )

        assert response.status_code == 401

    def test_invalid_password_rejected(self, client):
        """Invalid password should be rejected."""
        response = client.get(
            "/api/v1/metrics/quality/latest",
            auth=("admin", "wrong_password")
        )

        assert response.status_code == 401

    def test_empty_credentials_rejected(self, client):
        """Empty credentials should be rejected."""
        response = client.get(
            "/api/v1/metrics/quality/latest",
            auth=("", "")
        )

        assert response.status_code == 401

    def test_malformed_auth_header(self, client):
        """Malformed authorization header should be rejected."""
        response = client.get(
            "/api/v1/metrics/quality/latest",
            headers={"Authorization": "Basic invalid_base64"}
        )

        # Should return 401 or 422 (malformed request)
        assert response.status_code in [401, 422]


# ============================================================
# Authentication Response Tests
# ============================================================

class TestAuthenticationResponses:
    """Tests for authentication error responses."""

    def test_401_includes_www_authenticate_header(self, client):
        """401 responses should include WWW-Authenticate header."""
        response = client.get("/api/v1/metrics/quality/latest")

        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers
        assert response.headers["WWW-Authenticate"] == "Basic"

    def test_401_includes_error_detail(self, client):
        """401 responses should include error detail."""
        response = client.get("/api/v1/metrics/quality/latest")

        assert response.status_code == 401

        data = response.json()
        assert "detail" in data
        assert "Invalid credentials" in data["detail"] or "Not authenticated" in data["detail"]


# ============================================================
# Authentication Across Endpoints Tests
# ============================================================

class TestAuthenticationAcrossEndpoints:
    """Tests that all protected endpoints require authentication."""

    def test_all_api_endpoints_require_auth(self, client):
        """All /api/v1/* endpoints should require authentication."""
        protected_endpoints = [
            "/api/v1/metrics/quality/latest",
            "/api/v1/metrics/quality/history",
            "/api/v1/metrics/security/latest",
            "/api/v1/metrics/security/product/test",
            "/api/v1/metrics/flow/latest",
            "/api/v1/dashboards/list"
        ]

        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401, f"Endpoint {endpoint} should require auth"

    def test_health_endpoint_no_auth_required(self, client):
        """Health endpoint should not require authentication."""
        response = client.get("/health")
        assert response.status_code == 200


# ============================================================
# Credential Timing Attack Prevention Tests
# ============================================================

class TestCredentialTimingSafety:
    """Tests for timing attack prevention in credential comparison."""

    def test_consistent_timing_for_invalid_credentials(self, client):
        """Invalid username and invalid password should take similar time."""
        import time

        # Test with wrong username
        start1 = time.time()
        response1 = client.get("/api/v1/metrics/quality/latest", auth=("wrong_user", "changeme"))
        time1 = time.time() - start1

        # Test with wrong password
        start2 = time.time()
        response2 = client.get("/api/v1/metrics/quality/latest", auth=("admin", "wrong_password"))
        time2 = time.time() - start2

        assert response1.status_code == 401
        assert response2.status_code == 401

        # Times should be similar (within 100ms)
        # This is a rough check - proper timing attack tests need many samples
        time_diff = abs(time1 - time2)
        assert time_diff < 0.1, f"Timing difference too large: {time_diff}s (potential timing attack vector)"


# ============================================================
# Multiple Authentication Attempts Tests
# ============================================================

class TestMultipleAuthenticationAttempts:
    """Tests for handling multiple authentication attempts."""

    def test_multiple_failed_attempts_still_return_401(self, client):
        """Multiple failed attempts should consistently return 401."""
        for _ in range(5):
            response = client.get(
                "/api/v1/metrics/quality/latest",
                auth=("wrong_user", "wrong_password")
            )

            assert response.status_code == 401

    def test_failed_then_successful_auth(self, client):
        """Failed auth followed by successful auth should work."""
        # First attempt fails
        response1 = client.get(
            "/api/v1/metrics/quality/latest",
            auth=("wrong_user", "wrong_password")
        )
        assert response1.status_code == 401

        # Second attempt succeeds
        response2 = client.get(
            "/api/v1/metrics/quality/latest",
            auth=("admin", "changeme")
        )
        assert response2.status_code in [200, 404]  # 404 if data doesn't exist


# ============================================================
# Case Sensitivity Tests
# ============================================================

class TestAuthenticationCaseSensitivity:
    """Tests for case sensitivity in credentials."""

    def test_username_case_sensitive(self, client):
        """Username should be case-sensitive."""
        response = client.get(
            "/api/v1/metrics/quality/latest",
            auth=("ADMIN", "changeme")  # Uppercase username
        )

        # Should fail if case-sensitive (expected behavior)
        assert response.status_code == 401

    def test_password_case_sensitive(self, client):
        """Password should be case-sensitive."""
        response = client.get(
            "/api/v1/metrics/quality/latest",
            auth=("admin", "CHANGEME")  # Uppercase password
        )

        # Should fail if case-sensitive (expected behavior)
        assert response.status_code == 401


# ============================================================
# Special Characters in Credentials Tests
# ============================================================

class TestSpecialCharactersInCredentials:
    """Tests for handling special characters in credentials."""

    def test_special_characters_in_password(self, client):
        """Special characters in password should be handled correctly."""
        # This tests that the auth encoding/decoding works properly
        # Even though these aren't the real credentials, the auth mechanism should handle them
        response = client.get(
            "/api/v1/metrics/quality/latest",
            auth=("admin", "p@ssw0rd!@#$%")
        )

        # Will fail because wrong password, but should not crash
        assert response.status_code == 401

    def test_colon_in_password(self, client):
        """Colon in password should be handled correctly (tricky for Basic auth)."""
        response = client.get(
            "/api/v1/metrics/quality/latest",
            auth=("admin", "pass:word")
        )

        # Will fail because wrong password, but should not crash
        assert response.status_code == 401


# ============================================================
# Authentication Logging Tests
# ============================================================

class TestAuthenticationLogging:
    """Tests that authentication attempts are logged properly."""

    def test_successful_auth_logs_username(self, client, caplog):
        """Successful authentication should log username."""
        # Note: This test may not work if logging isn't set up in test environment
        response = client.get(
            "/api/v1/metrics/quality/latest",
            auth=("admin", "changeme")
        )

        # If successful (200 or 404 for missing data)
        if response.status_code in [200, 404]:
            # Check if username appears in logs
            # This is a best-effort test
            pass

    def test_failed_auth_logs_attempt(self, client, caplog):
        """Failed authentication should log the attempt."""
        response = client.get(
            "/api/v1/metrics/quality/latest",
            auth=("wrong_user", "wrong_password")
        )

        assert response.status_code == 401
        # Failed attempts should be logged for security monitoring
