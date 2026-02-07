"""Check team information in findings and test team filtering"""
import json
import os

import requests
from dotenv import load_dotenv
from http_client import delete, get, patch, post, put

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
base_url = 'https://app.armorcode.com'
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

print("="*70)
print("CHECKING TEAM INFORMATION")
print("="*70)

# Test 1: Get sample finding and check team field
print("\n1. Check team field in current findings")
print("-"*70)

request_body = {
    "severity": ["HIGH", "CRITICAL"],
    "status": ["Open", "In Progress"]
}

response = post(f"{base_url}/api/findings", headers=headers, json=request_body, timeout=60)
data = response.json()

if 'data' in data:
    findings = data['data'].get('findings', [])
    if findings:
        # Get first finding
        sample = findings[0]

        print("Sample finding structure:")
        print(f"  Product: {sample.get('product', {}).get('name', 'N/A')}")
        print(f"  Team: {sample.get('team')}")
        print(f"  Owner: {sample.get('owner')}")

        # Check all unique teams
        teams = set()
        for f in findings:
            team = f.get('team')
            if team:
                if isinstance(team, dict):
                    teams.add(team.get('name', 'Unknown'))
                else:
                    teams.add(str(team))

        print(f"\nUnique teams in current findings ({len(teams)}):")
        for team in sorted(teams):
            print(f"  - {team}")

# Test 2: Try different team filter parameters
print("\n\n2. Test team-based filtering")
print("-"*70)

# Try with team parameter
team_tests = [
    {"team": "legal"},
    {"team": ["legal"]},
    {"teamName": "legal"},
    {"teams": ["legal"]},
]

for i, test_body in enumerate(team_tests, 1):
    test_body.update({"severity": ["HIGH", "CRITICAL"]})

    print(f"\nTest {i}: {test_body}")
    try:
        response = post(f"{base_url}/api/findings", headers=headers, json=test_body, timeout=60)
        data = response.json()

        if 'data' in data and 'findings' in data['data']:
            findings = data['data'].get('findings', [])
            products = set()
            for f in findings:
                prod = f.get('product', {})
                if isinstance(prod, dict):
                    products.add(prod.get('name', 'Unknown'))

            print(f"  Result: {len(findings)} findings, {len(products)} products")
            if len(products) != 3:  # Different from our baseline
                print(f"  [!] DIFFERENT! Products: {sorted(products)}")
            else:
                print("  Same 3 products as before")
        else:
            print(f"  Error or no data: {str(data)[:200]}")
    except Exception as e:
        print(f"  Exception: {e}")

# Test 3: Try with organization/hierarchy headers
print("\n\n3. Test with organization/hierarchy headers")
print("-"*70)

header_tests = [
    {'X-Team': 'legal'},
    {'X-Hierarchy': 'Development Director - Legal BU'},
    {'X-Organization': 'The Access Group'},
    {'X-Business-Unit': 'Legal BU'},
]

for i, extra_headers in enumerate(header_tests, 1):
    test_headers = {**headers, **extra_headers}
    print(f"\nTest {i}: {extra_headers}")

    try:
        response = post(
            f"{base_url}/api/findings",
            headers=test_headers,
            json={"severity": ["HIGH", "CRITICAL"]},
            timeout=60
        )
        data = response.json()

        if 'data' in data and 'findings' in data['data']:
            findings = data['data'].get('findings', [])
            products = set()
            for f in findings:
                prod = f.get('product', {})
                if isinstance(prod, dict):
                    products.add(prod.get('name', 'Unknown'))

            print(f"  Result: {len(findings)} findings, {len(products)} products")
            if len(products) != 3:
                print(f"  [!] DIFFERENT! Products: {sorted(products)}")
            else:
                print("  Same 3 products as before")
        else:
            print("  Error or no data")
    except Exception as e:
        print(f"  Exception: {e}")

print("\n" + "="*70)
print("Team Investigation Complete")
print("="*70)
