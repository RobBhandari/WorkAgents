"""
Tests for Security Bug Filter Module

Tests the shared security bug filtering functionality to ensure it properly
identifies and filters out ArmorCode-created security bugs.

Run with:
    pytest tests/collectors/test_security_bug_filter.py -v
"""

import pytest

from execution.collectors.security_bug_filter import filter_security_bugs, is_security_bug


class TestIsSecurityBug:
    """Tests for is_security_bug() function"""

    def test_is_security_bug_creator_name_dict_format(self):
        """Test detection when creator is ArmorCode (dict format)"""
        work_item = {
            "System.CreatedBy": {"displayName": "ArmorCode Bot", "uniqueName": "armorcode@example.com"},
            "System.Tags": "",
        }

        assert is_security_bug(work_item) is True

    def test_is_security_bug_creator_name_string_format(self):
        """Test detection when creator is ArmorCode (string format)"""
        work_item = {"System.CreatedBy": "ArmorCode Bot", "System.Tags": ""}

        assert is_security_bug(work_item) is True

    def test_is_security_bug_creator_name_case_insensitive(self):
        """Test that creator name matching is case-insensitive"""
        work_item = {
            "System.CreatedBy": {"displayName": "ARMORCODE Bot"},
            "System.Tags": "",
        }

        assert is_security_bug(work_item) is True

    def test_is_security_bug_tag_detection(self):
        """Test detection when bug is tagged with armorcode"""
        work_item = {
            "System.CreatedBy": {"displayName": "John Doe"},
            "System.Tags": "security;armorcode;vulnerability",
        }

        assert is_security_bug(work_item) is True

    def test_is_security_bug_tag_case_insensitive(self):
        """Test that tag matching is case-insensitive"""
        work_item = {
            "System.CreatedBy": {"displayName": "John Doe"},
            "System.Tags": "security;ARMORCODE;vulnerability",
        }

        assert is_security_bug(work_item) is True

    def test_is_security_bug_both_creator_and_tag(self):
        """Test detection when both creator and tag match"""
        work_item = {
            "System.CreatedBy": {"displayName": "ArmorCode Bot"},
            "System.Tags": "armorcode;security",
        }

        assert is_security_bug(work_item) is True

    def test_is_not_security_bug(self):
        """Test that normal bugs are not detected as security bugs"""
        work_item = {
            "System.CreatedBy": {"displayName": "John Doe"},
            "System.Tags": "bug;high-priority",
        }

        assert is_security_bug(work_item) is False

    def test_is_not_security_bug_empty_fields(self):
        """Test that bugs with empty fields are not detected as security bugs"""
        work_item = {"System.CreatedBy": {}, "System.Tags": ""}

        assert is_security_bug(work_item) is False

    def test_is_not_security_bug_missing_fields(self):
        """Test that bugs with missing fields are not detected as security bugs"""
        work_item = {}

        assert is_security_bug(work_item) is False

    def test_is_not_security_bug_none_values(self):
        """Test that bugs with None values are not detected as security bugs"""
        work_item = {"System.CreatedBy": None, "System.Tags": None}

        assert is_security_bug(work_item) is False

    def test_is_security_bug_partial_match_in_name(self):
        """Test that partial match in creator name is detected"""
        work_item = {
            "System.CreatedBy": {"displayName": "System-ArmorCode-Integration"},
            "System.Tags": "",
        }

        assert is_security_bug(work_item) is True


class TestFilterSecurityBugs:
    """Tests for filter_security_bugs() function"""

    def test_filter_security_bugs_empty_list(self):
        """Test filtering an empty list"""
        filtered, excluded = filter_security_bugs([])

        assert filtered == []
        assert excluded == 0

    def test_filter_security_bugs_no_security_bugs(self):
        """Test filtering when no security bugs are present"""
        work_items = [
            {"System.CreatedBy": {"displayName": "Alice"}, "System.Tags": "bug"},
            {"System.CreatedBy": {"displayName": "Bob"}, "System.Tags": "feature"},
            {"System.CreatedBy": {"displayName": "Charlie"}, "System.Tags": "enhancement"},
        ]

        filtered, excluded = filter_security_bugs(work_items)

        assert len(filtered) == 3
        assert excluded == 0
        assert filtered == work_items

    def test_filter_security_bugs_all_security_bugs(self):
        """Test filtering when all bugs are security bugs"""
        work_items = [
            {"System.CreatedBy": {"displayName": "ArmorCode Bot"}, "System.Tags": ""},
            {"System.CreatedBy": {"displayName": "John Doe"}, "System.Tags": "armorcode"},
            {"System.CreatedBy": {"displayName": "ArmorCode Integration"}, "System.Tags": "security"},
        ]

        filtered, excluded = filter_security_bugs(work_items)

        assert len(filtered) == 0
        assert excluded == 3

    def test_filter_security_bugs_mixed_list(self):
        """Test filtering a mixed list of regular and security bugs"""
        work_items = [
            {"System.CreatedBy": {"displayName": "Alice"}, "System.Tags": "bug"},
            {"System.CreatedBy": {"displayName": "ArmorCode Bot"}, "System.Tags": "security"},
            {"System.CreatedBy": {"displayName": "Bob"}, "System.Tags": "feature"},
            {"System.CreatedBy": {"displayName": "Charlie"}, "System.Tags": "armorcode"},
            {"System.CreatedBy": {"displayName": "Dave"}, "System.Tags": "enhancement"},
        ]

        filtered, excluded = filter_security_bugs(work_items)

        assert len(filtered) == 3
        assert excluded == 2

        # Verify the correct items were filtered
        filtered_names = [item["System.CreatedBy"]["displayName"] for item in filtered]
        assert "Alice" in filtered_names
        assert "Bob" in filtered_names
        assert "Dave" in filtered_names
        assert "ArmorCode Bot" not in filtered_names
        assert "Charlie" not in filtered_names

    def test_filter_security_bugs_return_type(self):
        """Test that filter_security_bugs returns a tuple"""
        work_items = [{"System.CreatedBy": {"displayName": "Alice"}, "System.Tags": "bug"}]

        result = filter_security_bugs(work_items)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert isinstance(result[1], int)

    def test_filter_security_bugs_preserves_order(self):
        """Test that filtering preserves the original order of work items"""
        work_items = [
            {"System.Id": 1, "System.CreatedBy": {"displayName": "Alice"}, "System.Tags": "bug"},
            {"System.Id": 2, "System.CreatedBy": {"displayName": "ArmorCode Bot"}, "System.Tags": ""},
            {"System.Id": 3, "System.CreatedBy": {"displayName": "Bob"}, "System.Tags": "feature"},
            {"System.Id": 4, "System.CreatedBy": {"displayName": "Charlie"}, "System.Tags": "armorcode"},
            {"System.Id": 5, "System.CreatedBy": {"displayName": "Dave"}, "System.Tags": "enhancement"},
        ]

        filtered, excluded = filter_security_bugs(work_items)

        # Check that IDs are in order
        filtered_ids = [item["System.Id"] for item in filtered]
        assert filtered_ids == [1, 3, 5]

    def test_filter_security_bugs_does_not_modify_original(self):
        """Test that filtering does not modify the original list"""
        work_items = [
            {"System.CreatedBy": {"displayName": "Alice"}, "System.Tags": "bug"},
            {"System.CreatedBy": {"displayName": "ArmorCode Bot"}, "System.Tags": ""},
        ]

        original_length = len(work_items)
        filtered, excluded = filter_security_bugs(work_items)

        # Original list should be unchanged
        assert len(work_items) == original_length
        assert len(work_items) == 2
