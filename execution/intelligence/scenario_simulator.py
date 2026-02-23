"""
Scenario Simulator — execution/intelligence/scenario_simulator.py

Monte Carlo simulation for engineering metric scenarios.
Generates P10/P50/P90 forecast bands under different parametric assumptions.

Typical usage:
    from execution.intelligence.scenario_simulator import run_monte_carlo, compare_scenarios

    result = run_monte_carlo(
        base_series=[300, 295, 290, 285, 280, 275, 270, 265, 260, 255, 250, 245],
        scenario_params={"closure_rate_multiplier": 1.5},
        horizon_weeks=13,
        n_simulations=1000,
        lower_is_better=True,
        scenario_name="Accelerated",
        metric="open_bugs",
    )

Security:
- All scenario parameters validated: bounded floats, no NaN/inf
- No file I/O in this module (pure computation)
- No pickle/joblib
- Uses np.random.default_rng (modern API, not legacy np.random.seed)
- All numpy arrays: float64, no object dtype
"""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np
from scipy.stats import linregress

from execution.domain.intelligence import ScenarioPoint, ScenarioResult

# ---------------------------------------------------------------------------
# Parameter bounds (security: clamp to prevent extreme values crashing numpy)
# ---------------------------------------------------------------------------

SCENARIO_PARAM_BOUNDS: dict[str, tuple[float, float]] = {
    "closure_rate_multiplier": (0.1, 10.0),
    "arrival_rate_multiplier": (0.1, 10.0),
    "velocity_multiplier": (0.1, 10.0),
    "trend_slope_override": (-50.0, 50.0),
}

_DEFAULT_BOUNDS: tuple[float, float] = (-100.0, 100.0)

# Minimum number of observations required to run a simulation
_MIN_DATA_POINTS: int = 4


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_scenario_params(params: dict[str, float]) -> dict[str, float]:
    """
    Validate and clamp scenario parameters.

    - Rejects NaN/inf values (raises ValueError)
    - Clamps each parameter to its SCENARIO_PARAM_BOUNDS entry,
      or to _DEFAULT_BOUNDS for unrecognised keys
    - Returns a new validated dict (does not mutate input)

    Args:
        params: Raw scenario parameters supplied by the caller.

    Returns:
        Validated and clamped parameter dict.

    Raises:
        ValueError: If any value is NaN or infinite.
    """
    validated: dict[str, float] = {}
    for key, value in params.items():
        float_val = float(value)
        if math.isnan(float_val):
            raise ValueError(f"Scenario parameter '{key}' is NaN — NaN values are not permitted.")
        if math.isinf(float_val):
            raise ValueError(f"Scenario parameter '{key}' is infinite — infinite values are not permitted.")
        lo, hi = SCENARIO_PARAM_BOUNDS.get(key, _DEFAULT_BOUNDS)
        validated[key] = max(lo, min(hi, float_val))
    return validated


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fit_slope_and_residual_std(series: list[float]) -> tuple[float, float]:
    """
    Fit a linear trend to series and return (slope, residual_std).

    Args:
        series: Observed values in chronological order (length >= _MIN_DATA_POINTS).

    Returns:
        (slope, residual_std) where residual_std is the standard deviation
        of the regression residuals (used for Monte Carlo noise sampling).
    """
    y = np.array(series, dtype=np.float64)
    x = np.arange(len(y), dtype=np.float64)
    result = linregress(x, y)
    slope = float(result.slope)
    intercept = float(result.intercept)

    fitted = slope * x + intercept
    residuals = y - fitted
    n = len(y)
    # Residual std with n-2 degrees of freedom (unbiased estimate)
    dof = max(n - 2, 1)
    residual_std = float(np.sqrt(np.sum(residuals**2) / dof))
    return slope, residual_std


def _apply_params_to_slope(
    base_slope: float,
    params: dict[str, float],
) -> float:
    """
    Modify the base trend slope according to scenario parameters.

    Priority order:
    1. If 'trend_slope_override' present, replace slope entirely.
    2. Otherwise apply multipliers:
       - velocity_multiplier: scales the slope
       - closure_rate_multiplier: multiplies the slope (for lower_is_better metrics,
         a stronger closure rate makes a negative slope more negative)
       - arrival_rate_multiplier: adds an offset that counteracts improvement
         (higher arrival rate means more items arriving, opposing closure)

    Args:
        base_slope: OLS slope from the historical series.
        params:     Validated scenario parameters.

    Returns:
        Modified slope float.
    """
    if "trend_slope_override" in params:
        return float(params["trend_slope_override"])

    slope = base_slope

    velocity = params.get("velocity_multiplier", 1.0)
    slope = slope * velocity

    closure = params.get("closure_rate_multiplier", 1.0)
    slope = slope * closure

    arrival = params.get("arrival_rate_multiplier", 1.0)
    # Arrival rate offsets improvement: adds a positive term proportional to
    # the absolute slope magnitude scaled by (arrival - 1.0)
    offset = abs(base_slope) * (arrival - 1.0)
    slope = slope + offset

    return slope


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_monte_carlo(
    base_series: list[float],
    scenario_params: dict[str, float],
    horizon_weeks: int = 13,
    n_simulations: int = 1000,
    lower_is_better: bool = True,
    scenario_name: str = "Scenario",
    metric: str = "metric",
    random_seed: int | None = None,
) -> ScenarioResult:
    """
    Run Monte Carlo simulation for a single scenario.

    Algorithm:
        1. Validate and clamp scenario_params.
        2. Fit linear trend to base_series (scipy.stats.linregress).
        3. Compute residual std from fit.
        4. Apply scenario_params to modify slope via _apply_params_to_slope().
        5. For each of n_simulations:
               project forward horizon_weeks from last observed value,
               sampling Gaussian noise (mean=0, std=residual_std) at each step.
        6. At each week, compute P10/P50/P90 across all simulations.
        7. Compute probability_of_improvement = fraction of simulations
           where final projected value is "better" than starting value.

    Args:
        base_series:     Historical observations in chronological order.
                         Minimum _MIN_DATA_POINTS (4) required.
        scenario_params: Scenario parameter overrides (see SCENARIO_PARAM_BOUNDS).
        horizon_weeks:   Number of weeks to project forward (default: 13).
        n_simulations:   Number of Monte Carlo runs (default: 1000).
        lower_is_better: True for bugs/vulns (decrease = good),
                         False for throughput (increase = good).
        scenario_name:   Display name for this scenario.
        metric:          Metric name for labelling output.
        random_seed:     Optional seed for reproducibility.

    Returns:
        ScenarioResult with P10/P50/P90 at each horizon week.

    Raises:
        ValueError: If base_series has fewer than _MIN_DATA_POINTS observations.
        ValueError: If any scenario_param value is NaN or infinite.
    """
    if len(base_series) < _MIN_DATA_POINTS:
        raise ValueError(
            f"Insufficient data for Monte Carlo simulation: "
            f"{len(base_series)} observations provided, "
            f"minimum {_MIN_DATA_POINTS} required."
        )

    validated_params = _validate_scenario_params(scenario_params)

    base_slope, residual_std = _fit_slope_and_residual_std(base_series)
    scenario_slope = _apply_params_to_slope(base_slope, validated_params)

    start_value = float(base_series[-1])
    rng = np.random.default_rng(random_seed)

    # Shape: (n_simulations, horizon_weeks)
    noise = rng.normal(loc=0.0, scale=max(residual_std, 1e-9), size=(n_simulations, horizon_weeks))
    noise = noise.astype(np.float64)

    # Project forward: each simulation is start + cumulative slope steps + noise
    # paths[i, w] = value at week (w+1) for simulation i
    slope_steps = np.arange(1, horizon_weeks + 1, dtype=np.float64) * scenario_slope
    # Broadcast slope_steps over all simulations then add cumulative noise
    cumulative_noise = np.cumsum(noise, axis=1)
    paths = start_value + slope_steps[np.newaxis, :] + cumulative_noise

    # Compute percentiles at each week
    p10_arr = np.percentile(paths, 10, axis=0)
    p50_arr = np.percentile(paths, 50, axis=0)
    p90_arr = np.percentile(paths, 90, axis=0)

    forecast_points: list[ScenarioPoint] = [
        ScenarioPoint(
            week=int(w + 1),
            p10=float(p10_arr[w]),
            p50=float(p50_arr[w]),
            p90=float(p90_arr[w]),
        )
        for w in range(horizon_weeks)
    ]

    # Probability of improvement: compare final projected value to start
    final_values = paths[:, -1]
    if lower_is_better:
        improved = float(np.sum(final_values < start_value)) / float(n_simulations)
    else:
        improved = float(np.sum(final_values > start_value)) / float(n_simulations)

    return ScenarioResult(
        timestamp=datetime.now(),
        scenario_name=scenario_name,
        metric=metric,
        horizon_weeks=horizon_weeks,
        n_simulations=n_simulations,
        forecast=forecast_points,
        probability_of_improvement=improved,
    )


def compare_scenarios(
    base_series: list[float],
    scenarios: dict[str, dict[str, float]],
    horizon_weeks: int = 13,
    n_simulations: int = 1000,
    lower_is_better: bool = True,
    metric: str = "metric",
    random_seed: int | None = None,
) -> list[ScenarioResult]:
    """
    Run multiple scenario comparisons and return results for all scenarios.

    Automatically includes a "BAU" (Business As Usual) scenario using the
    historical trend with no parameter modifications.

    Args:
        base_series:     Historical observations in chronological order.
        scenarios:       Mapping of scenario_name → parameter dict.
                         "BAU" is added automatically if not already present.
        horizon_weeks:   Number of weeks to project forward.
        n_simulations:   Number of Monte Carlo runs per scenario.
        lower_is_better: True for bugs/vulns, False for throughput.
        metric:          Metric name for labelling.
        random_seed:     Optional seed for reproducibility (same seed
                         applied per-scenario for consistent comparisons).

    Returns:
        List of ScenarioResult objects, one per scenario (BAU first).
    """
    all_scenarios: dict[str, dict[str, float]] = {}

    # BAU always first and always included
    if "BAU" not in scenarios:
        all_scenarios["BAU"] = {}
    else:
        all_scenarios["BAU"] = scenarios["BAU"]

    for name, params in scenarios.items():
        if name != "BAU":
            all_scenarios[name] = params

    results: list[ScenarioResult] = []
    for scenario_name, params in all_scenarios.items():
        result = run_monte_carlo(
            base_series=base_series,
            scenario_params=params,
            horizon_weeks=horizon_weeks,
            n_simulations=n_simulations,
            lower_is_better=lower_is_better,
            scenario_name=scenario_name,
            metric=metric,
            random_seed=random_seed,
        )
        results.append(result)

    return results
