"""
Shared test fixtures for the execution/intelligence/ module tests.

All fixtures use synthetic data only — no real project names, no real
ADO data, no external API calls. Mirrors the skill file conventions
from memory/skills/intelligence-testing.md.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------


def _weeks(n: int) -> list[datetime]:
    """Generate n weekly datetimes ending on today."""
    base = datetime(2025, 10, 6)  # Fixed base so tests are deterministic
    return [base + timedelta(weeks=i) for i in range(n)]


# ---------------------------------------------------------------------------
# Quality fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_quality_series() -> pd.DataFrame:
    """20 weeks of synthetic quality data with a mild improving trend."""
    dates = _weeks(20)
    open_bugs = [300 - i * 2 + (i % 3) for i in range(20)]  # ~improving
    p1_bugs = [15 - i // 3 for i in range(20)]
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Product_A"] * 20,
            "open_bugs": open_bugs,
            "p1_bugs": p1_bugs,
        }
    )


@pytest.fixture
def sample_quality_series_short() -> pd.DataFrame:
    """Only 8 weeks — below the 12-week minimum for forecasting."""
    dates = _weeks(8)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Product_A"] * 8,
            "open_bugs": [300 - i for i in range(8)],
            "p1_bugs": [15] * 8,
        }
    )


# ---------------------------------------------------------------------------
# Security fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_security_series() -> pd.DataFrame:
    """20 weeks of synthetic security data with a worsening trend."""
    dates = _weeks(20)
    vulns = [200 + i * 3 for i in range(20)]  # worsening
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Product_B"] * 20,
            "total_vulnerabilities": vulns,
            "critical_count": [10 + i // 4 for i in range(20)],
        }
    )


# ---------------------------------------------------------------------------
# Anomaly fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_clean_series() -> pd.DataFrame:
    """20 weeks with no anomalies — stable values."""
    dates = _weeks(20)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Product_C"] * 20,
            "value": [100.0] * 20,
        }
    )


@pytest.fixture
def sample_anomaly_series() -> pd.DataFrame:
    """20 weeks with a clear 3-sigma spike at week 15."""
    dates = _weeks(20)
    values = [100.0] * 20
    values[14] = 350.0  # 3-sigma spike
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Product_C"] * 20,
            "value": values,
        }
    )


# ---------------------------------------------------------------------------
# Change-point fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_change_point_series() -> pd.DataFrame:
    """24 weeks with a clear regime change at week 12."""
    dates = _weeks(24)
    values = [50.0] * 12 + [120.0] * 12  # step change at index 12
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Product_D"] * 24,
            "value": values,
        }
    )


# ---------------------------------------------------------------------------
# Forecast context fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_forecast_context() -> dict:
    """
    Minimal context dict for insight generator / narrative tests.
    Uses only generic names — no real project names.
    """
    return {
        "metric": "open_bugs",
        "project": "Product_A",
        "current": 240,
        "delta": -5.2,
        "trend_direction": "improving",
        "trend_strength": 0.78,
        "forecast_p50": 210,
        "forecast_p10": 185,
        "forecast_p90": 238,
        "context": "4-week forecast based on 20 weeks of history",
    }
