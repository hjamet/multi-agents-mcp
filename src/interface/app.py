import streamlit as st
from streamlit_autorefresh import st_autorefresh
import graphviz
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

# --- CSS STYLING ---
st.markdown("""
<style>
    div[data-testid="stSidebar"] {
        background-color: #f0f2f6;
    }
    .stButton button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
    }
    .big-font {
        font-size: 20px !important;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def load_config():
    state = state_store.load()
    config = state.get("config", {})
    if "profiles" not in config:
        config["profiles"] = [
            {"name": "Agent", "description": "Generic Agent", "system_prompt": "You are a helpful assistant.", "connections": [], "count": 1, "capabilities": ["public", "private", "audience"]}
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

def render_graph(profiles, current_editing=None):
    graph = graphviz.Digraph()
    graph.attr(rankdir='LR', size='10,10', bgcolor='transparent')
    
    # Nodes
    for p in profiles:
        name = p["name"]
        color = 'lightblue'
        if current_editing and name == current_editing:
            color = 'gold'
        
        # Show count in label
        count = p.get("count", 0)
        label = f"{name}\n(x{count})"
        
        graph.node(name, label=label, style='filled', fillcolor=color, shape='box', fontsize='10')

    # Edges
    for p in profiles:
        source = p["name"]
        for conn in p.get("connections", []):
            target = conn.get("target")
            # Only draw if target exists
            if any(prof["name"] == target for prof in profiles):
                graph.edge(source, target, fontsize='8', color='gray')

    return graph

# --- NAVIGATION & SIDEBAR ---
if "page" not in st.session_state:
    st.session_state.page = "Cockpit"

with st.sidebar:
    st.title("🤖 Orchestra")
    
    st.markdown("### Navigation")
    
    # Navigation Buttons (Full Width)
    if st.button("🎛️ Simulation Cockpit", use_container_width=True):
        st.session_state.page = "Cockpit"
        st.rerun()
    if st.button("🛠️ Agent Editor", use_container_width=True):
        st.session_state.page = "Editor"
        st.rerun()
    if st.button("💬 Live Chat", use_container_width=True):
        st.session_state.page = "Chat"
        st.rerun()
    
    st.divider()
    st.caption(f"Current Mode: **{st.session_state.page}**")


# --- PAGE 1: AGENT EDITOR ---
if st.session_state.page == "Editor":
    st.header("🛠️ Agent Architect")
    
    state, config = load_config()
    profiles = config.get("profiles", [])
    
    # Top Visualizer
    with st.expander("🕸️ Network Topology (Graph)", expanded=False):
        viz = render_graph(profiles, st.session_state.get("editing_agent_name"))
        st.graphviz_chart(viz, use_container_width=True)
    
    st.divider()
    
    # 1. Select Profile to Edit
    profile_names = [p["name"] for p in profiles]
    profile_names.append("➕ Create New")
    
    col_sel, col_del = st.columns([3, 1])
    selected_name = col_sel.selectbox("Select Agent Profile", profile_names, label_visibility="collapsed")
    
    if selected_name == "➕ Create New":
        current_profile = {"name": "New Agent", "description": "", "system_prompt": "", "connections": [], "count": 1, "capabilities": ["public", "private", "audience"]}
        new_mode = True
        st.session_state.editing_agent_name = "New Agent"
    else:
        current_profile = next((p for p in profiles if p["name"] == selected_name), None)
        new_mode = False
        st.session_state.editing_agent_name = selected_name
        
        if col_del.button("🗑️ Delete"):
            config["profiles"] = [p for p in profiles if p["name"] != selected_name]
            save_config(config)
            st.warning("Deleted.")
            st.rerun()

    
    if current_profile:
        with st.container(border=True):
            # Header
            c1, c2 = st.columns([1, 2])
            new_name = c1.text_input("Name", current_profile.get("name", ""), key="p_name")
            new_desc = c2.text_input("Short Description", current_profile.get("description", ""), key="p_desc")
            
            # System Prompt
            st.markdown("##### System Identity")
            new_prompt = st.text_area("Core Instructions", current_profile.get("system_prompt", ""), height=150, key="p_prompt")
            
            # Capabilities
            st.markdown("##### 🛡️ Capabilities")
            caps = current_profile.get("capabilities", [])
            
            start_caps = caps.copy()
            
            cc1, cc2, cc3, cc4 = st.columns(4)
            has_public = cc1.checkbox("Public Speech", "public" in caps)
            has_private = cc2.checkbox("Private (Direct)", "private" in caps)
            has_audience = cc3.checkbox("Private (Audience)", "audience" in caps)
            has_open = cc4.checkbox("🔓 OPEN MODE", "open" in caps, help="If checked, can talk to ANYONE regardless of connections.")
            
            new_caps = []
            if has_public: new_caps.append("public")
            if has_private: new_caps.append("private")
            if has_audience: new_caps.append("audience")
            if has_open: new_caps.append("open")
            
            # Connections Editor
            st.markdown("##### 🔗 Connections")
            connections = current_profile.get("connections", [])
            
            # Add New
            with st.expander("➕ Add Connection Rule", expanded=not connections):
                c_targ, c_ctx, c_add = st.columns([1, 2, 0.5])
                target_options = [p["name"] for p in profiles if p["name"] != current_profile.get("name")]
                
                target = c_targ.selectbox("Target", target_options, key="new_conn_target") if target_options else None
                context_rule = c_ctx.text_input("Context / Strategy", placeholder="e.g. 'Lie to them'")
                
                if c_add.button("Add"):
                    if target and context_rule:
                        connections.append({"target": target, "context": context_rule})
                        st.rerun()

            # List
            for i, conn in enumerate(connections):
                c_del, c_info = st.columns([0.2, 4])
                if c_del.button("x", key=f"del_c_{i}"):
                    connections.pop(i)
                    st.rerun()
                c_info.success(f"**-> {conn.get('target')}**: {conn.get('context')}")

            # Safe Check: At least one capability
            if not new_caps:
                st.error("⚠️ You must select at least one Capability.")
            
            # Save Actions
            st.divider()
            
            if st.button("💾 Save Profile", type="primary", disabled=not new_caps):
                # Update object
                current_profile["name"] = new_name
                current_profile["description"] = new_desc
                current_profile["system_prompt"] = new_prompt
                current_profile["connections"] = connections
                current_profile["capabilities"] = new_caps
                
                if new_mode:
                    profiles.append(current_profile)
                
                # Check for Rename duplications in 'profiles' list logic (basic ref replacement)
                # Ideally we replace the old object ref in list, which we did.
                
                save_config(config)
                st.toast("Profile Saved!", icon="✅")
                time.sleep(0.5)
                st.rerun()


# --- PAGE 2: COCKPIT ---
elif st.session_state.page == "Cockpit":
    st.header("🎛️ Mission Control")
    
    state, config = load_config()
    profiles = config.get("profiles", [])
    
    # Check Preset Dir
    preset_dir = os.path.join("assets", "presets")
    if not os.path.exists(preset_dir):
        os.makedirs(preset_dir, exist_ok=True)
        
    # Top Visualizer
    with st.expander("🕸️ Network Topology (Graph)", expanded=False):
        viz = render_graph(profiles)
        st.graphviz_chart(viz, use_container_width=True)
    
    # 0. Scenario Manager
    with st.expander("💾 Scenario / Preset Manager", expanded=False):
        # Save
        c_save, c_load = st.columns(2)
        save_name = c_save.text_input("Save As (name)")
        if c_save.button("Save Current Config"):
            if save_name:
                path = os.path.join(preset_dir, f"{save_name}.json")
                with open(path, "w") as f:
                    json.dump(config, f, indent=2)
                st.success(f"Saved to {path}")
        
        # Load
        presets = [f for f in os.listdir(preset_dir) if f.endswith(".json")]
        selected_preset = c_load.selectbox("Load Preset", presets) if presets else None
        if c_load.button("Load Preset") and selected_preset:
            path = os.path.join(preset_dir, selected_preset)
            with open(path, "r") as f:
                new_conf = json.load(f)
            config = new_conf # Update local var
            save_config(new_conf) # Push to state
            st.success(f"Loaded {selected_preset}")
            time.sleep(0.5)
            st.rerun()
    
    st.divider()

    # Context
    st.markdown("##### 🌍 Global Simulation Context")
    global_context = st.text_area("Shared Scenario", config.get("context", ""), height=80, label_visibility="collapsed")
    if global_context != config.get("context", ""):
        if st.button("Update Context"):
            config["context"] = global_context
            save_config(config)
            st.success("Context Updated")
    
    st.divider()
    
    # Grid
    total_agents = get_total_agents(profiles)
    st.markdown(f"### 👥 Active Crew ({total_agents})")
    
    cols = st.columns(3)
    for i, p in enumerate(profiles):
        col = cols[i % 3]
        with col.container(border=True):
            st.markdown(f"#### {p['name']}")
            st.caption(p.get("description", "No description"))
            
            c_minus, c_val, c_plus = st.columns([1, 1, 1])
            count = int(p.get("count", 0))
            
            if c_minus.button("➖", key=f"d_{i}"):
                p["count"] = max(0, count - 1)
                save_config(config)
                st.rerun()
            
            c_val.markdown(f"<h2 style='text-align: center; margin:0;'>{count}</h2>", unsafe_allow_html=True)
            
            if c_plus.button("➕", key=f"i_{i}"):
                p["count"] = count + 1
                save_config(config)
                st.rerun()
            
            # Status line
            caps = p.get("capabilities", [])
            cap_icons = ""
            if "public" in caps: cap_icons += "📢 "
            if "private" in caps: cap_icons += "🔒 "
            if "open" in caps: cap_icons += "🔓 "
            st.text(cap_icons)

    # RESET
    st.markdown("___")
    if st.button("🚀 INITIALIZE / RESET SIMULATION", type="primary", use_container_width=True):
        def reset_logic(s):
            s["conversation_id"] = str(uuid.uuid4())
            s["messages"] = []
            s["turn"] = {"current": None, "next": None}
            s["config"]["context"] = global_context # Ensure context is saved
            
            new_agents = {}
            for p in profiles:
                p_name = p.get("name")
                p_count = int(p.get("count", 0))
                # Store prompt base here, but logic.py will do the rest
                for k in range(1, p_count + 1):
                    agent_id = f"{p_name}_{k}"
                    new_agents[agent_id] = {
                        "role": p.get("system_prompt", ""), 
                        "status": "pending_connection",
                        "profile_ref": p_name
                    }
                    
            s["agents"] = new_agents
            s["config"]["total_agents"] = get_total_agents(profiles)
            return f"Simulation Launched! ID: {s['conversation_id']}"
            
        msg = state_store.update(reset_logic)
        st.success(msg)
        time.sleep(1)
        st.session_state.page = "Chat" # Jump to chat
        st.rerun()


# --- PAGE 3: LIVE CHAT ---
elif st.session_state.page == "Chat":
    st.header("💬 Live Frequency")
    st_autorefresh(interval=2000, key="chatrefresh")
    
    data = state_store.load()
    messages = data.get("messages", [])
    turn = data.get("turn", {})
    agents = data.get("agents", {})
    
    # Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Speaker", turn.get("current", "None"))
    c2.metric("Next", turn.get("next", "TBD"))
    connected = sum(1 for a in agents.values() if a.get("status") == "connected")
    c3.metric("Online", f"{connected}/{data.get('config', {}).get('total_agents', 0)}")
    
    st.divider()
    
    for m in messages:
        sender = m.get("from", "?")
        content = m.get("content", "")
        # Styling based on sender
        with st.chat_message(sender):
            st.write(content)
            meta = f"to {m.get('target', 'all')}"
            if not m.get("public"): meta += " 🔒"
            if m.get("audience"): meta += f" (+{len(m['audience'])})"
            st.caption(meta)
