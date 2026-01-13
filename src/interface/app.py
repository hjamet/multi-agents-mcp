import streamlit as st
import streamlit.components.v1 as components
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
from pathlib import Path
import sys
import os

CODE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(CODE_ROOT) not in sys.path:
    sys.path.append(str(CODE_ROOT))

from src.config import STATE_FILE, MEMORY_DIR, TEMPLATE_DIR, LOCAL_DATA_DIR, CODE_ROOT as CONFIG_CODE_ROOT
from src.core.state import StateStore

st.set_page_config(page_title="Agent Orchestra", page_icon="🤖", layout="wide")

# --- HELPER FUNCTIONS ---
def inject_custom_css():
    st.markdown("""
    <style>
    .stChatMessage {
        border-radius: 12px;
        padding: 10px;
        margin-bottom: 10px;
        transition: all 0.2s ease-in-out;
    }
    .stChatMessage:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    .message-bubble {
        border-radius: 12px;
        padding: 15px;
        line-height: 1.5;
        font-size: 1.05em;
        position: relative;
    }
    .sender-badge {
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        margin-right: 5px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .target-badge {
        font-weight: 500;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        color: #555;
        background: rgba(0,0,0,0.05);
        border: 1px solid rgba(0,0,0,0.1);
    }
    .status-tag {
        font-size: 0.75em;
        font-weight: 600;
        padding: 1px 6px;
        border-radius: 10px;
        margin-left: 8px;
    }
    .public-tag { color: #2e7d32; background: #e8f5e9; border: 1px solid #a5d6a7; }
    .direct-tag { color: #c62828; background: #ffebee; border: 1px solid #ffcdd2; }
    .urgent-tag { color: #f57f17; background: #fffde7; border: 1px solid #fff59d; }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# --- INITIALIZE STATE (ONCE) ---
state_store = StateStore()

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

# --- DIALOGS ---
PRESET_DIR = LOCAL_DATA_DIR / "presets"
PRESET_DIR.mkdir(parents=True, exist_ok=True)

@st.dialog("Sauvegarder le Scénario")
def save_scenario_dialog(current_config):
    save_name = st.text_input("Nom de Sauvegarde", placeholder="mon_scenario")
    if st.button("Confirmer la Sauvegarde", use_container_width=True):
        if save_name:
            # Basic filename cleaning
            filename = "".join([c for c in save_name if c.isalnum() or c in (' ', '.', '_', '-')]).rstrip()
            path = PRESET_DIR / f"{filename}.json"
            with open(path, "w") as f:
                json.dump(current_config, f, indent=2)
            st.success(f"Sauvegardé : {filename}")
            time.sleep(1)
            st.rerun()
        else:
            st.error("Veuillez entrer un nom.")

@st.dialog("Charger un Scénario")
def load_scenario_dialog():
    presets = sorted([f for f in os.listdir(PRESET_DIR) if f.endswith(".json")])
    if not presets:
        st.warning("Aucun scénario trouvé.")
        return
        
    selected_preset = st.selectbox("Choisir un Preset", presets)
    if st.button("Charger la Configuration", use_container_width=True, type="primary"):
        if selected_preset:
            path = PRESET_DIR / selected_preset
            with open(path, "r") as f:
                new_conf = json.load(f)
            save_config(new_conf)
            st.success("Configuration chargée !")
            time.sleep(1)
            st.rerun()

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
    
    # 1. First decorate @everyone
    text = re.sub(
        r'(@everyone)',
        r'<span style="color: #ffffff; background-color: #ff4b4b; padding: 2px 8px; border-radius: 6px; font-weight: 700; font-size: 0.9em; box-shadow: 0 2px 4px rgba(255,75,75,0.3);">\1</span>',
        text
    )
    
    # 2. Then decorate @AgentName
    # Regex for @Name (handling spaces/hashes for Agent IDs)
    return re.sub(
        r'(@(?!everyone)[a-zA-Z0-9_ #]+)', 
        r'<span style="color: #ffffff; background-color: #0d47a1; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 0.85em; box-shadow: 0 1px 3px rgba(0,0,0,0.2);">\1</span>', 
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

def inject_mention_system(agent_names):
    import json
    agents_json = json.dumps(agent_names)
    
    components_code = f"""
    <script>
    (function() {{
        const agents = {agents_json};
        let selectedIndex = 0;
        let isVisible = false;
        let currentFilter = "";

        function setupMentions() {{
            const doc = window.parent.document;
            const textarea = doc.querySelector('textarea[data-testid="stChatInputTextArea"]');
            
            if (!textarea) {{
                setTimeout(setupMentions, 500);
                return;
            }}

            // Avoid double initialization
            if (textarea.dataset.mentionAdded === 'true') return;
            textarea.dataset.mentionAdded = 'true';

            let menu = doc.getElementById('mention-menu');
            if (!menu) {{
                menu = doc.createElement('div');
                menu.id = 'mention-menu';
                Object.assign(menu.style, {{
                    display: 'none',
                    position: 'fixed',
                    background: 'white',
                    border: '1px solid #ddd',
                    borderRadius: '8px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                    zIndex: '999999',
                    maxHeight: '200px',
                    overflowY: 'auto',
                    minWidth: '200px',
                    fontFamily: 'sans-serif'
                }});
                doc.body.appendChild(menu);
            }}

            // Inject styles into parent
            if (!doc.getElementById('mention-styles')) {{
                const style = doc.createElement('style');
                style.id = 'mention-styles';
                style.innerHTML = `
                    .mention-item:hover {{
                        background-color: #f0f2f6 !important;
                    }}
                `;
                doc.head.appendChild(style);
            }}

            textarea.addEventListener('input', (e) => {{
                if (e.isComposing) return;
                const value = textarea.value;
                const cursorPos = textarea.selectionStart;
                const textBeforeCursor = value.substring(0, cursorPos);
                const mentionMatch = textBeforeCursor.match(/@([\\w\\s#]*)$/);

                if (mentionMatch) {{
                    isVisible = true;
                    currentFilter = mentionMatch[1].toLowerCase();
                    renderMenu(textarea);
                }} else {{
                    hideMenu();
                }}
            }});

            textarea.addEventListener('keydown', (e) => {{
                if (!isVisible) return;

                const filtered = agents.filter(a => a.toLowerCase().includes(currentFilter));
                if (filtered.length === 0) return;
                
                if (e.key === 'ArrowDown') {{
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    selectedIndex = (selectedIndex + 1) % filtered.length;
                    renderMenu(textarea);
                }} else if (e.key === 'ArrowUp') {{
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    selectedIndex = (selectedIndex - 1 + filtered.length) % filtered.length;
                    renderMenu(textarea);
                }} else if (e.key === 'Enter' || e.key === 'Tab') {{
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    insertMention(textarea, filtered[selectedIndex]);
                }} else if (e.key === 'Escape') {{
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    hideMenu();
                }}
            }}, true);
        }}

        function renderMenu(textarea) {{
            const doc = window.parent.document;
            const menu = doc.getElementById('mention-menu');
            const filtered = agents.filter(a => a.toLowerCase().includes(currentFilter));
            
            if (filtered.length === 0) {{
                hideMenu();
                return;
            }}

            menu.innerHTML = filtered.map((a, i) => `
                <div class="mention-item" style="
                    padding: 8px 12px;
                    cursor: pointer;
                    background: ${{i === selectedIndex ? '#f0f2f6' : 'transparent'}};
                    border-bottom: 1px solid #eee;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    color: ${{a === 'everyone' ? '#ff4b4b' : '#31333F'}};
                    font-size: 14px;
                ">
                    <span style="font-weight: ${{i === selectedIndex ? '600' : '400'}};">@${{a}}</span>
                    ${{a === 'everyone' ? '<span style="font-size: 10px; background: #ff4b4b; color: white; padding: 1px 4px; border-radius: 4px; margin-left: 5px;">PUBLIC</span>' : ''}}
                </div>
            `).join('');

            const rect = textarea.getBoundingClientRect();
            menu.style.display = 'block';
            menu.style.left = rect.left + 'px';
            
            // Position above the textarea
            menu.style.bottom = (window.parent.innerHeight - rect.top + 10) + 'px';
            isVisible = true;
        }}

        function insertMention(textarea, name) {{
            const value = textarea.value;
            const cursorPos = textarea.selectionStart;
            const textBeforeCursor = value.substring(0, cursorPos);
            const textAfterCursor = value.substring(cursorPos);
            
            const newTextBefore = textBeforeCursor.replace(/@([\\w\\s#]*)$/, '@' + name + ' ');
            const newValue = newTextBefore + textAfterCursor;

            // Robust React state update
            const nativeTextareaValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
            nativeTextareaValueSetter.call(textarea, newValue);
            
            // Trigger events
            textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
            textarea.dispatchEvent(new Event('change', {{ bubbles: true }}));

            textarea.focus();
            // Move cursor to end of inserted mention
            const newPos = newTextBefore.length;
            textarea.setSelectionRange(newPos, newPos);
            
            hideMenu();
        }}

        function hideMenu() {{
            const doc = window.parent.document;
            const menu = doc.getElementById('mention-menu');
            if (menu) menu.style.display = 'none';
            isVisible = false;
            selectedIndex = 0;
        }}

        // Initial setup
        setupMentions();
    }})();
    </script>
    """
    components.html(components_code, height=0)

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
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: white;
        border-radius: 12px !important;
        border: 1px solid #e0e0e0 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
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
        min-height: 4em;
        line-height: 1.4;
    }
    .agent-controls {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 5px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
    }
    .reset-button-container {
        display: flex;
        justify-content: center;
        padding: 20px;
    }
    @keyframes pulse-gold {
        0% { box-shadow: 0 0 0 0 rgba(255, 215, 0, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(255, 215, 0, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 215, 0, 0); }
    }
    .active-turn {
        animation: pulse-gold 2s infinite;
        background-color: #fffde7 !important;
        border: 2px solid #ffd700 !important;
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
    
    # User status toggle
    is_available = st.toggle("Available", value=(user_status == "available"), help="Switch between Available (🟢) and Busy (🔴)")
    new_status = "available" if is_available else "busy"
    
    if new_status != user_status:
        config["user_availability"] = new_status
        save_config(config)
        st.rerun()

    status_icon = "🟢" if new_status == "available" else "🔴"
    st.info(f"User Status: **{new_status.upper()}** {status_icon}")

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
    connected_count = len([n for n, d in agents.items() if n != "User" and d.get("status") == "connected"])
    st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px;">
            <h3 style="margin: 0; font-size: 1.2em;">👥 Agents Actifs</h3>
            <span style="background: #e0e0e0; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; font-weight: bold;">{connected_count}</span>
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
            
            card_class = "active-turn" if is_turn else ""
            
            if status == "connected":
                status_color = "#4CAF50" # Green
                status_label = "En ligne"
                bg = "rgba(76, 175, 80, 0.05)"
                border_color = "rgba(76, 175, 80, 0.2)"
            elif status == "pending_connection":
                status_color = "#FF9800" # Orange
                status_label = "Initialisation..."
                bg = "rgba(255, 152, 0, 0.05)"
                border_color = "rgba(255, 152, 0, 0.2)"
            elif status == "working":
                status_color = "#2196F3" # Blue
                status_label = "Travaille..."
                bg = "rgba(33, 150, 243, 0.05)"
                border_color = "rgba(33, 150, 243, 0.2)"
            else:
                status_color = "#9E9E9E" # Grey
                status_label = "Hors-ligne"
                bg = "transparent"
                border_color = "#eee"
            
            # Additional pulse if it's their turn and they are connected
            is_active_working = is_turn and status == "connected"
            if is_active_working:
                status_color = "#2196F3"
                status_label = "En action..."
            
            st.markdown(f"""
            <div class="{card_class}" style="background-color: {bg}; border: 1px solid {border_color}; border-radius: 10px; padding: 10px 14px; margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between; transition: all 0.3s ease;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="font-size: 1.4em; background: white; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                        {emoji}
                    </div>
                    <div style="display: flex; flex-direction: column;">
                        <span style="font-weight: 600; color: {'#1a1a1a' if status == 'connected' else '#666'}; font-size: 0.95em;">{name}</span>
                        <div style="display: flex; align-items: center; gap: 4px;">
                            <div style="width: 6px; height: 6px; background-color: {status_color}; border-radius: 50%;"></div>
                            <span style="font-size: 0.7em; color: {status_color}; font-weight: 500; letter-spacing: 0.5px;">{status_label}</span>
                        </div>
                    </div>
                </div>
                {'<span style="font-size: 1.2em;" title="C&rsquo;est son tour !">✨</span>' if is_turn else ''}
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
                    current_dir = str(CONFIG_CODE_ROOT)
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
                mem_dir = str(MEMORY_DIR)
                if os.path.exists(mem_dir):
                    import shutil
                    shutil.rmtree(mem_dir)
                    os.makedirs(mem_dir, exist_ok=True)
                    st.success("Memories Cleared")
            except Exception as e:
                st.error(str(e))


# ==========================================
# PAGE: COMMUNICATION (Chat)
# ==========================================
if st.session_state.page == "Communication":
    c_title, c_status = st.columns([6, 4])
    with c_title:
        st.header("💬 Flux Neural")
    with c_status:
        current_turn = turn.get("current", "?")
        if current_turn == "User":
            st.markdown("""
                <div style="background-color: #fff3cd; border: 1px solid #ffeeba; padding: 10px; border-radius: 8px; text-align: center; animation: pulse 2s infinite;">
                    <span style="color: #856404; font-weight: bold; font-size: 1.1em;">⚡ À VOUS DE JOUER</span>
                </div>
                <style>
                @keyframes pulse {
                    0% { box-shadow: 0 0 0 0 rgba(255, 193, 7, 0.4); }
                    70% { box-shadow: 0 0 0 10px rgba(255, 193, 7, 0); }
                    100% { box-shadow: 0 0 0 0 rgba(255, 193, 7, 0); }
                }
                </style>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
                <div style="background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 10px; border-radius: 8px; text-align: center;">
                    <span style="color: #6c757d; font-size: 0.9em;">En attente de :</span><br>
                    <span style="color: #1f1f1f; font-weight: bold; font-size: 1.1em;">🤖 {current_turn}</span>
                </div>
            """, unsafe_allow_html=True)
    
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
        
        # Style and Tag Logic
        tag_html = ""
        bubble_style = ""
        
        if is_public:
            tag_html = '<span class="status-tag public-tag">📢 Neural Broadcast</span>'
            bubble_style = "background-color: rgba(240, 242, 246, 0.5); border-left: 5px solid #2e7d32;"
        else:
            if target == "User":
                tag_html = '<span class="status-tag direct-tag">🔒 Direct Link</span>'
                if not is_replied:
                    tag_html += '<span class="status-tag urgent-tag">⚡ Action Required</span>'
                    bubble_style = "background-color: #fff9c4; border-left: 5px solid #fbc02d; box-shadow: 0 2px 8px rgba(251, 192, 45, 0.2);"
                else:
                    bubble_style = "background-color: #e3f2fd; border-left: 5px solid #1976d2;"
            elif sender == "User":
                tag_html = f'<span class="status-tag">📤 Outgoing to {target}</span>'
                bubble_style = "background-color: #f8f9fa; border-left: 5px solid #9e9e9e;"
            else:
                tag_html = f'<span class="status-tag direct-tag">🔒 Private {sender} → {target}</span>'
                bubble_style = "background-color: #eeeeee; border-left: 5px solid #757575;"

        with st.chat_message(sender, avatar=sender_emoji):
            # Header with sender, target and status tags
            c_header, c_action = st.columns([10, 1])
            
            with c_header:
                # Modern Header
                st.markdown(f"""
                    <div style="display: flex; align-items: center; margin-bottom: 5px; gap: 8px;">
                        <span style="font-weight: 800; color: #1f1f1f; font-size: 0.95em;">{sender}</span>
                        <span style="color: #888; font-size: 0.8em;">→</span>
                        <span class="target-badge">{target if target != 'all' else 'everyone'}</span>
                        {tag_html}
                        <span style="color: #aaa; font-size: 0.7em; margin-left: auto;">{time.strftime('%H:%M:%S', time.localtime(timestamp))}</span>
                    </div>
                """, unsafe_allow_html=True)
            
            with c_action:
                render_reply_button(sender, content, real_idx)

            # Message Content
            st.markdown(f"""
                <div class="message-bubble" style="{bubble_style}">
                    <div style="color: #333;">{content_visual}</div>
                </div>
            """, unsafe_allow_html=True)
            st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)


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

    # 2. Target Selector (REPLACED BY MENTIONS)
    connected_agents = sorted([name for name, d in agents.items() if d.get("status") == "connected" and name != "User"])
    
    # We still need this for the mention system to know the list, adding everyone
    inject_mention_system(["everyone"] + connected_agents)

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
            
            # Special case: @everyone forces public broadcast
            if "@everyone" in prompt:
                target = "all"
                public = True
                found_mention = True
            else:
                known_agents = sorted(list(agents.keys()), key=len, reverse=True)
                for name in known_agents:
                    if f"@{name}" in prompt:
                        target = name
                        public = False
                        found_mention = True
                        break
            
            if not found_mention:
                if st.session_state.reply_to:
                     # Reply Context overrides Selector
                     target = st.session_state.reply_to["sender"]
                     reply_ref_id = st.session_state.reply_to["id"]
                     public = False
                else:
                    # No mention, no reply context -> Public Broadcast
                    target = "all"
                    public = True
            
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
            
            # --- TURN MANAGEMENT (If User had the turn) ---
            if s.get("turn", {}).get("current") == "User":
                next_speaker = None
                if target and target != "all" and target in s.get("agents", {}):
                    next_speaker = target
                else:
                    # Pass to the first connected agent if no specific target
                    connected = [n for n, d in s.get("agents", {}).items() if d.get("status") == "connected"]
                    if connected:
                        next_speaker = connected[0]
                
                if next_speaker:
                    s["turn"]["current"] = next_speaker
                    s.setdefault("messages", []).append({
                        "from": "System", "content": f"Tour à : **{next_speaker}** (suite au message de l'utilisateur)", "public": True, "timestamp": time.time()
                    })

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

    # Scenarios
    st.subheader("💾 Scénarios")
    with st.container(border=True):
        col_scen1, col_scen2 = st.columns(2)
        if col_scen1.button("💾 Sauvegarder", use_container_width=True, help="Sauvegarder la configuration actuelle"):
            save_scenario_dialog(config)
        if col_scen2.button("📂 Charger", use_container_width=True, help="Charger une configuration existante"):
            load_scenario_dialog()

    # Global Context (Full Width)
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
                    with st.container(border=True):
                        count = int(p.get("count", 0))
                        emoji = p.get("emoji", "🤖")
                        description = p.get("description", "Aucune description.")
                        
                        st.markdown(f"""
                            <div class="agent-header">
                                <span style="font-size: 1.5em;">{emoji}</span>
                                <span class="agent-name">{p['name']}</span>
                            </div>
                            <div class="agent-desc">{description}</div>
                        """, unsafe_allow_html=True)
                        
                        # Controls inside the card (container)
                        ctrl_c1, ctrl_c2, ctrl_c3, ctrl_c4 = st.columns([1, 1.5, 1, 1.5])
                        if ctrl_c1.button("➖", key=f"d_{i+j}", use_container_width=True):
                            p["count"] = max(0, count - 1)
                            save_config(config)
                            st.rerun()
                        
                        ctrl_c2.markdown(f"<h3 style='text-align: center; margin: 0; line-height: 1.5;'>{count}</h3>", unsafe_allow_html=True)
                        
                        if ctrl_c3.button("➕", key=f"i_{i+j}", use_container_width=True):
                            p["count"] = count + 1
                            save_config(config)
                            st.rerun()
                            
                        if ctrl_c4.button("✏️ Edit", key=f"ed_{i+j}", use_container_width=True):
                            st.session_state.editing_agent_name = p["name"]
                            st.session_state.page = "Editor"
                            st.rerun()

    st.markdown("---")

    # --- 2.5 FIRST SPEAKER SELECTOR ---
    st.subheader("🎯 Séquence de Départ")
    potential_agents = ["User"]
    
    # Calculate potential agent IDs the same way reset_logic does
    temp_slots = []
    for p in profiles:
        for _ in range(int(p.get("count", 0))):
            temp_slots.append(p.get("display_name") or p["name"])
            
    counters = {}
    for base in temp_slots:
        counters.setdefault(base, 0)
        counters[base] += 1
        total_of_this_base = sum(1 for b in temp_slots if b == base)
        agent_id = f"{base} #{counters[base]}" if total_of_this_base > 1 else base
        potential_agents.append(agent_id)

    # Use session state to persist choice
    if "first_speaker" not in st.session_state:
        st.session_state.first_speaker = "User"

    # Check if current choice is still valid (profiles might have changed)
    if st.session_state.first_speaker not in potential_agents:
        st.session_state.first_speaker = "User"

    selected_first = st.selectbox("Qui doit parler en premier ?", potential_agents,
                                 index=potential_agents.index(st.session_state.first_speaker),
                                 help="L'agent ou l'utilisateur qui aura le premier tour lors de l'initialisation.")
    st.session_state.first_speaker = selected_first

    st.markdown("<br>", unsafe_allow_html=True)

    # --- 3. RESET BUTTON (MODERN) ---
    col_r1, col_r2, col_r3 = st.columns([1, 2, 1])
    with col_r2:
        if st.button("🚀 INITIALISER LA SIMULATION", type="primary", use_container_width=True, help="Réinitialise tous les agents et la conversation"):
            first_speaker_choice = st.session_state.first_speaker
            
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
                
                # Turn Management
                first = None
                if first_speaker_choice == "User":
                    first = "User"
                elif first_speaker_choice in new_agents:
                    first = first_speaker_choice
                elif new_agents:
                    # Fallback to first available agent if choice is invalid for some reason
                    first = list(new_agents.keys())[0]
                
                if first:
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
        new_name = cA.text_input("Nom", current_profile.get("name", ""), key=f"edit_name_{selected_name}")
        disp = cB.text_input("Affichage", current_profile.get("display_name", ""), key=f"edit_disp_{selected_name}")
        
        new_desc = st.text_input("Description", current_profile.get("description", ""), key=f"edit_desc_{selected_name}")
        new_prompt = st.text_area("System Prompt", current_profile.get("system_prompt", ""), height=300, key=f"edit_prompt_{selected_name}")
        
        st.subheader("Capacités")
        caps = current_profile.get("capabilities", [])
        cc1, cc2, cc3, cc4 = st.columns(4)
        has_pub = cc1.checkbox("Public", "public" in caps, key=f"cap_pub_{selected_name}")
        has_priv = cc2.checkbox("Private", "private" in caps, key=f"cap_priv_{selected_name}")
        has_aud = cc3.checkbox("Audience", "audience" in caps, key=f"cap_aud_{selected_name}")
        has_open = cc4.checkbox("Open Mode", "open" in caps, key=f"cap_open_{selected_name}")
        
        new_caps = []
        if has_pub: new_caps.append("public")
        if has_priv: new_caps.append("private")
        if has_aud: new_caps.append("audience")
        if has_open: new_caps.append("open")

        st.subheader("Connexions")
        st.info("Définissez qui cet agent peut contacter et dans quel but (contexte stratégique).")
        
        other_profile_names = [p["name"] for p in profiles if p["name"] != current_profile.get("name")]
        # Standardize targets to title case for matching with state.json while keeping user/public accessible
        targets = ["public", "User"] + other_profile_names
        
        new_connections = []
        
        # Header for the "Table"
        with st.container():
            h1, h2, h3 = st.columns([2, 5, 1])
            h1.markdown("**Cible**")
            h2.markdown("**Condition / Contexte**")
            h3.markdown("**Active**")
            st.markdown("<hr style='margin-top: 0; margin-bottom: 10px; border-color: #eee;'>", unsafe_allow_html=True)
        
        for target in targets:
            # Case-insensitive match for connections
            existing_conn = next((c for c in current_profile.get("connections", []) if c["target"].lower() == target.lower()), None)
            
            c1, c2, c3 = st.columns([2, 5, 1])
            
            # Label
            target_emoji = "🌐" if target == "public" else "👤" if target == "User" else "🤖"
            c1.markdown(f"{target_emoji} **{target}**")
            
            default_ctx = existing_conn.get("context", "") if existing_conn else ""
            default_auth = existing_conn.get("authorized", False) if existing_conn else False
            
            # Unique key with selected_name and target
            ctx = c2.text_area(f"Condition for {target}", default_ctx, key=f"conn_ctx_{selected_name}_{target}", label_visibility="collapsed", height=68)
            auth = c3.checkbox(f"Active for {target}", default_auth, key=f"conn_auth_{selected_name}_{target}", label_visibility="collapsed")
            
            if auth or ctx:
                new_connections.append({"target": target, "context": ctx, "authorized": auth})
            st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)
        
        if st.button("💾 Enregistrer Modifications", type="primary"):
            current_profile["name"] = new_name
            current_profile["display_name"] = disp
            current_profile["description"] = new_desc
            current_profile["system_prompt"] = new_prompt
            current_profile["capabilities"] = new_caps
            current_profile["connections"] = new_connections
            
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
