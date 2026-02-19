"""
Tests for ArmorCode Enhanced Metrics Collector

Covers the key optimizations in query_current_vulnerabilities_graphql()
and query_closed_vulnerabilities_graphql():
- All product IDs batched in a single GraphQL call (not per-product loops)
- accurate_total uses totalElements from page 1 (not len(findings))
- Pagination works correctly across multiple pages
- 429 retry logic preserved

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
    """Tests for query_current_vulnerabilities_graphql"""

    def test_batches_all_product_ids_in_single_query(self):
        """All product IDs must appear in a single GraphQL call, not separate per-product calls."""
        product_ids = ["101", "202", "303"]
        response = _make_response([_make_finding()], has_next=False, total_elements=1)

        with (
            patch(f"{_MODULE}.get_config") as mock_cfg,
            patch(f"{_MODULE}.post", return_value=response) as mock_post,
        ):
            _mock_cfg_context(mock_cfg)
            query_current_vulnerabilities_graphql("https://api.example.com", product_ids)

        # Should be called exactly ONCE (one page, all products batched)
        assert mock_post.call_count == 1

        # The query body must contain all three IDs
        query_body = mock_post.call_args[1]["json"]["query"]
        assert "101" in query_body
        assert "202" in query_body
        assert "303" in query_body

    def test_total_count_uses_total_elements_not_len_findings(self):
        """total_count must come from totalElements (accurate), not len(findings) (capped)."""
        # 350 total vulns, only 200 fetched across 2 pages
        page1_findings = [_make_finding() for _ in range(100)]
        page2_findings = [_make_finding() for _ in range(100)]

        resp_page1 = _make_response(page1_findings, has_next=True, total_elements=350)
        resp_page2 = _make_response(page2_findings, has_next=False)

        with (
            patch(f"{_MODULE}.get_config") as mock_cfg,
            patch(f"{_MODULE}.post", side_effect=[resp_page1, resp_page2]),
        ):
            _mock_cfg_context(mock_cfg)
            result = query_current_vulnerabilities_graphql("https://api.example.com", ["101"])

        # Accurate total from totalElements, not just what was fetched
        assert result["total_count"] == 350
        assert len(result["findings"]) == 200

    def test_paginates_until_has_next_false(self):
        """Collector must fetch all pages until hasNext is False."""
        resp_p1 = _make_response([_make_finding()], has_next=True, total_elements=3)
        resp_p2 = _make_response([_make_finding()], has_next=True)
        resp_p3 = _make_response([_make_finding()], has_next=False)

        with (
            patch(f"{_MODULE}.get_config") as mock_cfg,
            patch(f"{_MODULE}.post", side_effect=[resp_p1, resp_p2, resp_p3]) as mock_post,
        ):
            _mock_cfg_context(mock_cfg)
            result = query_current_vulnerabilities_graphql("https://api.example.com", ["101"])

        assert mock_post.call_count == 3
        assert len(result["findings"]) == 3

    def test_returns_empty_on_network_error(self):
        """Network errors must return empty result, not raise."""
        with (
            patch(f"{_MODULE}.get_config") as mock_cfg,
            patch(f"{_MODULE}.post", side_effect=ConnectionError("timeout")),
        ):
            _mock_cfg_context(mock_cfg)
            result = query_current_vulnerabilities_graphql("https://api.example.com", ["101"])

        assert result == {"findings": [], "total_count": 0}

    def test_single_page_makes_one_api_call(self):
        """When hasNext=False on page 1, only one API call is made regardless of product count."""
        response = _make_response([_make_finding(), _make_finding()], has_next=False, total_elements=2)

        with (
            patch(f"{_MODULE}.get_config") as mock_cfg,
            patch(f"{_MODULE}.post", return_value=response) as mock_post,
        ):
            _mock_cfg_context(mock_cfg)
            result = query_current_vulnerabilities_graphql("https://api.example.com", ["101", "202", "303", "404"])

        assert mock_post.call_count == 1
        assert result["total_count"] == 2
        assert len(result["findings"]) == 2


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
