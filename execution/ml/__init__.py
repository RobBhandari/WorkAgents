"""
ML-powered analytics for Observatory metrics.

Modules:
- TrendPredictor: linear regression + confidence intervals for quality/bug metrics
- AnomalyDetector: cross-metric z-score anomaly detection across all dashboards
- AlertEngine: threshold rules + anomaly alerts persisted to SQLite
"""

from .alert_engine import Alert, AlertEngine
from .anomaly_detector import AnomalyDetector, AnomalyResult
from .trend_predictor import TrendPredictor

__all__ = ["TrendPredictor", "AnomalyDetector", "AnomalyResult", "AlertEngine", "Alert"]
