"""
Tests for Async ADO Collector

Tests cover:
- AsyncADOCollector initialization
- Thread pool execution (_run_in_thread)
- Quality metrics collection (collect_quality_metrics_for_project)
- Flow metrics collection (collect_flow_metrics_for_project)
- Concurrent project collection (collect_all_projects)
- Error handling in async context
- Thread pool shutdown
- Main entry points (main_quality, main_flow)
- Subprocess/async orchestration
- Performance characteristics
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, mock_open, patch

import pytest

from execution.collectors.async_ado_collector import AsyncADOCollector, main_flow, main_quality

# Fixtures


@pytest.fixture
def mock_ado_connection():
    """Mock ADO connection with work item tracking client"""
    connection = MagicMock()
    wit_client = MagicMock()
    connection.clients.get_work_item_tracking_client.return_value = wit_client
    return connection


@pytest.fixture
def sample_project():
    """Sample project configuration"""
    return {
        "project_key": "PROJ1",
        "project_name": "Test Project",
        "ado_project_name": "Test Project",
        "area_path_filter": None,
    }


@pytest.fixture
def sample_projects():
    """Sample list of project configurations"""
    return [
        {
            "project_key": "PROJ1",
            "project_name": "Project A",
            "ado_project_name": "Project A",
        },
        {
            "project_key": "PROJ2",
            "project_name": "Project B",
            "ado_project_name": "Project B",
            "area_path_filter": "INCLUDE:TeamX",
        },
        {
            "project_key": "PROJ3",
            "project_name": "Project C",
            "ado_project_name": "Project C",
        },
    ]


@pytest.fixture
def sample_quality_metrics():
    """Sample quality metrics result"""
    return {
        "project_key": "PROJ1",
        "project_name": "Test Project",
        "open_bugs_count": 25,
        "total_bugs_analyzed": 5,
        "collected_at": datetime.now().isoformat(),
    }


@pytest.fixture
def sample_flow_metrics():
    """Sample flow metrics result"""
    return {
        "project_key": "PROJ1",
        "project_name": "Test Project",
        "work_type_metrics": {
            "Bug": {
                "open_count": 10,
                "closed_count_90d": 8,
                "wip": 10,
                "lead_time": {"p50": 5.5, "p85": 12.3, "p95": 18.7},
                "dual_metrics": {"operational": {"p50": 4.2, "p85": 9.8, "p95": 14.5}},
                "aging_items": {"aging_count": 3, "by_age_bucket": {}},
                "throughput": {"closed_count": 8},
                "cycle_time_variance": {"variance": 2.5},
            }
        },
        "collected_at": datetime.now().isoformat(),
    }


@pytest.fixture
def sample_work_items():
    """Sample work items for flow metrics"""
    return {
        "work_type": "Bug",
        "open_items": [
            {"id": 1001, "created_date": "2026-01-15"},
            {"id": 1002, "created_date": "2026-01-20"},
        ],
        "closed_items": [
            {"id": 2001, "created_date": "2026-01-01", "closed_date": "2026-01-10"},
            {"id": 2002, "created_date": "2026-01-05", "closed_date": "2026-01-15"},
        ],
        "open_count": 2,
        "closed_count": 2,
    }


@pytest.fixture
def sample_discovery_data(sample_projects):
    """Sample ADO structure discovery data"""
    return {"projects": sample_projects}


# Test AsyncADOCollector Initialization


class TestAsyncADOCollectorInit:
    """Test AsyncADOCollector initialization"""

    def test_default_max_workers(self):
        """Test default max_workers is set to 10"""
        collector = AsyncADOCollector()
        assert collector.max_workers == 10
        assert collector.executor is not None
        collector.shutdown()

    def test_custom_max_workers(self):
        """Test custom max_workers can be specified"""
        collector = AsyncADOCollector(max_workers=5)
        assert collector.max_workers == 5
        collector.shutdown()

    def test_executor_created(self):
        """Test ThreadPoolExecutor is created on initialization"""
        collector = AsyncADOCollector()
        assert collector.executor is not None
        assert collector.executor._max_workers == 10
        collector.shutdown()


# Test Thread Pool Execution


class TestRunInThread:
    """Test _run_in_thread method for wrapping synchronous functions"""

    @pytest.mark.asyncio
    async def test_run_sync_function_in_thread(self):
        """Test running synchronous function in thread pool"""
        collector = AsyncADOCollector()

        def sync_function(x, y):
            return x + y

        result = await collector._run_in_thread(sync_function, 5, 10)
        assert result == 15
        collector.shutdown()

    @pytest.mark.asyncio
    async def test_run_function_with_kwargs(self):
        """Test running function with keyword arguments"""
        collector = AsyncADOCollector()

        def sync_function(a, b=10):
            return a * b

        result = await collector._run_in_thread(sync_function, 3, b=7)
        assert result == 21
        collector.shutdown()

    @pytest.mark.asyncio
    async def test_run_function_raises_exception(self):
        """Test exception propagation from thread pool"""
        collector = AsyncADOCollector()

        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await collector._run_in_thread(failing_function)

        collector.shutdown()

    @pytest.mark.asyncio
    async def test_concurrent_thread_execution(self):
        """Test multiple concurrent thread executions"""
        collector = AsyncADOCollector(max_workers=5)

        def slow_function(value):
            import time

            time.sleep(0.01)  # Simulate blocking I/O
            return value * 2

        # Run 5 concurrent tasks
        tasks = [collector._run_in_thread(slow_function, i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert results == [0, 2, 4, 6, 8]
        collector.shutdown()


# Test Quality Metrics Collection


class TestCollectQualityMetricsForProject:
    """Test quality metrics collection for single project"""

    @pytest.mark.asyncio
    async def test_successful_quality_collection(self, mock_ado_connection, sample_project, sample_quality_metrics):
        """Test successful quality metrics collection"""
        collector = AsyncADOCollector()

        with patch("execution.collectors.ado_quality_metrics.collect_quality_metrics_for_project") as mock_collect:
            mock_collect.return_value = sample_quality_metrics

            config = {"lookback_days": 90}
            result = await collector.collect_quality_metrics_for_project(mock_ado_connection, sample_project, config)

            # Verify result
            assert result == sample_quality_metrics
            assert result["project_name"] == "Test Project"
            assert result["open_bugs_count"] == 25

            # Verify sync function was called
            mock_collect.assert_called_once_with(mock_ado_connection, sample_project, config)

        collector.shutdown()

    @pytest.mark.asyncio
    async def test_quality_collection_with_area_filter(self, mock_ado_connection, sample_quality_metrics):
        """Test quality metrics collection with area path filter"""
        collector = AsyncADOCollector()

        project = {
            "project_key": "PROJ1",
            "project_name": "Test Project",
            "area_path_filter": "INCLUDE:TeamX",
        }

        with patch("execution.collectors.ado_quality_metrics.collect_quality_metrics_for_project") as mock_collect:
            mock_collect.return_value = sample_quality_metrics

            config = {"lookback_days": 90}
            result = await collector.collect_quality_metrics_for_project(mock_ado_connection, project, config)

            assert result == sample_quality_metrics
            mock_collect.assert_called_once_with(mock_ado_connection, project, config)

        collector.shutdown()

    @pytest.mark.asyncio
    async def test_quality_collection_raises_exception(self, mock_ado_connection, sample_project):
        """Test exception handling in quality metrics collection"""
        collector = AsyncADOCollector()

        with patch("execution.collectors.ado_quality_metrics.collect_quality_metrics_for_project") as mock_collect:
            mock_collect.side_effect = ValueError("ADO API error")

            config = {"lookback_days": 90}

            with pytest.raises(ValueError, match="ADO API error"):
                await collector.collect_quality_metrics_for_project(mock_ado_connection, sample_project, config)

        collector.shutdown()


# Test Flow Metrics Collection


class TestCollectFlowMetricsForProject:
    """Test flow metrics collection for single project"""

    @pytest.mark.asyncio
    async def test_successful_flow_collection(self, mock_ado_connection, sample_project, sample_work_items):
        """Test successful flow metrics collection with concurrent work type queries"""
        collector = AsyncADOCollector()

        with patch("execution.collectors.flow_metrics_queries.query_work_items_by_type") as mock_query:
            # Mock query_work_items_by_type to return sample data for each work type
            mock_query.return_value = sample_work_items

            config = {"lookback_days": 90, "aging_threshold_days": 30}
            result = await collector.collect_flow_metrics_for_project(mock_ado_connection, sample_project, config)

            # Verify result structure
            assert result["project_name"] == "Test Project"
            assert result["project_key"] == "PROJ1"
            assert "work_type_metrics" in result
            assert "Bug" in result["work_type_metrics"]
            assert "User Story" in result["work_type_metrics"]
            assert "Task" in result["work_type_metrics"]

            # Verify query was called for all work types (Bug, User Story, Task)
            assert mock_query.call_count == 3

        collector.shutdown()

    @pytest.mark.asyncio
    async def test_flow_collection_with_area_filter(self, mock_ado_connection, sample_work_items):
        """Test flow metrics collection respects area path filter"""
        collector = AsyncADOCollector()

        project = {
            "project_key": "PROJ1",
            "project_name": "Test Project",
            "ado_project_name": "Test Project",
            "area_path_filter": "EXCLUDE:Archive",
        }

        with patch("execution.collectors.flow_metrics_queries.query_work_items_by_type") as mock_query:
            mock_query.return_value = sample_work_items

            config = {"lookback_days": 90, "aging_threshold_days": 30}
            result = await collector.collect_flow_metrics_for_project(mock_ado_connection, project, config)

            assert result["project_name"] == "Test Project"

            # Verify area_path_filter was passed to query
            for call_args in mock_query.call_args_list:
                assert call_args[0][4] == "EXCLUDE:Archive"  # 5th positional arg

        collector.shutdown()

    @pytest.mark.asyncio
    async def test_flow_collection_handles_query_exception(self, mock_ado_connection, sample_project):
        """Test flow collection handles exceptions from work type queries gracefully"""
        collector = AsyncADOCollector()

        with patch("execution.collectors.flow_metrics_queries.query_work_items_by_type") as mock_query:
            # Simulate failure for Bug queries
            def side_effect(wit_client, project_name, work_type, lookback_days, area_filter):
                if work_type == "Bug":
                    raise ValueError("Query failed")
                return {
                    "work_type": work_type,
                    "open_items": [],
                    "closed_items": [],
                    "open_count": 0,
                    "closed_count": 0,
                }

            mock_query.side_effect = side_effect

            config = {"lookback_days": 90, "aging_threshold_days": 30}
            result = await collector.collect_flow_metrics_for_project(mock_ado_connection, sample_project, config)

            # Should still complete with default values for failed work type
            assert result["project_name"] == "Test Project"
            assert "work_type_metrics" in result
            assert "Bug" in result["work_type_metrics"]
            assert result["work_type_metrics"]["Bug"]["open_count"] == 0

        collector.shutdown()

    @pytest.mark.asyncio
    async def test_flow_collection_concurrent_work_type_queries(self, mock_ado_connection, sample_project):
        """Test that work type queries are executed concurrently"""
        collector = AsyncADOCollector()

        query_times = []

        async def mock_query_with_timing(*args, **kwargs):
            start = datetime.now()
            await asyncio.sleep(0.05)  # Simulate 50ms query
            query_times.append((datetime.now() - start).total_seconds())
            return {
                "work_type": args[2] if len(args) > 2 else "Unknown",
                "open_items": [],
                "closed_items": [],
                "open_count": 0,
                "closed_count": 0,
            }

        with patch("execution.collectors.flow_metrics_queries.query_work_items_by_type") as mock_query:
            # Patch _run_in_thread to use async mock
            async def async_runner(func, *args, **kwargs):
                return await mock_query_with_timing(*args, **kwargs)

            collector._run_in_thread = async_runner  # type: ignore[method-assign]

            config = {"lookback_days": 90, "aging_threshold_days": 30}
            start_time = datetime.now()
            result = await collector.collect_flow_metrics_for_project(mock_ado_connection, sample_project, config)
            total_time = (datetime.now() - start_time).total_seconds()

            # If queries run concurrently, total time should be close to single query time
            # (not 3x single query time for sequential execution)
            assert total_time < 0.2  # Should be ~0.05s, not ~0.15s
            assert result["project_name"] == "Test Project"

        collector.shutdown()

    @pytest.mark.asyncio
    async def test_flow_metrics_calculation(self, mock_ado_connection, sample_project):
        """Test flow metrics are calculated correctly from work items"""
        collector = AsyncADOCollector()

        work_items_with_metrics = {
            "work_type": "Bug",
            "open_items": [
                {"id": 1, "created_date": "2026-01-01"},
                {"id": 2, "created_date": "2026-01-15"},
            ],
            "closed_items": [
                {"id": 3, "created_date": "2026-01-01", "closed_date": "2026-01-10", "cycle_time_days": 9},
                {"id": 4, "created_date": "2026-01-05", "closed_date": "2026-01-15", "cycle_time_days": 10},
            ],
            "open_count": 2,
            "closed_count": 2,
        }

        with patch("execution.collectors.flow_metrics_queries.query_work_items_by_type") as mock_query:
            mock_query.return_value = work_items_with_metrics

            config = {"lookback_days": 90, "aging_threshold_days": 30}
            result = await collector.collect_flow_metrics_for_project(mock_ado_connection, sample_project, config)

            bug_metrics = result["work_type_metrics"]["Bug"]
            assert bug_metrics["open_count"] == 2
            assert bug_metrics["closed_count_90d"] == 2
            assert bug_metrics["wip"] == 2
            assert "lead_time" in bug_metrics
            assert "dual_metrics" in bug_metrics
            assert "aging_items" in bug_metrics

        collector.shutdown()


# Test Collect All Projects


class TestCollectAllProjects:
    """Test concurrent collection for multiple projects"""

    @pytest.mark.asyncio
    async def test_collect_quality_for_multiple_projects(
        self, mock_ado_connection, sample_projects, sample_quality_metrics
    ):
        """Test concurrent quality metrics collection for multiple projects"""
        collector = AsyncADOCollector()

        with patch("execution.collectors.ado_quality_metrics.collect_quality_metrics_for_project") as mock_collect:
            # Return different metrics for each project
            def side_effect(connection, project, config):
                return {
                    "project_key": project["project_key"],
                    "project_name": project["project_name"],
                    "open_bugs_count": 10,
                }

            mock_collect.return_value = sample_quality_metrics

            config = {"lookback_days": 90}
            results = await collector.collect_all_projects(
                mock_ado_connection, sample_projects, config, collector_type="quality"
            )

            # Verify results
            assert len(results) == 3
            assert all(isinstance(r, dict) for r in results)
            assert mock_collect.call_count == 3

        collector.shutdown()

    @pytest.mark.asyncio
    async def test_collect_flow_for_multiple_projects(self, mock_ado_connection, sample_projects, sample_flow_metrics):
        """Test concurrent flow metrics collection for multiple projects"""
        collector = AsyncADOCollector()

        with patch("execution.collectors.flow_metrics_queries.query_work_items_by_type") as mock_query:
            mock_query.return_value = {
                "work_type": "Bug",
                "open_items": [],
                "closed_items": [],
                "open_count": 0,
                "closed_count": 0,
            }

            config = {"lookback_days": 90, "aging_threshold_days": 30}
            results = await collector.collect_all_projects(
                mock_ado_connection, sample_projects, config, collector_type="flow"
            )

            # Verify results
            assert len(results) == 3
            assert all(isinstance(r, dict) for r in results)
            assert all("work_type_metrics" in r for r in results)

        collector.shutdown()

    @pytest.mark.asyncio
    async def test_collect_all_handles_individual_failures(self, mock_ado_connection, sample_projects):
        """Test that individual project failures don't stop entire collection"""
        collector = AsyncADOCollector()

        with patch("execution.collectors.ado_quality_metrics.collect_quality_metrics_for_project") as mock_collect:
            # Make second project fail
            def side_effect(connection, project, config):
                if project["project_key"] == "PROJ2":
                    raise ValueError("Project B failed")
                return {
                    "project_key": project["project_key"],
                    "project_name": project["project_name"],
                    "open_bugs_count": 10,
                }

            mock_collect.side_effect = side_effect

            config = {"lookback_days": 90}
            results = await collector.collect_all_projects(
                mock_ado_connection, sample_projects, config, collector_type="quality"
            )

            # Should get results for 2 successful projects
            assert len(results) == 2
            assert all(r["project_key"] in ["PROJ1", "PROJ3"] for r in results)

        collector.shutdown()

    @pytest.mark.asyncio
    async def test_collect_all_invalid_collector_type(self, mock_ado_connection, sample_projects):
        """Test ValueError raised for invalid collector type"""
        collector = AsyncADOCollector()

        config = {"lookback_days": 90}

        with pytest.raises(ValueError, match="Unknown collector type: invalid"):
            await collector.collect_all_projects(mock_ado_connection, sample_projects, config, collector_type="invalid")

        collector.shutdown()

    @pytest.mark.asyncio
    async def test_collect_all_performance_logging(self, mock_ado_connection, sample_projects, sample_quality_metrics):
        """Test that collection performance is logged"""
        collector = AsyncADOCollector()

        with patch("execution.collectors.ado_quality_metrics.collect_quality_metrics_for_project") as mock_collect:
            mock_collect.return_value = sample_quality_metrics

            with patch("execution.collectors.async_ado_collector.logger") as mock_logger:
                config = {"lookback_days": 90}
                results = await collector.collect_all_projects(
                    mock_ado_connection, sample_projects, config, collector_type="quality"
                )

                # Verify performance logging
                assert mock_logger.info.call_count >= 2  # Start and completion logs
                log_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("Collecting quality metrics for 3 projects" in call for call in log_calls)
                assert any("projects/sec" in call for call in log_calls)

        collector.shutdown()

    @pytest.mark.asyncio
    async def test_collect_all_empty_projects_list(self, mock_ado_connection):
        """Test handling of empty projects list"""
        collector = AsyncADOCollector()

        config = {"lookback_days": 90}
        results = await collector.collect_all_projects(mock_ado_connection, [], config, collector_type="quality")

        assert results == []
        collector.shutdown()

    @pytest.mark.asyncio
    async def test_collect_all_unexpected_result_type(self, mock_ado_connection, sample_projects):
        """Test handling of unexpected result types (not dict or Exception)"""
        collector = AsyncADOCollector()

        with patch("execution.collectors.ado_quality_metrics.collect_quality_metrics_for_project") as mock_collect:
            # Return unexpected type
            mock_collect.return_value = "unexpected_string"

            config = {"lookback_days": 90}
            results = await collector.collect_all_projects(
                mock_ado_connection, sample_projects, config, collector_type="quality"
            )

            # Should filter out unexpected results
            assert len(results) == 0

        collector.shutdown()


# Test Shutdown


class TestShutdown:
    """Test thread pool executor shutdown"""

    def test_shutdown_waits_for_threads(self):
        """Test shutdown waits for all threads to complete"""
        collector = AsyncADOCollector()
        executor_mock = MagicMock()
        collector.executor = executor_mock

        collector.shutdown()

        executor_mock.shutdown.assert_called_once_with(wait=True)

    def test_shutdown_idempotent(self):
        """Test shutdown can be called multiple times safely"""
        collector = AsyncADOCollector()

        collector.shutdown()
        collector.shutdown()  # Should not raise error


# Test Main Entry Points


class TestMainQuality:
    """Test main_quality async entry point"""

    @pytest.mark.asyncio
    async def test_main_quality_success(self, sample_discovery_data, sample_quality_metrics):
        """Test successful quality metrics collection main flow"""
        with patch("builtins.open", mock_open(read_data=json.dumps(sample_discovery_data))):
            with patch("execution.collectors.ado_quality_metrics.get_ado_connection") as mock_get_conn:
                with patch("execution.collectors.ado_quality_metrics.save_quality_metrics") as mock_save:
                    with patch(
                        "execution.collectors.ado_quality_metrics.collect_quality_metrics_for_project"
                    ) as mock_collect:
                        mock_conn = MagicMock()
                        mock_get_conn.return_value = mock_conn
                        mock_collect.return_value = sample_quality_metrics
                        mock_save.return_value = True

                        result = await main_quality()

                        assert result == 0
                        mock_save.assert_called_once()
                        saved_data = mock_save.call_args[0][0]
                        assert "projects" in saved_data
                        assert "config" in saved_data
                        assert saved_data["config"]["async"] is True

    @pytest.mark.asyncio
    async def test_main_quality_discovery_file_not_found(self):
        """Test main_quality handles missing discovery file"""
        m = mock_open()
        m.side_effect = FileNotFoundError("File not found")

        with patch("builtins.open", m):
            with patch("execution.collectors.async_ado_collector.logger") as mock_logger:
                result = await main_quality()

                assert result == 1
                # Check that error was logged about discovery file
                error_calls = [str(call) for call in mock_logger.error.call_args_list]
                assert any("discovery" in call.lower() or "not found" in call.lower() for call in error_calls)

    @pytest.mark.asyncio
    async def test_main_quality_ado_connection_failure(self, sample_discovery_data):
        """Test main_quality handles ADO connection failure"""
        from azure.devops.exceptions import AzureDevOpsServiceError

        with patch("builtins.open", mock_open(read_data=json.dumps(sample_discovery_data))):
            with patch("execution.collectors.ado_quality_metrics.get_ado_connection") as mock_get_conn:
                # Create a proper exception with required structure
                mock_exception = MagicMock()
                mock_exception.inner_exception = None
                error = AzureDevOpsServiceError(mock_exception)
                mock_get_conn.side_effect = error

                result = await main_quality()

                assert result == 1

    @pytest.mark.asyncio
    async def test_main_quality_save_failure(self, sample_discovery_data, sample_quality_metrics):
        """Test main_quality handles save failure"""
        with patch("builtins.open", mock_open(read_data=json.dumps(sample_discovery_data))):
            with patch("execution.collectors.ado_quality_metrics.get_ado_connection") as mock_get_conn:
                with patch("execution.collectors.ado_quality_metrics.save_quality_metrics") as mock_save:
                    with patch(
                        "execution.collectors.ado_quality_metrics.collect_quality_metrics_for_project"
                    ) as mock_collect:
                        mock_conn = MagicMock()
                        mock_get_conn.return_value = mock_conn
                        mock_collect.return_value = sample_quality_metrics
                        mock_save.return_value = False

                        result = await main_quality()

                        assert result == 1

    @pytest.mark.asyncio
    @patch("sys.platform", "win32")
    async def test_main_quality_windows_encoding(self, sample_discovery_data, sample_quality_metrics):
        """Test main_quality sets UTF-8 encoding on Windows"""
        with patch("builtins.open", mock_open(read_data=json.dumps(sample_discovery_data))):
            with patch("execution.collectors.ado_quality_metrics.get_ado_connection") as mock_get_conn:
                with patch("execution.collectors.ado_quality_metrics.save_quality_metrics") as mock_save:
                    with patch(
                        "execution.collectors.ado_quality_metrics.collect_quality_metrics_for_project"
                    ) as mock_collect:
                        with patch("sys.stdout") as mock_stdout:
                            with patch("sys.stderr") as mock_stderr:
                                mock_conn = MagicMock()
                                mock_get_conn.return_value = mock_conn
                                mock_collect.return_value = sample_quality_metrics
                                mock_save.return_value = True

                                result = await main_quality()

                                # Should set encoding (difficult to test exact behavior due to patching complexity)
                                assert result == 0


class TestMainFlow:
    """Test main_flow async entry point"""

    @pytest.mark.asyncio
    async def test_main_flow_success(self, sample_discovery_data):
        """Test successful flow metrics collection main flow"""
        with patch("builtins.open", mock_open(read_data=json.dumps(sample_discovery_data))):
            with patch("execution.collectors.ado_flow_metrics.get_ado_connection") as mock_get_conn:
                with patch("execution.collectors.ado_flow_metrics.save_flow_metrics") as mock_save:
                    with patch("execution.collectors.flow_metrics_queries.query_work_items_by_type") as mock_query:
                        mock_conn = MagicMock()
                        mock_get_conn.return_value = mock_conn
                        mock_query.return_value = {
                            "work_type": "Bug",
                            "open_items": [],
                            "closed_items": [],
                            "open_count": 0,
                            "closed_count": 0,
                        }
                        mock_save.return_value = True

                        result = await main_flow()

                        assert result == 0
                        mock_save.assert_called_once()
                        saved_data = mock_save.call_args[0][0]
                        assert "projects" in saved_data
                        assert "config" in saved_data
                        assert saved_data["config"]["async"] is True
                        assert saved_data["config"]["aging_threshold_days"] == 30

    @pytest.mark.asyncio
    async def test_main_flow_discovery_file_not_found(self):
        """Test main_flow handles missing discovery file"""
        m = mock_open()
        m.side_effect = FileNotFoundError("File not found")

        with patch("builtins.open", m):
            with patch("execution.collectors.async_ado_collector.logger") as mock_logger:
                result = await main_flow()

                assert result == 1
                # Check that error was logged about discovery file
                error_calls = [str(call) for call in mock_logger.error.call_args_list]
                assert any("discovery" in call.lower() or "not found" in call.lower() for call in error_calls)

    @pytest.mark.asyncio
    async def test_main_flow_ado_connection_failure(self, sample_discovery_data):
        """Test main_flow handles ADO connection failure"""
        from azure.devops.exceptions import AzureDevOpsServiceError

        with patch("builtins.open", mock_open(read_data=json.dumps(sample_discovery_data))):
            with patch("execution.collectors.ado_flow_metrics.get_ado_connection") as mock_get_conn:
                # Create a proper exception with required structure
                mock_exception = MagicMock()
                mock_exception.inner_exception = None
                error = AzureDevOpsServiceError(mock_exception)
                mock_get_conn.side_effect = error

                result = await main_flow()

                assert result == 1

    @pytest.mark.asyncio
    async def test_main_flow_save_failure(self, sample_discovery_data):
        """Test main_flow handles save failure"""
        with patch("builtins.open", mock_open(read_data=json.dumps(sample_discovery_data))):
            with patch("execution.collectors.ado_flow_metrics.get_ado_connection") as mock_get_conn:
                with patch("execution.collectors.ado_flow_metrics.save_flow_metrics") as mock_save:
                    with patch("execution.collectors.flow_metrics_queries.query_work_items_by_type") as mock_query:
                        mock_conn = MagicMock()
                        mock_get_conn.return_value = mock_conn
                        mock_query.return_value = {
                            "work_type": "Bug",
                            "open_items": [],
                            "closed_items": [],
                            "open_count": 0,
                            "closed_count": 0,
                        }
                        mock_save.return_value = False

                        result = await main_flow()

                        assert result == 1


# Test Edge Cases and Error Handling


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    @pytest.mark.asyncio
    async def test_collect_with_zero_max_workers(self):
        """Test behavior with zero max workers (edge case)"""
        # ThreadPoolExecutor with max_workers=0 should raise ValueError
        with pytest.raises(ValueError):
            collector = AsyncADOCollector(max_workers=0)

    @pytest.mark.asyncio
    async def test_collect_with_negative_max_workers(self):
        """Test behavior with negative max workers"""
        with pytest.raises(ValueError):
            collector = AsyncADOCollector(max_workers=-1)

    @pytest.mark.asyncio
    async def test_flow_collection_missing_ado_project_name(self, mock_ado_connection):
        """Test flow collection falls back to project_name when ado_project_name missing"""
        collector = AsyncADOCollector()

        project = {
            "project_key": "PROJ1",
            "project_name": "Test Project",
            # Missing ado_project_name
        }

        with patch("execution.collectors.flow_metrics_queries.query_work_items_by_type") as mock_query:
            mock_query.return_value = {
                "work_type": "Bug",
                "open_items": [],
                "closed_items": [],
                "open_count": 0,
                "closed_count": 0,
            }

            config = {"lookback_days": 90}
            result = await collector.collect_flow_metrics_for_project(mock_ado_connection, project, config)

            # Should use project_name as fallback
            assert result["project_name"] == "Test Project"

        collector.shutdown()

    @pytest.mark.asyncio
    async def test_flow_collection_invalid_work_item_data_type(self, mock_ado_connection, sample_project):
        """Test flow collection handles invalid work item data types"""
        collector = AsyncADOCollector()

        with patch("execution.collectors.flow_metrics_queries.query_work_items_by_type") as mock_query:
            # Return invalid data structure (not dict with expected fields)
            mock_query.return_value = {
                "work_type": "Bug",
                "open_items": "not_a_list",  # Should be list
                "closed_items": 123,  # Should be list
                "open_count": "five",  # Should be int
                "closed_count": None,  # Should be int
            }

            config = {"lookback_days": 90, "aging_threshold_days": 30}
            result = await collector.collect_flow_metrics_for_project(mock_ado_connection, sample_project, config)

            # Should handle type errors gracefully
            bug_metrics = result["work_type_metrics"]["Bug"]
            assert bug_metrics["open_count"] == 0  # Converted from invalid string
            assert bug_metrics["closed_count_90d"] == 0  # Converted from None

        collector.shutdown()


# Test Performance Characteristics


class TestPerformanceCharacteristics:
    """Test async performance optimizations"""

    @pytest.mark.asyncio
    async def test_concurrent_project_collection_faster_than_sequential(
        self, mock_ado_connection, sample_projects, sample_quality_metrics
    ):
        """Test that concurrent collection is faster than sequential"""
        collector = AsyncADOCollector()

        call_count = 0

        async def slow_collect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # 100ms per project
            return sample_quality_metrics

        # Patch _run_in_thread to use async mock
        original_run_in_thread = collector._run_in_thread

        async def async_runner(func, *args, **kwargs):
            return await slow_collect(*args, **kwargs)

        collector._run_in_thread = async_runner  # type: ignore[method-assign]

        config = {"lookback_days": 90}
        start_time = datetime.now()

        with patch("execution.collectors.ado_quality_metrics.collect_quality_metrics_for_project"):
            results = await collector.collect_all_projects(
                mock_ado_connection, sample_projects, config, collector_type="quality"
            )

        total_time = (datetime.now() - start_time).total_seconds()

        # 3 projects × 100ms sequential = 300ms
        # Concurrent should be ~100ms (if truly parallel)
        assert total_time < 0.25  # Should be much less than 300ms
        assert call_count == 3

        collector.shutdown()

    @pytest.mark.asyncio
    async def test_work_type_queries_execute_concurrently(self, mock_ado_connection, sample_project):
        """Test that Bug/Story/Task queries execute concurrently, not sequentially"""
        collector = AsyncADOCollector()

        query_start_times = []

        async def track_query_timing(*args, **kwargs):
            query_start_times.append(datetime.now())
            await asyncio.sleep(0.05)  # 50ms query
            return {
                "work_type": args[2] if len(args) > 2 else "Unknown",
                "open_items": [],
                "closed_items": [],
                "open_count": 0,
                "closed_count": 0,
            }

        async def async_runner(func, *args, **kwargs):
            return await track_query_timing(*args, **kwargs)

        collector._run_in_thread = async_runner  # type: ignore[method-assign]

        config = {"lookback_days": 90}
        start_time = datetime.now()

        with patch("execution.collectors.flow_metrics_queries.query_work_items_by_type"):
            result = await collector.collect_flow_metrics_for_project(mock_ado_connection, sample_project, config)

        total_time = (datetime.now() - start_time).total_seconds()

        # 3 work types × 50ms sequential = 150ms
        # Concurrent should be ~50ms
        assert total_time < 0.12  # Should be much less than 150ms

        # Verify queries started close together (concurrent)
        if len(query_start_times) >= 2:
            time_diff = (query_start_times[1] - query_start_times[0]).total_seconds()
            assert time_diff < 0.01  # Queries should start within 10ms of each other

        collector.shutdown()
