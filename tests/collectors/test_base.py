#!/usr/bin/env python3
"""
Tests for BaseCollector abstract class

Verifies shared infrastructure for all collectors:
- Platform setup (Windows UTF-8 encoding)
- Discovery data loading with error handling
- ADO REST client initialization
- Concurrent collection orchestration
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, mock_open, patch

import pytest

from execution.collectors.ado_rest_client import AzureDevOpsRESTClient
from execution.collectors.base import BaseCollector


class TestCollector(BaseCollector):
    """Concrete implementation of BaseCollector for testing"""

    def __init__(self, name: str = "test", lookback_days: int = 90):
        super().__init__(name=name, lookback_days=lookback_days)
        self.collected_projects: list[str] = []

    async def collect(self, project: str, rest_client: AzureDevOpsRESTClient):
        """Test implementation of collect method"""
        self.collected_projects.append(project)
        return {"project": project, "data": "test_data"}

    def save_metrics(self, results: list) -> bool:
        """Test implementation of save_metrics method"""
        return len(results) > 0


@pytest.fixture
def sample_discovery_data() -> dict:
    """Sample discovery data matching ado_structure.json format"""
    return {
        "projects": [
            {
                "project_name": "Project1",
                "project_key": "P1",
                "ado_project_name": "Project1",
            },
            {
                "project_name": "Project2",
                "project_key": "P2",
                "ado_project_name": "Project2",
            },
        ]
    }


class TestBaseCollectorInit:
    """Test BaseCollector initialization"""

    def test_init_sets_name_and_config(self):
        """Test collector initializes with name and config"""
        collector = TestCollector(name="ownership", lookback_days=30)

        assert collector.name == "ownership"
        assert collector.config == {"lookback_days": 30}

    def test_init_creates_logger(self):
        """Test collector creates logger with correct name"""
        collector = TestCollector(name="quality")

        assert collector.logger is not None
        # Logger name should match collector name
        assert "quality" in collector.logger.name or collector.logger.name == "quality"

    @patch("sys.platform", "win32")
    @patch("codecs.getwriter")
    def test_setup_platform_windows(self, mock_getwriter):
        """Test platform setup configures UTF-8 on Windows"""
        mock_encoder = Mock()
        mock_getwriter.return_value = mock_encoder

        collector = TestCollector()

        # Should call getwriter for UTF-8 encoding
        assert mock_getwriter.call_count >= 2  # stdout and stderr


class TestBaseCollectorLoadDiscoveryData:
    """Test discovery data loading"""

    def test_load_discovery_data_success(self, sample_discovery_data, tmp_path):
        """Test loading valid discovery data"""
        # Create temporary discovery file
        discovery_file = tmp_path / "ado_structure.json"
        discovery_file.write_text(json.dumps(sample_discovery_data))

        collector = TestCollector()
        result = collector.load_discovery_data(str(discovery_file))

        assert result == sample_discovery_data
        assert len(result["projects"]) == 2

    def test_load_discovery_data_file_not_found(self):
        """Test handling of missing discovery file"""
        collector = TestCollector()

        # log_and_raise re-raises the original exception
        with pytest.raises(FileNotFoundError):
            collector.load_discovery_data("/nonexistent/path.json")

    def test_load_discovery_data_invalid_json(self, tmp_path):
        """Test handling of invalid JSON in discovery file"""
        # Create file with invalid JSON
        discovery_file = tmp_path / "invalid.json"
        discovery_file.write_text("{invalid json content")

        collector = TestCollector()

        # log_and_raise re-raises the original exception
        with pytest.raises(json.JSONDecodeError):
            collector.load_discovery_data(str(discovery_file))

    def test_load_discovery_data_empty_projects(self, tmp_path):
        """Test handling of discovery file with no projects"""
        discovery_file = tmp_path / "empty.json"
        discovery_file.write_text(json.dumps({"projects": []}))

        collector = TestCollector()
        result = collector.load_discovery_data(str(discovery_file))

        assert result["projects"] == []


class TestBaseCollectorGetRestClient:
    """Test ADO REST client initialization"""

    @patch("execution.collectors.base.get_ado_rest_client")
    def test_get_rest_client_success(self, mock_get_client):
        """Test successful REST client initialization"""
        mock_client = Mock(spec=AzureDevOpsRESTClient)
        mock_get_client.return_value = mock_client

        collector = TestCollector()
        result = collector.get_rest_client()

        assert result == mock_client
        mock_get_client.assert_called_once()

    @patch("execution.collectors.base.get_ado_rest_client")
    def test_get_rest_client_failure(self, mock_get_client):
        """Test handling of REST client initialization failure"""
        mock_get_client.side_effect = ValueError("Invalid credentials")

        collector = TestCollector()

        # log_and_raise re-raises the original exception
        with pytest.raises(ValueError, match="Invalid credentials"):
            collector.get_rest_client()


class TestBaseCollectorConcurrentCollection:
    """Test concurrent collection orchestration"""

    @pytest.mark.asyncio
    async def test_run_concurrent_collection_success(self):
        """Test concurrent collection with all successes"""
        collector = TestCollector()

        async def mock_collect(project: str) -> dict:
            await asyncio.sleep(0.01)  # Simulate async work
            return {"project": project, "status": "success"}

        projects = ["Project1", "Project2", "Project3"]
        results = await collector.run_concurrent_collection(projects, mock_collect)

        assert len(results) == 3
        assert all(isinstance(r, dict) for r in results)
        assert all(r["status"] == "success" for r in results)

    @pytest.mark.asyncio
    async def test_run_concurrent_collection_with_exceptions(self):
        """Test concurrent collection handles exceptions gracefully"""
        collector = TestCollector()

        async def mock_collect(project: str) -> dict:
            if project == "FailProject":
                raise ValueError(f"Collection failed for {project}")
            return {"project": project, "status": "success"}

        projects = ["Project1", "FailProject", "Project3"]
        results = await collector.run_concurrent_collection(projects, mock_collect)

        assert len(results) == 3
        # Two successful, one exception
        successes = [r for r in results if isinstance(r, dict)]
        exceptions = [r for r in results if isinstance(r, Exception)]

        assert len(successes) == 2
        assert len(exceptions) == 1
        assert isinstance(exceptions[0], ValueError)

    @pytest.mark.asyncio
    async def test_run_concurrent_collection_empty_projects(self):
        """Test concurrent collection with no projects"""
        collector = TestCollector()

        async def mock_collect(project: str) -> dict:
            return {"project": project}

        results = await collector.run_concurrent_collection([], mock_collect)

        assert len(results) == 0


class TestBaseCollectorRun:
    """Test main execution flow"""

    @pytest.mark.asyncio
    @patch("execution.collectors.base.track_collector_performance")
    async def test_run_success(self, mock_tracker, sample_discovery_data, tmp_path):
        """Test successful end-to-end collection run"""
        # Create discovery file
        discovery_file = tmp_path / "ado_structure.json"
        discovery_file.write_text(json.dumps(sample_discovery_data))

        # Mock tracker
        mock_tracker_instance = Mock()
        mock_tracker_instance.__enter__ = Mock(return_value=mock_tracker_instance)
        mock_tracker_instance.__exit__ = Mock(return_value=None)
        mock_tracker.return_value = mock_tracker_instance

        collector = TestCollector()

        # Patch methods
        with patch.object(collector, "load_discovery_data", return_value=sample_discovery_data):
            with patch.object(collector, "get_rest_client", return_value=Mock()):
                with patch.object(collector, "save_metrics", return_value=True):
                    result = await collector.run()

        assert result is True
        assert mock_tracker_instance.project_count == 2
        assert mock_tracker_instance.success is True

    @pytest.mark.asyncio
    @patch("execution.collectors.base.track_collector_performance")
    async def test_run_no_projects(self, mock_tracker, tmp_path):
        """Test run with no projects in discovery data"""
        # Mock tracker
        mock_tracker_instance = Mock()
        mock_tracker_instance.__enter__ = Mock(return_value=mock_tracker_instance)
        mock_tracker_instance.__exit__ = Mock(return_value=None)
        mock_tracker.return_value = mock_tracker_instance

        collector = TestCollector()

        with patch.object(collector, "load_discovery_data", return_value={"projects": []}):
            result = await collector.run()

        assert result is False

    @pytest.mark.asyncio
    @patch("execution.collectors.base.track_collector_performance")
    async def test_run_save_failure(self, mock_tracker, sample_discovery_data):
        """Test run when save_metrics fails"""
        # Mock tracker
        mock_tracker_instance = Mock()
        mock_tracker_instance.__enter__ = Mock(return_value=mock_tracker_instance)
        mock_tracker_instance.__exit__ = Mock(return_value=None)
        mock_tracker.return_value = mock_tracker_instance

        collector = TestCollector()

        with patch.object(collector, "load_discovery_data", return_value=sample_discovery_data):
            with patch.object(collector, "get_rest_client", return_value=Mock()):
                with patch.object(collector, "save_metrics", return_value=False):
                    result = await collector.run()

        assert result is False


class TestAbstractMethods:
    """Test that abstract methods must be implemented"""

    def test_cannot_instantiate_basecollector_directly(self):
        """Test BaseCollector cannot be instantiated without implementing abstract methods"""
        with pytest.raises(TypeError) as exc_info:
            # This should fail because abstract methods aren't implemented
            collector = BaseCollector(name="test")  # type: ignore

        assert "Can't instantiate abstract class" in str(exc_info.value)
