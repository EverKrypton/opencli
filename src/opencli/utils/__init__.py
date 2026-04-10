"""Utils module for OPENCLI."""

from .config import Config, AIConfig, EditorConfig
from .permissions import PermissionManager, is_dangerous_command, is_sensitive_path

__all__ = [
    "Config", "AIConfig", "EditorConfig",
    "PermissionManager", "is_dangerous_command", "is_sensitive_path",
]
