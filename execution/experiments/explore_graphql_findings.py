"""Test fetching findings via GraphQL instead of REST API"""
import json
import os

import requests
from dotenv import load_dotenv
from http_client import delete, get, patch, post, put

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
base_url = 'https://app.armorcode.com'
graphql_url = f'{base_url}/api/graphql'
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

product_id = 10480
product_name = "Access Diversity"

print("="*70)
print("TESTING GRAPHQL FINDINGS QUERY")
print("="*70)
print(f"Product: {product_name} (ID: {product_id})")
print("Expected from UI: 2 HIGH findings")
print()

# Try GraphQL findings query with product filter
query = f"""
{{
  findings(
    page: 1
    size: 50
    severity: [HIGH, CRITICAL]
    status: [OPEN, INPROGRESS]
    productIds: [{product_id}]
  ) {{
    findings {{
      id
      title
      severity
      status
      product {{
        id
        name
      }}
    }}
    pageInfo {{
      totalElements
      totalPages
      hasNext
    }}
  }}
}}
"""

print("GraphQL Query:")
print(query)
print()

try:
    response = post(graphql_url, headers=headers, json={'query': query}, timeout=60)

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print("\nResponse:")
        print(json.dumps(data, indent=2)[:2000])

        if 'data' in data and 'findings' in data['data']:
            findings_data = data['data']['findings']
            findings = findings_data.get('findings', [])
            page_info = findings_data.get('pageInfo', {})

            print("\n" + "="*70)
            print("RESULTS")
            print("="*70)
            print(f"Total findings: {page_info.get('totalElements', 'N/A')}")
            print(f"Findings in this page: {len(findings)}")

            if findings:
                print("\nFirst 5 findings:")
                for i, f in enumerate(findings[:5], 1):
                    product_info = f.get('product', {})
                    print(f"\n  {i}. [{f.get('severity')}] {f.get('title', 'No title')[:50]}")
                    print(f"     Product: {product_info.get('name', 'Unknown')} (ID: {product_info.get('id', 'N/A')})")
                    print(f"     Status: {f.get('status')}")

                # Check if all findings are for the correct product
                correct_product = sum(1 for f in findings if f.get('product', {}).get('id') == product_id)
                print(f"\n  Findings for correct product: {correct_product}/{len(findings)}")

                if correct_product == len(findings):
                    print("  [OK] All findings are for the requested product!")
                else:
                    print("  [WARNING] Some findings are for other products")
        elif 'errors' in data:
            print("\n[ERROR] GraphQL query returned errors:")
            print(json.dumps(data['errors'], indent=2))
    else:
        print(f"[ERROR] HTTP {response.status_code}")
        print(response.text[:500])

except Exception as e:
    print(f"[ERROR] Exception: {e}")

print("\n" + "="*70)
print("Test Complete")
print("="*70)
