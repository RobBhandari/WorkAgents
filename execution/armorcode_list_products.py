"""
ArmorCode Product Discovery Script

Discovers and lists all products/hierarchies available in ArmorCode platform.
This helps identify which products to configure for vulnerability tracking.

Usage:
    python armorcode_list_products.py
    python armorcode_list_products.py --output-format json
    python armorcode_list_products.py --output-file custom_products.json
"""

from execution.core import get_config
import os
import sys
import argparse
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
from http_client import get, post, put, delete, patch

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'.tmp/armorcode_list_products_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def list_products(api_key: str, base_url: str) -> dict:
    """
    List all products/hierarchies from ArmorCode platform.

    Args:
        api_key: ArmorCode API key
        base_url: ArmorCode base URL

    Returns:
        dict: Product listing results

    Raises:
        RuntimeError: If product listing fails
    """
    logger.info("Connecting to ArmorCode API")

    try:
        import requests

        # Make API request to list products
        logger.info(f"Connecting to ArmorCode API: {base_url}")

        # Common ArmorCode API endpoints for products
        # Try multiple potential endpoints
        product_endpoints = [
            '/api/v1/products',
            '/api/products',
            '/v1/products',
            '/products'
        ]

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        products = None
        successful_endpoint = None

        for endpoint in product_endpoints:
            try:
                url = f"{base_url.rstrip('/')}{endpoint}"
                logger.info(f"Trying endpoint: {url}")

                response = get(url, headers=headers, timeout=30)

                if response.status_code == 200:
                    products = response.json()
                    successful_endpoint = endpoint
                    logger.info(f"Successfully fetched products from: {endpoint}")
                    break
                elif response.status_code == 404:
                    logger.debug(f"Endpoint not found: {endpoint}")
                    continue
                else:
                    logger.warning(f"Endpoint {endpoint} returned status {response.status_code}")
                    continue

            except requests.exceptions.RequestException as e:
                logger.debug(f"Request to {endpoint} failed: {e}")
                continue

        if products is None:
            raise RuntimeError(
                "Unable to fetch products from ArmorCode API.\n"
                "Attempted endpoints:\n" + "\n".join([f"  - {base_url}{ep}" for ep in product_endpoints]) + "\n\n"
                "Please verify:\n"
                "1. API key is correct and has read permissions\n"
                "2. Base URL is correct\n"
                "3. Consult ArmorCode API documentation for the correct endpoint"
            )

        if not products:
            logger.warning("No products found in ArmorCode")
            return {
                "status": "success",
                "product_count": 0,
                "products": [],
                "queried_at": datetime.now().isoformat()
            }

        # Process products into a standardized format
        product_list = []
        if isinstance(products, list):
            for product in products:
                # Extract key fields (adjust based on actual API response)
                product_data = {
                    "id": product.get('id') or product.get('product_id'),
                    "name": product.get('name') or product.get('product_name'),
                    "description": product.get('description', ''),
                    "environment": product.get('environment', ''),
                    "hierarchy": product.get('hierarchy', ''),
                }
                product_list.append(product_data)
        elif isinstance(products, dict):
            # If response is a dict with products nested
            if 'products' in products:
                product_list = products['products']
            elif 'data' in products:
                product_list = products['data']

        logger.info(f"Found {len(product_list)} products")

        result = {
            "status": "success",
            "product_count": len(product_list),
            "products": product_list,
            "queried_at": datetime.now().isoformat(),
            "base_url": base_url
        }

        return result

    except Exception as e:
        logger.error(f"Error listing products: {e}", exc_info=True)
        raise RuntimeError(f"Failed to list products: {e}") from e


def format_products_table(products: list) -> str:
    """
    Format products as a human-readable table.

    Args:
        products: List of product dictionaries

    Returns:
        str: Formatted table string
    """
    if not products:
        return "No products found."

    output = []
    output.append("=" * 80)
    output.append("ArmorCode Products")
    output.append("=" * 80)
    output.append("")

    for i, product in enumerate(products, 1):
        output.append(f"{i}. {product.get('name', 'N/A')}")
        if product.get('id'):
            output.append(f"   ID: {product['id']}")
        if product.get('environment'):
            output.append(f"   Environment: {product['environment']}")
        if product.get('hierarchy'):
            output.append(f"   Hierarchy: {product['hierarchy']}")
        if product.get('description'):
            output.append(f"   Description: {product['description']}")
        output.append("")

    output.append("=" * 80)
    output.append(f"Total products: {len(products)}")
    output.append("=" * 80)

    return "\n".join(output)


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='List all products/hierarchies from ArmorCode platform'
    )

    parser.add_argument(
        '--output-format',
        choices=['table', 'json'],
        default='table',
        help='Output format (default: table)'
    )

    parser.add_argument(
        '--output-file',
        type=str,
        default='.tmp/armorcode_products.json',
        help='Path to output JSON file (default: .tmp/armorcode_products.json)'
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
        api_key = get_config().get_armorcode_config().api_key
        base_url = get_config().get_armorcode_config().base_url

        # Validate environment variables
        if not api_key or api_key == 'your_armorcode_api_key_here':
            raise RuntimeError(
                "ARMORCODE_API_KEY not configured in .env file.\n"
                "Please obtain an API key from ArmorCode:\n"
                "1. Log in to ArmorCode platform\n"
                "2. Navigate to Settings > API Keys\n"
                "3. Click 'Generate New Key'\n"
                "4. Copy the key and add to .env file:\n"
                "   ARMORCODE_API_KEY=your_actual_key_here"
            )

        # List products
        result = list_products(api_key=api_key, base_url=base_url)

        # Output results
        if args.output_format == 'json':
            output = json.dumps(result, indent=2)
            print(output)
        else:
            output = format_products_table(result['products'])
            print(output)

        # Save JSON output to file
        os.makedirs('.tmp', exist_ok=True)
        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        logger.info(f"Products saved to {args.output_file}")

        # Print configuration hint
        print("\nTo configure products for tracking, update .env file:")
        print("ARMORCODE_PRODUCTS=Product1,Product2,Product3")
        print("\nOr use product IDs if names contain special characters:")
        print("ARMORCODE_PRODUCTS=prod-123,prod-456,prod-789")

        # Exit with success code
        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
