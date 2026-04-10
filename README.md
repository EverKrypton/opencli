# ORINNE

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
curl -sSL https://raw.githubusercontent.com/EverKrypton/orinne/main/install-termux.sh | bash
```

### Linux / macOS
```bash
pip3 install git+https://github.com/EverKrypton/orinne.git
```

## Usage

```bash
orinne
```

### Quick Start

1. Run `orinne`
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
export ORINNE_API_KEY="your-api-key"
export ORINNE_BASE_URL="https://api.openai.com/v1"
```

### Config File
`~/.orinne/config.json`

## Requirements

- Python 3.9+
- Terminal with UTF-8 support

## License

MIT
