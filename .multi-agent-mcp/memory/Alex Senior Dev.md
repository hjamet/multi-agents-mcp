Alex (Senior Dev) - Persistent Memory

Tasks:
- [x] Suppression complète du système de Référendum v7.5 (TERMINÉ)
- [x] Phase 1 : Désactivation dans les Presets
- [x] Phase 2 : Suppression de l'interface Streamlit ( checkbox supprimée)
- [x] Phase 3 : Suppression de la logique serveur MCP (fonctions et injections retirées)
- [x] Phase 4 : Extraction et Simplification des prompts (Templates J2 créés, config actualisée)
- [x] Configuration FULL MESH des Presets (Tous agents connectés entre eux, Miller = proxy User)

Observations:
- Le système est maintenant "Legacy-free" concernant le référendum.
- Les presets `software_development.json` et `scientific_research_group.json` sont en Full Mesh.
- Les instructions de déconnexion sont concises et chargées depuis `assets/templates/`.

Détails techniques :
- Fichiers modifiés : src/config.py, src/core/server.py, src/core/logic.py, src/interface/app.py, assets/presets/*.json, assets/templates/*.j2.
- Commits à prévoir : `fix: Full mesh presets and final prompt extraction (Phase 4)`.