"""Main TUI application for OPENCLI."""

from typing import Optional, List
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header,
    Footer,
    Static,
    TextArea,
    Button,
    Input,
    Label,
)
from textual.widget import Widget
from textual.screen import Screen
from textual.reactive import reactive
from textual.binding import Binding
from textual.message import Message
from rich.syntax import Syntax
from rich.text import Text

from opencli.utils.config import Config
from opencli.editor.editor import Editor, Buffer
from opencli.ai.client import AIClient


class EditorWidget(Widget):
    DEFAULT_CSS = """
    EditorWidget {
        height: 1fr;
        background: $surface;
        border: solid $primary;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+f", "search", "Search"),
        Binding("ctrl+g", "goto", "Go to line"),
    ]

    def __init__(self, buffer: Optional[Buffer] = None, **kwargs):
        super().__init__(**kwargs)
        self.buffer = buffer or Buffer()
        self.cursor_line = 0
        self.cursor_col = 0
        self.scroll_offset = 0

    def on_mount(self) -> None:
        self.set_interval(0.1, self._update_cursor)

    def _update_cursor(self) -> None:
        pass

    def render(self) -> Text:
        lines = []
        visible_height = self.size.height - 2 if self.size.height > 2 else 10
        
        for i in range(self.scroll_offset, min(self.scroll_offset + visible_height, self.buffer.line_count)):
            line_num = f"{i + 1:4d} │ "
            line_content = self.buffer.get_line(i)
            
            if i == self.cursor_line:
                text = Text(line_num, style="bold cyan")
                text.append(line_content)
                lines.append(text)
            else:
                text = Text(line_num, style="dim")
                text.append(line_content)
                lines.append(text)
        
        return Text("\n").join(lines)

    def action_save(self) -> None:
        if self.buffer.filename:
            self.buffer.save()
            self.app.notify("File saved!")
        else:
            self.app.push_screen("save_as")

    def action_search(self) -> None:
        self.app.push_screen("search")

    def action_goto(self) -> None:
        self.app.push_screen("goto")

    def on_key(self, event) -> None:
        key = event.key
        buf = self.buffer

        if key == "up":
            if self.cursor_line > 0:
                self.cursor_line -= 1
                if self.cursor_line < self.scroll_offset:
                    self.scroll_offset = self.cursor_line
        elif key == "down":
            if self.cursor_line < buf.line_count - 1:
                self.cursor_line += 1
                if self.cursor_line >= self.scroll_offset + self.size.height - 2:
                    self.scroll_offset = self.cursor_line - self.size.height + 3
        elif key == "left":
            if self.cursor_col > 0:
                self.cursor_col -= 1
            elif self.cursor_line > 0:
                self.cursor_line -= 1
                self.cursor_col = len(buf.get_line(self.cursor_line))
        elif key == "right":
            current_line = buf.get_line(self.cursor_line)
            if self.cursor_col < len(current_line):
                self.cursor_col += 1
            elif self.cursor_line < buf.line_count - 1:
                self.cursor_line += 1
                self.cursor_col = 0
        elif key == "home":
            self.cursor_col = 0
        elif key == "end":
            self.cursor_col = len(buf.get_line(self.cursor_line))
        elif key == "enter":
            buf.insert_line(self.cursor_line + 1, "")
            self.cursor_line += 1
            self.cursor_col = 0
        elif key == "backspace":
            if self.cursor_col > 0:
                buf.delete_char(self.cursor_line, self.cursor_col)
                self.cursor_col -= 1
            elif self.cursor_line > 0:
                self.cursor_line -= 1
                self.cursor_col = len(buf.get_line(self.cursor_line))
                buf.delete_char(self.cursor_line, len(buf.get_line(self.cursor_line)))
        elif key == "delete":
            buf.delete_char(self.cursor_line, self.cursor_col + 1)
        elif key == "tab":
            for _ in range(4):
                buf.insert_char(" ", self.cursor_line, self.cursor_col)
                self.cursor_col += 1
        elif len(key) == 1:
            buf.insert_char(key, self.cursor_line, self.cursor_col)
            self.cursor_col += 1
        
        self.refresh()


class AIChatWidget(Widget):
    DEFAULT_CSS = """
    AIChatWidget {
        height: 1fr;
        background: $panel;
        border: solid $accent;
    }
    """

    def __init__(self, ai_client: Optional[AIClient] = None, **kwargs):
        super().__init__(**kwargs)
        self.ai_client = ai_client
        self.messages: List[tuple] = []

    def render(self) -> Text:
        if not self.messages:
            return Text("AI Chat - Type a message and press Enter", style="dim italic")
        
        lines = []
        for role, content in self.messages[-20:]:
            style = "bold green" if role == "user" else "bold blue"
            header = Text(f"\n[{role.upper()}]\n", style=style)
            lines.append(header)
            lines.append(Text(content))
        
        return Text("").join(lines)

    def add_message(self, role: str, content: str) -> None:
        self.messages.append((role, content))
        self.refresh()


class StatusBar(Widget):
    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $primary;
        color: $text;
    }
    """

    filename = reactive("")
    line = reactive(1)
    col = reactive(1)
    modified = reactive(False)

    def render(self) -> Text:
        status = f" {self.filename or '[New File]'}"
        if self.modified:
            status += " [+]"
        status += f" | Ln {self.line}, Col {self.col} | OPENCLI"
        return Text(status, style="bold white on blue")


class ChatInput(Widget):
    DEFAULT_CSS = """
    ChatInput {
        dock: bottom;
        height: 3;
        padding: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Message AI (Enter to send)...", id="chat_input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.value.strip():
            self.app.handle_ai_chat(event.value)
            event.input.value = ""


class MainScreen(Screen):
    BINDINGS = [
        Binding("ctrl+n", "new_file", "New"),
        Binding("ctrl+o", "open_file", "Open"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+e", "toggle_editor", "Editor"),
        Binding("ctrl+a", "toggle_ai", "AI Chat"),
        Binding("f1", "help", "Help"),
    ]

    def __init__(self, config: Config, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.editor = Editor(
            tab_size=config.editor.tab_size,
            auto_indent=config.editor.auto_indent,
        )
        self.ai_client: Optional[AIClient] = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main"):
            with Horizontal(id="content"):
                with Vertical(id="editor_panel"):
                    yield EditorWidget(self.editor.new_buffer(), id="editor_widget")
                with Vertical(id="ai_panel"):
                    yield AIChatWidget(id="ai_chat")
                    yield ChatInput()
        yield StatusBar()

    def on_mount(self) -> None:
        self.editor_widget = self.query_one("#editor_widget", EditorWidget)
        self.ai_chat = self.query_one("#ai_chat", AIChatWidget)
        self.status_bar = self.query_one(StatusBar)
        
        if self.config.ai.api_key:
            self.ai_client = AIClient(
                api_key=self.config.ai.api_key,
                base_url=self.config.ai.base_url,
                model=self.config.ai.model,
                max_tokens=self.config.ai.max_tokens,
                temperature=self.config.ai.temperature,
            )

    def action_new_file(self) -> None:
        self.editor.new_buffer()
        self.editor_widget.buffer = self.editor.active_buffer
        self.editor_widget.refresh()

    def action_open_file(self) -> None:
        self.app.push_screen("file_open")

    def action_toggle_editor(self) -> None:
        editor_panel = self.query_one("#editor_panel")
        editor_panel.toggle_class("hidden")

    def action_toggle_ai(self) -> None:
        ai_panel = self.query_one("#ai_panel")
        ai_panel.toggle_class("hidden")

    def action_help(self) -> None:
        self.app.push_screen("help")


class OpenCLIApp(App):
    CSS = """
    Screen {
        background: $surface;
    }
    
    #main {
        height: 100%;
    }
    
    #content {
        height: 1fr;
    }
    
    #editor_panel {
        width: 1fr;
        height: 1fr;
    }
    
    #ai_panel {
        width: 1fr;
        height: 1fr;
    }
    
    .hidden {
        display: none;
    }
    
    Header {
        background: $primary;
        color: $text;
    }
    
    Footer {
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("f10", "quit", "Quit"),
    ]

    SCREENS = {
        "main": MainScreen,
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = Config.load()

    def on_mount(self) -> None:
        self.push_screen("main")

    def handle_ai_chat(self, message: str) -> None:
        screen = self.screen
        if isinstance(screen, MainScreen):
            ai_chat = screen.query_one("#ai_chat", AIChatWidget)
            ai_chat.add_message("user", message)
            
            if screen.ai_client:
                self._send_ai_message(message, screen)
            else:
                ai_chat.add_message("assistant", "Please configure your API key in ~/.opencli/config.json")

    async def _send_ai_message(self, message: str, screen: MainScreen) -> None:
        ai_chat = screen.query_one("#ai_chat", AIChatWidget)
        
        try:
            async with screen.ai_client as client:
                response = await client.chat(message)
                ai_chat.add_message("assistant", response.content)
        except Exception as e:
            ai_chat.add_message("assistant", f"Error: {str(e)}")


def main():
    app = OpenCLIApp()
    app.run()


if __name__ == "__main__":
    main()
