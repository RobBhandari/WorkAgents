"""
Tests for Enhanced Security Dashboard Generator

Tests cover:
- Product data loading from ArmorCode API
- Summary calculation across products
- Product detail page generation
- Main dashboard HTML generation
- Error handling (API failures, missing data)
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from execution.dashboards.security_enhanced import generate_security_dashboard_enhanced
from execution.domain.security import SecurityMetrics, Vulnerability


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


@pytest.fixture
def sample_vulnerabilities():
    """Sample vulnerability details for a product"""
    return [
        Vulnerability(
            id="vuln-001",
            title="SQL Injection in Login Form",
            severity="CRITICAL",
            cve_id="CVE-2026-1234",
            age_days=45,
            status="Open",
            product="Web Application",
        ),
        Vulnerability(
            id="vuln-002",
            title="XSS in User Profile",
            severity="HIGH",
            cve_id="CVE-2026-5678",
            age_days=30,
            status="Open",
            product="Web Application",
        ),
    ]


class TestLoadSecurityData:
    """Tests for loading security data from ArmorCode API"""

    @patch("execution.dashboards.security_enhanced.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security_enhanced.ArmorCodeLoader")
    @patch("execution.dashboards.security_enhanced.get_dashboard_framework")
    @patch("execution.dashboards.security_enhanced.generate_product_detail_page")
    @patch("pathlib.Path.write_text")
    def test_load_products_success(
        self,
        mock_write,
        mock_detail_page,
        mock_framework,
        mock_loader_class,
        mock_vuln_loader_class,
        sample_security_products,
        sample_vulnerabilities,
    ):
        """Should load products from ArmorCode API"""
        # Setup metrics loader
        mock_loader = Mock()
        mock_loader.load_latest_metrics.return_value = sample_security_products
        mock_loader_class.return_value = mock_loader

        # Setup vulnerability loader
        mock_vuln_loader = Mock()
        mock_vuln_loader.load_vulnerabilities_for_products.return_value = sample_vulnerabilities
        mock_vuln_loader.group_by_product.return_value = {"Web Application": sample_vulnerabilities}
        mock_vuln_loader.get_product_ids.return_value = {"Web Application": "prod-001"}
        mock_vuln_loader_class.return_value = mock_vuln_loader

        # Setup framework and detail page
        mock_framework.return_value = ("<style></style>", "<script></script>")
        mock_detail_page.return_value = "<html>Detail</html>"

        html, count = generate_security_dashboard_enhanced()

        assert count == 0  # No detail pages (using expandable rows)
        mock_loader.load_latest_metrics.assert_called_once()

    @patch("execution.dashboards.security_enhanced.ArmorCodeLoader")
    def test_load_products_api_failure(self, mock_loader_class):
        """Should handle API failure gracefully"""
        mock_loader = Mock()
        mock_loader.load_latest_metrics.side_effect = Exception("API connection failed")
        mock_loader_class.return_value = mock_loader

        with pytest.raises(Exception, match="API connection failed"):
            generate_security_dashboard_enhanced()

    @patch("execution.dashboards.security_enhanced.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security_enhanced.ArmorCodeLoader")
    @patch("execution.dashboards.security_enhanced.get_dashboard_framework")
    @patch("pathlib.Path.write_text")
    def test_load_products_empty_list(self, mock_write, mock_framework, mock_loader_class, mock_vuln_loader_class):
        """Should handle empty product list"""
        mock_loader = Mock()
        mock_loader.load_latest_metrics.return_value = {}
        mock_loader_class.return_value = mock_loader

        mock_vuln_loader = Mock()
        mock_vuln_loader.load_vulnerabilities_for_products.return_value = []
        mock_vuln_loader.group_by_product.return_value = {}
        mock_vuln_loader_class.return_value = mock_vuln_loader

        mock_framework.return_value = ("<style></style>", "<script></script>")

        html, count = generate_security_dashboard_enhanced()

        assert count == 0
        assert len(html) > 0  # Should still generate HTML with empty state


class TestCalculateSummary:
    """Tests for summary calculation across products"""

    def test_calculate_total_vulnerabilities(self, sample_security_products):
        """Should correctly sum total vulnerabilities"""
        total_vulns = sum(m.total_vulnerabilities for m in sample_security_products.values())
        assert total_vulns == 80  # 45 + 23 + 12

    def test_calculate_critical_count(self, sample_security_products):
        """Should correctly count critical vulnerabilities"""
        critical_count = sum(m.critical for m in sample_security_products.values())
        assert critical_count == 7  # 5 + 2 + 0

    def test_calculate_high_count(self, sample_security_products):
        """Should correctly calculate high vulnerability count"""
        high_count = sum(m.high for m in sample_security_products.values())
        assert high_count == 20  # 12 + 6 + 2


class TestGenerateProductDetailPage:
    """Tests for individual product detail page generation"""

    @patch("execution.dashboards.security_enhanced.generate_product_detail_page")
    @patch("execution.dashboards.security_enhanced.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security_enhanced.ArmorCodeLoader")
    @patch("execution.dashboards.security_enhanced.get_dashboard_framework")
    @patch("pathlib.Path.write_text")
    def test_detail_pages_created_for_each_product(
        self,
        mock_write,
        mock_framework,
        mock_loader_class,
        mock_vuln_loader_class,
        mock_detail_generator,
        sample_security_products,
        sample_vulnerabilities,
    ):
        """Should create detail page for each product"""
        mock_loader = Mock()
        mock_loader.load_latest_metrics.return_value = sample_security_products
        mock_loader_class.return_value = mock_loader

        mock_vuln_loader = Mock()
        mock_vuln_loader.load_vulnerabilities_for_products.return_value = sample_vulnerabilities
        mock_vuln_loader.group_by_product.return_value = {
            "Web Application": sample_vulnerabilities,
            "Mobile App": sample_vulnerabilities,
            "API Gateway": sample_vulnerabilities,
        }
        mock_vuln_loader.get_product_ids.return_value = {
            "Web Application": "prod-001",
            "Mobile App": "prod-002",
            "API Gateway": "prod-003",
        }
        mock_vuln_loader_class.return_value = mock_vuln_loader

        mock_framework.return_value = ("<style></style>", "<script></script>")
        mock_detail_generator.return_value = "<html>Detail Page</html>"

        html, count = generate_security_dashboard_enhanced()

        # No longer generates detail pages (using expandable rows instead)
        assert mock_detail_generator.call_count == 0
        assert count == 0

    @patch("execution.dashboards.security_enhanced.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security_enhanced.generate_product_detail_page")
    @patch("execution.dashboards.security_enhanced.ArmorCodeLoader")
    @patch("execution.dashboards.security_enhanced.get_dashboard_framework")
    @patch("pathlib.Path.write_text")
    def test_detail_page_includes_vulnerabilities(
        self,
        mock_write,
        mock_framework,
        mock_loader_class,
        mock_detail_generator,
        mock_vuln_loader_class,
        sample_security_products,
        sample_vulnerabilities,
    ):
        """Should load vulnerabilities for detail pages"""
        mock_loader = Mock()
        mock_loader.load_latest_metrics.return_value = sample_security_products
        mock_loader_class.return_value = mock_loader

        mock_vuln_loader = Mock()
        mock_vuln_loader.load_vulnerabilities_for_products.return_value = sample_vulnerabilities
        mock_vuln_loader.group_by_product.return_value = {
            "Web Application": sample_vulnerabilities,
            "Mobile App": sample_vulnerabilities,
            "API Gateway": sample_vulnerabilities,
        }
        mock_vuln_loader.get_product_ids.return_value = {
            "Web Application": "prod-001",
            "Mobile App": "prod-002",
            "API Gateway": "prod-003",
        }
        mock_vuln_loader_class.return_value = mock_vuln_loader

        mock_framework.return_value = ("<style></style>", "<script></script>")
        mock_detail_generator.return_value = "<html>Detail with vulns</html>"

        generate_security_dashboard_enhanced()

        # No longer generates detail pages (using expandable rows instead)
        assert mock_detail_generator.call_count == 0


class TestGenerateSecurityDashboardEnhanced:
    """Tests for full dashboard generation"""

    @patch("execution.dashboards.security_enhanced.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security_enhanced.ArmorCodeLoader")
    @patch("execution.dashboards.security_enhanced.get_dashboard_framework")
    @patch("execution.dashboards.security_enhanced.generate_product_detail_page")
    @patch("pathlib.Path.write_text")
    def test_generate_dashboard_success(
        self,
        mock_write,
        mock_detail,
        mock_framework,
        mock_loader_class,
        mock_vuln_loader_class,
        sample_security_products,
        sample_vulnerabilities,
    ):
        """Should generate complete dashboard HTML"""
        mock_loader = Mock()
        mock_loader.load_latest_metrics.return_value = sample_security_products
        mock_loader_class.return_value = mock_loader

        mock_vuln_loader = Mock()
        mock_vuln_loader.load_vulnerabilities_for_products.return_value = sample_vulnerabilities
        mock_vuln_loader.group_by_product.return_value = {
            "Web Application": sample_vulnerabilities,
            "Mobile App": sample_vulnerabilities,
            "API Gateway": sample_vulnerabilities,
        }
        mock_vuln_loader.get_product_ids.return_value = {
            "Web Application": "prod-001",
            "Mobile App": "prod-002",
            "API Gateway": "prod-003",
        }
        mock_vuln_loader_class.return_value = mock_vuln_loader

        mock_framework.return_value = ("<style>.card{}</style>", "<script></script>")
        mock_detail.return_value = "<html></html>"

        html, count = generate_security_dashboard_enhanced()

        assert isinstance(html, str)
        assert len(html) > 0
        assert count == 0  # No detail pages (using expandable rows)
        assert "Web Application" in html

    @patch("execution.dashboards.security_enhanced.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security_enhanced.ArmorCodeLoader")
    @patch("execution.dashboards.security_enhanced.get_dashboard_framework")
    @patch("execution.dashboards.security_enhanced.generate_product_detail_page")
    @patch("pathlib.Path.write_text")
    def test_write_to_output_directory(
        self,
        mock_write,
        mock_detail,
        mock_framework,
        mock_loader_class,
        mock_vuln_loader_class,
        sample_security_products,
        sample_vulnerabilities,
        tmp_path,
    ):
        """Should write HTML to specified output directory"""
        mock_loader = Mock()
        mock_loader.load_latest_metrics.return_value = sample_security_products
        mock_loader_class.return_value = mock_loader

        mock_vuln_loader = Mock()
        mock_vuln_loader.load_vulnerabilities_for_products.return_value = sample_vulnerabilities
        mock_vuln_loader.group_by_product.return_value = {
            "Web Application": sample_vulnerabilities,
            "Mobile App": sample_vulnerabilities,
            "API Gateway": sample_vulnerabilities,
        }
        mock_vuln_loader.get_product_ids.return_value = {
            "Web Application": "prod-001",
            "Mobile App": "prod-002",
            "API Gateway": "prod-003",
        }
        mock_vuln_loader_class.return_value = mock_vuln_loader

        mock_framework.return_value = ("<style></style>", "<script></script>")
        mock_detail.return_value = "<html></html>"

        output_dir = tmp_path / "dashboards"

        html, count = generate_security_dashboard_enhanced(output_dir)
        # Should have written main dashboard only (no detail pages)
        assert mock_write.call_count == 1  # Only main dashboard

    @patch("execution.dashboards.security_enhanced.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security_enhanced.ArmorCodeLoader")
    @patch("execution.dashboards.security_enhanced.get_dashboard_framework")
    @patch("execution.dashboards.security_enhanced.generate_product_detail_page")
    @patch("pathlib.Path.write_text")
    def test_handles_missing_data_gracefully(
        self, mock_write, mock_detail, mock_framework, mock_loader_class, mock_vuln_loader_class
    ):
        """Should handle missing optional fields in product data"""
        incomplete_product = {
            "Incomplete Product": SecurityMetrics(
                timestamp=datetime.now(),
                project="Incomplete Product",
                total_vulnerabilities=10,
                critical=0,
                high=0,
                # medium and low have defaults of 0
            )
        }

        mock_loader = Mock()
        mock_loader.load_latest_metrics.return_value = incomplete_product
        mock_loader_class.return_value = mock_loader

        mock_vuln_loader = Mock()
        mock_vuln_loader.load_vulnerabilities_for_products.return_value = []
        mock_vuln_loader.group_by_product.return_value = {"Incomplete Product": []}
        mock_vuln_loader.get_product_ids.return_value = {"Incomplete Product": "prod-999"}
        mock_vuln_loader_class.return_value = mock_vuln_loader

        mock_framework.return_value = ("<style></style>", "<script></script>")
        mock_detail.return_value = "<html></html>"

        # Should not raise exception
        html, count = generate_security_dashboard_enhanced()
        assert count == 0  # No detail pages generated (using expandable rows instead)
