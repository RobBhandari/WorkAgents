"""
Security Utilities for Input Validation and Sanitization

This package provides centralized security validation to prevent injection attacks
and other security vulnerabilities across the application.

Package Structure:
    - validation: Base ValidationError exception
    - wiql_validator: WIQL query input validation (Azure DevOps)
    - html_sanitizer: HTML escaping for XSS prevention
    - path_validator: File path validation for traversal prevention
    - command_validator: Command-line argument validation

Usage:
    from execution.security import WIQLValidator, ValidationError

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
Refactored: 2026-02-08
"""

# Core exception
from .command_validator import CommandValidator
from .html_sanitizer import HTMLSanitizer
from .path_validator import PathValidator
from .validation import ValidationError

# Validators
from .wiql_validator import WIQLValidator


# Convenience functions for common use cases
def safe_html(text: str | None) -> str:
    """Convenience wrapper for HTMLSanitizer.escape_html()"""
    return HTMLSanitizer.escape_html(text)


def safe_wiql(template: str, **params) -> str:
    """Convenience wrapper for WIQLValidator.build_safe_wiql()"""
    return WIQLValidator.build_safe_wiql(template, **params)


# Public API
__all__ = [
    "ValidationError",
    "WIQLValidator",
    "HTMLSanitizer",
    "PathValidator",
    "CommandValidator",
    "safe_html",
    "safe_wiql",
]
