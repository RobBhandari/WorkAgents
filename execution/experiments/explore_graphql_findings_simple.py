"""Test GraphQL findings query with minimal parameters"""
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
print("TESTING GRAPHQL FINDINGS - SIMPLE QUERY")
print("="*70)

# Try basic query without filters
query = """
{
  findings(page: 1, size: 10) {
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

print("Query: Basic findings query (no filters)")
print()

try:
    response = post(graphql_url, headers=headers, json={'query': query}, timeout=60)

    if response.status_code == 200:
        data = response.json()

        if 'errors' in data:
            print("[ERROR] GraphQL query returned errors:")
            print(json.dumps(data['errors'], indent=2))
        elif 'data' in data and 'findings' in data['data']:
            findings_data = data['data']['findings']
            findings = findings_data.get('findings', [])
            page_info = findings_data.get('pageInfo', {})

            print("[OK] Query successful!")
            print(f"Total findings: {page_info.get('totalElements', 'N/A')}")
            print(f"Findings returned: {len(findings)}")

            if findings:
                print("\nFirst 3 findings:")
                for i, f in enumerate(findings[:3], 1):
                    product_info = f.get('product', {})
                    print(f"  {i}. [{f.get('severity')}] {product_info.get('name', 'Unknown')}")
                    print(f"      Status: {f.get('status')}")

            # Now try to introspect what filters are available
            print("\n" + "="*70)
            print("Now testing GraphQL introspection to find available arguments...")
            print("="*70)

            introspection_query = """
            {
              __type(name: "Query") {
                fields {
                  name
                  args {
                    name
                    type {
                      name
                      kind
                    }
                  }
                }
              }
            }
            """

            intro_response = post(graphql_url, headers=headers, json={'query': introspection_query}, timeout=60)
            if intro_response.status_code == 200:
                intro_data = intro_response.json()
                if 'data' in intro_data:
                    query_type = intro_data['data'].get('__type', {})
                    fields = query_type.get('fields', [])

                    # Find the findings field
                    findings_field = next((f for f in fields if f['name'] == 'findings'), None)
                    if findings_field:
                        print("\nAvailable arguments for 'findings' query:")
                        for arg in findings_field.get('args', []):
                            print(f"  - {arg['name']}: {arg.get('type', {}).get('name', 'Unknown')}")
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
