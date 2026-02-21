#!/usr/bin/env python3
"""
One-off script: fetch ArmorCode product name → ID mapping for ARMORCODE_ID_MAP secret.

Usage:
    python scripts/fetch_armorcode_id_map.py

Output: JSON object suitable for pasting directly as the ARMORCODE_ID_MAP GitHub secret.
Requires: ARMORCODE_BASE_URL, ARMORCODE_API_KEY, ARMORCODE_HIERARCHY in .env
"""

import json
from pathlib import Path

from dotenv import load_dotenv

from execution.http_client import post
from execution.secure_config import get_config

load_dotenv()


def _fetch_all_products(api_key: str, base_url: str) -> dict[str, str]:
    """Fetch all products from ArmorCode GraphQL API, returning {name: id}."""
    graphql_url = f"{base_url.rstrip('/')}/api/graphql"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    name_to_id: dict[str, str] = {}

    for page in range(1, 20):
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
        response = post(graphql_url, headers=headers, json={"query": query}, timeout=60)
        response.raise_for_status()

        data = response.json()
        result = data.get("data", {}).get("products", {})
        for p in result.get("products", []):
            name_to_id[p["name"]] = str(p["id"])

        if not result.get("pageInfo", {}).get("hasNext", False):
            break

    return name_to_id


if __name__ == "__main__":
    config = get_config()
    armorcode_cfg = config.get_armorcode_config()

    print(f"Fetching all products from: {armorcode_cfg.base_url}\n")

    name_to_id = _fetch_all_products(armorcode_cfg.api_key, armorcode_cfg.base_url)

    print(f"Found {len(name_to_id)} products:\n")
    for name, pid in sorted(name_to_id.items()):
        print(f"  {pid:>10}  {name}")

    output = json.dumps(name_to_id, indent=2, sort_keys=True)
    print("\n--- ARMORCODE_ID_MAP secret value (copy this) ---")
    print(output)

    # Save locally so code can run without the secret being set
    local_path = Path("data/armorcode_id_map.json")
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(output, encoding="utf-8")
    print(f"\n✅ Also saved to {local_path} for local development")
