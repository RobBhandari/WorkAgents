"""
Path Validator for Preventing Traversal Attacks

Validates file paths to prevent path traversal attacks.
Use this when handling user-supplied file paths or filenames.

Author: Security Audit Implementation
Date: 2026-02-06
Refactored: 2026-02-08
"""

import os

from execution.security.validation import ValidationError


def _reject_traversal(filename: str, basename: str) -> None:
    """Raise ValidationError if filename or basename contains traversal patterns."""
    if not basename or basename in (".", ".."):
        raise ValidationError(f"Invalid filename: '{filename}'")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise ValidationError(f"Filename contains path separators: '{filename}'")


def _reject_extension(basename: str, allowed_extensions: list[str]) -> None:
    """Raise ValidationError if basename extension is not in the allowed list."""
    if not any(basename.lower().endswith(ext.lower()) for ext in allowed_extensions):
        raise ValidationError(f"Invalid file extension. Allowed: {', '.join(allowed_extensions)}")


class PathValidator:
    """
    Validates file paths to prevent path traversal attacks.

    Use this when handling user-supplied file paths or filenames.
    """

    @staticmethod
    def validate_filename(filename: str, allowed_extensions: list[str] | None = None) -> str:
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
        _reject_traversal(filename, basename)

        if allowed_extensions:
            _reject_extension(basename, allowed_extensions)

        if basename.startswith("."):
            raise ValidationError("Hidden files not allowed")

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
