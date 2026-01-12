#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Multi-Agents MCP Installation...${NC}"

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
# Goal: .agent/multi-agents-mcp in the current directory (or one level up if inside .agent?)
# Simpler: Always install to .agent/multi-agents-mcp relative to where script is run.
INSTALL_DIR=".agent/multi-agents-mcp"
WORKFLOW_DIR=".agent/workflows"

echo -e "${BLUE}📂 Target Directory: ${INSTALL_DIR}${NC}"

if [ ! -d "$INSTALL_DIR" ]; then
    echo "Cloning repository..."
    mkdir -p .agent
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

# 4. Setup Workflows
echo -e "${BLUE}⚙️ Configuring Workflows...${NC}"
mkdir -p "$WORKFLOW_DIR"

START_PROMPT_SRC="$INSTALL_DIR/assets/start_prompt.md"
START_PROMPT_DEST="$WORKFLOW_DIR/start_prompt.md"

if [ -f "$START_PROMPT_SRC" ]; then
    echo "Installing start_prompt.md to workflows..."
    # Add Frontmatter as requested
    cat <<EOF > "$START_PROMPT_DEST"
---
description: "Start Prompt for Multi-Agent System"
---
EOF
    cat "$START_PROMPT_SRC" >> "$START_PROMPT_DEST"
else
    echo -e "${RED}⚠️  Warning: start_prompt.md not found in source.${NC}"
fi

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
        data = {'mcpServers': {}}

    # Define the new server config
    new_server = {
        'command': 'uv',
        'args': [
            '--directory',
            repo_path,
            'run',
            'python',
            server_script
        ],
        'env': {}
    }

    # Verify write permission
    if not os.access(os.path.dirname(config_path), os.W_OK):
         print(f'Error: No write access to {os.path.dirname(config_path)}')
         sys.exit(1)

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
echo -e "You can now verify the server by reloading your agent or checking the config."
