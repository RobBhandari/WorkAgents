"""
Tests for generate_trends_dashboard module.

Covers the pure-logic helpers extracted to reduce McCabe complexity:
- _log_domain_extracted
- _extract_simple_domain
- _extract_all_trends
- _extract_security_trends
"""

from unittest.mock import MagicMock, patch

import pytest

from execution.generate_trends_dashboard import (
    _extract_all_trends,
    _extract_security_trends,
    _extract_simple_domain,
    _log_domain_extracted,
)


def _make_trend(weeks: int, key: str) -> dict:
    """Build a minimal trend result dict with the given number of data points."""
    return {key: {"trend_data": list(range(weeks))}}


class TestLogDomainExtracted:
    """Tests for _log_domain_extracted."""

    def test_logs_correct_week_count(self, caplog):
        """Should log the number of weeks in trend_data."""
        import logging

        result = _make_trend(5, "bugs")
        with caplog.at_level(logging.INFO, logger="execution.generate_trends_dashboard"):
            _log_domain_extracted("quality", result, "bugs")

        assert "5 weeks" in caplog.text

    def test_domain_name_capitalised(self, caplog):
        """Should capitalise the domain name in the log message."""
        import logging

        result = _make_trend(3, "lead_time")
        with caplog.at_level(logging.INFO, logger="execution.generate_trends_dashboard"):
            _log_domain_extracted("flow", result, "lead_time")

        assert "Flow" in caplog.text


class TestExtractSimpleDomain:
    """Tests for _extract_simple_domain."""

    def test_stores_result_when_extractor_returns_data(self):
        """Result should be added to trends dict when extractor returns data."""
        calculator = MagicMock()
        weeks = [{"week": 1}]
        calculator.extract_quality_trends.return_value = _make_trend(3, "bugs")

        trends: dict = {}
        _extract_simple_domain(calculator, weeks, trends, "quality", "extract_quality_trends", "bugs")

        assert "quality" in trends
        assert len(trends["quality"]["bugs"]["trend_data"]) == 3

    def test_skips_when_extractor_returns_empty(self):
        """Trends dict should not be modified when extractor returns empty/None."""
        calculator = MagicMock()
        calculator.extract_quality_trends.return_value = {}

        trends: dict = {}
        _extract_simple_domain(calculator, [], trends, "quality", "extract_quality_trends", "bugs")

        assert "quality" not in trends

    def test_skips_when_extractor_returns_none(self):
        """Trends dict should not be modified when extractor returns None."""
        calculator = MagicMock()
        calculator.extract_flow_trends.return_value = None

        trends: dict = {}
        _extract_simple_domain(calculator, [], trends, "flow", "extract_flow_trends", "lead_time")

        assert "flow" not in trends

    def test_uses_correct_extractor_method(self):
        """Should dispatch to the named extractor method on the calculator."""
        calculator = MagicMock()
        calculator.extract_deployment_trends.return_value = _make_trend(2, "build_success")

        trends: dict = {}
        _extract_simple_domain(
            calculator, ["week1"], trends, "deployment", "extract_deployment_trends", "build_success"
        )

        calculator.extract_deployment_trends.assert_called_once_with(["week1"])


class TestExtractSecurityTrends:
    """Tests for _extract_security_trends."""

    def _vuln_trend(self, weeks: int) -> dict:
        return {"vulnerabilities": {"trend_data": list(range(weeks))}}

    def test_stores_all_three_variants(self):
        """All three security keys should be set when all extractors return data."""
        calculator = MagicMock()
        calculator.extract_security_trends.return_value = self._vuln_trend(4)
        calculator.extract_security_code_cloud_trends.return_value = self._vuln_trend(4)
        calculator.extract_security_infra_trends.return_value = self._vuln_trend(4)

        trends: dict = {}
        _extract_security_trends(calculator, [], trends)

        assert "security" in trends
        assert "security_code_cloud" in trends
        assert "security_infra" in trends

    def test_skips_empty_variants(self):
        """Keys should be absent when the extractor returns empty/None."""
        calculator = MagicMock()
        calculator.extract_security_trends.return_value = self._vuln_trend(3)
        calculator.extract_security_code_cloud_trends.return_value = None
        calculator.extract_security_infra_trends.return_value = {}

        trends: dict = {}
        _extract_security_trends(calculator, [], trends)

        assert "security" in trends
        assert "security_code_cloud" not in trends
        assert "security_infra" not in trends


class TestExtractAllTrends:
    """Tests for _extract_all_trends."""

    def _quality_data(self) -> dict:
        return {"quality": {"weeks": [{"week": 1}]}}

    def _security_data(self) -> dict:
        return {"security": {"weeks": [{"week": 1}]}}

    def test_returns_empty_dict_for_empty_metrics(self):
        """Should return an empty trends dict when no domain keys are present."""
        calculator = MagicMock()
        trends = _extract_all_trends(calculator, {})
        assert trends == {}

    def test_processes_quality_domain(self):
        """quality key should appear in trends when quality data is present."""
        calculator = MagicMock()
        calculator.extract_quality_trends.return_value = {"bugs": {"trend_data": [1, 2, 3]}}

        metrics_data = self._quality_data()
        trends = _extract_all_trends(calculator, metrics_data)

        assert "quality" in trends

    def test_skips_absent_domains(self):
        """Keys absent from metrics_data should not appear in trends."""
        calculator = MagicMock()
        calculator.extract_quality_trends.return_value = {"bugs": {"trend_data": [1]}}

        metrics_data = self._quality_data()
        trends = _extract_all_trends(calculator, metrics_data)

        for absent in ("flow", "deployment", "collaboration", "ownership", "risk", "exploitable", "security"):
            assert absent not in trends

    def test_processes_security_through_dedicated_helper(self):
        """Security domain should fan out into three sub-keys."""
        calculator = MagicMock()
        vuln = {"vulnerabilities": {"trend_data": [1, 2]}}
        calculator.extract_security_trends.return_value = vuln
        calculator.extract_security_code_cloud_trends.return_value = vuln
        calculator.extract_security_infra_trends.return_value = vuln

        metrics_data = self._security_data()
        trends = _extract_all_trends(calculator, metrics_data)

        assert "security" in trends
        assert "security_code_cloud" in trends
        assert "security_infra" in trends

    def test_processes_multiple_domains_together(self):
        """Multiple domain keys in metrics_data should all be processed."""
        calculator = MagicMock()
        calculator.extract_quality_trends.return_value = {"bugs": {"trend_data": [1]}}
        calculator.extract_flow_trends.return_value = {"lead_time": {"trend_data": [1]}}
        calculator.extract_security_trends.return_value = None
        calculator.extract_security_code_cloud_trends.return_value = None
        calculator.extract_security_infra_trends.return_value = None

        metrics_data = {
            "quality": {"weeks": []},
            "flow": {"weeks": []},
            "security": {"weeks": []},
        }
        trends = _extract_all_trends(calculator, metrics_data)

        assert "quality" in trends
        assert "flow" in trends
