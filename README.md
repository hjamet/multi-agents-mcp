# 🤖 Multi-Agents MCP

**Multi-Agents MCP** est une infrastructure d'orchestration permettant de transformer n'importe quel agent d'IA (Cursor, Claude, Antigravity) en participant d'une simulation multi-agents distribuée. En agissant comme un "Hub" central via le Model Context Protocol (MCP), ce système résout les problèmes de coordination, de timeout et de partage de contexte, offrant un mode "talkie-walkie" robuste visualisable via un Dashboard Streamlit.

# Installation

Installation rapide (Global & MCP) :

```bash
curl -sSL https://raw.githubusercontent.com/hjamet/multi-agents-mcp/main/src/scripts/install_agent.sh | bash
```

Une fois installé, utilisez la commande `mamcp` dans n'importe quel dossier pour démarrer l'interface :

```bash
mamcp
```

### Installation pour Développeur (Local)

Si vous travaillez sur le code de mamcp et souhaitez tester vos modifications en direct :

```bash
# Depuis la racine du repository
./src/scripts/install_dev.sh
```

Cette commande installe `mamcp-dev` et configure un serveur MCP nommé `multi-agents-mcp-dev` pointant sur votre dossier de travail.

**Pré-requis** :
- Python 3.10+
- `uv` (installé automatiquement si absent)

# Description détaillée

### Cœur du Système : Le Hub MCP
Ce projet fournit un serveur MCP qui expose des outils critiques (`agent`, `talk`, `note`, `sleep`, `wait_for_turn`) aux agents connectés. Il agit comme un chef d'orchestre, imposant une "State Machine" stricte où chaque agent doit attendre son tour et s'identifier formellement pour éviter les collisions de session.

### Flux de Travail
1.  **Configuration** : L'humain définit les rôles et le scénario via le panneau d'administration (Sidebar). Une gestion fine des connexions est possible via un éditeur intégré.
2.  **Connexion** : Les agents (clients MCP) se connectent et reçoivent leur identité via `register_agent`. Le système gère le découplage entre les profils internes et les noms d'affichage publics.
3.  **Simulation** : Les agents échangent des messages. Le mécanisme de **Smart Blocking** empêche les timeouts HTTP en maintenant les agents en attente active jusqu'à leur tour. Une logique de **Strict Turn Enforcement** garantit qu'aucun agent ne peut parler hors de son tour.

### Rôle de l'Architecte & Direction
Le système évolue vers une plateforme agnostique permettant des simulations complexes (Debates, Jeux, Planification Stratégique). Les travaux actuels se concentrent sur la robustesse de la gestion d'état (File Locking) et l'expérience utilisateur (Dashboard temps réel avec Pagination et Personnalisation par Emoji).

# Principaux résultats

| Métrique | Résultat | Description |
| :--- | :--- | :--- |
| **Stabilité Connexion** | > 300s | Validé via Smart Blocking (boucles d'attente actives) |
| **Concurrence** | 10+ Agents | Testé sur simulation "Loup-Garou" |
| **Latence État** | < 100ms | Synchronisation via `state.json` et Portalocker |

# Plan du repo

```text
.
├── src/
│   ├── core/           # Logique métier (StateMachine, StateStore)
│   ├── interface/      # Application Streamlit (Dashboard)
│   └── scripts/        # Outils d'installation et maintenance
├── state.json          # Source de vérité partagée (Persistance)
├── mcp_config.json     # Configuration générée pour les clients MCP
└── .agent/             # Règles et Workflows
```

# Scripts d'entrée principaux

| Script/Commande | Description détaillée | Usage |
| :--- | :--- | :--- |
| `mamcp` | Lance l'interface unifiée "Neural Stream" (Chat + Admin Sidebar) dans le dossier courant. | `mamcp` |
| `install_agent.sh` | Installe l'environnement global, la commande `mamcp` et configure le MCP. | `curl ... | bash` |
| `install_dev.sh` | Installe l'environnement de développement, la commande `mamcp-dev` et le MCP-dev. | `./src/scripts/install_dev.sh` |

# Scripts exécutables secondaires & Utilitaires

| Script | Rôle technique | Contexte d'exécution |
| :--- | :--- | :--- |
| `src/core/server.py` | Point d'entrée du Serveur MCP (exécuté par le client). | Arrière-plan (via config MCP) |
| `src/core/state.py` | Gestionnaire de stockage atomique (JSON + Lock). | Importé par Core & Interface |
| `src/core/logic.py` | Moteur logique de la simulation (Règles, Tours). | Importé par Server |

# Roadmap

| Fonctionnalité | Priorité | Statut |
| :--- | :--- | :--- |
| **Script d'installation universel** | Haute | ✅ Terminé |
| **Règles d'Auto-Configuration (.agent)** | Moyenne | 📅 Prévu |
| **Intégration Graphviz dynamique** | Moyenne | ✅ Restauré (Hotfix) |
| **Refonte UI (Neural Stream + Graph Tabs)** | Haute | ✅ Terminé (Polished) |
| **Correction Visibilité Messages Agent/User** | Haute | ✅ Terminé (Bugfix) |
| **Support Multi-Room / Multi-Thread** | Basse | 📅 Futur |

## 🕹️ Simulation en cours
- **Date** : 13 Janvier 2026
- **Scénario** : Équipe de Développement Logiciel (Neural Stream Refactor)
- **Configuration** : Planner, Builder, Challenger
- **État** : 🟢 **COMPLETE**. Sprint 5: Discord Ultimate Experience.
- **Agent Anais** : Connecté (Debug & Validation).
- **Résultat** : ✅ Tests Techniques Validés (Comms, Fichiers, Mémoire, Privé).
- **Features Ajoutées** :
    - God Mode (Visibilité Admin Totale).
    - Sécurité Renforcée (Whitelist Anti-Ghost).
    - UX : User dans Sidebar + Self-Loop (5 msgs max).
