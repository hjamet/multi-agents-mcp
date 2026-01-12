# Optimizing Streamlit Chat Interface

## User Requirements
1.  **Pagination**: [DONE] Live Chat & Direct Chat -> Show last 10 messages initially. "Load more" button for older ones.
2.  **Design**: [DONE] Improve chat aesthetics.
3.  **Emoji Identity**:
    *   Add emoji selection during Agent creation.
    *   [NEW] **Grid Picker**: Replace text input with a UI grid (WhatsApp style).

## Plan (Updated)
1.  **Modify Agent Editor (`src/interface/app.py`)**:
    *   Define `EMOJI_CATEGORIES` (Faces, Roles/Fantasy, Objects).
    *   Replace `st.text_input` for emoji with a `st.popover`.
    *   Inside the popover, render tabs/grid of buttons.
    *   Callback mechanism to update the profile's emoji logic on click.
    *   Ensure "Save" persists the selection.
