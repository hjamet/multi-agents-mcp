# Technical Audit & Robustness Plan
**Date:** 2026-01-12
**Author:** Tech Lead

## 1. Fragility Analysis (`src/core/server.py` & `src/core/state.py`)

### A. Path Resolution & Imports
- **Current State**: Uses `sys.path.append(...)` and `os.path.join(..., "..", "..")` quirks to resolve paths.
- **Risk**: High. Moving the entry point or installing as a package in a different environment will break imports and asset loading.
- **Recommendation**: Switch to `pathlib` for robust, platform-independent path handling. Standardize the `src` package to avoid `sys.path` manipulation.

### B. File-Based State Locking (`portalocker`)
- **Current State**: Uses `portalocker` with a retry loop on `state.json`.
- **Risk**: Moderate to High.
    - **Stale Locks**: If a process crashes while holding an exclusive lock (`LOCK_EX`), the entire system may hang until manual intervention.
    - **Contention**: With loose retries and `time.sleep`, high-frequency updates (multiple agents talking) will cause latency spikes.
- **Recommendation**: 
    - Short-term: Implement a "Lock TTL" or "Steal Lock" mechanism if the lock file is too old.
    - Long-term: Migrate to SQLite for atomic, concurrent access without file locking fragility.

## 2. Logic Verification (`src/core/logic.py`)

### A. Turn Management ("The User Exception")
- **Observation**: `post_message` treats `next_agent="User"` as a special case where the turn is *not* passed. The agent retains the turn to wait for a reply.
- **Verdict**: Valid logic for "Human-in-the-loop" but risky. If the User never replies (or the wait times out), the Agent might get stuck or the turn never advances.
- **Fix**: Ensure `wait_for_user` has a strict timeout that defaults to specific fallbacks (e.g., auto-pass turn to PM or self) to prevent deadlock.

### B. Async/Sync Hybrid
- **Observation**: `logic.py` implements both struct `wait_for_turn` (Blocking) and `wait_for_turn_async`. 
- **Risk**: Mixing blocking I/O (file reads) in async loops can starve the event loop. `wait_for_all_agents_async` correctly uses `asyncio.to_thread`, which is good.

## 3. Implementation Plan (Operation Self-Repair)

### Phase 1: Hardening (Immediate)
1. **Refactor Pathing**: Replace `os.path` soup with `pathlib.Path`.
2. **Sanitize Logging**: Replace distributed `print(..., file=sys.stderr)` with the centralized `src.utils.logger`.
3. **Type Safety**: Introduce `TypedDict` or `Pydantic` models for the `state` dictionary to prevent schema drift errors (e.g., missing "config" keys).

### Phase 2: Architecture
1. **State Database**: Evaluate SQLite replacement for `state.json`.
2. **Deadlock Prevention**: Add a "Turn Watchdog" system agent that resets the turn if an agent is silent > 5 minutes.
