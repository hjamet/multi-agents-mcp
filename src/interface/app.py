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
    /* Agent Card Styling */
    .agent-config-card {
        background-color: white;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s;
    }
    .agent-config-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }
    .agent-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 8px;
    }
    .agent-name {
        font-weight: 700;
        font-size: 1.1em;
        color: #1f1f1f;
    }
    .agent-desc {
        font-size: 0.85em;
        color: #666;
        margin-bottom: 12px;
        min-height: 3em;
    }
    .reset-button-container {
        display: flex;
        justify-content: center;
        padding: 20px;
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

    st.divider()

    # 2. PERMANENT ROSTER (v2.0)
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
            <h3 style="margin: 0;">👥 Agents Actifs</h3>
        </div>
    """, unsafe_allow_html=True)
    
    active_agents = []
    inactive_agents = []
    
    current_turn = turn.get("current")
    
    for name, d in agents.items():
        if name == "User": continue
        if d.get("status") == "connected":
            active_agents.append(name)
        else:
            inactive_agents.append(name)
    
    active_agents.sort()
    inactive_agents.sort()
    
    roster_list = active_agents + inactive_agents
    
    if not roster_list:
        st.caption("Aucun agent détecté.")
    else:
        for name in roster_list:
            info = agents[name]
            status = info.get("status", "pending")
            emoji = info.get("emoji", "🤖")
            is_turn = (name == current_turn)
            
            if status == "connected":
                status_color = "#4CAF50" # Green
                status_label = "Actif"
                bg = "rgba(76, 175, 80, 0.1)"
                border = "1px solid rgba(76, 175, 80, 0.2)"
            elif status == "pending_connection":
                status_color = "#FF9800" # Orange
                status_label = "Connexion..."
                bg = "rgba(255, 152, 0, 0.1)"
                border = "1px solid rgba(255, 152, 0, 0.2)"
            else:
                status_color = "#9E9E9E" # Grey
                status_label = "Inactif"
                bg = "transparent"
                border = "1px solid #eee"
            
            # Highlight if it's their turn
            if is_turn:
                bg = "#fff9c4" # Light yellow
                border = "2px solid #fbc02d"
                animation = "animation: pulse 2s infinite;"
            else:
                animation = ""

            st.markdown(f"""
            <div style="background-color: {bg}; border: {border}; border-radius: 8px; padding: 8px 12px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between; {animation}">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 1.2em;">{emoji}</span>
                    <span style="font-weight: {'bold' if is_turn else 'normal'}; color: #333;">{name}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 5px;">
                    <div style="width: 8px; height: 8px; background-color: {status_color}; border-radius: 50%;"></div>
                    <span style="font-size: 0.75em; color: {status_color}; font-weight: 600; text-transform: uppercase;">{status_label}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    st.divider()
    
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
    st.header("💬 Flux Neural")
    
    st_autorefresh(interval=3000, key="comms_refresh")

    # 1. Reply Context State
    if "reply_to" not in st.session_state:
        st.session_state.reply_to = None

    # --- FLUX NEURAL (FULL WIDTH) ---
    
    # Toggle Focus Urgences (Top Filter)
    col_toggle, col_spacer = st.columns([2, 5])
    is_urgent_focus = col_toggle.toggle("🔍 Focus Urgences", help="Affiche uniquement les messages non-répondus")

    # Helper for rendering messages and reply buttons
    def render_reply_button(sender, content, idx):
        if st.button("↩️", key=f"btn_reply_set_{idx}", help=f"Reply to {sender}", type="tertiary"):
            st.session_state.reply_to = {
                "sender": sender,
                "id": idx,
                "preview": content[:50] + "..." if len(content) > 50 else content
            }
            st.rerun()

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
            c_h, c_a = st.columns([19, 1]) 
            c_h.caption(f"{context_tag} | {time.ctime(timestamp)}")
            
            with c_a:
                render_reply_button(sender, content, real_idx)

            st.markdown(f"""
            <div style="background-color: {bg_color}; border: {border_style}; padding: 12px; border-radius: 8px; margin-bottom: 5px;">
                {content_visual}
            </div>
            """, unsafe_allow_html=True)


    # --- OMNI-CHANNEL INPUT ---
    st.divider()

    # 1. Reply Context Banner
    if st.session_state.reply_to:
        ctx = st.session_state.reply_to
        with st.container():
            c_info, c_close = st.columns([8, 1])
            c_info.info(f"↩️ Réponse à **{ctx['sender']}**: \"{ctx['preview']}\"")
            if c_close.button("✖️", key="cancel_reply"):
                st.session_state.reply_to = None
                st.rerun()

    # 2. Target Selector (Helper v2.0)
    connected_agents = sorted([name for name, d in agents.items() if d.get("status") == "connected" and name != "User"])
    
    target_options = ["📢 Tous (Broadcast)"] + connected_agents
    
    # Use selectbox for explicit targeting
    target_sel = st.selectbox("🎯 Destinataire", target_options, label_visibility="visible")

    # 3. Main Input
    if prompt := st.chat_input("Message..."):
        def send_omni_msg(s):
            target = None
            public = True
            reply_ref_id = None
            
            # Logic v2.0
            
            # 1. Context Reply (Strongest implicit) 
            # Tech Lead said: "1. Si @Mention -> Priority. 2. Sinon si target_sel != Tous -> Target."
            # Actually Context Reply usually overrides Selector visually, but Mention overrides all?
            # Let's follow instruction:
            # 1. Mention check
            # 2. Selector check
            # 3. Public
            
            found_mention = False
            known_agents = sorted(list(agents.keys()), key=len, reverse=True)
            for name in known_agents:
                if f"@{name}" in prompt:
                    target = name
                    public = False
                    found_mention = True
                    break
            
            if not found_mention:
                if st.session_state.reply_to:
                     # Reply Context overrides Selector? Tech Lead didn't mention Context in v2.0 logic.
                     # But it exists in UI. Usually Reply Context implies Target.
                     target = st.session_state.reply_to["sender"]
                     reply_ref_id = st.session_state.reply_to["id"]
                     public = False
                elif target_sel != "📢 Tous (Broadcast)":
                    target = target_sel
                    public = False
            
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
            
            # Context Cleanup
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
    
    # --- 0. GRAPHVIZ VIEW (TOP) ---
    with st.expander("🕸️ Topologie de la Flotte (Graphviz)", expanded=False):
        try:
            g = render_graph(profiles)
            st.graphviz_chart(g, use_container_width=True)
        except Exception as e:
            st.error(f"Erreur de rendu du graphe : {e}")

    preset_dir = os.path.join("assets", "presets")
    if not os.path.exists(preset_dir):
        os.makedirs(preset_dir, exist_ok=True)
    
    # Standard Layout for Scenarios and Global Context
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.subheader("💾 Scénarios")
        with st.container(border=True):
            save_name = st.text_input("Nom de Sauvegarde", placeholder="scenaro_1")
            if st.button("Sauvegarder", use_container_width=True):
                if save_name:
                    path = os.path.join(preset_dir, f"{save_name}.json")
                    with open(path, "w") as f:
                        json.dump(config, f, indent=2)
                    st.success(f"Sauvegardé : {path}")
            
            st.divider()
            
            presets = [f for f in os.listdir(preset_dir) if f.endswith(".json")]
            selected_preset = st.selectbox("Charger Preset", presets) if presets else None
            if st.button("Charger la Configuration", use_container_width=True, type="secondary"):
                if selected_preset:
                    path = os.path.join(preset_dir, selected_preset)
                    with open(path, "r") as f:
                        new_conf = json.load(f)
                    save_config(new_conf)
                    st.rerun()

    with c2:
        st.subheader("🌍 Contexte Global")
        with st.container(border=True):
            global_context = st.text_area("Narratif / Contexte Partagé", config.get("context", ""), height=215)
            if global_context != config.get("context", ""):
                if st.button("Mettre à jour le Contexte", use_container_width=True):
                    config["context"] = global_context
                    save_config(config)
                    st.success("Contexte mis à jour")

    st.divider()
    
    # --- 2. CREW MANAGEMENT (MODERN CARDS) ---
    st.subheader("👥 Crew Management")
    
    # Display cards in a grid
    cols_per_row = 3
    for i in range(0, len(profiles), cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            if i + j < len(profiles):
                p = profiles[i + j]
                with cols[j]:
                    count = int(p.get("count", 0))
                    emoji = p.get("emoji", "🤖")
                    description = p.get("description", "Aucune description.")
                    
                    st.markdown(f"""
                        <div class="agent-config-card">
                            <div class="agent-header">
                                <span style="font-size: 1.5em;">{emoji}</span>
                                <span class="agent-name">{p['name']}</span>
                            </div>
                            <div class="agent-desc">{description}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Controls inside the column but outside the HTML for functionality
                    ctrl_c1, ctrl_c2, ctrl_c3 = st.columns([1, 2, 1])
                    if ctrl_c1.button("➖", key=f"d_{i+j}", use_container_width=True):
                        p["count"] = max(0, count - 1)
                        save_config(config)
                        st.rerun()
                    
                    ctrl_c2.markdown(f"<h3 style='text-align: center; margin: 0;'>{count}</h3>", unsafe_allow_html=True)
                    
                    if ctrl_c3.button("➕", key=f"i_{i+j}", use_container_width=True):
                        p["count"] = count + 1
                        save_config(config)
                        st.rerun()
                    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("---")
    
    # --- 3. RESET BUTTON (MODERN) ---
    col_r1, col_r2, col_r3 = st.columns([1, 2, 1])
    with col_r2:
        if st.button("🚀 INITIALISER LA SIMULATION", type="primary", use_container_width=True, help="Réinitialise tous les agents et la conversation"):
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
                return "Réinitialisation terminée"
            msg = state_store.update(reset_logic)
            st.toast(msg)
            time.sleep(0.5)
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
