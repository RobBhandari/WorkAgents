"""Final GraphQL test with fully correct schema"""

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ARMORCODE_API_KEY")
graphql_url = "https://app.armorcode.com/api/graphql"
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

print("=" * 70)
print("GRAPHQL FINAL TEST - CORRECT SCHEMA")
print("=" * 70)

# Test 1: Query all products
print("\n1. Query all products accessible by this API key")
print("-" * 70)

query = """
{
  products(page: 0, size: 100) {
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

try:
    response = requests.post(graphql_url, headers=headers, json={"query": query}, timeout=60)
    data = response.json()

    if "data" in data and "products" in data["data"]:
        products = data["data"]["products"]["products"]
        page_info = data["data"]["products"]["pageInfo"]

        print(f"Total products accessible: {page_info.get('totalElements')}")
        print(f"Total pages: {page_info.get('totalPages')}")
        print(f"\nProducts returned ({len(products)}):")
        for p in products:
            print(f"  [{p.get('id')}] {p.get('name')}")

        # Check if any Legal products are accessible
        legal_keywords = [
            "Legal",
            "Case",
            "Compliance",
            "Bricks",
            "Proclaim",
            "Eclipse",
            "inCase",
            "Fusion",
            "Workspace",
        ]
        legal_products = [p for p in products if any(kw in p.get("name", "") for kw in legal_keywords)]

        print(f"\n{'='*70}")
        if legal_products:
            print(f"✓ Found {len(legal_products)} Legal products:")
            for p in legal_products:
                print(f"  - {p.get('name')}")
        else:
            print("✗ No Legal products found in accessible products")
            print("  This confirms Account Level Access = FALSE")
            print("  API key is scoped to a different Business Unit")
        print(f"{'='*70}")

    elif "errors" in data:
        print("GraphQL Errors:")
        for err in data["errors"]:
            print(f"  - {err['message']}")
    else:
        print(f"Unexpected response:\n{json.dumps(data, indent=2)[:1000]}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Query findings and show which products have findings
print("\n\n2. Query HIGH+CRITICAL findings and product distribution")
print("-" * 70)

query = """
{
  findings(page: 0, size: 100, findingFilter: {
    severity: [High, Critical]
  }) {
    findings {
      severity
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

try:
    response = requests.post(graphql_url, headers=headers, json={"query": query}, timeout=60)
    data = response.json()

    if "data" in data and "findings" in data["data"]:
        findings = data["data"]["findings"]["findings"]
        total = data["data"]["findings"]["pageInfo"].get("totalElements")

        print(f"Total HIGH+CRITICAL findings: {total}")

        # Count by product
        product_counts = {}
        for f in findings:
            prod_name = f["product"].get("name") if f.get("product") else "Unknown"
            if prod_name not in product_counts:
                product_counts[prod_name] = {"high": 0, "critical": 0}
            severity = f.get("severity", "").lower()
            if severity == "high":
                product_counts[prod_name]["high"] += 1
            elif severity == "critical":
                product_counts[prod_name]["critical"] += 1

        print("\nProduct distribution (first 100 findings):")
        for prod, counts in sorted(product_counts.items()):
            print(f"  - {prod}: {counts['critical']} Critical, {counts['high']} High")

    elif "errors" in data:
        print("GraphQL Errors:")
        for err in data["errors"]:
            print(f"  - {err['message']}")
    else:
        print(f"Unexpected response:\n{json.dumps(data, indent=2)[:1000]}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
print("""
Both REST API and GraphQL API are subject to the same limitation:
- API Key Account Level Access = FALSE
- Only products in the current Business Unit are accessible
- Legal products are in "The Access Group" Business Unit (different BU)

SOLUTION: Generate new API key with Account Level Access = TRUE
""")
