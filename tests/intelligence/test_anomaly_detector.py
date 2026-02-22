"""
Tests for execution/intelligence/anomaly_detector.py

Covers:
- detect_anomalies_zscore() on sample_anomaly_series — detects the spike at index 14
- detect_anomalies_zscore() on sample_clean_series — returns empty list
- detect_anomalies_isolation_forest() on anomaly series — detects the spike
- detect_anomalies() primary entry point — correct structure of AnomalyResult dicts
- Model is NOT serialized (no pickle import in the module)
- contamination parameter clamped to valid range
- Invalid method raises ValueError
- Empty DataFrame / missing column handled gracefully
- ALLOWED_ROOT_CAUSE_DIMENSIONS whitelist is a frozenset
"""

from __future__ import annotations

import importlib.util
import inspect

import numpy as np
import pandas as pd
import pytest

from execution.intelligence.anomaly_detector import (
    ALLOWED_ROOT_CAUSE_DIMENSIONS,
    AnomalyResult,
    detect_anomalies,
    detect_anomalies_isolation_forest,
    detect_anomalies_zscore,
)

# ---------------------------------------------------------------------------
# TestNoPickleSerialization
# ---------------------------------------------------------------------------


class TestNoPickleSerialization:
    def test_pickle_not_imported_in_module(self) -> None:
        """The anomaly_detector module must NOT have 'import pickle' (security requirement).

        Note: The module may mention 'pickle' in docstrings/comments as a prohibition.
        We check for the actual import statement, not the word 'pickle' itself.
        """
        import execution.intelligence.anomaly_detector as mod

        source = inspect.getsource(mod)
        # Check line by line for actual import statements (not comments or docstrings)
        import_lines = [
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith("import pickle") or line.strip().startswith("from pickle")
        ]
        assert len(import_lines) == 0, f"'import pickle' must NOT appear as an import statement. Found: {import_lines}"

    def test_joblib_not_imported_in_module(self) -> None:
        """joblib must not be imported (would enable model serialization to disk)."""
        import execution.intelligence.anomaly_detector as mod

        source = inspect.getsource(mod)
        import_lines = [
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith("import joblib") or line.strip().startswith("from joblib")
        ]
        assert len(import_lines) == 0, f"'import joblib' must NOT appear as an import statement. Found: {import_lines}"


# ---------------------------------------------------------------------------
# TestAllowedRootCauseDimensions
# ---------------------------------------------------------------------------


class TestAllowedRootCauseDimensions:
    def test_is_frozenset(self) -> None:
        assert isinstance(ALLOWED_ROOT_CAUSE_DIMENSIONS, frozenset)

    def test_contains_security(self) -> None:
        assert "security" in ALLOWED_ROOT_CAUSE_DIMENSIONS

    def test_contains_quality(self) -> None:
        assert "quality" in ALLOWED_ROOT_CAUSE_DIMENSIONS

    def test_contains_deployment(self) -> None:
        assert "deployment" in ALLOWED_ROOT_CAUSE_DIMENSIONS

    def test_arbitrary_string_not_in_whitelist(self) -> None:
        assert "attacker_controlled_string" not in ALLOWED_ROOT_CAUSE_DIMENSIONS


# ---------------------------------------------------------------------------
# TestDetectAnomaliesZscore
# ---------------------------------------------------------------------------


class TestDetectAnomaliesZscore:
    def test_detects_spike_in_anomaly_series(self, sample_anomaly_series: pd.DataFrame) -> None:
        """3-sigma spike at index 14 should be detected."""
        values = sample_anomaly_series["value"].tolist()
        indices = detect_anomalies_zscore(values, threshold=3.0)
        assert 14 in indices, f"Expected index 14 (spike at 350.0) in detected indices, got {indices}"

    def test_clean_series_returns_empty(self, sample_clean_series: pd.DataFrame) -> None:
        """Stable series (all 100.0) should produce zero anomalies."""
        values = sample_clean_series["value"].tolist()
        indices = detect_anomalies_zscore(values, threshold=3.0)
        assert len(indices) == 0, f"Expected no anomalies for stable series, got {indices}"

    def test_returns_list_of_ints(self, sample_anomaly_series: pd.DataFrame) -> None:
        values = sample_anomaly_series["value"].tolist()
        indices = detect_anomalies_zscore(values)
        assert isinstance(indices, list)
        assert all(isinstance(i, int) for i in indices)

    def test_empty_input_returns_empty(self) -> None:
        assert detect_anomalies_zscore([]) == []

    def test_constant_series_returns_empty(self) -> None:
        """Zero std deviation → no anomalies."""
        constant = [100.0] * 20
        assert detect_anomalies_zscore(constant) == []

    def test_single_element_returns_empty(self) -> None:
        assert detect_anomalies_zscore([42.0]) == []

    def test_higher_threshold_fewer_detections(self, sample_anomaly_series: pd.DataFrame) -> None:
        values = sample_anomaly_series["value"].tolist()
        low_threshold = detect_anomalies_zscore(values, threshold=1.5)
        high_threshold = detect_anomalies_zscore(values, threshold=5.0)
        assert len(high_threshold) <= len(low_threshold)

    def test_numpy_array_input_accepted(self, sample_anomaly_series: pd.DataFrame) -> None:
        arr = sample_anomaly_series["value"].to_numpy()
        indices = detect_anomalies_zscore(arr)
        assert isinstance(indices, list)


# ---------------------------------------------------------------------------
# TestDetectAnomaliesIsolationForest
# ---------------------------------------------------------------------------


class TestDetectAnomaliesIsolationForest:
    def test_detects_spike_in_anomaly_series(self, sample_anomaly_series: pd.DataFrame) -> None:
        """Isolation Forest should flag the obvious 350.0 spike at index 14."""
        indices = detect_anomalies_isolation_forest(sample_anomaly_series, "value", contamination=0.1)
        assert 14 in indices, f"Expected index 14 (spike=350.0) to be detected by Isolation Forest, got {indices}"

    def test_returns_list_of_ints(self, sample_anomaly_series: pd.DataFrame) -> None:
        indices = detect_anomalies_isolation_forest(sample_anomaly_series, "value")
        assert isinstance(indices, list)
        assert all(isinstance(i, int) for i in indices)

    def test_missing_value_col_returns_empty(self, sample_anomaly_series: pd.DataFrame) -> None:
        indices = detect_anomalies_isolation_forest(sample_anomaly_series, "nonexistent_col")
        assert indices == []

    def test_contamination_clamped_low(self, sample_anomaly_series: pd.DataFrame) -> None:
        """contamination=0.0 should be clamped to 0.01 (not raise ValueError)."""
        # Should not raise
        indices = detect_anomalies_isolation_forest(sample_anomaly_series, "value", contamination=0.0)
        assert isinstance(indices, list)

    def test_contamination_clamped_high(self, sample_anomaly_series: pd.DataFrame) -> None:
        """contamination=0.9 should be clamped to 0.499 (not raise ValueError)."""
        indices = detect_anomalies_isolation_forest(sample_anomaly_series, "value", contamination=0.9)
        assert isinstance(indices, list)

    def test_too_few_rows_returns_empty(self) -> None:
        """DataFrame with only 1 non-null row should return empty."""
        df = pd.DataFrame({"value": [100.0]})
        result = detect_anomalies_isolation_forest(df, "value")
        assert result == []

    def test_deterministic_with_random_state(self, sample_anomaly_series: pd.DataFrame) -> None:
        """Same input should produce same output (random_state=42)."""
        r1 = detect_anomalies_isolation_forest(sample_anomaly_series, "value")
        r2 = detect_anomalies_isolation_forest(sample_anomaly_series, "value")
        assert r1 == r2


# ---------------------------------------------------------------------------
# TestDetectAnomalies (primary entry point)
# ---------------------------------------------------------------------------


class TestDetectAnomalies:
    def test_invalid_method_raises_value_error(self, sample_anomaly_series: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="Unknown method"):
            detect_anomalies(sample_anomaly_series, "value", method="invalid_method")

    def test_missing_value_col_returns_empty(self, sample_anomaly_series: pd.DataFrame) -> None:
        results = detect_anomalies(sample_anomaly_series, "no_such_col")
        assert results == []

    def test_returns_list_of_anomaly_result_dicts(self, sample_anomaly_series: pd.DataFrame) -> None:
        results = detect_anomalies(sample_anomaly_series, "value", method="zscore", threshold=3.0)
        assert isinstance(results, list)
        for r in results:
            assert "week_date" in r
            assert "value" in r
            assert "z_score" in r
            assert "is_anomaly" in r
            assert "method" in r
            assert "root_cause_hint" in r

    def test_all_results_have_is_anomaly_true(self, sample_anomaly_series: pd.DataFrame) -> None:
        results = detect_anomalies(sample_anomaly_series, "value", method="zscore", threshold=3.0)
        assert all(r["is_anomaly"] is True for r in results)

    def test_zscore_method_detects_spike(self, sample_anomaly_series: pd.DataFrame) -> None:
        results = detect_anomalies(sample_anomaly_series, "value", method="zscore", threshold=3.0)
        detected_values = [r["value"] for r in results]
        assert 350.0 in detected_values, "Spike at 350.0 should be detected by zscore"

    def test_isolation_forest_method_detects_spike(self, sample_anomaly_series: pd.DataFrame) -> None:
        results = detect_anomalies(
            sample_anomaly_series,
            "value",
            method="isolation_forest",
            contamination=0.1,
        )
        detected_values = [r["value"] for r in results]
        assert 350.0 in detected_values, "Spike at 350.0 should be detected by isolation_forest"

    def test_results_sorted_by_week_date(self, sample_anomaly_series: pd.DataFrame) -> None:
        results = detect_anomalies(sample_anomaly_series, "value", method="zscore", threshold=3.0)
        dates = [r["week_date"] for r in results]
        assert dates == sorted(dates)

    def test_method_field_matches_requested_method_zscore(self, sample_anomaly_series: pd.DataFrame) -> None:
        results = detect_anomalies(sample_anomaly_series, "value", method="zscore", threshold=3.0)
        for r in results:
            assert r["method"] == "zscore"

    def test_method_field_matches_requested_method_isolation_forest(self, sample_anomaly_series: pd.DataFrame) -> None:
        results = detect_anomalies(sample_anomaly_series, "value", method="isolation_forest", contamination=0.1)
        for r in results:
            assert r["method"] == "isolation_forest"

    def test_clean_series_no_anomalies_zscore(self, sample_clean_series: pd.DataFrame) -> None:
        results = detect_anomalies(sample_clean_series, "value", method="zscore", threshold=3.0)
        assert results == []

    def test_z_score_sign_matches_value_direction(self, sample_anomaly_series: pd.DataFrame) -> None:
        """350.0 is above mean so z_score should be positive."""
        results = detect_anomalies(sample_anomaly_series, "value", method="zscore", threshold=3.0)
        spike_results = [r for r in results if r["value"] == 350.0]
        assert len(spike_results) > 0
        assert spike_results[0]["z_score"] > 0

    def test_week_date_is_string(self, sample_anomaly_series: pd.DataFrame) -> None:
        results = detect_anomalies(sample_anomaly_series, "value", method="zscore", threshold=3.0)
        for r in results:
            assert isinstance(r["week_date"], str)

    def test_root_cause_hint_is_string(self, sample_anomaly_series: pd.DataFrame) -> None:
        results = detect_anomalies(sample_anomaly_series, "value", method="zscore", threshold=3.0)
        for r in results:
            assert isinstance(r["root_cause_hint"], str)

    def test_root_cause_hint_within_whitelist_or_empty(self, sample_anomaly_series: pd.DataFrame) -> None:
        """root_cause_hint must either be empty or be in ALLOWED_ROOT_CAUSE_DIMENSIONS."""
        results = detect_anomalies(sample_anomaly_series, "value", method="zscore", threshold=3.0)
        for r in results:
            hint = r["root_cause_hint"]
            assert hint == "" or hint in ALLOWED_ROOT_CAUSE_DIMENSIONS, f"root_cause_hint '{hint}' not in whitelist"

    def test_multicolumn_dataframe_with_dimension(self, sample_anomaly_series: pd.DataFrame) -> None:
        """DataFrame with an extra dimension column — should not raise."""
        df = sample_anomaly_series.copy()
        df["quality"] = [10.0] * 14 + [50.0] + [10.0] * 5  # spike aligns with value spike
        results = detect_anomalies(df, "value", method="zscore", threshold=3.0)
        assert isinstance(results, list)
