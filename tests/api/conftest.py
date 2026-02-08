"""
API Test Configuration

Provides fixtures for API testing including authentication mocking.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_api_auth_config():
    """
    Auto-use fixture to mock API authentication configuration for all API tests.

    Provides test credentials:
    - username: admin
    - password: changeme
    """
    # Create mock auth config
    mock_auth = MagicMock()
    mock_auth.username = "admin"
    mock_auth.password = "changeme"

    # Create mock config
    mock_config = MagicMock()
    mock_config.get_api_auth_config.return_value = mock_auth

    # Patch the get_config function where it's imported
    with patch("execution.secure_config.get_config", return_value=mock_config):
        yield


@pytest.fixture(autouse=True)
def mock_env_vars():
    """
    Auto-use fixture to set required environment variables for API tests.
    """
    env_vars = {
        "API_USERNAME": "admin",
        "API_PASSWORD": "changeme",
    }

    with patch.dict(os.environ, env_vars, clear=False):
        yield
