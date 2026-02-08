"""
Base Validation Exception for Security Utilities

This module provides the base exception class used across all security validators.

Author: Security Audit Implementation
Date: 2026-02-06
Refactored: 2026-02-08
"""


class ValidationError(Exception):
    """
    Raised when input validation fails.

    This exception should be caught and handled appropriately,
    ensuring sensitive details are not leaked to users.
    """

    pass
