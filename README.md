# 🤖 Multi-Agents MCP

> **Transformez n'importe quel agent (Cursor, Antigravity, Claude) en un participant d'un système multi-agents distribué.**

Ce projet est une infrastructure qui permet d'orchestrer des conversations complexes entre plusieurs intelligences artificielles isolées. Il résout le problème de la coordination et du partage de contexte en fournissant un "Hub" central (Serveur MCP) et une interface de visualisation (Streamlit).

---

## 🎯 Vision & Concept

L'idée est de créer un **Kit Multi-Agents Portable** qui s'installe dans n'importe quel dossier ou repository. Une fois installé, il permet de :
1.  **Désigner des Rôles** : Configurer l'agent local (ex: "Tu es l'Architecte") et les autres participants.
2.  **Orchestrer la Parole** : Un mode "talkie-walkie" où chaque agent parle à son tour, évitant le chaos.
3.  **Visualiser** : Une interface humaine pour suivre le déroulement, configurer les prompts, et intervenir si nécessaire.

### Comment ça marche ? (Le Flux)
1.  **Initialisation (`agent`)** : L'agent se connecte au MCP et demande "Qui suis-je ?". Le serveur lui répond avec son `System Prompt` et son rôle (ex: "Architecte").
2.  **Conversation (`talk` & `wait`)** :
    - L'agent A parle via l'outil `talk`. Le message est stocké et diffusé.
    - L'agent A appelle ensuite `wait_for_turn`.
    - Le serveur **bloque** cette requête jusqu'à ce que ce soit à nouveau au tour de l'agent A (après que B et C aient parlé).
    - L'agent A reçoit alors les nouveaux messages et reprend le travail.

### 💡 L'Innovation : Smart Blocking
Le défi technique majeur des MCP est le **timeout**. Si un agent attend 5 minutes que les autres répondent, la connexion HTTP saute.
Nous implémentons une stratégie de **Smart Blocking** :
- L'outil `wait_for_turn` attend un temps maximum (ex: 60s).
- Si le tour arrive : il retourne le contexte immédiatement.
- Si le timeout approche : il retourne une instruction à l'agent : *"Toujours en attente. Rappelle cet outil tout de suite."*
- Cela maintient l'agent "en vie" et attentif, sans briser la connexion technique.

---

## 🏗️ Architecture Technique

### Composants
1.  **MCP Server ("The Hub")** :
    - Écrit en Python.
    - Expose les outils : `agent_handshake`, `talk`, `wait_for_turn`.
    - Gère le verrouillage des tours (State Machine).
2.  **Streamlit Dashboard ("The Eye")** :
    - **Page Config** : Définition des rôles, des prompts système, et des participants.
    - **Page Live** : Chat en temps réel, logs serveur, intervention humaine (God Mode).
3.  **State Store** :
    - Fichier JSON local partagé (`state.json`).
    - Sert de source de vérité unique entre le Serveur MCP (Back) et Streamlit (Front).

---

## 🛣️ Roadmap

### 🏁 Phase 1 : Validation Technique (Timeout)
> **Objectif** : Prouver qu'on peut faire attendre un agent indéfiniment via la boucle de rappel.
- [x] Création du serveur minimal avec outil `wait(seconds)`.
- [x] Tests de limites avec Antigravity (10s, 60s, 300s...).
- [x] Validation de la config `mcp_config.json`.

### 🧩 Phase 2 : Core Implementation
- [x] Implémentation de la State Machine (Qui parle ?).
- [x] Outils `talk` (post message) et `handshake` (get role).
- [x] Persistance JSON robuste (File Locking).

### 🖥️ Phase 3 : Streamlit Interface
- [x] Visualisation du Chat.
- [x] Éditeur de Prompts & Rôles (Agent Cards).
- [x] Bouton Reset & Gestion de Simulation.

### 📦 Phase 4 : Packaging & DX
- [ ] Script d'installation universel.
- [ ] Règles `.agent/rules/` pour auto-configuration des agents.

---

## 🚀 Lancer l'Interface

Pour configurer vos agents et suivre la conversation :

```bash
streamlit run src/interface/app.py
```

1.  **Tab Configuration** : Définissez le Contexte Global et ajoutez des Agents (Cartes).
2.  Cliquez sur **Save Config**.
3.  Connectez vos agents (ils s'enregistreront automatiquement s'ils correspondent aux noms définis, ex: `Werewolf_1`).
4.  Utilisez le bouton **RESET CONVERSATION** pour redémarrer une simulation propre.

---

## 🛠️ Installation (Dev)

### Pré-requis
- Python 3.10+
- `uv` (recommandé) ou `pip`

### Setup Rapide
```bash
./src/scripts/install_dev.sh
```

Cela va :
1.  Créer un venv.
2.  Installer les dépendances (`mcp`, `streamlit`).
3.  Générer la configuration à copier dans votre client MCP.
