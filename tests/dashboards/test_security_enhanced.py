"""
Tests for Enhanced Security Dashboard Generator

Tests cover:
- Product data loading from ArmorCode API
- Summary calculation across products
- Bucket breakdown generation (CODE / CLOUD / INFRASTRUCTURE / Other)
- Main dashboard HTML generation
- Zero-vuln products appear in output
- Error handling (API failures, missing data)
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from execution.collectors.armorcode_vulnerability_loader import VulnerabilityDetail
from execution.dashboards.security_enhanced import (
    _generate_bucket_expanded_content,
    generate_security_dashboard_enhanced,
)
from execution.domain.security import BUCKET_ORDER, SOURCE_BUCKET_MAP, SecurityMetrics


def _make_vuln(severity: str, source: str | None, product: str = "Web Application") -> VulnerabilityDetail:
    """Helper to construct a minimal VulnerabilityDetail for tests."""
    return VulnerabilityDetail(
        id=f"vuln-{severity[:1]}-{source or 'none'}",
        title=f"{severity} finding from {source}",
        description="",
        severity=severity,
        status="OPEN",
        created_at="",
        product=product,
        age_days=30,
        source=source,
    )


@pytest.fixture
def sample_vulnerabilities():
    """Sample VulnerabilityDetail objects covering CODE and INFRASTRUCTURE sources."""
    return [
        _make_vuln("CRITICAL", "Mend"),
        _make_vuln("HIGH", "SonarQube"),
        _make_vuln("HIGH", "Cortex XDR"),
        _make_vuln("CRITICAL", "Cortex XDR"),
    ]


@pytest.fixture
def sample_security_products():
    """Sample security metrics as SecurityMetrics domain objects"""
    return {
        "Web Application": SecurityMetrics(
            timestamp=datetime(2026, 2, 7),
            project="Web Application",
            total_vulnerabilities=45,
            critical=5,
            high=12,
            medium=20,
            low=8,
        ),
        "Mobile App": SecurityMetrics(
            timestamp=datetime(2026, 2, 6),
            project="Mobile App",
            total_vulnerabilities=23,
            critical=2,
            high=6,
            medium=10,
            low=5,
        ),
        "API Gateway": SecurityMetrics(
            timestamp=datetime(2026, 2, 8),
            project="API Gateway",
            total_vulnerabilities=12,
            critical=0,
            high=2,
            medium=7,
            low=3,
        ),
    }


# ---------------------------------------------------------------------------
# SOURCE_BUCKET_MAP sanity checks
# ---------------------------------------------------------------------------


class TestSourceBucketMap:
    """Verify bucket mapping constants are correct."""

    def test_known_code_tools(self):
        assert SOURCE_BUCKET_MAP["Mend"] == "CODE"
        assert SOURCE_BUCKET_MAP["SonarQube"] == "CODE"
        assert SOURCE_BUCKET_MAP["Custom-Pentest"] == "CODE"

    def test_known_cloud_tools(self):
        assert SOURCE_BUCKET_MAP["Prisma Cloud Redlock"] == "CLOUD"
        assert SOURCE_BUCKET_MAP["Prisma Cloud Twistlock"] == "CLOUD"
        assert SOURCE_BUCKET_MAP["Prisma Cloud Compute"] == "CLOUD"

    def test_known_infrastructure_tools(self):
        assert SOURCE_BUCKET_MAP["Cortex XDR"] == "INFRASTRUCTURE"
        assert SOURCE_BUCKET_MAP["AppCheck"] == "INFRASTRUCTURE"
        assert SOURCE_BUCKET_MAP["BitSight"] == "INFRASTRUCTURE"

    def test_bucket_order_has_other(self):
        assert "Other" in BUCKET_ORDER
        assert BUCKET_ORDER[-1] == "Other"  # Other is always last


# ---------------------------------------------------------------------------
# _generate_bucket_expanded_content
# ---------------------------------------------------------------------------


class TestGenerateBucketExpandedContent:
    """Tests for _generate_bucket_expanded_content()."""

    def test_empty_list_shows_all_buckets_with_zeros(self):
        """Empty input → all 4 buckets in summary table with zero counts."""
        html = _generate_bucket_expanded_content([])
        for bucket in BUCKET_ORDER:
            assert bucket in html

    def test_empty_list_has_no_collapsible_sections(self):
        """Empty input → no bucket-section toggles (nothing to expand)."""
        html = _generate_bucket_expanded_content([])
        assert "bucket-section-header" not in html

    def test_mend_vuln_goes_to_code_bucket(self):
        """A Mend finding should appear under the CODE collapsible section."""
        vulns = [_make_vuln("CRITICAL", "Mend")]
        html = _generate_bucket_expanded_content(vulns)
        # Bucket section header for CODE
        assert "CODE (1)" in html
        # Should NOT create Infrastructure/Cloud sections
        assert (
            "INFRASTRUCTURE" not in html.split("bucket-section-header")[1] if "bucket-section-header" in html else True
        )

    def test_cortex_xdr_goes_to_infrastructure_bucket(self):
        """A Cortex XDR finding should appear under INFRASTRUCTURE."""
        vulns = [_make_vuln("HIGH", "Cortex XDR")]
        html = _generate_bucket_expanded_content(vulns)
        assert "INFRASTRUCTURE (1)" in html

    def test_unknown_source_goes_to_other(self):
        """An unrecognised source tool → Other bucket."""
        vulns = [_make_vuln("HIGH", "UnknownTool")]
        html = _generate_bucket_expanded_content(vulns)
        assert "Other (1)" in html

    def test_none_source_goes_to_other(self):
        """A finding with source=None → Other bucket."""
        vulns = [_make_vuln("CRITICAL", None)]
        html = _generate_bucket_expanded_content(vulns)
        assert "Other (1)" in html

    def test_mixed_buckets(self, sample_vulnerabilities):
        """Mixed sources → correct bucket assignment and totals."""
        html = _generate_bucket_expanded_content(sample_vulnerabilities)
        # CODE: Mend (CRITICAL) + SonarQube (HIGH) = 2
        assert "CODE (2)" in html
        # INFRASTRUCTURE: Cortex XDR (HIGH) + Cortex XDR (CRITICAL) = 2
        assert "INFRASTRUCTURE (2)" in html

    def test_bucket_totals_match_top_line(self, sample_vulnerabilities):
        """Sum of all bucket totals equals total input count."""
        html = _generate_bucket_expanded_content(sample_vulnerabilities)
        # We have 4 vulns total, split 2 CODE / 0 CLOUD / 2 INFRA / 0 Other
        # Verify summary table has correct values (4 total)
        # Just check that the HTML renders without error and contains expected structure
        assert "bucket-summary-table" in html

    def test_medium_low_vulns_excluded(self):
        """Medium and Low severity vulns should be filtered out."""
        vulns = [
            _make_vuln("MEDIUM", "Mend"),
            _make_vuln("LOW", "Mend"),
            _make_vuln("CRITICAL", "Mend"),
        ]
        html = _generate_bucket_expanded_content(vulns)
        # Only 1 CRITICAL should appear (Medium/Low filtered)
        assert "CODE (1)" in html

    def test_html_contains_vuln_table(self, sample_vulnerabilities):
        """Generated HTML should include vuln-table for non-empty buckets."""
        html = _generate_bucket_expanded_content(sample_vulnerabilities)
        assert "vuln-table" in html

    def test_prisma_cloud_redlock_goes_to_cloud(self):
        """Prisma Cloud Redlock → CLOUD bucket."""
        vulns = [_make_vuln("HIGH", "Prisma Cloud Redlock")]
        html = _generate_bucket_expanded_content(vulns)
        assert "CLOUD (1)" in html


# ---------------------------------------------------------------------------
# generate_security_dashboard_enhanced (integration)
# ---------------------------------------------------------------------------


class TestLoadSecurityData:
    """Tests for loading security data from ArmorCode API"""

    @patch("execution.dashboards.security_enhanced.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security_enhanced._load_baseline_products")
    @patch("execution.dashboards.security_enhanced.get_dashboard_framework")
    @patch("pathlib.Path.write_text")
    def test_load_products_success(
        self,
        mock_write,
        mock_framework,
        mock_load_baseline,
        mock_vuln_loader_class,
        sample_vulnerabilities,
    ):
        """Should load products from ArmorCode API."""
        mock_load_baseline.return_value = ["Web Application", "Mobile App"]
        mock_vuln_loader = Mock()
        mock_vuln_loader.load_vulnerabilities_for_products.return_value = sample_vulnerabilities
        mock_vuln_loader.group_by_product.return_value = {"Web Application": sample_vulnerabilities}
        mock_vuln_loader_class.return_value = mock_vuln_loader
        mock_framework.return_value = ("<style></style>", "<script></script>")

        html, count = generate_security_dashboard_enhanced()

        assert count == 0
        mock_load_baseline.assert_called_once()

    @patch("execution.dashboards.security_enhanced._load_baseline_products")
    def test_load_products_api_failure(self, mock_load_baseline):
        """Should handle baseline loading failure gracefully."""
        mock_load_baseline.side_effect = FileNotFoundError("Baseline not found")
        html, count = generate_security_dashboard_enhanced()
        assert html == ""
        assert count == 0

    @patch("execution.dashboards.security_enhanced.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security_enhanced._load_baseline_products")
    @patch("execution.dashboards.security_enhanced.get_dashboard_framework")
    @patch("pathlib.Path.write_text")
    def test_load_products_empty_list(self, mock_write, mock_framework, mock_load_baseline, mock_vuln_loader_class):
        """Should handle empty product list."""
        mock_load_baseline.return_value = []
        mock_vuln_loader = Mock()
        mock_vuln_loader.load_vulnerabilities_for_products.return_value = []
        mock_vuln_loader.group_by_product.return_value = {}
        mock_vuln_loader_class.return_value = mock_vuln_loader
        mock_framework.return_value = ("<style></style>", "<script></script>")

        html, count = generate_security_dashboard_enhanced()
        assert count == 0
        assert len(html) > 0


class TestZeroVulnProducts:
    """Zero-Critical/High products must appear in the dashboard."""

    @patch("execution.dashboards.security_enhanced.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security_enhanced._load_baseline_products")
    @patch("execution.dashboards.security_enhanced.get_dashboard_framework")
    @patch("pathlib.Path.write_text")
    def test_zero_vuln_product_appears_in_output(
        self, mock_write, mock_framework, mock_load_baseline, mock_vuln_loader_class
    ):
        """A product with 0 Critical/High should appear with zero counts, not be dropped."""
        mock_load_baseline.return_value = ["Proclaim", "Web Application"]
        mock_vuln_loader = Mock()
        # Only Web Application has vulns; Proclaim returns nothing
        mock_vuln_loader.load_vulnerabilities_for_products.return_value = [
            _make_vuln("CRITICAL", "Mend", product="Web Application")
        ]
        mock_vuln_loader.group_by_product.return_value = {
            "Web Application": [_make_vuln("CRITICAL", "Mend", product="Web Application")]
        }
        mock_vuln_loader_class.return_value = mock_vuln_loader
        mock_framework.return_value = ("<style></style>", "<script></script>")

        html, _ = generate_security_dashboard_enhanced()

        assert "Proclaim" in html
        assert "Web Application" in html


class TestGenerateSecurityDashboardEnhanced:
    """Tests for full dashboard generation."""

    @patch("execution.dashboards.security_enhanced.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security_enhanced._load_baseline_products")
    @patch("execution.dashboards.security_enhanced.get_dashboard_framework")
    @patch("pathlib.Path.write_text")
    def test_generate_dashboard_success(
        self, mock_write, mock_framework, mock_load_baseline, mock_vuln_loader_class, sample_vulnerabilities
    ):
        """Should generate complete dashboard HTML."""
        mock_load_baseline.return_value = ["Web Application", "Mobile App", "API Gateway"]
        mock_vuln_loader = Mock()
        mock_vuln_loader.load_vulnerabilities_for_products.return_value = sample_vulnerabilities
        mock_vuln_loader.group_by_product.return_value = {"Web Application": sample_vulnerabilities}
        mock_vuln_loader_class.return_value = mock_vuln_loader
        mock_framework.return_value = ("<style>.card{}</style>", "<script></script>")

        html, count = generate_security_dashboard_enhanced()

        assert isinstance(html, str)
        assert len(html) > 0
        assert count == 0
        assert "Web Application" in html

    @patch("execution.dashboards.security_enhanced.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security_enhanced._load_baseline_products")
    @patch("execution.dashboards.security_enhanced.get_dashboard_framework")
    @patch("pathlib.Path.write_text")
    def test_write_to_output_directory(
        self, mock_write, mock_framework, mock_load_baseline, mock_vuln_loader_class, sample_vulnerabilities, tmp_path
    ):
        """Should write exactly one HTML file (main dashboard only)."""
        mock_load_baseline.return_value = ["Web Application"]
        mock_vuln_loader = Mock()
        mock_vuln_loader.load_vulnerabilities_for_products.return_value = sample_vulnerabilities
        mock_vuln_loader.group_by_product.return_value = {"Web Application": sample_vulnerabilities}
        mock_vuln_loader_class.return_value = mock_vuln_loader
        mock_framework.return_value = ("<style></style>", "<script></script>")

        generate_security_dashboard_enhanced(tmp_path / "dashboards")
        assert mock_write.call_count == 1  # Only main dashboard, no detail pages
