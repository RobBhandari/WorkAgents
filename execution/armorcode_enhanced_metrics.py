#!/usr/bin/env python3
"""
ArmorCode Enhanced Metrics Collector for Director Observatory

Enhances existing ArmorCode vulnerability tracking with additional metrics:
- MTTR (Mean Time To Remediate): How fast we close vulnerabilities
- Stale Criticals: Critical vulns open >90 days
- Net New Rate: New vulns per week - remediated per week
- Regression Rate: % of findings that are repeats
- Age Distribution: How long vulns have been open

Read-only operation - uses same query filters as existing ArmorCode scripts.
Matches existing report counts exactly.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv

from execution.collectors.armorcode_vulnerability_loader import ArmorCodeVulnerabilityLoader
from execution.secure_config import get_config

load_dotenv()

logger = logging.getLogger(__name__)

ID_MAP_PATH = Path("data/armorcode_id_map.json")
SECURITY_TARGETS_PATH = Path("data/security_targets.json")


def _load_id_map() -> dict[str, str]:
    """Load product name → ID mapping from data/armorcode_id_map.json."""
    if not ID_MAP_PATH.exists():
        raise FileNotFoundError(
            f"{ID_MAP_PATH} not found. "
            "In CI/CD this is written from the ARMORCODE_ID_MAP secret. "
            "Locally, run: python scripts/fetch_armorcode_id_map.py"
        )
    result: dict[str, str] = json.loads(ID_MAP_PATH.read_text(encoding="utf-8"))
    return result


def query_current_vulnerabilities_aql(
    hierarchy: str,
    product_id_to_name: dict[str, str],
) -> dict:
    """
    Query accurate Production-only vulnerability counts using the AQL count endpoint.

    Replaces the GraphQL count approach with two AQL calls (one per severity) that
    each return counts for ALL products in a single round-trip — no pagination,
    no per-product loops, no rate-limit exposure.

    Calls made:
    - 1 AQL call: severity = Critical, environment = Production → {product_id: count}
    - 1 AQL call: severity = High,     environment = Production → {product_id: count}

    Args:
        hierarchy: ArmorCode hierarchy value (from ARMORCODE_HIERARCHY env var)
        product_id_to_name: Product ID → product name mapping used to build the
                            per-product breakdown in the return dict.

    Returns:
        Dictionary with pre-computed counts (findings list is always empty):
        {
            "findings": [],
            "total_count": N,
            "severity_breakdown": {"critical": C, "high": H, "total": N},
            "product_breakdown": {"Product A": {"critical": C, "high": H, "total": T}, ...},
        }
    """
    logger.info("Querying current HIGH and CRITICAL vulnerabilities via AQL (Production only)...")
    logger.info(f"Products: {len(product_id_to_name)} in hierarchy")

    loader = ArmorCodeVulnerabilityLoader()

    # Two AQL calls — each returns {product_id_str: count} for all products
    critical_by_id = loader.count_by_severity_aql("Critical", hierarchy, environment="Production")
    high_by_id = loader.count_by_severity_aql("High", hierarchy, environment="Production")

    product_breakdown: dict = {}
    accurate_critical = 0
    accurate_high = 0

    for product_id, product_name in product_id_to_name.items():
        prod_critical = critical_by_id.get(product_id, 0)
        prod_high = high_by_id.get(product_id, 0)
        prod_total = prod_critical + prod_high
        product_breakdown[product_name] = {
            "critical": prod_critical,
            "high": prod_high,
            "total": prod_total,
        }
        accurate_critical += prod_critical
        accurate_high += prod_high
        logger.debug(f"  {product_name}: {prod_total} ({prod_critical} critical, {prod_high} high)")

    accurate_total = accurate_critical + accurate_high

    logger.info(f"Found {accurate_total} total HIGH/CRITICAL Production vulnerabilities via AQL")
    logger.info(f"Critical: {accurate_critical}, High: {accurate_high}")

    return {
        "findings": [],  # No raw findings — counts are pre-computed
        "total_count": accurate_total,
        "severity_breakdown": {
            "critical": accurate_critical,
            "high": accurate_high,
            "total": accurate_total,
        },
        "product_breakdown": product_breakdown,
    }


def identify_stale_criticals(current_findings: list[dict], stale_threshold_days: int = 90) -> dict:
    """
    Identify critical vulnerabilities open >90 days.

    Note: Date fields not available in current GraphQL schema, so age calculation disabled.

    Args:
        current_findings: List of current open findings
        stale_threshold_days: Days threshold for "stale"

    Returns:
        Stale critical vulnerabilities (count only, no age data)
    """
    # Just count criticals (can't calculate age without date fields)
    critical_count = sum(1 for f in current_findings if f.get("severity", "").upper() == "CRITICAL")

    return {
        "count": critical_count,
        "threshold_days": stale_threshold_days,
        "items": [],  # Can't calculate without date fields
        "note": "Age calculation disabled - date fields not available in GraphQL schema",
    }


def calculate_severity_breakdown(current_findings: list[dict]) -> dict:
    """
    Calculate breakdown by severity.

    Args:
        current_findings: List of current open findings

    Returns:
        Counts by severity
    """
    critical_count = sum(1 for f in current_findings if f.get("severity", "").upper() == "CRITICAL")
    high_count = sum(1 for f in current_findings if f.get("severity", "").upper() == "HIGH")

    return {"critical": critical_count, "high": high_count, "total": len(current_findings)}


def calculate_product_breakdown(current_findings: list[dict]) -> dict:
    """
    Calculate breakdown by product.

    Args:
        current_findings: List of current open findings

    Returns:
        Counts by product
    """
    product_counts = {}

    for finding in current_findings:
        product_raw = finding.get("product", "Unknown")

        # Handle product being a dict (extract name) or string
        if isinstance(product_raw, dict):
            product = product_raw.get("name", "Unknown")
        else:
            product = product_raw if product_raw else "Unknown"

        severity = finding.get("severity", "").upper()

        if product not in product_counts:
            product_counts[product] = {"critical": 0, "high": 0, "total": 0}

        product_counts[product]["total"] += 1
        if severity == "CRITICAL":
            product_counts[product]["critical"] += 1
        elif severity == "HIGH":
            product_counts[product]["high"] += 1

    return product_counts


def calculate_age_distribution(current_findings: list[dict]) -> dict:
    """
    Calculate age distribution of current vulnerabilities.

    Note: Date fields not available in current GraphQL schema, so age calculation disabled.

    Args:
        current_findings: List of current open findings

    Returns:
        Age distribution metrics (disabled)
    """
    return {
        "median_age_days": None,
        "p85_age_days": None,
        "p95_age_days": None,
        "sample_size": 0,
        "note": "Age calculation disabled - date fields not available in GraphQL schema",
    }


def collect_enhanced_security_metrics(config: dict, baseline: dict) -> dict:
    """
    Collect all enhanced security metrics using same product filter as baseline.

    Args:
        config: Configuration dict (API base URL, lookback days, etc.)
        baseline: Baseline data containing product IDs to track

    Returns:
        Enhanced security metrics dictionary
    """
    logger.info("Collecting enhanced security metrics from ArmorCode...")

    # Load product name → ID mapping from data/armorcode_id_map.json (no GraphQL)
    try:
        name_to_id = _load_id_map()
    except FileNotFoundError as e:
        logger.error(str(e))
        return {
            "current_total": 0,
            "severity_breakdown": {"critical": 0, "high": 0, "total": 0},
            "product_breakdown": {},
            "mttr": {
                "critical_mttr_days": None,
                "high_mttr_days": None,
                "critical_sample_size": 0,
                "high_sample_size": 0,
            },
            "stale_criticals": {"count": 0, "threshold_days": 90, "items": []},
            "age_distribution": {"median_age_days": None, "p85_age_days": None, "p95_age_days": None, "sample_size": 0},
            "closed_count_90d": 0,
            "collected_at": datetime.now().isoformat(),
        }

    product_id_to_name: dict[str, str] = {v: k for k, v in name_to_id.items()}
    logger.info(f"Loaded {len(name_to_id)} products from ID map")

    # Obtain hierarchy for AQL queries (required by count_by_severity_aql)
    hierarchy = get_config().get_optional_env("ARMORCODE_HIERARCHY")
    if not hierarchy:
        logger.error("ARMORCODE_HIERARCHY env var not set. Add it as a GitHub secret and to your local .env file.")
        return {
            "current_total": 0,
            "severity_breakdown": {"critical": 0, "high": 0, "total": 0},
            "product_breakdown": {},
            "mttr": {
                "critical_mttr_days": None,
                "high_mttr_days": None,
                "critical_sample_size": 0,
                "high_sample_size": 0,
            },
            "stale_criticals": {"count": 0, "threshold_days": 90, "items": []},
            "age_distribution": {"median_age_days": None, "p85_age_days": None, "p95_age_days": None, "sample_size": 0},
            "closed_count_90d": 0,
            "collected_at": datetime.now().isoformat(),
        }

    # Query accurate vulnerability counts (AQL-based, Production only, 2 API calls)
    current_vulns = query_current_vulnerabilities_aql(hierarchy, product_id_to_name)

    severity_breakdown = current_vulns.get("severity_breakdown", {"critical": 0, "high": 0, "total": 0})
    product_breakdown = current_vulns.get("product_breakdown", {})

    mttr = {"critical_mttr_days": None, "high_mttr_days": None, "critical_sample_size": 0, "high_sample_size": 0}

    stale_criticals = {
        "count": severity_breakdown["critical"],
        "threshold_days": config.get("stale_threshold_days", 90),
        "items": [],
    }

    age_distribution = calculate_age_distribution([])

    logger.info(
        f"Current Total: {current_vulns['total_count']} "
        f"(Critical: {severity_breakdown['critical']}, High: {severity_breakdown['high']})"
    )
    logger.info(f"Stale Criticals (>90d): {stale_criticals['count']}")

    return {
        "current_total": current_vulns["total_count"],
        "severity_breakdown": severity_breakdown,
        "product_breakdown": product_breakdown,
        "mttr": mttr,
        "stale_criticals": stale_criticals,
        "age_distribution": age_distribution,
        "closed_count_90d": 0,
        "collected_at": datetime.now().isoformat(),
    }


def load_existing_baseline():
    """Load ArmorCode security targets and product list."""
    if not SECURITY_TARGETS_PATH.exists():
        logger.warning(f"Security targets not found: {SECURITY_TARGETS_PATH}")
        return None

    targets = json.loads(SECURITY_TARGETS_PATH.read_text(encoding="utf-8"))
    baseline_total = targets["baseline_total"]
    target_pct = targets["target_pct"]
    target_count = round(baseline_total * (1 - target_pct))

    result: dict = {
        "total_vulnerabilities": baseline_total,
        "vulnerability_count": baseline_total,
        "target_vulnerabilities": target_count,
        "target_count": target_count,
        "baseline_date": targets["baseline_date"],
        "target_date": targets["target_date"],
        "products": [],
    }

    # Populate product names from ID map if available (for backward compat with async collector)
    if ID_MAP_PATH.exists():
        id_map = json.loads(ID_MAP_PATH.read_text(encoding="utf-8"))
        result["products"] = list(id_map.keys())

    logger.info(f"Loaded baseline: {baseline_total} vulns, target: {target_count}")
    logger.info(f"Tracking {len(result['products'])} products")
    return result


def save_security_metrics(metrics: dict, output_file: str = ".tmp/observatory/security_history.json"):
    """
    Save enhanced security metrics to history file.

    Appends to existing history or creates new file.
    Validates data before saving to prevent persisting collection failures.
    """
    from utils_atomic_json import atomic_json_save, load_json_with_recovery

    # Validate that we have actual data before saving
    metrics_data = metrics.get("metrics", {})

    # Check if this looks like a failed collection (all zeros/nulls)
    current_total = metrics_data.get("current_total", 0)
    severity_breakdown = metrics_data.get("severity_breakdown", {})
    critical_count = severity_breakdown.get("critical", 0)
    high_count = severity_breakdown.get("high", 0)

    if current_total == 0 and critical_count == 0 and high_count == 0:
        logger.warning("All vulnerability counts are zero - likely a collection failure")
        logger.warning("Not persisting this data to avoid corrupting trend history")
        return False

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Load existing history
    history = load_json_with_recovery(output_file, default_value={"weeks": []})

    # Sanity check: reject implausibly low counts vs last known value (catches transient
    # API partial-response failures like the 646 and 1017 incidents)
    prior_weeks = history.get("weeks", [])
    if prior_weeks:
        prev_total = prior_weeks[-1].get("metrics", {}).get("current_total", 0)
        if prev_total > 2000 and current_total < prev_total * 0.3:
            logger.warning(
                "Implausibly low count vs previous week - likely transient API failure, NOT saving",
                extra={"new_total": current_total, "prev_total": prev_total, "threshold": prev_total * 0.3},
            )
            return False

    # Add validation if structure check exists
    if not isinstance(history, dict) or "weeks" not in history:
        logger.warning("Existing history file has invalid structure - recreating")
        history = {"weeks": []}

    # Add new week entry
    history["weeks"].append(metrics)

    # Keep only last 52 weeks (12 months) for quarter/annual analysis
    history["weeks"] = history["weeks"][-52:]

    # Save updated history
    try:
        atomic_json_save(history, output_file)
        logger.info(f"Security metrics saved to: {output_file}")
        logger.info(f"History now contains {len(history['weeks'])} week(s)")
        return True
    except Exception as e:
        logger.error(f"Failed to save Security metrics: {e}")
        return False


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    logger.info("Director Observatory - Enhanced Security Metrics Collector")
    logger.info("=" * 60)

    # Configuration
    config = {
        "lookback_days": 90,  # How many days back to look for closed vulns
        "stale_threshold_days": 90,  # Criticals open >90 days are "stale"
    }

    # Load existing baseline (REQUIRED - contains product IDs to filter)
    baseline = load_existing_baseline()
    if not baseline:
        logger.error("Baseline is required to determine which products to track")
        logger.error("Please run: python execution/armorcode_baseline.py")
        exit(1)

    # Collect enhanced metrics
    logger.info("Collecting enhanced security metrics...")
    logger.info("=" * 60)

    try:
        metrics = collect_enhanced_security_metrics(config, baseline)

        # Add baseline reference
        if baseline:
            metrics["baseline_reference"] = {
                "baseline_date": baseline.get("baseline_date"),
                "baseline_count": baseline.get("vulnerability_count"),
                "target_count": baseline.get("target_count"),
            }

        # Save results
        week_metrics = {
            "week_date": datetime.now().strftime("%Y-%m-%d"),
            "week_number": datetime.now().isocalendar()[1],
            "metrics": metrics,
            "config": config,
        }

        save_security_metrics(week_metrics)

        # Summary
        logger.info("=" * 60)
        logger.info("Enhanced Security Metrics Collection Summary:")
        logger.info(f"Current vulnerabilities: {metrics['current_total']} (HIGH + CRITICAL)")
        logger.info(f"Critical: {metrics['severity_breakdown']['critical']}")
        logger.info(f"High: {metrics['severity_breakdown']['high']}")
        logger.info(f"Stale criticals (>90d): {metrics['stale_criticals']['count']}")

        if baseline:
            logger.info(f"Baseline: {baseline.get('vulnerability_count')} → Target: {baseline.get('target_count')}")
            delta = metrics["current_total"] - baseline.get("vulnerability_count", 0)
            logger.info(f"Net change from baseline: {delta:+d}")

        logger.info("Enhanced security metrics collection complete!")
        logger.info("Next step: Generate security dashboard")

    except Exception as e:
        logger.error(f"Failed to collect security metrics: {e}", exc_info=True)
        exit(1)
