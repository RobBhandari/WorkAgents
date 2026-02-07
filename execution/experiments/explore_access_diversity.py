"""Test what findings are being returned for Access Diversity"""
import json
import os
from collections import Counter

import requests
from dotenv import load_dotenv
from http_client import delete, get, patch, post, put

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
base_url = 'https://app.armorcode.com'
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

product_id = 10480
product_name = "Access Diversity"

print("="*70)
print(f"INVESTIGATING: {product_name} (ID: {product_id})")
print("="*70)
print("Expected from UI: 2 HIGH findings")
print()

# Fetch first 50 findings
request_body = {
    "severity": ["HIGH", "CRITICAL"],
    "status": ["Open", "In Progress"],
    "product": [product_id]
}

print("Request body:")
print(json.dumps(request_body, indent=2))
print()

response = post(
    f"{base_url}/api/findings",
    headers=headers,
    json=request_body,
    timeout=30
)

if response.status_code == 200:
    data = response.json()
    if 'data' in data:
        findings = data['data'].get('findings', [])
        print(f"API returned: {len(findings)} findings in first page")
        print()

        if findings:
            # Analyze what we got
            products = []
            severities = []
            statuses = []

            for f in findings[:20]:  # Look at first 20
                # Extract product info
                product = f.get('product', {})
                if isinstance(product, dict):
                    products.append(product.get('name', 'Unknown'))

                # Extract severity and status
                severities.append(f.get('severity', 'Unknown'))
                statuses.append(f.get('status', 'Unknown'))

            # Count occurrences
            product_counts = Counter(products)
            severity_counts = Counter(severities)
            status_counts = Counter(statuses)

            print("Analysis of first 20 findings:")
            print("-"*70)
            print("\nProducts found:")
            for prod, count in product_counts.most_common():
                print(f"  {prod}: {count}")

            print("\nSeverities:")
            for sev, count in severity_counts.most_common():
                print(f"  {sev}: {count}")

            print("\nStatuses:")
            for stat, count in status_counts.most_common():
                print(f"  {stat}: {count}")

            # Show sample finding details
            print("\n" + "-"*70)
            print("Sample finding (first one):")
            print("-"*70)
            first = findings[0]
            interesting_fields = ['product', 'severity', 'status', 'title', 'id', 'businessUnit']
            for field in interesting_fields:
                if field in first:
                    value = first[field]
                    if isinstance(value, dict):
                        print(f"{field}: {json.dumps(value, indent=2)}")
                    else:
                        print(f"{field}: {value}")

            # Check if there's a BU field
            bus = set()
            for f in findings[:20]:
                bu = f.get('businessUnit')
                if bu:
                    if isinstance(bu, dict):
                        bus.add(bu.get('name', 'Unknown'))
                    else:
                        bus.add(str(bu))

            if bus:
                print("\nBusiness Units in findings:")
                for bu in bus:
                    print(f"  - {bu}")
else:
    print(f"[ERROR] HTTP {response.status_code}")
    print(response.text[:500])

print("\n" + "="*70)
print("CONCLUSION")
print("="*70)
print("If API returns more than 2 HIGH findings, the product filter")
print("is likely NOT working correctly or is including other products.")
print("="*70)
