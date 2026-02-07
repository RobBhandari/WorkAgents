"""Test date filter parameters with ArmorCode API"""
import json
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
print("TESTING DATE FILTER PARAMETERS")
print("="*70)
print(f"Product: {product_name} (ID: {product_id})")
print(f"Baseline Date: {baseline_date}")
print(f"Expected: Findings discovered on or before {baseline_date}")
print()

# Test different date filter parameter names
test_cases = [
    {"name": "firstDetectedOnBefore", "param": "firstDetectedOnBefore"},
    {"name": "firstDetectedOn (lte)", "param": "firstDetectedOn", "value": {"lte": baseline_date}},
    {"name": "firstDetectedOn ($lte)", "param": "firstDetectedOn", "value": {"$lte": baseline_date}},
    {"name": "createdBefore", "param": "createdBefore"},
    {"name": "discoveredBefore", "param": "discoveredBefore"},
]

for i, test in enumerate(test_cases, 1):
    print(f"\n{i}. Testing: {test['name']}")
    print("-"*70)

    request_body = {
        "severity": ["HIGH", "CRITICAL"],
        "status": ["Open", "In Progress"],
        "product": [product_id]
    }

    # Add date filter
    if "value" in test:
        request_body[test["param"]] = test["value"]
    else:
        request_body[test["param"]] = baseline_date

    print(f"Request body: {json.dumps(request_body, indent=2)}")

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
                findings = data['data'].get('findings', [])
                print(f"[OK] SUCCESS: Got {len(findings)} findings in first page")

                # Show date info from first finding if available
                if findings:
                    first = findings[0]
                    print("  Sample finding dates:")
                    for date_field in ['firstDetectedOn', 'createdAt', 'discoveredDate', 'createdDate']:
                        if date_field in first:
                            print(f"    {date_field}: {first[date_field]}")
            else:
                print("[X] Unexpected response structure")
        else:
            print(f"[X] HTTP {response.status_code}")
            error_msg = response.text[:200]
            print(f"  Error: {error_msg}")

    except Exception as e:
        print(f"[X] Exception: {str(e)[:100]}")

# Also test WITHOUT any date filter as baseline
print(f"\n\n{len(test_cases)+1}. Testing: NO DATE FILTER (baseline)")
print("-"*70)

request_body = {
    "severity": ["HIGH", "CRITICAL"],
    "status": ["Open", "In Progress"],
    "product": [product_id]
}

print(f"Request body: {json.dumps(request_body, indent=2)}")

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
            findings = data['data'].get('findings', [])
            print(f"[OK] Got {len(findings)} findings in first page (no date filter)")

            # Show date range
            if findings:
                dates = []
                for f in findings[:10]:  # Check first 10
                    if 'firstDetectedOn' in f:
                        dates.append(f['firstDetectedOn'])

                if dates:
                    print("  Sample dates from first 10 findings:")
                    for d in dates[:5]:
                        print(f"    - {d}")

except Exception as e:
    print(f"[X] Exception: {str(e)[:100]}")

print("\n" + "="*70)
print("Test Complete")
print("="*70)
