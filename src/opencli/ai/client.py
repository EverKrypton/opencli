"""AI client for OPENCLI - OpenAI-compatible API integration."""

import json
from typing import AsyncIterator, List, Dict, Any, Optional
from dataclasses import dataclass
import httpx


@dataclass
class Message:
    role: str
    content: str
    
    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass  
class ChatResponse:
    content: str
    model: str
    usage: Dict[str, int]


class AIClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.messages: List[Message] = []
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=120.0)
        return self
    
    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client
    
    def add_message(self, role: str, content: str) -> None:
        self.messages.append(Message(role=role, content=content))
    
    def clear_messages(self) -> None:
        self.messages = []
    
    def set_system_prompt(self, prompt: str) -> None:
        self.messages = [m for m in self.messages if m.role != "system"]
        self.messages.insert(0, Message(role="system", content=prompt))
    
    async def chat(self, message: str) -> ChatResponse:
        self.add_message("user", message)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [m.to_dict() for m in self.messages],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        
        content = data["choices"][0]["message"]["content"]
        self.add_message("assistant", content)
        
        return ChatResponse(
            content=content,
            model=data.get("model", self.model),
            usage=data.get("usage", {}),
        )
    
    async def stream_chat(self, message: str) -> AsyncIterator[str]:
        self.add_message("user", message)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [m.to_dict() for m in self.messages],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": True,
        }
        
        async with self.client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            response.raise_for_status()
            full_content = ""
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_content += content
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
            
            if full_content:
                self.add_message("assistant", full_content)
    
    async def get_code_suggestion(
        self,
        code: str,
        language: str = "python",
        context: str = "",
    ) -> str:
        system_prompt = f"""You are an expert {language} programmer. 
Provide helpful, clean, and efficient code suggestions.
Only output code when asked. Be concise and practical."""
        
        self.set_system_prompt(system_prompt)
        
        prompt = f"Context:\n{context}\n\nCode:\n```\n{code}\n```\n\nHelp improve or complete this code."
        
        response = await self.chat(prompt)
        return response.content
    
    async def explain_code(self, code: str, language: str = "python") -> str:
        system_prompt = "You are a programming teacher. Explain code clearly and concisely."
        self.set_system_prompt(system_prompt)
        
        prompt = f"Explain this {language} code:\n```\n{code}\n```"
        response = await self.chat(prompt)
        return response.content
    
    async def fix_code(self, code: str, error: str = "", language: str = "python") -> str:
        system_prompt = f"You are a {language} debugger. Fix code issues and return the corrected code."
        self.set_system_prompt(system_prompt)
        
        prompt = f"Fix this code"
        if error:
            prompt += f" (error: {error})"
        prompt += f":\n```\n{code}\n```\n\nReturn only the fixed code."
        
        response = await self.chat(prompt)
        return response.content
