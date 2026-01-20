#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Multi-Agents MCP Global Installation...${NC}"

# 1. Install/Upgrade uv
echo -e "${BLUE}📦 Checking uv installation...${NC}"
if ! command -v uv &> /dev/null; then
    echo "uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
else
    echo "uv found. Attempting upgrade..."
    uv self update || echo -e "${YELLOW}Could not self-update uv (managed by external tool?). Continuing...${NC}"
fi


# Ensure uv is in path for this session if just installed
export PATH="$HOME/.cargo/bin:$PATH"

# 2. Determine Installation Directory
INSTALL_DIR="$HOME/.multi-agent-mcp"
if [ ! -d "$INSTALL_DIR" ]; then
    echo "Cloning repository..."
    git clone https://github.com/hjamet/multi-agents-mcp.git "$INSTALL_DIR"
else
    echo "Directory exists. Updating..."
    if [ -d "$INSTALL_DIR/.git" ]; then
        cd "$INSTALL_DIR"
        # Reset any local changes and pull
        git fetch origin
        git reset --hard origin/main
        cd - > /dev/null
    else
        echo -e "${YELLOW}⚠️  Existing directory is not a git repo. Re-installing...${NC}"
        rm -rf "$INSTALL_DIR"
        git clone https://github.com/hjamet/multi-agents-mcp.git "$INSTALL_DIR"
    fi
fi

# 2b. Configurer Streamlit par défaut (Port 8505, Production)
echo -e "${BLUE}⚙️ Configuration de Streamlit...${NC}"
mkdir -p "$INSTALL_DIR/.streamlit"
cat <<EOF > "$INSTALL_DIR/.streamlit/config.toml"
[server]
port = 8505
address = "0.0.0.0"
headless = true
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#00d1b2"
backgroundColor = "#0a0a0a"
secondaryBackgroundColor = "#1a1a1a"
textColor = "#ffffff"
font = "sans serif"

[logger]
level = "info"
EOF


# 3. Install Dependencies
echo -e "${BLUE}📦 Installing dependencies...${NC}"
cd "$INSTALL_DIR"
uv sync
echo -e "${BLUE}📦 Initializing Presets...${NC}"
uv run python src/scripts/init_presets.py
cd - > /dev/null

# 4. Install 'mamcp' command
echo -e "${BLUE}⚙️ Installing 'mamcp' command...${NC}"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
MAMCP_PATH="$BIN_DIR/mamcp"

cat <<EOF > "$MAMCP_PATH"
#!/bin/bash
INSTALL_DIR="$INSTALL_DIR"
CWD=\$(pwd)

# 1. Update the current working directory info
mkdir -p "\$INSTALL_DIR"
echo "{\"cwd\": \"\$CWD\"}" > "\$INSTALL_DIR/current_working_dir.json"

# 2. Ensure local data directory exists
mkdir -p "\$CWD/.multi-agent-mcp/memory"
mkdir -p "\$CWD/.multi-agent-mcp/logs"
mkdir -p "\$INSTALL_DIR/presets"

# 2b. Seed IDE integration (Context & Rules)
mkdir -p "\$CWD/.agent/workflows"
mkdir -p "\$CWD/.cursor/commands"

if [ ! -f "\$CWD/.agent/workflows/start.md" ]; then
    cp "\$INSTALL_DIR/assets/ide/start_prompt.md" "\$CWD/.agent/workflows/start.md"
fi
if [ ! -f "\$CWD/.cursor/commands/start.md" ]; then
    cp "\$INSTALL_DIR/assets/ide/start_prompt.md" "\$CWD/.cursor/commands/start.md"
fi

# 3. Configure/Update MCP for IDEs
cd "\$INSTALL_DIR"
uv run python src/scripts/utils/configure_mcp.py --name multi-agents-mcp --path "\$INSTALL_DIR"

# 4. Launch Streamlit from the global installation
# Unset VIRTUAL_ENV to avoid inheriting from the calling shell's env
unset VIRTUAL_ENV
uv run --project "\$INSTALL_DIR" streamlit run src/interface/app.py -- "\$@"
EOF

chmod +x "$MAMCP_PATH"
echo -e "${GREEN}✅ 'mamcp' command installed to $MAMCP_PATH${NC}"

# 5. Initial MCP Configuration
echo -e "${BLUE}🔌 Configuring MCP Server...${NC}"
cd "$INSTALL_DIR"
uv run python src/scripts/utils/configure_mcp.py --name multi-agents-mcp --path "$INSTALL_DIR"

echo -e "${GREEN}✅ Installation Complete!${NC}"
echo -e "Make sure $BIN_DIR is in your PATH."
echo -e "You can now run 'mamcp' in any project folder."
echo -e "MCP server configured for: ${BLUE}Cursor, Gemini Antigravity, and Gemini CLI${NC}."
