"""
Intelligence Pipeline Orchestrator.

Single entry point that runs all ML/analytics steps after data collection.
Called from CI (refresh-dashboards.yml) once metrics artifacts are available.

Pipeline steps (in order — each is independent; failure is logged, not fatal):
    1. Feature engineering  → data/features/*.parquet
    2. Forecasting          → data/forecasts/{metric}_forecast_{date}.json
                           → data/forecasts/forecast_summary.json
    3. Scenario simulation  → data/insights/scenario_results_{date}.json
    4. Risk scoring         → data/insights/risk_scores_{date}.json
    5. Model performance    → data/model_performance.json (MAPE tracking)

Usage:
    python scripts/run_intelligence_pipeline.py

Exit codes:
    0 — all steps succeeded
    1 — one or more steps failed (partial output may still be present)
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from execution.core.logging_config import get_logger
from execution.intelligence.feature_engineering import _build_all_features, load_features
from execution.intelligence.forecast_engine import forecast_all_projects, save_forecasts
from execution.intelligence.risk_scorer import compute_all_risks, save_risk_scores
from execution.intelligence.scenario_simulator import compare_scenarios

logger: logging.Logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Metric → primary forecast column pairs.
# Only metrics with reliable per-project time-series are included.
# Security is portfolio-level only (_portfolio) — excluded from per-project forecast.
# ---------------------------------------------------------------------------
_FORECAST_TARGETS: list[tuple[str, str]] = [
    ("quality", "open_bugs"),
    ("flow", "throughput"),
    ("deployment", "build_success_rate"),
    ("ownership", "unassigned_pct"),
]

# Metrics where lower values are better (bugs, unassigned work)
_LOWER_IS_BETTER: frozenset[str] = frozenset({"open_bugs", "unassigned_pct"})

_MODEL_PERF_PATH = Path("data/model_performance.json")
_FORECASTS_DIR = Path("data/forecasts")
_INSIGHTS_DIR = Path("data/insights")


# ---------------------------------------------------------------------------
# Step 1: Feature engineering
# ---------------------------------------------------------------------------


def _run_feature_engineering() -> bool:
    """Build Parquet feature store from history JSON files. Returns True on success."""
    try:
        logger.info("Step 1/5 — Building feature store...")
        _build_all_features()
        logger.info("Feature store built successfully.")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Feature engineering failed", extra={"error": str(exc)})
        return False


# ---------------------------------------------------------------------------
# Step 2: Forecasting
# ---------------------------------------------------------------------------


def _run_forecasts() -> list[dict]:
    """
    Run P10/P50/P90 forecasts for all configured metric/column pairs.

    Returns list of model performance records for Step 5.
    Empty list signals total failure (individual metric failures are skipped).
    Also writes data/forecasts/forecast_summary.json for the Executive Panel.
    """
    records: list[dict] = []
    logger.info("Step 2/5 — Running forecasts for %d metric(s)...", len(_FORECAST_TARGETS))

    for metric, col in _FORECAST_TARGETS:
        try:
            results = forecast_all_projects(metric, col)
            if not results:
                logger.warning(
                    "No forecast results — feature file may be absent",
                    extra={"metric": metric},
                )
                continue
            save_forecasts(results, metric)
            avg_mape = sum(r.mape for r in results) / len(results)
            records.append(
                {
                    "name": f"forecast_{metric}",
                    "metric": metric,
                    "column": col,
                    "project_count": len(results),
                    "mape": round(avg_mape, 4),
                    "accuracy": round(1.0 - avg_mape, 4),
                    "status": "pass" if avg_mape < 0.15 else "degraded",
                    "last_updated": datetime.now().isoformat(),
                }
            )
            logger.info(
                "Forecast saved",
                extra={
                    "metric": metric,
                    "projects": len(results),
                    "avg_mape": round(avg_mape, 4),
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Forecast failed for metric",
                extra={"metric": metric, "error": str(exc)},
            )

    logger.info("Forecasting complete — %d metric(s) succeeded.", len(records))
    _write_forecast_summary(records)
    return records


def _write_forecast_summary(forecast_records: list[dict]) -> None:
    """
    Write data/forecasts/forecast_summary.json for the Executive Panel.

    Derives org_trend from pass/degraded counts across all forecast models.
    No-op when forecast_records is empty.
    """
    if not forecast_records:
        return
    try:
        pass_count = sum(1 for r in forecast_records if r.get("status") == "pass")
        degraded_count = len(forecast_records) - pass_count
        if degraded_count == 0:
            org_trend = "improving"
        elif pass_count == 0:
            org_trend = "worsening"
        else:
            org_trend = "stable"

        _FORECASTS_DIR.mkdir(parents=True, exist_ok=True)
        summary = {
            "org_trend": org_trend,
            "pass_count": pass_count,
            "degraded_count": degraded_count,
            "last_updated": datetime.now().isoformat(),
        }
        (_FORECASTS_DIR / "forecast_summary.json").write_text(json.dumps(summary, indent=2))
        logger.info("Forecast summary written", extra={"org_trend": org_trend})
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to write forecast summary", extra={"error": str(exc)})


# ---------------------------------------------------------------------------
# Step 3: Scenario simulation
# ---------------------------------------------------------------------------


def _run_scenarios() -> bool:
    """
    Run Monte Carlo scenario analysis for all forecast targets.

    For each metric, loads the org-level weekly time series from the feature
    store, runs BAU + Accelerated + Conservative scenarios, and saves results
    to data/insights/scenario_results_{date}.json.
    """
    try:
        logger.info("Step 3/5 — Running scenario simulations...")
        all_entries: list[dict] = []

        for metric, col in _FORECAST_TARGETS:
            try:
                df = load_features(metric)
                if col not in df.columns:
                    logger.warning(
                        "Column not in features — skipping scenario",
                        extra={"metric": metric, "column": col},
                    )
                    continue

                # Aggregate to org-level weekly mean time series
                series: list[float] = df.sort_values("week_date").groupby("week_date")[col].mean().dropna().tolist()
                if len(series) < 4:
                    logger.warning(
                        "Insufficient data for scenarios",
                        extra={"metric": metric, "points": len(series)},
                    )
                    continue

                lower_is_better = col in _LOWER_IS_BETTER
                accelerated_params = (
                    {"closure_rate_multiplier": 1.5} if lower_is_better else {"velocity_multiplier": 1.5}
                )
                scenarios = {
                    "Accelerated": accelerated_params,
                    "Conservative": {"arrival_rate_multiplier": 1.5},
                }

                results = compare_scenarios(
                    base_series=series,
                    scenarios=scenarios,
                    horizon_weeks=13,
                    metric=col,
                    lower_is_better=lower_is_better,
                    random_seed=42,
                )

                for sr in results:
                    all_entries.append(
                        {
                            "scenario_name": sr.scenario_name,
                            "metric": sr.metric,
                            "horizon_weeks": sr.horizon_weeks,
                            "n_simulations": sr.n_simulations,
                            "forecast": [
                                {
                                    "week": p.week,
                                    "p10": p.p10,
                                    "p50": p.p50,
                                    "p90": p.p90,
                                }
                                for p in sr.forecast
                            ],
                            "probability_of_improvement": sr.probability_of_improvement,
                            "description": sr.description,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

                logger.info(
                    "Scenarios computed",
                    extra={"metric": metric, "scenarios": len(results)},
                )

            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Scenario failed for metric",
                    extra={"metric": metric, "error": str(exc)},
                )

        if not all_entries:
            logger.warning("No scenario results produced.")
            return False

        _INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        out_path = _INSIGHTS_DIR / f"scenario_results_{date_str}.json"
        out_path.write_text(json.dumps(all_entries, indent=2))
        logger.info(
            "Scenario results saved",
            extra={"total_scenarios": len(all_entries), "path": str(out_path)},
        )
        return True

    except Exception as exc:  # noqa: BLE001
        logger.error("Scenario simulation failed", extra={"error": str(exc)})
        return False


# ---------------------------------------------------------------------------
# Step 4: Risk scoring
# ---------------------------------------------------------------------------


def _run_risk_scoring() -> bool:
    """Compute and persist composite risk scores for all projects."""
    try:
        logger.info("Step 4/5 — Computing risk scores...")
        scores = compute_all_risks()
        if not scores:
            logger.warning("No risk scores computed — feature store may be empty")
            return False
        save_risk_scores(scores)
        logger.info("Risk scoring complete", extra={"project_count": len(scores)})
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Risk scoring failed", extra={"error": str(exc)})
        return False


# ---------------------------------------------------------------------------
# Step 5: Model performance tracking
# ---------------------------------------------------------------------------


def _update_model_performance(forecast_records: list[dict]) -> None:
    """
    Merge new forecast MAPE records into data/model_performance.json.

    Existing entries are updated in-place by name; new entries are appended.
    The file is committed to the repo by the CI deploy job after each run.
    """
    logger.info("Step 5/5 — Updating model performance tracking...")
    if not forecast_records:
        logger.info("No forecast records to write — skipping model performance update.")
        return

    try:
        existing: dict = json.loads(_MODEL_PERF_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        existing = {"last_updated": None, "models": []}

    # Merge by name (update existing, append new)
    existing_by_name: dict[str, dict] = {m["name"]: m for m in existing.get("models", [])}
    for record in forecast_records:
        existing_by_name[record["name"]] = record

    existing["models"] = sorted(existing_by_name.values(), key=lambda m: m["name"])
    existing["last_updated"] = datetime.now().isoformat()

    _MODEL_PERF_PATH.write_text(json.dumps(existing, indent=2))
    logger.info(
        "model_performance.json updated",
        extra={"model_count": len(existing["models"])},
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> int:
    """
    Run the full intelligence pipeline.

    Returns:
        0 — all steps succeeded
        1 — one or more steps failed (partial output may still be usable)
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    logger.info("=== Intelligence Pipeline starting ===")

    steps_failed = 0

    # Step 1: Feature engineering (required — all downstream steps depend on it)
    if not _run_feature_engineering():
        logger.error("Feature engineering failed — downstream steps may produce no output.")
        steps_failed += 1

    # Step 2: Forecasting (depends on feature store)
    forecast_records = _run_forecasts()
    if not forecast_records:
        steps_failed += 1

    # Step 3: Scenario simulation (depends on feature store)
    if not _run_scenarios():
        steps_failed += 1

    # Step 4: Risk scoring (depends on feature store)
    if not _run_risk_scoring():
        steps_failed += 1

    # Step 5: Model performance (depends on forecast records)
    _update_model_performance(forecast_records)

    if steps_failed:
        logger.warning(
            "=== Intelligence Pipeline finished with failures ===",
            extra={"steps_failed": steps_failed},
        )
        return 1

    logger.info("=== Intelligence Pipeline complete — all steps passed ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
