"""
Tests for Engineering Health Dashboard

Covers:
- SecurityForecaster: forecasting, probability calculation, missing-data handling
- HealthScorer: bug scoring, security scoring, anomaly detection, org summary
- health_dashboard.py: context building, generate function (mocked I/O)
- ProductHealth domain model: status_class, trend_arrow, forecast_label
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from execution.dashboards.health_dashboard import (
    _build_context,
    _build_product_rows,
    _build_summary_cards,
    _calculate_display_summary,
    generate_health_dashboard,
)
from execution.domain.health import OrgHealthSummary, ProductHealth
from execution.ml.health_scorer import HealthScorer, SecurityForecaster, _health_status, _normal_cdf

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_quality_week(week_date: str, products: list[dict]) -> dict:
    """Helper: build a quality history week dict."""
    return {"week_date": week_date, "week_number": 1, "projects": products}


def _make_product_entry(key: str, name: str, open_bugs: int) -> dict:
    return {
        "project_key": key,
        "project_name": name,
        "open_bugs_count": open_bugs,
        "mttr": {"mttr_days": 10.0},
    }


_QUALITY_DATES = ["2026-01-05", "2026-01-12", "2026-01-19", "2026-01-26", "2026-02-02"]
_SECURITY_DATES = ["2026-01-05", "2026-01-12", "2026-01-19", "2026-01-26", "2026-02-02", "2026-02-09"]


@pytest.fixture
def sample_quality_weeks() -> list[dict]:
    """5 weeks × 2 products — enough for TrendPredictor."""
    return [
        _make_quality_week(
            _QUALITY_DATES[i],
            [
                _make_product_entry("Product_A", "Product A", 100 - i * 5),
                _make_product_entry("Product_B", "Product B", 50 + i * 3),
            ],
        )
        for i in range(5)
    ]


@pytest.fixture
def sample_security_weeks() -> list[dict]:
    """6 weeks of org-level security data (declining from 280 → 250)."""
    return [
        {
            "week_date": _SECURITY_DATES[i],
            "week_number": i + 1,
            "metrics": {
                "current_total": 280 - i * 6,
                "severity_breakdown": {"critical": 8, "high": 272 - i * 6, "total": 280 - i * 6},
                "product_breakdown": {
                    "Product A": {"critical": 1, "high": 66, "total": 67},
                    "Product B": {"critical": 0, "high": 15, "total": 15},
                },
            },
        }
        for i in range(6)
    ]


@pytest.fixture
def sample_exploitable() -> dict:
    """One week of exploitable data."""
    return {
        "weeks": [
            {
                "week_date": "2026-02-20",
                "week_number": 8,
                "metrics": {
                    "current_total": 10,
                    "severity_breakdown": {"critical": 0, "high": 8, "medium": 2, "total": 10},
                    "product_breakdown": {
                        "Product A": {"critical": 0, "high": 0, "medium": 1, "total": 1},
                        "Product B": {"critical": 0, "high": 8, "medium": 1, "total": 9},
                    },
                },
            }
        ]
    }


@pytest.fixture
def sample_product_health() -> ProductHealth:
    """A realistic ProductHealth snapshot."""
    return ProductHealth(
        timestamp=datetime(2026, 2, 20),
        product_name="Product A",
        health_score=72.5,
        health_status="Healthy",
        bug_score=35.0,
        security_score=37.5,
        bug_trend="stable",
        bug_forecast_4wk=95,
        bug_ci_lower=80,
        bug_ci_upper=110,
        current_bug_count=100,
        has_anomaly=False,
        anomaly_severity=None,
        anomaly_description=None,
        exploitable_total=1,
    )


@pytest.fixture
def sample_org_summary() -> OrgHealthSummary:
    return OrgHealthSummary(
        overall_score=65.0,
        healthy_count=1,
        at_risk_count=1,
        critical_count=0,
        total_products=2,
        critical_anomalies=[],
        warning_anomalies=[],
        security_target_probability=55.0,
        security_predicted_count_june30=120,
        security_target_count=74,
        security_predicted_shortfall=46,
        org_security_trajectory="At Risk",
    )


# ---------------------------------------------------------------------------
# _normal_cdf
# ---------------------------------------------------------------------------


def test_normal_cdf_at_mean():
    """CDF at the mean should be exactly 0.5."""
    result = _normal_cdf(mu=100.0, x=100.0, sigma=10.0)
    assert abs(result - 0.5) < 1e-9


def test_normal_cdf_above_mean():
    """CDF above mean should be > 0.5."""
    assert _normal_cdf(x=110.0, mu=100.0, sigma=10.0) > 0.5


def test_normal_cdf_below_mean():
    """CDF below mean should be < 0.5."""
    assert _normal_cdf(x=90.0, mu=100.0, sigma=10.0) < 0.5


def test_normal_cdf_zero_sigma():
    """Zero sigma: return 1.0 when x >= mu, 0.0 otherwise."""
    assert _normal_cdf(x=100.0, mu=100.0, sigma=0.0) == 1.0
    assert _normal_cdf(x=99.0, mu=100.0, sigma=0.0) == 0.0


# ---------------------------------------------------------------------------
# _health_status
# ---------------------------------------------------------------------------


def test_health_status_healthy():
    assert _health_status(70.0) == "Healthy"
    assert _health_status(100.0) == "Healthy"


def test_health_status_at_risk():
    assert _health_status(40.0) == "At Risk"
    assert _health_status(69.9) == "At Risk"


def test_health_status_critical():
    assert _health_status(0.0) == "Critical"
    assert _health_status(39.9) == "Critical"


# ---------------------------------------------------------------------------
# SecurityForecaster
# ---------------------------------------------------------------------------


class TestSecurityForecaster:
    def test_forecast_with_sufficient_data(self, sample_security_weeks, tmp_path):
        history_file = tmp_path / "security_history.json"
        history_file.write_text(json.dumps({"weeks": sample_security_weeks}))
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps({"vulnerability_count": 246, "target_count": 74}))

        forecaster = SecurityForecaster(history_file=history_file, baseline_file=baseline_file)
        result = forecaster.forecast()

        assert "target_probability" in result
        assert 0 <= result["target_probability"] <= 100
        assert result["target_count"] == 74
        assert result["baseline_count"] == 246
        assert result["data_weeks"] == len(sample_security_weeks)
        assert result["trajectory"] in ("On Track", "At Risk", "Behind")

    def test_forecast_with_insufficient_data(self, tmp_path):
        history_file = tmp_path / "security_history.json"
        history_file.write_text(json.dumps({"weeks": []}))
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps({"vulnerability_count": 246, "target_count": 74}))

        forecaster = SecurityForecaster(history_file=history_file, baseline_file=baseline_file)
        result = forecaster.forecast()

        # Should return fallback, not raise
        assert result["target_probability"] == 50.0
        assert result["data_weeks"] == 0

    def test_forecast_missing_baseline_uses_defaults(self, sample_security_weeks, tmp_path):
        history_file = tmp_path / "security_history.json"
        history_file.write_text(json.dumps({"weeks": sample_security_weeks}))
        # No baseline file → should use defaults (246 / 74)
        missing = tmp_path / "missing_baseline.json"

        forecaster = SecurityForecaster(history_file=history_file, baseline_file=missing)
        result = forecaster.forecast()

        assert result["baseline_count"] == 246
        assert result["target_count"] == 74


# ---------------------------------------------------------------------------
# HealthScorer
# ---------------------------------------------------------------------------


class TestHealthScorer:
    def _make_scorer(self, tmp_path, quality_weeks, exploitable_data=None):
        quality_file = tmp_path / "quality.json"
        quality_file.write_text(json.dumps({"weeks": quality_weeks}))

        exploit_file = tmp_path / "exploitable.json"
        exploit_file.write_text(json.dumps(exploitable_data or {"weeks": []}))

        security_file = tmp_path / "security.json"
        security_file.write_text(json.dumps({"weeks": []}))  # Minimal - tested separately

        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps({"vulnerability_count": 246, "target_count": 74}))

        return HealthScorer(
            quality_history_file=quality_file,
            exploitable_history_file=exploit_file,
            security_history_file=security_file,
            baseline_file=baseline_file,
        )

    def test_score_all_products_returns_sorted_worst_first(self, tmp_path, sample_quality_weeks, sample_exploitable):
        scorer = self._make_scorer(tmp_path, sample_quality_weeks, sample_exploitable)
        products, summary = scorer.score_all_products()

        assert len(products) > 0
        # Sorted ascending by health_score (worst first)
        scores = [p.health_score for p in products]
        assert scores == sorted(scores)

    def test_score_all_products_total_matches(self, tmp_path, sample_quality_weeks):
        scorer = self._make_scorer(tmp_path, sample_quality_weeks)
        products, summary = scorer.score_all_products()

        assert summary.total_products == len(products)
        assert summary.healthy_count + summary.at_risk_count + summary.critical_count == len(products)

    def test_bug_score_improving_trend(self):
        scorer = HealthScorer.__new__(HealthScorer)
        score = scorer._compute_bug_score("decreasing", False, None)
        assert score == 50.0

    def test_bug_score_worsening_trend(self):
        scorer = HealthScorer.__new__(HealthScorer)
        score = scorer._compute_bug_score("increasing", False, None)
        assert score == 15.0

    def test_bug_score_with_critical_anomaly_penalty(self):
        scorer = HealthScorer.__new__(HealthScorer)
        score = scorer._compute_bug_score("decreasing", True, "critical")
        assert score == 25.0  # 50 - 25

    def test_bug_score_with_warning_anomaly_penalty(self):
        scorer = HealthScorer.__new__(HealthScorer)
        score = scorer._compute_bug_score("stable", True, "warning")
        assert score == 20.0  # 35 - 15

    def test_bug_score_floored_at_zero(self):
        scorer = HealthScorer.__new__(HealthScorer)
        # worsening (15) with critical penalty (-25) = -10 → floor 0
        score = scorer._compute_bug_score("increasing", True, "critical")
        assert score == 0.0

    def test_security_score_zero_exploitable(self):
        scorer = HealthScorer.__new__(HealthScorer)
        score = scorer._compute_security_score("Product A", {}, 0)
        assert score == 50.0

    def test_security_score_highest_exploitable_product(self):
        scorer = HealthScorer.__new__(HealthScorer)
        exploitable = {"Product K": 653}
        score = scorer._compute_security_score("Product K", exploitable, 653)
        assert score == 0.0

    def test_security_score_partial_exploitable(self):
        scorer = HealthScorer.__new__(HealthScorer)
        exploitable = {"Product A": 10, "Product K": 100}
        score_a = scorer._compute_security_score("Product A", exploitable, 100)
        score_k = scorer._compute_security_score("Product K", exploitable, 100)
        assert 0.0 < score_a <= 50.0
        assert score_k == 0.0
        assert score_a > score_k

    def test_detect_current_anomaly_normal(self):
        scorer = HealthScorer.__new__(HealthScorer)
        # Stable series - last value same as rest
        series = [100, 102, 98, 101, 100]
        has_anomaly, severity, z = scorer._detect_current_anomaly(series)
        assert not has_anomaly

    def test_detect_current_anomaly_spike(self):
        scorer = HealthScorer.__new__(HealthScorer)
        # Large spike in last value
        series = [100, 102, 98, 101, 250]
        has_anomaly, severity, z = scorer._detect_current_anomaly(series)
        assert has_anomaly
        assert severity in ("warning", "critical")

    def test_detect_current_anomaly_insufficient_data(self):
        scorer = HealthScorer.__new__(HealthScorer)
        # Only 3 points - not enough
        has_anomaly, severity, z = scorer._detect_current_anomaly([100, 105, 102])
        assert not has_anomaly

    def test_no_quality_data_returns_empty_products(self, tmp_path):
        scorer = self._make_scorer(tmp_path, [])
        products, summary = scorer.score_all_products()
        assert products == []
        assert summary.total_products == 0


# ---------------------------------------------------------------------------
# ProductHealth domain model
# ---------------------------------------------------------------------------


class TestProductHealth:
    def test_status_class_healthy(self, sample_product_health):
        assert sample_product_health.status_class == "status-good"

    def test_status_class_at_risk(self, sample_product_health):
        sample_product_health.health_status = "At Risk"
        assert sample_product_health.status_class == "status-caution"

    def test_status_class_critical(self, sample_product_health):
        sample_product_health.health_status = "Critical"
        assert sample_product_health.status_class == "status-action"

    def test_trend_arrow_improving(self, sample_product_health):
        sample_product_health.bug_trend = "improving"
        assert sample_product_health.trend_arrow == "↓"

    def test_trend_arrow_worsening(self, sample_product_health):
        sample_product_health.bug_trend = "worsening"
        assert sample_product_health.trend_arrow == "↑"

    def test_trend_arrow_stable(self, sample_product_health):
        sample_product_health.bug_trend = "stable"
        assert sample_product_health.trend_arrow == "→"

    def test_forecast_label_with_ci(self, sample_product_health):
        label = sample_product_health.forecast_label
        assert "95" in label
        assert "80" in label
        assert "110" in label

    def test_forecast_label_no_data(self, sample_product_health):
        sample_product_health.bug_forecast_4wk = None
        assert "Insufficient" in sample_product_health.forecast_label


# ---------------------------------------------------------------------------
# OrgHealthSummary
# ---------------------------------------------------------------------------


class TestOrgHealthSummary:
    def test_has_critical_anomaly_true(self, sample_org_summary):
        sample_org_summary.critical_anomalies = ["Product A"]
        assert sample_org_summary.has_critical_anomaly

    def test_has_critical_anomaly_false(self, sample_org_summary):
        assert not sample_org_summary.has_critical_anomaly

    def test_overall_status_healthy(self, sample_org_summary):
        sample_org_summary.overall_score = 75.0
        assert sample_org_summary.overall_status == "Healthy"
        assert sample_org_summary.overall_status_class == "status-good"

    def test_overall_status_at_risk(self, sample_org_summary):
        assert sample_org_summary.overall_status == "At Risk"
        assert sample_org_summary.overall_status_class == "status-caution"

    def test_overall_status_critical(self, sample_org_summary):
        sample_org_summary.overall_score = 30.0
        assert sample_org_summary.overall_status == "Critical"
        assert sample_org_summary.overall_status_class == "status-action"


# ---------------------------------------------------------------------------
# Dashboard context builders
# ---------------------------------------------------------------------------


class TestDashboardContext:
    def test_build_context_includes_framework_keys(self, sample_product_health, sample_org_summary):
        context = _build_context([sample_product_health], sample_org_summary)
        assert "framework_css" in context
        assert "framework_js" in context
        assert len(context["framework_css"]) > 0
        assert len(context["framework_js"]) > 0

    def test_build_context_includes_summary_cards(self, sample_product_health, sample_org_summary):
        context = _build_context([sample_product_health], sample_org_summary)
        assert "summary_cards" in context
        assert len(context["summary_cards"]) == 4

    def test_build_context_includes_product_rows(self, sample_product_health, sample_org_summary):
        context = _build_context([sample_product_health], sample_org_summary)
        assert "product_rows" in context
        assert len(context["product_rows"]) == 1
        row = context["product_rows"][0]
        assert row["product_name"] == "Product A"
        assert "health_score" in row
        assert "forecast_4wk" in row
        assert "anomaly_badge" in row

    def test_build_product_rows_anomaly_badge(self, sample_product_health):
        sample_product_health.has_anomaly = True
        sample_product_health.anomaly_severity = "critical"
        rows = _build_product_rows([sample_product_health])
        assert "Critical Spike" in rows[0]["anomaly_badge"]

    def test_build_product_rows_warning_badge(self, sample_product_health):
        sample_product_health.has_anomaly = True
        sample_product_health.anomaly_severity = "warning"
        rows = _build_product_rows([sample_product_health])
        assert "Warning" in rows[0]["anomaly_badge"]

    def test_build_product_rows_no_anomaly(self, sample_product_health):
        rows = _build_product_rows([sample_product_health])
        assert "Normal" in rows[0]["anomaly_badge"]

    def test_display_summary_shortfall_ahead(self, sample_org_summary):
        sample_org_summary.security_predicted_shortfall = -10
        display = _calculate_display_summary([], sample_org_summary)
        assert "ahead" in display["shortfall_text"]

    def test_display_summary_shortfall_behind(self, sample_org_summary):
        display = _calculate_display_summary([], sample_org_summary)
        assert "above" in display["shortfall_text"]


# ---------------------------------------------------------------------------
# generate_health_dashboard (integration with mocked I/O)
# ---------------------------------------------------------------------------


class TestGenerateHealthDashboard:
    def test_generate_writes_html(self, tmp_path, sample_quality_weeks, sample_exploitable):
        quality_file = tmp_path / "quality_history.json"
        quality_file.write_text(json.dumps({"weeks": sample_quality_weeks}))
        exploit_file = tmp_path / "exploitable_history.json"
        exploit_file.write_text(json.dumps(sample_exploitable))
        security_file = tmp_path / "security_history.json"
        security_file.write_text(json.dumps({"weeks": []}))
        baseline_file = tmp_path / "armorcode_baseline.json"
        baseline_file.write_text(json.dumps({"vulnerability_count": 246, "target_count": 74}))
        output_file = tmp_path / "health_dashboard.html"

        with (
            patch("execution.dashboards.health_dashboard.HealthScorer") as mock_scorer_class,
            patch("execution.dashboards.health_dashboard.OUTPUT_PATH", output_file),
        ):
            mock_instance = MagicMock()
            mock_scorer_class.return_value = mock_instance

            # Build minimal but valid sample data
            sample_health = ProductHealth(
                timestamp=datetime(2026, 2, 20),
                product_name="Product A",
                health_score=72.0,
                health_status="Healthy",
                bug_score=35.0,
                security_score=37.0,
                bug_trend="stable",
                bug_forecast_4wk=95,
                bug_ci_lower=80,
                bug_ci_upper=110,
                current_bug_count=100,
                has_anomaly=False,
                anomaly_severity=None,
                anomaly_description=None,
                exploitable_total=1,
            )
            sample_summary = OrgHealthSummary(
                overall_score=72.0,
                healthy_count=1,
                at_risk_count=0,
                critical_count=0,
                total_products=1,
                security_target_probability=60.0,
                security_predicted_count_june30=100,
                security_target_count=74,
                security_predicted_shortfall=26,
                org_security_trajectory="At Risk",
            )
            mock_instance.score_all_products.return_value = ([sample_health], sample_summary)

            html = generate_health_dashboard(output_path=output_file)

        assert len(html) > 500
        assert "Engineering Health" in html
        assert output_file.exists()
