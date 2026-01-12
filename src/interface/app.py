import streamlit as st
from streamlit_autorefresh import st_autorefresh
import graphviz
import json
import uuid
import sys
import os
import time

# Add src to path
# Add src to path to allow imports if run directly
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
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
EMOJI_CATEGORIES = {
    "Smileys & People": ["😀", "😃", "😄", "😁", "😆", "😅", "😂", "🤣", "🥲", "☺️", "😊", "😇", "🙂", "🙃", "😉", "😌", "😍", "🥰", "😘", "😗", "😙", "😚", "😋", "😛", "😝", "😜", "🤪", "🤨", "🧐", "🤓", "😎", "🥸", "🤩", "🥳", "😏", "😒", "😞", "😔", "😟", "😕", "🙁", "☹️", "😣", "😖", "😫", "😩", "🥺", "😢", "😭", "😤", "😠", "😡", "🤬", "🤯", "😳", "🥵", "🥶", "😱", "😨", "😰", "😥", "😓", "🤗", "🤔", "🤭", "🤫", "🤥", "😶", "😐", "😑", "😬", "🙄", "😯", "😦", "😧", "😮", "😲", "🥱", "😴", "🤤", "😪", "😵", "🤐", "🥴", "🤢", "🤮", "🤧", "😷", "🤒", "🤕", "🤑", "🤠", "😈", "👿", "👹", "👺", "🤡", "💩", "👻", "💀", "☠️", "👽", "👾", "🤖", "🎃", "😺", "😸", "😹", "😻", "😼", "😽", "🙀", "😿", "😾"],
    "Roles & Fantasy": ["🐺", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐮", "🐷", "🐸", "🐵", "🐔", "🐧", "🐦", "🐤", "🦅", "🦉", "🦇", "🐝", "🪱", "🐛", "🦋", "🐌", "🐞", "🐜", "🪰", "🪲", "🪳", "🦟", "🦗", "🕷️", "🕸️", "🦂", "🐢", "🐍", "🦎", "🦖", "🦕", "🐙", "🦑", "🦐", "🦞", "🦀", "🐡", "🐠", "🐟", "🐬", "🐳", "🐋", "🦈", "🐊", "🐅", "🐆", "🦓", "🦍", "🦧", "🦣", "🐘", "🦛", "🦏", "🐪", "🐫", "🦒", "🦘", "🦬", "🐃", "🐂", "🐄", "🐎", "🐖", "🐏", "🐑", "🦙", "🐐", "🦌", "🐕", "🐩", "🦮", "🐕‍🦺", "🐈", "🐈‍⬛", "🐓", "🦃", "🦚", "🦜", "🦢", "🦩", "🕊️", "🐇", "🦝", "🦨", "🦡", "🦫", "🦦", "🦥", "🐁", "🐀", "🐿️", "🦔", "🐾", "🐉", "🐲", "🧙", "🧚", "🧛", "🧜", "🧝", "🧞", "🧟", "👼", "🤴", "👸", "👮", "🕵️", "💂", "🥷", "👳", "🤵", "👰"],
    "Objects & Symbols": ["💡", "💣", "💤", "💥", "💦", "💨", "💫", "🗨️", "👁️‍🗨️", "💍", "💎", "👑", "👒", "🎩", "🎓", "🧢", "⛑️", "📿", "💄", "🏹", "🗡️", "⚔️", "🛡️", "🔮", "🧿", "🩹", "💊", "🧬", "🔭", "🔬", "🩸", "🖼️", "🎭", "🎰", "🚂", "🚓", "🚑", "🚒", "🛸", "🚀", "🛶", "⚓", "🚧", "🚦", "🛑", "🔔", "📣", "📢", "🎙️", "🎤", "🎧", "📻", "🎷", "🎸", "🎹", "🎺", "🎻", "🪕", "🥁", "📱", "📲", "☎️", "📞", "📟", "📠", "🔋", "🔌", "💻", "🖥️", "🖨️", "⌨️", "🖱️", "🖲️", "💽", "💾", "💿", "📀", "🧮", "🎥", "🎞️", "📽️", "🎬", "📺", "📷", "📸", "📹", "📼", "🔍", "🔎", "🕯️", "💡", "🔦", "🏮", "📔", "📕", "📖", "📗", "📘", "📙", "📚", "📓", "📒", "📃", "📜", "📄", "📰", "🗞️", "📑", "🔖", "🏷️", "💰", "💴", "💵", "💶", "💷", "🪙", "💸", "💳", "🧾", "✉️", "📧", "📨", "📩", "📤", "📥", "📦", "📫", "📪", "📬", "📭", "📮", "🗳️", "✏️", "✒️", "🖋️", "🖊️", "🖌️", "🖍️", "📝", "💼", "📁", "📂", "🗂️", "📅", "📆", "🗒️", "🗓️", "📇", "📈", "📉", "📊", "📋", "📌", "📍", "📎", "🖇️", "📏", "📐", "✂️", "🗃️", "🗄️", "🗑️"]
}

def load_config():
    state = state_store.load()
    config = state.get("config", {})
    if "profiles" not in config:
        config["profiles"] = [
            {"name": "Agent", "description": "Generic Agent", "emoji": "🤖", "system_prompt": "You are a helpful assistant.", "connections": [], "count": 1, "capabilities": ["public", "private", "audience"]}
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
    # Banner style: Landscape, fixed height constraint
    graph.attr(rankdir='LR', size='12,2', ratio='fill', bgcolor='transparent', margin='0')
    
    # Nodes
    for p in profiles:
        name = p["name"]
        color = 'lightblue'
        if current_editing and name == current_editing:
            color = 'gold'
        
        # Show count in label
        count = p.get("count", 0)
        label = f"{name}\n(x{count})"
        
        graph.node(name, label=label, style='filled', fillcolor=color, shape='box', fontsize='10', height='0.5')

    # Edges
    for p in profiles:
        source = p["name"]
        for conn in p.get("connections", []):
            target = conn.get("target")
            # Only draw if target exists
            # Only draw if target exists AND is authorized
            is_auth = conn.get("authorized", True)
            if is_auth and any(prof["name"] == target for prof in profiles):
                graph.edge(source, target, fontsize='8', color='gray', arrowsize='0.5')

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
    # NEW PAGE
    if st.button("📱 Direct Chat", use_container_width=True):
        st.session_state.page = "Direct"
        st.rerun()

    st.divider()
    
    # --- FIX MCP CONFIG ---
    with st.expander("🔧 MCP Fix"):
        st.caption("Fixes the absolute path in mcp_config.json")
        if st.button("Update Config Path"):
            import subprocess
            
            # 1. Update JSON
            try:
                config_path = os.path.expanduser("~/.gemini/antigravity/mcp_config.json")
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        data = json.load(f)
                    
                    # Update directory to CURRENT absolute path
                    current_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                    
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        data = json.load(f)
                    
                    # Update directory to CURRENT absolute path
                    current_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                    server_script = os.path.join(current_dir, "src", "core", "server.py")
                    
                    # Robust Command: cd [DIR] && uv run python [SCRIPT]
                    command_str = f"cd {current_dir} && uv run python {server_script}"
                    
                    if "mcpServers" not in data:
                        data["mcpServers"] = {}
                        
                    data["mcpServers"]["multi-agents-mcp"] = {
                        "command": "sh",
                        "args": ["-c", command_str],
                        "env": {}
                    }
                    
                    with open(config_path, "w") as f:
                        json.dump(data, f, indent=2)
                    
                    st.success(f"Updated Config with Robust Path: {current_dir}")
                    st.info("✅ Patched with 'sh -c' wrapper. Compatible with all uv versions.")
                    st.info("⚠️ Please Reload/Restart your MCP Client to apply.")
                        
                else:
                    st.error(f"Config file not found: {config_path}")
            except Exception as e:
                st.error(f"Error: {e}")

            # 2. Check UV Version (Info Only)
            try:
                res = subprocess.run(["uv", "--version"], capture_output=True, text=True)
                version = res.stdout.strip().split(" ")[1]
                st.caption(f"uv version: {version}")
            except:
                pass        # --- MEMORY MANAGEMENT ---
    with st.expander("🧠 Memory Management"):
        st.caption("Manage agent persistent memories.")
        if st.button("🗑️ Delete All Memories"):
            try:
                mem_dir = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "memory")
                if os.path.exists(mem_dir):
                    import shutil
                    # Iterate files to keep directory
                    for filename in os.listdir(mem_dir):
                        file_path = os.path.join(mem_dir, filename)
                        try:
                            if os.path.isfile(file_path) or os.path.islink(file_path):
                                os.unlink(file_path)
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                        except Exception as e:
                            print(f'Failed to delete {file_path}. Reason: {e}')
                    st.success("All memories cleared.")
                else:
                    st.info("No memory directory found.")
            except Exception as e:
                st.error(f"Error: {e}")

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
    # Sync Logic for External Navigation (e.g. from Cockpit)
    # If 'editing_agent_name' (Intent) differs from 'agent_editor_selector' (Widget), 
    # and the Intent is valid, we force-update the Widget.
    intent = st.session_state.get("editing_agent_name")
    
    # Map internal "New Agent" state to UI "Create New" option
    if intent == "New Agent" and "New Agent" not in profile_names:
        intent = "➕ Create New"

    if intent and intent in profile_names:
        if st.session_state.get("agent_editor_selector") != intent:
            st.session_state["agent_editor_selector"] = intent

    def on_selector_change():
        val = st.session_state.agent_editor_selector
        if val == "➕ Create New":
            st.session_state.editing_agent_name = "New Agent"
        else:
            st.session_state.editing_agent_name = val

    selected_name = col_sel.selectbox(
        "Select Agent Profile", 
        profile_names, 
        key="agent_editor_selector", 
        on_change=on_selector_change,
        label_visibility="collapsed"
    )
    
    if selected_name == "➕ Create New":
        current_profile = {"name": "New Agent", "description": "", "system_prompt": "", "connections": [], "count": 1, "capabilities": ["public", "private", "audience"]}
        new_mode = True
        st.session_state.editing_agent_name = "New Agent" # Redundant but safe
        k_suffix = "new"
    else:
        current_profile = next((p for p in profiles if p["name"] == selected_name), None)
        new_mode = False
        st.session_state.editing_agent_name = selected_name
        k_suffix = selected_name
        
        if col_del.button("🗑️ Delete"):
            config["profiles"] = [p for p in profiles if p["name"] != selected_name]
            save_config(config)
            st.warning("Deleted.")
            st.rerun()

    
    if current_profile:
        with st.container(border=True):
            # Header
            st.markdown(f"### ✏️ Editing: {current_profile.get('name', 'New')}")
            
            c1, c2, c_emoji = st.columns([3, 3, 1])
            # Dynamic keys force refresh
            new_name = c1.text_input("Internal Profile Name", current_profile.get("name", ""), key=f"p_name_{k_suffix}", help="Used for Admin Logic and Connections (e.g. 'LoupGarou').")
            # Display Name
            # Default to empty if not set, let placeholder show the fallback
            d_val = current_profile.get("display_name", "")
            display_name = c2.text_input("Public Display Name", d_val, placeholder=f"Par défaut: {new_name}", key=f"p_disp_{k_suffix}", help="Base name shown in chat (e.g. 'Habitant').")
            # Emoji Picker
            current_emoji = current_profile.get("emoji", "🤖")
            
            # Use Popover for "WhatsApp-style" grid
            with c_emoji:
                st.markdown("Avatar")
                # Using a container or columns to keep label alignment
                popover = st.popover(f"{current_emoji} Change")
                
                # Hidden/State input to store the selection for Save
                # We initialize it with current, but if a button in popover is clicked, we need to update this.
                # Since st.button rerun, we rely on session_state to persist the "new_emoji_selection".
                
                emoji_key = f"selected_emoji_{k_suffix}"
                if emoji_key not in st.session_state:
                    st.session_state[emoji_key] = current_emoji
                
                # Determine 'new_emoji' from session state
                new_emoji = st.session_state[emoji_key]
                
                with popover:
                    st.markdown("### Select an Avatar")
                    tabs = st.tabs(list(EMOJI_CATEGORIES.keys()))
                    
                    for i, (cat_name, emojis) in enumerate(EMOJI_CATEGORIES.items()):
                        with tabs[i]:
                            # Render grid (e.g. 8 columns)
                            cols = st.columns(8)
                            for idx, emo in enumerate(emojis):
                                with cols[idx % 8]:
                                    if st.button(emo, key=f"emo_{k_suffix}_{i}_{idx}"):
                                         st.session_state[emoji_key] = emo
                                         st.rerun()
                
                # Show selection feedback
                st.caption(f"Selected: {new_emoji}")

            c3, c4 = st.columns(2)
            new_desc = c3.text_input("Admin Description (Internal)", current_profile.get("description", ""), key=f"p_desc_{k_suffix}", help="Note for you (e.g. 'The Bad Guy').")
            p_val = current_profile.get("public_description", "")
            public_desc = c4.text_input("Public Description (All)", p_val, placeholder=f"Par défaut: {new_desc}", key=f"p_pubdesc_{k_suffix}", help="Visible to other agents (e.g. 'Simple Villager').")
            
            # System Prompt
            st.markdown("##### 🎭 System Prompt (Private Role)")
            new_prompt = st.text_area("Instructions", current_profile.get("system_prompt", ""), height=150, key=f"p_prompt_{k_suffix}")
            
            # Capabilities
            st.markdown("##### 🛡️ Capabilities")
            caps = current_profile.get("capabilities", [])
            
            cc1, cc2, cc3, cc4 = st.columns(4)
            has_public = cc1.checkbox("Public Speech", "public" in caps, key=f"cap_pub_{k_suffix}")
            has_private = cc2.checkbox("Private (Direct)", "private" in caps, key=f"cap_priv_{k_suffix}")
            has_audience = cc3.checkbox("Private (Audience)", "audience" in caps, key=f"cap_aud_{k_suffix}")
            has_open = cc4.checkbox("🔓 OPEN MODE", "open" in caps, help="If checked, can talk to ANYONE regardless of connections.", key=f"cap_open_{k_suffix}")
            
            new_caps = []
            if has_public: new_caps.append("public")
            if has_private: new_caps.append("private")
            if has_audience: new_caps.append("audience")
            if has_open: new_caps.append("open")
            
            # Connections Editor (Data Table)
            st.markdown("##### 🔗 Connections & Strategy")
            st.caption("Manage communication rules. Check 'Authorized' to allow standard communication.")
            
            # 1. Build Data for Table
            # Targets: All other profiles + User + Public
            potential_targets = [p["name"] for p in profiles if p["name"] != current_profile.get("name")]
            potential_targets.append("User")
            potential_targets.insert(0, "Public") # Top of list
            
            # Current Config Map
            connections = current_profile.get("connections", [])
            curr_map = {c["target"]: c for c in connections}
            
            table_data = []
            for t in potential_targets:
                existing = curr_map.get(t, {})
                # Default authorized:
                # If it exists in old config (which had no auth flag), it was authorized.
                # If it's a new row (not in config), it's unauthorized by default.
                is_auth = existing.get("authorized", True) if t in curr_map else False
                ctx_text = existing.get("context", "")
                
                table_data.append({
                    "Authorized": is_auth,
                    "Target": t,
                    "Context": ctx_text
                })
            
            # 2. Render Editor
            # We use a column config to make Target read-only
            edited_data = st.data_editor(
                table_data,
                column_config={
                    "Authorized": st.column_config.CheckboxColumn(
                        "Authorized",
                        help="Check to allow communication in Standard Mode.",
                        default=False,
                    ),
                    "Target": st.column_config.TextColumn(
                        "Target Agent",
                        disabled=True
                    ),
                    "Context": st.column_config.TextColumn(
                        "Strategy / Notes",
                        help="Context provided to the agent about this relationship.",
                        width="large"
                    )
                },
                hide_index=True,
                use_container_width=True,
                key=f"conn_editor_{k_suffix}" # Unique key per profile to avoid state bleed
            )
            
            # 3. Update Connections Object for Save
            # We replace the 'connections' list with the state from the table.
            # We save ALL rows (even unauthorized) to persist the Context/Check state.
            new_connections = []
            for row in edited_data:
                new_connections.append({
                    "target": row["Target"],
                    "context": row["Context"],
                    "authorized": row["Authorized"]
                })
            
            # Assign back to variable used in Save
            connections = new_connections

            # Safe Check: At least one capability
            if not new_caps:
                st.error("⚠️ You must select at least one Capability.")
            
            # Save Actions
            st.divider()
            
            if st.button("💾 Save Profile", type="primary", disabled=not new_caps, key=f"save_btn_{k_suffix}"):
                old_name = current_profile.get("name")
                
                # Update object
                current_profile["name"] = new_name
                current_profile["emoji"] = new_emoji
                current_profile["description"] = new_desc
                current_profile["display_name"] = display_name
                current_profile["public_description"] = public_desc
                current_profile["system_prompt"] = new_prompt
                current_profile["connections"] = connections
                current_profile["capabilities"] = new_caps
                # Remove legacy
                current_profile.pop("instance_names", None)
                
                # SMART RENAMING LOGIC
                if not new_mode and old_name and new_name != old_name:
                    # Rename references in other profiles
                    count_migrations = 0
                    for p in profiles:
                        for conn in p.get("connections", []):
                            if conn.get("target") == old_name:
                                conn["target"] = new_name
                                count_migrations += 1
                    if count_migrations > 0:
                        st.toast(f"Smart Rename: Updated {count_migrations} connections pointing to '{old_name}' -> '{new_name}'", icon="🔄")
                
                if new_mode:
                    profiles.append(current_profile)
                
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
            c_head, c_edit = st.columns([5, 1])
            c_head.markdown(f"#### {p['name']}")
            if c_edit.button("✏️", key=f"edit_btn_{i}", help=f"Edit {p['name']}"):
                st.session_state.editing_agent_name = p["name"]
                st.session_state.page = "Editor"
                st.rerun()
            st.caption(p.get("description", "No description"))
            st.info(f"Public: **{p.get('display_name', p['name'])}**")
            
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
    
    # 0.5 Starter Selection
    profile_names = [p["name"] for p in profiles]
    col_start, col_opt = st.columns([2, 1])
    starter_role = col_start.selectbox("🏁 Entry Point (First Turn)", profile_names) if profile_names else None
    clear_memories = col_opt.checkbox("Clear Agent Memories?", value=False, help="If checked, deletes all agent note files.")

    if st.button("🚀 INITIALIZE / RESET SIMULATION", type="primary", use_container_width=True):
        def reset_logic(s):
            # 0. Memory Cleanup
            if clear_memories:
                 try:
                    mem_dir = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "memory")
                    if os.path.exists(mem_dir):
                        for filename in os.listdir(mem_dir):
                            file_path = os.path.join(mem_dir, filename)
                            if os.path.isfile(file_path):
                                os.unlink(file_path)
                 except Exception as e:
                     print(f"Memory Cleanup Error: {e}")

            s["conversation_id"] = str(uuid.uuid4())
            s["messages"] = []
            s["turn"] = {"current": None, "next": None}
            s["config"]["context"] = global_context # Ensure context is saved
            
            # 1. Collect all slots
            pending_slots = []
            import random
            
            for p in profiles:
                p_count = int(p.get("count", 0))
                for _ in range(p_count):
                    pending_slots.append({
                        "profile_ref": p["name"],
                        "role": p.get("system_prompt", ""),
                        "display_base": p.get("display_name") or p["name"],
                        "emoji": p.get("emoji", "🤖")
                    })
            
            # 2. Shuffle
            random.shuffle(pending_slots)
            
            # 3. Assign IDs
            new_agents = {}
            counters = {}
            
            for slot in pending_slots:
                base = slot["display_base"]
                counters.setdefault(base, 0)
                counters[base] += 1
                
                # Check duplication
                total_base = sum(1 for sl in pending_slots if sl["display_base"] == base)
                
                if total_base > 1:
                    agent_id = f"{base} #{counters[base]}"
                else:
                    agent_id = base
                    
                new_agents[agent_id] = {
                    "role": slot["role"], 
                    "status": "pending_connection",
                    "profile_ref": slot["profile_ref"],
                    "emoji": slot["emoji"]
                }
                    
            s["agents"] = new_agents
            s["config"]["total_agents"] = get_total_agents(profiles)
            
            # --- 4. Omniscience for MaitreDuJeu (Sync with setup_werewolf.py) ---
            mj_real_id = None
            for aid, d in new_agents.items():
                if d["profile_ref"] == "MaitreDuJeu":
                    mj_real_id = aid
                    break
            
            if mj_real_id:
                mj_conns = []
                for other_id, other_data in new_agents.items():
                    if other_id == mj_real_id: continue
                    p_ref = other_data["profile_ref"]
                    # Find profile for description
                    p_desc = next((p["description"] for p in profiles if p["name"] == p_ref), p_ref)
                    mj_conns.append({"target": other_id, "context": f"Identité réelle: {p_desc}"})
                new_agents[mj_real_id]["connections"] = mj_conns
            
            # 4. Set Entry Point
            found_starter = None
            if starter_role:
                # Find first agent matching this profile
                for aid, adata in new_agents.items():
                    if adata.get("profile_ref") == starter_role:
                        found_starter = aid
                        break
            
            if found_starter:
                s["turn"]["current"] = found_starter
                sys_msg = f"🟢 Simulation Started. First turn assigned to **{found_starter}**."
            else:
                sys_msg = "🟢 Simulation Started. Waiting for agents..."
                
            s["messages"].append({
                "from": "System",
                "content": sys_msg,
                "public": True,
                "timestamp": time.time()
            })

            return f"Simulation Launched! ID: {s['conversation_id']}"
            
        msg = state_store.update(reset_logic)
        st.success(msg)
        time.sleep(1)
        st.session_state.page = "Chat" # Jump to chat
        st.rerun()


# --- PAGE 3: LIVE CHAT (OBSERVER) ---
elif st.session_state.page == "Chat":
    # 1. Header & Controls
    col_head, col_act = st.columns([4, 1])
    with col_head:
        st.header("💬 Neural Link (Observer)")
    with col_act:
        if st.button("🔄 Force Refresh"):
            st.rerun()
            
    # Auto-refresh (keep interval reasonable)
    st_autorefresh(interval=3000, key="chatrefresh")
    
    state, config = load_config()
    profiles = config.get("profiles", [])
    
    # 2. visualizers
    with st.expander("🕸️ Network Topology", expanded=False):
        viz = render_graph(profiles)
        st.graphviz_chart(viz, use_container_width=True)

    # 3. Load Live Data
    data = state_store.load()
    messages = data.get("messages", [])
    turn = data.get("turn", {})
    agents = data.get("agents", {})
    
    # 5. Chat Stream
    st.markdown("### 📜 Communication Log")
    
    # --- PAGINATION LOGIC ---
    if "live_chat_limit" not in st.session_state:
        st.session_state.live_chat_limit = 10
    
    total_msgs = len(messages)
    limit = st.session_state.live_chat_limit
    
    # Show "Load More" if there are more messages hidden
    if total_msgs > limit:
        if st.button(f"⬆️ Load Previous Messages ({total_msgs - limit} hidden)", key="load_more_live"):
            st.session_state.live_chat_limit += 10
            st.rerun()
            
    # Slicing: Get the last 'limit' messages
    # Messages are usually appended, so valid slice is starts from max(0, total - limit)
    start_idx = max(0, total_msgs - limit)
    visible_messages = messages[start_idx:]
    
    for m in visible_messages:
        sender = m.get("from", "?")
        content = m.get("content", "")
        
        # Determine Visual Style
        # Public: Transparent/Default
        # Private: Blue tint
        is_public = m.get('public', False)
        
        # Retrieve Sender Logic
        agent_info = agents.get(sender, {})
        sender_emoji = agent_info.get("emoji", "🤖") if sender != "System" else "💾"
        
        # Override for System
        if sender == "System":
             with st.chat_message(sender, avatar=sender_emoji):
                 st.markdown(f"**{sender}**: {content}")
        else:
            # Metadata Construction
            target = m.get('target', '?')
            audiences = m.get("audience", [])
            profile_ref = agent_info.get("profile_ref", "Unknown")
            
            meta_parts = [f"**{sender}** ({profile_ref})"]
            
            if is_public:
                meta_parts.append("📢 **PUBLIC**")
                msg_bg = "transparent" # Default
            else:
                meta_parts.append(f"🔒 **PRIVATE** to **{target}**")
                if audiences:
                     meta_parts.append(f"(cc: {', '.join(audiences)})")
                msg_bg = "#e3f2fd" # Light Blue for private
            
            meta_str = " | ".join(meta_parts)
            
            # Use st.chat_message for avatar handling + Custom rendering inside
            with st.chat_message(sender, avatar=sender_emoji):
                # We can't easily change the bubble bg color in st.chat_message without hacky CSS.
                # But we can style the content inside.
                
                # Header
                st.caption(meta_str)
                
                # Content Body
                if not is_public:
                    # distinct visualization for private
                    st.markdown(f"""
                    <div style="
                        background-color: {msg_bg}; 
                        padding: 10px; 
                        border-radius: 8px; 
                        border-left: 4px solid #2196f3;
                    ">
                        {content}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(content)

    st.divider()

    # 4. Mission Dashboard
    connection_status = "🔴 OFFLINE"
    connected_count = sum(1 for a in agents.values() if a.get("status") == "connected")
    total_required = data.get('config', {}).get('total_agents', 0)
    
    if connected_count >= total_required and total_required > 0:
        connection_status = "🟢 ONLINE"
    elif connected_count > 0:
        connection_status = "🟡 CONNECTING..."
        
    st.markdown("### 🛰️ Uplink Status")
    
    # Status Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Status", connection_status)
    m2.metric("Connected", f"{connected_count}/{total_required}")
    m3.metric("Current Speaker", turn.get("current", "None"))
    m4.metric("Next Up", turn.get("next", "Wait..."))
    
    st.markdown("---")

    # 6. Active Roles
    st.markdown("### 🎭 Active Roles & Stats")

    if not agents:
        st.info("No agents configured. Go to Cockpit to start.")
    else:
        # Sort agents
        agent_names = sorted([k for k in agents.keys() if k != "User"]) # Exclude User from this list
        
        with st.container():
            cols = st.columns(4)
            for i, name in enumerate(agent_names):
                col = cols[i % 4]
                
                info = agents[name]
                status = info.get("status", "pending_connection")
                role_text = info.get("role", "No Role Assigned")
                role_excerpt = (role_text[:75] + '..') if len(role_text) > 75 else role_text
                
                is_turn = (turn.get("current") == name)
                
                profile_ref = info.get("profile_ref", "")
                display_html = name
                if profile_ref and profile_ref not in name:
                     display_html += f"<br><span style='font-size:0.8em; font-weight:normal; color:#666'>({profile_ref})</span>"
                
                bg_color = "#f8f9fa"
                border_color = "#dee2e6"
                status_icon = "💤" 
                status_label = "WAITING"
                text_color = "#adb5bd"
                box_shadow = "none"
                opacity = "0.7"
                
                if status == "connected":
                    opacity = "1.0"
                    if is_turn:
                        bg_color = "#fff3cd"
                        border_color = "#ffecb5"
                        status_icon = "🗣️"
                        status_label = "ACTIVE"
                        text_color = "#856404"
                        box_shadow = "0 4px 6px rgba(0,0,0,0.1)"
                    else:
                        bg_color = "#d1e7dd"
                        border_color = "#badbcc"
                        status_icon = "✅"
                        status_label = "READY"
                        text_color = "#0f5132"
                elif status.startswith("sleeping"):
                    opacity = "0.9"
                    bg_color = "#e2e3f5" # Purple tint
                    border_color = "#d6d8db"
                    status_icon = "💤"
                    status_label = status.upper() # SLEEPING: 5S
                    text_color = "#383d41"
                    box_shadow = "inset 0 0 10px rgba(0,0,0,0.05)"
                
                with col:
                    st.markdown(f"""
                    <div style="
                        background-color: {bg_color};
                        border: 1px solid {border_color};
                        border-radius: 6px;
                        padding: 12px;
                        margin-bottom: 12px;
                        height: 120px;
                        box-shadow: {box_shadow};
                        opacity: {opacity};
                        display: flex; flex-direction: column; justify-content: space-between;
                    ">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                            <span style="font-weight:bold; color:#000; line-height:1.1;">{display_html}</span>
                            <span style="font-size:1.2em;">{status_icon}</span>
                        </div>
                        <div style="font-size:0.75em; color:{text_color}; font-weight:800; letter-spacing:1px; margin-top:4px;">{status_label}</div>
                        <div style="font-size:0.7em; color:#666; font-style:italic; line-height:1.2; overflow:hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;">
                            {role_excerpt}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

# --- PAGE 4: DIRECT CHAT ---
elif st.session_state.page == "Direct":
    st.header("📱 Direct Chat (User Terminal)")
    
    st_autorefresh(interval=3000, key="directchatrefresh")
    
    state, config = load_config()
    
    # Load Live Data
    data = state_store.load()
    messages = data.get("messages", [])
    turn = data.get("turn", {})
    profiles = config.get("profiles", [])
    
    # 0. Sidebar Control: Availability
    with st.sidebar:
        st.divider()
        st.markdown("### 🚦 Status Utilisateur")
        
        # Load current status or default
        current_status = config.get("user_availability", "busy") # default busy to be safe/non-blocking
        is_avail = (current_status == "available")
        
        # Toggle
        new_avail = st.toggle("Disponible pour discuter ?", value=is_avail, help="Si activé, les agents attendront votre réponse avant de continuer.")
        
        status_label = "🟢 DISPONIBLE" if new_avail else "🔴 OCCUPÉ"
        st.caption(f"Statut: **{status_label}**")
        
        # Save if changed
        new_status_str = "available" if new_avail else "busy"
        if new_status_str != current_status:
            config["user_availability"] = new_status_str
            save_config(config)
            st.rerun()

    # 1. Sidebar: Select who I am chatting with?
    # Actually, User chats with the system. We should filter messages relevant to User.
    # Relevant = Public OR Private to "User" OR From "User"
    
    # Render Chat Log
    st.markdown("### 📥 Inbox (Tâches en attente)")
    
    # Filter messages addressed to User
    all_inbox_messages = []
    for i, m in enumerate(messages):
        if m.get("target") == "User":
            all_inbox_messages.append((i, m))
    
    # Sort by timestamp desc (Newest first)
    all_inbox_messages.sort(key=lambda x: x[1].get("timestamp", 0), reverse=True)
    
    # --- PAGINATION LOGIC ---
    if "direct_chat_limit" not in st.session_state:
        st.session_state.direct_chat_limit = 10
        
    limit = st.session_state.direct_chat_limit
    total_inbox = len(all_inbox_messages)
    
    visible_inbox = all_inbox_messages[:limit]
    
    if total_inbox > limit:
         if st.button(f"⬇️ Load Older Messages ({total_inbox - limit} remaining)", key="load_more_direct"):
             st.session_state.direct_chat_limit += 10
             st.rerun()

    if not visible_inbox:
        st.info("Aucun message reçu pour le moment.")
    
    for real_idx, m in visible_inbox:
        sender = m.get("from", "?")
        content = m.get("content", "")
        timestamp = m.get("timestamp", 0)
        is_replied = m.get("replied", False)
        
        # Get Sender Emoji from full agent list lookup
        # Since 'agents' isn't explicitly loaded in Direct Chat (it is calling state_store.load which returns data), 
        # let's grab it from 'data.get("agents", {})' which we have.
        # Wait, 'state' was loaded, and 'data' is the dict.
        # But we need 'agents' dict to lookup emoji.
        live_agents = data.get("agents", {})
        sender_info = live_agents.get(sender, {})
        sender_emoji = sender_info.get("emoji", "👤") # Default user icon
        
        # Style
        if is_replied:
            status_intro = "✅ **RÉPONDU**"
            msg_opacity = 0.6
        else:
            status_intro = "🛑 **À TRAITER**"
            msg_opacity = 1.0
            
        with st.chat_message(sender, avatar=sender_emoji):
            # Layout
            st.markdown(f"{status_intro} | 🕒 {time.ctime(timestamp)}")
            st.markdown(f"**{sender}**: {content}")
            if is_replied:
                st.caption(f"ID: {real_idx} (Archived)")
            else:
                st.caption(f"ID: {real_idx} (Active)")
            
            # Action Area
            if not is_replied:
                c_input, c_btn = st.columns([4, 1])
                # Unique keys using real_idx
                reply_text = c_input.text_input("Réponse", key=f"reply_input_{real_idx}", label_visibility="collapsed", placeholder="Votre réponse...")
                
                if c_btn.button("Envoyer", key=f"reply_btn_{real_idx}", type="primary", use_container_width=True):
                    if reply_text:
                        def send_reply(s):
                            # 1. Add Message
                            msg = {
                                "from": "User",
                                "content": reply_text,
                                "public": False,
                                "target": sender,
                                "audience": [],
                                "timestamp": time.time()
                            }
                            s.setdefault("messages", []).append(msg)
                            
                            # 2. Mark Original as Replied
                            # Access by index? Risky if list changed. 
                            # Better to find by timestamp match or strictly use index if we lock.
                            # Since we reload state in update_fn, indices might shift if new messages arrived?
                            # No, append only adds to end.
                            # But let's check basic integrity
                            if real_idx < len(s["messages"]):
                                # Double check timestamp to be sure we are hitting right message
                                if s["messages"][real_idx].get("timestamp") == timestamp:
                                    s["messages"][real_idx]["replied"] = True
                            
                            return "Réponse envoyée & Message marqué traité."
                        
                        res = state_store.update(send_reply)
                        st.toast(res)
                        st.rerun()
            else:
                 # Show what we replied? (Optional, maybe too complex for now)
                 pass

    st.divider()
    
    # 3. God Mode Injector (Unhidden)
    st.markdown("### 🛠️ Admin / God Mode (Broadcast)")
    st.caption("Envoyer un message spontané sans répondre à une requête spécifique.")
    
    # Retrieve agents if not in scope (it was in data)
    agents = data.get("agents", {})
    
    c_in_gm, c_targ_gm = st.columns([3, 1])
    all_agent_keys = sorted([k for k in agents.keys() if k != "User"])
    
    # 1. Targets (Persisted via key)
    targets_gm = c_targ_gm.multiselect(
        "Destinataires", 
        all_agent_keys, 
        placeholder="Tous (Broadcast)",
        key="gm_targets"  # FIX: Persist selection
    )
    
    # 2. Input (Managed State for clearing)
    if "gm_content" not in st.session_state:
        st.session_state.gm_content = ""
        
    gm_input = c_in_gm.text_area(
        "Message God Mode", 
        key="gm_content",
        height=100
    )
    
    # 3. Submit
    if st.button("Injecter Message", type="secondary", use_container_width=True):
         def inject_gm(s):
             msg = {
                 "from": "User",
                 "content": gm_input,
                 "timestamp": time.time()
             }
             if not targets_gm:
                 msg["public"] = True
                 msg["target"] = "all"
             else:
                 msg["public"] = False
                 msg["target"] = targets_gm[0]
                 msg["audience"] = targets_gm[1:]
                 # Force turn
                 s["turn"]["current"] = targets_gm[0]
                 s["turn"]["next"] = None
                 
             s.setdefault("messages", []).append(msg)
             return "Message Injecté"
         
         if gm_input:
            state_store.update(inject_gm)
            st.success("Message envoyé.")
            # FIX: Clear input explicitly
            st.session_state.gm_content = "" 
            st.rerun()
         else:
            st.warning("Message vide.")
