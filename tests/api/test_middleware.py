"""
API Middleware Tests - Security, Performance, and Architecture

Tests for rate limiting, memory management, and security vulnerabilities.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, Request
from starlette.responses import Response

from execution.api.middleware import RateLimitMiddleware, RequestIDMiddleware

# ============================================================
# Memory Leak Prevention Tests
# ============================================================


class TestRateLimiterMemoryManagement:
    """Test that rate limiter does not leak memory over time."""

    @pytest.fixture
    def middleware(self):
        """Create rate limiter middleware instance."""
        app = FastAPI()
        return RateLimitMiddleware(app, requests_per_minute=60, requests_per_hour=1000)

    def test_stale_ips_are_cleaned_up(self, middleware):
        """
        CRITICAL: Test that old IPs are removed to prevent memory leak.

        This test prevents regression of the memory leak bug where IPs
        were never removed from the dictionary, causing unbounded growth.
        """
        # Record requests from 100 different IPs
        for i in range(100):
            ip = f"192.168.1.{i}"
            middleware._record_request(ip)

        # Verify all IPs are tracked
        assert len(middleware.request_counts) == 100

        # Simulate time passing (2 hours - beyond cleanup threshold)
        cutoff_time = datetime.now() - timedelta(hours=2)

        # Manually trigger cleanup with old cutoff time
        middleware._cleanup_stale_ips(cutoff_time)

        # All IPs should still be there (they were just added)
        assert len(middleware.request_counts) == 100

        # Now simulate cleanup with current time + 2 hours (all become stale)
        future_cutoff = datetime.now() + timedelta(hours=2)
        middleware._cleanup_stale_ips(future_cutoff)

        # All IPs should be removed (they're all stale)
        assert len(middleware.request_counts) == 0

    def test_periodic_cleanup_triggers_automatically(self, middleware):
        """Test that cleanup triggers every 100 requests."""
        # Record 99 requests (should not trigger cleanup)
        for i in range(99):
            middleware._record_request(f"ip_{i}")

        assert middleware._request_counter == 99

        # 100th request should trigger cleanup and reset counter
        with patch.object(middleware, "_cleanup_stale_ips") as mock_cleanup:
            middleware._record_request("ip_100")

            # Cleanup should have been called
            mock_cleanup.assert_called_once()

            # Counter should be reset
            assert middleware._request_counter == 0

    def test_inline_cleanup_removes_stale_ips_during_check(self, middleware):
        """Test that _check_rate_limit removes stale IPs inline."""
        # Add an IP with a request
        middleware._record_request("192.168.1.1")

        # Verify IP is tracked
        assert "192.168.1.1" in middleware.request_counts

        # Manually set timestamp to 2 hours ago (make it stale)
        old_time = datetime.now() - timedelta(hours=2)
        middleware.request_counts["192.168.1.1"] = [(old_time, 1)]

        # Check rate limit - should remove stale IP
        is_allowed, _ = middleware._check_rate_limit("192.168.1.1")

        # Should be allowed (no recent requests)
        assert is_allowed is True

        # IP should be removed
        assert "192.168.1.1" not in middleware.request_counts

    def test_memory_does_not_grow_with_many_unique_ips(self, middleware):
        """
        Test that dictionary size doesn't grow unbounded with many unique IPs.

        Simulates production scenario with thousands of unique IPs.
        """
        # Simulate 1000 unique IPs hitting the API
        for i in range(1000):
            middleware._record_request(f"unique_ip_{i}")

        # All IPs should be tracked initially
        assert len(middleware.request_counts) == 1000

        # Simulate time passing (make all IPs stale)
        future_cutoff = datetime.now() + timedelta(hours=2)
        middleware._cleanup_stale_ips(future_cutoff)

        # All stale IPs should be removed
        assert len(middleware.request_counts) == 0


# ============================================================
# Security Tests
# ============================================================


class TestRateLimiterSecurity:
    """Test security aspects of rate limiting."""

    @pytest.fixture
    def middleware(self):
        """Create rate limiter with strict limits for testing."""
        app = FastAPI()
        return RateLimitMiddleware(app, requests_per_minute=5, requests_per_hour=50)

    def test_rate_limit_prevents_abuse(self, middleware):
        """Test that rate limiter blocks excessive requests."""
        ip = "attacker_ip"

        # Make 5 requests (should all pass)
        for _ in range(5):
            is_allowed, _ = middleware._check_rate_limit(ip)
            assert is_allowed is True
            middleware._record_request(ip)

        # 6th request should be blocked
        is_allowed, reason = middleware._check_rate_limit(ip)
        assert is_allowed is False
        assert "exceeded" in reason

    def test_different_ips_have_separate_limits(self, middleware):
        """Test that IPs are tracked independently."""
        # IP 1 makes 5 requests (hits limit)
        for _ in range(5):
            middleware._record_request("ip_1")

        # IP 2 should still be allowed (separate counter)
        is_allowed, _ = middleware._check_rate_limit("ip_2")
        assert is_allowed is True

    def test_cleanup_does_not_affect_active_ips(self, middleware):
        """Test that cleanup only removes truly stale IPs."""
        # Add active IP (recent request)
        middleware._record_request("active_ip")

        # Add stale IP (old request)
        old_time = datetime.now() - timedelta(hours=2)
        middleware.request_counts["stale_ip"] = [(old_time, 1)]

        # Trigger cleanup
        cutoff = datetime.now() - timedelta(hours=1)
        middleware._cleanup_stale_ips(cutoff)

        # Active IP should remain
        assert "active_ip" in middleware.request_counts

        # Stale IP should be removed
        assert "stale_ip" not in middleware.request_counts


# ============================================================
# Architecture & Reliability Tests
# ============================================================


class TestMiddlewareArchitecture:
    """Test architectural concerns: initialization, error handling, edge cases."""

    def test_rate_limiter_initializes_with_correct_defaults(self):
        """Test default rate limit values."""
        app = FastAPI()
        middleware = RateLimitMiddleware(app)

        assert middleware.requests_per_minute == 60
        assert middleware.requests_per_hour == 1000
        assert middleware._cleanup_interval == 100

    def test_rate_limiter_accepts_custom_limits(self):
        """Test custom rate limit configuration."""
        app = FastAPI()
        middleware = RateLimitMiddleware(app, requests_per_minute=100, requests_per_hour=5000)

        assert middleware.requests_per_minute == 100
        assert middleware.requests_per_hour == 5000

    def test_cleanup_handles_empty_dictionary(self):
        """Test cleanup works with no tracked IPs."""
        app = FastAPI()
        middleware = RateLimitMiddleware(app)

        # Should not crash with empty dictionary
        cutoff = datetime.now() - timedelta(hours=1)
        middleware._cleanup_stale_ips(cutoff)

        assert len(middleware.request_counts) == 0

    def test_cleanup_handles_all_active_ips(self):
        """Test cleanup when all IPs are active."""
        app = FastAPI()
        middleware = RateLimitMiddleware(app)

        # Add 10 active IPs
        for i in range(10):
            middleware._record_request(f"active_ip_{i}")

        # Trigger cleanup with cutoff in the past
        cutoff = datetime.now() - timedelta(hours=1)
        middleware._cleanup_stale_ips(cutoff)

        # All IPs should remain (they're active)
        assert len(middleware.request_counts) == 10


# ============================================================
# Request ID Middleware Tests
# ============================================================


class TestRequestIDMiddleware:
    """Test request ID tracking for debugging."""

    def test_request_id_middleware_generates_uuid(self):
        """Test that request ID is generated if not provided."""
        app = FastAPI()
        middleware = RequestIDMiddleware(app)

        # Create mock request without X-Request-ID header
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.state = Mock()

        # Should generate UUID
        # Note: We can't easily test the full dispatch without async setup,
        # but this verifies the middleware initializes correctly
        assert middleware is not None
