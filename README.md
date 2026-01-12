# 🤖 Multi-Agents MCP

**Multi-Agents MCP** est une infrastructure d'orchestration permettant de transformer n'importe quel agent d'IA (Cursor, Claude, Antigravity) en participant d'une simulation multi-agents distribuée. En agissant comme un "Hub" central via le Model Context Protocol (MCP), ce système résout les problèmes de coordination, de timeout et de partage de contexte, offrant un mode "talkie-walkie" robuste visualisable via un Dashboard Streamlit.

# Installation

Installation rapide pour le développement :

```bash
./src/scripts/install_dev.sh
```

**Pré-requis** :
- Python 3.10+
- `uv` (recommandé) ou `pip`

# Description détaillée

### Cœur du Système : Le Hub MCP
Ce projet fournit un serveur MCP qui expose des outils critiques (`agent`, `talk`, `note`, `sleep`, `wait_for_turn`) aux agents connectés. Il agit comme un chef d'orchestre, imposant une "State Machine" stricte où chaque agent doit attendre son tour et s'identifier formellement pour éviter les collisions de session.

### Flux de Travail
1.  **Configuration** : L'humain définit les rôles (ex: "Loup-Garou", "Voyante") et le scénario dans l'interface Streamlit.
2.  **Connexion** : Les agents (clients MCP) se connectent et reçoivent leur identité via `register_agent`. Le système gère le découplage entre les profils internes et les noms d'affichage publics.
3.  **Simulation** : Les agents échangent des messages. Le mécanisme de **Smart Blocking** empêche les timeouts HTTP en maintenant les agents en attente active jusqu'à leur tour. Une logique de **Strict Turn Enforcement** garantit qu'aucun agent ne peut parler hors de son tour.

### Rôle de l'Architecte & Direction
Le système évolue vers une plateforme agnostique permettant des simulations complexes (Debates, Jeux, Planification Stratégique). Les travaux actuels se concentrent sur la robustesse de la gestion d'état (File Locking) et l'expérience utilisateur (Dashboard temps réel).

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
| `streamlit run src/interface/app.py` | Lance le "Cockpit" de simulation (Configuration, Chat, Logs). | `streamlit run ...` |
| `./src/scripts/install_dev.sh` | Installe l'environnement, les dépendances et génère la config. | `./src/scripts/install_dev.sh` |

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
| **Intégration Graphviz dynamique** | Moyenne | ✅ Terminé |
| **Support Multi-Room / Multi-Thread** | Basse | 📅 Futur |

## 🕹️ Simulation en cours
- **Date** : 12 Janvier 2026
- **Scénario** : Loup-Garou de Thiercelieux
- **Configuration** : 9 Habitants + 1 Maître du Jeu
- **État** : Jour 1 - Le village se réveille sans aucune victime. Discussion en cours.
- **Agent Antigravity** : Connecté sous l'identité **Habitant #3**.
