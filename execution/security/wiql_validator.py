"""
WIQL Validator for Azure DevOps Query Language

Validates and sanitizes inputs for Azure DevOps WIQL (Work Item Query Language) queries.
Azure DevOps does not support parameterized WIQL queries, so strict whitelist-based
validation is used to prevent SQL-like injection attacks.

Security Note:
    Never use string interpolation for WIQL queries without validation.
    Always use WIQLValidator.build_safe_wiql() or validate inputs individually.

Author: Security Audit Implementation
Date: 2026-02-06
Refactored: 2026-02-08
"""

import re
from datetime import datetime

from .validation import ValidationError


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
            year_str, month_str, day_str = date_str.split("-")
            year, month, day = int(year_str), int(month_str), int(day_str)

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
    def build_safe_wiql(template: str, **params: str) -> str:
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
