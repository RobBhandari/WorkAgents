"""
Security Utilities for Input Validation and Sanitization

This module provides centralized security validation to prevent injection attacks
and other security vulnerabilities across the application.

Key Classes:
    - WIQLValidator: Validates Azure DevOps WIQL query inputs
    - HTMLSanitizer: Escapes HTML to prevent XSS attacks
    - PathValidator: Validates file paths to prevent traversal attacks
    - CommandValidator: Validates command-line arguments

Usage:
    from execution.security_utils import WIQLValidator, ValidationError

    try:
        safe_project = WIQLValidator.validate_project_name(user_input)
        query = WIQLValidator.build_safe_wiql(
            "WHERE [System.TeamProject] = '{project}'",
            project=safe_project
        )
    except ValidationError as e:
        logger.error(f"Invalid input: {e}")
        raise

Author: Security Audit Implementation
Date: 2026-02-06
"""

import os
import re
from datetime import datetime


class ValidationError(Exception):
    """
    Raised when input validation fails.

    This exception should be caught and handled appropriately,
    ensuring sensitive details are not leaked to users.
    """

    pass


class WIQLValidator:
    """
    Validates and sanitizes inputs for Azure DevOps WIQL (Work Item Query Language) queries.

    Azure DevOps does not support parameterized WIQL queries, so we must use
    strict whitelist-based validation to prevent SQL-like injection attacks.

    Security Note:
        Never use string interpolation for WIQL queries without validation.
        Always use WIQLValidator.build_safe_wiql() or validate inputs individually.
    """

    # Whitelist of valid ADO field names
    VALID_FIELDS = {
        "System.Id",
        "System.Title",
        "System.State",
        "System.WorkItemType",
        "System.TeamProject",
        "System.CreatedDate",
        "System.CreatedBy",
        "System.ChangedDate",
        "System.ChangedBy",
        "System.ClosedDate",
        "System.AreaPath",
        "System.IterationPath",
        "System.AssignedTo",
        "Microsoft.VSTS.Common.Priority",
        "Microsoft.VSTS.Common.Severity",
        "Microsoft.VSTS.Common.ClosedDate",
        "Microsoft.VSTS.Common.StateChangeDate",
        "Microsoft.VSTS.Common.ActivatedDate",
        "Microsoft.VSTS.Common.ResolvedDate",
    }

    # Whitelist of valid work item types
    VALID_WORK_TYPES = {
        "Bug",
        "User Story",
        "Task",
        "Epic",
        "Feature",
        "Issue",
        "Test Case",
        "Product Backlog Item",
    }

    # Whitelist of valid states
    VALID_STATES = {
        "New",
        "Active",
        "Resolved",
        "Closed",
        "Removed",
        "Done",
        "Committed",
        "In Progress",
        "To Do",
    }

    # Whitelist of valid operators
    VALID_OPERATORS = {
        "=",
        "<>",
        ">",
        "<",
        ">=",
        "<=",
        "UNDER",
        "NOT UNDER",
        "IN",
        "NOT IN",
        "CONTAINS",
        "NOT CONTAINS",
        "LIKE",
        "NOT LIKE",
    }

    @staticmethod
    def validate_project_name(project_name: str) -> str:
        """
        Validate and sanitize Azure DevOps project name.

        ADO project names can only contain:
        - Letters (a-z, A-Z)
        - Numbers (0-9)
        - Spaces
        - Hyphens (-)
        - Underscores (_)
        - Periods (.)

        Max length: 64 characters

        Args:
            project_name: User-supplied project name

        Returns:
            Validated project name (unchanged if valid)

        Raises:
            ValidationError: If project name is invalid or contains injection patterns

        Example:
            >>> WIQLValidator.validate_project_name("My Project")
            'My Project'
            >>> WIQLValidator.validate_project_name("'; DROP TABLE--")
            ValidationError: Project name contains potentially dangerous pattern: '
        """
        if not project_name:
            raise ValidationError("Project name cannot be empty")

        if not isinstance(project_name, str):
            raise ValidationError(f"Project name must be string, got {type(project_name)}")

        if len(project_name) > 64:
            raise ValidationError(f"Project name too long: {len(project_name)} chars (max 64)")

        # Strict whitelist: alphanumeric, space, hyphen, underscore, period
        if not re.match(r"^[a-zA-Z0-9 _\-\.]+$", project_name):
            raise ValidationError(
                f"Invalid project name: '{project_name}'. "
                f"Only letters, numbers, spaces, hyphens, underscores, and periods allowed."
            )

        # Check for WIQL injection patterns (defense in depth)
        dangerous_patterns = [
            "'",
            '"',  # Quote characters
            ";",
            "--",
            "/*",
            "*/",  # SQL comment patterns
        ]

        for pattern in dangerous_patterns:
            if pattern in project_name:
                raise ValidationError(f"Project name contains potentially dangerous pattern: {pattern}")

        # Check for SQL/WIQL keywords that shouldn't be in project names
        project_upper = project_name.upper()
        dangerous_keywords = [
            "OR ",
            " OR",
            "AND ",
            " AND",
            "UNION",
            "SELECT",
            "DROP",
            "INSERT",
            "UPDATE",
            "DELETE",
            "EXEC",
            "EXECUTE",
            "SCRIPT",
        ]

        for keyword in dangerous_keywords:
            if keyword in project_upper:
                raise ValidationError(f"Project name contains potentially dangerous keyword: {keyword.strip()}")

        return project_name

    @staticmethod
    def validate_work_item_type(work_type: str) -> str:
        """
        Validate work item type against whitelist.

        Args:
            work_type: Work item type (e.g., 'Bug', 'User Story')

        Returns:
            Validated work item type

        Raises:
            ValidationError: If work type is not in whitelist
        """
        if work_type not in WIQLValidator.VALID_WORK_TYPES:
            raise ValidationError(
                f"Invalid work item type: '{work_type}'. "
                f"Must be one of: {', '.join(sorted(WIQLValidator.VALID_WORK_TYPES))}"
            )
        return work_type

    @staticmethod
    def validate_state(state: str) -> str:
        """
        Validate state against whitelist.

        Args:
            state: State name (e.g., 'Active', 'Closed')

        Returns:
            Validated state

        Raises:
            ValidationError: If state is not in whitelist
        """
        if state not in WIQLValidator.VALID_STATES:
            raise ValidationError(
                f"Invalid state: '{state}'. " f"Must be one of: {', '.join(sorted(WIQLValidator.VALID_STATES))}"
            )
        return state

    @staticmethod
    def validate_date_iso8601(date_str: str) -> str:
        """
        Validate date string is in ISO 8601 format (YYYY-MM-DD).

        This prevents injection via date fields and ensures consistent date handling.

        Args:
            date_str: Date string in YYYY-MM-DD format

        Returns:
            Validated date string

        Raises:
            ValidationError: If date format is invalid

        Example:
            >>> WIQLValidator.validate_date_iso8601("2026-02-06")
            '2026-02-06'
            >>> WIQLValidator.validate_date_iso8601("2026/02/06")
            ValidationError: Invalid date format
        """
        if not date_str:
            raise ValidationError("Date cannot be empty")

        if not isinstance(date_str, str):
            raise ValidationError(f"Date must be string, got {type(date_str)}")

        # Validate format
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            raise ValidationError(f"Invalid date format: '{date_str}'. Must be YYYY-MM-DD")

        # Validate date components are valid
        try:
            year, month, day = date_str.split("-")
            year, month, day = int(year), int(month), int(day)

            if not (1900 <= year <= 2100):
                raise ValidationError(f"Year out of range: {year} (must be 1900-2100)")
            if not (1 <= month <= 12):
                raise ValidationError(f"Month out of range: {month} (must be 1-12)")
            if not (1 <= day <= 31):
                raise ValidationError(f"Day out of range: {day} (must be 1-31)")

            # Validate date is actually valid (e.g., not Feb 30)
            datetime.strptime(date_str, "%Y-%m-%d")

        except ValueError as e:
            raise ValidationError(f"Invalid date: {e}")

        return date_str

    @staticmethod
    def validate_area_path(area_path: str) -> str:
        """
        Validate area path.

        Area paths are hierarchical strings like "Project\\Team\\SubTeam"

        Args:
            area_path: Area path string

        Returns:
            Validated area path

        Raises:
            ValidationError: If area path is invalid
        """
        if not area_path:
            raise ValidationError("Area path cannot be empty")

        if len(area_path) > 256:
            raise ValidationError(f"Area path too long: {len(area_path)} chars (max 256)")

        # Allow backslashes, forward slashes, alphanumeric, spaces, hyphens, underscores
        if not re.match(r"^[a-zA-Z0-9 _\-\\/]+$", area_path):
            raise ValidationError(
                f"Invalid area path: '{area_path}'. "
                f"Only letters, numbers, spaces, hyphens, underscores, and slashes allowed."
            )

        # Check for dangerous patterns
        if "'" in area_path or '"' in area_path:
            raise ValidationError("Area path cannot contain quotes")

        return area_path

    @staticmethod
    def validate_field_name(field_name: str) -> str:
        """
        Validate WIQL field name against whitelist.

        Args:
            field_name: Field name (e.g., 'System.Id', 'System.Title')

        Returns:
            Validated field name

        Raises:
            ValidationError: If field name is not in whitelist
        """
        if field_name not in WIQLValidator.VALID_FIELDS:
            raise ValidationError(
                f"Field '{field_name}' not in whitelist. "
                f"Valid fields: {', '.join(sorted(WIQLValidator.VALID_FIELDS))}"
            )
        return field_name

    @staticmethod
    def build_safe_wiql(template: str, **params) -> str:
        """
        Build WIQL query with validated parameters.

        This is the recommended way to construct WIQL queries. All parameters
        are validated before insertion.

        Args:
            template: WIQL query template with {parameter} placeholders
            **params: Named parameters to insert into template

        Returns:
            Complete WIQL query with validated parameters

        Raises:
            ValidationError: If any parameter fails validation

        Example:
            >>> query = WIQLValidator.build_safe_wiql(
            ...     '''SELECT [System.Id] FROM WorkItems
            ...        WHERE [System.TeamProject] = '{project}'
            ...        AND [System.WorkItemType] = '{work_type}' ''',
            ...     project='My Project',
            ...     work_type='Bug'
            ... )
        """
        validated_params = {}

        for key, value in params.items():
            # Determine validation based on parameter name
            key_lower = key.lower()

            if "project" in key_lower:
                validated_params[key] = WIQLValidator.validate_project_name(value)

            elif "work_type" in key_lower or "workitemtype" in key_lower:
                validated_params[key] = WIQLValidator.validate_work_item_type(value)

            elif "state" in key_lower:
                validated_params[key] = WIQLValidator.validate_state(value)

            elif "date" in key_lower:
                validated_params[key] = WIQLValidator.validate_date_iso8601(value)

            elif "area" in key_lower and "path" in key_lower:
                validated_params[key] = WIQLValidator.validate_area_path(value)

            elif "field" in key_lower:
                validated_params[key] = WIQLValidator.validate_field_name(value)

            else:
                # Generic validation for unknown parameters
                if not isinstance(value, str):
                    value = str(value)

                if len(value) > 256:
                    raise ValidationError(f"Parameter '{key}' too long (max 256 chars)")

                # Block quotes and semicolons
                if "'" in value or '"' in value:
                    raise ValidationError(f"Parameter '{key}' contains quotes")
                if ";" in value:
                    raise ValidationError(f"Parameter '{key}' contains semicolon")

                validated_params[key] = value

        try:
            return template.format(**validated_params)
        except KeyError as e:
            raise ValidationError(f"Missing required parameter: {e}")


class HTMLSanitizer:
    """
    Sanitizes HTML output to prevent Cross-Site Scripting (XSS) attacks.

    Use this when generating HTML from user-supplied or external data.
    For production use, consider migrating to Jinja2 with auto-escaping.
    """

    # HTML entities that must be escaped
    HTML_ESCAPES = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
        "/": "&#x2F;",
    }

    @staticmethod
    def escape_html(text: str | None) -> str:
        """
        Escape HTML special characters to prevent XSS.

        This provides defense-in-depth against XSS attacks. Ideally, use
        a templating engine with auto-escaping (like Jinja2).

        Args:
            text: Text to escape (may be None)

        Returns:
            Escaped text safe for HTML context

        Example:
            >>> HTMLSanitizer.escape_html("<script>alert('XSS')</script>")
            '&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;'
        """
        if text is None:
            return ""

        text = str(text)

        # Escape each special character
        for char, escape in HTMLSanitizer.HTML_ESCAPES.items():
            text = text.replace(char, escape)

        return text

    @staticmethod
    def escape_html_attribute(text: str | None) -> str:
        """
        Escape text for use in HTML attributes.

        More strict than regular escaping - removes control characters.

        Args:
            text: Text to escape

        Returns:
            Escaped text safe for HTML attribute context
        """
        if text is None:
            return ""

        text = str(text)

        # Remove control characters (ASCII < 32, except space)
        text = "".join(char for char in text if ord(char) >= 32 or char == " ")

        # Escape HTML entities
        return HTMLSanitizer.escape_html(text)

    @staticmethod
    def escape_javascript_string(text: str | None) -> str:
        """
        Escape text for use in JavaScript string context.

        Args:
            text: Text to escape

        Returns:
            Escaped text safe for JavaScript string context
        """
        if text is None:
            return ""

        text = str(text)

        # Escape JavaScript special characters
        js_escapes = {
            "\\": "\\\\",
            "'": "\\'",
            '"': '\\"',
            "\n": "\\n",
            "\r": "\\r",
            "\t": "\\t",
            "<": "\\x3C",  # Prevent </script> injection
            ">": "\\x3E",
        }

        for char, escape in js_escapes.items():
            text = text.replace(char, escape)

        return text


class PathValidator:
    """
    Validates file paths to prevent path traversal attacks.

    Use this when handling user-supplied file paths or filenames.
    """

    @staticmethod
    def validate_filename(filename: str, allowed_extensions: list[str] = None) -> str:
        """
        Validate filename to prevent path traversal.

        Returns only the basename (no directory components) to prevent
        directory traversal attacks.

        Args:
            filename: User-supplied filename
            allowed_extensions: List of allowed extensions (e.g., ['.json', '.html'])

        Returns:
            Sanitized filename (basename only)

        Raises:
            ValidationError: If filename is invalid

        Example:
            >>> PathValidator.validate_filename("../../etc/passwd")
            ValidationError: Filename contains path separators
            >>> PathValidator.validate_filename("report.html", ['.html'])
            'report.html'
        """
        if not filename:
            raise ValidationError("Filename cannot be empty")

        if not isinstance(filename, str):
            raise ValidationError(f"Filename must be string, got {type(filename)}")

        # Get basename to prevent directory traversal
        basename = os.path.basename(filename)

        if not basename or basename in (".", ".."):
            raise ValidationError(f"Invalid filename: '{filename}'")

        # Check for path traversal attempts
        if ".." in filename or "/" in filename or "\\" in filename:
            raise ValidationError(f"Filename contains path separators: '{filename}'")

        # Validate extension if whitelist provided
        if allowed_extensions:
            if not any(basename.lower().endswith(ext.lower()) for ext in allowed_extensions):
                raise ValidationError(f"Invalid file extension. Allowed: {', '.join(allowed_extensions)}")

        # Check for dangerous patterns
        if basename.startswith("."):
            raise ValidationError("Hidden files not allowed")

        # Validate length
        if len(basename) > 255:
            raise ValidationError(f"Filename too long: {len(basename)} chars (max 255)")

        return basename

    @staticmethod
    def validate_safe_path(base_dir: str, user_path: str) -> str:
        """
        Validate that user_path is within base_dir.

        Prevents directory traversal attacks by ensuring the resolved
        absolute path stays within the allowed base directory.

        Args:
            base_dir: Base directory (must exist)
            user_path: User-supplied path (relative to base_dir)

        Returns:
            Absolute path if valid and within base_dir

        Raises:
            ValidationError: If path escapes base directory

        Example:
            >>> PathValidator.validate_safe_path('/tmp', 'report.json')
            '/tmp/report.json'
            >>> PathValidator.validate_safe_path('/tmp', '../../etc/passwd')
            ValidationError: Path traversal detected
        """
        if not base_dir:
            raise ValidationError("Base directory cannot be empty")

        if not user_path:
            raise ValidationError("User path cannot be empty")

        # Get absolute paths
        base_dir = os.path.abspath(base_dir)
        full_path = os.path.abspath(os.path.join(base_dir, user_path))

        # Check if full_path is within base_dir
        # Use os.path.commonpath to handle edge cases correctly
        try:
            common = os.path.commonpath([base_dir, full_path])
        except ValueError:
            # Paths on different drives (Windows)
            raise ValidationError("Path traversal detected: paths on different drives")

        if common != base_dir:
            raise ValidationError(f"Path traversal detected: '{user_path}' escapes base directory")

        return full_path


class CommandValidator:
    """
    Validates command-line arguments to prevent command injection.

    Use this when building subprocess commands with user input.
    """

    @staticmethod
    def validate_safe_argument(arg: str) -> str:
        """
        Validate command-line argument.

        For use with subprocess calls. Note that subprocess with list arguments
        is generally safe, but this provides defense-in-depth.

        Args:
            arg: Command-line argument

        Returns:
            Validated argument

        Raises:
            ValidationError: If argument contains dangerous characters

        Example:
            >>> CommandValidator.validate_safe_argument("myfile.txt")
            'myfile.txt'
            >>> CommandValidator.validate_safe_argument("file.txt && rm -rf /")
            ValidationError: Argument contains dangerous character: &
        """
        if not arg:
            raise ValidationError("Argument cannot be empty")

        if not isinstance(arg, str):
            arg = str(arg)

        # Check for dangerous patterns
        dangerous_chars = ["&", "|", ";", "`", "$", "(", ")", "<", ">", "\n", "\r", "\x00"]

        for char in dangerous_chars:
            if char in arg:
                raise ValidationError(f"Argument contains dangerous character: {char}")

        # Validate length
        if len(arg) > 1024:
            raise ValidationError(f"Argument too long: {len(arg)} chars (max 1024)")

        return arg

    @staticmethod
    def validate_command_path(command_path: str, allowed_commands: list[str] = None) -> str:
        """
        Validate command executable path.

        Args:
            command_path: Path to command executable
            allowed_commands: Whitelist of allowed command names

        Returns:
            Validated command path

        Raises:
            ValidationError: If command is not allowed
        """
        if not command_path:
            raise ValidationError("Command path cannot be empty")

        # Get basename (command name)
        command_name = os.path.basename(command_path)

        # If whitelist provided, check against it
        if allowed_commands:
            if command_name not in allowed_commands:
                raise ValidationError(
                    f"Command '{command_name}' not in whitelist. " f"Allowed: {', '.join(allowed_commands)}"
                )

        # Validate path doesn't contain dangerous patterns
        if ".." in command_path:
            raise ValidationError("Command path contains '..' (path traversal)")

        return command_path


# Convenience functions for common use cases


def safe_html(text: str | None) -> str:
    """Convenience wrapper for HTMLSanitizer.escape_html()"""
    return HTMLSanitizer.escape_html(text)


def safe_wiql(template: str, **params) -> str:
    """Convenience wrapper for WIQLValidator.build_safe_wiql()"""
    return WIQLValidator.build_safe_wiql(template, **params)


# Module-level test
if __name__ == "__main__":
    print("Security Utils - Self Test")
    print("=" * 60)

    # Test WIQL validation
    print("\n1. Testing WIQL Validator:")
    try:
        WIQLValidator.validate_project_name("'; DROP TABLE--")
        print("  [FAIL] Injection attempt not blocked")
    except ValidationError as e:
        print(f"  [PASS] Injection blocked: {e}")

    try:
        valid = WIQLValidator.validate_project_name("My Project")
        print(f"  [PASS] Valid project name accepted: '{valid}'")
    except ValidationError as e:
        print(f"  [FAIL] Valid input rejected: {e}")

    # Test HTML sanitizer
    print("\n2. Testing HTML Sanitizer:")
    xss_payload = "<script>alert('XSS')</script>"
    escaped = HTMLSanitizer.escape_html(xss_payload)
    if "<script>" not in escaped and "&lt;" in escaped:
        print(f"  [PASS] XSS payload escaped: {escaped}")
    else:
        print(f"  [FAIL] XSS not properly escaped: {escaped}")

    # Test path validator
    print("\n3. Testing Path Validator:")
    try:
        PathValidator.validate_filename("../../etc/passwd")
        print("  [FAIL] Path traversal not blocked")
    except ValidationError as e:
        print(f"  [PASS] Path traversal blocked: {e}")

    try:
        safe_file = PathValidator.validate_filename("report.html", [".html"])
        print(f"  [PASS] Valid filename accepted: '{safe_file}'")
    except ValidationError as e:
        print(f"  [FAIL] Valid filename rejected: {e}")

    # Test command validator
    print("\n4. Testing Command Validator:")
    try:
        CommandValidator.validate_safe_argument("file.txt && rm -rf /")
        print("  [FAIL] Command injection not blocked")
    except ValidationError as e:
        print(f"  [PASS] Command injection blocked: {e}")

    print("\n" + "=" * 60)
    print("Self test complete! All validators working correctly.")
