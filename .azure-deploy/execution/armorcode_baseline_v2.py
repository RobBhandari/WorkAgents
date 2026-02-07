"""
ArmorCode Baseline Creator V2 - Using Product IDs

Creates an immutable baseline snapshot of HIGH and CRITICAL vulnerabilities.
This version correctly queries by product ID instead of product name.

Usage:
    python armorcode_baseline_v2.py
    python armorcode_baseline_v2.py --force  # Overwrite existing baseline
"""

import os
import sys
import argparse
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'.tmp/armorcode_baseline_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def get_product_ids(api_key, base_url, product_names):
    """Get product IDs for the specified product names via GraphQL."""
    logger.info("Fetching product IDs from ArmorCode GraphQL API...")

    graphql_url = f"{base_url.rstrip('/')}/api/graphql"
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    all_products = []

    # Fetch all pages of products
    for page in range(1, 10):  # Max 10 pages (should be enough for 1000 products)
        query = f"""
        {{
          products(page: {page}, size: 100) {{
            products {{
              id
              name
            }}
            pageInfo {{
              hasNext
              totalElements
            }}
          }}
        }}
        """

        try:
            response = requests.post(graphql_url, headers=headers, json={'query': query}, timeout=60)

            if response.status_code == 200:
                data = response.json()

                if 'data' in data and 'products' in data['data']:
                    result = data['data']['products']
                    products = result.get('products', [])
                    all_products.extend(products)

                    logger.info(f"  Page {page}: {len(products)} products")

                    if not result.get('pageInfo', {}).get('hasNext', False):
                        break
                else:
                    logger.warning(f"Unexpected GraphQL response on page {page}")
                    break
            else:
                logger.error(f"GraphQL query failed with status {response.status_code}")
                break

        except Exception as e:
            logger.error(f"Error fetching products: {e}")
            break

    logger.info(f"Total products fetched: {len(all_products)}")

    # Map product names to IDs
    product_map = {p['name']: p['id'] for p in all_products}

    # Find IDs for our target products
    product_ids = []
    found_products = []
    missing_products = []

    for name in product_names:
        if name in product_map:
            product_ids.append(product_map[name])
            found_products.append(name)
        else:
            missing_products.append(name)

    logger.info(f"Found {len(found_products)}/{len(product_names)} products:")
    for name in found_products:
        logger.info(f"  [{product_map[name]}] {name}")

    if missing_products:
        logger.warning(f"Missing {len(missing_products)} products:")
        for name in missing_products:
            logger.warning(f"  - {name}")

    return product_ids, found_products


def fetch_all_findings(api_key, base_url, product_ids):
    """Fetch all HIGH+CRITICAL findings for the specified product IDs."""
    logger.info(f"Fetching findings for {len(product_ids)} products...")

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    url = f"{base_url.rstrip('/')}/api/findings"

    all_findings = []
    after_key = None
    page_num = 0

    while True:
        page_num += 1

        request_body = {
            "severity": ["HIGH", "CRITICAL"],
            "status": ["Open", "In Progress"],
            "product": product_ids  # Use product IDs, not names
        }

        if after_key:
            request_body["afterKey"] = after_key

        try:
            response = requests.post(url, headers=headers, json=request_body, timeout=60)

            if response.status_code == 200:
                data = response.json()

                if 'data' in data:
                    findings = data['data'].get('findings', [])
                    after_key = data['data'].get('afterKey')

                    all_findings.extend(findings)
                    logger.info(f"  Page {page_num}: {len(findings)} findings (total: {len(all_findings)})")

                    # Stop if no more pages
                    if not after_key or len(findings) == 0:
                        logger.info(f"  No more pages (afterKey: {after_key})")
                        break
                else:
                    logger.warning(f"Unexpected response structure on page {page_num}")
                    break
            else:
                logger.error(f"API request failed with status {response.status_code}")
                logger.error(response.text[:500])
                break

        except Exception as e:
            logger.error(f"Error fetching findings on page {page_num}: {e}")
            break

        # Safety limit
        if page_num >= 1000:
            logger.warning("Reached page limit (1000)")
            break

    logger.info(f"Total findings fetched: {len(all_findings)}")
    return all_findings


def create_baseline(force=False):
    """Create baseline snapshot."""
    baseline_file = '.tmp/armorcode_baseline.json'

    # Check if baseline exists
    if os.path.exists(baseline_file) and not force:
        logger.error(f"Baseline already exists at {baseline_file}")
        print(f"\n[ERROR] Baseline already exists and is immutable.")
        print(f"File: {baseline_file}")
        print(f"Use --force to overwrite (NOT RECOMMENDED)\n")
        return None

    # Get configuration from environment
    api_key = os.getenv('ARMORCODE_API_KEY')
    base_url = os.getenv('ARMORCODE_BASE_URL', 'https://app.armorcode.com')
    products_str = os.getenv('ARMORCODE_PRODUCTS', '')
    baseline_date = os.getenv('ARMORCODE_BASELINE_DATE')
    target_date = os.getenv('ARMORCODE_TARGET_DATE')
    reduction_goal = float(os.getenv('ARMORCODE_REDUCTION_GOAL', '0.70'))

    if not api_key:
        raise ValueError("ARMORCODE_API_KEY not set in environment")

    product_names = [p.strip() for p in products_str.split(',') if p.strip()]

    logger.info("="*70)
    logger.info("ARMORCODE BASELINE CREATION V2")
    logger.info("="*70)
    logger.info(f"Baseline Date: {baseline_date}")
    logger.info(f"Target Date: {target_date}")
    logger.info(f"Reduction Goal: {reduction_goal*100}%")
    logger.info(f"Target Products: {len(product_names)}")

    # Step 1: Get product IDs
    product_ids, found_products = get_product_ids(api_key, base_url, product_names)

    if not product_ids:
        raise ValueError("No valid product IDs found")

    # Step 2: Fetch all findings
    findings = fetch_all_findings(api_key, base_url, product_ids)

    # Step 3: Aggregate by product
    product_counts = {}
    for finding in findings:
        product = finding.get('product', {})
        if isinstance(product, dict):
            product_name = product.get('name', 'Unknown')
            severity = finding.get('severity', 'UNKNOWN').upper()

            if product_name not in product_counts:
                product_counts[product_name] = {'HIGH': 0, 'CRITICAL': 0, 'total': 0}

            if severity == 'HIGH':
                product_counts[product_name]['HIGH'] += 1
            elif severity == 'CRITICAL':
                product_counts[product_name]['CRITICAL'] += 1

            product_counts[product_name]['total'] += 1

    # Step 4: Create baseline
    baseline = {
        'created_at': datetime.now().isoformat(),
        'baseline_date': baseline_date,
        'target_date': target_date,
        'reduction_goal': reduction_goal,
        'products': found_products,
        'product_ids': product_ids,
        'total_vulnerabilities': len(findings),
        'by_product': product_counts,
        'summary': {
            'total_critical': sum(p.get('CRITICAL', 0) for p in product_counts.values()),
            'total_high': sum(p.get('HIGH', 0) for p in product_counts.values()),
            'products_tracked': len(product_counts)
        }
    }

    # Step 5: Save baseline
    os.makedirs('.tmp', exist_ok=True)
    with open(baseline_file, 'w') as f:
        json.dump(baseline, f, indent=2)

    logger.info("="*70)
    logger.info("BASELINE SUMMARY")
    logger.info("="*70)
    logger.info(f"Total Findings: {baseline['total_vulnerabilities']}")
    logger.info(f"  CRITICAL: {baseline['summary']['total_critical']}")
    logger.info(f"  HIGH: {baseline['summary']['total_high']}")
    logger.info(f"Products: {baseline['summary']['products_tracked']}")
    logger.info(f"\nBaseline saved to: {baseline_file}")
    logger.info("="*70)

    # Print product breakdown
    print(f"\nProduct Breakdown:")
    for product_name in sorted(product_counts.keys()):
        counts = product_counts[product_name]
        print(f"  {product_name}: {counts['total']} ({counts['CRITICAL']} C + {counts['HIGH']} H)")

    return baseline


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create ArmorCode baseline snapshot')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite existing baseline (NOT RECOMMENDED)')
    args = parser.parse_args()

    try:
        baseline = create_baseline(force=args.force)
        if baseline:
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to create baseline: {e}", exc_info=True)
        sys.exit(1)
