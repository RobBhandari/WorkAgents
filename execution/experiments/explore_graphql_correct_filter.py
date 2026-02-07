"""Test GraphQL findings with correct filter field names"""
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

print("="*70)
print("TESTING GRAPHQL FINDINGS WITH CORRECT FILTER")
print("="*70)
print("Product: Access Diversity (ID: 10480)")
print("Expected from UI: 2 HIGH findings")
print()

# Test with correct field names and enum values
test_query = """
{
  findings(
    page: 1
    size: 50
    findingFilter: {
      product: [10480]
      severity: [High, Critical]
      status: ["Open", "In Progress"]
    }
  ) {
    findings {
      id
      title
      severity
      status
      product {
        id
        name
      }
    }
    pageInfo {
      totalElements
      hasNext
    }
  }
}
"""

print("Query with filter:")
print("  product: [10480]")
print("  severity: [High, Critical]")
print("  status: [\"Open\", \"In Progress\"]")
print()

try:
    response = post(graphql_url, headers=headers, json={'query': test_query}, timeout=60)

    if response.status_code == 200:
        data = response.json()

        if 'errors' in data:
            print("[ERROR] Query failed:")
            for err in data['errors']:
                print(f"  - {err.get('message')}")
        elif 'data' in data and 'findings' in data['data']:
            findings_data = data['data']['findings']
            findings = findings_data.get('findings', [])
            total = findings_data.get('pageInfo', {}).get('totalElements', 0)

            print("[OK] Query successful!")
            print(f"Total findings: {total}")
            print(f"Returned in page: {len(findings)}")
            print()

            if findings:
                print("Findings:")
                print("-"*70)
                for i, f in enumerate(findings, 1):
                    prod = f.get('product', {})
                    print(f"{i}. [{f.get('severity')}] {f.get('status')}")
                    print(f"   Product: {prod.get('name')} (ID: {prod.get('id')})")
                    print(f"   Title: {f.get('title', 'No title')[:60]}")
                    print()

                # Verify filtering
                correct_product = sum(1 for f in findings if f.get('product', {}).get('id') == 10480)
                high_critical = sum(1 for f in findings if f.get('severity') in ['HIGH', 'CRITICAL'])

                print("="*70)
                print("VERIFICATION")
                print("="*70)
                print(f"Findings for Access Diversity: {correct_product}/{len(findings)}")
                print(f"Findings that are HIGH/CRITICAL: {high_critical}/{len(findings)}")

                if correct_product == len(findings) and high_critical == len(findings):
                    print("\n[SUCCESS] GraphQL filtering works correctly!")
                    print(f"Total findings for Access Diversity HIGH+CRITICAL: {total}")

                    if total == 2:
                        print("[PERFECT] Matches UI expectation of 2 findings!")
                    else:
                        print(f"[NOTE] UI shows 2, API shows {total} - need to check status filter")
            else:
                print("No findings returned")

        else:
            print("Unexpected response structure")
            print(json.dumps(data, indent=2)[:500])
    else:
        print(f"[ERROR] HTTP {response.status_code}")
        print(response.text[:500])

except Exception as e:
    print(f"[ERROR] Exception: {e}")

print("\n" + "="*70)
print("Test Complete")
print("="*70)
