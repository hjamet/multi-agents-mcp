# 📋 Product Backlog

## 🏃 Current Sprint: Application Self-Improvement

### 1. System Health Audit & Bug Fixes
- **Status**: ✅ Ready for Release (PO Validated)
- **Tasks**:
    - [x] Refactor Paths to `pathlib`
    - [x] Centralize Logging
    - [x] Pydantic State Schema

### 2. (NEW) UX: Unified Chat Interface
- **As a**: User
- **I want to**: See Direct Messages and Public Chat in a single unified view (or easily togglable)
- **So that**: I don't have to switch pages constantly.
- **Status**: ✅ Released (v1.1.0)
- **Priority**: High (UX Friction)

## 🏃 Sprint 2: Seamless Chat (Discord-like)

### 3. UX: Hybrid Stream & Inline Actions
- **As a**: User
- **I want to**: See a single combined timeline of Public and Private messages, with inline "Reply" buttons.
- **So that**: The experience feels like a modern group chat (Discord/WhatsApp) and I never miss a notification.
- **Details**:
    - "Action Required" messages must be visually distinct (High Visibility).
    - Maintain "Inbox" tab only for async catch-up.
    - Allow sending public/private messages from the same input bar (or inline).
- **Status**: ✅ Released (v1.2.0)
- **Priority**: Critical (User Feedback)

## 🏎️ Sprint 3: Advanced Chat Interaction

### 4. UX: Modern Input & Key Bindings (Discord-like)
- **As a**: User
- **I want to**: Send messages via `Enter` (Shift+Enter for newline) and use a sleek input bar instead of an Accordion/Button.
- **So that**: Chatting feels fast and native.
- **Details**:
    - Remove "Universal Transmitter" accordion.
    - Implement streamlined Input Bar.
    - Small round send button.
- **Status**: ✅ Ready for Release
- **Priority**: High (UX/DX)

### 5. Logic: Mentions & Contextual Replies
- **As a**: User
- **I want to**: Target agents using `@Name` mentions and Reply to specific messages with context.
- **So that**: I don't have to fiddle with dropdowns and the Agent knows exactly what I'm answering.
- **Details**:
    - **@Mentions**: Parse message content for `@AgentName` to set `target` automatically.
    - **Quoted Reply**: Clicking "Reply" on a message captures its ID/Content as context for the new message.
    - **Data Model**: Ensure `reply_to` context is passed to the Agent via MCP.
- **Status**: ✅ Released (v1.3.0)
- **Priority**: High (UX/DX)

## 💎 Sprint 4: Polish & Ergonomics

### 6. UX: Sticky Roster & Layout
- **Status**: ✅ Released (v1.5.0)
- **Priority**: High

### 7. UX: Single-Page Focus
- **Status**: ✅ Released (v1.5.0)
- **Priority**: High

### 8. Feature: Universal Reply
- **Status**: ✅ Released (v1.5.0)
- **Priority**: High

### 9. Feature: Mention Autocomplete & Visuals
- **Details**: Implemented `format_mentions` visualizer.
- **Status**: ✅ Released (v1.5.0)
- **Priority**: Medium

## 🧊 Icebox
(Empty)
