"""Deep exploration of ArmorCode API structure"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
base_url = 'https://app.armorcode.com'
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

print("="*70)
print("ARMORCODE API EXPLORATION")
print("="*70)

# 1. Get a sample finding with ALL fields
print("\n1. SAMPLE FINDING - ALL FIELDS")
print("-"*70)
resp = requests.post(f"{base_url}/api/findings", headers=headers, json={"severity": ["HIGH"]}, timeout=60)
finding = resp.json()['data']['findings'][0]

# Group fields by category
org_fields = {}
product_fields = {}
owner_fields = {}
meta_fields = {}

for key, value in finding.items():
    if any(x in key.lower() for x in ['org', 'hierarchy', 'tenant']):
        org_fields[key] = value
    elif any(x in key.lower() for x in ['product', 'subproduct', 'component']):
        product_fields[key] = value
    elif any(x in key.lower() for x in ['owner', 'team']):
        owner_fields[key] = value
    elif any(x in key.lower() for x in ['project', 'armorcode']):
        meta_fields[key] = value

print("\nOrganization/Hierarchy fields:")
for k, v in org_fields.items():
    print(f"  {k}: {v}")

print("\nProduct fields:")
for k, v in product_fields.items():
    if isinstance(v, dict):
        print(f"  {k}: {v}")
    else:
        print(f"  {k}: {str(v)[:100]}")

print("\nOwnership/Team fields:")
for k, v in owner_fields.items():
    print(f"  {k}: {v}")

print("\nArmorCode Project fields:")
for k, v in meta_fields.items():
    print(f"  {k}: {v}")

# 2. Try alternative API endpoints
print("\n\n2. TESTING ALTERNATIVE ENDPOINTS")
print("-"*70)

endpoints_to_test = [
    '/api/products',
    '/api/organizations',
    '/api/hierarchies',
    '/api/projects',
    '/api/user/info',
    '/api/user/permissions',
    '/api/account/info',
]

for endpoint in endpoints_to_test:
    try:
        resp = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=30)
        print(f"\nGET {endpoint}: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Response keys: {list(data.keys())[:5]}")
            # Save successful response
            with open(f'.tmp/api_explore_{endpoint.replace("/", "_")}.json', 'w') as f:
                json.dump(data, f, indent=2)
            print(f"  Saved to .tmp/api_explore_{endpoint.replace('/', '_')}.json")
    except Exception as e:
        print(f"  Error: {str(e)[:50]}")

# 3. Check findings response metadata
print("\n\n3. RESPONSE METADATA")
print("-"*70)
resp = requests.post(f"{base_url}/api/findings", headers=headers, json={"severity": ["HIGH"]}, timeout=60)
full_response = resp.json()

print(f"Top-level keys: {list(full_response.keys())}")
print(f"Data keys: {list(full_response.get('data', {}).keys())}")
print(f"Success: {full_response.get('success')}")
print(f"Timestamp: {full_response.get('timestamp')}")

# 4. Check all unique values for key fields
print("\n\n4. UNIQUE VALUES IN FINDINGS (first 100)")
print("-"*70)

all_teams = set()
all_products = set()
all_subproducts = set()
all_owners = set()

after_key = None
for page in range(10):  # Get 10 pages
    body = {"severity": ["HIGH", "CRITICAL"]}
    if after_key:
        body["afterKey"] = after_key

    resp = requests.post(f"{base_url}/api/findings", headers=headers, json=body, timeout=60)
    data = resp.json().get('data', {})
    findings = data.get('findings', [])
    after_key = data.get('afterKey')

    for f in findings:
        # Teams
        team = f.get('team')
        if team and isinstance(team, dict):
            all_teams.add(team.get('name', 'Unknown'))

        # Products
        prod = f.get('product')
        if prod and isinstance(prod, dict):
            all_products.add(prod.get('name', 'Unknown'))

        # Subproducts
        subprod = f.get('subProduct')
        if subprod and isinstance(subprod, dict):
            all_subproducts.add(subprod.get('name', 'Unknown'))

        # Owners
        owner = f.get('owner')
        if owner and isinstance(owner, dict):
            all_owners.add(owner.get('name', 'Unknown'))

    if not after_key:
        break

print(f"\nUnique Teams ({len(all_teams)}):")
for team in sorted(all_teams):
    print(f"  - {team}")

print(f"\nUnique Products ({len(all_products)}):")
for prod in sorted(all_products):
    print(f"  - {prod}")

print(f"\nUnique Owners ({len(all_owners)}):")
for owner in sorted(list(all_owners)[:10]):
    print(f"  - {owner}")

print("\n" + "="*70)
print("Exploration complete! Check .tmp/ for saved responses.")
print("="*70)
