"""
Signal v1 — Rule-based signal detection over Executive Trends metrics.

Three rule families:

  threshold_breach        — fixed baseline (deployment build success: 90.0%)
  sustained_deterioration — worsening in >= 3 of the last 4 consecutive pairs
  recovery_trend          — improving in >= 3 of the last 4 consecutive pairs

Input : the ``metrics`` list returned by build_trends_context()
        (rendered dashboard cards, each with ``id``, ``current``, ``data``).
Output: deterministically-ranked list of up to MAX_SIGNALS signals.

Public entry point: build_signals_response(metrics) -> dict
"""

from __future__ import annotations

import statistics
from datetime import UTC, datetime, timezone
from typing import Any

# Maximum signals to surface per response.
MAX_SIGNALS = 5

# Minimum data points required for deterioration / recovery rules.
# Rule inspects 4 consecutive *pairs*, which requires 5 data points.
MIN_SERIES_LEN = 5

# Window for series-relative baseline (8-week rolling mean).
BASELINE_WINDOW = 8

# Deployment build-success fixed threshold (percentage).
_DEPLOYMENT_THRESHOLD = 90.0

# Severity ordering for ranking (lower value = higher priority).
_SEVERITY_RANK: dict[str, int] = {"critical": 0, "warning": 1, "info": 2}

# Metric direction table derived from TrendsRenderer._METRIC_CONFIGS.
# "down" — lower is better; "up" — higher is better.
# Metrics absent from this table (e.g. "risk": stable, "ai-usage": no data)
# are excluded from directional rules.
_METRIC_DIRECTION: dict[str, str] = {
    "security": "down",
    "security-infra": "down",
    "bugs": "down",
    "flow": "down",
    "deployment": "up",
    "collaboration": "down",
    "ownership": "down",
    "exploitable": "down",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _numeric_series(data: list[Any]) -> list[float] | None:
    """Return data as list[float] if all elements are numeric, else None."""
    if not data:
        return None
    try:
        return [float(v) for v in data]
    except (TypeError, ValueError):
        return None


def _rolling_mean(series: list[float], window: int) -> float:
    """Mean of the last ``window`` points (or all points if fewer available)."""
    tail = series[-window:] if len(series) >= window else series
    return statistics.mean(tail)


def _count_worsening_pairs(series: list[float], good_direction: str, n: int) -> int:
    """Count consecutive pairs among the last n+1 points that move in the bad direction."""
    tail = series[-(n + 1) :]
    count = 0
    for i in range(len(tail) - 1):
        delta = tail[i + 1] - tail[i]
        if good_direction == "down" and delta > 0:
            count += 1
        elif good_direction == "up" and delta < 0:
            count += 1
    return count


def _count_improving_pairs(series: list[float], good_direction: str, n: int) -> int:
    """Count consecutive pairs among the last n+1 points that move in the good direction."""
    tail = series[-(n + 1) :]
    count = 0
    for i in range(len(tail) - 1):
        delta = tail[i + 1] - tail[i]
        if good_direction == "down" and delta < 0:
            count += 1
        elif good_direction == "up" and delta > 0:
            count += 1
    return count


def _signal_id(metric_id: str, signal_type: str) -> str:
    return f"signal-{metric_id}-{signal_type.replace('_', '-')}"


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------


def _rule_threshold_breach(metric: dict[str, Any]) -> dict[str, Any] | None:
    """Threshold breach: deployment build success rate below 90.0%."""
    if metric.get("id") != "deployment":
        return None
    try:
        current = float(metric["current"])
    except (TypeError, ValueError, KeyError):
        return None
    if current >= _DEPLOYMENT_THRESHOLD:
        return None
    severity = "critical" if current < 80.0 else "warning"
    magnitude = _DEPLOYMENT_THRESHOLD - current
    return {
        "id": _signal_id("deployment", "threshold_breach"),
        "metric_id": "deployment",
        "type": "threshold_breach",
        "severity": severity,
        "direction": "down",
        "title": "Build success rate below baseline",
        "message": (f"Build success rate is {current:.1f}% — " f"below the {_DEPLOYMENT_THRESHOLD:.0f}% baseline."),
        "current_value": current,
        "baseline_value": _DEPLOYMENT_THRESHOLD,
        "window_weeks": 1,
        "_magnitude": magnitude,
    }


def _rule_sustained_deterioration(metric: dict[str, Any]) -> dict[str, Any] | None:
    """Sustained deterioration: worsening in >= 3 of the last 4 consecutive pairs."""
    metric_id = metric.get("id", "")
    good_direction = _METRIC_DIRECTION.get(metric_id)
    if not good_direction:
        return None

    series = _numeric_series(metric.get("data", []))
    if series is None or len(series) < MIN_SERIES_LEN:
        return None

    try:
        current = float(metric["current"])
    except (TypeError, ValueError, KeyError):
        return None

    worsening = _count_worsening_pairs(series, good_direction, 4)
    if worsening < 3:
        return None

    baseline = _rolling_mean(series, BASELINE_WINDOW)
    magnitude = abs(current - baseline)
    direction_label = "rising" if good_direction == "down" else "falling"
    title_str = metric.get("title") or metric_id
    return {
        "id": _signal_id(metric_id, "sustained_deterioration"),
        "metric_id": metric_id,
        "type": "sustained_deterioration",
        "severity": "warning",
        "direction": "down",
        "title": f"{title_str} — sustained {direction_label}",
        "message": (
            f"{title_str} has worsened in {worsening} of the last 4 weeks "
            f"(current: {current}, 8-week mean: {baseline:.1f})."
        ),
        "current_value": current,
        "baseline_value": round(baseline, 2),
        "window_weeks": 4,
        "_magnitude": magnitude,
    }


def _rule_recovery_trend(metric: dict[str, Any]) -> dict[str, Any] | None:
    """Recovery trend: improving in >= 3 of the last 4 consecutive pairs."""
    metric_id = metric.get("id", "")
    good_direction = _METRIC_DIRECTION.get(metric_id)
    if not good_direction:
        return None

    series = _numeric_series(metric.get("data", []))
    if series is None or len(series) < MIN_SERIES_LEN:
        return None

    try:
        current = float(metric["current"])
    except (TypeError, ValueError, KeyError):
        return None

    improving = _count_improving_pairs(series, good_direction, 4)
    if improving < 3:
        return None

    baseline = _rolling_mean(series, BASELINE_WINDOW)
    magnitude = abs(current - baseline)
    title_str = metric.get("title") or metric_id
    return {
        "id": _signal_id(metric_id, "recovery_trend"),
        "metric_id": metric_id,
        "type": "recovery_trend",
        "severity": "info",
        "direction": "up",
        "title": f"{title_str} — recovery trend",
        "message": (
            f"{title_str} has improved in {improving} of the last 4 weeks "
            f"(current: {current}, 8-week mean: {baseline:.1f})."
        ),
        "current_value": current,
        "baseline_value": round(baseline, 2),
        "window_weeks": 4,
        "_magnitude": magnitude,
    }


_RULES = [_rule_threshold_breach, _rule_sustained_deterioration, _rule_recovery_trend]


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def _rank_key(signal: dict[str, Any]) -> tuple[int, float, str]:
    """Deterministic sort key: severity asc, magnitude desc, metric_id asc."""
    severity = _SEVERITY_RANK.get(signal["severity"], 99)
    magnitude = -signal.get("_magnitude", 0.0)  # negate: larger ranks higher
    return (severity, magnitude, signal["metric_id"])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_signals_response(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Run all signal rules over a metrics list and return the top-N response dict.

    Args:
        metrics: The ``metrics`` list from build_trends_context() output.

    Returns:
        Dict with ``generated_at``, ``signal_count``, and ``signals``.
        Returns an empty-state payload rather than raising.
    """
    candidates: list[dict[str, Any]] = []
    for metric in metrics:
        for rule in _RULES:
            try:
                result = rule(metric)
            except Exception:  # noqa: BLE001 — per-rule errors must not crash the response
                continue
            if result is not None:
                candidates.append(result)

    candidates.sort(key=_rank_key)
    top = candidates[:MAX_SIGNALS]

    # Strip internal _magnitude field before serialisation.
    signals = [{k: v for k, v in s.items() if k != "_magnitude"} for s in top]

    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "signal_count": len(signals),
        "signals": signals,
    }
