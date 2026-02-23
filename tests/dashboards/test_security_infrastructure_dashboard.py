"""
Tests for Security Infrastructure Dashboard Generator

Verifies that the infrastructure-only dashboard:
- Has the correct title and subtitle (Infrastructure, not Code & Cloud)
- Only exposes an Infrastructure filter button (no Code or Cloud buttons)
- Does NOT include the 70% reduction target glossary entry
- Is written as a side effect of generate_security_dashboard_enhanced()
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from execution.collectors.armorcode_vulnerability_loader import VulnerabilityDetail
from execution.dashboards.security_content_builder import _generate_infra_dashboard_html
from execution.dashboards.security_enhanced import generate_security_dashboard_enhanced
from execution.domain.security import SecurityMetrics

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_metrics_by_product() -> dict:
    """Minimal SecurityMetrics for one product."""
    return {
        "Web Application": SecurityMetrics(
            timestamp=datetime(2026, 2, 7),
            project="Web Application",
            total_vulnerabilities=10,
            critical=2,
            high=5,
            medium=2,
            low=1,
        )
    }


@pytest.fixture
def sample_vulns_by_product() -> dict:
    """Minimal VulnerabilityDetail list keyed by product."""
    return {
        "Web Application": [
            VulnerabilityDetail(
                id="v1",
                title="Infra critical",
                description="",
                severity="CRITICAL",
                status="OPEN",
                created_at="",
                product="Web Application",
                age_days=10,
                source="Cortex XDR",
            )
        ]
    }


@pytest.fixture
def sample_bucket_counts() -> dict:
    """Per-product bucket counts for CODE, CLOUD, and INFRASTRUCTURE."""
    return {
        "Web Application": {
            "CODE": {"critical": 1, "high": 3, "total": 4},
            "CLOUD": {"critical": 0, "high": 1, "total": 1},
            "INFRASTRUCTURE": {"critical": 2, "high": 5, "total": 7},
        }
    }


# ---------------------------------------------------------------------------
# HTML content tests (call _generate_infra_dashboard_html directly)
# ---------------------------------------------------------------------------


class TestInfraDashboardHtmlContent:
    """Tests for the rendered infrastructure dashboard HTML."""

    @patch("execution.dashboards.security_content_builder.get_dashboard_framework")
    def test_title_contains_infrastructure(
        self,
        mock_framework,
        sample_metrics_by_product,
        sample_vulns_by_product,
        sample_bucket_counts,
    ):
        """Dashboard title and header must reference 'Infrastructure', not 'Code & Cloud'."""
        mock_framework.return_value = ("<style></style>", "<script></script>")

        html = _generate_infra_dashboard_html(
            sample_metrics_by_product,
            sample_vulns_by_product,
            sample_bucket_counts,
            {},
        )

        assert "Infrastructure" in html
        assert "Code &amp; Cloud" not in html
        assert "Code & Cloud" not in html

    @patch("execution.dashboards.security_content_builder.get_dashboard_framework")
    def test_does_not_contain_code_filter_button(
        self,
        mock_framework,
        sample_metrics_by_product,
        sample_vulns_by_product,
        sample_bucket_counts,
    ):
        """Infrastructure dashboard must not expose a 'Code' category filter button."""
        mock_framework.return_value = ("<style></style>", "<script></script>")

        html = _generate_infra_dashboard_html(
            sample_metrics_by_product,
            sample_vulns_by_product,
            sample_bucket_counts,
            {},
        )

        # The Code & Cloud dashboard has data-cat="code" and data-cat="cloud" buttons.
        # The infrastructure dashboard must have neither.
        assert 'data-cat="code"' not in html
        assert 'data-cat="cloud"' not in html

    @patch("execution.dashboards.security_content_builder.get_dashboard_framework")
    def test_excludes_70pct_target_glossary(
        self,
        mock_framework,
        sample_metrics_by_product,
        sample_vulns_by_product,
        sample_bucket_counts,
    ):
        """Infrastructure dashboard must NOT include the 70% reduction target glossary entry."""
        mock_framework.return_value = ("<style></style>", "<script></script>")

        html = _generate_infra_dashboard_html(
            sample_metrics_by_product,
            sample_vulns_by_product,
            sample_bucket_counts,
            {},
        )

        # The 70% target glossary is present in security_dashboard.html but
        # deliberately omitted from security_infrastructure_dashboard.html.
        assert "70%" not in html
        assert "70&percnt;" not in html

    @patch("execution.dashboards.security_content_builder.get_dashboard_framework")
    def test_infrastructure_filter_button_present(
        self,
        mock_framework,
        sample_metrics_by_product,
        sample_vulns_by_product,
        sample_bucket_counts,
    ):
        """Infrastructure dashboard must have a data-cat='infrastructure' filter button."""
        mock_framework.return_value = ("<style></style>", "<script></script>")

        html = _generate_infra_dashboard_html(
            sample_metrics_by_product,
            sample_vulns_by_product,
            sample_bucket_counts,
            {},
        )

        assert 'data-cat="infrastructure"' in html


# ---------------------------------------------------------------------------
# Side-effect test: generate_security_dashboard_enhanced writes infra file
# ---------------------------------------------------------------------------


class TestGenerateSecurityEnhancedWritesInfraDashboard:
    """Verify that generate_security_dashboard_enhanced() writes both HTML files."""

    @patch("execution.dashboards.security_enhanced.get_config")
    @patch("execution.dashboards.security_enhanced._update_history_current_total")
    @patch("execution.dashboards.security_enhanced._patch_history_bucket_breakdown")
    @patch("execution.dashboards.security_enhanced.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security_enhanced._load_id_map")
    @patch("execution.dashboards.security_content_builder.get_dashboard_framework")
    @patch("pathlib.Path.write_text")
    def test_writes_infra_dashboard_as_side_effect(
        self,
        mock_write,
        mock_framework,
        mock_load_id_map,
        mock_vuln_loader_class,
        mock_patch_history,
        mock_update_history,
        mock_get_config,
        tmp_path,
    ):
        """
        Calling generate_security_dashboard_enhanced() must write exactly two HTML files:
        security_dashboard.html (main) and security_infrastructure_dashboard.html (infra).
        """
        mock_load_id_map.return_value = {"Web Application": "pid1"}
        mock_get_config.return_value.get_optional_env.return_value = "test/hierarchy"
        mock_vuln_loader = Mock()
        mock_vuln_loader.count_by_severity_aql.return_value = {"pid1": 2}
        mock_vuln_loader.fetch_findings_aql.return_value = []
        mock_vuln_loader_class.return_value = mock_vuln_loader
        mock_framework.return_value = ("<style></style>", "<script></script>")

        generate_security_dashboard_enhanced(tmp_path / "dashboards")

        # Two write_text calls: main dashboard + infrastructure dashboard
        assert mock_write.call_count == 2
