# Multi-Agents MCP

Un système MCP permettant de transformer n'importe quel agent (Antigravity, Cursor, Claude Desktop) en participant d'un système multi-agents distribué.

## 🚀 Vision
Ce projet fournit un **Serveur MCP** "Hub" et une interface **Streamlit** pour orchestrer des conversations entre plusieurs intelligences artificielles isolées. Il résout le problème de coordination en fournissant un état partagé et un mécanisme de "tour de parole".

## 🚧 Roadmap
### Phase 1 : Infrastructure & Validation (En Cours)
- [x] Brainstorming Architecture
- [ ] Setup initial du projet (`src/`)
- [ ] **Expérience Critique : Validation des Timeouts MCP**
    - Tester les limites de connexion long-polling avec différents clients.

### Phase 2 : Core Implementation
- [ ] Serveur MCP (`talk`, `wait_for_turn`)
- [ ] Gestion d'état JSON partagé
- [ ] Mécanisme de "Smart Blocking" pour contourner les timeouts

### Phase 3 : Interface & Expérience
- [ ] Dashboard Streamlit (Config & Chat)
- [ ] Règle système `.agent/rules/multi_agent.md` pour autopilotage

## 🛠️ Installation
*Section à venir...*
