"""Scan multiple pages to find all accessible products"""
import os

import requests
from dotenv import load_dotenv
from http_client import delete, get, patch, post, put

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
base_url = 'https://app.armorcode.com'
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

print("="*70)
print("SCANNING ALL PAGES FOR PRODUCTS")
print("="*70)
print(f"API Key: {api_key[:8]}...{api_key[-8:]}")

all_products = set()
after_key = None
max_pages = 30
total_findings = 0

print("\nFetching HIGH+CRITICAL findings across all pages...")
print("-"*70)

for page in range(1, max_pages + 1):
    request_body = {
        "severity": ["HIGH", "CRITICAL"],
        "status": ["Open", "In Progress"]
    }

    if after_key:
        request_body["afterKey"] = after_key

    try:
        response = post(
            f"{base_url}/api/findings",
            headers=headers,
            json=request_body,
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()

            if isinstance(data, dict) and 'data' in data:
                findings = data['data'].get('findings', [])
                after_key = data['data'].get('afterKey')

                total_findings += len(findings)

                for finding in findings:
                    product = finding.get('product')
                    if isinstance(product, dict):
                        product_name = product.get('name', 'Unknown')
                        all_products.add(product_name)

                print(f"  Page {page}: {len(findings)} findings (total products: {len(all_products)}, total findings: {total_findings})")

                # Stop if no more data
                if not after_key or len(findings) == 0:
                    print(f"\n  [i] No more pages (afterKey: {after_key})")
                    break
            else:
                print(f"  [ERROR] Unexpected response structure on page {page}")
                break
        else:
            print(f"  [ERROR] HTTP {response.status_code} on page {page}")
            break

    except Exception as e:
        print(f"  [ERROR] {e}")
        break

print("\n" + "="*70)
print(f"RESULTS: Scanned {page} pages, {total_findings} total findings")
print("="*70)

print(f"\nAll unique products found ({len(all_products)}):")
for prod in sorted(all_products):
    print(f"  - {prod}")

# Check for Legal products
legal_keywords = ['Legal', 'Eclipse', 'Proclaim', 'inCase', 'Fusion', 'Bricks', 'Workspace', 'Diversity', 'MyCalendars', 'Office']
legal_products = [p for p in all_products if any(kw in p for kw in legal_keywords)]

print(f"\n{'='*70}")
if legal_products:
    print(f"SUCCESS! Found {len(legal_products)} Legal products:")
    for p in legal_products:
        print(f"  [+] {p}")
    print("\n>>> Account Level Access is ENABLED!")
    print(">>> The new API key is working correctly!")
else:
    print(f"[!] No Legal products found after scanning {page} pages.")
    print(f"    Total products accessible: {len(all_products)}")
    print(f"    Products: {', '.join(sorted(all_products))}")
    print("\n>>> Account Level Access is still DISABLED")
    print(">>> The new API key has the same scope as the old one")
    print("\n>>> ACTION REQUIRED:")
    print("    When creating the API key, the 'Account Level Access'")
    print("    toggle must be ENABLED to access products across all")
    print("    Business Units.")
print(f"{'='*70}")
