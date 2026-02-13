"""
Tests for ADO Connection Module

Tests the shared ADO connection functionality to ensure it properly
creates connections and returns WIT clients.

Run with:
    pytest tests/collectors/test_ado_connection.py -v
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from execution.collectors.ado_connection import (
    get_ado_connection,
    get_wit_client,
)


class TestGetAdoConnection:
    """Tests for get_ado_connection() function"""

    @patch("execution.collectors.ado_connection.get_config")
    @patch("execution.collectors.ado_connection.Connection")
    @patch("execution.collectors.ado_connection.BasicAuthentication")
    def test_get_ado_connection_success(self, mock_auth, mock_connection, mock_get_config):
        """Test successful ADO connection creation"""
        # Setup mock config
        mock_ado_config = MagicMock()
        mock_ado_config.organization_url = "https://dev.azure.com/testorg"
        mock_ado_config.pat = "test_pat_token_123456789012345"

        mock_config = MagicMock()
        mock_config.get_ado_config.return_value = mock_ado_config
        mock_get_config.return_value = mock_config

        # Setup mock connection
        mock_connection_instance = MagicMock()
        mock_connection.return_value = mock_connection_instance

        # Setup mock auth
        mock_auth_instance = MagicMock()
        mock_auth.return_value = mock_auth_instance

        # Call function
        result = get_ado_connection()

        # Verify
        mock_get_config.assert_called_once()
        mock_config.get_ado_config.assert_called_once()
        mock_auth.assert_called_once_with("", "test_pat_token_123456789012345")
        mock_connection.assert_called_once_with(base_url="https://dev.azure.com/testorg", creds=mock_auth_instance)
        assert result == mock_connection_instance

    @patch("execution.collectors.ado_connection.get_config")
    def test_get_ado_connection_missing_url(self, mock_get_config):
        """Test that ValueError is raised when organization URL is missing"""
        # Setup mock config with missing URL
        mock_ado_config = MagicMock()
        mock_ado_config.organization_url = None
        mock_ado_config.pat = "test_pat_token_123456789012345"

        mock_config = MagicMock()
        mock_config.get_ado_config.return_value = mock_ado_config
        mock_get_config.return_value = mock_config

        # Verify error is raised
        with pytest.raises(ValueError, match="ADO_ORGANIZATION_URL and ADO_PAT must be set"):
            get_ado_connection()

    @patch("execution.collectors.ado_connection.get_config")
    def test_get_ado_connection_missing_pat(self, mock_get_config):
        """Test that ValueError is raised when PAT is missing"""
        # Setup mock config with missing PAT
        mock_ado_config = MagicMock()
        mock_ado_config.organization_url = "https://dev.azure.com/testorg"
        mock_ado_config.pat = None

        mock_config = MagicMock()
        mock_config.get_ado_config.return_value = mock_ado_config
        mock_get_config.return_value = mock_config

        # Verify error is raised
        with pytest.raises(ValueError, match="ADO_ORGANIZATION_URL and ADO_PAT must be set"):
            get_ado_connection()

    @patch("execution.collectors.ado_connection.get_config")
    def test_get_ado_connection_empty_values(self, mock_get_config):
        """Test that ValueError is raised when credentials are empty strings"""
        # Setup mock config with empty strings
        mock_ado_config = MagicMock()
        mock_ado_config.organization_url = ""
        mock_ado_config.pat = ""

        mock_config = MagicMock()
        mock_config.get_ado_config.return_value = mock_ado_config
        mock_get_config.return_value = mock_config

        # Verify error is raised
        with pytest.raises(ValueError, match="ADO_ORGANIZATION_URL and ADO_PAT must be set"):
            get_ado_connection()


class TestGetWitClient:
    """Tests for get_wit_client() function"""

    @patch("execution.collectors.ado_connection.get_ado_connection")
    def test_get_wit_client_without_connection(self, mock_get_ado_connection):
        """Test get_wit_client() creates connection when none provided"""
        # Setup mock connection
        mock_connection = MagicMock()
        mock_wit_client = MagicMock()
        mock_connection.clients.get_work_item_tracking_client.return_value = mock_wit_client
        mock_get_ado_connection.return_value = mock_connection

        # Call function without connection parameter
        result = get_wit_client()

        # Verify
        mock_get_ado_connection.assert_called_once()
        mock_connection.clients.get_work_item_tracking_client.assert_called_once()
        assert result == mock_wit_client

    @patch("execution.collectors.ado_connection.get_ado_connection")
    def test_get_wit_client_with_connection(self, mock_get_ado_connection):
        """Test get_wit_client() uses provided connection"""
        # Setup mock connection
        mock_connection = MagicMock()
        mock_wit_client = MagicMock()
        mock_connection.clients.get_work_item_tracking_client.return_value = mock_wit_client

        # Call function with connection parameter
        result = get_wit_client(mock_connection)

        # Verify connection was not created (existing connection used)
        mock_get_ado_connection.assert_not_called()
        mock_connection.clients.get_work_item_tracking_client.assert_called_once()
        assert result == mock_wit_client

    @patch("execution.collectors.ado_connection.get_ado_connection")
    def test_get_wit_client_with_none_connection(self, mock_get_ado_connection):
        """Test get_wit_client() creates connection when explicitly passed None"""
        # Setup mock connection
        mock_connection = MagicMock()
        mock_wit_client = MagicMock()
        mock_connection.clients.get_work_item_tracking_client.return_value = mock_wit_client
        mock_get_ado_connection.return_value = mock_connection

        # Call function with None
        result = get_wit_client(None)

        # Verify new connection was created
        mock_get_ado_connection.assert_called_once()
        mock_connection.clients.get_work_item_tracking_client.assert_called_once()
        assert result == mock_wit_client
