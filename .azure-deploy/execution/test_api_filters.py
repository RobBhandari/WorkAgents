"""Quick test of ArmorCode API filters"""

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ARMORCODE_API_KEY")
base_url = os.getenv("ARMORCODE_BASE_URL")

headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

# Test 1: No filters - get everything
print("Test 1: No filters")
response = requests.post(f"{base_url}/api/findings", headers=headers, json={"limit": 10000}, timeout=60)
data = response.json()
all_findings = data.get("data", {}).get("findings", [])
print(f"Total findings (no filter): {len(all_findings)}")

# Count by severity
severity_counts = {}
for f in all_findings:
    sev = f.get("severity", "Unknown")
    severity_counts[sev] = severity_counts.get(sev, 0) + 1
print(f"By severity: {severity_counts}")

# Test 2: HIGH and CRITICAL only
print("\nTest 2: HIGH + CRITICAL only")
response = requests.post(
    f"{base_url}/api/findings", headers=headers, json={"severity": ["HIGH", "CRITICAL"], "limit": 10000}, timeout=60
)
data = response.json()
high_crit = data.get("data", {}).get("findings", [])
print(f"HIGH + CRITICAL: {len(high_crit)}")

# Test 3: With status filter
print("\nTest 3: HIGH + CRITICAL + Status filter")
response = requests.post(
    f"{base_url}/api/findings",
    headers=headers,
    json={"severity": ["HIGH", "CRITICAL"], "status": ["Open", "In Progress"], "limit": 10000},
    timeout=60,
)
data = response.json()
filtered = data.get("data", {}).get("findings", [])
print(f"HIGH + CRITICAL + Open/In Progress: {len(filtered)}")

# Save full response for inspection
with open(".tmp/api_test_response.json", "w") as f:
    json.dump(
        {
            "all_findings_count": len(all_findings),
            "severity_counts": severity_counts,
            "high_crit_count": len(high_crit),
            "filtered_count": len(filtered),
            "sample_finding": all_findings[0] if all_findings else None,
        },
        f,
        indent=2,
    )
print("\nDetails saved to .tmp/api_test_response.json")
