"""
Tests for execution/intelligence/health_classifier.py

Single responsibility: verify that health classification produces valid,
correctly typed results with labels in the allowed set.

All fixtures use synthetic data only — no real project names, no real ADO data.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from execution.domain.intelligence import HealthClassification
from execution.intelligence.health_classifier import (
    _MODEL_VERSION,
    _VALID_HEALTH_LABELS,
    _build_training_dataframe,
    _derive_health_label,
    classify_project_health,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_health_df(n_rows: int = 8, metric: str = "quality") -> pd.DataFrame:
    """
    Synthetic feature DataFrame for health classifier tests.

    Mirrors the structure produced by feature_engineering.extract_features().
    """
    from datetime import timedelta

    rng = np.random.default_rng(42)
    base = datetime(2025, 10, 6)
    dates = [base + timedelta(weeks=i) for i in range(n_rows)]
    projects = [f"Product_{chr(65 + i)}" for i in range(n_rows)]

    if metric == "quality":
        return pd.DataFrame(
            {
                "week_date": dates,
                "project": projects,
                "open_bugs": rng.integers(10, 400, n_rows).tolist(),
                "closed_bugs": rng.integers(5, 100, n_rows).tolist(),
            }
        )
    if metric == "security":
        return pd.DataFrame(
            {
                "week_date": dates,
                "project": projects,
                "total_vulnerabilities": rng.integers(0, 600, n_rows).tolist(),
                "critical": rng.integers(0, 50, n_rows).tolist(),
            }
        )
    if metric == "flow":
        return pd.DataFrame(
            {
                "week_date": dates,
                "project": projects,
                "lead_time_p85": rng.normal(30, 15, n_rows).tolist(),
                "wip": rng.integers(10, 300, n_rows).tolist(),
            }
        )
    if metric == "deployment":
        return pd.DataFrame(
            {
                "week_date": dates,
                "project": projects,
                "deploy_frequency": rng.normal(3, 1, n_rows).tolist(),
                "build_success_rate": rng.uniform(60, 99, n_rows).tolist(),
            }
        )
    if metric == "risk":
        return pd.DataFrame(
            {
                "week_date": dates,
                "project": projects,
                "risk_score": rng.uniform(0, 100, n_rows).tolist(),
            }
        )
    return pd.DataFrame({"week_date": dates, "project": projects})


def _multi_metric_side_effect(metric: str, **kwargs: object) -> pd.DataFrame:
    """Returns the appropriate synthetic DataFrame for each metric."""
    return _make_health_df(n_rows=8, metric=metric)


# ---------------------------------------------------------------------------
# Tests: _derive_health_label
# ---------------------------------------------------------------------------


def test_derive_health_label_green_from_low_risk() -> None:
    """Risk score <= 30 should produce 'Green' label."""
    row = pd.Series({"risk_score": 20.0})
    assert _derive_health_label(row) == "Green"


def test_derive_health_label_amber_from_medium_risk() -> None:
    """Risk score 31–60 should produce 'Amber' label."""
    row = pd.Series({"risk_score": 45.0})
    assert _derive_health_label(row) == "Amber"


def test_derive_health_label_red_from_high_risk() -> None:
    """Risk score > 60 should produce 'Red' label."""
    row = pd.Series({"risk_score": 80.0})
    assert _derive_health_label(row) == "Red"


def test_derive_health_label_fallback_amber_with_no_data() -> None:
    """No data at all (no risk_score, no bugs, no vulns) → 'Amber'."""
    row = pd.Series({})
    assert _derive_health_label(row) == "Amber"


def test_derive_health_label_fallback_uses_bugs_and_vulns() -> None:
    """Without risk_score, composite from open_bugs + total_vulnerabilities is used."""
    # Low bugs + low vulns → should be Green or Amber
    row_low = pd.Series({"open_bugs": 5.0, "total_vulnerabilities": 10.0})
    result_low = _derive_health_label(row_low)
    assert result_low in _VALID_HEALTH_LABELS

    # Very high bugs + high vulns → should trend Red or Amber
    row_high = pd.Series({"open_bugs": 500.0, "total_vulnerabilities": 500.0})
    result_high = _derive_health_label(row_high)
    assert result_high in _VALID_HEALTH_LABELS


def test_derive_health_label_boundary_green_max() -> None:
    """risk_score == 30 is the boundary for Green (inclusive)."""
    row = pd.Series({"risk_score": 30.0})
    assert _derive_health_label(row) == "Green"


def test_derive_health_label_boundary_amber_max() -> None:
    """risk_score == 60 is the boundary for Amber (inclusive)."""
    row = pd.Series({"risk_score": 60.0})
    assert _derive_health_label(row) == "Amber"


def test_derive_health_label_boundary_just_over_amber() -> None:
    """risk_score == 60.1 crosses into Red."""
    row = pd.Series({"risk_score": 60.1})
    assert _derive_health_label(row) == "Red"


# ---------------------------------------------------------------------------
# Tests: classify_project_health — return type
# ---------------------------------------------------------------------------


def test_classify_project_health_returns_list() -> None:
    """classify_project_health() should return a list."""
    with patch(
        "execution.intelligence.health_classifier.load_features",
        side_effect=_multi_metric_side_effect,
    ):
        results = classify_project_health()

    assert isinstance(results, list)


def test_classify_project_health_returns_health_classification_objects() -> None:
    """Every item in the result must be a HealthClassification instance."""
    with patch(
        "execution.intelligence.health_classifier.load_features",
        side_effect=_multi_metric_side_effect,
    ):
        results = classify_project_health()

    for r in results:
        assert isinstance(r, HealthClassification)


# ---------------------------------------------------------------------------
# Tests: label validation
# ---------------------------------------------------------------------------


def test_all_labels_in_valid_set() -> None:
    """All HealthClassification labels must be Green, Amber, or Red."""
    with patch(
        "execution.intelligence.health_classifier.load_features",
        side_effect=_multi_metric_side_effect,
    ):
        results = classify_project_health()

    for r in results:
        assert r.label in _VALID_HEALTH_LABELS, f"Unexpected label: {r.label!r}"


def test_labels_are_strings() -> None:
    """All labels must be Python str."""
    with patch(
        "execution.intelligence.health_classifier.load_features",
        side_effect=_multi_metric_side_effect,
    ):
        results = classify_project_health()

    for r in results:
        assert isinstance(r.label, str)


# ---------------------------------------------------------------------------
# Tests: confidence scores
# ---------------------------------------------------------------------------


def test_confidence_is_float_between_0_and_1() -> None:
    """Confidence scores must be Python float in [0.0, 1.0]."""
    with patch(
        "execution.intelligence.health_classifier.load_features",
        side_effect=_multi_metric_side_effect,
    ):
        results = classify_project_health()

    for r in results:
        assert isinstance(r.confidence, float), f"confidence must be float, got {type(r.confidence)}"
        assert 0.0 <= r.confidence <= 1.0, f"confidence {r.confidence} out of [0, 1]"


def test_confidence_has_at_most_4_decimal_places() -> None:
    """Confidence is rounded to 4 decimal places."""
    with patch(
        "execution.intelligence.health_classifier.load_features",
        side_effect=_multi_metric_side_effect,
    ):
        results = classify_project_health()

    for r in results:
        # Check that rounding to 4dp produces the same value
        assert round(r.confidence, 4) == r.confidence


# ---------------------------------------------------------------------------
# Tests: insufficient data
# ---------------------------------------------------------------------------


def test_insufficient_data_returns_empty() -> None:
    """With fewer than _MIN_SAMPLES projects, should return empty list."""

    def _tiny_side_effect(metric: str, **kwargs: object) -> pd.DataFrame:
        return _make_health_df(n_rows=1, metric=metric)

    with patch(
        "execution.intelligence.health_classifier.load_features",
        side_effect=_tiny_side_effect,
    ):
        results = classify_project_health()

    assert results == []


def test_no_features_returns_empty() -> None:
    """When all load_features calls raise ValueError, should return empty list."""
    with patch(
        "execution.intelligence.health_classifier.load_features",
        side_effect=ValueError("no parquet found"),
    ):
        results = classify_project_health()

    assert results == []


# ---------------------------------------------------------------------------
# Tests: HealthClassification domain model
# ---------------------------------------------------------------------------


def test_health_classification_inherits_metric_snapshot() -> None:
    """HealthClassification should have timestamp and project attributes."""
    hc = HealthClassification(
        timestamp=datetime(2025, 10, 6),
        label="Green",
        project="Product_A",
    )
    assert hc.status == "Good"
    assert hc.status_class == "status-good"
    assert hc.project == "Product_A"
    assert hc.timestamp == datetime(2025, 10, 6)


def test_health_classification_amber_status() -> None:
    """Amber label maps to 'Caution' status and 'status-caution' class."""
    hc = HealthClassification(
        timestamp=datetime(2025, 10, 6),
        label="Amber",
        project="Product_B",
    )
    assert hc.status == "Caution"
    assert hc.status_class == "status-caution"


def test_health_classification_red_status() -> None:
    """Red label maps to 'Action Needed' status and 'status-action' class."""
    hc = HealthClassification(
        timestamp=datetime(2025, 10, 6),
        label="Red",
        project="Product_C",
    )
    assert hc.status == "Action Needed"
    assert hc.status_class == "status-action"


def test_health_classification_model_version_set() -> None:
    """Each result must include the model_version string."""
    with patch(
        "execution.intelligence.health_classifier.load_features",
        side_effect=_multi_metric_side_effect,
    ):
        results = classify_project_health()

    for r in results:
        assert r.model_version == _MODEL_VERSION


def test_health_classification_feature_importances_are_floats() -> None:
    """feature_importances dict values must all be Python float."""
    with patch(
        "execution.intelligence.health_classifier.load_features",
        side_effect=_multi_metric_side_effect,
    ):
        results = classify_project_health()

    for r in results:
        for feat, imp in r.feature_importances.items():
            assert isinstance(imp, float), f"feature_importances[{feat}] must be float, got {type(imp)}"


def test_health_classification_from_json_roundtrip() -> None:
    """HealthClassification.from_json should deserialise correctly."""
    data = {
        "timestamp": "2025-10-06T00:00:00",
        "project": "Product_A",
        "label": "Green",
        "confidence": 0.92,
        "feature_importances": {"open_bugs": 0.35, "risk_score": 0.55},
        "model_version": "v1.0.0",
    }
    hc = HealthClassification.from_json(data)
    assert hc.label == "Green"
    assert hc.confidence == 0.92
    assert hc.feature_importances["risk_score"] == 0.55
    assert hc.model_version == "v1.0.0"
    assert hc.project == "Product_A"


def test_health_classification_project_is_string() -> None:
    """project field must be Python str on every result."""
    with patch(
        "execution.intelligence.health_classifier.load_features",
        side_effect=_multi_metric_side_effect,
    ):
        results = classify_project_health()

    for r in results:
        assert isinstance(r.project, str)
