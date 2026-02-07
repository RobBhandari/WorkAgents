"""
Domain Models - Type-safe data structures for metrics

This package contains dataclasses representing business domain concepts:
    - quality: Bug, QualityMetrics
    - security: Vulnerability, SecurityMetrics
    - flow: FlowMetrics, LeadTime, CycleTime

Usage:
    from execution.domain.quality import Bug, QualityMetrics
    from execution.domain.security import Vulnerability, SecurityMetrics

    bug = Bug(id=123, title="Test", state="Active", age_days=30)
    if bug.is_open:
        print(f"Bug {bug.id} is still open")
"""

# Import domain models for convenient access
from .metrics import MetricSnapshot, TrendData
from .quality import Bug, QualityMetrics
from .security import Vulnerability, SecurityMetrics
from .flow import FlowMetrics

__all__ = [
    # Base classes
    'MetricSnapshot',
    'TrendData',

    # Quality domain
    'Bug',
    'QualityMetrics',

    # Security domain
    'Vulnerability',
    'SecurityMetrics',

    # Flow domain
    'FlowMetrics',
]
