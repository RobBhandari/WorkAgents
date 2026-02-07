"""Test new API key with Account Level Access enabled"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
base_url = 'https://app.armorcode.com'
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

print("="*70)
print("TESTING NEW API KEY")
print("="*70)
print(f"API Key: {api_key[:8]}...{api_key[-8:]}")

# Test 1: Get HIGH+CRITICAL findings
print("\n1. Fetching HIGH+CRITICAL findings...")
print("-"*70)

request_body = {
    "severity": ["HIGH", "CRITICAL"],
    "status": ["Open", "In Progress"]
}

try:
    response = requests.post(
        f"{base_url}/api/findings",
        headers=headers,
        json=request_body,
        timeout=60
    )

    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()

        if isinstance(data, dict) and 'data' in data:
            findings = data['data'].get('findings', [])
            print(f"[OK] Found {len(findings)} findings in first page")

            # Extract unique products
            products = set()
            for finding in findings:
                product = finding.get('product')
                if isinstance(product, dict):
                    product_name = product.get('name', 'Unknown')
                    products.add(product_name)

            print(f"\n[OK] Products found ({len(products)}):")
            for prod in sorted(products):
                print(f"  - {prod}")

            # Check for Legal products
            legal_keywords = ['Legal', 'Eclipse', 'Proclaim', 'inCase', 'Fusion', 'Bricks', 'Workspace', 'Diversity']
            legal_products = [p for p in products if any(kw in p for kw in legal_keywords)]

            print(f"\n{'='*70}")
            if legal_products:
                print(f"SUCCESS! Found {len(legal_products)} Legal products:")
                for p in legal_products:
                    print(f"  [+] {p}")
                print(f"\nAccount Level Access is ENABLED!")
            else:
                print(f"[!] No Legal products found yet.")
                print(f"   Products: {', '.join(sorted(products))}")
                print(f"\n   May need to fetch more pages or check BU scope.")
            print(f"{'='*70}")

        else:
            print(f"Unexpected response structure:")
            print(f"{data}")
    else:
        print(f"[ERROR] HTTP {response.status_code}")
        print(f"Response: {response.text[:500]}")

except Exception as e:
    print(f"[ERROR] {e}")

print("\n" + "="*70)
print("Test Complete")
print("="*70)
