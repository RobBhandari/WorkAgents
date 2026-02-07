"""
API Middleware - Rate Limiting, Request Tracking, Cache Control

Middleware for FastAPI application to handle:
- Rate limiting (prevent abuse)
- Request ID tracking (for debugging)
- Cache-Control headers (client-side caching)
"""

import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from execution.core import get_logger

logger = get_logger(__name__)


# ============================================================
# Rate Limiting Middleware
# ============================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent API abuse.

    Implements a simple sliding window rate limiter per IP address.

    Configuration:
        - requests_per_minute: Maximum requests per minute per IP
        - requests_per_hour: Maximum requests per hour per IP
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

        # Track requests: {ip: [(timestamp, count), ...]}
        self.request_counts: dict[str, list[tuple[datetime, int]]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""

        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Check rate limits
        is_allowed, reason = self._check_rate_limit(client_ip)

        if not is_allowed:
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "ip": client_ip,
                    "path": request.url.path,
                    "reason": reason
                }
            )

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": f"Rate limit exceeded: {reason}",
                    "retry_after": 60  # seconds
                },
                headers={"Retry-After": "60"}
            )

        # Record request
        self._record_request(client_ip)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = self._get_remaining_requests(client_ip)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response

    def _check_rate_limit(self, client_ip: str) -> tuple[bool, str]:
        """
        Check if client has exceeded rate limits.

        Returns:
            Tuple of (is_allowed, reason)
        """
        now = datetime.now()
        requests = self.request_counts[client_ip]

        # Clean old entries
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)

        requests_last_minute = sum(
            count for timestamp, count in requests
            if timestamp >= minute_ago
        )

        requests_last_hour = sum(
            count for timestamp, count in requests
            if timestamp >= hour_ago
        )

        # Check limits
        if requests_last_minute >= self.requests_per_minute:
            return False, f"{self.requests_per_minute} requests per minute exceeded"

        if requests_last_hour >= self.requests_per_hour:
            return False, f"{self.requests_per_hour} requests per hour exceeded"

        return True, ""

    def _record_request(self, client_ip: str) -> None:
        """Record a request for rate limiting."""
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)

        # Clean old entries (keep last hour only)
        self.request_counts[client_ip] = [
            (timestamp, count)
            for timestamp, count in self.request_counts[client_ip]
            if timestamp >= hour_ago
        ]

        # Add new request
        self.request_counts[client_ip].append((now, 1))

    def _get_remaining_requests(self, client_ip: str) -> int:
        """Get remaining requests for client in current minute."""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)

        requests_last_minute = sum(
            count for timestamp, count in self.request_counts[client_ip]
            if timestamp >= minute_ago
        )

        return max(0, self.requests_per_minute - requests_last_minute)


# ============================================================
# Request ID Middleware
# ============================================================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Add unique request ID to each request for tracing and debugging.

    Adds X-Request-ID header to both request and response.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add request ID to request and response."""

        # Generate or use existing request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Add to request state for access in endpoints
        request.state.request_id = request_id

        # Log request
        logger.info(
            "API request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown"
            }
        )

        # Process request
        start_time = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000

        # Add request ID to response
        response.headers["X-Request-ID"] = request_id

        # Log response
        logger.info(
            "API response",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2)
            }
        )

        return response


# ============================================================
# Cache Control Middleware
# ============================================================

class CacheControlMiddleware(BaseHTTPMiddleware):
    """
    Add Cache-Control headers for client-side caching.

    Different cache strategies for different endpoint types:
    - /health: 1 minute cache
    - /api/v1/metrics/*/latest: 1 hour cache (data refreshes daily)
    - /api/v1/metrics/*/history: 1 hour cache
    - /api/v1/dashboards/list: 10 minutes cache
    - /docs, /redoc: 1 day cache (static docs)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add Cache-Control headers based on endpoint."""

        response = await call_next(request)

        # Only add cache headers for successful GET requests
        if request.method != "GET" or response.status_code >= 400:
            return response

        path = request.url.path

        # Health check: 1 minute cache
        if path == "/health":
            response.headers["Cache-Control"] = "public, max-age=60"
            response.headers["Expires"] = self._get_expires_header(60)

        # Latest metrics: 1 hour cache (data updates once daily at 6am)
        elif "/metrics/" in path and "/latest" in path:
            response.headers["Cache-Control"] = "public, max-age=3600"
            response.headers["Expires"] = self._get_expires_header(3600)

        # Historical metrics: 1 hour cache
        elif "/metrics/" in path and "/history" in path:
            response.headers["Cache-Control"] = "public, max-age=3600"
            response.headers["Expires"] = self._get_expires_header(3600)

        # Dashboard list: 10 minutes cache
        elif "/dashboards/list" in path:
            response.headers["Cache-Control"] = "public, max-age=600"
            response.headers["Expires"] = self._get_expires_header(600)

        # API docs: 1 day cache (static content)
        elif path in ["/docs", "/redoc", "/openapi.json"]:
            response.headers["Cache-Control"] = "public, max-age=86400"
            response.headers["Expires"] = self._get_expires_header(86400)

        # ML predictions: 30 minutes cache
        elif "/predictions/" in path:
            response.headers["Cache-Control"] = "public, max-age=1800"
            response.headers["Expires"] = self._get_expires_header(1800)

        # Default: No cache for unknown endpoints
        else:
            response.headers["Cache-Control"] = "no-cache, must-revalidate"

        return response

    def _get_expires_header(self, seconds: int) -> str:
        """Generate Expires header value."""
        expires_time = datetime.utcnow() + timedelta(seconds=seconds)
        return expires_time.strftime("%a, %d %b %Y %H:%M:%S GMT")


# ============================================================
# CORS Middleware (Optional)
# ============================================================

def add_cors_middleware(app):
    """
    Add CORS middleware for cross-origin requests.

    Call this if you need to enable CORS for browser-based clients.

    Example:
        from fastapi.middleware.cors import CORSMiddleware
        add_cors_middleware(app)
    """
    try:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        logger.info("CORS middleware enabled")
    except ImportError:
        logger.warning("CORSMiddleware not available, skipping CORS setup")
