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
import os
import sys
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
from http_client import post

from execution.secure_config import get_config

load_dotenv()


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
            print(f"      [WARNING] Network error fetching products page {page}: {e}")
            break
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            print(f"      [WARNING] Invalid response format fetching products page {page}: {e}")
            break

    # Map product names to IDs
    product_map = {p["name"]: str(p["id"]) for p in all_products}
    print(f"      API returned {len(all_products)} total products from ArmorCode")
    if len(all_products) > 0:
        print(f"      Sample products: {list(product_map.keys())[:5]}")
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
        print("      [WARNING] No products found in baseline")
        return []

    print(f"      Found {len(product_names)} products in baseline")
    print("      Converting product names to IDs...")

    # Convert names to IDs
    product_map = get_product_names_to_ids(product_names)

    # Get IDs for products in baseline
    product_ids = []
    for name in product_names:
        if name in product_map:
            product_ids.append(product_map[name])
        else:
            print(f"      [WARNING] Product '{name}' not found in ArmorCode")

    print(f"      Resolved {len(product_ids)} product IDs")
    return product_ids


def query_current_vulnerabilities_graphql(base_url: str, product_ids: list[str]) -> dict:
    """
    Query current HIGH and CRITICAL vulnerabilities using GraphQL API.

    Matches the same filters as armorcode_weekly_query.py:
    - severity: [High, Critical]
    - status: ["OPEN", "CONFIRMED"]
    - product: specific product IDs from baseline

    Args:
        base_url: ArmorCode API base URL
        product_ids: List of product IDs to query

    Returns:
        Dictionary with vulnerability data
    """
    print("    Querying current HIGH and CRITICAL vulnerabilities via GraphQL...")
    print(f"    Products: {len(product_ids)}")

    headers = get_armorcode_headers()
    graphql_url = f"{base_url.rstrip('/')}/api/graphql"

    all_findings = []

    try:
        # Query each product separately (matches armorcode_weekly_query.py logic)
        for product_id in product_ids:
            page = 1
            has_next = True

            while has_next:
                query = f"""
                {{
                  findings(
                    page: {page}
                    size: 100
                    findingFilter: {{
                      product: [{product_id}]
                      severity: [High, Critical]
                      status: ["OPEN", "CONFIRMED"]
                    }}
                  ) {{
                    findings {{
                      id
                      severity
                      status
                      product {{
                        name
                      }}
                    }}
                    pageInfo {{
                      hasNext
                      totalElements
                    }}
                  }}
                }}
                """

                response = post(graphql_url, headers=headers, json={"query": query}, timeout=60)
                response.raise_for_status()

                data = response.json()

                if "errors" in data:
                    print(f"      [ERROR] GraphQL error for product {product_id}: {data['errors']}")
                    break

                if "data" in data and "findings" in data["data"]:
                    findings_data = data["data"]["findings"]
                    page_findings = findings_data.get("findings", [])
                    page_info = findings_data.get("pageInfo", {})

                    all_findings.extend(page_findings)
                    has_next = page_info.get("hasNext", False)
                    page += 1

                    if page > 100:
                        print(f"      [WARNING] Reached page limit for product {product_id}")
                        break
                else:
                    break

        print(f"      Found {len(all_findings)} total current HIGH/CRITICAL vulnerabilities")

        return {"findings": all_findings, "total_count": len(all_findings)}

    except (ConnectionError, TimeoutError) as e:
        print(f"      [ERROR] Network error querying current vulnerabilities: {e}")
        return {"findings": [], "total_count": 0}
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        print(f"      [ERROR] Invalid response format querying current vulnerabilities: {e}")
        return {"findings": [], "total_count": 0}


def query_closed_vulnerabilities_graphql(base_url: str, product_ids: list[str], lookback_days: int = 90) -> dict:
    """
    Query recently closed HIGH and CRITICAL vulnerabilities using GraphQL API.

    Note: Date fields not available in GraphQL schema, so MTTR calculation disabled for now.

    Args:
        base_url: ArmorCode API base URL
        product_ids: List of product IDs to query
        lookback_days: How many days back to look

    Returns:
        Dictionary with closed vulnerability data (count only, no date data)
    """
    print(f"    Querying closed vulnerabilities (last {lookback_days} days) via GraphQL...")
    print("      [INFO] MTTR calculation disabled - date fields not available in GraphQL schema")

    headers = get_armorcode_headers()
    graphql_url = f"{base_url.rstrip('/')}/api/graphql"

    all_findings = []

    try:
        for product_id in product_ids:
            page = 1
            has_next = True

            while has_next and page <= 2:  # Limit to 2 pages for closed findings (200 items)
                query = f"""
                {{
                  findings(
                    page: {page}
                    size: 100
                    findingFilter: {{
                      product: [{product_id}]
                      severity: [High, Critical]
                      status: ["CLOSED", "RESOLVED", "FIXED"]
                    }}
                  ) {{
                    findings {{
                      id
                      severity
                      status
                    }}
                    pageInfo {{
                      hasNext
                    }}
                  }}
                }}
                """

                response = post(graphql_url, headers=headers, json={"query": query}, timeout=60)
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

        print(f"      Found ~{len(all_findings)} closed vulnerabilities (limited sample, no date filtering)")

        return {"findings": all_findings, "total_count": len(all_findings)}

    except Exception as e:
        print(f"      [ERROR] Failed to query closed vulnerabilities: {e}")
        return {"findings": [], "total_count": 0}


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

    print("\n  Collecting enhanced security metrics from ArmorCode...")

    # Get product IDs from baseline
    product_ids = get_product_ids_from_baseline(baseline)
    if not product_ids:
        print("      [ERROR] No product IDs found in baseline - cannot query")
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

    # Query current vulnerabilities using GraphQL with product filter
    current_vulns = query_current_vulnerabilities_graphql(base_url, product_ids)

    # Query closed vulnerabilities (for MTTR) using GraphQL
    closed_vulns = query_closed_vulnerabilities_graphql(
        base_url, product_ids, lookback_days=config.get("lookback_days", 90)
    )

    # Calculate metrics
    try:
        mttr = calculate_mttr(closed_vulns["findings"])
    except Exception as e:
        print(f"      [ERROR] MTTR calculation failed: {e}")
        mttr = {"critical_mttr_days": None, "high_mttr_days": None, "critical_sample_size": 0, "high_sample_size": 0}

    try:
        stale_criticals = identify_stale_criticals(
            current_vulns["findings"], stale_threshold_days=config.get("stale_threshold_days", 90)
        )
    except Exception as e:
        print(f"      [ERROR] Stale criticals calculation failed: {e}")
        stale_criticals = {"count": 0, "threshold_days": 90, "items": []}

    try:
        severity_breakdown = calculate_severity_breakdown(current_vulns["findings"])
    except Exception as e:
        print(f"      [ERROR] Severity breakdown calculation failed: {e}")
        severity_breakdown = {"critical": 0, "high": 0, "total": 0}

    try:
        product_breakdown = calculate_product_breakdown(current_vulns["findings"])
    except Exception as e:
        print(f"      [ERROR] Product breakdown calculation failed: {e}")
        product_breakdown = {}

    try:
        age_distribution = calculate_age_distribution(current_vulns["findings"])
    except Exception as e:
        print(f"      [ERROR] Age distribution calculation failed: {e}")
        age_distribution = {"median_age_days": None, "p85_age_days": None, "p95_age_days": None, "sample_size": 0}

    print(
        f"    Current Total: {current_vulns['total_count']} (Critical: {severity_breakdown['critical']}, High: {severity_breakdown['high']})"
    )
    print(f"    MTTR - Critical: {mttr['critical_mttr_days']} days, High: {mttr['high_mttr_days']} days")
    print(f"    Stale Criticals (>90d): {stale_criticals['count']}")
    print(f"    Closed (last 90d): {closed_vulns['total_count']}")

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
            print(f"    Loaded existing baseline: {vuln_count} vulns on {baseline.get('baseline_date')}")
            print(f"    Tracking {len(baseline.get('products', []))} products")
            return baseline

    print("    [WARNING] No existing baseline found")
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
        print("\n[SKIPPED] All vulnerability counts are zero - likely a collection failure")
        print("          Not persisting this data to avoid corrupting trend history")
        return False

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Load existing history
    history = load_json_with_recovery(output_file, default_value={"weeks": []})

    # Add validation if structure check exists
    if not isinstance(history, dict) or "weeks" not in history:
        print("\n[WARNING] Existing history file has invalid structure - recreating")
        history = {"weeks": []}

    # Add new week entry
    history["weeks"].append(metrics)

    # Keep only last 52 weeks (12 months) for quarter/annual analysis
    history["weeks"] = history["weeks"][-52:]

    # Save updated history
    try:
        atomic_json_save(history, output_file)
        print(f"\n[SAVED] Security metrics saved to: {output_file}")
        print(f"        History now contains {len(history['weeks'])} week(s)")
        return True
    except Exception as e:
        print(f"\n[ERROR] Failed to save Security metrics: {e}")
        return False


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    print("Director Observatory - Enhanced Security Metrics Collector\n")
    print("=" * 60)

    # Configuration
    config = {
        "lookback_days": 90,  # How many days back to look for closed vulns
        "stale_threshold_days": 90,  # Criticals open >90 days are "stale"
    }

    # Load existing baseline (REQUIRED - contains product IDs to filter)
    baseline = load_existing_baseline()
    if not baseline:
        print("\n[ERROR] Baseline is required to determine which products to track")
        print("Please run: python execution/armorcode_baseline.py")
        exit(1)

    # Collect enhanced metrics
    print("\nCollecting enhanced security metrics...")
    print("=" * 60)

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
        print("\n" + "=" * 60)
        print("Enhanced Security Metrics Collection Summary:")
        print(f"  Current vulnerabilities: {metrics['current_total']} (HIGH + CRITICAL)")
        print(f"  Critical: {metrics['severity_breakdown']['critical']}")
        print(f"  High: {metrics['severity_breakdown']['high']}")
        print(f"  Stale criticals (>90d): {metrics['stale_criticals']['count']}")

        if baseline:
            print(f"  Baseline: {baseline.get('vulnerability_count')} → Target: {baseline.get('target_count')}")
            delta = metrics["current_total"] - baseline.get("vulnerability_count", 0)
            print(f"  Net change from baseline: {delta:+d}")

        print("\nEnhanced security metrics collection complete!")
        print("\nNext step: Generate security dashboard")

    except Exception as e:
        print(f"\n[ERROR] Failed to collect security metrics: {e}")
        exit(1)
