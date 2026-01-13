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

def render_graph(profiles):
    graph = graphviz.Digraph()
    graph.attr(rankdir='LR', bgcolor='transparent')
    
    # Nodes
    for p in profiles:
        name = p["name"]
        count = int(p.get("count", 0))
        label = f"{name}\n(x{count})"
        color = '#e3f2fd'
        graph.node(name, label=label, style='filled', fillcolor=color, shape='box', fontsize='10')

    # Edges
    for p in profiles:
        source = p["name"]
        for conn in p.get("connections", []):
            target = conn.get("target")
            is_auth = conn.get("authorized", True)
            if is_auth:
                graph.edge(source, target, color='#90a4ae', arrowsize='0.6')
    return graph

def format_mentions(text):
    if not text: return text
    return re.sub(
        r'(@[a-zA-Z0-9_ #]+)', 
        r'<span style="color: white; background-color: #5865F2; padding: 3px 8px; border-radius: 6px; font-weight: bold; box-shadow: 0 2px 5px rgba(88,101,242,0.4); border: 1px solid #4752C4; display: inline-block;">\1</span>', 
        text
    )

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

# --- SIDEBAR ---
with st.sidebar:
    st.title("🤖 Orchestra")
    
    # NAVIGATION
    page = st.radio("Navigation", ["💬 Neural Stream", "🎛️ Cockpit"], label_visibility="collapsed")
    st.divider()

    # IDENTITY / USER STATUS
    st.markdown("### 👤 Identity")
    user_status = config.get("user_availability", "busy")
    status_icon = "🟢" if user_status == "available" else "🔴"
    st.info(f"User Status: **{user_status.upper()}** {status_icon}")

    # ROSTER
    st.markdown("### 👥 Agents Actifs")
    active_agents = []
    inactive_agents = []
    
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
            
    st.divider()
    st.caption(f"Turn: {turn.get('current', 'None')} -> {turn.get('next', 'Wait...')}")


# ==========================================
# PAGE: NEURAL STREAM
# ==========================================
if page == "💬 Neural Stream":
    # HEADER: User Availability Switch
    col_head, col_switch = st.columns([4, 1])
    col_head.header("💬 Flux Neural")
    
    current_avail = config.get("user_availability", "busy") == "available"
    new_avail = col_switch.toggle("Disponibilité", value=current_avail)
    
    if new_avail != current_avail:
        config["user_availability"] = "available" if new_avail else "busy"
        save_config(config)
        st.rerun()

    st_autorefresh(interval=3000, key="comms_refresh")

    # 1. Reply Context State
    if "reply_to" not in st.session_state:
        st.session_state.reply_to = None

    # Toggle Focus Urgences (Top Filter)
    col_toggle, col_spacer = st.columns([2, 5])
    is_urgent_focus = col_toggle.toggle("🔍 Focus Urgences", help="Affiche uniquement les messages non-répondus")

    # Alerting (High-Visibility)
    pending_mentions = sum(1 for m in messages if m.get("target") == "User" and not m.get("replied", False))
    if pending_mentions > 0:
        st.markdown(f"#### 🔔 **{pending_mentions} mentions** require your attention !")

    # Helper for rendering messages and reply buttons
    def render_reply_button(sender, content, idx):
        if st.button("↩️", key=f"btn_reply_set_{idx}", help=f"Reply to {sender}", type="tertiary"):
            st.session_state.reply_to = {
                "sender": sender,
                "id": idx,
                "preview": content[:50] + "..." if len(content) > 50 else content
            }
            st.rerun()

    # Message Stream
    stream_msgs = []
    for i, m in enumerate(messages):
        is_relevant = m.get("public", False) or m.get("target") == "User" or m.get("from") == "User"
        if is_relevant:
            # FILTER LOGIC
            if is_urgent_focus:
                target = m.get("target")
                is_replied = m.get("replied", False)
                if target != "User" or is_replied:
                    continue
            stream_msgs.append((i, m))
    
    # Pagination
    if "stream_limit" not in st.session_state: st.session_state.stream_limit = 15
    total_stream = len(stream_msgs)
    limit_stream = st.session_state.stream_limit
    if total_stream > limit_stream:
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
                context_tag = "🔒 DIRECT (Action Requise)"
                bg_color = "#fff3cd" if not is_replied else "#e3f2fd"
                border_style = "3px solid #ff9800; box-shadow: 0 4px 6px rgba(0,0,0,0.1)" if not is_replied else "1px solid #dee2e6"
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

    # --- INPUT AREA ---
    st.divider()

    # Reply Context Banner
    if st.session_state.reply_to:
        ctx = st.session_state.reply_to
        with st.container():
            c_info, c_close = st.columns([8, 1])
            c_info.info(f"↩️ Réponse à **{ctx['sender']}**: \"{ctx['preview']}\"")
            if c_close.button("✖️", key="cancel_reply"):
                st.session_state.reply_to = None
                st.rerun()

    # Target Selector
    connected_agents = sorted([name for name, d in agents.items() if d.get("status") == "connected" and name != "User"])
    target_options = ["📢 Tous (Broadcast)"] + connected_agents
    target_sel = st.selectbox("🎯 Destinataire", target_options, label_visibility="visible")

    if prompt := st.chat_input("Message..."):
        def send_omni_msg(s):
            target = None
            public = True
            reply_ref_id = None
            
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
            
            if reply_ref_id is not None and reply_ref_id < len(s["messages"]):
                 s["messages"][reply_ref_id]["replied"] = True
                        
            return "Message Transmis."

        res = state_store.update(send_omni_msg)
        st.session_state.reply_to = None
        st.toast(res)
        st.rerun()


# ==========================================
# PAGE: COCKPIT
# ==========================================
elif page == "🎛️ Cockpit":
    st.title("🎛️ Cockpit de Supervision")
    
    tab_mission, tab_agents, tab_graph = st.tabs(["🚀 Mission", "🤖 Agents", "🕸️ Relations"])
    
    # --------------------------
    # TAB 1: MISSION
    # --------------------------
    with tab_mission:
        c1, c2 = st.columns([1, 1])
        
        with c1:
            st.subheader("💾 Presets")
            preset_dir = os.path.join("assets", "presets")
            if not os.path.exists(preset_dir):
                os.makedirs(preset_dir, exist_ok=True)
                
            save_name = st.text_input("Nom de Sauvegarde", placeholder="scenaro_1")
            if st.button("Sauvegarder Preset"):
                if save_name:
                    path = os.path.join(preset_dir, f"{save_name}.json")
                    with open(path, "w") as f:
                        json.dump(config, f, indent=2)
                    st.success(f"Sauvegardé: {path}")
            
            presets = [f for f in os.listdir(preset_dir) if f.endswith(".json")]
            selected_preset = st.selectbox("Charger Preset", presets) if presets else None
            if st.button("Charger Preset"):
                if selected_preset:
                    path = os.path.join(preset_dir, selected_preset)
                    with open(path, "r") as f:
                        new_conf = json.load(f)
                    save_config(new_conf)
                    st.rerun()

        with c2:
            st.subheader("🚀 Contrôle")
            if st.button("♻️ RESET SIMULATION", type="primary"):
                def reset_logic(s):
                    s["conversation_id"] = str(uuid.uuid4())
                    s["messages"] = []
                    s["turn"] = {"current": None, "next": None}
                    
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
                st.rerun()

        st.markdown("---")
        st.subheader("🌍 Contexte Global")
        global_context = st.text_area("Narratif / Contexte", config.get("context", ""), height=200)
        if global_context != config.get("context", ""):
            if st.button("Mettre à jour Contexte"):
                config["context"] = global_context
                save_config(config)
                st.success("Updated")
                
    # --------------------------
    # TAB 2: AGENTS
    # --------------------------
    with tab_agents:
        st.header("🛠️ Éditeur d'Agents")
        
        # Crew Counts
        st.subheader("👥 Déploiement")
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
        
        st.divider()
        
        # Profile Editor
        st.subheader("✏️ Edition Profils")
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
            
            if st.button("🗑️ Supprimer Profil"):
                 config["profiles"] = [p for p in profiles if p["name"] != selected_name]
                 save_config(config)
                 st.rerun()

        if current_profile:
            st.markdown("---")
            # Edit Form
            cA, cB = st.columns(2)
            new_name = cA.text_input("Nom", current_profile.get("name", ""))
            disp = cB.text_input("Affichage", current_profile.get("display_name", ""))
            
            new_desc = st.text_input("Description", current_profile.get("description", ""))
            new_prompt = st.text_area("System Prompt", current_profile.get("system_prompt", ""), height=300)
            
            # Capabilities
            st.caption("Capacités")
            caps = current_profile.get("capabilities", [])
            cc1, cc2, cc3 = st.columns(3)
            has_pub = cc1.checkbox("Public", "public" in caps)
            has_priv = cc2.checkbox("Private", "private" in caps)
            has_aud = cc3.checkbox("Audience", "audience" in caps)
            
            new_caps = []
            if has_pub: new_caps.append("public")
            if has_priv: new_caps.append("private")
            if has_aud: new_caps.append("audience")
            
            # CONNECTIONS EDITOR
            st.subheader("🔗 Connexions")
            conns = current_profile.get("connections", [])
            
            # Viewer
            if conns:
                for i, conn in enumerate(conns):
                    c_t, c_c, c_del = st.columns([2, 3, 1])
                    c_t.write(f"➡️ **{conn.get('target')}**")
                    c_c.caption(conn.get('context', ''))
                    if c_del.button("❌", key=f"del_conn_{i}"):
                        conns.pop(i)
                        save_config(config)
                        st.rerun()
            else:
                st.caption("Aucune connexion définie.")
                
            # Adder
            with st.expander("Ajouter Connexion"):
                candidates = [p["name"] for p in profiles if p["name"] != current_profile.get("name")]
                if candidates:
                    new_target = st.selectbox("Cible", candidates)
                    new_ctx = st.text_input("Contexte (Relation)")
                    if st.button("Ajouter"):
                        conns.append({"target": new_target, "context": new_ctx, "authorized": True})
                        save_config(config)
                        st.rerun()
            
            if st.button("💾 Enregistrer Profil", type="primary"):
                current_profile["name"] = new_name
                current_profile["display_name"] = disp
                current_profile["description"] = new_desc
                current_profile["system_prompt"] = new_prompt
                current_profile["capabilities"] = new_caps
                current_profile["connections"] = conns
                
                if new_mode:
                    profiles.append(current_profile)
                
                # Smart renaming references
                if not new_mode and selected_name and new_name != selected_name:
                    for p in profiles:
                        for conn in p.get("connections", []):
                            if conn.get("target") == selected_name:
                                conn["target"] = new_name
                
                save_config(config)
                st.toast("Profil Sauvegardé")
                st.rerun()

    # --------------------------
    # TAB 3: RELATIONS
    # --------------------------
    with tab_graph:
        st.subheader("🕸️ Visualisation des Relations")
        try:
            g = render_graph(profiles)
            st.graphviz_chart(g)
        except Exception as e:
            st.error(f"Erreur rendu graphe: {e}")
