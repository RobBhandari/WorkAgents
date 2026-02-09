"""
Integration Test Suite for Security Utilities

Tests combining multiple validators to ensure they work together correctly.

Run with:
    pytest tests/security/test_integration.py -v
"""

import os
import sys

import pytest

from execution.security import PathValidator, ValidationError, safe_html, safe_wiql


class TestIntegration:
    """Integration tests combining multiple validators"""

    def test_wiql_query_end_to_end(self):
        """Test complete WIQL query construction"""
        query = safe_wiql(
            """SELECT [System.Id], [System.Title], [System.State]
               FROM WorkItems
               WHERE [System.TeamProject] = '{project}'
               AND [System.WorkItemType] = '{work_type}'
               AND [System.CreatedDate] >= '{start_date}'
               ORDER BY [System.Id] ASC""",
            project="Access Legal",
            work_type="Bug",
            start_date="2026-01-01",
        )

        assert "Access Legal" in query
        assert "Bug" in query
        assert "2026-01-01" in query
        # Ensure no injection
        assert "DROP" not in query
        assert "OR 1=1" not in query

    def test_html_dashboard_generation(self):
        """Test HTML generation with user data"""
        bug_title = "<script>alert('XSS')</script>"
        safe_title = safe_html(bug_title)

        html = f"<td>{safe_title}</td>"

        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_file_output_validation(self):
        """Test file path validation for reports"""
        user_filename = "../../etc/passwd"

        with pytest.raises(ValidationError):
            safe_filename = PathValidator.validate_filename(user_filename)

        # Valid filename should work
        safe_filename = PathValidator.validate_filename("report.html")
        assert safe_filename == "report.html"
