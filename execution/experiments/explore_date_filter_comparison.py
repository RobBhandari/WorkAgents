"""Compare finding counts WITH and WITHOUT date filter"""
import os

import requests
from dotenv import load_dotenv
from http_client import delete, get, patch, post, put

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
base_url = 'https://app.armorcode.com'
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

# Test with one product: Access Diversity (ID: 10480)
product_id = 10480
product_name = "Access Diversity"
baseline_date = "2025-12-01"

print("="*70)
print("COMPARING FINDING COUNTS WITH/WITHOUT DATE FILTER")
print("="*70)
print(f"Product: {product_name} (ID: {product_id})")
print(f"Baseline Date: {baseline_date}")
print()

def fetch_all_findings(product_id, date_filter=None, max_pages=10):
    """Fetch findings with pagination up to max_pages"""
    findings = []
    after_key = None
    page = 0

    while page < max_pages:
        page += 1

        request_body = {
            "severity": ["HIGH", "CRITICAL"],
            "status": ["Open", "In Progress"],
            "product": [product_id]
        }

        if date_filter:
            request_body["firstDetectedOnBefore"] = date_filter

        if after_key:
            request_body["afterKey"] = after_key

        try:
            response = post(
                f"{base_url}/api/findings",
                headers=headers,
                json=request_body,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    page_findings = data['data'].get('findings', [])
                    after_key = data['data'].get('afterKey')

                    findings.extend(page_findings)

                    print(f"  Page {page}: {len(page_findings)} findings (total: {len(findings)})")

                    if not after_key or len(page_findings) == 0:
                        print("  [No more pages]")
                        break
                else:
                    break
            else:
                print(f"  [ERROR] HTTP {response.status_code}")
                break

        except Exception as e:
            print(f"  [ERROR] {str(e)[:50]}")
            break

    return findings

# Test 1: WITH date filter
print("\n1. WITH DATE FILTER (firstDetectedOnBefore: 2025-12-01)")
print("-"*70)
findings_with_filter = fetch_all_findings(product_id, baseline_date, max_pages=10)
print(f"\nTotal with filter: {len(findings_with_filter)} findings")

# Test 2: WITHOUT date filter
print("\n\n2. WITHOUT DATE FILTER")
print("-"*70)
findings_without_filter = fetch_all_findings(product_id, None, max_pages=10)
print(f"\nTotal without filter: {len(findings_without_filter)} findings")

# Compare
print("\n" + "="*70)
print("COMPARISON")
print("="*70)
print(f"With date filter (<=2025-12-01):    {len(findings_with_filter)} findings")
print(f"Without date filter (all current):  {len(findings_without_filter)} findings")
print(f"Difference:                          {len(findings_without_filter) - len(findings_with_filter)} findings")

if len(findings_with_filter) < len(findings_without_filter):
    print("\n[OK] Date filter IS WORKING - fewer findings returned with filter")
    print(f"The filter reduced findings by {len(findings_without_filter) - len(findings_with_filter)}")
elif len(findings_with_filter) == len(findings_without_filter):
    print("\n[WARNING] Date filter appears to be IGNORED - same count with/without filter")
    print("The API may not support this date filter parameter")
else:
    print("\n[ERROR] Unexpected result - more findings with filter than without")

print("="*70)
