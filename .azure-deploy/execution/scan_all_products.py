"""Scan all pages to find all product names"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

all_products = set()
after_key = None
max_pages = 50

print("Scanning for all products...")
for page in range(1, max_pages + 1):
    body = {'severity': ['HIGH', 'CRITICAL']}
    if after_key:
        body['afterKey'] = after_key

    resp = requests.post('https://app.armorcode.com/api/findings', headers=headers, json=body, timeout=60)
    data = resp.json().get('data', {})
    findings = data.get('findings', [])
    after_key = data.get('afterKey')

    for f in findings:
        prod = f.get('product', {})
        if isinstance(prod, dict):
            all_products.add(prod.get('name', 'Unknown'))

    print(f"  Page {page}: {len(findings)} findings (total products: {len(all_products)})")

    if not after_key or not findings:
        break

print(f"\n{'='*60}")
print(f"All unique products found:")
print(f"{'='*60}")
for p in sorted(all_products):
    print(f"  - {p}")
