"""
Tests for execution/dashboards/correlation_heatmap.py

Covers:
- _load_correlation_matrix() with mocked empty correlation → returns {}
- _calculate_summary() with empty matrix → has_data False
- _calculate_summary() with 3x3 matrix → correct metric_count, strong_correlations
- _build_context() → framework_css/js present
- generate_correlation_heatmap() with mocked matrix → returns HTML string
- generate_correlation_heatmap() with output_dir → writes file
- _build_correlation_heatmap_chart() with empty matrix → returns ""
- _build_correlation_heatmap_chart() with known matrix → returns non-empty string
- main() integration behaviour (mocked generate)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from execution.dashboards.correlation_heatmap import (
    _build_context,
    _build_correlation_heatmap_chart,
    _calculate_summary,
    _load_correlation_matrix,
    generate_correlation_heatmap,
    main,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_matrix() -> dict:
    return {}


@pytest.fixture
def small_matrix() -> dict[str, dict[str, float]]:
    """3x3 correlation matrix with known values."""
    return {
        "open_bugs": {
            "open_bugs": 1.0,
            "vulnerabilities": 0.72,
            "deployment_frequency": -0.55,
        },
        "vulnerabilities": {
            "open_bugs": 0.72,
            "vulnerabilities": 1.0,
            "deployment_frequency": -0.30,
        },
        "deployment_frequency": {
            "open_bugs": -0.55,
            "vulnerabilities": -0.30,
            "deployment_frequency": 1.0,
        },
    }


@pytest.fixture
def matrix_no_strong() -> dict[str, dict[str, float]]:
    """2x2 matrix with no correlation pair above |r| = 0.5."""
    return {
        "metric_a": {"metric_a": 1.0, "metric_b": 0.1},
        "metric_b": {"metric_a": 0.1, "metric_b": 1.0},
    }


@pytest.fixture
def full_summary(small_matrix: dict) -> dict:
    return _calculate_summary(small_matrix)


@pytest.fixture
def empty_summary(empty_matrix: dict) -> dict:
    return _calculate_summary(empty_matrix)


# ---------------------------------------------------------------------------
# TestLoadCorrelationMatrix
# ---------------------------------------------------------------------------


class TestLoadCorrelationMatrix:
    def test_returns_empty_dict_when_value_error(self, tmp_path: Path) -> None:
        with patch(
            "execution.dashboards.correlation_heatmap.compute_correlation_matrix",
            side_effect=ValueError("no features"),
        ):
            result = _load_correlation_matrix(feature_dir=tmp_path)

        assert result == {}

    def test_returns_empty_dict_when_os_error(self, tmp_path: Path) -> None:
        with patch(
            "execution.dashboards.correlation_heatmap.compute_correlation_matrix",
            side_effect=OSError("permission denied"),
        ):
            result = _load_correlation_matrix(feature_dir=tmp_path)

        assert result == {}

    def test_returns_matrix_when_compute_succeeds(self, tmp_path: Path, small_matrix: dict) -> None:
        with patch(
            "execution.dashboards.correlation_heatmap.compute_correlation_matrix",
            return_value=small_matrix,
        ):
            result = _load_correlation_matrix(feature_dir=tmp_path)

        assert result == small_matrix

    def test_returns_empty_dict_on_empty_result(self, tmp_path: Path) -> None:
        with patch(
            "execution.dashboards.correlation_heatmap.compute_correlation_matrix",
            return_value={},
        ):
            result = _load_correlation_matrix(feature_dir=tmp_path)

        assert result == {}


# ---------------------------------------------------------------------------
# TestCalculateSummary
# ---------------------------------------------------------------------------


class TestCalculateSummary:
    def test_empty_matrix_has_data_false(self, empty_matrix: dict) -> None:
        result = _calculate_summary(empty_matrix)
        assert result["has_data"] is False

    def test_empty_matrix_metric_count_zero(self, empty_matrix: dict) -> None:
        result = _calculate_summary(empty_matrix)
        assert result["metric_count"] == 0

    def test_empty_matrix_strong_correlations_empty(self, empty_matrix: dict) -> None:
        result = _calculate_summary(empty_matrix)
        assert result["strong_correlations"] == []

    def test_empty_matrix_matrix_empty(self, empty_matrix: dict) -> None:
        result = _calculate_summary(empty_matrix)
        assert result["matrix"] == {}

    def test_has_data_true_when_matrix_present(self, small_matrix: dict) -> None:
        result = _calculate_summary(small_matrix)
        assert result["has_data"] is True

    def test_metric_count_correct(self, small_matrix: dict) -> None:
        result = _calculate_summary(small_matrix)
        assert result["metric_count"] == 3

    def test_strong_correlations_excludes_self(self, small_matrix: dict) -> None:
        result = _calculate_summary(small_matrix)
        # Self-correlations (r=1.0) must not appear
        for metric_a, metric_b, _ in result["strong_correlations"]:
            assert metric_a != metric_b

    def test_strong_correlations_sorted_by_abs_desc(self, small_matrix: dict) -> None:
        result = _calculate_summary(small_matrix)
        corrs = result["strong_correlations"]
        abs_values = [abs(r) for _, _, r in corrs]
        assert abs_values == sorted(abs_values, reverse=True)

    def test_strong_correlations_threshold_is_0_5(self, small_matrix: dict) -> None:
        result = _calculate_summary(small_matrix)
        # open_bugs ↔ vulnerabilities: r=0.72 (|r|>=0.5 → included)
        # open_bugs ↔ deployment_frequency: r=-0.55 (|r|>=0.5 → included)
        # vulnerabilities ↔ deployment_frequency: r=-0.30 (|r|<0.5 → excluded)
        corr_pairs = {frozenset({a, b}) for a, b, _ in result["strong_correlations"]}
        assert frozenset({"open_bugs", "vulnerabilities"}) in corr_pairs
        assert frozenset({"open_bugs", "deployment_frequency"}) in corr_pairs
        assert frozenset({"vulnerabilities", "deployment_frequency"}) not in corr_pairs

    def test_no_strong_correlations_when_all_weak(self, matrix_no_strong: dict) -> None:
        result = _calculate_summary(matrix_no_strong)
        assert result["strong_correlations"] == []

    def test_strong_correlations_capped_at_5(self) -> None:
        """Ensure only top 5 pairs are returned even if more qualify."""
        big_matrix: dict[str, dict[str, float]] = {}
        metrics = [f"metric_{i}" for i in range(6)]
        for m_a in metrics:
            big_matrix[m_a] = {}
            for m_b in metrics:
                # All off-diagonal pairs have |r|=0.8
                big_matrix[m_a][m_b] = 1.0 if m_a == m_b else 0.8
        result = _calculate_summary(big_matrix)
        assert len(result["strong_correlations"]) <= 5

    def test_matrix_preserved_in_summary(self, small_matrix: dict) -> None:
        result = _calculate_summary(small_matrix)
        assert result["matrix"] == small_matrix


# ---------------------------------------------------------------------------
# TestBuildCorrelationHeatmapChart
# ---------------------------------------------------------------------------


class TestBuildCorrelationHeatmapChart:
    def test_empty_matrix_returns_empty_string(self, empty_matrix: dict) -> None:
        result = _build_correlation_heatmap_chart(empty_matrix)
        assert result == ""

    def test_small_matrix_returns_non_empty_html(self, small_matrix: dict) -> None:
        result = _build_correlation_heatmap_chart(small_matrix)
        assert isinstance(result, str)
        assert len(result) > 100

    def test_html_contains_plotly_div(self, small_matrix: dict) -> None:
        result = _build_correlation_heatmap_chart(small_matrix)
        assert "<div" in result

    def test_html_contains_metric_names(self, small_matrix: dict) -> None:
        result = _build_correlation_heatmap_chart(small_matrix)
        # Display labels are title-cased, underscores replaced by spaces
        assert "Open Bugs" in result or "open_bugs" in result

    def test_integer_values_coerced_to_float(self) -> None:
        matrix: dict[str, dict[str, float]] = {
            "a": {"a": 1, "b": 1},  # type: ignore[dict-item]
            "b": {"a": 1, "b": 1},  # type: ignore[dict-item]
        }
        # Should not raise TypeError
        result = _build_correlation_heatmap_chart(matrix)
        assert isinstance(result, str)

    def test_single_metric_matrix_returns_html(self) -> None:
        single: dict[str, dict[str, float]] = {"metric_x": {"metric_x": 1.0}}
        result = _build_correlation_heatmap_chart(single)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_2x2_matrix_returns_html(self, matrix_no_strong: dict) -> None:
        result = _build_correlation_heatmap_chart(matrix_no_strong)
        assert isinstance(result, str)
        assert len(result) > 100


# ---------------------------------------------------------------------------
# TestBuildContext
# ---------------------------------------------------------------------------


class TestBuildContext:
    def test_framework_css_present(self, empty_summary: dict) -> None:
        context = _build_context(empty_summary, "")
        assert "framework_css" in context
        assert context["framework_css"] != ""

    def test_framework_js_present(self, empty_summary: dict) -> None:
        context = _build_context(empty_summary, "")
        assert "framework_js" in context
        assert context["framework_js"] != ""

    def test_has_data_false_propagated(self, empty_summary: dict) -> None:
        context = _build_context(empty_summary, "")
        assert context["has_data"] is False

    def test_has_data_true_propagated(self, full_summary: dict) -> None:
        context = _build_context(full_summary, "")
        assert context["has_data"] is True

    def test_metric_count_in_context(self, full_summary: dict) -> None:
        context = _build_context(full_summary, "")
        assert context["metric_count"] == 3

    def test_strong_correlations_in_context(self, full_summary: dict) -> None:
        context = _build_context(full_summary, "")
        assert "strong_correlations" in context
        assert len(context["strong_correlations"]) >= 1

    def test_heatmap_html_forwarded(self, empty_summary: dict) -> None:
        context = _build_context(empty_summary, "<div>heatmap</div>")
        assert context["heatmap_html"] == "<div>heatmap</div>"

    def test_generated_at_present(self, empty_summary: dict) -> None:
        context = _build_context(empty_summary, "")
        assert "generated_at" in context
        assert len(context["generated_at"]) > 0

    def test_matrix_in_context(self, full_summary: dict, small_matrix: dict) -> None:
        context = _build_context(full_summary, "")
        assert context["matrix"] == small_matrix


# ---------------------------------------------------------------------------
# TestGenerateCorrelationHeatmap (integration — mocked I/O)
# ---------------------------------------------------------------------------


class TestGenerateCorrelationHeatmap:
    def test_returns_html_string_with_no_data(self) -> None:
        with patch(
            "execution.dashboards.correlation_heatmap._load_correlation_matrix",
            return_value={},
        ):
            html = generate_correlation_heatmap()

        assert isinstance(html, str)
        assert len(html) > 100

    def test_html_is_valid_document(self) -> None:
        with patch(
            "execution.dashboards.correlation_heatmap._load_correlation_matrix",
            return_value={},
        ):
            html = generate_correlation_heatmap()

        assert "<!DOCTYPE html>" in html or "<html" in html

    def test_html_contains_framework_css(self, small_matrix: dict) -> None:
        with patch(
            "execution.dashboards.correlation_heatmap._load_correlation_matrix",
            return_value=small_matrix,
        ):
            html = generate_correlation_heatmap()

        assert "<style" in html

    def test_html_contains_metric_name_when_data_present(self, small_matrix: dict) -> None:
        with patch(
            "execution.dashboards.correlation_heatmap._load_correlation_matrix",
            return_value=small_matrix,
        ):
            html = generate_correlation_heatmap()

        # Metric names appear title-cased in HTML
        assert "Open Bugs" in html or "open_bugs" in html

    def test_writes_file_when_output_dir_provided(self, tmp_path: Path) -> None:
        with patch(
            "execution.dashboards.correlation_heatmap._load_correlation_matrix",
            return_value={},
        ):
            generate_correlation_heatmap(output_dir=tmp_path)

        written = tmp_path / "correlation_heatmap.html"
        assert written.exists()
        assert written.stat().st_size > 100

    def test_no_file_written_when_no_output_dir(self, tmp_path: Path) -> None:
        with patch(
            "execution.dashboards.correlation_heatmap._load_correlation_matrix",
            return_value={},
        ):
            generate_correlation_heatmap(output_dir=None)

        assert not (tmp_path / "correlation_heatmap.html").exists()

    def test_no_data_message_in_html_when_empty(self) -> None:
        with patch(
            "execution.dashboards.correlation_heatmap._load_correlation_matrix",
            return_value={},
        ):
            html = generate_correlation_heatmap()

        assert "Not Yet Available" in html or "not" in html.lower()

    def test_heatmap_glossary_present(self, small_matrix: dict) -> None:
        with patch(
            "execution.dashboards.correlation_heatmap._load_correlation_matrix",
            return_value=small_matrix,
        ):
            html = generate_correlation_heatmap()

        assert "Glossary" in html or "Pearson" in html


# ---------------------------------------------------------------------------
# TestMain
# ---------------------------------------------------------------------------


class TestMain:
    def test_main_calls_generate(self, tmp_path: Path) -> None:
        fake_html = "<html><body>test</body></html>"
        with (
            patch(
                "execution.dashboards.correlation_heatmap.generate_correlation_heatmap",
                return_value=fake_html,
            ) as mock_gen,
            patch(
                "execution.dashboards.correlation_heatmap.OUTPUT_PATH",
                tmp_path / "correlation_heatmap.html",
            ),
        ):
            main()

        mock_gen.assert_called_once()

    def test_main_logs_when_output_file_exists(self, tmp_path: Path) -> None:
        output_path = tmp_path / "correlation_heatmap.html"
        output_path.write_text("<html></html>", encoding="utf-8")

        with (
            patch(
                "execution.dashboards.correlation_heatmap.generate_correlation_heatmap",
                return_value="<html></html>",
            ),
            patch(
                "execution.dashboards.correlation_heatmap.OUTPUT_PATH",
                output_path,
            ),
        ):
            main()  # Should not raise

    def test_main_logs_when_output_file_not_on_disk(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "not_written.html"

        with (
            patch(
                "execution.dashboards.correlation_heatmap.generate_correlation_heatmap",
                return_value="<html>content</html>",
            ),
            patch(
                "execution.dashboards.correlation_heatmap.OUTPUT_PATH",
                nonexistent,
            ),
        ):
            main()  # Takes the else branch — should not raise

    def test_main_raises_oserror_on_failure(self) -> None:
        with patch(
            "execution.dashboards.correlation_heatmap.generate_correlation_heatmap",
            side_effect=OSError("disk full"),
        ):
            with pytest.raises(OSError, match="disk full"):
                main()
