"""Test GraphQL with correct schema structure"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
graphql_url = 'https://app.armorcode.com/api/graphql'
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

print("="*70)
print("GRAPHQL TEST WITH CORRECT SCHEMA")
print("="*70)

# Test 1: Query all products (correct structure)
print("\n1. Query all products (correct schema)")
print("-"*70)

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
      page
      size
      totalPages
      totalElements
    }
  }
}
"""

try:
    response = requests.post(graphql_url, headers=headers, json={'query': query}, timeout=60)
    print(f"Status: {response.status_code}")
    data = response.json()

    if 'data' in data and 'products' in data['data']:
        products = data['data']['products']['products']
        page_info = data['data']['products']['pageInfo']

        print(f"Page: {page_info.get('page')} of {page_info.get('totalPages')}")
        print(f"Total products: {page_info.get('totalElements')}")
        print(f"\nProducts found ({len(products)}):")
        for p in products:
            print(f"  - {p.get('name')} (ID: {p.get('id')})")

        # Check for Legal products
        legal_keywords = ['Legal', 'Access', 'Eclipse', 'Proclaim', 'inCase']
        legal_products = [p for p in products if any(kw in p.get('name', '') for kw in legal_keywords)]
        print(f"\nLegal-related products: {len(legal_products)}")
        for p in legal_products:
            print(f"  ✓ {p.get('name')}")
    else:
        print(f"Response:\n{json.dumps(data, indent=2)}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Query findings with correct severity enum and product filter
print("\n\n2. Query findings with FindingFilter (correct schema)")
print("-"*70)

query = """
{
  findings(page: 0, size: 5, findingFilter: {
    severity: [High, Critical]
  }) {
    findings {
      id
      title
      severity
      product {
        id
        name
      }
      subProduct {
        id
        name
      }
    }
    pageInfo {
      page
      size
      totalPages
      totalElements
    }
  }
}
"""

try:
    response = requests.post(graphql_url, headers=headers, json={'query': query}, timeout=60)
    print(f"Status: {response.status_code}")
    data = response.json()

    if 'data' in data and 'findings' in data['data']:
        findings = data['data']['findings']['findings']
        page_info = data['data']['findings']['pageInfo']

        print(f"Total HIGH+CRITICAL findings: {page_info.get('totalElements')}")
        print(f"\nSample findings ({len(findings)}):")
        for f in findings:
            print(f"  - [{f.get('severity')}] {f.get('title')[:60]}...")
            print(f"    Product: {f['product'].get('name') if f.get('product') else 'None'}")
    else:
        print(f"Response:\n{json.dumps(data, indent=2)[:1500]}")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Try to query findings with specific product name filter
print("\n\n3. Try FindingFilter with product name 'Access Legal Case Management'")
print("-"*70)

query = """
{
  findings(page: 0, size: 5, findingFilter: {
    severity: [High, Critical],
    product: "Access Legal Case Management"
  }) {
    findings {
      id
      title
      product {
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
    response = requests.post(graphql_url, headers=headers, json={'query': query}, timeout=60)
    print(f"Status: {response.status_code}")
    data = response.json()

    if 'data' in data and 'findings' in data['data']:
        findings = data['data']['findings']['findings']
        total = data['data']['findings']['pageInfo'].get('totalElements')

        print(f"Total findings for 'Access Legal Case Management': {total}")
        if findings:
            print(f"Sample findings ({len(findings)}):")
            for f in findings:
                print(f"  - {f.get('title')[:60]}... ({f['product'].get('name')})")
        else:
            print("  No findings returned (likely BU scope limitation)")
    else:
        print(f"Response:\n{json.dumps(data, indent=2)[:1500]}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*70)
print("GraphQL Test Complete")
print("="*70)
