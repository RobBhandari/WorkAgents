"""
Shared Security Bug Filter Module

Provides centralized security bug filtering logic for metrics collectors.
Filters out ArmorCode-created security bugs to prevent double-counting
(they're tracked separately in the Security Dashboard).

Functions:
    is_security_bug(work_item: dict) -> bool
        Check if a single work item is a security bug created by ArmorCode.

    filter_security_bugs(work_items: list[dict]) -> tuple
        Filter a list of work items, removing security bugs.

Usage:
    from execution.collectors.security_bug_filter import filter_security_bugs

    bugs = [...]  # List of bug work items from ADO
    filtered_bugs, excluded_count = filter_security_bugs(bugs)
    print(f"Excluded {excluded_count} security bugs from metrics")
"""


def is_security_bug(work_item: dict) -> bool:
    """
    Check if a work item is a security bug created by ArmorCode.

    Security bugs are identified by:
    - Created by a user with "armorcode" in their name (case-insensitive)
    - Tagged with "armorcode" (case-insensitive)

    Args:
        work_item: Work item dictionary with System.CreatedBy and System.Tags fields

    Returns:
        bool: True if this is a security bug that should be filtered out

    Example:
        work_item = {
            "System.CreatedBy": {"displayName": "ArmorCode Bot"},
            "System.Tags": "security;armorcode"
        }
        if is_security_bug(work_item):
            print("This is a security bug - exclude from quality metrics")
    """
    created_by = work_item.get("System.CreatedBy", {})
    tags = work_item.get("System.Tags", "")

    # Extract creator name (handle both dict and string formats)
    if isinstance(created_by, dict):
        creator_name = created_by.get("displayName", "").lower()
    else:
        creator_name = str(created_by).lower()

    # Extract tags (handle as string, typically semicolon-separated)
    tags_str = str(tags).lower() if tags else ""

    # Check if created by ArmorCode OR tagged with armorcode
    return "armorcode" in creator_name or "armorcode" in tags_str


def filter_security_bugs(work_items: list[dict]) -> tuple[list[dict], int]:
    """
    Filter out security bugs created by ArmorCode to avoid double-counting.

    These bugs are already tracked in the Security Dashboard, so we exclude them
    from quality and flow metrics to prevent inflating bug counts.

    Args:
        work_items: List of work item dictionaries from ADO

    Returns:
        tuple: (filtered_work_items, excluded_count)
            - filtered_work_items: List of work items excluding security bugs
            - excluded_count: Number of security bugs that were filtered out

    Example:
        all_bugs = query_bugs_from_ado()
        clean_bugs, excluded = filter_security_bugs(all_bugs)
        print(f"Analyzing {len(clean_bugs)} bugs (excluded {excluded} security bugs)")
    """
    filtered = []
    excluded = 0

    for work_item in work_items:
        if is_security_bug(work_item):
            excluded += 1
        else:
            filtered.append(work_item)

    return filtered, excluded
