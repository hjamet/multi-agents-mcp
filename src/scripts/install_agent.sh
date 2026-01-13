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

echo -e "${BLUE}📂 Target Directory: ${INSTALL_DIR}${NC}"

if [ ! -d "$INSTALL_DIR" ]; then
    echo "Cloning repository..."
    git clone https://github.com/Starttoaster/multi-agents-mcp.git "$INSTALL_DIR"
else
    echo "Directory exists. Pulling latest changes..."
    cd "$INSTALL_DIR" && git pull && cd - > /dev/null
fi

# 3. Install Dependencies
echo -e "${BLUE}📦 Installing dependencies...${NC}"
cd "$INSTALL_DIR"
uv sync
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
mkdir -p "\$CWD/.multi-agent-mcp/presets"
mkdir -p "\$CWD/.multi-agent-mcp/logs"

# 3. Launch Streamlit from the global installation
cd "\$INSTALL_DIR"
uv run streamlit run src/interface/app.py
EOF

chmod +x "$MAMCP_PATH"
echo -e "${GREEN}✅ 'mamcp' command installed to $MAMCP_PATH${NC}"

# 5. Connect to MCP using Python script for JSON safety
echo -e "${BLUE}🔌 Configuring MCP Server ID...${NC}"
CONFIG_PATH="$HOME/.gemini/antigravity/mcp_config.json"
REPO_ABS_PATH=$(realpath "$INSTALL_DIR")

# We use a small python snippet to handle the JSON update safely
python3 -c "
import json
import os
import sys

config_path = '$CONFIG_PATH'
repo_path = '$REPO_ABS_PATH'
server_script = os.path.join(repo_path, 'src', 'core', 'server.py')

try:
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            data = json.load(f)
    else:
        # Check if parent dir exists
        if not os.path.exists(os.path.dirname(config_path)):
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
        data = {'mcpServers': {}}

    # Define the new server config with shell wrapper for compatibility
    command_str = f'cd {repo_path} && uv run python {server_script}'
    
    new_server = {
        'command': 'sh',
        'args': ['-c', command_str],
        'env': {}
    }

    data.setdefault('mcpServers', {})
    data['mcpServers']['multi-agents-mcp'] = new_server

    with open(config_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print('✅ MCP Config updated successfully.')

except Exception as e:
    print(f'Error updating JSON: {e}')
    sys.exit(1)
"

echo -e "${GREEN}✅ Installation Complete!${NC}"
echo -e "Make sure $BIN_DIR is in your PATH."
echo -e "You can now run 'mamcp' in any project folder."
