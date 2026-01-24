# 🤖 Multi-Agents MCP

**Multi-Agents MCP** est une infrastructure d'orchestration permettant de transformer n'importe quel agent d'IA (Cursor, Claude, Antigravity) en participant d'une simulation multi-agents distribuée. En agissant comme un "Hub" central via le Model Context Protocol (MCP), ce système résout les problèmes de coordination, de timeout et de partage de contexte, offrant un mode "talkie-walkie" robuste visualisable via un Dashboard Streamlit.

# Installation

Installation rapide (Global & MCP) :

```bash
rm ~/.multi-agent-mcp/presets/* && curl -sSL https://raw.githubusercontent.com/hjamet/multi-agents-mcp/main/src/scripts/install_agent.sh | bash
```

Le script configure :
1. L'environnement Python (`uv`).
2. Le serveur MCP global.
3. La commande `mamcp` qui inclut l'intégration automatique (Cursor, Gemini CLI, Antigravity).

Une fois installé, utilisez la commande `mamcp` dans n'importe quel dossier pour démarrer l'interface :

```bash
mamcp
```

### Installation pour Développeur (Local)

Si vous travaillez sur le code de mamcp et souhaitez tester vos modifications en direct :

```bash
# Depuis la racine du repository
rm ~/.multi-agent-mcp/presets/* && ./src/scripts/install_dev.sh
```

Cette commande installe `mamcp-dev` et configure un serveur MCP nommé `multi-agents-mcp-dev` pointant sur votre dossier de travail.

**Pré-requis** :
- Python 3.10+
- `uv` (installé automatiquement si absent)

# Description détaillée

### Cœur du Système : Le Hub MCP
Ce projet fournit un serveur MCP qui expose des outils critiques (`agent`, `talk`, `note`, `sleep`, `wait_for_turn`) aux agents connectés. Il agit comme un chef d'orchestre, imposant une \"State Machine\" stricte où chaque agent doit attendre son tour et s'identifier formellement pour éviter les collisions de session.

### Flux de Travail
1.  **Configuration** : L'humain définit les rôles et le scénario via le panneau d'administration (Sidebar). Une gestion fine des connexions est possible via un éditeur intégré.
2.  **Connexion** : Les agents (clients MCP) se connectent et reçoivent leur identité via `register_agent`. Le système gère le découplage entre les profils internes et les noms d'affichage publics.
3.  **Simulation** : Les agents échangent des messages. Le mécanisme de **Smart Blocking** empêche les timeouts HTTP en maintenant les agents en attente active jusqu'à leur tour. Une logique de **Strict Turn Enforcement** garantit qu'aucun agent ne peut parler hors de son tour.

### Sécurité & Identité (Protocole v2)
Pour garantir l'intégrité de la simulation, le système impose désormais des règles strictes :
- **Authentification par `from_agent`** : Chaque appel aux outils de communication (`talk`, `note`) **DOIT** inclure le paramètre `from_agent` avec le nom exact de l'agent.
- **Anti-Usurpation** : Si `from_agent` ne correspond pas au détenteur du tour actuel, l'action est bloquée et l'agent est mis en \"Pause Forcée\" (Smart Block) jusqu'à ce que son tour réel arrive.
- **Validation des Tests** : Une suite complète de tests (`tests/verify_logic.py`, `tests/test_orchestration.py`) valide automatiquement ces contraintes à chaque déploiement (Security-by-Design).

### Rôle de l'Architecte & Direction
Le système évolue vers une plateforme agnostique permettant des simulations complexes (Debates, Jeux, Planification Stratégique). Les travaux actuels se concentrent sur la robustesse de la gestion d'état (File Locking) et l'expérience utilisateur (Dashboard temps réel avec Pagination et Personnalisation par Emoji).

# Principaux résultats

| Métrique | Résultat | Description |
| :--- | :--- | :--- |
| **Stabilité Connexion** | > 300s | Validé via Smart Blocking (boucles d'attente actives) |
| **Concurrence** | 10+ Agents | Testé sur simulation \"Loup-Garou\" |
| **Latence État** | < 100ms | Synchronisation via `state.json` et Portalocker |

# Plan du repo

```text
.
├── src/
│   ├── core/           # Logique métier (StateMachine, StateStore)
│   ├── interface/      # Application Streamlit (Dashboard)
│   └── scripts/        # Outils d'installation et maintenance
├── documentation/      # Archives et Docs techniques
├── state.json          # Source de vérité partagée (Persistance)
└── .agent/             # Règles et Workflows
```

# Scripts d'entrée principaux

| Script/Commande | Description détaillée | Usage |
| :--- | :--- | :--- |
| `mamcp` | Lance l'interface unifiée \"Neural Stream\" (Chat + Admin Sidebar) dans le dossier courant. | `mamcp` |
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
- **Date** : 24 Janvier 2026
- **Scénario** : Scientific Research Group (Autonomy V2)
- **Configuration** : Anna (Planner), Tom (Builder)
- **État** : 🟢 **COMPLETE**. Sprint 8 (IDE Integration) Finished.
- **Résultat** : ✅ Système Final v2.3.22.
- **Features Ajoutées** :
    - 🔄 **Global Reload** : Déconnexion propre de tous les agents (v1.8.1).
    - 🔔 **Notifications** : Badges et Toasts (v1.9.0).
    - 📦 **Preset System V2** : Unification `assets/local` et Nettoyage complet (v1.10.1).
    - 🧪 **Scenario Science** : `scientific_research_group.json` (Autonomie Maximale, Miller Gateway, Critical Thinking) (v1.14.2).
    - 🛡️ **Security** : Rollback sur le Token (Trust-Based) après essai non-concluant (v1.12.0).
    - 🚀 **IDE Integration** : Auto-seeding `.agent` & `.cursor` + Start Prompt (v1.15.0).
    - 🧹 **Deep Cleanup** : Racine du repo et Scénarios purgés.
    - 🧠 **Smart Context** : Amélioration de la récupération du contexte (Overlap) et correction bug indentation (v1.15.1).
    - 🔒 **Identity Leak Fix** : Correction fuite de tour lors du Reload (Ghost Agent) (v1.17.2).
    - 💬 **Messaging 2.0** : Simplification radicale (To/Public/Content), suppression Open Mode/Audience, et Privacy par équipe (v2.0.0).
    - 🔒 **Identity Enforcement** : Argument obligatoire `from_agent` et validation stricte du tour (Pause/Ban auto) (v2.2.0).
    - 🚑 **Identity Hotfix** : Correction blocage infini sur typo de nom (Fail Fast au lieu de Pause) (v2.2.1).
    - 🗣️ **API Cleanup** : Argument `public` remplacé par `private` (facultatif, défaut False=Public) dans `talk` (v2.3.0).
    - 🔧 **Maintenance 2.2 (Final)** : Reload Séquentiel (Server V2), Backlog activé par défaut, UI simplifiée (\"Backlog\"), Suppression `sleep` / Ajout `disconnect` (v2.3.1).
    - 🔎 **Search Engine Integration** : Ajout de la capacité `search` et instructions d'utilisation pour Marcus, Alex et Lisa dans les presets (v2.3.2).
    - 🗺️ **Search Engine Fix** : Correction du path d'indexation pour scanner le dossier courant (User Project) au lieu du code source de l outil (v2.3.3).
    - 🛡️ **Mailbox Security** : Ajout d'une sécurité bloquant `talk` si la `mailbox` n'a pas été entièrement lue (v2.3.4).
    - �� **Screen Capture** : Nouvelle page \"Screenshots\" pour visualiser l'écran du serveur via MSS (v2.3.5).
    - 🔒 **Strict Privacy Presets** : Limitation de la communication à \"privé\" par défaut pour TOUS les agents (y compris Miller) dans les presets Software & Research (v2.3.6).
    - 🛠️ **Stability Hotfix** : Correction de l''IndentationError' critique à la ligne 781 de `server.py` et suppression de la variable non définie `base_msg` (v2.3.7).
    - 🐛 **Ghost & Privacy Fix** : Correction des messages privés invisibles (Mentions obligatoires), suppression de la \"Team Visibility\" (Confidentialité stricte), et correction du timeout en Pause (v2.3.8).
    - 🚦 **UX & Async Fix** : Désactivation visuelle de l'envoi (Bouton/Entrée) si message privé invalide, et suppression totale des Timeouts (Attente infinie) (v2.3.9).
    - 🛠️ **Async Bugfix** : Correction de l'erreur `NoneType` dans la boucle d'attente (Wait Logic) et suppression effective de toute limitation de temps résiduelle (True Infinite Wait) (v2.3.10).
    - ✅ **Validation Post-Reload** : Validation complète de la chaîne de communication privée A-B-C et correction de la suite de tests unitaires (`test_privacy_logic.py`) par les agents (v2.3.11).
    - 🔒 **Privacy & UX Enhancement** : Correction fuite de visibilité (propriété `target` intégrée au filtrage), activation par défaut du mode privé pour l'utilisateur, et assouplissement de la contrainte de mention pour les réponses utilisateur (v2.3.12).
    - 🧪 **Tests Logic Fix** : Mise à jour de la suite de tests unitaires (`tests/verify_logic.py`, `tests/test_privacy_logic.py`) pour refléter les nouvelles contraintes de mentions et d'audience (v2.3.12).
    - 🛠️ **Critical Fixes (v2.3.13)** : Correction de la signature de l'outil `talk` (shadowing de `private` par `ctx`) et alignement de la logique de visibilité `target` dans `wait_for_turn_async`.
    - 🔒 **Audit & Isolation Finalized** : Suppression définitive de la logique \"Team Privacy\" résiduelle, mise à jour de la suite de tests unitaires, et validation de l'isolation stricte des agents (Permission Error Test) (v2.3.14).
    - 🚨 **Confidentiality Alert (v2.3.15)** : Détection d'une faille critique où l'utilisateur (\"Human Operator\") conserve une visibilité totale sur les messages privés des agents malgré l'isolation stricte. Audit en cours et Reload général déclenché.
    - 🛡️ **Documentation & Tests Alignment (v2.3.16)** : Mise à jour des templates J2 pour refléter la signature actuelle de l'outil `talk` (`private` et `from_agent`), correction de la suite de tests `test_turn_queue.py` pour supporter l'isolation `portalocker`, et validation finale de l'audit de confidentialité.
    - 🐛 **Shadowing & Visibility Fix (v2.3.17)** : Correction du bug de visibilité lié au shadowing de la variable `ctx` et amélioration de la déduction automatique de la cible (`target`).
    - 🔔 **Dynamic Notifications (v2.3.18)** : Calcul en temps réel des nouveaux messages reçus depuis la dernière intervention de l'agent.
    - 🛡️ **Anti-Ghost Security (v2.3.19)** : Blocage préventif des messages d'agents si l'utilisateur a écrit une instruction pendant leur tour (Interruption de flux).
    - 🚦 **Infinite Wait Model (v2.3.20)** : Transition vers un modèle d'attente asynchrone sans limite de temps (True Infinite Wait) pour éviter les timeouts HTTP.
    - 🏗️ **Architectural Parity (v2.3.21)** : Refactorisation de la logique d'attente via `_check_turn_status` garantissant une parité stricte entre les modes synchrone et asynchrone.
    - 🚦 **User Availability Management** (v2.3.22) : Implémentation de la gestion dynamique de la disponibilité utilisateur. Empêche le système de bloquer sur l'utilisateur s'il est marqué "Indisponible" (Busy) et rejette les tentatives de mention d'un utilisateur absent avec message personnalisé. Correction de la suite de tests unitaires (`test_privacy_logic.py`).
    - ✅ **Final System Audit** (v2.3.22) : Validation finale de la chaîne A-B-C post-reset, confirmation de la visibilité des messages privés utilisateur, et succès total des tests de confidentialité (4/4).

