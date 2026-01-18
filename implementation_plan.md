# Implementation Plan - Referendum System

## Goal
Replace the "Critique & Alignment" system with a "Referendum Protocol" to enforce critical thinking and consensus via voting.

## Affected Files
- `src/core/logic.py`

## Changes

### `src/core/logic.py`: Replace Critical Instruction
Update `_get_critical_instruction_text` to provide the new Referendum prompt.

**New Content Pattern:**

```python
def _get_critical_instruction_text(state: dict) -> str:
    """Helper to inject Critical Mode instruction."""
    if state.get("config", {}).get("enable_critical_mode", False):
        return """### 🗳️ REFERENDUM PROTOCOL (DISTRIBUTED CONSENSUS)
**MANDATORY**: You are a critical thinker. Use the **Voting System** to flag issues.

**YOUR DUTY (THE VOTE)**:
At the START of your turn, you MUST perform **EXACTLY ONE** of these actions regarding active subjects (or create a new one):
1.  **PROPOSE**: Raise a NEW doubt/issue. (Vote +1)
2.  **SUPPORT**: Agree with an existing doubt. (Vote +1)
3.  **REFUTE**: Disagree with a doubt (minimize issue). (Vote -1)
4.  **RETRACT**: Change your previous vote.

**THE THRESHOLD (SCORE >= 2)**:
If a subject's Total Score reaches **2**, the **Distributed Consensus** has declared it a PRIORITY.
-> You **MUST** stop your current task and address this subject immediately as your **MAIN TOPIC**.

**FORMAT**:
Start your message with this block:

> **🗳️ REFERENDUM STATUS**
>
> | ID | Subject | Score | My Action | Justification |
> | :--- | :--- | :--- | :--- | :--- |
> | #1 | (Subject Title) | **X** | (Action) | (Short Reason) |
> ...

*Rules*:
- **Score**: Positive = Doubt/Problem. Negative = Trusted/Resolved (Cap at -1).
- **Persistence**: Subjects disappear when they leave the Context Window (150 lines).
- **Single Vote**: You cannot vote twice for the same subject.
"""
    return ""
```

## Verification
1.  Review `src/core/logic.py`.
2.  Reload agents.
3.  Verify agents use the table format and respect votes.
