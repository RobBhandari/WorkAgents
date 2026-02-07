"""
Core Infrastructure - Secure Configuration, HTTP, Validation

This package provides centralized infrastructure utilities that should be used
throughout the application instead of direct library calls.

Usage:
    from execution.core import get_config, get, post

    # Configuration
    config = get_config()
    ado_config = config.get_ado_config()

    # HTTP requests
    response = get(api_url)  # SSL verified, timeout enforced
"""

# Re-export from secure_config
try:
    from ..secure_config import (
        ArmorCodeConfig,
        AzureDevOpsConfig,
        ConfigurationError,
        EmailConfig,
        MicrosoftTeamsConfig,
        SecureConfig,
        get_config,
        validate_config_on_startup,
    )
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from secure_config import (
        ArmorCodeConfig,
        AzureDevOpsConfig,
        ConfigurationError,
        EmailConfig,
        MicrosoftTeamsConfig,
        SecureConfig,
        get_config,
        validate_config_on_startup,
    )

# Re-export from http_client
try:
    from ..http_client import SecureHTTPClient, delete, get, patch, post, put
except ImportError:
    from http_client import SecureHTTPClient, delete, get, patch, post, put

# Re-export from security_utils
try:
    from ..security_utils import (
        CommandValidator,
        HTMLSanitizer,
        PathValidator,
        ValidationError,
        WIQLValidator,
        safe_html,
        safe_wiql,
    )
except ImportError:
    from security_utils import (
        CommandValidator,
        HTMLSanitizer,
        PathValidator,
        ValidationError,
        WIQLValidator,
        safe_html,
        safe_wiql,
    )

__all__ = [
    # Configuration
    "get_config",
    "validate_config_on_startup",
    "ConfigurationError",
    "SecureConfig",
    "AzureDevOpsConfig",
    "ArmorCodeConfig",
    "EmailConfig",
    "MicrosoftTeamsConfig",
    # HTTP
    "get",
    "post",
    "put",
    "delete",
    "patch",
    "SecureHTTPClient",
    # Validation
    "WIQLValidator",
    "HTMLSanitizer",
    "PathValidator",
    "CommandValidator",
    "ValidationError",
    "safe_html",
    "safe_wiql",
]
