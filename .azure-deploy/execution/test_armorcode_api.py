"""
Test ArmorCode API - Try different endpoints and methods
"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
base_url = os.getenv('ARMORCODE_BASE_URL', 'https://app.armorcode.com')

headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

print("=" * 80)
print("Testing ArmorCode API Endpoints")
print("=" * 80)
print()

# Test 1: GraphQL endpoint
print("Test 1: GraphQL endpoint (/graphql)")
print("-" * 80)
graphql_query = {
    "query": """
    {
      findings(first: 5) {
        edges {
          node {
            id
            title
            severity
            status
          }
        }
      }
    }
    """
}

try:
    response = requests.post(
        f"{base_url}/graphql",
        headers=headers,
        json=graphql_query,
        timeout=30
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    if response.status_code == 200:
        print("[SUCCESS] GraphQL endpoint works!")
except Exception as e:
    print(f"[ERROR] {e}")

print("\n")

# Test 2: REST API with POST to /api/findings
print("Test 2: POST to /api/findings")
print("-" * 80)
post_body = {
    "severity": ["HIGH", "CRITICAL"],
    "status": ["Open", "In Progress"],
    "limit": 5
}

try:
    response = requests.post(
        f"{base_url}/api/findings",
        headers=headers,
        json=post_body,
        timeout=30
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    if response.status_code == 200:
        print("[SUCCESS] POST /api/findings works!")
        # Pretty print the response
        print("\nSample response structure:")
        print(json.dumps(response.json(), indent=2)[:1000])
except Exception as e:
    print(f"[ERROR] {e}")

print("\n")

# Test 3: REST API with POST to /api/v1/findings
print("Test 3: POST to /api/v1/findings")
print("-" * 80)

try:
    response = requests.post(
        f"{base_url}/api/v1/findings",
        headers=headers,
        json=post_body,
        timeout=30
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    if response.status_code == 200:
        print("[SUCCESS] POST /api/v1/findings works!")
except Exception as e:
    print(f"[ERROR] {e}")

print("\n")

# Test 4: Different auth header format
print("Test 4: Different auth format (X-API-Key)")
print("-" * 80)
alt_headers = {
    'X-API-Key': api_key,
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

try:
    response = requests.post(
        f"{base_url}/api/findings",
        headers=alt_headers,
        json=post_body,
        timeout=30
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    if response.status_code == 200:
        print("[SUCCESS] X-API-Key header works!")
except Exception as e:
    print(f"[ERROR] {e}")

print("\n")

# Test 5: GraphQL with alternative query
print("Test 5: GraphQL - List products")
print("-" * 80)
graphql_products = {
    "query": """
    {
      products {
        id
        name
      }
    }
    """
}

try:
    response = requests.post(
        f"{base_url}/graphql",
        headers=headers,
        json=graphql_products,
        timeout=30
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    if response.status_code == 200:
        print("[SUCCESS] GraphQL products query works!")
except Exception as e:
    print(f"[ERROR] {e}")

print("\n")
print("=" * 80)
print("Test Complete")
print("=" * 80)
