"""
Command Validator for Preventing Command Injection

Validates command-line arguments to prevent command injection attacks.
Use this when building subprocess commands with user input.

Author: Security Audit Implementation
Date: 2026-02-06
Refactored: 2026-02-08
"""

import os

from .validation import ValidationError


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
    def validate_command_path(command_path: str, allowed_commands: list[str] | None = None) -> str:
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
