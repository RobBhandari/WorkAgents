"""
Engineering Health Scorer

Combines bug trend ML (via TrendPredictor) and security vulnerability posture
into a composite 0-100 health score per product.

Components:
- SecurityForecaster: Linear regression on security history → P(hit June 30 target)
- HealthScorer: Orchestrates per-product scoring + builds OrgHealthSummary

Health Score Formula (0-100):
  bug_score    (0-50): trend direction × anomaly penalty
  security_score (0-50): exploitable vuln density (log-scaled)

Status thresholds:
  >= 70  → Healthy (green)
  40-69  → At Risk (amber)
  <  40  → Critical (red)
"""

import json
from datetime import datetime
from math import erf, log10, sqrt
from pathlib import Path
from statistics import median

import numpy as np
from sklearn.linear_model import LinearRegression

from execution.core import get_logger
from execution.domain.health import OrgHealthSummary, ProductHealth
from execution.ml.trend_predictor import TrendPredictor

logger = get_logger(__name__)

# Default history file paths
_QUALITY_HISTORY = Path(".tmp/observatory/quality_history.json")
_SECURITY_HISTORY = Path(".tmp/observatory/security_history.json")
_EXPLOITABLE_HISTORY = Path(".tmp/observatory/exploitable_history.json")
_SECURITY_BASELINE = Path("data/security_targets.json")

# June 30 target date
_TARGET_DATE = datetime(2026, 6, 30)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normal_cdf(x: float, mu: float, sigma: float) -> float:
    """Cumulative distribution function of the normal distribution.

    Uses Python's standard math.erf — no scipy dependency required.

    Returns:
        Probability P(X <= x) where X ~ Normal(mu, sigma)
    """
    if sigma <= 0:
        return 1.0 if x >= mu else 0.0
    return 0.5 * (1.0 + erf((x - mu) / (sigma * sqrt(2))))


def _health_status(score: float) -> str:
    """Map numeric score to status label."""
    if score >= 70:
        return "Healthy"
    elif score >= 40:
        return "At Risk"
    return "Critical"


# ---------------------------------------------------------------------------
# Security Forecaster
# ---------------------------------------------------------------------------


class SecurityForecaster:
    """Linear regression forecast for org-level security target by June 30.

    Reads security_history.json weekly vulnerability totals, fits a linear
    model, and extrapolates to the June 30 deadline.  Computes the probability
    of hitting the target using a normal approximation over residuals.

    Args:
        history_file: Path to security_history.json
        baseline_file: Path to security_targets.json

    Example:
        forecaster = SecurityForecaster()
        result = forecaster.forecast()
        print(f"Probability of hitting target: {result['target_probability']:.1f}%")
    """

    def __init__(
        self,
        history_file: Path | None = None,
        baseline_file: Path | None = None,
    ) -> None:
        self.history_file = history_file or _SECURITY_HISTORY
        self.baseline_file = baseline_file or _SECURITY_BASELINE

    def forecast(self) -> dict:
        """Forecast security vulnerability count on June 30.

        Returns:
            Dict with keys:
                target_probability (float): 0-100, P(count <= target on June 30)
                predicted_count_june30 (int): linear extrapolation
                target_count (int): required count for 70% reduction
                shortfall (int): predicted - target (negative = ahead of target)
                baseline_count (int): starting baseline count
                trajectory (str): "On Track" / "At Risk" / "Behind"
                data_weeks (int): number of history weeks used
        """
        baseline_count, target_count = self._load_baseline()
        weeks = self._load_weeks(baseline_count)

        if len(weeks) < 2:
            logger.warning("Insufficient security history for forecasting", extra={"weeks": len(weeks)})
            return self._fallback_result(baseline_count, target_count, len(weeks))

        # Build date-indexed time series
        dates = [datetime.strptime(w["week_date"], "%Y-%m-%d") for w in weeks]
        first_date = dates[0]
        x_vals = np.array([(d - first_date).days for d in dates], dtype=float).reshape(-1, 1)
        y_vals = np.array([w["metrics"]["current_total"] for w in weeks], dtype=float)

        # Fit model
        model = LinearRegression()
        model.fit(x_vals, y_vals)

        # Extrapolate to June 30
        days_to_target = float((_TARGET_DATE - first_date).days)
        predicted = float(model.predict([[days_to_target]])[0])
        predicted_count = max(0, round(predicted))

        # Residual standard deviation → confidence
        residuals = y_vals - model.predict(x_vals).flatten()
        residual_std = float(np.std(residuals))

        # P(predicted <= target) using normal CDF
        prob = _normal_cdf(float(target_count), predicted, residual_std)
        target_probability = min(100.0, max(0.0, prob * 100.0))

        shortfall = predicted_count - target_count

        if target_probability >= 70:
            trajectory = "On Track"
        elif target_probability >= 30:
            trajectory = "At Risk"
        else:
            trajectory = "Behind"

        logger.info(
            "Security forecast complete",
            extra={
                "predicted_june30": predicted_count,
                "target": target_count,
                "probability": round(target_probability, 1),
                "trajectory": trajectory,
                "weeks": len(weeks),
            },
        )

        return {
            "target_probability": round(target_probability, 1),
            "predicted_count_june30": predicted_count,
            "target_count": target_count,
            "shortfall": shortfall,
            "baseline_count": baseline_count,
            "trajectory": trajectory,
            "data_weeks": len(weeks),
        }

    def _load_baseline(self) -> tuple[int, int]:
        """Load baseline and target counts from security_targets.json."""
        if not self.baseline_file.exists():
            logger.warning("Baseline file not found, using defaults", extra={"file": str(self.baseline_file)})
            return 246, 74

        data = json.loads(self.baseline_file.read_text(encoding="utf-8"))
        baseline = int(
            data.get("baseline_total", data.get("vulnerability_count", data.get("total_vulnerabilities", 246)))
        )
        target_pct = float(data.get("target_pct", 0.70))
        target = int(data.get("target_count", data.get("target_vulnerabilities", round(baseline * (1 - target_pct)))))
        return baseline, target

    def _load_weeks(self, baseline_count: int = 246) -> list[dict]:
        """Load security history weeks, filtered and deduplicated.

        The security_history.json contains multiple raw API collection runs per
        day (not one-per-week snapshots), and may include corrupted spike entries
        (current_total far above baseline due to transient API issues).

        This method:
        1. Filters entries where current_total > baseline * 3 (clearly corrupt)
        2. Deduplicates to one representative entry per calendar week_number,
           using the median of valid counts for that week
        3. Sorts the resulting weekly points by date

        Args:
            baseline_count: Baseline vulnerability count, used to detect outliers

        Returns:
            List of deduplicated weekly dicts, sorted by week_date
        """
        if not self.history_file.exists():
            logger.warning("Security history not found", extra={"file": str(self.history_file)})
            return []

        data = json.loads(self.history_file.read_text(encoding="utf-8"))
        raw_weeks = data.get("weeks", [])

        # 1. Filter obvious corrupt entries (>3x baseline)
        threshold = baseline_count * 3
        valid = [w for w in raw_weeks if w.get("metrics", {}).get("current_total", 0) <= threshold]
        if len(valid) < len(raw_weeks):
            logger.debug(
                "Filtered corrupt security entries",
                extra={"removed": len(raw_weeks) - len(valid), "threshold": threshold},
            )

        # 2. Deduplicate: one representative entry per week_number (median count)
        from collections import defaultdict
        from statistics import median as _median

        by_week: dict[int, list[dict]] = defaultdict(list)
        for w in valid:
            by_week[w.get("week_number", 0)].append(w)

        deduped = []
        for _wk_num, entries in by_week.items():
            # Use median total to represent this week; pick the entry closest to median
            counts = [e["metrics"]["current_total"] for e in entries]
            med = _median(counts)
            best = min(entries, key=lambda e: abs(e["metrics"]["current_total"] - med))
            deduped.append(best)

        result = sorted(deduped, key=lambda w: w["week_date"])
        logger.debug(
            "Security weeks after dedup",
            extra={"weeks": len(result), "totals": [w["metrics"]["current_total"] for w in result]},
        )
        return result

    def _fallback_result(self, baseline_count: int, target_count: int, data_weeks: int) -> dict:
        """Return a neutral result when insufficient data."""
        return {
            "target_probability": 50.0,
            "predicted_count_june30": baseline_count,
            "target_count": target_count,
            "shortfall": baseline_count - target_count,
            "baseline_count": baseline_count,
            "trajectory": "Unknown",
            "data_weeks": data_weeks,
        }


# ---------------------------------------------------------------------------
# Health Scorer
# ---------------------------------------------------------------------------


class HealthScorer:
    """Score all products and produce per-product health + org summary.

    Combines:
    1. Bug trend score from TrendPredictor (per product from quality history)
    2. Security score from exploitable vuln density (per product, log-scaled)
    3. Anomaly detection: z-score on latest week vs historical distribution

    Args:
        quality_history_file: Path to quality_history.json
        security_history_file: Path to security_history.json
        exploitable_history_file: Path to exploitable_history.json
        baseline_file: Path to security_targets.json

    Example:
        scorer = HealthScorer()
        products, summary = scorer.score_all_products()
        for p in products:
            print(f"{p.product_name}: {p.health_score:.0f} ({p.health_status})")
    """

    def __init__(
        self,
        quality_history_file: Path | None = None,
        security_history_file: Path | None = None,
        exploitable_history_file: Path | None = None,
        baseline_file: Path | None = None,
    ) -> None:
        self.quality_history_file = quality_history_file or _QUALITY_HISTORY
        self.security_history_file = security_history_file or _SECURITY_HISTORY
        self.exploitable_history_file = exploitable_history_file or _EXPLOITABLE_HISTORY
        self._predictor = TrendPredictor(history_file=self.quality_history_file)
        self._security_forecaster = SecurityForecaster(
            history_file=security_history_file or _SECURITY_HISTORY,
            baseline_file=baseline_file or _SECURITY_BASELINE,
        )

    def score_all_products(self) -> tuple[list[ProductHealth], OrgHealthSummary]:
        """Score every product with available quality data.

        Returns:
            Tuple of (list[ProductHealth], OrgHealthSummary) sorted by health_score asc
        """
        quality_weeks = self._load_quality_weeks()
        exploitable_by_product = self._load_exploitable_by_product()
        security_forecast = self._security_forecaster.forecast()

        if not quality_weeks:
            logger.warning("No quality history available for health scoring")
            empty_summary = OrgHealthSummary(
                overall_score=0.0,
                healthy_count=0,
                at_risk_count=0,
                critical_count=0,
                total_products=0,
                security_target_probability=security_forecast["target_probability"],
                security_predicted_count_june30=security_forecast["predicted_count_june30"],
                security_target_count=security_forecast["target_count"],
                security_predicted_shortfall=security_forecast["shortfall"],
                org_security_trajectory=security_forecast["trajectory"],
            )
            return [], empty_summary

        # Determine all products present in quality history
        product_keys = self._get_product_keys(quality_weeks)

        # Compute max exploitable for relative scoring
        max_exploitable = max(exploitable_by_product.values(), default=1)

        products: list[ProductHealth] = []
        for project_key, project_name in product_keys.items():
            health = self._score_product(
                project_key=project_key,
                project_name=project_name,
                quality_weeks=quality_weeks,
                exploitable_by_product=exploitable_by_product,
                max_exploitable=max_exploitable,
            )
            if health is not None:
                products.append(health)

        # Sort by health score ascending (worst first for dashboard prominence)
        products.sort(key=lambda p: p.health_score)

        summary = self._build_org_summary(products, security_forecast)

        logger.info(
            "Health scoring complete",
            extra={
                "products_scored": len(products),
                "healthy": summary.healthy_count,
                "at_risk": summary.at_risk_count,
                "critical": summary.critical_count,
                "critical_anomalies": len(summary.critical_anomalies),
            },
        )

        return products, summary

    # ------------------------------------------------------------------
    # Per-product scoring
    # ------------------------------------------------------------------

    def _score_product(
        self,
        project_key: str,
        project_name: str,
        quality_weeks: list[dict],
        exploitable_by_product: dict[str, int],
        max_exploitable: int,
    ) -> ProductHealth | None:
        """Score a single product. Returns None if insufficient data."""
        # Extract this product's bug series
        bug_series = self._get_bug_series(project_key, quality_weeks)
        if len(bug_series) < 3:
            logger.debug(
                "Skipping product - insufficient data", extra={"product": project_key, "weeks": len(bug_series)}
            )
            return None

        current_bugs = bug_series[-1]

        # ------ Bug score (0-50) via TrendPredictor ------
        bug_trend = "stable"
        bug_forecast_4wk: int | None = None
        bug_ci_lower: int | None = None
        bug_ci_upper: int | None = None

        try:
            analysis = self._predictor.predict_trends(project_key, weeks_ahead=4)
            bug_trend = analysis.trend_direction
            if analysis.predictions:
                last_pred = analysis.predictions[-1]
                bug_forecast_4wk = last_pred.predicted_count
                bug_ci_lower, bug_ci_upper = last_pred.confidence_interval
        except ValueError as exc:
            logger.debug("TrendPredictor could not score product", extra={"product": project_key, "error": str(exc)})

        # ------ Anomaly detection ------
        has_anomaly, anomaly_severity, z_score = self._detect_current_anomaly(bug_series)
        anomaly_description: str | None = None
        if has_anomaly:
            direction = "above" if bug_series[-1] > float(np.mean(bug_series[:-1])) else "below"
            anomaly_description = (
                f"{project_name} bug count {direction} normal range " f"(z={z_score:.1f}, this week: {current_bugs})"
            )

        # ------ Compute sub-scores ------
        bug_score = self._compute_bug_score(bug_trend, has_anomaly, anomaly_severity)
        security_score = self._compute_security_score(project_name, exploitable_by_product, max_exploitable)

        health_score = round(bug_score + security_score, 1)
        health_status = _health_status(health_score)

        return ProductHealth(
            timestamp=datetime.now(),
            product_name=project_name,
            health_score=health_score,
            health_status=health_status,
            bug_score=round(bug_score, 1),
            security_score=round(security_score, 1),
            bug_trend=bug_trend,
            bug_forecast_4wk=bug_forecast_4wk,
            bug_ci_lower=bug_ci_lower,
            bug_ci_upper=bug_ci_upper,
            current_bug_count=current_bugs,
            has_anomaly=has_anomaly,
            anomaly_severity=anomaly_severity,
            anomaly_description=anomaly_description,
            exploitable_total=exploitable_by_product.get(project_name, 0),
        )

    def _compute_bug_score(self, trend: str, has_anomaly: bool, severity: str | None) -> float:
        """Compute bug sub-score (0-50).

        Base: decreasing=50, stable=35, increasing=15
        Anomaly penalty: warning=−15, critical=−25
        """
        if trend == "decreasing":
            base = 50.0
        elif trend == "increasing":
            base = 15.0
        else:
            base = 35.0

        if has_anomaly:
            base -= 25.0 if severity == "critical" else 15.0

        return max(0.0, base)

    def _compute_security_score(
        self, product_name: str, exploitable_by_product: dict[str, int], max_exploitable: int
    ) -> float:
        """Compute security sub-score (0-50) using log-scaled exploitable count.

        Products with 0 exploitable vulns score 50 (perfect).
        The product with the most exploitable vulns scores 0.
        Log scale avoids one dominant product collapsing all other scores.
        """
        count = exploitable_by_product.get(product_name, 0)
        if count <= 0 or max_exploitable <= 0:
            return 50.0

        log_ratio = log10(1 + count) / log10(1 + max_exploitable)
        return round(max(0.0, 50.0 * (1.0 - log_ratio)), 1)

    def _detect_current_anomaly(self, bug_series: list[int]) -> tuple[bool, str | None, float]:
        """Check if this week's bug count is statistically unusual.

        Uses z-score on the historical series (all-but-last used as baseline).

        Returns:
            Tuple of (has_anomaly, severity, z_score)
            severity is "critical" (>3σ) or "warning" (2-3σ), None if no anomaly
        """
        if len(bug_series) < 4:
            return False, None, 0.0

        history = np.array(bug_series[:-1], dtype=float)
        current = float(bug_series[-1])
        mean = float(np.mean(history))
        std = float(np.std(history))

        if std < 1e-6:
            return False, None, 0.0

        z = abs(current - mean) / std

        if z > 3.0:
            return True, "critical", round(z, 2)
        elif z > 2.0:
            return True, "warning", round(z, 2)
        return False, None, round(z, 2)

    # ------------------------------------------------------------------
    # Data loading helpers
    # ------------------------------------------------------------------

    def _load_quality_weeks(self) -> list[dict]:
        """Load quality history sorted by date."""
        if not self.quality_history_file.exists():
            logger.warning("Quality history not found", extra={"file": str(self.quality_history_file)})
            return []

        data = json.loads(self.quality_history_file.read_text(encoding="utf-8"))
        weeks = data.get("weeks", [])
        return sorted(weeks, key=lambda w: w["week_date"])

    def _load_exploitable_by_product(self) -> dict[str, int]:
        """Load latest exploitable counts keyed by product name.

        History files store product_breakdown keyed by product ID (e.g. "12345").
        This method translates IDs to names using data/armorcode_id_map.json.
        If the ID map is unavailable (local dev without secret), keys are returned as-is.
        """
        if not self.exploitable_history_file.exists():
            logger.debug("Exploitable history not found", extra={"file": str(self.exploitable_history_file)})
            return {}

        data = json.loads(self.exploitable_history_file.read_text(encoding="utf-8"))
        weeks = data.get("weeks", [])
        if not weeks:
            return {}

        # Use the most recent week
        latest = sorted(weeks, key=lambda w: w["week_date"])[-1]
        product_breakdown = latest.get("metrics", {}).get("product_breakdown", {})

        # Translate product IDs → names via armorcode_id_map.json (written from ARMORCODE_ID_MAP secret)
        id_map_path = Path("data/armorcode_id_map.json")
        if id_map_path.exists():
            name_to_id: dict[str, str] = json.loads(id_map_path.read_text(encoding="utf-8"))
            id_to_name = {v: k for k, v in name_to_id.items()}
            return {id_to_name.get(pid, pid): int(info.get("total", 0)) for pid, info in product_breakdown.items()}

        # Fallback: return keys as-is (may be IDs or legacy names)
        return {k: int(info.get("total", 0)) for k, info in product_breakdown.items()}

    def _get_product_keys(self, quality_weeks: list[dict]) -> dict[str, str]:
        """Build mapping of project_key → project_name from quality history."""
        mapping: dict[str, str] = {}
        for week in quality_weeks:
            for proj in week.get("projects", []):
                key = proj.get("project_key", "")
                name = proj.get("project_name", key)
                if key and key not in mapping:
                    mapping[key] = name
        return mapping

    def _get_bug_series(self, project_key: str, quality_weeks: list[dict]) -> list[int]:
        """Extract chronological open_bugs_count series for a product."""
        series = []
        for week in quality_weeks:
            for proj in week.get("projects", []):
                if proj.get("project_key") == project_key:
                    count = proj.get("open_bugs_count", 0)
                    series.append(int(count))
                    break
        return series

    def _build_org_summary(self, products: list[ProductHealth], security_forecast: dict) -> OrgHealthSummary:
        """Aggregate per-product health into org-level summary."""
        scores = [p.health_score for p in products]
        overall = round(median(scores), 1) if scores else 0.0

        healthy = sum(1 for p in products if p.health_score >= 70)
        at_risk = sum(1 for p in products if 40 <= p.health_score < 70)
        critical = sum(1 for p in products if p.health_score < 40)

        critical_anomalies = [p.product_name for p in products if p.anomaly_severity == "critical"]
        warning_anomalies = [p.product_name for p in products if p.anomaly_severity == "warning"]

        return OrgHealthSummary(
            overall_score=overall,
            healthy_count=healthy,
            at_risk_count=at_risk,
            critical_count=critical,
            total_products=len(products),
            critical_anomalies=critical_anomalies,
            warning_anomalies=warning_anomalies,
            security_target_probability=security_forecast["target_probability"],
            security_predicted_count_june30=security_forecast["predicted_count_june30"],
            security_target_count=security_forecast["target_count"],
            security_predicted_shortfall=security_forecast["shortfall"],
            org_security_trajectory=security_forecast["trajectory"],
        )


# Self-test
if __name__ == "__main__":
    from execution.core import setup_logging

    setup_logging(level="INFO", json_output=False)

    logger.info("Health Scorer - Self Test")
    logger.info("=" * 60)

    scorer = HealthScorer()
    products, summary = scorer.score_all_products()

    logger.info(f"Org health score: {summary.overall_score}")
    logger.info(
        f"Products: {summary.healthy_count} Healthy, {summary.at_risk_count} At Risk, {summary.critical_count} Critical"
    )
    logger.info(f"Security target P: {summary.security_target_probability:.1f}%  ({summary.org_security_trajectory})")

    if summary.critical_anomalies:
        logger.info(f"CRITICAL ANOMALIES: {summary.critical_anomalies}")

    for p in products:
        anomaly_tag = f" ⚠ {p.anomaly_severity.upper()}" if p.has_anomaly and p.anomaly_severity else ""
        logger.info(
            f"  {p.product_name}: {p.health_score:.0f} ({p.health_status}) "
            f"bugs={p.current_bug_count} trend={p.bug_trend} "
            f"exploit={p.exploitable_total}{anomaly_tag}"
        )

    logger.info("=" * 60)
    logger.info("✅ Self-test PASSED")
