"""
Tests for execution/domain/intelligence.py

Covers: ForecastResult, TrendStrengthScore, RiskScore, RiskScoreComponent, ForecastPoint.
All fixtures use synthetic data only — no real project names, no real metric data.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from execution.domain.intelligence import (
    ForecastPoint,
    ForecastResult,
    RiskScore,
    RiskScoreComponent,
    TrendStrengthScore,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_forecast_point() -> ForecastPoint:
    return ForecastPoint(week=4, p10=80.0, p50=95.0, p90=110.0)


@pytest.fixture
def sample_forecast_result(sample_forecast_point: ForecastPoint) -> ForecastResult:
    return ForecastResult(
        timestamp=datetime(2025, 10, 6),
        project="Product_A",
        metric="open_bugs",
        forecast=[sample_forecast_point],
        model="arima",
        mape=0.07,
        trend_direction="improving",
        trend_strength=0.72,
    )


@pytest.fixture
def sample_trend_score() -> TrendStrengthScore:
    return TrendStrengthScore(
        timestamp=datetime(2025, 10, 6),
        project="Product_B",
        metric="open_bugs",
        score=72.0,
        direction="improving",
        r_squared=0.72,
        weeks_analyzed=20,
    )


@pytest.fixture
def sample_risk_score() -> RiskScore:
    return RiskScore(
        project="Product_C",
        total=65.0,
        components=[
            RiskScoreComponent(name="vuln_risk", raw_score=70.0, weight=0.35, weighted=24.5),
            RiskScoreComponent(name="quality_risk", raw_score=60.0, weight=0.25, weighted=15.0),
        ],
    )


# ---------------------------------------------------------------------------
# ForecastPoint
# ---------------------------------------------------------------------------


class TestForecastPoint:
    def test_fields_stored_correctly(self, sample_forecast_point: ForecastPoint) -> None:
        assert sample_forecast_point.week == 4
        assert sample_forecast_point.p10 == 80.0
        assert sample_forecast_point.p50 == 95.0
        assert sample_forecast_point.p90 == 110.0

    def test_band_ordering(self, sample_forecast_point: ForecastPoint) -> None:
        assert sample_forecast_point.p10 <= sample_forecast_point.p50 <= sample_forecast_point.p90


# ---------------------------------------------------------------------------
# ForecastResult
# ---------------------------------------------------------------------------


class TestForecastResult:
    def test_inherits_metric_snapshot(self, sample_forecast_result: ForecastResult) -> None:
        assert hasattr(sample_forecast_result, "timestamp")
        assert hasattr(sample_forecast_result, "project")

    def test_status_improving(self, sample_forecast_result: ForecastResult) -> None:
        assert sample_forecast_result.status == "Improving"

    def test_status_worsening(self) -> None:
        fr = ForecastResult(
            timestamp=datetime(2025, 10, 6),
            project="Product_A",
            metric="open_bugs",
            trend_direction="worsening",
        )
        assert fr.status == "Action Needed"

    def test_status_flat(self) -> None:
        fr = ForecastResult(
            timestamp=datetime(2025, 10, 6),
            project="Product_A",
            metric="open_bugs",
            trend_direction="flat",
        )
        assert fr.status == "Stable"

    def test_status_class_improving(self, sample_forecast_result: ForecastResult) -> None:
        assert sample_forecast_result.status_class == "status-good"

    def test_status_class_worsening(self) -> None:
        fr = ForecastResult(
            timestamp=datetime(2025, 10, 6),
            project="Product_A",
            metric="vulns",
            trend_direction="worsening",
        )
        assert fr.status_class == "status-action"

    def test_status_class_flat(self) -> None:
        fr = ForecastResult(
            timestamp=datetime(2025, 10, 6),
            project="Product_A",
            metric="vulns",
            trend_direction="flat",
        )
        assert fr.status_class == "status-caution"

    def test_forecast_4w_returns_correct_point(self, sample_forecast_result: ForecastResult) -> None:
        point = sample_forecast_result.forecast_4w
        assert point is not None
        assert point.week == 4

    def test_forecast_4w_returns_none_when_missing(self) -> None:
        fr = ForecastResult(
            timestamp=datetime(2025, 10, 6),
            project="Product_A",
            metric="open_bugs",
            forecast=[ForecastPoint(week=13, p10=80.0, p50=90.0, p90=100.0)],
        )
        assert fr.forecast_4w is None

    def test_from_json_roundtrip(self) -> None:
        data = {
            "generated_date": "2025-10-06T00:00:00",
            "project": "Product_A",
            "metric": "open_bugs",
            "forecast": [{"week": 4, "p10": 80.0, "p50": 95.0, "p90": 110.0}],
            "model": "arima",
            "mape": 0.07,
            "trend_direction": "improving",
            "trend_strength": 0.72,
        }
        fr = ForecastResult.from_json(data)
        assert fr.project == "Product_A"
        assert fr.metric == "open_bugs"
        assert fr.mape == pytest.approx(0.07)
        assert fr.trend_direction == "improving"
        assert len(fr.forecast) == 1
        assert fr.forecast[0].p50 == pytest.approx(95.0)

    def test_from_json_defaults(self) -> None:
        data = {"generated_date": "2025-10-06T00:00:00", "metric": "open_bugs"}
        fr = ForecastResult.from_json(data)
        assert fr.model == "prophet"
        assert fr.mape == 0.0
        assert fr.trend_direction == "flat"
        assert fr.trend_strength == 0.0
        assert fr.project is None

    def test_project_inherited_from_metric_snapshot(self, sample_forecast_result: ForecastResult) -> None:
        assert sample_forecast_result.project == "Product_A"


# ---------------------------------------------------------------------------
# TrendStrengthScore
# ---------------------------------------------------------------------------


class TestTrendStrengthScore:
    def test_inherits_metric_snapshot(self, sample_trend_score: TrendStrengthScore) -> None:
        assert hasattr(sample_trend_score, "timestamp")
        assert hasattr(sample_trend_score, "project")

    def test_status_improving(self, sample_trend_score: TrendStrengthScore) -> None:
        assert sample_trend_score.status == "Improving"

    def test_status_worsening(self) -> None:
        ts = TrendStrengthScore(
            timestamp=datetime(2025, 10, 6),
            project="Product_B",
            metric="vulns",
            direction="worsening",
        )
        assert ts.status == "Worsening"

    def test_status_flat(self) -> None:
        ts = TrendStrengthScore(
            timestamp=datetime(2025, 10, 6),
            project="Product_B",
            metric="vulns",
            direction="flat",
        )
        assert ts.status == "Flat"

    def test_status_class_improving(self, sample_trend_score: TrendStrengthScore) -> None:
        assert sample_trend_score.status_class == "status-good"

    def test_status_class_worsening(self) -> None:
        ts = TrendStrengthScore(
            timestamp=datetime(2025, 10, 6),
            project="Product_B",
            metric="vulns",
            direction="worsening",
        )
        assert ts.status_class == "status-action"

    def test_status_class_flat(self) -> None:
        ts = TrendStrengthScore(
            timestamp=datetime(2025, 10, 6),
            project="Product_B",
            metric="vulns",
            direction="flat",
        )
        assert ts.status_class == "status-caution"

    def test_from_json_roundtrip(self) -> None:
        data = {
            "timestamp": "2025-10-06T00:00:00",
            "project": "Product_B",
            "metric": "open_bugs",
            "score": 72.0,
            "direction": "improving",
            "r_squared": 0.72,
            "weeks_analyzed": 20,
        }
        ts = TrendStrengthScore.from_json(data)
        assert ts.project == "Product_B"
        assert ts.score == pytest.approx(72.0)
        assert ts.direction == "improving"
        assert ts.weeks_analyzed == 20

    def test_from_json_defaults(self) -> None:
        data = {"metric": "open_bugs"}
        ts = TrendStrengthScore.from_json(data)
        assert ts.score == 0.0
        assert ts.direction == "flat"
        assert ts.r_squared == 0.0


# ---------------------------------------------------------------------------
# RiskScoreComponent
# ---------------------------------------------------------------------------


class TestRiskScoreComponent:
    def test_fields_stored(self) -> None:
        c = RiskScoreComponent(name="vuln_risk", raw_score=70.0, weight=0.35, weighted=24.5)
        assert c.name == "vuln_risk"
        assert c.raw_score == pytest.approx(70.0)
        assert c.weight == pytest.approx(0.35)
        assert c.weighted == pytest.approx(24.5)


# ---------------------------------------------------------------------------
# RiskScore
# ---------------------------------------------------------------------------


class TestRiskScore:
    def test_level_critical(self) -> None:
        rs = RiskScore(project="Product_X", total=85.0)
        assert rs.level == "critical"

    def test_level_high(self) -> None:
        rs = RiskScore(project="Product_X", total=65.0)
        assert rs.level == "high"

    def test_level_medium(self) -> None:
        rs = RiskScore(project="Product_X", total=50.0)
        assert rs.level == "medium"

    def test_level_low(self) -> None:
        rs = RiskScore(project="Product_X", total=30.0)
        assert rs.level == "low"

    def test_status_critical_is_action_needed(self) -> None:
        rs = RiskScore(project="Product_X", total=85.0)
        assert rs.status == "Action Needed"

    def test_status_high_is_action_needed(self) -> None:
        rs = RiskScore(project="Product_X", total=65.0)
        assert rs.status == "Action Needed"

    def test_status_medium_is_caution(self) -> None:
        rs = RiskScore(project="Product_X", total=50.0)
        assert rs.status == "Caution"

    def test_status_low_is_good(self) -> None:
        rs = RiskScore(project="Product_X", total=30.0)
        assert rs.status == "Good"

    def test_status_class_action(self) -> None:
        rs = RiskScore(project="Product_X", total=85.0)
        assert rs.status_class == "status-action"

    def test_status_class_caution(self) -> None:
        rs = RiskScore(project="Product_X", total=50.0)
        assert rs.status_class == "status-caution"

    def test_status_class_good(self) -> None:
        rs = RiskScore(project="Product_X", total=30.0)
        assert rs.status_class == "status-good"

    def test_from_json_roundtrip(self, sample_risk_score: RiskScore) -> None:
        data = {
            "project": "Product_C",
            "total": 65.0,
            "components": [
                {"name": "vuln_risk", "raw_score": 70.0, "weight": 0.35, "weighted": 24.5},
                {"name": "quality_risk", "raw_score": 60.0, "weight": 0.25, "weighted": 15.0},
            ],
        }
        rs = RiskScore.from_json(data)
        assert rs.project == "Product_C"
        assert rs.total == pytest.approx(65.0)
        assert len(rs.components) == 2
        assert rs.components[0].name == "vuln_risk"

    def test_from_json_empty_components(self) -> None:
        data = {"project": "Product_X", "total": 42.0}
        rs = RiskScore.from_json(data)
        assert rs.components == []

    def test_boundary_exactly_80(self) -> None:
        """total == 80 is NOT critical (> 80 required)."""
        rs = RiskScore(project="Product_X", total=80.0)
        assert rs.level == "high"

    def test_boundary_exactly_60(self) -> None:
        """total == 60 is NOT high (> 60 required)."""
        rs = RiskScore(project="Product_X", total=60.0)
        assert rs.level == "medium"

    def test_boundary_exactly_40(self) -> None:
        """total == 40 is NOT medium (> 40 required)."""
        rs = RiskScore(project="Product_X", total=40.0)
        assert rs.level == "low"
