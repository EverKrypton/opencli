"""Main TUI application for OPENCLI."""

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
                output.append("\n", style="")
                output.append("  You\n", style="bold #22c55e")
                output.append("  ", style="dim")
                output.append(f"{content}\n", style="white")
                output.append("\n")
            elif role == "assistant":
                output.append("\n", style="")
                output.append("  AI\n", style="bold #06b6d4")
                output.append("  ", style="dim")
                output.append(f"{content}\n", style="white")
                output.append("\n")
            elif role == "system":
                output.append(f"{content}\n", style="#64748b")
            elif role == "tool":
                output.append(f"\n  └─ {content[:200]}\n", style="#eab308")
        
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
        background: $surface;
        border-top: solid $border;
        padding: 0 2;
    }
    
    InputBox Input {
        background: $surface-darken-1;
        border: none;
        padding: 0 1;
    }
    
    InputBox Input:focus {
        border: none;
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
        width: 70;
        height: 25;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }
    
    ModelSelectDialog .title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    
    ModelSelectDialog .model-item {
        padding: 0 1;
    }
    
    ModelSelectDialog .selected {
        background: $primary;
        color: white;
    }
    """
    
    BINDINGS = [
        Binding("up", "up", "Up"),
        Binding("down", "down", "Down"),
        Binding("enter", "select", "Select"),
        Binding("escape", "cancel", "Cancel"),
    ]
    
    def __init__(self, models: List[str], current: str = "", **kwargs):
        super().__init__(**kwargs)
        self.models = models
        self.current = current
        self.result: Optional[str] = None
        self.selected_index = 0
        
        if current in models:
            self.selected_index = models.index(current)
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Select Model", classes="title")
            yield Static("")
            yield Static("  Use ↑↓ to navigate, Enter to select", classes="hint")
            yield Static("")
            yield Static(self._render_models(), id="model_list")
            yield Static("")
            yield Static("  Or type to search:", classes="hint")
            yield Input(placeholder="Type model name...", id="model_input")
    
    def _render_models(self) -> str:
        lines = []
        start = max(0, self.selected_index - 5)
        end = min(len(self.models), start + 12)
        
        for i in range(start, end):
            model = self.models[i]
            if i == self.selected_index:
                lines.append(f"  ▸ {model}")
            else:
                lines.append(f"    {model}")
        
        return "\n".join(lines)
    
    def on_mount(self):
        self.query_one(Input).focus()
    
    def action_up(self):
        if self.selected_index > 0:
            self.selected_index -= 1
            self._update_list()
    
    def action_down(self):
        if self.selected_index < len(self.models) - 1:
            self.selected_index += 1
            self._update_list()
    
    def action_select(self):
        self.result = self.models[self.selected_index]
        self.dismiss(self.result)
    
    def _update_list(self):
        model_list = self.query_one("#model_list", Static)
        model_list.update(self._render_models())
    
    def on_input_submitted(self, event: Input.Submitted):
        text = event.value.strip()
        if text:
            for i, m in enumerate(self.models):
                if text.lower() in m.lower():
                    self.result = m
                    self.dismiss(m)
                    return
            self.result = text
            self.dismiss(text)
    
    def action_cancel(self):
        self.dismiss(None)


class StatusBar(Widget):
    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 2;
    }
    """
    
    provider = reactive("not configured")
    model = reactive("")
    cost = reactive(0.0)
    mode = reactive("READY")
    logged_in = reactive(False)
    
    def render(self) -> Text:
        text = Text()
        
        if self.logged_in:
            text.append(" ○ ", style="#22c55e")
            text.append(f"{self.provider}", style="bold #6366f1")
            text.append(" · ", style="#4b5563")
            text.append(self.model, style="#9ca3af")
        else:
            text.append(" ○ ", style="#6b7280")
            text.append("/login to start", style="#6b7280")
        
        text.append("  ", style="")
        
        if self.cost > 0:
            text.append(f"${self.cost:.4f}", style="#fbbf24")
        
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
        
        base_url = self.config.ai.base_url or os.environ.get("OPENCLI_BASE_URL")
        provider = os.environ.get("OPENCLI_PROVIDER", "")
        
        if not api_key and not provider:
            self.status.logged_in = False
            return
        
        if api_key == "ollama" or provider == "ollama":
            provider = "ollama"
        elif api_key:
            provider = provider or detect_provider(api_key)
        else:
            self.status.logged_in = False
            return
        
        self.permission_manager.set_ask_callback(self._ask_permission)
        
        self.tools = ToolsRegistry(
            workdir=os.getcwd(),
            permission_handler=self._check_permission
        )
        
        self.ai_client = AIClient(
            api_key=api_key if api_key != "ollama" else "ollama",
            provider=provider,
            model=self.config.ai.model,
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
        
        self.status.provider = provider
        self.status.model = self.ai_client.model
        self.status.logged_in = True
    
    def _show_banner(self):
        logged_icon = "●" if self.status.logged_in else "○"
        provider = getattr(self, 'ai_client', None) and self.ai_client.provider_name or ""
        model = getattr(self, 'ai_client', None) and self.ai_client.model or ""
        logged_text = f"{provider} · {model}" if self.status.logged_in else "/login to start"
        
        banner = f"""


  ╔══════════════════════════════════════════════════════════════════════════════════╗
  ║                                                                                  ║
  ║                                                                                  ║
  ║    ██████╗ ██████╗ ██████╗ ███████╗      ██╗      ██╗███╗   ██╗ ██████╗           ║
  ║   ██╔═══██╗██╔══██╗██╔══██╗██╔════╝      ██║      ██║████╗  ██║██╔════╝           ║
  ║   ██║   ██║██████╔╝██████╔╝█████╗        ██║      ██║██╔██╗ ██║██║  ███╗          ║
  ║   ██║   ██║██╔═══╝ ██╔═══╝ ██╔══╝        ██║      ██║██║╚██╗██║██║   ██║          ║
  ║   ╚██████╔╝██║     ██║     ███████╗      ███████╗ ██║██║ ╚████║╚██████╔╝          ║
  ║    ╚═════╝ ╚═╝     ╚═╝     ╚══════╝      ╚══════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝           ║
  ║                                                                                  ║
  ║                          AI-powered CLI agent                                    ║
  ║                                                                                  ║
  ╚══════════════════════════════════════════════════════════════════════════════════╝

   {logged_icon} {logged_text}

   ──────────────────────────────────────────────────────────────────────────────────

    /login [key]     Configure API key
    /models          List models  ·  /model <name>  Switch model
    /clear           Clear chat   ·  /new           New session
    /help            Show all commands
    /exit            Quit

"""
        self.chat.add("system", banner)
    
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
        elif cmd == "/ollama":
            await self._cmd_ollama(args)
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
    
    async def _cmd_ollama(self, args: List[str]):
        """Connect to Ollama (local models, no API key needed)."""
        import httpx
        
        ollama_url = args[0] if args else "http://localhost:11434"
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{ollama_url}/api/tags", timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["name"] for m in data.get("models", [])]
                    
                    if not models:
                        self.chat.add("system", "Ollama is running but no models found.\n\nInstall a model with:\n  ollama pull llama3.2")
                        return
                    
                    self.config.ai.api_key = "ollama"
                    self.config.ai.base_url = f"{ollama_url}/v1"
                    self.config.ai.model = models[0]
                    self.config.save()
                    
                    await self._setup_client()
                    self.status.provider = "ollama"
                    self.status.logged_in = True
                    
                    model_list = "\n".join(f"  • {m}" for m in models)
                    self.chat.add("system", f"""✓ Connected to Ollama!

  URL: {ollama_url}
  
  Available models:
{model_list}

  Use /model to switch models.
""")
                else:
                    self.chat.add("system", f"Could not connect to Ollama at {ollama_url}\n\nMake sure Ollama is running:\n  ollama serve")
        except Exception as e:
            self.chat.add("system", f"Could not connect to Ollama at {ollama_url}\n\nError: {str(e)}\n\nMake sure Ollama is running:\n  ollama serve")
    
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
        except Exception as e:
            models = self.ai_client.provider_config.models
        
        model_list = "\n".join(f"  • {m}" for m in models[:25])
        current = f"\n\n  Current: {self.ai_client.model}" if self.ai_client else ""
        self.chat.add("system", f"Available models:\n{model_list}{current}\n\nUse /model to select or press Enter for dropdown.")
    
    async def _cmd_set_model(self, args: List[str]):
        if not self.ai_client:
            self.chat.add("system", "Please login first: /login")
            return
        
        try:
            models = await fetch_models(self.ai_client.provider_name, self.ai_client.api_key)
        except:
            models = self.ai_client.provider_config.models
        
        if args:
            model = args[0]
        else:
            model = await self.app.push_screen_wait(
                ModelSelectDialog(
                    models,
                    self.ai_client.model
                )
            )
        
        if model:
            self.ai_client.set_model(model)
            self.config.ai.model = model
            self.config.save()
            self.status.model = model
            self.chat.add("system", f"✓ Model changed to: {model}")
    
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
  /ollama [url]    Connect to Ollama (local models, no key needed)
  /logout          Clear saved credentials
  /models          List available models
  /model           Select model (dropdown)
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
  • Ollama         (local, use /ollama to connect)
        """)
    
    async def _send_message(self, message: str):
        if not self.ai_client:
            self.chat.add("system", "Please login first: /login or /ollama")
            return
        
        if not self.ai_client.api_key and self.ai_client.provider_name != "ollama":
            self.chat.add("system", "Please login first: /login or /ollama")
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
        background: $surface;
        color: $primary;
        text-style: bold;
    }
    
    Footer {
        background: $surface;
        color: $text;
    }
    
    .title {
        text-align: center;
        text-style: bold;
        color: $primary;
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
            "primary": "#6366f1",
            "accent": "#f97316",
            "surface": "#0c0c0c",
            "surface-darken-1": "#1a1a1a",
            "border": "#333333",
            "text": "#e5e5e5",
        }


def main():
    app = OpenCLIApp()
    app.run()


if __name__ == "__main__":
    main()
