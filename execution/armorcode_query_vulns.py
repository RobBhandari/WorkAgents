"""
ArmorCode Vulnerability Query and Comparison

Queries current HIGH and CRITICAL vulnerabilities from ArmorCode and compares
them to the baseline to track progress toward the 70% reduction goal.

Usage:
    python armorcode_query_vulns.py
    python armorcode_query_vulns.py --output-format json
    python armorcode_query_vulns.py --output-file custom_query.json
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from requests.exceptions import RequestException

from execution.core import get_config
from execution.http_client import get

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'.tmp/armorcode_query_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def load_baseline() -> dict:
    """
    Load baseline data from file.

    Returns:
        dict: Baseline data

    Raises:
        FileNotFoundError: If baseline file doesn't exist
    """
    baseline_file = ".tmp/armorcode_baseline.json"

    if not os.path.exists(baseline_file):
        raise FileNotFoundError(
            f"Baseline not found: {baseline_file}\n" f"Please run: python execution/armorcode_baseline.py"
        )

    logger.info(f"Loading baseline from {baseline_file}")

    with open(baseline_file, encoding="utf-8") as f:
        baseline = json.load(f)

    logger.info(f"Baseline loaded: {baseline['vulnerability_count']} vulnerabilities on {baseline['baseline_date']}")
    return baseline


def load_tracking_history() -> dict:
    """
    Load historical tracking data.

    Returns:
        dict: Tracking history (or empty structure if file doesn't exist)
    """
    tracking_file = ".tmp/armorcode_tracking.json"

    if not os.path.exists(tracking_file):
        logger.info("No previous tracking data found, starting fresh")
        return {"queries": []}

    logger.info(f"Loading tracking history from {tracking_file}")

    with open(tracking_file, encoding="utf-8") as f:
        tracking = json.load(f)

    logger.info(f"Loaded {len(tracking.get('queries', []))} previous queries")
    return tracking


def save_tracking_history(tracking: dict):
    """
    Save tracking history to file.

    Args:
        tracking: Tracking data
    """
    tracking_file = ".tmp/armorcode_tracking.json"
    os.makedirs(".tmp", exist_ok=True)

    with open(tracking_file, "w", encoding="utf-8") as f:
        json.dump(tracking, f, indent=2, ensure_ascii=False)

    logger.info(f"Tracking history saved to {tracking_file}")


def query_current_vulnerabilities(api_key: str, base_url: str, environment: str, products: list) -> list:
    """
    Query current vulnerabilities from ArmorCode.

    Args:
        api_key: ArmorCode API key
        base_url: ArmorCode base URL
        environment: Environment filter
        products: List of products to query

    Returns:
        list: Current vulnerabilities

    Raises:
        RuntimeError: If query fails
    """
    try:
        # Connect to ArmorCode API
        logger.info(f"Connecting to ArmorCode API: {base_url}")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Build query parameters
        params = {
            "severity": "HIGH,CRITICAL",
            "environment": environment,
            "status": "Open,In Progress",  # Exclude closed/resolved
        }

        if products:
            params["products"] = ",".join(products)

        logger.info(f"Querying current vulnerabilities with filters: {params}")

        # Query vulnerabilities from API
        # Try multiple potential endpoints
        vuln_endpoints = [
            "/api/v1/findings",
            "/api/findings",
            "/api/v1/vulnerabilities",
            "/api/vulnerabilities",
            "/v1/findings",
        ]

        vulnerabilities = None
        successful_endpoint = None

        for endpoint in vuln_endpoints:
            try:
                url = f"{base_url.rstrip('/')}{endpoint}"
                logger.info(f"Trying endpoint: {url}")

                response = get(url, headers=headers, params=params, timeout=60)

                if response.status_code == 200:
                    vulnerabilities = response.json()
                    successful_endpoint = endpoint
                    logger.info(f"Successfully fetched vulnerabilities from: {endpoint}")
                    break
                elif response.status_code == 404:
                    logger.debug(f"Endpoint not found: {endpoint}")
                    continue
                else:
                    logger.warning(f"Endpoint {endpoint} returned status {response.status_code}")
                    continue

            except RequestException as e:
                logger.debug(f"Request to {endpoint} failed: {e}")
                continue

        if vulnerabilities is None:
            raise RuntimeError(
                "Unable to fetch vulnerabilities from ArmorCode API.\n"
                "Attempted endpoints:\n" + "\n".join([f"  - {base_url}{ep}" for ep in vuln_endpoints]) + "\n\n"
                "Please verify:\n"
                "1. API key is correct\n"
                "2. Base URL is correct\n"
                "3. Consult ArmorCode API documentation"
            )

        # Process results
        vulnerability_list = []
        if isinstance(vulnerabilities, list):
            vulnerability_list = vulnerabilities
        elif isinstance(vulnerabilities, dict):
            if "vulnerabilities" in vulnerabilities:
                vulnerability_list = vulnerabilities["vulnerabilities"]
            elif "findings" in vulnerabilities:
                vulnerability_list = vulnerabilities["findings"]
            elif "data" in vulnerabilities:
                vulnerability_list = vulnerabilities["data"]

        logger.info(f"Found {len(vulnerability_list)} current vulnerabilities")

        # Format vulnerability data
        formatted_vulns = []
        for vuln in vulnerability_list:
            vuln_data = {
                "id": vuln.get("id") or vuln.get("vulnerability_id") or vuln.get("finding_id"),
                "title": vuln.get("title") or vuln.get("name"),
                "severity": vuln.get("severity"),
                "product": vuln.get("product") or vuln.get("product_name"),
                "asset": vuln.get("asset") or vuln.get("component"),
                "cve": vuln.get("cve") or vuln.get("cve_id"),
                "cwe": vuln.get("cwe") or vuln.get("cwe_id"),
                "status": vuln.get("status"),
                "first_seen": str(vuln.get("first_seen") or vuln.get("discovered_date") or ""),
                "last_seen": str(vuln.get("last_seen") or vuln.get("last_updated") or ""),
                "description": vuln.get("description", ""),
                "remediation": vuln.get("remediation") or vuln.get("recommendation", ""),
            }
            formatted_vulns.append(vuln_data)

        return formatted_vulns

    except Exception as e:
        logger.error(f"Error querying vulnerabilities: {e}", exc_info=True)
        raise RuntimeError(f"Failed to query vulnerabilities: {e}") from e


def calculate_comparison(baseline: dict, current_vulns: list) -> dict:
    """
    Calculate comparison metrics between baseline and current state.

    Args:
        baseline: Baseline data
        current_vulns: Current vulnerability list

    Returns:
        dict: Comparison metrics
    """
    baseline_count = baseline["vulnerability_count"]
    target_count = baseline["target_count"]
    current_count = len(current_vulns)

    # Calculate reduction metrics
    reduction_amount = baseline_count - current_count
    reduction_pct = (reduction_amount / baseline_count * 100) if baseline_count > 0 else 0

    # Calculate progress to goal
    remaining_to_goal = current_count - target_count
    total_reduction_needed = baseline_count - target_count
    progress_to_goal_pct = (reduction_amount / total_reduction_needed * 100) if total_reduction_needed > 0 else 0

    # Calculate days since baseline and to target
    baseline_date = datetime.strptime(baseline["baseline_date"], "%Y-%m-%d")
    target_date = datetime.strptime(baseline["target_date"], "%Y-%m-%d")
    today = datetime.now()

    days_since_baseline = (today - baseline_date).days
    days_to_target = (target_date - today).days

    comparison = {
        "reduction_amount": reduction_amount,
        "reduction_pct": round(reduction_pct, 1),
        "remaining_to_goal": remaining_to_goal,
        "progress_to_goal_pct": round(progress_to_goal_pct, 1),
        "days_since_baseline": days_since_baseline,
        "days_to_target": days_to_target,
    }

    return comparison


def query_and_compare(api_key: str, base_url: str, environment: str, products: list) -> dict:
    """
    Query current vulnerabilities and compare to baseline.

    Args:
        api_key: ArmorCode API key
        base_url: ArmorCode base URL
        environment: Environment filter
        products: List of products

    Returns:
        dict: Query and comparison results
    """
    # Load baseline
    baseline = load_baseline()

    # Load tracking history
    tracking = load_tracking_history()

    # Query current vulnerabilities
    current_vulns = query_current_vulnerabilities(api_key, base_url, environment, products)

    # Calculate comparison
    comparison = calculate_comparison(baseline, current_vulns)

    # Build result
    result = {
        "queried_at": datetime.now().isoformat(),
        "baseline": {"date": baseline["baseline_date"], "count": baseline["vulnerability_count"]},
        "target": {
            "date": baseline["target_date"],
            "count": baseline["target_count"],
            "reduction_goal_pct": baseline["reduction_goal_pct"],
        },
        "current": {"count": len(current_vulns), "vulnerabilities": current_vulns},
        "comparison": comparison,
        "environment": environment,
        "products": products or [],
    }

    # Append to tracking history
    tracking_entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
        "count": len(current_vulns),
        "reduction_pct": comparison["reduction_pct"],
        "progress_to_goal_pct": comparison["progress_to_goal_pct"],
    }

    tracking["queries"].append(tracking_entry)
    save_tracking_history(tracking)

    return result


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Query current ArmorCode vulnerabilities and compare to baseline")

    parser.add_argument(
        "--output-format", choices=["summary", "json"], default="summary", help="Output format (default: summary)"
    )

    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Path to output JSON file (default: .tmp/armorcode_query_[timestamp].json)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    """
    Entry point when script is run from command line.
    """
    try:
        # Parse command-line arguments
        args = parse_arguments()

        # Load configuration from environment
        api_key = get_config().get_armorcode_config().api_key
        base_url = get_config().get_armorcode_config().base_url
        environment = get_config().get("ARMORCODE_ENVIRONMENT")
        products_str = get_config().get("ARMORCODE_PRODUCTS")

        # Parse products list
        products = [p.strip() for p in products_str.split(",") if p.strip()] if products_str else []

        # Validate environment variables
        if not api_key or api_key == "your_armorcode_api_key_here":
            raise RuntimeError(
                "ARMORCODE_API_KEY not configured in .env file.\n" "Please obtain an API key and add to .env file"
            )

        # Query and compare
        result = query_and_compare(api_key=api_key, base_url=base_url, environment=environment, products=products)

        # Output results
        if args.output_format == "json":
            output = json.dumps(result, indent=2)
            print(output)
        else:
            # Print summary
            print(f"\n{'='*70}")
            print("ArmorCode Vulnerability Tracking")
            print(f"{'='*70}")
            print(f"Query Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"\nBaseline ({result['baseline']['date']}):     {result['baseline']['count']:>3} vulnerabilities")
            print(
                f"Target ({result['target']['reduction_goal_pct']}% reduction):        {result['target']['count']:>3} vulnerabilities"
            )
            print(f"Current:                           {result['current']['count']:>3} vulnerabilities")
            print("\nProgress:")
            print(
                f"  Reduced: {result['comparison']['reduction_amount']:>3} vulnerabilities ({result['comparison']['reduction_pct']:>5.1f}%)"
            )
            print(f"  Remaining to goal: {result['comparison']['remaining_to_goal']:>3} vulnerabilities")
            print(f"  Progress to goal: {result['comparison']['progress_to_goal_pct']:>5.1f}%")
            print("\nTimeline:")
            print(f"  Days since baseline: {result['comparison']['days_since_baseline']}")
            print(f"  Days to target: {result['comparison']['days_to_target']}")
            print(f"{'='*70}\n")

        # Save detailed JSON output
        if args.output_file:
            output_file = args.output_file
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f".tmp/armorcode_query_{timestamp}.json"

        os.makedirs(".tmp", exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        logger.info(f"Query results saved to {output_file}")

        # Exit with success code
        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
