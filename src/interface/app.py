import streamlit as st
from streamlit_autorefresh import st_autorefresh
import graphviz
import json
import uuid
import sys
import os
import time
import re
from pathlib import Path

# Add src to path to allow imports if run directly
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.core.state import StateStore

st.set_page_config(page_title="Agent Orchestra", page_icon="🤖", layout="wide")

# --- INITIALIZE STATE (ONCE) ---
state_store = StateStore()

# --- HELPER FUNCTIONS ---
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

def format_mentions(text):
    if not text: return text
    # Regex for @Name (handling spaces/hashes for Agent IDs)
    return re.sub(
        r'(@[a-zA-Z0-9_ #]+)', 
        r'<span style="color: #1565C0; background-color: #E3F2FD; padding: 2px 6px; border-radius: 12px; font-weight: 600; display: inline-block;">\1</span>', 
        text
    )

def render_graph(profiles, current_editing=None):
    graph = graphviz.Digraph()
    graph.attr(rankdir='LR', size='12,2', ratio='fill', bgcolor='transparent', margin='0')
    
    for p in profiles:
        name = p["name"]
        color = 'lightblue'
        if current_editing and name == current_editing:
            color = 'gold'
        count = p.get("count", 0)
        label = f"{name}\n(x{count})"
        graph.node(name, label=label, style='filled', fillcolor=color, shape='box', fontsize='10', height='0.5')

    for p in profiles:
        source = p["name"]
        for conn in p.get("connections", []):
            target = conn.get("target")
            is_auth = conn.get("authorized", True)
            if is_auth and any(prof["name"] == target for prof in profiles):
                graph.edge(source, target, fontsize='8', color='gray', arrowsize='0.5')
    return graph

# --- MAIN LOGIC ---

# 1. Load Data
state, config = load_config()
data = state
profiles = config.get("profiles", [])
agents = data.get("agents", {})
turn = data.get("turn", {})
messages = data.get("messages", [])

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
    /* Tertiary button compact style */
    button[kind="tertiary"] {
        background: transparent;
        border: none;
        box-shadow: none;
    }
</style>
""", unsafe_allow_html=True)

# --- NAVIGATION ROUTER ---
if "page" not in st.session_state:
    st.session_state.page = "Communication"

# --- SIDEBAR ---
with st.sidebar:
    st.title("🤖 Orchestra")
    
    st.markdown("### Navigation")
    if st.button("💬 Communication", use_container_width=True, type="primary" if st.session_state.page == "Communication" else "secondary"):
        st.session_state.page = "Communication"
        st.rerun()
        
    if st.button("🎛️ Cockpit", use_container_width=True, type="primary" if st.session_state.page == "Cockpit" else "secondary"):
        st.session_state.page = "Cockpit"
        st.rerun()
        
    if st.button("🛠️ Éditeur", use_container_width=True, type="primary" if st.session_state.page == "Editor" else "secondary"):
        st.session_state.page = "Editor"
        st.rerun()

    st.divider()
    
    # 1. Identity / User Status
    st.markdown("### 👤 Identity")
    user_status = config.get("user_availability", "busy")
    status_icon = "🟢" if user_status == "available" else "🔴"
    st.info(f"User Status: **{user_status.upper()}** {status_icon}")

    # Language
    st.markdown("### 🌐 Language")
    langs = ["English", "French", "Chinese", "Persian"]
    current_lang = config.get("language", "English")
    if current_lang not in langs: current_lang = "English"
    new_lang = st.selectbox("Interface Language", langs, index=langs.index(current_lang))
    if new_lang != current_lang:
        config["language"] = new_lang
        save_config(config)
        st.rerun()

    # 2. System Status
    st.markdown("### 📡 System Status")
    connected_count = sum(1 for a in agents.values() if a.get("status") == "connected")
    total_required = get_total_agents(profiles)
    
    if connected_count >= total_required and total_required > 0:
        connection_text = "🟢 ONLINE"
    elif connected_count > 0:
        connection_text = "🟡 CONNECTING"
    else:
        connection_text = "🔴 OFFLINE"

    m1, m2 = st.columns(2)
    m1.metric("Status", connection_text)
    m2.metric("Agents", f"{connected_count}/{total_required}")
    
    st.metric("Turn", turn.get("current", "None"))
    st.metric("Next", turn.get("next", "Wait..."))

    # Debug Tools
    with st.expander("🔧 DEBUG"):
        if st.button("Fix MCP Config"):
            import subprocess
            try:
                config_path = os.path.expanduser("~/.gemini/antigravity/mcp_config.json")
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        json_data = json.load(f)
                    current_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                    server_script = os.path.join(current_dir, "src", "core", "server.py")
                    command_str = f"cd {current_dir} && uv run python {server_script}"
                    if "mcpServers" not in json_data:
                        json_data["mcpServers"] = {}
                    json_data["mcpServers"]["multi-agents-mcp"] = {
                        "command": "sh",
                        "args": ["-c", command_str],
                        "env": {}
                    }
                    with open(config_path, "w") as f:
                        json.dump(json_data, f, indent=2)
                    st.success("Config Path Updated")
            except Exception as e:
                st.error(str(e))

        if st.button("Delete Memories"):
            try:
                mem_dir = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "memory")
                if os.path.exists(mem_dir):
                    import shutil
                    shutil.rmtree(mem_dir)
                    os.makedirs(mem_dir)
                    st.success("Memories Cleared")
            except Exception as e:
                st.error(str(e))


# ==========================================
# PAGE: COMMUNICATION (Chat)
# ==========================================
if st.session_state.page == "Communication":
    st.header("💬 Communication Console")
    
    # Auto-Refresh ONLY on Chat Page
    st_autorefresh(interval=3000, key="comms_refresh")

    # 1. Reply Context State
    if "reply_to" not in st.session_state:
        st.session_state.reply_to = None

    # LAYOUT SPLIT: Main Chat | Roster
    c_main, c_roster = st.columns([5, 1])

    with c_main:
        # 2 TABS ONLY (Refactor 1.5)
        tab_stream, tab_public = st.tabs(["📥 Flux Neural", "📢 Fréquence Publique"])

        # Helper for rendering messages and reply buttons
        def render_reply_button(sender, content, idx):
            # UI Minimaliste (Type Tertiary)
            if st.button("↩️", key=f"btn_reply_set_{idx}", help=f"Reply to {sender}", type="tertiary"):
                st.session_state.reply_to = {
                    "sender": sender,
                    "id": idx,
                    "preview": content[:50] + "..." if len(content) > 50 else content
                }
                st.rerun()

        # --- TAB 1: FLUX NEURAL (MERGED) ---
        with tab_stream:
            # Toggle Focus Urgences (Top Filter)
            col_title, col_toggle = st.columns([3, 1])
            col_title.caption("Timeline Unifiée : Publique + Privée")
            is_urgent_focus = col_toggle.toggle("🔍 Focus Urgences", help="Affiche uniquement les messages non-répondus")

            stream_msgs = []
            for i, m in enumerate(messages):
                is_relevant = m.get("public", False) or m.get("target") == "User" or m.get("from") == "User"
                if is_relevant:
                    # FILTER LOGIC
                    if is_urgent_focus:
                        target = m.get("target")
                        is_replied = m.get("replied", False)
                        # Show only if directed to User AND not replied
                        if target != "User" or is_replied:
                            continue
                    stream_msgs.append((i, m))
            
            # Pagination
            if "stream_limit" not in st.session_state: st.session_state.stream_limit = 15
            total_stream = len(stream_msgs)
            limit_stream = st.session_state.stream_limit
            if total_stream > limit_stream:
                 # UI Minimaliste (Tertiary)
                 if st.button(f"🔃 Historique ({total_stream - limit_stream})", key="load_more_stream", type="tertiary"):
                     st.session_state.stream_limit += 15
                     st.rerun()
            
            visible_stream = stream_msgs[max(0, total_stream - limit_stream):]
            
            if not visible_stream:
                st.info("Aucune activité détectée sur les bandes neurales.")
                
            for real_idx, m in visible_stream:
                sender = m.get("from", "?")
                target = m.get("target", "?")
                content = m.get("content", "")
                is_public = m.get("public", False)
                timestamp = m.get("timestamp", 0)
                is_replied = m.get("replied", False)
                
                # FORMAT MENTIONS
                content_visual = format_mentions(content)
                
                agent_info = agents.get(sender, {})
                sender_emoji = agent_info.get("emoji", "🤖") if sender != "System" else "💾"
                if sender == "User": sender_emoji = "👤"
                
                context_tag = ""
                if is_public:
                    context_tag = "📢 PUBLIC"
                    bg_color = "transparent"
                    border_style = "none"
                else:
                    if target == "User":
                        context_tag = "🔒 DIRECT"
                        bg_color = "#fff3cd" if not is_replied else "#e3f2fd"
                        border_style = "2px solid #ffecb5" if not is_replied else "1px solid #dee2e6"
                    elif sender == "User":
                         context_tag = f"📤 SENT to {target}"
                         bg_color = "#f8f9fa"
                         border_style = "1px solid #eee"
                    else:
                         context_tag = f"🔒 DIRECT {sender}->{target}"
                         bg_color = "#f1f1f1"
                         border_style = "none"

                with st.chat_message(sender, avatar=sender_emoji):
                    c_h, c_a = st.columns([19, 1]) # Adjusted ratio for minimal button
                    c_h.caption(f"{context_tag} | {time.ctime(timestamp)}")
                    
                    with c_a:
                        render_reply_button(sender, content, real_idx)

                    st.markdown(f"""
                    <div style="background-color: {bg_color}; border: {border_style}; padding: 12px; border-radius: 8px; margin-bottom: 5px;">
                        {content_visual}
                    </div>
                    """, unsafe_allow_html=True)


        # --- TAB 2: PUBLIC FREQUENCY ---
        with tab_public:
            with st.expander("🕸️ Network", expanded=False):
                st.graphviz_chart(render_graph(profiles), use_container_width=True)

            st.markdown("### 📜 Log Public")
            
            if "live_chat_limit" not in st.session_state: st.session_state.live_chat_limit = 10
            total_live = len(messages)
            if total_live > st.session_state.live_chat_limit:
                if st.button(f"🔃 Historique", key="load_more_live", type="tertiary"):
                    st.session_state.live_chat_limit += 10
                    st.rerun()
                    
            visible_live = messages[max(0, total_live - st.session_state.live_chat_limit):]
            start_i = max(0, total_live - st.session_state.live_chat_limit)
            
            for idx, m in enumerate(visible_live):
                real_idx = start_i + idx
                sender = m.get("from", "?")
                content = m.get("content", "")
                content_visual = format_mentions(content)
                
                agent_info = agents.get(sender, {})
                sender_emoji = agent_info.get("emoji", "🤖") if sender != "System" else "💾"
                
                with st.chat_message(sender, avatar=sender_emoji):
                    c_head, c_act = st.columns([19, 1])
                    c_head.caption(f"📢 PUBLIC | **{sender}**")
                    with c_act:
                        render_reply_button(sender, content, real_idx)
                    st.markdown(content_visual, unsafe_allow_html=True)


    # --- ROSTER (RIGHT PANEL) ---
    with c_roster:
        st.caption("👥 Agents Actifs")
        
        # STICKY ROSTER CONTAINER
        st.markdown('<div style="height: 70vh; overflow-y: auto; padding-right: 5px;">', unsafe_allow_html=True)
        
        active_agents = []
        inactive_agents = []
        
        for name, data in agents.items():
            if name == "User": continue
            if data.get("status") == "connected":
                active_agents.append(name)
            else:
                inactive_agents.append(name)
        
        active_agents.sort()
        inactive_agents.sort()
        
        for name in active_agents + inactive_agents:
            info = agents[name]
            status = info.get("status", "pending")
            emoji = info.get("emoji", "🤖")
            
            if status == "connected":
                status_dot = "🟢"
                style = "font-weight:bold; color: black;"
                bg = "#e3f2fd"
            else:
                status_dot = "🔴"
                style = "color: grey;"
                bg = "transparent"
            
            st.markdown(f"""
            <div style="background-color: {bg}; border-radius: 5px; padding: 4px; margin-bottom: 4px;">
                {status_dot} {emoji} <span style="{style}">{name}</span>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)


    # --- OMNI-CHANNEL INPUT ---
    st.divider()

    # 1. Reply Banner
    if st.session_state.reply_to:
        ctx = st.session_state.reply_to
        with st.container():
            c_info, c_close = st.columns([8, 1])
            c_info.info(f"↩️ Réponse à **{ctx['sender']}**: \"{ctx['preview']}\"")
            if c_close.button("✖️", key="cancel_reply"):
                st.session_state.reply_to = None
                st.rerun()

    # 2. Helper Targets (Visual Aid)
    connected_agents = [name for name, d in agents.items() if d.get("status") == "connected" and name != "User"]
    target_list = ", ".join([f"@{n}" for n in connected_agents])
    if target_list:
        st.caption(f"🎯 Cibles Disponibles : {target_list} (ou Broadcast)")

    # 3. Main Input
    if prompt := st.chat_input("Broadcast ou @Cible..."):
        def send_omni_msg(s):
            target = None
            public = True
            reply_ref_id = None
            
            if st.session_state.reply_to:
                target = st.session_state.reply_to["sender"]
                reply_ref_id = st.session_state.reply_to["id"]
                public = False
            
            known_agents = sorted(list(agents.keys()), key=len, reverse=True)
            for name in known_agents:
                if f"@{name}" in prompt:
                    target = name
                    public = False
                    break
            
            msg = {
                "from": "User",
                "content": prompt,
                "timestamp": time.time(),
                "public": public,
                "audience": []
            }
            if target:
                msg["target"] = target
            else:
                msg["target"] = "all"
                
            s.setdefault("messages", []).append(msg)
            
            if reply_ref_id is not None:
                if reply_ref_id < len(s["messages"]):
                     s["messages"][reply_ref_id]["replied"] = True
                     
            return "Message Transmis."

        res = state_store.update(send_omni_msg)
        st.session_state.reply_to = None
        st.toast(res)
        st.rerun()

# ==========================================
# PAGE: COCKPIT (Admin)
# ==========================================
elif st.session_state.page == "Cockpit":
    st.header("🎛️ Cockpit de Supervision")
    
    preset_dir = os.path.join("assets", "presets")
    if not os.path.exists(preset_dir):
        os.makedirs(preset_dir, exist_ok=True)
    
    # Standard Layout
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.subheader("💾 Scénarios")
        save_name = st.text_input("Nom de Sauvegarde", placeholder="scenaro_1")
        if st.button("Sauvegarder", use_container_width=True):
            if save_name:
                path = os.path.join(preset_dir, f"{save_name}.json")
                with open(path, "w") as f:
                    json.dump(config, f, indent=2)
                st.success(f"Sauvegardé: {path}")
        
        presets = [f for f in os.listdir(preset_dir) if f.endswith(".json")]
        selected_preset = st.selectbox("Charger Preset", presets) if presets else None
        if st.button("Charger", use_container_width=True):
            if selected_preset:
                path = os.path.join(preset_dir, selected_preset)
                with open(path, "r") as f:
                    new_conf = json.load(f)
                save_config(new_conf)
                st.rerun()

    with c2:
        st.subheader("👥 Crew Management")
        for i, p in enumerate(profiles):
            cl, cc = st.columns([3, 2])
            cl.write(f"**{p['name']}**")
            count = int(p.get("count", 0))
            if cc.button("➖", key=f"d_{i}"):
                p["count"] = max(0, count - 1)
                save_config(config)
                st.rerun()
            cc.write(f"Count: {count}")
            if cc.button("➕", key=f"i_{i}"):
                p["count"] = count + 1
                save_config(config)
                st.rerun()

    st.markdown("---")
    st.subheader("🌍 Contexte Global")
    global_context = st.text_area("Narratif / Contexte", config.get("context", ""), height=200)
    if global_context != config.get("context", ""):
        if st.button("Mettre à jour Contexte"):
            config["context"] = global_context
            save_config(config)
            st.success("Updated")

    st.markdown("---")
    if st.button("🚀 RÉSÉT SIMULATION", type="primary"):
        def reset_logic(s):
            s["conversation_id"] = str(uuid.uuid4())
            s["messages"] = []
            s["turn"] = {"current": None, "next": None}
            s["config"]["context"] = global_context
            
            pending_slots = []
            import random
            for p in profiles:
                for _ in range(int(p.get("count", 0))):
                    pending_slots.append({
                        "profile_ref": p["name"],
                        "role": p.get("system_prompt", ""),
                        "display_base": p.get("display_name") or p["name"],
                        "emoji": p.get("emoji", "🤖")
                    })
            random.shuffle(pending_slots)
            
            new_agents = {}
            counters = {}
            for slot in pending_slots:
                base = slot["display_base"]
                counters.setdefault(base, 0)
                counters[base] += 1
                agent_id = f"{base} #{counters[base]}" if sum(1 for sl in pending_slots if sl["display_base"] == base) > 1 else base
                new_agents[agent_id] = {
                    "role": slot["role"], "status": "pending_connection",
                    "profile_ref": slot["profile_ref"], "emoji": slot["emoji"]
                }
            s["agents"] = new_agents
            if new_agents:
                first = list(new_agents.keys())[0]
                s["turn"]["current"] = first
                s.setdefault("messages", []).append({
                    "from": "System", "content": f"🟢 SIMULATION RESET. First Turn: {first}", "public": True, "timestamp": time.time()
                })
            return "Reset Complete"
        msg = state_store.update(reset_logic)
        st.toast(msg)
        time.sleep(1)
        st.session_state.page = "Communication"
        st.rerun()


# ==========================================
# PAGE: EDITOR (Admin)
# ==========================================
elif st.session_state.page == "Editor":
    st.header("🛠️ Éditeur d'Agents")
    
    profile_names = [p["name"] for p in profiles]
    profile_names.append("➕ Create New")
    
    sel_idx = 0
    cur_edit = st.session_state.get("editing_agent_name")
    if cur_edit in profile_names:
        sel_idx = profile_names.index(cur_edit)
        
    selected_name = st.selectbox("Selection Profil", profile_names, index=sel_idx, key="edit_sel_page")
    
    if selected_name == "➕ Create New":
        current_profile = {"name": "New Agent", "description": "", "connections": [], "count": 1, "capabilities": ["public"]}
        new_mode = True
        st.session_state.editing_agent_name = "New Agent"
    else:
        current_profile = next((p for p in profiles if p["name"] == selected_name), None)
        new_mode = False
        st.session_state.editing_agent_name = selected_name
        
        if st.button("🗑️ Supprimer Profil", type="primary"):
             config["profiles"] = [p for p in profiles if p["name"] != selected_name]
             save_config(config)
             st.rerun()

    if current_profile:
        st.markdown("---")
        # Layout Spacieux (Columns)
        cA, cB = st.columns(2)
        new_name = cA.text_input("Nom", current_profile.get("name", ""))
        disp = cB.text_input("Affichage", current_profile.get("display_name", ""))
        
        new_desc = st.text_input("Description", current_profile.get("description", ""))
        new_prompt = st.text_area("System Prompt", current_profile.get("system_prompt", ""), height=300)
        
        st.subheader("Capacités")
        caps = current_profile.get("capabilities", [])
        cc1, cc2, cc3, cc4 = st.columns(4)
        has_pub = cc1.checkbox("Public", "public" in caps)
        has_priv = cc2.checkbox("Private", "private" in caps)
        has_aud = cc3.checkbox("Audience", "audience" in caps)
        has_open = cc4.checkbox("Open Mode", "open" in caps)
        
        new_caps = []
        if has_pub: new_caps.append("public")
        if has_priv: new_caps.append("private")
        if has_aud: new_caps.append("audience")
        if has_open: new_caps.append("open")
        
        if st.button("💾 Enregistrer Modifications", type="primary"):
            current_profile["name"] = new_name
            current_profile["display_name"] = disp
            current_profile["description"] = new_desc
            current_profile["system_prompt"] = new_prompt
            current_profile["capabilities"] = new_caps
            
            if new_mode:
                profiles.append(current_profile)
            
            # Smart renaming
            if not new_mode and selected_name and new_name != selected_name:
                for p in profiles:
                    for conn in p.get("connections", []):
                        if conn.get("target") == selected_name:
                            conn["target"] = new_name
            
            save_config(config)
            st.toast("Saved!")
            st.rerun()
