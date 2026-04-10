# OPENCLI

AI-powered CLI editor with full-screen TUI for Termux.

## Features

- Full-screen TUI interface built with Textual
- Built-in code editor with syntax highlighting
- AI integration (OpenAI-compatible APIs)
- Designed for Termux on Android
- Keyboard-driven workflow

## Installation

### Termux (Android)

```bash
pkg update
pkg install python git

git clone https://github.com/yourname/opencli.git
cd opencli
pip install -e .
```

### Linux/macOS

```bash
pip install opencli
```

## Configuration

Create a config file at `~/.opencli/config.json`:

```json
{
  "ai": {
    "api_key": "your-api-key-here",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o",
    "max_tokens": 4096,
    "temperature": 0.7
  },
  "editor": {
    "tab_size": 4,
    "show_line_numbers": true,
    "auto_indent": true,
    "theme": "monokai"
  }
}
```

Or use environment variables:

```bash
export OPENCLI_API_KEY="your-api-key"
export OPENCLI_BASE_URL="https://api.openai.com/v1"
```

## Usage

```bash
opencli
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+N | New file |
| Ctrl+O | Open file |
| Ctrl+S | Save file |
| Ctrl+Q | Quit |
| Ctrl+E | Toggle editor panel |
| Ctrl+A | Toggle AI chat panel |
| Ctrl+F | Search |
| Ctrl+G | Go to line |
| F1 | Help |
| F10/Ctrl+C | Quit |

## Editor Features

- Line numbers
- Auto-indent
- Syntax highlighting
- Multi-buffer support
- Search and replace

## AI Features

- Chat with AI assistant
- Code suggestions
- Code explanation
- Bug fixing assistance

## Requirements

- Python 3.9+
- Works best in terminals with true color support

## License

MIT
