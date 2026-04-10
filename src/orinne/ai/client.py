"""AI Client with tools support, streaming, and multi-provider."""

import json
import asyncio
from typing import Dict, List, Optional, Any, AsyncIterator, Callable
from dataclasses import dataclass
import httpx

from orinne.providers import (
    Provider, ProviderConfig, detect_provider, get_provider_config,
    get_pricing, PricingInfo
)
from orinne.tools import ToolsRegistry, ToolResult
from orinne.session import Session, SessionManager, Message


@dataclass
class StreamChunk:
    content: str = ""
    tool_calls: List[Dict] = None
    finish_reason: str = ""
    
    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []


class AIClient:
    def __init__(
        self,
        api_key: str = None,
        provider: str = None,
        model: str = None,
        base_url: str = None,
        tools: ToolsRegistry = None,
        session_manager: SessionManager = None,
        permission_handler: Callable = None,
    ):
        self.api_key = api_key or ""
        
        if provider:
            self.provider_name = provider
        elif api_key:
            self.provider_name = detect_provider(api_key)
        else:
            self.provider_name = "openai"
        
        self.provider_config = get_provider_config(self.provider_name)
        
        if base_url:
            self.base_url = base_url
        else:
            self.base_url = self.provider_config.base_url
        
        if api_key:
            self.provider_config.api_key = api_key
        
        self.model = model or self.provider_config.default_model
        self.tools = tools
        self.session_manager = session_manager or SessionManager()
        self.permission_handler = permission_handler
        
        self.max_tokens = 4096
        self.temperature = 0.7
        self._client: Optional[httpx.AsyncClient] = None
        
        self._on_stream_chunk: Optional[Callable] = None
        self._on_tool_call: Optional[Callable] = None
        self._on_cost_update: Optional[Callable] = None
    
    def set_callbacks(
        self,
        on_stream_chunk: Callable = None,
        on_tool_call: Callable = None,
        on_cost_update: Callable = None,
    ):
        self._on_stream_chunk = on_stream_chunk
        self._on_tool_call = on_tool_call
        self._on_cost_update = on_cost_update
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=180.0)
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def get_session(self) -> Session:
        return self.session_manager.get_or_create()
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        
        if self.provider_name == "anthropic":
            headers["x-api-key"] = self.api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        if self.provider_config.headers:
            headers.update(self.provider_config.headers)
        
        return headers
    
    def _build_messages(self, session: Session) -> List[Dict]:
        messages = []
        
        for msg in session.messages:
            if msg.role == "tool":
                for result in msg.tool_results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": result.get("tool_call_id"),
                        "content": result.get("content", ""),
                    })
            elif msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": msg.tool_calls,
                })
            else:
                messages.append(msg.to_api_format())
        
        return messages
    
    async def chat(self, message: str, stream: bool = True) -> AsyncIterator[str]:
        session = self.get_session()
        session.add_message("user", message)
        
        if stream:
            async for chunk in self._stream_chat(session):
                yield chunk
        else:
            response = await self._complete_chat(session)
            yield response
    
    async def _stream_chat(self, session: Session) -> AsyncIterator[str]:
        messages = self._build_messages(session)
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": True,
        }
        
        if self.tools:
            payload["tools"] = self.tools.get_schemas()
        
        full_content = ""
        tool_calls_buffer: Dict[int, Dict] = {}
        
        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    
                    if "content" in delta and delta["content"]:
                        content = delta["content"]
                        full_content += content
                        if self._on_stream_chunk:
                            await self._on_stream_chunk(content)
                        yield content
                    
                    if "tool_calls" in delta:
                        for tc in delta["tool_calls"]:
                            idx = tc.get("index", 0)
                            if idx not in tool_calls_buffer:
                                tool_calls_buffer[idx] = {
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            
                            if "id" in tc:
                                tool_calls_buffer[idx]["id"] = tc["id"]
                            if "function" in tc:
                                if "name" in tc["function"]:
                                    tool_calls_buffer[idx]["function"]["name"] = tc["function"]["name"]
                                if "arguments" in tc["function"]:
                                    tool_calls_buffer[idx]["function"]["arguments"] += tc["function"]["arguments"]
            
            if tool_calls_buffer:
                tool_calls = list(tool_calls_buffer.values())
                session.add_message("assistant", full_content, tool_calls=tool_calls)
                
                for tc in tool_calls:
                    result = await self._execute_tool_call(tc)
                    session.add_tool_result(tc["id"], result)
                
                if self._on_tool_call:
                    await self._on_tool_call(tool_calls)
                
                async for chunk in self._stream_chat(session):
                    yield chunk
            elif full_content:
                session.add_message("assistant", full_content)
            
            self.session_manager.save_session()
            
        except httpx.HTTPStatusError as e:
            error_msg = f"API Error: {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", {}).get("message", error_msg)
            except:
                pass
            yield f"\n[Error] {error_msg}"
        except Exception as e:
            yield f"\n[Error] {str(e)}"
    
    async def _complete_chat(self, session: Session) -> str:
        messages = self._build_messages(session)
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        
        if self.tools:
            payload["tools"] = self.tools.get_schemas()
        
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            headers=self._get_headers(),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        
        choice = data["choices"][0]
        content = choice["message"].get("content", "")
        
        usage = data.get("usage", {})
        if usage and self._on_cost_update:
            pricing = get_pricing(self.model)
            cost = pricing.estimate(
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0)
            )
            await self._on_cost_update(cost, usage)
        
        session.add_message("assistant", content)
        self.session_manager.save_session()
        
        return content
    
    async def _execute_tool_call(self, tool_call: Dict) -> str:
        func = tool_call.get("function", {})
        name = func.get("name", "")
        args_str = func.get("arguments", "{}")
        
        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid arguments JSON"})
        
        if self._on_tool_call:
            await self._on_tool_call([tool_call])
        
        result = await self.tools.execute(name, **args)
        
        return json.dumps({
            "success": result.success,
            "output": result.output,
            "error": result.error,
        }) if not result.success else result.output
    
    def set_model(self, model: str):
        self.model = model
    
    def set_provider(self, provider: str, api_key: str = None):
        self.provider_name = provider
        self.provider_config = get_provider_config(provider)
        self.base_url = self.provider_config.base_url
        
        if api_key:
            self.api_key = api_key
            self.provider_config.api_key = api_key
        
        if not self.model or self.model not in self.provider_config.models:
            self.model = self.provider_config.default_model
    
    def clear_session(self):
        session = self.get_session()
        session.clear()
        self.session_manager.save_session()
