"""
Intelligence Pipeline Orchestrator.

Single entry point that runs all ML/analytics steps after data collection.
Called from CI (refresh-dashboards.yml) once metrics artifacts are available.

Pipeline steps (in order — each is independent; failure is logged, not fatal):
    1. Feature engineering  → data/features/*.parquet
    2. Forecasting          → data/forecasts/{metric}_forecast_{date}.json
    3. Risk scoring         → data/insights/risk_scores_{date}.json
    4. Model performance    → data/model_performance.json (MAPE tracking)

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
from execution.intelligence.feature_engineering import _build_all_features
from execution.intelligence.forecast_engine import forecast_all_projects, save_forecasts
from execution.intelligence.risk_scorer import compute_all_risks, save_risk_scores

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

_MODEL_PERF_PATH = Path("data/model_performance.json")


# ---------------------------------------------------------------------------
# Step 1: Feature engineering
# ---------------------------------------------------------------------------


def _run_feature_engineering() -> bool:
    """Build Parquet feature store from history JSON files. Returns True on success."""
    try:
        logger.info("Step 1/4 — Building feature store...")
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

    Returns list of model performance records for Step 4.
    Empty list signals total failure (individual metric failures are skipped).
    """
    records: list[dict] = []
    logger.info("Step 2/4 — Running forecasts for %d metric(s)...", len(_FORECAST_TARGETS))

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
    return records


# ---------------------------------------------------------------------------
# Step 3: Risk scoring
# ---------------------------------------------------------------------------


def _run_risk_scoring() -> bool:
    """Compute and persist composite risk scores for all projects."""
    try:
        logger.info("Step 3/4 — Computing risk scores...")
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
# Step 4: Model performance tracking
# ---------------------------------------------------------------------------


def _update_model_performance(forecast_records: list[dict]) -> None:
    """
    Merge new forecast MAPE records into data/model_performance.json.

    Existing entries are updated in-place by name; new entries are appended.
    The file is committed to the repo by the CI deploy job after each run.
    """
    logger.info("Step 4/4 — Updating model performance tracking...")
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

    # Step 3: Risk scoring (depends on feature store)
    if not _run_risk_scoring():
        steps_failed += 1

    # Step 4: Model performance (depends on forecast records)
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
