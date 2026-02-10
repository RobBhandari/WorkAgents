"""Tests for TrendsCalculator class"""

from datetime import datetime, timedelta

import pytest

from execution.dashboards.trends.calculator import TrendsCalculator


@pytest.fixture
def sample_baselines():
    """Sample baseline data for target progress calculations"""
    return {"bugs": 300, "security": 500}


@pytest.fixture
def sample_quality_weeks():
    """Sample quality history data with declining bug counts"""
    return [
        {"projects": [{"open_bugs_count": 300}, {"open_bugs_count": 50}]},  # Week 1: 350 bugs
        {"projects": [{"open_bugs_count": 280}, {"open_bugs_count": 45}]},  # Week 2: 325 bugs
        {"projects": [{"open_bugs_count": 260}, {"open_bugs_count": 40}]},  # Week 3: 300 bugs
        {"projects": [{"open_bugs_count": 240}, {"open_bugs_count": 35}]},  # Week 4: 275 bugs
        {"projects": [{"open_bugs_count": 220}, {"open_bugs_count": 30}]},  # Week 5: 250 bugs
        {
            "projects": [
                {"open_bugs_count": 200, "mttr": {"mttr_days": 10}},
                {"open_bugs_count": 25, "mttr": {"mttr_days": 8}},
            ]
        },  # Week 6: 225 bugs
    ]


@pytest.fixture
def sample_security_weeks():
    """Sample security history data with declining vulnerability counts"""
    return [
        {"metrics": {"current_total": 500}},  # Week 1
        {"metrics": {"current_total": 475}},  # Week 2
        {"metrics": {"current_total": 450}},  # Week 3
        {"metrics": {"current_total": 425}},  # Week 4
        {"metrics": {"current_total": 400}},  # Week 5
        {"metrics": {"current_total": 375}},  # Week 6
    ]


@pytest.fixture
def sample_flow_weeks():
    """Sample flow history data with lead time metrics"""
    return [
        {"projects": [{"lead_time": {"p85": 45.5}}, {"lead_time": {"p85": 38.2}}]},
        {"projects": [{"lead_time": {"p85": 42.0}}, {"lead_time": {"p85": 35.8}}]},
        {"projects": [{"lead_time": {"p85": 40.3}}, {"lead_time": {"p85": 33.5}}]},
    ]


@pytest.fixture
def sample_flow_weeks_with_cleanup():
    """Sample flow data with cleanup indicators"""
    return [
        {
            "projects": [
                {
                    "work_type_metrics": {
                        "Feature": {
                            "lead_time": {"p85": 45.5},
                            "dual_metrics": {
                                "indicators": {"is_cleanup_effort": True},
                                "operational": {"p85": 30.0},
                            },
                        }
                    }
                }
            ]
        },
        {
            "projects": [
                {
                    "work_type_metrics": {
                        "Bug": {
                            "lead_time": {"p85": 20.0},
                            "dual_metrics": {"indicators": {"is_cleanup_effort": False}},
                        }
                    }
                }
            ]
        },
    ]


@pytest.fixture
def sample_deployment_weeks():
    """Sample deployment history data"""
    return [
        {
            "projects": [
                {"build_success_rate": {"total_builds": 100, "succeeded": 90}},
                {"build_success_rate": {"total_builds": 50, "succeeded": 45}},
            ]
        },
        {
            "projects": [
                {"build_success_rate": {"total_builds": 100, "succeeded": 92}},
                {"build_success_rate": {"total_builds": 50, "succeeded": 47}},
            ]
        },
    ]


@pytest.fixture
def sample_collaboration_weeks():
    """Sample collaboration history data"""
    return [
        {"projects": [{"pr_merge_time": {"median_hours": 5.5}}, {"pr_merge_time": {"median_hours": 3.2}}]},
        {"projects": [{"pr_merge_time": {"median_hours": 4.8}}, {"pr_merge_time": {"median_hours": 2.9}}]},
    ]


@pytest.fixture
def sample_ownership_weeks():
    """Sample ownership history data"""
    return [
        {
            "projects": [
                {"unassigned": {"total_items": 100, "unassigned_count": 30}},
                {"unassigned": {"total_items": 50, "unassigned_count": 10}},
            ]
        },
        {
            "projects": [
                {"unassigned": {"total_items": 100, "unassigned_count": 25}},
                {"unassigned": {"total_items": 50, "unassigned_count": 8}},
            ]
        },
    ]


@pytest.fixture
def sample_risk_weeks():
    """Sample risk history data"""
    return [
        {"projects": [{"code_churn": {"total_commits": 150}}, {"code_churn": {"total_commits": 75}}]},
        {"projects": [{"code_churn": {"total_commits": 160}}, {"code_churn": {"total_commits": 80}}]},
    ]


class TestTrendsCalculator:
    """Test TrendsCalculator methods"""

    def test_init_with_baselines(self, sample_baselines):
        """Test calculator initialization with baselines"""
        calc = TrendsCalculator(sample_baselines)
        assert calc.baselines == sample_baselines

    def test_init_without_baselines(self):
        """Test calculator initialization without baselines"""
        calc = TrendsCalculator()
        assert calc.baselines == {}

    def test_calculate_target_progress_success(self, sample_baselines, sample_quality_weeks, sample_security_weeks):
        """Test successful target progress calculation"""
        calc = TrendsCalculator(sample_baselines)
        result = calc.calculate_target_progress(sample_quality_weeks, sample_security_weeks)

        assert result is not None
        assert "current" in result
        assert "previous" in result
        assert "trend_data" in result
        assert "unit" in result
        assert "forecast" in result

        # Check forecast details
        forecast = result["forecast"]
        assert "trajectory" in forecast
        assert "trajectory_color" in forecast
        assert "weeks_to_target" in forecast
        assert "required_bugs_burn" in forecast
        assert "required_vulns_burn" in forecast
        assert "actual_bugs_burn" in forecast
        assert "actual_vulns_burn" in forecast
        assert "forecast_msg" in forecast

    def test_calculate_target_progress_no_data(self, sample_baselines):
        """Test target progress with no data"""
        calc = TrendsCalculator(sample_baselines)
        result = calc.calculate_target_progress([], [])
        assert result is None

    def test_calculate_target_progress_positive_trend(
        self, sample_baselines, sample_quality_weeks, sample_security_weeks
    ):
        """Test target progress shows positive trend when metrics improve"""
        calc = TrendsCalculator(sample_baselines)
        result = calc.calculate_target_progress(sample_quality_weeks, sample_security_weeks)

        # Should have positive progress since bugs/vulns are declining
        assert result is not None
        assert result["current"] > 0
        assert len(result["trend_data"]) == 6

    def test_calculate_target_progress_burn_rate_negative(self, sample_baselines):
        """Test target progress when metrics are increasing (negative burn rate)"""
        # Create data where bugs/vulns are INCREASING
        quality_weeks = [
            {"projects": [{"open_bugs_count": 200}]},
            {"projects": [{"open_bugs_count": 210}]},
            {"projects": [{"open_bugs_count": 220}]},
            {"projects": [{"open_bugs_count": 230}]},
            {"projects": [{"open_bugs_count": 240}]},
            {"projects": [{"open_bugs_count": 250}]},
        ]
        security_weeks = [
            {"metrics": {"current_total": 400}},
            {"metrics": {"current_total": 410}},
            {"metrics": {"current_total": 420}},
            {"metrics": {"current_total": 430}},
            {"metrics": {"current_total": 440}},
            {"metrics": {"current_total": 450}},
        ]

        calc = TrendsCalculator(sample_baselines)
        result = calc.calculate_target_progress(quality_weeks, security_weeks)

        # Should detect negative burn rate
        assert result is not None
        assert "⚠" in result["forecast"]["forecast_msg"]
        assert "increasing" in result["forecast"]["forecast_msg"].lower()

    def test_extract_quality_trends_success(self, sample_quality_weeks):
        """Test quality trends extraction"""
        calc = TrendsCalculator()
        result = calc.extract_quality_trends(sample_quality_weeks)

        assert result is not None
        assert "bugs" in result
        assert "mttr" in result

        bugs = result["bugs"]
        assert bugs["current"] == 225  # Last week
        assert bugs["previous"] == 250  # Second to last
        assert len(bugs["trend_data"]) == 6
        assert bugs["unit"] == "bugs"

        mttr = result["mttr"]
        assert mttr["current"] == 9.0  # Average of 10 and 8
        assert mttr["unit"] == "days"

    def test_extract_quality_trends_no_data(self):
        """Test quality trends with no data"""
        calc = TrendsCalculator()
        result = calc.extract_quality_trends([])
        assert result is None

    def test_extract_security_trends_success(self, sample_security_weeks):
        """Test security trends extraction"""
        calc = TrendsCalculator()
        result = calc.extract_security_trends(sample_security_weeks)

        assert result is not None
        assert "vulnerabilities" in result

        vulns = result["vulnerabilities"]
        assert vulns["current"] == 375
        assert vulns["previous"] == 400
        assert len(vulns["trend_data"]) == 6
        assert vulns["unit"] == "vulns"

    def test_extract_security_trends_no_data(self):
        """Test security trends with no data"""
        calc = TrendsCalculator()
        result = calc.extract_security_trends([])
        assert result is None

    def test_extract_flow_trends_success(self, sample_flow_weeks):
        """Test flow trends extraction with standard data"""
        calc = TrendsCalculator()
        result = calc.extract_flow_trends(sample_flow_weeks)

        assert result is not None
        assert "lead_time" in result

        lead_time = result["lead_time"]
        assert lead_time["current"] > 0
        assert len(lead_time["trend_data"]) == 3
        assert lead_time["unit"] == "days"

    def test_extract_flow_trends_with_cleanup(self, sample_flow_weeks_with_cleanup):
        """Test flow trends with cleanup indicators (uses operational metrics)"""
        calc = TrendsCalculator()
        result = calc.extract_flow_trends(sample_flow_weeks_with_cleanup)

        assert result is not None
        lead_time = result["lead_time"]

        # First week uses operational metric (30.0), second uses standard (20.0)
        # Current is last week value
        assert lead_time["current"] == 20.0

    def test_extract_flow_trends_no_data(self):
        """Test flow trends with no data"""
        calc = TrendsCalculator()
        result = calc.extract_flow_trends([])
        assert result is None

    def test_extract_deployment_trends_success(self, sample_deployment_weeks):
        """Test deployment trends extraction"""
        calc = TrendsCalculator()
        result = calc.extract_deployment_trends(sample_deployment_weeks)

        assert result is not None
        assert "build_success" in result

        build_success = result["build_success"]
        # Week 1: (90+45)/(100+50) = 135/150 = 90.0%
        # Week 2: (92+47)/(100+50) = 139/150 = 92.7%
        assert build_success["previous"] == 90.0
        assert build_success["current"] == 92.7
        assert build_success["unit"] == "%"

    def test_extract_deployment_trends_no_data(self):
        """Test deployment trends with no data"""
        calc = TrendsCalculator()
        result = calc.extract_deployment_trends([])
        assert result is None

    def test_extract_collaboration_trends_success(self, sample_collaboration_weeks):
        """Test collaboration trends extraction"""
        calc = TrendsCalculator()
        result = calc.extract_collaboration_trends(sample_collaboration_weeks)

        assert result is not None
        assert "pr_merge_time" in result

        pr_merge = result["pr_merge_time"]
        # Uses median, so week 1 = median(5.5, 3.2) = 4.35, week 2 = median(4.8, 2.9) = 3.85
        # Rounded to 3.8
        assert pr_merge["current"] == 3.8
        assert pr_merge["unit"] == "hours"

    def test_extract_collaboration_trends_no_data(self):
        """Test collaboration trends with no data"""
        calc = TrendsCalculator()
        result = calc.extract_collaboration_trends([])
        assert result is None

    def test_extract_ownership_trends_success(self, sample_ownership_weeks):
        """Test ownership trends extraction"""
        calc = TrendsCalculator()
        result = calc.extract_ownership_trends(sample_ownership_weeks)

        assert result is not None
        assert "work_unassigned" in result

        unassigned = result["work_unassigned"]
        # Week 1: (30+10)/(100+50) = 40/150 = 26.7%
        # Week 2: (25+8)/(100+50) = 33/150 = 22.0%
        assert unassigned["previous"] == 26.7
        assert unassigned["current"] == 22.0
        assert unassigned["unit"] == "%"

    def test_extract_ownership_trends_no_data(self):
        """Test ownership trends with no data"""
        calc = TrendsCalculator()
        result = calc.extract_ownership_trends([])
        assert result is None

    def test_extract_risk_trends_success(self, sample_risk_weeks):
        """Test risk trends extraction"""
        calc = TrendsCalculator()
        result = calc.extract_risk_trends(sample_risk_weeks)

        assert result is not None
        assert "total_commits" in result

        commits = result["total_commits"]
        assert commits["previous"] == 225  # 150 + 75
        assert commits["current"] == 240  # 160 + 80
        assert commits["unit"] == "commits"

    def test_extract_risk_trends_no_data(self):
        """Test risk trends with no data"""
        calc = TrendsCalculator()
        result = calc.extract_risk_trends([])
        assert result is None


class TestTrendIndicators:
    """Test trend indicator calculations"""

    def test_get_trend_indicator_decreasing_good(self):
        """Test trend indicator when value decreases (good direction = down)"""
        arrow, css_class, change = TrendsCalculator.get_trend_indicator(90, 100, "down")
        assert arrow == "↓"
        assert css_class == "trend-down"
        assert change == -10

    def test_get_trend_indicator_increasing_bad(self):
        """Test trend indicator when value increases (good direction = down)"""
        arrow, css_class, change = TrendsCalculator.get_trend_indicator(110, 100, "down")
        assert arrow == "↑"
        assert css_class == "trend-up"
        assert change == 10

    def test_get_trend_indicator_increasing_good(self):
        """Test trend indicator when value increases (good direction = up)"""
        arrow, css_class, change = TrendsCalculator.get_trend_indicator(110, 100, "up")
        assert arrow == "↑"
        assert css_class == "trend-down"
        assert change == 10

    def test_get_trend_indicator_decreasing_bad(self):
        """Test trend indicator when value decreases (good direction = up)"""
        arrow, css_class, change = TrendsCalculator.get_trend_indicator(90, 100, "up")
        assert arrow == "↓"
        assert css_class == "trend-up"
        assert change == -10

    def test_get_trend_indicator_stable(self):
        """Test trend indicator when value is stable (change < 0.5)"""
        arrow, css_class, change = TrendsCalculator.get_trend_indicator(100.3, 100, "down")
        assert arrow == "→"
        assert css_class == "trend-stable"
        assert abs(change - 0.3) < 0.01  # Allow for floating point precision


class TestRAGColors:
    """Test RAG color determination"""

    def test_rag_color_lead_time(self):
        """Test RAG colors for lead time metric"""
        assert TrendsCalculator.get_rag_color(25, "lead_time") == "#10b981"  # Green
        assert TrendsCalculator.get_rag_color(45, "lead_time") == "#f59e0b"  # Amber
        assert TrendsCalculator.get_rag_color(75, "lead_time") == "#ef4444"  # Red

    def test_rag_color_mttr(self):
        """Test RAG colors for MTTR metric"""
        assert TrendsCalculator.get_rag_color(5, "mttr") == "#10b981"  # Green
        assert TrendsCalculator.get_rag_color(10, "mttr") == "#f59e0b"  # Amber
        assert TrendsCalculator.get_rag_color(20, "mttr") == "#ef4444"  # Red

    def test_rag_color_vulnerabilities(self):
        """Test RAG colors for vulnerabilities metric"""
        assert TrendsCalculator.get_rag_color(100, "total_vulns") == "#10b981"  # Green
        assert TrendsCalculator.get_rag_color(200, "total_vulns") == "#f59e0b"  # Amber
        assert TrendsCalculator.get_rag_color(300, "total_vulns") == "#ef4444"  # Red

    def test_rag_color_bugs(self):
        """Test RAG colors for bugs metric"""
        assert TrendsCalculator.get_rag_color(50, "bugs") == "#10b981"  # Green
        assert TrendsCalculator.get_rag_color(150, "bugs") == "#f59e0b"  # Amber
        assert TrendsCalculator.get_rag_color(250, "bugs") == "#ef4444"  # Red

    def test_rag_color_success_rate(self):
        """Test RAG colors for success rate metric"""
        assert TrendsCalculator.get_rag_color(95, "success_rate") == "#10b981"  # Green
        assert TrendsCalculator.get_rag_color(85, "success_rate") == "#f59e0b"  # Amber
        assert TrendsCalculator.get_rag_color(65, "success_rate") == "#ef4444"  # Red

    def test_rag_color_merge_time(self):
        """Test RAG colors for merge time metric"""
        assert TrendsCalculator.get_rag_color(2, "merge_time") == "#10b981"  # Green
        assert TrendsCalculator.get_rag_color(12, "merge_time") == "#f59e0b"  # Amber
        assert TrendsCalculator.get_rag_color(36, "merge_time") == "#ef4444"  # Red

    def test_rag_color_unassigned(self):
        """Test RAG colors for unassigned work metric"""
        assert TrendsCalculator.get_rag_color(10, "unassigned") == "#10b981"  # Green
        assert TrendsCalculator.get_rag_color(30, "unassigned") == "#f59e0b"  # Amber
        assert TrendsCalculator.get_rag_color(50, "unassigned") == "#ef4444"  # Red

    def test_rag_color_target_progress(self):
        """Test RAG colors for target progress metric"""
        assert TrendsCalculator.get_rag_color(80, "target_progress") == "#10b981"  # Green
        assert TrendsCalculator.get_rag_color(55, "target_progress") == "#f59e0b"  # Amber
        assert TrendsCalculator.get_rag_color(30, "target_progress") == "#ef4444"  # Red

    def test_rag_color_commits(self):
        """Test RAG colors for commits metric (neutral)"""
        assert TrendsCalculator.get_rag_color(100, "commits") == "#6366f1"  # Purple

    def test_rag_color_none_value(self):
        """Test RAG color for None value"""
        assert TrendsCalculator.get_rag_color(None, "bugs") == "#94a3b8"  # Gray

    def test_rag_color_na_value(self):
        """Test RAG color for N/A value"""
        assert TrendsCalculator.get_rag_color("N/A", "bugs") == "#94a3b8"  # Gray

    def test_rag_color_invalid_value(self):
        """Test RAG color for invalid value"""
        assert TrendsCalculator.get_rag_color("invalid", "bugs") == "#94a3b8"  # Gray

    def test_rag_color_unknown_metric(self):
        """Test RAG color for unknown metric type"""
        assert TrendsCalculator.get_rag_color(100, "unknown_metric") == "#6366f1"  # Default purple


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_single_week_data(self):
        """Test extraction with single week of data"""
        calc = TrendsCalculator()
        single_week = [{"projects": [{"open_bugs_count": 100}]}]
        result = calc.extract_quality_trends(single_week)

        assert result is not None
        assert result["bugs"]["current"] == 100
        assert result["bugs"]["previous"] == 0  # No previous week

    def test_empty_projects_list(self):
        """Test extraction with empty projects list"""
        calc = TrendsCalculator()
        empty_projects: list[dict] = [{"projects": []}]
        result = calc.extract_quality_trends(empty_projects)

        assert result is not None
        assert result["bugs"]["current"] == 0

    def test_missing_metrics_keys(self):
        """Test extraction with missing metric keys"""
        calc = TrendsCalculator()
        incomplete_data: list[dict] = [{"projects": [{}]}]  # Missing open_bugs_count
        result = calc.extract_quality_trends(incomplete_data)

        assert result is not None
        assert result["bugs"]["current"] == 0

    def test_zero_division_protection(self):
        """Test that calculations handle zero division gracefully"""
        calc = TrendsCalculator({"bugs": 0, "security": 0})
        quality_weeks = [{"projects": [{"open_bugs_count": 0}]}]
        security_weeks = [{"metrics": {"current_total": 0}}]

        result = calc.calculate_target_progress(quality_weeks, security_weeks)
        assert result is not None  # Should not crash

    def test_median_with_empty_list(self):
        """Test flow trends with no valid lead time values"""
        calc = TrendsCalculator()
        no_lead_times: list[dict] = [{"projects": [{}]}]  # No lead_time key
        result = calc.extract_flow_trends(no_lead_times)

        assert result is not None
        assert result["lead_time"]["current"] == 0
