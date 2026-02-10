"""Trends dashboard calculation logic"""

from execution.dashboards.trends.calculator import TrendsCalculator
from execution.dashboards.trends.data_loader import TrendsDataLoader
from execution.dashboards.trends.renderer import TrendsRenderer

__all__ = ["TrendsCalculator", "TrendsDataLoader", "TrendsRenderer"]
