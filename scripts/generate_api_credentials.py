#!/usr/bin/env python3
"""
Generate Secure API Credentials

Generates cryptographically secure random credentials for API authentication.
Use this script to create strong credentials for the REST API in your .env file.

Usage:
    python scripts/generate_api_credentials.py

Output:
    Prints environment variable assignments ready to copy to .env file

Security:
    - Uses Python's secrets module (cryptographically secure RNG)
    - Username: 8-character random hex suffix
    - Password: 32-character URL-safe base64 string (192 bits of entropy)
"""

import secrets
import sys


def generate_credentials() -> tuple[str, str]:
    """
    Generate cryptographically secure API credentials.

    Returns:
        Tuple of (username, password)
    """
    username = f"api_user_{secrets.token_hex(4)}"  # e.g., api_user_a1b2c3d4
    password = secrets.token_urlsafe(32)  # 32 bytes = 256 bits, base64-encoded

    return username, password


def main():
    """Generate and display secure API credentials."""
    print("=" * 70)
    print("Secure API Credentials Generator")
    print("=" * 70)
    print()
    print("Generating cryptographically secure credentials...")
    print()

    username, password = generate_credentials()

    print("✅ Credentials generated successfully!")
    print()
    print("Copy the following lines to your .env file:")
    print("-" * 70)
    print(f"API_USERNAME={username}")
    print(f"API_PASSWORD={password}")
    print("-" * 70)
    print()
    print("⚠️  SECURITY REMINDERS:")
    print("  • Keep these credentials secret - do NOT commit .env to git")
    print("  • Rotate credentials regularly (at least annually)")
    print("  • Use different credentials for dev/staging/production")
    print("  • If credentials are compromised, regenerate immediately")
    print()
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
