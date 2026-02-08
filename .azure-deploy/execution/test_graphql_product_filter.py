"""Test GraphQL productFilter to access Legal products"""

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ARMORCODE_API_KEY")
graphql_url = "https://app.armorcode.com/api/graphql"
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

print("=" * 70)
print("GRAPHQL PRODUCT FILTER TEST")
print("=" * 70)

# Test 1: Query products with filter for "Access Legal Case Management"
print("\n1. Test productFilter for 'Access Legal Case Management'")
print("-" * 70)

query = """
{
  products(page: 0, size: 10, productFilter: {name: "Access Legal Case Management"}) {
    id
    name
    tier
    status
  }
}
"""

try:
    response = requests.post(graphql_url, headers=headers, json={"query": query}, timeout=60)
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response:\n{json.dumps(data, indent=2)[:1500]}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Query products with filter for "Legal Bricks"
print("\n\n2. Test productFilter for 'Legal Bricks'")
print("-" * 70)

query = """
{
  products(page: 0, size: 10, productFilter: {name: "Legal Bricks"}) {
    id
    name
    tier
    status
  }
}
"""

try:
    response = requests.post(graphql_url, headers=headers, json={"query": query}, timeout=60)
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response:\n{json.dumps(data, indent=2)[:1500]}")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Query ALL products without filter
print("\n\n3. Query ALL products (no filter)")
print("-" * 70)

query = """
{
  products(page: 0, size: 100) {
    id
    name
    tier
    status
  }
}
"""

try:
    response = requests.post(graphql_url, headers=headers, json={"query": query}, timeout=60)
    print(f"Status: {response.status_code}")
    data = response.json()

    if "data" in data and "products" in data["data"]:
        products = data["data"]["products"]
        print(f"Found {len(products)} products:")
        for p in products:
            print(f"  - {p.get('name')} (ID: {p.get('id')})")

        # Check if any Legal products are in the list
        legal_products = [
            p for p in products if any(x in p.get("name", "") for x in ["Legal", "Access", "Eclipse", "Proclaim"])
        ]
        print(f"\nLegal-related products: {len(legal_products)}")
        for p in legal_products:
            print(f"  - {p.get('name')}")
    else:
        print(f"Response:\n{json.dumps(data, indent=2)[:1500]}")
except Exception as e:
    print(f"Error: {e}")

# Test 4: Query findings with findingFilter for specific product
print("\n\n4. Test findingFilter for specific product")
print("-" * 70)

query = """
{
  findings(page: 0, size: 5, findingFilter: {
    severity: [HIGH, CRITICAL],
    product: "Access Legal Case Management"
  }) {
    id
    title
    severity
    product {
      id
      name
    }
  }
}
"""

try:
    response = requests.post(graphql_url, headers=headers, json={"query": query}, timeout=60)
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response:\n{json.dumps(data, indent=2)[:1500]}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 70)
print("GraphQL Product Filter Test Complete")
print("=" * 70)
