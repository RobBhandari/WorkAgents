"""
Secure Configuration Management

Provides centralized, validated configuration for the application.
Replaces weak os.getenv() calls with strict validation and fail-fast behavior.

Usage:
    from secure_config import get_config

    config = get_config()
    ado_config = config.get_ado_config()
    print(ado_config.organization_url)
    print(ado_config.pat)

Security Features:
    - Strict validation of all configuration values
    - Fail-fast on missing/invalid configuration
    - No default values that could mask misconfigurations
    - Placeholder detection (e.g., "your_pat_here")
    - HTTPS enforcement for URLs
    - Length/format validation for credentials

Raises:
    ConfigurationError: If configuration is missing or invalid
"""

import os
import re
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv


class ConfigurationError(Exception):
    """Raised when configuration is missing or invalid."""
    pass


@dataclass
class AzureDevOpsConfig:
    """
    Validated Azure DevOps configuration.
    """
    organization_url: str
    pat: str
    project: Optional[str] = None

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self):
        """
        Validate Azure DevOps configuration.

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Validate organization URL
        if not self.organization_url:
            raise ConfigurationError("ADO_ORGANIZATION_URL is required")

        if not self.organization_url.startswith('https://'):
            raise ConfigurationError(
                f"ADO_ORGANIZATION_URL must use HTTPS: {self.organization_url}"
            )

        if not ('dev.azure.com' in self.organization_url or 'visualstudio.com' in self.organization_url):
            raise ConfigurationError(
                f"ADO_ORGANIZATION_URL must be a valid Azure DevOps URL: {self.organization_url}"
            )

        # Validate PAT
        if not self.pat:
            raise ConfigurationError("ADO_PAT is required")

        if len(self.pat) < 20:
            raise ConfigurationError(
                f"ADO_PAT appears invalid (too short: {len(self.pat)} chars, expected ≥20)"
            )

        # Check for placeholder values
        placeholders = ['your_pat', 'your_token', 'example', 'placeholder', 'xxx', 'replace_me']
        if any(placeholder in self.pat.lower() for placeholder in placeholders):
            raise ConfigurationError(
                "ADO_PAT contains a placeholder value - please set a real Personal Access Token"
            )

        # Validate project if provided
        if self.project:
            if not re.match(r'^[a-zA-Z0-9 _\-\.]+$', self.project):
                raise ConfigurationError(
                    f"ADO_PROJECT contains invalid characters: {self.project}"
                )


@dataclass
class ArmorCodeConfig:
    """
    Validated ArmorCode configuration.
    """
    api_key: str
    base_url: str

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self):
        """
        Validate ArmorCode configuration.

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Validate API key
        if not self.api_key:
            raise ConfigurationError("ARMORCODE_API_KEY is required")

        # Check for UUID format (ArmorCode uses UUIDs)
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if not re.match(uuid_pattern, self.api_key.lower()):
            raise ConfigurationError(
                f"ARMORCODE_API_KEY must be a valid UUID format"
            )

        # Validate base URL
        if not self.base_url:
            raise ConfigurationError("ARMORCODE_BASE_URL is required")

        if not self.base_url.startswith('https://'):
            raise ConfigurationError(
                f"ARMORCODE_BASE_URL must use HTTPS: {self.base_url}"
            )


@dataclass
class EmailConfig:
    """
    Validated email configuration (Gmail SMTP).
    """
    sender_email: str
    sender_password: str
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self):
        """
        Validate email configuration.

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Validate sender email
        if not self.sender_email:
            raise ConfigurationError("EMAIL_SENDER is required")

        # Basic email format validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, self.sender_email):
            raise ConfigurationError(
                f"EMAIL_SENDER must be a valid email address: {self.sender_email}"
            )

        # Validate password
        if not self.sender_password:
            raise ConfigurationError("EMAIL_PASSWORD is required")

        if len(self.sender_password) < 8:
            raise ConfigurationError(
                "EMAIL_PASSWORD appears invalid (too short)"
            )

        # Check for placeholders
        placeholders = ['your_password', 'password', 'example', 'xxx']
        if any(placeholder in self.sender_password.lower() for placeholder in placeholders):
            raise ConfigurationError(
                "EMAIL_PASSWORD contains a placeholder value"
            )


@dataclass
class MicrosoftTeamsConfig:
    """
    Validated Microsoft Teams bot configuration.
    """
    app_id: str
    app_password: str

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self):
        """
        Validate Teams bot configuration.

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Validate app ID (GUID format)
        if not self.app_id:
            raise ConfigurationError("MICROSOFT_APP_ID is required")

        guid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if not re.match(guid_pattern, self.app_id.lower()):
            raise ConfigurationError(
                "MICROSOFT_APP_ID must be a valid GUID"
            )

        # Validate app password
        if not self.app_password:
            raise ConfigurationError("MICROSOFT_APP_PASSWORD is required")

        if len(self.app_password) < 10:
            raise ConfigurationError(
                "MICROSOFT_APP_PASSWORD appears invalid (too short)"
            )


class SecureConfig:
    """
    Centralized secure configuration manager.

    Loads and validates all application configuration from environment variables.
    Provides fail-fast behavior to catch configuration issues early.
    """

    def __init__(self):
        """Initialize configuration (loads .env file)."""
        load_dotenv()

    def get_ado_config(self, project: Optional[str] = None) -> AzureDevOpsConfig:
        """
        Get validated Azure DevOps configuration.

        Args:
            project: Optional project name (overrides ADO_PROJECT env var)

        Returns:
            AzureDevOpsConfig: Validated configuration

        Raises:
            ConfigurationError: If configuration is missing or invalid
        """
        organization_url = os.getenv('ADO_ORGANIZATION_URL')
        pat = os.getenv('ADO_PAT')
        project = project or os.getenv('ADO_PROJECT')

        return AzureDevOpsConfig(
            organization_url=organization_url or '',
            pat=pat or '',
            project=project
        )

    def get_armorcode_config(self) -> ArmorCodeConfig:
        """
        Get validated ArmorCode configuration.

        Returns:
            ArmorCodeConfig: Validated configuration

        Raises:
            ConfigurationError: If configuration is missing or invalid
        """
        api_key = os.getenv('ARMORCODE_API_KEY')
        base_url = os.getenv('ARMORCODE_BASE_URL', 'https://api.armorcode.com')

        return ArmorCodeConfig(
            api_key=api_key or '',
            base_url=base_url
        )

    def get_email_config(self) -> EmailConfig:
        """
        Get validated email configuration.

        Returns:
            EmailConfig: Validated configuration

        Raises:
            ConfigurationError: If configuration is missing or invalid
        """
        sender_email = os.getenv('EMAIL_SENDER')
        sender_password = os.getenv('EMAIL_PASSWORD')

        return EmailConfig(
            sender_email=sender_email or '',
            sender_password=sender_password or ''
        )

    def get_teams_config(self) -> MicrosoftTeamsConfig:
        """
        Get validated Microsoft Teams bot configuration.

        Returns:
            MicrosoftTeamsConfig: Validated configuration

        Raises:
            ConfigurationError: If configuration is missing or invalid
        """
        app_id = os.getenv('MICROSOFT_APP_ID')
        app_password = os.getenv('MICROSOFT_APP_PASSWORD')

        return MicrosoftTeamsConfig(
            app_id=app_id or '',
            app_password=app_password or ''
        )


# Convenience function for getting configuration
_config_instance = None

def get_config() -> SecureConfig:
    """
    Get the global configuration instance (singleton pattern).

    Returns:
        SecureConfig: The configuration manager
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = SecureConfig()
    return _config_instance


def validate_config_on_startup(required_services: list[str]) -> None:
    """
    Validate required configuration at application startup.

    Call this in your main() function to fail fast if configuration is invalid.

    Args:
        required_services: List of services to validate (e.g., ['ado', 'armorcode', 'email'])

    Raises:
        ConfigurationError: If any required configuration is missing or invalid

    Example:
        if __name__ == '__main__':
            validate_config_on_startup(['ado', 'armorcode'])
            # Rest of your code...
    """
    config = get_config()

    for service in required_services:
        if service == 'ado':
            config.get_ado_config()  # Raises if invalid
        elif service == 'armorcode':
            config.get_armorcode_config()  # Raises if invalid
        elif service == 'email':
            config.get_email_config()  # Raises if invalid
        elif service == 'teams':
            config.get_teams_config()  # Raises if invalid
        else:
            raise ValueError(f"Unknown service: {service}")


# Self-test when run directly
if __name__ == '__main__':
    print("Secure Configuration - Self Test")
    print("=" * 60)

    config = get_config()

    # Test ADO config
    print("\n[TEST] Azure DevOps Configuration")
    try:
        ado_config = config.get_ado_config()
        print(f"  [OK] Organization: {ado_config.organization_url}")
        print(f"  [OK] PAT: {'*' * 20} (masked)")
        if ado_config.project:
            print(f"  [OK] Project: {ado_config.project}")
    except ConfigurationError as e:
        print(f"  [FAIL] {e}")

    # Test ArmorCode config
    print("\n[TEST] ArmorCode Configuration")
    try:
        ac_config = config.get_armorcode_config()
        print(f"  [OK] Base URL: {ac_config.base_url}")
        print(f"  [OK] API Key: {'*' * 20} (masked)")
    except ConfigurationError as e:
        print(f"  [FAIL] {e}")

    # Test Email config
    print("\n[TEST] Email Configuration")
    try:
        email_config = config.get_email_config()
        print(f"  [OK] Sender: {email_config.sender_email}")
        print(f"  [OK] SMTP: {email_config.smtp_server}:{email_config.smtp_port}")
    except ConfigurationError as e:
        print(f"  [FAIL] {e}")

    print("\n" + "=" * 60)
    print("Configuration validation complete!")
    print("\nUsage:")
    print("  from secure_config import get_config")
    print("  config = get_config()")
    print("  ado_config = config.get_ado_config()")
