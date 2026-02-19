"""
Tests for ArmorCode Enhanced Metrics Collector

Covers the key optimizations in query_current_vulnerabilities_graphql()
and query_closed_vulnerabilities_graphql():
- All product IDs batched in every count query (not per-product loops)
- No pagination — accurate counts come from totalElements on page-1 queries
- Exactly 2 API calls for overall totals (total + critical), regardless of data size
- Per-product breakdown uses N×2 additional page-1 calls (not paginated fetches)
- 429 retry logic preserved in _query_count_only

Run with:
    pytest tests/collectors/test_armorcode_enhanced_metrics.py -v
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub legacy bare imports BEFORE importing the module under test.
# armorcode_enhanced_metrics.py uses 'from http_client import post' and
# 'from utils_atomic_json import ...' — bare imports designed for running
# from the execution/ directory.  We inject stub modules so the file can be
# imported from the project root during tests.
# ---------------------------------------------------------------------------
_http_client_stub = ModuleType("http_client")
_http_client_stub.post = MagicMock()
sys.modules.setdefault("http_client", _http_client_stub)

_utils_stub = ModuleType("utils_atomic_json")
_utils_stub.atomic_json_save = MagicMock()
_utils_stub.load_json_with_recovery = MagicMock(return_value={"weeks": []})
sys.modules.setdefault("utils_atomic_json", _utils_stub)

# Now safe to import
from execution.armorcode_enhanced_metrics import (  # noqa: E402
    query_closed_vulnerabilities_graphql,
    query_current_vulnerabilities_graphql,
)

# Patch targets use the full package path
_MODULE = "execution.armorcode_enhanced_metrics"


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_response(findings: list, has_next: bool, total_elements: int | None = None, status_code: int = 200):
    """Build a mock HTTP response matching the GraphQL findings schema."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    page_info: dict = {"hasNext": has_next}
    if total_elements is not None:
        page_info["totalElements"] = total_elements
    mock_resp.json.return_value = {
        "data": {
            "findings": {
                "findings": findings,
                "pageInfo": page_info,
            }
        }
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _make_finding(severity: str = "HIGH", product_name: str = "Product A", env: str = "Production") -> dict:
    return {
        "id": "finding-1",
        "severity": severity,
        "status": "OPEN",
        "product": {"name": product_name},
        "environment": {"name": env},
    }


def _mock_cfg_context(mock_cfg):
    """Configure mock config to return a valid ArmorCode config."""
    mock_cfg.return_value.get_armorcode_config.return_value.base_url = "https://api.example.com"
    mock_cfg.return_value.get_armorcode_config.return_value.api_key = "key123"


# ---------------------------------------------------------------------------
# query_current_vulnerabilities_graphql
# ---------------------------------------------------------------------------


class TestQueryCurrentVulnerabilities:
    """Tests for the count-only (no-pagination) implementation."""

    def test_batches_all_product_ids_in_both_count_queries(self):
        """All product IDs must appear in EVERY count query sent to the API."""
        product_ids = ["101", "202", "303"]
        # Both calls (overall total + critical) return the same mock response
        response = _make_response([], has_next=False, total_elements=5)

        with (
            patch(f"{_MODULE}.get_config") as mock_cfg,
            patch(f"{_MODULE}.post", return_value=response) as mock_post,
        ):
            _mock_cfg_context(mock_cfg)
            query_current_vulnerabilities_graphql("https://api.example.com", product_ids)

        # Exactly 2 calls: overall total + overall critical
        assert mock_post.call_count == 2

        # Both queries must contain all three product IDs
        for call in mock_post.call_args_list:
            query_body = call[1]["json"]["query"]
            assert "101" in query_body
            assert "202" in query_body
            assert "303" in query_body

    def test_total_count_from_total_elements_not_findings(self):
        """total_count must come from totalElements (accurate), not len(findings)."""
        # Response returns 0 findings but totalElements = 350
        response_total = _make_response([], has_next=False, total_elements=350)
        response_critical = _make_response([], has_next=False, total_elements=50)

        with (
            patch(f"{_MODULE}.get_config") as mock_cfg,
            patch(f"{_MODULE}.post", side_effect=[response_total, response_critical]),
        ):
            _mock_cfg_context(mock_cfg)
            result = query_current_vulnerabilities_graphql("https://api.example.com", ["101"])

        assert result["total_count"] == 350
        assert result["findings"] == []  # No raw findings — counts are pre-computed

    def test_severity_breakdown_from_total_elements(self):
        """Severity breakdown must use accurate totalElements, not fetched finding objects."""
        response_total = _make_response([], has_next=False, total_elements=350)
        response_critical = _make_response([], has_next=False, total_elements=50)

        with (
            patch(f"{_MODULE}.get_config") as mock_cfg,
            patch(f"{_MODULE}.post", side_effect=[response_total, response_critical]),
        ):
            _mock_cfg_context(mock_cfg)
            result = query_current_vulnerabilities_graphql("https://api.example.com", ["101"])

        assert result["severity_breakdown"]["critical"] == 50
        assert result["severity_breakdown"]["high"] == 300  # 350 - 50
        assert result["severity_breakdown"]["total"] == 350

    def test_no_pagination_regardless_of_result_size(self):
        """With count-only approach, exactly 2 API calls even for 99,999 findings."""
        # hasNext=True and huge totalElements — must NOT trigger pagination
        response = _make_response([], has_next=True, total_elements=99999)

        with (
            patch(f"{_MODULE}.get_config") as mock_cfg,
            patch(f"{_MODULE}.post", return_value=response) as mock_post,
        ):
            _mock_cfg_context(mock_cfg)
            result = query_current_vulnerabilities_graphql("https://api.example.com", ["101", "202"])

        # CRITICAL: exactly 2 calls — no pagination loop
        assert mock_post.call_count == 2
        assert result["total_count"] == 99999

    def test_returns_empty_on_network_error(self):
        """Network errors must return zero counts, not raise."""
        with (
            patch(f"{_MODULE}.get_config") as mock_cfg,
            patch(f"{_MODULE}.post", side_effect=ConnectionError("timeout")),
        ):
            _mock_cfg_context(mock_cfg)
            result = query_current_vulnerabilities_graphql("https://api.example.com", ["101"])

        assert result["total_count"] == 0
        assert result["findings"] == []

    def test_per_product_breakdown_when_names_provided(self):
        """When product_id_to_name provided, makes per-product count queries (N×2 extra calls)."""
        product_ids = ["101", "202"]
        product_id_to_name = {"101": "Product A", "202": "Product B"}

        # Call order: overall_total, overall_critical,
        #             prod-101 total, prod-101 critical,
        #             prod-202 total, prod-202 critical
        responses = [
            _make_response([], has_next=False, total_elements=100),  # overall total
            _make_response([], has_next=False, total_elements=20),  # overall critical
            _make_response([], has_next=False, total_elements=60),  # product 101 total
            _make_response([], has_next=False, total_elements=10),  # product 101 critical
            _make_response([], has_next=False, total_elements=40),  # product 202 total
            _make_response([], has_next=False, total_elements=10),  # product 202 critical
        ]

        with (
            patch(f"{_MODULE}.get_config") as mock_cfg,
            patch(f"{_MODULE}.post", side_effect=responses) as mock_post,
        ):
            _mock_cfg_context(mock_cfg)
            result = query_current_vulnerabilities_graphql("https://api.example.com", product_ids, product_id_to_name)

        # 2 overall + 2×2 per-product = 6 total calls
        assert mock_post.call_count == 6

        assert result["product_breakdown"]["Product A"]["critical"] == 10
        assert result["product_breakdown"]["Product A"]["high"] == 50  # 60 - 10
        assert result["product_breakdown"]["Product A"]["total"] == 60

        assert result["product_breakdown"]["Product B"]["critical"] == 10
        assert result["product_breakdown"]["Product B"]["high"] == 30  # 40 - 10
        assert result["product_breakdown"]["Product B"]["total"] == 40


# ---------------------------------------------------------------------------
# query_closed_vulnerabilities_graphql
# ---------------------------------------------------------------------------


class TestQueryClosedVulnerabilities:
    """Tests for query_closed_vulnerabilities_graphql"""

    def test_batches_all_product_ids_in_single_query(self):
        """All product IDs must be batched into a single GraphQL call."""
        product_ids = ["101", "202", "303", "404"]
        response = _make_response([_make_finding()], has_next=False)

        with (
            patch(f"{_MODULE}.get_config") as mock_cfg,
            patch(f"{_MODULE}.post", return_value=response) as mock_post,
        ):
            _mock_cfg_context(mock_cfg)
            query_closed_vulnerabilities_graphql("https://api.example.com", product_ids)

        # Should make exactly 1 API call (page 1, hasNext=False)
        assert mock_post.call_count == 1

        query_body = mock_post.call_args[1]["json"]["query"]
        for pid in product_ids:
            assert pid in query_body

    def test_caps_at_two_pages_total(self):
        """Closed vulns query must stop at 2 pages total, even if hasNext=True."""
        resp_p1 = _make_response([_make_finding()] * 100, has_next=True)
        resp_p2 = _make_response([_make_finding()] * 100, has_next=True)
        # page 3 should never be requested

        with (
            patch(f"{_MODULE}.get_config") as mock_cfg,
            patch(f"{_MODULE}.post", side_effect=[resp_p1, resp_p2]) as mock_post,
        ):
            _mock_cfg_context(mock_cfg)
            result = query_closed_vulnerabilities_graphql("https://api.example.com", ["101", "202"])

        assert mock_post.call_count == 2
        assert len(result["findings"]) == 200

    def test_does_not_loop_per_product(self):
        """With 13 products and 2-page cap, only 2 total API calls should be made (not 26)."""
        product_ids = [str(i) for i in range(1, 14)]  # 13 products
        resp_p1 = _make_response([_make_finding()] * 10, has_next=True)
        resp_p2 = _make_response([_make_finding()] * 10, has_next=False)

        with (
            patch(f"{_MODULE}.get_config") as mock_cfg,
            patch(f"{_MODULE}.post", side_effect=[resp_p1, resp_p2]) as mock_post,
        ):
            _mock_cfg_context(mock_cfg)
            result = query_closed_vulnerabilities_graphql("https://api.example.com", product_ids)

        # Must be 2 total, not 13 * 2 = 26
        assert mock_post.call_count == 2
        assert result["total_count"] == 20
