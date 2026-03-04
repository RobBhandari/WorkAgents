"""
Tests for private helper functions extracted from create_baseline()
in execution/armorcode_baseline.py.

The module imports execution.config and execution.http_client at the top level,
so we stub those modules into sys.modules before importing our target module.
"""

import sys
import types
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stub out unavailable / side-effecting module-level dependencies before import
# ---------------------------------------------------------------------------

# Stub execution.config so the module-level import doesn't fail
_config_mod = types.ModuleType("execution.config")
_config_mod.get_config = MagicMock()  # type: ignore[attr-defined]
sys.modules.setdefault("execution.config", _config_mod)

# Stub execution.http_client so the module-level import doesn't fail
_http_mod = types.ModuleType("execution.http_client")
_http_mod.get = MagicMock()  # type: ignore[attr-defined]
sys.modules.setdefault("execution.http_client", _http_mod)

# ---------------------------------------------------------------------------
# Now import the helpers under test
# ---------------------------------------------------------------------------

from unittest.mock import patch

import pytest

from execution.armorcode_baseline import (
    _extract_vulnerability_list,
    _first_value,
    _format_vulnerability,
    _truncate_description,
    _try_endpoint_urls,
)

# ---------------------------------------------------------------------------
# _first_value
# ---------------------------------------------------------------------------


class TestFirstValue:
    def test_returns_first_present_key(self):
        raw = {"id": "abc", "vulnerability_id": "xyz"}
        assert _first_value(raw, "id", "vulnerability_id") == "abc"

    def test_falls_back_to_second_key_when_first_absent(self):
        raw = {"vulnerability_id": "xyz"}
        assert _first_value(raw, "id", "vulnerability_id") == "xyz"

    def test_falls_back_through_multiple_keys(self):
        raw = {"finding_id": "zzz"}
        assert _first_value(raw, "id", "vulnerability_id", "finding_id") == "zzz"

    def test_returns_none_when_no_key_present(self):
        assert _first_value({}, "id", "vulnerability_id") is None

    def test_skips_none_values(self):
        raw = {"id": None, "vulnerability_id": "xyz"}
        assert _first_value(raw, "id", "vulnerability_id") == "xyz"

    def test_skips_empty_string_values(self):
        raw = {"id": "", "vulnerability_id": "xyz"}
        assert _first_value(raw, "id", "vulnerability_id") == "xyz"

    def test_returns_integer_zero_correctly(self):
        """Integer 0 is falsy but is a valid non-None, non-empty value."""
        raw = {"count": 0}
        assert _first_value(raw, "count") == 0


# ---------------------------------------------------------------------------
# _truncate_description
# ---------------------------------------------------------------------------


class TestTruncateDescription:
    def test_short_description_unchanged(self):
        raw = {"description": "Short text"}
        assert _truncate_description(raw) == "Short text"

    def test_long_description_is_truncated(self):
        raw = {"description": "x" * 201}
        result = _truncate_description(raw)
        assert len(result) == 203  # 200 chars + "..."
        assert result.endswith("...")

    def test_exactly_200_chars_unchanged(self):
        raw = {"description": "y" * 200}
        result = _truncate_description(raw)
        assert result == "y" * 200
        assert not result.endswith("...")

    def test_missing_description_returns_empty_string(self):
        assert _truncate_description({}) == ""

    def test_none_description_returns_empty_string(self):
        raw = {"description": None}
        assert _truncate_description(raw) == ""

    def test_custom_max_len(self):
        raw = {"description": "abcde"}
        result = _truncate_description(raw, max_len=3)
        assert result == "abc..."


# ---------------------------------------------------------------------------
# _extract_vulnerability_list
# ---------------------------------------------------------------------------


class TestExtractVulnerabilityList:
    def test_raw_list_returned_as_is(self):
        data = [{"id": "1"}, {"id": "2"}]
        assert _extract_vulnerability_list(data) == data

    def test_empty_list_returned_as_is(self):
        assert _extract_vulnerability_list([]) == []

    def test_dict_with_vulnerabilities_key(self):
        data = {"vulnerabilities": [{"id": "v1"}]}
        assert _extract_vulnerability_list(data) == [{"id": "v1"}]

    def test_dict_with_findings_key(self):
        data = {"findings": [{"id": "f1"}]}
        assert _extract_vulnerability_list(data) == [{"id": "f1"}]

    def test_dict_with_data_key(self):
        data = {"data": [{"id": "d1"}]}
        assert _extract_vulnerability_list(data) == [{"id": "d1"}]

    def test_dict_prefers_vulnerabilities_over_findings(self):
        """'vulnerabilities' key takes precedence over 'findings'."""
        data = {"vulnerabilities": [{"id": "v"}], "findings": [{"id": "f"}]}
        result = _extract_vulnerability_list(data)
        assert result == [{"id": "v"}]

    def test_dict_with_no_known_key_returns_empty_list(self):
        data = {"total": 0, "page": 1}
        assert _extract_vulnerability_list(data) == []

    def test_empty_dict_returns_empty_list(self):
        assert _extract_vulnerability_list({}) == []


# ---------------------------------------------------------------------------
# _format_vulnerability
# ---------------------------------------------------------------------------


class TestFormatVulnerability:
    def test_maps_primary_fields(self):
        raw = {
            "id": "vuln-1",
            "title": "SQL Injection",
            "severity": "HIGH",
            "status": "Open",
        }
        result = _format_vulnerability(raw)
        assert result["id"] == "vuln-1"
        assert result["title"] == "SQL Injection"
        assert result["severity"] == "HIGH"
        assert result["status"] == "Open"

    def test_falls_back_to_vulnerability_id(self):
        raw = {"vulnerability_id": "v-99"}
        result = _format_vulnerability(raw)
        assert result["id"] == "v-99"

    def test_falls_back_to_finding_id(self):
        raw = {"finding_id": "f-42"}
        result = _format_vulnerability(raw)
        assert result["id"] == "f-42"

    def test_falls_back_to_name_for_title(self):
        raw = {"name": "XSS Finding"}
        result = _format_vulnerability(raw)
        assert result["title"] == "XSS Finding"

    def test_falls_back_to_product_name(self):
        raw = {"product_name": "MyProduct"}
        result = _format_vulnerability(raw)
        assert result["product"] == "MyProduct"

    def test_falls_back_to_component_for_asset(self):
        raw = {"component": "frontend"}
        result = _format_vulnerability(raw)
        assert result["asset"] == "frontend"

    def test_falls_back_to_cve_id(self):
        raw = {"cve_id": "CVE-2024-1234"}
        result = _format_vulnerability(raw)
        assert result["cve"] == "CVE-2024-1234"

    def test_falls_back_to_cwe_id(self):
        raw = {"cwe_id": "CWE-79"}
        result = _format_vulnerability(raw)
        assert result["cwe"] == "CWE-79"

    def test_falls_back_to_discovered_date_for_first_seen(self):
        raw = {"discovered_date": "2026-01-01"}
        result = _format_vulnerability(raw)
        assert result["first_seen"] == "2026-01-01"

    def test_first_seen_defaults_to_empty_string(self):
        result = _format_vulnerability({})
        assert result["first_seen"] == ""

    def test_long_description_is_truncated(self):
        raw = {"description": "x" * 201}
        result = _format_vulnerability(raw)
        assert result["description"].endswith("...")
        assert len(result["description"]) == 203

    def test_missing_fields_return_none_without_raising(self):
        result = _format_vulnerability({})
        assert isinstance(result, dict)
        assert result["id"] is None
        assert result["severity"] is None

    def test_all_expected_keys_present(self):
        expected_keys = {
            "id",
            "title",
            "severity",
            "product",
            "asset",
            "cve",
            "cwe",
            "status",
            "first_seen",
            "description",
        }
        result = _format_vulnerability({})
        assert set(result.keys()) == expected_keys


# ---------------------------------------------------------------------------
# _try_endpoint_urls
# ---------------------------------------------------------------------------


class TestTryEndpointUrls:
    def _make_response(self, status_code: int, json_data=None, text: str = ""):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_data if json_data is not None else []
        mock_resp.text = text
        return mock_resp

    def test_returns_data_and_endpoint_on_first_200(self):
        payload = [{"id": "1"}]
        with patch("execution.armorcode_baseline.get") as mock_get:
            mock_get.return_value = self._make_response(200, payload)
            data, endpoint = _try_endpoint_urls(
                "https://api.example.com",
                ["/api/v1/findings"],
                {},
                {},
            )
        assert data == payload
        assert endpoint == "/api/v1/findings"

    def test_skips_404_and_tries_next(self):
        payload = [{"id": "2"}]
        responses = [
            self._make_response(404),
            self._make_response(200, payload),
        ]
        with patch("execution.armorcode_baseline.get", side_effect=responses):
            data, endpoint = _try_endpoint_urls(
                "https://api.example.com",
                ["/api/v1/not_found", "/api/v1/findings"],
                {},
                {},
            )
        assert data == payload
        assert endpoint == "/api/v1/findings"

    def test_skips_non_200_non_404_and_tries_next(self):
        payload = [{"id": "3"}]
        responses = [
            self._make_response(500, text="Internal Error"),
            self._make_response(200, payload),
        ]
        with patch("execution.armorcode_baseline.get", side_effect=responses):
            data, endpoint = _try_endpoint_urls(
                "https://api.example.com",
                ["/api/v1/bad", "/api/v1/findings"],
                {},
                {},
            )
        assert data == payload

    def test_raises_runtime_error_when_all_fail(self):
        with patch("execution.armorcode_baseline.get") as mock_get:
            mock_get.return_value = self._make_response(404)
            with pytest.raises(RuntimeError, match="Unable to fetch vulnerabilities"):
                _try_endpoint_urls(
                    "https://api.example.com",
                    ["/ep1", "/ep2"],
                    {},
                    {},
                )

    def test_skips_endpoint_on_request_exception(self):
        from requests.exceptions import RequestException

        payload = [{"id": "4"}]
        with patch("execution.armorcode_baseline.get") as mock_get:
            mock_get.side_effect = [
                RequestException("Connection failed"),
                self._make_response(200, payload),
            ]
            data, endpoint = _try_endpoint_urls(
                "https://api.example.com",
                ["/api/v1/bad", "/api/v1/ok"],
                {},
                {},
            )
        assert data == payload
        assert endpoint == "/api/v1/ok"

    def test_raises_when_all_endpoints_raise_request_exception(self):
        from requests.exceptions import RequestException

        with patch("execution.armorcode_baseline.get") as mock_get:
            mock_get.side_effect = RequestException("timeout")
            with pytest.raises(RuntimeError, match="Unable to fetch vulnerabilities"):
                _try_endpoint_urls(
                    "https://api.example.com",
                    ["/a", "/b"],
                    {},
                    {},
                )

    def test_error_message_lists_all_attempted_endpoints(self):
        with patch("execution.armorcode_baseline.get") as mock_get:
            mock_get.return_value = self._make_response(404)
            with pytest.raises(RuntimeError) as exc_info:
                _try_endpoint_urls(
                    "https://api.example.com",
                    ["/ep1", "/ep2"],
                    {},
                    {},
                )
        assert "/ep1" in str(exc_info.value)
        assert "/ep2" in str(exc_info.value)
