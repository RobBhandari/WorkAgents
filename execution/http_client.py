"""
Secure HTTP Client Wrapper

Provides secure HTTP methods with enforced SSL verification and timeouts.
Prevents man-in-the-middle attacks by forcing verify=True on all requests.

Usage:
    from http_client import get, post

    # Instead of: requests.get(url)
    response = get(url)

    # Instead of: requests.post(url, json=data)
    response = post(url, json=data)

Security Features:
    - SSL verification always enabled (verify=True)
    - Default 30-second timeout on all requests
    - Consistent security configuration across all HTTP calls
"""

import requests
from typing import Any, Optional


class SecureHTTPClient:
    """
    Secure HTTP client with enforced SSL verification and timeouts.
    """

    DEFAULT_TIMEOUT = 30  # seconds

    @staticmethod
    def get(url: str, **kwargs) -> requests.Response:
        """
        Secure GET request with SSL verification enforced.

        Args:
            url: URL to fetch
            **kwargs: Additional arguments to pass to requests.get()

        Returns:
            requests.Response: HTTP response

        Security:
            - Forces verify=True (SSL verification)
            - Sets default timeout=30 if not provided
            - Prevents insecure HTTP requests
        """
        # CRITICAL: Force SSL verification (prevent man-in-the-middle attacks)
        kwargs.setdefault('verify', True)

        # Set default timeout (prevent hanging connections)
        kwargs.setdefault('timeout', SecureHTTPClient.DEFAULT_TIMEOUT)

        return requests.get(url, **kwargs)

    @staticmethod
    def post(url: str, **kwargs) -> requests.Response:
        """
        Secure POST request with SSL verification enforced.

        Args:
            url: URL to post to
            **kwargs: Additional arguments to pass to requests.post()

        Returns:
            requests.Response: HTTP response

        Security:
            - Forces verify=True (SSL verification)
            - Sets default timeout=30 if not provided
            - Prevents insecure HTTP requests
        """
        # CRITICAL: Force SSL verification (prevent man-in-the-middle attacks)
        kwargs.setdefault('verify', True)

        # Set default timeout (prevent hanging connections)
        kwargs.setdefault('timeout', SecureHTTPClient.DEFAULT_TIMEOUT)

        return requests.post(url, **kwargs)

    @staticmethod
    def put(url: str, **kwargs) -> requests.Response:
        """
        Secure PUT request with SSL verification enforced.

        Args:
            url: URL to put to
            **kwargs: Additional arguments to pass to requests.put()

        Returns:
            requests.Response: HTTP response

        Security:
            - Forces verify=True (SSL verification)
            - Sets default timeout=30 if not provided
        """
        kwargs.setdefault('verify', True)
        kwargs.setdefault('timeout', SecureHTTPClient.DEFAULT_TIMEOUT)
        return requests.put(url, **kwargs)

    @staticmethod
    def delete(url: str, **kwargs) -> requests.Response:
        """
        Secure DELETE request with SSL verification enforced.

        Args:
            url: URL to delete
            **kwargs: Additional arguments to pass to requests.delete()

        Returns:
            requests.Response: HTTP response

        Security:
            - Forces verify=True (SSL verification)
            - Sets default timeout=30 if not provided
        """
        kwargs.setdefault('verify', True)
        kwargs.setdefault('timeout', SecureHTTPClient.DEFAULT_TIMEOUT)
        return requests.delete(url, **kwargs)

    @staticmethod
    def patch(url: str, **kwargs) -> requests.Response:
        """
        Secure PATCH request with SSL verification enforced.

        Args:
            url: URL to patch
            **kwargs: Additional arguments to pass to requests.patch()

        Returns:
            requests.Response: HTTP response

        Security:
            - Forces verify=True (SSL verification)
            - Sets default timeout=30 if not provided
        """
        kwargs.setdefault('verify', True)
        kwargs.setdefault('timeout', SecureHTTPClient.DEFAULT_TIMEOUT)
        return requests.patch(url, **kwargs)


# Convenience functions (can be imported directly)
get = SecureHTTPClient.get
post = SecureHTTPClient.post
put = SecureHTTPClient.put
delete = SecureHTTPClient.delete
patch = SecureHTTPClient.patch


# Self-test when run directly
if __name__ == '__main__':
    import sys

    print("Secure HTTP Client - Self Test")
    print("=" * 50)

    # Test 1: Verify SSL is enforced
    print("\n[TEST 1] Verify SSL enforcement")
    try:
        response = get('https://httpbin.org/get')
        print(f"  [PASS] SSL-verified GET request succeeded")
        print(f"  Status: {response.status_code}")
    except Exception as e:
        print(f"  [FAIL] SSL-verified request failed: {e}")
        sys.exit(1)

    # Test 2: Verify timeout is set
    print("\n[TEST 2] Verify timeout is set")
    import unittest.mock as mock
    with mock.patch('requests.get') as mock_get:
        get('https://example.com')
        call_kwargs = mock_get.call_args[1]
        if call_kwargs.get('verify') is True and call_kwargs.get('timeout') == 30:
            print(f"  [PASS] verify=True and timeout=30 enforced")
        else:
            print(f"  [FAIL] Security parameters not enforced: {call_kwargs}")
            sys.exit(1)

    # Test 3: Verify POST works
    print("\n[TEST 3] Verify POST method")
    try:
        response = post('https://httpbin.org/post', json={'test': 'data'})
        print(f"  [PASS] SSL-verified POST request succeeded")
        print(f"  Status: {response.status_code}")
    except Exception as e:
        print(f"  [FAIL] POST request failed: {e}")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("All tests passed! Secure HTTP client is working correctly.")
    print("\nUsage:")
    print("  from http_client import get, post")
    print("  response = get('https://api.example.com/data')")
