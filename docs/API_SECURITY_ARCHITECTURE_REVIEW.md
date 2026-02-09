# API Security & Architecture Review
**Date:** 2026-02-09
**Scope:** `execution/api/` - FastAPI REST API

## Executive Summary

This document identifies security vulnerabilities, architecture weaknesses, and reliability concerns in the Engineering Metrics REST API. Each issue is rated by severity and includes actionable remediation steps.

---

## 🔴 Critical Issues (Immediate Action Required)

### 1. **Thread Safety - Rate Limiter Race Conditions**

**Severity:** 🔴 Critical
**Risk:** Data corruption, incorrect rate limiting
**Current Code:**
```python
# Line 47-51: Shared mutable state without locks
self.request_counts: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
self._request_counter = 0
```

**Problem:**
- FastAPI is async - multiple requests can modify `request_counts` simultaneously
- Race condition: Two requests from same IP could both pass rate limit
- Counter increment is not atomic

**Impact:**
- Rate limiter can be bypassed
- Data corruption in `request_counts`
- Unpredictable behavior under load

**Remediation:**
```python
import asyncio
from collections import defaultdict

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, ...):
        super().__init__(app)
        self.request_counts: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
        self._lock = asyncio.Lock()  # ✅ Add async lock
        self._request_counter = 0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"

        async with self._lock:  # ✅ Protect shared state
            is_allowed, reason = self._check_rate_limit(client_ip)

            if not is_allowed:
                return JSONResponse(...)

            self._record_request(client_ip)

        response = await call_next(request)
        return response
```

**Priority:** 🔴 **Fix before production deployment**

---

### 2. **IP Spoofing - Proxy Header Manipulation**

**Severity:** 🔴 Critical
**Risk:** Rate limit bypass, attribution evasion
**Current Code:**
```python
# Line 61: Trusts direct connection IP only
client_ip = request.client.host if request.client else "unknown"
```

**Problem:**
- Does not check `X-Forwarded-For`, `X-Real-IP` headers
- If behind reverse proxy (nginx, load balancer), all requests appear to come from proxy IP
- Attacker can bypass rate limits by routing through multiple proxies

**Impact:**
- Single attacker can make unlimited requests by changing proxies
- All legitimate users behind same proxy share one rate limit
- No way to track actual client IP in production

**Remediation:**
```python
def _get_client_ip(self, request: Request) -> str:
    """
    Extract client IP, checking proxy headers in trusted environments.

    Security: Only trust X-Forwarded-For if behind known proxy.
    """
    # Check if behind trusted proxy (configure based on deployment)
    if self._trust_proxy:
        # Get first IP in X-Forwarded-For chain (original client)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Fallback to X-Real-IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

    # Default: direct connection IP
    return request.client.host if request.client else "unknown"
```

**Configuration:**
```python
# In production config
TRUST_PROXY = True  # Set to True when behind nginx/ALB
TRUSTED_PROXY_IPS = ["10.0.0.0/8", "172.16.0.0/12"]  # Private network
```

**Priority:** 🔴 **Required for production behind proxy**

---

### 3. **CORS Misconfiguration - Overly Permissive**

**Severity:** 🔴 Critical
**Risk:** CSRF, data theft, XSS amplification
**Current Code:**
```python
# Line 275: Allows ALL origins
allow_origins=["*"]
```

**Problem:**
- `allow_origins=["*"]` allows any website to call your API
- Combined with `allow_credentials=True`, this is a security vulnerability
- CSRF attacks possible if session cookies used

**Impact:**
- Malicious website can make API calls on behalf of authenticated users
- Sensitive data exposed to untrusted origins
- Violates Same-Origin Policy

**Remediation:**
```python
# ❌ NEVER IN PRODUCTION
allow_origins=["*"]

# ✅ Whitelist specific origins
allow_origins=[
    "https://yourdomain.com",
    "https://app.yourdomain.com",
    "https://staging.yourdomain.com",
]

# ✅ Or use environment variable
import os
ALLOWED_ORIGINS = os.getenv("API_ALLOWED_ORIGINS", "").split(",")
```

**Priority:** 🔴 **Change before enabling CORS in production**

---

## 🟠 High Priority Issues

### 4. **Basic Auth Credentials - Insufficient Security**

**Severity:** 🟠 High
**Risk:** Credential theft, unauthorized access
**Current State:**
- HTTP Basic Authentication
- Credentials sent in every request (Base64 encoded, not encrypted)
- No session management
- No token expiration

**Recommendation:** Migrate to modern authentication:
```python
# Option 1: OAuth2 with JWT tokens
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Validate credentials
    # Return JWT token with expiration
    return {"access_token": jwt_token, "token_type": "bearer"}

# Option 2: API Keys
@app.post("/api-keys")
async def create_api_key(current_user: User = Depends(get_current_user)):
    # Generate API key with expiration
    api_key = secrets.token_urlsafe(32)
    # Store hashed key in database
    return {"api_key": api_key, "expires_at": expires}
```

**Benefits:**
- Tokens can be revoked
- Short-lived credentials (expire after N hours)
- No password sent with every request
- Support for refresh tokens

---

### 5. **No Request Size Limits - DoS Vector**

**Severity:** 🟠 High
**Risk:** Memory exhaustion, DoS
**Current State:**
- No max request body size configured
- Attacker can send GB-sized requests
- Memory allocated per request

**Remediation:**
```python
# In app configuration
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

app = FastAPI()

@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Reject requests larger than 10MB."""
    MAX_SIZE = 10 * 1024 * 1024  # 10MB

    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_SIZE:
        return JSONResponse(
            status_code=413,
            content={"detail": "Request body too large (max 10MB)"}
        )

    return await call_next(request)
```

---

### 6. **No Rate Limit State Persistence**

**Severity:** 🟠 High
**Risk:** Rate limit bypass via service restart
**Current State:**
- Rate limit state stored in memory
- Lost on restart/deploy
- Attacker can abuse by forcing restarts

**Impact:**
- Rate limits reset every deploy
- No protection across multiple API instances
- Cannot track long-term abuse patterns

**Remediation:** Use Redis for shared state
```python
import redis.asyncio as redis

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_url: str = "redis://localhost:6379"):
        super().__init__(app)
        self.redis = redis.from_url(redis_url, decode_responses=True)

    async def _check_rate_limit(self, client_ip: str) -> tuple[bool, str]:
        """Check rate limit using Redis."""
        key = f"rate_limit:{client_ip}"

        # Use Redis sorted sets for time-based expiry
        now = datetime.now().timestamp()
        hour_ago = now - 3600

        # Remove old entries
        await self.redis.zremrangebyscore(key, "-inf", hour_ago)

        # Count requests in last hour
        count = await self.redis.zcard(key)

        if count >= self.requests_per_hour:
            return False, "Rate limit exceeded"

        # Record new request
        await self.redis.zadd(key, {str(now): now})
        await self.redis.expire(key, 3600)

        return True, ""
```

**Benefits:**
- Persistent across restarts
- Shared across multiple API instances
- Redis handles cleanup automatically

---

## 🟡 Medium Priority Issues

### 7. **No Monitoring/Metrics**

**Severity:** 🟡 Medium
**Current State:**
- No metrics on rate limit hits
- No visibility into abuse patterns
- Cannot detect attacks in real-time

**Remediation:** Add Prometheus metrics
```python
from prometheus_client import Counter, Histogram

rate_limit_hits = Counter(
    "api_rate_limit_hits_total",
    "Number of requests blocked by rate limiter",
    ["ip", "reason"]
)

request_duration = Histogram(
    "api_request_duration_seconds",
    "API request duration",
    ["method", "path", "status"]
)

@middleware
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    request_duration.labels(
        method=request.method,
        path=request.url.path,
        status=response.status_code
    ).observe(duration)

    return response
```

---

### 8. **Error Messages Leak Implementation Details**

**Severity:** 🟡 Medium
**Risk:** Information disclosure
**Example:**
```python
# Line 67: Exposes exact rate limit values
return JSONResponse(
    content={"detail": f"Rate limit exceeded: {reason}", "retry_after": 60}
)
```

**Remediation:**
```python
# ✅ Generic error for production
if not is_production():
    detail = f"Rate limit exceeded: {reason}"  # Detailed for dev
else:
    detail = "Too many requests. Please try again later."  # Generic for prod
```

---

### 9. **No Input Validation on Query Parameters**

**Severity:** 🟡 Medium
**Example:** `/api/v1/metrics/quality/history?weeks=999999`

**Remediation:**
```python
from pydantic import BaseModel, Field

class HistoryQuery(BaseModel):
    weeks: int = Field(default=4, ge=1, le=52, description="Number of weeks (1-52)")

@app.get("/api/v1/metrics/quality/history")
async def get_history(query: HistoryQuery = Depends()):
    # Query params automatically validated
    ...
```

---

### 10. **Deprecated FastAPI Patterns**

**Severity:** 🟡 Medium
**Issue:** `@app.on_event("startup")` is deprecated

**Remediation:**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("API starting up...")
    yield
    # Shutdown
    logger.info("API shutting down...")

app = FastAPI(lifespan=lifespan)
```

---

## 🟢 Low Priority (Future Improvements)

### 11. **Rate Limiter Granularity**
- Add per-endpoint rate limits (stricter for expensive operations)
- Add per-user rate limits (after auth)
- Implement tiered rate limits (free vs paid users)

### 12. **Request Replay Protection**
- Add nonce/timestamp validation
- Prevent replay attacks on sensitive endpoints

### 13. **API Versioning**
- Currently `/api/v1/...` but no version negotiation
- Add support for multiple API versions

---

## Recommended Test Additions

```python
# tests/api/test_security.py

def test_rate_limiter_thread_safety():
    """Test concurrent requests don't cause race conditions."""
    import asyncio
    middleware = RateLimitMiddleware(app)

    async def make_request(ip):
        return middleware._check_rate_limit(ip)

    # Make 10 concurrent requests from same IP
    results = await asyncio.gather(*[make_request("same_ip") for _ in range(10)])

    # Only first 5 should pass (if limit is 5)
    passed = sum(1 for allowed, _ in results if allowed)
    assert passed == 5  # Not 6-10 due to race condition

def test_ip_spoofing_prevention():
    """Test that X-Forwarded-For is handled correctly."""
    # Test with spoofed header
    # Verify correct IP is extracted

def test_request_size_limit():
    """Test that large requests are rejected."""
    large_body = "x" * (11 * 1024 * 1024)  # 11MB
    response = client.post("/endpoint", content=large_body)
    assert response.status_code == 413
```

---

## Summary & Priorities

| Issue | Severity | Priority | Effort | Impact |
|-------|----------|----------|--------|--------|
| Thread safety | 🔴 Critical | P0 | Medium | High |
| IP spoofing | 🔴 Critical | P0 | Low | High |
| CORS config | 🔴 Critical | P0 | Low | High |
| Basic Auth → OAuth2 | 🟠 High | P1 | High | Medium |
| Request size limits | 🟠 High | P1 | Low | Medium |
| Redis persistence | 🟠 High | P2 | High | Medium |
| Monitoring/metrics | 🟡 Medium | P2 | Medium | Low |
| Error messages | 🟡 Medium | P3 | Low | Low |
| Input validation | 🟡 Medium | P3 | Medium | Low |

---

## Action Plan

**Week 1:**
- [ ] Add `asyncio.Lock` for thread safety
- [ ] Fix IP extraction for proxy environments
- [ ] Configure CORS whitelist

**Week 2:**
- [ ] Add request size limits
- [ ] Implement monitoring/metrics
- [ ] Add security tests

**Month 2:**
- [ ] Migrate to OAuth2/JWT
- [ ] Add Redis for rate limit persistence
- [ ] Implement per-endpoint rate limits

---

*Review conducted by: Claude Sonnet 4.5*
*Next review due: Q2 2026*
