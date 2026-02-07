"""Query findings for specific Legal products by ID"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
base_url = 'https://app.armorcode.com'
graphql_url = f'{base_url}/api/graphql'
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

print("="*70)
print("QUERY FINDINGS FOR LEGAL PRODUCTS")
print("="*70)

# Step 1: Get all products to find Legal ones
print("\n1. Fetching all products to get Legal product IDs...")
print("-"*70)

all_products = []
for page in range(1, 5):  # 4 pages total
    query = f"""
    {{
      products(page: {page}, size: 100) {{
        products {{
          id
          name
        }}
        pageInfo {{
          hasNext
        }}
      }}
    }}
    """

    response = requests.post(graphql_url, headers=headers, json={'query': query}, timeout=60)
    data = response.json()

    if 'data' in data and 'products' in data['data']:
        products = data['data']['products']['products']
        all_products.extend(products)
        print(f"  Page {page}: {len(products)} products")
    else:
        print(f"  Page {page}: Error or no data")
        break

# Find Legal products
target_product_names = [
    'Access Legal Case Management',
    'Access Legal Compliance',
    'Access Legal Framework',
    'Legal Bricks',
    'Eclipse',
    'Proclaim',
    'inCase',
    'Law Fusion',
    'Access Diversity',
    'Proclaim Portals - Eclipse',
    'Legal Workspace',
    'Access MyCalendars',
    'One Office & Financial Director',
    'Access Legal AI Services',
]

legal_products = {}
for product in all_products:
    if product['name'] in target_product_names:
        legal_products[product['name']] = product['id']

print(f"\nFound {len(legal_products)} Legal products:")
for name, pid in sorted(legal_products.items()):
    print(f"  [{pid}] {name}")

# Step 2: Query findings for each Legal product using REST API
print("\n\n2. Querying findings for each Legal product...")
print("-"*70)

total_findings = 0
products_with_findings = []

for product_name, product_id in sorted(legal_products.items()):
    # Try REST API with product filter
    request_body = {
        "severity": ["HIGH", "CRITICAL"],
        "status": ["Open", "In Progress"],
        "product": [product_id]  # Try filtering by product ID
    }

    try:
        response = requests.post(
            f"{base_url}/api/findings",
            headers=headers,
            json=request_body,
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                findings = data['data'].get('findings', [])
                if len(findings) > 0:
                    total_findings += len(findings)
                    products_with_findings.append((product_name, len(findings)))
                    print(f"  [{product_id}] {product_name}: {len(findings)} findings")
                else:
                    print(f"  [{product_id}] {product_name}: 0 findings")
        else:
            print(f"  [{product_id}] {product_name}: HTTP {response.status_code}")

    except Exception as e:
        print(f"  [{product_id}] {product_name}: Error - {str(e)[:50]}")

print(f"\n{'='*70}")
if total_findings > 0:
    print(f"[SUCCESS] Found {total_findings} HIGH+CRITICAL findings across Legal products!")
    print(f"\nProducts with findings:")
    for name, count in products_with_findings:
        print(f"  - {name}: {count}")
else:
    print(f"[!] No findings returned when filtering by Legal product IDs")
    print(f"\nThis suggests:")
    print(f"  1. Legal products may not have HIGH/CRITICAL findings currently")
    print(f"  2. Product ID filtering might not work in REST API")
    print(f"  3. Need to try GraphQL findings query instead")
print(f"{'='*70}")

print("\n" + "="*70)
print("Test Complete")
print("="*70)
