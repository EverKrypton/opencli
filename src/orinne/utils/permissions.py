"""Permission system for OPENCLI."""

import os
from typing import Dict, Set, Callable, Optional
from dataclasses import dataclass, field
from enum import Enum


class Permission(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass
class PermissionRule:
    action: str
    resource: str
    permission: Permission


class PermissionManager:
    def __init__(self):
        self.always_allow: Set[str] = set()
        self.always_deny: Set[str] = set()
        self.interactive: bool = True
        self._ask_callback: Optional[Callable] = None
    
    def set_ask_callback(self, callback: Callable):
        self._ask_callback = callback
    
    def add_always_allow(self, key: str):
        self.always_allow.add(key)
    
    def add_always_deny(self, key: str):
        self.always_deny.add(key)
    
    def _make_key(self, action: str, resource: str) -> str:
        return f"{action}:{resource}"
    
    async def check(self, action: str, resource: str = "") -> bool:
        key = self._make_key(action, resource)
        
        if key in self.always_allow:
            return True
        
        if key in self.always_deny:
            return False
        
        if f"{action}:*" in self.always_allow:
            return True
        
        if f"{action}:*" in self.always_deny:
            return False
        
        if not self.interactive:
            return True
        
        if self._ask_callback:
            return await self._ask_callback(action, resource)
        
        return True
    
    def from_response(self, action: str, resource: str, response: str):
        key = self._make_key(action, resource)
        
        if response.lower() in ("a", "always"):
            self.always_allow.add(key)
            return True
        elif response.lower() in ("n", "never"):
            self.always_deny.add(key)
            return False
        elif response.lower() in ("y", "yes", "allow"):
            return True
        else:
            return False


DANGEROUS_COMMANDS = [
    "rm -rf",
    "rm -r",
    "dd if=",
    "mkfs",
    "format",
    "del /",
    "> /dev/sd",
    "chmod -R 777",
    "chown -R",
    ":(){:|:&};:",
    "wget | sh",
    "curl | bash",
    "> /dev/null",
]

SENSITIVE_PATHS = [
    ".env",
    ".pem",
    ".key",
    "id_rsa",
    "credentials",
    "secrets",
    "password",
    "token",
    "api_key",
]


def is_dangerous_command(command: str) -> bool:
    """Check if a command is potentially dangerous."""
    cmd_lower = command.lower()
    for pattern in DANGEROUS_COMMANDS:
        if pattern.lower() in cmd_lower:
            return True
    return False


def is_sensitive_path(path: str) -> bool:
    """Check if a path contains sensitive data."""
    path_lower = path.lower()
    for pattern in SENSITIVE_PATHS:
        if pattern in path_lower:
            return True
    return False
