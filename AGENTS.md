# OPENCLI Project

AI-powered CLI agent with full-screen TUI for Termux and Linux.

## Build & Run Commands

```bash
# Install
pip install -e .

# Run
opencli

# Run from source
PYTHONPATH=src python3 -m opencli
```

## Project Structure

```
src/opencli/
├── __main__.py    # Entry point
├── tui/           # Textual TUI components
│   └── app.py     # Main application
├── ai/            # AI client with tools
│   └── client.py  # OpenAI-compatible client
├── tools/         # Tool implementations
│   └── __init__.py
├── providers/     # Multi-provider support
│   └── __init__.py
├── session/       # Session management
│   └── __init__.py
├── editor/        # Code editor
│   └── editor.py
└── utils/         # Config and permissions
    ├── config.py
    └── permissions.py
```

## Code Style

- Python 3.9+
- Type hints where helpful
- Async/await for I/O
- No external native dependencies for Termux compatibility

## Features

- Tools: bash, read, write, edit, glob, grep, webfetch
- Multi-provider: OpenAI, Anthropic, Google, Groq, OpenRouter, Ollama
- Streaming responses
- Permission system
- Session persistence
- Cost estimation
