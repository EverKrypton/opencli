# ORINNE Project

AI-powered CLI agent with full-screen TUI for Termux and Linux.

## Build & Run Commands

```bash
# Install
pip install -e .

# Run
orinne

# Run from source
PYTHONPATH=src python3 -m orinne
```

## Project Structure

```
src/orinne/
├── __main__.py    # Entry point
├── tui/app.py     # Main TUI application
├── ai/client.py   # AI client with tools
├── tools/         # Tool implementations
├── providers/     # Multi-provider support
├── session/       # Session management
├── editor/        # Code editor
└── utils/         # Config & permissions
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
