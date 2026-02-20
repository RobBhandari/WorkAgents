"""
Tests for Security Dashboard Generator

Tests cover:
- Data loading from ArmorCodeLoader
- Summary calculation (totals, by severity, by product)
- Summary card generation
- Product row generation with status determination
- Context building (framework CSS/JS included)
- Dashboard HTML rendering
- Heatmap generation (aging distribution)
- Vulnerability breakdown generation
- Error handling (missing data files)
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

from execution.dashboards.security import (
    _build_context,
    _build_product_rows,
    _build_summary_cards,
    _calculate_summary,
    _generate_aging_heatmap_estimated,
    _generate_heatmap_cell,
    _generate_product_details,
    _generate_vulnerability_breakdown,
    generate_security_dashboard,
)
from execution.domain.security import SecurityMetrics


@pytest.fixture
def sample_security_metrics():
    """Sample security metrics by product for testing"""
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
def sample_single_product():
    """Single product for detailed testing"""
    return SecurityMetrics(
        timestamp=datetime(2026, 2, 7),
        project="Test Product",
        total_vulnerabilities=30,
        critical=3,
        high=8,
        medium=15,
        low=4,
    )


class TestCalculateSummary:
    """Test _calculate_summary function"""

    def test_calculate_summary_totals(self, sample_security_metrics):
        """Test summary calculation with multiple products"""
        summary = _calculate_summary(sample_security_metrics)

        assert summary["total_vulnerabilities"] == 80  # 45 + 23 + 12
        assert summary["total_critical"] == 7  # 5 + 2 + 0
        assert summary["total_high"] == 20  # 12 + 6 + 2
        assert summary["total_medium"] == 37  # 20 + 10 + 7
        assert summary["total_low"] == 16  # 8 + 5 + 3

    def test_calculate_summary_critical_high_total(self, sample_security_metrics):
        """Test critical+high combined total"""
        summary = _calculate_summary(sample_security_metrics)

        assert summary["critical_high_total"] == 27  # 7 + 20

    def test_calculate_summary_products_with_critical(self, sample_security_metrics):
        """Test count of products with critical vulnerabilities"""
        summary = _calculate_summary(sample_security_metrics)

        # Web Application (5) and Mobile App (2) have critical
        assert summary["products_with_critical"] == 2

    def test_calculate_summary_products_with_high(self, sample_security_metrics):
        """Test count of products with high vulnerabilities"""
        summary = _calculate_summary(sample_security_metrics)

        # All 3 products have high vulnerabilities
        assert summary["products_with_high"] == 3

    def test_calculate_summary_product_count(self, sample_security_metrics):
        """Test product count"""
        summary = _calculate_summary(sample_security_metrics)

        assert summary["product_count"] == 3

    def test_calculate_summary_empty_dict(self):
        """Test summary calculation with empty metrics"""
        summary = _calculate_summary({})

        assert summary["total_vulnerabilities"] == 0
        assert summary["total_critical"] == 0
        assert summary["total_high"] == 0
        assert summary["critical_high_total"] == 0
        assert summary["product_count"] == 0

    def test_calculate_summary_zero_vulnerabilities(self):
        """Test products with zero vulnerabilities"""
        metrics = {
            "Clean Product": SecurityMetrics(
                timestamp=datetime.now(),
                project="Clean Product",
                total_vulnerabilities=0,
                critical=0,
                high=0,
                medium=0,
                low=0,
            )
        }

        summary = _calculate_summary(metrics)

        assert summary["total_vulnerabilities"] == 0
        assert summary["products_with_critical"] == 0
        assert summary["products_with_high"] == 0


class TestBuildSummaryCards:
    """Test _build_summary_cards function"""

    def test_build_summary_cards_count(self):
        """Test that 4 summary cards are generated"""
        summary_stats = {
            "total_vulnerabilities": 80,
            "total_critical": 7,
            "total_high": 20,
            "critical_high_total": 27,
            "products_with_critical": 2,
            "products_with_high": 3,
            "product_count": 3,
        }

        cards = _build_summary_cards(summary_stats)

        assert len(cards) == 4

    def test_build_summary_cards_total_vulnerabilities(self):
        """Test priority findings card content (Critical + High)"""
        summary_stats = {
            "total_vulnerabilities": 80,
            "total_critical": 7,
            "total_high": 20,
            "critical_high_total": 27,
            "products_with_critical": 2,
            "products_with_high": 3,
            "product_count": 3,
        }

        cards = _build_summary_cards(summary_stats)

        # First card should be priority findings (Critical + High)
        assert "Priority Findings" in cards[0]
        assert "27" in cards[0]
        assert "Critical + High severity" in cards[0]

    def test_build_summary_cards_critical_red_when_present(self):
        """Test critical card is red when critical vulns exist"""
        summary_stats = {
            "total_vulnerabilities": 80,
            "total_critical": 7,
            "total_high": 20,
            "critical_high_total": 27,
            "products_with_critical": 2,
            "products_with_high": 3,
            "product_count": 3,
        }

        cards = _build_summary_cards(summary_stats)

        # Critical card should have rag-red class
        assert "rag-red" in cards[1]
        assert "7" in cards[1]

    def test_build_summary_cards_critical_green_when_zero(self):
        """Test critical card is green when no critical vulns"""
        summary_stats = {
            "total_vulnerabilities": 30,
            "total_critical": 0,
            "total_high": 10,
            "critical_high_total": 10,
            "products_with_critical": 0,
            "products_with_high": 2,
            "product_count": 2,
        }

        cards = _build_summary_cards(summary_stats)

        # Critical card should have rag-green class
        assert "rag-green" in cards[1]

    def test_build_summary_cards_high_amber_threshold(self):
        """Test high card is amber when > 5 high vulns"""
        summary_stats = {
            "total_vulnerabilities": 80,
            "total_critical": 0,
            "total_high": 20,
            "critical_high_total": 20,
            "products_with_critical": 0,
            "products_with_high": 3,
            "product_count": 3,
        }

        cards = _build_summary_cards(summary_stats)

        # High card should have rag-amber class (20 > 5)
        assert "rag-amber" in cards[2]

    def test_build_summary_cards_high_green_threshold(self):
        """Test high card is green when <= 5 high vulns"""
        summary_stats = {
            "total_vulnerabilities": 20,
            "total_critical": 0,
            "total_high": 3,
            "critical_high_total": 3,
            "products_with_critical": 0,
            "products_with_high": 1,
            "product_count": 1,
        }

        cards = _build_summary_cards(summary_stats)

        # High card should have rag-green class (3 <= 5)
        assert "rag-green" in cards[2]


class TestBuildProductRows:
    """Test _build_product_rows function"""

    @patch("execution.dashboards.security._generate_product_details")
    def test_build_product_rows_count(self, mock_details, sample_security_metrics):
        """Test correct number of product rows"""
        mock_details.return_value = "<div>Product details</div>"

        rows = _build_product_rows(sample_security_metrics)

        assert len(rows) == 3

    @patch("execution.dashboards.security._generate_product_details")
    def test_build_product_rows_content(self, mock_details, sample_security_metrics):
        """Test product row content"""
        mock_details.return_value = "<div>Product details</div>"

        rows = _build_product_rows(sample_security_metrics)

        # Find API Gateway row
        api_row = next(r for r in rows if r["name"] == "API Gateway")

        assert api_row["total"] == 12
        assert api_row["critical"] == 0
        assert api_row["high"] == 2
        assert api_row["medium"] == 7

    @patch("execution.dashboards.security._generate_product_details")
    def test_build_product_rows_status_critical(self, mock_details, sample_security_metrics):
        """Test status for product with critical vulnerabilities"""
        mock_details.return_value = "<div>Product details</div>"

        rows = _build_product_rows(sample_security_metrics)

        # Web Application has 5 critical
        web_row = next(r for r in rows if r["name"] == "Web Application")

        assert web_row["status"] == "Critical"
        assert web_row["status_class"] == "action"

    @patch("execution.dashboards.security._generate_product_details")
    def test_build_product_rows_status_high_risk(self, mock_details):
        """Test status for product with > 5 high vulnerabilities"""
        mock_details.return_value = "<div>Product details</div>"

        metrics = {
            "High Risk Product": SecurityMetrics(
                timestamp=datetime.now(),
                project="High Risk Product",
                total_vulnerabilities=20,
                critical=0,
                high=8,
                medium=10,
                low=2,
            )
        }

        rows = _build_product_rows(metrics)

        assert rows[0]["status"] == "High Risk"
        assert rows[0]["status_class"] == "caution"

    @patch("execution.dashboards.security._generate_product_details")
    def test_build_product_rows_status_attention(self, mock_details):
        """Test status for product with 1-5 high vulnerabilities"""
        mock_details.return_value = "<div>Product details</div>"

        metrics = {
            "Attention Product": SecurityMetrics(
                timestamp=datetime.now(),
                project="Attention Product",
                total_vulnerabilities=10,
                critical=0,
                high=3,
                medium=5,
                low=2,
            )
        }

        rows = _build_product_rows(metrics)

        assert rows[0]["status"] == "Attention"
        assert rows[0]["status_class"] == "caution"

    @patch("execution.dashboards.security._generate_product_details")
    def test_build_product_rows_status_good(self, mock_details, sample_security_metrics):
        """Test status for product with no critical/high vulnerabilities"""
        mock_details.return_value = "<div>Product details</div>"

        # API Gateway has 0 critical, 2 high - but let's test with clean product
        metrics = {
            "Clean Product": SecurityMetrics(
                timestamp=datetime.now(),
                project="Clean Product",
                total_vulnerabilities=5,
                critical=0,
                high=0,
                medium=3,
                low=2,
            )
        }

        rows = _build_product_rows(metrics)

        assert rows[0]["status"] == "Good"
        assert rows[0]["status_class"] == "good"

    @patch("execution.dashboards.security._generate_product_details")
    def test_build_product_rows_expandable_enabled(self, mock_details, sample_security_metrics):
        """Test that rows have expandable details"""
        mock_details.return_value = "<div>Product details</div>"

        rows = _build_product_rows(sample_security_metrics)

        for row in rows:
            assert row["expandable"] is True
            assert "details" in row
            assert isinstance(row["details"], str)

    @patch("execution.dashboards.security._generate_product_details")
    def test_build_product_rows_sorted_alphabetically(self, mock_details, sample_security_metrics):
        """Test that products are sorted alphabetically"""
        mock_details.return_value = "<div>Product details</div>"

        rows = _build_product_rows(sample_security_metrics)

        names = [row["name"] for row in rows]
        assert names == sorted(names)


class TestGenerateHeatmapCell:
    """Test _generate_heatmap_cell function"""

    @patch("execution.dashboards.security.render_template")
    def test_heatmap_cell_zero_count(self, mock_render):
        """Test cell with zero count (empty cell)"""
        mock_render.return_value = '<div style="background: rgba(148, 163, 184, 0.1)"></div>'

        html = _generate_heatmap_cell(0, 0.0, "critical")

        # Verify render_template was called with correct parameters
        mock_render.assert_called_once()
        call_args = mock_render.call_args[1]
        assert "rgba(148, 163, 184, 0.1)" in call_args["bg_color"]

    @patch("execution.dashboards.security.render_template")
    def test_heatmap_cell_critical_low_intensity(self, mock_render):
        """Test critical cell with low intensity"""
        mock_render.return_value = '<div style="background: rgba(239, 68, 68, 0.3)">2</div>'

        html = _generate_heatmap_cell(2, 0.2, "critical")

        # Verify render_template was called
        mock_render.assert_called_once()
        call_args = mock_render.call_args[1]
        assert "239, 68, 68" in call_args["bg_color"]
        assert call_args["display_value"] == "2"

    @patch("execution.dashboards.security.render_template")
    def test_heatmap_cell_critical_high_intensity(self, mock_render):
        """Test critical cell with high intensity"""
        mock_render.return_value = '<div style="background: rgba(220, 38, 38, 0.9)">10</div>'

        html = _generate_heatmap_cell(10, 0.9, "critical")

        # Verify render_template was called
        mock_render.assert_called_once()
        call_args = mock_render.call_args[1]
        assert "220, 38, 38" in call_args["bg_color"]
        assert call_args["display_value"] == "10"

    @patch("execution.dashboards.security.render_template")
    def test_heatmap_cell_high_low_intensity(self, mock_render):
        """Test high severity cell with low intensity"""
        mock_render.return_value = '<div style="background: rgba(251, 146, 60, 0.3)">3</div>'

        html = _generate_heatmap_cell(3, 0.3, "high")

        # Verify render_template was called
        mock_render.assert_called_once()
        call_args = mock_render.call_args[1]
        assert "251, 146, 60" in call_args["bg_color"] or "249, 115, 22" in call_args["bg_color"]
        assert call_args["display_value"] == "3"

    @patch("execution.dashboards.security.render_template")
    def test_heatmap_cell_high_high_intensity(self, mock_render):
        """Test high severity cell with high intensity"""
        mock_render.return_value = '<div style="background: rgba(234, 88, 12, 0.9)">8</div>'

        html = _generate_heatmap_cell(8, 0.8, "high")

        # Verify render_template was called
        mock_render.assert_called_once()
        call_args = mock_render.call_args[1]
        assert "234, 88, 12" in call_args["bg_color"] or "249, 115, 22" in call_args["bg_color"]
        assert call_args["display_value"] == "8"


class TestGenerateAgingHeatmapEstimated:
    """Test _generate_aging_heatmap_estimated function"""

    @patch("execution.dashboards.security.render_template")
    def test_aging_heatmap_with_vulnerabilities(self, mock_render, sample_single_product):
        """Test heatmap generation with vulnerabilities"""
        mock_render.return_value = "<div>Heatmap HTML</div>"

        html = _generate_aging_heatmap_estimated(sample_single_product)

        # Should contain heatmap structure
        assert isinstance(html, str)
        assert len(html) > 0

    @patch("execution.dashboards.security.render_template")
    def test_aging_heatmap_zero_vulnerabilities(self, mock_render):
        """Test heatmap with zero vulnerabilities"""
        mock_render.return_value = "<div>Heatmap HTML</div>"

        metrics = SecurityMetrics(
            timestamp=datetime.now(),
            project="Clean",
            total_vulnerabilities=0,
            critical=0,
            high=0,
            medium=0,
            low=0,
        )

        html = _generate_aging_heatmap_estimated(metrics)

        # Should still generate valid HTML
        assert isinstance(html, str)
        assert len(html) > 0

    @patch("execution.dashboards.security.render_template")
    def test_aging_heatmap_critical_only(self, mock_render):
        """Test heatmap with only critical vulnerabilities"""
        mock_render.return_value = "<div>Heatmap HTML</div>"

        metrics = SecurityMetrics(
            timestamp=datetime.now(),
            project="Critical Only",
            total_vulnerabilities=10,
            critical=10,
            high=0,
            medium=0,
            low=0,
        )

        html = _generate_aging_heatmap_estimated(metrics)

        # Should generate heatmap
        assert isinstance(html, str)
        assert len(html) > 0


class TestGenerateVulnerabilityBreakdown:
    """Test _generate_vulnerability_breakdown function"""

    @patch("execution.dashboards.security.render_template")
    def test_vulnerability_breakdown_with_data(self, mock_render, sample_single_product):
        """Test breakdown generation with vulnerability data"""
        mock_render.return_value = "<div>Breakdown HTML</div>"

        html = _generate_vulnerability_breakdown(sample_single_product)

        assert isinstance(html, str)
        assert len(html) > 0
        mock_render.assert_called_once()

    @patch("execution.dashboards.security.render_template")
    def test_vulnerability_breakdown_percentages(self, mock_render, sample_single_product):
        """Test that percentages are calculated correctly"""
        mock_render.return_value = "<div>10.0%, 26.7%, 50.0%, 13.3%</div>"

        html = _generate_vulnerability_breakdown(sample_single_product)

        # Verify render_template was called with correct calculations
        mock_render.assert_called_once()
        call_args = mock_render.call_args[1]
        # Total = 30, Critical = 3 (10%), High = 8 (26.7%), Medium = 15 (50%), Low = 4 (13.3%)
        assert call_args["critical_pct"] == "10.0"
        assert call_args["high_pct"] == "26.7"
        assert call_args["medium_pct"] == "50.0"
        assert call_args["low_pct"] == "13.3"

    @patch("execution.dashboards.security.render_template")
    def test_vulnerability_breakdown_zero_vulnerabilities(self, mock_render):
        """Test breakdown with zero vulnerabilities"""
        mock_render.return_value = "<div>0.0%</div>"

        metrics = SecurityMetrics(
            timestamp=datetime.now(),
            project="Clean",
            total_vulnerabilities=0,
            critical=0,
            high=0,
            medium=0,
            low=0,
        )

        html = _generate_vulnerability_breakdown(metrics)

        # Verify all percentages are 0.0
        call_args = mock_render.call_args[1]
        assert call_args["critical_pct"] == "0.0"
        assert call_args["high_pct"] == "0.0"
        assert call_args["medium_pct"] == "0.0"
        assert call_args["low_pct"] == "0.0"


class TestGenerateProductDetails:
    """Test _generate_product_details function"""

    @patch("execution.dashboards.security.render_template")
    def test_generate_product_details_structure(self, mock_render, sample_single_product):
        """Test product details HTML structure"""
        # Mock returns for ALL render_template calls including heatmap cells
        # Aging heatmap needs ~10 cells (5 age buckets x 2 severity levels)
        mock_render.return_value = "<div>Mock HTML</div>"

        html = _generate_product_details("Test Product", sample_single_product)

        assert isinstance(html, str)
        assert len(html) > 0

    @patch("execution.dashboards.security.render_template")
    def test_generate_product_details_contains_heatmap(self, mock_render, sample_single_product):
        """Test that product details include heatmap"""
        mock_render.return_value = "<div>Mock HTML</div>"

        html = _generate_product_details("Test Product", sample_single_product)

        # Should be generated
        assert isinstance(html, str)
        # Verify render_template was called multiple times
        assert mock_render.call_count >= 3

    @patch("execution.dashboards.security.render_template")
    def test_generate_product_details_contains_breakdown(self, mock_render, sample_single_product):
        """Test that product details include breakdown"""
        mock_render.return_value = "<div>Mock HTML</div>"

        html = _generate_product_details("Test Product", sample_single_product)

        # Should be generated
        assert isinstance(html, str)
        assert mock_render.call_count >= 3


class TestBuildContext:
    """Test _build_context function"""

    @patch("execution.dashboards.security.render_template")
    def test_build_context_structure(self, mock_render, sample_security_metrics):
        """Test context dictionary structure"""
        # Mock all nested template calls
        mock_render.return_value = "<div>Mock HTML</div>"

        summary_stats = _calculate_summary(sample_security_metrics)
        context = _build_context(sample_security_metrics, summary_stats)

        required_keys = [
            "framework_css",
            "framework_js",
            "generation_date",
            "summary_cards",
            "products",
            "show_glossary",
        ]

        for key in required_keys:
            assert key in context

    @patch("execution.dashboards.security.render_template")
    def test_build_context_framework_included(self, mock_render, sample_security_metrics):
        """Test that framework CSS and JS are included"""
        mock_render.return_value = "<div>Mock HTML</div>"

        summary_stats = _calculate_summary(sample_security_metrics)
        context = _build_context(sample_security_metrics, summary_stats)

        assert isinstance(context["framework_css"], str)
        assert isinstance(context["framework_js"], str)
        assert len(context["framework_css"]) > 0
        assert len(context["framework_js"]) > 0

    @patch("execution.dashboards.security.render_template")
    def test_build_context_generation_date(self, mock_render, sample_security_metrics):
        """Test generation date is formatted correctly"""
        mock_render.return_value = "<div>Mock HTML</div>"

        summary_stats = _calculate_summary(sample_security_metrics)
        context = _build_context(sample_security_metrics, summary_stats)

        assert isinstance(context["generation_date"], str)
        # Should be in YYYY-MM-DD HH:MM:SS format
        assert "-" in context["generation_date"]
        assert ":" in context["generation_date"]

    @patch("execution.dashboards.security.render_template")
    def test_build_context_summary_cards(self, mock_render, sample_security_metrics):
        """Test summary cards are included"""
        mock_render.return_value = "<div>Mock HTML</div>"

        summary_stats = _calculate_summary(sample_security_metrics)
        context = _build_context(sample_security_metrics, summary_stats)

        assert isinstance(context["summary_cards"], list)
        assert len(context["summary_cards"]) == 4

    @patch("execution.dashboards.security.render_template")
    def test_build_context_products(self, mock_render, sample_security_metrics):
        """Test products are included"""
        mock_render.return_value = "<div>Mock HTML</div>"

        summary_stats = _calculate_summary(sample_security_metrics)
        context = _build_context(sample_security_metrics, summary_stats)

        assert isinstance(context["products"], list)
        assert len(context["products"]) == 3

    @patch("execution.dashboards.security.render_template")
    def test_build_context_glossary_enabled(self, mock_render, sample_security_metrics):
        """Test glossary is enabled"""
        mock_render.return_value = "<div>Mock HTML</div>"

        summary_stats = _calculate_summary(sample_security_metrics)
        context = _build_context(sample_security_metrics, summary_stats)

        assert context["show_glossary"] is True


def _setup_loader_mock(mock_loader_class, products, critical=None, high=None):
    """Helper: configure ArmorCodeVulnerabilityLoader mock for AQL count approach."""
    mock_loader = Mock()
    # get_product_ids returns {name -> id}
    mock_loader.get_product_ids.return_value = {p: f"id_{i}" for i, p in enumerate(products)}
    # count_by_severity_aql returns {product_id -> count}; default all zeros
    critical_counts = critical or {f"id_{i}": 0 for i in range(len(products))}
    high_counts = high or {f"id_{i}": 0 for i in range(len(products))}
    mock_loader.count_by_severity_aql.side_effect = [critical_counts, high_counts]
    mock_loader_class.return_value = mock_loader
    return mock_loader


class TestGenerateSecurityDashboard:
    """Test generate_security_dashboard function"""

    @patch("execution.dashboards.security.render_template")
    @patch("execution.dashboards.security.render_dashboard")
    @patch("execution.dashboards.security.get_config")
    @patch("execution.dashboards.security.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security._load_baseline_products")
    def test_generate_dashboard_success(
        self,
        mock_load_baseline,
        mock_loader_class,
        mock_get_config,
        mock_render,
        mock_template,
        sample_security_metrics,
    ):
        """Test successful dashboard generation using AQL count endpoint"""
        mock_load_baseline.return_value = ["Product1", "Product2"]
        mock_get_config.return_value.get_optional_env.return_value = "test/hierarchy"
        _setup_loader_mock(mock_loader_class, ["Product1", "Product2"])
        mock_template.return_value = "<div>Mock HTML</div>"
        mock_render.return_value = "<html>Security Dashboard</html>"

        html = generate_security_dashboard()

        mock_load_baseline.assert_called_once()
        mock_render.assert_called_once()
        assert html == "<html>Security Dashboard</html>"

    @patch("execution.dashboards.security.render_template")
    @patch("execution.dashboards.security.render_dashboard")
    @patch("execution.dashboards.security.get_config")
    @patch("execution.dashboards.security.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security._load_baseline_products")
    def test_generate_dashboard_with_output_path(
        self,
        mock_load_baseline,
        mock_loader_class,
        mock_get_config,
        mock_render,
        mock_template,
        sample_security_metrics,
        tmp_path,
    ):
        """Test dashboard generation with file output"""
        mock_load_baseline.return_value = ["Product1"]
        mock_get_config.return_value.get_optional_env.return_value = "test/hierarchy"
        _setup_loader_mock(mock_loader_class, ["Product1"])
        mock_template.return_value = "<div>Mock HTML</div>"
        mock_render.return_value = "<html>Security Dashboard</html>"

        output_path = tmp_path / "security.html"
        html = generate_security_dashboard(output_path)

        assert output_path.exists()
        assert output_path.read_text(encoding="utf-8") == "<html>Security Dashboard</html>"

    @patch("execution.dashboards.security._load_baseline_products")
    def test_generate_dashboard_file_not_found(self, mock_load_baseline):
        """Test dashboard generation with missing baseline file"""
        mock_load_baseline.side_effect = FileNotFoundError("Baseline not found")

        with pytest.raises(FileNotFoundError, match="Baseline not found"):
            generate_security_dashboard()

    @patch("execution.dashboards.security.render_dashboard")
    @patch("execution.dashboards.security.get_config")
    @patch("execution.dashboards.security.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security._load_baseline_products")
    def test_generate_dashboard_empty_products(
        self, mock_load_baseline, mock_loader_class, mock_get_config, mock_render
    ):
        """Test dashboard generation with no vulnerabilities returns zero counts"""
        mock_load_baseline.return_value = ["Product1"]
        mock_get_config.return_value.get_optional_env.return_value = "test/hierarchy"
        _setup_loader_mock(mock_loader_class, ["Product1"])
        mock_render.return_value = "<html>Empty Dashboard</html>"

        html = generate_security_dashboard()

        assert html == "<html>Empty Dashboard</html>"

    @patch("execution.dashboards.security.render_template")
    @patch("execution.dashboards.security.render_dashboard")
    @patch("execution.dashboards.security.get_config")
    @patch("execution.dashboards.security.ArmorCodeVulnerabilityLoader")
    @patch("execution.dashboards.security._load_baseline_products")
    def test_generate_dashboard_creates_parent_directory(
        self,
        mock_load_baseline,
        mock_loader_class,
        mock_get_config,
        mock_render,
        mock_template,
        sample_security_metrics,
        tmp_path,
    ):
        """Test that parent directories are created if needed"""
        mock_load_baseline.return_value = ["Product1"]
        mock_get_config.return_value.get_optional_env.return_value = "test/hierarchy"
        _setup_loader_mock(mock_loader_class, ["Product1"])
        mock_template.return_value = "<div>Mock HTML</div>"
        mock_render.return_value = "<html>Security Dashboard</html>"

        output_path = tmp_path / "nested" / "directories" / "security.html"
        html = generate_security_dashboard(output_path)

        assert output_path.parent.exists()
        assert output_path.exists()


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    @patch("execution.dashboards.security._generate_product_details")
    def test_product_with_only_critical(self, mock_details):
        """Test product with only critical vulnerabilities"""
        mock_details.return_value = "<div>Product details</div>"

        metrics = {
            "Critical Only": SecurityMetrics(
                timestamp=datetime.now(),
                project="Critical Only",
                total_vulnerabilities=5,
                critical=5,
                high=0,
                medium=0,
                low=0,
            )
        }

        rows = _build_product_rows(metrics)

        assert rows[0]["status"] == "Critical"
        assert rows[0]["critical"] == 5

    def test_product_with_large_numbers(self):
        """Test product with large vulnerability counts"""
        metrics = {
            "Large Product": SecurityMetrics(
                timestamp=datetime.now(),
                project="Large Product",
                total_vulnerabilities=10000,
                critical=500,
                high=2000,
                medium=5000,
                low=2500,
            )
        }

        summary = _calculate_summary(metrics)

        assert summary["total_vulnerabilities"] == 10000
        assert summary["critical_high_total"] == 2500

    def test_multiple_products_same_severity(self):
        """Test multiple products with identical severity counts"""
        metrics = {
            "Product A": SecurityMetrics(
                timestamp=datetime.now(),
                project="Product A",
                total_vulnerabilities=10,
                critical=2,
                high=3,
                medium=3,
                low=2,
            ),
            "Product B": SecurityMetrics(
                timestamp=datetime.now(),
                project="Product B",
                total_vulnerabilities=10,
                critical=2,
                high=3,
                medium=3,
                low=2,
            ),
        }

        summary = _calculate_summary(metrics)

        assert summary["total_vulnerabilities"] == 20
        assert summary["products_with_critical"] == 2

    def test_summary_with_single_product(self):
        """Test summary calculation with single product"""
        metrics = {
            "Solo Product": SecurityMetrics(
                timestamp=datetime.now(),
                project="Solo Product",
                total_vulnerabilities=25,
                critical=3,
                high=7,
                medium=10,
                low=5,
            )
        }

        summary = _calculate_summary(metrics)

        assert summary["product_count"] == 1
        assert summary["total_vulnerabilities"] == 25
        assert summary["critical_high_total"] == 10
