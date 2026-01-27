
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
import shutil
import argparse
import hashlib
import importlib
from pathlib import Path

# Add src to path to allow imports if run directly
from pathlib import Path
import sys
import os

CODE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(CODE_ROOT) not in sys.path:
    sys.path.append(str(CODE_ROOT))

from src.config import (
    STATE_FILE, 
    MEMORY_DIR, 
    EXECUTION_DIR,
    TEMPLATE_DIR, 
    LOCAL_DATA_DIR, 
    GLOBAL_PRESET_DIR, 
    ASSETS_DIR,
    CODE_ROOT as CONFIG_CODE_ROOT,
    RELOAD_INSTRUCTION
)
from src.core.state import StateStore
from src.services.search_engine import SearchEngine

st.set_page_config(page_title="Agent Orchestra", page_icon="🤖", layout="wide")

# --- AUTHENTICATION ---
def check_authentication():
    # 1. Parse CLI Arguments for --password
    parser = argparse.ArgumentParser()
    parser.add_argument("--password", type=str, default=None, help="Optional password to secure the interface")
    args, unknown = parser.parse_known_args()
    
    cli_password = args.password
    
    # If no password configured, we are good
    if not cli_password:
        return

    # 2. Check Session State
    if st.session_state.get("authenticated", False):
        return

    # 3. Show Login Page
    st.markdown("### 🔒 Authentication Required")
    password_input = st.text_input("Enter Password", type="password")
    
    if st.button("Login"):
        if password_input == cli_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ Incorrect Password")
            
    # Stop Execution until authenticated
    st.stop()

check_authentication()

# --- EMOJI LIST ---
EMOJI_LIST = [
    "🤖", "🧠", "🕵️", "🦸", "🥷", "🧙", "🧛", "🧟", "🧞", "🧝",
    "👽", "👾", "🤖", "🎃", "👻", "👹", "👺", "🤡", "💩", "🦄",
    "🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐻‍❄️", "🐨",
    "🐯", "🦁", "🐮", "🐷", "🐸", "🐵", "🐔", "🐧", "🐦", "🐤",
    "🦆", "🦅", "🦉", "🦇", "🐺", "🐗", "🐴", "🦄", "🐝", "🐛",
    "🦋", "🐌", "🐞", "🐜", "🦗", "🕷️", "🦂", "🐢", "🐍", "🦎",
    "🦖", "🦕", "🐙", "🦑", "🦐", "🦞", "🦀", "🐡", "🐠", "🐟",
    "🐬", "🐳", "🐋", "🦈", "🐊", "🐅", "🐆", "🦓", "🦍", "🦧",
    "🐘", "🦛", "🦏", "🐪", "🐫", "🦒", "🦘", "🦬", "🐃", "🐂",
    "🐄", "🐎", "🐖", "🐏", "🐑", "🐐", "🦌", "🐕", "🐩", "🐈",
    "🐓", "🦃", "🦚", "🦜", "🦢", "🦩", "🕊️", "🐇", "🦝", "🦨",
    "🦡", "🦦", "🦥", "🐁", "🐀", "🐿️", "🦔", "🐾", "🐉", "🐲",
    "🌵", "🎄", "🌲", "🌳", "🌴", "🌱", "🌿", "☘️", "🍀", "🍃"
]

def get_random_emoji():
    import random
    return random.choice(EMOJI_LIST)

# --- HELPER FUNCTIONS ---
def inject_custom_css():
    st.markdown("""<style>
    /* Global message container - optimized for mobile */
    [data-testid="stChatMessage"] {
        padding: 0.5rem 0.6rem 0.5rem 0 !important;
        margin-bottom: 0.8rem !important;
    }
    
    [data-testid="stChatMessage"] [data-testid="stVerticalBlock"] {
        gap: 6px !important;
    }
    
    [data-testid="stChatMessageContent"] {
        padding-left: 0 !important;
        margin-left: 0 !important;
    }
    
    /* Hide default Streamlit avatar since we show it in header */
    [data-testid="stChatMessage"] > div:first-child {
        display: none !important;
    }
    
    /* Remove gap since avatar is hidden */
    [data-testid="stChatMessage"] > div {
        gap: 0 !important;
        margin-left: 0 !important;
    }
    
    /* User messages styling - green and aligned right */
    [data-testid="stChatMessage"]:has([aria-label*="Chat message from User"]) {
        margin-left: auto !important;
        margin-right: 0 !important;
        max-width: 85% !important;
    }
    
    [aria-label*="Chat message from User"] .message-bubble {
        background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%) !important;
        border-left: 4px solid #4caf50 !important;
        box-shadow: 0 2px 8px rgba(76, 175, 80, 0.15) !important;
    }
    
    [aria-label*="Chat message from User"] .message-header {
        opacity: 0.95 !important;
    }

    /* Header layout inside message */
    .message-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 6px;
        opacity: 0.85;
        flex-wrap: wrap;
    }

    .message-bubble {
        border-radius: 4px 14px 14px 14px;
        padding: 10px 14px;
        line-height: 1.5;
        font-size: 0.95em;
        border-left: 4px solid transparent;
        box-shadow: 0 2px 5px rgba(0,0,0,0.04);
        background: white;
        width: 100%;
        max-width: 100%;
    }
    
    /* Mobile optimizations */
    @media (max-width: 768px) {
        [data-testid="stChatMessage"] {
            padding: 0.4rem 0.5rem 0.4rem 0 !important;
            margin-bottom: 0.6rem !important;
        }
        
        .message-bubble {
            padding: 8px 12px;
            font-size: 0.9em;
        }
        
        .message-header {
            gap: 6px;
            margin-bottom: 4px;
        }
    }
    
    .reply-banner-custom {
        background: #f0f7ff;
        border: 1px solid #d0e7ff;
        border-radius: 8px;
        padding: 6px 12px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 6px;
        font-size: 0.85em;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    
    @media (max-width: 768px) {
        .reply-banner-custom {
            padding: 5px 10px;
            font-size: 0.8em;
            margin-bottom: 5px;
        }
    }

    /* Premium Toggle Styling (Targeting the specific widget) */
    div[data-testid="stToggle"] {
        background: #ffffff;
        padding: 10px 24px !important;
        border-radius: 50px !important;
        border: 1px solid #ff4b4b22 !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.06) !important;
        transition: all 0.3s ease !important;
        width: fit-content !important;
        margin: 10px auto !important;
    }
    
    div[data-testid="stToggle"]:hover {
        border-color: #ff4b4b !important;
        box-shadow: 0 6px 20px rgba(255,75,75,0.12) !important;
        transform: translateY(-1px);
    }

    /* Target only the main content area toggles to avoid breaking sidebar */
    .stMain div[data-testid="stToggle"] {
        display: flex;
        justify-content: center;
    }

    div[data-testid="stToggle"] label {
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
        margin: 0 !important;
    }

    div[data-testid="stToggle"] label p {
        font-weight: 700 !important;
        font-size: 0.95em !important;
        color: #1a1a1a !important;
        margin: 0 !important;
        letter-spacing: -0.2px !important;
    }
    
    .target-badge {
        font-weight: 600;
        padding: 1px 5px;
        border-radius: 3px;
        font-size: 0.7em;
        color: #444;
        background: rgba(0,0,0,0.08);
        border: 1px solid rgba(0,0,0,0.1);
    }
    
    .status-tag {
        font-size: 0.65em;
        font-weight: 700;
        padding: 1px 4px;
        border-radius: 3px;
        text-transform: uppercase;
        letter-spacing: 0.4px;
    }
    
    /* Reply button optimization */
    button[kind="tertiary"] {
        padding: 0 !important;
        min-height: 24px !important;
        height: 24px !important;
        font-size: 1.1em !important;
    }
    
    @media (max-width: 768px) {
        .target-badge {
            font-size: 0.65em;
            padding: 1px 4px;
        }
        
        .status-tag {
            font-size: 0.6em;
            padding: 1px 3px;
        }
    }
    
    .public-tag { color: #2e7d32; background: #e8f5e9; border: 1px solid #a5d6a7; }
    .direct-tag { color: #c62828; background: #ffebee; border: 1px solid #ffcdd2; }
    .urgent-tag { color: #f57f17; background: #fffde7; border: 1px solid #fff59d; }
    
    /* Typing Indicator */
    .typing-container {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 5px 14px;
        color: #666;
        font-size: 0.85em;
        font-style: italic;
        background: rgba(0,0,0,0.03);
        border-radius: 20px;
        margin: 8px auto;
        width: fit-content;
        border: 1px solid rgba(0,0,0,0.05);
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .typing-dots {
        display: flex; gap: 4px; margin-left: 8px;
    }
    .typing-dot {
        width: 5px; height: 5px; background: #999; border-radius: 50%;
        animation: typing-bounce 1.4s infinite ease-in-out;
    }
    .typing-dot:nth-child(1) { animation-delay: -0.32s; }
    .typing-dot:nth-child(2) { animation-delay: -0.16s; }
    @keyframes typing-bounce {
        0%, 80%, 100% { transform: translateY(0); opacity: 0.3; }
        40% { transform: translateY(-3px); opacity: 1; }
    }
    
    @media (max-width: 768px) {
        .typing-container {
            padding: 4px 12px;
            font-size: 0.8em;
            margin: 6px auto;
        }
    }
    </style>""", unsafe_allow_html=True)

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


# --- SEARCH ENGINE INIT ---
@st.cache_resource
def init_search_engine():
    engine = SearchEngine()
    # Ensure directory exists for persist
    persist = LOCAL_DATA_DIR / "vector_store"
    persist.mkdir(parents=True, exist_ok=True)
    engine.initialize(root_dir=EXECUTION_DIR, persist_dir=persist)
    return engine

# Initialize background service
search_engine = init_search_engine()


# --- DIALOGS ---
def handle_disconnect_agent(agent_name):
    """
    Sets the reload_active flag for the agent.
    Does NOT set 'pending_connection' immediately (Agent must do it via disconnect tool).
    """
    def update_fn(s):
        if agent_name in s.get("agents", {}):
            s["agents"][agent_name]["reload_active"] = True
            # Status remains 'connected'/'working' until Agent calls disconnect()
            
            # Inject System Message for the Agent
            msg = {
                "from": "System",
                "content": RELOAD_INSTRUCTION,
                "public": False,
                "target": agent_name,
                "timestamp": time.time()
            }
            s.setdefault("messages", []).append(msg)
            
        return f"Reload signal sent to: {agent_name}"
    
    state_store.update(update_fn)
    st.toast(f"Reload signal sent to {agent_name} 🔁")

def force_disconnect_agent(agent_name):
    """
    Forces status to pending_connection immediately.
    """
    def update_fn(s):
        if agent_name in s.get("agents", {}):
            s["agents"][agent_name]["reload_active"] = False # Reset flag
            s["agents"][agent_name]["status"] = "pending_connection"
        return f"Force disconnect: {agent_name}"
    state_store.update(update_fn)
    st.toast(f"☠️ Force Disconnect: {agent_name}")

PRESET_DIR = GLOBAL_PRESET_DIR

@st.dialog("Save Scenario")
def save_scenario_dialog(current_config):
    save_name = st.text_input("Save Name", placeholder="my_scenario")
    if st.button("Confirm Save", use_container_width=True):
        if save_name:
            # Basic filename cleaning
            filename = "".join([c for c in save_name if c.isalnum() or c in (' ', '.', '_', '-')]).rstrip()
            path = PRESET_DIR / f"{filename}.json"
            with open(path, "w") as f:
                json.dump(current_config, f, indent=2)
            
            # --- PERSISTENCE TO REPO (DEV MODE) ---
            repo_presets = ASSETS_DIR / "presets"
            if repo_presets.exists() and repo_presets.is_dir():
                repo_path = repo_presets / f"{filename}.json"
                try:
                    with open(repo_path, "w") as f:
                        json.dump(current_config, f, indent=2)
                    st.toast(f"💾 Synced to Repo: {filename}")
                except Exception as e:
                    # Non-blocking, just dev convenience
                    print(f"Failed to sync to repo: {e}")
            st.success(f"Saved: {filename}")
            time.sleep(1)
            st.rerun()
        else:
            st.error("Please enter a name.")

@st.dialog("Load Scenario")
def load_scenario_dialog():
    # Unified Source: User Global Presets
    # (Defaults have been synced here by sync_presets)
    presets = sorted([f for f in os.listdir(PRESET_DIR) if f.endswith(".json")])
    
    if not presets:
        st.warning("No scenarios found.")
        return

    options = [f"💾 {f}" for f in presets]
    path_map = {f"💾 {f}": PRESET_DIR / f for f in presets}
        
    selected_label = st.selectbox("Choose a Preset", options)
    
    c_load, c_del = st.columns([0.85, 0.15])
    
    with c_load:
        if st.button("Load Configuration", use_container_width=True, type="primary"):
            if selected_label:
                path = path_map[selected_label]
                with open(path, "r") as f:
                    new_conf = json.load(f)
                
                # Recalculate total_agents for consistency
                if "profiles" in new_conf:
                    new_conf["total_agents"] = get_total_agents(new_conf["profiles"])
                    
                save_config(new_conf)
                st.success(f"Configuration '{selected_label}' loaded!")
                time.sleep(1)
                st.rerun()
                
    with c_del:
        if st.button("🗑️", key="del_scen_btn", help="Delete permanently", use_container_width=True):
             if selected_label:
                 path = path_map[selected_label]
                 try:
                     os.remove(path)
                     st.toast(f"Scenario deleted: {selected_label}")
                     time.sleep(0.7)
                     st.rerun()
                 except Exception as e:
                     st.error(f"Error: {e}")

def get_total_agents(profiles):
    total = 0
    for p in profiles:
        try:
            total += int(p.get("count", 0))
        except:
            pass
    return total

def format_mentions(text, agent_names=None):
    """
    Format mentions in text with HTML styling.
    FIX BUG #7: Synchronize with logic.py's character-by-character parsing.
    FIX BUG #12: Respect backslash escaping (\@) and backticks to avoid rendering escaped mentions.
    UX IMPROVEMENT: Remove @ from badges to avoid confusion when copying.
    
    Args:
        text: The text to format
        agent_names: List of valid agent names (including "User"). If None, uses a permissive regex.
    """
    if not text: return text
    
    # FIX BUG #12: Strip code blocks (backticks) to avoid rendering mentions inside them
    # We'll process the text in segments: code vs non-code
    # Split by backticks and track which segments are code
    segments = re.split(r'(`[^`]*`)', text)
    
    processed_segments = []
    for i, segment in enumerate(segments):
        # Odd indices are inside backticks (code)
        if i % 2 == 1:
            # This is a code segment, don't process mentions
            processed_segments.append(segment)
            continue
        
        # Even indices are outside backticks (normal text)
        # Process this segment for mentions
        
        # 1. First decorate @everyone (but not \@everyone)
        # UX: Remove @ from badge, show only "everyone"
        segment = re.sub(
            r'(?<!\\)@(everyone)',
            r'<span style="color: #ffffff; background-color: #ff4b4b; padding: 2px 8px; border-radius: 6px; font-weight: 700; font-size: 0.9em; box-shadow: 0 2px 4px rgba(255,75,75,0.3);">\1</span>',
            segment
        )
        
        # 2. Then decorate @AgentName (but not \@AgentName)
        # FIX BUG #7: Use exact matching with agent names (same as logic.py)
        # FIX BUG #12: Use negative lookbehind to avoid matching \@
        # UX: Remove @ from badge, show only agent name
        if agent_names:
            # Build a regex that matches exact agent names
            # Sort by length (longest first) to ensure greedy matching
            sorted_names = sorted(agent_names, key=len, reverse=True)
            # Escape special regex characters in names
            escaped_names = [re.escape(name) for name in sorted_names if name != "everyone"]
            if escaped_names:
                # Negative lookbehind (?<!\\) ensures we don't match \@
                pattern = r'(?<!\\)@(' + '|'.join(escaped_names) + r')(?=\s|$|[^\w])'
                segment = re.sub(
                    pattern,
                    r'<span style="color: #ffffff; background-color: #0d47a1; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 0.85em; box-shadow: 0 1px 3px rgba(0,0,0,0.2);">\1</span>',
                    segment
                )
        else:
            # Fallback: Use permissive pattern (original behavior)
            # FIX BUG #12: Add negative lookbehind for backslash
            # UX: Capture the name without @ and display only the name
            segment = re.sub(
                r'(?<!\\)@((?!everyone)[\w\s()#]+)', 
                r'<span style="color: #ffffff; background-color: #0d47a1; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 0.85em; box-shadow: 0 1px 3px rgba(0,0,0,0.2);">\1</span>', 
                segment
            )
        
        processed_segments.append(segment)
    
    # Rejoin all segments
    return ''.join(processed_segments)

def render_graph(profiles, current_editing=None):
    graph = graphviz.Digraph()
    graph.attr(rankdir='LR', size='12,2', ratio='fill', bgcolor='transparent', margin='0')
    
    # Add User node
    graph.node("User", label="👤 User", style='filled', fillcolor='lightgrey', shape='circle', fontsize='10', height='0.5')
    
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
            if is_auth and (target == "User" or any(prof["name"] == target for prof in profiles)):
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
                // Polled by setInterval, so just return
                return;
            }}

            // Cleanup previous interaction from this or previous iframes
            // We use a custom property on the DOM node to store the controller
            if (textarea._mentionController) {{
                // If the controller belongs to a DEAD iframe, this might fail or succeed. 
                // But mostly it allows us to signal "Stop Listing".
                try {{
                    textarea._mentionController.abort();
                }} catch(e) {{}}
            }}

            // Create new controller for this instance
            const controller = new AbortController();
            textarea._mentionController = controller;
            const signal = controller.signal;

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

            // Inject styles
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
            }}, {{ signal }});

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
            }}, {{ capture: true, signal: signal }});
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

        // Initial setup & Polling for re-mounts
        setInterval(setupMentions, 1000);
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
        border-radius: 16px !important;
        border: 1px solid #f0f0f0 !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.04);
        padding: 0.5rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 24px rgba(0,0,0,0.08);
        border-color: #ff4b4b44 !important;
    }
    .agent-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 12px;
    }
    .agent-icon {
        font-size: 1.5em;
        background: #f8f9fa;
        width: 42px;
        height: 42px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 10px;
        box-shadow: inset 0 0 0 1px rgba(0,0,0,0.05);
    }
    .agent-name {
        font-weight: 800;
        font-size: 1.1em;
        color: #1a1a1a;
        letter-spacing: -0.01em;
    }
    .agent-desc {
        font-size: 0.85em;
        color: #64748b;
        margin-bottom: 1rem;
        min-height: 4.2em;
        line-height: 1.5;
    }
    .count-display {
        background: #f1f5f9;
        color: #0f172a;
        height: 2.4em;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
        font-weight: 700;
        font-size: 1.1em;
    }
    /* Compact buttons in cards */
    [data-testid="stVerticalBlockBorderWrapper"] .stButton button {
        height: 2.4em !important;
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
    
    # Global Autorefresh (Active on all pages to catch messages)
    st_autorefresh(interval=4000, key="global_pulse")

    st.markdown("### Navigation")
    
    # --- NOTIFICATION LOGIC ---
    total_msgs = len(messages)
    if "last_read_count" not in st.session_state:
        st.session_state.last_read_count = total_msgs
        st.session_state.last_toast_count = total_msgs

    unread = 0
    if st.session_state.page != "Communication":
        unread = max(0, total_msgs - st.session_state.last_read_count)
        
        # Toast for new messages
        if "last_toast_count" not in st.session_state:
             st.session_state.last_toast_count = total_msgs
             
        if total_msgs > st.session_state.last_toast_count:
             new_count = total_msgs - st.session_state.last_toast_count
             # Toast the last one
             newest = messages[-1]
             sender = newest.get("from", "?")
             content = newest.get("content", "")
             preview = (content[:60] + "...") if len(content) > 60 else content
             st.toast(f"📨 {sender}: {preview}", icon="🔔")
             st.session_state.last_toast_count = total_msgs
    else:
        # On Chat Page -> Mark all read
        st.session_state.last_read_count = total_msgs
        st.session_state.last_toast_count = total_msgs

    label_comm = "💬 Communication"
    if unread > 0:
        label_comm = f"💬 Chat ({unread} 🔴)"

    if st.button(label_comm, use_container_width=True, type="primary" if st.session_state.page == "Communication" else "secondary"):
        st.session_state.page = "Communication"
        st.rerun()
        
    if st.button("🎛️ Cockpit", use_container_width=True, type="primary" if st.session_state.page == "Cockpit" else "secondary"):
        st.session_state.page = "Cockpit"
        st.rerun()
        
    if st.button("🛠️ Editor", use_container_width=True, type="primary" if st.session_state.page == "Editor" else "secondary"):
        st.session_state.page = "Editor"
        st.rerun()

    if st.button("📝 Notes", use_container_width=True, type="primary" if st.session_state.page == "Notes" else "secondary"):
        st.session_state.page = "Notes"
        st.rerun()

    # Dynamic Streamlit Page
    streamlit_path = EXECUTION_DIR / "mamcp-streamlit"
    if streamlit_path.exists() and streamlit_path.is_dir(): 
        if st.button("📊 Streamlit", use_container_width=True, type="primary" if st.session_state.page == "Streamlit" else "secondary"):
            st.session_state.page = "Streamlit"
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
        
        # Public system message about availability
        def announce_availability(s):
            if new_status == "available":
                content = "The user has reconnected and is available again."
            else:
                content = "The user has disconnected. He will let you know when he is back. Please continue your work autonomously."
            
            msg = {
                "from": "System",
                "content": content,
                "timestamp": time.time(),
                "public": True,
                "target": "all"
            }
            s.setdefault("messages", []).append(msg)
            return "Availability Announced"
        
        state_store.update(announce_availability)
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
    


    st.divider()

    # 2. PERMANENT ROSTER (v2.0)
    connected_count = len([n for n, d in agents.items() if n != "User" and d.get("status") == "connected"])
    st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px;">
            <h3 style="margin: 0; font-size: 1.2em;">👥 Active Agents</h3>
            <span style="background: #e0e0e0; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; font-weight: bold;">{connected_count}</span>
        </div>
    """, unsafe_allow_html=True)
    
    # Get queue data for priority display (UI Enhancement)
    queue_raw = turn.get("queue", [])
    queue_counts = {}
    queue_items = {}  # Store full queue items for sorting
    for item in queue_raw:
        if isinstance(item, dict):
            name = item.get("name")
            queue_counts[name] = item.get("count", 0)
            queue_items[name] = item
    
    # Build roster list sorted by turn priority (FIX: User request for proper ordering)
    # 1. User always first
    # 2. Current turn agent (if not User)
    # 3. Agents in queue (sorted by count DESC, timestamp ASC)
    # 4. Other agents
    current_turn = turn.get("current")
    roster_list = ["User"]
    
    # Add current turn agent (if not User and not already in list)
    if current_turn and current_turn != "User" and current_turn not in roster_list:
        roster_list.append(current_turn)
    
    # Add agents from queue (sorted by priority: count DESC, timestamp ASC)
    queue_sorted = sorted(
        [(name, item) for name, item in queue_items.items()],
        key=lambda x: (-x[1].get("count", 0), x[1].get("timestamp", 0))
    )
    for name, _ in queue_sorted:
        if name not in roster_list and name in agents:
            roster_list.append(name)
    
    # Add remaining agents not in queue
    for name in agents.keys():
        if name not in roster_list:
            roster_list.append(name)
    
    if not roster_list:
        st.caption("No agents detected.")
    else:
        for name in roster_list:
            # Handle User specifically since they are not in 'agents' dict
            if name == "User":
                u_avail = config.get("user_availability", "busy")
                # Map 'available' -> 'connected' (Green), 'busy' -> 'working' (Blue/Busy look)
                info = {
                    "status": "connected" if u_avail == "available" else "working",
                    "emoji": "👤"
                }
            else:
                info = agents[name]
            status = info.get("status", "pending")
            emoji = info.get("emoji", "🤖")
            is_turn = (name == current_turn)
            
            card_class = "active-turn" if is_turn else ""
            
            if info.get("reload_active"):
                status_color = "#FF5722" # Deep Orange
                status_label = "Disconnecting..."
                bg = "rgba(255, 87, 34, 0.1)"
                border_color = "rgba(255, 87, 34, 0.3)"
            elif status == "connected":
                status_color = "#4CAF50" # Green
                status_label = "Online"
                bg = "rgba(76, 175, 80, 0.05)"
                border_color = "rgba(76, 175, 80, 0.2)"
            elif status == "pending_connection":
                status_color = "#FF9800" # Orange
                status_label = "Waiting for Reconnection"
                bg = "rgba(255, 152, 0, 0.05)"
                border_color = "rgba(255, 152, 0, 0.2)"
            elif status == "working":
                status_color = "#2196F3" # Blue
                status_label = "Working..."
                bg = "rgba(33, 150, 243, 0.05)"
                border_color = "rgba(33, 150, 243, 0.2)"
            else:
                status_color = "#9E9E9E" # Grey
                status_label = "Offline"
                bg = "transparent"
                border_color = "#eee"
            
            # Additional pulse if it's their turn and they are connected
            is_active_working = is_turn and status == "connected"
            if is_active_working:
                status_color = "#2196F3"
                status_label = "In action..."
            
            # Get mention count for this agent (UI Enhancement)
            mention_count = queue_counts.get(name, 0)
            mention_badge = f'<span style="background: #ff4b4b; color: white; padding: 2px 6px; border-radius: 8px; font-size: 0.7em; font-weight: 700; margin-left: 6px;" title="Mentions in queue">{mention_count}</span>' if mention_count > 0 else ''
            
            card_html = f"""<div class="{card_class}" style="background-color: {bg}; border: 1px solid {border_color}; border-radius: 10px; padding: 10px 14px; margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between; transition: all 0.3s ease;"><div style="display: flex; align-items: center; gap: 12px;"><div style="font-size: 1.4em; background: white; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">{emoji}</div><div style="display: flex; flex-direction: column;"><div style="display: flex; align-items: center;"><span style="font-weight: 600; color: {'#1a1a1a' if status == 'connected' else '#666'}; font-size: 0.95em;">{name}</span>{mention_badge}</div><div style="display: flex; align-items: center; gap: 4px;"><div style="width: 6px; height: 6px; background-color: {status_color}; border-radius: 50%;"></div><span style="font-size: 0.7em; color: {status_color}; font-weight: 500; letter-spacing: 0.5px;">{status_label}</span></div></div></div>{'<span style="font-size: 1.2em;" title="It is their turn!">✨</span>' if is_turn else ''}</div>"""
            
            if name == "User":
                st.markdown(card_html, unsafe_allow_html=True)
            else:
                c_card, c_btn = st.columns([0.82, 0.18])
                with c_card:
                    st.markdown(card_html, unsafe_allow_html=True)
                with c_btn:
                    # Center the button vertically relative to card is hard, but simple button works
                    # Add some top margin to align with card center approx
                    st.markdown('<div style="height: 6px;"></div>', unsafe_allow_html=True)
                    agent_info = agents.get(name, {})
                    is_reloading = agent_info.get("reload_active") or (name in st.session_state.get("reload_queue", []))

                    if is_reloading:
                        if st.button("❌", key=f"force_{name}", help="Force Disconnect (If blocked)", type="primary"):
                             force_disconnect_agent(name)
                             # Also remove from queue if present to unblock sequence
                             if name in st.session_state.get("reload_queue", []):
                                 st.session_state.reload_queue.remove(name)
                             st.rerun()
                    else:
                        if st.button("🔄", key=f"reload_{name}", help=f"Recharger {name}"):
                            handle_disconnect_agent(name)
                            st.rerun()
            
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    if st.button("🔄 Reload All Agents", type="secondary", use_container_width=True, help="Reload sequence (Parallel)."):
         # Identify Targets
        to_reload = [
            n for n, d in agents.items() 
            if d.get("status") in ["connected", "working"] 
        ]
        if not to_reload:
            st.toast("No active agents to reload.")
        else:
            # START PARALLEL SEQUENCE
            st.session_state.reload_queue = list(to_reload)
            
            # Atomic Bulk Update
            def bulk_reload_signal(s):
                count = 0
                for name in to_reload:
                    if name in s.get("agents", {}):
                         s["agents"][name]["reload_active"] = True
                         # Inject System Message (Private to Agent)
                         msg = {
                            "from": "System",
                            "content": RELOAD_INSTRUCTION,
                            "public": False,
                            "target": name,
                            "timestamp": time.time()
                         }
                         s.setdefault("messages", []).append(msg)
                         count += 1
                return f"Global reload signal sent ({count} agents)."

            
            state_store.update(bulk_reload_signal)
            st.session_state.is_reloading_all = True # Local flag to post final message
            st.toast(f"PARALLEL reload sequence initialized for {len(to_reload)} agents.")
            st.rerun()

    # --- SEQUENTIAL RELOAD PROCESSOR ---
    # Global Processor for the Queue
    if "reload_queue" in st.session_state and st.session_state.reload_queue:
        current_target = st.session_state.reload_queue[0]
        
        # Check current status (Refetch from fresh state)
        if current_target in agents:
            agent_data = agents[current_target]
            status = agent_data.get("status")
            is_reload_active = agent_data.get("reload_active")
            
            # Condition 1: Agent is finished (Disconnect/Pending)
            if status in ["pending_connection", "disconnected", "offline"]:
                st.session_state.reload_queue.pop(0) # Done
                
                # Check if it was the last one
                if not st.session_state.reload_queue:
                    def post_reload_done(s):
                        # Reset all reload flags
                        for a in s.get("agents", {}).values():
                            a["reload_active"] = False
                        
                        return "Reload Done"
                    state_store.update(post_reload_done)
                    st.toast("✅ Full System Reload Done!")

                st.rerun() # Proceed to next immediately
                
            # Condition 2: Agent needs to be signaled
            elif not is_reload_active:
                 handle_disconnect_agent(current_target)
                 st.rerun()
                 
            # Condition 3: Waiting for agent...
            else:
                # Just wait. The autorefresh will loop us.
                st.toast(f"⏳ Waiting for disconnection: {current_target}...")
        else:
            # Agent gone? Remove from queue
            st.session_state.reload_queue.pop(0) 
            st.rerun()

    st.divider()

    # --- PAUSE CONTROL ---
    is_paused = config.get("paused", False)
    if st.toggle("⏸️ PAUSE MCP", value=is_paused, help="Freezes time for all agents."):
        if not is_paused:
            config["paused"] = True
            save_config(config)
            st.rerun()
    else:
        if is_paused:
            config["paused"] = False
            save_config(config)
            st.rerun()
            
    if is_paused:
        st.warning("⚠️ SIMULATION PAUSED")
    
    st.divider()

    
    # Debug Tools
    with st.expander("🔧 DEBUG"):
        st.markdown("### 🔎 Search Engine")
        
        # Status Indicator
        if search_engine and search_engine.initialized:
            dev_label = search_engine.device.upper().replace("”", "") 
            st.caption(f"Status: **Active** | Device: **{dev_label}** ⚡")
        else:
            st.caption("Status: 🔴 Disabled (Missing Deps)")

        search_conf = config.get("search", {})
        
        sc1, sc2 = st.columns(2)
        with sc1:
            x_val = st.number_input("Context (X)", min_value=0, max_value=10, value=search_conf.get("x_markdown", 3), help="Number of full markdown result to inject (Passive)")
        with sc2:
            y_val = st.number_input("Total (Y)", min_value=1, max_value=50, value=search_conf.get("y_total", 15), help="Default limit for Search Tool")
            
        if x_val != search_conf.get("x_markdown", 3) or y_val != search_conf.get("y_total", 15):
            if "search" not in config: config["search"] = {}
            config["search"]["x_markdown"] = x_val
            config["search"]["y_total"] = y_val
            save_config(config)
            st.toast("Search config saved!")
            time.sleep(0.5)
            st.rerun()

        st.divider()

        st.markdown("### ✂️ MCP Truncation Settings")
        current_trunc = config.get("truncation_limit", 4096) # Default 4096
        new_trunc = st.number_input("Max Character Limit (0 = Disabled)", min_value=0, value=int(current_trunc), step=100, help="Limite manuelle pour éviter le tronquage silencieux du client MCP (4096 bytes max).")
        if new_trunc != current_trunc:
             config["truncation_limit"] = int(new_trunc)
             save_config(config)
             st.rerun()
             
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
    # 0. Global Filter State
    is_urgent_focus = st.session_state.get("is_urgent_focus", False)

    c_title, c_status = st.columns([6, 4])
    with c_title:
        st.header("💬 Neural Stream")
    with c_status:
        current_turn = turn.get("current", "?")
        if current_turn == "User":
            # FOCUS MODE STYLES
            st.markdown("""
            <style>
            /* Gray out previous messages to focus on input */
            .stChatMessage { opacity: 0.5; filter: grayscale(0.6); transition: all 0.3s; }
            /* Highlight Input Area */
            div[data-testid="stChatInput"] { 
                border: 2px solid #ff3d00 !important; 
                border-radius: 12px;
                box-shadow: 0 0 15px rgba(255, 61, 0, 0.4) !important;
                background-color: #fff8f5 !important;
            }
            </style>
            """, unsafe_allow_html=True)
            

        else:
            st.markdown(f"""<div style="background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 10px; border-radius: 8px; text-align: center;"><span style="color: #6c757d; font-size: 0.9em;">Waiting for:</span><br><span style="color: #1f1f1f; font-weight: bold; font-size: 1.1em;">🤖 {current_turn}</span></div>""", unsafe_allow_html=True)
    
    # 1. Reply Context State
    if "reply_to" not in st.session_state:
        st.session_state.reply_to = None

    # --- FLUX NEURAL (FULL WIDTH) ---
    
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
        # GOD MODE: Always True to allow Admin (User) to see everything
        is_relevant = True 
        # is_relevant = m.get("public", False) or m.get("target") == "User" or m.get("from") == "User"
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
    if "stream_limit" not in st.session_state: st.session_state.stream_limit = 25
    total_stream = len(stream_msgs)
    limit_stream = st.session_state.stream_limit
    if total_stream > limit_stream:
            # UI Minimaliste (Tertiary)
            if st.button(f"🔃 History ({total_stream - limit_stream})", key="load_more_stream", type="tertiary"):
                st.session_state.stream_limit += 25
                st.rerun()
    
    visible_stream = stream_msgs[max(0, total_stream - limit_stream):]
    
    if not visible_stream:
        st.info("No activity detected on neural bands.")
        
    for real_idx, m in visible_stream:
        sender = m.get("from", "?")
        target = m.get("target", "?")
        content = m.get("content", "")
        is_public = m.get("public", False)
        timestamp = m.get("timestamp", 0)
        is_replied = m.get("replied", False)
        
        # FORMAT MENTIONS
        # Build list of all agent names (including User) for exact matching
        all_agent_names = list(agents.keys()) + ["User"]
        content_visual = format_mentions(content, agent_names=all_agent_names)
        
        agent_info = agents.get(sender, {})
        sender_emoji = agent_info.get("emoji", "🤖") if sender != "System" else "💾"
        if sender == "User": sender_emoji = "👤"
        
        # Extract mentions from content for better target display (UI Enhancement)
        # Parse mentions using same logic as backend
        mentioned_agents = []
        if target == "Queue":
            # Extract mentions from content
            import re
            content_no_code = re.sub(r'`[^`]*`', lambda m: ' ' * len(m.group(0)), content)
            for agent_name in all_agent_names:
                if f'@{agent_name}' in content_no_code:
                    mentioned_agents.append(agent_name)
        
        # Format target display
        if target == "Queue" and mentioned_agents:
            target_display = ", ".join(mentioned_agents)
        else:
            target_display = target if target != 'all' else 'everyone'
        
        # Style and Tag Logic
        tag_html = ""
        bubble_style = ""
        
        if is_public:
            tag_html = ''
            bubble_style = "background-color: rgba(248, 249, 250, 0.8); border-left: 4px solid #2e7d32;"
        else:
            if target == "User":
                tag_html = '<span class="status-tag direct-tag">🔒 Direct Link</span>'
                if not is_replied:
                    tag_html += '<span class="status-tag urgent-tag">⚡ Action Required</span>'
                    bubble_style = "background-color: #fffdf0; border-left: 4px solid #fbc02d; box-shadow: 0 4px 12px rgba(251, 192, 45, 0.12);"
                else:
                    bubble_style = "background-color: #f0f7ff; border-left: 4px solid #1976d2;"
            elif sender == "User":
                tag_html = f'<span class="status-tag">📤 Outgoing to {target_display}</span>'
                bubble_style = "background-color: #ffffff; border-left: 4px solid #94a3b8;"
            else:
                tag_html = f'<span class="status-tag direct-tag" style="background: #ffebee; color: #c62828;">🔒 Private {sender} → {target_display}</span>'
                bubble_style = "background-color: #fff8f8; border: 2px dashed #ff4b4b;"

        with st.chat_message(sender, avatar=sender_emoji):
            # Header with sender, target, status tags and reply button
            c_header, c_reply = st.columns([11, 1])
            
            with c_header:
                st.markdown(f"""<div class="message-header"><div style="font-size: 1.2em; line-height: 1;">{sender_emoji}</div><span style="font-weight: 700; color: #333; font-size: 0.9em;">{sender}</span><span style="color: #999; font-size: 0.8em;">→</span><span class="target-badge">{target_display}</span>{tag_html}<span style="color: #bbb; font-size: 0.7em;">{time.strftime('%H:%M:%S', time.localtime(timestamp))}</span></div>""", unsafe_allow_html=True)
            
            with c_reply:
                render_reply_button(sender, content, real_idx)

            # Message Content
            st.markdown(f"""<div class="message-bubble" style="{bubble_style}"><div style="color: #1f1f1f; line-height: 1.5;">\n\n{content_visual}</div></div>""", unsafe_allow_html=True)


    # --- UI CONTROLS (Above Input) ---
    # 1. Reply Banner
    if st.session_state.reply_to:
        ctx = st.session_state.reply_to
        col_banner, col_x = st.columns([11, 1])
        with col_banner:
            st.markdown(f'<div class="reply-banner-custom">↩️ Reply to <b>{ctx["sender"]}</b>: "{ctx["preview"]}"</div>', unsafe_allow_html=True)
        with col_x:
            if st.button("✖️", key="cancel_reply_v6", help="Cancel"):
                st.session_state.reply_to = None
                st.rerun()

    # 2. Status & Focus Row
    # (No extra spacer here to avoid empty divs)
    
    # 2a. Typing Indicator (Centered)
    typing_agents = []
    current_turn_name = turn.get("current")
    for name, info in agents.items():
        if name == "User": continue
        if info.get("status") == "working" or (name == current_turn_name and info.get("status") == "connected"):
            typing_agents.append(name)
    
    if typing_agents:
        agent_names = ", ".join(typing_agents)
        plural = "are" if len(typing_agents) > 1 else "is"
        st.markdown(f'<div class="typing-container">{agent_names} {plural} typing...<div class="typing-dots"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div></div>', unsafe_allow_html=True)
    
    # 2b. Focus Toggle (Removed)
    c1, c2, c3 = st.columns([1, 1, 1])
    
    # MOVED: Banner in bottom right (c3)
    if turn.get("current") == "User":
        with c3:
            st.markdown("""<div style="background-color: #fff3cd; border: 2px solid #ff3d00; padding: 8px; border-radius: 8px; text-align: center; animation: pulse 2s infinite;"><span style="color: #bf360c; font-weight: 900; font-size: 0.9em; text-transform: uppercase;">⚡ YOUR TURN ⚡</span></div><style>@keyframes pulse {0% { box-shadow: 0 0 0 0 rgba(255, 61, 0, 0.4); } 70% { box-shadow: 0 0 0 15px rgba(255, 61, 0, 0); } 100% { box-shadow: 0 0 0 0 rgba(255, 61, 0, 0); }}</style>""", unsafe_allow_html=True)

    # --- OMNI-CHANNEL INPUT ---
    # Maintain original order for mention system
    connected_agents = [name for name in agents.keys() if agents[name].get("status") == "connected" and name != "User"]
    
    # We still need this for the mention system to know the list, adding everyone
    # FIXED: Moved injection to bottom to ensure DOM readiness
    # inject_mention_system(["everyone"] + connected_agents)

    # Private toggle for user messages
    user_private_mode = st.toggle("🔒 Private Message", value=True, help="If enabled, only mentioned agents will see your message.")

    # Main Input
    if prompt := st.chat_input("Message..."):
        def send_omni_msg(s):
            # Use toggle state for public/private
            is_private = user_private_mode
            public = not is_private
            reply_ref_id = None
            
            # --- MENTION PARSING (Same logic as agents - dedupe per message) ---
            known_agents = s.get("agents", {})
            
            # FIX BUG #15 & #16: Build profile_map and Scan properly for Multi-word agent names
            # Logic: Match known agent names (and profile refs) in the string, prioritizing longest matches 
            # but respecting appearance order.
            
            profile_map = {}
            for name, data in known_agents.items():
                pref = data.get("profile_ref")
                if pref:
                    profile_map[pref] = name
            
            # 1. Build a map of {Token: AgentName} for all possible valid mentions (Full Name & Profile Name)
            # We want to search for "@FullName" or "@ProfileName"
            mention_candidates = {}
            for name in known_agents.keys():
                mention_candidates[name] = name # "Agent B (Private Tester)" -> "Agent B (Private Tester)"
            for prof, real in profile_map.items():
                mention_candidates[prof] = real # "Agent_B" -> "Agent B (Private Tester)"
            mention_candidates["User"] = "User"

            # 2. Find all occurrences
            found_mentions_raw = [] # list of (start_index, end_index, resolved_name)
            
            # We iterate over all candidates and find their positions in the text
            for candidate_key, resolved_name in mention_candidates.items():
                # Search for @candidate_key
                # We use regex escape to handle parentheses in names
                pattern = r'@' + re.escape(candidate_key)
                for match in re.finditer(pattern, prompt):
                    found_mentions_raw.append((match.start(), match.end(), resolved_name))
            
            # 3. Sort by position (asc), then by length (desc) to handle prefixes/overlaps
            # Example: @Agent B vs @Agent B (Private Tester). We want the longer one if they start at same pos.
            found_mentions_raw.sort(key=lambda x: (x[0], -(x[1]-x[0])))
            
            valid_mentions = []
            seen_agents = set()
            last_end = -1
            
            for start, end, resolved_name in found_mentions_raw:
                # If this mention starts after the previous one ended, it's valid (no overlap)
                if start >= last_end:
                    if resolved_name not in seen_agents:
                        valid_mentions.append(resolved_name)
                        seen_agents.add(resolved_name)
                    last_end = end
            
            # Prepare content with Reply Context
            final_content = prompt
            if st.session_state.reply_to:
                ref = st.session_state.reply_to
                final_content = f"↪️ [Reply to {ref['sender']}: \"{ref['preview']}\"]\n{prompt}"
                reply_ref_id = ref["id"]
            
            # Determine target
            if valid_mentions:
                target = valid_mentions[0]  # Primary target for display
                audience = valid_mentions[1:]  # Additional audience
            elif st.session_state.reply_to:
                target = st.session_state.reply_to["sender"]
                audience = []
                if not public:
                    public = False  # Reply context forces private unless explicit
            else:
                # Fallback: If no mention and no reply_to, we still allow it but warn if it's potentially invisible
                if is_private:
                    # Try to find the last active agent to avoid "Ghost Messages"
                    connected = [n for n, d in s.get("agents", {}).items() if d.get("status") == "connected"]
                    if connected:
                        target = connected[0]
                    else:
                        return "🚫 ERROR: No target identified. Private messages MUST mention a recipient or be a reply!"
                else:
                    target = "all"
                audience = []


            msg = {
                "from": "User",
                "content": final_content,
                "timestamp": time.time(),
                "public": public,
                "audience": audience,
                "target": target,
                "mentions": valid_mentions # Explicitly store mentions for filtering
            }

                
            if "messages" not in s: s["messages"] = []
            s["messages"].append(msg)
            
            # CRITICAL: Update timestamp for Anti-Ghost logic in logic.py
            if "turn" not in s: s["turn"] = {}
            s["turn"]["last_user_message_time"] = msg["timestamp"]
            
            # --- TURN MANAGEMENT ---
            # 1. ALWAYS Update Queue from User Mentions (even if out of turn)
            # This ensures that if User says "@AgentA", AgentA gets priority for the NEXT turn
            from src.core.models import TurnQueueItem
            
            queue_raw = s.get("turn", {}).get("queue", [])
            queue_objs = []
            for item in queue_raw:
                if isinstance(item, dict):
                    queue_objs.append(TurnQueueItem(**item))
                else:
                    queue_objs.append(item)
            
            # Add mentions to queue (same logic: +1 per unique mention per message)
            max_ts = max([i.timestamp for i in queue_objs], default=0.0)
            base_ts = max(time.time(), max_ts + 0.001)
            
            for idx, vm in enumerate(valid_mentions):
                existing = next((i for i in queue_objs if i.name == vm), None)
                if existing:
                    existing.count += 1
                else:
                    queue_objs.append(TurnQueueItem(
                        name=vm,
                        count=1,
                        timestamp=base_ts + (idx * 0.001)
                    ))
            
            s["turn"]["queue"] = [i.model_dump() for i in queue_objs]

            # 2. Transition Logic (Only if it WAS the User's turn)
            if s.get("turn", {}).get("current") == "User":
                # Now finalize transition using centralized logic
                from src.core.logic import Engine
                engine = Engine(state_store)
                
                # FIX BUG #10/14: Improved transition logic
                target_to_summon = None
                if valid_mentions:
                    target_to_summon = valid_mentions[0]
                elif st.session_state.get("reply_to"):
                    target_to_summon = st.session_state.reply_to["sender"]
                
                if target_to_summon and target_to_summon in s.get("agents", {}) and s.get("agents", {}).get(target_to_summon, {}).get("status") == "connected":
                     engine._finalize_turn_transition(s, target_to_summon)
                else:
                    # Fallback to configured first agent preference
                    first_pref = s.get("turn", {}).get("first_agent")
                    if first_pref and first_pref in s.get("agents", {}) and s.get("agents", {}).get(first_pref, {}).get("status") == "connected":
                        engine._finalize_turn_transition(s, first_pref)
                    else:
                        # Fallback: use any connected agent
                        connected = [n for n, d in s.get("agents", {}).items() if d.get("status") == "connected"]
                        if connected:
                            engine._finalize_turn_transition(s, connected[0])
                        # If no one connected, turn remains/goes to User by default


            # Context Cleanup
            if reply_ref_id is not None:
                if reply_ref_id < len(s["messages"]):
                     s["messages"][reply_ref_id]["replied"] = True
                     
            return "Message Sent."

        res = state_store.update(send_omni_msg)
        st.session_state.reply_to = None
        st.toast(res)
        st.rerun()



# ==========================================
# PAGE: COCKPIT (Admin)
# ==========================================
elif st.session_state.page == "Cockpit":
    st.header("🎛️ Supervision Cockpit")
    
    # --- 0. GRAPHVIZ VIEW (TOP) ---
    with st.expander("🕸️ Fleet Topology (Graphviz)", expanded=False):
        try:
            g = render_graph(profiles)
            st.graphviz_chart(g, use_container_width=True)
        except Exception as e:
            st.error(f"Graph rendering error: {e}")

    # Scenarios
    st.subheader("💾 Scenarios")
    with st.container(border=True):
        col_scen1, col_scen2 = st.columns(2)
        if col_scen1.button("💾 Save", use_container_width=True, help="Save current configuration"):
            save_scenario_dialog(config)
        if col_scen2.button("📂 Load", use_container_width=True, help="Load an existing configuration"):
            load_scenario_dialog()

    # Global Context (Full Width)
    st.subheader("🌍 Global Context")
    with st.container(border=True):
        enable_backlog = st.checkbox("Backlog", value=config.get("enable_backlog", False), help="If checked, agents will consult and update BACKLOG.md at the root.")
        if enable_backlog != config.get("enable_backlog", False):
            config["enable_backlog"] = enable_backlog
            save_config(config)
            st.rerun()


        global_context = st.text_area("Narrative / Shared Context", config.get("context", ""), height=215)
        unavailable_suffix = st.text_area("User Unavailable Message (Suffix)", config.get("user_unavailable_suffix", ""), height=150, help="Text added to the default message when the user is unavailable.")
        
        if global_context != config.get("context", "") or unavailable_suffix != config.get("user_unavailable_suffix", ""):
            if st.button("Update Context & Suffix", use_container_width=True):
                config["context"] = global_context
                config["user_unavailable_suffix"] = unavailable_suffix
                save_config(config)
                st.success("Configuration updated")

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
                        
                        st.markdown(f"""<div class="agent-header"><div class="agent-icon">{emoji}</div><div class="agent-name">{p['name']}</div></div><div class="agent-desc">{description}</div>""", unsafe_allow_html=True)
                        
                        # Controls inside the card
                        ctrl_c1, ctrl_c2, ctrl_c3 = st.columns([1, 1.2, 1])
                        if ctrl_c1.button("➖", key=f"d_{i+j}", use_container_width=True):
                            p["count"] = max(0, count - 1)
                            save_config(config)
                            st.rerun()
                        
                        ctrl_c2.markdown(f'<div class="count-display">{count}</div>', unsafe_allow_html=True)
                        
                        if ctrl_c3.button("➕", key=f"i_{i+j}", use_container_width=True):
                            p["count"] = count + 1
                            save_config(config)
                            st.rerun()
                            
                        if st.button("✏️ Modifier", key=f"ed_{i+j}", use_container_width=True, type="secondary"):
                            st.session_state.editing_agent_name = p["name"]
                            st.session_state.page = "Editor"
                            st.rerun()

    st.markdown("---")

    # --- 2.5 FIRST SPEAKER SELECTOR ---
    st.subheader("🎯 Start Sequence")
    potential_agents = []
    
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
        st.session_state.first_speaker = potential_agents[0] if potential_agents else ""

    # Check if current choice is still valid (profiles might have changed)
    if st.session_state.first_speaker not in potential_agents:
        st.session_state.first_speaker = potential_agents[0] if potential_agents else ""

    selected_first = st.selectbox("Who will reply first to the user?", potential_agents,
                                 index=potential_agents.index(st.session_state.first_speaker) if st.session_state.first_speaker in potential_agents else 0,
                                 help="The agent who will have the first turn to respond to the user's first message.")
    st.session_state.first_speaker = selected_first

    st.markdown("<br>", unsafe_allow_html=True)

    # --- 3. RESET BUTTON (MODERN) ---
    col_r1, col_r2, col_r3 = st.columns([1, 2, 1])
    with col_r2:
        if st.button("🚀 INITIALIZE SIMULATION", type="primary", use_container_width=True, help="Resets all agents and the conversation"):
            first_speaker_choice = st.session_state.first_speaker
            
            def reset_logic(s):
                s["conversation_id"] = str(uuid.uuid4())
                s["messages"] = []
                s["turn"] = {"current": "User", "next": None, "first_agent": first_speaker_choice}
                s["config"]["context"] = global_context
                
                # Use profiles from the state s for absolute consistency
                current_profiles = s["config"].get("profiles", [])
                
                # Update total agents count
                total_count = get_total_agents(current_profiles)
                s["config"]["total_agents"] = total_count
                
                pending_slots = []
                # Remove random shuffle to maintain profile order
                for p in current_profiles:
                    for _ in range(int(p.get("count", 0))):
                        pending_slots.append({
                            "profile_ref": p["name"],
                            "role": p.get("system_prompt", ""),
                            "display_base": p.get("display_name") or p["name"],
                            "emoji": p.get("emoji", "🤖")
                        })
                
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
                
                s.setdefault("messages", []).append({
                    "from": "System", "content": f"🟢 SIMULATION RESET. Waiting for the user. (First respondent: {first_speaker_choice})", "public": True, "timestamp": time.time()
                })
                return "Reset completed"
            msg = state_store.update(reset_logic)
            st.toast(msg)
            time.sleep(0.5)
            st.session_state.page = "Communication"
            st.rerun()


# ==========================================
# PAGE: EDITOR (Admin)
# ==========================================
elif st.session_state.page == "Editor":
    st.header("🛠️ Agent Editor")
    
    profile_names = [p["name"] for p in profiles]
    profile_names.append("➕ Create New")
    
    sel_idx = 0
    cur_edit = st.session_state.get("editing_agent_name")
    if cur_edit in profile_names:
        sel_idx = profile_names.index(cur_edit)
        
    selected_name = st.selectbox("Profile Selection", profile_names, index=sel_idx, key="edit_sel_page")
    
    if selected_name == "➕ Create New":
        current_profile = {
            "name": "New Agent", 
            "description": "", 
            "emoji": "🤖", # Default, will be randomized in session state
            "connections": [], 
            "count": 1, 
            "capabilities": ["public"]
        }
        new_mode = True
        st.session_state.editing_agent_name = "New Agent"
        
        # Initialize with a random emoji if not already set
        emoji_key = f"editing_emoji_{selected_name}"
        if emoji_key not in st.session_state:
            st.session_state[emoji_key] = get_random_emoji()
    else:
        current_profile = next((p for p in profiles if p["name"] == selected_name), None)
        new_mode = False
        st.session_state.editing_agent_name = selected_name
        
        if st.button("🗑️ Delete Profile", type="primary"):
             config["profiles"] = [p for p in profiles if p["name"] != selected_name]
             emoji_key = f"editing_emoji_{selected_name}"
             if emoji_key in st.session_state:
                 del st.session_state[emoji_key]
             save_config(config)
             st.rerun()

    if current_profile:
        st.markdown("---")
        # Layout Spacieux (Columns)
        c_main, c_disp = st.columns([3, 2])
        
        with c_main:
            c_emoji, c_name = st.columns([0.18, 0.82])
            
            emoji_key = f"editing_emoji_{selected_name}"
            if emoji_key not in st.session_state:
                st.session_state[emoji_key] = current_profile.get("emoji", "🤖")
            current_emoji = st.session_state[emoji_key]
            
            with c_emoji:
                st.markdown('<div style="height: 28px;"></div>', unsafe_allow_html=True) # Spacer to align with text input label
                with st.popover(f"{current_emoji}", use_container_width=True):
                    cols = st.columns(8)
                    for idx, emoji in enumerate(EMOJI_LIST):
                        if cols[idx % 8].button(emoji, key=f"emoji_btn_{selected_name}_{idx}"):
                            st.session_state[emoji_key] = emoji
                            st.rerun()
            
            with c_name:
                new_name = st.text_input("Name", current_profile.get("name", ""), key=f"edit_name_{selected_name}")

        with c_disp:
            disp = st.text_input("Display Name", current_profile.get("display_name", ""), key=f"edit_disp_{selected_name}")
        
        new_desc = st.text_input("Description", current_profile.get("description", ""), key=f"edit_desc_{selected_name}")
        new_prompt = st.text_area("System Prompt", current_profile.get("system_prompt", ""), height=300, key=f"edit_prompt_{selected_name}")
        
        st.subheader("Communication Capabilities")
        caps = current_profile.get("capabilities", [])
        
        # Preserve other capabilities (e.g. shell_exec)
        other_caps = [c for c in caps if c not in ["public", "private"]]
        
        has_pub = "public" in caps
        has_priv = "private" in caps
        
        # Determine default index
        default_idx = 0 # Public
        if has_pub and has_priv:
            default_idx = 2 # Both
        elif has_priv and not has_pub:
            default_idx = 1 # Private
        
        comm_mode = st.radio(
            "Communication Scope",
            ["Public", "Private", "Both (Public & Private)"],
            index=default_idx,
            key=f"comm_mode_{selected_name}",
            horizontal=True,
            help="Defines the allowed communication scope for this agent."
        )
        
        new_caps = list(other_caps)
        if comm_mode == "Public":
            new_caps.append("public")
        elif comm_mode == "Private":
            new_caps.append("private")
        else:
            new_caps.append("public")
            new_caps.append("private")

        st.subheader("Connections")
        st.info("Define who this agent can contact and for what purpose (strategic context).")
        
        other_profile_names = [p["name"] for p in profiles if p["name"] != current_profile.get("name")]
        # Standardize targets to title case for matching with state.json while keeping user/public accessible
        targets = ["public", "User"] + other_profile_names
        
        new_connections = []
        
        # Header for the "Table"
        with st.container():
            h1, h2, h3 = st.columns([2, 5, 1])
            h1.markdown("**Target**")
            h2.markdown("**Condition / Context**")
            h3.markdown("**Active**")
            st.markdown("<hr style='margin-top: 0; margin-bottom: 10px; border-color: #eee;'>", unsafe_allow_html=True)
        
        for target in targets:
            # Case-insensitive match for connections
            existing_conn = next((c for c in current_profile.get("connections", []) if c["target"].lower() == target.lower()), None)
            
            c1, c2, c3 = st.columns([2, 5, 1])
            
            # Label
            target_profile = next((p for p in profiles if p["name"] == target), None)
            target_emoji = "🌐" if target == "public" else "👤" if target == "User" else (target_profile.get("emoji", "🤖") if target_profile else "🤖")
            c1.markdown(f"{target_emoji} **{target}**")
            
            default_ctx = existing_conn.get("context", "") if existing_conn else ""
            default_auth = existing_conn.get("authorized", True) if existing_conn else False
            
            # Unique key with selected_name and target
            ctx = c2.text_area(f"Condition for {target}", default_ctx, key=f"conn_ctx_{selected_name}_{target}", label_visibility="collapsed", height=68)
            auth = c3.checkbox(f"Active for {target}", default_auth, key=f"conn_auth_{selected_name}_{target}", label_visibility="collapsed")
            
            if auth or ctx:
                new_connections.append({"target": target, "context": ctx, "authorized": auth})
            st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)
        
        if st.button("💾 Save Changes", type="primary"):
            current_profile["name"] = new_name
            current_profile["display_name"] = disp
            current_profile["description"] = new_desc
            current_profile["system_prompt"] = new_prompt
            current_profile["capabilities"] = new_caps
            current_profile["connections"] = new_connections
            
            # Use the emoji from session state
            emoji_key = f"editing_emoji_{selected_name}"
            if emoji_key in st.session_state:
                current_profile["emoji"] = st.session_state[emoji_key]
                del st.session_state[emoji_key]
            
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

# ==========================================
# PAGE: NOTES (Memory & Backlog)
# ==========================================
elif st.session_state.page == "Notes":
    st.header("📝 Notes & Memory")
    
    # Tabs for different data sources
    tab_memory, tab_backlog = st.tabs(["🧠 Agent Memory", "📋 Backlog"])
    
    with tab_memory:
        st.subheader("Agent Memories")
        
        # Scan for memory files
        if MEMORY_DIR.exists():
            memory_files = sorted(list(MEMORY_DIR.glob("*.md")))
        else:
            memory_files = []
            
        if not memory_files:
            st.info("No memory files found yet.")
        else:
            # Selector
            # Filenames are typically "AgentName.md"
            options = [f.stem for f in memory_files]
            selected_agent = st.selectbox("Select Agent", options)
            
            if selected_agent:
                selected_file = MEMORY_DIR / f"{selected_agent}.md"
                if selected_file.exists():
                    content = selected_file.read_text(encoding="utf-8")
                    st.markdown(f"### {selected_agent}'s Memory")
                    st.markdown("---")
                    st.markdown(content)
                    
                    st.markdown("---")
                    st.caption(f"Path: {selected_file}")
    
    with tab_backlog:
        st.subheader("Project Backlog")
        
        # Check for BACKLOG.md at root
        backlog_path = EXECUTION_DIR / "BACKLOG.md"
        
        if backlog_path.exists():
            content = backlog_path.read_text(encoding="utf-8")
            st.markdown(content)
        else:
            st.warning("No BACKLOG.md found in the project root.")
            if st.button("Create Default BACKLOG.md"):
                default_content = "# Project Backlog\n\n- [ ] Initial Task"
                with open(backlog_path, "w") as f:
                    f.write(default_content)
                st.rerun()

# ==========================================
# PAGE: STREAMLIT (Agents Shared Dashboard)
# ==========================================
elif st.session_state.page == "Streamlit":
    st.header("📊 Agents Dashboard (Beta)")
    
    streamlit_path = EXECUTION_DIR / "mamcp-streamlit"
    
    # 1. Add to sys.path if needed
    if str(streamlit_path) not in sys.path:
        sys.path.append(str(streamlit_path))
        
    # 2. Try identifying the entry point
    # Priority: app.py > main.py > dashboard.py > __init__.py
    candidates = ["app.py", "main.py", "dashboard.py", "__init__.py"]
    entry_file = None
    for c in candidates:
        if (streamlit_path / c).exists():
            entry_file = c
            break
            
    if not entry_file:
        st.warning(f"Directory `mamcp-streamlit` found, but no entry file ({', '.join(candidates)}) detected.")
    else:
        module_name = entry_file.replace(".py", "")
        # We might need to handle package imports differently if it's __init__
        if entry_file == "__init__.py":
            module_name = "mamcp-streamlit" # simplistic approach
            
        try:
            # We use a trick to force reload to see changes without restarting main app
            # But standard streamlit reload watch might not catch external files unless watched
            
            # Allow import from that directory specifically
            # Note: Since we appended sys.path, we can import module_name directly IF it is unique
            # Use importlib
            
            # If the module is already loaded, reload it to get fresh code
            if module_name in sys.modules:
                module = importlib.reload(sys.modules[module_name])
            else:
                module = importlib.import_module(module_name)
                
            # If the module has a main() function, run it? 
            # Or just importing it runs the script (Standard streamlit behavior usually requires running script directly)
            
            # Since we are importing, the code at top level runs.
            # If the code is inside `if __name__ == "__main__":` it WON'T run.
            # So we check for a main() function and call it.
            
            if hasattr(module, "main"):
                module.main()
            else:
                # If no main() and no top-level side effects (unlikely for proper streamlit app), show info
                pass
                
        except Exception as e:
            st.error(f"Error loading Streamlit module during execution.")
            st.exception(e)


# --- GLOBAL INJECTION (Fixed by Anais) ---
if st.session_state.page == "Communication":
    # Ensure mentions are injected even if logic flow was broken
    active_names = [name for name in agents.keys() if agents[name].get("status") == "connected" and name != "User"]
    inject_mention_system(active_names)
