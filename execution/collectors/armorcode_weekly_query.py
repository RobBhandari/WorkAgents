"""
ArmorCode Weekly Query - Fetch Current State and Compare to Baseline

Queries current vulnerability counts and compares against baseline
to track progress towards 70% reduction goal.
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from http_client import post

from execution.core.secure_config import get_config

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_baseline(baseline_file: str = ".tmp/armorcode_baseline.json") -> dict[str, Any]:
    """
    Load vulnerability baseline data from JSON file.

    Baseline is used to calculate progress towards 70% reduction target.
    Contains initial vulnerability counts and timestamp.

    :param baseline_file: Path to baseline JSON file (default: .tmp/armorcode_baseline.json)
    :returns: Dictionary with baseline data::

        {
            "baseline_date": str,           # ISO timestamp
            "total_vulnerabilities": int,   # Total vulns at baseline
            "by_product": dict,             # Per-product counts
            "by_severity": dict             # Severity breakdown
        }

    :raises FileNotFoundError: If baseline file doesn't exist

    Example:
        >>> baseline = load_baseline()
        >>> print(f"Baseline: {baseline['total_vulnerabilities']} vulnerabilities")
    """
    if not os.path.exists(baseline_file):
        raise FileNotFoundError(f"Baseline file not found: {baseline_file}")

    with open(baseline_file) as f:
        baseline: dict[str, Any] = json.load(f)

    logger.info(f"Loaded baseline from {baseline_file}")
    logger.info(f"Baseline date: {baseline.get('baseline_date')}")
    logger.info(f"Baseline total: {baseline.get('total_vulnerabilities')}")

    return baseline


def get_product_ids(api_key: str, base_url: str, product_names: list[str]) -> list[dict[str, str]]:
    """
    Get ArmorCode product IDs for specified product names via GraphQL.

    Queries ArmorCode GraphQL API with pagination to retrieve all products,
    then filters to requested product names.

    :param api_key: ArmorCode API key (Bearer token)
    :param base_url: ArmorCode base URL (e.g., https://company.armorcode.com)
    :param product_names: List of product names to lookup
    :returns: List of product dictionaries with name and ID::

        [
            {"name": "Product A", "id": "uuid-1"},
            {"name": "Product B", "id": "uuid-2"}
        ]

    :raises requests.RequestException: If API request fails

    Example:
        >>> products = get_product_ids(api_key, base_url, ["WebApp", "MobileApp"])
        >>> len(products)
        2
    """
    logger.info("Fetching product IDs...")

    graphql_url = f"{base_url.rstrip('/')}/api/graphql"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    all_products = []

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
            else:
                break

        except Exception as e:
            logger.error(f"Error fetching products: {e}")
            break

    product_map = {p["name"]: p["id"] for p in all_products}

    product_data = []
    for name in product_names:
        if name in product_map:
            product_data.append({"name": name, "id": product_map[name]})
        else:
            logger.warning(f"Product not found: {name}")

    return product_data


def fetch_current_findings(api_key: str, base_url: str, product_id: str, product_name: str) -> list[dict[str, Any]]:
    """Fetch current HIGH+CRITICAL findings with OPEN+CONFIRMED status."""

    graphql_url = f"{base_url.rstrip('/')}/api/graphql"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    findings = []
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
            }}
            pageInfo {{
              hasNext
              totalElements
            }}
          }}
        }}
        """

        try:
            response = post(graphql_url, headers=headers, json={"query": query}, timeout=60)

            if response.status_code == 200:
                data = response.json()

                if "errors" in data:
                    logger.error(f"GraphQL error for {product_name}: {data['errors']}")
                    break

                if "data" in data and "findings" in data["data"]:
                    findings_data = data["data"]["findings"]
                    page_findings = findings_data.get("findings", [])
                    page_info = findings_data.get("pageInfo", {})

                    findings.extend(page_findings)
                    has_next = page_info.get("hasNext", False)

                    page += 1

                    if page > 100:
                        logger.warning(f"Reached page limit for {product_name}")
                        break
                else:
                    break
            else:
                logger.error(f"HTTP {response.status_code} for {product_name}")
                break

        except Exception as e:
            logger.error(f"Error fetching findings for {product_name}: {e}")
            break

    return findings


def query_current_state(baseline: dict) -> dict[str, Any]:
    """Query current vulnerability counts for all products in baseline."""
    api_key = get_config().get_armorcode_config().api_key
    base_url = get_config().get_armorcode_config().base_url

    if not api_key:
        raise ValueError("ARMORCODE_API_KEY not set")

    product_names = baseline.get("products", [])

    logger.info("=" * 70)
    logger.info("ARMORCODE WEEKLY QUERY")
    logger.info("=" * 70)
    logger.info(f"Query Date: {datetime.now().strftime('%Y-%m-%d')}")
    logger.info(f"Products: {len(product_names)}")

    # Get product IDs
    product_data = get_product_ids(api_key, base_url, product_names)

    # Fetch current findings for each product
    current_counts = {}
    all_findings = []

    for product in product_data:
        product_name = product["name"]
        product_id = product["id"]

        logger.info(f"Querying: {product_name}")
        findings = fetch_current_findings(api_key, base_url, product_id, product_name)

        # Count by severity
        current_counts[product_name] = {"HIGH": 0, "CRITICAL": 0, "total": 0}

        for finding in findings:
            severity = finding.get("severity", "").upper()
            if severity == "HIGH":
                current_counts[product_name]["HIGH"] += 1
            elif severity == "CRITICAL":
                current_counts[product_name]["CRITICAL"] += 1
            current_counts[product_name]["total"] += 1

        all_findings.extend(findings)
        logger.info(f"  {product_name}: {current_counts[product_name]['total']}")

    # Calculate summary
    current_total = len(all_findings)
    current_critical = sum(p.get("CRITICAL", 0) for p in current_counts.values())
    current_high = sum(p.get("HIGH", 0) for p in current_counts.values())

    logger.info("=" * 70)
    logger.info("CURRENT STATE SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total: {current_total}")
    logger.info(f"  CRITICAL: {current_critical}")
    logger.info(f"  HIGH: {current_high}")

    return {
        "query_date": datetime.now().isoformat(),
        "total_vulnerabilities": current_total,
        "by_product": current_counts,
        "summary": {
            "total_critical": current_critical,
            "total_high": current_high,
            "products_tracked": len(current_counts),
        },
    }


def calculate_progress(baseline: dict, current: dict) -> dict[str, Any]:
    """Calculate progress metrics comparing current state to baseline."""
    baseline_total = baseline.get("total_vulnerabilities", 0)
    current_total = current.get("total_vulnerabilities", 0)
    reduction_goal = baseline.get("reduction_goal", 0.70)

    # Calculate changes
    change = baseline_total - current_total
    change_percent = (change / baseline_total * 100) if baseline_total > 0 else 0

    # Calculate goal
    target_reduction = int(baseline_total * reduction_goal)
    target_remaining = baseline_total - target_reduction

    # Calculate progress towards goal
    progress_towards_goal = (change / target_reduction * 100) if target_reduction > 0 else 0

    # Days tracking
    created_at = baseline.get("created_at")
    if not created_at:
        raise ValueError("Baseline missing 'created_at' field")
    baseline_date = datetime.fromisoformat(created_at)
    current_date = datetime.now()
    days_tracking = (current_date - baseline_date).days

    # Target date
    target_date_str = baseline.get("target_date", "")
    if target_date_str:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        days_remaining = (target_date - current_date).days
    else:
        days_remaining = 0

    reduction_goal_percent = int(reduction_goal * 100)

    progress = {
        "baseline_total": baseline_total,
        "current_total": current_total,
        "change": change,
        "change_percent": round(change_percent, 1),
        "reduction_goal_percent": reduction_goal_percent,
        "target_reduction": target_reduction,
        "target_remaining": target_remaining,
        "progress_towards_goal": round(progress_towards_goal, 1),
        "days_tracking": days_tracking,
        "days_remaining": days_remaining,
        "on_track": change >= 0,  # Positive change means reduction
    }

    logger.info("=" * 70)
    logger.info("PROGRESS METRICS")
    logger.info("=" * 70)
    logger.info(f"Baseline: {baseline_total} → Current: {current_total}")
    logger.info(f"Change: {change} ({change_percent:+.1f}%)")
    logger.info(f"Goal: {reduction_goal_percent}% reduction ({target_reduction} vulnerabilities)")
    logger.info(f"Target Remaining: {target_remaining}")
    logger.info(f"Progress: {progress_towards_goal:.1f}% towards goal")
    logger.info(f"Days Tracking: {days_tracking} | Days Remaining: {days_remaining}")

    return progress


def main() -> dict[str, Any]:
    """Main execution."""
    try:
        # Load baseline
        baseline = load_baseline()

        # Query current state
        current = query_current_state(baseline)

        # Calculate progress
        progress = calculate_progress(baseline, current)

        # Save results
        result = {
            "baseline": baseline,
            "current": current,
            "progress": progress,
            "generated_at": datetime.now().isoformat(),
        }

        output_file = f'.tmp/armorcode_weekly_{datetime.now().strftime("%Y%m%d")}.json'
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)

        logger.info("=" * 70)
        logger.info(f"Results saved to: {output_file}")
        logger.info("=" * 70)

        return result

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
