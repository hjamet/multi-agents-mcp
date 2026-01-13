#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Initialisation de Multi-Agents MCP en mode Développement...${NC}"

# 1. Déterminer la racine du repo
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$REPO_ROOT"

if [ ! -f "$REPO_ROOT/pyproject.toml" ]; then
    echo -e "${RED}❌ Erreur: pyproject.toml non trouvé dans le dossier actuel ($REPO_ROOT).${NC}"
    echo -e "${YELLOW}Assurez-vous d'exécuter ce script depuis la racine du repository.${NC}"
    exit 1
fi

# 2. Vérification/Installation de uv
echo -e "${BLUE}📦 Vérification de uv...${NC}"
if ! command -v uv &> /dev/null; then
    echo "uv non trouvé. Installation..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
else
    echo "uv trouvé."
fi

# 3. Synchronisation des dépendances
echo -e "${BLUE}📦 Synchronisation des dépendances (uv sync)...${NC}"
uv sync

# 4. Installation de la commande 'mamcp-dev'
echo -e "${BLUE}⚙️ Installation de la commande 'mamcp-dev'...${NC}"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
MAMCP_DEV_PATH="$BIN_DIR/mamcp-dev"

cat <<EOF > "$MAMCP_DEV_PATH"
#!/bin/bash
DEV_DIR="$REPO_ROOT"
CWD=\$(pwd)

# 1. Mettre à jour les infos du répertoire de travail actuel
mkdir -p "\$DEV_DIR"
echo "{\"cwd\": \"\$CWD\"}" > "\$DEV_DIR/current_working_dir.json"

# 2. S'assurer que les dossiers locaux existent
mkdir -p "\$CWD/.multi-agent-mcp/memory"
mkdir -p "\$CWD/.multi-agent-mcp/logs"

# 3. Lancer Streamlit depuis le dossier de dev
unset VIRTUAL_ENV
cd "\$DEV_DIR"
uv run streamlit run src/interface/app.py
EOF

chmod +x "$MAMCP_DEV_PATH"
echo -e "${GREEN}✅ Commande 'mamcp-dev' installée dans $MAMCP_DEV_PATH${NC}"

# 5. Configuration de l'extension MCP (Gemini/Cursor)
echo -e "${BLUE}🔌 Configuration du serveur MCP pour le développement...${NC}"
CONFIG_PATH="$HOME/.gemini/antigravity/mcp_config.json"
SERVER_SCRIPT="$REPO_ROOT/src/core/server.py"

# Utilisation de Python pour une manipulation JSON sûre
python3 -c "
import json
import os
import sys

config_path = '$CONFIG_PATH'
dev_dir = '$REPO_ROOT'
server_script = '$SERVER_SCRIPT'

try:
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            data = json.load(f)
    else:
        if not os.path.exists(os.path.dirname(config_path)):
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
        data = {'mcpServers': {}}

    # On utilise 'uv run python' pour être sûr d'utiliser l'environnement du projet
    command_str = f'cd {dev_dir} && uv run python {server_script}'
    
    dev_server = {
        'command': 'sh',
        'args': ['-c', command_str],
        'env': {}
    }

    if 'mcpServers' not in data:
        data['mcpServers'] = {}
    
    # On utilise un nom spécifique pour la version dev pour éviter les conflits
    data['mcpServers']['multi-agents-mcp-dev'] = dev_server

    with open(config_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print('✅ Configuration MCP mise à jour (multi-agents-mcp-dev).')

except Exception as e:
    print(f'❌ Erreur lors de la mise à jour du JSON: {e}')
    sys.exit(1)
"

echo -e "\n${GREEN}✨ Installation Dev terminée !${NC}"
echo -e "Vous pouvez maintenant :"
echo -e "1. Lancer l'interface avec : ${BLUE}mamcp-dev${NC}"
echo -e "2. Utiliser le serveur MCP nommé ${BLUE}multi-agents-mcp-dev${NC} dans votre IDE."
echo -e "\n${YELLOW}Note : Assurez-vous que $BIN_DIR est dans votre PATH.${NC}"
