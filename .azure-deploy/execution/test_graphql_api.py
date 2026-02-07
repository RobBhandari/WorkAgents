"""Test ArmorCode GraphQL API"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
base_url = 'https://app.armorcode.com'
graphql_url = f'{base_url}/api/graphql'

headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

print("="*70)
print("ARMORCODE GRAPHQL API EXPLORATION")
print("="*70)

# Test 1: Query for products
print("\n1. Query all products")
print("-"*70)
query = """
{
  products {
    id
    name
    tier
    status
  }
}
"""

try:
    response = requests.post(graphql_url, headers=headers, json={'query': query}, timeout=60)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if 'data' in data and 'products' in data['data']:
            products = data['data']['products']
            print(f"Found {len(products)} products:")
            for p in products[:20]:  # Show first 20
                print(f"  - {p.get('name')} (ID: {p.get('id')})")
        else:
            print(f"Response: {json.dumps(data, indent=2)[:1000]}")
    else:
        print(f"Error: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Query findings with filters
print("\n\n2. Query findings with product filter")
print("-"*70)
query = """
{
  findings(first: 5, severity: [HIGH, CRITICAL]) {
    edges {
      node {
        id
        title
        severity
        product {
          id
          name
        }
      }
    }
    totalCount
  }
}
"""

try:
    response = requests.post(graphql_url, headers=headers, json={'query': query}, timeout=60)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Response structure:")
        print(json.dumps(data, indent=2)[:1500])
    else:
        print(f"Error: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Introspection - what fields are available?
print("\n\n3. Schema introspection - Finding type")
print("-"*70)
query = """
{
  __type(name: "Finding") {
    name
    fields {
      name
      type {
        name
        kind
      }
    }
  }
}
"""

try:
    response = requests.post(graphql_url, headers=headers, json={'query': query}, timeout=60)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if 'data' in data and '__type' in data['data']:
            fields = data['data']['__type']['fields']
            print(f"Finding type has {len(fields)} fields")
            # Look for organization/hierarchy fields
            org_fields = [f for f in fields if any(x in f['name'].lower() for x in ['org', 'hierarchy', 'project', 'team'])]
            if org_fields:
                print("\nOrganization/Hierarchy related fields:")
                for f in org_fields:
                    print(f"  - {f['name']}: {f['type']['name']}")
    else:
        print(f"Error: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*70)
print("GraphQL Exploration Complete")
print("="*70)
