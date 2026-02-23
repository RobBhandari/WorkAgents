"""
Tests for execution/intelligence/scenario_simulator.py

Covers:
- run_monte_carlo() happy path with valid 12-point series
- run_monte_carlo() with fewer than 4 points raises ValueError
- run_monte_carlo() with NaN param raises ValueError
- run_monte_carlo() with inf param raises ValueError
- compare_scenarios() returns list including "BAU"
- ScenarioResult.summary_p50_at_horizon returns correct value
- ScenarioResult.from_dict roundtrip
- Reproducibility: same seed yields same result
- _validate_scenario_params clamping behaviour
- P10 <= P50 <= P90 ordering is maintained
- probability_of_improvement is in [0.0, 1.0]
- compare_scenarios() BAU is always first
- compare_scenarios() with BAU already in input dict does not duplicate it
- trend_slope_override replaces slope
- All known scenario param keys are accepted
"""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np
import pytest

from execution.domain.intelligence import ScenarioPoint, ScenarioResult

_TS = datetime(2025, 10, 6)
from execution.intelligence.scenario_simulator import (
    SCENARIO_PARAM_BOUNDS,
    _validate_scenario_params,
    compare_scenarios,
    run_monte_carlo,
)

# ---------------------------------------------------------------------------
# Synthetic series helpers
# ---------------------------------------------------------------------------


def _declining_series(n: int = 12, start: float = 300.0, slope: float = -3.0) -> list[float]:
    """Generate a deterministic linearly declining series (lower_is_better=True scenario)."""
    return [start + slope * i for i in range(n)]


def _rising_series(n: int = 12, start: float = 50.0, slope: float = 2.0) -> list[float]:
    """Generate a deterministic linearly rising series (lower_is_better=False scenario)."""
    return [start + slope * i for i in range(n)]


# ---------------------------------------------------------------------------
# TestRunMonteCarlo — happy path
# ---------------------------------------------------------------------------


class TestRunMonteCarloHappyPath:
    def test_returns_scenario_result_type(self) -> None:
        series = _declining_series()
        result = run_monte_carlo(series, {}, random_seed=42)
        assert isinstance(result, ScenarioResult)

    def test_result_has_correct_scenario_name(self) -> None:
        series = _declining_series()
        result = run_monte_carlo(series, {}, scenario_name="TestScenario", random_seed=42)
        assert result.scenario_name == "TestScenario"

    def test_result_has_correct_metric(self) -> None:
        series = _declining_series()
        result = run_monte_carlo(series, {}, metric="open_bugs", random_seed=42)
        assert result.metric == "open_bugs"

    def test_result_has_correct_horizon_weeks(self) -> None:
        series = _declining_series()
        result = run_monte_carlo(series, {}, horizon_weeks=13, random_seed=42)
        assert result.horizon_weeks == 13

    def test_result_has_correct_n_simulations(self) -> None:
        series = _declining_series()
        result = run_monte_carlo(series, {}, n_simulations=500, random_seed=42)
        assert result.n_simulations == 500

    def test_forecast_length_matches_horizon_weeks(self) -> None:
        series = _declining_series()
        result = run_monte_carlo(series, {}, horizon_weeks=8, random_seed=42)
        assert len(result.forecast) == 8

    def test_forecast_weeks_are_1_indexed(self) -> None:
        """Week numbers should be 1 through horizon_weeks, not 0-based."""
        series = _declining_series()
        result = run_monte_carlo(series, {}, horizon_weeks=5, random_seed=42)
        weeks = [fp.week for fp in result.forecast]
        assert weeks == [1, 2, 3, 4, 5]

    def test_p10_lte_p50_for_all_weeks(self) -> None:
        series = _declining_series()
        result = run_monte_carlo(series, {}, horizon_weeks=13, n_simulations=2000, random_seed=42)
        for fp in result.forecast:
            assert fp.p10 <= fp.p50, f"P10 > P50 at week {fp.week}: {fp.p10} > {fp.p50}"

    def test_p50_lte_p90_for_all_weeks(self) -> None:
        series = _declining_series()
        result = run_monte_carlo(series, {}, horizon_weeks=13, n_simulations=2000, random_seed=42)
        for fp in result.forecast:
            assert fp.p50 <= fp.p90, f"P50 > P90 at week {fp.week}: {fp.p50} > {fp.p90}"

    def test_probability_of_improvement_in_unit_range(self) -> None:
        series = _declining_series()
        result = run_monte_carlo(series, {}, lower_is_better=True, random_seed=42)
        assert 0.0 <= result.probability_of_improvement <= 1.0

    def test_forecast_points_are_scenario_point_instances(self) -> None:
        series = _declining_series()
        result = run_monte_carlo(series, {}, random_seed=42)
        for fp in result.forecast:
            assert isinstance(fp, ScenarioPoint)

    def test_all_forecast_floats_are_finite(self) -> None:
        """Ensure no NaN or inf sneaks into the output."""
        series = _declining_series()
        result = run_monte_carlo(series, {}, random_seed=42)
        for fp in result.forecast:
            assert math.isfinite(fp.p10), f"p10 not finite at week {fp.week}"
            assert math.isfinite(fp.p50), f"p50 not finite at week {fp.week}"
            assert math.isfinite(fp.p90), f"p90 not finite at week {fp.week}"


# ---------------------------------------------------------------------------
# TestRunMonteCarloInsufficientData
# ---------------------------------------------------------------------------


class TestRunMonteCarloInsufficientData:
    def test_raises_value_error_for_zero_points(self) -> None:
        with pytest.raises(ValueError, match="minimum 4 required"):
            run_monte_carlo([], {})

    def test_raises_value_error_for_one_point(self) -> None:
        with pytest.raises(ValueError, match="minimum 4 required"):
            run_monte_carlo([100.0], {})

    def test_raises_value_error_for_two_points(self) -> None:
        with pytest.raises(ValueError, match="minimum 4 required"):
            run_monte_carlo([100.0, 95.0], {})

    def test_raises_value_error_for_three_points(self) -> None:
        with pytest.raises(ValueError, match="minimum 4 required"):
            run_monte_carlo([100.0, 95.0, 90.0], {})

    def test_does_not_raise_for_exactly_four_points(self) -> None:
        """Exactly at the minimum — should succeed."""
        result = run_monte_carlo([100.0, 95.0, 90.0, 85.0], {}, random_seed=0)
        assert isinstance(result, ScenarioResult)

    def test_does_not_raise_for_large_series(self) -> None:
        series = _declining_series(n=52)
        result = run_monte_carlo(series, {}, random_seed=0)
        assert isinstance(result, ScenarioResult)


# ---------------------------------------------------------------------------
# TestRunMonteCarloInvalidParams
# ---------------------------------------------------------------------------


class TestRunMonteCarloInvalidParams:
    def test_raises_value_error_for_nan_param(self) -> None:
        series = _declining_series()
        with pytest.raises(ValueError, match="NaN"):
            run_monte_carlo(series, {"closure_rate_multiplier": float("nan")})

    def test_raises_value_error_for_positive_inf_param(self) -> None:
        series = _declining_series()
        with pytest.raises(ValueError, match="infinite"):
            run_monte_carlo(series, {"velocity_multiplier": float("inf")})

    def test_raises_value_error_for_negative_inf_param(self) -> None:
        series = _declining_series()
        with pytest.raises(ValueError, match="infinite"):
            run_monte_carlo(series, {"arrival_rate_multiplier": float("-inf")})

    def test_nan_in_unknown_key_also_raises(self) -> None:
        series = _declining_series()
        with pytest.raises(ValueError, match="NaN"):
            run_monte_carlo(series, {"some_unknown_param": float("nan")})


# ---------------------------------------------------------------------------
# TestReproducibility
# ---------------------------------------------------------------------------


class TestReproducibility:
    def test_same_seed_produces_identical_p50_values(self) -> None:
        series = _declining_series()
        result_a = run_monte_carlo(series, {}, random_seed=99)
        result_b = run_monte_carlo(series, {}, random_seed=99)
        for a, b in zip(result_a.forecast, result_b.forecast, strict=True):
            assert a.p50 == b.p50, f"P50 differs at week {a.week}: {a.p50} vs {b.p50}"

    def test_same_seed_produces_identical_probability(self) -> None:
        series = _declining_series()
        result_a = run_monte_carlo(series, {}, random_seed=99)
        result_b = run_monte_carlo(series, {}, random_seed=99)
        assert result_a.probability_of_improvement == result_b.probability_of_improvement

    def test_different_seeds_may_differ(self) -> None:
        """With high n_simulations, different seeds should produce different results."""
        series = _declining_series(n=20)
        result_a = run_monte_carlo(series, {}, n_simulations=500, random_seed=1)
        result_b = run_monte_carlo(series, {}, n_simulations=500, random_seed=2)
        # P50 values will differ due to different random draws
        # We check that at least one week differs (almost certain for 500 sims)
        p50_a = [fp.p50 for fp in result_a.forecast]
        p50_b = [fp.p50 for fp in result_b.forecast]
        assert p50_a != p50_b

    def test_none_seed_does_not_raise(self) -> None:
        """random_seed=None should work without error."""
        series = _declining_series()
        result = run_monte_carlo(series, {}, random_seed=None)
        assert isinstance(result, ScenarioResult)


# ---------------------------------------------------------------------------
# TestScenarioParams — clamping and known keys
# ---------------------------------------------------------------------------


class TestValidateScenarioParams:
    def test_valid_params_returned_unchanged_within_bounds(self) -> None:
        params = {"closure_rate_multiplier": 2.0, "velocity_multiplier": 1.5}
        validated = _validate_scenario_params(params)
        assert validated["closure_rate_multiplier"] == 2.0
        assert validated["velocity_multiplier"] == 1.5

    def test_params_above_upper_bound_are_clamped(self) -> None:
        upper = SCENARIO_PARAM_BOUNDS["closure_rate_multiplier"][1]
        params = {"closure_rate_multiplier": upper * 100.0}
        validated = _validate_scenario_params(params)
        assert validated["closure_rate_multiplier"] == upper

    def test_params_below_lower_bound_are_clamped(self) -> None:
        lower = SCENARIO_PARAM_BOUNDS["closure_rate_multiplier"][0]
        params = {"closure_rate_multiplier": lower / 100.0}
        validated = _validate_scenario_params(params)
        assert validated["closure_rate_multiplier"] == lower

    def test_unknown_key_uses_default_bounds(self) -> None:
        """Unknown keys are clamped to _DEFAULT_BOUNDS (-100, 100)."""
        params = {"unknown_param": 999.0}
        validated = _validate_scenario_params(params)
        assert validated["unknown_param"] == 100.0

    def test_nan_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="NaN"):
            _validate_scenario_params({"closure_rate_multiplier": float("nan")})

    def test_inf_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="infinite"):
            _validate_scenario_params({"velocity_multiplier": float("inf")})

    def test_empty_params_returns_empty_dict(self) -> None:
        result = _validate_scenario_params({})
        assert result == {}

    def test_all_known_keys_are_accepted(self) -> None:
        params = {
            "closure_rate_multiplier": 1.5,
            "arrival_rate_multiplier": 1.2,
            "velocity_multiplier": 1.0,
            "trend_slope_override": -5.0,
        }
        validated = _validate_scenario_params(params)
        assert set(validated.keys()) == set(params.keys())

    def test_trend_slope_override_is_clamped(self) -> None:
        lo, hi = SCENARIO_PARAM_BOUNDS["trend_slope_override"]
        params = {"trend_slope_override": hi * 10.0}
        validated = _validate_scenario_params(params)
        assert validated["trend_slope_override"] == hi

    def test_returns_new_dict_does_not_mutate_input(self) -> None:
        original = {"closure_rate_multiplier": 2.0}
        original_copy = dict(original)
        _validate_scenario_params(original)
        assert original == original_copy


# ---------------------------------------------------------------------------
# TestTrendSlopeOverride
# ---------------------------------------------------------------------------


class TestTrendSlopeOverride:
    def test_slope_override_replaces_historical_trend(self) -> None:
        """
        With trend_slope_override=-10.0 on a large-N series, the P50
        trajectory should decrease by ~10 per week, not follow the historical slope.
        """
        # Use a flat series so historical slope ~ 0
        flat_series = [100.0] * 20
        result_override = run_monte_carlo(
            flat_series,
            {"trend_slope_override": -10.0},
            horizon_weeks=5,
            n_simulations=2000,
            random_seed=42,
        )
        result_bau = run_monte_carlo(
            flat_series,
            {},
            horizon_weeks=5,
            n_simulations=2000,
            random_seed=42,
        )
        # With override slope=-10, P50 at week 5 should be ~50 (100 + 5*-10)
        # BAU with flat series should have P50 at week 5 near 100
        override_p50_w5 = result_override.forecast[4].p50
        bau_p50_w5 = result_bau.forecast[4].p50
        assert (
            override_p50_w5 < bau_p50_w5
        ), f"Expected override P50 ({override_p50_w5:.1f}) < BAU P50 ({bau_p50_w5:.1f})"

    def test_closure_rate_multiplier_accelerates_declining_trend(self) -> None:
        """
        closure_rate_multiplier > 1.0 on a declining series should produce
        a steeper decline (lower P50 at horizon) than BAU.
        """
        series = _declining_series(n=20)
        result_accel = run_monte_carlo(
            series,
            {"closure_rate_multiplier": 2.0},
            horizon_weeks=13,
            n_simulations=1000,
            random_seed=42,
        )
        result_bau = run_monte_carlo(
            series,
            {},
            horizon_weeks=13,
            n_simulations=1000,
            random_seed=42,
        )
        # Accelerated should have lower P50 at horizon (more bugs closed)
        assert result_accel.summary_p50_at_horizon < result_bau.summary_p50_at_horizon


# ---------------------------------------------------------------------------
# TestProbabilityOfImprovement
# ---------------------------------------------------------------------------


class TestProbabilityOfImprovement:
    def test_strongly_declining_trend_has_high_improvement_probability(self) -> None:
        """A clearly declining (lower_is_better) series should have high P(improve)."""
        series = [300.0 - i * 10.0 for i in range(20)]
        result = run_monte_carlo(series, {}, lower_is_better=True, n_simulations=2000, random_seed=42)
        assert result.probability_of_improvement > 0.6

    def test_strongly_rising_trend_lower_is_better_has_low_improvement_probability(self) -> None:
        """A worsening trend (rising) with lower_is_better should have low P(improve)."""
        series = [50.0 + i * 10.0 for i in range(20)]
        result = run_monte_carlo(series, {}, lower_is_better=True, n_simulations=2000, random_seed=42)
        assert result.probability_of_improvement < 0.4

    def test_lower_is_better_false_uses_increase_as_improvement(self) -> None:
        """For throughput metrics, increase = improvement."""
        series = _rising_series(n=20)
        result = run_monte_carlo(series, {}, lower_is_better=False, n_simulations=2000, random_seed=42)
        # Rising trend + lower_is_better=False → high probability
        assert result.probability_of_improvement > 0.5


# ---------------------------------------------------------------------------
# TestCompareScenarios
# ---------------------------------------------------------------------------


class TestCompareScenarios:
    def test_returns_list(self) -> None:
        series = _declining_series()
        results = compare_scenarios(series, {"Accelerated": {"closure_rate_multiplier": 2.0}}, random_seed=42)
        assert isinstance(results, list)

    def test_bau_always_included(self) -> None:
        series = _declining_series()
        results = compare_scenarios(series, {"Sprint": {"velocity_multiplier": 1.5}}, random_seed=42)
        scenario_names = [r.scenario_name for r in results]
        assert "BAU" in scenario_names

    def test_bau_is_first_in_list(self) -> None:
        series = _declining_series()
        results = compare_scenarios(
            series,
            {"Accelerated": {"closure_rate_multiplier": 2.0}, "Sprint": {"velocity_multiplier": 1.5}},
            random_seed=42,
        )
        assert results[0].scenario_name == "BAU"

    def test_all_named_scenarios_are_present(self) -> None:
        series = _declining_series()
        results = compare_scenarios(
            series,
            {
                "Accelerated": {"closure_rate_multiplier": 2.0},
                "Conservative": {"closure_rate_multiplier": 0.5},
            },
            random_seed=42,
        )
        names = {r.scenario_name for r in results}
        assert "BAU" in names
        assert "Accelerated" in names
        assert "Conservative" in names

    def test_total_result_count_is_named_plus_bau(self) -> None:
        series = _declining_series()
        input_scenarios: dict[str, dict[str, float]] = {"Alpha": {}, "Beta": {}}
        results = compare_scenarios(series, input_scenarios, random_seed=42)
        # BAU + Alpha + Beta = 3
        assert len(results) == 3

    def test_bau_already_present_not_duplicated(self) -> None:
        """If caller passes 'BAU' explicitly, it should not appear twice."""
        series = _declining_series()
        results = compare_scenarios(series, {"BAU": {}, "Sprint": {"velocity_multiplier": 1.2}}, random_seed=42)
        bau_count = sum(1 for r in results if r.scenario_name == "BAU")
        assert bau_count == 1

    def test_all_results_are_scenario_result_instances(self) -> None:
        series = _declining_series()
        results = compare_scenarios(series, {"Accel": {"closure_rate_multiplier": 1.5}}, random_seed=42)
        for r in results:
            assert isinstance(r, ScenarioResult)

    def test_empty_scenarios_dict_returns_only_bau(self) -> None:
        series = _declining_series()
        results = compare_scenarios(series, {}, random_seed=42)
        assert len(results) == 1
        assert results[0].scenario_name == "BAU"

    def test_metric_propagated_to_all_results(self) -> None:
        series = _declining_series()
        results = compare_scenarios(series, {"Accel": {}}, metric="vulnerabilities", random_seed=42)
        for r in results:
            assert r.metric == "vulnerabilities"

    def test_compare_raises_on_short_series(self) -> None:
        with pytest.raises(ValueError, match="minimum 4 required"):
            compare_scenarios([100.0, 90.0], {"Sprint": {}})


# ---------------------------------------------------------------------------
# TestScenarioResultDomainModel
# ---------------------------------------------------------------------------


class TestScenarioResultDomainModel:
    def _make_result(self) -> ScenarioResult:
        return ScenarioResult(
            timestamp=_TS,
            scenario_name="BAU",
            metric="open_bugs",
            horizon_weeks=5,
            n_simulations=1000,
            forecast=[
                ScenarioPoint(week=1, p10=290.0, p50=295.0, p90=300.0),
                ScenarioPoint(week=2, p10=285.0, p50=290.0, p90=295.0),
                ScenarioPoint(week=3, p10=280.0, p50=285.0, p90=290.0),
                ScenarioPoint(week=4, p10=275.0, p50=280.0, p90=285.0),
                ScenarioPoint(week=5, p10=270.0, p50=275.0, p90=280.0),
            ],
            probability_of_improvement=0.72,
        )

    def test_summary_p50_at_horizon_returns_last_week_p50(self) -> None:
        result = self._make_result()
        assert result.summary_p50_at_horizon == 275.0

    def test_summary_p50_at_horizon_empty_forecast_returns_zero(self) -> None:
        result = ScenarioResult(
            timestamp=_TS,
            scenario_name="Empty",
            metric="bugs",
            horizon_weeks=0,
            n_simulations=0,
            forecast=[],
            probability_of_improvement=0.0,
        )
        assert result.summary_p50_at_horizon == 0.0

    def test_summary_p50_at_horizon_single_point(self) -> None:
        result = ScenarioResult(
            timestamp=_TS,
            scenario_name="Single",
            metric="bugs",
            horizon_weeks=1,
            n_simulations=100,
            forecast=[ScenarioPoint(week=1, p10=90.0, p50=100.0, p90=110.0)],
            probability_of_improvement=0.5,
        )
        assert result.summary_p50_at_horizon == 100.0

    def test_description_defaults_to_empty_string(self) -> None:
        result = self._make_result()
        assert result.description == ""

    def test_description_can_be_set(self) -> None:
        result = ScenarioResult(
            timestamp=_TS,
            scenario_name="BAU",
            metric="bugs",
            horizon_weeks=1,
            n_simulations=100,
            forecast=[],
            probability_of_improvement=0.5,
            description="Business as usual trajectory.",
        )
        assert result.description == "Business as usual trajectory."


# ---------------------------------------------------------------------------
# TestScenarioResultFromDict — roundtrip
# ---------------------------------------------------------------------------


class TestScenarioResultFromDict:
    def _make_dict(self) -> dict:
        return {
            "scenario_name": "Accelerated",
            "metric": "vulnerabilities",
            "horizon_weeks": 3,
            "n_simulations": 500,
            "forecast": [
                {"week": 1, "p10": 180.0, "p50": 200.0, "p90": 220.0},
                {"week": 2, "p10": 160.0, "p50": 180.0, "p90": 200.0},
                {"week": 3, "p10": 140.0, "p50": 160.0, "p90": 180.0},
            ],
            "probability_of_improvement": 0.85,
            "description": "Accelerated remediation scenario.",
        }

    def test_from_dict_returns_scenario_result_instance(self) -> None:
        data = self._make_dict()
        result = ScenarioResult.from_dict(data)
        assert isinstance(result, ScenarioResult)

    def test_from_dict_scenario_name(self) -> None:
        data = self._make_dict()
        result = ScenarioResult.from_dict(data)
        assert result.scenario_name == "Accelerated"

    def test_from_dict_metric(self) -> None:
        data = self._make_dict()
        result = ScenarioResult.from_dict(data)
        assert result.metric == "vulnerabilities"

    def test_from_dict_horizon_weeks(self) -> None:
        data = self._make_dict()
        result = ScenarioResult.from_dict(data)
        assert result.horizon_weeks == 3

    def test_from_dict_n_simulations(self) -> None:
        data = self._make_dict()
        result = ScenarioResult.from_dict(data)
        assert result.n_simulations == 500

    def test_from_dict_probability_of_improvement(self) -> None:
        data = self._make_dict()
        result = ScenarioResult.from_dict(data)
        assert result.probability_of_improvement == pytest.approx(0.85)

    def test_from_dict_forecast_count(self) -> None:
        data = self._make_dict()
        result = ScenarioResult.from_dict(data)
        assert len(result.forecast) == 3

    def test_from_dict_forecast_points_are_scenario_points(self) -> None:
        data = self._make_dict()
        result = ScenarioResult.from_dict(data)
        for fp in result.forecast:
            assert isinstance(fp, ScenarioPoint)

    def test_from_dict_first_forecast_values(self) -> None:
        data = self._make_dict()
        result = ScenarioResult.from_dict(data)
        first = result.forecast[0]
        assert first.week == 1
        assert first.p10 == 180.0
        assert first.p50 == 200.0
        assert first.p90 == 220.0

    def test_from_dict_description(self) -> None:
        data = self._make_dict()
        result = ScenarioResult.from_dict(data)
        assert result.description == "Accelerated remediation scenario."

    def test_from_dict_missing_description_defaults_to_empty(self) -> None:
        data = self._make_dict()
        del data["description"]
        result = ScenarioResult.from_dict(data)
        assert result.description == ""

    def test_from_dict_empty_forecast_list(self) -> None:
        data = self._make_dict()
        data["forecast"] = []
        result = ScenarioResult.from_dict(data)
        assert result.forecast == []

    def test_from_dict_summary_p50_at_horizon_roundtrip(self) -> None:
        data = self._make_dict()
        result = ScenarioResult.from_dict(data)
        # Horizon week 3 has p50=160.0
        assert result.summary_p50_at_horizon == 160.0


# ---------------------------------------------------------------------------
# TestScenarioPoint
# ---------------------------------------------------------------------------


class TestScenarioPoint:
    def test_scenario_point_stores_fields(self) -> None:
        sp = ScenarioPoint(week=4, p10=90.0, p50=100.0, p90=110.0)
        assert sp.week == 4
        assert sp.p10 == 90.0
        assert sp.p50 == 100.0
        assert sp.p90 == 110.0
