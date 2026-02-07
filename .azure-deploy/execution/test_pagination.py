"""Test ArmorCode API pagination"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('ARMORCODE_API_KEY')
base_url = 'https://app.armorcode.com'

headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

# Try different pagination parameters
tests = [
    {"name": "Default (limit 10000)", "body": {"limit": 10000}},
    {"name": "Page 0, Size 100", "body": {"page": 0, "size": 100}},
    {"name": "Page 0, PageSize 100", "body": {"page": 0, "pageSize": 100}},
    {"name": "Offset 0, Limit 100", "body": {"offset": 0, "limit": 100}},
    {"name": "PageNumber 0, PageSize 100", "body": {"pageNumber": 0, "pageSize": 100}},
]

for test in tests:
    print(f"\n{test['name']}:")
    print("-" * 60)
    try:
        response = requests.post(
            f"{base_url}/api/findings",
            headers=headers,
            json=test['body'],
            timeout=60
        )
        data = response.json()

        # Print response structure
        if 'data' in data:
            print(f"  Response keys: {list(data.keys())}")
            print(f"  Data keys: {list(data['data'].keys())}")
            findings = data['data'].get('findings', [])
            print(f"  Findings returned: {len(findings)}")

            # Check for pagination metadata
            for key in data['data'].keys():
                if key != 'findings':
                    print(f"  {key}: {data['data'][key]}")
        else:
            print(f"  Full response: {json.dumps(data, indent=2)[:500]}")
    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "=" * 60)
print("Checking for pagination in response metadata...")
