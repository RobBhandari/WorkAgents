"""Test different product filter parameters"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
base_url = 'https://app.armorcode.com'
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

test_products = ["Access Legal Case Management", "Legal Bricks"]

tests = [
    {"name": "products (list)", "body": {"severity": ["HIGH", "CRITICAL"], "products": test_products}},
    {"name": "product (list)", "body": {"severity": ["HIGH", "CRITICAL"], "product": test_products}},
    {"name": "productNames (list)", "body": {"severity": ["HIGH", "CRITICAL"], "productNames": test_products}},
    {"name": "productName (list)", "body": {"severity": ["HIGH", "CRITICAL"], "productName": test_products}},
    {"name": "hierarchy (list)", "body": {"severity": ["HIGH", "CRITICAL"], "hierarchy": ["The Access Group"]}},
    {"name": "team (list)", "body": {"severity": ["HIGH", "CRITICAL"], "team": ["The Access Group"]}},
]

for test in tests:
    print(f"\nTest: {test['name']}")
    print("-" * 60)
    try:
        response = requests.post(f"{base_url}/api/findings", headers=headers, json=test['body'], timeout=60)
        data = response.json()
        findings = data.get('data', {}).get('findings', [])

        if findings:
            products = set()
            for f in findings[:5]:  # Check first 5
                prod = f.get('product', {})
                if isinstance(prod, dict):
                    products.add(prod.get('name', 'Unknown'))
            print(f"  Found {len(findings)} findings")
            print(f"  Sample products: {', '.join(list(products)[:3])}")
        else:
            print(f"  No findings returned")
    except Exception as e:
        print(f"  Error: {e}")
