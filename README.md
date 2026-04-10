# OPENCLI

AI-powered CLI agent with full-screen TUI for Termux and Linux.

## Features

- **Tools** - bash, read, write, edit, glob, grep, webfetch
- **Multi-Provider** - OpenAI, Anthropic, Google, Groq, OpenRouter, Ollama
- **Auto-detect** - Detects provider from API key format
- **Streaming** - Real-time responses
- **Permissions** - Ask before destructive operations
- **Sessions** - Persistent conversation history
- **Cost tracking** - Track API usage costs

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

```bash
opencli
```

### Quick Start

1. Run `opencli`
2. Type `/login` and paste your API key (provider is auto-detected)
3. Start chatting!

### Commands

| Command | Description |
|---------|-------------|
| `/login [key]` | Login with API key |
| `/logout` | Clear saved credentials |
| `/models` | List available models |
| `/model <name>` | Switch model |
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
| Ollama | (local, no key) |

## Configuration

### Environment Variables
```bash
export OPENCLI_API_KEY="your-api-key"
export OPENCLI_BASE_URL="https://api.openai.com/v1"
```

### Config File
`~/.opencli/config.json`

## Requirements

- Python 3.9+
- Terminal with UTF-8 support

## License

MIT
