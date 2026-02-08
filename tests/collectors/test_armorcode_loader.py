"""
Tests for ArmorCode Data Loader

Tests cover:
- Loading latest metrics from history file
- Product breakdown aggregation
- File not found error handling
- Invalid JSON handling
- Empty data handling
- Missing fields handling
- load_all_weeks() functionality
- get_product_names() functionality
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from execution.collectors.armorcode_loader import ArmorCodeLoader, load_security_metrics
from execution.domain.security import SecurityMetrics


@pytest.fixture
def security_history_complete():
    """Sample security history with complete data"""
    return {
        "weeks": [
            {
                "week_ending": "2026-01-31",
                "metrics": {
                    "current_total": 120,
                    "critical": 5,
                    "high": 20,
                    "medium": 60,
                    "low": 35,
                    "product_breakdown": {
                        "API Gateway": {"total": 42, "critical": 3, "high": 12, "medium": 20, "low": 7},
                        "Web App": {"total": 38, "critical": 1, "high": 5, "medium": 22, "low": 10},
                        "Mobile App": {"total": 40, "critical": 1, "high": 3, "medium": 18, "low": 18},
                    },
                },
            },
            {
                "week_date": "2026-02-07",
                "metrics": {
                    "current_total": 100,
                    "critical": 3,
                    "high": 15,
                    "medium": 52,
                    "low": 30,
                    "product_breakdown": {
                        "API Gateway": {"total": 35, "critical": 2, "high": 10, "medium": 18, "low": 5},
                        "Web App": {"total": 32, "critical": 1, "high": 3, "medium": 20, "low": 8},
                        "Mobile App": {"total": 33, "critical": 0, "high": 2, "medium": 14, "low": 17},
                    },
                },
            },
        ]
    }


@pytest.fixture
def security_history_minimal():
    """Sample security history with minimal data"""
    return {
        "weeks": [
            {
                "week_date": "2026-02-07",
                "metrics": {
                    "product_breakdown": {
                        "Single Product": {"total": 10, "critical": 1, "high": 2},
                    },
                },
            }
        ]
    }


@pytest.fixture
def temp_history_file(tmp_path):
    """Create a temporary history file path"""
    return tmp_path / "security_history.json"


class TestArmorCodeLoaderInit:
    """Test ArmorCodeLoader initialization"""

    def test_default_history_file_path(self):
        """Test default history file path is set correctly"""
        loader = ArmorCodeLoader()
        assert loader.history_file == Path(".tmp/observatory/security_history.json")

    def test_custom_history_file_path(self, temp_history_file):
        """Test custom history file path is accepted"""
        loader = ArmorCodeLoader(history_file=temp_history_file)
        assert loader.history_file == temp_history_file

    def test_pathlib_path_object(self, temp_history_file):
        """Test that pathlib.Path objects are handled correctly"""
        loader = ArmorCodeLoader(history_file=temp_history_file)
        assert isinstance(loader.history_file, Path)


class TestLoadLatestMetrics:
    """Test loading latest security metrics"""

    def test_load_latest_week_complete_data(self, temp_history_file, security_history_complete):
        """Test loading latest week with complete data"""
        temp_history_file.write_text(json.dumps(security_history_complete))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should have 3 products
        assert len(metrics) == 3
        assert "API Gateway" in metrics
        assert "Web App" in metrics
        assert "Mobile App" in metrics

        # Check API Gateway metrics (latest week: 2026-02-07)
        api_metrics = metrics["API Gateway"]
        assert isinstance(api_metrics, SecurityMetrics)
        assert api_metrics.project == "API Gateway"
        assert api_metrics.total_vulnerabilities == 35
        assert api_metrics.critical == 2
        assert api_metrics.high == 10
        assert api_metrics.medium == 18
        assert api_metrics.low == 5

    def test_load_latest_week_uses_last_entry(self, temp_history_file, security_history_complete):
        """Test that loader uses the last week in the array"""
        temp_history_file.write_text(json.dumps(security_history_complete))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should use values from 2026-02-07 (second week), not 2026-01-31
        api_metrics = metrics["API Gateway"]
        assert api_metrics.total_vulnerabilities == 35  # Not 42 from first week
        assert api_metrics.critical == 2  # Not 3 from first week

    def test_missing_optional_severity_fields(self, temp_history_file):
        """Test loading when optional severity fields are missing"""
        history = {
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "metrics": {
                        "product_breakdown": {
                            "Minimal Product": {
                                "total": 15,
                                "critical": 2,
                                # Missing high, medium, low
                            },
                        },
                    },
                }
            ]
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        product_metrics = metrics["Minimal Product"]
        assert product_metrics.total_vulnerabilities == 15
        assert product_metrics.critical == 2
        assert product_metrics.high == 0  # Should default to 0
        assert product_metrics.medium == 0
        assert product_metrics.low == 0

    def test_timestamp_uses_current_time(self, temp_history_file, security_history_minimal):
        """Test that timestamp is set to current time"""
        temp_history_file.write_text(json.dumps(security_history_minimal))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        before = datetime.now()
        metrics = loader.load_latest_metrics()
        after = datetime.now()

        product_metrics = metrics["Single Product"]
        assert before <= product_metrics.timestamp <= after

    def test_week_date_preferred_over_week_ending(self, temp_history_file):
        """Test that week_date is used if present, otherwise week_ending"""
        history = {
            "weeks": [
                {
                    "week_ending": "2026-01-31",
                    "metrics": {
                        "product_breakdown": {
                            "Product A": {"total": 10, "critical": 1, "high": 2},
                        },
                    },
                },
                {
                    "week_date": "2026-02-07",
                    "week_ending": "2026-02-06",  # This should be ignored
                    "metrics": {
                        "product_breakdown": {
                            "Product B": {"total": 15, "critical": 2, "high": 3},
                        },
                    },
                },
            ]
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        # Should successfully load (week_date takes precedence)
        metrics = loader.load_latest_metrics()
        assert "Product B" in metrics

    def test_zero_vulnerabilities(self, temp_history_file):
        """Test handling products with zero vulnerabilities"""
        history = {
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "metrics": {
                        "product_breakdown": {
                            "Clean Product": {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0},
                        },
                    },
                }
            ]
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        product_metrics = metrics["Clean Product"]
        assert product_metrics.total_vulnerabilities == 0
        assert product_metrics.critical == 0
        assert not product_metrics.has_critical


class TestErrorHandling:
    """Test error handling for various failure scenarios"""

    def test_file_not_found(self, temp_history_file):
        """Test FileNotFoundError when history file doesn't exist"""
        loader = ArmorCodeLoader(history_file=temp_history_file)

        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load_latest_metrics()

        assert "Security history file not found" in str(exc_info.value)
        assert str(temp_history_file) in str(exc_info.value)
        assert "armorcode_weekly_query.py" in str(exc_info.value)  # Help message

    def test_invalid_json(self, temp_history_file):
        """Test JSONDecodeError when file contains invalid JSON"""
        temp_history_file.write_text("{ invalid json }")

        loader = ArmorCodeLoader(history_file=temp_history_file)

        with pytest.raises(json.JSONDecodeError):
            loader.load_latest_metrics()

    def test_missing_weeks_key(self, temp_history_file):
        """Test ValueError when 'weeks' key is missing"""
        history = {"some_other_key": "value"}
        temp_history_file.write_text(json.dumps(history))

        loader = ArmorCodeLoader(history_file=temp_history_file)

        with pytest.raises(ValueError) as exc_info:
            loader.load_latest_metrics()

        assert "No weeks data found" in str(exc_info.value)
        assert "corrupted or empty" in str(exc_info.value)

    def test_empty_weeks_array(self, temp_history_file):
        """Test ValueError when weeks array is empty"""
        history = {"weeks": []}
        temp_history_file.write_text(json.dumps(history))

        loader = ArmorCodeLoader(history_file=temp_history_file)

        with pytest.raises(ValueError) as exc_info:
            loader.load_latest_metrics()

        assert "No weeks data found" in str(exc_info.value)

    def test_missing_metrics_key(self, temp_history_file):
        """Test handling when metrics key is missing"""
        history = {"weeks": [{"week_date": "2026-02-07"}]}
        temp_history_file.write_text(json.dumps(history))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should return empty dict when no product_breakdown
        assert metrics == {}

    def test_missing_product_breakdown(self, temp_history_file):
        """Test handling when product_breakdown is missing"""
        history = {
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "metrics": {
                        "current_total": 50,
                        # No product_breakdown
                    },
                }
            ]
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should return empty dict
        assert metrics == {}

    def test_empty_product_breakdown(self, temp_history_file):
        """Test handling when product_breakdown is empty"""
        history = {"weeks": [{"week_date": "2026-02-07", "metrics": {"product_breakdown": {}}}]}
        temp_history_file.write_text(json.dumps(history))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        # Should return empty dict
        assert metrics == {}


class TestLoadAllWeeks:
    """Test load_all_weeks() functionality"""

    def test_load_all_weeks(self, temp_history_file, security_history_complete):
        """Test loading all weeks of historical data"""
        temp_history_file.write_text(json.dumps(security_history_complete))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        weeks = loader.load_all_weeks()

        assert len(weeks) == 2
        assert weeks[0]["week_ending"] == "2026-01-31"
        assert weeks[1]["week_date"] == "2026-02-07"

    def test_load_all_weeks_empty(self, temp_history_file):
        """Test load_all_weeks with empty weeks array"""
        history = {"weeks": []}
        temp_history_file.write_text(json.dumps(history))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        weeks = loader.load_all_weeks()

        assert weeks == []

    def test_load_all_weeks_file_not_found(self, temp_history_file):
        """Test load_all_weeks raises FileNotFoundError"""
        loader = ArmorCodeLoader(history_file=temp_history_file)

        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load_all_weeks()

        assert str(temp_history_file) in str(exc_info.value)


class TestGetProductNames:
    """Test get_product_names() functionality"""

    def test_get_product_names(self, temp_history_file, security_history_complete):
        """Test getting sorted list of product names"""
        temp_history_file.write_text(json.dumps(security_history_complete))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        products = loader.get_product_names()

        # Should be sorted alphabetically
        assert products == ["API Gateway", "Mobile App", "Web App"]

    def test_get_product_names_empty(self, temp_history_file):
        """Test get_product_names with no products"""
        history = {"weeks": [{"week_date": "2026-02-07", "metrics": {"product_breakdown": {}}}]}
        temp_history_file.write_text(json.dumps(history))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        products = loader.get_product_names()

        assert products == []

    def test_get_product_names_single_product(self, temp_history_file):
        """Test get_product_names with single product"""
        history = {
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "metrics": {"product_breakdown": {"Solo Product": {"total": 5, "critical": 1, "high": 1}}},
                }
            ]
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        products = loader.get_product_names()

        assert products == ["Solo Product"]


class TestConvenienceFunction:
    """Test load_security_metrics() convenience function"""

    def test_convenience_function_default_path(self, security_history_complete, monkeypatch, temp_history_file):
        """Test convenience function with default path"""
        temp_history_file.write_text(json.dumps(security_history_complete))

        # Mock the default path
        monkeypatch.setattr("execution.collectors.armorcode_loader.ArmorCodeLoader.__init__",
                           lambda self, history_file=None: setattr(self, 'history_file', temp_history_file))

        metrics = load_security_metrics(history_file=temp_history_file)

        assert len(metrics) == 3
        assert "API Gateway" in metrics

    def test_convenience_function_custom_path(self, temp_history_file, security_history_minimal):
        """Test convenience function with custom path"""
        temp_history_file.write_text(json.dumps(security_history_minimal))

        metrics = load_security_metrics(history_file=temp_history_file)

        assert len(metrics) == 1
        assert "Single Product" in metrics


class TestLogging:
    """Test logging behavior"""

    @patch("execution.collectors.armorcode_loader.logger")
    def test_logs_on_successful_load(self, mock_logger, temp_history_file, security_history_complete):
        """Test that successful loads are logged"""
        temp_history_file.write_text(json.dumps(security_history_complete))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        loader.load_latest_metrics()

        # Should log loading message
        mock_logger.info.assert_called()
        # Check that it logged with week_ending and product_count
        call_args = mock_logger.info.call_args
        assert "extra" in call_args.kwargs
        assert "week_ending" in call_args.kwargs["extra"]
        assert "product_count" in call_args.kwargs["extra"]
        assert call_args.kwargs["extra"]["product_count"] == 3


class TestDomainModelIntegration:
    """Test integration with SecurityMetrics domain model"""

    def test_security_metrics_properties(self, temp_history_file):
        """Test that SecurityMetrics domain model properties work correctly"""
        history = {
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "metrics": {
                        "product_breakdown": {
                            "Test Product": {"total": 50, "critical": 5, "high": 10, "medium": 20, "low": 15},
                        },
                    },
                }
            ]
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        product_metrics = metrics["Test Product"]

        # Test domain model properties
        assert product_metrics.critical_high_count == 15  # 5 + 10
        assert product_metrics.has_critical is True
        assert product_metrics.has_high is True

    def test_security_metrics_no_critical(self, temp_history_file):
        """Test SecurityMetrics properties when no critical vulnerabilities"""
        history = {
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "metrics": {
                        "product_breakdown": {
                            "Safe Product": {"total": 10, "critical": 0, "high": 2, "medium": 5, "low": 3},
                        },
                    },
                }
            ]
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        product_metrics = metrics["Safe Product"]
        assert product_metrics.has_critical is False
        assert product_metrics.has_high is True
        assert product_metrics.critical_high_count == 2


class TestMultipleProducts:
    """Test scenarios with multiple products"""

    def test_many_products(self, temp_history_file):
        """Test loading many products"""
        products = {f"Product {i}": {"total": i * 5, "critical": i, "high": i * 2} for i in range(1, 11)}

        history = {
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "metrics": {"product_breakdown": products},
                }
            ]
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        assert len(metrics) == 10
        assert "Product 1" in metrics
        assert "Product 10" in metrics
        assert metrics["Product 5"].total_vulnerabilities == 25
        assert metrics["Product 5"].critical == 5

    def test_products_with_special_characters(self, temp_history_file):
        """Test product names with special characters"""
        history = {
            "weeks": [
                {
                    "week_date": "2026-02-07",
                    "metrics": {
                        "product_breakdown": {
                            "Product-API-v2": {"total": 10, "critical": 1, "high": 2},
                            "Product_Web.App": {"total": 15, "critical": 2, "high": 3},
                            "Product (Mobile)": {"total": 20, "critical": 3, "high": 4},
                        },
                    },
                }
            ]
        }
        temp_history_file.write_text(json.dumps(history))

        loader = ArmorCodeLoader(history_file=temp_history_file)
        metrics = loader.load_latest_metrics()

        assert len(metrics) == 3
        assert "Product-API-v2" in metrics
        assert "Product_Web.App" in metrics
        assert "Product (Mobile)" in metrics
