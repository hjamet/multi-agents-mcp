#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Setting up Multi-Agents MCP (Dev Environment)...${NC}"

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "uv not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# Create venv and install dependencies
echo -e "${BLUE}📦 Installing dependencies with uv...${NC}"
uv venv .venv
source .venv/bin/activate
uv pip install -r pyproject.toml

# Get absolute path to python
PYTHON_PATH=$(which python)
SCRIPT_PATH="$(pwd)/src/core/server.py"

echo -e "${GREEN}✅ Installation complete!${NC}"
echo -e "${BLUE}📋 Add this to your mcp_config.json:${NC}"

cat <<EOF
    "multi-agents-exp": {
      "command": "${PYTHON_PATH}",
      "args": [
        "${SCRIPT_PATH}"
      ]
    }
EOF
