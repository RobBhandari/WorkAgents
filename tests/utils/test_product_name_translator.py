"""
Tests for product name translation utilities.

This test suite validates the shared translation logic used by both
genericization and de-genericization scripts. These tests would have
caught the dictionary key translation bug that occurred in production.
"""

import json
import pytest
from pathlib import Path
from typing import Dict
from unittest.mock import Mock, patch, mock_open

from execution.utils.product_name_translator import (
    translate_value,
    translate_history_file,
    load_mapping_file,
    _check_unmapped_generics,
    _anonymize_emails,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def forward_mapping() -> Dict[str, str]:
    """Forward mapping: real names -> generic names (for genericization)."""
    return {
        "Access Legal Case Management": "Product A",
        "Access Legal Proclaim": "Product D",
        "Access Diversity": "Product G",
        "Access Legal AI Services": "Product H",
        "Eclipse": "Product K",
    }


@pytest.fixture
def reverse_mapping() -> Dict[str, str]:
    """Reverse mapping: generic names -> real names (for de-genericization)."""
    return {
        "Product A": "Access Legal Case Management",
        "Product D": "Access Legal Proclaim",
        "Product G": "Access Diversity",
        "Product H": "Access Legal AI Services",
        "Product K": "Eclipse",
    }


@pytest.fixture
def sample_history_data() -> dict:
    """Sample history JSON structure with products in multiple locations."""
    return {
        "weeks": [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "metrics": {
                    "total": 100,
                    "product_breakdown": {
                        "Product G": {"count": 25, "status": "Good"},
                        "Product H": {"count": 30, "status": "Good"},
                        "Product K": {"count": 45, "status": "Action Needed"},
                    },
                },
            }
        ]
    }


# ============================================================================
# TEST: Dictionary Key Translation (THE BUG WE FIXED)
# ============================================================================


def test_translate_dictionary_keys_reverse(reverse_mapping):
    """
    CRITICAL TEST: Ensure dictionary KEYS are translated, not just values.

    This test would have caught the production bug where products in
    dictionary keys (like {"Product G": {...}}) were not being converted.
    """
    data = {
        "product_breakdown": {
            "Product G": {"count": 5},
            "Product H": {"count": 3},
        }
    }
    stats: Dict[str, int] = {}

    result = translate_value(data, reverse_mapping, stats, direction="reverse")

    # These assertions would have FAILED with the old buggy code
    assert "Access Diversity" in result["product_breakdown"]
    assert "Access Legal AI Services" in result["product_breakdown"]
    assert "Product G" not in result["product_breakdown"]
    assert "Product H" not in result["product_breakdown"]

    # Verify stats tracked the replacements
    assert stats["Product G"] == 1
    assert stats["Product H"] == 1


def test_translate_dictionary_keys_forward(forward_mapping):
    """Test forward translation of dictionary keys (real -> generic)."""
    data = {
        "product_breakdown": {
            "Access Diversity": {"count": 5},
            "Eclipse": {"count": 3},
        }
    }
    stats: Dict[str, int] = {}

    result = translate_value(data, forward_mapping, stats, direction="forward")

    assert "Product G" in result["product_breakdown"]
    assert "Product K" in result["product_breakdown"]
    assert "Access Diversity" not in result["product_breakdown"]
    assert "Eclipse" not in result["product_breakdown"]


# ============================================================================
# TEST: Dictionary Value Translation
# ============================================================================


def test_translate_dictionary_values(reverse_mapping):
    """Test that dictionary VALUES are translated correctly."""
    data = {
        "description": "Product G deployment",
        "product": "Product H",
    }
    stats: Dict[str, int] = {}

    result = translate_value(data, reverse_mapping, stats, direction="reverse")

    assert result["description"] == "Access Diversity deployment"
    assert result["product"] == "Access Legal AI Services"


# ============================================================================
# TEST: Nested Dictionary Translation
# ============================================================================


def test_translate_nested_dictionaries(reverse_mapping):
    """Test translation in deeply nested dictionaries (keys AND values)."""
    data = {
        "level1": {
            "Product G": {
                "level2": {
                    "description": "Product H features",
                    "Product K": {"count": 5},
                }
            }
        }
    }
    stats: Dict[str, int] = {}

    result = translate_value(data, reverse_mapping, stats, direction="reverse")

    # Check all levels were translated
    assert "Access Diversity" in result["level1"]
    assert "Product G" not in result["level1"]
    assert (
        result["level1"]["Access Diversity"]["level2"]["description"]
        == "Access Legal AI Services features"
    )
    assert "Eclipse" in result["level1"]["Access Diversity"]["level2"]


# ============================================================================
# TEST: List Translation
# ============================================================================


def test_translate_list_of_strings(reverse_mapping):
    """Test translation of product names in lists."""
    data = {"products": ["Product G", "Product H", "Product K"]}
    stats: Dict[str, int] = {}

    result = translate_value(data, reverse_mapping, stats, direction="reverse")

    assert result["products"] == [
        "Access Diversity",
        "Access Legal AI Services",
        "Eclipse",
    ]


def test_translate_list_of_dicts(reverse_mapping):
    """Test translation in list of dictionaries."""
    data = {
        "items": [
            {"name": "Product G", "count": 5},
            {"name": "Product H", "count": 3},
        ]
    }
    stats: Dict[str, int] = {}

    result = translate_value(data, reverse_mapping, stats, direction="reverse")

    assert result["items"][0]["name"] == "Access Diversity"
    assert result["items"][1]["name"] == "Access Legal AI Services"


# ============================================================================
# TEST: String Translation
# ============================================================================


def test_translate_string_multiple_occurrences(reverse_mapping):
    """Test string with multiple product name occurrences."""
    text = "Product G and Product H are using Product K"
    stats: Dict[str, int] = {}

    result = translate_value(text, reverse_mapping, stats, direction="reverse")

    assert (
        result
        == "Access Diversity and Access Legal AI Services are using Eclipse"
    )
    assert stats["Product G"] == 1
    assert stats["Product H"] == 1
    assert stats["Product K"] == 1


def test_translate_string_partial_match_avoided(forward_mapping):
    """Test that partial matches don't cause incorrect replacements."""
    # "Access Legal Case Management" should match before "Access"
    text = "Access Legal Case Management system"
    stats: Dict[str, int] = {}

    result = translate_value(text, forward_mapping, stats, direction="forward")

    # Should be "Product A system", not "ProductLegal Case Management system"
    assert result == "Product A system"


# ============================================================================
# TEST: Email Anonymization (Forward Only)
# ============================================================================


def test_anonymize_emails_forward(forward_mapping):
    """Test email anonymization during genericization."""
    text = "Created by jac.martin@theaccessgroup.com"
    stats: Dict[str, int] = {}

    result = translate_value(text, forward_mapping, stats, direction="forward")

    assert "@theaccessgroup.com" not in result
    assert "Jac Martin" in result
    assert stats.get("email_anonymized") == 1


def test_anonymize_multiple_emails_forward(forward_mapping):
    """Test multiple email anonymization."""
    text = "Authors: john.doe@theaccessgroup.com, jane.smith@theaccessgroup.com"
    stats: Dict[str, int] = {}

    result = translate_value(text, forward_mapping, stats, direction="forward")

    assert "@theaccessgroup.com" not in result
    assert "John Doe" in result
    assert "Jane Smith" in result
    assert stats.get("email_anonymized") == 2


def test_no_email_anonymization_reverse(reverse_mapping):
    """Test that reverse translation does NOT anonymize emails."""
    text = "Created by jac.martin@theaccessgroup.com"
    stats: Dict[str, int] = {}

    result = translate_value(text, reverse_mapping, stats, direction="reverse")

    # Should remain unchanged (reverse doesn't touch emails)
    assert result == text
    assert "email_anonymized" not in stats


# ============================================================================
# TEST: Fail-Loud Validation (Unmapped Generic Products)
# ============================================================================


def test_fail_loud_on_unmapped_generic_key(reverse_mapping):
    """Test fail-loud validation when unmapped generic product in key."""
    data = {
        "product_breakdown": {
            "Product Z": {"count": 5},  # Not in mapping
        }
    }
    stats: Dict[str, int] = {}

    with pytest.raises(ValueError, match="UNMAPPED GENERIC PRODUCTS FOUND"):
        translate_value(
            data, reverse_mapping, stats, direction="reverse", fail_on_unmapped=True
        )


def test_fail_loud_on_unmapped_generic_value(reverse_mapping):
    """Test fail-loud validation when unmapped generic product in value."""
    data = {"description": "Product Z deployment"}  # Not in mapping
    stats: Dict[str, int] = {}

    with pytest.raises(ValueError, match="UNMAPPED GENERIC PRODUCTS FOUND"):
        translate_value(
            data, reverse_mapping, stats, direction="reverse", fail_on_unmapped=True
        )


def test_no_fail_when_fail_on_unmapped_disabled(reverse_mapping):
    """Test that unmapped products are silently ignored when fail_on_unmapped=False."""
    data = {"description": "Product Z deployment"}
    stats: Dict[str, int] = {}

    # Should NOT raise (fail_on_unmapped=False)
    result = translate_value(
        data, reverse_mapping, stats, direction="reverse", fail_on_unmapped=False
    )

    # Product Z should remain unchanged
    assert result["description"] == "Product Z deployment"


def test_check_unmapped_generics_helper():
    """Test the _check_unmapped_generics helper function directly."""
    mapping = {"Product A": "Real A", "Product B": "Real B"}

    # Should raise for unmapped product
    with pytest.raises(ValueError, match="Product Z"):
        _check_unmapped_generics("Product Z found", mapping, "test context")

    # Should NOT raise for mapped product
    _check_unmapped_generics(
        "Product A found", mapping, "test context"
    )  # No exception


# ============================================================================
# TEST: Edge Cases
# ============================================================================


def test_translate_empty_dict(reverse_mapping):
    """Test translation of empty dictionary."""
    stats: Dict[str, int] = {}
    result = translate_value({}, reverse_mapping, stats, direction="reverse")
    assert result == {}
    assert stats == {}


def test_translate_empty_list(reverse_mapping):
    """Test translation of empty list."""
    stats: Dict[str, int] = {}
    result = translate_value([], reverse_mapping, stats, direction="reverse")
    assert result == []


def test_translate_empty_string(reverse_mapping):
    """Test translation of empty string."""
    stats: Dict[str, int] = {}
    result = translate_value("", reverse_mapping, stats, direction="reverse")
    assert result == ""


def test_translate_none_values(reverse_mapping):
    """Test translation preserves None values."""
    data = {"value": None, "count": 0}
    stats: Dict[str, int] = {}
    result = translate_value(data, reverse_mapping, stats, direction="reverse")
    assert result["value"] is None
    assert result["count"] == 0


def test_translate_numeric_values(reverse_mapping):
    """Test translation preserves numeric values."""
    data = {"count": 42, "percentage": 85.5, "active": True}
    stats: Dict[str, int] = {}
    result = translate_value(data, reverse_mapping, stats, direction="reverse")
    assert result == data  # Should be unchanged


# ============================================================================
# TEST: translate_history_file Function
# ============================================================================


def test_translate_history_file_success(reverse_mapping, sample_history_data, tmp_path):
    """Test translate_history_file successfully processes a file."""
    # Create temporary history file
    history_file = tmp_path / "test_history.json"
    history_file.write_text(json.dumps(sample_history_data))

    # Translate the file
    stats = translate_history_file(
        history_file, reverse_mapping, direction="reverse", fail_on_unmapped=False
    )

    # Verify file was modified
    result_data = json.loads(history_file.read_text())

    # Check that product names in keys were translated
    product_breakdown = result_data["weeks"][0]["metrics"]["product_breakdown"]
    assert "Access Diversity" in product_breakdown
    assert "Access Legal AI Services" in product_breakdown
    assert "Eclipse" in product_breakdown
    assert "Product G" not in product_breakdown

    # Check stats
    assert stats["Product G"] == 1
    assert stats["Product H"] == 1
    assert stats["Product K"] == 1


def test_translate_history_file_not_found():
    """Test translate_history_file raises error for missing file."""
    mapping = {"Product A": "Real A"}
    non_existent = Path("/non/existent/file.json")

    with pytest.raises(FileNotFoundError):
        translate_history_file(non_existent, mapping, direction="reverse")


def test_translate_history_file_invalid_json(tmp_path):
    """Test translate_history_file raises error for invalid JSON."""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{ invalid json }")

    mapping = {"Product A": "Real A"}

    with pytest.raises(json.JSONDecodeError):
        translate_history_file(invalid_file, mapping, direction="reverse")


# ============================================================================
# TEST: load_mapping_file Function
# ============================================================================


def test_load_mapping_file_success(tmp_path):
    """Test load_mapping_file successfully loads valid mapping."""
    mapping_data = {"Product A": "Real A", "Product B": "Real B"}
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text(json.dumps(mapping_data))

    result = load_mapping_file(mapping_file, direction="reverse")

    assert result == mapping_data


def test_load_mapping_file_not_found(tmp_path):
    """Test load_mapping_file exits when file not found."""
    non_existent = tmp_path / "missing.json"

    with pytest.raises(SystemExit) as exc_info:
        load_mapping_file(non_existent, direction="reverse")

    assert exc_info.value.code == 1


def test_load_mapping_file_invalid_json(tmp_path):
    """Test load_mapping_file exits for invalid JSON."""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{ invalid json }")

    with pytest.raises(SystemExit) as exc_info:
        load_mapping_file(invalid_file, direction="reverse")

    assert exc_info.value.code == 1


def test_load_mapping_file_not_dict(tmp_path):
    """Test load_mapping_file exits for non-dictionary JSON."""
    invalid_file = tmp_path / "list.json"
    invalid_file.write_text('["not", "a", "dict"]')

    with pytest.raises(SystemExit) as exc_info:
        load_mapping_file(invalid_file, direction="reverse")

    assert exc_info.value.code == 1


def test_load_mapping_file_warns_unexpected_key(tmp_path, capsys):
    """Test load_mapping_file warns about unexpected keys."""
    mapping_data = {
        "Product A": "Real A",
        "Build Product A Searches": "Build Real A Searches",  # Unexpected key
    }
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text(json.dumps(mapping_data))

    load_mapping_file(mapping_file, direction="reverse")

    captured = capsys.readouterr()
    assert "WARN" in captured.out
    assert "Build Product A Searches" in captured.out


# ============================================================================
# TEST: Integration - Real-World Scenario
# ============================================================================


def test_integration_security_history_structure(reverse_mapping):
    """
    Integration test: Full security_history.json structure.

    This mimics the exact structure that caused the production bug.
    """
    security_history = {
        "weeks": [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "metrics": {
                    "total_vulnerabilities": 144,
                    "product_breakdown": {
                        "Product G": {
                            "critical": 2,
                            "high": 5,
                            "medium": 8,
                            "low": 10,
                        },
                        "Product H": {
                            "critical": 1,
                            "high": 3,
                            "medium": 6,
                            "low": 8,
                        },
                        "Product K": {
                            "critical": 0,
                            "high": 2,
                            "medium": 4,
                            "low": 6,
                        },
                    },
                },
            }
        ]
    }

    stats: Dict[str, int] = {}
    result = translate_value(
        security_history, reverse_mapping, stats, direction="reverse"
    )

    # Verify ALL product names in keys were translated
    product_breakdown = result["weeks"][0]["metrics"]["product_breakdown"]
    assert "Access Diversity" in product_breakdown
    assert "Access Legal AI Services" in product_breakdown
    assert "Eclipse" in product_breakdown

    # Verify NO generic names remain
    assert "Product G" not in product_breakdown
    assert "Product H" not in product_breakdown
    assert "Product K" not in product_breakdown

    # Verify counts
    assert product_breakdown["Access Diversity"]["critical"] == 2
    assert product_breakdown["Eclipse"]["low"] == 6
