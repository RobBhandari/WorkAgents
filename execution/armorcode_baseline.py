"""
ArmorCode Baseline Creator

Creates an immutable baseline snapshot of HIGH and CRITICAL vulnerabilities
open on January 1, 2026. This baseline is used to track progress toward
the 70% reduction target by June 30, 2026.

Usage:
    python armorcode_baseline.py
    python armorcode_baseline.py --force  # Overwrite existing baseline (use with caution)
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from requests.exceptions import RequestException

from execution.config import get_config
from execution.http_client import get

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'.tmp/armorcode_baseline_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

_VULN_ENDPOINTS = [
    "/api/v1/findings",
    "/api/findings",
    "/api/v1/vulnerabilities",
    "/api/vulnerabilities",
    "/v1/findings",
]


def _try_endpoint_urls(
    base_url: str,
    url_candidates: list,
    headers: dict,
    params: dict,
) -> tuple:
    """
    Attempt each candidate endpoint until one returns HTTP 200.

    Args:
        base_url: ArmorCode base URL (used only for error messages)
        url_candidates: List of endpoint path strings to try in order
        headers: HTTP headers including Authorization
        params: Query parameters to include in the request

    Returns:
        tuple: (response_data, successful_endpoint_path)

    Raises:
        RuntimeError: If all endpoints fail or return non-200 responses
    """
    for endpoint in url_candidates:
        url = f"{base_url.rstrip('/')}{endpoint}"
        logger.info(f"Trying endpoint: {url}")
        try:
            response = get(url, headers=headers, params=params, timeout=60)
        except RequestException as e:
            logger.debug(f"Request to {endpoint} failed: {e}")
            continue

        if response.status_code == 200:
            logger.info(f"Successfully fetched vulnerabilities from: {endpoint}")
            return response.json(), endpoint
        elif response.status_code == 404:
            logger.debug(f"Endpoint not found: {endpoint}")
        else:
            logger.warning(f"Endpoint {endpoint} returned status {response.status_code}: {response.text[:200]}")

    raise RuntimeError(
        "Unable to fetch vulnerabilities from ArmorCode API.\n"
        "Attempted endpoints:\n" + "\n".join([f"  - {base_url}{ep}" for ep in url_candidates]) + "\n\n"
        "Please verify:\n"
        "1. API key is correct and has read permissions\n"
        "2. Base URL is correct\n"
        "3. Consult ArmorCode API documentation for the correct endpoint and filter parameters"
    )


def _extract_vulnerability_list(response_data) -> list:
    """
    Normalise the API response shape into a flat list of vulnerability dicts.

    Handles:
    - Raw list response
    - Dict with a "vulnerabilities" key
    - Dict with a "findings" key
    - Dict with a "data" key
    - Any other dict (returns empty list)

    Args:
        response_data: Parsed JSON response from the API (list or dict)

    Returns:
        list: Flat list of vulnerability dicts (may be empty)
    """
    if isinstance(response_data, list):
        return response_data
    if isinstance(response_data, dict):
        for key in ("vulnerabilities", "findings", "data"):
            if key in response_data:
                return response_data[key]
    return []


def _first_value(raw: dict, *keys: str):
    """Return the first non-None/non-empty value from *keys* in *raw*."""
    for key in keys:
        value = raw.get(key)
        if value is not None and value != "":
            return value
    return None


def _truncate_description(raw: dict, max_len: int = 200) -> str:
    """Extract and optionally truncate the description field from a raw record."""
    description = raw.get("description", "") or ""
    if len(description) > max_len:
        return description[:max_len] + "..."
    return description


def _format_vulnerability(raw: dict) -> dict:
    """
    Map raw API fields to a standardised vulnerability dict.

    Uses _first_value() with fallbacks for all fields so that missing keys
    never raise. Truncates descriptions longer than 200 characters.

    Args:
        raw: Single vulnerability record from the API response

    Returns:
        dict: Standardised vulnerability data dict
    """
    return {
        "id": _first_value(raw, "id", "vulnerability_id", "finding_id"),
        "title": _first_value(raw, "title", "name"),
        "severity": raw.get("severity"),
        "product": _first_value(raw, "product", "product_name"),
        "asset": _first_value(raw, "asset", "component"),
        "cve": _first_value(raw, "cve", "cve_id"),
        "cwe": _first_value(raw, "cwe", "cwe_id"),
        "status": raw.get("status"),
        "first_seen": str(_first_value(raw, "first_seen", "discovered_date") or ""),
        "description": _truncate_description(raw),
    }


def create_baseline(
    api_key: str,
    base_url: str,
    environment: str,
    products: list,
    baseline_date: str,
    target_date: str,
    reduction_goal: float,
    force: bool = False,
) -> dict:
    """
    Create baseline snapshot of HIGH and CRITICAL vulnerabilities.

    Args:
        api_key: ArmorCode API key
        base_url: ArmorCode base URL
        environment: Environment filter (e.g., "PRODUCTION")
        products: List of products to track
        baseline_date: Baseline date (YYYY-MM-DD)
        target_date: Target date for reduction goal (YYYY-MM-DD)
        reduction_goal: Reduction goal as decimal (e.g., 0.70 for 70%)
        force: If True, overwrite existing baseline

    Returns:
        dict: Baseline data

    Raises:
        ValueError: If baseline already exists and force=False
        RuntimeError: If baseline creation fails
    """
    baseline_file = ".tmp/armorcode_baseline.json"

    # Step 1: Guard — refuse to overwrite unless --force
    if os.path.exists(baseline_file) and not force:
        logger.error(f"Baseline already exists at {baseline_file}")
        raise ValueError(
            f"Baseline already exists and is immutable.\n"
            f"File: {baseline_file}\n"
            f"Use --force to overwrite (NOT RECOMMENDED)"
        )

    logger.info(f"Creating baseline for vulnerabilities open on {baseline_date}")

    try:
        # Step 2: Build request headers and query parameters
        logger.info(f"Connecting to ArmorCode API: {base_url}")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        params: dict = {
            "severity": "HIGH,CRITICAL",
            "environment": environment,
            "status": "Open,In Progress",
            "discovered_before": baseline_date,
        }

        if products:
            params["products"] = ",".join(products)

        logger.info(f"Querying vulnerabilities with filters: {params}")

        # Step 3: Discover a working endpoint and fetch raw data
        raw_response, successful_endpoint = _try_endpoint_urls(base_url, _VULN_ENDPOINTS, headers, params)
        logger.debug(f"Successful endpoint: {successful_endpoint}")

        # Step 4: Normalise response into a flat list
        vulnerability_list = _extract_vulnerability_list(raw_response)
        baseline_count = len(vulnerability_list)
        logger.info(f"Found {baseline_count} vulnerabilities on {baseline_date}")

        # Step 5: Calculate baseline metrics
        target_count = int(baseline_count * (1 - reduction_goal))
        baseline_dt = datetime.strptime(baseline_date, "%Y-%m-%d")
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        days_to_target = (target_dt - baseline_dt).days
        weeks_to_target = days_to_target // 7
        required_reduction = (baseline_count - target_count) / weeks_to_target if weeks_to_target > 0 else 0

        # Step 6: Format individual vulnerability records
        formatted_vulns = [_format_vulnerability(v) for v in vulnerability_list]

        # Step 7: Assemble baseline data structure
        baseline = {
            "baseline_date": baseline_date,
            "target_date": target_date,
            "reduction_goal": reduction_goal,
            "reduction_goal_pct": int(reduction_goal * 100),
            "vulnerability_count": baseline_count,
            "target_count": target_count,
            "days_to_target": days_to_target,
            "weeks_to_target": weeks_to_target,
            "required_weekly_reduction": round(required_reduction, 2),
            "immutable": True,
            "created_at": datetime.now().isoformat(),
            "environment": environment,
            "severities": ["HIGH", "CRITICAL"],
            "products": products or [],
            "base_url": base_url,
            "vulnerabilities": formatted_vulns,
        }

        # Step 8: Persist baseline to disk
        os.makedirs(".tmp", exist_ok=True)
        with open(baseline_file, "w", encoding="utf-8") as f:
            json.dump(baseline, f, indent=2, ensure_ascii=False)

        logger.info(f"Baseline created successfully: {baseline_file}")
        return baseline

    except Exception as e:
        logger.error(f"Error creating baseline: {e}", exc_info=True)
        raise RuntimeError(f"Failed to create baseline: {e}") from e


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Create immutable baseline snapshot for ArmorCode vulnerability tracking"
    )

    parser.add_argument("--force", action="store_true", help="Force overwrite of existing baseline (NOT RECOMMENDED)")

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
        baseline_date = get_config().get("ARMORCODE_BASELINE_DATE")
        target_date = get_config().get("ARMORCODE_TARGET_DATE")
        reduction_goal = float(get_config().get("ARMORCODE_REDUCTION_GOAL"))

        # Parse products list
        products = [p.strip() for p in products_str.split(",") if p.strip()] if products_str else []

        # Validate environment variables
        if not api_key or api_key == "your_armorcode_api_key_here":
            raise RuntimeError(
                "ARMORCODE_API_KEY not configured in .env file.\n"
                "Please obtain an API key from ArmorCode:\n"
                "1. Log in to ArmorCode platform\n"
                "2. Navigate to Settings > API Keys\n"
                "3. Click 'Generate New Key'\n"
                "4. Copy the key and add to .env file"
            )

        if not products:
            logger.warning(
                "No products configured in ARMORCODE_PRODUCTS.\n"
                "Baseline will include ALL products.\n"
                "Run 'python execution/armorcode_list_products.py' to discover products.\n"
                "Then update .env: ARMORCODE_PRODUCTS=Product1,Product2,Product3"
            )

        # Create baseline
        baseline = create_baseline(
            api_key=api_key,
            base_url=base_url,
            environment=environment,
            products=products,
            baseline_date=baseline_date,
            target_date=target_date,
            reduction_goal=reduction_goal,
            force=args.force,
        )

        # Print summary
        print(f"\n{'='*70}")
        print("ArmorCode Baseline Created")
        print(f"{'='*70}")
        print(f"Baseline Date: {baseline['baseline_date']}")
        print(f"Vulnerabilities on {baseline['baseline_date']}: {baseline['vulnerability_count']}")
        print(f"Target ({baseline['reduction_goal_pct']}% reduction): {baseline['target_count']}")
        print(f"Target Date: {baseline['target_date']}")
        print(f"Days to Target: {baseline['days_to_target']} ({baseline['weeks_to_target']} weeks)")
        print(f"Required Weekly Reduction: {baseline['required_weekly_reduction']:.2f} vulnerabilities/week")
        print(f"\nEnvironment: {baseline['environment']}")
        print(f"Severities: {', '.join(baseline['severities'])}")
        if baseline["products"]:
            print(f"Products: {', '.join(baseline['products'])}")
        else:
            print("Products: ALL")
        print("\nBaseline saved to: .tmp/armorcode_baseline.json")
        print(f"{'='*70}\n")

        # Exit with success code
        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
