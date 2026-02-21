"""
Tests for ArmorCode Enhanced Metrics Collector

Covers the AQL-based query_current_vulnerabilities_aql():
- Makes exactly 2 API calls (Critical + High) regardless of product count
- Per-product breakdown is built from AQL response dicts (product_id → count)
- Totals are summed across products from the two AQL calls
- Empty AQL responses return zero counts, not exceptions

Run with:
    pytest tests/collectors/test_armorcode_enhanced_metrics.py -v
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub legacy bare imports BEFORE importing the module under test.
# armorcode_enhanced_metrics.py uses 'from utils_atomic_json import ...' —
# a bare import designed for running from the execution/ directory.
# We inject a stub module so the file can be imported from the project root.
# ---------------------------------------------------------------------------
_utils_stub = ModuleType("utils_atomic_json")
_utils_stub.atomic_json_save = MagicMock()  # type: ignore[attr-defined]
_utils_stub.load_json_with_recovery = MagicMock(return_value={"weeks": []})  # type: ignore[attr-defined]
sys.modules.setdefault("utils_atomic_json", _utils_stub)

# Now safe to import
from execution.armorcode_enhanced_metrics import query_current_vulnerabilities_aql  # noqa: E402

# Patch targets use the full package path
_MODULE = "execution.armorcode_enhanced_metrics"
_LOADER_CLASS = f"{_MODULE}.ArmorCodeVulnerabilityLoader"


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

        # Keys are product IDs after Phase 2 migration
        assert result["product_breakdown"]["101"] == {"critical": 10, "high": 30, "total": 40}
        assert result["product_breakdown"]["202"] == {"critical": 5, "high": 20, "total": 25}

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

        # Key is product ID "202" (Product B → "202" in product_id_to_name)
        assert result["product_breakdown"]["202"] == {"critical": 0, "high": 0, "total": 0}
        assert result["total_count"] == 20  # only Product A (8+12)

    def test_returns_zeros_when_aql_returns_empty_dict(self):
        """Empty AQL responses must return zero counts without raising exceptions."""
        mock_loader = MagicMock()
        mock_loader.count_by_severity_aql.return_value = {}

        with patch(_LOADER_CLASS, return_value=mock_loader):
            result = query_current_vulnerabilities_aql("hier", {"101": "Product A"})

        assert result["total_count"] == 0
        assert result["severity_breakdown"] == {"critical": 0, "high": 0, "total": 0}
