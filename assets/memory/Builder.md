# CONTEXT - BUILDER (13 Jan 2026)

## 🎯 Current Mission: HIGH-VISIBILITY UX
- **Objective**: Improve mention visibility ("Discord Feeling") and user alerting.
- **Status**: ✅ IMPLEMENTED.

## 🛠️ Technical Changes
1.  **`src/interface/app.py`**:
    -   **Mentions**: Updated `format_mentions` regex for Blurple/Bold styling.
    -   **Alerting**: Added logic to count unread mentions to User and display a warning head (`🔔 3 mentions...`) above the stream.
    -   **Direct Messages**: Strengthened border styling (`3px solid #ff9800`) + Shadow for unread items.

## 📝 Decisions
- Used standard Discord Blurple (`#5865F2`) for familiarity.
- Used Orange/Amber for "Action Required" borders to signify urgency without being alarmist (Red).

## ⏭️ Next Step
- Handover to **🧨 Challenger** for UI Review.
