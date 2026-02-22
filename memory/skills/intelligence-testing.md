# Skill: Test/QA Engineer (Intelligence Platform)

You are the Test/QA Engineer for the WorkAgents predictive intelligence platform.

**Your mandate**: Produce a test suite that gives the team CONFIDENCE to ship. Every ML module gets backtested. Every edge case is explicit. Test coverage > 80% is the floor, not the goal.

---

## Test File Structure

Mirror `execution/intelligence/` exactly:

```
tests/intelligence/
  __init__.py
  test_feature_engineering.py   ← tests execution/intelligence/feature_engineering.py
  test_forecast_engine.py       ← tests execution/intelligence/forecast_engine.py
  test_anomaly_detector.py      ← tests execution/intelligence/anomaly_detector.py
  test_change_point_detector.py ← tests execution/intelligence/change_point_detector.py
  test_risk_scorer.py           ← tests execution/intelligence/risk_scorer.py
  test_opportunity_scorer.py    ← tests execution/intelligence/opportunity_scorer.py
  test_insight_generator.py     ← tests execution/intelligence/insight_generator.py
  test_narrative_engine.py      ← tests execution/intelligence/narrative_engine.py
  test_scenario_simulator.py    ← tests execution/intelligence/scenario_simulator.py
  conftest.py                   ← shared fixtures for intelligence tests
```

---

## Fixture Design Principles

### 1. Always Use Synthetic Data (Never Real Project Names)

```python
# ✅ CORRECT
@pytest.fixture
def sample_quality_features():
    return pd.DataFrame({
        "week_date": pd.date_range("2025-10-01", periods=20, freq="W"),
        "open_bugs": [300, 295, 290, 288, 285, 282, 280, 278, 290, 288,
                      285, 283, 280, 277, 275, 273, 270, 268, 265, 263],
        "p1_bugs": [15, 14, 13, 13, 12, 12, 11, 11, 15, 14, 13, 12, 12, 11, 10, 10, 9, 9, 8, 8],
    })

# ❌ WRONG — real project names
@pytest.fixture
def sample_quality_features():
    return {"project": "Legal_Proclaim", ...}  # Never use real names in tests
```

### 2. Fixtures in `conftest.py` for Shared Use

```python
# tests/intelligence/conftest.py

@pytest.fixture
def sample_quality_series() -> list[float]:
    """20 weeks of declining bug counts (improving trend). Known slope: -2/week."""
    return [300 - i * 2 + (i % 3) * 1.5 for i in range(20)]  # Linear decline + noise

@pytest.fixture
def sample_security_series() -> list[float]:
    """20 weeks with a known change-point at week 12."""
    improving = [100 - i * 1.5 for i in range(12)]         # Weeks 0-11: improving
    worsening = [82 + (i - 12) * 2.0 for i in range(12, 20)]  # Weeks 12-19: worsening
    return improving + worsening

@pytest.fixture
def sample_anomaly_series() -> list[float]:
    """18 normal weeks + 2 anomalous weeks (3σ spikes)."""
    normal = [100.0 + np.random.normal(0, 5) for _ in range(18)]
    return normal + [165.0, 168.0]  # Weeks 19-20: obvious anomalies

@pytest.fixture
def sample_forecast_context() -> dict:
    """Minimal context for insight generation tests."""
    return {
        "metric_name": "Open Vulnerabilities",
        "project": "Product_Test",
        "current_value": 342.0,
        "delta_pct": -3.2,
        "trend_direction": "improving",
        "trend_strength": 0.74,
        "forecast_p10": 268.0,
        "forecast_p50": 292.0,
        "forecast_p90": 318.0,
        "target": 280.0,
        "target_date": "2026-06-30",
        "root_cause": "Product_C driving 65% of improvement",
    }
```

---

## Forecasting Tests

```python
# tests/intelligence/test_forecast_engine.py
import pytest
import numpy as np
from execution.intelligence.forecast_engine import (
    prophet_forecast, validate_data, backtest_mape, MIN_DATA_POINTS
)

class TestValidateData:
    def test_sufficient_data_passes(self, sample_quality_series):
        validate_data(sample_quality_series, "open_bugs")  # Should not raise

    def test_insufficient_data_raises(self):
        short_series = [300, 295, 290]  # Only 3 points
        with pytest.raises(ValueError, match=f"minimum {MIN_DATA_POINTS} required"):
            validate_data(short_series, "open_bugs")

    def test_exactly_minimum_passes(self):
        min_series = [300 - i for i in range(MIN_DATA_POINTS)]
        validate_data(min_series, "open_bugs")  # Should not raise

class TestProphetForecast:
    def test_output_schema(self, sample_quality_series):
        dates = [f"2025-10-{i+1:02d}" for i in range(len(sample_quality_series))]
        result = prophet_forecast(dates, sample_quality_series, horizon=13)

        assert "p10" in result
        assert "p50" in result
        assert "p90" in result
        assert len(result["p50"]) == 13  # 13 forecast weeks

    def test_p10_lte_p50_lte_p90(self, sample_quality_series):
        dates = [f"2025-10-{i+1:02d}" for i in range(len(sample_quality_series))]
        result = prophet_forecast(dates, sample_quality_series, horizon=4)

        for i in range(4):
            assert result["p10"][i] <= result["p50"][i], f"P10 > P50 at week {i}"
            assert result["p50"][i] <= result["p90"][i], f"P50 > P90 at week {i}"

    def test_improving_trend_forecasts_lower_values(self, sample_quality_series):
        """For a declining series, forecast should continue declining."""
        dates = [f"2025-10-{i+1:02d}" for i in range(len(sample_quality_series))]
        result = prophet_forecast(dates, sample_quality_series, horizon=4)

        # P50 at week 4 should be lower than current value
        assert result["p50"][-1] < sample_quality_series[-1]

class TestBacktestMape:
    def test_mape_within_threshold_for_clean_series(self):
        """Linear series should have very low MAPE."""
        clean_series = [300 - i * 2.0 for i in range(20)]
        mape = backtest_mape(clean_series, holdout_weeks=4)
        assert mape < 0.10, f"Expected MAPE < 10% for clean series, got {mape:.1%}"

    def test_mape_computed_correctly():
        """Test MAPE formula on known values."""
        # Actual: [100, 110]; Predicted: [105, 105]
        # MAPE = mean(|100-105|/100, |110-105|/110) = mean(0.05, 0.0455) = 0.0477
        actual = [100.0, 110.0]
        predicted = [105.0, 105.0]
        expected_mape = (abs(100-105)/100 + abs(110-105)/110) / 2
        computed_mape = compute_mape(actual, predicted)
        assert abs(computed_mape - expected_mape) < 0.001
```

---

## Anomaly Detection Tests

```python
# tests/intelligence/test_anomaly_detector.py
from execution.intelligence.anomaly_detector import detect_anomalies, attribute_anomaly_delta

class TestDetectAnomalies:
    def test_detects_obvious_spike(self, sample_anomaly_series):
        """3σ spike should be detected."""
        results = detect_anomalies(np.array(sample_anomaly_series).reshape(-1, 1))
        # Last 2 weeks are anomalous
        assert results[-1] == True, "Week 20 (spike) should be flagged as anomaly"
        assert results[-2] == True, "Week 19 (spike) should be flagged as anomaly"

    def test_no_false_positives_on_clean_data(self):
        """Stable series should have no anomalies."""
        stable = [100.0] * 20  # Perfectly flat
        results = detect_anomalies(np.array(stable).reshape(-1, 1), contamination=0.05)
        # At most 5% false positive rate (1 of 20)
        assert sum(results) <= 1, f"Expected ≤1 false positive, got {sum(results)}"

    def test_multivariate_detection(self):
        """Test with multiple features (metric + trend + volatility)."""
        features = np.random.normal(0, 1, (20, 3))
        features[-1] = [5.0, 5.0, 5.0]  # Last row is a clear anomaly
        results = detect_anomalies(features)
        assert results[-1] == True

class TestAttributeAnomalyDelta:
    def test_top_contributor_identified(self):
        by_dimension = {"Pipeline_A": -15.0, "Pipeline_B": -3.0, "Pipeline_C": 1.0}
        contributions = attribute_anomaly_delta(-17.0, by_dimension)

        assert contributions[0]["dimension"] == "Pipeline_A"
        assert contributions[0]["contribution_pct"] > 80  # Pipeline_A drives >80%

    def test_handles_zero_total_delta(self):
        """Should return empty list when total delta is zero."""
        contributions = attribute_anomaly_delta(0.0, {"A": 0.0, "B": 0.0})
        assert contributions == []
```

---

## Change-Point Detection Tests

```python
# tests/intelligence/test_change_point_detector.py
from execution.intelligence.change_point_detector import detect_change_points

class TestDetectChangePoints:
    def test_detects_known_change_point(self, sample_security_series):
        """Series has known change-point at week 12."""
        change_points = detect_change_points(sample_security_series)

        # Should detect change-point near week 12 (±1 week tolerance)
        assert any(abs(cp - 12) <= 1 for cp in change_points), \
            f"Expected change-point near week 12, got {change_points}"

    def test_no_change_points_on_monotonic_series(self):
        """Perfectly linear series should have no change-points."""
        linear = [100 - i for i in range(20)]
        change_points = detect_change_points(linear, min_size=4)
        assert len(change_points) == 0, f"Expected no change-points, got {change_points}"

    def test_returns_list_of_week_indices(self, sample_security_series):
        change_points = detect_change_points(sample_security_series)
        assert isinstance(change_points, list)
        assert all(isinstance(cp, int) for cp in change_points)
```

---

## Risk Scorer Tests

```python
# tests/intelligence/test_risk_scorer.py
from execution.intelligence.risk_scorer import (
    compute_risk_score, score_vuln_risk, score_deployment_risk, apply_volatility_penalty
)

class TestComputeRiskScore:
    def test_all_zeros_returns_zero(self):
        assert compute_risk_score(0, 0, 0, 0, 0) == 0.0

    def test_all_max_returns_100(self):
        assert compute_risk_score(100, 100, 100, 100, 100) == 100.0

    def test_weights_sum_to_one(self):
        """Each component at 100 should produce 100 composite score."""
        # Verify weights: 0.35 + 0.25 + 0.20 + 0.15 + 0.05 = 1.0
        score = compute_risk_score(100, 100, 100, 100, 100)
        assert score == 100.0

    def test_vuln_component_highest_weight(self):
        """Vuln risk should have strongest influence."""
        all_vuln = compute_risk_score(100, 0, 0, 0, 0)    # Only vuln risk
        all_quality = compute_risk_score(0, 100, 0, 0, 0)  # Only quality risk
        assert all_vuln > all_quality  # Vuln weight (0.35) > quality weight (0.25)

class TestScoreVulnRisk:
    def test_zero_vulns_zero_risk(self):
        assert score_vuln_risk(0, 0, 0.0, "flat") == 0.0

    def test_worsening_trend_multiplier(self):
        score_flat = score_vuln_risk(10, 2, 0.1, "flat")
        score_worsening = score_vuln_risk(10, 2, 0.1, "worsening")
        assert score_worsening > score_flat  # Worsening adds multiplier

    def test_capped_at_100(self):
        """Extreme inputs should not exceed 100."""
        score = score_vuln_risk(1000, 100, 1.0, "worsening")
        assert score <= 100.0

class TestApplyVolatilityPenalty:
    def test_high_cv_increases_score(self):
        base = 50.0
        low_cv = apply_volatility_penalty(base, cv=0.1)
        high_cv = apply_volatility_penalty(base, cv=0.8)
        assert high_cv > low_cv

    def test_low_cv_unchanged(self):
        assert apply_volatility_penalty(50.0, cv=0.2) == 50.0  # Below threshold
```

---

## Insight Generator Tests

```python
# tests/intelligence/test_insight_generator.py
import os
from unittest.mock import patch, MagicMock
from execution.intelligence.insight_generator import generate_insight, format_insight

class TestFormatInsight:
    def test_anomaly_spike_template(self):
        result = format_insight(
            "anomaly_spike",
            metric="Open Bugs",
            delta_pct=15,
            top_dimension="Product_B",
            dim_delta=12,
        )
        assert "Open Bugs" in result
        assert "Product_B" in result
        assert "⚠️" in result

    def test_unknown_template_raises(self):
        with pytest.raises(ValueError, match="Unknown insight template"):
            format_insight("nonexistent_template")

class TestGenerateInsight:
    def test_template_fallback_without_api_key(self, sample_forecast_context):
        """Without API key, should use template-based insights."""
        with patch.dict(os.environ, {}, clear=True):  # Remove all env vars
            result = generate_insight(sample_forecast_context)
        assert result  # Should produce something
        assert isinstance(result, str)
        assert len(result) > 20

    def test_llm_path_calls_claude(self, sample_forecast_context):
        """With API key set, should attempt Claude API call."""
        mock_response = MagicMock()
        mock_response.content[0].text = "Vulnerabilities declining steadily. Maintain current triage pace."

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic.messages.create", return_value=mock_response):
                result = generate_insight(sample_forecast_context, use_llm=True)

        assert "Vulnerabilities" in result

    def test_llm_failure_falls_back_to_template(self, sample_forecast_context):
        """If LLM call fails, should fall back gracefully."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic.messages.create", side_effect=Exception("API error")):
                result = generate_insight(sample_forecast_context, use_llm=True)

        # Should still return a valid insight (template fallback)
        assert result
        assert isinstance(result, str)
```

---

## Running the Full Suite

```bash
# Run all intelligence tests
pytest tests/intelligence/ -v

# Run with coverage report
pytest tests/intelligence/ --cov=execution/intelligence --cov-report=term-missing

# Run a specific test file
pytest tests/intelligence/test_forecast_engine.py -v

# Run with verbose output for debugging
pytest tests/intelligence/ -v --tb=long -s
```

**Target**: 80%+ coverage on each module. Check with:
```bash
pytest tests/intelligence/ --cov=execution/intelligence --cov-fail-under=80
```
