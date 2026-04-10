#!/bin/bash
# OPENCLI Installer for Termux

set -e

echo "╔══════════════════════════════════════╗"
echo "║     OPENCLI Installer for Termux     ║"
echo "╚══════════════════════════════════════╝"

# Check if running in Termux
if [ -z "$TERMUX_VERSION" ]; then
    echo "Warning: Not running in Termux. Some features may not work."
fi

# Update packages
echo "[1/5] Updating packages..."
pkg update -y

# Install Python if not present
echo "[2/5] Checking Python..."
if ! command -v python &> /dev/null; then
    echo "Installing Python..."
    pkg install python -y
fi

# Install build dependencies
echo "[3/5] Installing dependencies..."
pkg install python build-essential -y

# Upgrade pip
echo "[4/5] Upgrading pip..."
python -m pip install --upgrade pip

# Install OPENCLI
echo "[5/5] Installing OPENCLI..."
if [ -d "opencli" ]; then
    cd opencli
    pip install -e .
else
    pip install opencli
fi

# Create config directory
mkdir -p ~/.opencli

# Create default config if not exists
if [ ! -f ~/.opencli/config.json ]; then
    echo '{
  "ai": {
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o"
  },
  "editor": {
    "tab_size": 4,
    "show_line_numbers": true,
    "auto_indent": true
  }
}' > ~/.opencli/config.json
    echo "Created config file at ~/.opencli/config.json"
fi

echo ""
echo "✅ OPENCLI installed successfully!"
echo ""
echo "To configure your API key:"
echo "  export OPENCLI_API_KEY='your-key'"
echo ""
echo "Or edit ~/.opencli/config.json"
echo ""
echo "Run 'opencli' to start!"
