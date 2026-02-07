"""Introspect ProductFilter and FindingFilter types"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
graphql_url = 'https://app.armorcode.com/api/graphql'
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

print("="*70)
print("GRAPHQL SCHEMA INTROSPECTION - FILTERS")
print("="*70)

# Introspect ProductFilter type
print("\n1. ProductFilter input type structure")
print("-"*70)
query = """
{
  __type(name: "ProductFilter") {
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
    response = requests.post(graphql_url, headers=headers, json={'query': query}, timeout=60)
    data = response.json()
    if 'data' in data and '__type' in data['data'] and data['data']['__type']:
        fields = data['data']['__type']['inputFields']
        print(f"ProductFilter has {len(fields)} input fields:")
        for f in fields:
            type_info = f['type']
            if type_info.get('ofType'):
                type_name = f"{type_info['name']}[{type_info['ofType']['name']}]"
            else:
                type_name = type_info.get('name', 'Unknown')
            print(f"  - {f['name']}: {type_name}")
    else:
        print("ProductFilter type not found or structure different")
        print(json.dumps(data, indent=2)[:1000])
except Exception as e:
    print(f"Error: {e}")

# Introspect FindingFilter type
print("\n\n2. FindingFilter input type structure")
print("-"*70)
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
    response = requests.post(graphql_url, headers=headers, json={'query': query}, timeout=60)
    data = response.json()
    if 'data' in data and '__type' in data['data'] and data['data']['__type']:
        fields = data['data']['__type']['inputFields']
        print(f"FindingFilter has {len(fields)} input fields:")
        for f in fields[:20]:  # Show first 20
            type_info = f['type']
            if type_info.get('ofType'):
                type_name = f"{type_info['name']}[{type_info['ofType']['name']}]"
            else:
                type_name = type_info.get('name', 'Unknown')
            print(f"  - {f['name']}: {type_name}")
        if len(fields) > 20:
            print(f"  ... and {len(fields) - 20} more fields")
    else:
        print("FindingFilter type not found")
        print(json.dumps(data, indent=2)[:1000])
except Exception as e:
    print(f"Error: {e}")

# Introspect ProductPageResult type
print("\n\n3. ProductPageResult return type structure")
print("-"*70)
query = """
{
  __type(name: "ProductPageResult") {
    name
    kind
    fields {
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
    response = requests.post(graphql_url, headers=headers, json={'query': query}, timeout=60)
    data = response.json()
    if 'data' in data and '__type' in data['data'] and data['data']['__type']:
        fields = data['data']['__type']['fields']
        print(f"ProductPageResult has {len(fields)} fields:")
        for f in fields:
            type_info = f['type']
            if type_info.get('ofType'):
                type_name = f"{type_info['name']}[{type_info['ofType']['name']}]"
            else:
                type_name = type_info.get('name', 'Unknown')
            print(f"  - {f['name']}: {type_name}")
    else:
        print("ProductPageResult type not found")
        print(json.dumps(data, indent=2)[:1000])
except Exception as e:
    print(f"Error: {e}")

# Introspect Severity enum
print("\n\n4. Severity enum values")
print("-"*70)
query = """
{
  __type(name: "Severity") {
    name
    kind
    enumValues {
      name
    }
  }
}
"""

try:
    response = requests.post(graphql_url, headers=headers, json={'query': query}, timeout=60)
    data = response.json()
    if 'data' in data and '__type' in data['data'] and data['data']['__type']:
        values = data['data']['__type']['enumValues']
        print(f"Severity enum has {len(values)} values:")
        for v in values:
            print(f"  - {v['name']}")
    else:
        print("Severity type not found")
        print(json.dumps(data, indent=2)[:1000])
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*70)
print("Schema Introspection Complete")
print("="*70)
