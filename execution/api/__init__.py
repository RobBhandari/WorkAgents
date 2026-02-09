"""
REST API for Engineering Metrics Platform

Provides programmatic access to metrics via HTTP endpoints.
"""

from .app import create_app

__all__ = ["create_app"]
