"""
Health Score v1 — Provisional portfolio health score over Executive Trends metrics.

PROVISIONAL: This module produces a convenience score derived from the
``ragColor`` classifications already computed by TrendsRenderer. It is NOT a
domain model and does NOT represent a formally agreed health definition.  It
is intended as a directional indicator only — "fair" or "at risk" should
prompt further inspection of individual metrics, not be acted on in isolation.

Score model
-----------
Input : the ``metrics`` list returned by build_trends_context()
        (rendered dashboard cards, each with ``id``, ``current``,
        ``data``, and ``ragColor``).

Each metric card whose ``ragColor`` is one of the three known RAG values
contributes a component score:

    Green  (#10b981) → 100 points
    Amber  (#f59e0b) →  50 points
    Red    (#ef4444) →   0 points

Portfolio score = round(mean(component_scores)), clamped to [0, 100].
Metrics with an unknown or absent ``ragColor`` are skipped and do NOT
contribute — they reduce ``contributing_metrics`` but do NOT penalise the
score.

Excluded metrics (never scored):
    "ai-usage"  — no ragColor (static launcher card)
    "target"    — measures progress toward a goal, not operational health

Weighting
---------
ALL contributing metrics have EQUAL WEIGHT in v1.

Security-adjacent metrics ("security", "security-infra", "exploitable")
are currently three separate entries in the metrics list.  If all three
are present and scoreable, the security domain contributes approximately
3/N of the total score where N is the number of contributing metrics.
This is a known artefact of equal weighting; it is intentional for v1
and documented here so future weighting changes are deliberate.

ragColor dependency
-------------------
This module treats ``ragColor`` as a stable-enough signal to base v1 on.
It is NOT a formal API contract — it is an internal renderer field.

If TrendsRenderer changes the colour constants, metrics will shift to
"skipped" (not penalised) and ``contributing_metrics`` will drop, which
surfaces the drift to the caller.  Tests in test_health_score.py explicitly
document the three expected colour values so any change is immediately visible.

Label thresholds
----------------
    >= 80  →  "healthy"
    >= 60  →  "fair"
    <  60  →  "at risk"

Public entry point: build_health_score_response(metrics) -> dict
"""

from __future__ import annotations

import statistics
from datetime import UTC, datetime
from typing import Any

# Known RAG colour values from TrendsRenderer / TrendsCalculator.
# If these constants change, affected metrics will be skipped (score coverage
# drops) rather than silently misclassified.
_RAG_GREEN = "#10b981"
_RAG_AMBER = "#f59e0b"
_RAG_RED = "#ef4444"

_RAG_POINTS: dict[str, int] = {
    _RAG_GREEN: 100,
    _RAG_AMBER: 50,
    _RAG_RED: 0,
}

# Metrics excluded from scoring (see module docstring).
_EXCLUDED_METRIC_IDS: frozenset[str] = frozenset({"ai-usage", "target"})

# Label thresholds.
_LABEL_HEALTHY = "healthy"
_LABEL_FAIR = "fair"
_LABEL_AT_RISK = "at risk"


def _label_for_score(score: int) -> str:
    if score >= 80:
        return _LABEL_HEALTHY
    if score >= 60:
        return _LABEL_FAIR
    return _LABEL_AT_RISK


def build_health_score_response(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute a provisional portfolio health score from rendered metric cards.

    Args:
        metrics: The ``metrics`` list from build_trends_context() output.
                 Each entry must contain at minimum ``id`` and ``ragColor``.

    Returns:
        Dict with ``generated_at``, ``score``, ``label``,
        ``contributing_metrics``, and ``total_metrics``.
        Always returns a valid payload — never raises.
    """
    component_scores: list[int] = []
    total = 0

    for metric in metrics:
        metric_id = metric.get("id", "")
        if metric_id in _EXCLUDED_METRIC_IDS:
            continue

        total += 1
        rag = metric.get("ragColor", "")
        points = _RAG_POINTS.get(rag)
        if points is not None:
            component_scores.append(points)

    if component_scores:
        raw = statistics.mean(component_scores)
        score = max(0, min(100, round(raw)))
    else:
        score = 0

    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "score": score,
        "label": _label_for_score(score),
        "contributing_metrics": len(component_scores),
        "total_metrics": total,
    }
