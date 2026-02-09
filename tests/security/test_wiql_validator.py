"""
Test Suite for WIQL Validator

Tests WIQL injection prevention with legitimate inputs, edge cases, and
malicious attack vectors to ensure robust security.

Run with:
    pytest tests/security/test_wiql_validator.py -v
"""

import os
import sys

import pytest

from execution.security import ValidationError, WIQLValidator, safe_wiql


class TestWIQLValidator:
    """Tests for WIQL injection prevention"""

    def test_valid_project_names(self):
        """Test that valid project names are accepted"""
        valid_names = [
            "My Project",
            "Access-Legal_v2.0",
            "Project123",
            "Test.Project",
            "A",  # Single character
            "A" * 64,  # Max length
        ]
        for name in valid_names:
            result = WIQLValidator.validate_project_name(name)
            assert result == name

    def test_project_name_injection_with_quotes(self):
        """Test that SQL injection with quotes is blocked"""
        malicious_names = [
            "'; DROP TABLE bugs--",
            "Project' OR '1'='1",
            'Project" OR "1"="1',
            "Project'; DELETE FROM WorkItems--",
        ]
        for name in malicious_names:
            with pytest.raises(ValidationError):  # Just check that it raises ValidationError
                WIQLValidator.validate_project_name(name)

    def test_project_name_injection_with_keywords(self):
        """Test that SQL/WIQL keywords are blocked"""
        malicious_names = [
            "Project OR 1=1",
            "Project AND TRUE",
            "Project UNION SELECT",
            "Project; DROP TABLE",
            "Project /* comment */ OR",
        ]
        for name in malicious_names:
            with pytest.raises(ValidationError):
                WIQLValidator.validate_project_name(name)

    def test_project_name_too_long(self):
        """Test that overly long project names are rejected"""
        with pytest.raises(ValidationError, match="too long"):
            WIQLValidator.validate_project_name("A" * 65)

    def test_project_name_empty(self):
        """Test that empty project names are rejected"""
        with pytest.raises(ValidationError, match="cannot be empty"):
            WIQLValidator.validate_project_name("")

    def test_project_name_invalid_type(self):
        """Test that non-string types are rejected"""
        with pytest.raises(ValidationError, match="must be string"):
            WIQLValidator.validate_project_name(123)

    def test_project_name_special_chars(self):
        """Test that special characters are rejected"""
        invalid_names = [
            "Project@Email",
            "Project#Tag",
            "Project$Money",
            "Project%Percent",
            "Project&Ampersand",
        ]
        for name in invalid_names:
            with pytest.raises(ValidationError, match="Invalid project name"):
                WIQLValidator.validate_project_name(name)

    def test_valid_work_item_types(self):
        """Test that valid work item types are accepted"""
        valid_types = ["Bug", "User Story", "Task", "Epic", "Feature"]
        for work_type in valid_types:
            result = WIQLValidator.validate_work_item_type(work_type)
            assert result == work_type

    def test_invalid_work_item_types(self):
        """Test that invalid work item types are rejected"""
        with pytest.raises(ValidationError, match="Invalid work item type"):
            WIQLValidator.validate_work_item_type("InvalidType")

    def test_valid_states(self):
        """Test that valid states are accepted"""
        valid_states = ["New", "Active", "Resolved", "Closed", "Done"]
        for state in valid_states:
            result = WIQLValidator.validate_state(state)
            assert result == state

    def test_invalid_states(self):
        """Test that invalid states are rejected"""
        with pytest.raises(ValidationError, match="Invalid state"):
            WIQLValidator.validate_state("InvalidState")

    def test_valid_dates(self):
        """Test that valid ISO 8601 dates are accepted"""
        valid_dates = [
            "2026-01-01",
            "2026-12-31",
            "2000-02-29",  # Leap year
        ]
        for date in valid_dates:
            result = WIQLValidator.validate_date_iso8601(date)
            assert result == date

    def test_invalid_date_formats(self):
        """Test that invalid date formats are rejected"""
        invalid_dates = [
            "2026/01/01",  # Wrong separator
            "01-01-2026",  # Wrong order
            "2026-1-1",  # Missing zero padding
            "not-a-date",
            "2026-13-01",  # Invalid month
            "2026-02-30",  # Invalid day
            "2026-00-01",  # Month zero
        ]
        for date in invalid_dates:
            with pytest.raises(ValidationError):
                WIQLValidator.validate_date_iso8601(date)

    def test_build_safe_wiql_basic(self):
        """Test basic WIQL query building"""
        query = WIQLValidator.build_safe_wiql("WHERE [System.TeamProject] = '{project}'", project="My Project")
        assert "My Project" in query
        assert "WHERE [System.TeamProject] = 'My Project'" in query

    def test_build_safe_wiql_multiple_params(self):
        """Test WIQL building with multiple parameters"""
        query = WIQLValidator.build_safe_wiql(
            "WHERE [System.TeamProject] = '{project}' AND [System.WorkItemType] = '{work_type}'",
            project="Test Project",
            work_type="Bug",
        )
        assert "Test Project" in query
        assert "Bug" in query

    def test_build_safe_wiql_injection_blocked(self):
        """Test that injection attempts are blocked in WIQL building"""
        with pytest.raises(ValidationError):
            WIQLValidator.build_safe_wiql("WHERE [System.TeamProject] = '{project}'", project="'; DROP TABLE--")

    def test_build_safe_wiql_missing_param(self):
        """Test that missing parameters raise error"""
        with pytest.raises(ValidationError, match="Missing required parameter"):
            WIQLValidator.build_safe_wiql(
                "WHERE [System.TeamProject] = '{project}'",
                # Missing 'project' parameter
            )
