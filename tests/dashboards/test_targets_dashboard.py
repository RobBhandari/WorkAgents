"""
Tests for Target Dashboard Generator

Tests cover:
- Dashboard generation
- Baseline loading
- Current state querying
- Summary calculation
- Metric calculation (progress, status, burn rate)
- Context building
- Error handling
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from execution.dashboards.targets import (
    _build_context,
    _calculate_metrics,
    _calculate_summary,
    _load_baselines,
    _query_current_ado_bugs,
    _query_current_armorcode_vulns,
    _query_current_state,
    generate_targets_dashboard,
)


@pytest.fixture
def sample_security_baseline():
    """Sample security baseline data for testing"""
    return {
        "baseline_date": "2025-12-01",
        "target_date": "2026-06-30",
        "weeks_to_target": 30,
        "total_vulnerabilities": 100,
        "target_vulnerabilities": 30,
        "reduction_percentage": 70,
    }


@pytest.fixture
def sample_bugs_baseline():
    """Sample bugs baseline data for testing"""
    return {
        "baseline_date": "2025-12-01",
        "target_date": "2026-06-30",
        "weeks_to_target": 30,
        "open_count": 200,
        "target_count": 60,
        "reduction_percentage": 70,
    }


@pytest.fixture
def sample_security_history():
    """Sample security history data for testing"""
    return {
        "weeks": [
            {
                "week_number": 1,
                "week_date": "2026-01-05",
                "metrics": {
                    "current_total": 95,
                    "severity_breakdown": {"critical": 10, "high": 85, "medium": 30, "low": 15},
                },
            },
            {
                "week_number": 2,
                "week_date": "2026-02-01",
                "metrics": {
                    "current_total": 85,
                    "severity_breakdown": {"critical": 8, "high": 77, "medium": 25, "low": 12},
                },
            },
        ]
    }


@pytest.fixture
def sample_quality_history():
    """Sample quality history data for testing"""
    return {
        "weeks": [
            {
                "week_number": 1,
                "week_date": "2026-01-05",
                "projects": [
                    {"project_name": "API Gateway", "open_bugs_count": 75},
                    {"project_name": "Web App", "open_bugs_count": 50},
                ],
            },
            {
                "week_number": 2,
                "week_date": "2026-02-01",
                "projects": [
                    {"project_name": "API Gateway", "open_bugs_count": 70},
                    {"project_name": "Web App", "open_bugs_count": 45},
                ],
            },
        ]
    }


# Test: _load_baselines
def test_load_baselines_success(sample_security_baseline, sample_bugs_baseline):
    """Test successful loading of baseline files"""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "builtins.open",
            side_effect=[
                mock_open(read_data=json.dumps(sample_security_baseline)).return_value,
                mock_open(read_data=json.dumps(sample_bugs_baseline)).return_value,
            ],
        ),
    ):
        result = _load_baselines()

        assert result["security"]["total_vulnerabilities"] == 100
        assert result["security"]["target_vulnerabilities"] == 30
        assert result["bugs"]["open_count"] == 200
        assert result["bugs"]["target_count"] == 60


def test_load_baselines_missing_security_file():
    """Test FileNotFoundError when security baseline is missing"""
    with patch.object(Path, "exists", side_effect=[False, True]):
        with pytest.raises(FileNotFoundError, match="Security baseline not found"):
            _load_baselines()


def test_load_baselines_missing_bugs_file():
    """Test FileNotFoundError when bugs baseline is missing"""
    with patch.object(Path, "exists", side_effect=[True, False]):
        with pytest.raises(FileNotFoundError, match="Bugs baseline not found"):
            _load_baselines()


# Test: _query_current_armorcode_vulns
def test_query_current_armorcode_vulns_success(sample_security_history):
    """Test successful querying of current vulnerabilities"""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=json.dumps(sample_security_history))),
    ):
        result = _query_current_armorcode_vulns()

        # Should return latest week's total
        assert result == 85


def test_query_current_armorcode_vulns_missing_file():
    """Test FileNotFoundError when security history is missing"""
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(FileNotFoundError, match="Security history not found"):
            _query_current_armorcode_vulns()


def test_query_current_armorcode_vulns_no_weeks():
    """Test ValueError when no weeks data found"""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=json.dumps({"weeks": []}))),
    ):
        with pytest.raises(ValueError, match="No weeks data found"):
            _query_current_armorcode_vulns()


# Test: _query_current_ado_bugs
def test_query_current_ado_bugs_success(sample_quality_history):
    """Test successful querying of current bugs"""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=json.dumps(sample_quality_history))),
    ):
        result = _query_current_ado_bugs()

        # Should return latest week's total (70 + 45 = 115)
        assert result == 115


def test_query_current_ado_bugs_missing_file():
    """Test FileNotFoundError when quality history is missing"""
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(FileNotFoundError, match="Quality history not found"):
            _query_current_ado_bugs()


def test_query_current_ado_bugs_no_weeks():
    """Test ValueError when no weeks data found"""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=json.dumps({"weeks": []}))),
    ):
        with pytest.raises(ValueError, match="No weeks data found"):
            _query_current_ado_bugs()


# Test: _calculate_metrics
def test_calculate_metrics_on_track():
    """Test metric calculation when on track"""
    from datetime import datetime, timedelta

    with patch("execution.dashboards.targets.datetime") as mock_datetime:
        # Mock current date to be 15 weeks (105 days) into the target period
        current_date = datetime(2026, 3, 15)
        target_date = datetime(2026, 6, 30)
        mock_datetime.now.return_value = current_date
        mock_datetime.strptime.return_value = target_date

        result = _calculate_metrics(
            baseline_count=100, target_count=30, current_count=50, weeks_to_target=30  # 70% reduction  # Halfway there
        )

        assert result["baseline_count"] == 100
        assert result["target_count"] == 30
        assert result["current_count"] == 50
        assert result["progress_from_baseline"] == 50  # 100 - 50
        assert result["progress_pct"] == 71.4  # 50/70 * 100
        assert result["status"] == "ON TRACK"
        assert result["status_color"] == "#10b981"


def test_calculate_metrics_behind_schedule():
    """Test metric calculation when behind schedule"""
    from datetime import datetime

    with patch("execution.dashboards.targets.datetime") as mock_datetime:
        # Mock current date
        current_date = datetime(2026, 3, 15)
        target_date = datetime(2026, 6, 30)
        mock_datetime.now.return_value = current_date
        mock_datetime.strptime.return_value = target_date

        result = _calculate_metrics(
            baseline_count=100, target_count=30, current_count=70, weeks_to_target=30  # Only 30% reduction
        )

        assert result["progress_from_baseline"] == 30  # 100 - 70
        assert result["progress_pct"] == 42.9  # 30/70 * 100
        assert result["status"] == "BEHIND SCHEDULE"
        assert result["status_color"] == "#f59e0b"


def test_calculate_metrics_at_risk():
    """Test metric calculation when at risk"""
    from datetime import datetime

    with patch("execution.dashboards.targets.datetime") as mock_datetime:
        # Mock current date
        current_date = datetime(2026, 3, 15)
        target_date = datetime(2026, 6, 30)
        mock_datetime.now.return_value = current_date
        mock_datetime.strptime.return_value = target_date

        result = _calculate_metrics(
            baseline_count=100, target_count=30, current_count=85, weeks_to_target=30  # Only 15% reduction
        )

        assert result["progress_from_baseline"] == 15  # 100 - 85
        assert result["progress_pct"] == 21.4  # 15/70 * 100
        assert result["status"] == "AT RISK"
        assert result["status_color"] == "#ef4444"


def test_calculate_metrics_target_met():
    """Test metric calculation when target is met"""
    from datetime import datetime

    with patch("execution.dashboards.targets.datetime") as mock_datetime:
        # Mock current date
        current_date = datetime(2026, 3, 15)
        target_date = datetime(2026, 6, 30)
        mock_datetime.now.return_value = current_date
        mock_datetime.strptime.return_value = target_date

        result = _calculate_metrics(
            baseline_count=100, target_count=30, current_count=25, weeks_to_target=30  # Exceeded target!
        )

        assert result["progress_from_baseline"] == 75  # 100 - 25
        assert result["progress_pct"] == 107.1  # 75/70 * 100
        assert result["status"] == "TARGET MET"
        assert result["status_color"] == "#10b981"


def test_calculate_metrics_negative_progress():
    """Test metric calculation when count increased from baseline"""
    from datetime import datetime

    with patch("execution.dashboards.targets.datetime") as mock_datetime:
        # Mock current date
        current_date = datetime(2026, 3, 15)
        target_date = datetime(2026, 6, 30)
        mock_datetime.now.return_value = current_date
        mock_datetime.strptime.return_value = target_date

        result = _calculate_metrics(
            baseline_count=100, target_count=30, current_count=120, weeks_to_target=30  # Count increased!
        )

        assert result["progress_from_baseline"] == -20  # 100 - 120
        assert result["progress_pct"] == -28.6  # -20/70 * 100
        assert result["status"] == "AT RISK"


# Test: _calculate_summary
def test_calculate_summary_success():
    """Test successful calculation of summary metrics"""
    from datetime import datetime

    baselines = {
        "security": {"total_vulnerabilities": 100, "target_vulnerabilities": 30, "weeks_to_target": 30},
        "bugs": {"open_count": 200, "target_count": 60, "weeks_to_target": 30},
    }

    current_state = {"security": 50, "bugs": 100}

    with patch("execution.dashboards.targets.datetime") as mock_datetime:
        # Mock current date
        current_date = datetime(2026, 3, 15)
        target_date = datetime(2026, 6, 30)
        mock_datetime.now.return_value = current_date
        mock_datetime.strptime.return_value = target_date

        result = _calculate_summary(baselines, current_state)

        assert "security" in result
        assert "bugs" in result
        assert result["security"]["current_count"] == 50
        assert result["bugs"]["current_count"] == 100


# Test: _build_context
def test_build_context_success():
    """Test successful context building for template"""
    summary_stats = {
        "security": {
            "baseline_count": 100,
            "current_count": 50,
            "target_count": 30,
            "progress_pct": 71.4,
            "status": "ON TRACK",
            "status_color": "#10b981",
            "remaining_to_target": 20,
            "days_remaining": 107,
            "weeks_remaining": 15.3,
            "required_weekly_burn": 1.31,
            "progress_from_baseline": 50,
        },
        "bugs": {
            "baseline_count": 200,
            "current_count": 100,
            "target_count": 60,
            "progress_pct": 71.4,
            "status": "ON TRACK",
            "status_color": "#10b981",
            "remaining_to_target": 40,
            "days_remaining": 107,
            "weeks_remaining": 15.3,
            "required_weekly_burn": 2.61,
            "progress_from_baseline": 100,
        },
    }

    result = _build_context(summary_stats)

    assert "framework_css" in result
    assert "framework_js" in result
    assert "generation_date" in result
    assert "security" in result
    assert "bugs" in result
    assert result["security"]["current_count"] == 50
    assert result["bugs"]["current_count"] == 100
    assert result["show_glossary"] is False


# Test: generate_targets_dashboard (integration test)
@patch("execution.dashboards.targets._load_baselines")
@patch("execution.dashboards.targets._query_current_state")
@patch("execution.dashboards.targets._calculate_summary")
@patch("execution.dashboards.targets._build_context")
@patch("execution.dashboards.targets.render_dashboard")
def test_generate_targets_dashboard_success(
    mock_render, mock_build_context, mock_calculate_summary, mock_query_state, mock_load_baselines
):
    """Test successful dashboard generation (integration)"""
    # Setup mocks
    mock_load_baselines.return_value = {
        "security": {"total_vulnerabilities": 100, "target_vulnerabilities": 30, "weeks_to_target": 30},
        "bugs": {"open_count": 200, "target_count": 60, "weeks_to_target": 30},
    }

    mock_query_state.return_value = {"security": 50, "bugs": 100}

    mock_calculate_summary.return_value = {
        "security": {"current_count": 50, "progress_pct": 71.4, "status": "ON TRACK"},
        "bugs": {"current_count": 100, "progress_pct": 71.4, "status": "ON TRACK"},
    }

    mock_build_context.return_value = {
        "framework_css": "<style></style>",
        "framework_js": "<script></script>",
        "generation_date": "2026-02-08 12:00:00",
        "security": {"current_count": 50},
        "bugs": {"current_count": 100},
    }

    mock_render.return_value = "<html>Mock Dashboard</html>"

    # Execute
    html = generate_targets_dashboard()

    # Verify
    assert html == "<html>Mock Dashboard</html>"
    mock_load_baselines.assert_called_once()
    mock_query_state.assert_called_once()
    mock_calculate_summary.assert_called_once()
    mock_build_context.assert_called_once()
    mock_render.assert_called_once()


@patch("execution.dashboards.targets._load_baselines")
def test_generate_targets_dashboard_missing_baselines(mock_load_baselines):
    """Test dashboard generation fails when baselines are missing"""
    mock_load_baselines.side_effect = FileNotFoundError("Security baseline not found")

    with pytest.raises(FileNotFoundError, match="Security baseline not found"):
        generate_targets_dashboard()


@patch("execution.dashboards.targets._load_baselines")
@patch("execution.dashboards.targets._query_current_state")
def test_generate_targets_dashboard_missing_history(mock_query_state, mock_load_baselines):
    """Test dashboard generation fails when history files are missing"""
    mock_load_baselines.return_value = {
        "security": {"total_vulnerabilities": 100},
        "bugs": {"open_count": 200},
    }

    mock_query_state.side_effect = FileNotFoundError("Security history not found")

    with pytest.raises(FileNotFoundError, match="Security history not found"):
        generate_targets_dashboard()


# Test: _query_current_state
@patch("execution.dashboards.targets._query_current_armorcode_vulns")
@patch("execution.dashboards.targets._query_current_ado_bugs")
def test_query_current_state_success(mock_query_bugs, mock_query_vulns):
    """Test successful querying of current state"""
    mock_query_vulns.return_value = 85
    mock_query_bugs.return_value = 115

    result = _query_current_state()

    assert result["security"] == 85
    assert result["bugs"] == 115
    mock_query_vulns.assert_called_once()
    mock_query_bugs.assert_called_once()
