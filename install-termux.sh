#!/usr/bin/env bash
# ORINNE Installer - Works on Termux, Linux, macOS
# No native compilation required - pure Python

set -e

echo ""
echo "  ╔═════════════════════════════════════════╗"
echo "  ║         ORINNE Installer               ║"
echo "  ║   AI-powered TUI agent for Termux      ║"
echo "  ╚═════════════════════════════════════════╝"
echo ""

# Detect environment
IS_TERMUX=false
if [ -n "$TERMUX_VERSION" ]; then
    IS_TERMUX=true
    echo "  ✓ Detected: Termux (Android)"
elif [ "$(uname -s)" = "Linux" ]; then
    echo "  ✓ Detected: Linux"
elif [ "$(uname -s)" = "Darwin" ]; then
    echo "  ✓ Detected: macOS"
fi

# Check Python
echo ""
echo "  [1/4] Checking Python 3..."

PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "  ✗ Python not found!"
    if [ "$IS_TERMUX" = true ]; then
        echo "  Installing Python..."
        pkg install python -y
        PYTHON_CMD="python"
    else
        echo "  Please install Python 3.9+ and try again."
        exit 1
    fi
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "  ✓ Python $PYTHON_VERSION found"

# Upgrade pip
echo ""
echo "  [2/4] Upgrading pip..."
$PYTHON_CMD -m pip install --upgrade pip --quiet 2>/dev/null || true
echo "  ✓ pip upgraded"

# Install ORINNE
echo ""
echo "  [3/4] Installing ORINNE..."

# Clone if not in project directory
INSTALL_DIR="$HOME/.orinne-src"
if [ ! -f "pyproject.toml" ] || [ ! -d "src/orinne" ]; then
    echo "  Downloading ORINNE..."
    rm -rf "$INSTALL_DIR"
    git clone https://github.com/EverKrypton/orinne.git "$INSTALL_DIR" --depth 1
    cd "$INSTALL_DIR"
fi

# Install dependencies (pure Python, no compilation)
echo "  Installing dependencies..."
$PYTHON_CMD -m pip install textual httpx pygments rich python-dotenv beautifulsoup4 --quiet

# Install orinne in user space
echo "  Installing ORINNE..."
$PYTHON_CMD -m pip install --user . --quiet 2>/dev/null || {
    # Fallback: create a simple wrapper script
    BIN_DIR="$HOME/.local/bin"
    mkdir -p "$BIN_DIR"
    
    cat > "$BIN_DIR/orinne" << 'WRAPPER'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$SCRIPT_DIR/.orinne-src/src"
exec python3 -m orinne "$@"
WRAPPER
    chmod +x "$BIN_DIR/orinne"
    echo "  ✓ Installed via wrapper script"
}

echo "  ✓ ORINNE installed"

# Create config directory
echo ""
echo "  [4/4] Setting up configuration..."
CONFIG_DIR="$HOME/.orinne"
mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_DIR/config.json" ]; then
    cat > "$CONFIG_DIR/config.json" << 'CONFIG'
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
    "auto_indent": true,
    "theme": "monokai",
    "word_wrap": false
  }
}
CONFIG
    echo "  ✓ Created config: $CONFIG_DIR/config.json"
else
    echo "  ✓ Config already exists"
fi

# Add to PATH if needed
SHELL_RC=""
if [ -n "$TERMUX_VERSION" ]; then
    SHELL_RC="$HOME/.bashrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
elif [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
fi

if [ -n "$SHELL_RC" ]; then
    if ! grep -q 'orinne' "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# ORINNE" >> "$SHELL_RC"
        echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$SHELL_RC"
    fi
fi

echo ""
echo "  ╔═════════════════════════════════════════╗"
echo "  ║         ✓ Installation Complete!        ║"
echo "  ╚═════════════════════════════════════════╝"
echo ""
echo "  Configure your AI API key:"
echo ""
echo "    export ORINNE_API_KEY='your-key-here'"
echo ""
echo "  Or edit: ~/.orinne/config.json"
echo ""
echo "  Run ORINNE:"
echo ""
echo "    orinne"
echo ""
if [ -n "$SHELL_RC" ]; then
    echo "  (Restart your shell or run: source $SHELL_RC)"
fi
echo ""
