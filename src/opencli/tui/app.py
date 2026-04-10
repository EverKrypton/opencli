"""Main TUI application for OPENCLI - Full-featured interface."""

import os
import asyncio
from typing import Optional, Dict, List, Any
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header,
    Footer,
    Static,
    TextArea,
    Input,
    Label,
    Button,
)
from textual.widget import Widget
from textual.screen import Screen, ModalScreen
from textual.reactive import reactive
from textual.binding import Binding
from textual.message import Message
from textual.events import Key
from rich.text import Text
from rich.syntax import Syntax
from rich.markdown import Markdown

from opencli.utils.config import Config
from opencli.utils.permissions import PermissionManager, is_dangerous_command, is_sensitive_path
from opencli.tools import ToolsRegistry
from opencli.providers import detect_provider, get_provider_config, fetch_models
from opencli.session import SessionManager
from opencli.ai.client import AIClient


class ChatHistory(Widget):
    DEFAULT_CSS = """
    ChatHistory {
        height: 1fr;
        padding: 0 1;
        overflow-y: auto;
    }
    """
    
    messages = reactive([])
    
    def render(self) -> Text:
        if not self.messages:
            return Text("")
        
        lines = []
        for msg in self.messages[-100:]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            if role == "user":
                prefix = Text("You: ", style="bold green")
            elif role == "assistant":
                prefix = Text("AI: ", style="bold cyan")
            elif role == "tool":
                prefix = Text("Tool: ", style="bold yellow")
            else:
                prefix = Text(f"{role}: ", style="bold")
            
            text = Text()
            text.append(prefix)
            text.append(content[:2000])
            lines.append(text)
            lines.append(Text(""))
        
        return Text("\n").join(lines)
    
    def add_message(self, role: str, content: str):
        self.messages = [*self.messages, {"role": role, "content": content}]
        self.scroll_end()
    
    def clear(self):
        self.messages = []


class StatusBar(Widget):
    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
    }
    """
    
    provider = reactive("openai")
    model = reactive("gpt-4o")
    cost = reactive(0.0)
    tokens = reactive(0)
    mode = reactive("chat")
    
    def render(self) -> Text:
        status = f" {self.provider} | {self.model} | ${self.cost:.4f} | {self.tokens} tokens | {self.mode} "
        return Text(status, style="bold white on blue")


class ToolOutput(Widget):
    DEFAULT_CSS = """
    ToolOutput {
        height: 8;
        border: solid $accent;
        padding: 1;
        overflow: hidden;
    }
    """
    
    content = reactive("")
    
    def render(self) -> Text:
        if not self.content:
            return Text("Tool output will appear here", style="dim italic")
        
        lines = self.content.split("\n")[-20:]
        return Text("\n".join(lines))


class PermissionDialog(ModalScreen):
    DEFAULT_CSS = """
    PermissionDialog {
        align: center middle;
    }
    
    PermissionDialog > Container {
        width: 60;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }
    """
    
    BINDINGS = [
        Binding("y", "allow", "Allow"),
        Binding("a", "always", "Always"),
        Binding("n", "deny", "Deny"),
        Binding("escape", "cancel", "Cancel"),
    ]
    
    def __init__(self, action: str, resource: str, **kwargs):
        super().__init__(**kwargs)
        self.action = action
        self.resource = resource
        self.result: Optional[str] = None
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Label(f"[bold]Permission Request[/bold]", classes="title")
            yield Label(f"Action: {self.action}")
            yield Label(f"Resource: {self.resource}")
            yield Label("")
            yield Label("[Y] Allow once  [A] Always  [N] Deny  [Esc] Cancel")
    
    def action_allow(self):
        self.result = "y"
        self.dismiss("y")
    
    def action_always(self):
        self.result = "a"
        self.dismiss("a")
    
    def action_deny(self):
        self.result = "n"
        self.dismiss("n")
    
    def action_cancel(self):
        self.dismiss(None)


class CommandInput(Input):
    DEFAULT_CSS = """
    CommandInput {
        dock: bottom;
        height: 3;
        padding: 0 1;
    }
    """


class MainScreen(Screen):
    BINDINGS = [
        Binding("ctrl+n", "new_session", "New"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("f1", "help", "Help"),
        Binding("f2", "settings", "Settings"),
        Binding("f3", "models", "Models"),
        Binding("f4", "sessions", "Sessions"),
        Binding("ctrl+c", "interrupt", "Interrupt"),
    ]
    
    def __init__(self, config: Config, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.permission_manager = PermissionManager()
        self.tools: Optional[ToolsRegistry] = None
        self.ai_client: Optional[AIClient] = None
        self.session_manager = SessionManager()
        self._is_processing = False
        self._current_task = None
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main"):
            with Vertical(id="chat_panel"):
                yield ChatHistory(id="chat_history")
            with Vertical(id="tool_panel"):
                yield ToolOutput(id="tool_output")
            with Horizontal(id="input_area"):
                yield CommandInput(
                    placeholder="Message (or /help for commands)...",
                    id="cmd_input"
                )
        yield StatusBar()
        yield Footer()
    
    async def on_mount(self) -> None:
        self.chat_history = self.query_one("#chat_history", ChatHistory)
        self.tool_output = self.query_one("#tool_output", ToolOutput)
        self.cmd_input = self.query_one("#cmd_input", CommandInput)
        self.status_bar = self.query_one(StatusBar)
        
        await self._setup_client()
        
        self._show_welcome()
    
    async def _setup_client(self):
        api_key = self.config.ai.api_key or os.environ.get("OPENCLI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        base_url = self.config.ai.base_url or os.environ.get("OPENCLI_BASE_URL")
        model = self.config.ai.model
        
        provider = detect_provider(api_key) if api_key else "openai"
        
        self.permission_manager.set_ask_callback(self._ask_permission)
        
        self.tools = ToolsRegistry(
            workdir=os.getcwd(),
            permission_handler=self._check_permission
        )
        
        self.ai_client = AIClient(
            api_key=api_key,
            provider=provider,
            model=model,
            base_url=base_url,
            tools=self.tools,
            session_manager=self.session_manager,
            permission_handler=self._check_permission,
        )
        
        self.ai_client.set_callbacks(
            on_stream_chunk=self._on_stream_chunk,
            on_tool_call=self._on_tool_call,
            on_cost_update=self._on_cost_update,
        )
        
        self.status_bar.provider = provider
        self.status_bar.model = model or self.ai_client.model
    
    async def _ask_permission(self, action: str, resource: str) -> bool:
        result = await self.app.push_screen_wait(
            PermissionDialog(action, resource)
        )
        
        if result:
            self.permission_manager.from_response(action, resource, result)
            return result in ("y", "a", "yes", "always")
        return False
    
    async def _check_permission(self, action: str, resource: str) -> bool:
        if action == "bash" and is_dangerous_command(resource):
            return await self._ask_permission(action, resource)
        
        if action in ("write", "edit") and is_sensitive_path(resource):
            return await self._ask_permission(action, resource)
        
        return True
    
    async def _on_stream_chunk(self, chunk: str):
        self.chat_history.messages[-1]["content"] += chunk
        self.chat_history.refresh()
    
    async def _on_tool_call(self, tool_calls: List[Dict]):
        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "unknown")
            self.tool_output.content = f"[{name}] Executing..."
            self.tool_output.refresh()
    
    async def _on_cost_update(self, cost: float, usage: Dict):
        self.status_bar.cost += cost
        self.status_bar.tokens += usage.get("total_tokens", 0)
    
    def _show_welcome(self):
        self.chat_history.add_message("system", """
╔═══════════════════════════════════════════════════════╗
║                    OPENCLI v1.0                       ║
║         AI-powered CLI agent for Terminal             ║
╚═══════════════════════════════════════════════════════╝

Commands:
  /help      - Show available commands
  /login     - Configure API key
  /models    - List available models
  /clear     - Clear conversation
  /settings  - View current settings
  /sessions  - List saved sessions

Just type your message to chat with AI!
        """.strip())
    
    async def on_input_submitted(self, event: Input.Submitted):
        message = event.value.strip()
        if not message:
            return
        
        event.input.value = ""
        
        if message.startswith("/"):
            await self._handle_slash_command(message)
        else:
            await self._send_message(message)
    
    async def _handle_slash_command(self, command: str):
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:]
        
        if cmd in ("/help", "/?"):
            self._show_help()
        elif cmd == "/login":
            await self._handle_login(args)
        elif cmd == "/models":
            await self._handle_models()
        elif cmd == "/clear":
            self.action_clear()
        elif cmd == "/settings":
            self._show_settings()
        elif cmd == "/sessions":
            await self._show_sessions()
        elif cmd == "/new":
            self.action_new_session()
        elif cmd in ("/exit", "/quit", "/q"):
            self.app.exit()
        else:
            self.chat_history.add_message("system", f"Unknown command: {cmd}")
    
    def _show_help(self):
        self.chat_history.add_message("system", """
Available Commands:
  /help       Show this help
  /login      Set API key (usage: /login <api-key>)
  /models     List available models
  /settings   Show current configuration
  /clear      Clear conversation history
  /sessions   List saved sessions
  /new        Start new session
  /exit       Exit OPENCLI

Keyboard Shortcuts:
  Ctrl+N      New session
  Ctrl+L      Clear screen
  Ctrl+C      Interrupt current operation
  F1          Help
  F2          Settings
  F3          Models
  F4          Sessions
        """.strip())
    
    async def _handle_login(self, args: List[str]):
        if not args:
            self.chat_history.add_message("system", "Usage: /login <api-key>")
            return
        
        api_key = args[0]
        provider = detect_provider(api_key)
        
        self.config.ai.api_key = api_key
        self.config.save()
        
        await self._setup_client()
        
        self.chat_history.add_message("system", f"Logged in to {provider}")
        self.status_bar.provider = provider
    
    async def _handle_models(self):
        if not self.ai_client:
            self.chat_history.add_message("system", "Please login first: /login <api-key>")
            return
        
        self.chat_history.add_message("system", "Fetching models...")
        
        try:
            models = await fetch_models(self.ai_client.provider_name, self.ai_client.api_key)
            model_list = "\n".join(f"  • {m}" for m in models[:20])
            self.chat_history.add_message("system", f"Available models:\n{model_list}")
        except Exception as e:
            config = get_provider_config(self.ai_client.provider_name)
            model_list = "\n".join(f"  • {m}" for m in config.models)
            self.chat_history.add_message("system", f"Default models:\n{model_list}")
    
    def _show_settings(self):
        settings = f"""
Current Settings:
  Provider: {self.ai_client.provider_name if self.ai_client else 'not configured'}
  Model: {self.ai_client.model if self.ai_client else 'not configured'}
  Base URL: {self.ai_client.base_url if self.ai_client else 'not configured'}
  Temperature: {self.config.ai.temperature}
  Max Tokens: {self.config.ai.max_tokens}
  
  Editor:
    Tab size: {self.config.editor.tab_size}
    Auto indent: {self.config.editor.auto_indent}
    Theme: {self.config.editor.theme}
        """.strip()
        self.chat_history.add_message("system", settings)
    
    async def _show_sessions(self):
        sessions = self.session_manager.list_sessions()
        if not sessions:
            self.chat_history.add_message("system", "No saved sessions")
            return
        
        session_list = "\n".join(
            f"  • {s['id']} ({s['message_count']} messages)"
            for s in sessions[:10]
        )
        self.chat_history.add_message("system", f"Recent sessions:\n{session_list}")
    
    async def _send_message(self, message: str):
        if not self.ai_client or not self.ai_client.api_key:
            self.chat_history.add_message("system", "Please login first: /login <api-key>")
            return
        
        self.chat_history.add_message("user", message)
        self.chat_history.add_message("assistant", "")
        
        self._is_processing = True
        self.status_bar.mode = "processing..."
        
        try:
            async for chunk in self.ai_client.chat(message, stream=True):
                if not self._is_processing:
                    break
        except Exception as e:
            self.chat_history.add_message("system", f"Error: {str(e)}")
        finally:
            self._is_processing = False
            self.status_bar.mode = "chat"
    
    def action_new_session(self):
        self.ai_client.clear_session()
        self.chat_history.clear()
        self._show_welcome()
        self.status_bar.cost = 0.0
        self.status_bar.tokens = 0
    
    def action_clear(self):
        self.chat_history.clear()
    
    def action_interrupt(self):
        self._is_processing = False
        self.status_bar.mode = "chat"
        self.chat_history.add_message("system", "[Interrupted]")


class OpenCLIApp(App):
    CSS = """
    Screen {
        background: $surface;
    }
    
    #main {
        height: 1fr;
    }
    
    #chat_panel {
        height: 1fr;
        border: solid $primary;
    }
    
    #tool_panel {
        height: 8;
        dock: bottom;
    }
    
    #input_area {
        height: 3;
        dock: bottom;
    }
    
    Header {
        background: $primary;
    }
    
    Footer {
        background: $surface-darken-1;
    }
    """
    
    SCREENS = {
        "main": MainScreen,
    }
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = Config.load()
    
    def on_mount(self):
        self.push_screen("main")
    
    def get_css_variables(self):
        return {
            "primary": "#0066cc",
            "accent": "#ff6600",
            "surface": "#1a1a2e",
            "text": "#ffffff",
        }


def main():
    app = OpenCLIApp()
    app.run()


if __name__ == "__main__":
    main()
