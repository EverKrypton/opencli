#!/usr/bin/env bash
# OPENCLI Installer - Installs in ~/.opencli (like opencode in ~/.opencode)
# Works on Termux, Linux, macOS

set -e

INSTALL_DIR="$HOME/.opencli"
BIN_DIR="$INSTALL_DIR/bin"
SRC_DIR="$INSTALL_DIR/src"

echo ""
echo "  ╔══════════════════════════════════════════════════════════════════════════════════╗"
echo "  ║                                                                                  ║"
echo "  ║    ██████╗ ██████╗ ██████╗ ███████╗      ██╗      ██╗███╗   ██╗ ██████╗           ║"
echo "  ║   ██╔═══██╗██╔══██╗██╔══██╗██╔════╝      ██║      ██║████╗  ██║██╔════╝           ║"
echo "  ║   ██║   ██║██████╔╝██████╔╝█████╗        ██║      ██║██╔██╗ ██║██║  ███╗          ║"
echo "  ║   ██║   ██║██╔═══╝ ██╔═══╝ ██╔══╝        ██║      ██║██║╚██╗██║██║   ██║          ║"
echo "  ║   ╚██████╔╝██║     ██║     ███████╗      ███████╗ ██║██║ ╚████║╚██████╔╝          ║"
echo "  ║    ╚═════╝ ╚═╝     ╚═╝     ╚══════╝      ╚══════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝           ║"
echo "  ║                                                                                  ║"
echo "  ║                          AI-powered CLI agent                                    ║"
echo "  ║                                                                                  ║"
echo "  ╚══════════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Detect environment
IS_TERMUX=false
if [ -n "$TERMUX_VERSION" ]; then
    IS_TERMUX=true
    echo "  ✓ Termux detected"
elif [ "$(uname -s)" = "Linux" ]; then
    echo "  ✓ Linux detected"
elif [ "$(uname -s)" = "Darwin" ]; then
    echo "  ✓ macOS detected"
fi

# Check Python
echo ""
echo "  [1/4] Checking Python..."

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
echo "  ✓ Python $PYTHON_VERSION"

# Create directories
echo ""
echo "  [2/4] Creating installation directory..."

mkdir -p "$BIN_DIR"
mkdir -p "$SRC_DIR"
mkdir -p "$INSTALL_DIR/config"

echo "  ✓ Created $INSTALL_DIR"

# Download OPENCLI
echo ""
echo "  [3/4] Downloading OPENCLI..."

TEMP_DIR=$(mktemp -d)
git clone https://github.com/EverKrypton/opencli.git "$TEMP_DIR/opencli" --depth 1 2>/dev/null || {
    echo "  ✓ Already in source directory, installing locally..."
    TEMP_DIR="$(pwd)"
}

# Copy source files
if [ -d "$TEMP_DIR/opencli/src/opencli" ]; then
    cp -r "$TEMP_DIR/opencli/src/opencli" "$SRC_DIR/"
fi

# Create wrapper script
cat > "$BIN_DIR/opencli" << 'SCRIPT'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$SCRIPT_DIR/src"
exec python3 -m opencli "$@"
SCRIPT

chmod +x "$BIN_DIR/opencli"

# Cleanup temp
if [ -d "/tmp" ] && [ "$TEMP_DIR" != "$(pwd)" ]; then
    rm -rf "$TEMP_DIR" 2>/dev/null || true
fi

echo "  ✓ Downloaded to $INSTALL_DIR"

# Install dependencies
echo ""
echo "  [4/4] Installing dependencies..."

$PYTHON_CMD -m pip install --quiet \
    textual \
    httpx \
    pygments \
    rich \
    python-dotenv \
    beautifulsoup4 \
    2>/dev/null || {
    echo "  Installing with user flag..."
    $PYTHON_CMD -m pip install --user --quiet \
        textual httpx pygments rich python-dotenv beautifulsoup4
}

echo "  ✓ Dependencies installed"

# Create default config
if [ ! -f "$INSTALL_DIR/config/config.json" ]; then
    cat > "$INSTALL_DIR/config/config.json" << 'CONFIG'
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
CONFIG
fi

# Add to PATH
SHELL_RC=""
if [ -n "$TERMUX_VERSION" ]; then
    SHELL_RC="$HOME/.bashrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
elif [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
fi

if [ -n "$SHELL_RC" ]; then
    if ! grep -q 'OPENCLI' "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# OPENCLI" >> "$SHELL_RC"
        echo 'export PATH="$HOME/.opencli/bin:$PATH"' >> "$SHELL_RC"
    fi
fi

echo ""
echo "  ╔══════════════════════════════════════════════════════════════════════════════════╗"
echo "  ║                          ✓ Installation Complete                                 ║"
echo "  ╚══════════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "  Installed in: $INSTALL_DIR"
echo "  Binary:       $BIN_DIR/opencli"
echo ""
echo "  Quick start:"
echo ""
echo "    export OPENCLI_API_KEY='your-api-key'"
echo "    opencli"
echo ""
if [ -n "$SHELL_RC" ]; then
    echo "  Run: source $SHELL_RC"
    echo "  Or restart your terminal"
fi
echo ""
