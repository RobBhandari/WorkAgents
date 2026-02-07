"""Query GraphQL schema to find FindingFilter fields"""
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
print("QUERYING FindingFilter SCHEMA")
print("="*70)

# Query to get FindingFilter input type definition
query = """
{
  __type(name: "FindingFilter") {
    name
    kind
    inputFields {
      name
      type {
        name
        kind
        ofType {
          name
          kind
        }
      }
    }
  }
}
"""

try:
    response = post(graphql_url, headers=headers, json={'query': query}, timeout=60)

    if response.status_code == 200:
        data = response.json()

        if 'data' in data and '__type' in data['data']:
            filter_type = data['data']['__type']

            print(f"\nType: {filter_type.get('name')}")
            print(f"Kind: {filter_type.get('kind')}")
            print("\nAvailable filter fields:")
            print("-"*70)

            for field in filter_type.get('inputFields', []):
                field_name = field['name']
                field_type = field.get('type', {})
                type_name = field_type.get('name') or field_type.get('ofType', {}).get('name', 'Unknown')

                print(f"  {field_name}: {type_name}")

            # Now let's test using the filter with productIds
            print("\n" + "="*70)
            print("TESTING FINDINGS QUERY WITH FILTER")
            print("="*70)

            test_query = """
            {
              findings(
                page: 1
                size: 10
                findingFilter: {
                  productIds: [10480]
                  severities: [HIGH, CRITICAL]
                  statuses: [OPEN]
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
                }
              }
            }
            """

            print("\nTesting with Access Diversity (ID: 10480)")
            print("Filter: productIds=[10480], severities=[HIGH,CRITICAL], statuses=[OPEN]")

            test_response = post(graphql_url, headers=headers, json={'query': test_query}, timeout=60)

            if test_response.status_code == 200:
                test_data = test_response.json()

                if 'errors' in test_data:
                    print("\n[ERROR] Query failed:")
                    for err in test_data['errors']:
                        print(f"  - {err.get('message')}")
                elif 'data' in test_data and 'findings' in test_data['data']:
                    findings_data = test_data['data']['findings']
                    findings = findings_data.get('findings', [])
                    total = findings_data.get('pageInfo', {}).get('totalElements', 0)

                    print("\n[OK] Query successful!")
                    print(f"Total findings: {total}")
                    print(f"Returned: {len(findings)}")

                    if findings:
                        print("\nFindings:")
                        for i, f in enumerate(findings, 1):
                            prod = f.get('product', {})
                            print(f"  {i}. [{f.get('severity')}] {prod.get('name')} - {f.get('title', 'No title')[:40]}")

                        # Check if all are for correct product
                        correct = sum(1 for f in findings if f.get('product', {}).get('id') == 10480)
                        print(f"\nProduct filter working: {correct}/{len(findings)} findings are for Access Diversity")

                        if correct == len(findings) and total > 0:
                            print("\n" + "="*70)
                            print("[SUCCESS] GraphQL FILTER WORKS!")
                            print("="*70)
                            print("We can use GraphQL to fetch findings with proper filtering!")
        else:
            print("Unexpected response")
            print(json.dumps(data, indent=2)[:500])
    else:
        print(f"[ERROR] HTTP {response.status_code}")

except Exception as e:
    print(f"[ERROR] Exception: {e}")

print("\n" + "="*70)
print("Test Complete")
print("="*70)
