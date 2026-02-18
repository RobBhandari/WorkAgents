"""
Tests for Quality Agent

Ensures agent uses skills correctly, handles retries, and saves metrics.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.collectors.quality_agent import QualityAgent


@pytest.fixture
def quality_agent():
    """Create quality agent instance for testing."""
    return QualityAgent(config={"lookback_days": 90})


@pytest.fixture
def sample_project():
    """Sample project metadata."""
    return {
        "project_name": "Test Project",
        "project_key": "test-project",
        "ado_project_name": "TestProject",
        "area_path_filter": None,
    }


@pytest.fixture
def sample_bugs():
    """Sample bug data."""
    return {
        "all_bugs": [
            {
                "System.Id": 1001,
                "System.CreatedDate": "2026-01-01T00:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-05T00:00:00Z",
            },
            {
                "System.Id": 1002,
                "System.CreatedDate": "2026-01-10T00:00:00Z",
                "Microsoft.VSTS.Common.ClosedDate": "2026-01-15T00:00:00Z",
            },
        ],
        "open_bugs": [
            {
                "System.Id": 1003,
                "System.CreatedDate": "2026-02-01T00:00:00Z",
            }
        ],
    }


@pytest.mark.asyncio
async def test_agent_collect_uses_skill_tools(quality_agent, sample_project):
    """Test that agent uses ADO skill tools instead of direct REST calls."""
    with (
        patch("agents.collectors.quality_agent.query_work_items") as mock_query,
        patch("agents.collectors.quality_agent.get_work_items_by_ids") as mock_get_items,
        patch("agents.collectors.quality_agent.get_test_runs") as mock_test_runs,
    ):

        # Mock skill tool responses
        mock_query.return_value = {"workItems": [{"id": 1001}, {"id": 1002}]}
        mock_get_items.return_value = {
            "value": [
                {
                    "fields": {
                        "System.Id": 1001,
                        "System.CreatedDate": "2026-01-01T00:00:00Z",
                        "Microsoft.VSTS.Common.ClosedDate": "2026-01-05T00:00:00Z",
                    }
                }
            ]
        }
        mock_test_runs.return_value = {"value": []}

        # Mock environment
        with patch("os.getenv", return_value="https://dev.azure.com/contoso"):
            result = await quality_agent.collect(sample_project)

        # Verify skill tools were called
        assert mock_query.called
        assert mock_get_items.called
        assert mock_test_runs.called

        # Verify result structure
        assert "project_name" in result
        assert "bug_age_distribution" in result
        assert "mttr" in result


@pytest.mark.asyncio
async def test_agent_retry_logic(quality_agent, sample_project):
    """Test that agent retries on failure."""
    with patch.object(quality_agent, "collect") as mock_collect:
        # First two calls fail, third succeeds
        mock_collect.side_effect = [
            Exception("API Error"),
            Exception("Timeout"),
            {"project_name": "Test", "metrics": "data"},
        ]

        result = await quality_agent.collect_with_retry(sample_project, max_retries=3)

        # Should have tried 3 times
        assert mock_collect.call_count == 3
        assert result == {"project_name": "Test", "metrics": "data"}


@pytest.mark.asyncio
async def test_agent_retry_exhausted(quality_agent, sample_project):
    """Test that agent raises error when all retries exhausted."""
    with patch.object(quality_agent, "collect") as mock_collect:
        # All calls fail
        mock_collect.side_effect = Exception("Persistent Error")

        with pytest.raises(Exception, match="Persistent Error"):
            await quality_agent.collect_with_retry(sample_project, max_retries=3)

        # Should have tried 3 times
        assert mock_collect.call_count == 3


def test_agent_calculate_bug_age_distribution(quality_agent):
    """Test bug age distribution calculation."""
    open_bugs = [
        {"System.CreatedDate": "2026-02-10T00:00:00Z"},  # 8 days old
        {"System.CreatedDate": "2026-01-01T00:00:00Z"},  # 48 days old
    ]

    result = quality_agent._calculate_bug_age_distribution(open_bugs)

    assert result["sample_size"] == 2
    assert result["median_age_days"] is not None
    assert "ages_distribution" in result


def test_agent_calculate_mttr(quality_agent):
    """Test MTTR calculation."""
    all_bugs = [
        {
            "System.CreatedDate": "2026-01-01T00:00:00Z",
            "Microsoft.VSTS.Common.ClosedDate": "2026-01-05T00:00:00Z",
        },  # 4 days
        {
            "System.CreatedDate": "2026-01-10T00:00:00Z",
            "Microsoft.VSTS.Common.ClosedDate": "2026-01-15T00:00:00Z",
        },  # 5 days
    ]

    result = quality_agent._calculate_mttr(all_bugs)

    assert result["sample_size"] == 2
    assert result["mttr_days"] is not None
    assert result["median_mttr_days"] is not None


def test_agent_save_metrics_validates_data(quality_agent):
    """Test that save_metrics validates data before saving."""
    # Empty metrics should return False
    assert quality_agent.save_metrics([]) is False

    # All zeros should return False
    metrics = [{"total_bugs_analyzed": 0, "open_bugs_count": 0}]
    assert quality_agent.save_metrics(metrics) is False


@pytest.mark.asyncio
async def test_agent_run_loads_discovery_data(quality_agent):
    """Test that agent.run() loads discovery data."""
    with (
        patch.object(quality_agent, "load_discovery_data") as mock_load,
        patch.object(quality_agent, "collect_with_retry") as mock_collect,
        patch.object(quality_agent, "save_metrics") as mock_save,
    ):

        mock_load.return_value = {"projects": [{"project_name": "Test", "project_key": "test"}]}
        mock_collect.return_value = {"metrics": "data"}
        mock_save.return_value = True

        await quality_agent.run()

        mock_load.assert_called_once()
        mock_collect.assert_called()
        mock_save.assert_called()
