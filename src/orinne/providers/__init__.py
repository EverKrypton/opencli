"""Multi-provider support with auto-detection."""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import httpx


class Provider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    GROQ = "groq"
    OPENROUTER = "openrouter"
    TOGETHER = "together"
    OLLAMA = "ollama"
    UNKNOWN = "unknown"


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key: str = ""
    models: List[str] = field(default_factory=list)
    default_model: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    
    def get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            if self.name == "anthropic":
                headers["x-api-key"] = self.api_key
                headers["anthropic-version"] = "2023-06-01"
            elif self.name == "google":
                headers["Authorization"] = f"Bearer {self.api_key}"
            else:
                headers["Authorization"] = f"Bearer {self.api_key}"
        return {**headers, **self.headers}


PROVIDERS: Dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        name="openai",
        base_url="https://api.openai.com/v1",
        models=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        default_model="gpt-4o"
    ),
    "anthropic": ProviderConfig(
        name="anthropic",
        base_url="https://api.anthropic.com/v1",
        models=["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-haiku-20240307"],
        default_model="claude-3-5-sonnet-20241022"
    ),
    "google": ProviderConfig(
        name="google",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        models=["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        default_model="gemini-2.0-flash"
    ),
    "groq": ProviderConfig(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        models=["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        default_model="llama-3.3-70b-versatile"
    ),
    "openrouter": ProviderConfig(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        models=["anthropic/claude-3.5-sonnet", "openai/gpt-4o", "meta-llama/llama-3.1-70b-instruct"],
        default_model="anthropic/claude-3.5-sonnet",
        headers={"HTTP-Referer": "https://github.com/EverKrypton/opencli"}
    ),
    "together": ProviderConfig(
        name="together",
        base_url="https://api.together.xyz/v1",
        models=["meta-llama/Llama-3-70b-chat-hf", "mistralai/Mixtral-8x7B-Instruct-v0.1"],
        default_model="meta-llama/Llama-3-70b-chat-hf"
    ),
    "ollama": ProviderConfig(
        name="ollama",
        base_url="http://localhost:11434/v1",
        models=["llama3.2", "codellama", "mistral", "qwen2.5-coder"],
        default_model="llama3.2"
    ),
}


def detect_provider(api_key: str) -> str:
    """Detect provider from API key format."""
    if not api_key:
        return "openai"
    
    key = api_key.lower()
    
    if key.startswith("sk-or-"):
        return "openrouter"
    elif key.startswith("sk-ant-"):
        return "anthropic"
    elif key.startswith("sk-"):
        return "openai"
    elif key.startswith("aiza"):
        return "google"
    elif key.startswith("gsk_"):
        return "groq"
    elif key.startswith("sk-") and len(key) > 50:
        return "openai"
    
    return "openai"


def get_provider_config(provider_name: str) -> ProviderConfig:
    """Get provider configuration."""
    return PROVIDERS.get(provider_name, PROVIDERS["openai"])


async def fetch_models(provider: str, api_key: str) -> List[str]:
    """Fetch available models from provider."""
    config = get_provider_config(provider)
    
    if provider == "ollama":
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{config.base_url.replace('/v1', '')}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    return [m["name"] for m in data.get("models", [])]
        except:
            pass
    elif provider in ["openai", "groq", "openrouter", "together"]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{config.base_url}/models",
                    headers=config.get_headers()
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return [m["id"] for m in data.get("data", [])]
        except:
            pass
    
    return config.models


@dataclass
class PricingInfo:
    input_cost: float
    output_cost: float
    
    def estimate(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens * self.input_cost / 1000) + (output_tokens * self.output_cost / 1000)


MODEL_PRICING: Dict[str, PricingInfo] = {
    "gpt-4o": PricingInfo(0.0025, 0.01),
    "gpt-4o-mini": PricingInfo(0.00015, 0.0006),
    "gpt-4-turbo": PricingInfo(0.01, 0.03),
    "gpt-3.5-turbo": PricingInfo(0.0005, 0.0015),
    "claude-3-5-sonnet-20241022": PricingInfo(0.003, 0.015),
    "claude-3-opus-20240229": PricingInfo(0.015, 0.075),
    "claude-3-haiku-20240307": PricingInfo(0.00025, 0.00125),
    "gemini-2.0-flash": PricingInfo(0.0001, 0.0004),
    "gemini-1.5-pro": PricingInfo(0.00125, 0.005),
    "llama-3.3-70b-versatile": PricingInfo(0.00059, 0.00079),
    "llama-3.1-8b-instant": PricingInfo(0.00005, 0.00008),
    "mixtral-8x7b-32768": PricingInfo(0.00027, 0.00027),
}


def get_pricing(model: str) -> Optional[PricingInfo]:
    """Get pricing info for a model."""
    for key, pricing in MODEL_PRICING.items():
        if key.lower() in model.lower():
            return pricing
    return PricingInfo(0.001, 0.002)
