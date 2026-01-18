# Vir (QA Engineer) - Audit Templates XML (V2)

## 🚨 Point de Blocage Identifié

Le contrat User n'est **PAS REMPLI**.

### Spec User
> "aussi pour les éléments au sein de ces sections (messages utilisateurs <user>...)"

### État Actuel
- `<conversation_history>` : ✅ OK (Conteneur)
- Contenu Interne : ❌ KO (Markdown `- **User** -> All`).

### Conséquence
Le parsing fin (niveau message) reste impossible/fragile. Risque de "messages invisibles" maintenu.

## 🎯 Action Requise
- **REFUS** de la validation en l'état.
- **Retour Dev** (Alex) : Implémenter le balisage granulaire (`<message>`, `<content>`, `<from>`).
