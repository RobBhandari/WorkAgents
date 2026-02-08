#!/usr/bin/env python3
"""
Generate index.html for Observatory dashboards.

Copies trends.html to index.html to serve as the default landing page.
"""

import shutil
from pathlib import Path


def generate_index_html():
    """Copy trends.html to index.html."""

    dashboards_dir = Path(".tmp/observatory/dashboards")
    dashboards_dir.mkdir(parents=True, exist_ok=True)

    trends_file = dashboards_dir / "trends.html"
    index_file = dashboards_dir / "index.html"

    if trends_file.exists():
        shutil.copy2(trends_file, index_file)
        print(f"✅ Generated index.html from trends.html")
        print(f"   Source: {trends_file}")
        print(f"   Target: {index_file}")
    else:
        print(f"⚠️  trends.html not found at {trends_file}")
        print(f"   Skipping index.html generation")
        return 1

    return 0


if __name__ == "__main__":
    exit(generate_index_html())
