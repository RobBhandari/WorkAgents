"""Introspect ArmorCode GraphQL schema"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
graphql_url = 'https://app.armorcode.com/api/graphql'
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

print("="*70)
print("GRAPHQL SCHEMA INTROSPECTION")
print("="*70)

# Query root types
query = """
{
  __schema {
    queryType {
      fields {
        name
        description
        args {
          name
          type {
            name
            kind
          }
        }
        type {
          name
          kind
        }
      }
    }
  }
}
"""

response = requests.post(graphql_url, headers=headers, json={'query': query}, timeout=60)
data = response.json()

if 'data' in data:
    fields = data['data']['__schema']['queryType']['fields']

    # Find product-related queries
    print("\nProduct-related queries:")
    product_queries = [f for f in fields if 'product' in f['name'].lower()]
    for q in product_queries:
        print(f"\n  {q['name']}: {q.get('description', 'No description')}")
        if q['args']:
            print(f"    Args: {[a['name'] for a in q['args']]}")
        print(f"    Returns: {q['type']['name']}")

    # Find finding-related queries
    print("\n\nFinding-related queries:")
    finding_queries = [f for f in fields if 'finding' in f['name'].lower()]
    for q in finding_queries:
        print(f"\n  {q['name']}: {q.get('description', 'No description')}")
        if q['args']:
            print(f"    Args: {[a['name'] for a in q['args']]}")
        print(f"    Returns: {q['type']['name']}")

    # Save full schema for reference
    with open('.tmp/graphql_schema.json', 'w') as f:
        json.dump(data, f, indent=2)
    print("\n\nFull schema saved to .tmp/graphql_schema.json")

else:
    print(f"Error: {data}")
