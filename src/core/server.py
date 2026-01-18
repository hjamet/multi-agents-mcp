import sys
import os
from pathlib import Path
from typing import List, Optional
import asyncio
import time
from jinja2 import Environment, FileSystemLoader
from mcp.server.fastmcp import FastMCP, Context

# Add project root to sys.path to allow 'src' imports
ROOT_DIR = Path(__file__).parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.core.logic import Engine
from src.config import TEMPLATE_DIR, MEMORY_DIR, EXECUTION_DIR, STOP_INSTRUCTION, RELOAD_INSTRUCTION, NOTE_RESPONSE, LOCAL_DATA_DIR
from src.services.search_engine import SearchEngine


# Initialize
mcp = FastMCP("MultiAgent-Hub", dependencies=["portalocker", "streamlit", "jinja2"])
engine = Engine()


# Truncation Buffer Global
# Map: agent_name -> {"content": str, "offset": int}
TRUNCATION_BUFFER = {}

def _truncate_and_buffer(agent_name: str, content: str, state: dict) -> str:
    """
    Truncates content if it exceeds the limit in config.
    Stores the full content in TRUNCATION_BUFFER for retrieval via mailbox.
    """
    truncation_limit = state.get("config", {}).get("truncation_limit", 4096)
    
    limit = truncation_limit
    
    if limit <= 0 or len(content) <= limit:
        # Clear buffer if it existed (clean state)
        if agent_name in TRUNCATION_BUFFER:
            del TRUNCATION_BUFFER[agent_name]
        return content
    
    # Determine Language for Instruction (to calculate overhead)
    lang = state.get("config", {}).get("language", "English")
    if lang in ["fr", "French"]:
        template = "\n\n🚨 [CRITIQUE : MESSAGE TRONQUÉ]\nLa fin de ce message a été coupée ({} caractères restants).\nVOUS DEVEZ OBLIGATOIREMENT appeler l'outil `mailbox(from_agent='{}` pour lire la suite."
    else:
        template = "\n\n🚨 [CRITICAL: MESSAGE TRUNCATED]\nThe end of this message was cutoff ({} chars remaining).\nYou MUST call the `mailbox(from_agent='{}')` tool to read the rest."

    # Calculate Overhead using a dummy number (7 digits safe for 10MB)
    # We want len(chunk) + len(msg) <= limit - 1
    
    dummy_overhead = len(template.format(9999999, agent_name))
    safe_chunk_size = limit - 1 - dummy_overhead
    
    if safe_chunk_size <= 0:
        # Edge case: Limit is too small for even the error message
        return content[:limit] # Just return what fits
    
    # Perform Truncation
    chunk = content[:safe_chunk_size]
    remaining = len(content) - safe_chunk_size
    
    # Final Message
    msg = template.format(remaining, agent_name)
    
    TRUNCATION_BUFFER[agent_name] = {
        "content": content,
        "offset": safe_chunk_size
    }
        
    return chunk + msg

# Logger Setup
from src.utils.logger import get_logger
logger = get_logger()


# Setup Templates
# Setup Templates
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

# --- SEARCH ENGINE SETUP ---
_SEARCH_ENGINE_INSTANCE = None
def _get_search_engine():
    global _SEARCH_ENGINE_INSTANCE
    if _SEARCH_ENGINE_INSTANCE is None:
        _SEARCH_ENGINE_INSTANCE = SearchEngine()
        persist = LOCAL_DATA_DIR / "vector_store"
        # Server is READ-ONLY (Streamlit handles watching)
        _SEARCH_ENGINE_INSTANCE.initialize(root_dir=ROOT_DIR, persist_dir=persist, watch=False)
    return _SEARCH_ENGINE_INSTANCE

def _get_search_context(state: dict, messages: List[dict]) -> str:
    """Helper to get relevant search context for talk."""
    try:
        conf = state.get("config", {}).get("search", {})
        x = conf.get("x_markdown", 2)
        y = conf.get("y_total", 5)
        
        if x == 0 and y == 0: return ""
        
        # Build query from last 3 messages
        query_parts = [m.get("content", "") for m in messages[-3:]]
        query = "\n".join(query_parts)
        
        if not query.strip(): return ""
        
        se = _get_search_engine()
        md, _ = se.get_relevant_context(query, max_markdown=x, max_total=y)
        return md
    except Exception as e:
        logger.error("System", f"Search Context Error: {e}")
        return ""



def _format_conversation_history(messages: List[dict], agent_name: Optional[str] = None) -> str:
    """
    Formats messages for context injection (XML).
    Logic: All unread messages + 1 previous (context anchor).
    """
    if not messages:
        return "(No messages yet)"
        
    start_index = 0
    if agent_name:
        # Find last message from me
        last_my_index = -1
        for i, m in enumerate(messages):
            if m.get("from") == agent_name:
                last_my_index = i
        
        if last_my_index != -1:
            # We want [last_my_index:] to include the last one I sent + subsequent
            start_index = max(0, last_my_index)
        else:
            # Never spoken? Show last 15 as fallback
            start_index = max(0, len(messages) - 15)
    else:
        # Fallback for generic calls
        start_index = max(0, len(messages) - 10)
        
    slice_msgs = messages[start_index:]
    
    # SECURITY PATCH: Hard limit of 20 unread messages (User Request)
    if len(slice_msgs) > 20:
        slice_msgs = slice_msgs[-20:]
    output = []
    
    for m in slice_msgs:
        sender = m.get("from", "Unknown")
        content = m.get("content", "")
        # Calculate Target for display
        target_display = "All"
        if not m.get("public"):
             target_display = m.get("target", "Unknown")
             
        # XML Format
        xml_msg = f"""<message>
    <from>{sender}</from>
    <to>{target_display}</to>
    <content>{content}</content>
</message>"""
        output.append(xml_msg)
        
    return "\n".join(output)


def _get_agent_connections(state, agent_name):
    """
    Resolve connections for an agent.
    Priority: Instance 'connections' > Profile 'connections'
    """
    connections = []
    try:
        agent_info = state["agents"].get(agent_name, {})
        
        # 1. Check Instance Level
        if "connections" in agent_info:
            return agent_info["connections"]
            
        # 2. Check Profile Level
        profile_ref = agent_info.get("profile_ref")
        profiles = state.get("config", {}).get("profiles", [])
        profile = next((p for p in profiles if p["name"] == profile_ref), None)
        
        if profile:
            return profile.get("connections", [])
            
    except Exception as e:
        logger.error("System", f"Error resolving connections for {agent_name}: {e}")
        
    return connections


def _get_latest_role(state, agent_name: str) -> str:
    """
    Fetches the most up-to-date system prompt for an agent.
    Priority: config.profiles[profile_ref].system_prompt > agents[agent_name].role
    """
    try:
        agent_info = state.get("agents", {}).get(agent_name, {})
        p_ref = agent_info.get("profile_ref")
        profiles = state.get("config", {}).get("profiles", [])

        # Find profile by name
        profile = next((p for p in profiles if p["name"] == p_ref), None)

        if profile and profile.get("system_prompt"):
            return profile["system_prompt"]

        # Fallback to the role stored in the agent's instance
        return agent_info.get("role", "Unknown Role")
    except Exception as e:
        logger.error("System", f"Error fetching latest role for {agent_name}: {e}")
        return "Unknown Role"

def _build_agent_directory(state, my_name):
    """
    Build a comprehensive list of all agents for the prompt.
    Includes only authorized connections.
    """
    directory = []
    
    # My Info
    my_info = state["agents"].get(my_name, {})
    my_profile_ref = my_info.get("profile_ref")
    profiles = state.get("config", {}).get("profiles", [])
    my_profile = next((p for p in profiles if p["name"] == my_profile_ref), {})
    my_caps = my_profile.get("capabilities", [])
    
    # My Connections (List of dicts {target, context, authorized})
    my_connections = _get_agent_connections(state, my_name)
    # Map target -> dict(context, authorized)
    conn_map = {c["target"]: c for c in my_connections if c.get("authorized", True)}
    
    # 1. SPECIAL: Public Entity
    if "public" in my_caps or "public" in conn_map:
        c_data = conn_map.get("public", {})
        directory.append({
            "name": "📢 PUBLIC",
            "public_desc": "All Agents",
            "note": c_data.get("context", "Public Announcement"),
            "authorized": True, 
            "status": "Authorized"
        })

    # 2. Real Agents
    all_agents = state.get("agents", {})
    
    # Identify authorized agents
    # We iterate over ALL agents and check if we match their ID or Profile in our conn_map
    for agent_id, info in all_agents.items():
        if agent_id == my_name:
            continue
            
        p_ref = info.get("profile_ref")
        
        # Check Authorization
        auth_context = None
        if agent_id in conn_map:
            auth_context = conn_map[agent_id].get("context", "")
        elif p_ref in conn_map:
            auth_context = conn_map[p_ref].get("context", "")
            
        if auth_context is not None:
            # Resolve Profile Data for description
            p_data = next((p for p in profiles if p["name"] == p_ref), {})
            display_name = agent_id
            public_desc = p_data.get("public_description") or p_data.get("description") or "Unknown"
            
            directory.append({
                "name": agent_id,
                "public_desc": public_desc,
                "note": auth_context,
                "authorized": True,
                "status": "✅ Authorized"
            })
    
    # 3. User
    if "User" in conn_map:
        directory.append({
            "name": "User",
            "public_desc": "Human Operator",
            "note": conn_map["User"].get("context", ""),
            "authorized": True,
            "status": "Authorized"
        })
        
    return directory

def _get_language_instruction_text(state: dict) -> str:
    """Helper to inject language instruction based on config."""
    # Default to French as requested by user context implies 'trimlits' interface defaults
    lang = state.get("config", {}).get("language", "fr") 
    if lang in ["fr", "French"]:
        return "INSTRUCTION SYSTÈME : Vous devez vous exprimer en Français."
    return "SYSTEM INSTRUCTION: You must speak in English."


def _get_backlog_instruction_text(state: dict) -> str:
    """Helper to inject backlog instruction based on config."""
    if state.get("config", {}).get("enable_backlog", False):
        return "⚠️ **IMPORTANT**: The Backlog is **ENABLED**. You MUST check `BACKLOG.md` at the end of every turn to keep it up to date. (Add new tasks, mark completed ones)."
    return ""




def _get_new_messages_notification(agent_name: str, messages: List[dict]) -> str:
    """
    Analyzes messages to count new ones since agent's last message.
    """
    last_my_index = -1
    for i, m in enumerate(messages):
        if m.get("from") == agent_name:
            last_my_index = i
            
    new_messages = messages[last_my_index + 1:]
    
    senders = set()
    count = 0
    for m in new_messages:
        sender = m.get("from")
        # Exclude System unless it's a real notification? No, user said "de Y, Z et W"
        if sender and sender != agent_name and sender != "System":
            # Map 'User' to 'l'utilisateur' if in French context? 
            # For now, just use the name.
            senders.add(sender)
            count += 1
            
    if count == 0:
        return f"No new messages. Review the Conversation History above to refresh your context."
    
    senders_list = sorted(list(senders))
    if len(senders_list) > 1:
        senders_str = ", ".join(senders_list[:-1]) + f" et {senders_list[-1]}"
    else:
        senders_str = senders_list[0]
        
    return f"CRITICAL: You have received {count} new messages from {senders_str}.\nMANDATORY PROTOCOL:\n1. READ the 'LATEST CONVERSATION HISTORY' section above carefully.\n2. If you need more context, you may use `read_file` on logs, but usually the last 10 messages are enough."


@mcp.tool()
async def agent(ctx: Context) -> str:
    """
    INITIALIZATION TOOL. Call this ONCE at the start.
    Assigns you a Role and Context automatically.
    """
    logger.log("INFO", "System", "New agent connecting...")
    result = engine.register_agent()
    
    if "error" in result:
        return f"ERROR: {result['error']}"
        
    name = result["name"]
    
    # Note: AGENT_SESSIONS is no longer used for identification to support multi-agent sessions (Cursor)
    # logger.log("INFO", "System", f"[{name}] Registered (Session {id(ctx.session)})")
    
    # Load state once
    state = engine.state.load()
    
    # helper to get directory
    agent_dir = _build_agent_directory(state, name)

    # BLOCKING: Wait for everyone before returning the initial prompt
    wait_msg = await engine.wait_for_all_agents_async(name)
    if wait_msg == "RELOAD_REQUIRED":
         return STOP_INSTRUCTION
    if wait_msg.startswith("TIMEOUT"):
         return wait_msg

    # BLOCKING: Wait for Turn (Strict Handshake)
    logger.log("INFO", name, "Network Ready. Waiting for Turn...")
    
    turn_messages = []
    instruction_text = ""
    
    while True:
        # Loop indefinitely until it is our turn
        turn_result = await engine.wait_for_turn_async(name, timeout_seconds=10)
        
        if turn_result["status"] == "success":
            # Acknowledge turn to reset interruption timer (Fix Ghost Bug)
            engine.acknowledge_turn(name)
            turn_messages = turn_result["messages"]
            instruction_text = turn_result["instruction"]
            break
            
        if turn_result["status"] == "reset":
            return f"⚠️ SYSTEM ALERT: {turn_result['instruction']}"
            
        # If timeout, we just loop again. (User requested: Never return until turn)
        # Using short timeout in wait_for_turn_async allows us to check for resets/signals more often
        continue

    template = jinja_env.get_template("agent_response.j2")
    
    # Get History for Context
    # Access state directly:
    visible_messages = []
    try:
        data = engine.state.load()
        full_messages = data.get("messages", [])
        # Simple filter: Public + targeted to me
        visible_messages = [m for m in full_messages if m.get("public") or m.get("target") == name or m.get("from") == name or name in (m.get("audience") or [])]
        
        # Smart Context Injection: REMOVED (Agent-Pull Model)
        # We now provide full history. Truncation logic removed.
        pass
    except Exception as e:
        logger.error(name, f"Error loading history: {e}")

    # Calculate Open Mode
    my_info = engine.state.load()['agents'].get(name, {})
    prof_ref = my_info.get("profile_ref")
    profiles = engine.state.load()['config']['profiles']
    my_prof = next((p for p in profiles if p["name"] == prof_ref), {})
    is_open_mode = "open" in my_prof.get("capabilities", [])

    # Prepare Context Data
    mem_content = _get_memory_content(name)
    if not mem_content: mem_content = "(No personal memory yet. Use `note()` to write one.)"
    
    conv_history_str = _format_conversation_history(visible_messages, name)

    # Calculate Notifications
    notification = _get_new_messages_notification(name, visible_messages)

    response = template.render(
        name=name,
        role=_get_latest_role(data, name),
        context=result["context"],
        agent_directory=agent_dir,
        connections=[d for d in agent_dir if d.get('authorized')],
        conversation_history=conv_history_str,
        memory_content=mem_content,
        is_open_mode=is_open_mode,
        language_instruction=_get_language_instruction_text(data),
        notification=notification,
        backlog_instruction=_get_backlog_instruction_text(data),
        search_results_markdown=_get_search_context(data, visible_messages),


    )
    return _truncate_and_buffer(name, response, data)

@mcp.tool()
async def talk(
    message: str,
    to: str,
    from_agent: str,  # <--- NEW MANDATORY ARGUMENT (Identity Assertion)
    ctx: Context,
    private: bool = False
) -> str:
    """
    MAIN COMMUNICATION TOOL.
    1. Posts your message.
    2. Passes the turn to 'to'.
    3. BLOCKS/SLEEPS until it is your turn again.
    
    Args:
        message: The content to speak.
        to: The name of the agent who should speak next. (The message is always visible to them).
        from_agent: YOUR IDENTITY. You must explicitly state who you are (e.g. "Software_Engineer").
        private: If true, ONLY 'to' sees the message. If false (default), everyone sees it.
    """
    try:
        # --- 1. STRICT TURN & IDENTITY VALIDATION (The "Source of Truth") ---
        # We no longer guess. We VALIDATE.
        
        # Poll briefly to ensure state is fresh (async race conditions)
        current_turn_holder = None
        for _ in range(3):
           state = engine.state.load()
           current_turn_holder = state.get("turn", {}).get("current")
           if current_turn_holder: break
           await asyncio.sleep(0.1)

        sender = from_agent
        
        # --- 0. EXISTENCE CHECK (Fix for Typos causing Infinite Loops) ---
        # If the agent name doesn't exist, we can't 'wait for its turn'.
        known_agents = state.get("agents", {})
        if sender != "User" and sender not in known_agents:
             # Helpful hint
             likely = [k for k in known_agents.keys() if sender in k]
             hint = f" Did you mean '{likely[0]}'?" if likely else ""
             return f"🚫 IDENTITY ERROR: Name '{sender}' not found in registry.{hint} You must use your EXACT registered name."
        
        # --- IDEMPOTENCY CHECK (Fix for Timeout/Retry) ---
        # Check if this is a retry of the very last successful action.
        # This handles cases where the client timed out waiting for the turn, but the message was posted.
        is_retry = False
        messages = state.get("messages", [])
        if messages:
            last_msg = messages[-1]
            # Check strictly if sender, content AND target match the last recorded message
            if (last_msg.get("from") == sender and 
                last_msg.get("content") == message and 
                last_msg.get("target") == to):
                is_retry = True
                if logger: logger.log("IDEMPOTENCY", sender, "Detected duplicate call (retry). Resuming wait logic.")

        # A. Identity/Turn Mismatch Check
        if sender != current_turn_holder and not is_retry:
            # 🚨 PROTOCOL VIOLATION DETECTED 🚨
            # Logic:
            # 1. Announce violation to chat (Public Shame / Debugging)
            # 2. PAUSE the offender (Blocking Wait) until it IS their turn.
            # 3. Resume with a warning.
            
            violation_msg = {
                "from": "System",
                "content": f"⚠️ **PROTOCOL VIOLATION**: Agent '{sender}' attempted to speak during '{current_turn_holder}'s turn. Action blocked and agent paused.",
                "public": True,
                "target": "all",
                "timestamp": time.time()
            }
            def log_violation(s):
                s.setdefault("messages", []).append(violation_msg)
                return "Violation Logged"
            engine.state.update(log_violation)
            
            if logger: logger.log("VIOLATION", sender, f"Spoke out of turn (Current: {current_turn_holder}). Pausing agent...")
            
            # BLOCKING REPAIR: Wait until it is actually my turn
            # This effectively "pauses" the agent in the `talk` call until the turn cycle comes back to them.
            wait_result = await engine.wait_for_turn_async(sender, timeout_seconds=600) # Long timeout
            
            if wait_result["status"] == "success":
                # Resumed!
                engine.acknowledge_turn(sender)
                return f"⚠️ **SYSTEM WARNING**: You attempted to speak out of turn and were paused. It is now correctly your turn. Review the conversation history with `tail -n 150 CONVERSATION.md` to see what happened while you were paused, then speak again."
            
            elif wait_result["status"] == "reset":
                 return f"⚠️ SYSTEM ALERT: {wait_result['instruction']}"
            else:
                 return "🚫 SYSTEM TIMEOUT: You were paused for speaking out of turn, but the turn never came back to you. Session timed out."

        # If we get here, Identity is Validated: sender == current_turn_holder
        
        # --- SECURITY: RELOAD ENFORCEMENT (Sprint 6 Fix) ---
        # If the agent is queued for reload, they MUST NOT speak.
        state = engine.state.load()
        sender_data = state.get("agents", {}).get(sender, {})
        
        if sender_data.get("reload_active"):
             logger.log("BLOCK", sender, "Blocked talk() due to reload_active=True")
             # Force them to quit immediately
             return RELOAD_INSTRUCTION

        next_agent = to

        # --- FEATURE: SELF-LOOP & ANTI-SPAM ---
        if next_agent == sender:
            # Check history for spam (Max 5 consecutive messages)
            data = engine.state.load()
            messages = data.get("messages", [])
            consecutive_count = 0
            for m in reversed(messages):
                if m.get("from") == sender:
                    consecutive_count += 1
                else:
                    break
            
            if consecutive_count >= 5:
                # Construct a helper directory for the error context
                try:
                     agent_directory = _build_agent_directory(data, sender)
                     connections_list = [d for d in agent_directory if d.get('authorized')]
                except:
                     connections_list = []
                     
                return f"🚫 ANTI-SPAM: You have reached the limit of 5 consecutive messages. You MUST yield the floor to another agent or the User.\n\nAvailable Connections: {', '.join([c['name'] for c in connections_list])}"
        
        # Logic Inversion
        is_public = not private

        if not is_retry:
            logger.log("ACTION", sender, f"talking -> {next_agent} (Public: {is_public})", {"message": message})
            
            # 1. Post Message
            post_result = engine.post_message(sender, message, is_public, next_agent)
            
            # Check for DENIED action
            if post_result.startswith("🚫"):
                if post_result.startswith("🚫 TARGET_NOT_FOUND:"):
                    target_tried = post_result.split(":", 1)[1].strip()
                    data = engine.state.load()
                    agent_dir = _build_agent_directory(data, sender)
                    connections_list = [d for d in agent_dir if d.get('authorized')]
                    
                    # Format a nice table-like list for the agent
                    dir_str = "\n".join([f"- **{c['name']}** ({c['public_desc']}): {c['note']}" for c in connections_list])
                    
                    error_msg = f"🚫 ACTION DENIED: Target agent '{target_tried}' does not exist.\n\n"
                    error_msg += "### 📋 YOUR AUTHORIZED CONNECTIONS:\n"
                    error_msg += "You must use the EXACT name from this list:\n"
                    error_msg += dir_str
                    error_msg += "\n\nAction rejected. You retain your turn. Please correct the 'to' argument and try again."
                    
                    if logger: logger.log("DENIED", "System", error_msg, {"target": sender})
                    return _truncate_and_buffer(sender, error_msg, engine.state.load())

                if logger: logger.log("DENIED", "System", post_result, {"target": sender})
                return post_result
                
            logger.log("SUCCESS", "System", f"Message posted: {post_result}")
        else:
             logger.log("SKIP", sender, "Skipped duplicate message post (retry detected).")
        
        # SPECIAL: User Turn Handling
        if next_agent == "User":
            is_user_available = False
            try:
                # Check availability config
                data = engine.state.load()
                config = data.get("config", {})
                # Default to 'busy' if not set, to be non-blocking by default
                is_user_available = (config.get("user_availability") == "available")
            except:
                pass

            # If Available, we BLOCK and wait for User Reply
            if is_user_available:
                logger.log("WAIT", "System", "User is AVAILABLE. Blocking wait for user reply...")
                
                wait_start = time.time()
                user_reply = None
                
                while True:
                    await asyncio.sleep(0.5)
                    
                    # Reload State
                    try:
                        data = engine.state.load()
                        messages = data.get("messages", [])
                        config = data.get("config", {})
                        
                        # 1. Critical Check: Did user switch to BUSY?
                        curr_avail = (config.get("user_availability") == "available")
                        if not curr_avail:
                            if logger: logger.log("WAIT_ABORT", "System", "User switched to BUSY. Aborting wait.")
                            break # Fallback to standard non-blocking response
                            
                        # 2. Check for Reset
                        new_cid = data.get("conversation_id")
                        # (Assuming capturing cid logic is similar to wait_for_turn, simplified here)
                        
                        # 3. Check for User Message
                        # Look for message FROM User where timestamp > wait_start
                        for m in reversed(messages):
                            if m.get("from") == "User" and m.get("timestamp", 0) > wait_start:
                                user_reply = m.get("content", "")
                                break
                        
                        if user_reply:
                            break
                            
                    except Exception as e:
                        logger.error("System", f"Error in user wait loop: {e}")
                        continue
                
                if user_reply:
                     # Prepare Template Render
                     try:
                        data = engine.state.load()
                        role_snippet = _get_latest_role(data, sender)
                        global_context = data.get("config", {}).get("context", "")
                        agent_directory = _build_agent_directory(data, sender)
                     except Exception as e:
                        logger.error(sender, f"Error loading state in talk (User Reply): {e}")
                        role_snippet = "Unknown"
                        global_context = ""
                        agent_directory = []

                     template = jinja_env.get_template("talk_response.j2")
                     
                     # Calculate Open Mode
                     is_open_mode = False
                     try:
                        my_info = data['agents'].get(sender, {})
                        prof_ref = my_info.get("profile_ref")
                        profiles = data['config']['profiles']
                        my_prof = next((p for p in profiles if p["name"] == prof_ref), {})
                        is_open_mode = "open" in my_prof.get("capabilities", [])
                     except: pass

                     # Combine Messages (Missed + User Reply)
                     # We need to construct the messages list carefully
                     # For simplicity, we just grab everything visible again or just the user reply
                     # But we need to maintain the 'start_turn_messages' logic if we want to be consistent
                     # Re-fetching visible messages is safer:
                     visible_msgs = [] # (Simplified logic for now to avoid complexity in this snippet)
                     # Actually, let's just use the user_reply as the instruction
                     
                     # Note: We need a valid 'messages' list for the template. 
                     # Let's re-fetch recent history
                     full_msgs = data.get("messages", []) # Full History (Agent-Pull)
                     visible_msgs = [m for m in full_msgs if m.get("public") or m.get("target") == sender or m.get("from") == sender or sender in (m.get("audience") or [])]
                     
                     # Prepare Context Data
                     mem_content = _get_memory_content(sender)
                     if not mem_content: mem_content = "(No personal memory yet. Use `note()` to write one.)"
                     
                     conv_history_str = _format_conversation_history(visible_msgs, sender)

                     # Calculate Notifications
                     notification = _get_new_messages_notification(sender, visible_msgs)

                     response = template.render(
                        name=sender,
                        role_snippet=role_snippet,
                        context=global_context,
                        agent_directory=agent_directory,
                        connections=[d for d in agent_directory if d.get('authorized')],
                        conversation_history=conv_history_str,
                        memory_content=mem_content,
                        is_open_mode=is_open_mode,
                        replied_to_message=message,  # <--- Context
                        language_instruction=_get_language_instruction_text(data),
                        notification=notification,
                        backlog_instruction=_get_backlog_instruction_text(data),
                        search_results_markdown=_get_search_context(data, visible_msgs),


                        instruction=f"✅ USER INTERCEPTION: The User replied: \"{user_reply}\". Your turn is back. READ THE CONVERSATION NOW."
                     )
                     return _truncate_and_buffer(sender, response, data)

            try:
                data = engine.state.load()
                role_snippet = _get_latest_role(data, sender)
                global_context = data.get("config", {}).get("context", "")
                agent_directory = _build_agent_directory(data, sender)
            except Exception as e:
                logger.error(sender, f"Error loading state in talk (User): {e}")
                role_snippet = "Unknown"
                global_context = ""
                agent_directory = []

            template = jinja_env.get_template("talk_response.j2")
            
            # User defined message:
            user_feedback_msg = "Message sent to User. They will reply when available. **CRITICAL: Review the 'LATEST CONVERSATION HISTORY' above to see if other agents spoke in the meantime.**"
            
            # Calculate Open Mode
            is_open_mode = False
            try:
                my_info = data['agents'].get(sender, {})
                prof_ref = my_info.get("profile_ref")
                profiles = data['config']['profiles']
                my_prof = next((p for p in profiles if p["name"] == prof_ref), {})
                is_open_mode = "open" in my_prof.get("capabilities", [])
            except: pass

            # Re-fetch recent messages
            full_msgs = data.get("messages", []) # Full History (Agent-Pull)
            visible_msgs = [m for m in full_msgs if m.get("public") or m.get("target") == sender or m.get("from") == sender or sender in (m.get("audience") or [])]

            # Prepare Context Data
            mem_content = _get_memory_content(sender)
            if not mem_content: mem_content = "(No personal memory yet. Use `note()` to write one.)"
            
            conv_history_str = _format_conversation_history(visible_msgs, sender)

            # Calculate Notifications
            notification = _get_new_messages_notification(sender, visible_msgs)

            rendered = template.render(
                name=sender,
                role_snippet=role_snippet,
                context=global_context,
                agent_directory=agent_directory,
                connections=[d for d in agent_directory if d.get('authorized')],
                conversation_history=conv_history_str,
                memory_content=mem_content,
                is_open_mode=is_open_mode,
                replied_to_message=message, # <--- Context
                language_instruction=_get_language_instruction_text(data),
                notification=notification,
                backlog_instruction=_get_backlog_instruction_text(data),
                search_results_markdown=_get_search_context(data, visible_msgs),


                instruction=f"✅ {user_feedback_msg}"
            )
            return _truncate_and_buffer(sender, rendered, data)

        # 2. Smart Block (Wait for Turn)
        # The turn has passed to next_agent. We now wait until it comes back to 'sender'.
        
        result = None
        while True:
            result = await engine.wait_for_turn_async(sender, timeout_seconds=10)
            
            if result["status"] == "success":
                engine.acknowledge_turn(sender)
                if logger: logger.log("TURN", sender, "It is my turn again.")
                break
                
            if result["status"] == "reset":
                return f"⚠️ SYSTEM ALERT: {result['instruction']}"
                
            # On timeout, loop again.
            continue
        
        # result is guaranteed to be success here
        if result["status"] == "reset":
            return f"⚠️ SYSTEM ALERT: {result['instruction']}"
        
        # Success - Render Template
        # Fetch Data
        role_snippet = "(Unknown Role)"
        global_context = ""
        agent_directory = []
        
        try:
            data = engine.state.load()
            role_snippet = _get_latest_role(data, sender)
            global_context = data.get("config", {}).get("context", "")
            agent_directory = _build_agent_directory(data, sender)
                
        except Exception as e:
            logger.error(sender, f"Error loading state in talk: {e}")
            pass

        template = jinja_env.get_template("talk_response.j2")
        # Calculate Open Mode
        is_open_mode = False
        try:
            my_info = data['agents'].get(sender, {})
            prof_ref = my_info.get("profile_ref")
            profiles = data['config']['profiles']
            my_prof = next((p for p in profiles if p["name"] == prof_ref), {})
            is_open_mode = "open" in my_prof.get("capabilities", [])
        except: pass
        
        # Write Context Files
        full_msgs = data.get("messages", []) # Full History (Agent-Pull)
        visible_msgs = [m for m in full_msgs if m.get("public") or m.get("target") == sender or m.get("from") == sender or sender in (m.get("audience") or [])]

        # Prepare Context Data
        mem_content = _get_memory_content(sender)
        if not mem_content: mem_content = "(No personal memory yet. Use `note()` to write one.)"
        
        conv_history_str = _format_conversation_history(visible_msgs)
        
        # Calculate Notifications
        notification = _get_new_messages_notification(sender, visible_msgs)

        response = template.render(
            name=sender,
            role_snippet=role_snippet,
            context=global_context,
            agent_directory=agent_directory,
            connections=[d for d in agent_directory if d.get('authorized')],
            conversation_history=conv_history_str,
            memory_content=mem_content,
            is_open_mode=is_open_mode,
            replied_to_message=message, # <--- Context
            language_instruction=_get_language_instruction_text(data),
            notification=notification,
            backlog_instruction=_get_backlog_instruction_text(data),
            search_results_markdown=_get_search_context(data, visible_msgs),


            instruction=result["instruction"]
        )
        return _truncate_and_buffer(sender, response, data)

    except Exception as e:
        # Logging
        logger.error("System", f"CRITICAL ERROR in talk: {e}", "crash_recovery")
        
        # Auto-Recovery
        if sender and sender != "User":
             try:
                def reset_status(s):
                    if sender in s.get("agents", {}):
                         s["agents"][sender]["status"] = "pending_connection"
                    return f"Reset {sender} to pending_connection"
                
                engine.state.update(reset_status)
                logger.log("RECOVERY", "System", f"Agent '{sender}' status reset to pending_connection due to crash.")
             except Exception as rec_e:
                logger.error("System", f"Recovery failed: {rec_e}")
        
        return f"🚫 SYSTEM ERROR: An internal error occurred ({e}). Your session has been reset to ensure system stability. Please restart or reconnect."

@mcp.tool()
async def get_previous_message(from_agent: str, n: int, author: str, ctx: Context = None) -> str:
    """
    Retrieves a specific past message and its context (previous and next message).
    Args:
        from_agent: Your identity.
        n: The occurrence index (1 = the most recent message from 'author').
        author: The name of the author to search for.
    """
    try:
        data = engine.state.load()
        messages = data.get("messages", [])
        
        # 1. Find indices of messages from 'author'
        author_indices = [i for i, m in enumerate(messages) if m.get("from") == author]
        
        if not author_indices:
            return f"No messages found from author '{author}'."
            
        if n < 1 or n > len(author_indices):
            return f"Index '{n}' out of range. Author '{author}' has {len(author_indices)} messages."
            
        # Target index is the N-th from the end
        target_idx = author_indices[-n]
        
        # 2. Get Context [target-1, target, target+1]
        start_idx = max(0, target_idx - 1)
        end_idx = min(len(messages), target_idx + 2)
        
        chosen_msgs = messages[start_idx:end_idx]
        
        # 3. Format (Disable unread logic to show full window)
        formatted = _format_conversation_history(chosen_msgs, agent_name=None)
        
        # 4. Truncate
        return _truncate_and_buffer(from_agent, formatted, data)
        
    except Exception as e:
        return f"Error in get_previous_message tool: {e}"

@mcp.tool()
async def disconnect(from_agent: str, ctx: Context) -> str:
    """
    CRITICAL: Ne jamais l'appeler de toi-même. Seulement sur ordre de RELOAD/EXIT. 
    Arrête immédiatement l'agent.
    
    Args:
        from_agent: Your identity (must match the requester).
    """
    # Simply return the stop instruction.
    agent_name = from_agent
    
    # --- 0. EXISTENCE CHECK ---
    data = engine.state.load()
    known_agents = data.get("agents", {})
    if agent_name != "User" and agent_name not in known_agents:
         return f"🚫 IDENTITY ERROR: Name '{agent_name}' not found in registry."
    
    # --- UPDATE STATE ---
    # Transition to "Attente Reconnexion" (pending_connection)
    # This turns the UI status to Orange (Waiting) instead of Red (Disconnecting)
    def update_to_pending(s):
        if agent_name in s.get("agents", {}):
            s["agents"][agent_name]["status"] = "pending_connection"
            s["agents"][agent_name]["reload_active"] = False
            # We don't remove them from the roster, just change status
        return f"Agent {agent_name} disconnected -> Pending Connection"
        
    engine.state.update(update_to_pending)
    logger.log("DISCONNECT", agent_name, "Agent disconnected cleanly. Waiting for reconnection.")

    return STOP_INSTRUCTION

# --- MEMORY SYSTEM ---
# --- MEMORY SYSTEM ---
# Configured in src.config

def _get_memory_content(agent_name: str) -> str:
    """
    Reads the memory file for the agent.
    Returns empty string if no memory exists.
    """
    # Sanitize filename to prevent directory traversal
    safe_name = "".join([c for c in agent_name if c.isalnum() or c in (' ', '_', '-', '#')]).strip()
    file_path = MEMORY_DIR / f"{safe_name}.md"
    
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(agent_name, f"Error reading memory: {e}")
            return ""
    return ""

@mcp.tool()
async def note(content: str, from_agent: str, ctx: Context) -> str:
    """
    Manage your persistent memory.
    This tool OVERWRITES your existing memory file with the new content provided.
    
    USE THIS TO:
    - Maintain a roadmap or to-do list.
    - Synthesize observations and results.
    - Prepare for future turns.
    
    IMPORTANT:
    - The content of this note is re-injected into your context at the start of every turn (via 'talk').
    - You must synthesize previous memories with new ones using a SUMMARY PRINCIPLE to integrate new memories while losing as little info as possible.
    - Do not just append blindly if you want to stay organized.
    - Maximum size: 5000 characters.
    
    Args:
        content: The text content to save.
        from_agent: YOUR IDENTITY. You must explicitly state who you are.
    """
    MAX_CHARS = 5000
    
    # --- Strict Turn/Identity Validation ---
    agent_name = from_agent
    
    # --- 0. EXISTENCE CHECK (Fix for Typos causing Infinite Loops) ---
    data = engine.state.load()
    known_agents = data.get("agents", {})
    if agent_name != "User" and agent_name not in known_agents:
         # Helpful hint
         likely = [k for k in known_agents.keys() if agent_name in k]
         hint = f" Did you mean '{likely[0]}'?" if likely else ""
         return f"🚫 IDENTITY ERROR: Name '{agent_name}' not found in registry.{hint} You must use your EXACT registered name."
    current_turn_holder = None
    try:
        data = engine.state.load()
        current_turn_holder = data.get("turn", {}).get("current")
    except:
        pass
        
    if agent_name != current_turn_holder:
         # Parallel Reload: Allow note() even if not their turn if reload_active is set
         if data.get("agents", {}).get(agent_name, {}).get("reload_active"):
             if logger: logger.log("RELOAD", agent_name, "Processing parallel reload note...")
         else:
             # Same auto-repair pause as talk()
             if logger: logger.log("VIOLATION", agent_name, f"Note() out of turn (Current: {current_turn_holder}). Pausing...")
             wait_result = await engine.wait_for_turn_async(agent_name, timeout_seconds=300)
             if wait_result["status"] != "success":
                 return "🚫 SYSTEM ERROR: You called note() out of turn and timed out waiting for your turn."
             # If success, proceed (they got the turn back)

    # 1. Validate Length
    if len(content) > MAX_CHARS:
        return f"🚫 ERROR: Note content too long ({len(content)} chars). Limit is {MAX_CHARS}. Please summarize and retry."
        
    # 2. Write File
    safe_name = "".join([c for c in agent_name if c.isalnum() or c in (' ', '_', '-', '#')]).strip()
    file_path = MEMORY_DIR / f"{safe_name}.md"
    
    # Read previous content for safety return
    old_content = "(No previous memory)"
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                old_content = f.read()
        except:
            old_content = "(Error reading previous memory)"
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        # Log
        logger.log("MEMORY", agent_name, "Updated memory note.")
        
        # --- PARALLEL RELOAD SUPPORTED ---
        # Agent can save note asynchronously during reload sequence.
        # The agent must now specifically call disconnect() after note().
        
        # Render Note Response Template
        response = jinja_env.from_string(NOTE_RESPONSE).render(
            agent_name=agent_name,
            old_content=old_content
        )
        return _truncate_and_buffer(agent_name, response, engine.state.load())
        
    except Exception as e:
        return f"🚫 SYSTEM ERROR writing note: {e}"



@mcp.tool()
async def mailbox(from_agent: str, ctx: Context) -> str:
    """
    Retrieves the remaining part of a truncated message.
    Only useful if you received a "CRITICAL: MESSAGE TRUNCATED" alert.
    
    Args:
        from_agent: Your identity (must match the truncated stream owner).
    """
    if from_agent not in TRUNCATION_BUFFER:
        return "📪 Mailbox empty. No truncated messages found."
        
    data_store = TRUNCATION_BUFFER[from_agent]
    full_content = data_store["content"]
    offset = data_store["offset"]
    
    state = engine.state.load()
    
    # Logic Refactor: Use unified truncation
    # we take the remaining content and treat it as a new stream to be truncated
    remaining_content = full_content[offset:]
    
    return _truncate_and_buffer(from_agent, remaining_content, state)

@mcp.tool()
async def search(query: str, from_agent: str, glob: str = None, ctx: Context = None) -> str:
    """
    Search the codebase using semantic vector search.
    Returns the most relevant code snippets.
    
    Args:
        query: The natural language query.
        from_agent: Your identity.
        glob: Optional glob pattern (e.g. "*.py", "src/*").
    """
    try:
        # Default limit from config if not specified
        se = _get_search_engine()
        state = engine.state.load()
        # Use Standard Default Y=15
        final_limit = state.get("config", {}).get("search", {}).get("y_total", 15)
        
        results = se.search(query, limit=final_limit, file_pattern=glob)
        
        if not results:
            return "No results found."
            
        output = [f"Found {len(results)} matches for '{query}' (Limit: {final_limit}):\n"]
        for r in results:
            output.append(f"--- {r['path']} (Lines {r['start_line']}-{r['end_line']}) ---")
            output.append(r['content'])
            output.append("--------------------------------------------------\n")
            
        full_response = "\n".join(output)
        return _truncate_and_buffer(from_agent, full_response, state)
    except Exception as e:
        return f"Error executing search: {e}"

if __name__ == "__main__":
    mcp.run()
