"""
Tests for execution/intelligence/feature_engineering.py

Covers:
- VALID_METRICS constant structure and contents
- extract_features() with mocked file I/O
- save_features() with mocked PathValidator and Parquet write
- load_features() with mocked glob and read_parquet
- Invalid metric raises ValueError
- Missing history file raises FileNotFoundError
- Empty history file returns empty DataFrame
- Quality, security, flow, deployment, ownership row extraction
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from execution.intelligence.feature_engineering import (
    VALID_METRICS,
    _extract_deployment_row,
    _extract_flow_row,
    _extract_ownership_row,
    _extract_quality_row,
    _extract_security_row,
    extract_features,
    load_features,
    save_features,
)

# ---------------------------------------------------------------------------
# Fixtures — synthetic history JSON blobs (never touch real files)
# ---------------------------------------------------------------------------


@pytest.fixture
def quality_history_json() -> str:
    """Minimal quality history JSON with 2 weeks × 2 projects."""
    return json.dumps(
        {
            "weeks": [
                {
                    "week_date": "2025-10-06",
                    "projects": [
                        {
                            "project_key": "Product_A",
                            "open_bugs_count": 300,
                            "total_bugs_analyzed": 50,
                            "bug_age_distribution": {"median_age_days": 14.0},
                            "mttr": {"mttr_days": 7.5},
                        },
                        {
                            "project_key": "Product_B",
                            "open_bugs_count": 120,
                            "total_bugs_analyzed": 20,
                            "bug_age_distribution": {"median_age_days": 9.0},
                            "mttr": {"mttr_days": 4.0},
                        },
                    ],
                },
                {
                    "week_date": "2025-10-13",
                    "projects": [
                        {
                            "project_key": "Product_A",
                            "open_bugs_count": 295,
                            "total_bugs_analyzed": 55,
                            "bug_age_distribution": {"median_age_days": 13.5},
                            "mttr": {"mttr_days": 7.0},
                        },
                    ],
                },
            ]
        }
    )


@pytest.fixture
def security_history_json() -> str:
    """Minimal security history JSON."""
    return json.dumps(
        {
            "weeks": [
                {
                    "week_date": "2025-10-06",
                    "metrics": {
                        "current_total": 500,
                        "severity_breakdown": {"critical": 10, "high": 40},
                        "product_breakdown": {
                            "123": {"total": 200, "critical": 5, "high": 20},
                            "456": {"total": 300, "critical": 5, "high": 20},
                        },
                    },
                }
            ]
        }
    )


@pytest.fixture
def flow_history_json() -> str:
    """Minimal flow history JSON."""
    return json.dumps(
        {
            "weeks": [
                {
                    "week_date": "2025-10-06",
                    "projects": [
                        {
                            "project_key": "Product_A",
                            "work_type_metrics": {
                                "Bug": {
                                    "lead_time": {"p85": 12.5},
                                    "throughput": {"per_week": 5.0},
                                    "wip": 8,
                                }
                            },
                        }
                    ],
                }
            ]
        }
    )


@pytest.fixture
def deployment_history_json() -> str:
    """Minimal deployment history JSON."""
    return json.dumps(
        {
            "weeks": [
                {
                    "week_date": "2025-10-06",
                    "projects": [
                        {
                            "project_key": "Product_A",
                            "build_success_rate": {"success_rate_pct": 95.0},
                            "deployment_frequency": {"deployments_per_week": 3.5},
                        }
                    ],
                }
            ]
        }
    )


@pytest.fixture
def ownership_history_json() -> str:
    """Minimal ownership history JSON."""
    return json.dumps(
        {
            "weeks": [
                {
                    "week_date": "2025-10-06",
                    "projects": [
                        {
                            "project_key": "Product_A",
                            "unassigned": {
                                "total_items": 100,
                                "unassigned_count": 15,
                                "unassigned_pct": 15.0,
                            },
                        }
                    ],
                }
            ]
        }
    )


@pytest.fixture
def empty_history_json() -> str:
    """History file with no weeks — should produce empty DataFrame."""
    return json.dumps({"weeks": []})


@pytest.fixture
def synthetic_df() -> pd.DataFrame:
    """A small DataFrame for save/load testing."""
    return pd.DataFrame(
        {
            "week_date": pd.to_datetime(["2025-10-06", "2025-10-13"]),
            "project": ["Product_A", "Product_A"],
            "open_bugs": [300, 295],
        }
    )


# ---------------------------------------------------------------------------
# TestValidMetrics
# ---------------------------------------------------------------------------


class TestValidMetrics:
    def test_is_frozenset(self) -> None:
        assert isinstance(VALID_METRICS, frozenset)

    def test_contains_quality(self) -> None:
        assert "quality" in VALID_METRICS

    def test_contains_security(self) -> None:
        assert "security" in VALID_METRICS

    def test_contains_flow(self) -> None:
        assert "flow" in VALID_METRICS

    def test_contains_deployment(self) -> None:
        assert "deployment" in VALID_METRICS

    def test_contains_ownership(self) -> None:
        assert "ownership" in VALID_METRICS

    def test_contains_risk(self) -> None:
        assert "risk" in VALID_METRICS

    def test_does_not_contain_invalid(self) -> None:
        assert "bugs" not in VALID_METRICS
        assert "unknown_metric" not in VALID_METRICS


# ---------------------------------------------------------------------------
# TestExtractFeatures — mocked Path I/O
# ---------------------------------------------------------------------------


class TestExtractFeaturesInvalidMetric:
    def test_invalid_metric_raises_value_error(self, tmp_path: Path) -> None:
        fake_path = tmp_path / "fake.json"
        fake_path.write_text('{"weeks": []}')
        with pytest.raises(ValueError, match="Invalid metric"):
            extract_features("nonexistent_metric", fake_path)

    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        missing = tmp_path / "no_such_file.json"
        with pytest.raises(FileNotFoundError, match="History file not found"):
            extract_features("quality", missing)

    def test_invalid_json_raises_value_error(self, tmp_path: Path) -> None:
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("NOT_JSON{{{")
        with pytest.raises(ValueError, match="invalid JSON"):
            extract_features("quality", bad_json)

    def test_malformed_structure_raises_value_error(self, tmp_path: Path) -> None:
        bad_structure = tmp_path / "bad_struct.json"
        bad_structure.write_text('{"weeks": "not_a_list"}')
        with pytest.raises(ValueError, match="unexpected structure"):
            extract_features("quality", bad_structure)


class TestExtractFeaturesEmptyHistory:
    def test_empty_history_returns_empty_dataframe(self, tmp_path: Path, empty_history_json: str) -> None:
        history_file = tmp_path / "quality_history.json"
        history_file.write_text(empty_history_json)
        df = extract_features("quality", history_file)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0


class TestExtractFeaturesQuality:
    def test_returns_dataframe(self, tmp_path: Path, quality_history_json: str) -> None:
        history_file = tmp_path / "quality_history.json"
        history_file.write_text(quality_history_json)
        df = extract_features("quality", history_file)
        assert isinstance(df, pd.DataFrame)

    def test_contains_required_columns(self, tmp_path: Path, quality_history_json: str) -> None:
        history_file = tmp_path / "quality_history.json"
        history_file.write_text(quality_history_json)
        df = extract_features("quality", history_file)
        assert "week_date" in df.columns
        assert "project" in df.columns
        assert "open_bugs" in df.columns

    def test_correct_row_count(self, tmp_path: Path, quality_history_json: str) -> None:
        history_file = tmp_path / "quality_history.json"
        history_file.write_text(quality_history_json)
        df = extract_features("quality", history_file)
        # 2 projects in week 1 + 1 project in week 2 = 3 rows
        assert len(df) == 3

    def test_sorted_by_week_date(self, tmp_path: Path, quality_history_json: str) -> None:
        history_file = tmp_path / "quality_history.json"
        history_file.write_text(quality_history_json)
        df = extract_features("quality", history_file)
        assert df["week_date"].is_monotonic_increasing

    def test_product_names_preserved(self, tmp_path: Path, quality_history_json: str) -> None:
        history_file = tmp_path / "quality_history.json"
        history_file.write_text(quality_history_json)
        df = extract_features("quality", history_file)
        assert "Product_A" in df["project"].values


class TestExtractFeaturesSecurity:
    def test_security_returns_portfolio_and_product_rows(self, tmp_path: Path, security_history_json: str) -> None:
        history_file = tmp_path / "security_history.json"
        history_file.write_text(security_history_json)
        df = extract_features("security", history_file)
        assert "_portfolio" in df["project"].values
        # 2 product IDs + 1 portfolio row = 3 rows
        assert len(df) == 3

    def test_security_has_vulnerability_columns(self, tmp_path: Path, security_history_json: str) -> None:
        history_file = tmp_path / "security_history.json"
        history_file.write_text(security_history_json)
        df = extract_features("security", history_file)
        assert "total_vulnerabilities" in df.columns
        assert "critical" in df.columns
        assert "high" in df.columns


class TestExtractFeaturesFlow:
    def test_flow_has_throughput_and_lead_time(self, tmp_path: Path, flow_history_json: str) -> None:
        history_file = tmp_path / "flow_history.json"
        history_file.write_text(flow_history_json)
        df = extract_features("flow", history_file)
        assert "throughput" in df.columns
        assert "lead_time_p85" in df.columns

    def test_flow_values_correct(self, tmp_path: Path, flow_history_json: str) -> None:
        history_file = tmp_path / "flow_history.json"
        history_file.write_text(flow_history_json)
        df = extract_features("flow", history_file)
        row = df.iloc[0]
        assert row["throughput"] == 5.0
        assert row["lead_time_p85"] == 12.5


class TestExtractFeaturesDeployment:
    def test_deployment_has_success_rate(self, tmp_path: Path, deployment_history_json: str) -> None:
        history_file = tmp_path / "deployment_history.json"
        history_file.write_text(deployment_history_json)
        df = extract_features("deployment", history_file)
        assert "build_success_rate" in df.columns
        assert "deploy_frequency" in df.columns

    def test_deployment_values_correct(self, tmp_path: Path, deployment_history_json: str) -> None:
        history_file = tmp_path / "deployment_history.json"
        history_file.write_text(deployment_history_json)
        df = extract_features("deployment", history_file)
        assert df.iloc[0]["build_success_rate"] == 95.0


class TestExtractFeaturesOwnership:
    def test_ownership_has_unassigned_columns(self, tmp_path: Path, ownership_history_json: str) -> None:
        history_file = tmp_path / "ownership_history.json"
        history_file.write_text(ownership_history_json)
        df = extract_features("ownership", history_file)
        assert "unassigned_pct" in df.columns
        assert "unassigned_count" in df.columns

    def test_ownership_values_correct(self, tmp_path: Path, ownership_history_json: str) -> None:
        history_file = tmp_path / "ownership_history.json"
        history_file.write_text(ownership_history_json)
        df = extract_features("ownership", history_file)
        assert df.iloc[0]["unassigned_pct"] == 15.0


# ---------------------------------------------------------------------------
# TestSaveFeatures — mocked PathValidator and parquet write
# ---------------------------------------------------------------------------


class TestSaveFeatures:
    def test_invalid_metric_raises_value_error(self, tmp_path: Path, synthetic_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="Invalid metric"):
            save_features(synthetic_df, "invalid_metric", base_dir=tmp_path)

    def test_path_validator_is_called(self, tmp_path: Path, synthetic_df: pd.DataFrame) -> None:
        with (
            patch("execution.intelligence.feature_engineering.PathValidator.validate_safe_path") as mock_validate,
            patch("execution.intelligence.feature_engineering.pq.write_table") as mock_write,
        ):
            # Return a valid path string so the code can continue
            mock_validate.return_value = str(tmp_path / "quality_features_2026-01-01.parquet")
            mock_write.return_value = None

            save_features(synthetic_df, "quality", base_dir=tmp_path)

            assert mock_validate.called, "PathValidator.validate_safe_path must be called"

    def test_parquet_write_is_attempted(self, tmp_path: Path, synthetic_df: pd.DataFrame) -> None:
        with (
            patch("execution.intelligence.feature_engineering.PathValidator.validate_safe_path") as mock_validate,
            patch("execution.intelligence.feature_engineering.pq.write_table") as mock_write,
        ):
            mock_validate.return_value = str(tmp_path / "quality_features_2026-01-01.parquet")
            mock_write.return_value = None

            save_features(synthetic_df, "quality", base_dir=tmp_path)

            assert mock_write.called, "pq.write_table must be called to persist data"

    def test_returns_path_object(self, tmp_path: Path, synthetic_df: pd.DataFrame) -> None:
        with (
            patch("execution.intelligence.feature_engineering.PathValidator.validate_safe_path") as mock_validate,
            patch("execution.intelligence.feature_engineering.pq.write_table") as mock_write,
        ):
            expected_path = str(tmp_path / "quality_features_2026-01-01.parquet")
            mock_validate.return_value = expected_path
            mock_write.return_value = None

            result = save_features(synthetic_df, "quality", base_dir=tmp_path)

            assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# TestLoadFeatures — mocked glob and read_parquet
# ---------------------------------------------------------------------------


class TestLoadFeatures:
    def test_invalid_metric_raises_value_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Invalid metric"):
            load_features("invalid_metric", base_dir=tmp_path)

    def test_no_parquet_files_raises_value_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="No feature Parquet found"):
            load_features("quality", base_dir=tmp_path)

    def test_loads_latest_file_when_multiple_exist(self, tmp_path: Path, synthetic_df: pd.DataFrame) -> None:
        """Lexicographically latest file should be selected."""
        with patch("execution.intelligence.feature_engineering.pd.read_parquet") as mock_read:
            mock_read.return_value = synthetic_df

            # Create two fake parquet files so glob finds them
            older = tmp_path / "quality_features_2025-01-01.parquet"
            newer = tmp_path / "quality_features_2026-01-01.parquet"
            older.touch()
            newer.touch()

            result = load_features("quality", base_dir=tmp_path)

            # Should have called read_parquet with the newer file
            call_args = mock_read.call_args[0][0]
            assert str(call_args).endswith("2026-01-01.parquet")
            assert isinstance(result, pd.DataFrame)

    def test_project_filter_applied(self, tmp_path: Path) -> None:
        df = pd.DataFrame(
            {
                "week_date": pd.to_datetime(["2025-10-06", "2025-10-06"]),
                "project": ["Product_A", "Product_B"],
                "open_bugs": [300, 120],
            }
        )
        with patch("execution.intelligence.feature_engineering.pd.read_parquet") as mock_read:
            mock_read.return_value = df
            parquet_file = tmp_path / "quality_features_2026-01-01.parquet"
            parquet_file.touch()

            result = load_features("quality", project="Product_A", base_dir=tmp_path)

            assert len(result) == 1
            assert result.iloc[0]["project"] == "Product_A"

    def test_returns_all_projects_when_no_filter(self, tmp_path: Path) -> None:
        df = pd.DataFrame(
            {
                "week_date": pd.to_datetime(["2025-10-06", "2025-10-06"]),
                "project": ["Product_A", "Product_B"],
                "open_bugs": [300, 120],
            }
        )
        with patch("execution.intelligence.feature_engineering.pd.read_parquet") as mock_read:
            mock_read.return_value = df
            parquet_file = tmp_path / "quality_features_2026-01-01.parquet"
            parquet_file.touch()

            result = load_features("quality", base_dir=tmp_path)

            assert len(result) == 2


# ---------------------------------------------------------------------------
# TestRowExtractors (unit tests for private helpers)
# ---------------------------------------------------------------------------


class TestExtractQualityRow:
    def test_extracts_open_bugs(self) -> None:
        project = {"project_key": "Product_A", "open_bugs_count": 300}
        row = _extract_quality_row("2025-10-06", project)
        assert row["open_bugs"] == 300

    def test_extracts_project_key(self) -> None:
        project = {"project_key": "Product_A"}
        row = _extract_quality_row("2025-10-06", project)
        assert row["project"] == "Product_A"

    def test_missing_fields_return_none(self) -> None:
        row = _extract_quality_row("2025-10-06", {})
        assert row["open_bugs"] is None
        assert row["project"] == ""


class TestExtractSecurityRow:
    def test_extracts_portfolio_row(self) -> None:
        metrics = {
            "current_total": 500,
            "severity_breakdown": {"critical": 10, "high": 40},
            "product_breakdown": {},
        }
        rows = _extract_security_row("2025-10-06", metrics)
        portfolio = next(r for r in rows if r["project"] == "_portfolio")
        assert portfolio["total_vulnerabilities"] == 500
        assert portfolio["critical"] == 10

    def test_extracts_per_product_rows(self) -> None:
        metrics = {
            "current_total": 500,
            "severity_breakdown": {"critical": 10, "high": 40},
            "product_breakdown": {
                "123": {"total": 200, "critical": 5, "high": 15},
            },
        }
        rows = _extract_security_row("2025-10-06", metrics)
        product_row = next(r for r in rows if r["project"] == "123")
        assert product_row["total_vulnerabilities"] == 200


class TestExtractFlowRow:
    def test_extracts_throughput(self) -> None:
        project = {
            "project_key": "Product_A",
            "work_type_metrics": {"Bug": {"throughput": {"per_week": 5.0}, "lead_time": {}, "wip": 3}},
        }
        row = _extract_flow_row("2025-10-06", project)
        assert row["throughput"] == 5.0

    def test_missing_metrics_return_none(self) -> None:
        row = _extract_flow_row("2025-10-06", {"project_key": "Product_A"})
        assert row["throughput"] is None
        assert row["lead_time_p85"] is None


class TestExtractOwnershipRow:
    def test_extracts_unassigned_pct(self) -> None:
        project = {
            "project_key": "Product_A",
            "unassigned": {"total_items": 100, "unassigned_count": 15, "unassigned_pct": 15.0},
        }
        row = _extract_ownership_row("2025-10-06", project)
        assert row["unassigned_pct"] == 15.0
        assert row["unassigned_count"] == 15

    def test_missing_unassigned_defaults_to_zero(self) -> None:
        row = _extract_ownership_row("2025-10-06", {"project_key": "Product_A"})
        assert row["unassigned_count"] == 0
        assert row["total_items"] == 0
