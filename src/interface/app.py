import streamlit as st
from streamlit_autorefresh import st_autorefresh
import json
import uuid
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from src.core.state import StateStore

st.set_page_config(page_title="Agent Orchestra", page_icon="🤖", layout="wide")

# Initialize State
state_store = StateStore()

# --- HEADER & CONTROLS ---
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🤖 Agent Orchestra Control")
with col2:
    if st.button("🔴 RESET CONVERSATION", type="primary"):
        def reset_logic(s):
            # 1. New ID
            s["conversation_id"] = str(uuid.uuid4())
            # 2. Clear messages
            s["messages"] = []
            # 3. Reset Turn
            s["turn"] = {"current": None, "next": None}
            # 4. Re-apply Config to Agents (Clear status)
            # We preserve the keys but reset status.
            # Actually, better to re-generate from Profiles to ensure consistency.
            config = s.get("config", {})
            profiles = config.get("profiles", [])
            
            new_agents = {}
            total_count = 0
            
            for p in profiles:
                p_name = p.get("name", "Unknown")
                p_count = int(p.get("count", 1))
                p_role = p.get("role_description", "")
                p_comm = p.get("communication_rules", "")
                
                for i in range(1, p_count + 1):
                    agent_id = f"{p_name}_{i}"
                    # Full System Prompt construction
                    full_role = f"{p_role}\n\n[COMMUNICATION RULES]\n{p_comm}"
                    
                    new_agents[agent_id] = {
                        "role": full_role,
                        "status": "pending_connection" 
                    }
                    total_count += 1
            
            s["agents"] = new_agents
            s["config"]["total_agents"] = total_count
            
            return f"Reset Complete. New ID: {s['conversation_id']}"
            
        msg = state_store.update(reset_logic)
        st.success(msg)
        st.rerun()

# --- TABS ---
tab_config, tab_chat = st.tabs(["⚙️ Configuration", "💬 Conversation Reference"])

with tab_config:
    st.header("Simulation Setup")
    
    # Load current config
    current_state = state_store.load()
    config = current_state.get("config", {})
    profiles = config.get("profiles", [
        {"name": "Agent", "count": 2, "role_description": "Helpful assistant.", "communication_rules": "Speak when spoken to."}
    ])
    context = config.get("context", "You are AI agents working together.")
    
    # 1. Global Context
    new_context = st.text_area("Global Shared Context", value=context, height=100)
    
    # 2. Profiles Editor
    st.subheader("Agent Profiles (Cards)")
    
    # We use session_state to manage the list if we want dynamic add/remove,
    # but st.data_editor is easier for v1.
    
    edited_profiles = st.data_editor(
        profiles,
        num_rows="dynamic",
        column_config={
            "name": "Agent Type Name",
            "count": st.column_config.NumberColumn("Count", min_value=1, max_value=10, step=1),
            "role_description": st.column_config.TextColumn("Role", width="large"),
            "communication_rules": st.column_config.TextColumn("Comm Rules", width="large")
        },
        use_container_width=True
    )
    
    # Calc total
    total_agents = 0
    for p in edited_profiles:
        try:
            val = p.get("count", 0)
            if val is None: val = 0
            total_agents += int(val)
        except (ValueError, TypeError):
            pass
            
    st.metric("Total Expected Agents", total_agents)
    
    # Save
    if st.button("💾 Save Configuration"):
        def save_logic(s):
            s.setdefault("config", {})
            s["config"]["profiles"] = edited_profiles
            s["config"]["context"] = new_context
            s["config"]["total_agents"] = total_agents
            return "Configuration Saved."
        
        state_store.update(save_logic)
        st.success("Configuration Saved!")

with tab_chat:
    # Auto-refresh
    count = st_autorefresh(interval=2000, key="chatrefresh")
    
    # Load Data
    data = state_store.load()
    messages = data.get("messages", [])
    agents = data.get("agents", {})
    turn = data.get("turn", {})
    
    # Status Bar
    st.caption(f"Conversation ID: {data.get('conversation_id', 'N/A')}")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Turn", turn.get("current", "Waiting..."))
    c1.metric("Next Up", turn.get("next", "TBD"))
    
    # Agent Status
    connected = sum(1 for a in agents.values() if a.get("status") == "connected")
    total = data.get("config", {}).get("total_agents", "?")
    c2.metric("Connected Agents", f"{connected}/{total}")
    
    # Render Status Grid
    st.subheader("Agent Status")
    cols = st.columns(4)
    for i, (name, info) in enumerate(agents.items()):
        col = cols[i % 4]
        status = info.get("status", "unknown")
        color = "green" if status == "connected" else "red"
        col.markdown(f"**{name}**")
        col.caption(f":{color}[{status}]")
    
    st.divider()
    
    # Chat
    st.subheader("Live Feed")
    for m in messages:
        sender = m.get("from", "Unknown")
        content = m.get("content", "")
        # role = "assistant" if sender != "User" else "user" # Just visual styling
        st.chat_message(name=sender).write(content)
        st.caption(f"Target: {m.get('target', 'all')} | Public: {m.get('public')}")

