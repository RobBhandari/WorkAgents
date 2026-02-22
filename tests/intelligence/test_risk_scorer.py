"""
Tests for execution/intelligence/risk_scorer.py

Single responsibility: verify that risk scoring functions produce correct,
bounded, and deterministic results from synthetic feature DataFrames.

All fixtures use synthetic data only — no real project names, no real ADO data.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from execution.domain.intelligence import RiskScore, RiskScoreComponent
from execution.intelligence.risk_scorer import (
    _NEUTRAL_SCORE,
    _compute_composite,
    _identify_primary_driver,
    compute_all_risks,
    compute_project_risk,
    save_risk_scores,
    score_deployment_risk,
    score_flow_risk,
    score_ownership_risk,
    score_quality_risk,
    score_security_risk,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _weeks(n: int) -> list[datetime]:
    """Generate n sequential weekly datetimes (deterministic base)."""
    base = datetime(2025, 10, 6)
    return [base + timedelta(weeks=i) for i in range(n)]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def improving_quality_df() -> pd.DataFrame:
    """20 weeks of open_bugs with a clear improving (decreasing) trend."""
    dates = _weeks(20)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Synth_A"] * 20,
            "open_bugs": [300 - i * 5 for i in range(20)],  # 300 → 205
            "p1_bugs": [10] * 20,
            "median_age_days": [60.0] * 20,
        }
    )


@pytest.fixture
def worsening_quality_df() -> pd.DataFrame:
    """20 weeks of open_bugs with a clear worsening (increasing) trend."""
    dates = _weeks(20)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Synth_A"] * 20,
            "open_bugs": [100 + i * 10 for i in range(20)],  # 100 → 290
            "p1_bugs": [5 + i // 5 for i in range(20)],
            "median_age_days": [80.0 + i * 2 for i in range(20)],
        }
    )


@pytest.fixture
def flat_quality_df() -> pd.DataFrame:
    """8 weeks of flat open_bugs (below trend window)."""
    dates = _weeks(8)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Synth_A"] * 8,
            "open_bugs": [200] * 8,
            "p1_bugs": [0] * 8,
            "median_age_days": [30.0] * 8,
        }
    )


@pytest.fixture
def empty_df() -> pd.DataFrame:
    return pd.DataFrame()


@pytest.fixture
def improving_deployment_df() -> pd.DataFrame:
    """20 weeks: build_success_rate improving from 70% → 90%."""
    dates = _weeks(20)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Synth_B"] * 20,
            "build_success_rate": [70.0 + i for i in range(20)],
            "deploy_frequency": [5.0] * 20,
        }
    )


@pytest.fixture
def poor_deployment_df() -> pd.DataFrame:
    """20 weeks: build_success_rate flat at 55% (below 90% threshold)."""
    dates = _weeks(20)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Synth_B"] * 20,
            "build_success_rate": [55.0] * 20,
            "deploy_frequency": [1.0] * 20,  # < 2/week adds freq risk
        }
    )


@pytest.fixture
def high_flow_df() -> pd.DataFrame:
    """20 weeks: high WIP and long lead time (high risk)."""
    dates = _weeks(20)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Synth_C"] * 20,
            "lead_time_p85": [300.0 + i for i in range(20)],
            "wip": [400] * 20,
        }
    )


@pytest.fixture
def low_flow_df() -> pd.DataFrame:
    """20 weeks: low WIP and short lead time (low risk)."""
    dates = _weeks(20)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Synth_C"] * 20,
            "lead_time_p85": [10.0] * 20,
            "wip": [5] * 20,
        }
    )


@pytest.fixture
def high_ownership_df() -> pd.DataFrame:
    """20 weeks: high unassigned_pct worsening trend."""
    dates = _weeks(20)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Synth_D"] * 20,
            "unassigned_pct": [60.0 + i * 0.5 for i in range(20)],
        }
    )


@pytest.fixture
def low_ownership_df() -> pd.DataFrame:
    """20 weeks: low unassigned_pct improving trend."""
    dates = _weeks(20)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Synth_D"] * 20,
            "unassigned_pct": [30.0 - i * 0.5 for i in range(20)],
        }
    )


@pytest.fixture
def security_portfolio_df() -> pd.DataFrame:
    """20 weeks of _portfolio security data with high and worsening vuln count.

    Uses counts calibrated to the real data range (10k-13k) so that the
    scorer — which divides by 200 — produces a score >= 60.
    """
    dates = _weeks(20)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["_portfolio"] * 20,
            "total_vulnerabilities": [12000 + i * 50 for i in range(20)],
            "critical": [500 + i * 5 for i in range(20)],
            "high": [11000 + i * 40 for i in range(20)],
        }
    )


@pytest.fixture
def low_security_df() -> pd.DataFrame:
    """20 weeks: very low vuln count (< 100) and improving trend."""
    dates = _weeks(20)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["_portfolio"] * 20,
            "total_vulnerabilities": [80 - i * 2 for i in range(20)],
            "critical": [5] * 20,
            "high": [70 - i * 2 for i in range(20)],
        }
    )


@pytest.fixture
def sample_risk_scores() -> list[RiskScore]:
    """Two synthetic RiskScore objects for persistence tests."""
    return [
        RiskScore(
            project="Synth_A",
            total=75.5,
            components=[RiskScoreComponent(name="vuln_risk", raw_score=90.0, weight=0.35, weighted=31.5)],
        ),
        RiskScore(
            project="Synth_B",
            total=30.0,
            components=[RiskScoreComponent(name="vuln_risk", raw_score=40.0, weight=0.35, weighted=14.0)],
        ),
    ]


# ---------------------------------------------------------------------------
# score_security_risk
# ---------------------------------------------------------------------------


class TestScoreSecurityRisk:
    def test_empty_df_returns_neutral(self, empty_df: pd.DataFrame) -> None:
        assert score_security_risk(empty_df) == _NEUTRAL_SCORE

    def test_high_vulns_produce_high_risk(self, security_portfolio_df: pd.DataFrame) -> None:
        score = score_security_risk(security_portfolio_df)
        assert score >= 60.0, f"Expected high risk, got {score}"

    def test_low_vulns_produce_low_risk(self, low_security_df: pd.DataFrame) -> None:
        score = score_security_risk(low_security_df)
        assert score < 50.0, f"Expected low risk, got {score}"

    def test_score_bounded_0_100(self, security_portfolio_df: pd.DataFrame) -> None:
        score = score_security_risk(security_portfolio_df)
        assert 0.0 <= score <= 100.0

    def test_missing_critical_column_still_scores(self) -> None:
        """Should work even without a 'critical' column."""
        dates = _weeks(5)
        df = pd.DataFrame(
            {
                "week_date": dates,
                "project": ["_portfolio"] * 5,
                "total_vulnerabilities": [500] * 5,
            }
        )
        score = score_security_risk(df)
        assert 0.0 <= score <= 100.0

    def test_worsening_trend_higher_than_improving(
        self,
        security_portfolio_df: pd.DataFrame,
        low_security_df: pd.DataFrame,
    ) -> None:
        worsening_score = score_security_risk(security_portfolio_df)
        improving_score = score_security_risk(low_security_df)
        assert worsening_score > improving_score


# ---------------------------------------------------------------------------
# score_quality_risk
# ---------------------------------------------------------------------------


class TestScoreQualityRisk:
    def test_empty_df_returns_neutral(self, empty_df: pd.DataFrame) -> None:
        assert score_quality_risk(empty_df) == _NEUTRAL_SCORE

    def test_worsening_higher_than_improving(
        self,
        worsening_quality_df: pd.DataFrame,
        improving_quality_df: pd.DataFrame,
    ) -> None:
        worsening = score_quality_risk(worsening_quality_df)
        improving = score_quality_risk(improving_quality_df)
        assert worsening > improving

    def test_score_bounded_0_100(self, worsening_quality_df: pd.DataFrame) -> None:
        assert 0.0 <= score_quality_risk(worsening_quality_df) <= 100.0

    def test_p1_bugs_increase_risk(self) -> None:
        dates = _weeks(10)
        base_df = pd.DataFrame(
            {
                "week_date": dates,
                "project": ["Synth_A"] * 10,
                "open_bugs": [100] * 10,
                "p1_bugs": [0] * 10,
                "median_age_days": [30.0] * 10,
            }
        )
        high_p1_df = base_df.copy()
        high_p1_df["p1_bugs"] = [20] * 10

        assert score_quality_risk(high_p1_df) > score_quality_risk(base_df)

    def test_too_few_data_points_gives_valid_score(self, flat_quality_df: pd.DataFrame) -> None:
        score = score_quality_risk(flat_quality_df)
        assert 0.0 <= score <= 100.0

    def test_missing_open_bugs_returns_neutral(self) -> None:
        dates = _weeks(10)
        df = pd.DataFrame(
            {
                "week_date": dates,
                "project": ["Synth_A"] * 10,
                "p1_bugs": [5] * 10,
            }
        )
        assert score_quality_risk(df) == _NEUTRAL_SCORE


# ---------------------------------------------------------------------------
# score_deployment_risk
# ---------------------------------------------------------------------------


class TestScoreDeploymentRisk:
    def test_empty_df_returns_neutral(self, empty_df: pd.DataFrame) -> None:
        assert score_deployment_risk(empty_df) == _NEUTRAL_SCORE

    def test_poor_build_rate_high_risk(self, poor_deployment_df: pd.DataFrame) -> None:
        score = score_deployment_risk(poor_deployment_df)
        assert score >= 50.0, f"Expected high risk for 55% build rate, got {score}"

    def test_good_build_rate_low_risk(self, improving_deployment_df: pd.DataFrame) -> None:
        """Last values of improving_deployment_df are near 90%, so risk should be low."""
        score = score_deployment_risk(improving_deployment_df)
        # Final rate is 89% — build_risk approaches 0, no freq risk (5/week), no trend penalty
        assert score < 50.0, f"Expected low risk for improving 90% build rate, got {score}"

    def test_score_bounded_0_100(self, poor_deployment_df: pd.DataFrame) -> None:
        assert 0.0 <= score_deployment_risk(poor_deployment_df) <= 100.0

    def test_low_deploy_frequency_increases_risk(self) -> None:
        dates = _weeks(10)
        high_freq_df = pd.DataFrame(
            {
                "week_date": dates,
                "project": ["Synth_B"] * 10,
                "build_success_rate": [92.0] * 10,
                "deploy_frequency": [5.0] * 10,
            }
        )
        low_freq_df = high_freq_df.copy()
        low_freq_df["deploy_frequency"] = [0.5] * 10  # < 2/week

        assert score_deployment_risk(low_freq_df) > score_deployment_risk(high_freq_df)

    def test_worsening_trend_penalty_applied(self) -> None:
        dates = _weeks(20)
        # Declining success rate from 85% to 66%
        declining_df = pd.DataFrame(
            {
                "week_date": dates,
                "project": ["Synth_B"] * 20,
                "build_success_rate": [85.0 - i for i in range(20)],
                "deploy_frequency": [5.0] * 20,
            }
        )
        flat_df = pd.DataFrame(
            {
                "week_date": dates,
                "project": ["Synth_B"] * 20,
                "build_success_rate": [75.0] * 20,
                "deploy_frequency": [5.0] * 20,
            }
        )
        # Declining should score higher than flat at the same ending value
        assert score_deployment_risk(declining_df) >= score_deployment_risk(flat_df)


# ---------------------------------------------------------------------------
# score_flow_risk
# ---------------------------------------------------------------------------


class TestScoreFlowRisk:
    def test_empty_df_returns_neutral(self, empty_df: pd.DataFrame) -> None:
        assert score_flow_risk(empty_df) == _NEUTRAL_SCORE

    def test_high_wip_and_lead_time_high_risk(self, high_flow_df: pd.DataFrame) -> None:
        score = score_flow_risk(high_flow_df)
        assert score >= 50.0, f"Expected high risk, got {score}"

    def test_low_wip_and_lead_time_low_risk(self, low_flow_df: pd.DataFrame) -> None:
        score = score_flow_risk(low_flow_df)
        assert score < 30.0, f"Expected low risk, got {score}"

    def test_score_bounded_0_100(self, high_flow_df: pd.DataFrame) -> None:
        assert 0.0 <= score_flow_risk(high_flow_df) <= 100.0

    def test_no_lead_time_column_still_scores(self) -> None:
        """Should use wip only when lead_time_p85 is absent."""
        dates = _weeks(10)
        df = pd.DataFrame(
            {
                "week_date": dates,
                "project": ["Synth_C"] * 10,
                "wip": [200] * 10,
            }
        )
        score = score_flow_risk(df)
        assert 0.0 <= score <= 100.0

    def test_df_with_no_useful_columns_returns_neutral(self) -> None:
        dates = _weeks(5)
        df = pd.DataFrame({"week_date": dates, "project": ["Synth_C"] * 5})
        assert score_flow_risk(df) == _NEUTRAL_SCORE


# ---------------------------------------------------------------------------
# score_ownership_risk
# ---------------------------------------------------------------------------


class TestScoreOwnershipRisk:
    def test_empty_df_returns_neutral(self, empty_df: pd.DataFrame) -> None:
        assert score_ownership_risk(empty_df) == _NEUTRAL_SCORE

    def test_high_unassigned_high_risk(self, high_ownership_df: pd.DataFrame) -> None:
        score = score_ownership_risk(high_ownership_df)
        assert score >= 50.0, f"Expected high risk, got {score}"

    def test_low_unassigned_low_risk(self, low_ownership_df: pd.DataFrame) -> None:
        score = score_ownership_risk(low_ownership_df)
        assert score < 30.0, f"Expected low risk, got {score}"

    def test_score_bounded_0_100(self, high_ownership_df: pd.DataFrame) -> None:
        assert 0.0 <= score_ownership_risk(high_ownership_df) <= 100.0

    def test_missing_column_returns_neutral(self) -> None:
        dates = _weeks(5)
        df = pd.DataFrame({"week_date": dates, "project": ["Synth_D"] * 5})
        assert score_ownership_risk(df) == _NEUTRAL_SCORE

    def test_worsening_trend_increases_risk(
        self,
        high_ownership_df: pd.DataFrame,
        low_ownership_df: pd.DataFrame,
    ) -> None:
        high_score = score_ownership_risk(high_ownership_df)
        low_score = score_ownership_risk(low_ownership_df)
        assert high_score > low_score


# ---------------------------------------------------------------------------
# _compute_composite
# ---------------------------------------------------------------------------


class TestComputeComposite:
    def test_all_zeros_gives_zero(self) -> None:
        components = {
            "vuln_risk": 0.0,
            "quality_risk": 0.0,
            "deployment_risk": 0.0,
            "flow_risk": 0.0,
            "ownership_risk": 0.0,
        }
        assert _compute_composite(components) == 0.0

    def test_all_hundreds_gives_hundred(self) -> None:
        components = {
            "vuln_risk": 100.0,
            "quality_risk": 100.0,
            "deployment_risk": 100.0,
            "flow_risk": 100.0,
            "ownership_risk": 100.0,
        }
        assert _compute_composite(components) == 100.0

    def test_weights_sum_correctly(self) -> None:
        """Verify formula: 0.35*50 + 0.25*50 + 0.20*50 + 0.15*50 + 0.05*50 = 50"""
        components = {
            "vuln_risk": 50.0,
            "quality_risk": 50.0,
            "deployment_risk": 50.0,
            "flow_risk": 50.0,
            "ownership_risk": 50.0,
        }
        assert _compute_composite(components) == pytest.approx(50.0, abs=0.01)

    def test_highest_component_dominates(self) -> None:
        """vuln_risk has weight 0.35 — a high vuln score should dominate."""
        low_all = {
            "vuln_risk": 0.0,
            "quality_risk": 0.0,
            "deployment_risk": 0.0,
            "flow_risk": 0.0,
            "ownership_risk": 0.0,
        }
        high_vuln = dict(low_all)
        high_vuln["vuln_risk"] = 100.0

        assert _compute_composite(high_vuln) == pytest.approx(35.0, abs=0.01)


# ---------------------------------------------------------------------------
# _identify_primary_driver
# ---------------------------------------------------------------------------


class TestIdentifyPrimaryDriver:
    def test_returns_highest_component(self) -> None:
        components = {
            "vuln_risk": 80.0,
            "quality_risk": 60.0,
            "deployment_risk": 40.0,
            "flow_risk": 20.0,
            "ownership_risk": 10.0,
        }
        assert _identify_primary_driver(components) == "vuln_risk"

    def test_tie_broken_by_dict_ordering(self) -> None:
        """When scores are equal, max() returns the last encountered key
        — this is acceptable deterministic behaviour."""
        components = {
            "vuln_risk": 50.0,
            "quality_risk": 90.0,
            "deployment_risk": 50.0,
            "flow_risk": 50.0,
            "ownership_risk": 50.0,
        }
        assert _identify_primary_driver(components) == "quality_risk"


# ---------------------------------------------------------------------------
# compute_project_risk (integration — mocked I/O)
# ---------------------------------------------------------------------------


class TestComputeProjectRisk:
    def test_returns_risk_score_instance(self) -> None:
        dates = _weeks(10)
        synthetic_df = pd.DataFrame(
            {
                "week_date": dates,
                "project": ["Synth_A"] * 10,
                "open_bugs": [200 - i * 5 for i in range(10)],
                "p1_bugs": [0] * 10,
                "median_age_days": [50.0] * 10,
            }
        )

        def mock_load(metric: str, project: str | None, base_dir: Path) -> pd.DataFrame:
            if metric == "quality":
                return synthetic_df
            if metric == "security":
                return pd.DataFrame(
                    {
                        "week_date": dates,
                        "project": ["_portfolio"] * 10,
                        "total_vulnerabilities": [500] * 10,
                        "critical": [20] * 10,
                        "high": [480] * 10,
                    }
                )
            # Other metrics: empty (will use neutral score)
            return pd.DataFrame()

        with patch("execution.intelligence.risk_scorer.load_features", side_effect=mock_load):
            result = compute_project_risk("Synth_A")

        assert isinstance(result, RiskScore)
        assert result.project == "Synth_A"
        assert 0.0 <= result.total <= 100.0
        assert len(result.components) == 5

    def test_all_missing_data_uses_neutral(self) -> None:
        """When all feature loads fail, total should equal composite of all-50 = 50."""
        with patch(
            "execution.intelligence.risk_scorer.load_features",
            side_effect=ValueError("no data"),
        ):
            result = compute_project_risk("Synth_Z")

        assert result.total == pytest.approx(50.0, abs=0.01)

    def test_component_list_has_correct_names(self) -> None:
        expected_names = {
            "vuln_risk",
            "quality_risk",
            "deployment_risk",
            "flow_risk",
            "ownership_risk",
        }
        with patch(
            "execution.intelligence.risk_scorer.load_features",
            side_effect=ValueError("no data"),
        ):
            result = compute_project_risk("Synth_Z")

        assert {c.name for c in result.components} == expected_names

    def test_weighted_sums_are_correct(self) -> None:
        """Verify that each component's weighted = raw_score * weight."""
        with patch(
            "execution.intelligence.risk_scorer.load_features",
            side_effect=ValueError("no data"),
        ):
            result = compute_project_risk("Synth_Z")

        for comp in result.components:
            assert comp.weighted == pytest.approx(comp.raw_score * comp.weight, abs=0.01)


# ---------------------------------------------------------------------------
# compute_all_risks (mocked)
# ---------------------------------------------------------------------------


class TestComputeAllRisks:
    def test_empty_feature_store_returns_empty_list(self) -> None:
        with patch(
            "execution.intelligence.risk_scorer.load_features",
            side_effect=ValueError("no data"),
        ):
            result = compute_all_risks()

        assert result == []

    def test_results_sorted_descending_by_total(self) -> None:
        dates = _weeks(10)

        # Full two-project dataset used for both discovery and per-project loading
        full_df = pd.DataFrame(
            {
                "week_date": dates * 2,
                "project": ["Synth_A"] * 10 + ["Synth_B"] * 10,
                "open_bugs": [50] * 10 + [300] * 10,
                "p1_bugs": [0] * 20,
                "median_age_days": [20.0] * 20,
            }
        )

        def mock_load(metric: str, project: str | None, base_dir: Path) -> pd.DataFrame:
            if metric == "quality":
                if project is None:
                    return full_df
                # Per-project filter: return only matching rows
                return full_df[full_df["project"] == project].reset_index(drop=True)
            raise ValueError(f"no data for {metric}")

        with patch("execution.intelligence.risk_scorer.load_features", side_effect=mock_load):
            results = compute_all_risks()

        assert len(results) == 2
        assert results[0].total >= results[1].total


# ---------------------------------------------------------------------------
# save_risk_scores
# ---------------------------------------------------------------------------


class TestSaveRiskScores:
    def test_creates_json_file(self, tmp_path: Path, sample_risk_scores: list[RiskScore]) -> None:
        output = save_risk_scores(sample_risk_scores, base_dir=tmp_path)
        assert output.exists()
        assert output.suffix == ".json"

    def test_json_is_valid_and_contains_all_scores(self, tmp_path: Path, sample_risk_scores: list[RiskScore]) -> None:
        output = save_risk_scores(sample_risk_scores, base_dir=tmp_path)
        payload = json.loads(output.read_text(encoding="utf-8"))

        assert "generated_at" in payload
        assert "scores" in payload
        assert len(payload["scores"]) == len(sample_risk_scores)

    def test_project_names_present_in_output(self, tmp_path: Path, sample_risk_scores: list[RiskScore]) -> None:
        output = save_risk_scores(sample_risk_scores, base_dir=tmp_path)
        payload = json.loads(output.read_text(encoding="utf-8"))
        projects_in_file = {s["project"] for s in payload["scores"]}
        assert "Synth_A" in projects_in_file
        assert "Synth_B" in projects_in_file

    def test_base_dir_created_if_absent(self, tmp_path: Path, sample_risk_scores: list[RiskScore]) -> None:
        new_dir = tmp_path / "nested" / "insights"
        save_risk_scores(sample_risk_scores, base_dir=new_dir)
        assert new_dir.exists()

    def test_empty_scores_list_writes_valid_json(self, tmp_path: Path) -> None:
        output = save_risk_scores([], base_dir=tmp_path)
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["scores"] == []
