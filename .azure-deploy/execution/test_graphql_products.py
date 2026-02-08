"""Query products via GraphQL with correct pagination"""

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ARMORCODE_API_KEY")
graphql_url = "https://app.armorcode.com/api/graphql"
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

print("=" * 70)
print("GRAPHQL PRODUCTS QUERY")
print("=" * 70)

# Query products with correct page numbering (starts at 1)
query = """
{
  products(page: 1, size: 100) {
    products {
      id
      name
      tier
      status
    }
    pageInfo {
      totalElements
      totalPages
      hasNext
    }
  }
}
"""

print("\nQuerying all accessible products via GraphQL...")
print("-" * 70)

try:
    response = requests.post(graphql_url, headers=headers, json={"query": query}, timeout=60)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()

        if "errors" in data:
            print("\n[ERROR] GraphQL Errors:")
            for err in data["errors"]:
                print(f"  - {err['message']}")
            print(f"\nFull response:\n{json.dumps(data, indent=2)[:1000]}")

        if "data" in data and "products" in data["data"] and data["data"]["products"]:
            result = data["data"]["products"]
            products = result.get("products", [])
            page_info = result.get("pageInfo", {})

            total = page_info.get("totalElements", 0)
            total_pages = page_info.get("totalPages", 0)

            print(f"\n[SUCCESS] API Key has access to {total} total products")
            print(f"Pages: {total_pages}, Returned: {len(products)} products")

            print("\nAll accessible products:")
            for p in products:
                print(f"  [{p.get('id')}] {p.get('name')} - {p.get('status', 'N/A')}")

            # Check for Legal products
            legal_keywords = [
                "Legal",
                "Eclipse",
                "Proclaim",
                "inCase",
                "Fusion",
                "Bricks",
                "Workspace",
                "Diversity",
                "MyCalendars",
                "Office",
            ]
            legal_products = [p for p in products if any(kw in p.get("name", "") for kw in legal_keywords)]

            print(f"\n{'='*70}")
            if legal_products:
                print(f"[SUCCESS!] Found {len(legal_products)} Legal products:")
                for p in legal_products:
                    print(f"  [+] {p.get('name')}")
                print("\nThe API key DOES have access to Legal products!")
                print("Issue might be with the /api/findings endpoint filtering")
            else:
                print("[!] No Legal products found")
                print("    API key only has access to:")
                for p in products:
                    print(f"      - {p.get('name')}")
            print(f"{'='*70}")

        else:
            print("\n[ERROR] Unexpected response structure:")
            print(json.dumps(data, indent=2)[:1000])

    else:
        print(f"[ERROR] HTTP {response.status_code}")
        print(response.text[:500])

except Exception as e:
    print(f"[ERROR] Exception: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 70)
print("GraphQL Products Query Complete")
print("=" * 70)
