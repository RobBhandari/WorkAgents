#!/usr/bin/env python3
"""
Tests for ArmorCode Weekly Query collector

Verifies:
- Baseline loading from JSON files
- Product ID retrieval via GraphQL API
- Current findings fetching with pagination
- Current state query orchestration
- Progress calculation math
- Main execution flow
"""

import json
import sys
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

# Mock external modules before importing the module under test
sys.modules.setdefault("http_client", MagicMock())
sys.modules.setdefault("execution.core.secure_config", MagicMock())

from execution.collectors.armorcode_weekly_query import (
    calculate_progress,
    fetch_current_findings,
    get_product_ids,
    load_baseline,
    main,
    query_current_state,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_baseline() -> dict[str, Any]:
    """Sample baseline data for testing."""
    return {
        "baseline_date": "2025-01-15T00:00:00",
        "total_vulnerabilities": 1000,
        "reduction_goal": 0.70,
        "created_at": "2025-01-15T00:00:00",
        "target_date": "2026-01-15",
        "products": ["WebApp", "MobileApp"],
        "by_product": {
            "WebApp": {"HIGH": 400, "CRITICAL": 100, "total": 500},
            "MobileApp": {"HIGH": 300, "CRITICAL": 200, "total": 500},
        },
        "by_severity": {"HIGH": 700, "CRITICAL": 300},
    }


@pytest.fixture
def sample_current_state() -> dict[str, Any]:
    """Sample current state result."""
    return {
        "query_date": "2025-06-15T00:00:00",
        "total_vulnerabilities": 400,
        "by_product": {
            "WebApp": {"HIGH": 100, "CRITICAL": 50, "total": 150},
            "MobileApp": {"HIGH": 150, "CRITICAL": 100, "total": 250},
        },
        "summary": {
            "total_critical": 150,
            "total_high": 250,
            "products_tracked": 2,
        },
    }


@pytest.fixture
def sample_graphql_products_response() -> dict[str, Any]:
    """Sample GraphQL response for product lookup."""
    return {
        "data": {
            "products": {
                "products": [
                    {"id": "uuid-1", "name": "WebApp"},
                    {"id": "uuid-2", "name": "MobileApp"},
                    {"id": "uuid-3", "name": "OtherApp"},
                ],
                "pageInfo": {"hasNext": False},
            }
        }
    }


@pytest.fixture
def sample_graphql_findings_response() -> dict[str, Any]:
    """Sample GraphQL response for findings query."""
    return {
        "data": {
            "findings": {
                "findings": [
                    {"id": "f1", "severity": "High", "status": "OPEN"},
                    {"id": "f2", "severity": "Critical", "status": "CONFIRMED"},
                ],
                "pageInfo": {"hasNext": False, "totalElements": 2},
            }
        }
    }


# ---------------------------------------------------------------------------
# load_baseline
# ---------------------------------------------------------------------------


class TestLoadBaseline:
    """Test baseline file loading."""

    def test_load_baseline_success(self, tmp_path: Any, sample_baseline: dict) -> None:
        """Test loading a valid baseline file."""
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps(sample_baseline))

        result = load_baseline(str(baseline_file))

        assert result["total_vulnerabilities"] == 1000
        assert result["products"] == ["WebApp", "MobileApp"]

    def test_load_baseline_file_not_found(self) -> None:
        """Test FileNotFoundError for missing baseline file."""
        with pytest.raises(FileNotFoundError, match="Baseline file not found"):
            load_baseline("/nonexistent/path/baseline.json")

    def test_load_baseline_valid_content_fields(self, tmp_path: Any, sample_baseline: dict) -> None:
        """Test that all expected fields are present in loaded baseline."""
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps(sample_baseline))

        result = load_baseline(str(baseline_file))

        assert "baseline_date" in result
        assert "total_vulnerabilities" in result
        assert "by_product" in result
        assert "by_severity" in result


# ---------------------------------------------------------------------------
# get_product_ids
# ---------------------------------------------------------------------------


class TestGetProductIds:
    """Test product ID retrieval via GraphQL."""

    @patch("execution.collectors.armorcode_weekly_query.post")
    def test_get_product_ids_success(self, mock_post: Mock, sample_graphql_products_response: dict) -> None:
        """Test successful product ID lookup."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_graphql_products_response
        mock_post.return_value = mock_response

        result = get_product_ids("key", "https://ac.com", ["WebApp", "MobileApp"])

        assert len(result) == 2
        assert result[0] == {"name": "WebApp", "id": "uuid-1"}
        assert result[1] == {"name": "MobileApp", "id": "uuid-2"}

    @patch("execution.collectors.armorcode_weekly_query.post")
    def test_get_product_ids_product_not_found(self, mock_post: Mock, sample_graphql_products_response: dict) -> None:
        """Test that missing products are excluded from results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_graphql_products_response
        mock_post.return_value = mock_response

        result = get_product_ids("key", "https://ac.com", ["NonExistent"])

        assert len(result) == 0

    @patch("execution.collectors.armorcode_weekly_query.post")
    def test_get_product_ids_pagination(self, mock_post: Mock) -> None:
        """Test pagination across multiple pages of products."""
        page1_response = Mock()
        page1_response.status_code = 200
        page1_response.json.return_value = {
            "data": {
                "products": {
                    "products": [{"id": "uuid-1", "name": "WebApp"}],
                    "pageInfo": {"hasNext": True},
                }
            }
        }

        page2_response = Mock()
        page2_response.status_code = 200
        page2_response.json.return_value = {
            "data": {
                "products": {
                    "products": [{"id": "uuid-2", "name": "MobileApp"}],
                    "pageInfo": {"hasNext": False},
                }
            }
        }

        mock_post.side_effect = [page1_response, page2_response]

        result = get_product_ids("key", "https://ac.com", ["WebApp", "MobileApp"])

        assert len(result) == 2
        assert mock_post.call_count == 2

    @patch("execution.collectors.armorcode_weekly_query.post")
    def test_get_product_ids_http_error(self, mock_post: Mock) -> None:
        """Test handling of non-200 HTTP response."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        result = get_product_ids("key", "https://ac.com", ["WebApp"])

        assert len(result) == 0

    @patch("execution.collectors.armorcode_weekly_query.post")
    def test_get_product_ids_exception(self, mock_post: Mock) -> None:
        """Test handling of request exception."""
        mock_post.side_effect = ConnectionError("Network error")

        result = get_product_ids("key", "https://ac.com", ["WebApp"])

        assert len(result) == 0


# ---------------------------------------------------------------------------
# fetch_current_findings
# ---------------------------------------------------------------------------


class TestFetchCurrentFindings:
    """Test findings fetching with pagination."""

    @patch("execution.collectors.armorcode_weekly_query.post")
    def test_fetch_findings_success(self, mock_post: Mock, sample_graphql_findings_response: dict) -> None:
        """Test successful single-page findings fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_graphql_findings_response
        mock_post.return_value = mock_response

        result = fetch_current_findings("key", "https://ac.com", "uuid-1", "WebApp")

        assert len(result) == 2
        assert result[0]["id"] == "f1"

    @patch("execution.collectors.armorcode_weekly_query.post")
    def test_fetch_findings_pagination(self, mock_post: Mock) -> None:
        """Test pagination across multiple pages of findings."""
        page1 = Mock()
        page1.status_code = 200
        page1.json.return_value = {
            "data": {
                "findings": {
                    "findings": [{"id": "f1", "severity": "High", "status": "OPEN"}],
                    "pageInfo": {"hasNext": True, "totalElements": 2},
                }
            }
        }

        page2 = Mock()
        page2.status_code = 200
        page2.json.return_value = {
            "data": {
                "findings": {
                    "findings": [{"id": "f2", "severity": "Critical", "status": "CONFIRMED"}],
                    "pageInfo": {"hasNext": False, "totalElements": 2},
                }
            }
        }

        mock_post.side_effect = [page1, page2]

        result = fetch_current_findings("key", "https://ac.com", "uuid-1", "WebApp")

        assert len(result) == 2
        assert mock_post.call_count == 2

    @patch("execution.collectors.armorcode_weekly_query.post")
    def test_fetch_findings_graphql_error(self, mock_post: Mock) -> None:
        """Test handling of GraphQL errors in response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Invalid query"}],
            "data": {
                "findings": {
                    "findings": [],
                    "pageInfo": {"hasNext": False, "totalElements": 0},
                }
            },
        }
        mock_post.return_value = mock_response

        result = fetch_current_findings("key", "https://ac.com", "uuid-1", "WebApp")

        assert len(result) == 0

    @patch("execution.collectors.armorcode_weekly_query.post")
    def test_fetch_findings_http_error(self, mock_post: Mock) -> None:
        """Test handling of non-200 HTTP response."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_post.return_value = mock_response

        result = fetch_current_findings("key", "https://ac.com", "uuid-1", "WebApp")

        assert len(result) == 0

    @patch("execution.collectors.armorcode_weekly_query.post")
    def test_fetch_findings_exception(self, mock_post: Mock) -> None:
        """Test handling of request exception."""
        mock_post.side_effect = ConnectionError("Timeout")

        result = fetch_current_findings("key", "https://ac.com", "uuid-1", "WebApp")

        assert len(result) == 0

    @patch("execution.collectors.armorcode_weekly_query.post")
    def test_fetch_findings_page_limit(self, mock_post: Mock) -> None:
        """Test that page limit (100) is enforced."""
        # Return hasNext=True for every page to trigger the limit
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "findings": {
                    "findings": [{"id": "f1", "severity": "High", "status": "OPEN"}],
                    "pageInfo": {"hasNext": True, "totalElements": 10000},
                }
            }
        }
        mock_post.return_value = mock_response

        result = fetch_current_findings("key", "https://ac.com", "uuid-1", "WebApp")

        # Should stop at page 100 (page increments to 101, then page > 100 breaks)
        assert mock_post.call_count == 100


# ---------------------------------------------------------------------------
# query_current_state
# ---------------------------------------------------------------------------


class TestQueryCurrentState:
    """Test current state query orchestration."""

    @patch("execution.collectors.armorcode_weekly_query.fetch_current_findings")
    @patch("execution.collectors.armorcode_weekly_query.get_product_ids")
    @patch("execution.collectors.armorcode_weekly_query.get_config")
    def test_query_current_state_success(
        self,
        mock_get_config: Mock,
        mock_get_product_ids: Mock,
        mock_fetch_findings: Mock,
        sample_baseline: dict,
    ) -> None:
        """Test successful current state query."""
        mock_ac_config = Mock()
        mock_ac_config.api_key = "test-key"
        mock_ac_config.base_url = "https://ac.com"
        mock_get_config.return_value.get_armorcode_config.return_value = mock_ac_config

        mock_get_product_ids.return_value = [
            {"name": "WebApp", "id": "uuid-1"},
            {"name": "MobileApp", "id": "uuid-2"},
        ]

        mock_fetch_findings.side_effect = [
            [{"id": "f1", "severity": "High", "status": "OPEN"}],
            [{"id": "f2", "severity": "Critical", "status": "CONFIRMED"}],
        ]

        result = query_current_state(sample_baseline)

        assert result["total_vulnerabilities"] == 2
        assert "WebApp" in result["by_product"]
        assert "MobileApp" in result["by_product"]
        assert result["summary"]["products_tracked"] == 2

    @patch("execution.collectors.armorcode_weekly_query.get_config")
    def test_query_current_state_no_api_key(self, mock_get_config: Mock, sample_baseline: dict) -> None:
        """Test ValueError when API key is missing."""
        mock_ac_config = Mock()
        mock_ac_config.api_key = ""
        mock_ac_config.base_url = "https://ac.com"
        mock_get_config.return_value.get_armorcode_config.return_value = mock_ac_config

        with pytest.raises(ValueError, match="ARMORCODE_API_KEY not set"):
            query_current_state(sample_baseline)


# ---------------------------------------------------------------------------
# calculate_progress
# ---------------------------------------------------------------------------


class TestCalculateProgress:
    """Test progress calculation math."""

    def test_calculate_progress_normal(self, sample_baseline: dict) -> None:
        """Test progress calculation with normal values."""
        current = {"total_vulnerabilities": 400}

        result = calculate_progress(sample_baseline, current)

        assert result["baseline_total"] == 1000
        assert result["current_total"] == 400
        assert result["change"] == 600
        assert result["change_percent"] == 60.0
        assert result["reduction_goal_percent"] == 70
        assert result["target_reduction"] == 700
        assert result["target_remaining"] == 300
        assert result["progress_towards_goal"] == pytest.approx(85.7, abs=0.1)
        assert result["on_track"] is True

    def test_calculate_progress_zero_baseline(self) -> None:
        """Test progress with zero baseline total (avoid division by zero)."""
        baseline = {
            "total_vulnerabilities": 0,
            "reduction_goal": 0.70,
            "created_at": "2025-01-15T00:00:00",
            "target_date": "2026-01-15",
        }
        current = {"total_vulnerabilities": 0}

        result = calculate_progress(baseline, current)

        assert result["change_percent"] == 0
        assert result["progress_towards_goal"] == 0

    def test_calculate_progress_increase(self) -> None:
        """Test progress when vulnerabilities increased."""
        baseline = {
            "total_vulnerabilities": 100,
            "reduction_goal": 0.70,
            "created_at": "2025-01-15T00:00:00",
            "target_date": "2026-01-15",
        }
        current = {"total_vulnerabilities": 150}

        result = calculate_progress(baseline, current)

        assert result["change"] == -50
        assert result["on_track"] is False

    def test_calculate_progress_missing_created_at(self) -> None:
        """Test ValueError when created_at is missing."""
        baseline = {"total_vulnerabilities": 100, "reduction_goal": 0.70}
        current = {"total_vulnerabilities": 50}

        with pytest.raises(ValueError, match="Baseline missing 'created_at' field"):
            calculate_progress(baseline, current)

    def test_calculate_progress_no_target_date(self) -> None:
        """Test progress when target_date is empty."""
        baseline = {
            "total_vulnerabilities": 100,
            "reduction_goal": 0.70,
            "created_at": "2025-01-15T00:00:00",
        }
        current = {"total_vulnerabilities": 50}

        result = calculate_progress(baseline, current)

        assert result["days_remaining"] == 0

    def test_calculate_progress_default_reduction_goal(self) -> None:
        """Test that default reduction goal (0.70) is used when not specified."""
        baseline = {
            "total_vulnerabilities": 200,
            "created_at": "2025-01-15T00:00:00",
            "target_date": "2026-01-15",
        }
        current = {"total_vulnerabilities": 100}

        result = calculate_progress(baseline, current)

        assert result["reduction_goal_percent"] == 70


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


class TestMain:
    """Test main execution flow."""

    @patch("execution.collectors.armorcode_weekly_query.track_collector_performance")
    @patch("execution.collectors.armorcode_weekly_query.calculate_progress")
    @patch("execution.collectors.armorcode_weekly_query.query_current_state")
    @patch("execution.collectors.armorcode_weekly_query.load_baseline")
    @patch("builtins.open", new_callable=mock_open)
    def test_main_success(
        self,
        mock_file: Mock,
        mock_load_baseline: Mock,
        mock_query: Mock,
        mock_progress: Mock,
        mock_tracker: Mock,
        sample_baseline: dict,
        sample_current_state: dict,
    ) -> None:
        """Test successful main execution."""
        mock_tracker_instance = MagicMock()
        mock_tracker.return_value.__enter__ = Mock(return_value=mock_tracker_instance)
        mock_tracker.return_value.__exit__ = Mock(return_value=False)

        mock_load_baseline.return_value = sample_baseline
        mock_query.return_value = sample_current_state
        mock_progress.return_value = {"change": 600}

        result = main()

        assert result["baseline"] == sample_baseline
        assert result["current"] == sample_current_state
        assert result["progress"] == {"change": 600}
        assert "generated_at" in result
        mock_file.assert_called_once()

    @patch("execution.collectors.armorcode_weekly_query.track_collector_performance")
    @patch("execution.collectors.armorcode_weekly_query.load_baseline")
    def test_main_error_exits(self, mock_load_baseline: Mock, mock_tracker: Mock) -> None:
        """Test that main calls sys.exit(1) on error."""
        mock_tracker_instance = MagicMock()
        mock_tracker.return_value.__enter__ = Mock(return_value=mock_tracker_instance)
        mock_tracker.return_value.__exit__ = Mock(return_value=False)

        mock_load_baseline.side_effect = FileNotFoundError("No baseline")

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
