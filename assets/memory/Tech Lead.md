# Roadmap - Full Stack

## Phase 1: Hardening (CURRENT)
- [x] Standardisation des Chemins (`pathlib`, `src/config.py`)
- [x] Nettoyage des Logs (`src/utils/logger`, remove `sys.stderr`)
- [x] Typage Fort (`src/core/models.py`, `state.py` validation)

## Next Steps
- Await QA validation?
- Implement Phase 2 features (not yet defined).

## Implementation Details
- Created `src/config.py` with `PROJECT_ROOT`, `TEMPLATE_DIR`, `MEMORY_DIR`.
- Refactored `src/core/server.py` and `src/core/state.py` to use config paths.
- Replaced all `print(..., file=sys.stderr)` with `logger.log/error` in `server.py` and `state.py`.
- Added `GlobalState` Pydantic model validation in `StateStore.load()`.
