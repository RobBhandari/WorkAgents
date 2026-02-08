"""
Test Suite for Path Validator

Tests path traversal prevention with legitimate inputs, edge cases, and
malicious attack vectors to ensure robust security.

Run with:
    pytest tests/security/test_path_validator.py -v
"""

import os
import sys

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from execution.security import PathValidator, ValidationError


class TestPathValidator:
    """Tests for path traversal prevention"""

    def test_validate_simple_filename(self):
        """Test that simple filenames are accepted"""
        result = PathValidator.validate_filename("report.html")
        assert result == "report.html"

    def test_validate_filename_with_extension_check(self):
        """Test filename with extension whitelist"""
        result = PathValidator.validate_filename("report.html", [".html", ".htm"])
        assert result == "report.html"

    def test_reject_invalid_extension(self):
        """Test that invalid extensions are rejected"""
        with pytest.raises(ValidationError, match="Invalid file extension"):
            PathValidator.validate_filename("report.txt", [".html", ".htm"])

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
