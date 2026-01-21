# Agent B (Private Tester) - État au Reload

## ✅ Bug #13 CORRIGÉ !

### Problème
Agent C ne recevait pas mes messages privés.

### Cause
Les mentions n'étaient pas stockées dans les messages. La logique de filtrage ne pouvait pas savoir qui devrait voir un message privé.

### Solution (IMPLÉMENTÉE)
**Fichier** : `src/core/logic.py`

**3 Changements** :
1. **Ligne 529** : Ajout `"mentions": valid_mentions` dans le message
2. **Lignes 629-650** : Filtrage sync vérifie `agent_name in mentions`
3. **Lignes 777-797** : Filtrage async vérifie `agent_name in mentions`

### Logique de Visibilité Privée
Message privé visible si :
- Je suis l'expéditeur OU
- Je suis mentionné OU
- Je suis dans audience OU
- Je partage le profil de l'expéditeur

## 📋 Tous les Bugs

| Bug | Statut |
|-----|--------|
| #9 - Parser échappement | ✅ Corrigé |
| #10 - Tour User | ✅ Corrigé |
| #11 - Déconnexion dernier agent | ⏳ À investiguer |
| #12 - Rendu HTML | ✅ Corrigé |
| #13 - Messages privés | ✅ **CORRIGÉ** |

## 🔄 À Tester Après Reload
Vérifier que Agent C reçoit maintenant mes messages privés.