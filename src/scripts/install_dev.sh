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

# 3b. Initialisation des Presets Utilisateur
echo -e "${BLUE}📦 Initialisation des Presets (copie locale)...${NC}"
uv run python src/scripts/init_presets.py

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

# 3. Configurer/Mettre à jour MCP pour les IDEs
cd "\$DEV_DIR"
uv run python src/scripts/utils/configure_mcp.py --name multi-agents-mcp-dev --path "\$DEV_DIR" --dev

# 4. Lancer Streamlit depuis le dossier de dev
unset VIRTUAL_ENV
uv run streamlit run src/interface/app.py
EOF

chmod +x "$MAMCP_DEV_PATH"
echo -e "${GREEN}✅ Commande 'mamcp-dev' installée dans $MAMCP_DEV_PATH${NC}"

# 5. Configuration initiale de l'extension MCP (Gemini/Cursor)
echo -e "${BLUE}🔌 Configuration du serveur MCP pour le développement...${NC}"
cd "$REPO_ROOT"
uv run python src/scripts/utils/configure_mcp.py --name multi-agents-mcp-dev --path "$REPO_ROOT" --dev

echo -e "\n${GREEN}✨ Installation Dev terminée !${NC}"
echo -e "Vous pouvez maintenant :"
echo -e "1. Lancer l'interface avec : ${BLUE}mamcp-dev${NC}"
echo -e "2. Utiliser le serveur MCP nommé ${BLUE}multi-agents-mcp-dev${NC} dans vos outils (Cursor, Gemini CLI, Antigravity)."
echo -e "\n${YELLOW}Note : Assurez-vous que $BIN_DIR est dans votre PATH.${NC}"
