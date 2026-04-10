# OPENCLI

AI-powered CLI agent with full-screen TUI for Termux and Linux.

## Features

- **Tools** - bash, read, write, edit, glob, grep, webfetch
- **Multi-Provider** - OpenAI, Anthropic, Google, Groq, OpenRouter, Ollama
- **Auto-detect** - Detects provider from API key format
- **Streaming** - Real-time responses
- **Local models** - Ollama support (no API key needed)
- **Dropdown models** - Select models with arrow keys
- **CLI commands** - Configure from terminal without opening TUI

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

## Usage

### CLI Commands (from terminal)

```bash
# Set API key without opening TUI
opencli login sk-your-api-key

# Or export environment variable
export OPENCLI_API_KEY="sk-your-api-key"

# List available models
opencli models

# Show config
opencli config

# List providers
opencli providers

# Start TUI
opencli
```

### Environment Variables

```bash
export OPENCLI_API_KEY="your-api-key"
export OPENCLI_PROVIDER="openai"    # optional: openai, anthropic, ollama, etc.
export OPENCLI_MODEL="gpt-4o"       # optional
```

### Inside TUI

| Command | Description |
|---------|-------------|
| `/login [key]` | Login with API key |
| `/ollama [url]` | Connect to Ollama (local models) |
| `/models` | List available models from API |
| `/model` | Select model (dropdown with ↑↓) |
| `/clear` | Clear conversation |
| `/new` | New session |
| `/help` | Show all commands |
| `/exit` | Quit |

### Supported Providers

| Provider | API Key Format |
|----------|---------------|
| OpenAI | `sk-...` |
| OpenRouter | `sk-or-...` |
| Anthropic | `sk-ant-...` |
| Groq | `gsk_...` |
| Google | `AIza...` |
| Ollama | (local, use `/ollama`) |

### Using Ollama (Local Models)

1. Install: https://ollama.ai
2. Pull model: `ollama pull llama3.2`
3. Run OPENCLI and type `/ollama`

Or from terminal:
```bash
export OPENCLI_PROVIDER=ollama
opencli
```

## Config File

`~/.opencli/config.json`:
```json
{
  "ai": {
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o"
  }
}
```

## Requirements

- Python 3.9+
- Terminal with UTF-8 support

## License

MIT
