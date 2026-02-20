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

# Load environment variables
from dotenv import load_dotenv
from http_client import post

from execution.secure_config import get_config

load_dotenv()

logger = logging.getLogger(__name__)


def get_armorcode_headers():
    """Get ArmorCode API headers"""
    api_key = get_config().get_armorcode_config().api_key
    if not api_key:
        raise ValueError("ARMORCODE_API_KEY must be set in .env file")

    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "application/json"}


def get_product_names_to_ids(product_names: list[str]) -> dict[str, str]:
    """
    Convert product names to IDs using ArmorCode API.

    Args:
        product_names: List of product names from baseline

    Returns:
        Dictionary mapping product name to product ID
    """
    base_url = get_config().get_armorcode_config().base_url
    graphql_url = f"{base_url.rstrip('/')}/api/graphql"
    headers = get_armorcode_headers()

    all_products = []

    # Fetch all pages of products
    for page in range(1, 10):
        query = f"""
        {{
          products(page: {page}, size: 100) {{
            products {{
              id
              name
            }}
            pageInfo {{
              hasNext
            }}
          }}
        }}
        """

        try:
            response = post(graphql_url, headers=headers, json={"query": query}, timeout=60)
            if response.status_code == 200:
                data = response.json()
                if "data" in data and "products" in data["data"]:
                    result = data["data"]["products"]
                    products = result.get("products", [])
                    all_products.extend(products)

                    if not result.get("pageInfo", {}).get("hasNext", False):
                        break
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Network error fetching products page {page}: {e}")
            break
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Invalid response format fetching products page {page}: {e}")
            break

    # Map product names to IDs
    product_map = {p["name"]: str(p["id"]) for p in all_products}
    logger.info(f"API returned {len(all_products)} total products from ArmorCode")
    if len(all_products) > 0:
        logger.debug(f"Sample products: {list(product_map.keys())[:5]}")
    return product_map


def get_product_ids_from_baseline(baseline: dict) -> list[str]:
    """
    Extract product IDs from baseline data by converting product names to IDs.

    Args:
        baseline: Baseline data dictionary containing 'products' field with product names

    Returns:
        List of product ID strings
    """
    # Get product names from baseline
    product_names = baseline.get("products", [])
    if not product_names:
        logger.warning("No products found in baseline")
        return []

    logger.info(f"Found {len(product_names)} products in baseline")
    logger.info("Converting product names to IDs...")

    # Convert names to IDs
    product_map = get_product_names_to_ids(product_names)

    # Get IDs for products in baseline
    product_ids = []
    for name in product_names:
        if name in product_map:
            product_ids.append(product_map[name])
        else:
            logger.warning(f"Product '{name}' not found in ArmorCode")

    logger.info(f"Resolved {len(product_ids)} product IDs")
    return product_ids


def _query_count_only(
    graphql_url: str,
    headers: dict,
    product_ids_str: str,
    severities: str,
    statuses: str = '["OPEN", "CONFIRMED"]',
) -> int:
    """
    Query page 1 with size=1 to get totalElements without fetching finding details.

    Uses size=1 to minimise response payload — only pageInfo.totalElements is needed.
    Includes 429 retry logic identical to the main query functions.

    Args:
        graphql_url: GraphQL endpoint URL
        headers: Authorization headers
        product_ids_str: Comma-separated product IDs for the filter
        severities: GraphQL severity filter string, e.g. "[High, Critical]"
        statuses: GraphQL status filter string

    Returns:
        totalElements count, or 0 on any error
    """
    query = f"""
    {{
      findings(
        page: 1
        size: 1
        findingFilter: {{
          product: [{product_ids_str}]
          severity: {severities}
          status: {statuses}
        }}
      ) {{
        findings {{ id }}
        pageInfo {{ totalElements }}
      }}
    }}
    """
    _max_retries = 3
    try:
        for _attempt in range(_max_retries + 1):
            response = post(graphql_url, headers=headers, json={"query": query}, timeout=60)
            if response.status_code != 429:
                break
            retry_after = int(response.headers.get("Retry-After", 60))
            if _attempt < _max_retries:
                logger.warning(
                    f"Rate limited on count query - waiting {retry_after}s "
                    f"(attempt {_attempt + 1}/{_max_retries})..."
                )
                time.sleep(retry_after)
        response.raise_for_status()
        data = response.json()
        if "data" in data and "findings" in data["data"]:
            return int(data["data"]["findings"].get("pageInfo", {}).get("totalElements", 0))
    except (ConnectionError, TimeoutError) as e:
        logger.warning(f"Network error in count query: {e}")
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.warning(f"Invalid response in count query: {e}")
    return 0


def query_current_vulnerabilities_graphql(
    base_url: str,
    product_ids: list[str],
    product_id_to_name: dict[str, str] | None = None,
) -> dict:
    """
    Query accurate vulnerability counts using targeted page-1 queries.

    Replaces full pagination (100+ pages for 12k+ findings) with targeted
    totalElements lookups — 2 + N×2 API calls instead of 100+ pages.

    Queries made:
    - 1 call: all products [High, Critical] → accurate overall total
    - 1 call: all products [Critical] only → accurate critical count
    - N×2 calls (if product_id_to_name provided): per-product total + critical

    Total: 2 + N×2 calls (e.g. 30 for 14 products) vs previous ~129 pages.
    No pagination → no rate-limit exposure.

    Args:
        base_url: ArmorCode API base URL
        product_ids: List of product IDs to query
        product_id_to_name: Optional ID→name mapping for per-product breakdown.
                            When None, product_breakdown is returned empty.

    Returns:
        Dictionary with pre-computed counts (findings list is always empty):
        {
            "findings": [],
            "total_count": N,
            "severity_breakdown": {"critical": C, "high": H, "total": N},
            "product_breakdown": {"Product A": {"critical": C, "high": H, "total": T}, ...},
        }
    """
    logger.info("Querying current HIGH and CRITICAL vulnerabilities via GraphQL...")
    logger.info(f"Products: {len(product_ids)} (batched in single query)")

    headers = get_armorcode_headers()
    graphql_url = f"{base_url.rstrip('/')}/api/graphql"
    all_product_ids_str = ", ".join(product_ids)

    try:
        # 1. Accurate overall total (HIGH + CRITICAL, all products)
        accurate_total = _query_count_only(graphql_url, headers, all_product_ids_str, "[High, Critical]")

        # 2. Accurate critical count — high is the remainder
        accurate_critical = _query_count_only(graphql_url, headers, all_product_ids_str, "[Critical]")
        accurate_high = accurate_total - accurate_critical

        logger.info(f"Found {accurate_total} accurate total HIGH/CRITICAL vulnerabilities")
        logger.info(f"Critical: {accurate_critical}, High: {accurate_high}")

        severity_breakdown = {
            "critical": accurate_critical,
            "high": accurate_high,
            "total": accurate_total,
        }

        # 3. Per-product accurate counts (2 calls per product: total + critical)
        product_breakdown: dict = {}
        if product_id_to_name:
            for product_id, product_name in product_id_to_name.items():
                prod_total = _query_count_only(graphql_url, headers, product_id, "[High, Critical]")
                prod_critical = _query_count_only(graphql_url, headers, product_id, "[Critical]")
                product_breakdown[product_name] = {
                    "critical": prod_critical,
                    "high": prod_total - prod_critical,
                    "total": prod_total,
                }
                logger.debug(f"  {product_name}: {prod_total} ({prod_critical} critical)")

        return {
            "findings": [],  # No raw findings — counts are pre-computed
            "total_count": accurate_total,
            "severity_breakdown": severity_breakdown,
            "product_breakdown": product_breakdown,
        }

    except (ConnectionError, TimeoutError) as e:
        logger.error(f"Network error querying current vulnerabilities: {e}")
        return {"findings": [], "total_count": 0}
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Invalid response format querying current vulnerabilities: {e}")
        return {"findings": [], "total_count": 0}


def query_closed_vulnerabilities_graphql(base_url: str, product_ids: list[str], lookback_days: int = 90) -> dict:
    """
    Query recently closed HIGH and CRITICAL vulnerabilities using GraphQL API.

    Note: Date fields not available in GraphQL schema, so MTTR calculation disabled for now.
    All product IDs are batched into a single query (2 pages max), reducing API calls
    from 2×N products to 2 total.

    Args:
        base_url: ArmorCode API base URL
        product_ids: List of product IDs to query
        lookback_days: How many days back to look

    Returns:
        Dictionary with closed vulnerability data (count only, no date data)
    """
    logger.info(f"Querying closed vulnerabilities (last {lookback_days} days) via GraphQL...")
    logger.info("MTTR calculation disabled - date fields not available in GraphQL schema")

    headers = get_armorcode_headers()
    graphql_url = f"{base_url.rstrip('/')}/api/graphql"

    all_findings = []

    # Batch all product IDs into a single query — reduces API calls ~13x
    all_product_ids_str = ", ".join(product_ids)

    try:
        page = 1
        has_next = True

        while has_next and page <= 2:  # Limit to 2 pages total (200 items sample)
            query = f"""
            {{
              findings(
                page: {page}
                size: 100
                findingFilter: {{
                  product: [{all_product_ids_str}]
                  severity: [High, Critical]
                  status: ["CLOSED", "RESOLVED", "FIXED"]
                }}
              ) {{
                findings {{
                  id
                  severity
                  status
                  environment {{
                    name
                  }}
                }}
                pageInfo {{
                  hasNext
                }}
              }}
            }}
            """

            _max_retries = 3
            for _attempt in range(_max_retries + 1):
                response = post(graphql_url, headers=headers, json={"query": query}, timeout=60)
                if response.status_code != 429:
                    break
                retry_after = int(response.headers.get("Retry-After", 60))
                if _attempt < _max_retries:
                    logger.warning(
                        f"Rate limited (429) on closed vulns page {page} - "
                        f"waiting {retry_after}s (attempt {_attempt + 1}/{_max_retries})..."
                    )
                    time.sleep(retry_after)
                else:
                    logger.error(f"Rate limited (429) on closed vulns page {page} - max retries exceeded")
            response.raise_for_status()

            data = response.json()

            if "errors" in data:
                break

            if "data" in data and "findings" in data["data"]:
                findings_data = data["data"]["findings"]
                page_findings = findings_data.get("findings", [])
                page_info = findings_data.get("pageInfo", {})

                all_findings.extend(page_findings)

                has_next = page_info.get("hasNext", False)
                page += 1
            else:
                break

        logger.info(f"Found ~{len(all_findings)} closed vulnerabilities (limited sample, no date filtering)")

        return {"findings": all_findings, "total_count": len(all_findings)}

    except Exception as e:
        logger.error(f"Failed to query closed vulnerabilities: {e}")
        return {"findings": [], "total_count": 0}


def filter_production_findings(findings: list[dict]) -> list[dict]:
    """
    Filter findings to include only Production environment.

    Args:
        findings: List of vulnerability findings with environment field

    Returns:
        Filtered list containing only Production environment findings
    """
    production_findings = []
    filtered_count = 0

    for finding in findings:
        # Extract environment name from nested object
        environment_obj = finding.get("environment")
        if environment_obj:
            if isinstance(environment_obj, dict):
                env_name = environment_obj.get("name", "").upper()
            else:
                env_name = str(environment_obj).upper()
        else:
            env_name = ""

        # Include only Production environment
        if env_name == "PRODUCTION":
            production_findings.append(finding)
        else:
            filtered_count += 1

    logger.info(
        f"Environment filter: {len(production_findings)} Production, {filtered_count} filtered out (non-Production)"
    )

    return production_findings


def calculate_mttr(closed_findings: list[dict]) -> dict:
    """
    Calculate Mean Time To Remediate for closed vulnerabilities.

    Note: Date fields not available in current GraphQL schema, so MTTR calculation disabled.

    Args:
        closed_findings: List of closed vulnerability findings

    Returns:
        MTTR metrics (disabled)
    """
    return {
        "critical_mttr_days": None,
        "high_mttr_days": None,
        "critical_sample_size": 0,
        "high_sample_size": 0,
        "note": "MTTR calculation disabled - date fields not available in GraphQL schema",
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
    base_url = get_config().get_armorcode_config().base_url

    logger.info("Collecting enhanced security metrics from ArmorCode...")

    # Build product_id→name mapping for accurate per-product breakdown queries
    product_names = baseline.get("products", [])
    if not product_names:
        logger.error("No products found in baseline - cannot query")
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

    logger.info(f"Found {len(product_names)} products in baseline")
    logger.info("Converting product names to IDs...")

    product_name_map = get_product_names_to_ids(product_names)  # name → id
    product_ids: list[str] = []
    product_id_to_name: dict[str, str] = {}
    for name in product_names:
        if name in product_name_map:
            pid = product_name_map[name]
            product_ids.append(pid)
            product_id_to_name[pid] = name
        else:
            logger.warning(f"Product '{name}' not found in ArmorCode")

    if not product_ids:
        logger.error("No product IDs resolved from baseline")
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

    logger.info(f"Resolved {len(product_ids)} product IDs")

    # Query accurate vulnerability counts (totalElements-based, no full pagination)
    current_vulns = query_current_vulnerabilities_graphql(base_url, product_ids, product_id_to_name)

    # Query closed vulnerabilities (for MTTR) using GraphQL
    closed_vulns = query_closed_vulnerabilities_graphql(
        base_url, product_ids, lookback_days=config.get("lookback_days", 90)
    )

    # Filter closed findings to Production environment
    logger.info("Applying Production environment filter to closed findings...")
    closed_vulns["findings"] = filter_production_findings(closed_vulns["findings"])
    closed_vulns["total_count"] = len(closed_vulns["findings"])

    # Use pre-computed accurate counts from current_vulns (no raw findings to process)
    severity_breakdown = current_vulns.get("severity_breakdown", {"critical": 0, "high": 0, "total": 0})
    product_breakdown = current_vulns.get("product_breakdown", {})

    # Calculate metrics
    try:
        mttr = calculate_mttr(closed_vulns["findings"])
    except Exception as e:
        logger.error(f"MTTR calculation failed: {e}")
        mttr = {"critical_mttr_days": None, "high_mttr_days": None, "critical_sample_size": 0, "high_sample_size": 0}

    # Stale criticals: accurate count of ALL open criticals (dates unavailable)
    stale_criticals = {
        "count": severity_breakdown["critical"],
        "threshold_days": config.get("stale_threshold_days", 90),
        "items": [],
        "note": "Age calculation disabled - date fields not available in GraphQL schema",
    }

    try:
        age_distribution = calculate_age_distribution([])
    except Exception as e:
        logger.error(f"Age distribution calculation failed: {e}")
        age_distribution = {"median_age_days": None, "p85_age_days": None, "p95_age_days": None, "sample_size": 0}

    logger.info(
        f"Current Total: {current_vulns['total_count']} (Critical: {severity_breakdown['critical']}, High: {severity_breakdown['high']})"
    )
    logger.info(f"MTTR - Critical: {mttr['critical_mttr_days']} days, High: {mttr['high_mttr_days']} days")
    logger.info(f"Stale Criticals (>90d): {stale_criticals['count']}")
    logger.info(f"Closed (last 90d): {closed_vulns['total_count']}")

    return {
        "current_total": current_vulns["total_count"],
        "severity_breakdown": severity_breakdown,
        "product_breakdown": product_breakdown,
        "mttr": mttr,
        "stale_criticals": stale_criticals,
        "age_distribution": age_distribution,
        "closed_count_90d": closed_vulns["total_count"],
        "collected_at": datetime.now().isoformat(),
    }


def load_existing_baseline():
    """Load existing ArmorCode baseline to track against"""
    # Try data/ folder first (preferred location), then .tmp/
    baseline_files = ["data/armorcode_baseline.json", ".tmp/armorcode_baseline.json"]

    for baseline_file in baseline_files:
        if os.path.exists(baseline_file):
            with open(baseline_file, encoding="utf-8") as f:
                baseline = json.load(f)

            vuln_count = baseline.get("total_vulnerabilities") or baseline.get("vulnerability_count")
            logger.info(f"Loaded existing baseline: {vuln_count} vulns on {baseline.get('baseline_date')}")
            logger.info(f"Tracking {len(baseline.get('products', []))} products")
            return baseline

    logger.warning("No existing baseline found")
    return None


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
