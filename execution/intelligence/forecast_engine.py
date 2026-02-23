"""
Forecast Engine — execution/intelligence/forecast_engine.py

Single responsibility: Generates P10/P50/P90 forecasts for metrics using
linear regression with confidence intervals (scipy.stats.linregress).

Security requirements satisfied:
- VALID_METRICS whitelist for all metric name → filename construction (Phase B cond. 1)
- PathValidator.validate_safe_path() called before every JSON write (Phase B cond. 2)
- Forecast JSON contains only generic project names (Phase B cond. 4)
"""

import json
import logging
from datetime import date, datetime
from pathlib import Path

import numpy as np
from scipy.stats import linregress

from execution.core.logging_config import get_logger
from execution.domain.intelligence import ForecastPoint, ForecastResult, TrendStrengthScore
from execution.intelligence.feature_engineering import VALID_METRICS, load_features
from execution.security.path_validator import PathValidator
from execution.security.validation import ValidationError

logger: logging.Logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FORECAST_HORIZONS: list[int] = [1, 4, 8, 13, 26]  # weeks ahead
MIN_DATA_POINTS: int = 12  # ~3 months of weekly data; raise ValueError if fewer
HOLDOUT_WEEKS: int = 4  # weeks withheld for MAPE back-test
_Z90: float = 1.645  # 90th percentile of standard normal (one-sided)


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------


def _validate_metric(metric: str) -> None:
    """Raise ValueError if metric is not in VALID_METRICS whitelist."""
    if metric not in VALID_METRICS:
        raise ValueError(f"Invalid metric '{metric}'. Allowed: {sorted(VALID_METRICS)}")


# ---------------------------------------------------------------------------
# Core regression helpers
# ---------------------------------------------------------------------------


def _fit_linear(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float, float]:
    """
    Fit a least-squares line and return (slope, intercept, r_squared, stderr).

    Args:
        x: Integer indices (0, 1, 2, ...).
        y: Observed values.

    Returns:
        (slope, intercept, r_squared, residual_stderr)
        r_squared clipped to [0.0, 1.0].
    """
    result = linregress(x, y)
    slope: float = float(result.slope)
    intercept: float = float(result.intercept)
    r_squared: float = float(max(0.0, min(1.0, result.rvalue**2)))

    # Residual standard error (std of prediction errors on training data)
    fitted = slope * x + intercept
    residuals = y - fitted
    n = len(y)
    # Use n-2 degrees of freedom for unbiased estimate
    stderr: float = float(np.sqrt(np.sum(residuals**2) / max(n - 2, 1)))

    return slope, intercept, r_squared, stderr


def _prediction_stderr(
    stderr_residual: float,
    x_train: np.ndarray,
    x_pred: float,
) -> float:
    """
    Standard error of a single prediction at x_pred, accounting for
    extrapolation distance from training mean.

    se_pred = stderr * sqrt(1 + 1/n + (x_pred - x_mean)^2 / SS_xx)
    """
    n = len(x_train)
    x_mean = float(np.mean(x_train))
    ss_xx = float(np.sum((x_train - x_mean) ** 2))
    if ss_xx == 0.0:
        return stderr_residual
    factor = 1.0 + 1.0 / n + (x_pred - x_mean) ** 2 / ss_xx
    return stderr_residual * float(np.sqrt(factor))


# ---------------------------------------------------------------------------
# MAPE back-test
# ---------------------------------------------------------------------------


def _compute_mape(y_values: np.ndarray) -> float:
    """
    Compute MAPE using a holdout of the last HOLDOUT_WEEKS weeks.

    Fit on [0 .. N-HOLDOUT_WEEKS-1], predict weeks N-HOLDOUT_WEEKS .. N-1.
    Returns MAPE in [0, 1] range (e.g. 0.08 = 8%).
    """
    n = len(y_values)
    train = y_values[: n - HOLDOUT_WEEKS]
    actual = y_values[n - HOLDOUT_WEEKS :]

    x_train = np.arange(len(train), dtype=float)
    slope, intercept, _, _ = _fit_linear(x_train, train)

    errors: list[float] = []
    for i, actual_val in enumerate(actual):
        x_pred = float(len(train) + i)
        predicted = slope * x_pred + intercept
        denom = max(abs(float(actual_val)), 1.0)
        errors.append(abs(float(actual_val) - predicted) / denom)

    return float(np.mean(errors)) if errors else 0.0


# ---------------------------------------------------------------------------
# Public API — forecast_metric
# ---------------------------------------------------------------------------


def forecast_metric(
    df,
    metric_col: str,
    project: str,
    horizons: list[int] = FORECAST_HORIZONS,
) -> ForecastResult:
    """
    Generate a P10/P50/P90 forecast for a single project/metric combination.

    Args:
        df:         DataFrame with columns [week_date, project, <metric_col>].
                    Output of load_features() — already filtered to one project.
        metric_col: Column to forecast (e.g. "open_bugs").
        project:    Project name (for labeling the ForecastResult).
        horizons:   Forecast horizons in weeks from the last observed data point.

    Returns:
        ForecastResult domain object with P10/P50/P90 bands.

    Raises:
        ValueError: If fewer than MIN_DATA_POINTS (12) non-null data points exist,
                    or if metric_col is absent from the DataFrame.
    """
    if metric_col not in df.columns:
        raise ValueError(f"Column '{metric_col}' not found in DataFrame. " f"Available: {list(df.columns)}")

    series = df[metric_col].dropna()
    n = len(series)

    if n < MIN_DATA_POINTS:
        raise ValueError(
            f"Insufficient data for '{metric_col}' / project '{project}': "
            f"{n} non-null points (minimum {MIN_DATA_POINTS} required)"
        )

    y = series.to_numpy(dtype=float)
    x = np.arange(n, dtype=float)

    slope, intercept, r_squared, stderr_residual = _fit_linear(x, y)
    mape = _compute_mape(y)

    # Build forecast points at each horizon
    last_x = float(n - 1)
    forecast_points: list[ForecastPoint] = []
    for h in horizons:
        x_pred = last_x + float(h)
        p50 = slope * x_pred + intercept
        se = _prediction_stderr(stderr_residual, x, x_pred)
        margin = _Z90 * se
        forecast_points.append(
            ForecastPoint(
                week=h,
                p10=float(p50 - margin),
                p50=float(p50),
                p90=float(p50 + margin),
            )
        )

    # Trend direction: slope relative to mean magnitude to normalise
    mean_abs = float(np.mean(np.abs(y))) if np.any(y != 0) else 1.0
    relative_slope = slope / mean_abs if mean_abs > 0 else slope
    if abs(relative_slope) < 0.005:
        direction = "flat"
    elif relative_slope < 0:
        direction = "improving"
    else:
        direction = "worsening"

    logger.info(
        "Forecast computed",
        extra={
            "project": project,
            "metric_col": metric_col,
            "n_points": n,
            "r_squared": round(r_squared, 3),
            "mape": round(mape, 3),
            "direction": direction,
        },
    )

    return ForecastResult(
        timestamp=datetime.now(),
        project=project,
        metric=metric_col,
        forecast=forecast_points,
        model="linear_regression",
        mape=mape,
        trend_direction=direction,
        trend_strength=r_squared,
    )


# ---------------------------------------------------------------------------
# Public API — compute_trend_strength
# ---------------------------------------------------------------------------


def compute_trend_strength(df, metric_col: str, project: str) -> TrendStrengthScore:
    """
    Compute trend strength score (R², direction, 0-100 score) for a metric.

    Args:
        df:         DataFrame with metric_col column (filtered to one project).
        metric_col: Column to analyse.
        project:    Project name for labeling.

    Returns:
        TrendStrengthScore domain object.
    """
    if metric_col not in df.columns:
        return TrendStrengthScore(
            timestamp=datetime.now(),
            project=project,
            metric=metric_col,
            score=0.0,
            direction="flat",
            r_squared=0.0,
            weeks_analyzed=0,
        )

    series = df[metric_col].dropna()
    n = len(series)

    if n < 2:
        return TrendStrengthScore(
            timestamp=datetime.now(),
            project=project,
            metric=metric_col,
            score=0.0,
            direction="flat",
            r_squared=0.0,
            weeks_analyzed=n,
        )

    y = series.to_numpy(dtype=float)
    x = np.arange(n, dtype=float)
    slope, _, r_squared, _ = _fit_linear(x, y)

    mean_abs = float(np.mean(np.abs(y))) if np.any(y != 0) else 1.0
    relative_slope = slope / mean_abs if mean_abs > 0 else slope
    if abs(relative_slope) < 0.005:
        direction = "flat"
    elif relative_slope < 0:
        direction = "improving"
    else:
        direction = "worsening"

    score = float(r_squared * 100.0)

    return TrendStrengthScore(
        timestamp=datetime.now(),
        project=project,
        metric=metric_col,
        score=score,
        direction=direction,
        r_squared=r_squared,
        weeks_analyzed=n,
    )


# ---------------------------------------------------------------------------
# Public API — forecast_all_projects
# ---------------------------------------------------------------------------


def forecast_all_projects(
    metric: str,
    metric_col: str,
    base_dir: Path = Path("data/features"),
) -> list[ForecastResult]:
    """
    Forecast all projects for a given metric.

    Loads the feature Parquet for the metric, then calls forecast_metric()
    for each project that has sufficient data.

    Args:
        metric:     Metric name — must be in VALID_METRICS.
        metric_col: Column to forecast within the feature DataFrame.
        base_dir:   Directory containing Parquet feature files.

    Returns:
        List of ForecastResult objects (one per project with enough data).
    """
    _validate_metric(metric)

    df_all = load_features(metric, base_dir=base_dir)

    if "project" not in df_all.columns:
        logger.warning(
            "No 'project' column found; forecasting as single series",
            extra={"metric": metric},
        )
        try:
            return [forecast_metric(df_all, metric_col, project="_all")]
        except ValueError as e:
            logger.error(
                "Forecast failed for single-series metric",
                extra={"metric": metric, "error": str(e)},
            )
            return []

    results: list[ForecastResult] = []
    for project_name in df_all["project"].unique():
        df_proj = df_all[df_all["project"] == project_name].reset_index(drop=True)
        try:
            result = forecast_metric(df_proj, metric_col, project=str(project_name))
            results.append(result)
        except ValueError as e:
            logger.warning(
                "Skipping project — insufficient data",
                extra={"metric": metric, "project": project_name, "error": str(e)},
            )

    logger.info(
        "Forecast all projects complete",
        extra={"metric": metric, "forecasted": len(results)},
    )
    return results


# ---------------------------------------------------------------------------
# Public API — save / load forecasts
# ---------------------------------------------------------------------------


def save_forecasts(
    results: list[ForecastResult],
    metric: str,
    base_dir: Path = Path("data/forecasts"),
) -> Path:
    """
    Save forecast results to JSON.

    Uses PathValidator.validate_safe_path() to prevent path traversal.

    Args:
        results:  List of ForecastResult objects to persist.
        metric:   Metric name — must be in VALID_METRICS.
        base_dir: Output directory (default: data/forecasts).

    Returns:
        Absolute Path of the written JSON file.

    Raises:
        ValueError: If metric is not in VALID_METRICS.
        ValidationError: If the resolved path escapes base_dir.
    """
    _validate_metric(metric)
    base_dir.mkdir(parents=True, exist_ok=True)

    date_str = date.today().isoformat()
    filename = f"{metric}_forecast_{date_str}.json"

    safe_path_str = PathValidator.validate_safe_path(
        base_dir=str(base_dir.resolve()),
        user_path=filename,
    )
    output_path = Path(safe_path_str)

    payload: list[dict] = []
    for r in results:
        payload.append(
            {
                "metric": r.metric,
                "project": r.project,
                "generated_date": r.timestamp.isoformat(),
                "forecast": [
                    {
                        "week": fp.week,
                        "p10": round(fp.p10, 4),
                        "p50": round(fp.p50, 4),
                        "p90": round(fp.p90, 4),
                    }
                    for fp in r.forecast
                ],
                "model": r.model,
                "mape": round(r.mape, 6),
                "trend_direction": r.trend_direction,
                "trend_strength": round(r.trend_strength, 6),
            }
        )

    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    logger.info(
        "Forecasts saved",
        extra={"metric": metric, "count": len(results), "path": str(output_path)},
    )
    return output_path


def load_forecasts(
    metric: str,
    base_dir: Path = Path("data/forecasts"),
) -> list[ForecastResult]:
    """
    Load forecast results from the most recent JSON file for a metric.

    Args:
        metric:   Metric name — must be in VALID_METRICS.
        base_dir: Directory containing forecast JSON files.

    Returns:
        List of ForecastResult objects.

    Raises:
        ValueError: If metric is not in VALID_METRICS or no forecast file found.
    """
    _validate_metric(metric)

    pattern = f"{metric}_forecast_*.json"
    candidates = sorted(base_dir.glob(pattern))

    if not candidates:
        raise ValueError(
            f"No forecast JSON found for metric '{metric}' in '{base_dir}'. "
            "Run forecast_all_projects() and save_forecasts() first."
        )

    latest = candidates[-1]
    raw_list = json.loads(latest.read_text(encoding="utf-8"))

    results: list[ForecastResult] = []
    for item in raw_list:
        try:
            results.append(ForecastResult.from_json(item))
        except (KeyError, ValueError) as e:
            logger.warning(
                "Skipping malformed forecast entry",
                extra={"error": str(e), "source": str(latest)},
            )

    logger.info(
        "Forecasts loaded",
        extra={"metric": metric, "count": len(results), "source": str(latest)},
    )
    return results


# ---------------------------------------------------------------------------
# __main__ entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    # Default: forecast open_bugs for all projects
    target_metric = sys.argv[1] if len(sys.argv) > 1 else "quality"
    target_col = sys.argv[2] if len(sys.argv) > 2 else "open_bugs"

    print(f"Forecasting metric='{target_metric}', column='{target_col}'")
    try:
        forecast_results = forecast_all_projects(target_metric, target_col)
        if not forecast_results:
            print("No results — ensure feature Parquet files exist in data/features/")
            sys.exit(1)

        out_path = save_forecasts(forecast_results, target_metric)
        print(f"Saved {len(forecast_results)} forecast(s) to: {out_path}")
        for fr in forecast_results:
            p4 = fr.forecast_4w
            p4_str = f"P50={p4.p50:.1f}" if p4 else "no 4w point"
            print(f"  {fr.project}: {fr.trend_direction} | {p4_str} | MAPE={fr.mape:.3f}")
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
