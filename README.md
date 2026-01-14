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
- **Date** : 14 Janvier 2026
- **Scénario** : Équipe de Développement Logiciel (Neural Stream Refactor)
- **Configuration** : Planner, Builder, Challenger
- **État** : 🟢 **READY**. Sprint 6 (Hardening) Started.
- **Agent Anna** : Connecté (Validation Lead).
- **Agent Tom** : Connecté (Tech Support).
- **Résultat** : ✅ Système Validé & Stabilisé (Ready for Hardcore Mode).
- **Features Ajoutées** :
    - 🩹 **Mentions Fix** : Réparation définitive du sélecteur (Anti-Zombie Listeners).
    - 🚑 **Reachability Fix** : Correction critique de l'accès User (typo Case Sensitive) dans `server.py`.
    - ⏸️ **Contrôle Flux** : Bouton Pause + Agent Self-Loop (Max 5).
    - 🧹 **UI Polish** : Nettoyage Chat (No "Tour à") + Bannière Sticky "High-Vis".
    - 🛡️ **Sécurité** : Whitelist Anti-Ghost (Race Condition Fix).
    - 🏗️ **Hardcore Preset** : Restauration du fichier `hardcore.json` (Protocole v2.3.0).
    - 🔄 **Graceful Reload** : Bouton dans l'interface pour déconnecter proprement un agent et libérer le slot (v1.6.0).
    - 💉 **Context Injection** : Restauration des 15 derniers messages après reload (v1.6.2).
    - ⚡ **Latency Optimization** : Polling User réduit à 0.5s (v1.6.3).
    - 🏛️ **Preset V2** : Architecture "Software Development V2" (Zero Trust) disponible.
    - 🛡️ **Auto-Recovery** : Résilience accrue (Try/Except talk -> Pending) (v1.7.0).
    - 🐞 **Syntax Fix** : Correction d'une erreur de syntaxe bloquante dans l'initialisation de l'agent (`server.py`) (v1.7.1).
    - 🧠 **Smart Context** : Injection d'un overlap contextuel (3 messages) lors de la reprise de main ou connexion (v1.7.2).
    - 👻 **Ghost-Buster Fix** : Résolution du Deadlock et du Silence lors d'une interruption User (Logic Reset) (v1.7.3).
    - 💬 **Reply Context** : Visibilité explicite du message auquel on répond dans l'interface (Template Injection) (v1.7.4).
    - 🔄 **Global Reload** : Bouton pour déconnecter tous les agents simultanément sans perte d'historique (v1.8.0).
    - 🛑 **Explicit Termination** : Signal `[TERMINATE_SESSION]` envoyé aux agents lors d'une déconnexion forcée (v1.8.0).
