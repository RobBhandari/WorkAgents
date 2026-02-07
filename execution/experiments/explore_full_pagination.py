"""Test fetching all pages from ArmorCode API"""
import os

import requests
from dotenv import load_dotenv
from http_client import delete, get, patch, post, put

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
base_url = 'https://app.armorcode.com'

headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

all_findings = []
after_key = None
page = 0
max_pages = 20  # Safety limit

print("Fetching all findings...")
print("=" * 60)

while page < max_pages:
    page += 1
    body = {"severity": ["HIGH", "CRITICAL"]}

    if after_key:
        body["afterKey"] = after_key

    response = post(
        f"{base_url}/api/findings",
        headers=headers,
        json=body,
        timeout=60
    )
    data = response.json()

    findings = data.get('data', {}).get('findings', [])
    after_key = data.get('data', {}).get('afterKey')

    all_findings.extend(findings)

    print(f"Page {page}: Got {len(findings)} findings (total so far: {len(all_findings)})")

    if not after_key or len(findings) == 0:
        print("No more pages!")
        break

print("=" * 60)
print(f"TOTAL HIGH + CRITICAL FINDINGS: {len(all_findings)}")

# Count by product
product_counts = {}
for f in all_findings:
    product = f.get('product', {})
    if isinstance(product, dict):
        product_name = product.get('name', 'Unknown')
    else:
        product_name = str(product) if product else 'Unknown'

    product_counts[product_name] = product_counts.get(product_name, 0) + 1

print("\nBy product:")
for product, count in sorted(product_counts.items(), key=lambda x: -x[1]):
    print(f"  {product}: {count}")
