"""Try to query products directly via API"""

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ARMORCODE_API_KEY")
base_url = "https://app.armorcode.com"
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

print("=" * 70)
print("QUERY PRODUCTS VIA API")
print("=" * 70)

# Test different product-related endpoints
endpoints = [
    "/api/products",
    "/api/v1/products",
    "/api/product",
    "/api/products/all",
    "/graphql",
]

print("\n1. Testing GET endpoints")
print("-" * 70)

for endpoint in endpoints:
    try:
        response = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=30)
        print(f"\nGET {endpoint}: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Success! Keys: {list(data.keys())[:5]}")

            # Save for inspection
            filename = f".tmp/api_products_{endpoint.replace('/', '_')}.json"
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)
            print(f"  Saved to {filename}")
        elif response.status_code != 404:
            print(f"  Response: {response.text[:200]}")
    except Exception as e:
        print(f"  Error: {str(e)[:100]}")

# Test GraphQL products query
print("\n\n2. Testing GraphQL products query")
print("-" * 70)

query = """
{
  products(page: 0, size: 100) {
    products {
      id
      name
      description
    }
    pageInfo {
      totalElements
    }
  }
}
"""

try:
    response = requests.post(f"{base_url}/api/graphql", headers=headers, json={"query": query}, timeout=60)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()

        if "errors" in data:
            print("GraphQL Errors:")
            for err in data["errors"]:
                print(f"  - {err['message']}")

        if "data" in data and "products" in data["data"]:
            products = data["data"]["products"]["products"]
            total = data["data"]["products"]["pageInfo"]["totalElements"]

            print(f"\nTotal products accessible via GraphQL: {total}")
            print(f"Products returned ({len(products)}):")
            for p in products:
                print(f"  [{p.get('id')}] {p.get('name')}")

            # Check for Legal products
            legal_keywords = ["Legal", "Eclipse", "Proclaim", "inCase", "Fusion", "Bricks", "Workspace", "Diversity"]
            legal_products = [p for p in products if any(kw in p.get("name", "") for kw in legal_keywords)]

            if legal_products:
                print(f"\n[SUCCESS] Found {len(legal_products)} Legal products via GraphQL!")
                for p in legal_products:
                    print(f"  - {p.get('name')}")
            else:
                print("\n[!] No Legal products found in GraphQL response")

        else:
            print(f"Response: {json.dumps(data, indent=2)[:1000]}")
    else:
        print(f"Error: {response.text[:500]}")

except Exception as e:
    print(f"Error: {e}")

# Test POST to products endpoint
print("\n\n3. Testing POST to /api/products")
print("-" * 70)

try:
    response = requests.post(f"{base_url}/api/products", headers=headers, json={}, timeout=60)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print("Success! Response structure:")
        print(json.dumps(data, indent=2)[:1000])
    else:
        print(f"Response: {response.text[:300]}")

except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 70)
print("Products Query Complete")
print("=" * 70)
