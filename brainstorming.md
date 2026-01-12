# 🧠 Brainstorming : Amélioration Rigueur Agents

> [!IMPORTANT]
> **Objectif User** : Les agents actuels sont trop "soft". Ils valident trop vite. 
> **Solution visée** : Injecter une culture "Zero Trust" / "Defensive Programming" dans les prompts.

## 🎯 Analyse de l'Existant (`software_development.json`)
- **Problème** : Les prompts sont basés sur des "Personalités" (MBTI) plutôt que sur des **Protocoles de Vérification**.
- **QA Actuel** : "Clique sur les boutons" (Impossible pour un LLM pur sans browser). Manque d'automatisation explicite.
- **Review Actuelle** : "Valide les PRs critiques". Trop vague.

## 🛣️ Pistes d'Amélioration (Approche "Hardcore")

### 1. Refonte des Prompts : "Rôles Adversariaux"
Transformer la bienveillance en **Rigueur Professionnelle**.

| Rôle Actuel | Nouveau Concept | Changement clé |
| :--- | :--- | :--- |
| **Product Owner** | **Product Owner (Value Sentinel)** | Rejette toute User Story floue. Exige des "Acceptance Criteria" atomiques. |
| **Tech Lead** | **Architect & Auditor** | Ne "regarde" pas le code. **Exige** des preuves (Linters, Tests d'intégration). Refuse tout code sans docstring. |
| **Dev** | **Software Craftsman** | **TDD Strict**. Écrit le test AVANT le code. Ne demande pas "si ça va", affirme "c'est prouvé par le test X". |
| **QA Ops** | **Adversary / Security** | Ne se contente pas de tester le "Happy Path". Cherche les Edge Cases, les injections, les race conditions. |

### 2. Le Protocole "Trust, but Verify"
Ajouter une instruction système globale ou par agent :
> "N'accepte jamais une affirmation d'un autre agent sans preuve (Sortie de terminal, Log, Résultat de test). Si un agent dit 'J'ai fixed', demande 'Montre-moi le run de test vert'."

### 3. Idée de Structure "Defense in Depth"
Ajouter un step explicite de **"Pre-Mortem"** : Avant de coder, le Tech Lead et le QA doivent lister 3 façons dont ça va planter.

## ✅ Décisions Proposées
1.  Créer une **copie améliorée** : `assets/presets/software_development_v2.json`.
2.  **Hardening du Tech Lead** : Liste de vérification explicite (Security, Perf, Type Hinting strict).
3.  **Hardening du QA** : Instruction de générer des scripts de test Python (`test_scenario.py`) et de les exécuter via `run_command`.
4.  **Suppression du MBTI** : Remplacer par des directives oérationnelles ("Use Python Type Hints", "Enforce Google Docstyle").

## 🗑️ Rejeté
- Ajouter plus d'agents (ex: Security Specialist) -> Trop de bruit/latence pour 5 agents max recommandé.
- Changer le nom des rôles radicalement -> Garder la familiarié "Agile".

## 🛣️ Roadmap & Handover
> [!IMPORTANT]
> **Action Immédiate** : Proposer cette nouvelle architecture JSON `software_development_v2.json` à l'utilisateur. Si validé, implémenter les nouveaux prompts.

