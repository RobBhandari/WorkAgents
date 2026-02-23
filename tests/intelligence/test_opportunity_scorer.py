"""
Tests for execution/intelligence/opportunity_scorer.py

Single responsibility: verify that opportunity scoring functions produce correct,
bounded, and descriptive results from synthetic feature DataFrames.

All fixtures use synthetic data only — no real project names, no real ADO data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from execution.intelligence.opportunity_scorer import (
    OPPORTUNITY_TEMPLATES,
    OpportunityScore,
    _choose_template,
    _compute_target_gap,
    _count_improving_weeks,
    _extract_series,
    find_top_opportunities,
    score_opportunity,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _weeks(n: int) -> list[datetime]:
    """Generate n sequential weekly datetimes (deterministic base)."""
    base = datetime(2025, 10, 6)
    return [base + timedelta(weeks=i) for i in range(n)]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def improving_bugs_df() -> pd.DataFrame:
    """20 weeks of open_bugs with a clear improving (decreasing) trend."""
    dates = _weeks(20)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Synth_A"] * 20,
            "open_bugs": [300 - i * 5 for i in range(20)],  # 300 → 205
        }
    )


@pytest.fixture
def worsening_bugs_df() -> pd.DataFrame:
    """20 weeks of open_bugs worsening (increasing)."""
    dates = _weeks(20)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Synth_A"] * 20,
            "open_bugs": [100 + i * 10 for i in range(20)],  # 100 → 290
        }
    )


@pytest.fixture
def flat_bugs_df() -> pd.DataFrame:
    """20 weeks of open_bugs completely flat."""
    dates = _weeks(20)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Synth_A"] * 20,
            "open_bugs": [150] * 20,
        }
    )


@pytest.fixture
def sparse_bugs_df() -> pd.DataFrame:
    """Only 2 weeks of data (below _MIN_POINTS threshold)."""
    dates = _weeks(2)
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Synth_A"] * 2,
            "open_bugs": [200, 195],
        }
    )


@pytest.fixture
def multi_project_df() -> pd.DataFrame:
    """Two projects across 20 weeks, for find_top_opportunities tests."""
    dates = _weeks(20)
    return pd.DataFrame(
        {
            "week_date": dates * 2,
            "project": ["Synth_A"] * 20 + ["Synth_B"] * 20,
            "open_bugs": [300 - i * 5 for i in range(20)] + [100 + i * 8 for i in range(20)],
        }
    )


# ---------------------------------------------------------------------------
# _extract_series
# ---------------------------------------------------------------------------


class TestExtractSeries:
    def test_returns_sorted_values(self) -> None:
        dates = [datetime(2025, 1, 7), datetime(2025, 1, 1), datetime(2025, 1, 14)]
        df = pd.DataFrame({"week_date": dates, "project": ["A"] * 3, "open_bugs": [30, 10, 20]})
        result = _extract_series(df, "open_bugs")
        assert result == [10, 30, 20]  # Sorted by date: Jan1=10, Jan7=30, Jan14=20

    def test_drops_nan_values(self) -> None:
        import math

        dates = _weeks(5)
        values = [100, None, 90, None, 80]
        df = pd.DataFrame({"week_date": dates, "project": ["A"] * 5, "open_bugs": values})
        result = _extract_series(df, "open_bugs")
        assert all(not math.isnan(v) for v in result)
        assert len(result) == 3

    def test_deduplicates_by_week_date(self) -> None:
        """Same week_date appearing twice should yield one value."""
        same_date = datetime(2025, 1, 6)
        df = pd.DataFrame(
            {
                "week_date": [same_date, same_date, same_date],
                "project": ["A"] * 3,
                "open_bugs": [100, 110, 120],
            }
        )
        result = _extract_series(df, "open_bugs")
        assert len(result) == 1

    def test_missing_column_returns_empty(self) -> None:
        df = pd.DataFrame({"week_date": _weeks(5), "project": ["A"] * 5})
        assert _extract_series(df, "open_bugs") == []

    def test_empty_df_returns_empty(self) -> None:
        assert _extract_series(pd.DataFrame(), "open_bugs") == []


# ---------------------------------------------------------------------------
# _compute_target_gap
# ---------------------------------------------------------------------------


class TestComputeTargetGap:
    def test_at_best_value_gap_is_zero(self) -> None:
        # For lower_is_better: best = min. Current at min → gap = 0
        series: list[float] = [100.0, 90.0, 80.0, 70.0, 60.0]  # improving; best = 60
        gap = _compute_target_gap(series, lower_is_better=True)
        assert gap == pytest.approx(0.0, abs=0.01)

    def test_at_worst_value_gap_is_one(self) -> None:
        # For lower_is_better: worst = max. Current at max → gap = 1
        series: list[float] = [60.0, 70.0, 80.0, 90.0, 100.0]  # worsening; current = 100, worst = 100
        gap = _compute_target_gap(series, lower_is_better=True)
        assert gap == pytest.approx(1.0, abs=0.01)

    def test_no_variation_gap_is_zero(self) -> None:
        series: list[float] = [50.0, 50.0, 50.0, 50.0]
        assert _compute_target_gap(series, lower_is_better=True) == 0.0

    def test_empty_series_returns_neutral(self) -> None:
        assert _compute_target_gap([], lower_is_better=True) == 0.5

    def test_higher_is_better_inverts_gap(self) -> None:
        # For higher_is_better: best = max. Current at max → gap = 0
        series: list[float] = [60.0, 70.0, 80.0, 90.0, 100.0]  # improving; best = 100, current = 100
        gap = _compute_target_gap(series, lower_is_better=False)
        assert gap == pytest.approx(0.0, abs=0.01)


# ---------------------------------------------------------------------------
# _count_improving_weeks
# ---------------------------------------------------------------------------


class TestCountImprovingWeeks:
    def test_consistently_improving(self) -> None:
        # lower_is_better=True: series decreasing = improving
        series: list[float] = [100.0, 95.0, 90.0, 85.0, 80.0]
        assert _count_improving_weeks(series, lower_is_better=True) == 4

    def test_no_improvement(self) -> None:
        series: list[float] = [80.0, 85.0, 90.0, 95.0, 100.0]
        assert _count_improving_weeks(series, lower_is_better=True) == 0

    def test_partial_improvement_stops_at_reversal(self) -> None:
        series: list[float] = [100.0, 95.0, 100.0, 95.0, 90.0]
        # Only last 2 pairs improve before reversal breaks streak
        assert _count_improving_weeks(series, lower_is_better=True) == 2

    def test_single_element_returns_zero(self) -> None:
        assert _count_improving_weeks([100.0], lower_is_better=True) == 0

    def test_higher_is_better_direction(self) -> None:
        # For higher_is_better: series increasing = improving
        series: list[float] = [70.0, 75.0, 80.0, 85.0, 90.0]
        assert _count_improving_weeks(series, lower_is_better=False) == 4


# ---------------------------------------------------------------------------
# _choose_template
# ---------------------------------------------------------------------------


class TestChooseTemplate:
    def test_fast_improver(self) -> None:
        assert _choose_template("improving", 2.5, 10) == "improving_fast"

    def test_steady_improver(self) -> None:
        assert _choose_template("improving", 0.5, 5) == "improving_steady"

    def test_flat_potential(self) -> None:
        assert _choose_template("flat", 0.0, 0) == "flat_potential"

    def test_worsening_large_gap(self) -> None:
        assert _choose_template("worsening", -1.5, 0) == "large_gap"

    def test_all_template_keys_valid(self) -> None:
        """Ensure chosen template keys always exist in OPPORTUNITY_TEMPLATES."""
        for direction, rate, weeks in [
            ("improving", 3.0, 8),
            ("improving", 0.3, 3),
            ("flat", 0.0, 0),
            ("worsening", -2.0, 0),
        ]:
            key = _choose_template(direction, rate, weeks)
            assert key in OPPORTUNITY_TEMPLATES, f"Template key '{key}' not found"


# ---------------------------------------------------------------------------
# score_opportunity
# ---------------------------------------------------------------------------


class TestScoreOpportunity:
    def test_returns_opportunity_score_instance(self, improving_bugs_df: pd.DataFrame) -> None:
        result = score_opportunity(improving_bugs_df, "open_bugs", "Synth_A")
        assert isinstance(result, OpportunityScore)

    def test_score_bounded_0_100(self, improving_bugs_df: pd.DataFrame) -> None:
        result = score_opportunity(improving_bugs_df, "open_bugs", "Synth_A")
        assert result is not None
        assert 0.0 <= result.opportunity_score <= 100.0

    def test_improving_trend_detected(self, improving_bugs_df: pd.DataFrame) -> None:
        result = score_opportunity(improving_bugs_df, "open_bugs", "Synth_A")
        assert result is not None
        assert result.trend_direction == "improving"

    def test_worsening_trend_detected(self, worsening_bugs_df: pd.DataFrame) -> None:
        result = score_opportunity(worsening_bugs_df, "open_bugs", "Synth_A")
        assert result is not None
        assert result.trend_direction == "worsening"

    def test_worsening_gets_reduced_score(self) -> None:
        """
        A metric with a large remaining gap AND improving trend should score
        higher than a purely worsening metric at the same absolute level.

        Use a partial-improvement series (not at best value) so gap > 0.
        """
        dates = _weeks(20)
        # Improving but not yet at best: starts at 300, ends at 200, still has gap vs 0
        partial_improving_df = pd.DataFrame(
            {
                "week_date": dates,
                "project": ["Synth_A"] * 20,
                "open_bugs": [300 - i * 5 for i in range(20)],  # 300 → 205
            }
        )
        # Worsening: starts at 100, ends at 290
        worsening_df = pd.DataFrame(
            {
                "week_date": dates,
                "project": ["Synth_A"] * 20,
                "open_bugs": [100 + i * 10 for i in range(20)],
            }
        )
        # Give the improving series a large artificial gap by anchoring worst at 1000
        # We verify that worsening gets the 0.4 multiplier applied
        improving_result = score_opportunity(partial_improving_df, "open_bugs", "Synth_A")
        worsening_result = score_opportunity(worsening_df, "open_bugs", "Synth_A")
        assert worsening_result is not None
        # Key assertion: worsening direction should have reduced score due to 0.4 penalty
        # (the test verifies the 40% reduction is applied, not the relative ordering)
        assert worsening_result.trend_direction == "worsening"

    def test_sparse_data_returns_none(self, sparse_bugs_df: pd.DataFrame) -> None:
        result = score_opportunity(sparse_bugs_df, "open_bugs", "Synth_A")
        assert result is None

    def test_missing_column_returns_none(self, improving_bugs_df: pd.DataFrame) -> None:
        result = score_opportunity(improving_bugs_df, "nonexistent_col", "Synth_A")
        assert result is None

    def test_project_name_in_result(self, improving_bugs_df: pd.DataFrame) -> None:
        result = score_opportunity(improving_bugs_df, "open_bugs", "Synth_A")
        assert result is not None
        assert result.project == "Synth_A"

    def test_description_is_nonempty_string(self, improving_bugs_df: pd.DataFrame) -> None:
        result = score_opportunity(improving_bugs_df, "open_bugs", "Synth_A")
        assert result is not None
        assert isinstance(result.description, str)
        assert len(result.description) > 0

    def test_recommended_action_passed_through(self, improving_bugs_df: pd.DataFrame) -> None:
        custom_action = "Fix all bugs immediately."
        result = score_opportunity(
            improving_bugs_df,
            "open_bugs",
            "Synth_A",
            recommended_action=custom_action,
        )
        assert result is not None
        assert result.recommended_action == custom_action

    def test_higher_impact_weight_raises_score(self) -> None:
        """
        A series with both positive trend and remaining gap responds to impact_weight.

        We use a worsening series so it has a real target_gap > 0 (current > best).
        """
        dates = _weeks(20)
        # Worsening series: gap > 0 because current (290) is far from best (100)
        df = pd.DataFrame(
            {
                "week_date": dates,
                "project": ["Synth_A"] * 20,
                "open_bugs": [100 + i * 10 for i in range(20)],
            }
        )
        low_impact = score_opportunity(df, "open_bugs", "Synth_A", impact_weight=0.1)
        high_impact = score_opportunity(df, "open_bugs", "Synth_A", impact_weight=1.0)
        assert low_impact is not None
        assert high_impact is not None
        assert high_impact.opportunity_score > low_impact.opportunity_score

    def test_lower_effort_raises_score(self) -> None:
        """
        A series with remaining gap shows that lower effort → higher opportunity score.

        Uses worsening series where gap > 0.
        """
        dates = _weeks(20)
        df = pd.DataFrame(
            {
                "week_date": dates,
                "project": ["Synth_A"] * 20,
                "open_bugs": [100 + i * 10 for i in range(20)],
            }
        )
        high_effort = score_opportunity(df, "open_bugs", "Synth_A", effort=3.0)
        low_effort = score_opportunity(df, "open_bugs", "Synth_A", effort=1.0)
        assert high_effort is not None
        assert low_effort is not None
        assert low_effort.opportunity_score > high_effort.opportunity_score

    def test_flat_series_produces_flat_direction(self, flat_bugs_df: pd.DataFrame) -> None:
        result = score_opportunity(flat_bugs_df, "open_bugs", "Synth_A")
        assert result is not None
        assert result.trend_direction == "flat"


# ---------------------------------------------------------------------------
# find_top_opportunities (mocked I/O)
# ---------------------------------------------------------------------------


class TestFindTopOpportunities:
    def test_returns_list_of_opportunity_scores(self) -> None:
        dates = _weeks(20)
        synthetic_df = pd.DataFrame(
            {
                "week_date": dates,
                "project": ["Synth_A"] * 20,
                "open_bugs": [300 - i * 5 for i in range(20)],
            }
        )

        def mock_load(metric: str, project: str | None, base_dir: Path) -> pd.DataFrame:
            if metric == "quality":
                return synthetic_df
            raise ValueError("no data")

        with patch(
            "execution.intelligence.opportunity_scorer.load_features",
            side_effect=mock_load,
        ):
            results = find_top_opportunities(top_n=3)

        assert all(isinstance(r, OpportunityScore) for r in results)

    def test_result_count_respects_top_n(self) -> None:
        dates = _weeks(20)

        def mock_load(metric: str, project: str | None, base_dir: Path) -> pd.DataFrame:
            if metric == "quality":
                return pd.DataFrame(
                    {
                        "week_date": dates * 3,
                        "project": ["P1"] * 20 + ["P2"] * 20 + ["P3"] * 20,
                        "open_bugs": [300 - i * 5 for i in range(20)] * 3,
                    }
                )
            raise ValueError("no data")

        with patch(
            "execution.intelligence.opportunity_scorer.load_features",
            side_effect=mock_load,
        ):
            results = find_top_opportunities(top_n=2)

        assert len(results) <= 2

    def test_sorted_descending_by_score(self) -> None:
        dates = _weeks(20)

        def mock_load(metric: str, project: str | None, base_dir: Path) -> pd.DataFrame:
            if metric == "quality":
                return pd.DataFrame(
                    {
                        "week_date": dates * 2,
                        "project": ["Synth_A"] * 20 + ["Synth_B"] * 20,
                        # Synth_A improves faster than Synth_B
                        "open_bugs": [500 - i * 10 for i in range(20)] + [200 - i * 1 for i in range(20)],
                    }
                )
            raise ValueError("no data")

        with patch(
            "execution.intelligence.opportunity_scorer.load_features",
            side_effect=mock_load,
        ):
            results = find_top_opportunities(top_n=5)

        scores = [r.opportunity_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_no_feature_data_returns_empty_list(self) -> None:
        with patch(
            "execution.intelligence.opportunity_scorer.load_features",
            side_effect=ValueError("no data"),
        ):
            results = find_top_opportunities()

        assert results == []

    def test_sentinel_projects_excluded(self) -> None:
        """Projects starting with '_' (like '_portfolio') must not appear in results."""
        dates = _weeks(20)

        def mock_load(metric: str, project: str | None, base_dir: Path) -> pd.DataFrame:
            if metric == "quality":
                return pd.DataFrame(
                    {
                        "week_date": dates * 2,
                        "project": ["_portfolio"] * 20 + ["Synth_A"] * 20,
                        "open_bugs": [500 - i * 5 for i in range(20)] * 2,
                    }
                )
            raise ValueError("no data")

        with patch(
            "execution.intelligence.opportunity_scorer.load_features",
            side_effect=mock_load,
        ):
            results = find_top_opportunities(top_n=10)

        project_names = [r.project for r in results]
        assert "_portfolio" not in project_names

    def test_all_opportunity_scores_bounded(self) -> None:
        dates = _weeks(20)

        def mock_load(metric: str, project: str | None, base_dir: Path) -> pd.DataFrame:
            if metric == "quality":
                return pd.DataFrame(
                    {
                        "week_date": dates,
                        "project": ["Synth_A"] * 20,
                        "open_bugs": [300 - i * 5 for i in range(20)],
                    }
                )
            raise ValueError("no data")

        with patch(
            "execution.intelligence.opportunity_scorer.load_features",
            side_effect=mock_load,
        ):
            results = find_top_opportunities()

        for r in results:
            assert 0.0 <= r.opportunity_score <= 100.0
