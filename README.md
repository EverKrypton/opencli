# OPENCLI

AI-powered CLI editor with full-screen TUI. Works on Termux (Android) and any Linux/macOS terminal.

## Features

- **Full-screen TUI** - Modern interface built with Textual
- **Built-in Editor** - Code editing with syntax highlighting
- **AI Integration** - Chat with AI, get code suggestions
- **Termux Optimized** - Pure Python, no native compilation
- **Keyboard-driven** - Efficient workflow without mouse

## Quick Install

### Termux (Android)

```bash
pkg install python git
curl -sSL https://raw.githubusercontent.com/EverKrypton/opencli/main/install-termux.sh | bash
```

### Linux / macOS

```bash
pip3 install git+https://github.com/EverKrypton/opencli.git
```

### From Source

```bash
git clone https://github.com/EverKrypton/opencli.git
cd opencli
pip install -e .
```

## Configuration

Set your AI API key:

```bash
export OPENCLI_API_KEY="your-api-key"
```

Or create `~/.opencli/config.json`:

```json
{
  "ai": {
    "api_key": "your-api-key",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o"
  },
  "editor": {
    "tab_size": 4,
    "show_line_numbers": true,
    "auto_indent": true
  }
}
```

### Supported AI Providers

| Provider | base_url |
|----------|----------|
| OpenAI | `https://api.openai.com/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |
| Groq | `https://api.groq.com/openai/v1` |
| Together | `https://api.together.xyz/v1` |
| Local (Ollama) | `http://localhost:11434/v1` |

## Usage

```bash
opencli
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+N` | New file |
| `Ctrl+O` | Open file |
| `Ctrl+S` | Save file |
| `Ctrl+E` | Toggle editor |
| `Ctrl+A` | Toggle AI chat |
| `Ctrl+F` | Search |
| `Ctrl+G` | Go to line |
| `Ctrl+Q` | Quit |
| `F1` | Help |

## Requirements

- Python 3.9+
- Terminal with UTF-8 support

## Project Structure

```
opencli/
├── src/opencli/
│   ├── tui/          # TUI components (Textual)
│   ├── editor/       # Code editor
│   ├── ai/           # AI client
│   └── utils/        # Config utilities
├── install-termux.sh # Termux installer
└── pyproject.toml
```

## License

MIT
