"""
ArmorCode Baseline Creator V3 - Query Each Product Separately

Queries each product individually to avoid API filter issues,
then combines results into a single baseline.
"""

import os
import sys
import argparse
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
import requests
from http_client import get, post, put, delete, patch

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
            response = post(graphql_url, headers=headers, json={'query': query}, timeout=60)

            if response.status_code == 200:
                data = response.json()

                if 'data' in data and 'products' in data['data']:
                    result = data['data']['products']
                    products = result.get('products', [])
                    all_products.extend(products)

                    if not result.get('pageInfo', {}).get('hasNext', False):
                        break
            else:
                break

        except Exception as e:
            logger.error(f"Error fetching products: {e}")
            break

    # Map product names to IDs
    product_map = {p['name']: p['id'] for p in all_products}

    # Find IDs for our target products
    product_data = []
    for name in product_names:
        if name in product_map:
            product_data.append({'name': name, 'id': product_map[name]})
        else:
            logger.warning(f"Product not found: {name}")

    logger.info(f"Found {len(product_data)}/{len(product_names)} products")
    return product_data


def fetch_findings_for_product(api_key, base_url, product_id, product_name):
    """Fetch ALL current HIGH+CRITICAL findings for a single product."""
    logger.info(f"Fetching findings for: {product_name} (ID: {product_id})")

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    url = f"{base_url.rstrip('/')}/api/findings"

    findings = []
    after_key = None
    page_num = 0

    while True:
        page_num += 1

        request_body = {
            "severity": ["HIGH", "CRITICAL"],
            "status": ["Open", "In Progress"],
            "product": [product_id]  # Single product ID
        }

        if after_key:
            request_body["afterKey"] = after_key

        try:
            response = post(url, headers=headers, json=request_body, timeout=60)

            if response.status_code == 200:
                data = response.json()

                if 'data' in data:
                    page_findings = data['data'].get('findings', [])
                    after_key = data['data'].get('afterKey')

                    findings.extend(page_findings)

                    # Log progress every 10 pages
                    if page_num % 10 == 0:
                        logger.info(f"  Page {page_num}: {len(findings)} findings so far...")

                    # Stop if no more pages
                    if not after_key or len(page_findings) == 0:
                        break

                    # Safety limit - stop at 500 pages (~5000 findings per product)
                    if page_num >= 500:
                        logger.warning(f"  Reached safety limit (500 pages) for {product_name}")
                        break
                else:
                    break
            else:
                logger.error(f"  API error {response.status_code} for {product_name}")
                break

        except Exception as e:
            logger.error(f"  Error fetching findings for {product_name}: {e}")
            break

    logger.info(f"  Fetched {len(findings)} findings for {product_name}")
    return findings


def create_baseline(force=False):
    """Create baseline snapshot by querying each product separately."""
    baseline_file = '.tmp/armorcode_baseline.json'

    # Check if baseline exists
    if os.path.exists(baseline_file) and not force:
        logger.error(f"Baseline already exists at {baseline_file}")
        print(f"\n[ERROR] Baseline already exists. Use --force to overwrite.\n")
        return None

    # Get configuration
    api_key = os.getenv('ARMORCODE_API_KEY')
    base_url = os.getenv('ARMORCODE_BASE_URL', 'https://app.armorcode.com')
    products_str = os.getenv('ARMORCODE_PRODUCTS', '')
    baseline_date = os.getenv('ARMORCODE_BASELINE_DATE')
    target_date = os.getenv('ARMORCODE_TARGET_DATE')
    reduction_goal = float(os.getenv('ARMORCODE_REDUCTION_GOAL', '0.70'))

    if not api_key:
        raise ValueError("ARMORCODE_API_KEY not set")

    product_names = [p.strip() for p in products_str.split(',') if p.strip()]

    logger.info("="*70)
    logger.info("ARMORCODE BASELINE CREATION V3 - Current State Snapshot")
    logger.info("="*70)
    logger.info(f"Snapshot Date: {datetime.now().strftime('%Y-%m-%d')}")
    logger.info(f"Baseline Reference Date: {baseline_date}")
    logger.info(f"Capturing: Current HIGH+CRITICAL findings (Open + In Progress)")
    logger.info(f"Target Products: {len(product_names)}")

    # Step 1: Get product IDs
    product_data = get_product_ids(api_key, base_url, product_names)

    if not product_data:
        raise ValueError("No valid products found")

    # Step 2: Fetch findings for each product separately
    all_findings = []
    product_counts = {}

    for product in product_data:
        product_name = product['name']
        product_id = product['id']

        findings = fetch_findings_for_product(api_key, base_url, product_id, product_name)

        # Aggregate counts
        if findings:
            all_findings.extend(findings)

            if product_name not in product_counts:
                product_counts[product_name] = {'HIGH': 0, 'CRITICAL': 0, 'total': 0}

            for finding in findings:
                severity = finding.get('severity', '').upper()
                if severity == 'HIGH':
                    product_counts[product_name]['HIGH'] += 1
                elif severity == 'CRITICAL':
                    product_counts[product_name]['CRITICAL'] += 1
                product_counts[product_name]['total'] += 1

    # Step 3: Create baseline
    baseline = {
        'created_at': datetime.now().isoformat(),
        'baseline_date': baseline_date,
        'target_date': target_date,
        'reduction_goal': reduction_goal,
        'products': [p['name'] for p in product_data],
        'product_ids': [p['id'] for p in product_data],
        'total_vulnerabilities': len(all_findings),
        'by_product': product_counts,
        'summary': {
            'total_critical': sum(p.get('CRITICAL', 0) for p in product_counts.values()),
            'total_high': sum(p.get('HIGH', 0) for p in product_counts.values()),
            'products_tracked': len(product_counts)
        }
    }

    # Step 4: Save baseline
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
                        help='Overwrite existing baseline')
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
