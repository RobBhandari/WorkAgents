"""
Security Utilities for Input Validation and Sanitization (DEPRECATED)

⚠️  DEPRECATION NOTICE ⚠️
This module is deprecated and will be removed in a future release.
Please update your imports to use the new package structure:

    OLD: from execution.security_utils import WIQLValidator, ValidationError
    NEW: from execution.security import WIQLValidator, ValidationError

Or for relative imports from execution/:
    OLD: from security_utils import WIQLValidator
    NEW: from execution.security import WIQLValidator

The new package provides better organization with separate modules:
    - execution.security.validation: ValidationError base exception
    - execution.security.wiql_validator: WIQL query validation
    - execution.security.html_sanitizer: HTML/XSS sanitization
    - execution.security.path_validator: Path traversal prevention
    - execution.security.command_validator: Command injection prevention

Migration Guide:
    1. Update imports from execution.security_utils to execution.security
    2. All classes and functions have the same API (zero behavior changes)
    3. Update import statements in your files
    4. No code changes required beyond imports

For now, this module continues to work by delegating to the new package.

Author: Security Audit Implementation
Original Date: 2026-02-06
Refactored: 2026-02-08
"""

import warnings

from execution.security import (
    CommandValidator as _CommandValidator,
)
from execution.security import (
    HTMLSanitizer as _HTMLSanitizer,
)
from execution.security import (
    PathValidator as _PathValidator,
)

# Import from new package
from execution.security import (
    ValidationError as _ValidationError,
)
from execution.security import (
    WIQLValidator as _WIQLValidator,
)
from execution.security import (
    safe_html as _safe_html,
)
from execution.security import (
    safe_wiql as _safe_wiql,
)

# Show deprecation warning when this module is imported
warnings.warn(
    "execution.security_utils is deprecated. "
    "Use 'from execution.security import ...' instead. "
    "See module docstring for migration guide.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export all classes for backward compatibility
ValidationError = _ValidationError
WIQLValidator = _WIQLValidator
HTMLSanitizer = _HTMLSanitizer
PathValidator = _PathValidator
CommandValidator = _CommandValidator

# Re-export convenience functions
safe_html = _safe_html
safe_wiql = _safe_wiql

# Maintain __all__ for * imports (though not recommended)
__all__ = [
    "ValidationError",
    "WIQLValidator",
    "HTMLSanitizer",
    "PathValidator",
    "CommandValidator",
    "safe_html",
    "safe_wiql",
]
