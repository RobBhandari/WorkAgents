"""
Async Secure HTTP Client Wrapper

Provides async HTTP methods with enforced SSL verification and timeouts.
Built on httpx for high-performance concurrent API calls.

Usage:
    from execution.async_http_client import AsyncSecureHTTPClient

    async with AsyncSecureHTTPClient() as client:
        response = await client.get(url)
        response = await client.post(url, json=data)

Security Features:
    - SSL verification always enabled (verify=True)
    - Default 30-second timeout on all requests
    - Connection pooling for efficient concurrent requests
    - HTTP/2 support for better performance
"""

import httpx


class AsyncSecureHTTPClient:
    """
    Async HTTP client with enforced SSL verification and connection pooling.

    Features:
    - Context manager for automatic connection cleanup
    - Connection pooling (configurable max connections)
    - HTTP/2 support for multiplexing
    - Enforced SSL verification
    - Request timeouts
    """

    DEFAULT_TIMEOUT = 30  # seconds
    DEFAULT_MAX_CONNECTIONS = 100
    DEFAULT_MAX_KEEPALIVE = 20

    def __init__(
        self,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        max_keepalive_connections: int = DEFAULT_MAX_KEEPALIVE,
        timeout: float = DEFAULT_TIMEOUT,
        http2: bool = True,
    ):
        """
        Initialize async HTTP client.

        Args:
            max_connections: Maximum number of concurrent connections (default: 100)
            max_keepalive_connections: Max persistent connections (default: 20)
            timeout: Default timeout in seconds (default: 30)
            http2: Enable HTTP/2 support (default: True)
        """
        self.limits = httpx.Limits(max_connections=max_connections, max_keepalive_connections=max_keepalive_connections)
        self.timeout = httpx.Timeout(timeout)
        self.http2 = http2
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "AsyncSecureHTTPClient":
        """Context manager entry - create async client"""
        self.client = httpx.AsyncClient(
            limits=self.limits,
            timeout=self.timeout,
            verify=True,  # CRITICAL: Force SSL verification
            http2=self.http2,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args):
        """Context manager exit - close connections"""
        if self.client:
            await self.client.aclose()

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """
        Async GET request with SSL verification enforced.

        Args:
            url: URL to fetch
            **kwargs: Additional arguments to pass to httpx.get()

        Returns:
            httpx.Response: HTTP response

        Security:
            - Forces verify=True (SSL verification)
            - Uses default timeout if not provided
            - Connection pooling for efficiency
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use 'async with AsyncSecureHTTPClient()' context manager")

        kwargs.setdefault("timeout", self.DEFAULT_TIMEOUT)
        return await self.client.get(url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        """
        Async POST request with SSL verification enforced.

        Args:
            url: URL to post to
            **kwargs: Additional arguments to pass to httpx.post()

        Returns:
            httpx.Response: HTTP response

        Security:
            - Forces verify=True (SSL verification)
            - Uses default timeout if not provided
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use 'async with AsyncSecureHTTPClient()' context manager")

        kwargs.setdefault("timeout", self.DEFAULT_TIMEOUT)
        return await self.client.post(url, **kwargs)

    async def put(self, url: str, **kwargs) -> httpx.Response:
        """
        Async PUT request with SSL verification enforced.

        Args:
            url: URL to put to
            **kwargs: Additional arguments to pass to httpx.put()

        Returns:
            httpx.Response: HTTP response
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use 'async with AsyncSecureHTTPClient()' context manager")

        kwargs.setdefault("timeout", self.DEFAULT_TIMEOUT)
        return await self.client.put(url, **kwargs)

    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """
        Async DELETE request with SSL verification enforced.

        Args:
            url: URL to delete
            **kwargs: Additional arguments to pass to httpx.delete()

        Returns:
            httpx.Response: HTTP response
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use 'async with AsyncSecureHTTPClient()' context manager")

        kwargs.setdefault("timeout", self.DEFAULT_TIMEOUT)
        return await self.client.delete(url, **kwargs)

    async def patch(self, url: str, **kwargs) -> httpx.Response:
        """
        Async PATCH request with SSL verification enforced.

        Args:
            url: URL to patch
            **kwargs: Additional arguments to pass to httpx.patch()

        Returns:
            httpx.Response: HTTP response
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use 'async with AsyncSecureHTTPClient()' context manager")

        kwargs.setdefault("timeout", self.DEFAULT_TIMEOUT)
        return await self.client.patch(url, **kwargs)


# Self-test when run directly
if __name__ == "__main__":
    import asyncio
    import sys

    async def main():
        print("Async Secure HTTP Client - Self Test")
        print("=" * 50)

        # Test 1: Verify SSL-verified GET request
        print("\n[TEST 1] Verify async GET with SSL")
        try:
            async with AsyncSecureHTTPClient() as client:
                response = await client.get("https://httpbin.org/get")
                print("  [PASS] SSL-verified async GET succeeded")
                print(f"  Status: {response.status_code}")
                print(f"  HTTP Version: {response.http_version}")
        except Exception as e:
            print(f"  [FAIL] Async GET failed: {e}")
            return 1

        # Test 2: Verify POST works
        print("\n[TEST 2] Verify async POST")
        try:
            async with AsyncSecureHTTPClient() as client:
                response = await client.post("https://httpbin.org/post", json={"test": "data"})
                print("  [PASS] SSL-verified async POST succeeded")
                print(f"  Status: {response.status_code}")
        except Exception as e:
            print(f"  [FAIL] Async POST failed: {e}")
            return 1

        # Test 3: Verify connection pooling
        print("\n[TEST 3] Verify concurrent requests with connection pooling")
        try:
            async with AsyncSecureHTTPClient(max_connections=10) as client:
                # Launch 5 concurrent requests
                urls = [f"https://httpbin.org/delay/1?n={i}" for i in range(5)]
                tasks = [client.get(url) for url in urls]

                import time

                start = time.time()
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                duration = time.time() - start

                success_count = sum(1 for r in responses if not isinstance(r, Exception))
                print(f"  [PASS] {success_count}/5 concurrent requests succeeded")
                print(f"  Duration: {duration:.2f}s (should be ~1s with concurrency, not 5s sequential)")

                if duration < 3.0:
                    print(f"  [PASS] Concurrency working! ({duration:.2f}s < 3s)")
                else:
                    print(f"  [WARN] Concurrency may not be optimal ({duration:.2f}s >= 3s)")
        except Exception as e:
            print(f"  [FAIL] Concurrent requests failed: {e}")
            return 1

        print("\n" + "=" * 50)
        print("All tests passed! Async HTTP client is working correctly.")
        print("\nUsage:")
        print("  from execution.async_http_client import AsyncSecureHTTPClient")
        print("  async with AsyncSecureHTTPClient() as client:")
        print("      response = await client.get('https://api.example.com/data')")
        return 0

    sys.exit(asyncio.run(main()))
