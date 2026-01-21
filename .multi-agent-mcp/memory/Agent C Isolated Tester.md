# Agent C (Isolated Tester) - Session Log (21 Jan 2026 - Reload)

## ✅ Validated
- **Isolation** : Visual isolation confirmed (Only Agent B visible).
- **Tools** : `list_dir` verified working.
- **Protocol** : Private communication with B working. Mailbox pagination handling working.

## 🐛 Issues Identified
1.  **User Mention Fallback (Rebound)** :
    - Scenario: Agent A sent `talk(to='User')`.
    - Result: Turn passed to Agent C (Fallback).
    - Implication: Mentions to `@User` do not reliably transfer the turn or wait for user input.

2.  **Priority Persistence (Turn Stealing)** :
    - Scenario: A mentioned C (+1 Prio). B took the turn (FIFO). C did NOT speak.
    - Result: C retained Priority 1.
    - Impact: Later, B mentioned A (+1 Prio). C (with Prio 1) was selected over A (Prio 1), presumably due to FIFO/Order, stealing the turn intended for A.
    - **Fix Needed**: Priorities should ideally decay or be evaluated differently when an agent is skipped?

## ⏭️ Next Steps
- Investigate `StateStore` logic regarding Priority Reset when an agent *could* speak but *doesn't* (e.g. skipped by FIFO).
- Verify handling of `@User` mentions in `_finalize_turn_transition`.