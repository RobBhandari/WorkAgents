"""
Pytest configuration and shared fixtures

Provides common test fixtures for domain models, components, and integrations.
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add execution directory to path for imports
execution_dir = Path(__file__).parent.parent / "execution"
sys.path.insert(0, str(execution_dir))


# ===== Domain Model Fixtures =====


@pytest.fixture
def sample_timestamp():
    """Provide a consistent timestamp for testing"""
    return datetime(2026, 2, 7, 12, 0, 0)


@pytest.fixture
def sample_bug():
    """Provide a sample Bug domain model"""
    from domain.quality import Bug

    return Bug(
        id=12345,
        title="Sample bug for testing",
        state="Active",
        priority=1,
        created_date="2026-01-15",
        closed_date=None,
        age_days=23,
    )


@pytest.fixture
def sample_closed_bug():
    """Provide a closed Bug domain model"""
    from domain.quality import Bug

    return Bug(
        id=67890,
        title="Closed bug for testing",
        state="Closed",
        priority=2,
        created_date="2026-01-10",
        closed_date="2026-01-25",
        age_days=15,
    )


@pytest.fixture
def sample_quality_metrics(sample_timestamp):
    """Provide sample QualityMetrics"""
    from domain.quality import QualityMetrics

    return QualityMetrics(
        timestamp=sample_timestamp,
        project="Test Project",
        open_bugs=50,
        closed_this_week=10,
        created_this_week=5,
        net_change=-5,
        p1_count=2,
        p2_count=8,
        aging_bugs=15,
    )


@pytest.fixture
def sample_vulnerability():
    """Provide a sample Vulnerability domain model"""
    from domain.security import Vulnerability

    return Vulnerability(
        id="VUL-2026-0123",
        title="SQL Injection vulnerability",
        severity="CRITICAL",
        status="Open",
        product="API Gateway",
        age_days=5,
        cve_id="CVE-2026-1234",
    )


@pytest.fixture
def sample_security_metrics(sample_timestamp):
    """Provide sample SecurityMetrics"""
    from domain.security import SecurityMetrics

    return SecurityMetrics(
        timestamp=sample_timestamp,
        project="API Gateway",
        total_vulnerabilities=42,
        critical=3,
        high=12,
        medium=20,
        low=7,
        baseline=100,
        target=30,
    )


@pytest.fixture
def sample_flow_metrics(sample_timestamp):
    """Provide sample FlowMetrics"""
    from domain.flow import FlowMetrics

    return FlowMetrics(
        timestamp=sample_timestamp,
        project="Test Project",
        lead_time_p50=7.5,
        lead_time_p85=15.2,
        lead_time_p95=25.8,
        cycle_time_p50=4.2,
        cycle_time_p85=8.5,
        cycle_time_p95=14.3,
        wip_count=25,
        aging_items=5,
        throughput=12,
    )


@pytest.fixture
def sample_trend_data(sample_timestamp):
    """Provide sample TrendData"""
    from datetime import timedelta

    from domain.metrics import TrendData

    return TrendData(
        values=[50.0, 45.0, 42.0, 38.0],
        timestamps=[
            sample_timestamp - timedelta(weeks=3),
            sample_timestamp - timedelta(weeks=2),
            sample_timestamp - timedelta(weeks=1),
            sample_timestamp,
        ],
        label="Open Bugs",
    )


# ===== Component Testing Fixtures =====


@pytest.fixture
def sample_table_data():
    """Provide sample data for table components"""
    return {
        "headers": ["Product", "Bugs", "Status"],
        "rows": [
            ["API Gateway", "5", "Good"],
            ["Web App", "12", "Attention"],
            ["Mobile App", "3", "Good"],
        ],
    }


# ===== File System Fixtures =====


@pytest.fixture
def temp_dashboard_output(tmp_path):
    """Provide a temporary directory for dashboard outputs"""
    output_dir = tmp_path / "dashboards"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def mock_history_file(tmp_path):
    """Create a mock history JSON file"""
    import json

    history = {"weeks": [{"week_ending": "2026-01-31", "metrics": {"current_total": 42, "critical": 3, "high": 12}}]}

    history_file = tmp_path / "security_history.json"
    history_file.write_text(json.dumps(history, indent=2))
    return history_file
