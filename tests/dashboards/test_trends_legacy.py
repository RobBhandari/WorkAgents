"""
Tests for legacy execution/dashboards/trends.py

This file tests the older trends.py implementation (218 lines) which has been
partially replaced by the trends/ subdirectory. These tests aim to achieve 90%+
coverage of the legacy code.
"""

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Import the specific trends.py file (not the trends/ package)
spec = importlib.util.spec_from_file_location(
    "execution.dashboards.trends_legacy", Path(__file__).parent.parent.parent / "execution" / "dashboards" / "trends.py"
)
if spec is None or spec.loader is None:
    raise ImportError("Could not load trends.py module")
trends_legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trends_legacy)

TrendsDashboardGenerator = trends_legacy.TrendsDashboardGenerator
generate_trends_dashboard = trends_legacy.generate_trends_dashboard


@pytest.fixture
def sample_quality_data():
    """Sample quality history data"""
    return {
        "weeks": [
            {
                "week_ending": "2024-01-07",
                "projects": [
                    {
                        "project_name": "Project A",
                        "open_bugs_count": 150,
                        "created_last_week": 10,
                        "closed_last_week": 15,
                    },
                    {
                        "project_name": "Project B",
                        "open_bugs_count": 100,
                        "created_last_week": 5,
                        "closed_last_week": 8,
                    },
                ],
            },
            {
                "week_ending": "2024-01-14",
                "projects": [
                    {
                        "project_name": "Project A",
                        "open_bugs_count": 145,
                        "created_last_week": 8,
                        "closed_last_week": 13,
                    },
                    {
                        "project_name": "Project B",
                        "open_bugs_count": 97,
                        "created_last_week": 3,
                        "closed_last_week": 6,
                    },
                ],
            },
            {
                "week_ending": "2024-01-21",
                "projects": [
                    {
                        "project_name": "Project A",
                        "open_bugs_count": 140,
                        "created_last_week": 7,
                        "closed_last_week": 12,
                    },
                    {
                        "project_name": "Project B",
                        "open_bugs_count": 94,
                        "created_last_week": 2,
                        "closed_last_week": 5,
                    },
                ],
            },
            {
                "week_ending": "2024-01-28",
                "projects": [
                    {
                        "project_name": "Project A",
                        "open_bugs_count": 135,
                        "created_last_week": 6,
                        "closed_last_week": 11,
                    },
                    {
                        "project_name": "Project B",
                        "open_bugs_count": 91,
                        "created_last_week": 1,
                        "closed_last_week": 4,
                    },
                ],
            },
        ]
    }


@pytest.fixture
def sample_security_data():
    """Sample security history data"""
    return {
        "weeks": [
            {
                "week_ending": "2024-01-07",
                "metrics": {"critical": 5, "high": 15, "current_total": 50},
            },
            {
                "week_ending": "2024-01-14",
                "metrics": {"critical": 4, "high": 13, "current_total": 45},
            },
            {
                "week_ending": "2024-01-21",
                "metrics": {"critical": 3, "high": 11, "current_total": 40},
            },
            {
                "week_ending": "2024-01-28",
                "metrics": {"critical": 2, "high": 9, "current_total": 35},
            },
        ]
    }


@pytest.fixture
def sample_flow_data():
    """Sample flow history data"""
    return {
        "weeks": [
            {
                "week_ending": "2024-01-07",
                "projects": [{"project_name": "Project A", "lead_time_p50": 5.5}],
            },
            {
                "week_ending": "2024-01-14",
                "projects": [{"project_name": "Project A", "lead_time_p50": 5.2}],
            },
            {
                "week_ending": "2024-01-21",
                "projects": [{"project_name": "Project A", "lead_time_p50": 4.8}],
            },
            {
                "week_ending": "2024-01-28",
                "projects": [{"project_name": "Project A", "lead_time_p50": 4.5}],
            },
        ]
    }


@pytest.fixture
def sample_baseline_bugs():
    """Sample baseline bugs data"""
    return {"open_count": 500}


@pytest.fixture
def sample_baseline_vulns():
    """Sample baseline vulnerabilities data"""
    return {"total_vulnerabilities": 200}


class TestTrendsDashboardGeneratorInit:
    """Test initialization of TrendsDashboardGenerator"""

    def test_default_initialization(self):
        """Test generator initializes with default values"""
        generator = TrendsDashboardGenerator()
        assert generator.weeks == 12
        assert generator.quality_file.name == "quality_history.json"
        assert generator.security_file.name == "security_history.json"
        assert generator.flow_file.name == "flow_history.json"

    def test_custom_weeks_initialization(self):
        """Test generator initializes with custom weeks"""
        generator = TrendsDashboardGenerator(weeks=8)
        assert generator.weeks == 8


class TestLoadHistoryFile:
    """Test loading history files"""

    def test_load_history_file_success(self, tmp_path, sample_quality_data):
        """Test successful history file loading"""
        generator = TrendsDashboardGenerator()
        file_path = tmp_path / "quality_history.json"
        file_path.write_text(json.dumps(sample_quality_data), encoding="utf-8")

        result = generator._load_history_file(file_path)

        assert result is not None
        assert "weeks" in result
        assert len(result["weeks"]) == 4
        assert "all_weeks" in result

    def test_load_history_file_missing(self, tmp_path):
        """Test loading missing history file"""
        generator = TrendsDashboardGenerator()
        file_path = tmp_path / "nonexistent.json"

        result = generator._load_history_file(file_path)

        assert result is None

    def test_load_history_file_empty_weeks(self, tmp_path):
        """Test loading history file with empty weeks"""
        generator = TrendsDashboardGenerator()
        file_path = tmp_path / "empty.json"
        file_path.write_text(json.dumps({"weeks": []}), encoding="utf-8")

        result = generator._load_history_file(file_path)

        assert result is None

    def test_load_history_file_limits_weeks(self, tmp_path, sample_quality_data):
        """Test loading history file limits to N weeks"""
        generator = TrendsDashboardGenerator(weeks=2)
        file_path = tmp_path / "quality_history.json"
        file_path.write_text(json.dumps(sample_quality_data), encoding="utf-8")

        result = generator._load_history_file(file_path)

        assert result is not None
        assert len(result["weeks"]) == 2  # Only last 2 weeks
        assert len(result["all_weeks"]) == 4  # All weeks preserved

    def test_load_history_file_invalid_json(self, tmp_path):
        """Test loading history file with invalid JSON"""
        generator = TrendsDashboardGenerator()
        file_path = tmp_path / "invalid.json"
        file_path.write_text("not valid json", encoding="utf-8")

        result = generator._load_history_file(file_path)

        assert result is None


class TestLoadAllHistory:
    """Test loading all history files"""

    def test_load_all_history_success(self, tmp_path, sample_quality_data, sample_security_data, sample_flow_data):
        """Test loading all history files successfully"""
        generator = TrendsDashboardGenerator()
        generator.quality_file = tmp_path / "quality_history.json"
        generator.security_file = tmp_path / "security_history.json"
        generator.flow_file = tmp_path / "flow_history.json"

        generator.quality_file.write_text(json.dumps(sample_quality_data), encoding="utf-8")
        generator.security_file.write_text(json.dumps(sample_security_data), encoding="utf-8")
        generator.flow_file.write_text(json.dumps(sample_flow_data), encoding="utf-8")

        result = generator._load_all_history()

        assert "quality" in result
        assert "security" in result
        assert "flow" in result
        assert result["quality"] is not None
        assert result["security"] is not None
        assert result["flow"] is not None

    def test_load_all_history_partial(self, tmp_path, sample_quality_data):
        """Test loading with some files missing"""
        generator = TrendsDashboardGenerator()
        generator.quality_file = tmp_path / "quality_history.json"
        generator.security_file = tmp_path / "nonexistent.json"
        generator.flow_file = tmp_path / "nonexistent2.json"

        generator.quality_file.write_text(json.dumps(sample_quality_data), encoding="utf-8")

        result = generator._load_all_history()

        assert result["quality"] is not None
        assert result["security"] is None
        assert result["flow"] is None


class TestCalculateProgress:
    """Test progress calculation"""

    def test_calc_progress_normal(self):
        """Test normal progress calculation"""
        generator = TrendsDashboardGenerator()
        # Baseline 100, target 30, current 50
        # Need to reduce: 70, achieved: 50
        # Progress: 50/70 = 71.43%
        progress = generator._calc_progress(baseline=100, current=50, target=30)
        assert 71 <= progress <= 72

    def test_calc_progress_complete(self):
        """Test progress when target is met"""
        generator = TrendsDashboardGenerator()
        progress = generator._calc_progress(baseline=100, current=30, target=30)
        assert progress == 100.0

    def test_calc_progress_exceeded(self):
        """Test progress when target is exceeded"""
        generator = TrendsDashboardGenerator()
        progress = generator._calc_progress(baseline=100, current=20, target=30)
        assert progress == 100.0

    def test_calc_progress_no_improvement(self):
        """Test progress when no improvement made"""
        generator = TrendsDashboardGenerator()
        progress = generator._calc_progress(baseline=100, current=100, target=30)
        assert progress == 0.0

    def test_calc_progress_negative(self):
        """Test progress when situation worsened"""
        generator = TrendsDashboardGenerator()
        progress = generator._calc_progress(baseline=100, current=120, target=30)
        assert progress == 0.0  # Clamped to 0

    def test_calc_progress_baseline_at_target(self):
        """Test progress when baseline equals target"""
        generator = TrendsDashboardGenerator()
        progress = generator._calc_progress(baseline=30, current=50, target=30)
        assert progress == 100.0


class TestCalculateBurnRate:
    """Test burn rate calculation"""

    def test_calculate_burn_rate_success(self, sample_quality_data):
        """Test successful burn rate calculation"""
        generator = TrendsDashboardGenerator()
        historical_data = {"quality": sample_quality_data}

        burn_rate = generator._calculate_burn_rate(historical_data)

        # First week: 250 bugs, last week: 226 bugs = 24 reduction over 4 weeks = 6/week
        assert burn_rate == 6

    def test_calculate_burn_rate_no_quality_data(self):
        """Test burn rate with no quality data"""
        generator = TrendsDashboardGenerator()
        historical_data = {"quality": None}

        burn_rate = generator._calculate_burn_rate(historical_data)

        assert burn_rate == 0

    def test_calculate_burn_rate_insufficient_weeks(self):
        """Test burn rate with insufficient weeks"""
        generator = TrendsDashboardGenerator()
        historical_data: dict = {"quality": {"weeks": [{"projects": []}]}}

        burn_rate = generator._calculate_burn_rate(historical_data)

        assert burn_rate == 0

    def test_calculate_burn_rate_increasing(self):
        """Test burn rate when bugs are increasing"""
        generator = TrendsDashboardGenerator()
        historical_data = {
            "quality": {
                "weeks": [
                    {"projects": [{"open_bugs_count": 100}]},
                    {"projects": [{"open_bugs_count": 110}]},
                    {"projects": [{"open_bugs_count": 120}]},
                    {"projects": [{"open_bugs_count": 130}]},
                ]
            }
        }

        burn_rate = generator._calculate_burn_rate(historical_data)

        assert burn_rate == 0  # Returns 0 if increasing


class TestCalculateForecast:
    """Test forecast calculation"""

    def test_calculate_forecast_on_track(
        self, tmp_path, sample_quality_data, sample_security_data, sample_baseline_bugs, sample_baseline_vulns
    ):
        """Test forecast calculation when on track"""
        generator = TrendsDashboardGenerator()
        generator.baseline_bugs_file = tmp_path / "baseline.json"
        generator.baseline_vulns_file = tmp_path / "armorcode_baseline.json"

        generator.baseline_bugs_file.write_text(json.dumps(sample_baseline_bugs), encoding="utf-8")
        generator.baseline_vulns_file.write_text(json.dumps(sample_baseline_vulns), encoding="utf-8")

        historical_data = {"quality": sample_quality_data, "security": sample_security_data}

        forecast = generator._calculate_forecast(historical_data)

        assert forecast is not None
        assert "status" in forecast
        assert "progress" in forecast
        assert "burn_rate" in forecast
        assert "required_rate" in forecast
        assert forecast["status"] in ["On Track", "At Risk", "Off Track"]

    def test_calculate_forecast_missing_quality(self, sample_security_data):
        """Test forecast with missing quality data"""
        generator = TrendsDashboardGenerator()
        historical_data = {"quality": None, "security": sample_security_data}

        forecast = generator._calculate_forecast(historical_data)

        assert forecast is None

    def test_calculate_forecast_missing_security(self, sample_quality_data):
        """Test forecast with missing security data"""
        generator = TrendsDashboardGenerator()
        historical_data = {"quality": sample_quality_data, "security": None}

        forecast = generator._calculate_forecast(historical_data)

        assert forecast is None

    def test_calculate_forecast_missing_baselines(self, tmp_path, sample_quality_data, sample_security_data):
        """Test forecast with missing baseline files"""
        generator = TrendsDashboardGenerator()
        # Point to non-existent files in tmp_path
        generator.baseline_bugs_file = tmp_path / "nonexistent_baseline.json"
        generator.baseline_vulns_file = tmp_path / "nonexistent_armorcode.json"
        historical_data = {"quality": sample_quality_data, "security": sample_security_data}

        forecast = generator._calculate_forecast(historical_data)

        assert forecast is None

    def test_calculate_forecast_at_risk(
        self, tmp_path, sample_quality_data, sample_security_data, sample_baseline_bugs, sample_baseline_vulns
    ):
        """Test forecast calculation when at risk"""
        generator = TrendsDashboardGenerator()
        generator.baseline_bugs_file = tmp_path / "baseline.json"
        generator.baseline_vulns_file = tmp_path / "armorcode_baseline.json"

        # Lower baseline to make progress moderate
        modified_baseline_bugs = {"open_count": 300}
        generator.baseline_bugs_file.write_text(json.dumps(modified_baseline_bugs), encoding="utf-8")
        generator.baseline_vulns_file.write_text(json.dumps(sample_baseline_vulns), encoding="utf-8")

        historical_data = {"quality": sample_quality_data, "security": sample_security_data}

        forecast = generator._calculate_forecast(historical_data)

        assert forecast is not None
        # Should be "At Risk" or "Off Track" depending on exact calculation
        assert forecast["status"] in ["At Risk", "Off Track"]


class TestBuildTrendMetrics:
    """Test building trend metrics"""

    def test_build_trend_metrics_all_data(self, sample_quality_data, sample_security_data, sample_flow_data):
        """Test building trend metrics with all data"""
        generator = TrendsDashboardGenerator()
        historical_data = {
            "quality": sample_quality_data,
            "security": sample_security_data,
            "flow": sample_flow_data,
        }

        metrics = generator._build_trend_metrics(historical_data)

        # Should have: Open Bugs, Critical Vulns, High Vulns, Total Vulns,
        # Lead Time, Bugs Created, Bugs Closed, Net Change
        assert len(metrics) >= 6  # At least 6 metrics
        assert any(m["title"] == "Open Bugs" for m in metrics)
        assert any(m["title"] == "Critical Vulnerabilities" for m in metrics)

    def test_build_trend_metrics_quality_only(self, sample_quality_data):
        """Test building trend metrics with only quality data"""
        generator = TrendsDashboardGenerator()
        historical_data = {"quality": sample_quality_data, "security": None, "flow": None}

        metrics = generator._build_trend_metrics(historical_data)

        # Should have: Open Bugs, Bugs Created, Bugs Closed, Net Change
        assert len(metrics) == 4
        assert all(m["title"] in ["Open Bugs", "Bugs Created", "Bugs Closed", "Net Change"] for m in metrics)

    def test_build_trend_metrics_no_data(self):
        """Test building trend metrics with no data"""
        generator = TrendsDashboardGenerator()
        historical_data = {"quality": None, "security": None, "flow": None}

        metrics = generator._build_trend_metrics(historical_data)

        assert metrics == []


class TestCreateMetricCard:
    """Test creating metric cards"""

    def test_create_metric_card_improving_lower_is_better(self):
        """Test creating metric card for improving trend (lower is better)"""
        generator = TrendsDashboardGenerator()
        values = [100.0, 95.0, 90.0, 85.0]

        card = generator._create_metric_card("Test Metric", values, lower_is_better=True)

        assert card is not None
        assert card["title"] == "Test Metric"
        assert card["current_value"] == "85"
        assert card["change_class"] == "improving"
        assert card["trend_arrow"] == "↓"
        assert "better" in card["change_text"]

    def test_create_metric_card_degrading_lower_is_better(self):
        """Test creating metric card for degrading trend (lower is better)"""
        generator = TrendsDashboardGenerator()
        values = [100.0, 105.0, 110.0, 115.0]

        card = generator._create_metric_card("Test Metric", values, lower_is_better=True)

        assert card is not None
        assert card["change_class"] == "degrading"
        assert card["trend_arrow"] == "↑"
        assert "worse" in card["change_text"]

    def test_create_metric_card_improving_higher_is_better(self):
        """Test creating metric card for improving trend (higher is better)"""
        generator = TrendsDashboardGenerator()
        values = [100.0, 105.0, 110.0, 115.0]

        card = generator._create_metric_card("Test Metric", values, lower_is_better=False)

        assert card is not None
        assert card["change_class"] == "improving"
        assert card["trend_arrow"] == "↑"
        assert "better" in card["change_text"]

    def test_create_metric_card_stable(self):
        """Test creating metric card for stable trend"""
        generator = TrendsDashboardGenerator()
        values = [100.0, 100.0, 100.0, 100.0]

        card = generator._create_metric_card("Test Metric", values, lower_is_better=True)

        assert card is not None
        assert card["change_class"] == "stable"
        assert card["trend_arrow"] == "→"
        assert card["change_text"] == "No change"

    def test_create_metric_card_days_format(self):
        """Test creating metric card with days format"""
        generator = TrendsDashboardGenerator()
        values = [5.5, 5.2, 4.8, 4.5]

        card = generator._create_metric_card("Lead Time", values, lower_is_better=True, format_as="days")

        assert card is not None
        assert "d" in card["current_value"]  # Contains 'd' for days

    def test_create_metric_card_insufficient_values(self):
        """Test creating metric card with insufficient values"""
        generator = TrendsDashboardGenerator()
        values = [100.0]

        card = generator._create_metric_card("Test Metric", values, lower_is_better=True)

        assert card is None

    def test_create_metric_card_empty_values(self):
        """Test creating metric card with empty values"""
        generator = TrendsDashboardGenerator()
        values: list[float] = []

        card = generator._create_metric_card("Test Metric", values, lower_is_better=True)

        assert card is None


class TestBuildContext:
    """Test building template context"""

    def test_build_context_with_forecast(self, sample_quality_data, sample_security_data):
        """Test building context with forecast data"""
        generator = TrendsDashboardGenerator()
        historical_data = {"quality": sample_quality_data, "security": sample_security_data, "flow": None}

        forecast = {
            "status": "On Track",
            "progress": 75.0,
            "burn_rate": 10,
            "required_rate": 8,
        }
        trend_metrics: list[dict] = []

        context = generator._build_context(forecast, trend_metrics, historical_data)

        assert "framework_css" in context
        assert "framework_js" in context
        assert "generation_date" in context
        assert context["forecast"] == forecast
        assert context["trend_metrics"] == trend_metrics
        assert "data_status" in context
        assert len(context["data_status"]) == 3

    def test_build_context_without_forecast(self, sample_quality_data):
        """Test building context without forecast data"""
        generator = TrendsDashboardGenerator()
        historical_data = {"quality": sample_quality_data, "security": None, "flow": None}

        context = generator._build_context(None, [], historical_data)

        assert context["forecast"] is None
        assert context["data_status"][1]["loaded"] is False  # Security not loaded


class TestGenerateDashboard:
    """Test generating the complete dashboard"""

    @patch("execution.dashboards.components.charts.sparkline")
    def test_generate_success(self, mock_sparkline, tmp_path, sample_quality_data, sample_security_data):
        """Test successful dashboard generation"""
        mock_sparkline.return_value = "<svg>sparkline</svg>"

        generator = TrendsDashboardGenerator()
        generator.quality_file = tmp_path / "quality_history.json"
        generator.security_file = tmp_path / "security_history.json"
        generator.flow_file = tmp_path / "flow_history.json"
        generator.baseline_bugs_file = tmp_path / "nonexistent_baseline.json"
        generator.baseline_vulns_file = tmp_path / "nonexistent_vulns.json"

        generator.quality_file.write_text(json.dumps(sample_quality_data), encoding="utf-8")
        generator.security_file.write_text(json.dumps(sample_security_data), encoding="utf-8")

        output_path = tmp_path / "output.html"
        html = generator.generate(output_path)

        assert html is not None
        assert len(html) > 100  # Should be substantial HTML
        assert output_path.exists()
        assert len(output_path.read_text(encoding="utf-8")) > 100

    @patch("execution.dashboards.components.charts.sparkline")
    def test_generate_without_output_path(self, mock_sparkline, tmp_path, sample_quality_data):
        """Test dashboard generation without output path"""
        mock_sparkline.return_value = "<svg>sparkline</svg>"

        generator = TrendsDashboardGenerator()
        generator.quality_file = tmp_path / "quality_history.json"
        generator.security_file = tmp_path / "nonexistent.json"
        generator.flow_file = tmp_path / "nonexistent2.json"
        generator.baseline_bugs_file = tmp_path / "nonexistent_baseline.json"
        generator.baseline_vulns_file = tmp_path / "nonexistent_vulns.json"

        generator.quality_file.write_text(json.dumps(sample_quality_data), encoding="utf-8")

        html = generator.generate()

        assert html is not None
        assert len(html) > 100  # Should be substantial HTML


class TestConvenienceFunction:
    """Test the convenience function"""

    def test_generate_trends_dashboard_default(self, tmp_path, sample_quality_data):
        """Test convenience function with default parameters"""
        # Set up a generator with proper files
        with patch.object(TrendsDashboardGenerator, "__init__", return_value=None):
            with patch.object(TrendsDashboardGenerator, "generate", return_value="<html>Dashboard</html>") as mock_gen:
                html = generate_trends_dashboard()
                assert html == "<html>Dashboard</html>"

    def test_generate_trends_dashboard_custom(self, tmp_path, sample_quality_data):
        """Test convenience function with custom parameters"""
        # Set up a generator with proper files
        with patch.object(TrendsDashboardGenerator, "__init__", return_value=None):
            with patch.object(TrendsDashboardGenerator, "generate", return_value="<html>Dashboard</html>") as mock_gen:
                output_path = tmp_path / "custom.html"
                html = generate_trends_dashboard(output_path, weeks=8)
                assert html == "<html>Dashboard</html>"
