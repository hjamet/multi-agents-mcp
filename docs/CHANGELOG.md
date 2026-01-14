# Changelog

Toutes les modifications notables de ce projet seront documentées dans ce fichier.

## [1.3.1] - 2026-01-13

### 🐛 Bug Fixes
- **Robustesse du démarrage** : Correction d'un bug majeur où les agents restaient bloqués dans l'attente du réseau ("Network Ready") en raison d'un décompte `total_agents` incohérent.
    - `logic.py` utilise désormais le nombre réel d'agents enregistrés (`len(agents)`) au lieu d'une valeur de configuration potentiellement erronée.
    - `app.py` recalcule systématiquement le nombre d'agents lors du chargement de presets ou du reset de la simulation.

## [1.3.0] - 2026-01-12

### ✨ Fonctionnalités Majeures (Discord-Native Upgrade)
- **Persistent Input & @Mentions** : Abandon du "God Mode" et des formulaires de réponse inline. Introduction d'une barre de saisie unique `st.chat_input` en bas d'écran.
    - Syntaxe : `@NomAgent Votre message` envoie un message privé.
    - Par défaut : Message public diffusé à tous.
- **Roster Panel** : Ajout d'un panneau latéral (colonne droite) listant les agents connectés, leur statut (Actif/Offline) et marquant visuellement celui dont c'est le tour ("🗣️").
- **Smart Reply Tracking** : Lorsqu'un utilisateur envoie un message privé à un agent, le dernier message reçu de cet agent est automatiquement marqué comme "Répondu" (`replied=True`).
- **I18n** : Sélecteur de langue (EN/FR) ajouté dans la sidebar.

## [1.2.0] - 2026-01-12

### ✨ Fonctionnalités Majeures (Major Features)
- **Neural Stream (Hybrid Chat)** : Fusion complète des canaux "Public Frequency" et "Direct Terminal".
- **Inline Replies**.

## [1.1.0] - 2026-01-12

### Initial Release
- Serveur MCP Multi-Agents.
- Orchestration par StateMachine.
