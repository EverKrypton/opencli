"""Configuration management for OPENCLI."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class AIConfig:
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class EditorConfig:
    tab_size: int = 4
    show_line_numbers: bool = True
    auto_indent: bool = True
    theme: str = "monokai"
    word_wrap: bool = False


@dataclass
class Config:
    ai: AIConfig = field(default_factory=AIConfig)
    editor: EditorConfig = field(default_factory=EditorConfig)
    
    @classmethod
    def get_config_path(cls) -> Path:
        if "TERMUX_VERSION" in os.environ:
            return Path.home() / ".opencli" / "config.json"
        xdg_config = os.environ.get("XDG_CONFIG_HOME", "")
        if xdg_config:
            return Path(xdg_config) / "opencli" / "config.json"
        return Path.home() / ".config" / "opencli" / "config.json"
    
    @classmethod
    def load(cls) -> "Config":
        config_path = cls.get_config_path()
        config = cls()
        
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    data = json.load(f)
                
                if "ai" in data:
                    config.ai = AIConfig(**data["ai"])
                if "editor" in data:
                    config.editor = EditorConfig(**data["editor"])
            except (json.JSONDecodeError, TypeError):
                pass
        
        env_api_key = os.environ.get("OPENCLI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if env_api_key:
            config.ai.api_key = env_api_key
        
        env_base_url = os.environ.get("OPENCLI_BASE_URL")
        if env_base_url:
            config.ai.base_url = env_base_url
        
        return config
    
    def save(self) -> None:
        config_path = self.get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "ai": {
                "api_key": self.ai.api_key,
                "base_url": self.ai.base_url,
                "model": self.ai.model,
                "max_tokens": self.ai.max_tokens,
                "temperature": self.ai.temperature,
            },
            "editor": {
                "tab_size": self.editor.tab_size,
                "show_line_numbers": self.editor.show_line_numbers,
                "auto_indent": self.editor.auto_indent,
                "theme": self.editor.theme,
                "word_wrap": self.editor.word_wrap,
            },
        }
        
        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)
