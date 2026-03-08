"""
Tests for execution/intelligence/signals.py

Coverage:
- empty / non-numeric metric data  → no signal generated
- insufficient series length       → no deterioration / recovery signal
- threshold_breach rule            → fires below 90%, correct severity bands
- sustained_deterioration rule     → fires at >= 3 of 4 worsening pairs
- recovery_trend rule              → fires at >= 3 of 4 improving pairs
- deterministic sorting            → severity first, then magnitude, then metric_id
- 5-signal cap                     → only top 5 returned from many candidates
- empty-state response shape       → correct keys when no signals fire
- auth on /api/v1/intelligence/signals  → 401 without credentials
- internal error handling          → 500 returned, detail not leaking internals
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from execution.api.app import create_app
from execution.intelligence.signals import (
    _DEPLOYMENT_THRESHOLD,
    _METRIC_DIRECTION,
    MAX_SIGNALS,
    MIN_SERIES_LEN,
    _rule_recovery_trend,
    _rule_sustained_deterioration,
    _rule_threshold_breach,
    build_signals_response,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metric(
    metric_id: str,
    current: Any = 100.0,
    data: list[Any] | None = None,
    title: str = "Test Metric",
) -> dict[str, Any]:
    """Build a minimal metric dict matching the renderer output shape."""
    return {
        "id": metric_id,
        "title": title,
        "current": current,
        "data": data if data is not None else [],
    }


def _worsening_series(n: int, good_direction: str = "down") -> list[float]:
    """Return a strictly worsening series of length n."""
    if good_direction == "down":
        return [float(100 + i * 5) for i in range(n)]  # rising (bad for "down")
    return [float(100 - i * 5) for i in range(n)]  # falling (bad for "up")


def _improving_series(n: int, good_direction: str = "down") -> list[float]:
    """Return a strictly improving series of length n."""
    if good_direction == "down":
        return [float(100 - i * 5) for i in range(n)]  # falling (good for "down")
    return [float(100 + i * 5) for i in range(n)]  # rising (good for "up")


# ---------------------------------------------------------------------------
# TestEmptyOrNonNumericData
# ---------------------------------------------------------------------------


class TestEmptyOrNonNumericData:
    def test_empty_data_no_deterioration_signal(self) -> None:
        result = _rule_sustained_deterioration(_metric("bugs", current=100.0, data=[]))
        assert result is None

    def test_empty_data_no_recovery_signal(self) -> None:
        result = _rule_recovery_trend(_metric("bugs", current=100.0, data=[]))
        assert result is None

    def test_non_numeric_data_no_deterioration_signal(self) -> None:
        result = _rule_sustained_deterioration(_metric("bugs", current=100.0, data=["a", "b", "c", "d", "e"]))
        assert result is None

    def test_non_numeric_current_no_threshold_signal(self) -> None:
        result = _rule_threshold_breach(_metric("deployment", current="N/A"))
        assert result is None

    def test_non_numeric_current_no_deterioration_signal(self) -> None:
        series = _worsening_series(MIN_SERIES_LEN)
        result = _rule_sustained_deterioration(_metric("bugs", current="N/A", data=series))
        assert result is None

    def test_metric_with_empty_string_current_skipped(self) -> None:
        """ai-usage style card with empty current/data must not produce signals."""
        result = build_signals_response([_metric("ai-usage", current="", data=[])])
        assert result["signal_count"] == 0
        assert result["signals"] == []


# ---------------------------------------------------------------------------
# TestInsufficientHistory
# ---------------------------------------------------------------------------


class TestInsufficientHistory:
    def test_too_short_for_deterioration(self) -> None:
        """Series shorter than MIN_SERIES_LEN must not trigger deterioration."""
        short = _worsening_series(MIN_SERIES_LEN - 1)
        result = _rule_sustained_deterioration(_metric("bugs", current=float(short[-1]), data=short))
        assert result is None

    def test_too_short_for_recovery(self) -> None:
        """Series shorter than MIN_SERIES_LEN must not trigger recovery."""
        short = _improving_series(MIN_SERIES_LEN - 1)
        result = _rule_recovery_trend(_metric("bugs", current=float(short[-1]), data=short))
        assert result is None

    def test_exactly_min_len_can_trigger(self) -> None:
        """Series of exactly MIN_SERIES_LEN points (4 pairs) is eligible."""
        series = _worsening_series(MIN_SERIES_LEN)
        result = _rule_sustained_deterioration(_metric("bugs", current=float(series[-1]), data=series))
        assert result is not None


# ---------------------------------------------------------------------------
# TestThresholdBreachRule
# ---------------------------------------------------------------------------


class TestThresholdBreachRule:
    def test_above_threshold_no_signal(self) -> None:
        result = _rule_threshold_breach(_metric("deployment", current=95.0))
        assert result is None

    def test_at_threshold_no_signal(self) -> None:
        result = _rule_threshold_breach(_metric("deployment", current=_DEPLOYMENT_THRESHOLD))
        assert result is None

    def test_below_threshold_warning(self) -> None:
        result = _rule_threshold_breach(_metric("deployment", current=85.0))
        assert result is not None
        assert result["severity"] == "warning"
        assert result["type"] == "threshold_breach"
        assert result["current_value"] == 85.0
        assert result["baseline_value"] == _DEPLOYMENT_THRESHOLD

    def test_below_80_critical(self) -> None:
        result = _rule_threshold_breach(_metric("deployment", current=75.0))
        assert result is not None
        assert result["severity"] == "critical"

    def test_non_deployment_metric_ignored(self) -> None:
        result = _rule_threshold_breach(_metric("bugs", current=50.0))
        assert result is None

    def test_schema_fields_present(self) -> None:
        result = _rule_threshold_breach(_metric("deployment", current=85.0))
        assert result is not None
        for field in (
            "id",
            "metric_id",
            "type",
            "severity",
            "direction",
            "title",
            "message",
            "current_value",
            "baseline_value",
            "window_weeks",
        ):
            assert field in result, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# TestSustainedDeteriorationRule
# ---------------------------------------------------------------------------


class TestSustainedDeteriorationRule:
    def test_3_of_4_worsening_triggers(self) -> None:
        # Pattern: up, up, up, down — 3 worsening pairs for "down" direction metric
        series = [100.0, 105.0, 110.0, 115.0, 112.0]  # last pair improves
        result = _rule_sustained_deterioration(_metric("bugs", current=112.0, data=series))
        assert result is not None
        assert result["type"] == "sustained_deterioration"
        assert result["severity"] == "warning"

    def test_only_2_of_4_worsening_no_signal(self) -> None:
        series = [100.0, 105.0, 100.0, 105.0, 100.0]  # alternating — 2 of 4 worsening
        result = _rule_sustained_deterioration(_metric("bugs", current=100.0, data=series))
        assert result is None

    def test_4_of_4_strictly_worsening(self) -> None:
        series = _worsening_series(MIN_SERIES_LEN)
        result = _rule_sustained_deterioration(_metric("bugs", current=float(series[-1]), data=series))
        assert result is not None

    def test_stable_direction_metric_excluded(self) -> None:
        assert "risk" not in _METRIC_DIRECTION
        series = _worsening_series(MIN_SERIES_LEN)
        result = _rule_sustained_deterioration(_metric("risk", current=float(series[-1]), data=series))
        assert result is None

    def test_baseline_value_is_8_week_mean(self) -> None:
        series = list(range(1, 14))  # 13 points; last 8: [6..13]
        result = _rule_sustained_deterioration(_metric("bugs", current=float(series[-1]), data=series))
        # Series is 1,2,...13 — strictly worsening (rising, bad for "down")
        assert result is not None
        expected_baseline = sum(range(6, 14)) / 8  # mean of [6,7,...,13]
        assert abs(result["baseline_value"] - expected_baseline) < 0.01


# ---------------------------------------------------------------------------
# TestRecoveryTrendRule
# ---------------------------------------------------------------------------


class TestRecoveryTrendRule:
    def test_3_of_4_improving_triggers(self) -> None:
        # Pattern: falling (good), falling, falling, rising — 3 improving pairs
        series = [115.0, 110.0, 105.0, 100.0, 103.0]  # last pair worsens
        result = _rule_recovery_trend(_metric("bugs", current=103.0, data=series))
        assert result is not None
        assert result["type"] == "recovery_trend"
        assert result["severity"] == "info"
        assert result["direction"] == "up"

    def test_only_2_of_4_improving_no_signal(self) -> None:
        series = [100.0, 95.0, 100.0, 95.0, 100.0]  # alternating — 2 of 4 improving
        result = _rule_recovery_trend(_metric("bugs", current=100.0, data=series))
        assert result is None

    def test_up_direction_metric_recovery(self) -> None:
        # deployment: higher is better — falling then recovering = bad then good
        series = [95.0, 85.0, 80.0, 85.0, 90.0]  # last 3 of 4 pairs are improving
        # pairs: (95→85)= -10 bad, (85→80)= -5 bad, (80→85)= +5 good, (85→90)= +5 good
        # 2 worsening, 2 improving — should NOT trigger (needs >=3)
        result = _rule_recovery_trend(_metric("deployment", current=90.0, data=series))
        assert result is None

    def test_up_direction_3_of_4_improving(self) -> None:
        # pairs: bad, good, good, good
        series = [90.0, 85.0, 88.0, 91.0, 94.0]
        result = _rule_recovery_trend(_metric("deployment", current=94.0, data=series))
        assert result is not None
        assert result["metric_id"] == "deployment"


# ---------------------------------------------------------------------------
# TestDeterministicSorting
# ---------------------------------------------------------------------------


class TestDeterministicSorting:
    def _make_signal(self, metric_id: str, severity: str, magnitude: float) -> dict[str, Any]:
        return {
            "id": f"signal-{metric_id}-threshold_breach",
            "metric_id": metric_id,
            "type": "threshold_breach",
            "severity": severity,
            "direction": "down",
            "title": f"{metric_id} signal",
            "message": "test",
            "current_value": 50.0,
            "baseline_value": 50.0 + magnitude,
            "window_weeks": 1,
            "_magnitude": magnitude,
        }

    def test_critical_before_warning(self) -> None:
        metrics = [
            _metric("deployment", current=85.0),  # warning threshold breach
        ]
        # Inject a critical signal via mock to test sorting without real data
        critical_m = _metric("bugs", current=50.0, data=_worsening_series(MIN_SERIES_LEN))
        with patch(
            "execution.intelligence.signals._RULES",
            [
                lambda m: self._make_signal("aaa", "warning", 5.0) if m["id"] == "aaa" else None,
                lambda m: self._make_signal("bbb", "critical", 3.0) if m["id"] == "bbb" else None,
            ],
        ):
            result = build_signals_response([_metric("aaa", current=10.0), _metric("bbb", current=10.0)])
        signals = result["signals"]
        assert signals[0]["severity"] == "critical"
        assert signals[1]["severity"] == "warning"

    def test_same_severity_higher_magnitude_first(self) -> None:
        with patch(
            "execution.intelligence.signals._RULES",
            [
                lambda m: self._make_signal("aaa", "warning", 10.0) if m["id"] == "aaa" else None,
                lambda m: self._make_signal("bbb", "warning", 50.0) if m["id"] == "bbb" else None,
            ],
        ):
            result = build_signals_response([_metric("aaa", current=10.0), _metric("bbb", current=10.0)])
        signals = result["signals"]
        assert signals[0]["metric_id"] == "bbb"  # larger magnitude first
        assert signals[1]["metric_id"] == "aaa"

    def test_same_severity_same_magnitude_metric_id_alphabetical(self) -> None:
        with patch(
            "execution.intelligence.signals._RULES",
            [
                lambda m: self._make_signal("zzz", "warning", 10.0) if m["id"] == "zzz" else None,
                lambda m: self._make_signal("aaa", "warning", 10.0) if m["id"] == "aaa" else None,
            ],
        ):
            result = build_signals_response([_metric("zzz", current=10.0), _metric("aaa", current=10.0)])
        signals = result["signals"]
        assert signals[0]["metric_id"] == "aaa"
        assert signals[1]["metric_id"] == "zzz"


# ---------------------------------------------------------------------------
# TestFiveSignalCap
# ---------------------------------------------------------------------------


class TestFiveSignalCap:
    def test_more_than_5_candidates_capped(self) -> None:
        def _make_rule(mid: str):
            def rule(m: dict[str, Any]) -> dict[str, Any] | None:
                if m["id"] == mid:
                    return {
                        "id": f"signal-{mid}-threshold_breach",
                        "metric_id": mid,
                        "type": "threshold_breach",
                        "severity": "warning",
                        "direction": "down",
                        "title": f"{mid} signal",
                        "message": "test",
                        "current_value": 50.0,
                        "baseline_value": 90.0,
                        "window_weeks": 1,
                        "_magnitude": 40.0,
                    }
                return None

            return rule

        metric_ids = [f"metric_{i}" for i in range(7)]
        with patch(
            "execution.intelligence.signals._RULES",
            [_make_rule(mid) for mid in metric_ids],
        ):
            result = build_signals_response([_metric(mid) for mid in metric_ids])

        assert result["signal_count"] == MAX_SIGNALS
        assert len(result["signals"]) == MAX_SIGNALS

    def test_magnitude_field_not_in_output(self) -> None:
        """Internal _magnitude field must be stripped from the serialised output."""
        metrics = [_metric("deployment", current=75.0)]
        result = build_signals_response(metrics)
        for signal in result["signals"]:
            assert "_magnitude" not in signal


# ---------------------------------------------------------------------------
# TestEmptyStateResponse
# ---------------------------------------------------------------------------


class TestEmptyStateResponse:
    def test_no_signals_returns_correct_shape(self) -> None:
        # Metric with no data and non-deployment id → no rules fire
        result = build_signals_response([_metric("unknown-metric", current=100.0, data=[])])
        assert result["signal_count"] == 0
        assert result["signals"] == []
        assert "generated_at" in result

    def test_empty_metrics_list(self) -> None:
        result = build_signals_response([])
        assert result["signal_count"] == 0
        assert result["signals"] == []
        assert "generated_at" in result


# ---------------------------------------------------------------------------
# TestApiAuth (integration — uses FastAPI TestClient)
# ---------------------------------------------------------------------------


def _mock_auth_config() -> MagicMock:
    """Return a mock config with admin/changeme credentials."""
    mock_auth = MagicMock()
    mock_auth.username = "admin"
    mock_auth.password = "changeme"
    mock_config = MagicMock()
    mock_config.get_api_auth_config.return_value = mock_auth
    return mock_config


class TestApiAuth:
    @pytest.fixture
    def client(self) -> Generator[TestClient, None, None]:
        with patch("execution.secure_config.get_config", return_value=_mock_auth_config()):
            yield TestClient(create_app())

    def test_unauthenticated_returns_401(self, client: TestClient) -> None:
        response = client.get("/api/v1/intelligence/signals")
        assert response.status_code == 401

    def test_invalid_credentials_returns_401(self, client: TestClient) -> None:
        response = client.get("/api/v1/intelligence/signals", auth=("wrong", "creds"))
        assert response.status_code == 401

    def test_valid_credentials_not_401(self, client: TestClient) -> None:
        """With valid credentials the endpoint responds — 200 or 404 (no data), not 401."""
        response = client.get("/api/v1/intelligence/signals", auth=("admin", "changeme"))
        assert response.status_code in (200, 404)


# ---------------------------------------------------------------------------
# TestInternalErrorHandling (integration)
# ---------------------------------------------------------------------------


class TestInternalErrorHandling:
    @pytest.fixture
    def client(self) -> Generator[TestClient, None, None]:
        with patch("execution.secure_config.get_config", return_value=_mock_auth_config()):
            yield TestClient(create_app())

    def test_unexpected_exception_returns_500(self, client: TestClient) -> None:
        with patch(
            "execution.dashboards.trends.pipeline.build_trends_context",
            side_effect=RuntimeError("boom"),
        ):
            response = client.get("/api/v1/intelligence/signals", auth=("admin", "changeme"))
        assert response.status_code == 500
        body = response.json()
        assert "detail" in body
        # Internal traceback must not be exposed.
        assert "boom" not in body["detail"]
        assert "Traceback" not in body["detail"]

    def test_no_historical_data_returns_404(self, client: TestClient) -> None:
        with patch(
            "execution.dashboards.trends.pipeline.build_trends_context",
            side_effect=ValueError("No historical data found"),
        ):
            response = client.get("/api/v1/intelligence/signals", auth=("admin", "changeme"))
        assert response.status_code == 404

    def test_build_signals_response_exception_returns_500(self, client: TestClient) -> None:
        """Unexpected error inside build_signals_response must return 500, not leak internals."""
        dummy_context = {
            "metrics": [],
            "active_alerts": [],
            "timestamp": "March 08, 2026 at 12:00",
        }
        with (
            patch(
                "execution.dashboards.trends.pipeline.build_trends_context",
                return_value=dummy_context,
            ),
            patch(
                "execution.intelligence.signals.build_signals_response",
                side_effect=RuntimeError("internal serialisation error"),
            ),
        ):
            response = client.get("/api/v1/intelligence/signals", auth=("admin", "changeme"))
        assert response.status_code == 500
        body = response.json()
        assert "detail" in body
        assert "internal serialisation error" not in body["detail"]
        assert "Traceback" not in body["detail"]
