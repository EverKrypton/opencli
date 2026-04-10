"""Main TUI application for OPENCLI - Inspired by opencode."""

import os
import asyncio
from typing import Optional, Dict, List, Any
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Input
from textual.widget import Widget
from textual.screen import Screen, ModalScreen
from textual.reactive import reactive
from textual.binding import Binding
from rich.text import Text
from rich.console import Console
from rich.panel import Panel

from opencli.utils.config import Config
from opencli.utils.permissions import PermissionManager, is_dangerous_command, is_sensitive_path
from opencli.tools import ToolsRegistry
from opencli.providers import detect_provider, get_provider_config, fetch_models, PROVIDERS
from opencli.session import SessionManager
from opencli.ai.client import AIClient


console = Console()


class ChatMessage(Widget):
    DEFAULT_CSS = """
    ChatMessage {
        margin: 0 1;
        padding: 0;
    }
    """
    
    content = reactive("")
    role = reactive("user")
    
    def __init__(self, content: str = "", role: str = "user", **kwargs):
        super().__init__(**kwargs)
        self.content = content
        self.role = role
    
    def render(self) -> Text:
        if self.role == "user":
            return Text(f"\n[You]\n{self.content}", style="bold green")
        elif self.role == "assistant":
            return Text(f"\n[AI]\n{self.content}", style="cyan")
        elif self.role == "system":
            return Text(f"\n{self.content}", style="dim yellow")
        elif self.role == "tool":
            return Text(f"\n[Tool]\n{self.content[:500]}", style="yellow")
        return Text(self.content)


class ChatArea(Widget):
    DEFAULT_CSS = """
    ChatArea {
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }
    """
    
    messages = reactive([])
    
    def render(self) -> Text:
        if not self.messages:
            return Text("")
        
        output = Text()
        for msg in self.messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            if role == "user":
                output.append("\n● You\n", style="bold green")
                output.append(f"{content}\n")
            elif role == "assistant":
                output.append("\n● AI\n", style="bold cyan")
                output.append(f"{content}\n")
            elif role == "system":
                output.append(f"\n{content}\n", style="dim")
            elif role == "tool":
                output.append(f"\n  └─ {content[:200]}\n", style="dim yellow")
        
        return output
    
    def add(self, role: str, content: str):
        self.messages = [*self.messages, {"role": role, "content": content}]
    
    def update_last(self, content: str):
        if self.messages:
            self.messages[-1]["content"] = content
    
    def clear(self):
        self.messages = []


class InputBox(Widget):
    DEFAULT_CSS = """
    InputBox {
        dock: bottom;
        height: 3;
        background: $surface-darken-1;
        border-top: solid $primary;
        padding: 0 1;
    }
    
    InputBox Input {
        background: $surface;
    }
    """
    
    def __init__(self, placeholder: str = ">", **kwargs):
        super().__init__(**kwargs)
        self._placeholder = placeholder
    
    def compose(self) -> ComposeResult:
        yield Input(placeholder=self._placeholder, id="main_input")
    
    def focus_input(self):
        self.query_one(Input).focus()


class LoginDialog(ModalScreen):
    DEFAULT_CSS = """
    LoginDialog {
        align: center middle;
    }
    
    LoginDialog > Container {
        width: 70;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    
    LoginDialog .title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    
    LoginDialog .hint {
        color: dim;
        margin-top: 1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.result: Optional[str] = None
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Static("🔐 Login to OPENCLI", classes="title")
            yield Static("")
            yield Static("Paste your API key below.")
            yield Static("Provider will be auto-detected:")
            yield Static("")
            yield Static("  sk-...     → OpenAI", classes="hint")
            yield Static("  sk-or-...  → OpenRouter", classes="hint")
            yield Static("  sk-ant-... → Anthropic", classes="hint")
            yield Static("  gsk_...    → Groq", classes="hint")
            yield Static("  AIza...    → Google", classes="hint")
            yield Static("")
            yield Input(placeholder="Paste API key and press Enter", id="api_key_input", password=True)
    
    def on_mount(self):
        self.query_one(Input).focus()
    
    def on_input_submitted(self, event: Input.Submitted):
        if event.value.strip():
            self.result = event.value.strip()
            self.dismiss(self.result)
    
    def action_cancel(self):
        self.dismiss(None)


class ModelSelectDialog(ModalScreen):
    DEFAULT_CSS = """
    ModelSelectDialog {
        align: center middle;
    }
    
    ModelSelectDialog > Container {
        width: 60;
        height: 20;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]
    
    def __init__(self, models: List[str], current: str = "", **kwargs):
        super().__init__(**kwargs)
        self.models = models
        self.current = current
        self.result: Optional[str] = None
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Select Model", classes="title")
            for model in self.models[:15]:
                marker = "→ " if model == self.current else "  "
                yield Static(f"{marker}{model}")
            yield Static("")
            yield Input(placeholder="Type model name and press Enter", id="model_input")
    
    def on_mount(self):
        self.query_one(Input).focus()
    
    def on_input_submitted(self, event: Input.Submitted):
        if event.value.strip():
            self.result = event.value.strip()
            self.dismiss(self.result)
    
    def action_cancel(self):
        self.dismiss(None)


class StatusBar(Widget):
    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $primary;
        color: white;
        padding: 0 1;
    }
    """
    
    provider = reactive("not configured")
    model = reactive("")
    cost = reactive(0.0)
    mode = reactive("READY")
    logged_in = reactive(False)
    
    def render(self) -> Text:
        if self.logged_in:
            left = f" {self.provider} | {self.model}"
        else:
            left = " not configured | /login to start"
        
        right = f"${self.cost:.4f} "
        
        text = Text()
        text.append(left, style="bold white")
        text.append(" " * max(1, 60 - len(left) - len(right)))
        text.append(right, style="white")
        return text


class MainScreen(Screen):
    BINDINGS = [
        Binding("ctrl+l", "clear", "Clear"),
        Binding("ctrl+n", "new_session", "New"),
        Binding("ctrl+q", "quit", "Quit"),
    ]
    
    def __init__(self, config: Config, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.permission_manager = PermissionManager()
        self.tools: Optional[ToolsRegistry] = None
        self.ai_client: Optional[AIClient] = None
        self.session_manager = SessionManager()
        self._is_processing = False
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(id="main"):
            yield ChatArea(id="chat")
        yield StatusBar(id="status")
        yield InputBox(placeholder="> Type a message or /help for commands", id="input_box")
        yield Footer()
    
    async def on_mount(self) -> None:
        self.chat = self.query_one("#chat", ChatArea)
        self.status = self.query_one("#status", StatusBar)
        self.input_box = self.query_one("#input_box", InputBox)
        
        await self._setup_client()
        self._show_banner()
        
        self.input_box.focus_input()
    
    async def _setup_client(self):
        api_key = (
            self.config.ai.api_key or
            os.environ.get("OPENCLI_API_KEY") or
            os.environ.get("OPENAI_API_KEY")
        )
        
        if not api_key:
            self.status.logged_in = False
            return
        
        provider = detect_provider(api_key)
        
        self.permission_manager.set_ask_callback(self._ask_permission)
        
        self.tools = ToolsRegistry(
            workdir=os.getcwd(),
            permission_handler=self._check_permission
        )
        
        self.ai_client = AIClient(
            api_key=api_key,
            provider=provider,
            model=self.config.ai.model,
            base_url=self.config.ai.base_url,
            tools=self.tools,
            session_manager=self.session_manager,
            permission_handler=self._check_permission,
        )
        
        self.ai_client.set_callbacks(
            on_stream_chunk=self._on_stream_chunk,
            on_tool_call=self._on_tool_call,
            on_cost_update=self._on_cost_update,
        )
        
        self.status.provider = provider
        self.status.model = self.ai_client.model
        self.status.logged_in = True
    
    def _show_banner(self):
        logged = "✓ logged in" if self.status.logged_in else "✗ /login to start"
        
        self.chat.add("system", f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║    ██████╗ ██████╗ ██╗███╗   ██╗███╗   ██╗███████╗██████╗   ║
║   ██╔═══██╗██╔══██╗██║████╗  ██║████╗  ██║██╔════╝██╔══██╗  ║
║   ██║   ██║██████╔╝██║██╔██╗ ██║██╔██╗ ██║█████╗  ██████╔╝  ║
║   ██║   ██║██╔══██╗██║██║╚██╗██║██║╚██╗██║██╔══╝  ██╔══██╗  ║
║   ╚██████╔╝██║  ██║██║██║ ╚████║██║ ╚████║███████╗██║  ██║  ║
║    ╚═════╝ ╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝  ║
║                                                              ║
║            AI-powered CLI agent for Terminal                 ║
╚══════════════════════════════════════════════════════════════╝

  Status: {logged}
  
  Commands:
    /login [key]    Configure API key
    /logout         Clear saved key
    /models         List available models  
    /model <name>   Switch model
    /clear          Clear conversation
    /new            New session
    /settings       Show settings
    /help           Show all commands
    /exit           Quit
        """)
    
    async def _ask_permission(self, action: str, resource: str) -> bool:
        return True
    
    async def _check_permission(self, action: str, resource: str) -> bool:
        return True
    
    async def _on_stream_chunk(self, chunk: str):
        self.chat.update_last(self.chat.messages[-1].get("content", "") + chunk)
        self.chat.refresh()
    
    async def _on_tool_call(self, tool_calls: List[Dict]):
        pass
    
    async def _on_cost_update(self, cost: float, usage: Dict):
        self.status.cost += cost
    
    async def on_input_submitted(self, event: Input.Submitted):
        text = event.value.strip()
        if not text:
            return
        
        event.input.value = ""
        
        if text.startswith("/"):
            await self._handle_command(text)
        else:
            await self._send_message(text)
    
    async def _handle_command(self, cmd_text: str):
        parts = cmd_text.split()
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if cmd in ("/login",):
            await self._cmd_login(args)
        elif cmd == "/logout":
            await self._cmd_logout()
        elif cmd in ("/models",):
            await self._cmd_models()
        elif cmd == "/model":
            await self._cmd_set_model(args)
        elif cmd in ("/clear",):
            self.chat.clear()
        elif cmd in ("/new",):
            self._cmd_new()
        elif cmd in ("/settings",):
            self._cmd_settings()
        elif cmd in ("/help", "/?"):
            self._cmd_help()
        elif cmd in ("/exit", "/quit", "/q"):
            self.app.exit()
        else:
            self.chat.add("system", f"Unknown command: {cmd}\nType /help for available commands.")
    
    async def _cmd_login(self, args: List[str]):
        if args:
            api_key = args[0]
        else:
            api_key = await self.app.push_screen_wait(LoginDialog())
        
        if not api_key:
            return
        
        provider = detect_provider(api_key)
        provider_config = get_provider_config(provider)
        
        self.config.ai.api_key = api_key
        self.config.save()
        
        await self._setup_client()
        
        self.chat.add("system", f"""
✓ Logged in successfully!

  Provider: {provider}
  Model: {self.ai_client.model}
  
  Ready to chat. Type your message or /help for commands.
        """)
    
    async def _cmd_logout(self):
        self.config.ai.api_key = ""
        self.config.save()
        self.status.logged_in = False
        self.status.provider = "not configured"
        self.status.model = ""
        self.ai_client = None
        self.chat.add("system", "Logged out. Use /login to authenticate again.")
    
    async def _cmd_models(self):
        if not self.ai_client:
            self.chat.add("system", "Please login first: /login")
            return
        
        self.chat.add("system", "Fetching models...")
        
        try:
            models = await fetch_models(self.ai_client.provider_name, self.ai_client.api_key)
        except:
            models = self.ai_client.provider_config.models
        
        model_list = "\n".join(f"  • {m}" for m in models[:20])
        self.chat.add("system", f"Available models:\n{model_list}\n\nUse /model <name> to switch.")
    
    async def _cmd_set_model(self, args: List[str]):
        if not self.ai_client:
            self.chat.add("system", "Please login first: /login")
            return
        
        if args:
            model = args[0]
        else:
            model = await self.app.push_screen_wait(
                ModelSelectDialog(
                    self.ai_client.provider_config.models,
                    self.ai_client.model
                )
            )
        
        if model:
            self.ai_client.set_model(model)
            self.config.ai.model = model
            self.config.save()
            self.status.model = model
            self.chat.add("system", f"Model changed to: {model}")
    
    def _cmd_new(self):
        if self.ai_client:
            self.ai_client.clear_session()
        self.chat.clear()
        self._show_banner()
        self.status.cost = 0.0
    
    def _cmd_settings(self):
        settings = f"""
Settings:
  Provider:    {self.ai_client.provider_name if self.ai_client else 'not configured'}
  Model:       {self.ai_client.model if self.ai_client else 'not configured'}
  Base URL:    {self.ai_client.base_url if self.ai_client else 'not configured'}
  
  Temperature: {self.config.ai.temperature}
  Max Tokens:  {self.config.ai.max_tokens}
  
Config file: ~/.opencli/config.json
        """
        self.chat.add("system", settings)
    
    def _cmd_help(self):
        self.chat.add("system", """
Commands:
  /login [key]     Login with API key (auto-detects provider)
  /logout          Clear saved credentials
  /models          List available models
  /model <name>    Switch to a different model
  /clear           Clear conversation history
  /new             Start a new session
  /settings        Show current settings
  /help            Show this help
  /exit            Quit OPENCLI

Keyboard Shortcuts:
  Ctrl+L           Clear screen
  Ctrl+N           New session
  Ctrl+Q           Quit

Supported Providers:
  • OpenAI         (sk-...)
  • OpenRouter     (sk-or-...)
  • Anthropic      (sk-ant-...)
  • Groq           (gsk_...)
  • Google         (AIza...)
  • Ollama         (local, no key needed)
        """)
    
    async def _send_message(self, message: str):
        if not self.ai_client or not self.ai_client.api_key:
            self.chat.add("system", "Please login first: /login")
            return
        
        self.chat.add("user", message)
        self.chat.add("assistant", "")
        
        self._is_processing = True
        
        try:
            async for _ in self.ai_client.chat(message, stream=True):
                if not self._is_processing:
                    break
                self.chat.refresh()
        except Exception as e:
            self.chat.add("system", f"Error: {str(e)}")
        finally:
            self._is_processing = False
    
    def action_clear(self):
        self.chat.clear()
    
    def action_new_session(self):
        self._cmd_new()


class OpenCLIApp(App):
    CSS = """
    Screen {
        background: $surface;
    }
    
    #main {
        height: 1fr;
    }
    
    Header {
        background: $primary;
        color: white;
    }
    
    Footer {
        background: $surface-darken-1;
    }
    """
    
    SCREENS = {"main": MainScreen}
    BINDINGS = [Binding("ctrl+q", "quit", "Quit")]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = Config.load()
    
    def on_mount(self):
        self.push_screen("main")
    
    def get_css_variables(self):
        return {
            "primary": "#2563eb",
            "accent": "#f97316",
            "surface": "#0f172a",
            "text": "#f8fafc",
        }


def main():
    app = OpenCLIApp()
    app.run()


if __name__ == "__main__":
    main()
