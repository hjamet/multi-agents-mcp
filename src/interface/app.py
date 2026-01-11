import streamlit as st
from streamlit_autorefresh import st_autorefresh
import json
import uuid
import sys
import os
import time

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from src.core.state import StateStore

st.set_page_config(page_title="Agent Orchestra", page_icon="🤖", layout="wide")

# Initialize State
state_store = StateStore()

# --- HELPER FUNCTIONS ---
def load_config():
    state = state_store.load()
    config = state.get("config", {})
    # Ensure structure
    if "profiles" not in config:
        config["profiles"] = [
            {"name": "Agent", "description": "Generic Agent", "system_prompt": "You are a helpful assistant.", "connections": [], "count": 1}
        ]
    return state, config

def save_config(new_config):
    def update_fn(s):
        s["config"] = new_config
        return "Config Saved"
    state_store.update(update_fn)

def get_total_agents(profiles):
    total = 0
    for p in profiles:
        try:
            total += int(p.get("count", 0))
        except:
            pass
    return total

# --- NAVIGATION ---
st.sidebar.title("🤖 Orchestra")
page = st.sidebar.radio("Navigation", ["Editors", "Simulation Cockpit", "Live Chat"])

# --- PAGE 1: AGENT EDITOR ---
if page == "Editors":
    st.header("🛠️ Agent Editor")
    
    state, config = load_config()
    profiles = config.get("profiles", [])
    
    # 1. Select Profile to Edit
    profile_names = [p["name"] for p in profiles]
    profile_names.append("➕ Create New Agent")
    
    selected_name = st.selectbox("Select Agent Profile", profile_names)
    
    if selected_name == "➕ Create New Agent":
        current_profile = {"name": "New Agent", "description": "", "system_prompt": "", "connections": [], "count": 1}
        new_mode = True
    else:
        # Find profile (by index or name)
        current_profile = next((p for p in profiles if p["name"] == selected_name), None)
        new_mode = False
        
    st.divider()
    
    if current_profile:
        with st.container(border=True):
            # Basic Info
            c1, c2 = st.columns([1, 2])
            new_name = c1.text_input("Name", current_profile.get("name", ""), key="p_name")
            new_desc = c2.text_input("Short Description", current_profile.get("description", ""), key="p_desc")
            
            new_prompt = st.text_area("System Prompt", current_profile.get("system_prompt", ""), height=150, key="p_prompt")
            
            # Connections Editor
            st.subheader("🔗 Connections & Strategy")
            st.info("Define how this agent should interact with others.")
            
            connections = current_profile.get("connections", [])
            
            # Simple UI to add connection
            with st.expander("Add New Connection"):
                target_options = [p["name"] for p in profiles if p["name"] != current_profile["name"]]
                if not target_options:
                    st.warning("Create other agents first to link them.")
                else:
                    target = st.selectbox("Target Agent", target_options)
                    context_rule = st.text_input("Context / Rule (e.g. 'Attack at night')")
                    if st.button("Add Link"):
                        connections.append({"target": target, "context": context_rule})
                        st.success(f"Linked to {target}")
                        st.rerun() # Refresh to show in list below

            # List existing connections
            if connections:
                st.write("###### Active Connections:")
                for i, conn in enumerate(connections):
                    c_del, c_info = st.columns([1, 5])
                    if c_del.button("❌", key=f"del_{i}"):
                        connections.pop(i)
                        st.rerun()
                    c_info.markdown(f"**To {conn.get('target')}**: {conn.get('context')}")
            else:
                st.caption("No specific connections definitions.")

            # Save Actions
            st.divider()
            
            if st.button("💾 Save Profile", type="primary"):
                # Update object
                current_profile["name"] = new_name
                current_profile["description"] = new_desc
                current_profile["system_prompt"] = new_prompt
                current_profile["connections"] = connections
                # Count preserves old value or default
                
                if new_mode:
                    profiles.append(current_profile)
                else:
                    # Update info in list (already ref, but good to be explicit if replacing)
                    pass 
                
                save_config(config)
                st.success("Profile Saved!")
                time.sleep(0.5)
                st.rerun()

            if not new_mode:
                if st.button("🗑️ Delete Profile"):
                    config["profiles"] = [p for p in profiles if p["name"] != selected_name]
                    save_config(config)
                    st.warning("Profile Deleted.")
                    time.sleep(0.5)
                    st.rerun()


# --- PAGE 2: COCKPIT ---
elif page == "Simulation Cockpit":
    st.header("🎛️ Simulation Cockpit")
    
    state, config = load_config()
    profiles = config.get("profiles", [])
    
    # 1. Global Context
    st.subheader("🌍 Global Context")
    global_context = st.text_area("Shared Scenario Context", config.get("context", ""), height=100)
    
    if global_context != config.get("context", ""):
        if st.button("Save Global Context"):
            config["context"] = global_context
            save_config(config)
            st.success("Context Updated")
    
    st.divider()
    
    # 2. Agent Cards Grid
    st.subheader("👥 Cast & Crew")
    
    # metrics
    total_agents = get_total_agents(profiles)
    st.metric("Total Agents in Simulation", total_agents)
    
    if not profiles:
        st.warning("No profiles found. Go to Editor to create agents.")
    
    cols = st.columns(3)
    for i, p in enumerate(profiles):
        col = cols[i % 3]
        with col.container(border=True):
            st.markdown(f"### {p['name']}")
            st.caption(p.get("description", "No description"))
            
            # Counter
            c_minus, c_val, c_plus = st.columns([1, 1, 1])
            current_count = int(p.get("count", 0))
            
            if c_minus.button("➖", key=f"dec_{i}"):
                p["count"] = max(0, current_count - 1)
                save_config(config)
                st.rerun()
                
            c_val.markdown(f"<h3 style='text-align: center;'>{current_count}</h3>", unsafe_allow_html=True)
            
            if c_plus.button("➕", key=f"inc_{i}"):
                p["count"] = current_count + 1
                save_config(config)
                st.rerun()
                
            # Mini preview of connections
            n_conns = len(p.get("connections", []))
            st.caption(f"{n_conns} Connection Rules")

    st.divider()
    
    # 3. GLOBAL RESET
    st.markdown("### 🚦 Controls")
    if st.button("🔴 RESET & APPLY CONFIGURATION", type="primary", use_container_width=True):
        def reset_logic(s):
            # 1. ID & Clean
            s["conversation_id"] = str(uuid.uuid4())
            s["messages"] = []
            s["turn"] = {"current": None, "next": None}
            
            # 2. Re-Bootstrap Agents
            new_agents = {}
            for p in profiles:
                p_name = p.get("name")
                p_count = int(p.get("count", 0))
                # For basic registration, we'll store the profile info
                # But wait! We need to handle the 'Role' construction here OR in the logic.
                # Strategy: Store the "Profile Name" in the agent entry. 
                # The logic.py will resolve the full prompt dynamically.
                # BUT logic.py only sees 'agents' dict. 
                # So we must pre-compile the PROMPT here, or ensure logic.py can read 'config.profiles'.
                
                # Let's Compile here for safety and simplicity in logic.py
                # Just base prompt. The "Connections" advice is dynamic in wait_for_turn.
                
                for k in range(1, p_count + 1):
                    agent_id = f"{p_name}_{k}"
                    new_agents[agent_id] = {
                        "role": p.get("system_prompt", ""),
                        "status": "pending_connection",
                        "profile_ref": p_name # Store ref to lookup connections later
                    }
                    
            s["agents"] = new_agents
            s["config"]["total_agents"] = get_total_agents(profiles)
            
            return f"Simulation Reset! New ID: {s['conversation_id']}"
            
        msg = state_store.update(reset_logic)
        st.toast(msg, icon="🚀")
        time.sleep(1)
        st.rerun()


# --- PAGE 3: LIVE CHAT ---
elif page == "Live Chat":
    st.header("💬 Live Frequency")
    
    # Auto-refresh
    st_autorefresh(interval=2000, key="chatrefresh")
    
    data = state_store.load()
    messages = data.get("messages", [])
    turn = data.get("turn", {})
    agents = data.get("agents", {})
    
    # Status Header
    c1, c2, c3 = st.columns(3)
    c1.metric("Status", "🟢 Running" if turn.get("current") else "🟡 Waiting")
    c1.caption(f"ID: {data.get('conversation_id')}")
    c2.metric("Current Speaker", turn.get("current", "None"))
    c2.caption(f"Next: {turn.get('next', '?')}")
    
    connected = sum(1 for a in agents.values() if a.get("status") == "connected")
    total = data.get("config", {}).get("total_agents", 0)
    c3.metric("Network", f"{connected} / {total}")
    
    st.divider()
    
    # Messages
    for m in messages:
        sender = m.get("from", "Unknown")
        target = m.get("target", "all")
        content = m.get("content", "")
        
        with st.chat_message(sender):
            st.write(content)
            # Metadata footer
            meta = f"Target: {target}"
            if not m.get("public"):
                meta += " 🔒 (Private)"
            st.caption(meta)
    
    if not messages:
        st.info("No messages properly recorded yet. Start the agents!")
