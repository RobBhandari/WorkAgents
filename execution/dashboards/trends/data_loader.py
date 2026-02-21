"""
Data loading module for Trends Dashboard

Responsible for loading and validating historical JSON data from various observatory files.
"""

import json
import os
from pathlib import Path
from typing import Any, Union


class TrendsDataLoader:
    """Loads historical data from observatory JSON files"""

    def __init__(self, history_dir: str | Path = ".tmp/observatory"):
        """
        Initialize data loader

        Args:
            history_dir: Directory containing history JSON files
        """
        self.history_dir = history_dir

    def load_history_file(self, filename: str) -> dict[str, Any] | None:
        """Load a history JSON file with error handling

        Args:
            filename: Name of the history file (e.g., 'quality_history.json')

        Returns:
            Dictionary with history data, or None if file not found/invalid
        """
        file_path = os.path.join(self.history_dir, filename)

        if not os.path.exists(file_path):
            print(f"  ⚠️ {filename}: File not found")
            return None

        try:
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                print(f"  ⚠️ {filename}: File is empty")
                return None

            # Load and parse JSON
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Validate structure
            if not isinstance(data, dict):
                print(f"  ⚠️ {filename}: Invalid data structure (not a dictionary)")
                return None

            if "weeks" not in data:
                print(f"  ⚠️ {filename}: Missing 'weeks' key")
                return None

            weeks = data.get("weeks", [])
            if not weeks:
                print(f"  ⚠️ {filename}: No weeks data found")
                return None

            print(f"  ✓ {filename}: Loaded successfully ({len(weeks)} weeks, {file_size:,} bytes)")
            return data

        except json.JSONDecodeError as e:
            print(f"  ✗ {filename}: JSON decode error - {e}")
            return None
        except UnicodeDecodeError as e:
            print(f"  ✗ {filename}: Unicode decode error - {e}")
            return None
        except Exception as e:
            print(f"  ✗ {filename}: Unexpected error - {e}")
            return None

    def load_baseline_data(self) -> dict[str, int]:
        """Load baseline data for target calculations

        Returns:
            Dictionary with baseline counts:
            {
                "security": <vulnerability_count>,
                "bugs": <open_bugs_count>
            }
        """
        baselines = {}

        # Load security targets (replaces armorcode_baseline.json)
        security_targets_file = "data/security_targets.json"
        if os.path.exists(security_targets_file):
            try:
                with open(security_targets_file, encoding="utf-8") as f:
                    data = json.load(f)
                    baselines["security"] = data.get("baseline_total", 0)
            except (json.JSONDecodeError, UnicodeDecodeError, Exception) as e:
                print(f"  ⚠️ Failed to load security_targets.json: {e}")

        # Load ADO bugs baseline
        ado_file = "data/baseline.json"
        if os.path.exists(ado_file):
            try:
                with open(ado_file, encoding="utf-8") as f:
                    data = json.load(f)
                    baselines["bugs"] = data.get("open_count", 0)  # Field is 'open_count' not 'total_bugs'
            except (json.JSONDecodeError, UnicodeDecodeError, Exception) as e:
                print(f"  ⚠️ Failed to load baseline.json: {e}")

        return baselines

    def load_all_metrics(self) -> dict[str, Any]:
        """
        Load all historical metrics data

        Returns:
            Dictionary containing loaded data from all history files
        """
        print("\nLoading historical data...")

        return {
            "quality": self.load_history_file("quality_history.json"),
            "security": self.load_history_file("security_history.json"),
            "flow": self.load_history_file("flow_history.json"),
            "deployment": self.load_history_file("deployment_history.json"),
            "collaboration": self.load_history_file("collaboration_history.json"),
            "ownership": self.load_history_file("ownership_history.json"),
            "risk": self.load_history_file("risk_history.json"),
            "exploitable": self.load_history_file("exploitable_history.json"),
            "baselines": self.load_baseline_data(),
        }
