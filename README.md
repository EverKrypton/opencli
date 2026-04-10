# OPENCLI

AI-powered CLI agent with full-screen TUI for Termux and Linux.

Inspired by [opencode](https://github.com/opencode-ai/opencode).

## Features

### 🛠️ Tools
- **bash** - Execute terminal commands
- **read** - Read files with line numbers
- **write** - Create/overwrite files
- **edit** - Edit files by replacing text
- **glob** - Find files by pattern
- **grep** - Search file contents
- **webfetch** - Fetch URLs

### 🌐 Multi-Provider Support
| Provider | API Key Format |
|----------|---------------|
| OpenAI | `sk-...` |
| Anthropic | `sk-ant-...` |
| OpenRouter | `sk-or-...` |
| Groq | `gsk_...` |
| Google | `AIza...` |
| Ollama | (local, no key) |

Auto-detects provider from API key format.

### 📊 Additional Features
- **Streaming** - Real-time responses
- **Permissions** - Ask before destructive operations
- **Sessions** - Persistent conversation history
- **Cost estimation** - Track API usage costs
- **Slash commands** - `/login`, `/models`, `/settings`, etc.

## Installation

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

## Usage

```bash
opencli
```

### Quick Start

1. Run `opencli`
2. Type `/login` and paste your API key (provider is auto-detected)
3. Start chatting!

### Slash Commands

| Command | Description |
|---------|-------------|
| `/login [key]` | Login with API key (interactive or provide key) |
| `/logout` | Clear saved credentials |
| `/models` | List available models |
| `/model <name>` | Switch to a different model |
| `/settings` | View current configuration |
| `/clear` | Clear conversation |
| `/new` | Start new session |
| `/help` | Show all commands |
| `/exit` | Quit OPENCLI |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+N` | New session |
| `Ctrl+L` | Clear screen |
| `Ctrl+C` | Interrupt operation |
| `F1` | Help |
| `F2` | Settings |
| `F3` | Models |
| `F4` | Sessions |
| `Ctrl+Q` | Quit |

## Configuration

### Environment Variables
```bash
export OPENCLI_API_KEY="your-api-key"
export OPENCLI_BASE_URL="https://api.openai.com/v1"  # optional
```

### Config File
`~/.opencli/config.json`:
```json
{
  "ai": {
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o",
    "max_tokens": 4096,
    "temperature": 0.7
  },
  "editor": {
    "tab_size": 4,
    "show_line_numbers": true,
    "auto_indent": true
  }
}
```

### Supported Providers

| Provider | base_url |
|----------|----------|
| OpenAI | `https://api.openai.com/v1` |
| Anthropic | `https://api.anthropic.com/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |
| Groq | `https://api.groq.com/openai/v1` |
| Together | `https://api.together.xyz/v1` |
| Ollama | `http://localhost:11434/v1` |

## Project Structure

```
src/opencli/
├── __main__.py      # Entry point
├── tui/app.py       # Textual TUI
├── ai/client.py     # AI client with tools
├── tools/           # Tool implementations
├── providers/       # Multi-provider support
├── session/         # Session management
├── editor/          # Code editor
└── utils/           # Config & permissions
```

## Requirements

- Python 3.9+
- Terminal with UTF-8 support

## Comparison with opencode

| Feature | opencode | OPENCLI |
|---------|----------|---------|
| Tools | ✅ 12+ | ✅ 7 |
| Multi-provider | ✅ | ✅ |
| Streaming | ✅ | ✅ |
| Permissions | ✅ | ✅ |
| Sessions | ✅ | ✅ |
| Cost tracking | ✅ | ✅ |
| Termux support | ⚠️ | ✅ |
| Pure Python | ❌ (Node.js) | ✅ |

## License

MIT
