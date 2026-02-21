"""
Tests for ArmorCode Enhanced Metrics Collector

Covers the AQL-based query_current_vulnerabilities_aql() and the unchanged
query_closed_vulnerabilities_graphql():
- AQL function makes exactly 2 API calls (Critical + High) regardless of product count
- Per-product breakdown is built from AQL response dicts (product_id → count)
- Totals are summed across products from the two AQL calls
- Empty AQL responses return zero counts, not exceptions
- Closed vulns query still uses GraphQL with 2-page cap and full-product-ID batching

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
_http_client_stub.post = MagicMock()  # type: ignore[attr-defined]
sys.modules.setdefault("http_client", _http_client_stub)

_utils_stub = ModuleType("utils_atomic_json")
_utils_stub.atomic_json_save = MagicMock()  # type: ignore[attr-defined]
_utils_stub.load_json_with_recovery = MagicMock(return_value={"weeks": []})  # type: ignore[attr-defined]
sys.modules.setdefault("utils_atomic_json", _utils_stub)

# Now safe to import
from execution.armorcode_enhanced_metrics import (  # noqa: E402
    query_closed_vulnerabilities_graphql,
    query_current_vulnerabilities_aql,
)

# Patch targets use the full package path
_MODULE = "execution.armorcode_enhanced_metrics"
_LOADER_CLASS = f"{_MODULE}.ArmorCodeVulnerabilityLoader"


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
# query_current_vulnerabilities_aql
# ---------------------------------------------------------------------------


class TestQueryCurrentVulnerabilitiesAql:
    """Tests for the AQL-based Production-only count implementation."""

    def test_makes_exactly_two_aql_calls(self):
        """Must call count_by_severity_aql exactly twice — Critical then High."""
        product_id_to_name = {"101": "Product A", "202": "Product B"}
        mock_loader = MagicMock()
        mock_loader.count_by_severity_aql.side_effect = [
            {"101": 10, "202": 5},  # Critical call
            {"101": 30, "202": 20},  # High call
        ]

        with patch(_LOADER_CLASS, return_value=mock_loader):
            query_current_vulnerabilities_aql("my-hierarchy", product_id_to_name)

        assert mock_loader.count_by_severity_aql.call_count == 2
        calls = mock_loader.count_by_severity_aql.call_args_list
        assert calls[0][0][0] == "Critical"
        assert calls[1][0][0] == "High"

    def test_passes_hierarchy_and_production_environment(self):
        """hierarchy and environment='Production' must be forwarded to every AQL call."""
        product_id_to_name = {"101": "Product A"}
        mock_loader = MagicMock()
        mock_loader.count_by_severity_aql.return_value = {"101": 0}

        with patch(_LOADER_CLASS, return_value=mock_loader):
            query_current_vulnerabilities_aql("test-hierarchy-value", product_id_to_name)

        for call in mock_loader.count_by_severity_aql.call_args_list:
            assert call[0][1] == "test-hierarchy-value"
            assert call[1].get("environment") == "Production"

    def test_totals_summed_across_all_products(self):
        """total_count must be the sum of all per-product critical + high counts."""
        product_id_to_name = {"101": "Product A", "202": "Product B"}
        mock_loader = MagicMock()
        mock_loader.count_by_severity_aql.side_effect = [
            {"101": 10, "202": 5},  # Critical
            {"101": 30, "202": 20},  # High
        ]

        with patch(_LOADER_CLASS, return_value=mock_loader):
            result = query_current_vulnerabilities_aql("hier", product_id_to_name)

        assert result["total_count"] == 65  # 10+5+30+20
        assert result["severity_breakdown"]["critical"] == 15  # 10+5
        assert result["severity_breakdown"]["high"] == 50  # 30+20
        assert result["severity_breakdown"]["total"] == 65

    def test_per_product_breakdown_uses_aql_counts(self):
        """product_breakdown must reflect individual AQL counts per product."""
        product_id_to_name = {"101": "Product A", "202": "Product B"}
        mock_loader = MagicMock()
        mock_loader.count_by_severity_aql.side_effect = [
            {"101": 10, "202": 5},  # Critical
            {"101": 30, "202": 20},  # High
        ]

        with patch(_LOADER_CLASS, return_value=mock_loader):
            result = query_current_vulnerabilities_aql("hier", product_id_to_name)

        assert result["product_breakdown"]["Product A"] == {"critical": 10, "high": 30, "total": 40}
        assert result["product_breakdown"]["Product B"] == {"critical": 5, "high": 20, "total": 25}

    def test_findings_list_always_empty(self):
        """findings key must always be an empty list — no raw findings fetched."""
        mock_loader = MagicMock()
        mock_loader.count_by_severity_aql.return_value = {}

        with patch(_LOADER_CLASS, return_value=mock_loader):
            result = query_current_vulnerabilities_aql("hier", {"101": "Product A"})

        assert result["findings"] == []

    def test_product_absent_from_aql_response_counts_as_zero(self):
        """Products not present in the AQL response must contribute 0 to totals."""
        product_id_to_name = {"101": "Product A", "202": "Product B"}
        mock_loader = MagicMock()
        # Product 202 absent from both responses
        mock_loader.count_by_severity_aql.side_effect = [
            {"101": 8},  # Critical — 202 missing
            {"101": 12},  # High — 202 missing
        ]

        with patch(_LOADER_CLASS, return_value=mock_loader):
            result = query_current_vulnerabilities_aql("hier", product_id_to_name)

        assert result["product_breakdown"]["Product B"] == {"critical": 0, "high": 0, "total": 0}
        assert result["total_count"] == 20  # only Product A (8+12)

    def test_returns_zeros_when_aql_returns_empty_dict(self):
        """Empty AQL responses must return zero counts without raising exceptions."""
        mock_loader = MagicMock()
        mock_loader.count_by_severity_aql.return_value = {}

        with patch(_LOADER_CLASS, return_value=mock_loader):
            result = query_current_vulnerabilities_aql("hier", {"101": "Product A"})

        assert result["total_count"] == 0
        assert result["severity_breakdown"] == {"critical": 0, "high": 0, "total": 0}


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
