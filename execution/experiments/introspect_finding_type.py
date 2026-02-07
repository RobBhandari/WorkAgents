"""Introspect Finding type fields in ArmorCode GraphQL"""
import json
import os

import requests
from dotenv import load_dotenv
from http_client import delete, get, patch, post, put

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
graphql_url = 'https://app.armorcode.com/api/graphql'
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

print("="*70)
print("INTROSPECTING FINDING TYPE FIELDS")
print("="*70)

# Introspection query for Finding type
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
    response = post(graphql_url, headers=headers, json={'query': query}, timeout=60)

    if response.status_code == 200:
        data = response.json()

        if 'data' in data and '__type' in data['data']:
            finding_type = data['data']['__type']
            fields = finding_type.get('fields', [])

            print(f"\nAvailable fields on Finding type ({len(fields)} fields):\n")

            for field in sorted(fields, key=lambda x: x['name']):
                field_name = field['name']
                field_type = field['type'].get('name', 'N/A')
                print(f"  - {field_name}: {field_type}")

            # Save for reference
            with open('.tmp/finding_type_fields.json', 'w') as f:
                json.dump(data, f, indent=2)
            print("\nFull data saved to .tmp/finding_type_fields.json")
        else:
            print("Error: Unexpected response structure")
            print(json.dumps(data, indent=2))
    else:
        print(f"Error: HTTP {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*70)
