"""
ArmorCode Baseline Creator

Creates an immutable baseline snapshot of HIGH and CRITICAL vulnerabilities
open on January 1, 2026. This baseline is used to track progress toward
the 70% reduction target by June 30, 2026.

Usage:
    python armorcode_baseline.py
    python armorcode_baseline.py --force  # Overwrite existing baseline (use with caution)
"""

import os
import sys
import argparse
import logging
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from http_client import get, post, put, delete, patch

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'.tmp/armorcode_baseline_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def create_baseline(api_key: str, base_url: str, environment: str,
                    products: list, baseline_date: str, target_date: str,
                    reduction_goal: float, force: bool = False) -> dict:
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
    baseline_file = '.tmp/armorcode_baseline.json'

    # Check if baseline already exists
    if os.path.exists(baseline_file) and not force:
        logger.error(f"Baseline already exists at {baseline_file}")
        raise ValueError(
            f"Baseline already exists and is immutable.\n"
            f"File: {baseline_file}\n"
            f"Use --force to overwrite (NOT RECOMMENDED)"
        )

    logger.info(f"Creating baseline for vulnerabilities open on {baseline_date}")

    try:
        import requests

        # Step 1: Connect to ArmorCode API
        logger.info(f"Connecting to ArmorCode API: {base_url}")

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        # Step 2: Build query filters for baseline date
        # Query for vulnerabilities that existed on the baseline date:
        # - Severity: HIGH or CRITICAL
        # - Environment: PRODUCTION (or specified)
        # - Products: Specified products
        # - First seen: Before or on baseline date
        # - Status: Open on baseline date (not closed before that date)

        params = {
            "severity": "HIGH,CRITICAL",  # May need adjustment based on API
            "environment": environment,
            "status": "Open,In Progress",  # Exclude closed
        }

        if products:
            params["products"] = ",".join(products)

        # Add baseline date filter
        # Note: Exact parameter names depend on ArmorCode API
        # Common patterns: discovered_before, first_seen_lte, etc.
        params["discovered_before"] = baseline_date

        logger.info(f"Querying vulnerabilities with filters: {params}")

        # Step 3: Query vulnerabilities from API
        # Try multiple potential endpoints
        vuln_endpoints = [
            '/api/v1/findings',
            '/api/findings',
            '/api/v1/vulnerabilities',
            '/api/vulnerabilities',
            '/v1/findings'
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
                    logger.warning(f"Endpoint {endpoint} returned status {response.status_code}: {response.text[:200]}")
                    continue

            except requests.exceptions.RequestException as e:
                logger.debug(f"Request to {endpoint} failed: {e}")
                continue

        if vulnerabilities is None:
            raise RuntimeError(
                "Unable to fetch vulnerabilities from ArmorCode API.\n"
                "Attempted endpoints:\n" + "\n".join([f"  - {base_url}{ep}" for ep in vuln_endpoints]) + "\n\n"
                "Please verify:\n"
                "1. API key is correct and has read permissions\n"
                "2. Base URL is correct\n"
                "3. Consult ArmorCode API documentation for the correct endpoint and filter parameters"
            )

        # Step 4: Process vulnerabilities
        vulnerability_list = []
        if isinstance(vulnerabilities, list):
            vulnerability_list = vulnerabilities
        elif isinstance(vulnerabilities, dict):
            if 'vulnerabilities' in vulnerabilities:
                vulnerability_list = vulnerabilities['vulnerabilities']
            elif 'findings' in vulnerabilities:
                vulnerability_list = vulnerabilities['findings']
            elif 'data' in vulnerabilities:
                vulnerability_list = vulnerabilities['data']

        baseline_count = len(vulnerability_list)
        logger.info(f"Found {baseline_count} vulnerabilities on {baseline_date}")

        # Step 5: Calculate baseline metrics
        target_count = int(baseline_count * (1 - reduction_goal))

        # Calculate days to target
        baseline_dt = datetime.strptime(baseline_date, "%Y-%m-%d")
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        days_to_target = (target_dt - baseline_dt).days
        weeks_to_target = days_to_target // 7

        # Calculate required reduction per week
        required_reduction = (baseline_count - target_count) / weeks_to_target if weeks_to_target > 0 else 0

        # Step 6: Format vulnerability data
        formatted_vulns = []
        for vuln in vulnerability_list:
            vuln_data = {
                "id": vuln.get('id') or vuln.get('vulnerability_id') or vuln.get('finding_id'),
                "title": vuln.get('title') or vuln.get('name'),
                "severity": vuln.get('severity'),
                "product": vuln.get('product') or vuln.get('product_name'),
                "asset": vuln.get('asset') or vuln.get('component'),
                "cve": vuln.get('cve') or vuln.get('cve_id'),
                "cwe": vuln.get('cwe') or vuln.get('cwe_id'),
                "status": vuln.get('status'),
                "first_seen": str(vuln.get('first_seen') or vuln.get('discovered_date') or ''),
                "description": vuln.get('description', '')[:200] + '...' if vuln.get('description') and len(vuln.get('description', '')) > 200 else vuln.get('description', '')
            }
            formatted_vulns.append(vuln_data)

        # Step 7: Create baseline data structure
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
            "vulnerabilities": formatted_vulns
        }

        # Step 8: Save baseline to file
        os.makedirs('.tmp', exist_ok=True)
        with open(baseline_file, 'w', encoding='utf-8') as f:
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
        description='Create immutable baseline snapshot for ArmorCode vulnerability tracking'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force overwrite of existing baseline (NOT RECOMMENDED)'
    )

    return parser.parse_args()


if __name__ == '__main__':
    """
    Entry point when script is run from command line.
    """
    try:
        # Parse command-line arguments
        args = parse_arguments()

        # Load configuration from environment
        api_key = os.getenv('ARMORCODE_API_KEY')
        base_url = os.getenv('ARMORCODE_BASE_URL', 'https://app.armorcode.com')
        environment = os.getenv('ARMORCODE_ENVIRONMENT', 'PRODUCTION')
        products_str = os.getenv('ARMORCODE_PRODUCTS', '')
        baseline_date = os.getenv('ARMORCODE_BASELINE_DATE', '2026-01-01')
        target_date = os.getenv('ARMORCODE_TARGET_DATE', '2026-06-30')
        reduction_goal = float(os.getenv('ARMORCODE_REDUCTION_GOAL', '0.70'))

        # Parse products list
        products = [p.strip() for p in products_str.split(',') if p.strip()] if products_str else []

        # Validate environment variables
        if not api_key or api_key == 'your_armorcode_api_key_here':
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
            force=args.force
        )

        # Print summary
        print(f"\n{'='*70}")
        print(f"ArmorCode Baseline Created")
        print(f"{'='*70}")
        print(f"Baseline Date: {baseline['baseline_date']}")
        print(f"Vulnerabilities on {baseline['baseline_date']}: {baseline['vulnerability_count']}")
        print(f"Target ({baseline['reduction_goal_pct']}% reduction): {baseline['target_count']}")
        print(f"Target Date: {baseline['target_date']}")
        print(f"Days to Target: {baseline['days_to_target']} ({baseline['weeks_to_target']} weeks)")
        print(f"Required Weekly Reduction: {baseline['required_weekly_reduction']:.2f} vulnerabilities/week")
        print(f"\nEnvironment: {baseline['environment']}")
        print(f"Severities: {', '.join(baseline['severities'])}")
        if baseline['products']:
            print(f"Products: {', '.join(baseline['products'])}")
        else:
            print(f"Products: ALL")
        print(f"\nBaseline saved to: .tmp/armorcode_baseline.json")
        print(f"{'='*70}\n")

        # Exit with success code
        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
