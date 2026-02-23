"""
Intelligence Platform ML domain models — Phase D.

Separated from intelligence.py to keep file size within the 500-line limit.

Models:
    HealthClassification — RandomForest health classification result (Phase D)
    ClusterResult        — KMeans/DBSCAN cluster assignment result (Phase D)

These are re-exported from execution.domain.intelligence for backward
compatibility — callers should import from there:

    from execution.domain.intelligence import HealthClassification, ClusterResult
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from execution.domain.metrics import MetricSnapshot


@dataclass(kw_only=True)
class HealthClassification(MetricSnapshot):
    """
    RandomForest health classification result for a project.

    Inherits from MetricSnapshot:
        timestamp (datetime) — when this classification was generated
        project  (str|None) — project name (generic form, e.g. "Product_A")

    Attributes:
        label:               "Green" | "Amber" | "Red"
        confidence:          Probability of predicted class (0.0–1.0)
        feature_importances: Top contributing features (name → importance float)
        model_version:       Model version string (e.g. "v1.0.0")
    """

    label: str
    confidence: float = 0.0
    feature_importances: dict[str, float] = field(default_factory=dict)
    model_version: str = ""

    @property
    def status(self) -> str:
        """Human-readable status based on classification label."""
        if self.label == "Green":
            return "Good"
        if self.label == "Amber":
            return "Caution"
        return "Action Needed"

    @property
    def status_class(self) -> str:
        """CSS class for status badge."""
        if self.label == "Green":
            return "status-good"
        if self.label == "Amber":
            return "status-caution"
        return "status-action"

    @classmethod
    def from_json(cls, data: dict) -> HealthClassification:
        """Deserialise from a JSON dict."""
        ts_raw = data.get("timestamp") or datetime.now().isoformat()
        return cls(
            timestamp=datetime.fromisoformat(ts_raw),
            project=data.get("project"),
            label=str(data["label"]),
            confidence=float(data.get("confidence", 0.0)),
            feature_importances={k: float(v) for k, v in data.get("feature_importances", {}).items()},
            model_version=str(data.get("model_version", "")),
        )


@dataclass
class ClusterResult:
    """
    KMeans/DBSCAN cluster assignment result for a project.

    No MetricSnapshot inheritance — ClusterResult has no independent
    timestamp; it is a derived computation over feature data whose
    timestamp context lives in the feature store.
    (Same pattern as CausalContribution in intelligence.py.)

    Attributes:
        project:        Generic project name (e.g. "Product_A")
        cluster_id:     Integer cluster label (-1 = noise for DBSCAN)
        algorithm:      "kmeans" | "dbscan"
        n_clusters:     Total number of clusters found
        feature_vector: Normalised feature values used (for transparency)
    """

    project: str
    cluster_id: int
    algorithm: str
    n_clusters: int
    feature_vector: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> ClusterResult:
        """Deserialise from a plain dictionary."""
        return cls(
            project=str(data["project"]),
            cluster_id=int(data["cluster_id"]),
            algorithm=str(data["algorithm"]),
            n_clusters=int(data["n_clusters"]),
            feature_vector={k: float(v) for k, v in data.get("feature_vector", {}).items()},
        )
