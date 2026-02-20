"""
Tests for Target Dashboard Generator

Tests cover:
- Dashboard generation (async)
- Baseline loading
- Current state querying from APIs (async)
- Summary calculation
- Metric calculation (progress, status, burn rate)
- Context building
- Error handling
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

import pytest

from execution.dashboards.targets import (
    _build_context,
    _calculate_metrics,
    _calculate_summary,
    _load_baselines,
    _load_discovery_data,
    _query_bugs_for_project,
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
        "products": ["Product A", "Product B"],
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
def sample_discovery_data():
    """Sample discovery data for testing"""
    return {
        "discovered_at": "2026-02-01T15:54:50.551684",
        "project_count": 2,
        "projects": [
            {
                "project_key": "Project_A",
                "project_name": "Project A",
                "organization": "https://dev.azure.com/test-org",
            },
            {
                "project_key": "Project_B",
                "project_name": "Project B",
                "organization": "https://dev.azure.com/test-org",
                "ado_project_name": "Project B ADO",
                "area_path_filter": "EXCLUDE:Project B\\Archive",
            },
        ],
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


# Test: _load_discovery_data
def test_load_discovery_data_success(sample_discovery_data):
    """Test successful loading of discovery data"""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=json.dumps(sample_discovery_data))),
    ):
        result = _load_discovery_data()

        assert result["project_count"] == 2
        assert len(result["projects"]) == 2
        assert result["projects"][0]["project_name"] == "Project A"


def test_load_discovery_data_missing_file():
    """Test FileNotFoundError when discovery file is missing"""
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(FileNotFoundError, match="Discovery file not found"):
            _load_discovery_data()


# Test: _query_current_armorcode_vulns
@pytest.mark.asyncio
async def test_query_current_armorcode_vulns_success():
    """Test successful querying of current vulnerabilities using AQL count endpoint (2 calls)"""
    mock_loader = Mock()
    # Critical: 1 from product A, High: 2 from product A → total 3
    mock_loader.count_by_severity_aql.side_effect = [
        {"product_id_1": 1},  # Critical counts
        {"product_id_1": 2},  # High counts
    ]

    with (
        patch("execution.dashboards.targets.ArmorCodeVulnerabilityLoader", return_value=mock_loader),
        patch("execution.dashboards.targets.get_config") as mock_config,
    ):
        mock_config.return_value.get_optional_env.return_value = "test/hierarchy"
        result = await _query_current_armorcode_vulns()

        # Should return sum of critical + high (3)
        assert result == 3
        assert mock_loader.count_by_severity_aql.call_count == 2
        mock_loader.count_by_severity_aql.assert_any_call("Critical", "test/hierarchy")
        mock_loader.count_by_severity_aql.assert_any_call("High", "test/hierarchy")


# Test: _query_current_ado_bugs
@pytest.mark.asyncio
async def test_query_current_ado_bugs_success(sample_discovery_data):
    """Test successful querying of current bugs from ADO API"""
    with (
        patch("execution.dashboards.targets._load_discovery_data", return_value=sample_discovery_data),
        patch("execution.dashboards.targets.get_ado_rest_client") as mock_get_client,
        patch("execution.dashboards.targets._query_bugs_for_project", new_callable=AsyncMock) as mock_query_bugs,
    ):
        mock_query_bugs.side_effect = [50, 65]  # Two projects return 50 and 65 bugs

        result = await _query_current_ado_bugs()

        # Should return sum of both projects (115)
        assert result == 115
        assert mock_query_bugs.call_count == 2


@pytest.mark.asyncio
async def test_query_current_ado_bugs_with_errors(sample_discovery_data):
    """Test querying bugs handles project errors gracefully"""
    with (
        patch("execution.dashboards.targets._load_discovery_data", return_value=sample_discovery_data),
        patch("execution.dashboards.targets.get_ado_rest_client"),
        patch("execution.dashboards.targets._query_bugs_for_project", new_callable=AsyncMock) as mock_query_bugs,
    ):
        # First project succeeds, second fails
        mock_query_bugs.side_effect = [50, Exception("API error")]

        result = await _query_current_ado_bugs()

        # Should return only the successful project's count
        assert result == 50


@pytest.mark.asyncio
async def test_query_current_ado_bugs_no_projects():
    """Test querying bugs returns 0 when no projects found"""
    with patch("execution.dashboards.targets._load_discovery_data", return_value={"projects": []}):
        result = await _query_current_ado_bugs()
        assert result == 0


# Test: _query_bugs_for_project
@pytest.mark.asyncio
async def test_query_bugs_for_project_success():
    """Test successful bug query for a single project"""
    project = {"project_name": "Test Project", "ado_project_name": "Test Project ADO"}

    mock_rest_client = AsyncMock()

    # Mock WIQL response
    mock_work_item_1 = Mock()
    mock_work_item_1.id = 1001
    mock_work_item_2 = Mock()
    mock_work_item_2.id = 1002

    mock_wiql_result = Mock()
    mock_wiql_result.work_items = [mock_work_item_1, mock_work_item_2]

    mock_rest_client.query_by_wiql.return_value = {}

    # Mock bug details
    mock_bugs = [{"System.Id": 1001, "System.Tags": ""}, {"System.Id": 1002, "System.Tags": ""}]

    with (
        patch(
            "execution.dashboards.targets.WorkItemTransformer.transform_wiql_response", return_value=mock_wiql_result
        ),
        patch(
            "execution.utils.ado_batch_utils.batch_fetch_work_items_rest", new_callable=AsyncMock
        ) as mock_batch_fetch,
        patch("execution.dashboards.targets.WorkItemTransformer.transform_work_items_response", return_value=mock_bugs),
        patch("execution.dashboards.targets.filter_security_bugs", return_value=(mock_bugs, 0)),
    ):
        mock_batch_fetch.return_value = (mock_bugs, [])

        result = await _query_bugs_for_project(mock_rest_client, project)

        assert result == 2
        mock_rest_client.query_by_wiql.assert_called_once()


@pytest.mark.asyncio
async def test_query_bugs_for_project_filters_security_bugs():
    """Test bug query filters out security bugs"""
    project = {"project_name": "Test Project"}

    mock_rest_client = AsyncMock()

    mock_work_item = Mock()
    mock_work_item.id = 1001

    mock_wiql_result = Mock()
    mock_wiql_result.work_items = [mock_work_item]

    mock_rest_client.query_by_wiql.return_value = {}

    mock_bugs = [{"System.Id": 1001, "System.Tags": "ArmorCode"}]
    mock_filtered_bugs: list[dict[str, object]] = []  # Security bug filtered out

    with (
        patch(
            "execution.dashboards.targets.WorkItemTransformer.transform_wiql_response", return_value=mock_wiql_result
        ),
        patch(
            "execution.utils.ado_batch_utils.batch_fetch_work_items_rest", new_callable=AsyncMock
        ) as mock_batch_fetch,
        patch("execution.dashboards.targets.WorkItemTransformer.transform_work_items_response", return_value=mock_bugs),
        patch("execution.dashboards.targets.filter_security_bugs", return_value=(mock_filtered_bugs, 1)),
    ):
        mock_batch_fetch.return_value = (mock_bugs, [])

        result = await _query_bugs_for_project(mock_rest_client, project)

        # Should return 0 after filtering
        assert result == 0


@pytest.mark.asyncio
async def test_query_bugs_for_project_no_bugs():
    """Test bug query returns 0 when no bugs found"""
    project = {"project_name": "Test Project"}

    mock_rest_client = AsyncMock()

    mock_wiql_result = Mock()
    mock_wiql_result.work_items = []

    mock_rest_client.query_by_wiql.return_value = {}

    with patch(
        "execution.dashboards.targets.WorkItemTransformer.transform_wiql_response", return_value=mock_wiql_result
    ):
        result = await _query_bugs_for_project(mock_rest_client, project)
        assert result == 0


# Test: _calculate_metrics
def test_calculate_metrics_on_track():
    """Test metric calculation when on track"""
    from datetime import datetime

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
    # Type-safe access to nested dictionaries
    security_value = result["security"]
    bugs_value = result["bugs"]
    assert isinstance(security_value, dict) and security_value["current_count"] == 50
    assert isinstance(bugs_value, dict) and bugs_value["current_count"] == 100
    assert result["show_glossary"] is False


# Test: _query_current_state
@pytest.mark.asyncio
async def test_query_current_state_success():
    """Test successful querying of current state from APIs"""
    baselines = {"security": {"products": ["Product A"]}, "bugs": {}}

    with (
        patch(
            "execution.dashboards.targets._query_current_armorcode_vulns", new_callable=AsyncMock
        ) as mock_query_vulns,
        patch("execution.dashboards.targets._query_current_ado_bugs", new_callable=AsyncMock) as mock_query_bugs,
    ):
        mock_query_vulns.return_value = 85
        mock_query_bugs.return_value = 115

        result = await _query_current_state(baselines)

        assert result["security"] == 85
        assert result["bugs"] == 115
        mock_query_vulns.assert_called_once_with()
        mock_query_bugs.assert_called_once()


# Test: generate_targets_dashboard (integration test)
@pytest.mark.asyncio
@patch("execution.dashboards.targets._load_baselines")
@patch("execution.dashboards.targets._query_current_state", new_callable=AsyncMock)
@patch("execution.dashboards.targets._calculate_summary")
@patch("execution.dashboards.targets._build_context")
@patch("execution.dashboards.targets.render_dashboard")
async def test_generate_targets_dashboard_success(
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
    html = await generate_targets_dashboard()

    # Verify
    assert html == "<html>Mock Dashboard</html>"
    mock_load_baselines.assert_called_once()
    mock_query_state.assert_called_once()
    mock_calculate_summary.assert_called_once()
    mock_build_context.assert_called_once()
    mock_render.assert_called_once()


@pytest.mark.asyncio
@patch("execution.dashboards.targets._load_baselines")
async def test_generate_targets_dashboard_missing_baselines(mock_load_baselines):
    """Test dashboard generation fails when baselines are missing"""
    mock_load_baselines.side_effect = FileNotFoundError("Security baseline not found")

    with pytest.raises(FileNotFoundError, match="Security baseline not found"):
        await generate_targets_dashboard()
